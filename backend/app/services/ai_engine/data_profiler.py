# app/services/ai_engine/data_profiler.py
"""
Precompute statistik dari data log mentah sebelum dikirim ke model AI (qwen3:8b).

LATAR BELAKANG: model kecil seperti qwen3:8b buruk kalau disuruh menghitung sendiri dari
ratusan baris data mentah (sering mengarang angka, salah hitung persentase, dll). Modul ini
memindahkan semua PERHITUNGAN ke Python/pandas (deterministik, selalu benar) — model AI
tinggal MENARASIKAN angka yang sudah pasti benar, bukan menghitung dari nol.

Deteksi kolom (severity, kategori, tanggal) berbasis ISI DATA, bukan nama kolom yang
di-hardcode — dipakai ulang dari chart_generator.py (_find_col, _rank_categorical_candidates)
dan period_detector.py (find_date_column) supaya konsisten dengan deteksi yang sudah dipakai
di fitur chart, bukan implementasi terpisah yang bisa berbeda hasil.
"""
import re
from typing import Any, Dict, List, Optional
import pandas as pd

from app.services.chart_generator import _find_col, _find_numeric_cols, _rank_categorical_candidates
from app.services.period_detector import find_date_column

# Kata kunci nama kolom per "niat" kategori utama yang disebutkan pengguna — dicoba dulu
# karena cepat & presisi kalau nama kolomnya memang lazim. Kolom yang tidak match salah satu
# ini akan diisi dari _rank_categorical_candidates (fallback berbasis isi) di compute_statistics.
_CATEGORY_INTENTS: Dict[str, List[str]] = {
    "source_ip": ["source_ip", "src_ip", "source ip", "ip_source", "ip_address", "src", "sumber_ip"],
    "destination_port": ["destination_port", "dst_port", "port", "target_port"],
    "location": ["location", "lokasi", "site", "region", "cabang"],
    "action": ["action", "tindakan", "response"],
    "status": ["status", "state", "kondisi"],
    # "asset" = ASET/TARGET yang diserang — beda makna dari "source_ip" (itu IP PENYERANG),
    # dibutuhkan supaya slide "Aset paling sering jadi sasaran" tidak keliru pakai IP penyerang.
    "asset": ["asset", "aset", "host", "hostname", "device", "server", "destination_ip",
              "dst_ip", "destination_host", "target", "endpoint"],
}

_SEVERITY_KEYWORDS = ["severity", "level", "priority", "tingkat", "threat_level", "risk", "status"]

# Maksimum kolom kategorikal (di luar severity) yang dihitung top-10-nya, supaya ringkasan
# tetap ringkas dan tidak membebani konteks model dengan puluhan kolom yang tidak relevan.
_MAX_CATEGORY_COLUMNS = 5


def _classify_severity_value(val_str: str) -> Optional[str]:
    """
    Aturan pengelompokan PERSIS SAMA dengan count_threats() di upload.py — supaya angka
    yang dinarasikan AI konsisten dengan threat_count_* yang sudah tampil di dashboard/riwayat,
    bukan dua sumber angka yang bisa beda kalau logikanya sedikit saja berbeda.
    """
    val_str = val_str.strip().lower()
    buckets = {"critical", "high", "medium", "low", "informational"}
    if val_str in buckets:
        return val_str
    if "crit" in val_str:
        return "critical"
    if "high" in val_str or "severe" in val_str:
        return "high"
    if "med" in val_str or "warn" in val_str:
        return "medium"
    if "info" in val_str:
        return "informational"
    if "low" in val_str:
        return "low"
    return None


def _detect_severity_column(df: pd.DataFrame, exclude: List[str]) -> Optional[str]:
    col = _find_col(df, _SEVERITY_KEYWORDS)
    if col:
        return col
    candidates = _rank_categorical_candidates(df, exclude=exclude, max_unique=8)
    return candidates[0] if candidates else None


def _compute_severity_distribution(df: pd.DataFrame, sev_col: Optional[str]) -> Dict[str, int]:
    empty_counters = {"critical": 0, "high": 0, "medium": 0, "low": 0, "informational": 0}
    if not sev_col or sev_col not in df.columns:
        return empty_counters

    values = df[sev_col].dropna()
    if values.empty:
        return empty_counters

    counters = dict(empty_counters)
    classified = 0
    for raw_val in values:
        bucket = _classify_severity_value(str(raw_val))
        if bucket:
            counters[bucket] += 1
            classified += 1

    # Kalau sebagian besar nilai TIDAK bisa diklasifikasi ke salah satu bucket, kolom ini
    # kemungkinan besar bukan kolom severity keamanan siber sungguhan — mis. kolom "Status"
    # berisi "Normal"/"Warning" untuk pemantauan jaringan, bukan kosakata severity baku.
    # Kembalikan kosong (bukan hitungan parsial) supaya bagian ini disembunyikan sepenuhnya
    # di laporan, alih-alih menampilkan persentase yang dihitung dari sebagian data saja
    # dan jadi menyesatkan (contoh nyata: nilai "Normal" hilang dari total, membuat
    # persentase Critical terlihat 69% padahal sebenarnya cuma ~40% dari seluruh data).
    if classified < 0.7 * len(values):
        return empty_counters
    return counters


