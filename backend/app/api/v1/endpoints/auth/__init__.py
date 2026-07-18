from fastapi import APIRouter
from app.api.v1.endpoints.auth.core import router as core_router, get_current_user
from app.api.v1.endpoints.auth.traditional import router as traditional_router
from app.api.v1.endpoints.auth.oauth import router as oauth_router
from app.api.v1.endpoints.auth.verification import router as verification_router
from app.api.v1.endpoints.auth.password import router as password_router

router = APIRouter()

router.include_router(core_router)
router.include_router(traditional_router)
router.include_router(oauth_router)
router.include_router(verification_router)
router.include_router(password_router)
