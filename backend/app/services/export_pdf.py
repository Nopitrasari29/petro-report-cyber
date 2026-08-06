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
import html
import io
import os
import random

from app.models.report import Report
from app.services.report_render_logic import build_report_blocks, is_english

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
    #
    # height eksplisit di <table> ini WAJIB (lihat catatan panjang di _card_grid) — kalau
    # tidak, xhtml2pdf meregangkan badge row ini (bahkan saat ditumpuk sebagai beberapa
    # <table> terpisah, sudah diuji langsung) supaya total tumpukannya penuh ke sisa tinggi
    # halaman, membuat jarak antar baris jadi puluhan kali lipat dari margin-bottom aslinya.
    # Nilai height digenerosikan (bukan pas-pasan) karena detail bisa wrap ke 2 baris.
    row_h = "50pt" if detail else "24pt"
    title_color = "#fff" if on_dark else TEXT_DARK
    detail_color = GOLD_LIGHT if on_dark else GRAY_TEXT
    detail_html = f'<div style="font-size:9.5pt;color:{detail_color};margin-top:2px;">{_esc(detail)}</div>' if detail else ""
    return (
        f'<table style="width:100%;height:{row_h};border-collapse:collapse;margin-bottom:14px;" cellpadding="0" cellspacing="0"><tr style="height:{row_h};">'
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
    # height eksplisit di <table> DAN tiap <tr> (lihat catatan panjang di _card_grid) — tanpanya
    # xhtml2pdf meregangkan tiap baris bar chart supaya penuh ke sisa tinggi halaman, membuat
    # jarak antar bar jadi ratusan pt padahal cuma dirancang ~24pt per baris.
    row_h = 24
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
            f'<tr style="height:{row_h}pt;">'
            f'<td style="width:100px;font-size:9.5pt;color:{TEXT_DARK};padding:0 0 8px 0;">{_esc(cat)}</td>'
            f'<td style="padding:0 8px 8px 0;">'
            f'<div style="background:#EEEEEE;border-radius:4px;">{fill_html}</div>'
            f'</td>'
            f'<td style="width:36px;text-align:right;font-weight:700;font-size:9.5pt;color:{TEXT_DARK};padding:0 0 8px 0;">{val:g}</td>'
            f'</tr>'
        )
    total_h = row_h * len(rows)
    return f'<table style="width:100%;height:{total_h}pt;border-collapse:collapse;" cellpadding="0" cellspacing="0">{"".join(rows)}</table>'


def _ivory_panel(icon_text, title_text, rows_html, footnote=None, content_rows=0) -> str:
    # panel_height dihitung dari jumlah baris konten (content_rows, diisi pemanggil) — WAJIB
    # eksplisit (lihat catatan panjang di _card_grid) karena panel ini <div> BERBACKGROUND
    # yang dibungkus di dalam halaman ber-height eksplisit penuh 1 halaman; tanpa height
    # sendiri, div ini (dan baris-baris di dalamnya) diregangkan xhtml2pdf mengisi sisa
    # tinggi halaman, meninggalkan celah kosong raksasa antar baris.
    footnote_html = ""
    footnote_h = 0
    if footnote:
        footnote_h = 34
        footnote_html = (
            f'<div style="border-top:1px solid {PANEL_BORDER};margin-top:12px;padding-top:10px;'
            f'font-size:8.5pt;font-style:italic;color:{GRAY_TEXT};">{_esc(footnote)}</div>'
        )
    header_html = (
        f'<table style="width:100%;height:22pt;margin-bottom:12px;" cellpadding="0" cellspacing="0"><tr style="height:22pt;">'
        f'<td style="width:30px;vertical-align:middle;padding:0;">{_badge(icon_text, GOLD_MAIN, size="22px", font_size="9pt")}</td>'
        f'<td style="vertical-align:middle;padding:0 0 0 6px;">'
        f'<span style="font-weight:700;font-size:10.5pt;color:{GREEN_MAIN};text-transform:uppercase;font-family:{BODY_FONT};">{_esc(title_text)}</span>'
        f'</td></tr></table>'
    )
    panel_h = 34 + max(content_rows, 1) * 34 + footnote_h + 32
    return (
        f'<table style="width:100%;height:{panel_h}pt;background:{IVORY};border:1px solid {PANEL_BORDER};border-radius:10px;" cellpadding="16">'
        f'<tr style="height:{panel_h}pt;"><td style="vertical-align:top;">'
        f'{header_html}{rows_html}{footnote_html}</td></tr></table>'
    )


