# app/main.py - updated

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.v1.router import api_router
from app.core.config import settings

# Konfigurasi logging APLIKASI (bukan pengganti print_banner() di bawah, yang memang
# dekorasi terminal murni saat startup) - sebelumnya semua log server (analisis AI, upload,
# auth, dst) pakai print() polos: tidak ada level (info/warning/error), tidak bisa difilter
# atau diarahkan ke file/monitoring terpisah dengan rapi begitu di-deploy ke produksi nanti.
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# BUG DIPERBAIKI (ditemukan langsung dari log terminal): basicConfig() di atas mengatur ROOT
# logger, yang otomatis diwarisi SEMUA logger termasuk punya library pihak ketiga (pdfminer,
# httpx/httpcore, urllib3, dst) - begitu DEBUG=True (default lokal sekarang), log internal
# library-library itu (detail parsing PDF per objek, detail koneksi HTTP per paket) ikut
# banjir ke terminal, menenggelamkan log APLIKASI sendiri yang sebenarnya mau dilihat.
# Dikunci ke WARNING supaya cuma masalah nyata dari library ini yang tetap tampil, terlepas
# dari level DEBUG aplikasi sendiri.
for _noisy_logger in ("pdfminer", "httpx", "httpcore", "urllib3", "PIL", "fontTools"):
    logging.getLogger(_noisy_logger).setLevel(logging.WARNING)

# ── ANSI Color Codes ──────────────────────────────────────────────
G  = "\033[92m"   # Green
Y  = "\033[93m"   # Yellow
C  = "\033[96m"   # Cyan
W  = "\033[97m"   # White
DIM = "\033[2m"   # Dim
R  = "\033[0m"    # Reset

def print_banner():
    try:
        print(f"""
{G}+----------------------------------------------------------+
|{W}       AI Security Reports — FastAPI Backend              {G}|
|{DIM}       PT Petrokimia Gresik · SOC Intelligence Platform    {G}|
+----------------------------------------------------------+
|  {C}API Docs  {R}->  {W}http://localhost:8000/docs                   {G}|
|  {C}Health   {R}->  {W}http://localhost:8000/health                  {G}|
|  {C}API Base {R}->  {W}http://localhost:8000/api/v1                  {G}|
+----------------------------------------------------------+
|  {Y}Database {R}->  {W}PostgreSQL @ localhost:5432                   {G}|
|  {Y}Auth     {R}->  {W}JWT + Google OAuth2                          {G}|
|  {Y}Email    {R}->  {W}SMTP (Fallback: Terminal Log Mode)            {G}|
+----------------------------------------------------------+{R}
""")
    except Exception:
        print("[STARTUP] AI Security Reports Backend running on http://localhost:8000")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from app.db.session import engine
    from app.db.base import Base
    try:
        Base.metadata.create_all(bind=engine)
        print(f"{G}[DB]{R} Database tables created or validated.")
        
        # RCA-24: Bersihkan status 'processing' yang terhenti akibat restart server
        from app.db.session import SessionLocal
        from app.models.report import Report
        db = SessionLocal()
        try:
            stuck_reports = db.query(Report).filter(Report.status == "processing").all()
            if stuck_reports:
                for r in stuck_reports:
                    r.status = "failed"
                db.commit()
                print(f"{Y}[RECOVERY]{R} {len(stuck_reports)} laporan yang terhenti akibat restart di-reset ke status 'failed'.")
        except Exception as rec_err:
            print(f"{Y}[RECOVERY WARNING]{R} Gagal reset status processing: {rec_err}")
        finally:
            db.close()
    except Exception as db_err:
        print(f"\033[91m[DB ERROR]\033[0m Gagal membuat tabel: {db_err}")
    print_banner()
    print(f"{G}[STARTUP]{R} Backend siap menerima request [OK]")
    print(f"{DIM}[INFO]{R}    Hot-reload aktif - perubahan kode otomatis ter-apply\n")
    yield
    # Shutdown
    print(f"\n{Y}[SHUTDOWN]{R} Backend sedang dimatikan...")

# BUG DIPERBAIKI: /docs & /redoc (Swagger UI, menampilkan SELURUH struktur API) dulu selalu
# aktif di lingkungan apa pun, termasuk produksi nanti - setting DEBUG sendiri sudah ada di
# config.py tapi tidak pernah benar-benar dibaca kode manapun. Sekarang jadi gerbang nyata:
# dokumentasi interaktif cuma aktif kalau DEBUG=True (default lokal), dimatikan otomatis
# begitu DEBUG=False di-set eksplisit di .env produksi - mengurangi permukaan yang terlihat
# pihak luar tanpa mengubah apa pun untuk development sekarang.
app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.APP_NAME}