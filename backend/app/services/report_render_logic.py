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

from app.crud.report import get_parsed_data
from app.services.ai_engine.data_profiler import compute_statistics, _classify_severity_value
from app.services.ai_engine.ollama_client import normalize_recommendations, sanitize_text, coerce_finding_text

SEVERITY_ORDER = ["critical", "high", "medium", "low", "informational"]
SEVERITY_LABEL = {
    "critical": "Critical", "high": "High", "medium": "Medium",
    "low": "Low", "informational": "Info",
}


def is_english(report) -> bool:
    return bool(getattr(report, "language", None)) and report.language.strip().lower() == "english"


def _L(report, id_text: str, en_text: str) -> str:
    """Pilih teks Indonesia atau Inggris sesuai report.language."""
    return en_text if is_english(report) else id_text


# Domain NON-keamanan yang punya nilai data_type tetap (lihat domainToDataType di
# generate/page.tsx & _DOMAIN_TITLE_LABELS di upload.py) — di luar ini (firewall,
# email_security, ids_ips, vapt, atau apapun yang tidak dikenal) DIANGGAP domain keamanan,
# mempertahankan SELURUH kosakata SOC/insiden yang sudah ada sebagai perilaku default/lama.
_NON_SECURITY_DATA_TYPES = {"keuangan", "financial", "kpi_hr", "operasional", "general", "procurement"}

