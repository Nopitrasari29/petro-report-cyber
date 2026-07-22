from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import EmailStr, BaseModel, Field
import secrets
from datetime import datetime, timedelta, timezone

from app.db.session import get_db
from app.core.security import get_password_hash
from app.core.rate_limit import rate_limiter
from app.crud.user import get_user_by_email
from app.models.user import User

router = APIRouter()

# ANSI Color Codes
G  = "\033[92m"   # Green
Y  = "\033[93m"   # Yellow
C  = "\033[96m"   # Cyan
R  = "\033[0m"    # Reset
RED = "\033[91m"  # Red

class ForgotPasswordPayload(BaseModel):
    email: EmailStr

@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordPayload, db: Session = Depends(get_db)):
    """
    Meminta link reset password untuk email yang didaftarkan.
    Dibatasi 3 percobaan per 15 menit per email, supaya tidak dipakai untuk email-bombing
    (spam email reset ke satu korban terus-menerus).
    """
    rate_limiter.check(key=f"forgot-password:{payload.email.lower()}", max_attempts=3, window_seconds=900)

    print(f"\n[AUTH] 🔑 {C}Permintaan Lupa Sandi untuk:{R} {payload.email}")
    user = get_user_by_email(db, email=payload.email)
    if not user:
        print(f"[AUTH] ⚠️ {Y}Lupa sandi selesai (keamanan): Email {payload.email} tidak ada.{R}\n")
        return {"message": "Instruksi reset kata sandi telah dikirim jika email terdaftar."}
        
    token = secrets.token_urlsafe(32)
    user.reset_password_token = token
    user.reset_password_token_expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
    db.commit()
    
    try:
        from app.services.email import send_reset_password_email
        await send_reset_password_email(email=user.email, token=token)
    except Exception as e:
        import logging
        logging.getLogger("app").error(f"Gagal mengirim email reset password: {str(e)}")
        
    print(f"[AUTH] ✅ {G}Link reset sandi dikirim/dicetak untuk:{R} {user.email}\n")
    return {"message": "Instruksi reset kata sandi telah dikirim. Silakan periksa email Anda."}

class ResetPasswordPayload(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=72)

@router.post("/reset-password")
def reset_password(payload: ResetPasswordPayload, db: Session = Depends(get_db)):
    """
    Mereset password user menggunakan token reset yang dikirim ke email.
    """
    print(f"\n[AUTH] 🔑 {C}Mencoba memperbarui kata sandi dengan token:{R} {payload.token[:10]}...")
    user = db.query(User).filter(User.reset_password_token == payload.token).first()
    if not user:
        print(f"[AUTH] ❌ {RED}Reset gagal: Token tidak ditemukan.{R}\n")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tautan reset kata sandi tidak valid atau tidak ditemukan."
        )
        
    if user.reset_password_token_expiry:
        expiry = user.reset_password_token_expiry
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if now > expiry:
            print(f"[AUTH] ❌ {RED}Reset gagal: Token telah kedaluwarsa.{R}\n")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tautan reset kata sandi telah kedaluwarsa."
              )
            
    user.hashed_password = get_password_hash(payload.password)
    user.reset_password_token = None
    user.reset_password_token_expiry = None
    db.commit()
    print(f"[AUTH] ✅ {G}Reset sukses: Kata sandi untuk {user.email} diperbarui.{R}\n")
    return {"message": "Kata sandi berhasil diperbarui! Silakan masuk dengan kata sandi baru Anda."}