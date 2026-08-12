# backend/app/api/v1/endpoints/chart.py
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.crud.report import get_owned_report, update_report, get_parsed_data
from app.schemas.report import ReportUpdate
from app.services.chart_generator import ChartGenerator

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/ping")
def ping():
    return {"message": "chart module ready"}

@router.get("/{report_id}")
def get_report_chart(
    report_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mendapatkan konfigurasi grafik Plotly interaktif untuk data log laporan keamanan.
    Hanya bisa diakses oleh pemilik laporan tersebut.
    """
    db_report = get_owned_report(db, report_id, current_user.id)
    if not db_report:
        raise HTTPException(status_code=404, detail="Data laporan tidak ditemukan.")

    parsed_data = get_parsed_data(db_report)
    if not parsed_data:
        raise HTTPException(status_code=400, detail="Data laporan belum di-parsing atau kosong.")

    try:
        chart_config = ChartGenerator.generate_chart_config(db_report.data_type, parsed_data)
    except Exception as e:
        # BUG DIPERBAIKI: dulu meneruskan detail exception Python mentah (bisa berisi path
        # file server/nama internal) langsung ke client - log lengkap di server, client cukup
        # dapat pesan generik yang aman.
        logger.error(f"Gagal merender grafik utk report {report_id} ({db_report.data_type}): {e}")
        raise HTTPException(
            status_code=500,
            detail="Gagal membuat grafik otomatis untuk laporan ini. Silakan coba lagi atau hubungi admin."
        )

    if not chart_config or chart_config.get("error") or "data" not in chart_config:
        raise HTTPException(
            status_code=500,
            detail=chart_config.get("error", "Gagal membuat grafik otomatis untuk laporan ini."),
        )

    if not db_report.chart_data:
        update_report(db, report_id, ReportUpdate(chart_data=chart_config), user_id=current_user.id)

    return chart_config