def _detect_main_category_columns(df: pd.DataFrame, exclude: List[str]) -> Dict[str, str]:
    """
    Cari kolom untuk tiap "niat" kategori (source_ip, port, lokasi, action, status) via nama
    dulu; niat yang tidak ketemu namanya diisi dari kandidat berbasis-isi yang belum dipakai
    kolom lain. Return dict {label: nama_kolom_asli} — label bisa nama niat ("source_ip") atau
    label generik ("category_2") kalau diisi dari fallback tanpa niat spesifik.
    """
    used = set(c.lower() for c in exclude)
    result: Dict[str, str] = {}

    for intent, keywords in _CATEGORY_INTENTS.items():
        col = _find_col(df, keywords)
        if col and col.lower() not in used:
            result[intent] = col
            used.add(col.lower())

    if len(result) < _MAX_CATEGORY_COLUMNS:
        fallback_candidates = _rank_categorical_candidates(
            df, exclude=list(used), max_unique=40
        )
        for col in fallback_candidates:
            if len(result) >= _MAX_CATEGORY_COLUMNS:
                break
            if col.lower() in used:
                continue
            result[f"category_{len(result) + 1}"] = col
            used.add(col.lower())

    return result


_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*")


def _normalize_category_key(value: str) -> str:
    """Kunci penggabungan untuk nilai kategori yang penulisannya mirip (mis. "Kantor Pusat
    (KAPUS)" dan "Kantor Pusat" seharusnya dihitung sebagai entitas yang sama, bukan 2
    kategori terpisah yang understate konsentrasi sebenarnya) — menghapus keterangan dalam
    kurung dan menyeragamkan spasi/huruf besar-kecil sebelum dibandingkan."""
    cleaned = _PAREN_RE.sub(" ", str(value))
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def _top_values(df: pd.DataFrame, col: str, n: int = 10) -> List[Dict[str, Any]]:
    raw_counts = df[col].dropna().astype(str).value_counts()
    merged: Dict[str, Dict[str, Any]] = {}
    for val, cnt in raw_counts.items():
        key = _normalize_category_key(val)
        if key not in merged:
            merged[key] = {"value": val, "count": 0}
        elif len(val) < len(merged[key]["value"]):
            # Pilih varian penulisan TERPENDEK sebagai label tampilan — biasanya bentuk
            # paling bersih tanpa keterangan/singkatan tambahan dalam kurung.
            merged[key]["value"] = val
        merged[key]["count"] += int(cnt)
    items = sorted(merged.values(), key=lambda x: x["count"], reverse=True)[:n]
    return items


_INDEX_COLUMN_NAMES = {"no", "no.", "nomor", "id", "index", "idx", "num", "urut", "row", "row_number", "#"}


def _is_row_index_column(col_name: str, series: "pd.Series") -> bool:
    """True kalau kolom ini kemungkinan besar cuma nomor urut baris (mis. "No": 1,2,3,...),
    bukan data analitis sungguhan — supaya tidak ikut dihitung sebagai statistik "sah"
    (min/max/rata-rata) yang dikirim ke AI sebagai bagian dari angka yang harus dipercaya,
    padahal isinya cuma indeks baris tanpa makna apa pun untuk analisis."""
    if col_name.strip().lower() in _INDEX_COLUMN_NAMES:
        return True
    values = series.dropna()
    if len(values) < 2:
        return False
    try:
        sorted_vals = sorted(int(v) for v in values)
    except (ValueError, TypeError):
        return False
    return sorted_vals == list(range(sorted_vals[0], sorted_vals[0] + len(sorted_vals)))


def _compute_numeric_summary(df: pd.DataFrame, exclude: List[str]) -> Dict[str, Dict[str, float]]:
    result = {}
    for col in _find_numeric_cols(df, exclude=exclude):
        series = df[col].dropna()
        if series.empty:
            continue
        if _is_row_index_column(col, series):
            continue
        result[col] = {
            "min": round(float(series.min()), 2),
            "max": round(float(series.max()), 2),
            "mean": round(float(series.mean()), 2),
        }
    return result


