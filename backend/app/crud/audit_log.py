# backend/app/crud/audit_log.py
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog


def log_action(
    db: Session,
    user_id: int | None,
    action: str,
    resource_type: str = "report",
    resource_id: int | None = None,
    detail: str | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """
    Fix #9: Helper untuk mencatat aksi audit ke database.
    Dipanggil dari endpoint mana pun yang melakukan aksi kritis.

    Args:
        db: SQLAlchemy session
        user_id: ID user yang melakukan aksi
        action: Nama aksi (mis. "upload", "analyze", "delete", "download_pdf")
        resource_type: Tipe resource (default: "report")
        resource_id: ID resource yang terlibat (mis. report_id)
        detail: Informasi tambahan (mis. judul laporan, jumlah item)
        ip_address: IP address user

    Returns:
        AuditLog object yang sudah disimpan ke DB
    """
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail,
        ip_address=ip_address,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
