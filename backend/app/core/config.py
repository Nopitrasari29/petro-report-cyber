from pydantic_settings import BaseSettings, SettingsConfigDict


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
    JWT_EXPIRE_MINUTES: int = 60

    # CORS — daftar origin frontend yang diizinkan. Default cuma localhost untuk dev;
    # isi lewat .env (format JSON array) kalau deploy ke domain lain, misal:
    # BACKEND_CORS_ORIGINS=["https://reports.petrokimia-gresik.internal"]
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # AI Engine (Local LLM)
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3:8b"

    # Storage
    UPLOAD_DIR: str = "storage/uploads"
    EXPORT_DIR: str = "storage/exports"

    # Upload constraints (Tier 1 — CSV, JSON, Excel)
    ALLOWED_EXTENSIONS: set[str] = {".csv", ".json", ".xlsx", ".xls"}
    MAX_UPLOAD_SIZE_MB: int = 25

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