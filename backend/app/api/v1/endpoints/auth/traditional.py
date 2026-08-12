import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import secrets
from datetime import datetime, timedelta, timezone

from app.db.session import get_db
from app.core.security import verify_password, create_access_token
from app.core.rate_limit import rate_limiter
from app.crud.user import create_user, get_user_by_email
from app.schemas.user import UserCreate, UserResponse, Token, LoginPayload
from app.services.email import send_verification_email

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Mendaftarkan user baru ke database dan memicu pengiriman email verifikasi.
    Dibatasi 3 percobaan per 5 menit per email untuk mencegah penyalahgunaan.
    """
    rate_limiter.check(key=f"register:{user_in.email.lower()}", max_attempts=3, window_seconds=300)

    logger.info(f"Mencoba registrasi manual: {user_in.email}")
    db_email = get_user_by_email(db, email=user_in.email)
    if db_email:
        logger.warning(f"Registrasi gagal: email '{user_in.email}' sudah terdaftar.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email sudah digunakan.",
        )

    # 1. Daftarkan user
    new_user = create_user(db, user_in)
    logger.info(f"User berhasil dibuat: ID={new_user.id}, Username={new_user.username}")

    # 2. Buat token verifikasi dengan format penulisan tanggal seragam (tz-naive UTC)
    token = secrets.token_urlsafe(32)
    from app.core.config import settings
    if not settings.SMTP_HOST:
        new_user.is_verified = True
    else:
        new_user.is_verified = False
    new_user.verification_token = token
    new_user.verification_token_expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=24)

    db.commit()
    db.refresh(new_user)

    # 3. Kirim email verifikasi
    try:
        await send_verification_email(email=new_user.email, token=token)
    except Exception as e:
        logger.error(f"Gagal mengirim email verifikasi: {str(e)}")

    logger.info("Registrasi selesai & link verifikasi dikirim/dicetak.")
    return new_user

@router.post("/login", response_model=Token)
def login(payload: LoginPayload, db: Session = Depends(get_db)):
    """
    Login user, mengembalikan token akses JWT jika kredensial valid dan email terverifikasi.
    Dibatasi 5 percobaan per 5 menit per alamat email, untuk mencegah brute-force password.
    """
    rate_limiter.check(key=f"login:{payload.email.lower()}", max_attempts=5, window_seconds=300)

    logger.info(f"Mencoba login manual: {payload.email}")
    user = get_user_by_email(db, email=payload.email)

    if not user or not verify_password(payload.password, user.hashed_password):
        logger.warning(f"Login gagal: email/password salah untuk {payload.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email atau password salah.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        logger.warning(f"Login gagal: akun {payload.email} dinonaktifkan.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun ini telah dinonaktifkan. Hubungi administrator.",
        )

    # Pengecekan verifikasi email sebelum login diberikan
    if not user.is_verified:
        logger.warning(f"Login gagal: akun {payload.email} belum memverifikasi email.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email Anda belum diverifikasi. Silakan periksa kotak masuk atau folder spam Anda.",
        )

    access_token = create_access_token(data={"sub": user.username})
    logger.info(f"Login berhasil: {user.email} (username: {user.username})")
    return {"access_token": access_token, "token_type": "bearer"}
