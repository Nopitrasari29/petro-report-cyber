import json
import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from app.models.report import Report
from app.schemas.report import ReportCreate, ReportUpdate

logger = logging.getLogger(__name__)

# Kunci global (lihat try_acquire_ai_lock) dulu HANYA bisa lepas lewat _run_analysis_job
# menandai status "analyzed"/"failed" sendiri di akhir kerjanya, atau lewat restart server
# manual (RCA-24 di main.py). Kalau job itu crash lewat jalur yang TIDAK tertangkap exception
# handler-nya (lihat catatan panjang di _run_analysis_job), status macet selamanya di
# "processing" dan mengunci SEMUA generate AI (laporan siapa pun) sampai server di-restart.
# Threshold ini jauh di bawah OLLAMA_TIMEOUT_SECONDS (20 menit/percobaan, sampai 3 percobaan)
# — job yang BENERAN masih hidup terus meng-update kolom `updated_at` tiap kali progres token
# baru masuk (biasanya tiap ~1.5 detik sekali proses generate mulai); mandek tanpa update SAMA
# SEKALI selama 10 menit penuh jauh lebih mungkin berarti proses sudah mati (bukan cuma lambat).
STALE_PROCESSING_THRESHOLD_SECONDS = 600


def _reap_stale_processing_reports(db: Session) -> None:
    """
    Pemulihan OTOMATIS (dicek setiap kali ada percobaan generate/retry AI baru) untuk laporan
    yang macet di status "processing" — sebelumnya satu-satunya pemulihan adalah restart server
    manual. Laporan macet ditandai "failed" di sini supaya kunci global langsung lepas.
    """
    now = datetime.now(timezone.utc)
    candidates = db.query(Report).filter(Report.status == "processing").all()
    reaped = False
    for r in candidates:
        updated = r.updated_at
        if updated is None:
            continue
        # SQLite tidak benar-benar menyimpan timezone (lihat pola yang sama di auth/password.py)
        # — kolom yang dibaca balik dari DB datang tanpa tzinfo, dianggap UTC.
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        if (now - updated).total_seconds() > STALE_PROCESSING_THRESHOLD_SECONDS:
            logger.warning(
                f"[STALE LOCK] Report {r.id} macet di status 'processing' sejak "
                f"{updated.isoformat()} tanpa progres — ditandai 'failed' otomatis."
            )
            r.status = "failed"
            reaped = True
    if reaped:
        db.commit()

def get_report(db: Session, report_id: int):
    return db.query(Report).filter(Report.id == report_id).first()

def get_parsed_data(db_report: Report) -> list:
    """
    Ambil data log yang sudah di-parse untuk sebuah laporan.

    Sejak Fix #2 (pemindahan parsed_data ke file system), kolom JSON parsed_data
    di DB dikosongkan setelah upload dan data sebenarnya disimpan di file lewat
    parsed_data_path — jadi baca dari file dulu, fallback ke kolom DB untuk
    laporan lama (dibuat sebelum Fix #2 ada).
    """
    if db_report.parsed_data_path:
        try:
            with open(db_report.parsed_data_path, "r", encoding="utf-8") as pf:
                return json.load(pf)
        except Exception:
            pass
    return db_report.parsed_data or []

def get_owned_report(db: Session, report_id: int, user_id: int):
    """
    Ambil laporan HANYA jika dimiliki oleh user_id yang diberikan.
    Dipakai di semua endpoint yang butuh proteksi kepemilikan data (anti-IDOR).
    Sengaja mengembalikan None (bukan raise 403) kalau laporan milik user lain,
    supaya endpoint di atasnya balas 404 — tidak membocorkan apakah ID itu eksis.
    """
    return (
        db.query(Report)
        .filter(Report.id == report_id, Report.user_id == user_id)
        .first()
    )

