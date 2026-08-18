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

from app.crud.report import get_parsed_data
from app.services.ai_engine.data_profiler import compute_statistics, _classify_severity_value
from app.services.ai_engine.ollama_client import normalize_recommendations, sanitize_text, coerce_finding_text

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


# Dipakai laporan LAMA (dibuat sebelum kolom report.visual_style ada, jadi NULL) — satu set
# tetap yang cocok dgn styling default sebelumnya (cover split, chart bar, kartu grid biasa),
# supaya laporan lama tidak pernah error/berubah tampilan sendiri gara-gara migrasi ini.
DEFAULT_VISUAL_STYLE = {
    "cover_style": "split",
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
        "cover_style": "split",
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
        "cover_style": "split",
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
            "cover_style": rnd.choice(["solid", "split"]),
            "category_style": rnd.choice(["bar", "donut", "stacked"]),
            "status_style": rnd.choice(["bar", "donut", "stacked"]),
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
            return sanitize_text(val) if val else fallback
        if isinstance(_raw_chart_captions, list):
            captions = [sanitize_text(c) for c in _raw_chart_captions if c]
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

    blocks: list[dict] = []
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
    blocks.append({
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
    })

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

    blocks.append({
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
    })

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

        caption = sanitize_text(ai_summary.get("executive_summary") or (key_findings[0] if key_findings else ""))
        blocks.append({
            "kind": "executive_summary",
            "dark": True,
            "title": _L(report, "Ringkasan Eksekutif", "Executive Summary"),
            "heading": heading,
            "stat_items": stat_items,
            "caption": caption,
        })

    # ---------------- Section Dinamis dari AI (opsional) ----------------
    # Section tambahan yang AI tulis berdasarkan domain data & dipilih user di Settings
    # (ai_summary["sections"], lihat get_analysis_prompt/selected_sections) — SEBELUMNYA
    # dihasilkan AI (menghabiskan waktu generate) tapi tidak pernah ditampilkan di
    # PDF/PPT/Preview sama sekali, walau user sudah memilihnya secara eksplisit di Settings.
    # Disisipkan di sini (setelah Ringkasan Eksekutif, sebelum chart analisis) supaya urutan
    # bacanya wajar: ringkasan besar dulu, baru pembahasan topik spesifik yang dipilih user.
    #
    # Section PERTAMA (order 0) DILEWATI di sini — section_suggester.py/prompts.py SECARA
    # DESAIN selalu mengharuskan order 0 berisi "ringkasan eksekutif tingkat tinggi", yang
    # SUDAH ditampilkan di slide Ringkasan Eksekutif (kartu KPI) lewat caption di atas.
    # Merender ulang jadi slide narasi terpisah menghasilkan 2 slide dengan isi yang
    # tumpang-tindih/nyaris sama (bug ditemukan user) — bukan dihapus dari data, cuma tidak
    # dirender dua kali. Section lain (order 1 dst) tetap tampil normal seperti biasa.
    # Data pendukung supaya slide narasi TIDAK cuma "judul + 1 paragraf" di kotak kosong
    # (temuan user: boros ruang kosong, semua slide identik) — setiap section dilengkapi 1
    # potongan angka/daftar kecil dari STATISTIK PYTHON (bukan karangan AI), berselang-seling
    # 2 pola tata letak (panel angka besar vs daftar ringkas) supaya tidak monoton.
    # aux_stat_value = hero_stat yang sama dipakai cover (dihitung sekali di atas, lihat
    # catatan panjang di sana) — supaya angka headline konsisten di seluruh laporan.
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

    # ---------------- Trend Analysis / Severity Analysis / Risk Assessment ----------------
    # 3 dari 6 field WAJIB yang AI SELALU tulis & bisa diedit user di tab Edit Text (lihat
    # reportSections.ts, urutan page 02/03/04 persis di bawah ini) — SEBELUMNYA tidak pernah
    # dibaca sama sekali di sini, jadi hasil generate maupun edit user untuk ketiganya hilang
    # tanpa jejak begitu di-export ke PDF/PPT (bug ditemukan lewat audit). Ditempatkan tepat
    # setelah Ringkasan Eksekutif, SEBELUM section dinamis AI & chart detail — bacanya jadi
    # wajar: ringkasan besar dulu, baru narasi lebih spesifik, baru breakdown per-chart.
    # Judul "Severity Analysis" DIHINDARI untuk domain non-keamanan (sama seperti bagian lain
    # di file ini) karena isinya genuinely membahas distribusi/prioritas data, bukan cuma
    # istilah keamanan siber — konten AI-nya sendiri sudah domain-neutral (lihat SYSTEM_PROMPT),
    # cuma LABEL slide-nya yang perlu ikut netral.
    if is_included("trend_analysis") and ai_summary.get("trend_analysis"):
        blocks.append({
            "kind": "dynamic_section",
            "dark": False,
            "kicker": _L(report, "ANALISIS", "ANALYSIS"),
            "title": _L(report, "Analisis Tren", "Trend Analysis"),
            "text": sanitize_text(ai_summary.get("trend_analysis")),
            "layout_variant": "stat",
            "aux_stat": aux_stat_value,
            "aux_list": None,
        })

    if is_included("severity_analysis") and ai_summary.get("severity_analysis"):
        blocks.append({
            "kind": "dynamic_section",
            "dark": False,
            "kicker": _L(report, "ANALISIS", "ANALYSIS"),
            "title": _L(report, "Analisis Tingkat Keparahan", "Severity Analysis") if sec_domain
            else _L(report, "Analisis Distribusi & Prioritas", "Distribution & Priority Analysis"),
            "text": sanitize_text(ai_summary.get("severity_analysis")),
            "layout_variant": "list" if aux_list_items else "stat",
            "aux_stat": None if aux_list_items else aux_stat_value,
            "aux_list": aux_list_items,
        })

    if is_included("risk_assessment") and ai_summary.get("risk_assessment"):
        blocks.append({
            "kind": "dynamic_section",
            "dark": False,
            "kicker": _L(report, "ANALISIS", "ANALYSIS"),
            "title": _L(report, "Penilaian Risiko", "Risk Assessment"),
            "text": sanitize_text(ai_summary.get("risk_assessment")),
            "layout_variant": "stat",
            "aux_stat": aux_stat_value,
            "aux_list": None,
        })

    dynamic_sections = [s for s in (ai_summary.get("sections") or []) if isinstance(s, dict)]
    for idx, sec in enumerate(dynamic_sections[1:]):
        sec_title = sanitize_text(sec.get("title") or "")
        sec_content = sanitize_text(sec.get("content") or "")
        if not sec_title or not sec_content:
            continue
        # Berselang-seling: index genap -> panel angka besar, index ganjil -> daftar ringkas
        # (kalau salah satu data tidak tersedia, fallback ke yang tersedia daripada kosong).
        use_list = (idx % 2 == 1) and bool(aux_list_items)
        blocks.append({
            "kind": "dynamic_section",
            "dark": False,
            "kicker": _L(report, "ANALISIS", "ANALYSIS"),
            "title": sec_title,
            "text": sec_content,
            "layout_variant": "list" if use_list else "stat",
            "aux_stat": None if use_list else aux_stat_value,
            "aux_list": aux_list_items if use_list else None,
        })

    # ---------------- Distribusi Kategori Event ----------------
    if category_pick:
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
            {"color_index": i % 5, "name": it["value"], "pct": round(it["count"] / cat_total * 100, 1)}
            for i, it in enumerate(top_items)
        ]
        blocks.append({
            "kind": "category_distribution",
            "dark": False,
            "kicker": _L(report, "ANALISIS DATA", "DATA ANALYSIS"),
            "label": humanize_label(label, source_cols),
            "raw_label": label,
            "title": _L(report, f"Distribusi Event Berdasarkan {humanize_label(label, source_cols)}", f"Event Distribution by {humanize_label(label, source_cols)}") if sec_domain
            else _L(report, f"Distribusi Data Berdasarkan {humanize_label(label, source_cols)}", f"Data Distribution by {humanize_label(label, source_cols)}"),
            "categories": [i["value"] for i in top_items],
            "values": [i["count"] for i in top_items],
            "legend": legend,
            "legend_panel_title": _L(report, "Proporsi Kategori", "Category Proportion"),
            "intro": intro,
            "footnote": sanitize_text(_L(
                report,
                f"{top_items[0]['value']} menjadi kontributor volume terbesar pada kategori ini.",
                f"{top_items[0]['value']} is the largest volume contributor in this category.",
            )),
            "ai_caption": _get_chart_caption("category", fallback=sanitize_text(_L(
                report,
                f"{top_items[0]['value']} mencatat volume tertinggi dengan {top_items[0]['count']} dari {cat_total} data "
                f"({round(top_items[0]['count']/cat_total*100,1)}%). Konsentrasi pada kategori ini bisa jadi dasar "
                f"evaluasi kebijakan atau alokasi sumber daya operasional ke depan.",
                f"{top_items[0]['value']} recorded the highest volume with {top_items[0]['count']} of {cat_total} records "
                f"({round(top_items[0]['count']/cat_total*100,1)}%). This concentration can guide policy evaluation or "
                f"operational resource allocation going forward.",
            ))),
        })

    # ---------------- Distribusi Severity ----------------
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
        blocks.append({
            "kind": "severity_distribution",
            "dark": False,
            "kicker": _L(report, "ANALISIS DATA", "DATA ANALYSIS"),
            "title": _L(report, "Distribusi Tingkat Keparahan (Severity)", "Severity Distribution"),
            "categories": [SEVERITY_LABEL[k] for k in SEVERITY_ORDER],
            "values": [severity.get(k, 0) for k in SEVERITY_ORDER],
            "severity_keys": list(SEVERITY_ORDER),
            "intro": intro,
            "crit_pct": crit_pct,
            "panel_text": _L(report, "dari seluruh event berstatus Critical Severity", "of all events at Critical severity"),
            "detail_text": detail_text,
            "ai_caption": _get_chart_caption("severity", fallback=sanitize_text(_L(
                report,
                f"Critical mencapai {crit_pct}% dan High {high_pct}% dari seluruh {total_sev} event. "
                f"Gabungan proporsi setinggi ini perlu diprioritaskan penanganannya agar tidak berdampak lebih luas ke operasional.",
                f"Critical accounts for {crit_pct}% and High {high_pct}% of all {total_sev} events. "
                f"This combined high proportion should be prioritized to avoid broader operational impact.",
            ))),
        })

    # ---------------- Status Penanganan Insiden ----------------
    if status_items:
        status_total = sum(i["count"] for i in status_items) or 1
        top_status = status_items[0]
        intro = sanitize_text(_L(
            report,
            f"{round(top_status['count']/status_total*100,1)}% event berstatus {top_status['value']}. "
            f"Sebagian kecil masih memerlukan tindak lanjut aktif.",
            f"{round(top_status['count']/status_total*100,1)}% of events are in {top_status['value']} status. "
            f"A small portion still requires active follow-up.",
        ))
        top_status_items = status_items[:8]
        blocks.append({
            "kind": "status_distribution",
            "dark": False,
            "kicker": _L(report, "ANALISIS DATA", "DATA ANALYSIS"),
            "title": _L(report, "Status Penanganan Insiden", "Incident Handling Status"),
            "categories": [i["value"] for i in top_status_items],
            "values": [i["count"] for i in top_status_items],
            "intro": intro,
            "ai_caption": _get_chart_caption("status", fallback=sanitize_text(_L(
                report,
                f"{round(top_status['count']/status_total*100,1)}% dari {status_total} event berstatus {top_status['value']}. "
                f"Sisanya tersebar di status lain yang perlu terus dipantau agar tidak menumpuk jadi backlog.",
                f"{round(top_status['count']/status_total*100,1)}% of {status_total} events are in {top_status['value']} status. "
                f"The remainder is spread across other statuses that need ongoing monitoring to avoid becoming a backlog.",
            ))),
        })

    # ---------------- Tabel Insiden Critical/Prioritas Tinggi ----------------
    if severity_col and parsed_data:
        critical_rows = [row for row in parsed_data if _classify_severity_value(str(row.get(severity_col, ""))) == "critical"]
        if len(critical_rows) < 5:
            critical_rows += [row for row in parsed_data if _classify_severity_value(str(row.get(severity_col, ""))) == "high"]
        critical_rows = critical_rows[:12]

        if critical_rows:
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

            blocks.append({
                "kind": "critical_table",
                "dark": False,
                "kicker": _L(report, "SOROTAN INSIDEN", "INCIDENT HIGHLIGHT") if sec_domain else _L(report, "SOROTAN DATA", "DATA HIGHLIGHT"),
                "title": _L(report, f"{len(critical_rows)} Insiden Prioritas Tinggi", f"{len(critical_rows)} High-Priority Incidents") if sec_domain
                else _L(report, f"{len(critical_rows)} Item Prioritas Tinggi", f"{len(critical_rows)} High-Priority Items"),
                "headers": headers,
                "rows": rows_out,
                "highlight_idx": highlight_idx,
                "open_count": open_count,
                "kicker_is_critical": bool(open_count),
                "caption": sanitize_text(_L(
                    report,
                    f"Baris merah menandai {open_count} insiden yang masih dalam proses penanganan per akhir periode data.",
                    f"Red rows mark {open_count} incidents still in progress as of the end of the data period.",
                ) if sec_domain else _L(
                    report,
                    f"Baris merah menandai {open_count} item yang masih dalam proses per akhir periode data.",
                    f"Red rows mark {open_count} items still in progress as of the end of the data period.",
                )) if open_count else None,
            })

    # ---------------- Aset Paling Sering Menjadi Sasaran ----------------
    if asset_pick:
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
        blocks.append({
            "kind": "asset_cards",
            "dark": True,
            "kicker": _L(report, "SOROTAN INSIDEN", "INCIDENT HIGHLIGHT") if sec_domain else _L(report, "SOROTAN DATA", "DATA HIGHLIGHT"),
            "label": humanize_label(label, source_cols),
            "title": _L(
                report,
                f"{humanize_label(label, source_cols)} yang Paling Sering Menjadi Sasaran",
                f"Most Frequently Affected {humanize_label(label, source_cols)}",
            ) if sec_domain else _L(
                report,
                f"{humanize_label(label, source_cols)} Paling Sering Muncul",
                f"Most Frequent {humanize_label(label, source_cols)}",
            ),
            "items": card_items,
        })

    # ---------------- Temuan Utama ----------------
    if key_findings:
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
            "kind": "key_findings",
            "dark": False,
            "kicker": _L(report, "ANALISIS", "ANALYSIS"),
            "title": _L(report, "Temuan Utama", "Key Findings"),
            "items": findings_items,
        })

    # ---------------- Rekomendasi Mitigasi ----------------
    if is_included("recommendations") and recommendations:
        items = recommendations[:6]
        rec_items = []
        for idx, item in enumerate(items):
            raw_title = item.get("title")
            raw_detail = item.get("detail") or ""
            if raw_title:
                title_txt = raw_title
                detail_txt = raw_detail or None
            else:
                # Tidak ada title terpisah — ambil kalimat pertama sebagai judul lewat batas
                # kalimat alami (". "), BUKAN potongan jumlah karakter tetap. Dulu dipotong
                # paksa di karakter ke-60 tanpa "..." dan SISA TEKSNYA HILANG PERMANEN (tidak
                # pernah ditampilkan di mana pun) — pola yang sama seperti build_key_findings
                # di atas, supaya tidak pernah memutus kata di tengah maupun membuang isi.
                title_txt, _, rest = raw_detail.partition(". ")
                detail_txt = rest.strip() or None
                if not title_txt:
                    title_txt = raw_detail
                elif not detail_txt and len(title_txt) > 70:
                    # BUG NYATA YANG DIPERBAIKI (dilaporkan user): kalau AI menulis SATU
                    # kalimat panjang tanpa kalimat kedua (umum sebelum prompt diperbaiki utk
                    # eksplisit minta {title, detail}), title_txt di atas jadi kalimat PANJANG
                    # itu utuh — kartu tampil sebagai satu paragraf tanpa judul pendek yang bisa
                    # di-scan cepat. Potong ke batas KATA (bukan karakter kasar) jadi judul
                    # singkat, kalimat ASLI UTUH tetap ditampilkan penuh sebagai detail (sedikit
                    # pengulangan di awal detail masih lebih baik daripada kartu tanpa judul).
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
        blocks.append({
            "kind": "recommendations",
            "dark": False,
            "kicker": _L(report, "TINDAK LANJUT", "FOLLOW-UP"),
            "title": _L(report, "Rekomendasi Mitigasi", "Mitigation Recommendations"),
            "items": rec_items,
        })

    # ---------------- Kesimpulan ----------------
    if is_included("conclusion") and ai_summary.get("conclusion"):
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

        priority_items = []
        for idx, rec in enumerate(recommendations[:4]):
            letter = chr(ord("a") + idx)
            # Pakai batas kalimat alami yang sama dengan blok Rekomendasi Mitigasi di atas
            # (BUKAN potongan 70 karakter terpisah) — supaya teks yang sama tidak terpotong
            # di titik yang berbeda-beda tergantung halaman mana yang menampilkannya.
            rec_title = rec.get("title") or (rec.get("detail") or "").partition(". ")[0] or rec.get("detail") or ""
            priority_items.append({"letter": letter, "text": sanitize_text(rec_title)})

        blocks.append({
            "kind": "conclusion",
            "dark": True,
            "kicker": _L(report, "PENUTUP", "CLOSING"),
            "title": _L(report, "Kesimpulan", "Conclusion"),
            "text": sanitize_text(ai_summary.get("conclusion")),
            "pills": pills,
            "priority_panel_title": _L(report, "Prioritas Berikutnya", "Next Priorities"),
            "priority_items": priority_items,
        })

    # ---------------- Penutup ----------------
    # hero_stat/header_title diulang dari cover (variabel yang sama, masih di scope function
    # ini) — dibutuhkan varian cover_style="split" (bookend angka hero yang sama di cover &
    # penutup, gaya laporan eksekutif) baik di exporter PPT/PDF maupun preview React
    # (ClosingBlock, lihat ReportBlockRenderer.tsx) supaya keduanya konsisten.
    blocks.append({
        "kind": "closing",
        "dark": True,
        "title": report.title,
        "thank_you": _L(report, "Terima Kasih", "Thank You"),
        "note": _L(report, "Diskusi dan pertanyaan dipersilakan.", "Questions and discussion are welcome."),
        "hero_stat": hero_stat,
        "header_title": (report.header_title or "PT PETROKIMIA GRESIK").upper(),
    })

    return blocks


