# backend/app/services/report_render_logic.py
"""
Logika & data murni yang dipakai BERSAMA oleh export_ppt.py, export_pdf.py, dan (nanti)
endpoint preview — TIDAK ADA import pptx atau HTML di sini, supaya aman dipakai ketiganya.

Sebelumnya fungsi-fungsi ini didefinisikan ULANG identik (byte-per-byte) di export_ppt.py
DAN export_pdf.py secara terpisah. Disatukan di sini murni supaya tidak ada 2 salinan yang
bisa diam-diam jadi beda saat salah satu diedit tanpa mengedit yang lain.

Konstanta warna (RGBColor vs hex string) & semua helper visual (badge/panel/tabel/chart)
SENGAJA TIDAK dipindah ke sini — itu genuinely berbeda implementasi per medium (PPTX vs
HTML), bukan duplikasi yang bisa disatukan.

Label/judul/kicker TETAP (bukan pilihan sinonim acak — itu tetap urusan masing-masing
renderer, lihat docstring export_ppt.py) juga dihitung di sini lewat _L(), supaya
pengaturan report.language benar-benar berlaku ke SELURUH laporan — sebelumnya hanya
paragraf tulisan AI yang menghormati bahasa ini, sementara semua judul/label tetap selalu
Bahasa Indonesia apa pun pengaturannya.
"""
import datetime
import os
import random
import re

import pandas as pd

from app.crud.report import get_parsed_data
from app.services.ai_engine.data_profiler import compute_statistics, _classify_severity_value
from app.services.ai_engine.ollama_client import normalize_recommendations, sanitize_text, coerce_finding_text, coerce_narrative_text

SEVERITY_ORDER = ["critical", "high", "medium", "low", "informational"]
SEVERITY_LABEL = {
    "critical": "Critical", "high": "High", "medium": "Medium",
    "low": "Low", "informational": "Info",
}


def find_logo_path() -> str | None:
    """Cari file logo perusahaan di frontend/public — SEBELUMNYA disalin persis (path resolusi
    identik) di export_pdf.py (_resolve_logo_b64) & export_ppt.py (_resolve_logo_path), cuma
    beda di langkah TERAKHIR (PDF butuh base64 utk <img src="data:...">, PPT butuh path file
    apa adanya utk add_picture()) — bagian PENCARIAN path-nya sendiri disatukan di sini."""
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "public"))
    for name in ("LOGO_PETRO_DANANTARA.png", "LOGO_PETRO.png"):
        p = os.path.join(base, name)
        if os.path.exists(p):
            return p
    return None


def is_english(report) -> bool:
    return bool(getattr(report, "language", None)) and report.language.strip().lower() == "english"


def _L(report, id_text: str, en_text: str) -> str:
    """Pilih teks Indonesia atau Inggris sesuai report.language."""
    return en_text if is_english(report) else id_text


def _shorten_to_caption(text: str, max_sentences: int = 2) -> str:
    """Ambil N kalimat pertama dari paragraf AI, jadi caption singkat dipasangkan dgn chart
    kecil di build_report_blocks (lihat blok dynamic_section/key_findings) — dipanggil HANYA
    saat assign block["text"], TIDAK pernah mengubah ai_summary itu sendiri, supaya tab Edit
    Text (baca ai_summary langsung, bukan lewat sini) tetap menampilkan teks AI penuh apa
    adanya. Pakai regex batas kalimat (bukan idiom `.partition(". ")` yang dipakai di tempat
    lain file ini) karena sanitize_text() menyambung ulang kalimat dgn SATU SPASI terlepas
    kalimat itu diakhiri "."/"!"/"?" — `.partition(". ")` bisa diam-diam gagal memotong kalau
    kalimat pertama diakhiri "!" atau "?"."""
    if not text:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[:max_sentences]).strip()


def _stable_color_index(name: str, n: int = 5) -> int:
    """Indeks warna berdasarkan NAMA kategori (bukan posisi urutannya di list top-N) —
    BUG YANG DIPERBAIKI (dilaporkan user): dulu `color_index = i % n` murni dari urutan
    ranking chart itu sendiri, jadi kategori yang sama (mis. "Pabrik II B") bisa dapat
    warna berbeda di grafik lain kalau kebetulan urutan/top-N nya beda. Hash sederhana
    (bukan hash() bawaan Python — hash string di-randomize per proses) supaya 1 nama
    kategori SELALU jatuh ke indeks warna yang sama di seluruh laporan yang sama."""
    return sum(ord(c) for c in str(name)) % n


# Dipakai laporan LAMA (dibuat sebelum kolom report.visual_style ada, jadi NULL) — satu set
# tetap yang cocok dgn styling default sebelumnya (cover split, chart bar, kartu grid biasa),
# supaya laporan lama tidak pernah error/berubah tampilan sendiri gara-gara migrasi ini.
DEFAULT_VISUAL_STYLE = {
    # PERMINTAAN USER: cover 2-kolom warna-penuh + angka besar ("split") dihapus dari opsi
    # yang bisa dipilih — dianggap terlalu ramai/tidak umum utk cover laporan. "solid" (latar
    # gelap penuh + kicker/judul/periode, tanpa angka besar) jadi SATU-SATUNYA gaya cover
    # dipakai mulai sekarang. Kode _split_cover_td/_build_split_cover_slide/CoverSplit TETAP
    # ada (TIDAK dihapus) — laporan LAMA yang sudah terlanjur terkunci ke "split" di
    # report.visual_style tidak boleh berubah tampilan sendiri (lihat catatan panjang di
    # pick_visual_style soal laporan lama tidak pernah berubah bentuk sendiri).
    "cover_style": "solid",
    "category_style": "bar",
    "status_style": "bar",
    "asset_style": "cards",
    "recommendation_style": "cards",
    "panel_side": "right",
    "stat_cols": 3,
    "card_cols": 3,
    "accent_bar_color": "green",
    "flourish_corner": "bottom_right",
    "resolved_theme_color": "green",
}


# Preset gaya/layout bernama yang bisa dipilih user di Report Settings (Step 2 wizard,
# field `style_preset` pada Report) — kombinasi TETAP dari knob yang sama dipakai
# pick_visual_style() acak di bawah, supaya "Simple"/"Professional"/"Bold" punya arti visual
# yang konsisten & bisa diprediksi, bukan ikut diacak lagi. `accent_bar_color` tetap disimpan
# di tiap preset demi kompatibilitas bentuk data dengan DEFAULT_VISUAL_STYLE/laporan lama —
# TIDAK lagi dipakai untuk warna aksen (lihat resolve_theme_color(), warna sekarang murni dari
# report.theme_color, terpisah dari style_preset).
STYLE_PRESETS: dict[str, dict] = {
    "minimalist": {  # Simple/Minimalist — densitas visual rendah, cepat dipindai
        "cover_style": "solid",
        "category_style": "bar",
        "status_style": "bar",
        "asset_style": "cards",
        "recommendation_style": "cards",
        "panel_side": "right",
        "stat_cols": 2,
        "card_cols": 2,
        "accent_bar_color": "green",
        "flourish_corner": "bottom_right",
    },
    "corporate": {  # Professional/Corporate — seimbang, dekat dengan gaya umum sebelumnya
        "cover_style": "solid",
        "category_style": "donut",
        "status_style": "bar",
        "asset_style": "cards",
        "recommendation_style": "cards",
        "panel_side": "right",
        "stat_cols": 3,
        "card_cols": 3,
        "accent_bar_color": "green",
        "flourish_corner": "bottom_right",
    },
    "executive": {  # Bold/Executive — lebih padat & grafis, untuk pembaca eksekutif/dewan
        "cover_style": "solid",
        "category_style": "stacked",
        "status_style": "donut",
        "asset_style": "podium",
        "recommendation_style": "timeline",
        "panel_side": "left",
        "stat_cols": 3,
        "card_cols": 3,
        "accent_bar_color": "green",
        "flourish_corner": "top_right",
    },
}


def pick_visual_style(preset: str | None = None) -> dict:
    """Pilih SATU kombinasi varian tampilan (bentuk cover, gaya chart, gaya kartu, dst) —
    dipanggil SEKALI oleh analysis.py tepat saat analisis AI berhasil, hasilnya DISIMPAN ke
    report.visual_style (bukan di-random ulang tiap kali file diunduh seperti sebelumnya).
    BUG YANG DIPERBAIKI (dilaporkan user): dulu setiap generate_ppt_report/generate_pdf_report
    dipanggil, pilihan acak baru diambil lagi — preview web (yang selalu 1 tampilan tetap)
    jadi bisa terlihat SANGAT berbeda dari file yang benar-benar diunduh. Sekarang preview,
    PDF, dan PPTX bertiga membaca `report.visual_style` yang SAMA, jadi dijamin konsisten utk
    1 laporan yang sama — regenerate laporan (analisis AI baru) boleh dapat kombinasi lain,
    laporan yang sudah ada tidak pernah berubah bentuk sendiri kapan pun dilihat/diunduh.

    `preset`: nilai report.style_preset ("minimalist"/"corporate"/"executive") — kalau cocok
    salah satu STYLE_PRESETS, kembalikan kombinasi TETAP itu (deterministik, sesuai pilihan
    user). Kalau None/""/"auto"/nilai tak dikenal, PERSIS perilaku lama: pilih acak penuh —
    supaya laporan lama & laporan tanpa preset eksplisit tidak berubah sama sekali.

    `resolved_theme_color` SELALU diisi acak di sini (terlepas dari preset gaya) — dipakai
    HANYA kalau report.theme_color = "auto" (lihat resolve_theme_color()); kalau user pilih
    warna eksplisit, nilai ini dihitung tapi tidak pernah dibaca. Diacak & DIKUNCI di sini
    (bukan saat render) dengan alasan SAMA PERSIS seperti knob gaya lain di atas — supaya
    preview web & file PDF/PPTX yang diunduh SELALU menampilkan warna yang identik untuk 1
    laporan yang sama, bukan re-roll acak tiap kali dibuka/diunduh."""
    key = (preset or "").strip().lower()
    if key in STYLE_PRESETS:
        result = dict(STYLE_PRESETS[key])
    else:
        rnd = random.Random()
        result = {
            "cover_style": "solid",  # "split" dihapus dari opsi acak, lihat catatan di DEFAULT_VISUAL_STYLE
            "category_style": rnd.choice(["bar", "donut", "stacked"]),
            "status_style": rnd.choice(["bar", "donut", "stacked", "funnel"]),
            "asset_style": rnd.choice(["cards", "podium", "bars"]),
            "recommendation_style": rnd.choice(["cards", "timeline", "banners"]),
            "panel_side": rnd.choice(["left", "right"]),
            "stat_cols": rnd.choice([2, 3]),
            "card_cols": rnd.choice([2, 3]),
            "accent_bar_color": rnd.choice(["green", "gold"]),
            "flourish_corner": rnd.choice(["bottom_right", "top_right", "bottom_left"]),
        }
    result["resolved_theme_color"] = random.choice(VALID_THEME_COLORS)
    return result


VALID_THEME_COLORS = ("green", "navy", "dark", "gold")


def resolve_theme_color(report) -> str:
    """Validasi report.theme_color ke salah satu dari 4 kunci tema dikenal (green/navy/dark/
    gold). Nilai HEX (export_pdf.py) vs RGBColor (export_ppt.py) SENGAJA didefinisikan
    terpisah per file (medium-specific), konsisten dengan konvensi warna module ini yang
    tidak disatukan.

    report.theme_color = "auto" (pilihan user, ATAU default utk laporan yang belum pernah
    disentuh pickernya) berarti warna diacak & DIKUNCI sekali oleh pick_visual_style() tepat
    saat analisis berhasil (lihat resolved_theme_color di sana) — dibaca dari situ di sini,
    BUKAN diacak ulang tiap render, supaya preview & file yang diunduh selalu sewarna utk 1
    laporan yang sama. Laporan lama (theme_color NULL, dari sebelum "auto" ada) & laporan yang
    belum pernah dianalisis (visual_style masih NULL) fallback ke "green"."""
    key = str(getattr(report, "theme_color", None) or "auto").strip().lower()
    if key in VALID_THEME_COLORS:
        return key
    # Support custom hex color (#RRGGBB) dari color picker frontend
    if key.startswith("#") and len(key) in (4, 7):
        return key  # Dikembalikan apa adanya — export_pdf/ppt akan map ke warna terdekat jika perlu
    resolved = get_visual_style(report).get("resolved_theme_color")
    return resolved if resolved in VALID_THEME_COLORS else "green"


def get_visual_style(report) -> dict:
    """Baca report.visual_style, fallback ke DEFAULT_VISUAL_STYLE kalau NULL (laporan lama)
    ATAU kalau formatnya tidak lengkap (jaga-jaga field baru ditambah di masa depan)."""
    stored = getattr(report, "visual_style", None) or {}
    return {**DEFAULT_VISUAL_STYLE, **stored}


# Domain NON-keamanan yang punya nilai data_type tetap (lihat domainToDataType di
# generate/page.tsx & _DOMAIN_TITLE_LABELS di upload.py) — di luar ini (firewall,
# email_security, ids_ips, vapt, atau apapun yang tidak dikenal) DIANGGAP domain keamanan,
# mempertahankan SELURUH kosakata SOC/insiden yang sudah ada sebagai perilaku default/lama.
_NON_SECURITY_DATA_TYPES = {"keuangan", "financial", "kpi_hr", "operasional", "general", "procurement"}


# BUG YANG DIPERBAIKI (dilaporkan user): dulu label tunggal per key, dipakai apa adanya
# terlepas dari report.language — "procurement" misalnya SELALU tampil "Pengadaan Barang &
# Jasa" walau laporannya berbahasa Inggris. Sekarang tiap key punya varian (id, en).
_DATA_TYPE_DISPLAY_LABELS = {
    "keuangan": ("Keuangan", "Finance"),
    "financial": ("Keuangan", "Finance"),
    "kpi_hr": ("KPI & SDM", "KPI & HR"),
    "operasional": ("Operasional", "Operational"),
    "general": ("Umum", "General"),
    "procurement": ("Pengadaan Barang & Jasa", "Goods & Services Procurement"),
}


def is_security_domain(report) -> bool:
    """False untuk data non-keamanan (keuangan/KPI-HR/operasional/umum) — dipakai memilih
    kosakata laporan yang netral (bukan istilah insiden/serangan/mitigasi keamanan siber)
    untuk domain yang sama sekali bukan konteks keamanan. Data_type yang tidak dikenal
    TETAP dianggap domain keamanan (default lama, tidak mengubah laporan SOC yang sudah ada)."""
    dt = str(getattr(report, "data_type", "") or "").strip().lower()
    return dt not in _NON_SECURITY_DATA_TYPES


def humanize_data_type(report) -> str:
    dt = str(getattr(report, "data_type", "") or "").strip().lower()
    labels = _DATA_TYPE_DISPLAY_LABELS.get(dt)
    if labels:
        return labels[1] if is_english(report) else labels[0]
    return dt.replace("_", " ").title() or "-"


def format_report_date(dt: datetime.datetime, language: str | None) -> str:
    """Format tanggal secara dinamis berdasarkan preferensi bahasa laporan."""
    if not dt:
        return "-"
    if language and language.strip().lower() == "indonesian":
        months_id = {
            1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
            5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
            9: "September", 10: "Oktober", 11: "November", 12: "Desember"
        }
        return f"{dt.day} {months_id[dt.month]} {dt.year}"
    return dt.strftime('%d %B %Y')


