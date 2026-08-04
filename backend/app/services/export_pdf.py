# backend/app/services/export_pdf.py
"""
Rombak total (ganti gaya lama sepenuhnya) — cermin 1:1 dari export_ppt.py, medium HTML/CSS
(A4) menggantikan PPTX. Palet hijau/emas PT Petrokimia Gresik, font Bookman Old Style
(judul) + Calibri (body), TANPA bullet titik (badge lingkaran nomor/huruf), TANPA em dash
(sanitize_text), TANPA garis aksen/bar dekoratif (kecuali ornamen lengkung emas di cover &
penutup). Chart jadi CSS bar (bukan gambar Plotly/Kaleido — chart_generator.py TIDAK dipakai
lagi di sini, angka diambil LANGSUNG dari compute_statistics()).

Struktur & sumber data SAMA PERSIS dengan export_ppt.py: konten narasi HANYA dari 6 key
wajib lama + key_findings opsional (BUKAN ai_summary["sections"]), jumlah & kehadiran
"halaman" fleksibel mengikuti data yang tersedia (skip aman kalau kolom terkait tak
terdeteksi).
"""
import datetime
import html
import io
import os
import random

from app.models.report import Report
from app.crud.report import get_parsed_data
from app.services.ai_engine.data_profiler import compute_statistics, _classify_severity_value
from app.services.ai_engine.ollama_client import normalize_recommendations, sanitize_text

try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError):
    WEASYPRINT_AVAILABLE = False

try:
    from xhtml2pdf import pisa
    XHTML2PDF_AVAILABLE = True
except ImportError:
    XHTML2PDF_AVAILABLE = False

# ============================================================================
# Palet & font — persis sama dgn export_ppt.py
# ============================================================================
GREEN_MAIN = "#1B5E3C"
GREEN_BG = "#0E3B26"
GREEN_CHART = "#2F7A52"
GOLD_MAIN = "#C9A227"
GOLD_LIGHT = "#E7C766"
WHITE = "#FFFFFF"
IVORY = "#F5F7F2"
TEXT_DARK = "#16241C"
GRAY_TEXT = "#5C6B62"
RED_CRIT = "#B23A2E"
RED_CRIT_BG = "#F8E2DE"
PANEL_BORDER = "#E2E5DE"
TITLE_FONT = '"Bookman Old Style", Georgia, serif'
BODY_FONT = 'Calibri, "Segoe UI", sans-serif'

CATEGORY_COLOR_RAMP = [GREEN_MAIN, GREEN_CHART, GOLD_MAIN, GOLD_LIGHT, GRAY_TEXT]
SEVERITY_COLOR = {
    "critical": RED_CRIT, "high": GOLD_MAIN, "medium": GREEN_MAIN,
    "low": GREEN_CHART, "informational": GRAY_TEXT,
}
SEVERITY_ORDER = ["critical", "high", "medium", "low", "informational"]
SEVERITY_LABEL = {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low", "informational": "Info"}


def format_report_date(dt: datetime.datetime, language: str | None) -> str:
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


def _format_period(report: Report) -> str:
    if report.period_start and report.period_end:
        if report.period_start == report.period_end:
            return format_report_date(report.period_end, report.language)
        return f"{format_report_date(report.period_start, report.language)} sampai {format_report_date(report.period_end, report.language)}"
    if report.period_end:
        return format_report_date(report.period_end, report.language)
    if report.period_start:
        return format_report_date(report.period_start, report.language)
    return format_report_date(report.created_at or datetime.datetime.now(), report.language)


def _resolve_logo_b64() -> str | None:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "public"))
    for name in ("LOGO_PETRO_DANANTARA.png", "LOGO_PETRO.png"):
        p = os.path.join(base, name)
        if os.path.exists(p):
            try:
                with open(p, "rb") as f:
                    return base64_encode(f.read())
            except Exception:
                return None
    return None


def base64_encode(data: bytes) -> str:
    import base64
    return base64.b64encode(data).decode("utf-8")


def _classify_open_status(value) -> bool | None:
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


def _pick_category(top_categories: dict, preferred: list, used: set):
    for label in preferred:
        items = top_categories.get(label)
        if items and label not in used:
            used.add(label)
            return label, items
    return None


def _humanize_label(label: str) -> str:
    return label.replace("_", " ").replace("category ", "Kategori ").strip().title()


def _build_key_findings(ai_summary: dict, report_stats: dict, open_count: int) -> list:
    findings = [sanitize_text(f) for f in (ai_summary.get("key_findings") or []) if f]
    if not findings:
        sev = report_stats.get("severity_distribution") or {}
        total_sev = sum(sev.values())
        if total_sev:
            top, count = max(sev.items(), key=lambda kv: kv[1])
            pct = round(count / total_sev * 100, 1)
            findings.append(f"Proporsi {SEVERITY_LABEL.get(top, top.capitalize())} paling tinggi, {count} event ({pct}%).")
        tops = report_stats.get("top_categories") or {}
        for label, items in tops.items():
            if items:
                findings.append(
                    f"Kategori teratas pada {_humanize_label(label)} adalah "
                    f"{items[0]['value']} dengan {items[0]['count']} kejadian."
                )
                break
        if not findings:
            findings.append("Temuan utama belum dapat dirumuskan otomatis dari data ini.")
    if open_count > 0:
        findings.insert(0, f"Terdapat {open_count} insiden berstatus terbuka/belum ditangani yang memerlukan tindak lanjut segera.")
    return findings[:6]


