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
    counters = {"critical": 0, "high": 0, "medium": 0, "low": 0, "informational": 0}
    if not sev_col or sev_col not in df.columns:
        return counters
    for raw_val in df[sev_col].dropna():
        bucket = _classify_severity_value(str(raw_val))
        if bucket:
            counters[bucket] += 1
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


def _top_values(df: pd.DataFrame, col: str, n: int = 10) -> List[Dict[str, Any]]:
    counts = df[col].dropna().astype(str).value_counts().head(n)
    return [{"value": val, "count": int(cnt)} for val, cnt in counts.items()]


def _compute_numeric_summary(df: pd.DataFrame, exclude: List[str]) -> Dict[str, Dict[str, float]]:
    result = {}
    for col in _find_numeric_cols(df, exclude=exclude):
        series = df[col].dropna()
        if series.empty:
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

    if date_col and date_series is not None:
        stats["time_pattern"] = _compute_time_pattern(date_series)

    exclude_for_numeric = exclude_for_top + list(category_cols.values())
    numeric_summary = _compute_numeric_summary(df, exclude=exclude_for_numeric)
    if numeric_summary:
        stats["numeric_summary"] = numeric_summary

    return stats


def format_statistics_as_text(stats: Dict[str, Any]) -> str:
    """Ubah dict statistik jadi teks ringkas siap tempel ke prompt (mudah dibaca model)."""
    if stats.get("total_records", 0) == 0:
        return "Tidak ada data untuk dianalisis."

    lines = [f"Total records: {stats['total_records']}"]

    sev = stats.get("severity_distribution")
    if sev:
        sev_str = ", ".join(f"{k}: {v}" for k, v in sev.items())
        lines.append(f"Distribusi severity: {sev_str}")

    for label, items in (stats.get("top_categories") or {}).items():
        if not items:
            continue
        top_str = ", ".join(f"{it['value']} ({it['count']}x)" for it in items[:10])
        lines.append(f"Top nilai kolom '{label}': {top_str}")

    tp = stats.get("time_pattern")
    if tp:
        if "peak_day_of_week" in tp:
            lines.append(f"Hari dengan aktivitas terbanyak: {tp['peak_day_of_week']}")
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