def format_period(report) -> str:
    joiner = " to " if is_english(report) else " sampai "
    if report.period_start and report.period_end:
        if report.period_start == report.period_end:
            return format_report_date(report.period_end, report.language)
        return f"{format_report_date(report.period_start, report.language)}{joiner}{format_report_date(report.period_end, report.language)}"
    if report.period_end:
        return format_report_date(report.period_end, report.language)
    if report.period_start:
        return format_report_date(report.period_start, report.language)
    return format_report_date(report.created_at or datetime.datetime.now(), report.language)


def classify_open_status(value) -> bool | None:
    """True = masih terbuka/belum tuntas, False = sudah tuntas, None = tak bisa diklasifikasi.
    Kosakata status SOC umum (Blocked/Mitigated/Isolated/Resolved/Logged/Quarantined = tuntas;
    Investigating/Open/Pending = masih berjalan)."""
    v = str(value).strip().lower()
    open_kw = ["investigating", "open", "pending", "in progress", "in-progress", "unresolved",
               "belum selesai", "belum ditangani", "menunggu", "baru", "new"]
    closed_kw = ["blocked", "mitigated", "isolated", "resolved", "logged", "quarantined",
                 "closed", "selesai", "done", "complete", "completed", "ditutup", "tertangani"]
    if any(kw in v for kw in open_kw):
        return True
    if any(kw in v for kw in closed_kw):
        return False
    return None


def pick_category(top_categories: dict, preferred: list, used: set):
    """Coba tiap label di `preferred` urut, kembalikan (label, items) pertama yang ADA
    isinya & belum dipakai slide/halaman lain — else None (bagian terkait di-skip aman).

    BUG NYATA YANG DIPERBAIKI (data VAPT nyata): kolom yang cocok lewat NAMA (mis. "asset"/
    "host", lihat _CATEGORY_INTENTS di data_profiler.py) dipilih tanpa cek apakah isinya
    genuinely berulang — beda dengan jalur fallback berbasis-isi (_rank_categorical_candidates)
    yang sudah punya filter rasio-unik sendiri. Kolom nama aset yang hampir semua barisnya
    unik (mis. tiap baris nama beda) tetap dipaksa tampil sebagai "3 aset paling sering jadi
    sasaran" padahal count-nya cuma 1 tiap item — bukan pola nyata, cuma kebetulan urutan
    data. Kalau item TERATAS (paling sering muncul) count-nya cuma 1, berarti SEMUA nilai di
    kolom itu unik (1 = nilai minimum sekaligus maksimum) — lewati kandidat ini, coba label
    berikutnya di `preferred` daripada memaksakan tampilan yang menyesatkan."""
    for label in preferred:
        items = top_categories.get(label)
        if items and label not in used and items[0].get("count", 0) > 1:
            used.add(label)
            return label, items
    return None


def humanize_label(label: str, source_cols: dict | None = None) -> str:
    """Ubah label internal (nama niat seperti "location", atau label generik "category_2")
    jadi teks tampilan yang manusiawi. Untuk label generik "category_N", PRIORITASKAN nama
    kolom ASLI dari file yang diupload (mis. "Kategori", "Unit_Kerja") lewat `source_cols`
    (report_stats["_source_columns"]) — bukan lagi tampil sebagai "Kategori 2" yang tidak
    bermakna apa-apa (bug yang sebelumnya kejadian bahkan untuk kolom yang nama aslinya
    sendiri sudah "Kategori", cuma tidak cocok kata kunci niat manapun)."""
    if source_cols and label.startswith("category_"):
        real_name = source_cols.get(label)
        if real_name:
            return str(real_name).replace("_", " ").strip().title()
    return label.replace("_", " ").replace("category ", "Kategori ").strip().title()


def build_key_findings(ai_summary: dict, report_stats: dict, open_count: int, sanitize_func=None, report=None) -> list:
    """`sanitize_func` opsional — fallback ke `sanitize_text` yang sudah diimpor di modul ini
    kalau pemanggil tidak mengisinya (pemanggil lama yang masih passing positional tetap
    kompatibel apa adanya)."""
    clean_fn = sanitize_func or sanitize_text
    findings = [
        clean_fn(coerce_finding_text(f))
        for f in (ai_summary.get("key_findings") or [])
        if coerce_finding_text(f)
    ]
    if not findings:
        sev = report_stats.get("severity_distribution") or {}
        total_sev = sum(sev.values())
        if total_sev:
            top, count = max(sev.items(), key=lambda kv: kv[1])
            pct = round(count / total_sev * 100, 1)
            findings.append(_L(
                report,
                f"Proporsi {SEVERITY_LABEL.get(top, top.capitalize())} paling tinggi, {count} event ({pct}%)." if is_security_domain(report)
                else f"Proporsi {SEVERITY_LABEL.get(top, top.capitalize())} paling tinggi, {count} data ({pct}%).",
                f"{SEVERITY_LABEL.get(top, top.capitalize())} has the highest share, {count} events ({pct}%).",
            ))
        # Sebelumnya di-break setelah kategori PERTAMA — kalau AI tidak mengisi key_findings
        # sama sekali, hasilnya cuma 1 temuan generik walau data punya beberapa dimensi
        # kategori sekaligus (mis. Metode Pengadaan, Vendor, Status) yang masing-masing
        # sebenarnya punya temuan yang layak ditampilkan. Sekarang diambil dari SEMUA dimensi
        # kategori yang terdeteksi (dibatasi 3 supaya tidak membanjiri halaman), fallback yang
        # jauh lebih informatif daripada satu baris generik saat AI tidak menyediakan findings.
        tops = report_stats.get("top_categories") or {}
        source_cols_for_findings = report_stats.get("_source_columns") or {}
        for label, items in list(tops.items())[:3]:
            if items:
                label_text = humanize_label(label, source_cols_for_findings)
                findings.append(_L(
                    report,
                    f"Kategori teratas pada {label_text} adalah {items[0]['value']} dengan {items[0]['count']} kejadian." if is_security_domain(report)
                    else f"Kategori teratas pada {label_text} adalah {items[0]['value']} dengan {items[0]['count']} data.",
                    f"The top category in {label_text} is {items[0]['value']} with {items[0]['count']} occurrences.",
                ))
        if not findings:
            findings.append(_L(
                report,
                "Temuan utama belum dapat dirumuskan otomatis dari data ini.",
                "Key findings could not be automatically derived from this data.",
            ))
    if open_count > 0:
        findings.insert(0, _L(
            report,
            f"Terdapat {open_count} item berstatus terbuka/belum ditangani yang memerlukan tindak lanjut segera." if not is_security_domain(report)
            else f"Terdapat {open_count} insiden berstatus terbuka/belum ditangani yang memerlukan tindak lanjut segera.",
            f"There are {open_count} items still open/unresolved that require immediate follow-up.",
        ))
    return findings[:6]


def is_section_included(key: str, included_sections) -> bool:
    """`included_sections` = report.included_sections (dict preset lama ATAU list section
    dinamis PART A2) — default True kalau key tidak ditemukan (tampilkan, bukan sembunyikan)."""
    if isinstance(included_sections, dict):
        return included_sections.get(key, True)
    if isinstance(included_sections, list):
        for sec in included_sections:
            if isinstance(sec, dict) and (sec.get("key") == key or sec.get("id") == key):
                return sec.get("enabled", True)
    return True


# ============================================================================
# Perhitungan tambahan KHUSUS bentuk visual baru (radar/heatmap/perbandingan periode) —
# SEMUA membaca `parsed_data`/`report_stats` yang SUDAH dihasilkan compute_statistics(),
# TIDAK PERNAH mengubah/menambah isi compute_statistics() itu sendiri (data_profiler.py
# tetap apa adanya). Dipisah jadi fungsi kecil sendiri (bukan inline di build_report_blocks)
# supaya gampang dites & gampang dibaca alurnya.
# ============================================================================
def _compute_kpi_radar(numeric_summary: dict, source_cols: dict | None) -> dict | None:
    """Radar skor multi-indikator — dipakai HANYA kalau data punya >=3 kolom numerik (mis.
    beberapa skor KPI/nilai capaian sekaligus). Tiap sumbu dinormalisasi jadi "rata-rata
    sebagai % dari nilai maksimum kolom itu sendiri" — supaya kolom dengan skala beda-beda
    (mis. skor 0-5 vs nilai kontrak jutaan rupiah) tetap bisa dibandingkan di 1 radar yang
    sama tanpa perlu tahu skala aslinya masing-masing."""
    axes, values = [], []
    for col, nstats in list(numeric_summary.items())[:6]:
        mx = nstats.get("max")
        mean = nstats.get("mean")
        if not mx or mean is None:
            continue
        axes.append(humanize_label(col, source_cols))
        values.append(max(0.0, min(100.0, round(mean / mx * 100, 1))))
    return {"axes": axes, "values": values} if len(axes) >= 3 else None


