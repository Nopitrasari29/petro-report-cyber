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
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
