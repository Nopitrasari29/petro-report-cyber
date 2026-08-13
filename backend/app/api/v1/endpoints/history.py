import logging
from fastapi import APIRouter, Depends, HTTPException, Response, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import io
import re
import urllib.parse

logger = logging.getLogger(__name__)

from app.db.session import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.crud.report import get_owned_report, delete_report, try_acquire_ai_lock
from app.crud.audit_log import log_action  # Fix #9: Audit Log
from app.schemas.report import ReportResponse
from app.models.report import Report
from app.services.export_pdf import PDFExporter
from app.services.export_ppt import PPTXExporter
from app.services.report_render_logic import build_report_blocks, get_visual_style, resolve_theme_color

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
    # visual_style dikirim terpisah (bukan diselipkan ke tiap block) supaya frontend cukup
    # baca 1 objek kecil ini utk tahu varian mana yg harus dirender (cover solid/split, chart
    # bar/donut/stacked, dst) — lihat pick_visual_style() di report_render_logic.py utk kenapa
    # ini WAJIB persis sama dgn yg dipakai export_pdf.py/export_ppt.py saat laporan ini diunduh.
    # theme_color juga dikirim terpisah (bukan bagian visual_style) — dipakai frontend utk
    # resolveThemeColors() supaya warna aksen preview sama dgn PDF/PPTX yang diunduh. SELALU
    # nilai TERRESOLVE (resolve_theme_color, bukan db_report.theme_color mentah) — kalau user
    # pilih "auto", kolom itu sendiri berisi literal "auto", bukan warna sungguhan; frontend
    # butuh warna yang SUDAH DIKUNCI acakannya (lihat resolved_theme_color di pick_visual_style)
    # supaya preview tidak diam-diam selalu jatuh ke hijau utk laporan yang temanya diacak.
    return {
        "blocks": blocks,
        "visual_style": get_visual_style(db_report),
        "theme_color": resolve_theme_color(db_report),
    }

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
    delete_report(db, report_id, user_id=current_user.id)
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

    from app.crud.report import _delete_file_safely

    # RCA-09: Ambil daftar laporan dulu untuk menghapus file fisik di disk
    reports_to_delete = db.query(Report).filter(
        Report.id.in_(report_ids),
        Report.user_id == current_user.id
    ).all()

    for r in reports_to_delete:
        _delete_file_safely(r.parsed_data_path)
        _delete_file_safely(r.file_pdf_path)
        _delete_file_safely(r.file_ppt_path)
        db.delete(r)

    deleted_count = len(reports_to_delete)
    db.commit()

    # Catat aksi bulk delete ke audit log
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
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Memicu ulang analisis AI untuk laporan berstatus 'failed'.
    """
    db_report = get_owned_report(db, report_id, current_user.id)
    if not db_report:
        raise HTTPException(status_code=404, detail="Data laporan tidak ditemukan.")

    # Kunci "1 proses AI per waktu di server" yang sama dengan endpoint generate (analysis.py)
    # — sebelumnya retry TIDAK mengecek kunci ini sama sekali, bisa memicu 2 job Ollama jalan
    # bersamaan kalau user retry sementara laporan lain (siapa pun usernya) sedang diproses.
    if not try_acquire_ai_lock(db, report_id):
        db.refresh(db_report)
        if db_report.status == "processing":
            raise HTTPException(status_code=429, detail="Laporan ini sudah sedang diproses.")
        other_active_job = (
            db.query(Report)
            .filter(Report.status == "processing", Report.id != report_id)
            .first()
        )
        raise HTTPException(
            status_code=429,
            detail=f"Sistem sedang memproses analisis AI untuk laporan lain (ID: {other_active_job.id if other_active_job else '?'}). Mohon tunggu sebentar sebelum mencoba lagi."
        )

    db.refresh(db_report)

    from app.api.v1.endpoints.analysis import _run_analysis_job
    background_tasks.add_task(_run_analysis_job, report_id)

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

def _cleanup_old_export_cache(export_dir: str, max_age_days: int = 7):
    """RCA-17: Hapus file cache export PDF/PPTX di disk yang umurnya lebih dari max_age_days."""
    try:
        import os, time
        now = time.time()
        max_age_sec = max_age_days * 86400
        for fname in os.listdir(export_dir):
            fpath = os.path.join(export_dir, fname)
            if os.path.isfile(fpath) and (now - os.path.getmtime(fpath)) > max_age_sec:
                try:
                    os.remove(fpath)
                except Exception:
                    pass
    except Exception:
        pass


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
    _cleanup_old_export_cache(export_dir)
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
            logger.error(f"Gagal ekspor PDF utk report {report_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail="Gagal membuat berkas PDF untuk laporan ini. Silakan coba lagi atau hubungi admin."
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
            logger.error(f"Gagal ekspor PPTX utk report {report_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail="Gagal membuat berkas PPTX untuk laporan ini. Silakan coba lagi atau hubungi admin."
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