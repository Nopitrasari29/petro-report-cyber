# backend/app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Set

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_NAME: str = "AI Security Analysis & Reporting Platform"
    DEBUG: bool = True

    # Database — default SQLite untuk dev lokal, ganti ke Postgres lewat .env
    DATABASE_URL: str = "sqlite:///./sql_app.db"

    # Security / Auth (JWT)
    # TIDAK ada default — wajib diisi lewat .env, biar app nolak start kalau lupa di-set.
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440 # 24 jam untuk kenyamanan pengujian lokal

    # CORS — daftar origin frontend yang diizinkan (Lokal & IP 127.0.0.1)
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]

    # AI Engine (Local LLM)
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3:8b"

    @property
    def OLLAMA_BASE_URL(self) -> str:
        """Alias kompatibilitas jika ada modul yang memanggil OLLAMA_BASE_URL"""
        return self.OLLAMA_HOST

    # Storage
    UPLOAD_DIR: str = "storage/uploads"
    EXPORT_DIR: str = "storage/exports"

    # Upload constraints (Mendukung .csv, .json, .xlsx, .xls, dan .pdf)
    ALLOWED_EXTENSIONS: Set[str] = {".csv", ".json", ".xlsx", ".xls", ".pdf"}
    MAX_UPLOAD_SIZE_MB: int = 100

    # Ambang waktu proses analisis AI (detik) yang dianggap "SLA met" di dashboard/riwayat.
    SLA_THRESHOLD_SECONDS: int = 25

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""

    # SMTP Settings (Untuk Email Verifikasi & Reset Password)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_FROM_NAME: str = "AI Security Reports"


# Singleton — di-import di seluruh app biar konsisten, jangan bikin Settings() berulang
settings = Settings()