# ============================================================================
# Helper HTML — badge, panel, bar chart, kartu, tabel
# ============================================================================
def _esc(text) -> str:
    return html.escape(str(text)) if text is not None else ""


def _badge(text, color=GREEN_MAIN, size="26px", font_size="10.5pt") -> str:
    # Lingkaran badge via inline-block + line-height (trik CSS klasik, BUKAN flexbox atau
    # tabel bersarang) — xhtml2pdf (fallback engine) rapuh dgn tabel yang bersarang terlalu
    # dalam + padding kumulatif (pernah crash "negative availWidth"), jadi badge SENGAJA
    # dibuat elemen paling sederhana (1 div) supaya tidak menambah level nesting di semua
    # tempat yang memakainya (badge muncul di hampir tiap bagian dokumen).
    return (
        f'<div style="display:inline-block;width:{size};height:{size};line-height:{size};'
        f'border-radius:50%;background:{color};text-align:center;color:#fff;font-weight:700;'
        f'font-size:{font_size};font-family:{BODY_FONT};">{_esc(text)}</div>'
    )


def _badge_row(number, title, detail, color=GREEN_MAIN, on_dark=False) -> str:
    # xhtml2pdf (fallback engine kalau WeasyPrint tak tersedia) TIDAK support flexbox —
    # dipakai <table> supaya badge+teks sejajar konsisten di kedua engine.
    title_color = "#fff" if on_dark else TEXT_DARK
    detail_color = GOLD_LIGHT if on_dark else GRAY_TEXT
    detail_html = f'<div style="font-size:9.5pt;color:{detail_color};margin-top:2px;">{_esc(detail)}</div>' if detail else ""
    return (
        f'<table style="width:100%;border-collapse:collapse;margin-bottom:14px;" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="width:34px;vertical-align:top;padding:0 12px 0 0;">{_badge(number, color)}</td>'
        f'<td style="vertical-align:top;padding:0;">'
        f'<div style="font-weight:700;font-size:11.5pt;color:{title_color};">{_esc(title)}</div>{detail_html}'
        f'</td></tr></table>'
    )


def _kicker(text, color=GREEN_MAIN) -> str:
    return (
        f'<div style="font-size:9pt;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;'
        f'color:{color};margin-bottom:6px;font-family:{BODY_FONT};">{_esc(text)}</div>'
    )


def _title(text, color=TEXT_DARK, size="20pt") -> str:
    return f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:{size};color:{color};margin-bottom:14px;">{_esc(text)}</div>'


def _bar_chart_html(categories, values, colors=None) -> str:
    # Bar dibangun dari lebar <table> (persen) di dalam <div> track, BUKAN flexbox — trik
    # aman dipakai di xhtml2pdf maupun WeasyPrint (flexbox tidak didukung xhtml2pdf).
    # PENTING: fill memakai <table width="{pct}%"> SATU KOLOM (bukan 2 kolom fill+filler)
    # sebab xhtml2pdf memberi rightPadding default non-nol ke kolom filler yang lebarnya
    # nyaris 0 (saat pct=100), menyebabkan availWidth negatif dan crash reportlab.
    max_val = max(values) if values else 1
    rows = []
    for i, (cat, val) in enumerate(zip(categories, values)):
        pct = round(val / max_val * 100, 1) if max_val else 0
        pct = max(pct, 1.5) if val else 0
        color = colors[i] if colors else GREEN_MAIN
        fill_html = (
            f'<table style="width:{pct}%;" cellpadding="0" cellspacing="0"><tr>'
            f'<td style="background:{color};height:16px;border-radius:4px;font-size:1px;line-height:16px;padding:0;">&nbsp;</td>'
            f'</tr></table>'
            if pct else ""
        )
        rows.append(
            f'<tr>'
            f'<td style="width:100px;font-size:9.5pt;color:{TEXT_DARK};padding:0 0 8px 0;">{_esc(cat)}</td>'
            f'<td style="padding:0 8px 8px 0;">'
            f'<div style="background:#EEEEEE;border-radius:4px;">{fill_html}</div>'
            f'</td>'
            f'<td style="width:36px;text-align:right;font-weight:700;font-size:9.5pt;color:{TEXT_DARK};padding:0 0 8px 0;">{val:g}</td>'
            f'</tr>'
        )
    return f'<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0">{"".join(rows)}</table>'


