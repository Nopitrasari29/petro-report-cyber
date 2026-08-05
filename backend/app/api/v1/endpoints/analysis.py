# app/api/v1/endpoints/analysis.py
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db, SessionLocal
from app.core.config import settings
from app.api.v1.endpoints.auth import get_current_user
from app.services.ai_engine.ollama_client import ollama_client, _REQUIRED_KEY_DEFAULTS
from app.services.chart_generator import ChartGenerator
from app.crud.report import get_owned_report, update_report
from app.models.report import Report
from app.schemas.report import AnalysisProgress, ReportResponse, ReportUpdate
import time

router = APIRouter()

@router.get("/ping")
def ping():
    return {"message": "analysis module ready"}

@router.get("/ollama-status")
def get_ollama_status(current_user = Depends(get_current_user)):
    """
    RCA-12: Endpoint health check proaktif untuk memantau ketersediaan Ollama LLM
    tanpa perlu melakukan pemanggilan inference yang berat.
    """
    available = ollama_client.is_available()
    return {
        "status": "online" if available else "offline",
        "host": settings.OLLAMA_HOST,
        "model": settings.OLLAMA_MODEL,
        "available": available
    }

@router.get("/test-llm")
def test_llm(current_user = Depends(get_current_user)):
    """
    Endpoint uji koneksi ke Ollama. Diproteksi login supaya tidak disalahgunakan
    orang luar untuk membanjiri LLM lokal dengan request percuma.
    """
    result = ollama_client.generate(
        prompt="Sebutkan 3 komponen utama dalam laporan security bulanan.",
        system_prompt="Kamu adalah asisten analis keamanan siber."
    )
    return {"response": result}


def _expected_total_tokens(db: Session, user_id: int) -> int | None:
    """
    Rata-rata tokens_generated dari laporan user sendiri yang sudah pernah selesai dianalisis
    (10 terakhir) — jadi dasar "total pekerjaan" buat menghitung sisa waktu, persis seperti
    fetchEstimatedSeconds() di frontend memakai rata-rata processing_time_sec. User baru / belum
    ada riwayat token yang tercatat: kembalikan None, jangan menebak angka.
    """
    rows = (
        db.query(Report.tokens_generated)
        .filter(
            Report.user_id == user_id,
            Report.status == "analyzed",
            Report.tokens_generated.isnot(None),
            Report.tokens_generated > 0,
        )
        .order_by(Report.id.desc())
        .limit(10)
        .all()
    )
    values = [r[0] for r in rows]
    if not values:
        return None
    return round(sum(values) / len(values))


_ALL_REQUIRED_FIELDS = list(_REQUIRED_KEY_DEFAULTS.keys())


def _count_default_fields(result: dict) -> int:
    """
    Hitung berapa dari 6 field wajib yang isinya PERSIS teks default dari
    _normalize_json_keys (artinya: key itu tidak ketemu sama sekali di respons AI).
    "Gagal merumuskan ringkasan" dicek terpisah karena itu pesan error dari cabang
    exception di analyze_security_data, bukan dari _REQUIRED_KEY_DEFAULTS.
    """
    count = 0
    for key in _ALL_REQUIRED_FIELDS:
        val = result.get(key)
        default_val = _REQUIRED_KEY_DEFAULTS[key]
        if val == default_val or "Gagal merumuskan ringkasan" in str(val):
            count += 1
    return count


