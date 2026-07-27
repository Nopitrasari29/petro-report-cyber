# backend/app/api/v1/endpoints/notifications.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.notification import Notification
from app.schemas.notification import NotificationResponse

router = APIRouter()

_PASSWORD_SETUP_TITLE = "Lengkapi Password Akun Anda"


@router.get("/", response_model=List[NotificationResponse])
def get_notifications(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mendapatkan seluruh daftar notifikasi milik user yang sedang terotentikasi.
    """
    # Akun daftar via Google yang belum pernah set password sendiri: pastikan ada notifikasi
    # pengingat di lonceng juga (bukan cuma popup) — dibuat sekali secara idempotent (dicek
    # duluan berdasar title supaya tidak duplikat tiap kali user buka notifikasi), dan otomatis
    # tidak dibuat lagi begitu current_user.password_set jadi True.
    if current_user.password_set is False:
        existing = db.query(Notification).filter(
            Notification.user_id == current_user.id,
            Notification.title == _PASSWORD_SETUP_TITLE,
        ).first()
        if not existing:
            db.add(Notification(
                user_id=current_user.id,
                type="warning",
                title=_PASSWORD_SETUP_TITLE,
                message="Akun Anda terdaftar via Google dan belum memiliki password sendiri. Atur password di halaman Settings agar bisa login lewat email & password biasa.",
                link="/settings?tab=account",
                is_read=False,
            ))
            db.commit()

    return db.query(Notification).filter(
        Notification.user_id == current_user.id
    ).order_by(Notification.created_at.desc()).limit(50).all()

@router.put("/read-all")
@router.put("/mark-read")
def mark_all_read(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Menandai seluruh notifikasi user sebagai 'is_read = True'.
    """
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).update({"is_read": True}, synchronize_session=False)
    db.commit()
    return {"status": "success", "message": "Seluruh notifikasi ditandai telah dibaca."}

@router.put("/{notification_id}/read")
def mark_single_read(
    notification_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Menandai notifikasi spesifik berdasarkan ID sebagai dibaca.
    """
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notifikasi tidak ditemukan.")
    notif.is_read = True
    db.commit()
    return {"status": "success", "message": "Notifikasi berhasil ditandai dibaca."}

@router.delete("/clear")
def clear_read_notifications(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Menghapus notifikasi yang sudah dibaca.
    """
    deleted_count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == True
    ).delete(synchronize_session=False)
    db.commit()
    return {"status": "success", "deleted_count": deleted_count}
