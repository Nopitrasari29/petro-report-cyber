from fastapi import APIRouter
from app.api.v1.endpoints import auth, upload, analysis, chart, history, datasources, validation, settings, dashboard, analytics, profile

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(chart.router, prefix="/chart", tags=["chart"])
api_router.include_router(history.router, prefix="/history", tags=["history"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(datasources.router, prefix="/datasources", tags=["datasources"])
api_router.include_router(validation.router, prefix="/validation", tags=["validation"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(profile.router, prefix="/settings", tags=["profile"])