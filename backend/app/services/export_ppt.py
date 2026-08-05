# backend/app/services/export_ppt.py
"""
Rombak total (ganti gaya lama sepenuhnya): palet hijau/emas PT Petrokimia Gresik, font
Bookman Old Style (judul) + Calibri (body), TANPA bullet titik (badge lingkaran nomor/
huruf), TANPA em dash (sanitize_text), TANPA garis aksen/bar dekoratif di judul/kartu/
footer (kecuali ornamen lengkung emas di cover & penutup, itu bukan "garis aksen" yang
dilarang — cuma flourish sudut satu kali). Chart NATIVE python-pptx (bukan gambar PNG dari
Plotly/Kaleido — chart_generator.py TIDAK disentuh/dipakai lagi di sini, statistik chart
diambil LANGSUNG dari compute_statistics()).

Jumlah & kehadiran slide FLEKSIBEL mengikuti data yang benar-benar tersedia (skip aman
kalau kolom terkait tak terdeteksi) — bukan struktur 12-slide yang kaku.

Konten narasi HANYA dari 6 key wajib lama (executive_summary, dst) + key_findings opsional
— SENGAJA TIDAK memakai ai_summary["sections"] (PART A) supaya render ini otomatis
backward & forward compatible tanpa menyentuh fitur section dinamis sama sekali.

Layout divariasikan tiap panggilan generate (posisi panel, jumlah kolom grid, sudut
ornamen) via `random` — supaya laporan tidak identik satu sama lain, tapi tetap dalam
identitas visual (palet/font/makna warna) yang sama.
"""
import math
import os
import random

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE

from app.models.report import Report
from app.services.report_render_logic import build_report_blocks

# ============================================================================
# Palet & font — persis sesuai brief, dipakai di SETIAP elemen (termasuk chart/tabel)
# ============================================================================
GREEN_MAIN = RGBColor(0x1B, 0x5E, 0x3C)
GREEN_BG = RGBColor(0x0E, 0x3B, 0x26)
GREEN_CHART = RGBColor(0x2F, 0x7A, 0x52)
GOLD_MAIN = RGBColor(0xC9, 0xA2, 0x27)
GOLD_LIGHT = RGBColor(0xE7, 0xC7, 0x66)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
IVORY = RGBColor(0xF5, 0xF7, 0xF2)
TEXT_DARK = RGBColor(0x16, 0x24, 0x1C)
GRAY_TEXT = RGBColor(0x5C, 0x6B, 0x62)
RED_CRIT = RGBColor(0xB2, 0x3A, 0x2E)
RED_CRIT_BG = RGBColor(0xF8, 0xE2, 0xDE)
PANEL_BORDER = RGBColor(0xE2, 0xE5, 0xDE)
TITLE_FONT = "Bookman Old Style"
BODY_FONT = "Calibri"

SLIDE_W = Inches(13.33)
SLIDE_H = Inches(7.5)
MARGIN_X = Inches(0.5)
CONTENT_W = SLIDE_W - MARGIN_X * 2

# Warna ramp kategori (dipakai legend panel "% Proporsi Kategori") — nuansa hijau/emas.
CATEGORY_COLOR_RAMP = [GREEN_MAIN, GREEN_CHART, GOLD_MAIN, GOLD_LIGHT, GRAY_TEXT]

# Warna per-level severity (bar chart & badge) — Critical selalu merah, tidak pernah "aman".
SEVERITY_COLOR = {
    "critical": RED_CRIT,
    "high": GOLD_MAIN,
    "medium": GREEN_MAIN,
    "low": GREEN_CHART,
    "informational": GRAY_TEXT,
}
def _resolve_logo_path() -> str | None:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "public"))
    for name in ("LOGO_PETRO_DANANTARA.png", "LOGO_PETRO.png"):
        p = os.path.join(base, name)
        if os.path.exists(p):
            return p
    return None


# ============================================================================
# Helper visual dasar
# ============================================================================
def _set_font(para_or_run, name=BODY_FONT, size=None, bold=None, italic=None, color=None):
    """Terima paragraph ATAU run. Kalau paragraph SUDAH punya run (biasanya karena
    `.text` sudah di-set, jadi ada 1 run implisit), font diterapkan LANGSUNG ke tiap run
    -- bukan cuma default level-paragraf (defRPr) -- supaya font benar-benar tertanam &
    konsisten terbaca (mis. oleh alat verifikasi atau software office lain)."""
    targets = para_or_run.runs if hasattr(para_or_run, "runs") and para_or_run.runs else [para_or_run]
    for t in targets:
        f = t.font
        f.name = name
        if size is not None:
            f.size = size
        if bold is not None:
            f.bold = bold
        if italic is not None:
            f.italic = italic
        if color is not None:
            f.color.rgb = color


