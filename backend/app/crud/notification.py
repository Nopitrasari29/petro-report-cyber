from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.notification import Notification
from app.schemas.notification import NotificationCreate

def get_notifications_by_user(db: Session, user_id: int, limit: int = 50) -> List[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )

def count_unread_notifications(db: Session, user_id: int) -> int:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == False)
        .count()
    )

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

def mark_notification_as_read(db: Session, notification_id: int, user_id: int) -> Optional[Notification]:
    db_notif = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user_id)
        .first()
    )
    if db_notif:
        db_notif.is_read = True
        db.commit()
        db.refresh(db_notif)
    return db_notif

def mark_all_notifications_as_read(db: Session, user_id: int) -> int:
    updated_count = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == False)
        .update({"is_read": True}, synchronize_session=False)
    )
    db.commit()
    return updated_count
