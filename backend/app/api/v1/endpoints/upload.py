# app/api/v1/endpoints/upload.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json

from app.db.session import get_db
from app.core.config import settings
from app.services.parser.factory import ParserFactory
from app.services.period_detector import detect_period
from app.crud.report import create_report
from app.schemas.report import ReportCreate, ReportResponse
from app.api.v1.endpoints.auth import get_current_user
from app.services.chart_generator import ChartGenerator
from app.services.ai_engine.section_suggester import suggest_sections_for_file
from app.utils.sanitizer import sanitize_for_json


router = APIRouter()

_MONTH_NAMES_EN = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _default_report_title(template_type: Optional[str]) -> str:
    """
    Judul template dipakai saat pengguna belum mengisi nama laporan sendiri — supaya laporan
    tidak pernah tersimpan dengan judul kosong. Formatnya "{Jenis Template} - {Bulan Tahun}",
    mis. "SOC Executive Summary - July 2026", bisa diganti pengguna kapan saja lewat halaman
    Preview & Edit atau History.
    """
    base = (template_type or "Laporan Analisis").split(" (")[0].strip()
    now = datetime.now()
    return f"{base} - {_MONTH_NAMES_EN[now.month - 1]} {now.year}"


def count_threats(parsed_data: list) -> dict:
    """
    Menghitung jumlah insiden keamanan berdasarkan level keparahan (severity) dari data log.
    Menangani berbagai macam variasi nama kunci severity yang dihasilkan oleh parser.
    """
    counters = {"critical": 0, "high": 0, "medium": 0, "low": 0, "informational": 0}
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
            elif "info" in val_str:
                # Dicek sebelum "low" supaya "Informational"/"Info" punya kategori sendiri,
                # bukan ikut ke-gabung ke "low" (dulu digabung, dashboard jadi harus
                # mengarang ulang angka informational dari 5% total low+medium).
                counters["informational"] += 1
            elif "low" in val_str:
                counters["low"] += 1

    return counters

@router.get("/ping")
def ping():
    return {"message": "upload module ready"}

@router.post("/detect-period")
def detect_period_from_file(
    file: UploadFile = File(...),
    current_user = Depends(get_current_user),
):
    """
    Parse cepat sebuah file (tanpa menyimpan apapun ke database) hanya untuk mendeteksi
    rentang tanggal (period_start/period_end) dari isinya, kalau ada kolom tanggal yang jelas.
    Dipanggil frontend sesaat setelah file dipilih di Step 1 (Upload Data), supaya field
    "Report Period" di Step 2 (Report Settings) sudah terisi otomatis.

    Kalau data tidak punya kolom tanggal yang bisa dideteksi (contoh: cuma ada "bulan": "Januari"
    tanpa tahun), period_start & period_end dikembalikan null — di sini frontend harus fallback
    ke pengisian manual oleh user.
    """
    try:
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if file.size is not None and file.size > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Ukuran berkas melebihi batas maksimum {settings.MAX_UPLOAD_SIZE_MB}MB."
            )

        try:
            parser = ParserFactory.get_parser(file.filename)
            raw_parsed = parser.parse(file.file)
            parsed_data = sanitize_for_json(raw_parsed)
        finally:
            file.file.close()

        period_start, period_end = detect_period(parsed_data)

        # Dynamic Section Suggester: coba AI dulu (butuh data LENGKAP untuk statistik akurat,
        # bukan potongan 10 baris), fallback ke preset heuristik kalau AI offline/gagal.
        columns = list(parsed_data[0].keys()) if parsed_data and len(parsed_data) > 0 else []
        suggestions = suggest_sections_for_file(columns=columns, sample_data=parsed_data, file_name=file.filename)

        return {
            "period_start": period_start,
            "period_end": period_end,
            "detected": period_start is not None and period_end is not None,
            "domain_type": suggestions["domain_type"],
            "domain_label": suggestions["domain_label"],
            "header_title": suggestions["header_title"],
            "header_subtitle": suggestions["header_subtitle"],
            "suggested_sections": suggestions["suggested_sections"],
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=f"Kesalahan validasi format data: {str(ve)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal membaca berkas untuk deteksi periode: {str(e)}")

