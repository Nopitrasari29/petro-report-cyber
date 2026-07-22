# app/api/v1/endpoints/analysis.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import settings
from app.api.v1.endpoints.auth import get_current_user
from app.services.ai_engine.ollama_client import ollama_client
from app.services.chart_generator import ChartGenerator
from app.crud.report import get_owned_report, update_report
from app.schemas.report import ReportResponse, ReportUpdate
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


@router.post("/generate/{report_id}", response_model=ReportResponse)
def generate_ai_analysis(
    report_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Memicu proses analisis keamanan AI menggunakan Ollama + Qwen secara dinamis.
    Hanya bisa dijalankan oleh pemilik laporan tersebut.
    """
    db_report = get_owned_report(db, report_id, current_user.id)
    if not db_report:
        raise HTTPException(status_code=404, detail="Data laporan tidak ditemukan.")

    if not db_report.parsed_data:
        raise HTTPException(status_code=400, detail="Data laporan kosong atau belum di-parsing.")

    start_time = time.time()
    update_report(db, report_id, ReportUpdate(status="processing"))

    analysis_result = None
    try:
        analysis_result = ollama_client.analyze_security_data(
            data_type=db_report.data_type,
            parsed_data=db_report.parsed_data,
            period_start=db_report.period_start.strftime("%Y-%m-%d") if db_report.period_start else None,
            period_end=db_report.period_end.strftime("%Y-%m-%d") if db_report.period_end else None,
            template_type=db_report.template_type,
            language=db_report.language
        )
    except Exception as ai_err:
        update_report(db, report_id, ReportUpdate(status="failed"))
        raise HTTPException(
            status_code=500,
            detail=f"AI Engine mengalami kegagalan pemrosesan data: {str(ai_err)}"
        )

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
            print(
                f"[ANALYSIS] ⚠️ Gagal generate chart otomatis: {chart_err}",
            )

    update_kwargs = {
        "status": "analyzed",
        "ai_summary": analysis_result,
        "ai_confidence": ai_confidence_score,
        "sla_met": sla_met_status,
        "processing_time_sec": elapsed_time,
    }
    if chart_config is not None:
        update_kwargs["chart_data"] = chart_config

    updated_report = update_report(db, report_id, ReportUpdate(**update_kwargs))

    return updated_report

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