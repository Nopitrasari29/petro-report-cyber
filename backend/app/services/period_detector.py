from typing import Any, Dict, List, Optional, Tuple
import warnings
import pandas as pd

# Nama kolom yang dianggap kandidat "tanggal" pada data log security (case-insensitive).
# Dicoba lebih dulu karena cepat & akurat kalau namanya cocok.
DATE_COLUMN_CANDIDATES = [
    "tanggal", "date", "datetime", "timestamp", "time", "day",
    "log_date", "event_date", "waktu",
]

# Minimal proporsi nilai dalam satu kolom yang harus berhasil diparse sebagai tanggal
# supaya kolom itu dianggap valid sebagai kolom periode (mencegah false-positive di
# kolom fallback yang kebetulan sebagian isinya bisa "dipaksa" jadi tanggal).
MIN_VALID_RATIO = 0.7


def _parse_dates(values: List[Any]) -> "pd.Series":
    """
    Parse list nilai jadi Timestamp memakai pandas (bukan daftar format manual),
    supaya otomatis menangani variasi format nyata di lapangan: dengan/tanpa detik,
    jam tanpa leading zero ("8:15" bukan cuma "08:15:00"), separator '/', '-', '.',
    nama bulan, offset timezone/'Z', dst. Nilai yang gagal diparse jadi NaT (errors="coerce"),
    bukan melempar exception.
    """
    with warnings.catch_warnings():
        # Ini cuma dipakai untuk deteksi otomatis berbasis heuristik (bukan sumber kebenaran
        # kritis), jadi warning pandas soal format ambigu/tidak seragam sengaja diredam supaya
        # tidak membanjiri log tiap kali ada file diupload.
        warnings.simplefilter("ignore")
        return pd.to_datetime(pd.Series(values), errors="coerce")


def detect_period(parsed_data: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
    """
    Mencoba mendeteksi rentang tanggal (period_start, period_end) secara otomatis dari data
    yang sudah di-parse.

    Strategi 2 tahap:
    1. Cari kolom yang namanya cocok/mirip kandidat kolom tanggal (cepat, presisi tinggi
       kalau nama kolomnya lazim seperti "tanggal"/"timestamp"/"date").
    2. Kalau tidak ketemu lewat nama, ATAU kolom yang cocok namanya ternyata isinya
       mayoritas gagal diparse jadi tanggal (nama mirip tapi isinya bukan tanggal),
       fallback: coba parse tiap kolom teks satu per satu, pilih kolom dengan proporsi
       nilai valid tertinggi (di atas MIN_VALID_RATIO). Ini penting karena tiap sumber
       data/departemen bisa kasih nama kolom yang beda-beda ("Waktu Kejadian", "Occurred At",
       dll) — jadi tidak bisa cuma mengandalkan daftar nama yang di-hardcode.

    Kolom numerik murni (int/float, misal kolom hitungan seperti "jumlah_temuan") sengaja
    dilewati di tahap fallback, supaya tidak salah dikira epoch timestamp oleh pandas.

    Mengembalikan (None, None) kalau tidak ada kolom tanggal yang bisa dideteksi/diparse secara
    valid — di kondisi ini frontend harus minta user isi periode secara manual (contoh kasus:
    data yang cuma punya kolom "bulan": "Januari" tanpa tahun, seperti email_data.json).
    """
    if not parsed_data:
        return None, None

    sample_row = parsed_data[0]
    if not isinstance(sample_row, dict):
        return None, None

    row_keys_lower = {k.lower(): k for k in sample_row.keys()}

    # 1. Coba exact match dulu
    date_col = None
    for candidate in DATE_COLUMN_CANDIDATES:
        if candidate in row_keys_lower:
            date_col = row_keys_lower[candidate]
            break

    # 2. Kalau ga ketemu, coba partial match (misal kolom "log_timestamp")
    if not date_col:
        for key_lower, original_key in row_keys_lower.items():
            if any(candidate in key_lower for candidate in DATE_COLUMN_CANDIDATES):
                date_col = original_key
                break

    # 3. Kalau kolom hasil match nama ternyata isinya valid, langsung pakai itu.
    #    Kolom numerik murni sengaja tidak dipercaya di sini juga (walau namanya cocok),
    #    supaya field angka seperti "phishing_detected" tidak disalahartikan cuma karena
    #    kebetulan mengandung kata kandidat.
    date_col_sample_value = sample_row.get(date_col) if date_col else None
    date_col_is_numeric = isinstance(date_col_sample_value, bool) or isinstance(date_col_sample_value, (int, float))
    if date_col and not date_col_is_numeric:
        raw_values = [row.get(date_col) for row in parsed_data if isinstance(row, dict)]
        parsed = _parse_dates(raw_values)
        valid = parsed.dropna()
        if len(raw_values) > 0 and len(valid) / len(raw_values) >= MIN_VALID_RATIO:
            return valid.min().strftime("%Y-%m-%d"), valid.max().strftime("%Y-%m-%d")

    # 4. Fallback berbasis isi: coba tiap kolom bertipe teks/tanggal (bukan angka murni),
    #    ambil yang proporsi berhasil-parse-nya paling tinggi.
    best_col_valid: Optional["pd.Series"] = None
    for key in sample_row.keys():
        sample_value = sample_row.get(key)
        # Lewati kolom numerik murni supaya angka hitungan tidak disalahartikan jadi epoch time.
        if isinstance(sample_value, bool) or isinstance(sample_value, (int, float)):
            continue

        raw_values = [row.get(key) for row in parsed_data if isinstance(row, dict)]
        if not raw_values:
            continue

        parsed = _parse_dates(raw_values)
        valid = parsed.dropna()
        ratio = len(valid) / len(raw_values)
        if ratio >= MIN_VALID_RATIO and (best_col_valid is None or len(valid) > len(best_col_valid)):
            best_col_valid = valid

    if best_col_valid is None or best_col_valid.empty:
        return None, None

    return best_col_valid.min().strftime("%Y-%m-%d"), best_col_valid.max().strftime("%Y-%m-%d")
