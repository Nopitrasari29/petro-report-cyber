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
import os
import re
import unicodedata
from typing import Any, Dict, List, Optional
import pandas as pd

from app.services.chart_generator import (
    _find_col, _find_numeric_cols, _rank_categorical_candidates,
    _classify_indo_numeric_column, _coerce_indo_numeric_series,
)
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


def _column_looks_like_severity(series: "pd.Series") -> bool:
    """Cek ISI (bukan cuma nama) - kolom genuinely severity keamanan HANYA kalau mayoritas
    (>=70%, SAMA persis dgn ambang _compute_severity_distribution) nilainya cocok kosakata
    keparahan baku (_classify_severity_value: critical/high/medium/low/informational & sinonim
    umumnya)."""
    values = series.dropna()
    if values.empty:
        return False
    classified = sum(1 for v in values if _classify_severity_value(str(v)))
    return classified >= 0.7 * len(values)


def _detect_severity_column(df: pd.DataFrame, exclude: List[str]) -> Optional[str]:
    """BUG NYATA DIPERBAIKI (dilaporkan user, dibuktikan langsung ke data - LEBIH SERIUS dari
    bug format angka Indonesia): SEBELUM INI kolom dipilih HANYA dari NAMANYA cocok kata kunci
    (_SEVERITY_KEYWORDS - termasuk "status", kata generik lintas domain, bukan eksklusif
    keamanan) TANPA PERNAH mengecek ISINYA genuinely kosakata keparahan. Kolom "Status"
    pengadaan berisi "Menunggu Persetujuan"/"Dalam Proses" (BUKAN severity keamanan sama
    sekali) tetap "terpilih" jadi sev_col cuma krn namanya cocok - lalu (lihat
    compute_statistics) DIKECUALIKAN dari deteksi kategori & nilai aslinya HILANG dari
    report_stats, DIGANTIKAN histogram keamanan generik yang semuanya nol. Ini BUKAN cuma
    "kolom tidak terbaca" (spt bug angka Indonesia, yang datanya sekadar hilang tanpa
    menggantikan apa pun) - ini MENGGANTI data asli dgn HASIL ANALISIS PALSU yang tampil
    seolah valid (severity_distribution kosong terlihat spt "genuinely tidak ada temuan",
    bukan "kolomnya salah baca").

    Sekarang kolom kandidat (baik dari nama YANG cocok maupun fallback berbasis isi) WAJIB
    JUGA lolos cek ISI (_column_looks_like_severity) sebelum dipakai - kalau tidak ada satu pun
    yang lolos, return None (BUKAN kolom severity sama sekali), bukan "dipakai tapi hasilnya
    kosong"."""
    col = _find_col(df, _SEVERITY_KEYWORDS)
    if col and _column_looks_like_severity(df[col]):
        return col
    candidates = _rank_categorical_candidates(df, exclude=exclude, max_unique=8)
    for cand in candidates:
        if _column_looks_like_severity(df[cand]):
            return cand
    return None


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


def _strip_decorative_symbols(text: str) -> str:
    return "".join(ch for ch in str(text) if unicodedata.category(ch) not in ("So", "Sk"))


def _normalize_category_key(value: str) -> str:
    """Kunci penggabungan untuk nilai kategori yang penulisannya mirip (mis. "Kantor Pusat
    (KAPUS)" dan "Kantor Pusat" seharusnya dihitung sebagai entitas yang sama, bukan 2
    kategori terpisah yang understate konsentrasi sebenarnya) — menghapus keterangan dalam
    kurung dan menyeragamkan spasi/huruf besar-kecil sebelum dibandingkan."""
    cleaned = _PAREN_RE.sub(" ", _strip_decorative_symbols(str(value)))
    return re.sub(r"\s+", " ", cleaned).strip().lower()


_PREFIX_BOUNDARY_CHARS = set("/\\.-_: ")


