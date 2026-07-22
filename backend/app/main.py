# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.v1.router import api_router
from app.core.config import settings

# ── ANSI Color Codes ──────────────────────────────────────────────
G  = "\033[92m"   # Green
Y  = "\033[93m"   # Yellow
C  = "\033[96m"   # Cyan
W  = "\033[97m"   # White
DIM = "\033[2m"   # Dim
R  = "\033[0m"    # Reset

def print_banner():
    print(f"""
{G}╔══════════════════════════════════════════════════════════╗
║{W}       AI Security Reports — FastAPI Backend              {G}║
║{DIM}       PT Petrokimia Gresik · SOC Intelligence Platform    {G}║
╠══════════════════════════════════════════════════════════╣
║  {C}API Docs  {R}→  {W}http://localhost:8000/docs                   {G}║
║  {C}Health   {R}→  {W}http://localhost:8000/health                  {G}║
║  {C}API Base {R}→  {W}http://localhost:8000/api/v1                  {G}║
╠══════════════════════════════════════════════════════════╣
║  {Y}Database {R}→  {W}PostgreSQL @ localhost:5432                   {G}║
║  {Y}Auth     {R}→  {W}JWT + Google OAuth2                          {G}║
║  {Y}Email    {R}→  {W}SMTP (Fallback: Terminal Log Mode)            {G}║
╚══════════════════════════════════════════════════════════╝{R}
""")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from app.db.session import engine
    from app.db.base import Base
    try:
        Base.metadata.create_all(bind=engine)
        print(f"{G}[DB]{R} Database tables created or validated.")
    except Exception as db_err:
        print(f"\033[91m[DB ERROR]\033[0m Gagal membuat tabel: {db_err}")
    print_banner()
    print(f"{G}[STARTUP]{R} Backend siap menerima request ✓")
    print(f"{DIM}[INFO]{R}    Hot-reload aktif — perubahan kode otomatis ter-apply\n")
    yield
    # Shutdown
    print(f"\n{Y}[SHUTDOWN]{R} Backend sedang dimatikan...")

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
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