import logging
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from app.core.config import settings

logger = logging.getLogger("app.services.email")

def get_mail_config() -> ConnectionConfig | None:
    """
    Mengembalikan konfigurasi SMTP jika diisi di .env.
    Jika kosong, mengembalikan None agar sistem menggunakan fallback terminal.
    """
    if not settings.SMTP_HOST or not settings.SMTP_USERNAME:
        return None
        
    return ConnectionConfig(
        MAIL_USERNAME=settings.SMTP_USERNAME,
        MAIL_PASSWORD=settings.SMTP_PASSWORD,
        MAIL_FROM=settings.SMTP_FROM or settings.SMTP_USERNAME,
        MAIL_PORT=settings.SMTP_PORT,
        MAIL_SERVER=settings.SMTP_HOST,
        MAIL_FROM_NAME=settings.SMTP_FROM_NAME,
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True
    )

def _get_base_email_html(title_text: str, body_text: str, button_label: str, link: str, validity_info: str) -> str:
    """
    Menghasilkan template HTML dasar email bermerek PT Petrokimia Gresik secara konsisten.
    """
    return f"""
    <html>
        <body style="font-family: 'Inter', sans-serif; background-color: #f6f9fc; padding: 40px 20px; margin: 0;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 16px; border: 1px solid #eef2f6; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
                <!-- Header -->
                <div style="background-color: #005c3a; padding: 32px; text-align: center;">
                    <h2 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 800; letter-spacing: -0.5px;">AI Security Reports</h2>
                    <p style="color: #e6f4ea; margin: 4px 0 0 0; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">PT Petrokimia Gresik</p>
                </div>
                <!-- Body -->
                <div style="padding: 40px 32px;">
                    <h3 style="color: #1a202c; margin: 0 0 16px 0; font-size: 20px; font-weight: 700;">{title_text}</h3>
                    <p style="color: #4a5568; font-size: 14px; line-height: 24px; margin: 0 0 32px 0;">
                        {body_text}
                    </p>
                    <div style="text-align: center; margin-bottom: 32px;">
                        <a href="{link}" style="display: inline-block; padding: 14px 32px; background-color: #005c3a; color: #ffffff; font-weight: 700; font-size: 14px; text-decoration: none; border-radius: 8px; box-shadow: 0 4px 6px rgba(0, 92, 58, 0.15); transition: background-color 0.2s;">
                            {button_label}
                        </a>
                    </div>
                    <p style="color: #718096; font-size: 12px; line-height: 20px; margin: 0 0 16px 0;">
                        {validity_info}
                    </p>
                    <p style="color: #005c3a; font-size: 12px; word-break: break-all; margin: 0;">
                        {link}
                    </p>
                </div>
                <!-- Footer -->
                <div style="background-color: #f7fafc; padding: 24px 32px; border-top: 1px solid #edf2f7; text-align: center;">
                    <p style="color: #a0aec0; font-size: 11px; margin: 0;">
                        Email ini dikirim secara otomatis oleh sistem keamanan AI Security Reports.<br>
                        Mohon untuk tidak membalas email ini.
                    </p>
                </div>
            </div>
        </body>
    </html>
    """

async def send_verification_email(email: str, token: str):
    """
    Mengirim email verifikasi akun. Jika SMTP kosong, dicetak ke terminal log.
    """
    link = f"http://localhost:3000/verify-email?token={token}"
    mail_config = get_mail_config()
    
    if not mail_config:
        # Fallback Mode - Cetak ke Terminal dengan gaya yang menonjol
        print("\n" + "📧 " * 20)
        print(" [EMAIL MOCK] VERIFIKASI EMAIL PENDAFTARAN")
        print(f" Ke Penerima : {email}")
        print(f" Tautan Aktif: {link}")
        print(" Silakan klik tautan di atas untuk memverifikasi akun Anda secara lokal.")
        print("📧 " * 20 + "\n")
        return
        
    html_content = _get_base_email_html(
        title_text="Konfirmasi Pendaftaran Akun Anda",
        body_text="Terima kasih telah mendaftar di platform AI Security Reports. Langkah terakhir untuk mengaktifkan akun Anda adalah dengan melakukan verifikasi email melalui tautan tombol di bawah ini:",
        button_label="Verifikasi Akun Saya",
        link=link,
        validity_info="Tautan ini hanya berlaku selama 24 jam. Jika tombol di atas tidak berfungsi, Anda juga dapat menyalin dan menempelkan tautan berikut ke browser Anda:"
    )
    
    message = MessageSchema(
        subject="[AI Security Reports] Konfirmasi Pendaftaran Akun Anda",
        recipients=[email],
        body=html_content,
        subtype=MessageType.html
    )
    
    fm = FastMail(mail_config)
    await fm.send_message(message)

async def send_reset_password_email(email: str, token: str):
    """
    Mengirim email reset password. Jika SMTP kosong, dicetak ke terminal log.
    """
    link = f"http://localhost:3000/reset-password?token={token}"
    mail_config = get_mail_config()
    
    if not mail_config:
        # Fallback Mode
        print("\n" + "🔑 " * 20)
        print(" [EMAIL MOCK] PERMINTAAN RESET PASSWORD")
        print(f" Ke Penerima : {email}")
        print(f" Tautan Aktif: {link}")
        print(" Silakan klik tautan di atas untuk mereset sandi Anda secara lokal.")
        print("🔑 " * 20 + "\n")
        return
        
    html_content = _get_base_email_html(
        title_text="Permintaan Reset Kata Sandi",
        body_text="Kami menerima permintaan untuk mereset kata sandi akun Anda. Jika Anda tidak melakukan permintaan ini, abaikan email ini. Jika Anda ingin melanjutkannya, silakan klik tombol di bawah ini:",
        button_label="Reset Kata Sandi",
        link=link,
        validity_info="Tautan reset ini hanya berlaku selama 1 jam. Jika Anda tidak dapat mengeklik tombol di atas, silakan salin tautan berikut ke browser:"
    )
    
    message = MessageSchema(
        subject="[AI Security Reports] Permintaan Reset Kata Sandi Akun",
        recipients=[email],
        body=html_content,
        subtype=MessageType.html
    )
    
    fm = FastMail(mail_config)
    await fm.send_message(message)