def _strip_shared_prefix(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Kalau SEMUA label kategori yang mau ditampilkan berbagi awalan sama persis (mis. path
    "/Common/" di depan tiap hostname F5/BIG-IP: "/Common/vs.pekapg...", "/Common/vs.abc..."),
    pangkas awalan itu dari SEMUA label sebelum dipakai sbg kategori chart/legend — utk
    path/hostname, bagian yang MEMBEDAKAN biasanya justru di belakang, jadi awalan seragam di
    depan cuma makan tempat (bikin label kepanjangan/terpotong di chart) tanpa nilai informasi
    tambahan (semua baris toh sama-sama "/Common/").

    Mundur ke batas pemisah TERAKHIR di dalam awalan yang ditemukan (bukan pangkas character-
    by-character mentah) supaya tidak motong di TENGAH token yang kebetulan sama beberapa huruf
    pertamanya (mis. "vs.pekapg" vs "vs.abc" -> awalan mentah cuma "vs." sampai huruf pembeda
    pertama, sudah pas berhenti di batas "."; tapi "server1" vs "server22" awalan mentah
    "server" tidak diakhiri pemisah -> dibatalkan, jangan sampai jadi "1"/"22" yang ambigu)."""
    if len(items) < 2:
        return items
    values = [str(it["value"]) for it in items]
    prefix = os.path.commonprefix(values)
    cut = max((i + 1 for i, ch in enumerate(prefix) if ch in _PREFIX_BOUNDARY_CHARS), default=0)
    prefix = prefix[:cut]
    if len(prefix) < 2:
        return items
    stripped = [v[len(prefix):] for v in values]
    if any(not s for s in stripped) or len(set(stripped)) != len(set(values)):
        # Awalan makan SELURUH salah satu label (jadi string kosong), atau ada 2 label beda
        # yang kebetulan jadi SAMA setelah dipangkas -> batalkan, pertahankan label asli utuh.
        return items
    for it, new_val in zip(items, stripped):
        it["value"] = new_val
    return items


def _top_values(df: pd.DataFrame, col: str, n: int = 10) -> List[Dict[str, Any]]:
    series = df[col].dropna()
    if pd.api.types.is_float_dtype(series) and not series.empty and (series % 1 == 0).all():
        # Kolom angka yang ada nilai kosongnya otomatis jadi float64 (NaN memaksa tipe
        # desimal) — kalau ternyata semua nilai terisinya bilangan bulat, bulatkan dulu
        # sebelum dijadikan label supaya tidak tampil "2.0"/"3.0" di laporan.
        series = series.astype("Int64")
    raw_counts = series.astype(str).map(_strip_decorative_symbols).value_counts()
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
    return _strip_shared_prefix(items)


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


_MONTH_ABBR_ID = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mei", 6: "Jun",
    7: "Jul", 8: "Agu", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Des",
}


def _compute_time_series(date_series: "pd.Series", max_buckets: int = 12) -> Dict[str, Any]:
    """Deret waktu asli per bucket (bulan/minggu/hari) — BEDA dari `trend` di
    _compute_time_pattern (cuma "naik/turun X%" dari 2 titik paruh awal vs akhir, tidak cukup
    utk digambar sbg chart tren sungguhan). Bucket dipilih otomatis dari rentang data (>=90
    hari -> bulanan, >=21 hari -> mingguan, sisanya harian) supaya chart tetap padat-informasi
    baik utk data 2 minggu maupun 1 tahun, dipotong ke `max_buckets` TERAKHIR kalau lebih
    panjang. Dipakai `report_render_logic.py` utk chart tren Analisis Tren (fallback ke
    `time_pattern.trend` yang sudah ada kalau ini kosong/rentang data terlalu pendek).

    Index `date_series` MASIH index baris DataFrame asli (bukan DatetimeIndex) — `.resample()`
    LANGSUNG di atasnya gagal (`TypeError: Only valid with DatetimeIndex`), jadi nilainya
    dibungkus ulang dulu lewat `pd.Series(1, index=pd.DatetimeIndex(...))` sebelum resample."""
    valid = date_series.dropna()
    if valid.empty:
        return {}
    span_days = (valid.max() - valid.min()).days
    if span_days >= 90:
        freq, unit = "MS", "month"
    elif span_days >= 21:
        freq, unit = "W-MON", "week"
    else:
        freq, unit = "D", "day"

    counts = pd.Series(1, index=pd.DatetimeIndex(valid.values)).resample(freq).sum().tail(max_buckets)
    if counts.empty:
        return {}

    if unit == "month":
        labels = [f"{_MONTH_ABBR_ID.get(ts.month, ts.strftime('%b'))} {ts.year}" for ts in counts.index]
    else:
        labels = [ts.strftime("%d/%m") for ts in counts.index]

    return {
        "unit": unit,
        "labels": labels,
        "counts": [int(v) for v in counts.tolist()],
        "cumulative": [int(v) for v in counts.cumsum().tolist()],
    }


def _compute_category_numeric_pairs(
    df: pd.DataFrame, category_cols: Dict[str, str], numeric_cols: List[str], top_n: int = 8,
) -> Optional[Dict[str, Any]]:
    """PERMINTAAN USER: tambah jenis visualisasi baru (scatter/bubble) — butuh 2 angka
    genuinely BERBEDA per entitas (mis. jumlah transaksi vendor VS rata-rata nilai
    kontraknya), bukan cuma 1 angka tunggal seperti chart yang sudah ada. `top_categories`/
    `numeric_summary` yang sudah ada TIDAK cukup sendirian (yang satu cuma hitungan
    kemunculan, yang satu cuma agregat SATU kolom independen dari kategori) — fungsi ini
    MENGELOMPOKKAN kolom numerik utama berdasarkan kolom kategori utama, supaya tiap entitas
    kategori (mis. tiap vendor) punya SEPASANG angka asli (jumlah kemunculan & rata-rata
    numerik) yang bisa diplot sbg satu titik scatter/bubble - TETAP angka asli dari data,
    bukan dikarang."""
    if not category_cols or not numeric_cols:
        return None

    def _looks_numeric_code(series: pd.Series) -> bool:
        """True kalau nilai kolom ini SEMUA kelihatan seperti angka/kode (mis. ID numerik),
        bukan label entitas sungguhan (mis. nama vendor) — BUG DIPERBAIKI (ditemukan lewat
        tes langsung): tanpa cek ini, kolom kategori PERTAMA yang kebetulan terdeteksi
        (urutan deteksi di _detect_main_category_columns, bukan berdasar makna) bisa berupa
        kode angka, hasilnya scatter/bubble menampilkan titik berlabel "2.0"/"1.2" yang sama
        sekali tidak bermakna sbg identitas entitas."""
        sample = series.dropna().astype(str).unique()[:5]
        if sample.size == 0:
            return False
        for v in sample:
            try:
                float(v)
            except (ValueError, TypeError):
                return False
        return True

    cat_label, cat_col = None, None
    for lbl, col in category_cols.items():
        if col not in df.columns:
            continue
        if _looks_numeric_code(df[col]):
            continue
        cat_label, cat_col = lbl, col
        break
    if not cat_col:
        return None
    num_col = numeric_cols[0]
    if num_col not in df.columns:
        return None
    grouped = df.groupby(cat_col)[num_col].agg(["count", "mean"]).reset_index()
    grouped = grouped.sort_values("count", ascending=False).head(top_n)
    if len(grouped) < 3:
        # Scatter/bubble butuh beberapa titik biar bermakna - kalau kategorinya cuma 1-2
        # nilai unik, chart lain (bar/donat) sudah lebih pas & lebih mudah dibaca.
        return None
    return {
        "category_label": cat_label,
        "category_col": cat_col,
        "numeric_label": num_col,
        "points": [
            {"label": str(row[cat_col]), "count": int(row["count"]), "avg": round(float(row["mean"]), 2)}
            for _, row in grouped.iterrows()
        ],
    }


_AGGREGATE_ROW_MARKERS = {
    "total", "grand total", "jumlah", "subtotal", "sub total", "all", "overall",
    "rata-rata", "rata rata", "average", "keseluruhan", "summary",
}


def _is_aggregate_row_marker(value) -> bool:
    return str(value).strip().lower() in _AGGREGATE_ROW_MARKERS


def _drop_aggregate_rows(df: pd.DataFrame, category_cols: Dict[str, str]) -> pd.DataFrame:
    """Buang baris yang nilainya di SALAH SATU kolom kategori cocok penanda ringkasan umum
    (mis. "Total") — baris semacam itu RINGKASAN bawaan tabel sumber (umum di PDF hasil
    ekstraksi, mis. baris "Total" di akhir tabel per-jam), bukan record data sungguhan.

    BUG NYATA DITEMUKAN (dibuktikan lewat generate ulang sungguhan): sebelum fungsi ini dipakai
    di _compute_numeric_summary/_compute_category_numeric_pairs, baris "Total" itu ikut
    dihitung sbg salah satu titik data numerik biasa - hasilnya "max"/"rata-rata" satu kolom
    (mis. "Authentication Failure") jadi angka TOTAL HARIAN (13111), BUKAN nilai per-jam
    tertinggi yang sebenarnya (671) - lalu angka salah itu genuinely (dan jujur, sesuai
    instruksi "jangan mengarang") dikutip AI di narasi ("Authentication Failure mencatat angka
    tertinggi 13111"), krn memang itu yang tertulis di STATISTIK TERHITUNG. AI-nya benar
    mengikuti instruksi - datanya sendiri yang perlu dibersihkan lebih dulu, bukan instruksinya
    yang ditambah lagi. _compute_category_numeric_breakdown SUDAH memfilter ini scr internal
    (per kolom kategori yang dipakainya) - fungsi ini menggeneralisasi filter yang sama ke
    fungsi lain yang JUGA melakukan groupby/agregasi per kolom kategori, supaya "Total" tidak
    bisa lolos lewat jalur numerik mana pun."""
    if df.empty or not category_cols:
        return df
    mask = pd.Series(False, index=df.index)
    for cat_col in category_cols.values():
        if cat_col not in df.columns:
            continue
        mask = mask | df[cat_col].astype(str).map(_is_aggregate_row_marker)
    return df[~mask] if mask.any() else df


def _compute_category_numeric_breakdown(
    df: pd.DataFrame, category_cols: Dict[str, str], numeric_cols: List[str],
    max_categories: int = _MAX_CATEGORY_COLUMNS, max_numeric_per_category: int = 20, max_buckets: int = 60,
    numeric_units: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Rincian ASLI nilai satu kolom numerik PER NILAI KATEGORI (mis. 'Authentication Failure'
    per 'Hour': 00:00->594, 01:00->577, dst) — BEDA dari _compute_category_numeric_pairs (itu
    (jumlah kemunculan, rata-rata) per ENTITAS, utk scatter/bubble); ini satu angka numerik ASLI
    per bucket, dibentuk supaya jadi SATU-SATUNYA sumber angka berlabel-lengkap yang valid utk
    field "chart" section custom AI (lihat SECTIONS_BATCH_SYSTEM_PROMPT/get_sections_batch_prompt
    di prompts.py — instruksinya sudah lama mewajibkan "labels"/"values" persis dari STATISTIK
    TERHITUNG, tapi SEBELUM breakdown ini ada, TIDAK ADA baris STATISTIK TERHITUNG yang benar2
    memberi pasangan label->nilai per bucket — model cuma diberi agregat min/max/rata2 SATU
    kolom + beberapa contoh nilai TANPA label. BUG NYATA DIBUKTIKAN lewat data asli (laporan
    "Authentication Failure Trend"): tanpa ground truth ini, model menukar nilai MAX/Total
    harian (13111) ke slot jam 00:00 yang seharusnya 594, sementara 2 slot lain kebetulan masih
    benar (577/596) — angkanya asli, cuma tertukar slot, krn model tidak pernah diberi tabel
    jam->nilai yang valid utk disalin.

    Baris yang nilai kategorinya cocok penanda agregat umum (mis. "Total") DIBUANG SEBELUM
    groupby — baris semacam itu RINGKASAN bawaan tabel sumber (umum di PDF hasil ekstraksi,
    mis. baris "Total" di akhir tabel per-jam), bukan bucket data sungguhan, dan justru itulah
    SUMBER tertukarnya nilai di atas kalau ikut disertakan.

    Dibatasi `max_categories`/`max_numeric_per_category`/`max_buckets` — kategori dgn nilai
    unik >max_buckets (mis. ratusan alamat IP) dilewati sepenuhnya, sudah lebih cocok diwakili
    top_categories (top-10 by count), bukan breakdown lengkap per bucket.

    BUG NYATA DIPERBAIKI (ditemukan lewat pengukuran 30 laporan): `max_categories` DULU default
    3, padahal `_detect_main_category_columns` (data_profiler.py) & allowlist eksplisit
    "Kolom KATEGORI yang BOLEH dipakai ..." (format_statistics_as_text) sama-sama memakai
    _MAX_CATEGORY_COLUMNS (5) - akibatnya kategori ke-4/ke-5 (mis. "Deskripsi_Barang_Jasa")
    DIIZINKAN dipilih AI di allowlist TAPI tidak pernah genuinely dapat baris "Rincian kolom ...
    per ..." (breakdown-nya berhenti di 3 kategori pertama) - trend_analysis yang menunjuk
    kategori ke-4/ke-5 SELALU dibuang walau AI sudah patuh persis pada allowlist yang diberikan.
    Disamakan ke _MAX_CATEGORY_COLUMNS supaya "kategori yang boleh dipakai" dan "kategori yang
    genuinely dihitung breakdown-nya" selalu SATU daftar yang sama, tidak ada lagi celah di
    antara keduanya.

    BUG NYATA DIPERBAIKI (ditemukan lewat generate ulang laporan management sungguhan — report
    dgn 33 aset unik): dulu `items` DIPOTONG di sini juga (`max_items_per_line`, dibuat awalnya
    cuma supaya baris teks "Rincian ..." ke prompt AI tetap ringkas) — akibatnya kartu bersarang
    di RENDER (_build_insight_page/_compute_multi_metric_items, TIDAK berhubungan dgn prompt AI
    sama sekali) cuma kebagian 12 entitas PERTAMA scr urutan kemunculan, bukan SEMUA 33 — kartu
    yg entitasnya "top-N by value" (bukan top-N by APPEARANCE ORDER) sering tidak ketemu di 12
    itu, sub-item-nya kosong padahal datanya genuinely ada. `items` SEKARANG disimpan LENGKAP di
    sini (dibatasi cuma oleh `max_buckets` scr KATEGORI, bukan lagi jumlah baris per kategori) —
    pemotongan "biar teks prompt AI ringkas" dipindah ke SATU tempat yang tepat memangkasnya:
    format_statistics_as_text (lapisan teks-ke-prompt), bukan di lapisan data yang dipakai ulang
    utk render juga."""
    if not category_cols or not numeric_cols:
        return []
    results: List[Dict[str, Any]] = []
    categories_used = 0
    for cat_label, cat_col in category_cols.items():
        if categories_used >= max_categories:
            break
        if cat_col not in df.columns:
            continue
        working = df[~df[cat_col].astype(str).map(_is_aggregate_row_marker)]
        n_unique = working[cat_col].dropna().nunique()
        if n_unique < 2 or n_unique > max_buckets:
            continue
        pairs_this_category = 0
        for num_col in numeric_cols:
            if pairs_this_category >= max_numeric_per_category:
                break
            if num_col not in working.columns:
                continue
            # PERMINTAAN USER: kolom persentase TIDAK BOLEH dijumlahkan spt nilai biasa
            # (jumlah beberapa persentase antar kategori tidak bermakna apa-apa) - rata-rata
            # per kategori yang genuinely mewakili "seberapa besar realisasi kategori ini".
            if (numeric_units or {}).get(num_col) == "percent":
                grouped = working.groupby(cat_col, sort=False)[num_col].mean().dropna()
            else:
                grouped = working.groupby(cat_col, sort=False)[num_col].sum(min_count=1).dropna()
            if len(grouped) < 2:
                continue
            items = [{"label": str(idx), "value": round(float(v), 2)} for idx, v in grouped.items()]
            results.append({
                "category_label": cat_label,
                "category_col": cat_col,
                "numeric_col": num_col,
                "items": items,
            })
            pairs_this_category += 1
        if pairs_this_category:
            categories_used += 1
    return results


def _compute_category_count_breakdown(
    df: pd.DataFrame, category_cols: Dict[str, str], max_categories: int = 5, max_buckets: int = 60,
) -> List[Dict[str, Any]]:
    """Jumlah kemunculan (count) ASLI per nilai kategori — pasangan Grup A utk "metric":"count"
    (lihat report_render_logic.py::_resolve_templated_narrative), MELENGKAPI
    _compute_category_numeric_breakdown di atas (itu utk nilai SUATU KOLOM ANGKA per kategori;
    ini menjawab pertanyaan yang BEDA & SAMA SAHnya - "kategori mana paling sering muncul" -
    TIDAK butuh kolom angka sama sekali).

    BUG NYATA DIPERBAIKI (dilaporkan user, dgn koreksi tegas: ini BUKAN AI berhalusinasi):
    sebelum breakdown ini ada, AI yang genuinely ingin membahas frekuensi kemunculan per
    kategori terpaksa MENGARANG nama kolom angka palsu ("Total records") krn kontrak lama
    HANYA menyediakan jalan menunjuk kolom angka asli (numeric_col) - tidak ada cara sah utk
    bilang "hitung saja jumlah barisnya". Kontraknya yang belum lengkap, bukan modelnya yang
    menebak sembarangan.

    Beda dari stats["top_categories"] (dipotong ke 10 tertinggi per kolom, dibuat utk ringkasan
    umum di prompt) - SEMUA nilai unik disimpan di sini (dibatasi cuma oleh max_buckets), supaya
    "kategori PALING JARANG muncul" tetap genuinely akurat kalau AI membahasnya, bukan cuma
    "ke-10 tersering dari yang kebetulan ditampilkan"."""
    if not category_cols:
        return []
    results: List[Dict[str, Any]] = []
    categories_used = 0
    for cat_label, cat_col in category_cols.items():
        if categories_used >= max_categories:
            break
        if cat_col not in df.columns:
            continue
        working = df[~df[cat_col].astype(str).map(_is_aggregate_row_marker)]
        counts = working[cat_col].dropna().astype(str).value_counts()
        if len(counts) < 2 or len(counts) > max_buckets:
            continue
        items = [{"label": str(idx), "value": int(v)} for idx, v in counts.items()]
        results.append({"category_label": cat_label, "category_col": cat_col, "items": items})
        categories_used += 1
    return results


def _coerce_indo_numeric_columns(df: pd.DataFrame) -> "tuple[pd.DataFrame, Dict[str, str]]":
    """Jalan SEKALI di awal compute_statistics(), SEBELUM deteksi kolom kategori/numerik apa
    pun — ubah kolom angka-tersimpan-sbg-teks (Rupiah "40.000.000", persentase "65%") jadi
    float ASLI di DataFrame-nya sendiri (bukan cuma "ditandai numerik" sementara nilainya tetap
    teks — .sum()/.mean() pandas di kolom teks akan gabung string atau error, bukan menghitung).

    Sesudah ini, `pd.api.types.is_numeric_dtype` utk kolom yang berhasil dikonversi otomatis
    True - _find_numeric_cols/_detect_main_category_columns/dst TIDAK PERLU diubah sama sekali,
    keduanya sudah benar begitu dikasih DataFrame yang sudah genuinely numerik.

    Return DataFrame baru (df asli tidak diubah) + dict {nama_kolom: "percent"|"currency"} utk
    kolom yang unit-nya berhasil dikenali - dipakai lapisan teks/narasi (format_statistics_as_text)
    & agregasi (_compute_category_numeric_breakdown, persentase pakai mean bukan sum) di bawah,
    SUPAYA SATUANNYA TIDAK HILANG bukan cuma angkanya yang keselamatan."""
    df = df.copy()
    units: Dict[str, str] = {}
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            continue
        if not (pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col])):
            continue
        info = _classify_indo_numeric_column(df[col].dropna(), col_name=col)
        if not info:
            continue
        df[col] = _coerce_indo_numeric_series(df[col], info)
        if info["unit"]:
            units[col] = info["unit"]
    return df, units


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

    df, numeric_units = _coerce_indo_numeric_columns(df)

    stats: Dict[str, Any] = {"total_records": len(df)}
    if numeric_units:
        # Prefix underscore = bukan bagian narasi AI (sama konvensinya dgn _source_columns) -
        # dipakai lapisan teks/render utk tahu kolom mana yang butuh sufiks "%"/"Rp".
        stats["_numeric_units"] = numeric_units

    date_col, date_series = find_date_column(parsed_data)
    exclude_for_categorical = [date_col] if date_col else []

    sev_col = _detect_severity_column(df, exclude=exclude_for_categorical)
    stats["severity_distribution"] = _compute_severity_distribution(df, sev_col)

    # PERMINTAAN USER (poin 2, perbaikan bug severity "Status" pengadaan): kolom severity yang
    # genuinely valid TIDAK LAGI otomatis dikecualikan dari deteksi kategori utama - nilai
    # mentahnya (dipakai top_categories/chart_source/category_numeric_breakdown/dst) HARUS
    # TETAP tersedia utk agregasi & narasi, bukan CUMA dikonsumsi severity_distribution lalu
    # hilang dari semua tempat lain ("simpan sbg kolom tambahan, jangan menimpa yang asli" -
    # severity & kategori sekarang BOLEH dual-purpose memakai kolom sumber yang sama). Kolom
    # tanggal TETAP dikecualikan (genuinely jalur analisis lain, lihat time_series/time_pattern).
    category_cols = _detect_main_category_columns(df, exclude=exclude_for_categorical)
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
        time_series = _compute_time_series(date_series)
        if time_series:
            stats["time_series"] = time_series

    # BUG NYATA DIPERBAIKI (dibuktikan lewat generate ulang sungguhan - lihat docstring
    # _drop_aggregate_rows): baris ringkasan bawaan tabel sumber (mis. "Total" di akhir tabel
    # per-jam) HARUS dibuang SEBELUM dihitung min/max/rata-rata/dst, supaya angka-angka itu
    # genuinely mewakili record data sungguhan - bukan lagi tercampur baris ringkasan.
    df_no_agg = _drop_aggregate_rows(df, category_cols)

    exclude_for_numeric = exclude_for_categorical + ([sev_col] if sev_col else []) + list(category_cols.values())
    numeric_summary = _compute_numeric_summary(df_no_agg, exclude=exclude_for_numeric)
    if numeric_summary:
        stats["numeric_summary"] = numeric_summary

    if category_cols and numeric_summary:
        pairs = _compute_category_numeric_pairs(df_no_agg, category_cols, list(numeric_summary.keys()))
        if pairs:
            stats["category_numeric_pairs"] = pairs

        breakdown = _compute_category_numeric_breakdown(
            df_no_agg, category_cols, list(numeric_summary.keys()), numeric_units=numeric_units,
        )
        if breakdown:
            stats["category_numeric_breakdown"] = breakdown

    if category_cols:
        count_breakdown = _compute_category_count_breakdown(df_no_agg, category_cols)
        if count_breakdown:
            stats["category_count_breakdown"] = count_breakdown

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


