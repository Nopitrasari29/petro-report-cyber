# app/api/v1/endpoints/analysis.py
import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import settings
from app.core.rate_limit import rate_limiter
from app.api.v1.endpoints.auth import get_current_user
from app.services.ai_engine.ollama_client import ollama_client
from app.services.analysis_runner import run_analysis_job
from app.crud.report import get_owned_report, update_report, try_acquire_ai_lock
from app.models.report import Report
from app.schemas.report import AnalysisProgress, ReportResponse, ReportUpdate, ReportUserEditableUpdate

logger = logging.getLogger(__name__)
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
    Endpoint uji koneksi ke Ollama. Diproteksi login & rate limit (maks 10 per menit)
    supaya tidak disalahgunakan untuk membanjiri LLM lokal dengan request percuma (RCA-A01).
    """
    rate_limiter.check(key=f"test-llm:{current_user.id}", max_attempts=10, window_seconds=60)
    result = ollama_client.generate(
        prompt="Sebutkan 3 komponen utama dalam laporan security bulanan.",
        system_prompt="Kamu adalah asisten analis keamanan siber."
    )
    return {"response": result}


def _expected_total_tokens(db: Session, user_id: int) -> int | None:
    """
    Rata-rata tokens_generated dari laporan user sendiri yang sudah pernah selesai dianalisis
    (10 terakhir) — jadi dasar "total pekerjaan" buat menghitung sisa waktu, persis seperti
    fetchEstimatedSeconds() di frontend memakai rata-rata processing_time_sec.
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

    # RCA-08 + fix race condition: kunci "1 proses AI per waktu di server" diambil lewat SATU
    # UPDATE atomik (try_acquire_ai_lock), BUKAN cek status dulu baru commit status baru belakangan
    # secara terpisah — pola lama itu ada celah waktu antara cek & tulis yang bisa ditembus 2
    # request nyaris bersamaan (dua-duanya lolos pengecekan sebelum salah satu sempat commit).
    if not try_acquire_ai_lock(db, report_id):
        db.refresh(db_report)
        if db_report.status == "processing":
            raise HTTPException(status_code=429, detail="Proses analisis AI untuk laporan ini sedang berjalan di background. Silakan tunggu hingga selesai.")
        other_active_job = (
            db.query(Report)
            .filter(Report.status == "processing", Report.id != report_id)
            .first()
        )
        raise HTTPException(
            status_code=429,
            detail=f"Sistem sedang memproses analisis AI untuk laporan lain (ID: {other_active_job.id if other_active_job else '?'}). Mohon tunggu sebentar sebelum memulai analisis baru."
        )

    # RCA-A01: Rate limit memicu analisis AI (maks 10 trigger per menit per user)
    rate_limiter.check(key=f"generate-analysis:{current_user.id}", max_attempts=10, window_seconds=60)

    db.refresh(db_report)
    background_tasks.add_task(run_analysis_job, report_id)

    # RCA-A02: Catat aksi trigger analisis AI ke audit log — sebelumnya endpoint ini
    # adalah satu-satunya aksi kritis yang TIDAK tercatat, padahal ini sumber utama
    # perubahan status laporan & penggunaan sumber daya server (Ollama inference).
    try:
        from app.crud.audit_log import log_action
        log_action(
            db, user_id=current_user.id, action="generate_analysis",
            resource_type="report", resource_id=report_id,
            detail=f"Analisis AI dipicu untuk laporan '{db_report.title}' (domain: {db_report.domain_type}, template: {db_report.template_type}).",
        )
    except Exception as audit_err:
        logger.warning(f"Gagal catat audit log generate_analysis: {audit_err}")

    return db_report


@router.post("/{report_id}/cancel", response_model=ReportResponse)
def cancel_analysis(
    report_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Tombol "Batalkan Proses" (Step 3) — dipanggil user SENGAJA saat mau berhenti menunggu &
    langsung mulai generate laporan lain, TANPA perlu menunggu job lama benar-benar selesai.

    TIDAK benar-benar menghentikan panggilan Ollama yang sedang berjalan di thread background
    (Python/library ollama yang dipakai di sini tidak punya cara aman untuk itu tanpa mengubah
    jadi koneksi streaming yang bisa diputus paksa) — tapi MELEPAS KUNCI GLOBAL SEKARANG JUGA
    (status jadi "failed") supaya user tidak perlu menunggu. Job lama yang masih jalan di
    background nanti kalau selesai akan mengecek dulu apakah statusnya masih "processing"
    sebelum menyimpan hasil (lihat catatan di _run_analysis_job) — karena sudah "failed" di
    sini, hasilnya otomatis dibuang, tidak menimpa balik pembatalan ini.
    """
    db_report = get_owned_report(db, report_id, current_user.id)
    if not db_report:
        raise HTTPException(status_code=404, detail="Data laporan tidak ditemukan.")
    if db_report.status != "processing":
        raise HTTPException(status_code=400, detail="Laporan ini sedang tidak diproses.")

    db_report.status = "failed"
    db.commit()
    db.refresh(db_report)
    logger.info(f"Report {report_id} dibatalkan oleh user {current_user.id}.")
    return db_report


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
    report_update: ReportUserEditableUpdate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Endpoint untuk fitur Preview & Edit (Step 4) — ganti judul & simpan hasil edit teks laporan.
    Hanya bisa dilakukan oleh pemilik laporan tersebut.

    Body dibatasi ke ReportUserEditableUpdate (title/ai_summary saja, lihat docstring-nya di
    schemas/report.py) SENGAJA, bukan ReportUpdate penuh — supaya field yang seharusnya cuma
    diisi sistem (status, ai_confidence, sla_met, dst — hasil analisis AI beneran) tidak bisa
    dipalsukan lewat endpoint yang menerima input user ini.
    """
    db_report = get_owned_report(db, report_id, current_user.id)
    if not db_report:
        raise HTTPException(status_code=404, detail="Data laporan tidak ditemukan.")

    updated = update_report(db, report_id, ReportUpdate(**report_update.model_dump(exclude_unset=True)), user_id=current_user.id)
    return updated