def _ivory_kv_rows(rows) -> str:
    row_h = 32
    trs = "".join(
        f'<tr style="height:{row_h}pt;"><td style="vertical-align:top;padding:0 0 10px 0;">'
        f'<div style="font-size:9.5pt;font-weight:700;color:{GREEN_MAIN};">{_esc(label)}</div>'
        f'<div style="font-size:9.5pt;color:{GRAY_TEXT};">{_esc(value)}</div></td></tr>'
        for label, value in rows
    )
    total_h = row_h * len(rows)
    return f'<table style="width:100%;height:{total_h}pt;border-collapse:collapse;" cellpadding="0" cellspacing="0">{trs}</table>'


def _legend_rows(rows) -> str:
    row_h = 22
    parts = []
    for color, label, pct in rows:
        parts.append(
            f'<tr style="height:{row_h}pt;">'
            f'<td style="width:16px;padding:0 0 8px 0;">'
            f'<table cellpadding="0" cellspacing="0"><tr><td style="width:12px;height:12px;background:{color};font-size:1px;line-height:1px;padding:0;">&nbsp;</td></tr></table>'
            f'</td>'
            f'<td style="padding:0 8px 8px 8px;font-size:9.5pt;color:{TEXT_DARK};">{_esc(label)}</td>'
            f'<td style="text-align:right;padding:0 0 8px 0;font-weight:700;font-size:9.5pt;color:{GREEN_MAIN};">{_esc(pct)}</td>'
            f'</tr>'
        )
    total_h = row_h * len(rows)
    return f'<table style="width:100%;height:{total_h}pt;border-collapse:collapse;" cellpadding="0" cellspacing="0">{"".join(parts)}</table>'


def _dark_panel(inner_html, panel_h, w="100%") -> str:
    return (
        f'<table style="width:{w};height:{panel_h}pt;background:{GREEN_BG};border:1px solid {GOLD_MAIN};border-radius:10px;" cellpadding="18">'
        f'<tr style="height:{panel_h}pt;"><td style="vertical-align:top;">{inner_html}</td></tr></table>'
    )


def _critical_highlight_panel(pct_text, sub_text, detail_text=None) -> str:
    detail_html = f'<div style="font-size:9.5pt;color:{GOLD_LIGHT};margin-top:14px;">{_esc(detail_text)}</div>' if detail_text else ""
    inner = (
        f'<div style="text-align:center;font-family:{TITLE_FONT};font-weight:700;font-size:34pt;color:{GOLD_MAIN};">{_esc(pct_text)}</div>'
        f'<div style="text-align:center;font-size:10.5pt;color:#fff;margin-top:6px;">{_esc(sub_text)}</div>'
        f'{detail_html}'
    )
    panel_h = 140 if detail_text else 90
    return _dark_panel(inner, panel_h)


def _ai_insight_strip(text) -> str:
    return (
        f'<div style="font-size:9.5pt;font-style:italic;color:{GRAY_TEXT};margin-top:10px;">'
        f'\U0001F4A1 {_esc(text)}</div>'
    )


def _priority_panel(title_text, items) -> str:
    row_h = 38
    rows = "".join(
        f'<tr style="height:{row_h}pt;">'
        f'<td style="width:32px;vertical-align:top;padding:0;">{_badge(letter, GOLD_MAIN, size="24px", font_size="10pt")}</td>'
        f'<td style="vertical-align:top;padding:2px 0 0 0;font-size:10.5pt;color:#fff;">{_esc(text)}</td>'
        f'</tr>'
        for letter, text in items
    )
    rows_h_total = row_h * max(len(items), 1)
    rows_table = f'<table style="width:100%;height:{rows_h_total}pt;border-collapse:collapse;" cellpadding="0" cellspacing="0">{rows}</table>'
    inner = (
        f'<div style="font-size:9.5pt;font-weight:700;letter-spacing:1px;text-transform:uppercase;'
        f'color:{GOLD_MAIN};margin-bottom:14px;">{_esc(title_text)}</div>{rows_table}'
    )
    panel_h = 40 + max(len(items), 1) * 38
    return _dark_panel(inner, panel_h)


