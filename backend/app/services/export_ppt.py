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
import datetime
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
from app.crud.report import get_parsed_data
from app.services.ai_engine.data_profiler import (
    compute_statistics,
    _classify_severity_value,
)
from app.services.ai_engine.ollama_client import normalize_recommendations, sanitize_text

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
SEVERITY_ORDER = ["critical", "high", "medium", "low", "informational"]
SEVERITY_LABEL = {
    "critical": "Critical", "high": "High", "medium": "Medium",
    "low": "Low", "informational": "Info",
}


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


def _resolve_logo_path() -> str | None:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "public"))
    for name in ("LOGO_PETRO_DANANTARA.png", "LOGO_PETRO.png"):
        p = os.path.join(base, name)
        if os.path.exists(p):
            return p
    return None


def _classify_open_status(value) -> bool | None:
    """True = masih terbuka/belum tuntas, False = sudah tuntas, None = tak bisa diklasifikasi.
    Kosakata status SOC umum (Blocked/Mitigated/Isolated/Resolved/Logged/Quarantined = tuntas;
    Investigating/Open/Pending = masih berjalan)."""
    v = str(value).strip().lower()
    open_kw = ["investigating", "open", "pending", "in progress", "in-progress", "unresolved",
               "belum selesai", "belum ditangani", "menunggu", "baru", "new"]
    closed_kw = ["blocked", "mitigated", "isolated", "resolved", "logged", "quarantined",
                 "closed", "resolved", "selesai", "done", "complete", "completed",
                 "ditutup", "tertangani"]
    if any(kw in v for kw in open_kw):
        return True
    if any(kw in v for kw in closed_kw):
        return False
    return None


def _pick_category(top_categories: dict, preferred: list[str], used: set[str]):
    """Coba tiap label di `preferred` urut, kembalikan (label, items) pertama yang ADA
    isinya & belum dipakai slide lain — else None (slide terkait di-skip dgn fallback aman)."""
    for label in preferred:
        items = top_categories.get(label)
        if items and label not in used:
            used.add(label)
            return label, items
    return None


def _humanize_label(label: str) -> str:
    return label.replace("_", " ").replace("category ", "Kategori ").strip().title()


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
def _build_key_findings(ai_summary: dict, report_stats: dict, open_count: int) -> list[str]:
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