def _estimate_wrapped_height_in(text: str, font_pt: float, box_width_in: float) -> float:
    """Estimasi kasar tinggi (inci) yang dipakai `text` kalau word-wrap dalam box selebar
    `box_width_in` pada ukuran `font_pt` — python-pptx bukan mesin render sungguhan (tidak
    tahu lebar karakter asli tiap font), jadi ini estimasi berbasis rata-rata lebar karakter
    huruf tebal (0.6em). Dipakai supaya elemen SETELAH judul (subtitle, info) tidak pernah
    ketimpa kalau judulnya panjang & wrap ke banyak baris — laporan bisa dari domain apa saja
    (SOC, keuangan, KPI, dll) dengan panjang judul yang jauh berbeda-beda, jadi TIDAK BOLEH
    diasumsikan selalu pendek/selalu 1 baris."""
    if not text:
        return font_pt * 1.25 / 72
    avg_char_width_in = (font_pt * 0.6) / 72
    chars_per_line = max(int(box_width_in / avg_char_width_in), 1)
    line_count = max(1, -(-len(text) // chars_per_line))  # ceil division
    return line_count * (font_pt * 1.25) / 72


def _no_shadow(shape):
    try:
        shape.shadow.inherit = False
    except Exception:
        pass


def _send_to_back(slide, shape):
    sp = shape._element
    spTree = slide.shapes._spTree
    spTree.remove(sp)
    spTree.insert(2, sp)


def add_dark_bg(slide):
    rect = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H)
    rect.fill.solid()
    rect.fill.fore_color.rgb = GREEN_BG
    rect.line.fill.background()
    _no_shadow(rect)
    _send_to_back(slide, rect)
    return rect


def add_corner_flourish(slide, corner: str = "bottom_right"):
    """Ornamen lengkung emas tipis (beberapa lingkaran konsentris tanpa isi, diposisikan
    menjorok keluar sudut) — dipakai HANYA di cover & penutup, mendekati motif referensi."""
    if corner == "bottom_left":
        base_x, base_y = Inches(-0.6), SLIDE_H - Inches(0.8)
    elif corner == "top_right":
        base_x, base_y = SLIDE_W - Inches(0.8), Inches(-0.6)
    else:
        base_x, base_y = SLIDE_W - Inches(0.8), SLIDE_H - Inches(0.8)

    for r in (Inches(1.6), Inches(2.15), Inches(2.7), Inches(3.25)):
        oval = slide.shapes.add_shape(MSO_SHAPE.OVAL, base_x - r, base_y - r, r * 2, r * 2)
        oval.fill.background()
        oval.line.color.rgb = GOLD_MAIN
        oval.line.width = Pt(0.75)
        _no_shadow(oval)


def add_kicker(slide, text: str, color=GREEN_MAIN, x=MARGIN_X, y=Inches(0.35), w=Inches(9)):
    box = slide.shapes.add_textbox(x, y, w, Inches(0.3))
    p = box.text_frame.paragraphs[0]
    p.text = text.upper()
    _set_font(p, BODY_FONT, Pt(11), bold=True, color=color)
    return box


def add_title(slide, text: str, color=TEXT_DARK, x=MARGIN_X, y=Inches(0.68), w=Inches(11.5), size=Pt(30)):
    box = slide.shapes.add_textbox(x, y, w, Inches(0.75))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    _set_font(p, TITLE_FONT, size, bold=True, color=color)
    return box


def add_footer(slide, page_num: int, total_pages: int):
    box = slide.shapes.add_textbox(MARGIN_X, SLIDE_H - Inches(0.42), CONTENT_W, Inches(0.3))
    p = box.text_frame.paragraphs[0]
    p.text = f"{page_num:02d} / {total_pages:02d}"
    p.alignment = PP_ALIGN.RIGHT
    _set_font(p, BODY_FONT, Pt(9), color=GRAY_TEXT)


def add_logo(slide, logo_path, x=None, y=Inches(0.25), width=Inches(1.3)):
    if not logo_path:
        return
    x = x if x is not None else (SLIDE_W - width - Inches(0.35))
    try:
        slide.shapes.add_picture(logo_path, x, y, width=width)
    except Exception:
        pass


def add_badge_circle(slide, x, y, diameter, text, badge_color, text_color=WHITE, font_size=Pt(14)):
    circle = slide.shapes.add_shape(MSO_SHAPE.OVAL, x, y, diameter, diameter)
    circle.fill.solid()
    circle.fill.fore_color.rgb = badge_color
    circle.line.fill.background()
    _no_shadow(circle)
    tf = circle.text_frame
    tf.word_wrap = False
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.text = str(text)
    p.alignment = PP_ALIGN.CENTER
    _set_font(p, BODY_FONT, font_size, bold=True, color=text_color)
    return circle


def add_badge_row(slide, x, y, w, number_text, title_text, detail_text, badge_color,
                   badge_d=Inches(0.42), on_dark=False, title_size=Pt(15), detail_size=Pt(12)):
    add_badge_circle(slide, x, y, badge_d, number_text, badge_color, font_size=Pt(14))
    text_x = x + badge_d + Inches(0.2)
    text_w = w - badge_d - Inches(0.2)
    box = slide.shapes.add_textbox(text_x, y - Inches(0.03), text_w, Inches(0.95))
    tf = box.text_frame
    tf.word_wrap = True
    p1 = tf.paragraphs[0]
    p1.text = title_text
    _set_font(p1, BODY_FONT, title_size, bold=True, color=(WHITE if on_dark else TEXT_DARK))
    if detail_text:
        p2 = tf.add_paragraph()
        p2.text = detail_text
        _set_font(p2, BODY_FONT, detail_size, color=(GOLD_LIGHT if on_dark else GRAY_TEXT))
        p2.space_before = Pt(2)
    return box


def add_badge_list(slide, x, y, w, items, badge_color=GREEN_MAIN, row_h=Inches(0.95), on_dark=False):
    """items: list of (number_or_letter, title, detail). badge_color: RGBColor tetap ATAU
    fungsi(idx, item)->RGBColor supaya bisa mem-variasi warna (mis. merah utk 1 item kritis)."""
    cur_y = y
    for idx, item in enumerate(items):
        color = badge_color(idx, item) if callable(badge_color) else badge_color
        add_badge_row(slide, x, cur_y, w, item[0], item[1], item[2], color, on_dark=on_dark)
        cur_y += row_h
    return cur_y


def add_stat_card_grid(slide, x, y, w, h, items, cols=3, dark=True):
    """items: list of (value_str, label_str)."""
    if not items:
        return y
    rows = math.ceil(len(items) / cols)
    gap = Inches(0.2)
    card_w = (w - gap * (cols - 1)) / cols
    card_h = (h - gap * (rows - 1)) / rows
    for idx, (value, label) in enumerate(items):
        r, c = idx // cols, idx % cols
        cx = x + c * (card_w + gap)
        cy = y + r * (card_h + gap)
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, cy, card_w, card_h)
        card.fill.solid()
        card.fill.fore_color.rgb = GREEN_MAIN if dark else IVORY
        card.line.color.rgb = GOLD_MAIN
        card.line.width = Pt(0.75)
        _no_shadow(card)
        tf = card.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.word_wrap = True
        p1 = tf.paragraphs[0]
        p1.text = str(value)
        p1.alignment = PP_ALIGN.CENTER
        _set_font(p1, TITLE_FONT, Pt(32), bold=True, color=GOLD_MAIN if dark else GREEN_MAIN)
        p2 = tf.add_paragraph()
        p2.text = label
        p2.alignment = PP_ALIGN.CENTER
        _set_font(p2, BODY_FONT, Pt(11.5), color=WHITE if dark else TEXT_DARK)
        p2.space_before = Pt(6)
    return y + rows * card_h + (rows - 1) * gap


