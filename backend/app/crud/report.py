from sqlalchemy.orm import Session
from app.models.report import Report
from app.schemas.report import ReportCreate, ReportUpdate

def get_report(db: Session, report_id: int):
    return db.query(Report).filter(Report.id == report_id).first()

def get_reports(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Report).order_by(Report.created_at.desc()).offset(skip).limit(limit).all()

def create_report(db: Session, report: ReportCreate, user_id: int | None = None):
    db_report = Report(
        title=report.title,
        data_type=report.data_type,
        input_file_name=report.input_file_name,
        parsed_data=report.parsed_data,
        user_id=user_id,
        period_start=report.period_start,
        period_end=report.period_end,
        template_type=report.template_type,
        output_format=report.output_format,
        language=report.language,
        include_ai_insights=report.include_ai_insights,
        include_raw_data_summary=report.include_raw_data_summary,
        ai_confidence=report.ai_confidence,
        sla_met=report.sla_met,
        processing_time_sec=report.processing_time_sec,
        created_by_name=report.created_by_name
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report

def update_report(db: Session, report_id: int, report_update: ReportUpdate):
    db_report = get_report(db, report_id)
    if not db_report:
        return None
    
    update_data = report_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_report, key, value)
        
    db.commit()
    db.refresh(db_report)
    return db_report

def delete_report(db: Session, report_id: int):
    db_report = get_report(db, report_id)
    if not db_report:
        return None
    db.delete(db_report)
    db.commit()
    return db_report