class PPTXExporter:
    @classmethod
    def generate_ppt_report(cls, report: Report) -> bytes:
        prs = Presentation()
        prs.slide_width = SLIDE_W
        prs.slide_height = SLIDE_H

        logo_path = _resolve_logo_path()
        parsed_data = get_parsed_data(report)
        report_stats = compute_statistics(parsed_data, report.data_type) if parsed_data else {"total_records": 0}
        ai_summary = report.ai_summary or {}

        # --- Variasi layout antar generate (identitas visual sama, tata letak beda) ---
        rnd = random.Random()
        panel_side = rnd.choice(["left", "right"])
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

        # Label generik "category_N" penomorannya TERGANTUNG berapa intent bernama lain yang
        # sudah kepakai duluan (mis. bisa jadi "category_3", bukan selalu "category_1") — cari
        # dinamis, jangan hardcode nomor, supaya kolom kategori generik tetap ketemu.
        used_labels: set[str] = set()
        generic_category_keys = sorted(k for k in top_categories if k.startswith("category_"))
        category_pick = _pick_category(
            top_categories, ["action", *generic_category_keys, "location", "destination_port"], used_labels
        )
        asset_pick = _pick_category(
            top_categories, ["asset", "destination_port", "location", *generic_category_keys], used_labels
        )

        # Nama kolom ASLI (bukan label) — dari data_profiler.py langsung, supaya deteksi
        # kolom severity/status/kategori 100% konsisten dgn yang dipakai compute_statistics
        # (tidak menebak ulang dgn logika terpisah yang berisiko beda hasil).
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

        included = report.included_sections or {}

        def is_included(key: str) -> bool:
            if isinstance(included, dict):
                return included.get(key, True)
            if isinstance(included, list):
                for sec in included:
                    if isinstance(sec, dict) and (sec.get("key") == key or sec.get("id") == key):
                        return sec.get("enabled", True)
            return True

        content_slides: list = []  # dipakai utk stamping footer di akhir (kecuali cover/penutup)

        # -------------------------------------------------------------
        # Slide: Cover
        # -------------------------------------------------------------
        cover = prs.slides.add_slide(prs.slide_layouts[6])
        add_dark_bg(cover)
        add_corner_flourish(cover, flourish_corner)
        add_logo(cover, logo_path)

        add_kicker(cover, "LAPORAN ANALISIS", color=GOLD_MAIN, y=Inches(1.7))
        title_box = cover.shapes.add_textbox(MARGIN_X, Inches(2.1), Inches(9.5), Inches(1.3))
        ttf = title_box.text_frame
        ttf.word_wrap = True
        tp = ttf.paragraphs[0]
        tp.text = report.title
        _set_font(tp, TITLE_FONT, Pt(44), bold=True, color=WHITE)

        sub_box = cover.shapes.add_textbox(MARGIN_X, Inches(3.05), Inches(9.5), Inches(0.5))
        sp = sub_box.text_frame.paragraphs[0]
        sp.text = sanitize_text(report.header_subtitle) or "Security Operation Center"
        _set_font(sp, BODY_FONT, Pt(15), color=WHITE)

        period_text = _format_period(report)
        info_box = cover.shapes.add_textbox(MARGIN_X, Inches(3.9), Inches(9.5), Inches(0.9))
        itf = info_box.text_frame
        itf.word_wrap = True
        p1 = itf.paragraphs[0]
        p1.text = f"Periode data. {period_text}"
        _set_font(p1, BODY_FONT, Pt(12.5), color=WHITE)
        p2 = itf.add_paragraph()
        cat_count = len(top_categories)
        crit_count = severity.get("critical", 0)
        p2.text = f"{total_records} entri log, {cat_count} kategori kejadian, {crit_count} insiden Critical"
        _set_font(p2, BODY_FONT, Pt(12.5), color=GOLD_LIGHT)
        p2.space_before = Pt(6)

        footer_l = cover.shapes.add_textbox(MARGIN_X, SLIDE_H - Inches(0.55), Inches(5), Inches(0.3))
        flp = footer_l.text_frame.paragraphs[0]
        flp.text = (report.header_title or "PT PETROKIMIA GRESIK").upper()
        _set_font(flp, BODY_FONT, Pt(10), bold=True, color=WHITE)

        # -------------------------------------------------------------
        # Slide: Latar Belakang & Tujuan
        # -------------------------------------------------------------
        bg_slide = prs.slides.add_slide(prs.slide_layouts[6])
        add_logo(bg_slide, logo_path)
        add_kicker(bg_slide, "PENDAHULUAN", color=GREEN_MAIN)
        add_title(bg_slide, "Latar Belakang dan Tujuan Analisis")

        left_w = Inches(7.0) if panel_side == "right" else Inches(4.9)
        left_x = MARGIN_X if panel_side == "right" else MARGIN_X + Inches(4.9) + Inches(0.4)
        panel_x = MARGIN_X + Inches(7.0) + Inches(0.4) if panel_side == "right" else MARGIN_X
        panel_w = Inches(4.9)

        purpose_text = (
            f"Sepanjang periode {period_text}, sistem keamanan siber mencatat {total_records} "
            f"event yang dianalisis pada laporan ini. Data log dianalisis untuk memetakan pola "
            f"kejadian, menilai efektivitas penanganan, dan menjadi dasar rekomendasi perbaikan."
        )
        para_box = bg_slide.shapes.add_textbox(left_x, Inches(1.65), left_w, Inches(1.3))
        ptf = para_box.text_frame
        ptf.word_wrap = True
        pp = ptf.paragraphs[0]
        pp.text = sanitize_text(purpose_text)
        _set_font(pp, BODY_FONT, Pt(13), color=GRAY_TEXT)

        objectives = [
            ("1", "Memetakan Pola Kejadian", "Mengidentifikasi kategori, tren waktu, dan aset yang paling sering menjadi sasaran."),
            ("2", "Menilai Efektivitas Respons", "Mengevaluasi status penanganan tiap insiden."),
            ("3", "Menyusun Rekomendasi", "Merumuskan langkah mitigasi prioritas berbasis temuan data aktual."),
        ]
        add_badge_list(bg_slide, left_x, Inches(3.05), left_w, objectives, badge_color=GREEN_MAIN, row_h=Inches(1.05))

        scope_rows = [
            ("Periode", f"{period_text}"),
            ("Total Event", f"{total_records} entri log"),
            ("Sumber Berkas", report.input_file_name or "-"),
            ("Jenis Data", (report.data_type or "-").replace("_", " ").title()),
        ]
        add_ivory_panel(
            bg_slide, panel_x, Inches(1.65), panel_w, Inches(4.3),
            "i", "Ruang Lingkup Data", scope_rows, mode="kv",
            footnote="Sumber. Data yang diunggah pengguna, diproses otomatis oleh sistem.",
        )
        content_slides.append(bg_slide)

        # -------------------------------------------------------------
        # Slide: Ringkasan Eksekutif (GELAP)
        # -------------------------------------------------------------
        if is_included("executive_summary"):
            exec_slide = prs.slides.add_slide(prs.slide_layouts[6])
            add_dark_bg(exec_slide)
            add_logo(exec_slide, logo_path)
            add_kicker(exec_slide, kicker_ringkasan, color=GOLD_MAIN)
            add_title(exec_slide, sanitize_text(f"Snapshot Log Keamanan, {period_text}"), color=WHITE)

            stat_items = [(str(total_records), "Total Event Log")]
            if total_sev:
                for level in ("critical", "high"):
                    if severity.get(level):
                        stat_items.append((str(severity[level]), f"{SEVERITY_LABEL[level]} Severity" if level == "high" else f"Insiden {SEVERITY_LABEL[level]}"))
            if status_col:
                closed = sum(1 for row in parsed_data if _classify_open_status(row.get(status_col)) is False)
                if closed:
                    stat_items.append((str(closed), "Sudah Ditangani"))
                stat_items.append((str(open_count), "Masih Terbuka"))
            if category_pick:
                stat_items.append((str(len(top_categories)), "Kategori Sumber"))
            stat_items = stat_items[:6]

            grid_bottom = add_stat_card_grid(exec_slide, MARGIN_X, Inches(1.7), CONTENT_W, Inches(4.3), stat_items, cols=stat_cols, dark=True)

            caption = sanitize_text(ai_summary.get("executive_summary") or (key_findings[0] if key_findings else ""))
            cap_box = exec_slide.shapes.add_textbox(MARGIN_X, grid_bottom + Inches(0.25), CONTENT_W, Inches(0.9))
            ctf = cap_box.text_frame
            ctf.word_wrap = True
            cp = ctf.paragraphs[0]
            cp.text = caption
            _set_font(cp, BODY_FONT, Pt(11.5), italic=True, color=GOLD_LIGHT)
            content_slides.append(exec_slide)

        # -------------------------------------------------------------
        # Slide: Distribusi Kategori Event
        # -------------------------------------------------------------
        if category_pick:
            label, items = category_pick
            cat_slide = prs.slides.add_slide(prs.slide_layouts[6])
            add_logo(cat_slide, logo_path)
            add_kicker(cat_slide, kicker_analisis, color=GREEN_MAIN)
            add_title(cat_slide, f"Distribusi Event Berdasarkan {_humanize_label(label)}")

            top_items = items[:6]
            cat_total = sum(i["count"] for i in items) or 1
            intro = sanitize_text(
                f"{top_items[0]['value']} mencatat volume tertinggi dengan {top_items[0]['count']} event "
                f"({round(top_items[0]['count']/cat_total*100,1)}% dari total)."
            )
            intro_box = cat_slide.shapes.add_textbox(MARGIN_X, Inches(1.45), CONTENT_W, Inches(0.5))
            itf2 = intro_box.text_frame
            itf2.word_wrap = True
            ip = itf2.paragraphs[0]
            ip.text = intro
            _set_font(ip, BODY_FONT, Pt(12), color=GRAY_TEXT)

            chart_w = Inches(7.3) if panel_side == "right" else Inches(4.9)
            chart_x = MARGIN_X if panel_side == "right" else MARGIN_X + Inches(4.9) + Inches(0.4)
            panel_x2 = MARGIN_X + Inches(7.3) + Inches(0.4) if panel_side == "right" else MARGIN_X
            add_native_bar_chart(
                cat_slide, chart_x, Inches(2.1), chart_w, Inches(4.6),
                [i["value"] for i in reversed(top_items)], [i["count"] for i in reversed(top_items)],
                horizontal=True,
            )
            legend_rows = [
                (CATEGORY_COLOR_RAMP[i % len(CATEGORY_COLOR_RAMP)], i_item["value"], f"{round(i_item['count']/cat_total*100,1)}%")
                for i, i_item in enumerate(top_items)
            ]
            add_ivory_panel(
                cat_slide, panel_x2, Inches(2.1), Inches(4.9), Inches(4.6),
                "%", "Proporsi Kategori", legend_rows, mode="legend",
                footnote=sanitize_text(f"{top_items[0]['value']} menjadi kontributor volume terbesar pada kategori ini."),
            )
            content_slides.append(cat_slide)

        # -------------------------------------------------------------
        # Slide: Distribusi Severity
        # -------------------------------------------------------------
        if total_sev > 0 and is_included("severity_analysis"):
            sev_slide = prs.slides.add_slide(prs.slide_layouts[6])
            add_logo(sev_slide, logo_path)
            add_kicker(sev_slide, kicker_analisis, color=GREEN_MAIN)
            add_title(sev_slide, "Distribusi Tingkat Keparahan (Severity)")

            crit_pct = round(severity.get("critical", 0) / total_sev * 100, 1)
            high_pct = round(severity.get("high", 0) / total_sev * 100, 1)
            intro = sanitize_text(
                f"{high_pct}% event berkategori High dan {crit_pct}% Critical. "
                f"Kombinasi keduanya memerlukan perhatian dan eskalasi serius."
            )
            intro_box = sev_slide.shapes.add_textbox(MARGIN_X, Inches(1.45), CONTENT_W, Inches(0.5))
            itf3 = intro_box.text_frame
            itf3.word_wrap = True
            ip3 = itf3.paragraphs[0]
            ip3.text = intro
            _set_font(ip3, BODY_FONT, Pt(12), color=GRAY_TEXT)

            sev_categories = [SEVERITY_LABEL[k] for k in SEVERITY_ORDER]
            sev_values = [severity.get(k, 0) for k in SEVERITY_ORDER]
            sev_colors = [SEVERITY_COLOR[k] for k in SEVERITY_ORDER]
            add_native_bar_chart(sev_slide, MARGIN_X, Inches(2.1), Inches(8.1), Inches(4.6), sev_categories, sev_values, colors=sev_colors)

            detail_text = None
            if category_pick:
                names = ", ".join(i["value"] for i in category_pick[1][:6])
                detail_text = sanitize_text(f"Insiden Critical tersebar pada kategori {names}.")
            add_critical_highlight_panel(
                sev_slide, MARGIN_X + Inches(8.5), Inches(2.1), Inches(4.3), Inches(4.6),
                f"{crit_pct}%", "dari seluruh event berstatus Critical Severity", detail_text,
            )
            content_slides.append(sev_slide)

        # -------------------------------------------------------------
        # Slide: Status Penanganan Insiden (skip kalau tak ada kolom status)
        # -------------------------------------------------------------
        if status_items:
            status_slide = prs.slides.add_slide(prs.slide_layouts[6])
            add_logo(status_slide, logo_path)
            add_kicker(status_slide, kicker_analisis, color=GREEN_MAIN)
            add_title(status_slide, "Status Penanganan Insiden")

            status_total = sum(i["count"] for i in status_items) or 1
            top_status = status_items[0]
            intro = sanitize_text(
                f"{round(top_status['count']/status_total*100,1)}% event berstatus {top_status['value']}. "
                f"Sebagian kecil masih memerlukan tindak lanjut aktif tim SOC."
            )
            intro_box = status_slide.shapes.add_textbox(MARGIN_X, Inches(1.45), CONTENT_W, Inches(0.5))
            itf4 = intro_box.text_frame
            itf4.word_wrap = True
            ip4 = itf4.paragraphs[0]
            ip4.text = intro
            _set_font(ip4, BODY_FONT, Pt(12), color=GRAY_TEXT)

            top_status_items = status_items[:8]
            add_native_bar_chart(
                status_slide, MARGIN_X, Inches(2.1), CONTENT_W, Inches(4.6),
                [i["value"] for i in top_status_items], [i["count"] for i in top_status_items],
            )
            content_slides.append(status_slide)

        # -------------------------------------------------------------
        # Slide: Tabel Insiden Critical/Prioritas Tinggi
        # -------------------------------------------------------------
        if severity_col and parsed_data:
            critical_rows = [row for row in parsed_data if _classify_severity_value(str(row.get(severity_col, ""))) == "critical"]
            if len(critical_rows) < 5:
                critical_rows += [row for row in parsed_data if _classify_severity_value(str(row.get(severity_col, ""))) == "high"]
            critical_rows = critical_rows[:12]

            if critical_rows:
                table_slide = prs.slides.add_slide(prs.slide_layouts[6])
                add_logo(table_slide, logo_path)
                kicker_color = RED_CRIT if open_count else GREEN_MAIN
                add_kicker(table_slide, "SOROTAN INSIDEN", color=kicker_color)
                add_title(table_slide, f"{len(critical_rows)} Insiden Prioritas Tinggi")

                headers = ["No"]
                if category_pick:
                    headers.append(_humanize_label(category_pick[0]))
                headers.append("Severity")
                if status_col:
                    headers.append("Status")

                rows_out = []
                highlight_idx = set()
                cat_col_name = source_cols.get(category_pick[0]) if category_pick else None
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

                add_native_table(table_slide, MARGIN_X, Inches(1.55), CONTENT_W, Inches(4.9), headers, rows_out, highlight_idx)

                if open_count:
                    cap_box = table_slide.shapes.add_textbox(MARGIN_X, Inches(6.55), CONTENT_W, Inches(0.4))
                    cp2 = cap_box.text_frame.paragraphs[0]
                    cp2.text = sanitize_text(f"Baris merah menandai {open_count} insiden yang masih dalam proses penanganan per akhir periode data.")
                    _set_font(cp2, BODY_FONT, Pt(10.5), italic=True, color=GRAY_TEXT)
                content_slides.append(table_slide)

        # -------------------------------------------------------------
        # Slide: Aset Paling Sering Menjadi Sasaran (GELAP)
        # -------------------------------------------------------------
        if asset_pick:
            label, items = asset_pick
            asset_slide = prs.slides.add_slide(prs.slide_layouts[6])
            add_dark_bg(asset_slide)
            add_logo(asset_slide, logo_path)
            add_kicker(asset_slide, "SOROTAN INSIDEN", color=GOLD_MAIN)
            add_title(asset_slide, f"{_humanize_label(label)} yang Paling Sering Menjadi Sasaran", color=WHITE)

            asset_total = sum(i["count"] for i in items) or 1
            top_assets = items[:3]
            card_items = []
            for idx, item in enumerate(top_assets):
                pct = round(item["count"] / asset_total * 100, 1)
                card_items.append((
                    str(idx + 1), item["value"], f"{item['count']} event",
                    sanitize_text(f"Tercatat {item['count']} kejadian ({pct}% dari total) yang menyasar kategori ini."),
                ))
            add_asset_card_row(asset_slide, MARGIN_X, Inches(1.9), CONTENT_W, Inches(4.6), card_items)
            content_slides.append(asset_slide)

        # -------------------------------------------------------------
        # Slide: Temuan Utama
        # -------------------------------------------------------------
        if key_findings:
            find_slide = prs.slides.add_slide(prs.slide_layouts[6])
            add_logo(find_slide, logo_path)
            add_kicker(find_slide, "ANALISIS", color=GREEN_MAIN)
            add_title(find_slide, "Temuan Utama")

            findings_items = []
            for idx, finding in enumerate(key_findings):
                title_part, _, detail_part = finding.partition(". ")
                if not detail_part:
                    title_part, detail_part = finding, ""
                findings_items.append((str(idx + 1), title_part.strip() or finding, detail_part.strip()))

            def _finding_color(idx, item):
                return RED_CRIT if (open_count and idx == 0) else GREEN_MAIN

            add_badge_list(find_slide, MARGIN_X, Inches(1.7), CONTENT_W, findings_items, badge_color=_finding_color, row_h=Inches(1.0))
            content_slides.append(find_slide)

        # -------------------------------------------------------------
        # Slide: Rekomendasi Mitigasi
        # -------------------------------------------------------------
        if is_included("recommendations") and recommendations:
            rec_slide = prs.slides.add_slide(prs.slide_layouts[6])
            add_logo(rec_slide, logo_path)
            add_kicker(rec_slide, "TINDAK LANJUT", color=GREEN_MAIN)
            add_title(rec_slide, "Rekomendasi Mitigasi")

            items = recommendations[:6]
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
                add_badge_circle(rec_slide, cx + Inches(0.2), cy + Inches(0.18), Inches(0.36), str(idx + 1), GOLD_MAIN, font_size=Pt(13))
                title_box = rec_slide.shapes.add_textbox(cx + Inches(0.2), cy + Inches(0.62), card_w - Inches(0.4), Inches(0.35))
                ttf2 = title_box.text_frame
                ttf2.word_wrap = True
                tp2 = ttf2.paragraphs[0]
                tp2.text = item.get("title") or (item.get("detail") or "")[:60]
                _set_font(tp2, BODY_FONT, Pt(13), bold=True, color=TEXT_DARK)
                if item.get("title") and item.get("detail"):
                    det_box = rec_slide.shapes.add_textbox(cx + Inches(0.2), cy + Inches(0.95), card_w - Inches(0.4), card_h - Inches(1.0))
                    dtf2 = det_box.text_frame
                    dtf2.word_wrap = True
                    dp2 = dtf2.paragraphs[0]
                    dp2.text = item.get("detail") or ""
                    _set_font(dp2, BODY_FONT, Pt(10.5), color=GRAY_TEXT)
            content_slides.append(rec_slide)

        # -------------------------------------------------------------
        # Slide: Kesimpulan (GELAP)
        # -------------------------------------------------------------
        if is_included("conclusion") and ai_summary.get("conclusion"):
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
            pp2.text = sanitize_text(ai_summary.get("conclusion"))
            _set_font(pp2, BODY_FONT, Pt(13), color=RGBColor(0xE8, 0xEC, 0xE6))

            pills = []
            if total_sev:
                resolved_pct = round((total_sev - open_count) / total_sev * 100, 1) if status_col else None
                if resolved_pct is not None:
                    pills.append(f"{resolved_pct}% event tertangani")
            if category_pick:
                pills.append(f"{category_pick[1][0]['value']} jadi prioritas perhatian")
            if open_count:
                pills.append(f"{open_count} insiden masih berjalan")
            pill_y = Inches(3.7)
            for pill_text in pills[:3]:
                add_pill_stat(concl_slide, MARGIN_X, pill_y, left_w2, Inches(0.6), pill_text)
                pill_y += Inches(0.75)

            priority_items = []
            for idx, rec in enumerate(recommendations[:4]):
                letter = chr(ord("a") + idx)
                priority_items.append((letter, rec.get("title") or (rec.get("detail") or "")[:70]))
            if priority_items:
                add_priority_panel(
                    concl_slide, MARGIN_X + left_w2 + Inches(0.4), Inches(1.7), Inches(4.3), Inches(4.6),
                    "Prioritas Berikutnya", priority_items,
                )
            content_slides.append(concl_slide)

        # -------------------------------------------------------------
        # Slide: Penutup / Terima Kasih
        # -------------------------------------------------------------
        closing = prs.slides.add_slide(prs.slide_layouts[6])
        add_dark_bg(closing)
        add_corner_flourish(closing, flourish_corner)
        title_box2 = closing.shapes.add_textbox(MARGIN_X, Inches(3.0), Inches(9), Inches(1.0))
        tp3 = title_box2.text_frame.paragraphs[0]
        tp3.text = "Terima Kasih"
        _set_font(tp3, TITLE_FONT, Pt(40), bold=True, color=WHITE)
        sub_box2 = closing.shapes.add_textbox(MARGIN_X, Inches(3.85), Inches(9), Inches(0.5))
        sp2 = sub_box2.text_frame.paragraphs[0]
        sp2.text = report.title
        _set_font(sp2, BODY_FONT, Pt(14), color=WHITE)
        note_box = closing.shapes.add_textbox(MARGIN_X, Inches(4.4), Inches(9), Inches(0.4))
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


