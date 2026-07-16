# backend/app/api/v1/endpoints/chart.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.crud.report import get_report, update_report
from app.schemas.report import ReportUpdate
# FIX: Jalur impor diselaraskan dengan struktur folder riil (app/services/parser/chart_generator.py)
from app.services.chart_generator import ChartGenerator

router = APIRouter()

@router.get("/ping")
def ping():
    return {"message": "chart module ready"}

@router.get("/{report_id}")
def get_report_chart(report_id: int, db: Session = Depends(get_db)):
    """
    Mendapatkan konfigurasi grafik Plotly interaktif untuk data log laporan keamanan.
    Mendukung penyimpanan otomatis ke dalam database untuk mempercepat load berikutnya.
    """
    db_report = get_report(db, report_id)
    if not db_report:
        raise HTTPException(status_code=404, detail="Data laporan tidak ditemukan.")
        
    if not db_report.parsed_data:
        raise HTTPException(status_code=400, detail="Data laporan belum di-parsing atau kosong.")
        
    try:
        # Hasilkan konfigurasi Plotly secara dinamis berdasarkan jenis log (firewall, email, dsb.)
        chart_config = ChartGenerator.generate_chart_config(db_report.data_type, db_report.parsed_data)
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Gagal merender grafik Plotly untuk data '{db_report.data_type}': {str(e)}"
        )
    
    # Jika database belum menyimpan chart_data, perbarui record tersebut (Cache pattern)
    if not db_report.chart_data:
        update_report(db, report_id, ReportUpdate(chart_data=chart_config))
        
    return chart_config