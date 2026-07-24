# backend/app/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

Base = declarative_base()

connect_args = {}
engine_kwargs = {}

# ── KONFIGURASI KETAHANAN KONEKSI DATABASE (FAIL-SAFE) ──────────────────
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    connect_args["timeout"] = 30  # Memberi batas waktu tunggu 30 detik untuk mencegah SQLite file-lock
else:
    # Parameter kesehatan kolam koneksi PostgreSQL
    engine_kwargs["pool_pre_ping"] = True  # Otomatis mendeteksi & menyegarkan koneksi yang terputus/stale
    engine_kwargs["pool_recycle"] = 1800   # Menyegarkan koneksi setiap 30 menit
    engine_kwargs["pool_size"] = 10        # Kapasitas standar kolam koneksi
    engine_kwargs["max_overflow"] = 20     # Batas koneksi ekstra jika traffic tinggi

engine = create_engine(
    settings.DATABASE_URL, 
    connect_args=connect_args,
    **engine_kwargs
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    Dependency generator untuk menyediakan sesi database yang aman di FastAPI.
    Menjamin sesi selalu ditutup di blok 'finally' agar tidak terjadi kebocoran koneksi.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()