from pydantic import BaseModel
from datetime import datetime, date
from typing import Any, Dict, List, Optional

class ReportBase(BaseModel):
    title: str
    data_type: str
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    template_type: Optional[str] = "SOC Executive Summary (Monthly)"
    output_format: Optional[str] = "PDF"
    language: Optional[str] = "Indonesian"
    include_ai_insights: Optional[bool] = True
    include_raw_data_summary: Optional[bool] = True
    header_title: Optional[str] = "PT PETROKIMIA GRESIK"
    header_subtitle: Optional[str] = "Sistem Otomasi Laporan & Eksekutif Presentasi Berbasis AI"
    theme_color: Optional[str] = "green"
    domain_type: Optional[str] = "general"
    tone: Optional[str] = "Professional"
    default_level: Optional[str] = "Standard"

class ReportCreate(ReportBase):
    input_file_name: Optional[str] = None
    parsed_data: Optional[List[Dict[str, Any]]] = None
    ai_confidence: Optional[float] = 94.0
    sla_met: Optional[bool] = True
    processing_time_sec: Optional[int] = 15
    created_by_name: Optional[str] = None
    threat_count_critical: Optional[int] = 0
    threat_count_high: Optional[int] = 0
    threat_count_medium: Optional[int] = 0
    threat_count_low: Optional[int] = 0
    threat_count_info: Optional[int] = 0
    total_records_parsed: Optional[int] = 0
    total_file_size_bytes: Optional[int] = None
    included_sections: Optional[Any] = None

class ReportUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    ai_summary: Optional[Dict[str, Any]] = None
    chart_data: Optional[Dict[str, Any]] = None
    file_pdf_path: Optional[str] = None
    file_ppt_path: Optional[str] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    template_type: Optional[str] = None
    output_format: Optional[str] = None
    language: Optional[str] = None
    include_ai_insights: Optional[bool] = None
    include_raw_data_summary: Optional[bool] = None
    header_title: Optional[str] = None
    header_subtitle: Optional[str] = None
    theme_color: Optional[str] = None
    domain_type: Optional[str] = None
    tone: Optional[str] = None
    default_level: Optional[str] = None
    ai_confidence: Optional[float] = None
    sla_met: Optional[bool] = None
    processing_time_sec: Optional[int] = None
    created_by_name: Optional[str] = None
    threat_count_critical: Optional[int] = None
    threat_count_high: Optional[int] = None
    threat_count_medium: Optional[int] = None
    threat_count_low: Optional[int] = None
    threat_count_info: Optional[int] = None
    total_records_parsed: Optional[int] = None
    total_file_size_bytes: Optional[int] = None
    included_sections: Optional[Any] = None
    tokens_generated: Optional[int] = None


class ReportUserEditableUpdate(BaseModel):
    """Skema SEMPIT khusus untuk endpoint `PUT /api/v1/analysis/{report_id}` (fitur Preview &
    Edit, Step 4 di wizard Generate + tab edit di History) — SENGAJA cuma berisi 2 field yang
    benar-benar dikirim frontend (dicek langsung ke semua caller-nya: generate/page.tsx &
    history/[id]/page.tsx, tidak ada satu pun yang pernah kirim field lain).

    ReportUpdate (di atas) TIDAK dipakai langsung sebagai tipe body endpoint itu karena field
    seperti "status"/"ai_confidence"/"sla_met" di dalamnya SEHARUSNYA cuma diisi sistem
    (hasil analisis AI beneran, lewat update_report() yang dipanggil internal dari
    _run_analysis_job) — endpoint yang tipenya ReportUpdate langsung menerima input user apa
    adanya tanpa allowlist, sehingga user bisa memalsukan status="analyzed"/ai_confidence=99.9
    tanpa laporannya pernah benar-benar dianalisis. Dengan tipe body dipersempit jadi skema
    ini, field-field itu secara teknis tidak mungkin ke-parse dari request user."""
    title: Optional[str] = None
    ai_summary: Optional[Dict[str, Any]] = None

class ReportResponse(ReportBase):
    id: int
    status: str
    input_file_name: Optional[str]
    parsed_data: Optional[List[Dict[str, Any]]]
    ai_summary: Optional[Dict[str, Any]]
    chart_data: Optional[Dict[str, Any]]
    file_pdf_path: Optional[str]
    file_ppt_path: Optional[str]
    user_id: Optional[int]
    ai_confidence: Optional[float]
    sla_met: Optional[bool]
    processing_time_sec: Optional[int]
    created_by_name: Optional[str]
    threat_count_critical: Optional[int]
    threat_count_high: Optional[int]
    threat_count_medium: Optional[int]
    threat_count_low: Optional[int]
    threat_count_info: Optional[int]
    total_records_parsed: Optional[int]
    total_file_size_bytes: Optional[int] = None
    included_sections: Optional[Any] = None
    tokens_generated: Optional[int]
    created_at: datetime
    updated_at: datetime


    class Config:
        from_attributes = True


class AnalysisProgress(BaseModel):
    """
    Payload ringan buat di-poll tiap beberapa detik selama status="processing" — sengaja TIDAK
    memakai ReportResponse penuh supaya tidak berulang kali mengirim ulang parsed_data/ai_summary
    yang bisa besar tiap polling tick.
    """
    status: str
    tokens_generated: int
    expected_total_tokens: Optional[int] = None
