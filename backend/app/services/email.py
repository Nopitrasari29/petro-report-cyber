"""
app/services/email.py

SMTP dihapus — platform ini tidak menggunakan layanan email eksternal.

Fungsi-fungsi di sini diganti dengan logger-only fallback:
- Token verifikasi & reset password dicetak ke terminal (logger.info)
- Cocok untuk lingkungan internal (intranet) PT Petrokimia Gresik
- Tidak ada dependensi eksternal (fastapi-mail dihapus dari requirements.txt)
"""
import logging
from app.core.config import settings

logger = logging.getLogger("app.services.email")


async def send_verification_email(email: str, token: str):
    """
    Cetak tautan verifikasi email ke log terminal.
    (SMTP dihapus — platform internal tidak memerlukan email eksternal)
    """
    link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    logger.info(f"[VERIFIKASI] Akun baru: {email} | Tautan: {link}")


async def send_reset_password_email(email: str, token: str):
    """
    Cetak tautan reset password ke log terminal.
    (SMTP dihapus — platform internal tidak memerlukan email eksternal)
    """
    link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    logger.info(f"[RESET PASSWORD] Permintaan dari: {email} | Tautan: {link}")
