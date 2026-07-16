# backend/app/api/v1/endpoints/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import jwt, JWTError
import secrets
from datetime import datetime, timedelta, timezone
from pydantic import EmailStr, Field

from app.db.session import get_db
from app.core.config import settings
from app.core.security import verify_password, create_access_token, get_password_hash
from app.crud.user import create_user, get_user_by_username, get_user_by_email
from app.schemas.user import UserCreate, UserResponse, Token, TokenData, LoginPayload
from app.models.user import User
from app.services.email import send_verification_email

router = APIRouter()

# Setup OAuth2 flow untuk validasi token di Swagger UI
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ── ANSI Color Codes ──────────────────────────────────────────────
G  = "\033[92m"   # Green
Y  = "\033[93m"   # Yellow
C  = "\033[96m"   # Cyan
W  = "\033[97m"   # White
DIM = "\033[2m"   # Dim
R  = "\033[0m"    # Reset
RED = "\033[91m"  # Red


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Dependency untuk memvalidasi token JWT dan mengembalikan data User saat ini.
    Dipakai di endpoint lain yang butuh proteksi login (Depends(get_current_user)).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token akses tidak valid atau telah kedaluwarsa.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = get_user_by_username(db, username=token_data.username)
    if user is None:
        raise credentials_exception

    # Proteksi keamanan: akun yang dinonaktifkan tidak boleh lolos walau token valid
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun ini telah dinonaktifkan. Hubungi administrator.",
        )

    return user


@router.get("/ping")
def ping():
    return {"message": "auth module ready"}


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Mendaftarkan user baru ke database dan memicu pengiriman email verifikasi.
    """
    print(f"\n[AUTH] 🔵 {C}Mencoba registrasi manual:{R} {user_in.email}")
    db_email = get_user_by_email(db, email=user_in.email)
    if db_email:
        print(f"[AUTH] ❌ {RED}Registrasi gagal: Email '{user_in.email}' sudah terdaftar.{R}\n")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email sudah digunakan.",
        )

    # 1. Daftarkan user
    new_user = create_user(db, user_in)
    print(f"[AUTH] 👤 {G}User berhasil dibuat:{R} ID={new_user.id}, Username={new_user.username}")
    
    # 2. Buat token verifikasi dengan format penulisan tanggal seragam (tz-naive UTC)
    token = secrets.token_urlsafe(32)
    new_user.is_verified = False
    new_user.verification_token = token
    new_user.verification_token_expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=24)
    
    db.commit()
    db.refresh(new_user)
    
    # 3. Kirim email verifikasi
    try:
        await send_verification_email(email=new_user.email, token=token)
    except Exception as e:
        import logging
        logging.getLogger("app").error(f"Gagal mengirim email verifikasi: {str(e)}")

    print(f"[AUTH] ✅ {G}Registrasi selesai & Link verifikasi dicetak.{R}\n")
    return new_user


@router.post("/login", response_model=Token)
def login(payload: LoginPayload, db: Session = Depends(get_db)):
    """
    Login user, mengembalikan token akses JWT jika kredensial valid dan email terverifikasi.
    """
    print(f"\n[AUTH] 🔑 {C}Mencoba login manual:{R} {payload.email}")
    user = get_user_by_email(db, email=payload.email)

    if not user or not verify_password(payload.password, user.hashed_password):
        print(f"[AUTH] ❌ {RED}Login gagal: Email/password salah untuk {payload.email}{R}\n")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email atau password salah.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        print(f"[AUTH] ❌ {RED}Login gagal: Akun {payload.email} dinonaktifkan.{R}\n")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun ini telah dinonaktifkan. Hubungi administrator.",
        )

    # Pengecekan verifikasi email sebelum login diberikan
    if not user.is_verified:
        print(f"[AUTH] ⚠️ {Y}Login gagal: Akun {payload.email} belum memverifikasi email.{R}\n")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email Anda belum diverifikasi. Silakan periksa kotak masuk atau folder spam Anda.",
        )

    access_token = create_access_token(data={"sub": user.username})
    print(f"[AUTH] ✅ {G}Login berhasil:{R} {user.email} (Username: {user.username})\n")
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def read_current_user(current_user=Depends(get_current_user)):
    """
    Mendapatkan profil user yang sedang login (berdasarkan token JWT di header).
    """
    return current_user


# ── GOOGLE OAUTH2 INTEGRATION ───────────────────────────────────

from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests

class GoogleLoginPayload(BaseModel):
    token: str

@router.post("/google-login", response_model=Token)
def google_login(payload: GoogleLoginPayload, db: Session = Depends(get_db)):
    """
    Login menggunakan Google OAuth. Mendaftarkan user secara otomatis jika email belum terdaftar di database.
    """
    print(f"\n[AUTH] 🌐 {C}Mencoba Google Sign-In...{R}")
    try:
        # 1. Validasi Google ID Token menggunakan client ID dari settings
        client_id = settings.GOOGLE_CLIENT_ID
        print(f"[AUTH] 🌐 Memvalidasi token Google dengan Client ID: {client_id}")
        id_info = id_token.verify_oauth2_token(
            payload.token,
            requests.Request(),
            client_id
        )
        
        email = id_info.get("email")
        name = id_info.get("name", "")
        picture = id_info.get("picture", "")
        
        print(f"[AUTH] 🌐 Token Google valid. Email: {email}, Nama: {name}")
        
        if not email:
            print(f"[AUTH] ❌ {RED}Google Sign-In gagal: Email tidak tersedia di payload Google.{R}\n")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Akun Google Anda tidak menyertakan email publik."
            )
            
        # 2. Cari / Daftarkan user baru di database
        user = get_user_by_email(db, email=email)
        if not user:
            print(f"[AUTH] 👤 Email {email} belum terdaftar. Mendaftarkan akun baru via Google OAuth...")
            username = email.split("@")[0]
            from app.crud.user import create_user_oauth
            user = create_user_oauth(
                db,
                email=email,
                username=username,
                full_name=name,
                avatar_url=picture
            )
            print(f"[AUTH] 👤 Akun baru berhasil didaftarkan: {user.username}")
        else:
            print(f"[AUTH] 👤 User terdaftar ditemukan di DB: {user.username}")
            
        # 3. Validasi status keaktifan user
        if not user.is_active:
            print(f"[AUTH] ❌ {RED}Google Sign-In gagal: Akun {email} dinonaktifkan.{R}\n")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Akun ini telah dinonaktifkan. Hubungi administrator."
            )
            
        # 4. Generate token JWT internal aplikasi
        access_token = create_access_token(data={"sub": user.username})
        print(f"[AUTH] ✅ {G}Google Sign-In berhasil:{R} {user.email}\n")
        return {"access_token": access_token, "token_type": "bearer"}
        
    except ValueError as ve:
        print(f"[AUTH] ❌ {RED}Google Sign-In gagal (ValueError): {str(ve)}{R}\n")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google ID Token tidak valid atau kedaluwarsa: {str(ve)}"
        )
    except Exception as e:
        print(f"[AUTH] ❌ {RED}Google Sign-In gagal (Exception): {str(e)}{R}\n")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sistem gagal melakukan login Google: {str(e)}"
        )


# ── EMAIL VERIFICATION & PASSWORD RESET ROUTERS ──────────────────

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


class ForgotPasswordPayload(BaseModel):
    email: EmailStr

@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordPayload, db: Session = Depends(get_db)):
    """
    Meminta link reset password untuk email yang didaftarkan.
    """
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