def get_reports_for_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return (
        db.query(Report)
        .filter(Report.user_id == user_id)
        .order_by(Report.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

def create_report(db: Session, report: ReportCreate, user_id: int | None = None):
    # Sengaja unpack SEMUA field dari ReportCreate secara otomatis (bukan daftar field manual
    # satu-satu seperti sebelumnya) — daftar manual itu ketinggalan menambahkan kolom baru
    # (threat_count_critical/high/medium/low/info, total_records_parsed) setiap kali skema
    # ditambah field baru, jadi nilai yang sudah dihitung di upload.py (mis. hasil count_threats())
    # diam-diam DIBUANG dan selalu jatuh ke default kolom (0/None) tiap kali laporan dibuat.
    # Semua field ReportCreate sudah dikonfirmasi cocok 1:1 dengan kolom Report.
    db_report = Report(**report.model_dump(), user_id=user_id)
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report

def try_acquire_ai_lock(db: Session, report_id: int) -> bool:
    """Tandai laporan ini "processing" HANYA KALAU tidak ada laporan lain (siapa pun usernya)
    yang statusnya sudah "processing" DAN laporan ini sendiri belum "processing" — satu
    pernyataan UPDATE tunggal (bukan SELECT untuk cek dulu, baru UPDATE terpisah belakangan)
    supaya celah waktu antara cek & tulis status collapse jadi nol. SQLite (DB proyek ini)
    men-serialize semua penulisan lewat satu file/koneksi, jadi UPDATE tunggal ini genuinely
    atomic di levelnya — dua request yang datang nyaris bersamaan tidak bisa dua-duanya lolos.

    Dipakai BERSAMA oleh endpoint generate (analysis.py) & retry (history.py) supaya keduanya
    patuh kunci global yang sama persis — sebelumnya retry_report_analysis sama sekali tidak
    mengecek kunci ini, jadi bisa memicu 2 job Ollama berjalan bersamaan (persis yang coba
    dicegah RCA-08 tapi cuma diterapkan di endpoint generate).

    Return True kalau kunci berhasil diambil (status sudah diubah ke "processing" oleh
    pemanggil ini) — False kalau ditolak (laporan ini atau laporan lain sudah "processing").
    """
    _reap_stale_processing_reports(db)
    updated_rows = (
        db.query(Report)
        .filter(
            Report.id == report_id,
            Report.status != "processing",
            ~db.query(Report.id)
            .filter(Report.status == "processing", Report.id != report_id)
            .exists(),
        )
        .update({"status": "processing", "tokens_generated": 0}, synchronize_session=False)
    )
    db.commit()
    return updated_rows > 0


def _delete_file_safely(file_path: str | None):
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            logger.error(f"[STORAGE CLEANUP] Gagal menghapus file '{file_path}': {e}")

def update_report(db: Session, report_id: int, report_update: ReportUpdate, user_id: int | None = None):
    """`user_id` opsional — pertahanan BERLAPIS (bukan satu-satunya), lihat catatan panjang di
    `delete_report` di bawah untuk alasan lengkapnya. Default None = perilaku lama, tidak ada
    perubahan untuk pemanggil yang sudah ada."""
    db_report = get_report(db, report_id)
    if not db_report:
        return None
    if user_id is not None and db_report.user_id != user_id:
        return None

    update_data = report_update.model_dump(exclude_unset=True)
    
    # RCA-02: Jika konten/pengaturan laporan berubah, hapus cache PDF & PPTX lama di disk
    # agar download berikutnya merender versi terbaru (bukan me-return file usang)
    invalidate_keys = {"ai_summary", "title", "header_title", "header_subtitle", "included_sections", "theme_color", "style_preset", "chart_data"}
    if any(k in update_data for k in invalidate_keys):
        _delete_file_safely(db_report.file_pdf_path)
        _delete_file_safely(db_report.file_ppt_path)
        db_report.file_pdf_path = None
        db_report.file_ppt_path = None

    for key, value in update_data.items():
        setattr(db_report, key, value)
        
    db.commit()
    db.refresh(db_report)
    return db_report

def delete_report(db: Session, report_id: int, user_id: int | None = None):
    """`user_id` opsional — pertahanan BERLAPIS di level fungsi CRUD itu sendiri, BUKAN
    pengganti pengecekan `get_owned_report` yang sudah dilakukan setiap pemanggil endpoint
    saat ini (yang sudah benar). Sebelumnya fungsi ini 100% percaya pemanggilnya sudah
    memverifikasi kepemilikan — aman selama SEMUA pemanggil ingat melakukannya, tapi endpoint
    BARU di masa depan yang lupa cek kepemilikan akan langsung jadi celah IDOR tanpa peringatan
    apa pun. Default None = perilaku lama (tidak ada perubahan untuk pemanggil yang sudah ada,
    yang semuanya sudah mengecek kepemilikan sebelum memanggil fungsi ini)."""
    db_report = get_report(db, report_id)
    if not db_report:
        return None
    if user_id is not None and db_report.user_id != user_id:
        return None

    # RCA-07: Hapus semua file fisik terkait di disk sebelum menghapus record dari DB
    _delete_file_safely(db_report.parsed_data_path)
    _delete_file_safely(db_report.file_pdf_path)
    _delete_file_safely(db_report.file_ppt_path)

    db.delete(db_report)
    db.commit()
    return db_report