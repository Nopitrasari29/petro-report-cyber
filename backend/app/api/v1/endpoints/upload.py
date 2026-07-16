# app/api/v1/endpoints/upload.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.db.session import get_db
from app.services.parser.factory import ParserFactory
from app.crud.report import create_report
from app.schemas.report import ReportCreate, ReportResponse
from app.api.v1.endpoints.auth import get_current_user
from app.services.chart_generator import ChartGenerator

router = APIRouter()

def count_threats(parsed_data: list) -> dict:
    """
    Menghitung jumlah insiden keamanan berdasarkan level keparahan (severity) dari data log.
    Menangani berbagai macam variasi nama kunci severity yang dihasilkan oleh parser.
    """
    counters = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    severity_keys = ["severity", "Severity", "level", "Level", "threat_level", "Threat Level", "priority", "Priority"]
    
    for row in parsed_data:
        severity_value = None
        for key in severity_keys:
            if key in row:
                severity_value = row[key]
                break
        
        if severity_value is not None:
            val_str = str(severity_value).strip().lower()
            if val_str in counters:
                counters[val_str] += 1
            elif "crit" in val_str:
                counters["critical"] += 1
            elif "high" in val_str or "severe" in val_str:
                counters["high"] += 1
            elif "med" in val_str or "warn" in val_str:
                counters["medium"] += 1
            elif "low" in val_str or "info" in val_str:
                counters["low"] += 1
                
    return counters

@router.get("/ping")
def ping():
    return {"message": "upload module ready"}

@router.post("/", response_model=ReportResponse)
def upload_security_file(
    title: str = Form(...),
    data_type: str = Form(...),  # firewall, email_security, ids_ips, vapt, dll.
    file: UploadFile = File(...),
    period_start: Optional[str] = Form(None),  # Format YYYY-MM-DD
    period_end: Optional[str] = Form(None),    # Format YYYY-MM-DD
    template_type: Optional[str] = Form("SOC Executive Summary (Monthly)"),
    output_format: Optional[str] = Form("PDF"),
    language: Optional[str] = Form("Indonesian"),
    include_ai_insights: bool = Form(True),
    include_raw_data_summary: bool = Form(True),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mengunggah berkas log keamanan, mengurainya via Parser, dan menyimpan laporannya ke DB 
    dengan konfigurasi awal (status Draft/Uploaded) untuk siap diproses di Step 3 oleh AI.
    """
    try:
        # Konversi tanggal periode log dengan validasi string kosong (Next.js Form safe)
        p_start = None
        p_end = None
        
        if period_start and period_start.strip():
            p_start = datetime.strptime(period_start.strip(), "%Y-%m-%d").date()
        if period_end and period_end.strip():
            p_end = datetime.strptime(period_end.strip(), "%Y-%m-%d").date()
            
        # Membaca file dan memanggil parser yang sesuai dari factory
        try:
            parser = ParserFactory.get_parser(file.filename)
            parsed_data = parser.parse(file.file)
        finally:
            # Pastikan file stream ditutup dengan aman setelah dibaca oleh parser
            file.file.close()
        
        # Hitung statistik ancaman dari log siber yang diunggah
        threat_metrics = count_threats(parsed_data)
        total_records = len(parsed_data) if parsed_data else 0
        
        # Buat instansiasi schema ReportCreate
        report_in = ReportCreate(
            title=title,
            data_type=data_type,
            input_file_name=file.filename,
            parsed_data=parsed_data,
            period_start=p_start,
            period_end=p_end,
            template_type=template_type,
            output_format=output_format,
            language=language,
            include_ai_insights=include_ai_insights,
            include_raw_data_summary=include_raw_data_summary,
            created_by_name=current_user.full_name or current_user.username,
            threat_count_critical=threat_metrics["critical"],
            threat_count_high=threat_metrics["high"],
            threat_count_medium=threat_metrics["medium"],
            threat_count_low=threat_metrics["low"],
            total_records_parsed=total_records
        )
        
        db_report = create_report(db, report_in, user_id=current_user.id)
        return db_report
        
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=f"Kesalahan validasi format data: {str(ve)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memproses unggahan log siber: {str(e)}")