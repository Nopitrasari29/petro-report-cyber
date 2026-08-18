# app/services/analysis_runner.py
"""
RCA-B03: Modularisasi eksekusi AI background job.

Sebelumnya _run_analysis_job berada di dalam app/api/v1/endpoints/analysis.py dan
diimpor langsung secara privat oleh app/api/v1/endpoints/history.py (cross-endpoint dependency).
Sekarang fungsi ini menjadi service mandiri di app/services/analysis_runner.py dan diimpor
secara bersih oleh analysis.py dan history.py.
"""
import logging
import time
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.core.config import settings
from app.models.report import Report
from app.models.user import User
from app.services.ai_engine.ollama_client import ollama_client, _REQUIRED_KEY_DEFAULTS
from app.services.report_render_logic import pick_visual_style

logger = logging.getLogger(__name__)

_ALL_REQUIRED_FIELDS = list(_REQUIRED_KEY_DEFAULTS.keys())


def count_default_fields(result: dict) -> int:
    """
    Hitung berapa dari 6 field wajib yang isinya teks default dari _normalize_json_keys.
    """
    count = 0
    for key in _ALL_REQUIRED_FIELDS:
        val = result.get(key)
        default_val = _REQUIRED_KEY_DEFAULTS.get(key, "")
        if val == default_val or "Gagal merumuskan ringkasan" in str(val):
            count += 1
    return count