def _compute_time_pattern(date_series: "pd.Series") -> Dict[str, Any]:
    valid = date_series.dropna()
    result: Dict[str, Any] = {}
    if valid.empty:
        return result

    day_counts = valid.dt.day_name().value_counts()
    if not day_counts.empty:
        result["peak_day_of_week"] = str(day_counts.idxmax())

    hours = valid.dt.hour
    if hours.nunique() > 1:
        result["peak_hour"] = int(hours.value_counts().idxmax())

    # Tren antar periode: bagi dua berdasar median waktu, bandingkan jumlah event
    # paruh pertama vs kedua — cara sederhana & jujur untuk "naik/turun berapa persen"
    # tanpa mengasumsikan periode kalender tertentu (mingguan/bulanan) yang belum tentu
    # cocok dengan rentang data yang diupload.
    if len(valid) >= 4:
        sorted_vals = valid.sort_values()
        midpoint = sorted_vals.iloc[len(sorted_vals) // 2]
        first_half = int((sorted_vals < midpoint).sum())
        second_half = int((sorted_vals >= midpoint).sum())
        if first_half > 0:
            pct_change = round(((second_half - first_half) / first_half) * 100, 1)
            result["trend"] = {
                "first_half_count": first_half,
                "second_half_count": second_half,
                "pct_change": pct_change,
            }

    return result


def compute_statistics(parsed_data: List[Dict[str, Any]], data_type: str) -> Dict[str, Any]:
    """
    Entry point poin 1. Mengembalikan dict statistik terhitung (deterministik, pandas) siap
    dinarasikan model AI — BUKAN mentah-mentah data log. Aman dipanggil dengan data kosong.
    """
    if not parsed_data:
        return {"total_records": 0}

    df = pd.DataFrame(parsed_data)
    if df.empty:
        return {"total_records": 0}

    stats: Dict[str, Any] = {"total_records": len(df)}

    date_col, date_series = find_date_column(parsed_data)
    exclude_for_categorical = [date_col] if date_col else []

    sev_col = _detect_severity_column(df, exclude=exclude_for_categorical)
    stats["severity_distribution"] = _compute_severity_distribution(df, sev_col)

    exclude_for_top = exclude_for_categorical + ([sev_col] if sev_col else [])
    category_cols = _detect_main_category_columns(df, exclude=exclude_for_top)
    stats["top_categories"] = {
        label: _top_values(df, col) for label, col in category_cols.items()
    }
    # Mapping label -> nama kolom ASLI (mis. "category_3" -> "jenis_insiden") — dipakai
    # exporter (export_ppt.py/export_pdf.py) utk membaca nilai baris mentah per kolom yang
    # tepat (mis. tabel insiden), tanpa perlu menebak ulang deteksi kolom yang sama persis.
    # Prefix underscore = bukan bagian narasi AI (format_statistics_as_text tidak memakainya).
    stats["_source_columns"] = {
        "date": date_col,
        "severity": sev_col,
        **category_cols,
    }

    if date_col and date_series is not None:
        stats["time_pattern"] = _compute_time_pattern(date_series)

    exclude_for_numeric = exclude_for_top + list(category_cols.values())
    numeric_summary = _compute_numeric_summary(df, exclude=exclude_for_numeric)
    if numeric_summary:
        stats["numeric_summary"] = numeric_summary

    return stats


def _humanize_stats_label(label: str, source_cols: Dict[str, str]) -> str:
    """Ganti label generik "category_N" dengan nama kolom ASLI dari file yang diupload (mis.
    "Vendor", "Departemen") kalau tersedia di `_source_columns` — supaya model AI tahu PERSIS
    konsep apa yang sedang dilihat (bukan cuma "category_1"), mengurangi ambiguitas yang bisa
    ikut berkontribusi model salah mengaitkan angka ke entitas yang keliru. Duplikat kecil dari
    logika `humanize_label` di report_render_logic.py (bukan diimpor dari sana) supaya modul ini
    tidak circular-import (report_render_logic.py justru yang mengimpor dari modul ini)."""
    if label.startswith("category_"):
        real_name = source_cols.get(label)
        if real_name:
            return str(real_name).replace("_", " ").strip().title()
    return label.replace("_", " ").title()


_DAY_NAME_ID = {
    "Monday": "Senin", "Tuesday": "Selasa", "Wednesday": "Rabu", "Thursday": "Kamis",
    "Friday": "Jumat", "Saturday": "Sabtu", "Sunday": "Minggu",
}


def format_statistics_as_text(stats: Dict[str, Any], language: str | None = None) -> str:
    """Ubah dict statistik jadi teks ringkas siap tempel ke prompt (mudah dibaca model).

    `language`: bahasa laporan (default None = Indonesia, konsisten dengan default lain di
    seluruh pipeline ini) — BUG NYATA YANG DIPERBAIKI (dilaporkan user): `peak_day_of_week`
    dihitung lewat `pandas.Series.dt.day_name()`, yang SELALU mengembalikan nama hari Bahasa
    Inggris ("Friday") apa pun locale server, lalu ikut ditempel ke stats_text apa adanya —
    model AI lantas mengutip kata Inggris itu mentah-mentah di tengah caption Bahasa Indonesia
    (laporan nyata: "...pola hari Jumat..." tercampur "Friday"). Diterjemahkan di SINI (lapisan
    presentasi/teks-ke-prompt), bukan di `_compute_time_pattern` — supaya nilai di dict statistik
    sendiri tetap murni/tidak berasumsi bahasa apa pun."""
    if stats.get("total_records", 0) == 0:
        return "Tidak ada data untuk dianalisis."

    lines = [f"Total records: {stats['total_records']}"]

    sev = stats.get("severity_distribution")
    if sev:
        sev_total = sum(sev.values())
        if sev_total > 0:
            sev_str = ", ".join(f"{k}: {v} ({round(v/sev_total*100, 1)}%)" for k, v in sev.items() if v > 0)
        else:
            sev_str = ", ".join(f"{k}: {v}" for k, v in sev.items())
        lines.append(f"Distribusi severity/kategori: {sev_str}")

    source_cols = stats.get("_source_columns") or {}
    for label, items in (stats.get("top_categories") or {}).items():
        if not items:
            continue
        label = _humanize_stats_label(label, source_cols)
        top_str = ", ".join(f"{it['value']} ({it['count']}x)" for it in items[:10])
        lines.append(f"Top nilai kolom '{label}': {top_str}")

    is_english = (language or "").strip().lower() == "english"
    tp = stats.get("time_pattern")
    if tp:
        if "peak_day_of_week" in tp:
            day_name = tp["peak_day_of_week"]
            if not is_english:
                day_name = _DAY_NAME_ID.get(day_name, day_name)
            lines.append(f"Hari dengan aktivitas terbanyak: {day_name}")
        if "peak_hour" in tp:
            lines.append(f"Jam dengan aktivitas terbanyak: {tp['peak_hour']}:00")
        if "trend" in tp:
            t = tp["trend"]
            arah = "naik" if t["pct_change"] > 0 else ("turun" if t["pct_change"] < 0 else "stabil")
            lines.append(
                f"Tren volume: paruh awal {t['first_half_count']} event, paruh akhir "
                f"{t['second_half_count']} event ({arah} {abs(t['pct_change'])}%)"
            )

    for col, s in (stats.get("numeric_summary") or {}).items():
        lines.append(f"Kolom '{col}': min {s['min']}, max {s['max']}, rata-rata {s['mean']}")

    return "\n".join(lines)


def compute_schema_summary(parsed_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Poin 2. Ringkasan SKEMA data (nama kolom + tipe + contoh nilai) — supaya model paham
    struktur file APAPUN jenisnya (bandwidth, firewall, VAPT, dst) tanpa hardcode per jenis
    data_type. Kolom kategorikal (kardinalitas rendah) menyertakan SEMUA nilai uniknya
    (dibatasi 20) supaya model tahu persis kosakata yang mungkin muncul; kolom teks bebas /
    numerik / tanggal cukup 3 contoh nilai.
    """
    if not parsed_data:
        return {"columns": []}
    df = pd.DataFrame(parsed_data)
    if df.empty:
        return {"columns": []}

    date_col, _ = find_date_column(parsed_data)

    columns = []
    for col in df.columns:
        series = df[col].dropna()
        if col == date_col:
            col_type = "datetime"
            samples = [str(v) for v in series.head(3).tolist()]
        elif pd.api.types.is_numeric_dtype(df[col]):
            col_type = "numeric"
            samples = [str(v) for v in series.head(3).tolist()]
        else:
            n_unique = series.nunique()
            if len(series) > 0 and n_unique <= 20:
                col_type = "categorical"
                samples = [str(v) for v in series.unique().tolist()]
            else:
                col_type = "text"
                samples = [str(v) for v in series.head(3).tolist()]
        columns.append({"name": col, "type": col_type, "sample_values": samples})

    return {"columns": columns}


def format_schema_as_text(schema: Dict[str, Any]) -> str:
    """Ubah schema summary jadi teks ringkas siap tempel ke prompt."""
    columns = schema.get("columns") or []
    if not columns:
        return "Tidak ada kolom terdeteksi."

    lines = []
    for col in columns:
        samples_str = ", ".join(col["sample_values"][:20])
        lines.append(f"- {col['name']} ({col['type']}): {samples_str}")
    return "\n".join(lines)


