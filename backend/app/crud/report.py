from sqlalchemy.orm import Session
from app.models.report import Report
from app.schemas.report import ReportCreate, ReportUpdate

def get_report(db: Session, report_id: int):
    return db.query(Report).filter(Report.id == report_id).first()

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

def update_report(db: Session, report_id: int, report_update: ReportUpdate):
    db_report = get_report(db, report_id)
    if not db_report:
        return None
    
    update_data = report_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_report, key, value)
        
    db.commit()
    db.refresh(db_report)
    return db_report

def delete_report(db: Session, report_id: int):
    db_report = get_report(db, report_id)
    if not db_report:
        return None
    db.delete(db_report)
    db.commit()
    return db_report