def add_ivory_panel(slide, x, y, w, h, icon_text, title_text, rows, mode="kv", footnote=None):
    """mode="kv": rows = [(label, value), ...]. mode="legend": rows = [(color, label, pct), ...]."""
    panel = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    panel.fill.solid()
    panel.fill.fore_color.rgb = IVORY
    panel.line.color.rgb = PANEL_BORDER
    panel.line.width = Pt(0.75)
    _no_shadow(panel)

    pad = Inches(0.25)
    inner_x = x + pad
    inner_w = w - pad * 2
    cur_y = y + Inches(0.22)

    add_badge_circle(slide, inner_x, cur_y, Inches(0.32), icon_text, GOLD_MAIN, font_size=Pt(11))
    title_box = slide.shapes.add_textbox(inner_x + Inches(0.45), cur_y + Inches(0.02), inner_w - Inches(0.45), Inches(0.32))
    tp = title_box.text_frame.paragraphs[0]
    tp.text = title_text.upper()
    _set_font(tp, BODY_FONT, Pt(11.5), bold=True, color=GREEN_MAIN)
    cur_y += Inches(0.55)

    if mode == "kv":
        for label, value in rows:
            lbl_box = slide.shapes.add_textbox(inner_x, cur_y, inner_w, Inches(0.24))
            lp = lbl_box.text_frame.paragraphs[0]
            lp.text = label
            _set_font(lp, BODY_FONT, Pt(10.5), bold=True, color=GREEN_MAIN)
            val_box = slide.shapes.add_textbox(inner_x, cur_y + Inches(0.22), inner_w, Inches(0.42))
            vtf = val_box.text_frame
            vtf.word_wrap = True
            vp = vtf.paragraphs[0]
            vp.text = str(value)
            _set_font(vp, BODY_FONT, Pt(10.5), color=GRAY_TEXT)
            cur_y += Inches(0.62)
    else:
        for color, label, pct in rows:
            sw = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, inner_x, cur_y + Inches(0.03), Inches(0.14), Inches(0.14))
            sw.fill.solid()
            sw.fill.fore_color.rgb = color
            sw.line.fill.background()
            _no_shadow(sw)
            lbl_box = slide.shapes.add_textbox(inner_x + Inches(0.22), cur_y, inner_w - Inches(1.0), Inches(0.28))
            lp = lbl_box.text_frame.paragraphs[0]
            lp.text = label
            _set_font(lp, BODY_FONT, Pt(11), color=TEXT_DARK)
            val_box = slide.shapes.add_textbox(inner_x + inner_w - Inches(0.8), cur_y, Inches(0.8), Inches(0.28))
            vp = val_box.text_frame.paragraphs[0]
            vp.text = pct
            vp.alignment = PP_ALIGN.RIGHT
            _set_font(vp, BODY_FONT, Pt(11), bold=True, color=GREEN_MAIN)
            cur_y += Inches(0.34)

    if footnote:
        cur_y += Inches(0.12)
        divider = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, inner_x, cur_y, inner_w, Pt(0.75))
        divider.fill.solid()
        divider.fill.fore_color.rgb = PANEL_BORDER
        divider.line.fill.background()
        _no_shadow(divider)
        cur_y += Inches(0.16)
        fn_box = slide.shapes.add_textbox(inner_x, cur_y, inner_w, max(y + h - cur_y - Inches(0.1), Inches(0.3)))
        ftf = fn_box.text_frame
        ftf.word_wrap = True
        fp = ftf.paragraphs[0]
        fp.text = footnote
        _set_font(fp, BODY_FONT, Pt(9.5), italic=True, color=GRAY_TEXT)
    return panel


def add_dark_panel(slide, x, y, w, h):
    panel = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    panel.fill.solid()
    panel.fill.fore_color.rgb = GREEN_BG
    panel.line.color.rgb = GOLD_MAIN
    panel.line.width = Pt(1)
    _no_shadow(panel)
    return panel