def _pill(text) -> str:
    return (
        f'<div style="background:{GREEN_MAIN};border:1px solid {GOLD_MAIN};border-radius:999px;'
        f'padding:10px 16px;text-align:center;font-weight:700;font-size:10.5pt;color:{GOLD_MAIN};margin-bottom:10px;">'
        f'{_esc(text)}</div>'
    )


def _card_grid(cell_inner_htmls: list, cols: int, row_height: str | None = None) -> str:
    """Susun daftar HTML kartu jadi grid N kolom pakai <table> (bukan flexbox/grid CSS —
    tidak didukung xhtml2pdf, fallback engine kalau WeasyPrint tak tersedia).

    `row_height` (kalau diisi) diterapkan sebagai height EKSPLISIT pada <td> pembungkus tiap
    kartu — WAJIB kalau grid ini dipakai di dalam halaman yang latarnya di-cat lewat <td
    height="..."> penuh 1 halaman (lihat _page()): xhtml2pdf TERBUKTI (diuji langsung, isolasi
    render+sampling) meregangkan <table> BERSARANG tanpa height eksplisit supaya penuh ke
    seluruh ruang vertikal ANCESTOR yang punya height eksplisit gede, walau kontennya cuma
    2-3 baris — height eksplisit di sini (dan di <table> kartu itu sendiri) MEMATAHKAN
    peregangan itu, kartu kembali sepadat kontennya."""
    col_w = round(100 / cols, 3)
    height_style = f"height:{row_height};" if row_height else ""
    cells = [f'<td style="width:{col_w}%;padding:6px;vertical-align:top;{height_style}">{inner}</td>' for inner in cell_inner_htmls]
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
    card_height = "1.3in"
    cell_htmls = [
        f'<table style="width:100%;height:{card_height};background:{bg};border:1px solid {GOLD_MAIN};border-radius:10px;" cellpadding="14"><tr><td style="text-align:center;vertical-align:middle;">'
        f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:22pt;color:{GOLD_MAIN};">{_esc(value)}</div>'
        f'<div style="font-size:9pt;color:{label_color};margin-top:6px;">{_esc(label)}</div>'
        f'</td></tr></table>'
        for value, label in items
    ]
    return _card_grid(cell_htmls, cols, row_height=card_height)


