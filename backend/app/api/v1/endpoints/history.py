from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import io

from app.db.session import get_db
from app.crud.report import get_report, delete_report, update_report
from app.schemas.report import ReportResponse, ReportUpdate
from app.models.report import Report
from app.services.export_pdf import PDFExporter
from app.services.export_ppt import PPTXExporter
from app.services.chart_generator import ChartGenerator

from datetime import datetime, date

router = APIRouter()

@router.get("/ping")
def ping():
    return {"message": "history module ready"}

@router.get("/", response_model=List[ReportResponse])
def read_reports(
    response: Response,
    skip: int = 0,
    limit: int = 100,
    data_type: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Mendapatkan daftar riwayat laporan dengan pencarian, filter tipe data/status/periode, dan paginasi.
    """
    query = db.query(Report)
    
    if data_type:
        query = query.filter(Report.data_type == data_type)
        
    if status:
        query = query.filter(Report.status == status)
        
    if search:
        query = query.filter(Report.title.ilike(f"%{search}%"))
        
    if period_start:
        try:
            p_start = datetime.strptime(period_start, "%Y-%m-%d").date()
            query = query.filter(Report.period_start >= p_start)
        except ValueError:
            pass
            
    if period_end:
        try:
            p_end = datetime.strptime(period_end, "%Y-%m-%d").date()
            query = query.filter(Report.period_end <= p_end)
        except ValueError:
            pass
            
    # Dapatkan total count sebelum paginasi offset/limit
    total_count = query.count()
    response.headers["X-Total-Count"] = str(total_count)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    
    return query.order_by(Report.created_at.desc()).offset(skip).limit(limit).all()

@router.get("/{report_id}", response_model=ReportResponse)
def read_report_detail(report_id: int, db: Session = Depends(get_db)):
    """
    Mendapatkan detail lengkap satu riwayat laporan berdasarkan ID.
    """
    db_report = get_report(db, report_id)
    if not db_report:
        raise HTTPException(status_code=404, detail="Data laporan tidak ditemukan.")
    return db_report

@router.delete("/{report_id}")
def remove_report(report_id: int, db: Session = Depends(get_db)):
    """
    Menghapus satu laporan dari database riwayat.
    """
    db_report = delete_report(db, report_id)
    if not db_report:
        raise HTTPException(status_code=404, detail="Data laporan tidak ditemukan.")
    return {"status": "success", "message": "Laporan berhasil dihapus dari riwayat siber."}

@router.get("/{report_id}/pdf")
def download_pdf_report(report_id: int, db: Session = Depends(get_db)):
    """
    Mengekspor laporan keamanan siber ke file PDF dan mendownloadnya.
    """
    db_report = get_report(db, report_id)
    if not db_report:
        raise HTTPException(status_code=404, detail="Data laporan tidak ditemukan.")
    
    if not db_report.ai_summary:
        raise HTTPException(
            status_code=400, 
            detail="Laporan belum dianalisis oleh AI. Silakan jalankan analisis terlebih dahulu sebelum melakukan ekspor."
        )

    # Auto-generate chart jika kosong sebelum diexport
    if not db_report.chart_data and db_report.parsed_data:
        try:
            chart_config = ChartGenerator.generate_chart_config(db_report.data_type, db_report.parsed_data)
            db_report = update_report(db, report_id, ReportUpdate(chart_data=chart_config))
        except Exception as chart_err:
            print(f"[EXPORT CHART WARNING] Gagal auto-generate chart untuk PDF: {chart_err}")
        
    try:
        pdf_bytes = PDFExporter.generate_pdf_report(db_report)
        # Mengembalikan berkas PDF biner langsung sebagai berkas unduhan
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=soc_report_{report_id}.pdf"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal melakukan ekspor PDF: {str(e)}"
        )

@router.get("/{report_id}/pptx")
def download_pptx_report(report_id: int, db: Session = Depends(get_db)):
    """
    Mengekspor laporan keamanan siber ke slide presentasi PowerPoint (.pptx).
    """
    db_report = get_report(db, report_id)
    if not db_report:
        raise HTTPException(status_code=404, detail="Data laporan tidak ditemukan.")
        
    if not db_report.ai_summary:
        raise HTTPException(
            status_code=400, 
            detail="Laporan belum dianalisis oleh AI. Silakan jalankan analisis terlebih dahulu."
        )

    # Auto-generate chart jika kosong sebelum diexport
    if not db_report.chart_data and db_report.parsed_data:
        try:
            chart_config = ChartGenerator.generate_chart_config(db_report.data_type, db_report.parsed_data)
            db_report = update_report(db, report_id, ReportUpdate(chart_data=chart_config))
        except Exception as chart_err:
            print(f"[EXPORT CHART WARNING] Gagal auto-generate chart untuk PPTX: {chart_err}")
        
    try:
        ppt_bytes = PPTXExporter.generate_ppt_report(db_report)
        return Response(
            content=ppt_bytes,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={
                "Content-Disposition": f"attachment; filename=soc_report_{report_id}.pptx"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal melakukan ekspor PPTX: {str(e)}"
        )
