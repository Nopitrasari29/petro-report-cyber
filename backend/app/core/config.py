# backend/app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Set

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_NAME: str = "AI Security Analysis & Reporting Platform"
    # BUG DIPERBAIKI: setting ini ADA tapi sebelumnya tidak pernah benar-benar dibaca kode
    # manapun (dokumentasi API /docs & /redoc selalu aktif apa pun nilainya). Sekarang jadi
    # gerbang nyata (lihat main.py) — default TRUE (bukan False) SENGAJA, supaya perilaku
    # development lokal sekarang (tanpa DEBUG di .env) TIDAK berubah sama sekali. Begitu
    # deploy ke server produksi, set DEBUG=False eksplisit di .env server itu untuk mematikan
    # /docs & /redoc di sana — mengikuti pola sama seperti pengaturan produksi lain di file ini.
    DEBUG: bool = True

    # Alamat frontend yang sebenarnya diakses user (dipakai bikin link di email verifikasi/
    # reset password, lihat email.py) — SEBELUMNYA hardcode "localhost:3000" langsung di
    # email.py, jadi begitu aplikasi ini dipasang di server sungguhan, setiap link email
    # yang terkirim tetap mengarah ke localhost (tidak pernah bisa diakses user manapun).
    # Isi lewat .env begitu deploy ke server sungguhan.
    FRONTEND_URL: str = "http://localhost:3000"

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
    # Batas waktu tunggu respon Ollama (detik). Tanpa ini, request bisa nge-hang tanpa batas
    # kalau Ollama macet/kelamaan — analysis.py tidak punya proteksi timeout-nya sendiri.
    # Dikonfirmasi lewat tes langsung: generate laporan 6-section lengkap di hardware ini
    # genuinely butuh beberapa menit (bukan cuma masalah prompt/model) — 180s kepotong
    # sebelum selesai, jadi dinaikkan supaya proses yang sebenarnya SUKSES tidak dianggap gagal.
    # Dinaikkan lagi dari 600 -> 1200: diukur langsung di mesin CPU-only ini, model qwen3:8b
    # butuh ~111 detik HANYA untuk cold-load ke memori (sebelum token pertama sekalipun) kalau
    # sempat di-unload Ollama karena idle — 600s kadang tidak cukup lagi setelah menghitung
    # cold-load + prefill prompt besar + generate token sungguhan. Dipasangkan dengan
    # "keep_alive" di ollama_client.py (menahan model tetap di memori) supaya cold-load itu
    # sendiri jarang terjadi berulang, tapi timeout tetap dilonggarkan sebagai jaring pengaman.
    OLLAMA_TIMEOUT_SECONDS: int = 1200

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

    # RCA-C03: Ambang waktu proses analisis AI (detik) yang dianggap "SLA met" di dashboard/riwayat.
    # DINAIKKAN dari 300s (5 menit) ke 900s (15 menit) — diukur langsung: qwen3:8b di hardware
    # CPU-only ini butuh ~111 detik cold-load + prefill + generate, rata-rata job 6-section bisa
    # 8-15 menit total. SLA 5 menit hampir selalu GAGAL walau sistem bekerja normal, membuat
    # metrik ini menyesatkan manajemen. 15 menit lebih realistis untuk server CPU-only lokal.
    # Sesuaikan lagi ke nilai yang lebih rendah saat di-deploy ke server GPU/cloud.
    SLA_THRESHOLD_SECONDS: int = 900

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""


# Singleton — di-import di seluruh app biar konsisten, jangan bikin Settings() berulang
settings = Settings()