# ==============================================================================
# Management Report Template
# Template khusus untuk laporan eksekutif/manajemen — lebih banyak grafis,
# KPI cards, risk heatmap, dan action items daripada narasi panjang.
# Dipakai ketika report.template_type == "Management Report"
# ==============================================================================

def build_management_report_blocks(report) -> list[dict]:
    """
    Blok laporan untuk template Management Report.
    Fokus pada:
    - KPI grid dengan angka kunci (total events, critical, SLA %, resolved %)
    - Risk heatmap summary (severity distribution visual)
    - Trend analisis ringkas
    - Action items dengan prioritas urgensi
    - Minimal teks narasi panjang, maksimal visualisasi
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

    critical_count = report.threat_count_critical or severity.get("critical", 0)
    high_count = report.threat_count_high or severity.get("high", 0)
    medium_count = report.threat_count_medium or severity.get("medium", 0)
    low_count = report.threat_count_low or severity.get("low", 0)
    info_count = report.threat_count_info or severity.get("informational", 0)

    # Hitung SLA met & resolved %
    sla_met = getattr(report, "sla_met", True)
    sla_pct = 100 if sla_met else max(0, 100 - round((getattr(report, "processing_time_sec", 0) or 0) / 3))

    source_cols = report_stats.get("_source_columns") or {}
    status_col = source_cols.get("status")
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

    blocks = []

    # ---- Cover ----
    blocks.append({
        "kind": "cover",
        "title": report.title,
        "subtitle": L("Laporan Eksekutif — Management Report", "Executive Report — Management Report"),
        "date": format_report_date(report.created_at, report.language),
        "period": format_period(report),
        "header_title": (report.header_title or "PT PETROKIMIA GRESIK").upper(),
        "header_subtitle": report.header_subtitle or "Sistem Otomasi Laporan & Eksekutif Presentasi Berbasis AI",
        "cover_style": "split",
        "theme_color": resolve_theme_color(report),
        "is_management": True,
    })

    # ---- KPI Grid — 6 kartu angka kunci ----
    kpi_items = [
        {
            "label": L("Total Events", "Total Events"),
            "value": str(total_records),
            "icon": "shield",
            "color": "blue",
            "delta": None,
        },
        {
            "label": L("Critical Threats", "Critical Threats"),
            "value": str(critical_count),
            "icon": "fire",
            "color": "red",
            "delta": L("Perlu tindakan segera", "Requires immediate action") if critical_count > 0 else L("Aman", "Safe"),
        },
        {
            "label": L("High Severity", "High Severity"),
            "value": str(high_count),
            "icon": "warning",
            "color": "orange",
            "delta": None,
        },
        {
            "label": L("SLA Terpenuhi", "SLA Met"),
            "value": f"{sla_pct}%",
            "icon": "clock",
            "color": "green" if sla_pct >= 80 else "red",
            "delta": L("Target: ≥ 80%", "Target: ≥ 80%"),
        },
        {
            "label": L("Terselesaikan", "Resolved"),
            "value": f"{resolved_pct}%",
            "icon": "check",
            "color": "green" if resolved_pct >= 70 else "amber",
            "delta": f"{resolved_count} / {total_records}",
        },
        {
            "label": L("Insiden Aktif", "Active Incidents"),
            "value": str(open_count),
            "icon": "alert",
            "color": "red" if open_count > 0 else "green",
            "delta": L("Butuh perhatian", "Needs attention") if open_count > 0 else L("Semua tertangani", "All handled"),
        },
    ]
    blocks.append({
        "kind": "management_kpi_grid",
        "kicker": L("RINGKASAN EKSEKUTIF", "EXECUTIVE SUMMARY"),
        "title": L("Indikator Kinerja Utama", "Key Performance Indicators"),
        "items": kpi_items,
    })

    # ---- Risk Heatmap / Severity Distribution ----
    severity_bars = []
    for sev_key in ["critical", "high", "medium", "low", "informational"]:
        count = severity.get(sev_key, 0)
        pct = round(count / max(total_sev, 1) * 100)
        severity_bars.append({
            "label": sev_key.title(),
            "count": count,
            "pct": pct,
            "color": {
                "critical": "red",
                "high": "orange",
                "medium": "amber",
                "low": "blue",
                "informational": "gray",
            }.get(sev_key, "gray"),
        })
    blocks.append({
        "kind": "management_risk_heatmap",
        "kicker": L("DISTRIBUSI RISIKO", "RISK DISTRIBUTION"),
        "title": L("Peta Risiko Keamanan", "Security Risk Heatmap"),
        "severity_bars": severity_bars,
        "total_sev": total_sev,
        "summary_text": sanitize_text(ai_summary.get("threat_analysis") or ai_summary.get("trend_analysis")),
    })

    # ---- Trend Chart Placeholder ----
    trend_items = []
    if top_categories:
        for cat_key, cat_items in list(top_categories.items())[:3]:
            if cat_items:
                trend_items.append({
                    "category": humanize_label(cat_key),
                    "top_values": [str(v[0]) for v in (cat_items if isinstance(cat_items[0], (list, tuple)) else [(x, 0) for x in cat_items])[:5]],
                })
    blocks.append({
        "kind": "management_trend_chart",
        "kicker": L("TREN & POLA", "TRENDS & PATTERNS"),
        "title": L("Analisis Tren Periode Ini", "Trend Analysis This Period"),
        "trend_items": trend_items,
        "narrative": sanitize_text(ai_summary.get("trend_analysis") or ai_summary.get("executive_summary")),
        "chart_data": getattr(report, "chart_data", None),
    })

    # ---- Action Items / Rekomendasi dengan Urgensi ----
    action_items = []
    urgency_map = ["critical", "high", "medium", "low"]
    for idx, rec in enumerate(recommendations[:6]):
        title = sanitize_text(rec.get("title") or (rec.get("detail") or "").partition(". ")[0])
        detail = sanitize_text(rec.get("detail") or "")
        urgency = urgency_map[min(idx, len(urgency_map) - 1)]
        action_items.append({
            "number": idx + 1,
            "title": title,
            "detail": detail,
            "urgency": urgency,
        })
    blocks.append({
        "kind": "management_action_items",
        "kicker": L("TINDAK LANJUT", "ACTION ITEMS"),
        "title": L("Rekomendasi Prioritas", "Priority Recommendations"),
        "items": action_items,
    })

    # ---- Closing ----
    blocks.append({
        "kind": "closing",
        "dark": True,
        "title": report.title,
        "thank_you": L("Terima Kasih", "Thank You"),
        "note": L("Laporan ini disiapkan untuk keperluan manajemen.", "This report is prepared for management use."),
        "hero_stat": str(total_records),
        "header_title": (report.header_title or "PT PETROKIMIA GRESIK").upper(),
    })

    return blocks