def _ivory_panel(icon_text, title_text, rows_html, footnote=None) -> str:
    footnote_html = ""
    if footnote:
        footnote_html = (
            f'<div style="border-top:1px solid {PANEL_BORDER};margin-top:12px;padding-top:10px;'
            f'font-size:8.5pt;font-style:italic;color:{GRAY_TEXT};">{_esc(footnote)}</div>'
        )
    header_html = (
        f'<table style="width:100%;margin-bottom:12px;" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="width:30px;vertical-align:middle;padding:0;">{_badge(icon_text, GOLD_MAIN, size="22px", font_size="9pt")}</td>'
        f'<td style="vertical-align:middle;padding:0 0 0 6px;">'
        f'<span style="font-weight:700;font-size:10.5pt;color:{GREEN_MAIN};text-transform:uppercase;font-family:{BODY_FONT};">{_esc(title_text)}</span>'
        f'</td></tr></table>'
    )
    return (
        f'<div style="background:{IVORY};border:1px solid {PANEL_BORDER};border-radius:10px;padding:16px;">'
        f'{header_html}{rows_html}{footnote_html}</div>'
    )


def _ivory_kv_rows(rows) -> str:
    parts = []
    for label, value in rows:
        parts.append(
            f'<div style="margin-bottom:10px;">'
            f'<div style="font-size:9.5pt;font-weight:700;color:{GREEN_MAIN};">{_esc(label)}</div>'
            f'<div style="font-size:9.5pt;color:{GRAY_TEXT};">{_esc(value)}</div></div>'
        )
    return "".join(parts)


def _legend_rows(rows) -> str:
    parts = []
    for color, label, pct in rows:
        parts.append(
            f'<tr>'
            f'<td style="width:16px;padding:0 0 8px 0;">'
            f'<table cellpadding="0" cellspacing="0"><tr><td style="width:12px;height:12px;background:{color};font-size:1px;line-height:1px;padding:0;">&nbsp;</td></tr></table>'
            f'</td>'
            f'<td style="padding:0 8px 8px 8px;font-size:9.5pt;color:{TEXT_DARK};">{_esc(label)}</td>'
            f'<td style="text-align:right;padding:0 0 8px 0;font-weight:700;font-size:9.5pt;color:{GREEN_MAIN};">{_esc(pct)}</td>'
            f'</tr>'
        )
    return f'<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0">{"".join(parts)}</table>'


def _dark_panel(inner_html, w="100%") -> str:
    return (
        f'<div style="background:{GREEN_BG};border:1px solid {GOLD_MAIN};border-radius:10px;'
        f'padding:18px;width:{w};box-sizing:border-box;">{inner_html}</div>'
    )


def _critical_highlight_panel(pct_text, sub_text, detail_text=None) -> str:
    detail_html = f'<div style="font-size:9.5pt;color:{GOLD_LIGHT};margin-top:14px;">{_esc(detail_text)}</div>' if detail_text else ""
    inner = (
        f'<div style="text-align:center;font-family:{TITLE_FONT};font-weight:700;font-size:34pt;color:{GOLD_MAIN};">{_esc(pct_text)}</div>'
        f'<div style="text-align:center;font-size:10.5pt;color:#fff;margin-top:6px;">{_esc(sub_text)}</div>'
        f'{detail_html}'
    )
    return _dark_panel(inner)


def _priority_panel(title_text, items) -> str:
    rows = "".join(
        f'<table style="width:100%;border-collapse:collapse;margin-bottom:12px;" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="width:32px;vertical-align:top;padding:0;">{_badge(letter, GOLD_MAIN, size="24px", font_size="10pt")}</td>'
        f'<td style="vertical-align:top;padding:2px 0 0 0;font-size:10.5pt;color:#fff;">{_esc(text)}</td>'
        f'</tr></table>'
        for letter, text in items
    )
    inner = (
        f'<div style="font-size:9.5pt;font-weight:700;letter-spacing:1px;text-transform:uppercase;'
        f'color:{GOLD_MAIN};margin-bottom:14px;">{_esc(title_text)}</div>{rows}'
    )
    return _dark_panel(inner)


def _pill(text) -> str:
    return (
        f'<div style="background:{GREEN_MAIN};border:1px solid {GOLD_MAIN};border-radius:999px;'
        f'padding:10px 16px;text-align:center;font-weight:700;font-size:10.5pt;color:{GOLD_MAIN};margin-bottom:10px;">'
        f'{_esc(text)}</div>'
    )


def _card_grid(cell_inner_htmls: list, cols: int) -> str:
    """Susun daftar HTML kartu jadi grid N kolom pakai <table> (bukan flexbox/grid CSS —
    tidak didukung xhtml2pdf, fallback engine kalau WeasyPrint tak tersedia)."""
    col_w = round(100 / cols, 3)
    cells = [f'<td style="width:{col_w}%;padding:6px;vertical-align:top;">{inner}</td>' for inner in cell_inner_htmls]
    rows = []
    for i in range(0, len(cells), cols):
        row_cells = cells[i:i + cols]
        while len(row_cells) < cols:
            row_cells.append(f'<td style="width:{col_w}%;"></td>')
        rows.append(f'<tr>{"".join(row_cells)}</tr>')
    return f'<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0">{"".join(rows)}</table>'


