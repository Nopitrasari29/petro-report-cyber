"""Nama berkas unduhan DIBANGUN DARI ISI laporan - deterministik, tanpa panggilan AI.

Sebelumnya nama berkas cuma judul laporan yang dirapikan, jadi setiap laporan SOC keluar
sebagai "SOC_Executive_Summary_Jan-Feb2026.pdf" - tiga laporan berbeda dengan isi berbeda
punya nama yang sama persis, dan namanya tidak memberi tahu apa pun tentang isinya.

Yang dipakai di sini: topik dominan dari section yang BENAR-BENAR aktif (included_sections
yang dicentang), plus periode yang terdeteksi. Semuanya sudah ada di objek laporan - tidak
ada panggilan model, tidak ada tebakan, dan dua kali panggil untuk laporan yang sama selalu
menghasilkan nama yang sama.
"""
import re
import unicodedata

# Kata yang muncul di HAMPIR SETIAP judul section, jadi tidak membedakan laporan satu dengan
# lainnya - justru itu yang membuat nama berkas lama seragam. Dibuang sebelum topik dipilih.
# Dua bahasa sekaligus krn judul section mengikuti bahasa laporan.
_KATA_UMUM = {
    # perancah judul
    "of", "by", "the", "and", "for", "in", "on", "to", "a", "an", "vs",
    "dan", "di", "per", "pada", "untuk", "dari", "ke", "yang",
    # jenis analisis - ada di semua laporan
    "analysis", "analisis", "summary", "ringkasan", "overview", "ikhtisar",
    "trend", "trends", "tren", "comparison", "perbandingan", "distribution",
    "distribusi", "breakdown", "insight", "insights", "wawasan", "review",
    "evaluation", "evaluasi", "assessment", "penilaian", "pattern", "patterns",
    "pola", "performance", "kinerja", "statistics", "statistik",
    # perancah laporan
    "report", "laporan", "executive", "eksekutif", "dashboard", "section",
    "sections", "bagian", "data", "detail", "details", "rincian",
    # seksi penutup - bukan topik
    "conclusion", "kesimpulan", "recommendation", "recommendations", "rekomendasi",
    "saran", "penutup", "finding", "findings", "temuan", "key", "utama", "action",
    "items", "tindak", "lanjut",
    # granularitas waktu - periode sudah punya tempatnya sendiri di nama berkas
    "hour", "hourly", "jam", "daily", "harian", "day", "hari", "weekly", "mingguan",
    "monthly", "bulanan", "month", "bulan", "year", "tahun", "time", "waktu",
    "period", "periode", "date", "tanggal",
    # kuantitas umum
    "total", "count", "jumlah", "number", "angka", "rate", "score", "skor",
    "value", "nilai", "average", "rata", "all", "semua", "seluruh", "other", "lain",
}

_BULAN_ID = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
             "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
_BULAN_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

_MAKS_TOPIK = 3
_MAKS_PANJANG = 80


def _tanpa_aksen(teks: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", teks)
                   if not unicodedata.combining(c))


def _kata_bermakna(judul: str) -> list:
    """Kata pembeda dari satu judul section, urutan aslinya dipertahankan."""
    bersih = _tanpa_aksen(str(judul or ""))
    hasil = []
    for k in re.findall(r"[A-Za-z0-9]+", bersih):
        if k.lower() in _KATA_UMUM or len(k) < 3 or k.isdigit():
            continue
        hasil.append(k)
    return hasil


def topik_dominan(report, maks: int = _MAKS_TOPIK) -> list:
    """Topik yang paling sering disebut judul-judul section AKTIF.

    Yang dihitung SERINGNYA sebuah kata muncul lintas judul, bukan urutan section -
    kata yang berulang di banyak section itulah yang benar-benar jadi tema laporan.
    Seri diputus oleh urutan kemunculan pertama, supaya hasilnya stabil (tidak
    bergantung urutan iterasi dict) dan mengikuti urutan `order` yang dipilih user."""
    inc = getattr(report, "included_sections", None)
    judul_aktif = []
    if isinstance(inc, list):
        aktif = [s for s in inc
                 if isinstance(s, dict) and s.get("enabled", True) and s.get("title")]
        aktif.sort(key=lambda s: s.get("order", 0))
        judul_aktif = [s["title"] for s in aktif]
    if not judul_aktif:
        ai = getattr(report, "ai_summary", None) or {}
        judul_aktif = [s.get("title") for s in (ai.get("sections") or [])
                       if isinstance(s, dict) and s.get("title")]

    freq, urutan, bentuk = {}, {}, {}
    for pos, judul in enumerate(judul_aktif):
        for kata in _kata_bermakna(judul):
            k = kata.lower()
            freq[k] = freq.get(k, 0) + 1
            if k not in urutan:
                urutan[k] = (pos, len(urutan))
                bentuk[k] = kata[:1].upper() + kata[1:]
    terurut = sorted(freq, key=lambda k: (-freq[k], urutan[k]))
    return [bentuk[k] for k in terurut[:maks]]


def label_periode(report) -> str:
    """"Sep2026" / "Jan-Feb2026" / "Des2025-Jan2026" - kosong kalau periode tak diketahui."""
    a = getattr(report, "period_start", None)
    b = getattr(report, "period_end", None)
    if not a and not b:
        return ""
    a, b = a or b, b or a
    bulan = _BULAN_EN if _bahasa_inggris(report) else _BULAN_ID
    ba, bb = bulan[a.month - 1], bulan[b.month - 1]
    if a.year != b.year:
        return "%s%d-%s%d" % (ba, a.year, bb, b.year)
    if a.month != b.month:
        return "%s-%s%d" % (ba, bb, a.year)
    return "%s%d" % (ba, a.year)


def _bahasa_inggris(report) -> bool:
    return str(getattr(report, "language", "") or "").strip().lower().startswith("en")


def _rapikan(nama: str) -> str:
    nama = re.sub(r"[^A-Za-z0-9\-_]+", "-", _tanpa_aksen(nama))
    nama = re.sub(r"-{2,}", "-", nama).strip("-_")
    return nama


def nama_berkas_laporan(report, fallback: str = "laporan") -> str:
    """Nama berkas (tanpa ekstensi) dari isi laporan. Selalu deterministik.

    Bentuknya `Topik1-Topik2-Topik3_Periode`, mis. "Jaringan-Insiden-Keamanan_Jan-Feb2026".
    Kalau tidak ada judul section yang bisa dipakai, jatuh ke `domain_type` + judul laporan -
    tetap tanpa AI."""
    topik = topik_dominan(report)
    if topik:
        inti = "-".join(topik)
    else:
        domain = _rapikan(str(getattr(report, "domain_type", "") or ""))
        judul = _rapikan(str(getattr(report, "title", "") or ""))
        inti = "-".join(x for x in (domain, judul) if x) or fallback
    periode = label_periode(report)
    nama = _rapikan(inti) + ("_" + _rapikan(periode) if periode else "")
    if len(nama) > _MAKS_PANJANG:
        nama = nama[:_MAKS_PANJANG].rstrip("-_")
    return nama or fallback
