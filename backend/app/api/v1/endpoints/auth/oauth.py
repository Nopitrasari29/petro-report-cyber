import logging

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

logger = logging.getLogger(__name__)
router = APIRouter()

class GoogleLoginPayload(BaseModel):
    token: str

@router.post("/google-login", response_model=Token)
def google_login(payload: GoogleLoginPayload, db: Session = Depends(get_db)):
    """
    Login menggunakan Google OAuth. Mendaftarkan user secara otomatis jika email belum terdaftar di database.
    """
    logger.info("Mencoba Google Sign-In...")
    try:
        client_id = settings.GOOGLE_CLIENT_ID
        logger.debug(f"Memvalidasi token Google dengan Client ID: {client_id}")
        id_info = id_token.verify_oauth2_token(
            payload.token,
            requests.Request(),
            client_id
        )

        email = id_info.get("email")
        name = id_info.get("name", "")
        picture = id_info.get("picture", "")

        logger.info(f"Token Google valid. Email: {email}, Nama: {name}")

        if not email:
            logger.warning("Google Sign-In gagal: email tidak tersedia di payload Google.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Akun Google Anda tidak menyertakan email publik."
            )

        user = get_user_by_email(db, email=email)
        if not user:
            logger.info(f"Email {email} belum terdaftar. Mendaftarkan akun baru via Google OAuth...")
            username = email.split("@")[0]
            user = create_user_oauth(
                db,
                email=email,
                username=username,
                full_name=name,
                avatar_url=picture
            )
            logger.info(f"Akun baru berhasil didaftarkan: {user.username}")
        else:
            logger.info(f"User terdaftar ditemukan di DB: {user.username}")
            # Sinkronkan foto profil dari Google setiap login, KECUALI user sudah pernah
            # upload foto sendiri secara manual (disimpan sebagai string Base64 "data:...",
            # beda dari URL Google yang selalu "https://...") — supaya foto Google yang
            # diganti user ikut ter-update di sini, tanpa menimpa foto custom yang sengaja
            # di-upload lewat halaman Settings.
            current_avatar = user.avatar_url or ""
            if picture and not current_avatar.startswith("data:"):
                user.avatar_url = picture
                db.commit()
                db.refresh(user)

        if not user.is_active:
            logger.warning(f"Google Sign-In gagal: akun {email} dinonaktifkan.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Akun ini telah dinonaktifkan. Hubungi administrator."
            )

        access_token = create_access_token(data={"sub": user.username})
        logger.info(f"Google Sign-In berhasil: {user.email}")
        return {"access_token": access_token, "token_type": "bearer"}

    except ValueError as ve:
        logger.warning(f"Google Sign-In gagal (ValueError): {str(ve)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google ID Token tidak valid atau kedaluwarsa: {str(ve)}"
        )
    except Exception as e:
        logger.error(f"Google Sign-In gagal (Exception): {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sistem gagal melakukan login Google: {str(e)}"
        )