def _stat_card_grid(items, cols=3, dark=True) -> str:
    bg = GREEN_MAIN if dark else IVORY
    label_color = "#fff" if dark else TEXT_DARK
    cell_htmls = [
        f'<table style="width:100%;background:{bg};border:1px solid {GOLD_MAIN};border-radius:10px;" cellpadding="14"><tr><td style="text-align:center;">'
        f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:22pt;color:{GOLD_MAIN};">{_esc(value)}</div>'
        f'<div style="font-size:9pt;color:{label_color};margin-top:6px;">{_esc(label)}</div>'
        f'</td></tr></table>'
        for value, label in items
    ]
    return _card_grid(cell_htmls, cols)


def _asset_card_row(items) -> str:
    n = len(items) or 1
    cell_htmls = [
        f'<table style="width:100%;background:{GREEN_MAIN};border:1px solid {GOLD_MAIN};border-radius:10px;" cellpadding="16"><tr><td>'
        f'{_badge(num, GOLD_MAIN, size="34px", font_size="13pt")}'
        f'<div style="font-weight:700;font-size:12.5pt;color:#fff;margin-top:12px;">{_esc(title)}</div>'
        f'<div style="font-weight:700;font-size:10.5pt;color:{GOLD_MAIN};margin-top:4px;">{_esc(stat)}</div>'
        f'<div style="font-size:9pt;color:#E8ECE6;margin-top:10px;">{_esc(desc)}</div>'
        f'</td></tr></table>'
        for num, title, stat, desc in items
    ]
    return _card_grid(cell_htmls, n)


def _two_col(left_html, right_html, left_pct=58) -> str:
    """Layout 2-kolom pakai <table> (bukan flexbox — tidak didukung xhtml2pdf)."""
    right_pct = 100 - left_pct
    return (
        f'<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="width:{left_pct}%;vertical-align:top;padding-right:16px;">{left_html}</td>'
        f'<td style="width:{right_pct}%;vertical-align:top;">{right_html}</td>'
        f'</tr></table>'
    )


def _critical_table(headers, rows, highlight_idx) -> str:
    thead = "".join(f'<th style="background:{GREEN_BG};color:#fff;padding:7px 9px;text-align:left;font-size:9pt;">{_esc(h)}</th>' for h in headers)
    trows = []
    for i, row_vals in enumerate(rows):
        is_open = i in highlight_idx
        row_bg = RED_CRIT_BG if is_open else (IVORY if i % 2 == 0 else "#FFFFFF")
        cells = []
        for c, val in enumerate(row_vals):
            is_status_col = c == len(row_vals) - 1
            style = f"padding:7px 9px;font-size:9pt;"
            if is_open and is_status_col:
                style += f"color:{RED_CRIT};font-weight:700;"
            cells.append(f'<td style="{style}">{_esc(val)}</td>')
        trows.append(f'<tr style="background:{row_bg};">{"".join(cells)}</tr>')
    return (
        f'<table style="width:100%;border-collapse:collapse;font-family:{BODY_FONT};" cellpadding="0" cellspacing="0">'
        f'<thead><tr>{thead}</tr></thead><tbody>{"".join(trows)}</tbody></table>'
    )


def _flourish_html(corner="bottom_right") -> str:
    pos = {
        "bottom_right": "bottom:-70px;right:-70px;",
        "top_right": "top:-70px;right:-70px;",
        "bottom_left": "bottom:-70px;left:-70px;",
    }.get(corner, "bottom:-70px;right:-70px;")
    circles = "".join(
        f'<div style="position:absolute;{pos}width:{140+ i*55}px;height:{140+i*55}px;'
        f'border-radius:50%;border:1px solid {GOLD_MAIN};"></div>'
        for i in range(4)
    )
    return f'<div style="position:absolute;inset:0;overflow:hidden;pointer-events:none;">{circles}</div>'


def _page(inner_html, dark=False, flourish=None, page_num=None, total_pages=None, logo_b64=None, last=False) -> str:
    bg = GREEN_BG if dark else "#FFFFFF"
    color = "#fff" if dark else TEXT_DARK
    break_style = "" if last else "page-break-after:always;"
    flourish_html = _flourish_html(flourish) if flourish else ""
    # top/right/bottom = 0 (bukan mis. "14mm") karena div halaman ini SUDAH PERSIS ADALAH
    # area konten (sudah diberi jarak dari tepi kertas asli oleh @page margin) — beri jarak
    # tambahan di sini berarti menjorok dua kali dari tepi.
    logo_html = (
        f'<img src="data:image/png;base64,{logo_b64}" style="position:absolute;top:0;right:0;height:34px;" />'
        if logo_b64 else ""
    )
    footer_html = ""
    if page_num is not None:
        footer_html = (
            f'<div style="position:absolute;bottom:0;right:0;font-size:8pt;color:{GRAY_TEXT if not dark else GOLD_LIGHT};'
            f'font-family:{BODY_FONT};">{page_num:02d} / {total_pages:02d}</div>'
        )
    # PENTING: div halaman ini SENGAJA TANPA padding — margin halaman diatur lewat @page
    # (lihat html_content di bawah), bukan padding di sini. xhtml2pdf (fallback engine kalau
    # WeasyPrint tak tersedia) crash ("negative availWidth") kalau div berpadding besar
    # membungkus tabel bersarang (padding div ikut terhitung berulang ke kalkulasi lebar sel
    # tabel di dalamnya oleh reportlab). @page margin diterapkan di level frame halaman
    # SEBELUM flowable di-layout, jadi tidak bentrok dengan tabel apapun di dalamnya.
    return (
        f'<div style="position:relative;{break_style}background:{bg};color:{color};min-height:267mm;'
        f'font-family:{BODY_FONT};">'
        f'{flourish_html}{logo_html}{inner_html}{footer_html}</div>'
    )


