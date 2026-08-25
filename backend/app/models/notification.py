# backend/app/models/notification.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from app.db.session import Base

class Notification(Base):
    __tablename__ = "notifications"
    # RCA-C05: Index komposit untuk query utama: notifikasi user yang belum dibaca,
    # diurutkan dari terbaru. Tanpa ini, semakin banyak notifikasi makin lambat querynya.
    __table_args__ = (
        Index("idx_notifications_user_read_created", "user_id", "is_read", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String, default="info")  # success, warning, info, error
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    link = Column(String, nullable=True, default="/history")
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