def _compute_day_hour_pattern(parsed_data: list, date_col: str | None) -> dict | None:
    """Grid pola kejadian per hari-dalam-minggu x blok jam (6 blok @4 jam) — dipakai utk
    heatmap. Butuh kolom tanggal terdeteksi & minimal 20 baris bertanggal valid supaya
    polanya bermakna (bukan cuma 1-2 sel terisi di tengah grid kosong)."""
    if not date_col or not parsed_data:
        return None
    try:
        dates = pd.to_datetime(pd.Series([row.get(date_col) for row in parsed_data]), errors="coerce")
        dates = dates.dropna()
        if len(dates) < 20:
            return None
        day_labels = [
            ("Senin", "Mon"), ("Selasa", "Tue"), ("Rabu", "Wed"), ("Kamis", "Thu"),
            ("Jumat", "Fri"), ("Sabtu", "Sat"), ("Minggu", "Sun"),
        ]
        hour_labels = ["00-04", "04-08", "08-12", "12-16", "16-20", "20-24"]
        grid = [[0] * 6 for _ in range(7)]
        for ts in dates:
            grid[int(ts.dayofweek)][min(int(ts.hour) // 4, 5)] += 1
        if sum(sum(row) for row in grid) == 0:
            return None
        # Data sumber yang cuma punya TANGGAL tanpa jam (umum di laporan produksi harian)
        # selalu ter-parse jam=00:00 — semua baris numpuk di kolom "00-04", 5 kolom lain
        # kosong permanen. Tabel 6 kolom yang 5-nya kosong tidak informatif, jadi kalau
        # cuma 1 kolom jam yang benar-benar terisi, tampilkan total per-hari saja (1 kolom)
        # drpd grid bolong.
        active_hour_cols = sum(1 for c in range(6) if any(grid[r][c] for r in range(7)))
        if active_hour_cols <= 1:
            day_totals = [[sum(row)] for row in grid]
            return {"day_labels": day_labels, "hour_labels": ["Total"], "grid": day_totals, "total": int(len(dates))}
        return {"day_labels": day_labels, "hour_labels": hour_labels, "grid": grid, "total": int(len(dates))}
    except Exception:
        return None


def _compute_period_compare(parsed_data: list, date_col: str | None, cat_col: str | None, top_values: list) -> dict | None:
    """Bandingkan jumlah kejadian per kategori teratas antara paruh awal vs paruh akhir
    periode data (dibagi di median tanggal) — dipakai utk grouped bar. Butuh kolom tanggal +
    kolom kategori yang sama-sama terdeteksi & minimal 12 baris bertanggal valid."""
    if not date_col or not cat_col or not parsed_data or not top_values:
        return None
    try:
        dates = pd.to_datetime(pd.Series([row.get(date_col) for row in parsed_data]), errors="coerce")
        valid = dates.dropna()
        if len(valid) < 12:
            return None
        median = valid.median()
        first = {v: 0 for v in top_values}
        second = {v: 0 for v in top_values}
        for i in valid.index:
            val = str(parsed_data[i].get(cat_col, ""))
            if val not in first:
                continue
            (first if dates[i] <= median else second)[val] += 1
        series_a = [first[v] for v in top_values]
        series_b = [second[v] for v in top_values]
        if sum(series_a) + sum(series_b) == 0:
            return None
        return {"categories": top_values, "series_a": series_a, "series_b": series_b}
    except Exception:
        return None


_STOP_WORDS = {
    "yang", "dan", "atau", "dari", "pada", "untuk", "dengan", "adalah", "akan", "telah",
    "masih", "perlu", "dapat", "juga", "para", "tersebut", "menjadi", "secara", "dalam",
    "this", "that", "with", "from", "have", "been", "will", "should", "need", "most", "into",
    "over", "than", "such", "were", "there", "their", "about", "across",
}


def _text_tokens(text: str) -> set:
    return {w for w in re.findall(r"[a-zA-ZÀ-ɏ]{4,}", (text or "").lower()) if w not in _STOP_WORDS}


def _conclusion_adds_new_insight(conclusion_text: str, prior_texts: list) -> bool:
    """Kesimpulan bukan section wajib — cek dulu apakah isinya menambah insight baru di luar
    yang sudah tersampaikan di halaman lain, bukan cuma mengulang. Heuristik sederhana &
    deterministik (tanpa panggilan AI baru): bandingkan kata-kata bermakna (>=4 huruf, bukan
    kata umum) di teks kesimpulan dgn gabungan kata-kata di SEMUA teks/caption yang sudah
    tampil sebelumnya — kalau porsi kata BARU terlalu kecil, isinya dianggap pengulangan &
    di-skip. Teks pendek (<5 kata bermakna) selalu dianggap lolos (terlalu pendek utk dinilai
    andal, lebih aman ditampilkan daripada salah membuang kesimpulan yang genuinely singkat)."""
    concl_tokens = _text_tokens(conclusion_text)
    if len(concl_tokens) < 5:
        return True
    seen_tokens: set = set()
    for t in prior_texts:
        seen_tokens |= _text_tokens(t)
    new_tokens = concl_tokens - seen_tokens
    return (len(new_tokens) / len(concl_tokens)) >= 0.3


def _candidate(panel_kind: str, theme_tag: str, weight: float, dark: bool, kicker, title, **payload) -> dict:
    """Satu "kandidat" konten (tahap 1) — 1 topik apa adanya, LENGKAP dgn saran bentuk visual
    (field-field di `payload`, mis. "chart"/"categories"/"values"), sebelum diputuskan (tahap
    2, lihat _group_candidates_into_pages) bakal jadi halaman sendiri atau digabung dgn
    kandidat lain yang temanya nyambung. `weight` = perkiraan kasar seberapa "penuh" 1 halaman
    kalau kandidat ini sendirian (skala 0-1, 1.0 = sepadat halaman penuh) — dipakai murni utk
    keputusan penggabungan, BUKAN dipakai renderer."""
    return {
        "panel_kind": panel_kind, "theme_tag": theme_tag, "weight": weight, "dark": dark,
        "kicker": kicker, "title": title, **payload,
    }


_GROUP_HEADING = {
    "insight": (("ANALISIS", "ANALYSIS"), ("Ringkasan Analisis", "Analysis Summary")),
    "distribution": (("ANALISIS DATA", "DATA ANALYSIS"), ("Distribusi & Pola Data", "Data Distribution & Patterns")),
    "action": (("TINDAK LANJUT", "FOLLOW-UP"), ("Rekomendasi & Kesimpulan", "Recommendations & Conclusion")),
    "overview": (("RINGKASAN", "SUMMARY"), ("Ringkasan Eksekutif", "Executive Summary")),
}


def _page_from_panels(panels: list, report, sec_domain: bool) -> dict:
    """Bungkus 1+ panel (kandidat yang sudah diputuskan tahap 2) jadi 1 dict halaman. Kalau
    cuma 1 panel, judul/kicker halaman = judul/kicker panel itu sendiri apa adanya (perilaku
    identik dgn dulu tiap kind = 1 halaman). Kalau >1 panel digabung, judul/kicker halaman
    diambil dari tema gabungannya (lihat _GROUP_HEADING) supaya tetap punya 1 judul yang
    masuk akal utk seluruh halaman, bukan cuma judul panel pertama."""
    if len(panels) == 1:
        p = panels[0]
        return {"kind": "page", "dark": p["dark"], "kicker": p.get("kicker"), "title": p.get("title"), "panels": panels}
    theme = panels[0]["theme_tag"]
    dark = panels[0]["dark"]
    if theme == "highlight":
        kicker = (_L(report, "SOROTAN INSIDEN", "INCIDENT HIGHLIGHT") if sec_domain
                  else _L(report, "SOROTAN DATA", "DATA HIGHLIGHT"))
        title = _L(report, "Sorotan Utama", "Key Highlights")
    elif theme in _GROUP_HEADING:
        (kicker_id, kicker_en), (title_id, title_en) = _GROUP_HEADING[theme]
        kicker = _L(report, kicker_id, kicker_en)
        title = _L(report, title_id, title_en)
    else:
        kicker, title = panels[0].get("kicker"), panels[0].get("title")
    return {"kind": "page", "dark": dark, "kicker": kicker, "title": title, "panels": panels}


def _group_candidates_into_pages(candidates: list, report, sec_domain: bool) -> list:
    """Tahap 2 dari build_report_blocks: gabungkan daftar kandidat jadi daftar HALAMAN.
    Kandidat "kaya" (weight tinggi, mis. severity_distribution/critical_table) otomatis
    berakhir sendirian di halamannya sendiri (weight-nya sendiri sudah nyaris/melebihi
    kapasitas 1 halaman). Kandidat kecil digabung BERURUTAN (urutan narasi tetap dijaga)
    selama: (a) tema gabungannya sama (theme_tag), (b) warna latarnya sama (dark), (c) total
    bobot belum melewati kapasitas halaman, (d) jumlah panel belum melebihi batas aman (3).

    Setelah pengelompokan awal, ada 1 langkah tambahan (backstop): halaman 1-panel yang masih
    terlalu tipis (<60% kapasitas) dicoba disambung paksa ke halaman TETANGGA (warna latar
    tetap harus sama, tema boleh beda) — supaya tidak ada halaman kosong/tipis dibiarkan
    sendirian begitu saja, sesuai prinsip "larangan (a)" dari spesifikasi tata letak."""
    # PERMINTAAN USER: halaman "text-style" (SOC Technical Report — narasi jadi sorotan
    # utama) dibatasi maksimal 2 visual/panel per halaman + teks singkat, BUKAN ditumpuk
    # banyak-banyak (dulu "insight" — kartu ringkas trend/severity/risk/dynamic_section —
    # bisa sampai 4 panel/halaman krn kartunya kecil & seragam; sekarang disamakan dgn tema
    # lain, maks 2, supaya halaman "text" tetap terasa naratif, bukan jadi dashboard mini).
    PAGE_CAP_BY_THEME = {"insight": 0.85}
    MAX_PANELS_BY_THEME = {"insight": 2}
    DEFAULT_PAGE_CAP = 1.05
    DEFAULT_MAX_PANELS = 3
    MIN_FULL = 0.6

    pages: list = []
    bucket: list = []
    bucket_w = 0.0
    bucket_theme = None
    bucket_dark = None

    def flush():
        nonlocal bucket, bucket_w, bucket_theme, bucket_dark
        if bucket:
            pages.append(_page_from_panels(bucket, report, sec_domain))
        bucket, bucket_w, bucket_theme, bucket_dark = [], 0.0, None, None

    for cand in candidates:
        page_cap = PAGE_CAP_BY_THEME.get(bucket_theme, DEFAULT_PAGE_CAP)
        max_panels = MAX_PANELS_BY_THEME.get(bucket_theme, DEFAULT_MAX_PANELS)
        fits = (
            bucket
            and cand["theme_tag"] == bucket_theme
            and cand["dark"] == bucket_dark
            and bucket_w + cand["weight"] <= page_cap
            and len(bucket) < max_panels
        )
        if fits:
            bucket.append(cand)
            bucket_w += cand["weight"]
        else:
            flush()
            bucket, bucket_w, bucket_theme, bucket_dark = [cand], cand["weight"], cand["theme_tag"], cand["dark"]
    flush()

    idx = 0
    while idx < len(pages):
        page = pages[idx]
        panels = page["panels"]
        thin = len(panels) == 1 and panels[0]["weight"] < MIN_FULL
        if not thin:
            idx += 1
            continue
        panel = panels[0]
        merged = False
        for neighbor_idx, append_at_end in ((idx - 1, True), (idx + 1, False)):
            if 0 <= neighbor_idx < len(pages) and neighbor_idx != idx:
                neighbor = pages[neighbor_idx]
                n_weight = sum(p["weight"] for p in neighbor["panels"])
                # theme_tag "insight" (insight_tile/dynamic_section) dirender sbg kartu ringkas
                # TANPA judul sendiri (judul halaman dipakai bersama) — tidak boleh disambung ke
                # panel "mandiri" (category_distribution dkk, sudah punya judul sendiri di dalam
                # kontennya) krn akan menghasilkan judul dobel di 1 halaman yang sama.
                same_header_style = (panel["theme_tag"] == "insight") == (neighbor["panels"][0]["theme_tag"] == "insight")
                n_theme = neighbor["panels"][0]["theme_tag"]
                n_cap = PAGE_CAP_BY_THEME.get(n_theme, DEFAULT_PAGE_CAP)
                n_max = MAX_PANELS_BY_THEME.get(n_theme, DEFAULT_MAX_PANELS)
                if same_header_style and neighbor["dark"] == page["dark"] and n_weight + panel["weight"] <= n_cap and len(neighbor["panels"]) < n_max:
                    merged_panels = (neighbor["panels"] + [panel]) if append_at_end else ([panel] + neighbor["panels"])
                    pages[neighbor_idx] = _page_from_panels(merged_panels, report, sec_domain)
                    pages.pop(idx)
                    merged = True
                    break
        if not merged:
            idx += 1
    return pages


# ============================================================================
# build_report_blocks — SATU-SATUNYA tempat yang memutuskan "bagian apa yang
# tampil & angka/isi apa di dalamnya" untuk sebuah laporan. export_ppt.py,
# export_pdf.py, DAN endpoint preview (frontend) semua memanggil fungsi ini lalu
# tinggal MERENDER tiap block sesuai "kind"-nya (shape pptx / HTML / komponen
# React) — jadi ketiganya DIJAMIN menampilkan section & angka yang sama persis,
# tidak mungkin diam-diam beda kecuali fungsi ini sendiri yang diubah.
#
# SENGAJA TIDAK termasuk di sini: pilihan kosmetik acak per generate (sinonim
# label kicker, jumlah kolom grid, sudut ornamen) — itu variasi tampilan yang
# memang disengaja beda tiap kali file di-generate ulang (lihat docstring atas
# export_ppt.py), bukan bagian dari ISI laporan, jadi tetap jadi urusan
# masing-masing renderer. Kicker/judul TETAP (bukan sinonim acak) DITENTUKAN di
# sini lewat _L(report, ...) supaya export_ppt.py/export_pdf.py/frontend Preview
# semua membaca label yang SAMA & SUDAH BENAR bahasanya, bukan 3 salinan
# hardcode terpisah yang cuma pernah ditulis dalam Bahasa Indonesia.
#
# DUA TAHAP (rombak dari versi lama yang langsung blocks.append per topik):
#   Tahap 1 — kumpulkan tiap topik jadi 1 "kandidat" (_candidate(...)), LENGKAP
#   dgn saran bentuk visual & perkiraan "bobot" halaman (lihat catatan di
#   _candidate/_group_candidates_into_pages). Statistik/angka yang dihitung tiap
#   topik PERSIS SAMA seperti versi lama, tidak ada logika hitung yang berubah.
#   Tahap 2 — _group_candidates_into_pages() memutuskan kandidat mana jadi
#   halaman sendiri vs digabung dgn kandidat lain yang temanya nyambung &
#   sama-sama ringkas, sehingga tata letak tiap halaman proporsional dgn
#   isinya. Cover/Pendahuluan/Penutup TETAP di luar sistem ini (selalu halaman
#   sendiri, isinya juga selalu berukuran tetap terlepas dari data).
# ============================================================================
def build_report_blocks(report) -> list[dict]:
    parsed_data = get_parsed_data(report)
    report_stats = compute_statistics(parsed_data, report.data_type) if parsed_data else {"total_records": 0}
    ai_summary = report.ai_summary or {}

    total_records = report_stats.get("total_records", 0)
    severity = report_stats.get("severity_distribution") or {}
    total_sev = sum(severity.values())
    top_categories = report_stats.get("top_categories") or {}
    status_items = top_categories.get("status") or []

    used_labels: set = set()
    generic_category_keys = sorted(k for k in top_categories if k.startswith("category_"))
    category_pick = pick_category(top_categories, ["action", *generic_category_keys, "location", "destination_port"], used_labels)
    asset_pick = pick_category(top_categories, ["asset", "destination_port", "location", *generic_category_keys], used_labels)

    source_cols = report_stats.get("_source_columns") or {}
    severity_col = source_cols.get("severity")
    status_col = source_cols.get("status")
    date_col = source_cols.get("date")
    open_count = 0
    if status_col and parsed_data:
        for row in parsed_data:
            if classify_open_status(row.get(status_col)) is True:
                open_count += 1

    recommendations = normalize_recommendations(ai_summary.get("recommendations"))
    key_findings = build_key_findings(ai_summary, report_stats, open_count, sanitize_text, report=report)
    period_text = format_period(report)
    included = report.included_sections or {}
    is_included = lambda key: is_section_included(key, included)

    # chart_captions — AI diminta menulis satu narasi per chart, DIKUNCI per jenis chart
    # ("category"/"severity"/"status", lihat prompts.py) BUKAN posisi array. Sebelumnya dipakai
    # counter posisional (elemen ke-N = chart ke-N yang muncul), tapi itu salah pasang kalau
    # ada chart yang di-skip TANPA sepengetahuan AI — mis. severity_distribution ikut di-skip
    # kalau user uncheck "Severity Analysis" di Include Sections (is_included di bawah), atau
    # kalau kategori/status tidak terdeteksi di data — geser semua caption setelahnya ke chart
    # yang salah. Format lama (list, dari laporan yang sudah digenerate sebelum fix ini) tetap
    # didukung lewat fallback counter yang sama seperti sebelumnya, best-effort saja.
    _raw_chart_captions = ai_summary.get("chart_captions")
    _chart_caption_state = {"i": 0}

    def _get_chart_caption(kind: str, fallback: str | None = None):
        """`fallback` (opsional) — BUG NYATA YANG DIPERBAIKI (dilaporkan user, disertai contoh
        laporan): sebelum ini, kalau AI mengisi "chart_captions" TAPI cuma sebagian (mis. isi
        "category" & lupa "severity"/"status" — dict-nya TIDAK kosong, jadi fallback level-atas
        di ollama_client.py TIDAK PERNAH kepicu), chart yang key-nya tidak diisi AI tampil TANPA
        penjelasan sama sekali di laporan. Tiap pemanggil sekarang menyertakan fallback
        deterministik (dibangun dari angka yang SAMA persis dipakai `intro`/`legend` blok itu,
        lihat tiap titik panggilnya) — dipakai HANYA kalau AI benar-benar tidak mengisi key
        ini, supaya SETIAP chart selalu punya penjelasan di sampingnya, bukan cuma visual."""
        if isinstance(_raw_chart_captions, dict):
            val = _raw_chart_captions.get(kind)
            return sanitize_text(coerce_narrative_text(val)) if val else fallback
        if isinstance(_raw_chart_captions, list):
            captions = [sanitize_text(coerce_narrative_text(c)) for c in _raw_chart_captions if c]
            idx = _chart_caption_state["i"]
            _chart_caption_state["i"] += 1
            return captions[idx] if idx < len(captions) else fallback
        return fallback

    # Detect domain & language. report.domain_type baru reliable utk laporan yang diunggah
    # lewat detector baru (section_suggester.py) — laporan LAMA defaultnya None/"general" walau
    # data_type-nya sebenarnya security/financial/kpi_hr. Fallback ke data_type di bawah supaya
    # laporan lama (termasuk SOC lama) tidak meregresi ke kosakata "general".
    domain = (report.domain_type or "").lower().strip().replace("-", "_")
    if domain in ("", "general"):
        _dt = str(getattr(report, "data_type", "") or "").strip().lower()
        if _dt in ("keuangan", "financial"):
            domain = "financial"
        elif _dt == "kpi_hr":
            domain = "kpi_hr"
        elif _dt not in _NON_SECURITY_DATA_TYPES:
            domain = "soc_security"
        else:
            domain = "general"
    is_en = is_english(report)
    sec_domain = is_security_domain(report)

    # "Hero stat" — satu angka/persentase paling representatif utk laporan ini, dipakai di
    # cover (varian split-warna, lihat export_pdf.py/export_ppt.py) DAN slide section dinamis
    # (aux_stat, sudah ada sebelumnya) — DIPINDAH ke sini (sebelumnya cuma dihitung di dekat
    # section dinamis, jauh sesudah cover di-append) supaya SATU logika prioritas yang sama
    # dipakai di kedua tempat, bukan dua salinan yang bisa diam-diam beda. Prioritas: proporsi
    # Critical (kalau ada data severity) > kategori teratas > rata-rata kolom numerik > total
    # data mentah sebagai fallback paling umum.
    numeric_summary_items = list((report_stats.get("numeric_summary") or {}).items())
    hero_stat = None
    if total_sev:
        hero_stat = (
            f"{round(severity.get('critical', 0) / total_sev * 100, 1)}%",
            _L(report, "Proporsi Critical", "Critical Share") if sec_domain else _L(report, "Proporsi Tertinggi", "Highest Share"),
        )
    elif category_pick:
        top_item = category_pick[1][0]
        hero_stat = (str(top_item["count"]), humanize_label(category_pick[0], source_cols))
    elif numeric_summary_items:
        col, nstats = numeric_summary_items[0]
        avg_val = nstats.get("mean")
        formatted = f"{avg_val:,.0f}" if avg_val is not None else "-"
        if not is_english(report):
            formatted = formatted.replace(",", ".")
        hero_stat = (formatted, _L(report, f"Rata-rata {humanize_label(col, source_cols)}", f"Average {humanize_label(col, source_cols)}"))
    else:
        hero_stat = (str(total_records), _L(report, "Total Data", "Total Records"))

    # ---------------- Cover ----------------
    cat_count = len(top_categories)
    crit_count = severity.get("critical", 0)
    if sec_domain:
        info_line = _L(
            report,
            f"{total_records} entri log, {cat_count} kategori kejadian" + (f", {crit_count} insiden Critical" if total_sev else ""),
            f"{total_records} log entries, {cat_count} event categories" + (f", {crit_count} Critical incidents" if total_sev else ""),
        )
    else:
        info_line = _L(
            report,
            f"{total_records} data, {cat_count} kategori" + (f", {crit_count} insiden Critical" if total_sev else ""),
            f"{total_records} records, {cat_count} categories" + (f", {crit_count} Critical incidents" if total_sev else ""),
        )
    cover_block = {
        "kind": "cover",
        "dark": True,
        "kicker": _L(report, "LAPORAN ANALISIS", "ANALYSIS REPORT"),
        "title": report.title,
        "subtitle": sanitize_text(report.header_subtitle) or (
            _L(report, "Security Operation Center", "Security Operations Center") if sec_domain
            else humanize_data_type(report)
        ),
        "period_text": period_text,
        "period_label": _L(report, "Periode data.", "Data period."),
        "total_records": total_records,
        "category_count": cat_count,
        "critical_count": crit_count,
        "info_line": info_line,
        "header_title": (report.header_title or "PT PETROKIMIA GRESIK").upper(),
        "hero_stat": hero_stat,
        "hero_stat_kicker": _L(report, "CAPAIAN KESELURUHAN", "OVERALL FIGURE"),
    }

    # ---------------- Latar Belakang & Tujuan (Domain & Language Aware) ----------------
    if domain == "financial":
        data_name = "financial transactions" if is_en else "data transaksi & operasional keuangan"
        obj1_title = "Map Financial Position" if is_en else "Memetakan Postur Keuangan"
        obj1_desc = "Identify expense categories, revenue trends, and budget efficiency." if is_en else "Mengidentifikasi kategori beban, pendapatan, dan efisiensi anggaran."
        obj2_title = "Evaluate Budget Efficiency" if is_en else "Evaluasi Efisiensi Anggaran"
        obj2_desc = "Evaluate expenditure ratio against target plans." if is_en else "Mengevaluasi rasio pengeluaran terhadap target kerja perusahaan."
        obj3_title = "Formulate Recommendations" if is_en else "Menyusun Rekomendasi Finansial"
        obj3_desc = "Formulate cost optimization and savings actions." if is_en else "Merumuskan langkah optimalisasi biaya dan penghematan."
    elif domain == "kpi_hr":
        data_name = "KPI & performance evaluation data" if is_en else "data penilaian KPI & kinerja SDM/mitra"
        obj1_title = "Map Target Achievement" if is_en else "Memetakan Pencapaian Target"
        obj1_desc = "Identify KPI achievement scores per unit/division." if is_en else "Mengidentifikasi pencapaian skor KPI per divisi/unit kerja."
        obj2_title = "Evaluate Performance Gaps" if is_en else "Evaluasi Gap & Performa"
        obj2_desc = "Assess development areas and top performers." if is_en else "Menilai area pembinaan dan mitra dengan performa teratas."
        obj3_title = "Formulate Action Plans" if is_en else "Rekomendasi Pengembangan"
        obj3_desc = "Formulate performance improvement steps." if is_en else "Merumuskan langkah perbaikan kinerja dan alokasi target."
    elif domain == "soc_security":
        data_name = "cybersecurity log events" if is_en else "sistem keamanan siber"
        obj1_title = "Map Event Patterns" if is_en else "Memetakan Pola Kejadian"
        obj1_desc = "Identify categories, time trends, and target assets." if is_en else "Mengidentifikasi kategori, tren waktu, dan aset sasaran."
        obj2_title = "Assess Response Status" if is_en else "Menilai Efektivitas Respons"
        obj2_desc = "Evaluate incident mitigation status." if is_en else "Mengevaluasi status penanganan tiap insiden."
        obj3_title = "Formulate Mitigations" if is_en else "Menyusun Rekomendasi"
        obj3_desc = "Formulate priority mitigation steps based on data." if is_en else "Merumuskan langkah mitigasi prioritas berbasis temuan data."
    else:
        data_name = "operational data records" if is_en else "data operasional"
        obj1_title = "Map Data Distribution" if is_en else "Memetakan Distribusi Data"
        obj1_desc = "Identify trends, frequency patterns, and main categories." if is_en else "Mengidentifikasi tren, pola frekuensi, dan kategori dominan."
        obj2_title = "Evaluate Operational Metrics" if is_en else "Evaluasi Kinerja Operasional"
        obj2_desc = "Evaluate key indicators and status." if is_en else "Menilai indikator utama dan status penanganan."
        obj3_title = "Formulate Strategic Actions" if is_en else "Menyusun Rekomendasi Taktis"
        obj3_desc = "Formulate improvement steps based on findings." if is_en else "Merumuskan langkah perbaikan berbasis temuan data."

    if is_en:
        purpose_text = sanitize_text(
            f"Throughout the period {period_text}, a total of {total_records} {data_name} "
            f"were analyzed in this report to map key patterns, evaluate operational efficiency, "
            f"and formulate data-driven strategic recommendations."
        )
    else:
        pola_text = "pola kejadian" if domain == "soc_security" else "pola data"
        purpose_text = sanitize_text(
            f"Sepanjang periode {period_text}, tercatat {total_records} {data_name} "
            f"yang dianalisis pada laporan ini untuk memetakan {pola_text}, "
            f"menilai efektivitas operasional, dan menjadi dasar rekomendasi perbaikan."
        )

    intro_block = {
        "kind": "intro",
        "dark": False,
        "kicker": _L(report, "PENDAHULUAN", "INTRODUCTION"),
        "title": _L(report, "Latar Belakang dan Tujuan Analisis", "Background and Objectives"),
        "purpose_text": purpose_text,
        "objectives": [
            {"num": "1", "title": obj1_title, "detail": obj1_desc},
            {"num": "2", "title": obj2_title, "detail": obj2_desc},
            {"num": "3", "title": obj3_title, "detail": obj3_desc},
        ],
        "scope": {
            "panel_title": _L(report, "Ruang Lingkup Data", "Data Scope"),
            "period_label": _L(report, "Periode", "Period"),
            "period_text": period_text,
            "total_event_label": _L(report, "Total Event", "Total Events") if sec_domain else _L(report, "Total Data", "Total Records"),
            "total_records": total_records,
            "total_records_text": _L(report, f"{total_records} entri log", f"{total_records} log entries") if sec_domain
            else _L(report, f"{total_records} data", f"{total_records} records"),
            "source_file_label": _L(report, "Sumber Berkas", "Source File"),
            # BUG KECIL YANG DIPERBAIKI (dilaporkan user): nama file asli kadang berisi spasi
            # ganda/berlebih (mis. "Data Dummy PKG   - Pengadaan.pdf") — dirapikan jadi 1 spasi
            # di sini (tampilan saja, TIDAK mengubah nama file sebenarnya di sistem/DB).
            "input_file_name": " ".join((report.input_file_name or "-").split()),
            "data_type_label_label": _L(report, "Jenis Data", "Data Type"),
            "data_type_label": humanize_data_type(report),
            "footnote": _L(
                report,
                "Sumber. Data yang diunggah pengguna, diproses otomatis oleh sistem.",
                "Source. Data uploaded by the user, processed automatically by the system.",
            ),
        },
    }

    # ---------------- TAHAP 1: kumpulkan kandidat (bukan langsung blocks.append) ----------------
    candidates: list = []
    prior_texts: list = [purpose_text]

    # ---------------- Ringkasan Eksekutif (Domain & Language Aware) ----------------
    if is_included("executive_summary"):
        lbl_total = "Total Records" if is_en else "Total Data"
        stat_items = [(str(total_records), lbl_total)]

        if total_sev:
            if severity.get("critical"):
                lbl_crit = "Critical" if is_en else "Kategori Kritis"
                stat_items.append((str(severity["critical"]), lbl_crit))
            if severity.get("high"):
                lbl_high = "High Priority" if is_en else "Prioritas Tinggi"
                stat_items.append((str(severity["high"]), lbl_high))
        if status_col:
            closed = sum(1 for row in parsed_data if classify_open_status(row.get(status_col)) is False)
            if closed:
                lbl_closed = "Completed" if is_en else "Sudah Ditangani"
                stat_items.append((str(closed), lbl_closed))
            lbl_open = "Pending" if is_en else "Masih Terbuka"
            stat_items.append((str(open_count), lbl_open))
        if category_pick:
            lbl_cat = "Categories" if is_en else "Kategori Sumber"
            stat_items.append((str(len(top_categories)), lbl_cat))
        # Domain non-keamanan (KPI/keuangan/pengadaan/operasional) sering TIDAK punya konsep
        # severity/status sama sekali — tanpa ini kartu KPI cuma berisi 1-2 item (Total Data,
        # Kategori Sumber), jadi grid kartunya kelihatan besar & nyaris kosong. Tambahkan
        # metrik dari kolom numerik lain yang terdeteksi (mis. nilai kontrak, skor, biaya)
        # selama masih ada slot tersisa dari batas 6 kartu.
        numeric_summary = report_stats.get("numeric_summary") or {}
        for col, nstats in numeric_summary.items():
            if len(stat_items) >= 6:
                break
            avg_val = nstats.get("mean")
            if avg_val is None:
                continue
            formatted = f"{avg_val:,.0f}"
            if not is_en:
                formatted = formatted.replace(",", ".")
            col_label = humanize_label(col, source_cols)
            stat_items.append((formatted, f"Average {col_label}" if is_en else f"Rata-rata {col_label}"))
        stat_items = stat_items[:6]

        if domain == "financial":
            heading = f"Financial Snapshot, {period_text}" if is_en else f"Ringkasan Kinerja Keuangan, {period_text}"
        elif domain == "kpi_hr":
            heading = f"KPI Performance Snapshot, {period_text}" if is_en else f"Ringkasan Pencapaian KPI, {period_text}"
        elif domain == "soc_security":
            heading = f"Security Log Snapshot, {period_text}" if is_en else f"Snapshot Log Keamanan, {period_text}"
        else:
            heading = f"Operational Snapshot, {period_text}" if is_en else f"Ringkasan Data Operasional, {period_text}"

        caption = _shorten_to_caption(sanitize_text(coerce_narrative_text(ai_summary.get("executive_summary")) or (key_findings[0] if key_findings else "")))
        prior_texts.append(caption)
        # Panel "overview" ini SATU-SATUNYA kandidat bertema "overview" — tidak pernah
        # digabung dgn kandidat lain (lihat _group_candidates_into_pages: gabung mensyaratkan
        # theme_tag SAMA), jadi SELALU jadi halaman sendiri berapa pun isinya. Tanpa donut
        # pendamping ini, halaman berisi kartu KPI + 1-2 kalimat caption saja terasa nyaris
        # kosong (dilaporkan user). Dipakai DONUT (bukan bar, sudah dipakai Temuan Utama di
        # bawah — lihat `chart=severity_gauge or category_chart or status_chart`) supaya
        # bentuk visualnya tidak berulang persis dgn panel lain di laporan yang sama.
        exec_chart = None
        if category_pick:
            _ec_items = category_pick[1][:5]
            exec_chart = {"type": "donut", "categories": [it["value"] for it in _ec_items], "values": [it["count"] for it in _ec_items]}
        elif status_items:
            _ec_items = status_items[:5]
            exec_chart = {"type": "donut", "categories": [it["value"] for it in _ec_items], "values": [it["count"] for it in _ec_items]}
        candidates.append(_candidate(
            "executive_summary", "overview", min(0.95, 0.4 + 0.09 * len(stat_items)), True,
            kicker=None, title=_L(report, "Ringkasan Eksekutif", "Executive Summary"),
            heading=heading, stat_items=stat_items, caption=caption, chart=exec_chart,
        ))

    # ---------------- Data visual pendukung utk insight tiles/dynamic_section/key_findings ----------------
    # 3 bentuk visual TAMBAHAN (di luar aux_stat/aux_list generik) supaya section narasi AI
    # (Trend/Severity/Risk/kustom) & Temuan Utama ditemani chart/gauge kecil yang BENAR-BENAR
    # relevan dgn topiknya. Semua dihitung dari data yang SUDAH ADA (category_pick/status_items/
    # severity/report_stats) — tidak ada statistik baru. Jenis chart SENGAJA TETAP per sumber
    # data (bukan ikut visual_style acak laporan) — panel-panel ini panel PENDUKUNG kecil.
    aux_stat_value = hero_stat
    aux_list_items = None
    if category_pick:
        cat_total = sum(i["count"] for i in category_pick[1]) or 1
        aux_list_items = [
            {"label": it["value"], "value": f"{round(it['count'] / cat_total * 100, 1)}%"}
            for it in category_pick[1][:4]
        ]
    elif status_items:
        status_total = sum(i["count"] for i in status_items) or 1
        aux_list_items = [
            {"label": it["value"], "value": f"{round(it['count'] / status_total * 100, 1)}%"}
            for it in status_items[:4]
        ]

    category_chart = None
    if category_pick:
        _cc_items = category_pick[1][:4]
        category_chart = {"type": "bar", "categories": [it["value"] for it in _cc_items], "values": [it["count"] for it in _cc_items]}

    status_chart = None
    if status_items:
        _sc_items = status_items[:4]
        status_chart = {"type": "donut", "categories": [it["value"] for it in _sc_items], "values": [it["count"] for it in _sc_items]}

    # severity_gauge — persentase Critical+High dari seluruh event berseverity.
    severity_gauge = None
    if total_sev:
        crit_high_pct = round((severity.get("critical", 0) + severity.get("high", 0)) / total_sev * 100, 1)
        severity_gauge = {
            "type": "gauge", "value": crit_high_pct, "max": 100,
            "label": _L(report, "Critical + High", "Critical + High"), "severity_keys": ["critical"],
        }

    # trend_stat/trend_series_chart — kartu panah 2-titik ATAU chart batang+garis kumulatif per
    # PERIODE ASLI (deret waktu -> "bar+line kumulatif" sesuai karakter datanya), lihat
    # _compute_time_series di data_profiler.py (unit/labels/counts/cumulative, TIDAK berubah).
    trend_data = (report_stats.get("time_pattern") or {}).get("trend")
    trend_stat = None
    if trend_data:
        _pct = trend_data["pct_change"]
        _arrow = "▲" if _pct > 0 else ("▼" if _pct < 0 else "→")
        trend_stat = {
            "value": f"{_arrow} {abs(_pct)}%",
            "label": _L(
                report,
                f"dari {trend_data['first_half_count']} ke {trend_data['second_half_count']} event",
                f"from {trend_data['first_half_count']} to {trend_data['second_half_count']} events",
            ),
            "direction": "up" if _pct > 0 else ("down" if _pct < 0 else "flat"),
        }

    _time_series = report_stats.get("time_series") or {}
    trend_series_chart = None
    if len(_time_series.get("counts") or []) >= 3:
        # Dipotong ke 8 bucket TERAKHIR (dari maks 12 yang dihitung data_profiler.py) — tile
        # ini cuma sebagian lebar halaman, kolom lebih dari 8 mulai susah dibaca labelnya.
        trend_series_chart = {
            "type": "bar_line",
            "categories": _time_series["labels"][-8:],
            "values": _time_series["counts"][-8:],
            "cumulative": (_time_series.get("cumulative") or [])[-8:],
        }

    # ---------------- Ringkasan Analisis: Trend + Severity + Risk (tiap tile = 1 kandidat) ----
    # 3 dari 6 field WAJIB yang AI SELALU tulis & bisa diedit user di tab Edit Text. Sebelumnya
    # dipaksa 1 block "insight_dashboard" berisi tiles — sekarang tiap tile jadi kandidat
    # SENDIRI (tema "insight") supaya bisa juga bergabung dgn dynamic_section AI lain yang
    # temanya sama (analisis naratif + chart pendukung kecil), bukan cuma sesama tile bawaan.
    # RANCANG ULANG (permintaan user): chart di tile-tile ini SEBELUMNYA punya fallback
    # "pinjam" category_chart/status_chart kalau chart genuine topiknya sendiri tidak ada —
    # akibatnya breakdown kategori yang SAMA bisa muncul berulang kali dlm bentuk berbeda-beda
    # (bar/donut/stacked) di halaman yang berdekatan, terasa "kebanyakan grafik" tanpa
    # menambah informasi baru. Sekarang HANYA chart yang genuinely topiknya sendiri yang
    # dipakai (trend_series_chart utk tren, severity_gauge utk severity) — kalau tidak ada,
    # tile tampil TEKS SAJA (caption lebih panjang, 2 kalimat bukan 1) drpd memaksakan chart
    # daur ulang.
    if is_included("trend_analysis") and ai_summary.get("trend_analysis"):
        caption = _shorten_to_caption(sanitize_text(coerce_narrative_text(ai_summary.get("trend_analysis"))), max_sentences=2)
        prior_texts.append(caption)
        candidates.append(_candidate(
            "insight_tile", "insight", 0.34, False,
            kicker=_L(report, "ANALISIS", "ANALYSIS"), title=_L(report, "Analisis Tren", "Trend Analysis"),
            label=_L(report, "Analisis Tren", "Trend Analysis"),
            trend_stat=None if trend_series_chart else trend_stat,
            chart=trend_series_chart,
            aux_stat=None if (trend_stat or trend_series_chart) else aux_stat_value,
            caption=caption,
        ))

    # BUG DIPERBAIKI (dilaporkan user): "Severity"/"Penilaian Risiko" SEBELUMNYA SELALU
    # muncul asal AI menulis teksnya, apa pun jenis datanya — utk domain yang genuinely tidak
    # punya konsep severity/risiko keamanan (mis. data keuangan/KPI TANPA kolom severity),
    # 2 tile ini cuma memaksakan istilah yang tidak relevan. Sekarang HANYA muncul kalau
    # datanya domain keamanan ATAU genuinely punya data severity terdeteksi (total_sev > 0)
    # — sama seperti syarat halaman severity_distribution di bawah, supaya konsisten.
    _severity_relevant = sec_domain or total_sev > 0
    if _severity_relevant and is_included("severity_analysis") and ai_summary.get("severity_analysis"):
        sev_label = _L(report, "Tingkat Keparahan", "Severity") if sec_domain else _L(report, "Distribusi & Prioritas", "Distribution & Priority")
        caption = _shorten_to_caption(sanitize_text(coerce_narrative_text(ai_summary.get("severity_analysis"))), max_sentences=2)
        prior_texts.append(caption)
        candidates.append(_candidate(
            "insight_tile", "insight", 0.34, False,
            kicker=_L(report, "ANALISIS", "ANALYSIS"), title=sev_label,
            label=sev_label, trend_stat=None, chart=severity_gauge,
            aux_stat=None if severity_gauge else aux_stat_value, caption=caption,
        ))

    if _severity_relevant and is_included("risk_assessment") and ai_summary.get("risk_assessment"):
        caption = _shorten_to_caption(sanitize_text(coerce_narrative_text(ai_summary.get("risk_assessment"))), max_sentences=2)
        prior_texts.append(caption)
        candidates.append(_candidate(
            "insight_tile", "insight", 0.34, False,
            kicker=_L(report, "ANALISIS", "ANALYSIS"), title=_L(report, "Penilaian Risiko", "Risk Assessment"),
            label=_L(report, "Penilaian Risiko", "Risk Assessment"),
            trend_stat=None, chart=None,
            aux_stat=aux_stat_value, caption=caption,
        ))

    # dynamic_section (section kustom AI) SEKARANG SELALU TEKS SAJA (tanpa chart daur ulang)
    # — ini narasi topik spesifik tulisan AI, lebih pas diberi ruang teks penuh drpd dipaksa
    # ditemani chart generik yang seringnya kebetulan sama dgn chart di halaman lain.
    dynamic_sections = [s for s in (ai_summary.get("sections") or []) if isinstance(s, dict)]
    # Section PERTAMA (order 0) DILEWATI — section_suggester.py/prompts.py SECARA DESAIN
    # selalu mengharuskan order 0 berisi "ringkasan eksekutif tingkat tinggi", sudah
    # ditampilkan di kandidat Ringkasan Eksekutif lewat caption di atas.
    for idx, sec in enumerate(dynamic_sections[1:]):
        sec_title = sanitize_text(coerce_narrative_text(sec.get("title")))
        sec_content = sanitize_text(coerce_narrative_text(sec.get("content")))
        if not sec_title or not sec_content:
            continue
        use_list = (idx % 2 == 1) and bool(aux_list_items)
        text = _shorten_to_caption(sec_content, max_sentences=3)
        prior_texts.append(text)
        candidates.append(_candidate(
            "dynamic_section", "insight", 0.4, False,
            kicker=_L(report, "ANALISIS", "ANALYSIS"), title=sec_title,
            text=text, chart=None,
            aux_stat=None if use_list else aux_stat_value,
            aux_list=aux_list_items if use_list else None,
        ))

    # ---------------- Distribusi Kategori/Status/Radar KPI/Pola Waktu (tiap panel = 1 kandidat) --
    # Data DIHITUNG PERSIS sama seperti sebelumnya (tidak ada perubahan angka/logika) — yang
    # berubah cuma cara dikumpulkannya (kandidat lepas, bukan langsung dipaksa 1 block
    # "distribution_dashboard" tetap 2 kolom). severity_distribution TETAP condong jadi halaman
    # sendiri (bobotnya sengaja tinggi) karena sudah cukup padat: chart + panel highlight crit%.
    if category_pick and is_included("category_distribution"):
        label, items = category_pick
        top_items = items[:6]
        cat_total = sum(i["count"] for i in items) or 1
        intro = sanitize_text(_L(
            report,
            f"{top_items[0]['value']} mencatat volume tertinggi dengan {top_items[0]['count']} event "
            f"({round(top_items[0]['count']/cat_total*100,1)}% dari total)." if sec_domain
            else f"{top_items[0]['value']} mencatat volume tertinggi dengan {top_items[0]['count']} data "
            f"({round(top_items[0]['count']/cat_total*100,1)}% dari total).",
            f"{top_items[0]['value']} recorded the highest volume with {top_items[0]['count']} events "
            f"({round(top_items[0]['count']/cat_total*100,1)}% of the total).",
        ))
        legend = [
            {"color_index": _stable_color_index(it["value"]), "name": it["value"], "pct": round(it["count"] / cat_total * 100, 1)}
            for i, it in enumerate(top_items)
        ]
        ai_caption = _get_chart_caption("category", fallback=sanitize_text(_L(
            report,
            f"{top_items[0]['value']} mencatat volume tertinggi dengan {top_items[0]['count']} dari {cat_total} data "
            f"({round(top_items[0]['count']/cat_total*100,1)}%). Konsentrasi pada kategori ini bisa jadi dasar "
            f"evaluasi kebijakan atau alokasi sumber daya operasional ke depan.",
            f"{top_items[0]['value']} recorded the highest volume with {top_items[0]['count']} of {cat_total} records "
            f"({round(top_items[0]['count']/cat_total*100,1)}%). This concentration can guide policy evaluation or "
            f"operational resource allocation going forward.",
        )))
        prior_texts += [intro, ai_caption]
        candidates.append(_candidate(
            "category_distribution", "distribution", 0.42, False,
            kicker=_L(report, "ANALISIS DATA", "DATA ANALYSIS"),
            title=_L(report, f"Distribusi Event Berdasarkan {humanize_label(label, source_cols)}", f"Event Distribution by {humanize_label(label, source_cols)}") if sec_domain
            else _L(report, f"Distribusi Data Berdasarkan {humanize_label(label, source_cols)}", f"Data Distribution by {humanize_label(label, source_cols)}"),
            label=humanize_label(label, source_cols), raw_label=label,
            categories=[i["value"] for i in top_items], values=[i["count"] for i in top_items],
            legend=legend, legend_panel_title=_L(report, "Proporsi Kategori", "Category Proportion"),
            intro=intro,
            footnote=sanitize_text(_L(
                report,
                f"{top_items[0]['value']} menjadi kontributor volume terbesar pada kategori ini.",
                f"{top_items[0]['value']} is the largest volume contributor in this category.",
            )),
            ai_caption=ai_caption,
        ))

    if status_items and is_included("status_distribution"):
        status_total = sum(i["count"] for i in status_items) or 1
        top_status = status_items[0]
        status_intro = sanitize_text(_L(
            report,
            f"{round(top_status['count']/status_total*100,1)}% event berstatus {top_status['value']}. "
            f"Sebagian kecil masih memerlukan tindak lanjut aktif.",
            f"{round(top_status['count']/status_total*100,1)}% of events are in {top_status['value']} status. "
            f"A small portion still requires active follow-up.",
        ))
        top_status_items = status_items[:8]
        status_caption = sanitize_text(_L(
            report,
            f"{round(top_status['count']/status_total*100,1)}% dari {status_total} event berstatus {top_status['value']}. "
            f"Sisanya tersebar di status lain yang perlu terus dipantau agar tidak menumpuk jadi backlog.",
            f"{round(top_status['count']/status_total*100,1)}% of {status_total} events are in {top_status['value']} status. "
            f"The remainder is spread across other statuses that need ongoing monitoring to avoid becoming a backlog.",
        ))
        prior_texts += [status_intro, status_caption]
        candidates.append(_candidate(
            "status_distribution", "distribution", 0.42, False,
            kicker=_L(report, "ANALISIS DATA", "DATA ANALYSIS"),
            title=_L(report, "Status Penanganan Insiden", "Incident Handling Status"),
            categories=[i["value"] for i in top_status_items], values=[i["count"] for i in top_status_items],
            intro=status_intro, ai_caption=_get_chart_caption("status", fallback=status_caption),
        ))

    radar_data = _compute_kpi_radar(report_stats.get("numeric_summary") or {}, source_cols)
    if radar_data and is_included("kpi_radar"):
        top_axis_idx = max(range(len(radar_data["values"])), key=lambda i: radar_data["values"][i])
        radar_intro = sanitize_text(_L(
            report,
            f"{radar_data['axes'][top_axis_idx]} mencatat capaian tertinggi di antara {len(radar_data['axes'])} indikator yang dibandingkan.",
            f"{radar_data['axes'][top_axis_idx]} recorded the highest achievement among the {len(radar_data['axes'])} indicators compared.",
        ))
        prior_texts.append(radar_intro)
        candidates.append(_candidate(
            "kpi_radar", "distribution", 0.45, False,
            kicker=_L(report, "ANALISIS DATA", "DATA ANALYSIS"),
            title=_L(report, "Perbandingan Capaian Multi-Indikator", "Multi-Indicator Achievement Comparison"),
            axes=radar_data["axes"], values=radar_data["values"], intro=radar_intro,
        ))

    heatmap_data = _compute_day_hour_pattern(parsed_data, date_col)
    if heatmap_data and is_included("time_heatmap"):
        heatmap_intro = sanitize_text(_L(
            report,
            f"Pola kejadian dipetakan dari {heatmap_data['total']} baris bertanggal valid, membantu mengenali hari/jam dengan aktivitas terpadat.",
            f"The event pattern is mapped from {heatmap_data['total']} validly dated rows, helping identify the busiest day/hour combinations.",
        ))
        prior_texts.append(heatmap_intro)
        candidates.append(_candidate(
            "time_heatmap", "distribution", 0.5, False,
            kicker=_L(report, "ANALISIS DATA", "DATA ANALYSIS"),
            title=_L(report, "Pola Kejadian per Hari & Jam", "Event Pattern by Day & Hour"),
            day_labels=[_L(report, id_, en_) for id_, en_ in heatmap_data["day_labels"]], hour_labels=heatmap_data["hour_labels"],
            grid=heatmap_data["grid"], intro=heatmap_intro,
        ))

    if category_pick and date_col and is_included("period_compare"):
        compare_data = _compute_period_compare(parsed_data, date_col, source_cols.get(category_pick[0]), [it["value"] for it in category_pick[1][:4]])
        if compare_data:
            compare_intro = sanitize_text(_L(
                report,
                "Perbandingan jumlah kejadian antara paruh awal dan paruh akhir periode data, per kategori teratas.",
                "Comparison of event counts between the first and second half of the data period, by top category.",
            ))
            prior_texts.append(compare_intro)
            candidates.append(_candidate(
                "period_compare", "distribution", 0.45, False,
                kicker=_L(report, "ANALISIS DATA", "DATA ANALYSIS"),
                title=_L(report, "Perbandingan Antar Paruh Periode", "Period-over-Period Comparison"),
                categories=compare_data["categories"], series_a=compare_data["series_a"], series_b=compare_data["series_b"],
                label_a=_L(report, "Paruh Awal", "First Half"), label_b=_L(report, "Paruh Akhir", "Second Half"),
                intro=compare_intro,
            ))

    if total_sev > 0 and is_included("severity_analysis"):
        crit_pct = round(severity.get("critical", 0) / total_sev * 100, 1)
        high_pct = round(severity.get("high", 0) / total_sev * 100, 1)
        intro = sanitize_text(_L(
            report,
            f"{high_pct}% event berkategori High dan {crit_pct}% Critical. Kombinasi keduanya memerlukan perhatian dan eskalasi serius.",
            f"{high_pct}% of events are High and {crit_pct}% are Critical. This combination requires serious attention and escalation.",
        ))
        detail_text = None
        if category_pick:
            names = ", ".join(i["value"] for i in category_pick[1][:6])
            detail_text = sanitize_text(_L(
                report,
                f"Insiden Critical tersebar pada kategori {names}.",
                f"Critical incidents are spread across the following categories: {names}.",
            ))
        sev_caption = sanitize_text(_L(
            report,
            f"Critical mencapai {crit_pct}% dan High {high_pct}% dari seluruh {total_sev} event. "
            f"Gabungan proporsi setinggi ini perlu diprioritaskan penanganannya agar tidak berdampak lebih luas ke operasional.",
            f"Critical accounts for {crit_pct}% and High {high_pct}% of all {total_sev} events. "
            f"This combined high proportion should be prioritized to avoid broader operational impact.",
        ))
        prior_texts += [intro, sev_caption]
        candidates.append(_candidate(
            "severity_distribution", "distribution", 0.8, False,
            kicker=_L(report, "ANALISIS DATA", "DATA ANALYSIS"),
            title=_L(report, "Distribusi Tingkat Keparahan (Severity)", "Severity Distribution"),
            categories=[SEVERITY_LABEL[k] for k in SEVERITY_ORDER], values=[severity.get(k, 0) for k in SEVERITY_ORDER],
            severity_keys=list(SEVERITY_ORDER), intro=intro, crit_pct=crit_pct,
            panel_text=_L(report, "dari seluruh event berstatus Critical Severity", "of all events at Critical severity"),
            detail_text=detail_text, ai_caption=_get_chart_caption("severity", fallback=sev_caption),
        ))

    # ---------------- Tabel Insiden Critical/Prioritas Tinggi ----------------
    if severity_col and parsed_data:
        critical_rows = [row for row in parsed_data if _classify_severity_value(str(row.get(severity_col, ""))) == "critical"]
        if len(critical_rows) < 5:
            critical_rows += [row for row in parsed_data if _classify_severity_value(str(row.get(severity_col, ""))) == "high"]
        critical_rows = critical_rows[:12]

        if critical_rows and is_included("critical_table"):
            headers = [_L(report, "No", "No")]
            if category_pick:
                headers.append(humanize_label(category_pick[0], source_cols))
            headers.append("Severity")
            if status_col:
                headers.append(_L(report, "Status", "Status"))

            cat_col_name = source_cols.get(category_pick[0]) if category_pick else None
            rows_out = []
            highlight_idx = []
            for idx, row in enumerate(critical_rows):
                row_vals = [str(idx + 1)]
                if category_pick:
                    row_vals.append(str(row.get(cat_col_name, "-")) if cat_col_name else "-")
                row_vals.append(_classify_severity_value(str(row.get(severity_col, ""))).capitalize())
                if status_col:
                    status_val = row.get(status_col, "-")
                    row_vals.append(str(status_val))
                    if classify_open_status(status_val) is True:
                        highlight_idx.append(idx)
                rows_out.append(row_vals)

            candidates.append(_candidate(
                "critical_table", "highlight", 1.0, False,
                kicker=_L(report, "SOROTAN INSIDEN", "INCIDENT HIGHLIGHT") if sec_domain else _L(report, "SOROTAN DATA", "DATA HIGHLIGHT"),
                title=_L(report, f"{len(critical_rows)} Insiden Prioritas Tinggi", f"{len(critical_rows)} High-Priority Incidents") if sec_domain
                else _L(report, f"{len(critical_rows)} Item Prioritas Tinggi", f"{len(critical_rows)} High-Priority Items"),
                headers=headers, rows=rows_out, highlight_idx=highlight_idx, open_count=open_count,
                kicker_is_critical=bool(open_count),
                caption=sanitize_text(_L(
                    report,
                    f"Baris merah menandai {open_count} insiden yang masih dalam proses penanganan per akhir periode data.",
                    f"Red rows mark {open_count} incidents still in progress as of the end of the data period.",
                ) if sec_domain else _L(
                    report,
                    f"Baris merah menandai {open_count} item yang masih dalam proses per akhir periode data.",
                    f"Red rows mark {open_count} items still in progress as of the end of the data period.",
                )) if open_count else None,
            ))

    # ---------------- Aset Paling Sering Menjadi Sasaran ----------------
    if asset_pick and is_included("asset_cards"):
        label, items = asset_pick
        asset_total = sum(i["count"] for i in items) or 1
        top_assets = items[:3]
        card_items = []
        for idx, item in enumerate(top_assets):
            pct = round(item["count"] / asset_total * 100, 1)
            card_items.append({
                "num": str(idx + 1),
                "name": item["value"],
                "count": item["count"],
                "pct": pct,
                "stat": _L(report, f"{item['count']} event", f"{item['count']} events") if sec_domain
                else _L(report, f"{item['count']} data", f"{item['count']} entries"),
                "detail": sanitize_text(_L(
                    report,
                    f"Tercatat {item['count']} kejadian ({pct}% dari total) yang menyasar kategori ini.",
                    f"Recorded {item['count']} occurrences ({pct}% of the total) affecting this category.",
                ) if sec_domain else _L(
                    report,
                    f"Tercatat {item['count']} data ({pct}% dari total) pada kategori ini.",
                    f"Recorded {item['count']} entries ({pct}% of the total) in this category.",
                )),
            })
        candidates.append(_candidate(
            "asset_cards", "highlight", 0.68, True,
            kicker=_L(report, "SOROTAN INSIDEN", "INCIDENT HIGHLIGHT") if sec_domain else _L(report, "SOROTAN DATA", "DATA HIGHLIGHT"),
            title=_L(
                report,
                f"{humanize_label(label, source_cols)} yang Paling Sering Menjadi Sasaran",
                f"Most Frequently Affected {humanize_label(label, source_cols)}",
            ) if sec_domain else _L(
                report,
                f"{humanize_label(label, source_cols)} Paling Sering Muncul",
                f"Most Frequent {humanize_label(label, source_cols)}",
            ),
            label=humanize_label(label, source_cols), items=card_items,
        ))

    # ---------------- Temuan Utama ----------------
    if key_findings and is_included("key_findings"):
        findings_items = []
        for idx, finding in enumerate(key_findings):
            title_part, _, detail_part = finding.partition(". ")
            if not detail_part:
                title_part, detail_part = finding, ""
            findings_items.append({
                "num": str(idx + 1),
                "title": title_part.strip() or finding,
                "detail": detail_part.strip(),
                "is_critical": bool(open_count and idx == 0),
            })
        prior_texts += key_findings
        candidates.append(_candidate(
            "key_findings", "highlight", 0.7, False,
            kicker=_L(report, "ANALISIS", "ANALYSIS"), title=_L(report, "Temuan Utama", "Key Findings"),
            items=findings_items,
            # Panel visual pendukung — pakai ulang persis data yang sudah dihitung di atas.
            chart=severity_gauge or category_chart or status_chart,
        ))

    # ---------------- Rekomendasi Mitigasi ----------------
    recommendations_shown = bool(is_included("recommendations") and recommendations)
    if recommendations_shown:
        items = recommendations
        rec_items = []
        for idx, item in enumerate(items):
            raw_title = item.get("title")
            raw_detail = item.get("detail") or ""
            if raw_title:
                title_txt = raw_title
                detail_txt = raw_detail or None
            else:
                # Tidak ada title terpisah — ambil kalimat pertama sebagai judul lewat batas
                # kalimat alami (". "), BUKAN potongan jumlah karakter tetap.
                title_txt, _, rest = raw_detail.partition(". ")
                detail_txt = rest.strip() or None
                if not title_txt:
                    title_txt = raw_detail
                elif not detail_txt and len(title_txt) > 70:
                    words = title_txt.split()
                    short_words, length = [], 0
                    for w in words:
                        if length + len(w) + 1 > 55:
                            break
                        short_words.append(w)
                        length += len(w) + 1
                    if short_words and len(short_words) < len(words):
                        detail_txt = title_txt
                        title_txt = " ".join(short_words) + "…"
            rec_items.append({
                "num": str(idx + 1),
                "title": sanitize_text(title_txt),
                "detail": sanitize_text(detail_txt) if detail_txt else None,
            })
        prior_texts += [r["title"] for r in rec_items] + [r["detail"] for r in rec_items if r["detail"]]
        # SOC memakai maksimal 2 rekomendasi per halaman agar judul dan keterangan panjang
        # tetap terbaca. Semua rekomendasi tetap dipaginasi, tidak ada yang dibuang.
        soc_recommendations_per_page = 2
        for chunk_index in range(0, len(rec_items), soc_recommendations_per_page):
            chunk = rec_items[chunk_index:chunk_index + soc_recommendations_per_page]
            continuation = chunk_index > 0
            candidates.append(_candidate(
                "recommendations", "action", min(0.9, 0.35 + 0.09 * len(chunk)), False,
                kicker=_L(report, "TINDAK LANJUT", "FOLLOW-UP"),
                title=_L(report, "Rekomendasi Mitigasi" if not continuation else "Rekomendasi Mitigasi (Lanjutan)", "Mitigation Recommendations" if not continuation else "Mitigation Recommendations (Continued)"),
                items=chunk,
            ))

    # ---------------- Kesimpulan (opsional — hanya kalau menambah insight baru) ----------------
    if is_included("conclusion") and ai_summary.get("conclusion"):
        conclusion_text = sanitize_text(coerce_narrative_text(ai_summary.get("conclusion")))
        if _conclusion_adds_new_insight(conclusion_text, prior_texts):
            pills = []
            if total_sev and status_col:
                resolved_pct = round((total_sev - open_count) / total_sev * 100, 1)
                pills.append(_L(
                    report,
                    f"{resolved_pct}% event tertangani" if sec_domain else f"{resolved_pct}% data tertangani",
                    f"{resolved_pct}% of events resolved",
                ))
            if category_pick:
                pills.append(_L(
                    report,
                    f"{category_pick[1][0]['value']} jadi prioritas perhatian",
                    f"{category_pick[1][0]['value']} is the top priority",
                ))
            if open_count:
                pills.append(_L(
                    report,
                    f"{open_count} insiden masih berjalan" if sec_domain else f"{open_count} item masih berjalan",
                    f"{open_count} incidents still in progress" if sec_domain else f"{open_count} items still in progress",
                ))

            # BUG YANG DIPERBAIKI (dilaporkan user): kalau halaman "Rekomendasi Mitigasi" di
            # atas SUDAH tampil, daftar "Prioritas Berikutnya" ini mengambil 4 item PERTAMA
            # dari `recommendations` YANG SAMA PERSIS — hasilnya 2 halaman berurutan
            # menampilkan rekomendasi yang identik. Diisi HANYA kalau halaman Rekomendasi
            # Mitigasi tidak ada (mis. is_included("recommendations")=False), supaya
            # Kesimpulan tetap berguna sbg satu-satunya tempat rekomendasi konkret muncul.
            priority_items = []
            if not recommendations_shown:
                for idx, rec in enumerate(recommendations):
                    letter = chr(ord("a") + idx) if idx < 26 else str(idx + 1)
                    rec_title = rec.get("title") or (rec.get("detail") or "").partition(". ")[0] or rec.get("detail") or ""
                    priority_items.append({"letter": letter, "text": sanitize_text(rec_title)})

            candidates.append(_candidate(
                "conclusion", "action", 0.62, True,
                kicker=_L(report, "RINGKASAN AKHIR", "FINAL SUMMARY"), title=_L(report, "Kesimpulan", "Conclusion"),
                text=_shorten_to_caption(conclusion_text, max_sentences=3), pills=pills,
                priority_panel_title=_L(report, "Prioritas Berikutnya", "Next Priorities"),
                priority_items=priority_items,
            ))

    # ---------------- TAHAP 2: kelompokkan kandidat jadi halaman ----------------
    pages = _group_candidates_into_pages(candidates, report, sec_domain)

    # ---------------- Penutup ----------------
    closing_block = {
        "kind": "closing",
        "dark": True,
        "title": report.title,
        "thank_you": _L(report, "Terima Kasih", "Thank You"),
        "note": _L(report, "Diskusi dan pertanyaan dipersilakan.", "Questions and discussion are welcome."),
        "hero_stat": hero_stat,
        "header_title": (report.header_title or "PT PETROKIMIA GRESIK").upper(),
    }

    return [cover_block, intro_block, *pages, closing_block]


# ==============================================================================
# Management Report Template
# Template khusus untuk laporan eksekutif/manajemen — lebih banyak grafis,
# KPI cards, risk heatmap, dan action items daripada narasi panjang.
# Dipakai ketika report.template_type == "Management Report"
# ==============================================================================

def build_management_report_blocks(report) -> list[dict]:
    """
    Blok laporan untuk template Management Report — "Visual tinggi, KPI ringkas, peta risiko
    & action items eksekutif" (lihat label di Step2Settings.tsx), pasangan dari
    build_report_blocks() ("SOC Technical Report" — analisis mendalam). Bedanya BUKAN "ada
    chart vs tanpa chart" (dua-duanya sama-sama pakai chart), tapi PORSI & KEPADATAN: di sini
    kartu angka besar-besar + chart jadi sorotan utama, teks penjelasan dipangkas seperlunya
    saja (1-2 kalimat per bagian) — bukan dihilangkan total.

    RANCANG ULANG (permintaan user): 3 BUG NYATA diperbaiki di sini (ditemukan lewat laporan
    sungguhan yang gagal/aneh saat diuji) —
    1. KPI grid & label "Peta Risiko" SEBELUMNYA hardcode istilah keamanan siber (Critical
       Threats/SLA/Insiden) apa pun jenis datanya — utk data non-keamanan (KPI/keuangan/dst)
       semua kartu tampil 0/tidak nyambung. Sekarang ikut menyesuaikan jenis data, sama seperti
       build_report_blocks() (pakai ulang is_security_domain/pick_category/numeric_summary).
    2. "Tren & Pola" SEBELUMNYA menampilkan representasi dict Python mentah sbg teks
       (mis. "{'value': 'Belanja TI', 'count': 8}") krn kode mengasumsikan tiap item
       top_categories berupa tuple/list, padahal isinya dict {"value","count"}.
    3. "Rekomendasi Prioritas" SEBELUMNYA menampilkan judul & detail dgn ISI SAMA PERSIS
       berulang (detail seharusnya SISA kalimat setelah judul diambil, bukan teks penuh lagi).
    """
    parsed_data = get_parsed_data(report)
    report_stats = compute_statistics(parsed_data, report.data_type) if parsed_data else {"total_records": 0}
    ai_summary = report.ai_summary or {}

    total_records = report_stats.get("total_records", 0)
    severity = report_stats.get("severity_distribution") or {}
    total_sev = sum(severity.values())
    top_categories = report_stats.get("top_categories") or {}
    recommendations = normalize_recommendations(ai_summary.get("recommendations"))
    is_id = (getattr(report, "language", "Indonesian") or "Indonesian").strip().lower() == "indonesian"

    def L(id_text: str, en_text: str) -> str:
        return id_text if is_id else en_text

    sec_domain = is_security_domain(report)
    source_cols = report_stats.get("_source_columns") or {}
    generic_category_keys = sorted(k for k in top_categories if k.startswith("category_"))
    used_labels: set = set()
    category_pick = pick_category(top_categories, ["action", *generic_category_keys, "location", "destination_port"], used_labels)
    asset_pick = pick_category(top_categories, ["asset", "destination_port", "location", *generic_category_keys], used_labels)
    numeric_summary = report_stats.get("numeric_summary") or {}
    # BUG YANG DIPERBAIKI (dilaporkan user): fungsi ini SEBELUMNYA tidak pernah memanggil
    # is_section_included() sama sekali — ceklis "Include Sections" di wizard nol pengaruh
    # ke gaya laporan Management Report. Pola & kunci section SAMA PERSIS dgn
    # build_report_blocks() di atas (mis. "period_compare"/"kpi_radar"/"time_heatmap") supaya
    # 1 ceklis konsisten mengontrol konsep yang sama di kedua gaya laporan.
    included = report.included_sections or {}
    is_included = lambda key: is_section_included(key, included)

    critical_count = report.threat_count_critical or severity.get("critical", 0)
    high_count = report.threat_count_high or severity.get("high", 0)

    # SLA hanya bermakna utk data yang genuinely punya konsep SLA/insiden (domain keamanan
    # DENGAN data severity) — dipaksakan ke SEMUA jenis data sebelumnya jadi angka "100%" palsu
    # yang tidak berarti apa-apa utk mis. data anggaran/KPI.
    sla_met = getattr(report, "sla_met", True)
    sla_pct = 100 if sla_met else max(0, 100 - round((getattr(report, "processing_time_sec", 0) or 0) / 3))

    status_col = source_cols.get("status")
    severity_col = source_cols.get("severity")
    open_count = 0
    resolved_count = 0
    if status_col and parsed_data:
        for row in parsed_data:
            val = classify_open_status(row.get(status_col))
            if val is True:
                open_count += 1
            elif val is False:
                resolved_count += 1
    resolved_pct = round(resolved_count / max(total_records, 1) * 100)
    key_findings = build_key_findings(ai_summary, report_stats, open_count, sanitize_text, report=report)

    blocks = []

    # ---- Cover ----
    _mgmt_period_text = format_period(report)
    blocks.append({
        "kind": "cover",
        "dark": True,
        # BUG YANG DIPERBAIKI: dict ini sebelumnya tidak menyertakan "kicker"/"period_label"/
        # "period_text"/"info_line" — field WAJIB dibaca _build_cover_block/_split_cover_td
        # (export_pdf.py) & _build_cover_slide/add_split_cover_slide (export_ppt.py), sama
        # persis skema yang dipakai build_report_blocks() di file ini. Tanpa field ini, ekspor
        # PDF/PPT utk template "Management Report" gagal dgn KeyError begitu blok cover dirender.
        "kicker": L("LAPORAN MANAJEMEN", "MANAGEMENT REPORT"),
        "title": report.title,
        "subtitle": L("Laporan Eksekutif — Management Report", "Executive Report — Management Report"),
        "date": format_report_date(report.created_at, report.language),
        "period": _mgmt_period_text,
        "period_text": _mgmt_period_text,
        "period_label": L("Periode data.", "Data period."),
        "total_records": total_records,
        "category_count": len(top_categories),
        "critical_count": critical_count,
        "info_line": L(
            f"{total_records} data, {critical_count} kategori kritis",
            f"{total_records} records, {critical_count} critical categories",
        ),
        "hero_stat": (str(total_records), L("Total Data", "Total Records")),
        "hero_stat_kicker": L("CAPAIAN KESELURUHAN", "OVERALL FIGURE"),
        "header_title": (report.header_title or "PT PETROKIMIA GRESIK").upper(),
        "header_subtitle": report.header_subtitle or "Sistem Otomasi Laporan & Eksekutif Presentasi Berbasis AI",
        "cover_style": "split",
        "theme_color": resolve_theme_color(report),
        "is_management": True,
    })

    # ---- KPI Grid — 6 kartu angka kunci, ISINYA ikut jenis data ----
    if total_sev:
        # Data punya dimensi severity (biasanya domain keamanan) — kartu bertema
        # insiden/SLA genuinely bermakna di sini.
        lbl_total = L("Total Insiden", "Total Incidents") if sec_domain else L("Total Event", "Total Events")
        kpi_items = [
            {"label": lbl_total, "value": str(total_records), "icon": "shield", "color": "blue", "delta": None},
            {
                "label": L("Critical", "Critical") if sec_domain else L("Prioritas Tertinggi", "Highest Priority"),
                "value": str(critical_count), "icon": "fire", "color": "red",
                "delta": L("Perlu tindakan segera", "Requires immediate action") if critical_count > 0 else L("Aman", "Safe"),
            },
            {"label": L("High", "High"), "value": str(high_count), "icon": "warning", "color": "orange", "delta": None},
        ]
        if status_col:
            kpi_items.append({
                "label": L("SLA Terpenuhi", "SLA Met"), "value": f"{sla_pct}%", "icon": "clock",
                "color": "green" if sla_pct >= 80 else "red", "delta": L("Target: ≥ 80%", "Target: ≥ 80%"),
            })
            kpi_items.append({
                "label": L("Terselesaikan", "Resolved"), "value": f"{resolved_pct}%", "icon": "check",
                "color": "green" if resolved_pct >= 70 else "amber", "delta": f"{resolved_count} / {total_records}",
            })
            kpi_items.append({
                "label": L("Masih Terbuka", "Still Open"), "value": str(open_count), "icon": "alert",
                "color": "red" if open_count > 0 else "green",
                "delta": L("Butuh perhatian", "Needs attention") if open_count > 0 else L("Semua tertangani", "All handled"),
            })
    else:
        # Data non-keamanan (KPI/keuangan/pengadaan/operasional dkk) — TIDAK ADA konsep
        # severity/SLA, jadi kartu dibangun dari kategori & kolom numerik yang genuinely
        # terdeteksi (pola sama dgn stat_items di build_report_blocks/executive_summary).
        kpi_items = [{"label": L("Total Data", "Total Records"), "value": str(total_records), "icon": "shield", "color": "blue", "delta": None}]
        if category_pick:
            label, items = category_pick
            top_item = items[0]
            cat_label = humanize_label(label, source_cols)
            # BUG YANG DIPERBAIKI (dilaporkan user): kartu ini dulu label=nama kolom (mis.
            # "Unit Produksi"), value=jumlah data kategori TERATAS, delta=nama kategori
            # teratas — jadi terbaca seolah "Unit Produksi: 11" padahal 11 itu jumlah data
            # Pabrik II B saja, bukan jumlah unit produksi. Sekarang value = nama kategori
            # teratas, delta = jumlah datanya, supaya kartu ini jelas berarti "siapa yang
            # teratas", bukan tercampur dgn metrik lain.
            kpi_items.append({
                "label": L(f"{cat_label} Teratas", f"Top {cat_label}"), "value": top_item["value"],
                "icon": "tag", "color": "amber",
                "delta": L(f"{top_item['count']} data", f"{top_item['count']} records"),
            })
        kpi_items.append({"label": L("Kategori Sumber", "Categories"), "value": str(len(top_categories)), "icon": "grid", "color": "green", "delta": None})
        if status_col:
            kpi_items.append({
                "label": L("Sudah Ditangani", "Completed"), "value": f"{resolved_pct}%", "icon": "check",
                "color": "green" if resolved_pct >= 70 else "amber", "delta": f"{resolved_count} / {total_records}",
            })
            kpi_items.append({
                "label": L("Masih Terbuka", "Still Open"), "value": str(open_count), "icon": "alert",
                "color": "red" if open_count > 0 else "green", "delta": None,
            })
        for col, nstats in numeric_summary.items():
            if len(kpi_items) >= 6:
                break
            avg_val = nstats.get("mean")
            if avg_val is None:
                continue
            formatted = f"{avg_val:,.0f}".replace(",", ".") if is_id else f"{avg_val:,.0f}"
            kpi_items.append({
                "label": L(f"Rata-rata {humanize_label(col, source_cols)}", f"Average {humanize_label(col, source_cols)}"),
                "value": formatted, "icon": "chart", "color": "blue", "delta": None,
            })
    kpi_items = kpi_items[:6]
    # total_records==0 = tidak ada data sama sekali (kasus tepi) — daripada kartu KPI
    # tampil dgn angka nol semua, halaman ini di-skip juga.
    if kpi_items and total_records and is_included("executive_summary"):
        blocks.append({
            "kind": "management_kpi_grid",
            "kicker": L("RINGKASAN EKSEKUTIF", "EXECUTIVE SUMMARY"),
            "title": L("Indikator Kinerja Utama", "Key Performance Indicators"),
            "items": kpi_items,
        })

    # PERMINTAAN USER: template "Visual tinggi" ini SEBELUMNYA menaruh tiap jenis
    # visualisasi (peta risiko, radar, funnel, perbandingan periode, heatmap waktu, tren) di
    # HALAMANNYA SENDIRI-SENDIRI — hasilnya "1 chart per halaman" berkali-kali, bukan benar2
    # padat/visual. visual_tiles menampung SEMUA jenis chart yang tersedia (bukan cuma yang
    # ada datanya) lalu ditumpuk jadi 1 (atau lebih, lihat loop chunking di bawah) halaman
    # dashboard grid — beberapa jenis visual sekaligus, keterangan tiap tile dipangkas jadi
    # 1 kalimat saja (bukan pengganti, tetap chart SUNGGUHAN per jenis data, cuma lebih ringkas).
    visual_tiles: list = []

    # ---- Distribusi Risiko/Kategori — severity kalau ada, kalau tidak pakai ranking kategori
    # teratas (dulu SELALU severity bars, tampil kosong total 0% utk data non-keamanan) ----
    if total_sev:
        bars = []
        for sev_key in ["critical", "high", "medium", "low", "informational"]:
            count = severity.get(sev_key, 0)
            pct = round(count / max(total_sev, 1) * 100)
            bars.append({
                "label": sev_key.title(), "count": count, "pct": pct,
                "color": {"critical": "red", "high": "orange", "medium": "amber", "low": "blue", "informational": "gray"}.get(sev_key, "gray"),
            })
        risk_title = L("Peta Risiko Keamanan", "Security Risk Map") if sec_domain else L("Peta Distribusi Prioritas", "Priority Distribution Map")
        risk_mode = "severity"
        # BUG DIPERBAIKI: sebelumnya narasi halaman "risiko" ini diambil dari
        # threat_analysis/trend_analysis (topik TREN, bukan risiko) — teks yang tampil sering
        # tidak nyambung dgn judul halamannya sendiri. Diganti prioritas field yang genuinely
        # membahas risiko/severity.
        risk_narrative = ai_summary.get("risk_assessment") or ai_summary.get("severity_analysis") or ai_summary.get("threat_analysis")
    else:
        bars = []
        risk_title = L("Peta Distribusi Kategori", "Category Distribution Map")
        risk_mode = "category"
        risk_narrative = ai_summary.get("risk_assessment") or ai_summary.get("severity_analysis")
        if category_pick:
            label, items = category_pick
            cat_total = sum(i["count"] for i in items) or 1
            palette = ["blue", "green", "amber", "orange", "gray", "red"]
            for i, item in enumerate(items[:6]):
                bars.append({
                    "label": item["value"], "count": item["count"],
                    "pct": round(item["count"] / cat_total * 100), "color": palette[i % len(palette)],
                })
    # Tile ini di-SKIP kalau memang tidak ada apa pun utk ditampilkan (bars kosong) —
    # jumlah/kehadiran tile FLEKSIBEL mengikuti data yang tersedia, bukan struktur tetap
    # (prinsip yang sama dipakai build_report_blocks(): tata letak proporsional dgn isinya).
    if bars and is_included("severity_analysis" if risk_mode == "severity" else "category_distribution"):
        visual_tiles.append({
            "tile_kind": "risk_heatmap",
            "kicker": L("DISTRIBUSI RISIKO", "RISK DISTRIBUTION") if risk_mode == "severity" else L("DISTRIBUSI DATA", "DATA DISTRIBUTION"),
            "title": risk_title,
            "mode": risk_mode,
            "bars": bars,
            # BUG DIPERBAIKI: model AI kadang "mengarang struktur" (list/dict bersarang, mis.
            # [{"id":"high_risk","description":...,"count":...}]) utk field yang kontraknya
            # SEHARUSNYA kalimat polos — tanpa coerce_narrative_text(), repr Python mentahnya
            # ("{'risk_assessment': [...]}") tampil apa adanya di laporan. sanitize_text() SENDIRI
            # cuma str(x), tidak meratakan struktur — coerce_narrative_text() WAJIB dipanggil
            # duluan (pola yang sama sudah dipakai di semua field naratif lain di file ini).
            "caption": _shorten_to_caption(sanitize_text(coerce_narrative_text(risk_narrative)), max_sentences=1) if risk_narrative else None,
        })

    # ---- Perbandingan Multi-Indikator (radar) — HANYA kalau data punya >=3 kolom numerik
    # genuinely sebanding (skor/nilai KPI dst).
    radar_data = _compute_kpi_radar(numeric_summary, source_cols)
    if radar_data and is_included("kpi_radar"):
        top_axis_idx = max(range(len(radar_data["values"])), key=lambda i: radar_data["values"][i])
        visual_tiles.append({
            "tile_kind": "kpi_radar",
            "kicker": L("PERBANDINGAN INDIKATOR", "INDICATOR COMPARISON"),
            "title": L("Perbandingan Capaian Multi-Indikator", "Multi-Indicator Achievement Comparison"),
            "axes": radar_data["axes"],
            "values": radar_data["values"],
            "caption": L(
                f"{radar_data['axes'][top_axis_idx]} mencatat capaian tertinggi.",
                f"{radar_data['axes'][top_axis_idx]} recorded the highest achievement.",
            ),
        })

    # ---- Alur Status (funnel) — HANYA kalau data punya kolom status genuinely terdeteksi
    # (Open/Investigating/Resolved dst) — bentuk visual dipilih sesuai KARAKTER data (alur
    # bertingkat -> funnel), bukan ranked-bar yang sama dipakai di tile Distribusi.
    status_items = top_categories.get("status") or []
    if status_items and is_included("status_distribution"):
        order = sorted(status_items, key=lambda it: -it["count"])[:6]
        visual_tiles.append({
            "tile_kind": "status_funnel",
            "kicker": L("STATUS PENANGANAN", "HANDLING STATUS"),
            "title": L("Alur Status Penanganan", "Handling Status Flow"),
            "categories": [it["value"] for it in order],
            "values": [it["count"] for it in order],
            "caption": None,
        })

    # ---- Perbandingan Antar Paruh Periode (grouped bar) — HANYA kalau ada kolom tanggal +
    # kategori genuinely terdeteksi. Bentuk visual dipilih sesuai KARAKTER data (perbandingan
    # 2 periode -> grouped bar), bukan ranked-bar yang sama dipakai di tile Distribusi.
    date_col = source_cols.get("date")
    if category_pick and date_col and is_included("period_compare"):
        _label, _items = category_pick
        compare_data = _compute_period_compare(parsed_data, date_col, source_cols.get(_label), [it["value"] for it in _items[:4]])
        if compare_data:
            visual_tiles.append({
                "tile_kind": "period_compare",
                "kicker": L("PERBANDINGAN PERIODE", "PERIOD COMPARISON"),
                "title": L("Perbandingan Antar Paruh Periode", "Period-over-Period Comparison"),
                "categories": compare_data["categories"],
                "series_a": compare_data["series_a"], "series_b": compare_data["series_b"],
                "label_a": L("Paruh Awal", "First Half"), "label_b": L("Paruh Akhir", "Second Half"),
                "caption": None,
            })

    # ---- Pola Kejadian per Hari/Jam (heatmap) — HANYA kalau kolom tanggal genuinely
    # terdeteksi & datanya cukup padat (min. 20 baris bertanggal valid, lihat
    # _compute_day_hour_pattern). Bentuk visual dipilih sesuai KARAKTER data (pola per
    # hari/jam -> heatmap grid), bukan bar/ranking yang sudah dipakai di tile lain.
    heatmap_data = _compute_day_hour_pattern(parsed_data, date_col)
    if heatmap_data and is_included("time_heatmap"):
        visual_tiles.append({
            "tile_kind": "time_heatmap",
            "kicker": L("POLA WAKTU", "TIME PATTERN"),
            "title": L("Pola Kejadian per Hari & Jam", "Event Pattern by Day & Hour"),
            "day_labels": [L(id_, en_) for id_, en_ in heatmap_data["day_labels"]],
            "hour_labels": heatmap_data["hour_labels"],
            "grid": heatmap_data["grid"],
            "caption": None,
        })

    # ---- Tren & Pola — chart SUNGGUHAN (bar+line utk deret waktu, atau bar ranking kalau
    # tidak ada data tanggal) ----
    _time_series = report_stats.get("time_series") or {}
    trend_chart = None
    if len(_time_series.get("counts") or []) >= 3:
        trend_chart = {
            "type": "bar_line",
            "categories": _time_series["labels"][-8:],
            "values": _time_series["counts"][-8:],
            "cumulative": (_time_series.get("cumulative") or [])[-8:],
        }
    elif category_pick:
        _items = category_pick[1][:6]
        trend_chart = {"type": "bar", "categories": [i["value"] for i in _items], "values": [i["count"] for i in _items]}
    trend_narrative = ai_summary.get("trend_analysis") or ai_summary.get("executive_summary")
    # Tile ini di-SKIP kalau tidak ada chart SAMA SEKALI — beda dari sebelumnya (yang tetap
    # tampil kalau ada trend_items/narasi walau tanpa chart), krn kartu naratif tanpa chart
    # kurang cocok jadi tile dashboard (identitas tumpukan "visual", bukan tumpukan teks).
    if trend_chart and is_included("trend_analysis"):
        visual_tiles.append({
            "tile_kind": "trend_chart",
            "kicker": L("TREN & POLA", "TRENDS & PATTERNS"),
            "title": L("Analisis Tren Periode Ini", "Trend Analysis This Period"),
            "chart": trend_chart,
            "caption": _shorten_to_caption(sanitize_text(coerce_narrative_text(trend_narrative)), max_sentences=1) if trend_narrative else None,
        })

    # PERMINTAAN USER: section custom AI ("Insight Tambahan") sebelumnya SELALU jadi kartu
    # teks, padahal Management Report harusnya "lebih banyak visualisasi". Sekarang: kalau
    # section-nya menyertakan data perbandingan kategori (field opsional "chart" dari AI,
    # lihat get_analysis_prompt), diubah jadi TILE chart sungguhan & digabung ke visual_tiles
    # SEBELUM ditumpuk jadi halaman dashboard (baris di bawah) — supaya ikut aturan "maks 6
    # visualisasi per halaman" & bentuknya bervariasi (gantian bar/donat/susun), bukan halaman
    # teks terpisah. Section TANPA data kategori (chart:null, murni narasi kualitatif) tetap
    # jadi kartu teks di management_ai_narrative (lihat di bawah, setelah action items).
    _custom_chart_styles = ["bar", "donut", "stacked"]
    _custom_chart_idx = 0
    dynamic_sections_all = [s for s in (ai_summary.get("sections") or []) if isinstance(s, dict)]
    narrative_items = []
    for sec in dynamic_sections_all[1:]:
        sec_title = sanitize_text(coerce_narrative_text(sec.get("title")))
        sec_content = sanitize_text(coerce_narrative_text(sec.get("content")))
        if not sec_title or not sec_content:
            continue
        chart_data = sec.get("chart") if isinstance(sec.get("chart"), dict) else None
        labels = chart_data.get("labels") if chart_data else None
        values = chart_data.get("values") if chart_data else None
        has_valid_chart = (
            isinstance(labels, list) and isinstance(values, list)
            and len(labels) >= 2 and len(labels) == len(values)
            and all(isinstance(v, (int, float)) for v in values)
        )
        if has_valid_chart:
            style = _custom_chart_styles[_custom_chart_idx % len(_custom_chart_styles)]
            _custom_chart_idx += 1
            visual_tiles.append({
                "tile_kind": "custom_topic",
                "chart_style": style,
                "kicker": L("INSIGHT AI", "AI INSIGHT"),
                "title": sec_title,
                "labels": [sanitize_text(str(lbl)) for lbl in labels[:6]],
                "values": [float(v) for v in values[:6]],
                "caption": _shorten_to_caption(sec_content, max_sentences=1),
            })
        else:
            narrative_items.append({"title": sec_title, "content": _shorten_to_caption(sec_content, max_sentences=3)})

    # Tumpuk SEMUA tile visual yang tersedia jadi 1 halaman dashboard (bisa 4/5/lebih
    # sekaligus, macam-macam jenis chart, keterangan tiap tile cuma 1 kalimat) — kalau
    # jumlahnya lebih dari 6 (bisa terjadi sekarang krn tile custom topic bisa nambah banyak),
    # dipecah jadi beberapa halaman dashboard supaya tetap terbaca (tidak dipaksa 1 halaman
    # kalau sudah kepenuhan).
    for i in range(0, len(visual_tiles), 6):
        chunk = visual_tiles[i:i + 6]
        blocks.append({
            "kind": "management_visual_dashboard",
            "kicker": L("SOROTAN VISUAL", "VISUAL HIGHLIGHTS"),
            "title": L("Sorotan Data & Pola", "Data & Pattern Highlights") if i == 0 else L("Sorotan Data & Pola (Lanjutan)", "Data & Pattern Highlights (Continued)"),
            "tiles": chunk,
        })

    # ---- Temuan Utama (setara build_report_blocks() — reuse builder PDF/PPT yang sama,
    # dibungkus "page"+panels 1-panel supaya lewat jalur "panel mandiri" apa adanya, lihat
    # _build_page_block/_build_page_slide) ----
    if key_findings and is_included("key_findings"):
        findings_items = []
        for idx, finding in enumerate(key_findings):
            title_part, _, detail_part = finding.partition(". ")
            if not detail_part:
                title_part, detail_part = finding, ""
            findings_items.append({
                "num": str(idx + 1),
                "title": title_part.strip() or finding,
                "detail": detail_part.strip(),
                "is_critical": bool(open_count and idx == 0),
            })
        blocks.append({
            "kind": "page",
            "dark": False,
            "panels": [{
                "panel_kind": "key_findings",
                "kicker": L("ANALISIS", "ANALYSIS"), "title": L("Temuan Utama", "Key Findings"),
                "items": findings_items, "chart": None,
            }],
        })

    # ---- Tabel Item Prioritas/Kritis (data dihitung persis sama seperti build_report_blocks(),
    # reuse builder PDF/PPT yang sama lewat "page"+panels) ----
    if severity_col and parsed_data and is_included("critical_table"):
        critical_rows = [row for row in parsed_data if _classify_severity_value(str(row.get(severity_col, ""))) == "critical"]
        if len(critical_rows) < 5:
            critical_rows += [row for row in parsed_data if _classify_severity_value(str(row.get(severity_col, ""))) == "high"]
        critical_rows = critical_rows[:12]
        if critical_rows:
            ct_headers = [L("No", "No")]
            if category_pick:
                ct_headers.append(humanize_label(category_pick[0], source_cols))
            ct_headers.append("Severity")
            if status_col:
                ct_headers.append(L("Status", "Status"))
            cat_col_name = source_cols.get(category_pick[0]) if category_pick else None
            ct_rows = []
            ct_highlight_idx = []
            for idx, row in enumerate(critical_rows):
                row_vals = [str(idx + 1)]
                if category_pick:
                    row_vals.append(str(row.get(cat_col_name, "-")) if cat_col_name else "-")
                row_vals.append(_classify_severity_value(str(row.get(severity_col, ""))).capitalize())
                if status_col:
                    status_val = row.get(status_col, "-")
                    row_vals.append(str(status_val))
                    if classify_open_status(status_val) is True:
                        ct_highlight_idx.append(idx)
                ct_rows.append(row_vals)
            blocks.append({
                "kind": "page",
                "dark": False,
                "panels": [{
                    "panel_kind": "critical_table",
                    "kicker": L("SOROTAN INSIDEN", "INCIDENT HIGHLIGHT") if sec_domain else L("SOROTAN DATA", "DATA HIGHLIGHT"),
                    "title": L(f"{len(critical_rows)} Insiden Prioritas Tinggi", f"{len(critical_rows)} High-Priority Incidents") if sec_domain
                    else L(f"{len(critical_rows)} Item Prioritas Tinggi", f"{len(critical_rows)} High-Priority Items"),
                    "headers": ct_headers, "rows": ct_rows, "highlight_idx": ct_highlight_idx, "open_count": open_count,
                    "kicker_is_critical": bool(open_count),
                    "caption": sanitize_text(L(
                        f"Baris merah menandai {open_count} insiden yang masih dalam proses penanganan per akhir periode data.",
                        f"Red rows mark {open_count} incidents still in progress as of the end of the data period.",
                    ) if sec_domain else L(
                        f"Baris merah menandai {open_count} item yang masih dalam proses per akhir periode data.",
                        f"Red rows mark {open_count} items still in progress as of the end of the data period.",
                    )) if open_count else None,
                }],
            })

    # ---- Ranking Entitas/Aset Tersering (versi padat/batang, khas Management Report — TIDAK
    # ikut pengacakan gaya kartu/podium SOC, lihat _build_management_asset_ranking_block/slide) ----
    if asset_pick and is_included("asset_cards"):
        asset_label, asset_pick_items = asset_pick
        bar_items = []
        for idx, item in enumerate(asset_pick_items[:5]):
            bar_items.append({
                "num": str(idx + 1),
                "name": item["value"],
                "count": item["count"],
                "stat": L(f"{item['count']} event", f"{item['count']} events") if sec_domain
                else L(f"{item['count']} data", f"{item['count']} entries"),
            })
        blocks.append({
            "kind": "management_asset_ranking",
            "kicker": L("SOROTAN INSIDEN", "INCIDENT HIGHLIGHT") if sec_domain else L("SOROTAN DATA", "DATA HIGHLIGHT"),
            "title": L(
                f"{humanize_label(asset_label, source_cols)} yang Paling Sering Menjadi Sasaran",
                f"Most Frequently Affected {humanize_label(asset_label, source_cols)}",
            ) if sec_domain else L(
                f"{humanize_label(asset_label, source_cols)} Paling Sering Muncul",
                f"Most Frequent {humanize_label(asset_label, source_cols)}",
            ),
            "items": bar_items,
        })

    # ---- Insight/Narasi Bebas AI TANPA data kategori (dihitung di atas, sebelum tile
    # dashboard — lihat narrative_items/_custom_chart_styles) — TIDAK dikontrol checkbox
    # "Include Sections", otomatis muncul kalau AI menulis narasi tambahan di luar section
    # baku; dirender sbg grid kartu, lihat _build_management_ai_narrative_block/slide) ----
    mgmt_narrative_per_page = 4
    for chunk_index in range(0, len(narrative_items), mgmt_narrative_per_page):
        chunk = narrative_items[chunk_index:chunk_index + mgmt_narrative_per_page]
        continuation = chunk_index > 0
        blocks.append({
            "kind": "management_ai_narrative",
            "kicker": L("ANALISIS", "ANALYSIS"),
            "title": L("Insight Tambahan" if not continuation else "Insight Tambahan (Lanjutan)", "Additional Insights" if not continuation else "Additional Insights (Continued)"),
            "items": chunk,
        })

    # ---- Action Items / Rekomendasi dengan Urgensi ----
    action_items = []
    urgency_map = ["critical", "high", "medium", "low"]
    for idx, rec in enumerate(recommendations if is_included("recommendations") else []):
        raw_title = rec.get("title")
        raw_detail = rec.get("detail") or ""
        # BUG DIPERBAIKI: sebelumnya `detail` SELALU diisi teks penuh `raw_detail` apa
        # adanya, terlepas apakah `title` di atas sudah "mencuri" kalimat pertamanya lewat
        # partition(". ") — hasilnya judul & detail tampil dgn isi yang SAMA PERSIS berulang
        # di kartu. Sekarang detail = SISA kalimat setelah judul diambil (partition
        # mengembalikan bagian sebelum & sesudah pemisah), kosong kalau tidak ada sisa.
        if raw_title:
            title = sanitize_text(raw_title)
            detail = sanitize_text(raw_detail) if raw_detail else None
        else:
            title_part, _, rest = raw_detail.partition(". ")
            title = sanitize_text(title_part or raw_detail)
            detail = sanitize_text(rest.strip()) if rest.strip() else None
        if detail:
            detail = _shorten_to_caption(detail, max_sentences=1)
        urgency = urgency_map[min(idx, len(urgency_map) - 1)]
        action_items.append({
            "number": idx + 1,
            "title": title,
            "detail": detail,
            "urgency": urgency,
        })
    # Halaman ini di-SKIP kalau AI tidak menulis rekomendasi sama sekali (bukan dipaksa
    # tampil kosong) — jumlah/kehadiran halaman FLEKSIBEL mengikuti data yang tersedia.
    for chunk_index in range(0, len(action_items), 6):
        chunk = action_items[chunk_index:chunk_index + 6]
        if chunk:
            continuation = chunk_index > 0
            blocks.append({
                "kind": "management_action_items",
                "kicker": L("TINDAK LANJUT", "ACTION ITEMS"),
                "title": L("Rekomendasi Prioritas" if not continuation else "Rekomendasi Prioritas (Lanjutan)", "Priority Recommendations" if not continuation else "Priority Recommendations (Continued)"),
                "items": chunk,
            })

    # ---- Kesimpulan (reuse builder yang sama dgn gaya SOC lewat "page"+panels — SEBELUMNYA
    # centang "Conclusion" tidak tersambung apa pun di Management Report, lihat komentar
    # is_included() di atas) ----
    if is_included("conclusion") and ai_summary.get("conclusion"):
        mgmt_conclusion_text = sanitize_text(coerce_narrative_text(ai_summary.get("conclusion")))
        if mgmt_conclusion_text:
            mgmt_pills = []
            if total_sev and status_col:
                mgmt_resolved_pct = round((total_sev - open_count) / total_sev * 100, 1)
                mgmt_pills.append(L(
                    f"{mgmt_resolved_pct}% event tertangani" if sec_domain else f"{mgmt_resolved_pct}% data tertangani",
                    f"{mgmt_resolved_pct}% of events resolved",
                ))
            if category_pick:
                mgmt_pills.append(L(
                    f"{category_pick[1][0]['value']} jadi prioritas perhatian",
                    f"{category_pick[1][0]['value']} is the top priority",
                ))
            if open_count:
                mgmt_pills.append(L(
                    f"{open_count} insiden masih berjalan" if sec_domain else f"{open_count} item masih berjalan",
                    f"{open_count} incidents still in progress" if sec_domain else f"{open_count} items still in progress",
                ))
            mgmt_recommendations_shown = bool(is_included("recommendations") and recommendations)
            mgmt_priority_items = []
            if not mgmt_recommendations_shown:
                for idx, rec in enumerate(recommendations):
                    letter = chr(ord("a") + idx) if idx < 26 else str(idx + 1)
                    rec_title = rec.get("title") or (rec.get("detail") or "").partition(". ")[0] or rec.get("detail") or ""
                    mgmt_priority_items.append({"letter": letter, "text": sanitize_text(rec_title)})
            blocks.append({
                "kind": "page",
                "dark": True,
                "panels": [{
                    "panel_kind": "conclusion",
                    "kicker": L("RINGKASAN AKHIR", "FINAL SUMMARY"), "title": L("Kesimpulan", "Conclusion"),
                    "text": _shorten_to_caption(mgmt_conclusion_text, max_sentences=3), "pills": mgmt_pills,
                    "priority_panel_title": L("Prioritas Berikutnya", "Next Priorities"),
                    "priority_items": mgmt_priority_items,
                }],
            })

    # ---- Closing ----
    blocks.append({
        "kind": "closing",
        "dark": True,
        "title": report.title,
        "thank_you": L("Terima Kasih", "Thank You"),
        "note": L("Laporan ini disiapkan untuk keperluan manajemen.", "This report is prepared for management use."),
        "hero_stat": (str(total_records), L("Total Data", "Total Records")),
        "header_title": (report.header_title or "PT PETROKIMIA GRESIK").upper(),
    })

    return blocks
