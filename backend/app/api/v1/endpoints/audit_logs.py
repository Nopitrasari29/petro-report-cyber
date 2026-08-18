# backend/app/api/v1/endpoints/audit_logs.py
"""
RCA-B07: Endpoint untuk membaca audit log \u2014 sebelumnya audit log hanya DITULIS
(upload, delete, download, retry, analyze) tapi tidak pernah BISA DIBACA via API.
Semua data forensik itu tidak berguna kalau tidak ada cara mengaksesnya.

Endpoint ini mengizinkan user melihat log aktivitas MEREKA SENDIRI (semua aksi),
sedangkan user dengan role "Admin" bisa melihat log aktivitas SEMUA USER.
"""
import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.db.session import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.audit_log import AuditLog
from app.models.user import User
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[int]
    detail: Optional[str]
    ip_address: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/", response_model=List[AuditLogResponse])
def get_audit_logs(
    action: Optional[str] = Query(None, description="Filter by action type (e.g. 'upload', 'delete', 'generate_analysis')"),
    resource_id: Optional[int] = Query(None, description="Filter by report ID"),
    from_date: Optional[str] = Query(None, description="Filter dari tanggal (format YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Filter sampai tanggal (format YYYY-MM-DD)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Membaca audit log aktivitas.

    - **User biasa**: hanya bisa melihat log aktivitas MEREKA SENDIRI.
    - **Admin**: bisa melihat log semua user (filter by user_id via query param, atau semua).

    Diurutkan dari yang terbaru. Bisa difilter berdasarkan jenis aksi, laporan ID, dan rentang tanggal.
    """
    is_admin = (current_user.role or "").strip().lower() in ("admin", "superadmin")

    query = db.query(AuditLog)

    # User biasa hanya bisa lihat log diri sendiri; admin bisa lihat semua
    if not is_admin:
        query = query.filter(AuditLog.user_id == current_user.id)

    if action:
        query = query.filter(AuditLog.action == action)

    if resource_id is not None:
        query = query.filter(AuditLog.resource_id == resource_id)

    if from_date:
        try:
            dt_from = datetime.strptime(from_date, "%Y-%m-%d")
            query = query.filter(AuditLog.created_at >= dt_from)
        except ValueError:
            pass

    if to_date:
        try:
            dt_to = datetime.strptime(to_date, "%Y-%m-%d")
            # Sampai akhir hari
            dt_to = dt_to.replace(hour=23, minute=59, second=59)
            query = query.filter(AuditLog.created_at <= dt_to)
        except ValueError:
            pass

    return query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/summary")
def get_audit_summary(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Ringkasan statistik aktivitas pengguna sendiri (bukan admin-only):
    jumlah per tipe aksi dalam 30 hari terakhir.
    """
    from sqlalchemy import func
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(days=30)

    rows = (
        db.query(AuditLog.action, func.count(AuditLog.id).label("count"))
        .filter(AuditLog.user_id == current_user.id)
        .filter(AuditLog.created_at >= cutoff)
        .group_by(AuditLog.action)
        .all()
    )

    return {
        "user_id": current_user.id,
        "period": "last_30_days",
        "actions": {row.action: row.count for row in rows},
        "total": sum(row.count for row in rows),
    }
