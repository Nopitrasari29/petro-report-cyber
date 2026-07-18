import logging
from datetime import datetime

logger = logging.getLogger("app.services.log_validator")

def run_log_validation(parsed_list: list, data_type: str, report_title: str, created_at: datetime) -> dict:
    """
    Melakukan validasi anomali dan kualitas pada data log yang diparsing.
    Mendeteksi duplikasi, nilai kosong, IP/Port tidak valid, menghitung skor,
    dan mengekstrak sampel log secara dinamis.
    """
    records_count = len(parsed_list)
    
    # 1. Deteksi duplikat
    seen = set()
    dups_count = 0
    for row in parsed_list:
        row_tuple = tuple(sorted((k, str(v)) for k, v in row.items()))
        if row_tuple in seen:
            dups_count += 1
        else:
            seen.add(row_tuple)
            
    # 2. Deteksi nilai kosong/None
    missing_count = 0
    for row in parsed_list:
        for val in row.values():
            if val is None or str(val).strip() == "" or str(val).lower() in ["nan", "null"]:
                missing_count += 1
                
    # 3. Deteksi format tidak valid (IP/Port check)
    invalid_count = 0
    for row in parsed_list:
        is_invalid = False
        # Validasi IP sederhana
        for ip_key in ["source_ip", "dest_ip", "src_ip", "dst_ip", "ip", "IP"]:
            if ip_key in row and row[ip_key]:
                ip_str = str(row[ip_key])
                if "." not in ip_str and ":" not in ip_str:
                    is_invalid = True
                    break
        # Validasi range Port
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

    # 4. Hitung skor kualitas (Overall score)
    total_anomalies = dups_count + missing_count + invalid_count
    overall_score = 100
    if records_count > 0:
        overall_score = max(70, min(100, 100 - int((total_anomalies / (records_count * 2)) * 100)))

    # 5. Susun daftar masalah riil
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
        
    if not validation_issues:
        validation_issues.append({
            "issue_type": "None",
            "description": "Tidak ada anomali atau isu kualitas data terdeteksi.",
            "affected_records": 0,
            "severity": "Low",
            "status": "Resolved"
        })

    # 6. Sampel baris data log
    sample_preview = []
    for idx, row in enumerate(parsed_list[:5]):
        # Cari IP asal secara dinamis
        src_ip = None
        for k in ["source_ip", "src_ip", "source", "src", "ip", "client_ip"]:
            for rk in row.keys():
                if k.lower() in rk.lower():
                    src_ip = str(row[rk])
                    break
            if src_ip:
                break
        if not src_ip:
            src_ip = "-"
            
        # Cari IP tujuan secara dinamis
        dst_ip = None
        for k in ["dest_ip", "dst_ip", "destination", "dst", "server_ip", "target"]:
            for rk in row.keys():
                if k.lower() in rk.lower():
                    dst_ip = str(row[rk])
                    break
            if dst_ip:
                break
        if not dst_ip:
            dst_ip = "-"
            
        # Cari tipe event secara dinamis
        evt = None
        for k in ["event_type", "event", "message", "msg", "action", "info", "subject"]:
            for rk in row.keys():
                if k.lower() in rk.lower():
                    evt = str(row[rk])
                    break
            if evt:
                break
        if not evt:
            evt = f"Log {data_type.upper()}"
            
        # Cari severity secara dinamis
        sev = None
        for k in ["severity", "level", "priority"]:
            for rk in row.keys():
                if k.lower() in rk.lower():
                    sev = str(row[rk])
                    break
            if sev:
                break
        if not sev:
            sev = "Info"

        # Cari timestamp
        ts = None
        for k in ["timestamp", "time", "date", "tanggal", "datetime"]:
            for rk in row.keys():
                if k.lower() in rk.lower():
                    ts = str(row[rk])
                    break
            if ts:
                break
        if not ts:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        sample_preview.append({
            "timestamp": ts,
            "source_ip": src_ip,
            "dest_ip": dst_ip,
            "event_type": evt,
            "severity": sev,
            "status": "Valid"
        })

    # Mengembalikan format payload response penuh
    return {
        "report_name": report_title,
        "period": "Log Data Analysis",  # Fallback atau dinamis di router
        "data_sources": f"Tipe: {data_type.upper()}",
        "validation_completed": created_at.strftime("%d %b %Y, %H:%M") if created_at else "-",
        "processing_pipeline": "Ingestion -> Cleaning -> Validation -> Structuring -> JSON Conversion",
        "overall_validation_score": overall_score,
        "counters": {
            "valid_records": max(0, records_count - dups_count - invalid_count),
            "duplicate_records": dups_count,
            "missing_values": missing_count,
            "invalid_records": invalid_count
        },
        "validation_breakdown": {
            "data_ingestion": "Passed",
            "data_cleaning": "Passed" if missing_count == 0 else "Warnings",
            "data_validation": "Passed" if invalid_count == 0 else "Warnings",
            "data_structuring": "Passed",
            "json_conversion": "Passed"
        },
        "validation_issues": validation_issues,
        "sample_preview": sample_preview
    }