def add_critical_highlight_panel(slide, x, y, w, h, pct_text, sub_text, detail_text=None):
    add_dark_panel(slide, x, y, w, h)
    pad = Inches(0.3)
    big_box = slide.shapes.add_textbox(x + pad, y + Inches(0.35), w - pad * 2, Inches(1.0))
    bp = big_box.text_frame.paragraphs[0]
    bp.text = pct_text
    bp.alignment = PP_ALIGN.CENTER
    _set_font(bp, TITLE_FONT, Pt(42), bold=True, color=GOLD_MAIN)

    sub_box = slide.shapes.add_textbox(x + pad, y + Inches(1.35), w - pad * 2, Inches(0.7))
    stf = sub_box.text_frame
    stf.word_wrap = True
    sp = stf.paragraphs[0]
    sp.text = sub_text
    sp.alignment = PP_ALIGN.CENTER
    _set_font(sp, BODY_FONT, Pt(12.5), color=WHITE)

    if detail_text:
        det_box = slide.shapes.add_textbox(x + pad, y + Inches(2.15), w - pad * 2, h - Inches(2.15) - Inches(0.25))
        dtf = det_box.text_frame
        dtf.word_wrap = True
        dp = dtf.paragraphs[0]
        dp.text = detail_text
        _set_font(dp, BODY_FONT, Pt(10.5), color=GOLD_LIGHT)


def add_priority_panel(slide, x, y, w, h, title_text, items):
    """items: list of (letter, text)."""
    add_dark_panel(slide, x, y, w, h)
    pad = Inches(0.28)
    title_box = slide.shapes.add_textbox(x + pad, y + Inches(0.22), w - pad * 2, Inches(0.32))
    tp = title_box.text_frame.paragraphs[0]
    tp.text = title_text.upper()
    _set_font(tp, BODY_FONT, Pt(11.5), bold=True, color=GOLD_MAIN)
    cur_y = y + Inches(0.7)
    for letter, text in items:
        add_badge_circle(slide, x + pad, cur_y, Inches(0.36), letter, GOLD_MAIN, font_size=Pt(13))
        box = slide.shapes.add_textbox(x + pad + Inches(0.5), cur_y + Inches(0.02), w - pad * 2 - Inches(0.5), Inches(0.55))
        btf = box.text_frame
        btf.word_wrap = True
        bp = btf.paragraphs[0]
        bp.text = text
        _set_font(bp, BODY_FONT, Pt(12), color=WHITE)
        cur_y += Inches(0.62)


def add_pill_stat(slide, x, y, w, h, text):
    pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    try:
        pill.adjustments[0] = 0.5
    except Exception:
        pass
    pill.fill.solid()
    pill.fill.fore_color.rgb = GREEN_MAIN
    pill.line.color.rgb = GOLD_MAIN
    pill.line.width = Pt(1)
    _no_shadow(pill)
    tf = pill.text_frame
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.text = text
    p.alignment = PP_ALIGN.CENTER
    _set_font(p, BODY_FONT, Pt(13), bold=True, color=GOLD_MAIN)


def add_asset_card_row(slide, x, y, w, h, items):
    """items: list of (badge_num, title, stat_text, desc_text)."""
    n = len(items)
    if n == 0:
        return
    gap = Inches(0.25)
    card_w = (w - gap * (n - 1)) / n
    for idx, (num, title, stat, desc) in enumerate(items):
        cx = x + idx * (card_w + gap)
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, y, card_w, h)
        card.fill.solid()
        card.fill.fore_color.rgb = GREEN_MAIN
        card.line.color.rgb = GOLD_MAIN
        card.line.width = Pt(0.75)
        _no_shadow(card)
        pad = Inches(0.22)
        add_badge_circle(slide, cx + pad, y + pad, Inches(0.42), num, GOLD_MAIN, font_size=Pt(15))
        title_box = slide.shapes.add_textbox(cx + pad, y + pad + Inches(0.55), card_w - pad * 2, Inches(0.55))
        ttf = title_box.text_frame
        ttf.word_wrap = True
        tp = ttf.paragraphs[0]
        tp.text = title
        _set_font(tp, BODY_FONT, Pt(15), bold=True, color=WHITE)
        stat_box = slide.shapes.add_textbox(cx + pad, y + pad + Inches(1.1), card_w - pad * 2, Inches(0.35))
        sp = stat_box.text_frame.paragraphs[0]
        sp.text = stat
        _set_font(sp, BODY_FONT, Pt(13), bold=True, color=GOLD_MAIN)
        desc_box = slide.shapes.add_textbox(cx + pad, y + pad + Inches(1.55), card_w - pad * 2, h - Inches(1.55) - pad * 2)
        dtf = desc_box.text_frame
        dtf.word_wrap = True
        dp = dtf.paragraphs[0]
        dp.text = desc
        _set_font(dp, BODY_FONT, Pt(10.5), color=RGBColor(0xE8, 0xEC, 0xE6))


def add_native_bar_chart(slide, x, y, cx, cy, categories, values, colors=None, horizontal=False):
    chart_data = CategoryChartData()
    chart_data.categories = categories
    chart_data.add_series("Jumlah", values)
    chart_type = XL_CHART_TYPE.BAR_CLUSTERED if horizontal else XL_CHART_TYPE.COLUMN_CLUSTERED
    gframe = slide.shapes.add_chart(chart_type, x, y, cx, cy, chart_data)
    chart = gframe.chart
    chart.has_legend = False

    plot = chart.plots[0]
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.font.size = Pt(11)
    dl.font.name = BODY_FONT
    dl.font.bold = True
    try:
        dl.number_format = "0"
        dl.number_format_is_linked = False
    except Exception:
        pass

    series = plot.series[0]
    if colors:
        for i, pt in enumerate(series.points):
            pt.format.fill.solid()
            pt.format.fill.fore_color.rgb = colors[i % len(colors)]
    else:
        series.format.fill.solid()
        series.format.fill.fore_color.rgb = GREEN_MAIN

    try:
        chart.category_axis.has_major_gridlines = False
        chart.value_axis.has_major_gridlines = False
        chart.category_axis.tick_labels.font.size = Pt(11)
        chart.category_axis.tick_labels.font.name = BODY_FONT
        chart.value_axis.visible = False
    except Exception:
        pass
    return gframe


