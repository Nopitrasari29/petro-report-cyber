# backend/app/models/audit_log.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from app.db.session import Base


class AuditLog(Base):
    """
    Fix #9: Audit Log System
    Mencatat setiap aksi kritis yang dilakukan pengguna terhadap laporan.
    Digunakan untuk investigasi forensik jika terjadi insiden data di dalam tim IT Petro.
    """
    __tablename__ = "audit_logs"
    # RCA-C01: Index komposit untuk query forensik yang umum dilakukan:
    # - Semua aktivitas user X dalam rentang waktu tertentu
    # - Semua aksi "delete" atau "download_pdf" hari ini (untuk monitoring)
    __table_args__ = (
        Index("idx_audit_user_created", "user_id", "created_at"),
        Index("idx_audit_action_created", "action", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Aksi yang dilakukan: "upload", "analyze", "delete", "bulk_delete",
    #                       "download_pdf", "download_pptx", "retry_analysis", "edit_report"
    action = Column(String, nullable=False)

    # Tipe resource yang terlibat: "report", "file"
    resource_type = Column(String, nullable=True, default="report")

    # ID spesifik resource (report_id, dll.)
    resource_id = Column(Integer, nullable=True)

    # Detail tambahan (mis. nama file, judul laporan, jumlah item yang dihapus)
    detail = Column(String, nullable=True)

    # IP address pengguna saat aksi dilakukan
    ip_address = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
