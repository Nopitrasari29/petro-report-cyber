from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.notification import Notification
from app.schemas.notification import NotificationCreate

def create_notification(db: Session, notification_in: NotificationCreate) -> Notification:
    db_notif = Notification(
        user_id=notification_in.user_id,
        type=notification_in.type,
        title=notification_in.title,
        message=notification_in.message,
        link=notification_in.link,
        is_read=False
    )
    db.add(db_notif)
    db.commit()
    db.refresh(db_notif)
    return db_notif

def cleanup_old_read_notifications(db: Session, max_age_days: int = 30) -> int:
    """
    RCA-B06: Membersihkan notifikasi yang sudah dibaca dan berusia lebih dari `max_age_days`.
    Dipanggil saat startup / background maintenance agar tabel notifications tidak bloat.
    """
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(days=max_age_days)
    deleted_count = (
        db.query(Notification)
        .filter(Notification.is_read == True, Notification.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted_count