def _asset_card_row(items) -> str:
    n = len(items) or 1
    card_height = "2.6in"
    cell_htmls = [
        f'<table style="width:100%;height:{card_height};background:{GREEN_MAIN};border:1px solid {GOLD_MAIN};border-radius:10px;" cellpadding="16"><tr><td style="vertical-align:top;">'
        f'{_badge(num, GOLD_MAIN, size="34px", font_size="13pt")}'
        f'<div style="font-weight:700;font-size:12.5pt;color:#fff;margin-top:12px;">{_esc(title)}</div>'
        f'<div style="font-weight:700;font-size:10.5pt;color:{GOLD_MAIN};margin-top:4px;">{_esc(stat)}</div>'
        f'<div style="font-size:9pt;color:#E8ECE6;margin-top:10px;">{_esc(desc)}</div>'
        f'</td></tr></table>'
        for num, title, stat, desc in items
    ]
    return _card_grid(cell_htmls, n, row_height=card_height)


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
    # height eksplisit di <table>, <tr> header, DAN tiap <tr> baris data — lihat catatan di
    # _card_grid soal kenapa ini WAJIB di dalam halaman yang latarnya dipaksa penuh 1 halaman
    # (_page()): tanpanya xhtml2pdf meregangkan SETIAP baris tabel supaya total tabel penuh
    # ke sisa tinggi halaman, walau isi barisnya cuma 1 baris teks pendek.
    row_h = 26
    header_h = 24
    total_h = header_h + row_h * len(rows)
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
        trows.append(f'<tr style="background:{row_bg};height:{row_h}pt;">{"".join(cells)}</tr>')
    return (
        f'<table style="width:100%;height:{total_h}pt;border-collapse:collapse;font-family:{BODY_FONT};" cellpadding="0" cellspacing="0">'
        f'<thead><tr style="height:{header_h}pt;">{thead}</tr></thead><tbody>{"".join(trows)}</tbody></table>'
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
    logo_html = (
        f'<img src="data:image/png;base64,{logo_b64}" style="position:absolute;top:0.3in;right:0.3in;height:34px;" />'
        if logo_b64 else ""
    )
    footer_html = ""
    if page_num is not None:
        footer_html = (
            f'<div style="position:absolute;bottom:0.3in;right:0.3in;font-size:8pt;color:{GRAY_TEXT if not dark else GOLD_LIGHT};'
            f'font-family:{BODY_FONT};">{page_num:02d} / {total_pages:02d}</div>'
        )
    # DUA bug xhtml2pdf yang ditemukan & dihindari di sini (dibuktikan lewat isolasi test
    # render+sampling langsung, bukan cuma baca dokumentasi):
    # 1. @page {margin: ...} TIDAK dihormati untuk sisi kanan/bawah kalau kontennya <table
    #    width:100%> — kiri/atas benar mengikuti margin, tapi kanan/bawah tetap nempel ke
    #    tepi kertas fisik apa pun nilai marginnya (shorthand maupun longhand sama-sama kena).
    # 2. CSS "padding" (properti, bukan atribut) pada <td>/<table> DIGANDAKAN 2x oleh
    #    xhtml2pdf — padding:0.5in dirender setara ~1in. Atribut HTML "cellpadding=N" TIDAK
    #    kena bug ini (dipakai di helper lain sepanjang file ini, aman).
    #
    # SOLUSI: @page tidak lagi menanggung margin (size doang, margin:0) — <td> latar
    # belakang dibuat PERSIS ukuran fisik kertas penuh (full-bleed, seperti slide PPTX yang
    # backgroundnya juga penuh 1 slide), lalu inset konten dari tepi dilakukan lewat MARGIN
    # (bukan padding) pada div pembungkus BIASA di dalamnya — margin pada div terbukti TIDAK
    # kena bug penggandaan di atas. Elemen dekoratif (flourish sudut, logo, nomor halaman)
    # sengaja DILUAR div inset ini, tetap dekat tepi fisik kertas asli (mis. logo pojok,
    # bukan mundur dua kali dari marginnya sendiri).
    return (
        f'<table style="width:13.333in;{break_style}" cellpadding="0" cellspacing="0">'
        f'<tr><td style="position:relative;background:{bg};color:{color};height:7.5in;vertical-align:top;'
        f'font-family:{BODY_FONT};">'
        f'{flourish_html}{logo_html}'
        f'<div style="margin:0.5in;">{inner_html}</div>'
        f'{footer_html}</td></tr></table>'
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
        blocks = build_report_blocks(report)

        rnd = random.Random()
        stat_cols = rnd.choice([2, 3])
        card_cols = rnd.choice([2, 3])
        flourish_corner = rnd.choice(["bottom_right", "top_right", "bottom_left"])
        if is_english(report):
            kicker_ringkasan = rnd.choice(["EXECUTIVE SUMMARY", "KEY SNAPSHOT", "EXECUTIVE OVERVIEW"])
            kicker_analisis = rnd.choice(["DATA ANALYSIS", "DATA REVIEW", "FINDINGS ANALYSIS"])
        else:
            kicker_ringkasan = rnd.choice(["RINGKASAN EKSEKUTIF", "SNAPSHOT UTAMA", "IKHTISAR EKSEKUTIF"])
            kicker_analisis = rnd.choice(["ANALISIS DATA", "TINJAUAN DATA", "ANALISIS TEMUAN"])

        pages = []  # list of (html, dark, flourish, is_last)

        for block in blocks:
            kind = block["kind"]

            if kind == "cover":
                inner = (
                    f'<div style="margin-top:1.6in;">'
                    f'{_kicker(block["kicker"], GOLD_MAIN)}'
                    f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:34pt;color:#fff;margin-bottom:10px;">{_esc(block["title"])}</div>'
                    f'<div style="font-size:12.5pt;color:#fff;margin-bottom:20px;">{_esc(block["subtitle"])}</div>'
                    f'<div style="font-size:10.5pt;color:#fff;">{_esc(block["period_label"])} {_esc(block["period_text"])}</div>'
                    f'<div style="font-size:10.5pt;color:{GOLD_LIGHT};margin-top:6px;">{_esc(block["info_line"])}</div>'
                    f'</div>'
                    f'<div style="position:absolute;bottom:0;left:0;font-size:9pt;font-weight:700;color:#fff;">{_esc(block["header_title"])}</div>'
                )
                pages.append((inner, True, flourish_corner, False))

            elif kind == "intro":
                objectives_html = "".join([
                    _badge_row(o["num"], o["title"], o["detail"], GREEN_MAIN) for o in block["objectives"]
                ])
                scope = block["scope"]
                scope_rows = _ivory_kv_rows([
                    (scope["period_label"], scope["period_text"]),
                    (scope["total_event_label"], scope["total_records_text"]),
                    (scope["source_file_label"], scope["input_file_name"]),
                    (scope["data_type_label_label"], scope["data_type_label"]),
                ])
                scope_panel = _ivory_panel("i", scope["panel_title"], scope_rows, footnote=scope["footnote"], content_rows=4)
                bg_left = f'<div style="font-size:11pt;color:{GRAY_TEXT};margin-bottom:18px;">{block["purpose_text"]}</div>{objectives_html}'
                inner = (
                    _kicker(block["kicker"], GREEN_MAIN) + _title(block["title"]) +
                    _two_col(bg_left, scope_panel, left_pct=58)
                )
                pages.append((inner, False, None, False))

            elif kind == "executive_summary":
                inner = (
                    _kicker(kicker_ringkasan, GOLD_MAIN) +
                    f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:20pt;color:#fff;margin-bottom:18px;">{_esc(block["heading"])}</div>' +
                    _stat_card_grid(block["stat_items"], cols=stat_cols, dark=True) +
                    f'<div style="font-size:10.5pt;font-style:italic;color:{GOLD_LIGHT};margin-top:18px;">{_esc(block["caption"])}</div>'
                )
                pages.append((inner, True, None, False))

            elif kind == "dynamic_section":
                text_html = f'<div style="font-size:11.5pt;color:{GRAY_TEXT};">{_esc(block["text"])}</div>'
                if block.get("aux_stat"):
                    value, label = block["aux_stat"]
                    panel_html = _critical_highlight_panel(value, label)
                    body = _two_col(text_html, panel_html, left_pct=62)
                elif block.get("aux_list"):
                    rows_html = _ivory_kv_rows([(it["label"], it["value"]) for it in block["aux_list"]])
                    panel_title = "Data Highlight" if is_english(report) else "Sorotan Data"
                    panel_html = _ivory_panel("i", panel_title, rows_html, content_rows=len(block["aux_list"]))
                    body = _two_col(text_html, panel_html, left_pct=62)
                else:
                    body = text_html
                inner = _kicker(block["kicker"], GREEN_MAIN) + _title(block["title"]) + body
                pages.append((inner, False, None, False))

            elif kind == "category_distribution":
                legend = _legend_rows([
                    (CATEGORY_COLOR_RAMP[l["color_index"]], l["name"], f"{l['pct']}%") for l in block["legend"]
                ])
                legend_panel = _ivory_panel("%", block["legend_panel_title"], legend, footnote=block["footnote"], content_rows=len(block["legend"]))
                chart_html = _bar_chart_html(block["categories"], block["values"])
                caption_html = _ai_insight_strip(block["ai_caption"]) if block.get("ai_caption") else ""
                inner = (
                    _kicker(kicker_analisis, GREEN_MAIN) + _title(block["title"]) +
                    f'<div style="font-size:11pt;color:{GRAY_TEXT};margin-bottom:16px;">{_esc(block["intro"])}</div>' +
                    _two_col(chart_html, legend_panel, left_pct=58) + caption_html
                )
                pages.append((inner, False, None, False))

            elif kind == "severity_distribution":
                sev_colors = [SEVERITY_COLOR[k] for k in block["severity_keys"]]
                chart_html = _bar_chart_html(block["categories"], block["values"], colors=sev_colors)
                panel = _critical_highlight_panel(f'{block["crit_pct"]}%', block["panel_text"], block["detail_text"])
                caption_html = _ai_insight_strip(block["ai_caption"]) if block.get("ai_caption") else ""
                inner = (
                    _kicker(kicker_analisis, GREEN_MAIN) + _title(block["title"]) +
                    f'<div style="font-size:11pt;color:{GRAY_TEXT};margin-bottom:16px;">{_esc(block["intro"])}</div>' +
                    _two_col(chart_html, panel, left_pct=62) + caption_html
                )
                pages.append((inner, False, None, False))

            elif kind == "status_distribution":
                chart_html = _bar_chart_html(block["categories"], block["values"])
                caption_html = _ai_insight_strip(block["ai_caption"]) if block.get("ai_caption") else ""
                inner = (
                    _kicker(kicker_analisis, GREEN_MAIN) + _title(block["title"]) +
                    f'<div style="font-size:11pt;color:{GRAY_TEXT};margin-bottom:16px;">{_esc(block["intro"])}</div>' + chart_html + caption_html
                )
                pages.append((inner, False, None, False))

            elif kind == "critical_table":
                table_html = _critical_table(block["headers"], block["rows"], set(block["highlight_idx"]))
                caption_html = ""
                if block["caption"]:
                    caption_html = (
                        f'<div style="font-size:9.5pt;font-style:italic;color:{GRAY_TEXT};margin-top:12px;">'
                        f'{_esc(block["caption"])}</div>'
                    )
                kicker_color = RED_CRIT if block["kicker_is_critical"] else GREEN_MAIN
                inner = (
                    _kicker(block["kicker"], kicker_color) + _title(block["title"]) +
                    table_html + caption_html
                )
                pages.append((inner, False, None, False))

            elif kind == "asset_cards":
                card_items = [(it["num"], it["name"], it["stat"], it["detail"]) for it in block["items"]]
                inner = (
                    _kicker(block["kicker"], GOLD_MAIN) +
                    f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:20pt;color:#fff;margin-bottom:18px;">{_esc(block["title"])}</div>' +
                    _asset_card_row(card_items)
                )
                pages.append((inner, True, None, False))

            elif kind == "key_findings":
                findings_html_parts = [
                    _badge_row(it["num"], it["title"], it["detail"], RED_CRIT if it["is_critical"] else GREEN_MAIN)
                    for it in block["items"]
                ]
                inner = _kicker(block["kicker"], GREEN_MAIN) + _title(block["title"]) + "".join(findings_html_parts)
                pages.append((inner, False, None, False))

            elif kind == "recommendations":
                # height eksplisit WAJIB di sini juga (lihat docstring _card_grid) — tanpanya
                # xhtml2pdf meregangkan kartu rekomendasi penuh 1 halaman walau isinya cuma
                # judul+2 baris detail.
                rec_card_height = "2.4in"
                cell_htmls = []
                for it in block["items"]:
                    detail_html = f'<div style="font-size:9.5pt;color:{GRAY_TEXT};margin-top:6px;">{_esc(it["detail"])}</div>' if it["detail"] else ""
                    cell_htmls.append(
                        f'<table style="width:100%;height:{rec_card_height};background:{IVORY};border:1px solid {PANEL_BORDER};border-radius:10px;" cellpadding="14"><tr><td style="vertical-align:top;">'
                        f'{_badge(it["num"], GOLD_MAIN, size="28px")}'
                        f'<div style="font-weight:700;font-size:11pt;color:{TEXT_DARK};margin-top:10px;">{_esc(it["title"])}</div>'
                        f'{detail_html}</td></tr></table>'
                    )
                inner = _kicker(block["kicker"], GREEN_MAIN) + _title(block["title"]) + _card_grid(cell_htmls, card_cols, row_height=rec_card_height)
                pages.append((inner, False, None, False))

            elif kind == "conclusion":
                pills_html = "".join(_pill(p) for p in block["pills"])
                priority_items = [(p["letter"], p["text"]) for p in block["priority_items"]]
                priority_html = _priority_panel(block["priority_panel_title"], priority_items) if priority_items else ""
                concl_left = (
                    f'<div style="font-size:11pt;color:#E8ECE6;margin-bottom:18px;">{_esc(block["text"])}</div>'
                    f'{pills_html}'
                )
                inner = (
                    _kicker(block["kicker"], GOLD_MAIN) +
                    f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:20pt;color:#fff;margin-bottom:16px;">{_esc(block["title"])}</div>' +
                    _two_col(concl_left, priority_html, left_pct=58)
                )
                pages.append((inner, True, None, False))

            elif kind == "closing":
                inner = (
                    f'<div style="margin-top:1.6in;">'
                    f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:30pt;color:#fff;margin-bottom:10px;">{_esc(block["thank_you"])}</div>'
                    f'<div style="font-size:12pt;color:#fff;margin-bottom:8px;">{_esc(block["title"])}</div>'
                    f'<div style="font-size:10.5pt;font-style:italic;color:{GOLD_LIGHT};">{_esc(block["note"])}</div>'
                    f'</div>'
                )
                pages.append((inner, True, flourish_corner, True))

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
                @page {{ size: 13.333in 7.5in; margin: 0; }}
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
