# app/api/v1/endpoints/analysis.py
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db, SessionLocal
from app.core.config import settings
from app.api.v1.endpoints.auth import get_current_user
from app.services.ai_engine.ollama_client import ollama_client
from app.services.chart_generator import ChartGenerator
from app.crud.report import get_owned_report, update_report
from app.models.report import Report
from app.schemas.report import AnalysisProgress, ReportResponse, ReportUpdate
import time

router = APIRouter()

@router.get("/ping")
def ping():
    return {"message": "analysis module ready"}

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
            # Throttle penulisan DB supaya tidak commit tiap token (bisa >1x/detik) — kecuali
            # ini update TERAKHIR (done=True), yang harus selalu tersimpan (angka eval_count final).
            if not done and (now - last_write_at) < 1.5:
                return
            last_write_at = now
            db_report.tokens_generated = tokens_so_far
            db.commit()

        try:
            analysis_result = ollama_client.analyze_security_data(
                data_type=db_report.data_type,
                parsed_data=db_report.parsed_data,
                period_start=db_report.period_start.strftime("%Y-%m-%d") if db_report.period_start else None,
                period_end=db_report.period_end.strftime("%Y-%m-%d") if db_report.period_end else None,
                template_type=db_report.template_type,
                language=db_report.language,
                on_progress=on_progress,
            )
        except Exception as ai_err:
            print(f"[ANALYSIS] ⚠️ Job AI gagal tak terduga untuk report {report_id}: {ai_err}")
            db_report.status = "failed"
            db.commit()
            return

        elapsed_time = round(time.time() - start_time)
        if elapsed_time <= 0:
            elapsed_time = 1

        sla_met_status = elapsed_time <= settings.SLA_THRESHOLD_SECONDS

        # Ollama dipanggil lewat chat completion sederhana yang tidak mengembalikan
        # logprob/confidence per-token, dan tiap kegagalan (data kosong, Ollama offline,
        # parser error) langsung mengganti SEMUA 6 bagian ringkasan sekaligus dengan teks
        # fallback (lihat ollama_client.analyze_security_data) — jadi tidak ada kondisi
        # "sebagian berhasil". Karena itu sinyal yang jujur di sini cuma biner: analisis
        # betulan jalan, atau jatuh ke fallback. Nilai skor tetap dibuat untuk kebutuhan
        # tampilan/riwayat, tapi TIDAK dipura-purakan presisi (dulu ada bumbu
        # "word_count % 14" yang kesannya terukur padahal cuma noise kosmetik).
        is_fallback = "Gagal merumuskan ringkasan" in analysis_result.get("executive_summary", "")
        ai_confidence_score = 40.0 if is_fallback else 95.0

        chart_config = None
        if db_report.parsed_data and not db_report.chart_data:
            try:
                candidate_chart = ChartGenerator.generate_chart_config(
                    db_report.data_type,
                    db_report.parsed_data,
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

    if not db_report.parsed_data:
        raise HTTPException(status_code=400, detail="Data laporan kosong atau belum di-parsing.")

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