def _fmt_unit_value(val: float, unit: Optional[str]) -> str:
    """Tempel satuan ke angka utk teks prompt AI - PERMINTAAN USER: satuan (persen/Rupiah)
    HARUS ikut tersimpan/tertampil, bukan cuma angka polosnya, supaya AI tidak menulis "65"
    padahal maksudnya "65%". Duplikat kecil gaya format Barat (koma pemisah ribuan) yang SAMA
    dgn _fmt_count di report_render_logic.py - tidak diimpor dari sana spy tidak circular-
    import (report_render_logic.py yang mengimpor DARI modul ini, lihat _humanize_stats_label)."""
    num_str = f"{int(val):,}" if float(val) == int(val) else f"{val:,.2f}"
    if unit == "percent":
        return f"{num_str}%"
    if unit == "currency":
        return f"Rp {num_str}"
    return num_str


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

    # PERMINTAAN USER (perbaikan Grup A poin 2): sebelum baris ini ada, satu-satunya cara AI
    # "tahu" kolom kategori/angka mana yang valid adalah MENYIMPULKAN SENDIRI dari baris
    # "Rincian kolom ..."/schema_text di bawah — BUG NYATA DIBUKTIKAN: AI kadang tetap
    # menunjuk kolom TANGGAL (mis. "Tanggal_PO") sbg category_col krn kolom itu memang ADA di
    # schema_text, padahal SENGAJA dikecualikan dari deteksi kategori (tanggal punya analisis
    # tren waktu sendiri) — bukan AI menebak sembarangan, instruksinya yang tidak eksplisit.
    # Sekarang daftar yang BOLEH dipakai dinyatakan LANGSUNG (bukan lagi disimpulkan) - PERSIS
    # kolom yang sama yang dipakai membangun "Rincian kolom ..."/"Rincian jumlah kemunculan"
    # di bawah, supaya tidak ada ruang menerka nama kolom lain di luar daftar ini.
    allowed_category_cols = [v for k, v in source_cols.items() if k not in ("date", "severity") and v]
    if allowed_category_cols:
        lines.append(
            "Kolom KATEGORI yang BOLEH dipakai sbg 'category_col' (trend_analysis/chart_source): "
            + ", ".join(dict.fromkeys(allowed_category_cols))
        )
    allowed_numeric_cols = list((stats.get("numeric_summary") or {}).keys())
    if allowed_numeric_cols:
        lines.append(
            "Kolom ANGKA yang BOLEH dipakai sbg 'numeric_col' (trend_analysis/chart_source): "
            + ", ".join(allowed_numeric_cols)
        )
    # PERMINTAAN USER (perbaikan Grup A poin, susulan): kolom tanggal SENGAJA tidak masuk
    # daftar "Kolom KATEGORI ..." di atas (analisis tren waktu jalurnya sendiri, lihat
    # "Rincian jumlah data per waktu" di bawah) - tapi kalau tidak dinyatakan di sini AI tidak
    # tahu ke NAMA APA kolom tanggal itu harus dirujuk kalau genuinely ingin membahas pola
    # waktu (bentuk kontrak "date_col") - dinyatakan eksplisit spy tidak perlu menerka dari
    # schema_text lagi.
    allowed_date_col = (stats.get("_source_columns") or {}).get("date")
    if allowed_date_col:
        lines.append(
            "Kolom TANGGAL yang BOLEH dipakai sbg 'date_col' (trend_analysis, bentuk pola waktu): "
            + allowed_date_col
        )

    numeric_units = stats.get("_numeric_units") or {}
    for col, s in (stats.get("numeric_summary") or {}).items():
        unit = numeric_units.get(col)
        lines.append(
            f"Kolom '{col}': min {_fmt_unit_value(s['min'], unit)}, max {_fmt_unit_value(s['max'], unit)}, "
            f"rata-rata {_fmt_unit_value(s['mean'], unit)}"
        )

    # BUG NYATA DIPERBAIKI (dilaporkan user, dibuktikan lewat data asli): sebelum baris ini
    # ada, model TIDAK PERNAH diberi tabel label->nilai berpasangan utk kolom numerik per
    # kategori/bucket (mis. per-jam) — cuma agregat min/max/rata2 di atas + contoh nilai lepas
    # tanpa label di schema_text. Akibatnya model kadang menukar nilai MAX/agregat ke slot
    # bucket pertama saat menulis field "chart" (mis. "Authentication Failure Trend" menampilkan
    # 13.111 - itu Total harian - di slot jam 00:00 yang seharusnya 594). Baris ini jadi SATU-
    # SATUNYA sumber angka berlabel-lengkap yang valid utk chart bertopik "per kategori/per
    # waktu" — instruksi WAJIB menyalin PERSIS dari sini ada di SECTIONS_BATCH_SYSTEM_PROMPT.
    # `item["items"]` di sini bisa panjang (SEMUA nilai unik kategori itu, lihat docstring
    # _compute_category_numeric_breakdown - sengaja TIDAK dipotong di sana lagi supaya lapisan
    # render juga kebagian data lengkap). Dipotong ke 12 baris pertama KHUSUS utk teks prompt
    # AI di sini saja (model kecil makin buruk kalau kontexnya kepanjangan) - potongan ini
    # TIDAK memengaruhi apa yang dipakai render (report_render_logic.py membaca stats dict-nya
    # langsung, bukan teks hasil fungsi ini).
    _STATS_TEXT_MAX_ITEMS_PER_LINE = 12
    for item in (stats.get("category_numeric_breakdown") or []):
        cat_name = _humanize_stats_label(item["category_label"], source_cols)
        item_unit = numeric_units.get(item["numeric_col"])
        pairs_str = ", ".join(
            f"{p['label']}: {_fmt_unit_value(p['value'], item_unit)}"
            for p in item["items"][:_STATS_TEXT_MAX_ITEMS_PER_LINE]
        )
        lines.append(f"Rincian kolom '{item['numeric_col']}' per '{cat_name}': {pairs_str}")

    # PERMINTAAN USER (perbaikan Grup A poin 1): pasangan "Rincian jumlah kemunculan" utk
    # metrik "count" - ground truth JUMLAH BARIS per kategori (bukan nilai kolom angka apa
    # pun), supaya AI yang genuinely ingin membahas frekuensi kemunculan (mis. "vendor mana
    # paling sering dipakai") punya jalan sah menunjuk category_col + "metric":"count" di
    # trend_analysis, bukan terpaksa mengarang nama kolom angka palsu.
    for item in (stats.get("category_count_breakdown") or []):
        cat_name = _humanize_stats_label(item["category_label"], source_cols)
        pairs_str = ", ".join(
            f"{p['label']}: {p['value']}" for p in item["items"][:_STATS_TEXT_MAX_ITEMS_PER_LINE]
        )
        lines.append(f"Rincian jumlah kemunculan per '{cat_name}': {pairs_str}")

    # PERMINTAAN USER (perbaikan Grup A poin 2, residu kolom tanggal): ground truth utk bentuk
    # kontrak "date_col" - jumlah data per bucket WAKTU (harian/mingguan/bulanan, granularitas
    # SUDAH otomatis dipilih _compute_time_series dari rentang data, bukan pilihan AI). Sebelum
    # baris ini ada, AI yang genuinely ingin membahas pola waktu ("tanggal mana paling sibuk")
    # tidak pernah diberi tabel bucket->jumlah yang valid utk dikutip - PERSIS gap yang sama
    # dgn sebelum "Rincian jumlah kemunculan" ada utk metrik count.
    ts = stats.get("time_series") or {}
    if ts.get("labels"):
        _unit_label = {"day": "harian", "week": "mingguan", "month": "bulanan"}.get(ts.get("unit"), ts.get("unit"))
        pairs_str = ", ".join(f"{lbl}: {c}" for lbl, c in zip(ts["labels"], ts["counts"]))
        lines.append(f"Rincian jumlah data per waktu (bucket {_unit_label}): {pairs_str}")

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