def add_native_table(slide, x, y, w, h, headers, rows, highlight_indices=None):
    highlight_indices = highlight_indices or set()
    n_rows = len(rows) + 1
    n_cols = len(headers)
    gframe = slide.shapes.add_table(n_rows, n_cols, x, y, w, h)
    table = gframe.table

    for c, htext in enumerate(headers):
        cell = table.cell(0, c)
        cell.fill.solid()
        cell.fill.fore_color.rgb = GREEN_BG
        cell.margin_left = cell.margin_right = Inches(0.08)
        p = cell.text_frame.paragraphs[0]
        p.text = htext
        _set_font(p, BODY_FONT, Pt(11), bold=True, color=WHITE)

    for r, row_vals in enumerate(rows):
        is_open = r in highlight_indices
        for c, val in enumerate(row_vals):
            cell = table.cell(r + 1, c)
            cell.fill.solid()
            cell.fill.fore_color.rgb = RED_CRIT_BG if is_open else (IVORY if r % 2 == 0 else WHITE)
            cell.margin_left = cell.margin_right = Inches(0.08)
            p = cell.text_frame.paragraphs[0]
            p.text = str(val)
            is_status_col = c == n_cols - 1
            _set_font(
                p, BODY_FONT, Pt(10.5),
                bold=bool(is_open and is_status_col),
                color=(RED_CRIT if (is_open and is_status_col) else TEXT_DARK),
            )
    return gframe


# ============================================================================
# Konten turunan dari data (bukan dari AI) — deterministik
# ============================================================================


