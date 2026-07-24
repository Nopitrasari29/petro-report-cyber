# backend/app/api/v1/endpoints/auth/__init__.py
from fastapi import APIRouter

# Gunakan impor relatif (.core, .traditional, dll.) untuk menghindari circular import
from .core import router as core_router, get_current_user
from .traditional import router as traditional_router
from .oauth import router as oauth_router
from .verification import router as verification_router
from .password import router as password_router

router = APIRouter()

# Gabungkan seluruh sub-router autentikasi ke dalam satu APIRouter terpadu
router.include_router(core_router)
router.include_router(traditional_router)
router.include_router(oauth_router)
router.include_router(verification_router)
router.include_router(password_router)

# Ekspor publik agar modul lain (upload.py, profile.py, dsb.)
# dapat mengimpor 'get_current_user' secara langsung dari folder auth
__all__ = [
    "router",
    "get_current_user",
]