def _run_analysis_job(report_id: int) -> None:
    """
    Kerja generate AI yang sebenarnya, dijalankan di background (FastAPI BackgroundTasks) SETELAH
    endpoint pemicu sudah mengembalikan response — supaya endpoint tidak lagi memblokir selama
    3-10 menit dan frontend bisa polling progress token secara live lewat GET /{id}/progress.

    Sesi DB dibuat sendiri di sini (SessionLocal()) — TIDAK memakai sesi request pemicu, karena
    sesi itu sudah ditutup begitu response dikirim (lihat get_db()'s finally block).
    """
    db = SessionLocal()
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

            # Throttle penulisan DB supaya tidak commit tiap token (bisa >1x/detik) — kecuali
            # ini update TERAKHIR (done=True), yang harus selalu tersimpan (angka eval_count final).
            if not done and (now - last_write_at) < 1.5:
                return
            last_write_at = now
            db_report.tokens_generated = tokens_so_far
            db.commit()

        # PART A3 — deteksi jalur section dinamis (list, hasil pilihan user di Settings dari
        # usulan AI/A2) vs jalur lama (dict, checkbox preset 6-section tetap). None/dict = TIDAK
        # ADA perubahan perilaku sama sekali (persis seperti sebelum PART A — backward compat).
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

        # Fix #7: Auto-retry logic — coba ulang hingga 2x dengan delay 5 detik
        # sebelum menyerah dan menandai laporan sebagai "failed"
        MAX_RETRIES = 2
        analysis_result = None
        last_err = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                if attempt > 0:
                    print(f"[ANALYSIS] 🔄 Retry attempt {attempt}/{MAX_RETRIES} untuk report {report_id}...")
                    time.sleep(5)  # Tunggu 5 detik sebelum retry agar Ollama punya waktu recover
                    # Reset token counter untuk retry yang bersih
                    db_report.tokens_generated = 0
                    db.commit()

                # Fix #2: Baca parsed_data dari file system terlebih dahulu (jika path tersedia),
                # dengan fallback ke kolom JSON DB untuk laporan-laporan lama (backward compat).
                parsed_data_to_use = db_report.parsed_data  # fallback default
                if db_report.parsed_data_path:
                    try:
                        import json as _json
                        with open(db_report.parsed_data_path, "r", encoding="utf-8") as pf:
                            parsed_data_to_use = _json.load(pf)
                    except Exception as fs_read_err:
                        print(f"[ANALYSIS] ⚠️ Gagal baca parsed_data dari file ({db_report.parsed_data_path}), fallback ke DB column: {fs_read_err}")
                        parsed_data_to_use = db_report.parsed_data

                raw_result = ollama_client.analyze_security_data(
                    data_type=db_report.data_type,
                    parsed_data=parsed_data_to_use,
                    period_start=db_report.period_start.strftime("%Y-%m-%d") if db_report.period_start else None,
                    period_end=db_report.period_end.strftime("%Y-%m-%d") if db_report.period_end else None,
                    template_type=db_report.template_type,
                    language=db_report.language,
                    domain_type=db_report.domain_type,  # Domain AI (financial, kpi_hr, soc_security, general)
                    selected_sections=selected_sections,  # PART A3 — None = jalur lama, tidak berubah
                    tone=db_report.tone,  # Professional/Technical/Executive dari Report Settings
                    default_level=db_report.default_level,  # Standard/Detailed/Summary Only
                    on_progress=on_progress,
                )

                # RCA-04: Validasi bahwa respon AI benar-benar berupa dictionary valid
                if not isinstance(raw_result, dict):
                    raise ValueError("Respon dari AI Engine bukan berupa objek JSON/dictionary valid.")

                analysis_result = raw_result

                # Kalau setengah atau lebih dari 6 field wajib cuma teks default (artinya
                # AI tidak menjawab dengan key yang dikenali sama sekali), perlakukan
                # sebagai kegagalan attempt ini juga — trigger retry yang sudah ada di
                # bawah, bukan diam-diam ditandai "analyzed" padahal isinya kosong.
                default_hit_count = _count_default_fields(analysis_result)
                if default_hit_count >= 3:
                    raise RuntimeError(
                        f"AI mengembalikan {default_hit_count}/6 bagian berupa teks default "
                        f"(key tidak dikenali atau model gagal menjawab)."
                    )

                last_err = None
                break  # Sukses — keluar dari loop retry
            except Exception as ai_err:
                last_err = ai_err
                print(f"[ANALYSIS] ⚠️ Attempt {attempt + 1}/{MAX_RETRIES + 1} gagal untuk report {report_id}: {ai_err}")

        if last_err is not None or analysis_result is None:
            print(f"[ANALYSIS] ❌ Semua {MAX_RETRIES + 1} attempt gagal untuk report {report_id}. Marking as failed.")
            db_report.status = "failed"
            db.commit()
            try:
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
                print(f"[ANALYSIS] ⚠️ Gagal buat notifikasi failure: {notif_err}")
            return

        elapsed_time = round(time.time() - start_time)
        if elapsed_time <= 0:
            elapsed_time = 1

        sla_met_status = elapsed_time <= settings.SLA_THRESHOLD_SECONDS

        # Kalau lolos loop retry di atas, default_hit_count di sini sudah pasti < 3 (kalau >= 3
        # akan sudah diretry / berakhir "failed" duluan) — tapi 1-2 field default masih mungkin
        # lolos, jadi tetap diturunkan confidence-nya lewat _calc_confidence di bawah.
        is_fallback = _count_default_fields(analysis_result) >= 1

        # Fix #6: Kalkulasi ai_confidence secara DINAMIS berdasarkan kualitas output AI
        # (bukan nilai hardcoded 94.0 atau 95.0)
        def _calc_confidence(result: dict) -> float:
            if is_fallback:
                return 40.0
            score = 50.0
            # +15 jika semua 6 field ada dan non-empty
            all_fields = ["executive_summary", "trend_analysis", "severity_analysis",
                          "risk_assessment", "recommendations", "conclusion"]
            filled = sum(1 for k in all_fields if result.get(k) and len(str(result.get(k, ""))) > 20)
            score += (filled / len(all_fields)) * 25
            # +10 jika recommendations berisi >= 3 item
            recs = result.get("recommendations", [])
            if isinstance(recs, list) and len(recs) >= 3:
                score += 10
            # +10 jika executive_summary > 200 karakter (narasi substantif)
            exec_sum = result.get("executive_summary", "")
            if len(str(exec_sum)) > 200:
                score += 10
            # -15 jika ada field yang mengandung pesan error fallback
            error_phrases = ["tidak tersedia", "gagal", "error", "tidak dapat"]
            for k in all_fields:
                val = str(result.get(k, "")).lower()
                if any(p in val for p in error_phrases):
                    score -= 5
                    break
            return round(min(99.0, max(40.0, score)), 1)

        ai_confidence_score = _calc_confidence(analysis_result)

        chart_config = None
        if parsed_data_to_use and not db_report.chart_data:
            try:
                candidate_chart = ChartGenerator.generate_chart_config(
                    db_report.data_type,
                    parsed_data_to_use,
                )
                if candidate_chart and not candidate_chart.get("error") and candidate_chart.get("data"):
                    chart_config = candidate_chart
            except Exception as chart_err:
                print(f"[ANALYSIS] ⚠️ Gagal generate chart otomatis: {chart_err}")

        db_report.status = "analyzed"
        db_report.ai_summary = analysis_result
        db_report.ai_confidence = ai_confidence_score
        db_report.sla_met = sla_met_status
        db_report.processing_time_sec = elapsed_time
        if chart_config is not None:
            db_report.chart_data = chart_config
        db.commit()

        # Auto-trigger notification
        try:
            from app.schemas.notification import NotificationCreate
            from app.crud.notification import create_notification
            create_notification(
                db,
                NotificationCreate(
                    user_id=db_report.user_id,
                    type="success" if not is_fallback else "warning",
                    title="Report Generated",
                    message=f"Analisis AI untuk {db_report.filename or 'laporan'} telah selesai.",
                    link="/history"
                )
            )
        except Exception as notif_err:
            print(f"[ANALYSIS] ⚠️ Gagal buat notifikasi success: {notif_err}")
    finally:
        db.close()