class PDFExporter:
    @classmethod
    def generate_pdf_report(cls, report: Report) -> bytes:
        if not WEASYPRINT_AVAILABLE and not XHTML2PDF_AVAILABLE:
            raise RuntimeError(
                "Pustaka sistem PDF (WeasyPrint dan xhtml2pdf) tidak ditemukan di sistem Anda. "
                "Silakan install xhtml2pdf atau jalankan aplikasi dengan WeasyPrint terinstal."
            )

        logo_b64 = _resolve_logo_b64()
        parsed_data = get_parsed_data(report)
        report_stats = compute_statistics(parsed_data, report.data_type) if parsed_data else {"total_records": 0}
        ai_summary = report.ai_summary or {}

        rnd = random.Random()
        stat_cols = rnd.choice([2, 3])
        card_cols = rnd.choice([2, 3])
        flourish_corner = rnd.choice(["bottom_right", "top_right", "bottom_left"])
        kicker_ringkasan = rnd.choice(["RINGKASAN EKSEKUTIF", "SNAPSHOT UTAMA", "IKHTISAR EKSEKUTIF"])
        kicker_analisis = rnd.choice(["ANALISIS DATA", "TINJAUAN DATA", "ANALISIS TEMUAN"])

        total_records = report_stats.get("total_records", 0)
        severity = report_stats.get("severity_distribution") or {}
        total_sev = sum(severity.values())
        top_categories = report_stats.get("top_categories") or {}
        status_items = top_categories.get("status") or []

        used_labels = set()
        generic_category_keys = sorted(k for k in top_categories if k.startswith("category_"))
        category_pick = _pick_category(top_categories, ["action", *generic_category_keys, "location", "destination_port"], used_labels)
        asset_pick = _pick_category(top_categories, ["asset", "destination_port", "location", *generic_category_keys], used_labels)

        source_cols = report_stats.get("_source_columns") or {}
        severity_col = source_cols.get("severity")
        status_col = source_cols.get("status")
        open_count = 0
        if status_col and parsed_data:
            for row in parsed_data:
                if _classify_open_status(row.get(status_col)) is True:
                    open_count += 1

        recommendations = normalize_recommendations(ai_summary.get("recommendations"))
        key_findings = _build_key_findings(ai_summary, report_stats, open_count)
        period_text = _format_period(report)

        included = report.included_sections or {}

        def is_included(key: str) -> bool:
            if isinstance(included, dict):
                return included.get(key, True)
            if isinstance(included, list):
                for sec in included:
                    if isinstance(sec, dict) and (sec.get("key") == key or sec.get("id") == key):
                        return sec.get("enabled", True)
            return True

        pages = []  # list of (html, dark, flourish)

        # ---------------- Cover ----------------
        cat_count = len(top_categories)
        crit_count = severity.get("critical", 0)
        cover_inner = (
            f'<div style="margin-top:60mm;">'
            f'{_kicker("LAPORAN ANALISIS", GOLD_MAIN)}'
            f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:34pt;color:#fff;margin-bottom:10px;">{_esc(report.title)}</div>'
            f'<div style="font-size:12.5pt;color:#fff;margin-bottom:20px;">{_esc(sanitize_text(report.header_subtitle) or "Security Operation Center")}</div>'
            f'<div style="font-size:10.5pt;color:#fff;">Periode data. {_esc(period_text)}</div>'
            f'<div style="font-size:10.5pt;color:{GOLD_LIGHT};margin-top:6px;">{total_records} entri log, {cat_count} kategori kejadian, {crit_count} insiden Critical</div>'
            f'</div>'
            f'<div style="position:absolute;bottom:14mm;left:16mm;font-size:9pt;font-weight:700;color:#fff;">{_esc((report.header_title or "PT PETROKIMIA GRESIK").upper())}</div>'
        )
        pages.append((cover_inner, True, flourish_corner, False))

        # ---------------- Latar Belakang & Tujuan ----------------
        purpose_text = sanitize_text(
            f"Sepanjang periode {period_text}, sistem keamanan siber mencatat {total_records} event "
            f"yang dianalisis pada laporan ini. Data log dianalisis untuk memetakan pola kejadian, "
            f"menilai efektivitas penanganan, dan menjadi dasar rekomendasi perbaikan."
        )
        objectives_html = "".join([
            _badge_row("1", "Memetakan Pola Kejadian", "Mengidentifikasi kategori, tren waktu, dan aset yang paling sering menjadi sasaran.", GREEN_MAIN),
            _badge_row("2", "Menilai Efektivitas Respons", "Mengevaluasi status penanganan tiap insiden.", GREEN_MAIN),
            _badge_row("3", "Menyusun Rekomendasi", "Merumuskan langkah mitigasi prioritas berbasis temuan data aktual.", GREEN_MAIN),
        ])
        scope_rows = _ivory_kv_rows([
            ("Periode", period_text),
            ("Total Event", f"{total_records} entri log"),
            ("Sumber Berkas", report.input_file_name or "-"),
            ("Jenis Data", (report.data_type or "-").replace("_", " ").title()),
        ])
        scope_panel = _ivory_panel("i", "Ruang Lingkup Data", scope_rows, footnote="Sumber. Data yang diunggah pengguna, diproses otomatis oleh sistem.")
        bg_left = f'<div style="font-size:11pt;color:{GRAY_TEXT};margin-bottom:18px;">{purpose_text}</div>{objectives_html}'
        bg_inner = (
            _kicker("PENDAHULUAN", GREEN_MAIN) + _title("Latar Belakang dan Tujuan Analisis") +
            _two_col(bg_left, scope_panel, left_pct=58)
        )
        pages.append((bg_inner, False, None, False))

        # ---------------- Ringkasan Eksekutif ----------------
        if is_included("executive_summary"):
            stat_items = [(str(total_records), "Total Event Log")]
            if total_sev:
                if severity.get("critical"):
                    stat_items.append((str(severity["critical"]), "Insiden Critical"))
                if severity.get("high"):
                    stat_items.append((str(severity["high"]), "High Severity"))
            if status_col:
                closed = sum(1 for row in parsed_data if _classify_open_status(row.get(status_col)) is False)
                if closed:
                    stat_items.append((str(closed), "Sudah Ditangani"))
                stat_items.append((str(open_count), "Masih Terbuka"))
            if category_pick:
                stat_items.append((str(len(top_categories)), "Kategori Sumber"))
            stat_items = stat_items[:6]

            caption = sanitize_text(ai_summary.get("executive_summary") or (key_findings[0] if key_findings else ""))
            exec_inner = (
                _kicker(kicker_ringkasan, GOLD_MAIN) +
                f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:20pt;color:#fff;margin-bottom:18px;">Snapshot Log Keamanan, {_esc(period_text)}</div>' +
                _stat_card_grid(stat_items, cols=stat_cols, dark=True) +
                f'<div style="font-size:10.5pt;font-style:italic;color:{GOLD_LIGHT};margin-top:18px;">{_esc(caption)}</div>'
            )
            pages.append((exec_inner, True, None, False))

        # ---------------- Distribusi Kategori Event ----------------
        if category_pick:
            label, items = category_pick
            top_items = items[:6]
            cat_total = sum(i["count"] for i in items) or 1
            intro = sanitize_text(
                f"{top_items[0]['value']} mencatat volume tertinggi dengan {top_items[0]['count']} event "
                f"({round(top_items[0]['count']/cat_total*100,1)}% dari total)."
            )
            legend = _legend_rows([
                (CATEGORY_COLOR_RAMP[i % len(CATEGORY_COLOR_RAMP)], it["value"], f"{round(it['count']/cat_total*100,1)}%")
                for i, it in enumerate(top_items)
            ])
            legend_panel = _ivory_panel("%", "Proporsi Kategori", legend, footnote=sanitize_text(f"{top_items[0]['value']} menjadi kontributor volume terbesar pada kategori ini."))
            chart_html = _bar_chart_html([i["value"] for i in top_items], [i["count"] for i in top_items])
            cat_inner = (
                _kicker(kicker_analisis, GREEN_MAIN) + _title(f"Distribusi Event Berdasarkan {_humanize_label(label)}") +
                f'<div style="font-size:11pt;color:{GRAY_TEXT};margin-bottom:16px;">{intro}</div>' +
                _two_col(chart_html, legend_panel, left_pct=58)
            )
            pages.append((cat_inner, False, None, False))

        # ---------------- Distribusi Severity ----------------
        if total_sev > 0 and is_included("severity_analysis"):
            crit_pct = round(severity.get("critical", 0) / total_sev * 100, 1)
            high_pct = round(severity.get("high", 0) / total_sev * 100, 1)
            intro = sanitize_text(f"{high_pct}% event berkategori High dan {crit_pct}% Critical. Kombinasi keduanya memerlukan perhatian dan eskalasi serius.")
            sev_categories = [SEVERITY_LABEL[k] for k in SEVERITY_ORDER]
            sev_values = [severity.get(k, 0) for k in SEVERITY_ORDER]
            sev_colors = [SEVERITY_COLOR[k] for k in SEVERITY_ORDER]
            chart_html = _bar_chart_html(sev_categories, sev_values, colors=sev_colors)
            detail_text = None
            if category_pick:
                names = ", ".join(i["value"] for i in category_pick[1][:6])
                detail_text = sanitize_text(f"Insiden Critical tersebar pada kategori {names}.")
            panel = _critical_highlight_panel(f"{crit_pct}%", "dari seluruh event berstatus Critical Severity", detail_text)
            sev_inner = (
                _kicker(kicker_analisis, GREEN_MAIN) + _title("Distribusi Tingkat Keparahan (Severity)") +
                f'<div style="font-size:11pt;color:{GRAY_TEXT};margin-bottom:16px;">{intro}</div>' +
                _two_col(chart_html, panel, left_pct=62)
            )
            pages.append((sev_inner, False, None, False))

        # ---------------- Status Penanganan Insiden ----------------
        if status_items:
            status_total = sum(i["count"] for i in status_items) or 1
            top_status = status_items[0]
            intro = sanitize_text(
                f"{round(top_status['count']/status_total*100,1)}% event berstatus {top_status['value']}. "
                f"Sebagian kecil masih memerlukan tindak lanjut aktif tim SOC."
            )
            top_status_items = status_items[:8]
            chart_html = _bar_chart_html([i["value"] for i in top_status_items], [i["count"] for i in top_status_items])
            status_inner = (
                _kicker(kicker_analisis, GREEN_MAIN) + _title("Status Penanganan Insiden") +
                f'<div style="font-size:11pt;color:{GRAY_TEXT};margin-bottom:16px;">{intro}</div>' + chart_html
            )
            pages.append((status_inner, False, None, False))

        # ---------------- Tabel Insiden Critical ----------------
        if severity_col and parsed_data:
            critical_rows = [row for row in parsed_data if _classify_severity_value(str(row.get(severity_col, ""))) == "critical"]
            if len(critical_rows) < 5:
                critical_rows += [row for row in parsed_data if _classify_severity_value(str(row.get(severity_col, ""))) == "high"]
            critical_rows = critical_rows[:12]

            if critical_rows:
                headers = ["No"]
                if category_pick:
                    headers.append(_humanize_label(category_pick[0]))
                headers.append("Severity")
                if status_col:
                    headers.append("Status")

                cat_col_name = source_cols.get(category_pick[0]) if category_pick else None
                rows_out = []
                highlight_idx = set()
                for idx, row in enumerate(critical_rows):
                    row_vals = [str(idx + 1)]
                    if category_pick:
                        row_vals.append(str(row.get(cat_col_name, "-")) if cat_col_name else "-")
                    row_vals.append(_classify_severity_value(str(row.get(severity_col, ""))).capitalize())
                    if status_col:
                        status_val = row.get(status_col, "-")
                        row_vals.append(str(status_val))
                        if _classify_open_status(status_val) is True:
                            highlight_idx.add(idx)
                    rows_out.append(row_vals)

                table_html = _critical_table(headers, rows_out, highlight_idx)
                caption_html = ""
                if open_count:
                    caption_html = (
                        f'<div style="font-size:9.5pt;font-style:italic;color:{GRAY_TEXT};margin-top:12px;">'
                        f'{_esc(sanitize_text(f"Baris merah menandai {open_count} insiden yang masih dalam proses penanganan per akhir periode data."))}</div>'
                    )
                kicker_color = RED_CRIT if open_count else GREEN_MAIN
                table_inner = (
                    _kicker("SOROTAN INSIDEN", kicker_color) + _title(f"{len(critical_rows)} Insiden Prioritas Tinggi") +
                    table_html + caption_html
                )
                pages.append((table_inner, False, None, False))

        # ---------------- Aset Paling Sering Menjadi Sasaran ----------------
        if asset_pick:
            label, items = asset_pick
            asset_total = sum(i["count"] for i in items) or 1
            top_assets = items[:3]
            card_items = []
            for idx, item in enumerate(top_assets):
                pct = round(item["count"] / asset_total * 100, 1)
                card_items.append((
                    str(idx + 1), item["value"], f"{item['count']} event",
                    sanitize_text(f"Tercatat {item['count']} kejadian ({pct}% dari total) yang menyasar kategori ini."),
                ))
            asset_inner = (
                _kicker("SOROTAN INSIDEN", GOLD_MAIN) +
                f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:20pt;color:#fff;margin-bottom:18px;">{_esc(_humanize_label(label))} yang Paling Sering Menjadi Sasaran</div>' +
                _asset_card_row(card_items)
            )
            pages.append((asset_inner, True, None, False))

        # ---------------- Temuan Utama ----------------
        if key_findings:
            findings_html_parts = []
            for idx, finding in enumerate(key_findings):
                title_part, _, detail_part = finding.partition(". ")
                if not detail_part:
                    title_part, detail_part = finding, ""
                color = RED_CRIT if (open_count and idx == 0) else GREEN_MAIN
                findings_html_parts.append(_badge_row(str(idx + 1), title_part.strip() or finding, detail_part.strip(), color))
            find_inner = _kicker("ANALISIS", GREEN_MAIN) + _title("Temuan Utama") + "".join(findings_html_parts)
            pages.append((find_inner, False, None, False))

        # ---------------- Rekomendasi Mitigasi ----------------
        if is_included("recommendations") and recommendations:
            items = recommendations[:6]
            cell_htmls = []
            for idx, item in enumerate(items):
                title_txt = item.get("title") or (item.get("detail") or "")[:60]
                detail_html = f'<div style="font-size:9.5pt;color:{GRAY_TEXT};margin-top:6px;">{_esc(item.get("detail"))}</div>' if (item.get("title") and item.get("detail")) else ""
                cell_htmls.append(
                    f'<table style="width:100%;background:{IVORY};border:1px solid {PANEL_BORDER};border-radius:10px;" cellpadding="14"><tr><td>'
                    f'{_badge(str(idx+1), GOLD_MAIN, size="28px")}'
                    f'<div style="font-weight:700;font-size:11pt;color:{TEXT_DARK};margin-top:10px;">{_esc(title_txt)}</div>'
                    f'{detail_html}</td></tr></table>'
                )
            rec_inner = _kicker("TINDAK LANJUT", GREEN_MAIN) + _title("Rekomendasi Mitigasi") + _card_grid(cell_htmls, card_cols)
            pages.append((rec_inner, False, None, False))

        # ---------------- Kesimpulan ----------------
        if is_included("conclusion") and ai_summary.get("conclusion"):
            pills = []
            if total_sev and status_col:
                resolved_pct = round((total_sev - open_count) / total_sev * 100, 1)
                pills.append(_pill(f"{resolved_pct}% event tertangani"))
            if category_pick:
                pills.append(_pill(f"{category_pick[1][0]['value']} jadi prioritas perhatian"))
            if open_count:
                pills.append(_pill(f"{open_count} insiden masih berjalan"))

            priority_items = []
            for idx, rec in enumerate(recommendations[:4]):
                letter = chr(ord("a") + idx)
                priority_items.append((letter, rec.get("title") or (rec.get("detail") or "")[:70]))
            priority_html = _priority_panel("Prioritas Berikutnya", priority_items) if priority_items else ""

            concl_left = (
                f'<div style="font-size:11pt;color:#E8ECE6;margin-bottom:18px;">{_esc(sanitize_text(ai_summary.get("conclusion")))}</div>'
                f'{"".join(pills)}'
            )
            concl_inner = (
                _kicker("PENUTUP", GOLD_MAIN) +
                f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:20pt;color:#fff;margin-bottom:16px;">Kesimpulan</div>' +
                _two_col(concl_left, priority_html, left_pct=58)
            )
            pages.append((concl_inner, True, None, False))

        # ---------------- Penutup ----------------
        closing_inner = (
            f'<div style="margin-top:60mm;">'
            f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:30pt;color:#fff;margin-bottom:10px;">Terima Kasih</div>'
            f'<div style="font-size:12pt;color:#fff;margin-bottom:8px;">{_esc(report.title)}</div>'
            f'<div style="font-size:10.5pt;font-style:italic;color:{GOLD_LIGHT};">Diskusi dan pertanyaan dipersilakan.</div>'
            f'</div>'
        )
        pages.append((closing_inner, True, flourish_corner, True))

        # ---------------- Rakit halaman jadi 1 dokumen HTML ----------------
        total_pages = len(pages) - 2  # tidak termasuk cover & penutup di penomoran
        page_html_parts = []
        content_idx = 0
        for i, (inner, dark, flourish, is_last) in enumerate(pages):
            is_cover_or_closing = i == 0 or i == len(pages) - 1
            page_num = None
            if not is_cover_or_closing:
                content_idx += 1
                page_num = content_idx
            page_html_parts.append(_page(
                inner, dark=dark, flourish=flourish,
                page_num=page_num, total_pages=total_pages,
                logo_b64=(logo_b64 if not is_cover_or_closing else None),
                last=is_last,
            ))

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{_esc(report.title)}</title>
            <style>
                @page {{ size: A4; margin: 16mm 16mm 14mm 16mm; }}
                * {{ box-sizing: border-box; }}
                body {{ margin: 0; font-family: {BODY_FONT}; }}
            </style>
        </head>
        <body>
            {''.join(page_html_parts)}
        </body>
        </html>
        """

        if WEASYPRINT_AVAILABLE:
            try:
                return HTML(string=html_content).write_pdf()
            except Exception as weasy_err:
                print(f"[PDF WARNING] WeasyPrint gagal merender: {weasy_err}. Menggunakan fallback xhtml2pdf.")
                if not XHTML2PDF_AVAILABLE:
                    raise weasy_err

        pdf_io = io.BytesIO()
        pisa_status = pisa.CreatePDF(html_content, dest=pdf_io)
        if pisa_status.err:
            raise RuntimeError(f"Gagal mengonversi HTML ke PDF menggunakan xhtml2pdf: {pisa_status.err}")
        return pdf_io.getvalue()
