from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import io
import re
import urllib.parse

from app.db.session import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.crud.report import get_owned_report, delete_report
from app.crud.audit_log import log_action  # Fix #9: Audit Log
from app.schemas.report import ReportResponse
from app.models.report import Report
from app.services.export_pdf import PDFExporter
from app.services.export_ppt import PPTXExporter
from app.services.report_render_logic import build_report_blocks

from datetime import datetime, date

router = APIRouter()

_ILLEGAL_FILENAME_CHARS_RE = re.compile(r'[\\/:*?"<>|]')


def _sanitize_filename(title: str | None, fallback: str) -> str:
    """Nama file download dari judul laporan — bukan cuma "soc_report_{id}" generik.
    Karakter ilegal filesystem DIGANTI spasi (bukan dihapus) supaya kata tidak nyambung
    (mis. "Q1/2024" -> "Q1_2024", bukan "Q12024"), lalu spasi dirapikan jadi underscore."""
    if not title or not title.strip():
        return fallback
    name = _ILLEGAL_FILENAME_CHARS_RE.sub(" ", title.strip())
    name = re.sub(r"\s+", "_", name.strip())
    name = name.strip("._")
    if len(name) > 80:
        name = name[:80].rstrip("._")
    return name or fallback


def _content_disposition(filename_base: str, ext: str) -> str:
    """filename (fallback ASCII, browser lama) + filename* RFC 5987 UTF-8 (browser modern) —
    supaya judul berbahasa Indonesia dengan karakter non-ASCII tetap tampil benar."""
    ascii_fallback = filename_base.encode("ascii", "ignore").decode("ascii").strip("._") or "report"
    quoted_utf8 = urllib.parse.quote(f"{filename_base}.{ext}")
    return f'attachment; filename="{ascii_fallback}.{ext}"; filename*=UTF-8\'\'{quoted_utf8}'

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
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mendapatkan daftar riwayat laporan dengan pencarian, filter tipe data/status/periode, dan paginasi.
    Hanya menampilkan laporan milik user yang sedang login (tidak bisa lihat punya user lain).
    """
    query = db.query(Report).filter(Report.user_id == current_user.id)

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

    total_count = query.count()
    response.headers["X-Total-Count"] = str(total_count)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"

    return query.order_by(Report.created_at.desc()).offset(skip).limit(limit).all()

@router.get("/{report_id}", response_model=ReportResponse)
def read_report_detail(
    report_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mendapatkan detail lengkap satu riwayat laporan berdasarkan ID.
    Hanya bisa diakses oleh pemilik laporan tersebut.
    """
    db_report = get_owned_report(db, report_id, current_user.id)
    if not db_report:
        raise HTTPException(status_code=404, detail="Data laporan tidak ditemukan.")
    return db_report