_DATA_TYPE_DISPLAY_LABELS = {
    "keuangan": "Keuangan",
    "financial": "Financial",
    "kpi_hr": "KPI & HR",
    "operasional": "Operasional",
    "general": "Umum",
    "procurement": "Pengadaan Barang & Jasa",
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
    return _DATA_TYPE_DISPLAY_LABELS.get(dt) or dt.replace("_", " ").title() or "-"


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
    isinya & belum dipakai slide/halaman lain — else None (bagian terkait di-skip aman)."""
    for label in preferred:
        items = top_categories.get(label)
        if items and label not in used:
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


def build_key_findings(ai_summary: dict, report_stats: dict, open_count: int, sanitize_text, report=None) -> list:
    """`sanitize_text` diterima sebagai parameter (bukan import langsung) supaya modul ini
    tidak perlu bergantung pada ollama_client — pemanggil (export_ppt.py/export_pdf.py) sudah
    mengimpornya untuk keperluan lain juga."""
    findings = [
        sanitize_text(coerce_finding_text(f))
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

    def _get_chart_caption(kind: str):
        if isinstance(_raw_chart_captions, dict):
            val = _raw_chart_captions.get(kind)
            return sanitize_text(val) if val else None
        if isinstance(_raw_chart_captions, list):
            captions = [sanitize_text(c) for c in _raw_chart_captions if c]
            idx = _chart_caption_state["i"]
            _chart_caption_state["i"] += 1
            return captions[idx] if idx < len(captions) else None
        return None

    blocks: list[dict] = []
    sec_domain = is_security_domain(report)

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
            _L(report, "Security Operation Center", "Security Operation Center") if sec_domain
            else humanize_data_type(report)
        ),
        "period_text": period_text,
        "period_label": _L(report, "Periode data.", "Data period."),
        "total_records": total_records,
        "category_count": cat_count,
        "critical_count": crit_count,
        "info_line": info_line,
        "header_title": (report.header_title or "PT PETROKIMIA GRESIK").upper(),
    })

    # ---------------- Latar Belakang & Tujuan ----------------
    if sec_domain:
        purpose_text = sanitize_text(_L(
            report,
            f"Sepanjang periode {period_text}, sistem keamanan siber mencatat {total_records} event "
            f"yang dianalisis pada laporan ini. Data log dianalisis untuk memetakan pola kejadian, "
            f"menilai efektivitas penanganan, dan menjadi dasar rekomendasi perbaikan.",
            f"Throughout the period {period_text}, the monitoring system recorded {total_records} events "
            f"analyzed in this report. Log data was analyzed to map event patterns, assess response "
            f"effectiveness, and form the basis for improvement recommendations.",
        ))
    else:
        purpose_text = sanitize_text(_L(
            report,
            f"Sepanjang periode {period_text}, sistem mencatat {total_records} data "
            f"yang dianalisis pada laporan ini. Data dianalisis untuk memetakan pola, "
            f"mengevaluasi capaian kinerja, dan menjadi dasar rekomendasi perbaikan.",
            f"Throughout the period {period_text}, the system recorded {total_records} records "
            f"analyzed in this report. Data was analyzed to map patterns, evaluate performance "
            f"achievements, and form the basis for improvement recommendations.",
        ))
    blocks.append({
        "kind": "intro",
        "dark": False,
        "kicker": _L(report, "PENDAHULUAN", "INTRODUCTION"),
        "title": _L(report, "Latar Belakang dan Tujuan Analisis", "Background and Objectives"),
        "purpose_text": purpose_text,
        "objectives": [
            {
                "num": "1",
                "title": _L(report, "Memetakan Pola Data", "Mapping Data Patterns") if not sec_domain else _L(report, "Memetakan Pola Kejadian", "Mapping Event Patterns"),
                "detail": _L(
                    report,
                    "Mengidentifikasi kategori, tren waktu, dan entitas yang paling sering muncul.",
                    "Identifying categories, time trends, and the most frequently occurring entities.",
                ) if not sec_domain else _L(
                    report,
                    "Mengidentifikasi kategori, tren waktu, dan aset yang paling sering menjadi sasaran.",
                    "Identifying categories, time trends, and the most frequently affected assets.",
                ),
            },
            {
                "num": "2",
                "title": _L(report, "Menilai Efektivitas Capaian", "Assessing Performance Effectiveness") if not sec_domain else _L(report, "Menilai Efektivitas Respons", "Assessing Response Effectiveness"),
                "detail": _L(report, "Mengevaluasi capaian dan tren kinerja utama.", "Evaluating key performance achievements and trends.") if not sec_domain
                else _L(report, "Mengevaluasi status penanganan tiap insiden.", "Evaluating the handling status of each incident."),
            },
            {
                "num": "3",
                "title": _L(report, "Menyusun Rekomendasi", "Formulating Recommendations"),
                "detail": _L(
                    report,
                    "Merumuskan langkah perbaikan prioritas berbasis temuan data aktual.",
                    "Formulating priority improvement steps based on actual data findings.",
                ) if not sec_domain else _L(
                    report,
                    "Merumuskan langkah mitigasi prioritas berbasis temuan data aktual.",
                    "Formulating priority mitigation steps based on actual data findings.",
                ),
            },
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
            "input_file_name": report.input_file_name or "-",
            "data_type_label_label": _L(report, "Jenis Data", "Data Type"),
            "data_type_label": humanize_data_type(report),
            "footnote": _L(
                report,
                "Sumber. Data yang diunggah pengguna, diproses otomatis oleh sistem.",
                "Source. Data uploaded by the user, processed automatically by the system.",
            ),
        },
    })

    # ---------------- Ringkasan Eksekutif ----------------
    if is_included("executive_summary"):
        stat_items = [(str(total_records), _L(report, "Total Event Log", "Total Log Events") if sec_domain else _L(report, "Total Data", "Total Records"))]
        if total_sev:
            if severity.get("critical"):
                stat_items.append((str(severity["critical"]), _L(report, "Insiden Critical", "Critical Incidents")))
            if severity.get("high"):
                stat_items.append((str(severity["high"]), _L(report, "High Severity", "High Severity")))
        if status_col:
            closed = sum(1 for row in parsed_data if classify_open_status(row.get(status_col)) is False)
            if closed:
                stat_items.append((str(closed), _L(report, "Sudah Ditangani", "Already Handled")))
            stat_items.append((str(open_count), _L(report, "Masih Terbuka", "Still Open")))
        if category_pick:
            stat_items.append((str(len(top_categories)), _L(report, "Kategori Sumber", "Source Categories")))
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
            if not is_english(report):
                formatted = formatted.replace(",", ".")
            col_label = humanize_label(col, source_cols)
            stat_items.append((formatted, _L(report, f"Rata-rata {col_label}", f"Average {col_label}")))
        stat_items = stat_items[:6]

        caption = sanitize_text(ai_summary.get("executive_summary") or (key_findings[0] if key_findings else ""))
        blocks.append({
            "kind": "executive_summary",
            "dark": True,
            "title": _L(report, "Ringkasan Eksekutif", "Executive Summary"),
            "heading": _L(report, f"Snapshot Log Keamanan, {period_text}", f"Log Snapshot, {period_text}") if sec_domain
            else _L(report, f"Snapshot Data, {period_text}", f"Data Snapshot, {period_text}"),
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
    numeric_summary_items = list((report_stats.get("numeric_summary") or {}).items())
    aux_stat_value = None
    if total_sev:
        aux_stat_value = (
            f"{round(severity.get('critical', 0) / total_sev * 100, 1)}%",
            _L(report, "Proporsi Critical", "Critical Share") if sec_domain else _L(report, "Proporsi Tertinggi", "Highest Share"),
        )
    elif category_pick:
        top_item = category_pick[1][0]
        aux_stat_value = (str(top_item["count"]), humanize_label(category_pick[0], source_cols))
    elif numeric_summary_items:
        col, nstats = numeric_summary_items[0]
        avg_val = nstats.get("mean")
        formatted = f"{avg_val:,.0f}" if avg_val is not None else "-"
        if not is_english(report):
            formatted = formatted.replace(",", ".")
        aux_stat_value = (formatted, _L(report, f"Rata-rata {humanize_label(col, source_cols)}", f"Average {humanize_label(col, source_cols)}"))
    else:
        aux_stat_value = (str(total_records), _L(report, "Total Data", "Total Records"))

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
            "ai_caption": _get_chart_caption("category"),
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
            "ai_caption": _get_chart_caption("severity"),
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
            "ai_caption": _get_chart_caption("status"),
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
    blocks.append({
        "kind": "closing",
        "dark": True,
        "title": report.title,
        "thank_you": _L(report, "Terima Kasih", "Thank You"),
        "note": _L(report, "Diskusi dan pertanyaan dipersilakan.", "Questions and discussion are welcome."),
    })

    return blocks