class PPTXExporter:
    @classmethod
    def generate_ppt_report(cls, report: Report) -> bytes:
        prs = Presentation()
        prs.slide_width = SLIDE_W
        prs.slide_height = SLIDE_H

        logo_path = _resolve_logo_path()
        blocks = build_report_blocks(report)

        # --- Variasi layout antar generate (identitas visual sama, tata letak beda) ---
        rnd = random.Random()
        panel_side = rnd.choice(["left", "right"])
        stat_cols = rnd.choice([2, 3])
        card_cols = rnd.choice([2, 3])
        flourish_corner = rnd.choice(["bottom_right", "top_right", "bottom_left"])
        kicker_ringkasan = rnd.choice(["RINGKASAN EKSEKUTIF", "SNAPSHOT UTAMA", "IKHTISAR EKSEKUTIF"])
        kicker_analisis = rnd.choice(["ANALISIS DATA", "TINJAUAN DATA", "ANALISIS TEMUAN"])

        content_slides: list = []  # dipakai utk stamping footer di akhir (kecuali cover/penutup)

        for block in blocks:
            kind = block["kind"]

            # ---------------------------------------------------------
            # Slide: Cover
            # ---------------------------------------------------------
            if kind == "cover":
                cover = prs.slides.add_slide(prs.slide_layouts[6])
                add_dark_bg(cover)
                add_corner_flourish(cover, flourish_corner)
                add_logo(cover, logo_path)

                add_kicker(cover, "LAPORAN ANALISIS", color=GOLD_MAIN, y=Inches(1.7))

                # Ukuran font judul menyesuaikan panjangnya (laporan bisa dari domain apa saja
                # - SOC, keuangan, KPI, dll - judulnya bisa jauh lebih panjang/pendek dari
                # contoh mana pun), lalu posisi subtitle & info DIHITUNG dari perkiraan tinggi
                # judul yang sebenarnya — bukan angka tetap — supaya tidak pernah tertimpa
                # berapa pun baris yang dibutuhkan judul untuk wrap.
                title_text = block["title"]
                if len(title_text) > 55:
                    title_size_pt = 26
                elif len(title_text) > 40:
                    title_size_pt = 32
                elif len(title_text) > 28:
                    title_size_pt = 38
                else:
                    title_size_pt = 44

                title_top_in = 2.1
                title_box = cover.shapes.add_textbox(MARGIN_X, Inches(title_top_in), Inches(9.5), Inches(2.4))
                ttf = title_box.text_frame
                ttf.word_wrap = True
                tp = ttf.paragraphs[0]
                tp.text = title_text
                _set_font(tp, TITLE_FONT, Pt(title_size_pt), bold=True, color=WHITE)

                title_height_in = _estimate_wrapped_height_in(title_text, title_size_pt, 9.5)
                sub_top_in = max(title_top_in + title_height_in + 0.15, 3.05)
                sub_box = cover.shapes.add_textbox(MARGIN_X, Inches(sub_top_in), Inches(9.5), Inches(0.5))
                sp = sub_box.text_frame.paragraphs[0]
                sp.text = block["subtitle"]
                _set_font(sp, BODY_FONT, Pt(15), color=WHITE)

                info_top_in = max(sub_top_in + 0.65, 3.9)
                info_box = cover.shapes.add_textbox(MARGIN_X, Inches(info_top_in), Inches(9.5), Inches(0.9))
                itf = info_box.text_frame
                itf.word_wrap = True
                p1 = itf.paragraphs[0]
                p1.text = f'Periode data. {block["period_text"]}'
                _set_font(p1, BODY_FONT, Pt(12.5), color=WHITE)
                p2 = itf.add_paragraph()
                p2.text = f'{block["total_records"]} entri log, {block["category_count"]} kategori kejadian, {block["critical_count"]} insiden Critical'
                _set_font(p2, BODY_FONT, Pt(12.5), color=GOLD_LIGHT)
                p2.space_before = Pt(6)

                footer_l = cover.shapes.add_textbox(MARGIN_X, SLIDE_H - Inches(0.55), Inches(5), Inches(0.3))
                flp = footer_l.text_frame.paragraphs[0]
                flp.text = block["header_title"]
                _set_font(flp, BODY_FONT, Pt(10), bold=True, color=WHITE)

            # ---------------------------------------------------------
            # Slide: Latar Belakang & Tujuan
            # ---------------------------------------------------------
            elif kind == "intro":
                bg_slide = prs.slides.add_slide(prs.slide_layouts[6])
                add_logo(bg_slide, logo_path)
                add_kicker(bg_slide, "PENDAHULUAN", color=GREEN_MAIN)
                add_title(bg_slide, "Latar Belakang dan Tujuan Analisis")

                left_w = Inches(7.0) if panel_side == "right" else Inches(4.9)
                left_x = MARGIN_X if panel_side == "right" else MARGIN_X + Inches(4.9) + Inches(0.4)
                panel_x = MARGIN_X + Inches(7.0) + Inches(0.4) if panel_side == "right" else MARGIN_X
                panel_w = Inches(4.9)

                para_box = bg_slide.shapes.add_textbox(left_x, Inches(1.65), left_w, Inches(1.3))
                ptf = para_box.text_frame
                ptf.word_wrap = True
                pp = ptf.paragraphs[0]
                pp.text = block["purpose_text"]
                _set_font(pp, BODY_FONT, Pt(13), color=GRAY_TEXT)

                objectives = [(o["num"], o["title"], o["detail"]) for o in block["objectives"]]
                add_badge_list(bg_slide, left_x, Inches(3.05), left_w, objectives, badge_color=GREEN_MAIN, row_h=Inches(1.05))

                scope = block["scope"]
                scope_rows = [
                    ("Periode", scope["period_text"]),
                    ("Total Event", f"{scope['total_records']} entri log"),
                    ("Sumber Berkas", scope["input_file_name"]),
                    ("Jenis Data", scope["data_type_label"]),
                ]
                add_ivory_panel(
                    bg_slide, panel_x, Inches(1.65), panel_w, Inches(4.3),
                    "i", "Ruang Lingkup Data", scope_rows, mode="kv",
                    footnote="Sumber. Data yang diunggah pengguna, diproses otomatis oleh sistem.",
                )
                content_slides.append(bg_slide)

            # ---------------------------------------------------------
            # Slide: Ringkasan Eksekutif (GELAP)
            # ---------------------------------------------------------
            elif kind == "executive_summary":
                exec_slide = prs.slides.add_slide(prs.slide_layouts[6])
                add_dark_bg(exec_slide)
                add_logo(exec_slide, logo_path)
                add_kicker(exec_slide, kicker_ringkasan, color=GOLD_MAIN)
                add_title(exec_slide, block["heading"], color=WHITE)

                grid_bottom = add_stat_card_grid(exec_slide, MARGIN_X, Inches(1.7), CONTENT_W, Inches(4.3), block["stat_items"], cols=stat_cols, dark=True)

                cap_box = exec_slide.shapes.add_textbox(MARGIN_X, grid_bottom + Inches(0.25), CONTENT_W, Inches(0.9))
                ctf = cap_box.text_frame
                ctf.word_wrap = True
                cp = ctf.paragraphs[0]
                cp.text = block["caption"]
                _set_font(cp, BODY_FONT, Pt(11.5), italic=True, color=GOLD_LIGHT)
                content_slides.append(exec_slide)

            # ---------------------------------------------------------
            # Slide: Distribusi Kategori Event
            # ---------------------------------------------------------
            elif kind == "category_distribution":
                cat_slide = prs.slides.add_slide(prs.slide_layouts[6])
                add_logo(cat_slide, logo_path)
                add_kicker(cat_slide, kicker_analisis, color=GREEN_MAIN)
                add_title(cat_slide, f'Distribusi Event Berdasarkan {block["label"]}')

                intro_box = cat_slide.shapes.add_textbox(MARGIN_X, Inches(1.45), CONTENT_W, Inches(0.5))
                itf2 = intro_box.text_frame
                itf2.word_wrap = True
                ip = itf2.paragraphs[0]
                ip.text = block["intro"]
                _set_font(ip, BODY_FONT, Pt(12), color=GRAY_TEXT)

                chart_w = Inches(7.3) if panel_side == "right" else Inches(4.9)
                chart_x = MARGIN_X if panel_side == "right" else MARGIN_X + Inches(4.9) + Inches(0.4)
                panel_x2 = MARGIN_X + Inches(7.3) + Inches(0.4) if panel_side == "right" else MARGIN_X
                add_native_bar_chart(
                    cat_slide, chart_x, Inches(2.1), chart_w, Inches(4.6),
                    list(reversed(block["categories"])), list(reversed(block["values"])),
                    horizontal=True,
                )
                legend_rows = [
                    (CATEGORY_COLOR_RAMP[l["color_index"]], l["name"], f'{l["pct"]}%')
                    for l in block["legend"]
                ]
                add_ivory_panel(
                    cat_slide, panel_x2, Inches(2.1), Inches(4.9), Inches(4.6),
                    "%", "Proporsi Kategori", legend_rows, mode="legend",
                    footnote=block["footnote"],
                )
                content_slides.append(cat_slide)

            # ---------------------------------------------------------
            # Slide: Distribusi Severity
            # ---------------------------------------------------------
            elif kind == "severity_distribution":
                sev_slide = prs.slides.add_slide(prs.slide_layouts[6])
                add_logo(sev_slide, logo_path)
                add_kicker(sev_slide, kicker_analisis, color=GREEN_MAIN)
                add_title(sev_slide, "Distribusi Tingkat Keparahan (Severity)")

                intro_box = sev_slide.shapes.add_textbox(MARGIN_X, Inches(1.45), CONTENT_W, Inches(0.5))
                itf3 = intro_box.text_frame
                itf3.word_wrap = True
                ip3 = itf3.paragraphs[0]
                ip3.text = block["intro"]
                _set_font(ip3, BODY_FONT, Pt(12), color=GRAY_TEXT)

                sev_colors = [SEVERITY_COLOR[k] for k in block["severity_keys"]]
                add_native_bar_chart(sev_slide, MARGIN_X, Inches(2.1), Inches(8.1), Inches(4.6), block["categories"], block["values"], colors=sev_colors)

                add_critical_highlight_panel(
                    sev_slide, MARGIN_X + Inches(8.5), Inches(2.1), Inches(4.3), Inches(4.6),
                    f'{block["crit_pct"]}%', block["panel_text"], block["detail_text"],
                )
                content_slides.append(sev_slide)

            # ---------------------------------------------------------
            # Slide: Status Penanganan Insiden
            # ---------------------------------------------------------
            elif kind == "status_distribution":
                status_slide = prs.slides.add_slide(prs.slide_layouts[6])
                add_logo(status_slide, logo_path)
                add_kicker(status_slide, kicker_analisis, color=GREEN_MAIN)
                add_title(status_slide, "Status Penanganan Insiden")

                intro_box = status_slide.shapes.add_textbox(MARGIN_X, Inches(1.45), CONTENT_W, Inches(0.5))
                itf4 = intro_box.text_frame
                itf4.word_wrap = True
                ip4 = itf4.paragraphs[0]
                ip4.text = block["intro"]
                _set_font(ip4, BODY_FONT, Pt(12), color=GRAY_TEXT)

                add_native_bar_chart(
                    status_slide, MARGIN_X, Inches(2.1), CONTENT_W, Inches(4.6),
                    block["categories"], block["values"],
                )
                content_slides.append(status_slide)

            # ---------------------------------------------------------
            # Slide: Tabel Insiden Critical/Prioritas Tinggi
            # ---------------------------------------------------------
            elif kind == "critical_table":
                table_slide = prs.slides.add_slide(prs.slide_layouts[6])
                add_logo(table_slide, logo_path)
                kicker_color = RED_CRIT if block["kicker_is_critical"] else GREEN_MAIN
                add_kicker(table_slide, "SOROTAN INSIDEN", color=kicker_color)
                add_title(table_slide, block["title"])

                add_native_table(table_slide, MARGIN_X, Inches(1.55), CONTENT_W, Inches(4.9), block["headers"], block["rows"], set(block["highlight_idx"]))

                if block["caption"]:
                    cap_box = table_slide.shapes.add_textbox(MARGIN_X, Inches(6.55), CONTENT_W, Inches(0.4))
                    cp2 = cap_box.text_frame.paragraphs[0]
                    cp2.text = block["caption"]
                    _set_font(cp2, BODY_FONT, Pt(10.5), italic=True, color=GRAY_TEXT)
                content_slides.append(table_slide)

            # ---------------------------------------------------------
            # Slide: Aset Paling Sering Menjadi Sasaran (GELAP)
            # ---------------------------------------------------------
            elif kind == "asset_cards":
                asset_slide = prs.slides.add_slide(prs.slide_layouts[6])
                add_dark_bg(asset_slide)
                add_logo(asset_slide, logo_path)
                add_kicker(asset_slide, "SOROTAN INSIDEN", color=GOLD_MAIN)
                add_title(asset_slide, block["title"], color=WHITE)

                card_items = [(it["num"], it["name"], it["stat"], it["detail"]) for it in block["items"]]
                add_asset_card_row(asset_slide, MARGIN_X, Inches(1.9), CONTENT_W, Inches(4.6), card_items)
                content_slides.append(asset_slide)

            # ---------------------------------------------------------
            # Slide: Temuan Utama
            # ---------------------------------------------------------
            elif kind == "key_findings":
                find_slide = prs.slides.add_slide(prs.slide_layouts[6])
                add_logo(find_slide, logo_path)
                add_kicker(find_slide, "ANALISIS", color=GREEN_MAIN)
                add_title(find_slide, "Temuan Utama")

                findings_items = [(it["num"], it["title"], it["detail"]) for it in block["items"]]

                def _finding_color(idx, item, _items=block["items"]):
                    return RED_CRIT if _items[idx]["is_critical"] else GREEN_MAIN

                add_badge_list(find_slide, MARGIN_X, Inches(1.7), CONTENT_W, findings_items, badge_color=_finding_color, row_h=Inches(1.0))
                content_slides.append(find_slide)

            # ---------------------------------------------------------
            # Slide: Rekomendasi Mitigasi
            # ---------------------------------------------------------
            elif kind == "recommendations":
                rec_slide = prs.slides.add_slide(prs.slide_layouts[6])
                add_logo(rec_slide, logo_path)
                add_kicker(rec_slide, "TINDAK LANJUT", color=GREEN_MAIN)
                add_title(rec_slide, "Rekomendasi Mitigasi")

                items = block["items"]
                gap = Inches(0.25)
                card_w = (CONTENT_W - gap * (card_cols - 1)) / card_cols
                card_h = Inches(1.3)
                for idx, item in enumerate(items):
                    r, c = idx // card_cols, idx % card_cols
                    cx = MARGIN_X + c * (card_w + gap)
                    cy = Inches(1.7) + r * (card_h + gap)
                    card = rec_slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, cy, card_w, card_h)
                    card.fill.solid()
                    card.fill.fore_color.rgb = IVORY
                    card.line.color.rgb = PANEL_BORDER
                    card.line.width = Pt(0.75)
                    _no_shadow(card)
                    add_badge_circle(rec_slide, cx + Inches(0.2), cy + Inches(0.18), Inches(0.36), item["num"], GOLD_MAIN, font_size=Pt(13))
                    title_box = rec_slide.shapes.add_textbox(cx + Inches(0.2), cy + Inches(0.62), card_w - Inches(0.4), Inches(0.35))
                    ttf2 = title_box.text_frame
                    ttf2.word_wrap = True
                    tp2 = ttf2.paragraphs[0]
                    tp2.text = item["title"]
                    _set_font(tp2, BODY_FONT, Pt(13), bold=True, color=TEXT_DARK)
                    if item["detail"]:
                        det_box = rec_slide.shapes.add_textbox(cx + Inches(0.2), cy + Inches(0.95), card_w - Inches(0.4), card_h - Inches(1.0))
                        dtf2 = det_box.text_frame
                        dtf2.word_wrap = True
                        dp2 = dtf2.paragraphs[0]
                        dp2.text = item["detail"]
                        _set_font(dp2, BODY_FONT, Pt(10.5), color=GRAY_TEXT)
                content_slides.append(rec_slide)

            # ---------------------------------------------------------
            # Slide: Kesimpulan (GELAP)
            # ---------------------------------------------------------
            elif kind == "conclusion":
                concl_slide = prs.slides.add_slide(prs.slide_layouts[6])
                add_dark_bg(concl_slide)
                add_logo(concl_slide, logo_path)
                add_kicker(concl_slide, "PENUTUP", color=GOLD_MAIN)
                add_title(concl_slide, "Kesimpulan", color=WHITE)

                left_w2 = Inches(7.0)
                para_box2 = concl_slide.shapes.add_textbox(MARGIN_X, Inches(1.7), left_w2, Inches(1.8))
                ptf2 = para_box2.text_frame
                ptf2.word_wrap = True
                pp2 = ptf2.paragraphs[0]
                pp2.text = block["text"]
                _set_font(pp2, BODY_FONT, Pt(13), color=RGBColor(0xE8, 0xEC, 0xE6))

                pill_y = Inches(3.7)
                for pill_text in block["pills"][:3]:
                    add_pill_stat(concl_slide, MARGIN_X, pill_y, left_w2, Inches(0.6), pill_text)
                    pill_y += Inches(0.75)

                priority_items = [(p["letter"], p["text"]) for p in block["priority_items"]]
                if priority_items:
                    add_priority_panel(
                        concl_slide, MARGIN_X + left_w2 + Inches(0.4), Inches(1.7), Inches(4.3), Inches(4.6),
                        "Prioritas Berikutnya", priority_items,
                    )
                content_slides.append(concl_slide)

            # ---------------------------------------------------------
            # Slide: Penutup / Terima Kasih
            # ---------------------------------------------------------
            elif kind == "closing":
                closing = prs.slides.add_slide(prs.slide_layouts[6])
                add_dark_bg(closing)
                add_corner_flourish(closing, flourish_corner)
                title_box2 = closing.shapes.add_textbox(MARGIN_X, Inches(3.0), Inches(9), Inches(1.0))
                tp3 = title_box2.text_frame.paragraphs[0]
                tp3.text = "Terima Kasih"
                _set_font(tp3, TITLE_FONT, Pt(40), bold=True, color=WHITE)
                sub2_top_in = 3.85
                sub_box2 = closing.shapes.add_textbox(MARGIN_X, Inches(sub2_top_in), Inches(9), Inches(0.8))
                sp2 = sub_box2.text_frame
                sp2.word_wrap = True
                sp2_p = sp2.paragraphs[0]
                sp2_p.text = block["title"]
                _set_font(sp2_p, BODY_FONT, Pt(14), color=WHITE)

                sub2_height_in = _estimate_wrapped_height_in(block["title"], 14, 9)
                note_top_in = max(sub2_top_in + sub2_height_in + 0.1, 4.4)
                note_box = closing.shapes.add_textbox(MARGIN_X, Inches(note_top_in), Inches(9), Inches(0.4))
                np_ = note_box.text_frame.paragraphs[0]
                np_.text = "Diskusi dan pertanyaan dipersilakan."
                _set_font(np_, BODY_FONT, Pt(11.5), italic=True, color=GOLD_LIGHT)

        # -------------------------------------------------------------
        # Footer: nomor halaman, semua slide isi kecuali cover & penutup
        # -------------------------------------------------------------
        total_pages = len(content_slides)
        for idx, s in enumerate(content_slides):
            add_footer(s, idx + 1, total_pages)

        ppt_io = __import__("io").BytesIO()
        prs.save(ppt_io)
        ppt_io.seek(0)
        return ppt_io.read()


