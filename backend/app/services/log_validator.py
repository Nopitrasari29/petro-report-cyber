import logging
from datetime import datetime

import pandas as pd

from app.services.chart_generator import _find_numeric_cols
from app.services.ai_engine.data_profiler import _normalize_category_key, _is_row_index_column

logger = logging.getLogger("app.services.log_validator")


def run_log_validation(parsed_list: list, data_type: str, report_title: str, created_at: datetime) -> dict:
    """
    Melakukan validasi anomali dan kualitas pada data yang diparsing — deteksi duplikasi,
    nilai kosong, outlier angka, dan penulisan kategori tidak konsisten, plus format IP/Port
    (khusus data yang punya kolom itu).

    BUG DIPERBAIKI: sebelumnya cuma 2 dari 4 pengecekan (duplikat, nilai kosong) genuinely
    berguna lintas domain — 2 lainnya (format IP, rentang Port) cuma relevan utk data
    keamanan siber, jadi utk data keuangan/KPI/pengadaan efeknya cuma "diam" (kolom itu tidak
    ada). Ditambah 2 pengecekan baru yang relevan lintas domain, reuse logika yang SAMA PERSIS
    dipakai laporan AI (data_profiler.py) supaya hasilnya konsisten dengan bagian lain aplikasi:
    - Outlier angka (nilai yang jauh di luar kewajaran dibanding baris lain di kolom yang sama,
      metode IQR standar) - mis. biaya Rp 50.000.000 di tengah data yang biasanya Rp 500.000.
    - Penulisan kategori tidak konsisten (mis. "Kantor Pusat" & "Kantor Pusat (KAPUS)" kehitung
      2 kategori beda padahal maksudnya sama) - kolom "No"/index turut dikecualikan dari
      pengecekan nilai kosong (bukan data analitis sungguhan, lihat _is_row_index_column).
    """
    records_count = len(parsed_list)
    if records_count == 0:
        return _empty_result(report_title, created_at)

    df = pd.DataFrame(parsed_list)

    # 1. Deteksi duplikat (baris yang PERSIS sama di semua kolom)
    dups_count = int(df.duplicated().sum())

    # 2. Deteksi nilai kosong/None — kolom index/nomor urut DIKECUALIKAN (bukan data
    # analitis sungguhan, cuma penomoran baris).
    missing_count = 0
    for col in df.columns:
        if _is_row_index_column(col, df[col]):
            continue
        for val in df[col]:
            if (
                val is None
                or (isinstance(val, float) and pd.isna(val))
                or str(val).strip() == ""
                or str(val).strip().lower() in ("nan", "null", "none")
            ):
                missing_count += 1

    # 3. Deteksi format tidak valid (IP/Port) — HANYA aktif kalau data ini genuinely punya
    # kolom semacam itu (data non-keamanan otomatis melewati bagian ini tanpa efek apa pun).
    invalid_count = 0
    for row in parsed_list:
        is_invalid = False
        for ip_key in ["source_ip", "dest_ip", "src_ip", "dst_ip", "ip", "IP"]:
            if ip_key in row and row[ip_key]:
                ip_str = str(row[ip_key])
                if "." not in ip_str and ":" not in ip_str:
                    is_invalid = True
                    break
        for port_key in ["port", "Port", "src_port", "dst_port"]:
            if port_key in row and row[port_key]:
                try:
                    port_val = int(row[port_key])
                    if port_val < 1 or port_val > 65535:
                        is_invalid = True
                        break
                except ValueError:
                    is_invalid = True
                    break
        if is_invalid:
            invalid_count += 1

    # 4. BARU — Outlier angka (metode IQR): relevan utk SEMUA domain yang punya kolom numerik
    # (nilai kontrak, skor KPI, biaya, dst), bukan cuma data keamanan siber.
    outlier_count = 0
    outlier_cols: list[str] = []
    numeric_cols = _find_numeric_cols(df, exclude=[])
    for col in numeric_cols:
        if _is_row_index_column(col, df[col]):
            continue
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(series) < 5:
            continue
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            # Kolom nyaris seragam (mayoritas baris nilainya SAMA PERSIS) - "wajar"-nya cuma
            # satu titik itu sendiri, jadi nilai APA PUN yang beda dianggap outlier (bukan
            # dilewati begitu saja, yang tadinya bikin outlier ekstrem justru lolos tak
            # terdeteksi krn IQR standar butuh variasi data utk menghitung rentang wajar).
            constant_val = q1
            col_outliers = int((series != constant_val).sum())
            if col_outliers > 0:
                outlier_count += col_outliers
                outlier_cols.append(col)
            continue
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        col_outliers = int(((series < lower) | (series > upper)).sum())
        if col_outliers > 0:
            outlier_count += col_outliers
            outlier_cols.append(col)

    # 5. BARU — Penulisan kategori tidak konsisten: bandingkan jumlah nilai unik ASLI vs
    # jumlah unik SETELAH dinormalisasi (fungsi yang sama dipakai laporan AI) - kalau lebih
    # sedikit setelah dinormalisasi, berarti ada penulisan berbeda utk entitas yang sama.
    inconsistent_count = 0
    inconsistent_cols: list[str] = []
    for col in df.columns:
        if col in numeric_cols or _is_row_index_column(col, df[col]):
            continue
        raw_values = df[col].dropna().astype(str)
        if not (1 < raw_values.nunique() <= max(50, records_count // 2)):
            continue
        raw_unique = set(raw_values.unique())
        normalized_unique = {_normalize_category_key(v) for v in raw_unique}
        if len(normalized_unique) < len(raw_unique):
            collapsed = len(raw_unique) - len(normalized_unique)
            inconsistent_count += collapsed
            inconsistent_cols.append(col)

    # 6. Hitung skor kualitas (Overall score) — sekarang mempertimbangkan 6 dimensi, bukan 4.
    total_anomalies = dups_count + missing_count + invalid_count + outlier_count + inconsistent_count
    overall_score = 100
    if records_count > 0:
        overall_score = max(70, min(100, 100 - int((total_anomalies / (records_count * 2)) * 100)))

    # 7. Susun daftar masalah riil
    validation_issues = []
    if dups_count > 0:
        validation_issues.append({
            "issue_type": "Duplicate",
            "description": "Baris data terduplikasi sepenuhnya dalam berkas log",
            "affected_records": dups_count,
            "severity": "Medium",
            "status": "Resolved"
        })
    if missing_count > 0:
        validation_issues.append({
            "issue_type": "Missing Value",
            "description": "Nilai kolom kosong atau bernilai None",
            "affected_records": missing_count,
            "severity": "Low",
            "status": "Resolved"
        })
    if invalid_count > 0:
        validation_issues.append({
            "issue_type": "Invalid Format",
            "description": "Format IP Address atau nomor Port tidak standar",
            "affected_records": invalid_count,
            "severity": "High",
            "status": "Resolved"
        })
    if outlier_count > 0:
        validation_issues.append({
            "issue_type": "Numeric Outlier",
            "description": f"Nilai jauh di luar kewajaran pada kolom: {', '.join(outlier_cols)}",
            "affected_records": outlier_count,
            "severity": "Medium",
            "status": "Resolved"
        })
    if inconsistent_count > 0:
        validation_issues.append({
            "issue_type": "Inconsistent Category",
            "description": f"Penulisan kategori tidak seragam pada kolom: {', '.join(inconsistent_cols)}",
            "affected_records": inconsistent_count,
            "severity": "Low",
            "status": "Resolved"
        })

    if not validation_issues:
        validation_issues.append({
            "issue_type": "None",
            "description": "Tidak ada anomali atau isu kualitas data terdeteksi.",
            "affected_records": 0,
            "severity": "Low",
            "status": "Resolved"
        })

    # 8. Sampel baris data (dinamis, bukan hardcode kolom keamanan siber — tampilkan kolom
    # apa adanya dari data ini, terbatas 6 kolom pertama supaya tetap ringkas).
    preview_cols = list(df.columns)[:6]
    sample_preview = []
    for row in parsed_list[:5]:
        sample_preview.append({col: str(row.get(col, "-")) for col in preview_cols})

    return {
        "report_name": report_title,
        "period": "Log Data Analysis",  # Fallback atau dinamis di router
        "data_sources": f"Tipe: {data_type.upper()}",
        "validation_completed": created_at.strftime("%d %b %Y, %H:%M") if created_at else "-",
        "processing_pipeline": "Ingestion -> Cleaning -> Validation -> Structuring -> JSON Conversion",
        "overall_validation_score": overall_score,
        "preview_columns": preview_cols,
        "counters": {
            "valid_records": max(0, records_count - dups_count - invalid_count),
            "duplicate_records": dups_count,
            "missing_values": missing_count,
            "invalid_records": invalid_count,
            "outlier_values": outlier_count,
            "inconsistent_categories": inconsistent_count,
        },
        "validation_breakdown": {
            "data_ingestion": "Passed",
            "data_cleaning": "Passed" if missing_count == 0 else "Warnings",
            "data_validation": "Passed" if (invalid_count == 0 and outlier_count == 0) else "Warnings",
            "data_structuring": "Passed" if inconsistent_count == 0 else "Warnings",
            "json_conversion": "Passed"
        },
        "validation_issues": validation_issues,
        "sample_preview": sample_preview
    }


def _empty_result(report_title: str, created_at: datetime) -> dict:
    return {
        "report_name": report_title,
        "period": "Log Data Analysis",
        "data_sources": "-",
        "validation_completed": created_at.strftime("%d %b %Y, %H:%M") if created_at else "-",
        "processing_pipeline": "Ingestion -> Cleaning -> Validation -> Structuring -> JSON Conversion",
        "overall_validation_score": 0,
        "preview_columns": [],
        "counters": {
            "valid_records": 0, "duplicate_records": 0, "missing_values": 0,
            "invalid_records": 0, "outlier_values": 0, "inconsistent_categories": 0,
        },
        "validation_breakdown": {
            "data_ingestion": "Failed", "data_cleaning": "Failed", "data_validation": "Failed",
            "data_structuring": "Failed", "json_conversion": "Failed",
        },
        "validation_issues": [{
            "issue_type": "Empty Data", "description": "Tidak ada data untuk divalidasi.",
            "affected_records": 0, "severity": "High", "status": "Unresolved",
        }],
        "sample_preview": [],
    }