@router.post("/generate/{report_id}", response_model=ReportResponse)
def generate_ai_analysis(
    report_id: int,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Memicu proses analisis keamanan AI menggunakan Ollama + Qwen secara dinamis.
    Hanya bisa dijalankan oleh pemilik laporan tersebut.

    Pekerjaan sebenarnya (panggilan Ollama yang bisa makan 3-10 menit) dijalankan di background
    lewat BackgroundTasks — endpoint ini langsung kembali dengan status="processing" begitu job
    dijadwalkan. Progress asli (token yang sudah dihasilkan) dipoll lewat GET /{report_id}/progress.
    """
    db_report = get_owned_report(db, report_id, current_user.id)
    if not db_report:
        raise HTTPException(status_code=404, detail="Data laporan tidak ditemukan.")

    if not db_report.parsed_data and not db_report.parsed_data_path:
        raise HTTPException(status_code=400, detail="Data laporan kosong atau belum di-parsing.")

    if db_report.status == "processing":
        raise HTTPException(status_code=429, detail="Proses analisis AI untuk laporan ini sedang berjalan di background. Silakan tunggu hingga selesai.")

    # RCA-08: Truly GLOBAL Rate Limiting — tolak jika ada laporan MANAPUN (siapapun usernya)
    # yang sedang diproses AI di server ini, untuk mencegah crash Ollama akibat request paralel.
    other_active_job = (
        db.query(Report)
        .filter(
            Report.status == "processing",
            Report.id != report_id,
        )
        .first()
    )
    if other_active_job:
        raise HTTPException(
            status_code=429,
            detail=f"Sistem sedang memproses analisis AI untuk laporan lain (ID: {other_active_job.id}). Mohon tunggu sebentar sebelum memulai analisis baru."
        )

    updated_report = update_report(
        db, report_id, ReportUpdate(status="processing", tokens_generated=0)
    )
    background_tasks.add_task(_run_analysis_job, report_id)
    return updated_report


@router.get("/{report_id}/progress", response_model=AnalysisProgress)
def get_analysis_progress(
    report_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Dipoll frontend tiap beberapa detik selama status="processing" — mengembalikan jumlah token
    yang sudah dihasilkan sejauh ini (live, dari background job) dan perkiraan total token
    (rata-rata riwayat laporan user). Frontend memakai dua angka ini untuk menghitung kecepatan
    generate token asli dan sisa waktu yang genuinely bereaksi terhadapnya — mirip ETA download.
    """
    db_report = get_owned_report(db, report_id, current_user.id)
    if not db_report:
        raise HTTPException(status_code=404, detail="Data laporan tidak ditemukan.")

    return AnalysisProgress(
        status=db_report.status,
        tokens_generated=db_report.tokens_generated or 0,
        expected_total_tokens=_expected_total_tokens(db, current_user.id),
    )

@router.put("/{report_id}", response_model=ReportResponse)
def update_report_analysis(
    report_id: int,
    report_update: ReportUpdate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Endpoint untuk fitur Preview & Edit (Step 4).
    Hanya bisa dilakukan oleh pemilik laporan tersebut.
    """
    db_report = get_owned_report(db, report_id, current_user.id)
    if not db_report:
        raise HTTPException(status_code=404, detail="Data laporan tidak ditemukan.")

    updated = update_report(db, report_id, report_update)
    return updated