def run_analysis_job(report_id: int) -> None:
    """
    Kerja generate AI yang sebenarnya, dijalankan di background (FastAPI BackgroundTasks)
    SETELAH endpoint pemicu mengembalikan response.
    """
    db = SessionLocal()
    db_report = None
    try:
        db_report = db.query(Report).filter(Report.id == report_id).first()
        if not db_report:
            return

        start_time = time.time()
        last_write_at = 0.0

        def on_progress(tokens_so_far: int, done: bool = False) -> None:
            nonlocal last_write_at
            now = time.time()
            # RCA-06: Watchdog timeout jika total job berjalan lebih lama dari OLLAMA_TIMEOUT_SECONDS
            if (now - start_time) > settings.OLLAMA_TIMEOUT_SECONDS:
                raise TimeoutError(f"Waktu eksekusi job melebihi batas maksimum {settings.OLLAMA_TIMEOUT_SECONDS} detik.")

            # Throttle penulisan DB supaya tidak commit tiap token
            if not done and (now - last_write_at) < 1.5:
                return
            last_write_at = now
            db_report.tokens_generated = tokens_so_far
            db.commit()

        # Deteksi jalur section dinamis vs jalur lama
        selected_sections = None
        if isinstance(db_report.included_sections, list):
            selected_sections = sorted(
                [
                    {
                        "key": s.get("key") or s.get("id"),
                        "title": s.get("title"),
                        "description": s.get("description", ""),
                        "order": s.get("order", idx),
                    }
                    for idx, s in enumerate(db_report.included_sections)
                    if isinstance(s, dict) and s.get("enabled", True) and s.get("title")
                ],
                key=lambda s: s["order"],
            ) or None

        # Fix #7 + RCA-B04: Auto-retry logic dengan exponential-ish backoff
        MAX_RETRIES = 2
        _RETRY_DELAYS = [30, 90]
        analysis_result = None
        last_err = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                if attempt > 0:
                    delay = _RETRY_DELAYS[min(attempt - 1, len(_RETRY_DELAYS) - 1)]
                    logger.info(f"Retry attempt {attempt}/{MAX_RETRIES} untuk report {report_id} — menunggu {delay} detik...")
                    time.sleep(delay)
                    db_report.tokens_generated = 0
                    db.commit()

                # Fix #2: Baca parsed_data dari file system (fallback ke DB)
                parsed_data_to_use = db_report.parsed_data
                if db_report.parsed_data_path:
                    try:
                        import json as _json
                        with open(db_report.parsed_data_path, "r", encoding="utf-8") as pf:
                            parsed_data_to_use = _json.load(pf)
                    except Exception as fs_read_err:
                        logger.warning(f"Gagal baca parsed_data dari file ({db_report.parsed_data_path}): {fs_read_err}")
                        parsed_data_to_use = db_report.parsed_data

                raw_result = ollama_client.analyze_security_data(
                    data_type=db_report.data_type,
                    parsed_data=parsed_data_to_use,
                    period_start=db_report.period_start.strftime("%Y-%m-%d") if db_report.period_start else None,
                    period_end=db_report.period_end.strftime("%Y-%m-%d") if db_report.period_end else None,
                    template_type=db_report.template_type,
                    language=db_report.language,
                    domain_type=db_report.domain_type,
                    selected_sections=selected_sections,
                    tone=db_report.tone,
                    default_level=db_report.default_level,
                    on_progress=on_progress,
                )

                if not isinstance(raw_result, dict):
                    raise ValueError("Respon dari AI Engine bukan berupa objek JSON/dictionary valid.")

                analysis_result = raw_result

                default_hit_count = count_default_fields(analysis_result)
                if default_hit_count >= 3:
                    raise RuntimeError(
                        f"AI mengembalikan {default_hit_count}/6 bagian berupa teks default "
                        f"(key tidak dikenali atau model gagal menjawab)."
                    )

                last_err = None
                break
            except Exception as ai_err:
                last_err = ai_err
                logger.warning(f"Attempt {attempt + 1}/{MAX_RETRIES + 1} gagal untuk report {report_id}: {ai_err}")

        if last_err is not None or analysis_result is None:
            logger.error(f"Semua {MAX_RETRIES + 1} attempt gagal untuk report {report_id}. Marking as failed.")
            db_report.status = "failed"
            db.commit()
            try:
                owner = db.query(User).filter(User.id == db_report.user_id).first()
                if owner is None or owner.notify_report_failed:
                    from app.schemas.notification import NotificationCreate
                    from app.crud.notification import create_notification
                    create_notification(
                        db,
                        NotificationCreate(
                            user_id=db_report.user_id,
                            type="warning",
                            title="Analysis Failed",
                            message=f"Gagal memproses analisis setelah {MAX_RETRIES + 1} percobaan. Coba lagi atau periksa status Ollama.",
                            link="/history"
                        )
                    )
            except Exception as notif_err:
                logger.warning(f"Gagal buat notifikasi failure: {notif_err}")
            return

        elapsed_time = round(time.time() - start_time)
        if elapsed_time <= 0:
            elapsed_time = 1

        sla_met_status = elapsed_time <= settings.SLA_THRESHOLD_SECONDS
        is_fallback = count_default_fields(analysis_result) >= 1

        # Fix #6: Kalkulasi ai_confidence secara dinamis
        def _calc_confidence(result: dict) -> float:
            if is_fallback:
                return 40.0
            score = 50.0
            all_fields = ["executive_summary", "trend_analysis", "severity_analysis",
                          "risk_assessment", "recommendations", "conclusion"]
            filled = sum(1 for k in all_fields if result.get(k) and len(str(result.get(k, ""))) > 20)
            score += (filled / len(all_fields)) * 25
            recs = result.get("recommendations", [])
            if isinstance(recs, list) and len(recs) >= 3:
                score += 10
            exec_sum = result.get("executive_summary", "")
            if len(str(exec_sum)) > 200:
                score += 10
            error_phrases = ["tidak tersedia", "gagal", "error", "tidak dapat"]
            for k in all_fields:
                val = str(result.get(k, "")).lower()
                if any(p in val for p in error_phrases):
                    score -= 5
                    break
            return round(min(99.0, max(40.0, score)), 1)

        ai_confidence_score = _calc_confidence(analysis_result)

        db.refresh(db_report)
        if db_report.status != "processing":
            logger.info(
                f"Report {report_id} sudah bukan 'processing' lagi (jadi '{db_report.status}') — "
                "kemungkinan dibatalkan pengguna. Hasil analisis dibuang."
            )
            return

        db_report.status = "analyzed"
        db_report.ai_summary = analysis_result
        db_report.ai_confidence = ai_confidence_score
        db_report.sla_met = sla_met_status
        db_report.processing_time_sec = elapsed_time
        db_report.visual_style = pick_visual_style(db_report.style_preset)
        db.commit()

        # Notifikasi sukses
        try:
            owner = db.query(User).filter(User.id == db_report.user_id).first()
            if owner is None or owner.notify_report_success:
                from app.schemas.notification import NotificationCreate
                from app.crud.notification import create_notification
                create_notification(
                    db,
                    NotificationCreate(
                        user_id=db_report.user_id,
                        type="success" if not is_fallback else "warning",
                        title="Report Generated",
                        message=f"Analisis AI untuk {db_report.title or 'laporan'} telah selesai.",
                        link="/history"
                    )
                )
        except Exception as notif_err:
            logger.warning(f"Gagal buat notifikasi success: {notif_err}")
    except Exception as fatal_err:
        logger.error(f"[FATAL] Kesalahan tak terduga saat memproses report {report_id}: {fatal_err}", exc_info=True)
        try:
            if db_report is not None:
                db.rollback()
                db_report.status = "failed"
                db.commit()
        except Exception as recovery_err:
            logger.error(f"[FATAL] Gagal tandai report {report_id} sbg 'failed': {recovery_err}")
    finally:
        db.close()
