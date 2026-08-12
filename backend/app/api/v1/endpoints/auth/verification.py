import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import EmailStr, BaseModel
import secrets
from datetime import datetime, timedelta, timezone

from app.db.session import get_db
from app.core.rate_limit import rate_limiter
from app.crud.user import get_user_by_email
from app.models.user import User
from app.services.email import send_verification_email

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    """
    Verifikasi email pengguna menggunakan token.
    """
    logger.info(f"Mencoba verifikasi email dengan token: {token[:10]}...")
    user = db.query(User).filter(User.verification_token == token).first()
    if not user:
        logger.warning("Verifikasi gagal: token tidak ditemukan.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tautan verifikasi tidak valid atau tidak ditemukan."
        )

    if user.verification_token_expiry:
        expiry = user.verification_token_expiry
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if now > expiry:
            logger.warning("Verifikasi gagal: token telah kedaluwarsa.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tautan verifikasi telah kedaluwarsa. Silakan minta kirim ulang email verifikasi."
            )

    user.is_verified = True
    user.verification_token = None
    user.verification_token_expiry = None
    db.commit()
    logger.info(f"Verifikasi sukses: akun {user.email} diaktifkan.")
    return {"message": "Email berhasil diverifikasi! Anda sekarang dapat masuk."}

class ResendVerificationPayload(BaseModel):
    email: EmailStr

@router.post("/resend-verification")
async def resend_verification(payload: ResendVerificationPayload, db: Session = Depends(get_db)):
    """
    Mengirim ulang email verifikasi ke email pengguna.
    Dibatasi 3 percobaan per 15 menit per email, supaya tidak dipakai untuk email-bombing.
    """
    rate_limiter.check(key=f"resend-verification:{payload.email.lower()}", max_attempts=3, window_seconds=900)

    logger.info(f"Mencoba kirim ulang verifikasi: {payload.email}")
    user = get_user_by_email(db, email=payload.email)
    if not user:
        logger.info(f"Kirim ulang selesai (keamanan): email {payload.email} tidak ada.")
        return {"message": "Tautan verifikasi baru telah dikirim jika email terdaftar."}

    if user.is_verified:
        logger.info(f"Kirim ulang selesai: akun {payload.email} sudah terverifikasi.")
        return {"message": "Akun Anda sudah terverifikasi."}

    token = secrets.token_urlsafe(32)
    user.verification_token = token
    user.verification_token_expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=24)
    db.commit()

    try:
        await send_verification_email(email=user.email, token=token)
    except Exception as e:
        logger.error(f"Gagal mengirim ulang email verifikasi: {str(e)}")

    logger.info(f"Tautan verifikasi baru dikirim/dicetak untuk: {user.email}")
    return {"message": "Tautan verifikasi baru telah dikirim. Silakan periksa email Anda."}
