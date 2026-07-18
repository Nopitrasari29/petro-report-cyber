from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests

from app.db.session import get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.crud.user import get_user_by_email, create_user_oauth
from app.schemas.user import Token

router = APIRouter()

# ANSI Color Codes
G  = "\033[92m"   # Green
Y  = "\033[93m"   # Yellow
C  = "\033[96m"   # Cyan
R  = "\033[0m"    # Reset
RED = "\033[91m"  # Red

class GoogleLoginPayload(BaseModel):
    token: str

@router.post("/google-login", response_model=Token)
def google_login(payload: GoogleLoginPayload, db: Session = Depends(get_db)):
    """
    Login menggunakan Google OAuth. Mendaftarkan user secara otomatis jika email belum terdaftar di database.
    """
    print(f"\n[AUTH] 🌐 {C}Mencoba Google Sign-In...{R}")
    try:
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
            
        user = get_user_by_email(db, email=email)
        if not user:
            print(f"[AUTH] 👤 Email {email} belum terdaftar. Mendaftarkan akun baru via Google OAuth...")
            username = email.split("@")[0]
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
            
        if not user.is_active:
            print(f"[AUTH] ❌ {RED}Google Sign-In gagal: Akun {email} dinonaktifkan.{R}\n")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Akun ini telah dinonaktifkan. Hubungi administrator."
            )
            
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
