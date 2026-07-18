from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.crud.report import get_report
from app.services.log_validator import run_log_validation

router = APIRouter()

@router.get("/summary/{report_id}")
def get_validation_summary(report_id: int, db: Session = Depends(get_db)):
    """
    Mendapatkan hasil ringkasan validasi kualitas data log laporan tertentu dari data nyata.
    """
    db_report = get_report(db, report_id)
    if not db_report:
        raise HTTPException(status_code=404, detail="Data laporan tidak ditemukan.")
        
    if not db_report.parsed_data:
        raise HTTPException(status_code=400, detail="Laporan tidak memiliki data log parsed untuk divalidasi.")
        
    result = run_log_validation(
        parsed_list=db_report.parsed_data,
        data_type=db_report.data_type,
        report_title=db_report.title,
        created_at=db_report.created_at
    )
    
    # Sesuaikan dengan format kunci JSON rute API lama agar selaras 100% dengan FE
    result["period"] = f"{db_report.period_start.strftime('%Y-%m-%d') if db_report.period_start else '2026-07-01'} - {db_report.period_end.strftime('%Y-%m-%d') if db_report.period_end else '2026-07-31'}"
    result["validation_issues_details"] = result.pop("validation_issues")
    result["sample_data_preview"] = result.pop("sample_preview")
    
    return result
