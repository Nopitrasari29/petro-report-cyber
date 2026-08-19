from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.report import Report
from typing import List
import datetime

router = APIRouter()

@router.get("/stats")
def get_dashboard_stats(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mendapatkan seluruh statistik ringkasan, grafik tren ancaman, dan antrean untuk Dashboard.
    Semua angka di sini di-scope hanya ke laporan milik user yang sedang login.
    """
    base_query = db.query(Report).filter(Report.user_id == current_user.id)

    # 1. Ambil 5 laporan terbaru milik user ini
    recent_reports = base_query.order_by(Report.created_at.desc()).limit(5).all()

    formatted_reports = []
    for rep in recent_reports:
        # BUG DIPERBAIKI: fallback dulu tanggal statis hardcode "2026-07-01/07-31" - benar
        # sekarang (bulan berjalan saat ditulis) tapi makin terasa aneh begitu waktu berjalan
        # lewat periode itu. Fallback ke created_at laporan itu sendiri (selalu relevan,
        # tidak pernah "expired") kalau period_start/end genuinely kosong.
        _fallback_date = rep.created_at.strftime("%Y-%m-%d") if rep.created_at else "-"
        formatted_reports.append({
            "id": rep.id,
            "title": rep.title,
            "data_type": rep.data_type,
            "period": f"{rep.period_start.strftime('%Y-%m-%d') if rep.period_start else _fallback_date} - {rep.period_end.strftime('%Y-%m-%d') if rep.period_end else _fallback_date}",
            "status": rep.status,
            "created_at": rep.created_at.strftime("%d %b %Y, %H:%M") if rep.created_at else "-",
            "created_by": rep.created_by_name or "SOC Analyst"
        })

    # 2. Hitung metrics/counters utama, semuanya di-scope ke user_id
    total_reports = base_query.count()
    pending_queue_count = base_query.filter(Report.status.in_(["processing", "queued", "waiting"])).count()

    crit_incidents = db.query(func.sum(Report.threat_count_critical)).filter(Report.user_id == current_user.id).scalar() or 0
    avg_confidence_val = db.query(func.avg(Report.ai_confidence)).filter(
        Report.user_id == current_user.id,
        Report.status.in_(["analyzed", "completed"]),
        Report.ai_confidence.isnot(None)
    ).scalar()
    avg_confidence = float(avg_confidence_val) if avg_confidence_val is not None else 0.0
    available_reports = base_query.filter(Report.status.in_(["parsed", "analyzed", "completed"])).count()

    # Hitung persentase perubahan Critical Incidents (30 hari terakhir vs 30 s/d 60 hari yang lalu)
    now = datetime.datetime.utcnow()
    last_30_days = now - datetime.timedelta(days=30)
    prev_30_to_60_days = now - datetime.timedelta(days=60)

    crit_last_30 = db.query(func.sum(Report.threat_count_critical))\
        .filter(Report.user_id == current_user.id)\
        .filter(Report.created_at >= last_30_days).scalar() or 0

    crit_prev_30 = db.query(func.sum(Report.threat_count_critical))\
        .filter(Report.user_id == current_user.id)\
        .filter(Report.created_at >= prev_30_to_60_days)\
        .filter(Report.created_at < last_30_days).scalar() or 0

    if crit_prev_30 > 0:
        crit_pct_change = round(((crit_last_30 - crit_prev_30) / crit_prev_30) * 100, 1)
    else:
        crit_pct_change = 0.0 if crit_last_30 == 0 else 100.0

    # 3. Distribusi tingkat keparahan (Severity Distribution), di-scope ke user_id
    user_reports_filter = Report.user_id == current_user.id
    sum_crit = db.query(func.sum(Report.threat_count_critical)).filter(user_reports_filter).scalar() or 0
    sum_high = db.query(func.sum(Report.threat_count_high)).filter(user_reports_filter).scalar() or 0
    sum_med = db.query(func.sum(Report.threat_count_medium)).filter(user_reports_filter).scalar() or 0
    sum_low = db.query(func.sum(Report.threat_count_low)).filter(user_reports_filter).scalar() or 0
    sum_info = db.query(func.sum(Report.threat_count_info)).filter(user_reports_filter).scalar() or 0

    total_events = sum_crit + sum_high + sum_med + sum_low + sum_info

    def get_percentage(part, total):
        return round((part / total) * 100) if total > 0 else 0

    severity_breakdown = [
        {"severity": "Critical", "count": sum_crit, "percentage": get_percentage(sum_crit, total_events)},
        {"severity": "High", "count": sum_high, "percentage": get_percentage(sum_high, total_events)},
        {"severity": "Medium", "count": sum_med, "percentage": get_percentage(sum_med, total_events)},
        {"severity": "Low", "count": sum_low, "percentage": get_percentage(sum_low, total_events)},
        {"severity": "Informational", "count": sum_info, "percentage": get_percentage(sum_info, total_events)}
    ]

    # 4. Tren ancaman bulanan (Threat Trend Chart), di-scope ke user_id
    trend_reports = base_query.order_by(Report.created_at.asc()).limit(5).all()
    if trend_reports:
        labels = [
            rep.period_start.strftime("%d %b") if rep.period_start else rep.created_at.strftime("%d %b")
            for rep in trend_reports
        ]
        datasets = [
            {"label": "Critical", "data": [rep.threat_count_critical or 0 for rep in trend_reports]},
            {"label": "High", "data": [rep.threat_count_high or 0 for rep in trend_reports]},
            {"label": "Medium", "data": [rep.threat_count_medium or 0 for rep in trend_reports]},
            {"label": "Low", "data": [rep.threat_count_low or 0 for rep in trend_reports]},
            # RCA-B02: Sertakan Informational agar total trend_trend konsisten dengan
            # total_events di severity_distribution (yang sudah menghitung sum_info).
            {"label": "Informational", "data": [rep.threat_count_info or 0 for rep in trend_reports]},
        ]
    else:
        labels = []
        datasets = [
            {"label": "Critical", "data": []},
            {"label": "High", "data": []},
            {"label": "Medium", "data": []},
            {"label": "Low", "data": []},
            {"label": "Informational", "data": []}
        ]

    # 5. Antrean pemrosesan AI, di-scope ke user_id
    db_queued = base_query.filter(Report.status.in_(["processing", "queued", "waiting", "draft"])).order_by(Report.updated_at.desc()).all()
    queue_list = []

    for rep in db_queued:
        progress = 0
        q_status = "Waiting in Queue"
        if rep.status == "processing":
            # RCA-B01: Hitung progress NYATA dari tokens_generated (bukan hardcoded 75%).
            tokens = rep.tokens_generated or 0
            progress = min(95, round((tokens / 3500) * 100)) if tokens > 0 else 15
            q_status = "Processing"
        elif rep.status == "draft":
            progress = 25
            q_status = "Parsed — Ready for Analysis"

        queue_list.append({
            "report_name": rep.title,
            "progress_percentage": progress,
            "status": q_status,
            "timestamp": rep.updated_at.strftime("%d %b %Y, %H:%M") if rep.updated_at else "-"
        })

    confidence_label = "High Confidence" if avg_confidence >= 85 else ("Medium Confidence" if avg_confidence > 0 else "No Reports Yet")

    return {
        "counters": {
            "critical_incidents": {
                "value": crit_incidents,
                "percentage_change": crit_pct_change,
                "label": "vs last 30 days"
            },
            "reports_generated": {
                "value": total_reports,
                "pending_queue": pending_queue_count
            },
            "ai_analysis_score": {
                "value": round(avg_confidence) if avg_confidence > 0 else 0,
                "label": confidence_label
            },
            "report_history": {
                "value": available_reports,
                "label": "Available Reports"
            }
        },
        "threat_trend": {
            "labels": labels,
            "datasets": datasets
        },
        "severity_distribution": {
            "total_events": total_events,
            "breakdown": severity_breakdown
        },
        "generation_queue": queue_list,
        "recent_reports": formatted_reports
    }