@router.get("/{report_id}/preview")
def get_report_preview_blocks(
    report_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mengembalikan struktur "block" (bagian, judul, angka, isi) yang SAMA PERSIS dipakai
    export_pdf.py/export_ppt.py untuk merender PDF/PPTX — dipakai tab Preview di frontend
    supaya tampilannya dijamin konsisten dengan file yang benar-benar diunduh, bukan
    implementasi tampilan terpisah yang bisa diam-diam beda.
    """
    db_report = get_owned_report(db, report_id, current_user.id)
    if not db_report:
        raise HTTPException(status_code=404, detail="Data laporan tidak ditemukan.")

    if not db_report.ai_summary:
        raise HTTPException(
            status_code=400,
            detail="Laporan belum dianalisis oleh AI. Silakan jalankan analisis terlebih dahulu sebelum melihat preview."
        )

    blocks = build_report_blocks(db_report)
    return {"blocks": blocks}

@router.delete("/{report_id}")
def remove_report(
    report_id: int,
    request: Request,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Menghapus satu laporan dari database riwayat.
    Hanya bisa dilakukan oleh pemilik laporan tersebut.
    """
    db_report = get_owned_report(db, report_id, current_user.id)
    if not db_report:
        raise HTTPException(status_code=404, detail="Data laporan tidak ditemukan.")
    report_title = db_report.title  # Simpan sebelum dihapus
    delete_report(db, report_id)
    # Fix #9: Catat aksi delete ke audit log
    try:
        log_action(
            db, user_id=current_user.id, action="delete",
            resource_type="report", resource_id=report_id,
            detail=f"Laporan '{report_title}' dihapus.",
            ip_address=request.client.host if request.client else None
        )
    except Exception:
        pass  # Audit log jangan sampai mengganggu respons utama
    return {"status": "success", "message": "Laporan berhasil dihapus dari riwayat siber."}

@router.post("/bulk-delete")
def bulk_remove_reports(
    report_ids: List[int],
    request: Request,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Menghapus beberapa laporan sekaligus dari database riwayat.
    Hanya bisa dilakukan untuk laporan milik user yang sedang login.
    """
    if not report_ids:
        raise HTTPException(status_code=400, detail="Daftar ID laporan tidak boleh kosong.")

    deleted_count = db.query(Report).filter(
        Report.id.in_(report_ids),
        Report.user_id == current_user.id
    ).delete(synchronize_session=False)

    db.commit()
    # Fix #9: Catat aksi bulk delete ke audit log
    try:
        log_action(
            db, user_id=current_user.id, action="bulk_delete",
            resource_type="report", resource_id=None,
            detail=f"{deleted_count} laporan dihapus sekaligus. IDs: {report_ids}",
            ip_address=request.client.host if request.client else None
        )
    except Exception:
        pass
    return {"status": "success", "deleted_count": deleted_count, "message": f"{deleted_count} laporan berhasil dihapus."}

@router.post("/{report_id}/retry")
def retry_report_analysis(
    report_id: int,
    request: Request,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Memicu ulang analisis AI untuk laporan berstatus 'failed'.
    """
    db_report = get_owned_report(db, report_id, current_user.id)
    if not db_report:
        raise HTTPException(status_code=404, detail="Data laporan tidak ditemukan.")

    db_report.status = "processing"
    db_report.tokens_generated = 0
    db.commit()
    db.refresh(db_report)

    from app.api.v1.endpoints.analysis import _run_analysis_job
    import threading
    threading.Thread(target=_run_analysis_job, args=(report_id,), daemon=True).start()

    # Fix #9: Catat aksi retry ke audit log
    try:
        log_action(
            db, user_id=current_user.id, action="retry_analysis",
            resource_type="report", resource_id=report_id,
            detail=f"Analisis AI dipicu ulang untuk laporan '{db_report.title}'.",
            ip_address=request.client.host if request.client else None
        )
    except Exception:
        pass
    return {"status": "processing", "message": "Analisis AI berhasil dipicu ulang di background."}

@router.get("/{report_id}/pdf")
def download_pdf_report(
    report_id: int,
    request: Request,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mengekspor laporan keamanan siber ke file PDF dan mendownloadnya.
    Disimpan di cache disk (storage/exports/) agar download berikutnya instan.
    """
    db_report = get_owned_report(db, report_id, current_user.id)
    if not db_report:
        raise HTTPException(status_code=404, detail="Data laporan tidak ditemukan.")

    if not db_report.ai_summary:
        raise HTTPException(
            status_code=400,
            detail="Laporan belum dianalisis oleh AI. Silakan jalankan analisis terlebih dahulu sebelum melakukan ekspor."
        )

    # Cek cache di disk
    import os
    export_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "storage", "exports")
    os.makedirs(export_dir, exist_ok=True)
    pdf_cache_path = os.path.join(export_dir, f"soc_report_{report_id}.pdf")

    if os.path.exists(pdf_cache_path) and db_report.file_pdf_path == pdf_cache_path:
        with open(pdf_cache_path, "rb") as f:
            pdf_bytes = f.read()
    else:
        try:
            pdf_bytes = PDFExporter.generate_pdf_report(db_report)
            with open(pdf_cache_path, "wb") as f:
                f.write(pdf_bytes)
            db_report.file_pdf_path = pdf_cache_path
            db.commit()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Gagal melakukan ekspor PDF: {str(e)}"
            )

    # Fix #9: Catat aksi download PDF ke audit log
    try:
        log_action(
            db, user_id=current_user.id, action="download_pdf",
            resource_type="report", resource_id=report_id,
            detail=f"PDF diunduh untuk laporan '{db_report.title}'.",
            ip_address=request.client.host if request.client else None
        )
    except Exception:
        pass

    filename_base = _sanitize_filename(db_report.title, f"soc_report_{report_id}")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": _content_disposition(filename_base, "pdf")
        }
    )

@router.get("/{report_id}/pptx")
def download_pptx_report(
    report_id: int,
    request: Request,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mengekspor laporan keamanan siber ke slide presentasi PowerPoint (.pptx).
    Disimpan di cache disk (storage/exports/) agar download berikutnya instan.
    """
    db_report = get_owned_report(db, report_id, current_user.id)
    if not db_report:
        raise HTTPException(status_code=404, detail="Data laporan tidak ditemukan.")

    if not db_report.ai_summary:
        raise HTTPException(
            status_code=400,
            detail="Laporan belum dianalisis oleh AI. Silakan jalankan analisis terlebih dahulu."
        )

    # Cek cache di disk
    import os
    export_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "storage", "exports")
    os.makedirs(export_dir, exist_ok=True)
    ppt_cache_path = os.path.join(export_dir, f"soc_report_{report_id}.pptx")

    if os.path.exists(ppt_cache_path) and db_report.file_ppt_path == ppt_cache_path:
        with open(ppt_cache_path, "rb") as f:
            ppt_bytes = f.read()
    else:
        try:
            ppt_bytes = PPTXExporter.generate_ppt_report(db_report)
            with open(ppt_cache_path, "wb") as f:
                f.write(ppt_bytes)
            db_report.file_ppt_path = ppt_cache_path
            db.commit()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Gagal melakukan ekspor PPTX: {str(e)}"
            )

    # Fix #9: Catat aksi download PPTX ke audit log
    try:
        log_action(
            db, user_id=current_user.id, action="download_pptx",
            resource_type="report", resource_id=report_id,
            detail=f"PPTX diunduh untuk laporan '{db_report.title}'.",
            ip_address=request.client.host if request.client else None
        )
    except Exception:
        pass

    filename_base = _sanitize_filename(db_report.title, f"soc_report_{report_id}")
    return Response(
        content=ppt_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Disposition": _content_disposition(filename_base, "pptx")
        }
    )