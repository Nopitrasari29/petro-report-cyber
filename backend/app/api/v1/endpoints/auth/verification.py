from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import EmailStr, BaseModel
import secrets
from datetime import datetime, timedelta, timezone

from app.db.session import get_db
from app.crud.user import get_user_by_email
from app.models.user import User
from app.services.email import send_verification_email

router = APIRouter()

# ANSI Color Codes
G  = "\033[92m"   # Green
Y  = "\033[93m"   # Yellow
C  = "\033[96m"   # Cyan
R  = "\033[0m"    # Reset
RED = "\033[91m"  # Red

@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    """
    Verifikasi email pengguna menggunakan token.
    """
    print(f"\n[AUTH] 📧 {C}Mencoba verifikasi email dengan token:{R} {token[:10]}...")
    user = db.query(User).filter(User.verification_token == token).first()
    if not user:
        print(f"[AUTH] ❌ {RED}Verifikasi gagal: Token tidak ditemukan.{R}\n")
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
            print(f"[AUTH] ❌ {RED}Verifikasi gagal: Token telah kedaluwarsa.{R}\n")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tautan verifikasi telah kedaluwarsa. Silakan minta kirim ulang email verifikasi."
            )
            
    user.is_verified = True
    user.verification_token = None
    user.verification_token_expiry = None
    db.commit()
    print(f"[AUTH] ✅ {G}Verifikasi sukses: Akun {user.email} diaktifkan.{R}\n")
    return {"message": "Email berhasil diverifikasi! Anda sekarang dapat masuk."}

class ResendVerificationPayload(BaseModel):
    email: EmailStr

@router.post("/resend-verification")
async def resend_verification(payload: ResendVerificationPayload, db: Session = Depends(get_db)):
    """
    Mengirim ulang email verifikasi ke email pengguna.
    """
    print(f"\n[AUTH] 📧 {C}Mencoba kirim ulang verifikasi:{R} {payload.email}")
    user = get_user_by_email(db, email=payload.email)
    if not user:
        print(f"[AUTH] ⚠️ {Y}Kirim ulang selesai (keamanan): Email {payload.email} tidak ada.{R}\n")
        return {"message": "Tautan verifikasi baru telah dikirim jika email terdaftar."}
        
    if user.is_verified:
        print(f"[AUTH] ⚠️ {Y}Kirim ulang selesai: Akun {payload.email} sudah terverifikasi.{R}\n")
        return {"message": "Akun Anda sudah terverifikasi."}
        
    token = secrets.token_urlsafe(32)
    user.verification_token = token
    user.verification_token_expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=24)
    db.commit()
    
    try:
        await send_verification_email(email=user.email, token=token)
    except Exception as e:
        import logging
        logging.getLogger("app").error(f"Gagal mengirim ulang email verifikasi: {str(e)}")
        
    print(f"[AUTH] ✅ {G}Tautan verifikasi baru dikirim/dicetak untuk:{R} {user.email}\n")
    return {"message": "Tautan verifikasi baru telah dikirim. Silakan periksa email Anda."}