@router.post("/", response_model=ReportResponse)
def upload_security_file(
    title: str = Form(...),
    data_type: str = Form(...),  # firewall, email_security, ids_ips, vapt, keuangan, kpi_hr, dll.
    files: List[UploadFile] = File(...),
    period_start: Optional[str] = Form(None),  # Format YYYY-MM-DD
    period_end: Optional[str] = Form(None),    # Format YYYY-MM-DD
    template_type: Optional[str] = Form("SOC Executive Summary (Monthly)"),
    output_format: Optional[str] = Form("PDF"),
    language: Optional[str] = Form("Indonesian"),
    include_ai_insights: bool = Form(True),
    include_raw_data_summary: bool = Form(True),
    included_sections: Optional[str] = Form(None),  # JSON string [{"key": "...", "title": "..."}, ...]
    header_title: Optional[str] = Form("PT PETROKIMIA GRESIK"),
    header_subtitle: Optional[str] = Form("Sistem Otomasi Laporan & Eksekutif Presentasi Berbasis AI"),
    theme_color: Optional[str] = Form("green"),
    domain_type: Optional[str] = Form("general"),
    tone: Optional[str] = Form("Professional"),  # Professional, Technical, Executive
    default_level: Optional[str] = Form("Standard"),  # Standard, Detailed, Summary Only
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    """
    Mengunggah berkas log keamanan, mengurainya via Parser, dan menyimpan laporannya ke DB 
    dengan konfigurasi awal (status Draft/Uploaded) untuk siap diproses di Step 3 oleh AI.
    """
    try:
        # Judul belum tentu diisi pengguna di form upload — pakai nama template otomatis
        # supaya tidak pernah tersimpan kosong (bisa diganti belakangan di Preview & Edit/History).
        title = title.strip() if title else ""
        if not title:
            title = _default_report_title(template_type)

        # Konversi tanggal periode log dengan validasi string kosong (Next.js Form safe)
        p_start = None
        p_end = None
        
        if period_start and period_start.strip():
            try:
                p_start = datetime.strptime(period_start.strip()[:10], "%Y-%m-%d").date()
            except Exception:
                p_start = None
        if period_end and period_end.strip():
            try:
                p_end = datetime.strptime(period_end.strip()[:10], "%Y-%m-%d").date()
            except Exception:
                p_end = None

        if not files:
            raise HTTPException(status_code=400, detail="Tidak ada berkas yang diunggah.")

        # Validasi konsistensi ekstensi file jika mengunggah beberapa file sekaligus
        if len(files) > 1:
            exts = {f.filename.split(".")[-1].lower() for f in files if "." in f.filename}
            if len(exts) > 1:
                raise HTTPException(
                    status_code=400,
                    detail="Semua berkas yang diunggah sekaligus harus memiliki format/ekstensi yang sama (contoh: semua .csv atau semua .xlsx)."
                )

        # Baca & parse SEMUA file yang diunggah, gabungkan hasilnya jadi satu daftar data
        # (baris dari tiap file digabung apa adanya — kalau strukturnya beda antar file,
        # kolom yang tidak ada di salah satu file otomatis kosong saat diproses ke DataFrame
        # di chart_generator.py/count_threats, bukan error).
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        
        # RCA-16: Cek total akumulasi kuota penyimpanan user di database (Maks 1GB per user)
        from sqlalchemy import func as _func
        from app.models.report import Report as _Report
        existing_user_bytes = db.query(_func.coalesce(_func.sum(_Report.total_file_size_bytes), 0)).filter(_Report.user_id == current_user.id).scalar() or 0
        USER_MAX_QUOTA_BYTES = 1024 * 1024 * 1024  # 1 GB
        
        parsed_data = []
        file_names = []
        total_size_bytes = 0
        for f in files:
            # Validasi ukuran berkas SEBELUM diproses, sesuai batas di settings (MAX_UPLOAD_SIZE_MB).
            if f.size is not None and f.size > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"Ukuran berkas '{f.filename}' melebihi batas maksimum {settings.MAX_UPLOAD_SIZE_MB}MB."
                )
            total_size_bytes += f.size or 0

        if existing_user_bytes + total_size_bytes > USER_MAX_QUOTA_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Total kuota penyimpanan akun Anda (1 GB) telah penuh. Silakan hapus beberapa laporan lama di Riwayat sebelum mengunggah file baru."
            )

        # Proses parsing masing-masing file setelah semua validasi ukuran lolos
        for f in files:
            try:
                parser = ParserFactory.get_parser(f.filename)
                raw_parsed = parser.parse(f.file)
            except ValueError as file_err:
                # Kasih tau berkas MANA yang bermasalah, bukan cuma "gagal" generik —
                # penting kalau user upload beberapa file sekaligus.
                raise ValueError(f"Berkas '{f.filename}': {str(file_err)}")
            finally:
                # Pastikan file stream ditutup dengan aman setelah dibaca oleh parser
                f.file.close()

            parsed_data.extend(sanitize_for_json(raw_parsed))
            file_names.append(f.filename)

        # Hitung statistik ancaman dari log siber yang diunggah (gabungan semua file)
        threat_metrics = count_threats(parsed_data)
        total_records = len(parsed_data) if parsed_data else 0

        # Parse pilihan section dari frontend. Kalau gagal/kosong, biarkan None (backward
        # compat: export_pdf.py/export_ppt.py menampilkan semua section kalau ini None).
        # Bisa berbentuk dict (jalur lama: checkbox preset {key: bool}) ATAU list (jalur baru
        # PART A2: section dinamis usulan AI yang dipilih user, tiap item {key,title,order,...}).
        parsed_sections = None
        if included_sections:
            try:
                parsed_sections = json.loads(included_sections)
                if not isinstance(parsed_sections, (dict, list)):
                    parsed_sections = None
            except (json.JSONDecodeError, TypeError):
                parsed_sections = None

        # Buat instansiasi schema ReportCreate
        report_in = ReportCreate(
            title=title,
            data_type=data_type,
            input_file_name=", ".join(file_names),
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
            threat_count_info=threat_metrics["informational"],
            total_records_parsed=total_records,
            total_file_size_bytes=total_size_bytes,
            included_sections=parsed_sections,
            header_title=header_title,
            header_subtitle=header_subtitle,
            theme_color=theme_color,
            domain_type=domain_type,
            tone=tone,
            default_level=default_level
        )

        
        db_report = create_report(db, report_in, user_id=current_user.id)

        # Fix #2: Simpan parsed_data ke file system alih-alih membiarkannya di kolom JSON DB.
        # Kolom JSON di DB masih terisi (dari create_report) — kita pindahkan ke file dan hapus dari DB.
        try:
            import os
            parsed_dir = os.path.join(
                os.path.dirname(__file__), "..", "..", "..", "..", "storage", "parsed"
            )
            os.makedirs(parsed_dir, exist_ok=True)
            parsed_file_path = os.path.join(parsed_dir, f"parsed_{db_report.id}.json")
            with open(parsed_file_path, "w", encoding="utf-8") as pf:
                import json as _json
                _json.dump(parsed_data, pf, ensure_ascii=False)
            # Update DB: set path, kosongkan kolom JSON besar
            db_report.parsed_data_path = parsed_file_path
            db_report.parsed_data = None  # Hapus data besar dari DB column
            db.commit()
            db.refresh(db_report)
        except Exception as fs_err:
            # Jika gagal simpan ke file system, biarkan parsed_data tetap di DB sebagai fallback
            print(f"[UPLOAD] ⚠️ Gagal simpan parsed_data ke file system, fallback ke DB column: {fs_err}")

        # Trigger Notifikasi Upload Berhasil
        try:
            from app.schemas.notification import NotificationCreate
            from app.crud.notification import create_notification
            create_notification(
                db,
                NotificationCreate(
                    user_id=current_user.id,
                    type="info",
                    title="Data Parsing Complete",
                    message=f"Berkas '{db_report.input_file_name}' ({total_records} baris) berhasil di-parse.",
                    link=f"/history/{db_report.id}"
                )
            )
        except Exception as notif_err:
            print(f"[UPLOAD] Gagal buat notifikasi upload: {notif_err}")

        # Fix #9: Audit log untuk aksi upload
        try:
            from app.crud.audit_log import log_action
            log_action(
                db, user_id=current_user.id, action="upload",
                resource_type="report", resource_id=db_report.id,
                detail=f"File '{db_report.input_file_name}' ({total_records} baris) diunggah dan di-parse.",
            )
        except Exception:
            pass

        return db_report

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=f"Kesalahan validasi format data: {str(ve)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memproses unggahan log siber: {str(e)}")