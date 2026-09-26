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

Layout bervariasi ANTAR LAPORAN (posisi panel, jumlah kolom grid, gaya cover/chart/kartu,
sudut ornamen) — dipilih SEKALI per laporan lewat pick_visual_style() (report_render_logic.py)
tepat saat analisis AI berhasil, disimpan ke report.visual_style, dibaca di sini via
get_visual_style() (BUKAN di-random di sini lagi) supaya preview web & file yang diunduh
SELALU menampilkan bentuk yang identik utk laporan yang sama, tapi tetap dalam identitas
visual (palet/font/makna warna) yang sama.
"""
import logging
import math
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.chart.data import CategoryChartData, BubbleChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_TICK_MARK, XL_TICK_LABEL_POSITION

from app.models.report import Report
from app.services.report_render_logic import (
    render_is_en, set_render_language,
    build_report_blocks, build_management_report_blocks, is_english, find_logo_path, get_visual_style,
    resolve_theme_color, best_grid_cols, _hard_truncate, _dedupe_truncated_labels, _layout_dashboard_column,
    _DASH_FACT_STRIP_H_IN, _DASH_FACT_PAIR_H_IN, _DASH_MARGIN_X_IN, _DASH_COL_GAP_IN, _DASH_TITLE_MAX_H_IN,
    _DASH_CONTENT_BOTTOM_IN, _layout_insight_layers, _layout_dashboard_column_content,
    tinggi_kartu_in, wrap_line_count, kolom_yang_digambar, _kpi_card_widths, _NESTED_CARD_GAP_IN,
    metrik_judul_dashboard,
    gelapkan_untuk_latar_terang, warna_teks_label, label_menempel_pada_bentuk,
    warna_pita_panel,
    fakta_strip_kolom, _DASH_COLS_FACT_H_IN, kumpulkan_catatan_halaman,
    alokasi_kolom_bertumpuk, _kepala_seksi_h_in,
    radar_label_layout,
    tinggi_kotak_catatan_halaman, tinggi_maks_kotak_catatan, _DASH_COLS_KEPALA_H_IN,
    _DASH_TILE_GAP_IN, tinggi_kolom_tersedia_in, _DASH_COLS_PAD_IN, _DASH_COLS_JUDUL_GAP_IN,
    _DASH_COLS_TITLE_PAD_IN, _KPI_VALUE_MAX_PT,
    muat_catatan,
    ukuran_judul_cover_mgmt, _MGMT_COVER_SUB_PT, _MGMT_COVER_PERIOD_PT,
    _MGMT_COVER_FOOTER_PT, _MGMT_CLOSING_THANKS_PT, _MGMT_CLOSING_NOTE_PT,
    _NESTED_CARD_HEADER_H_IN, _NESTED_CARD_HEADER_MIN_H_IN, _NESTED_CARD_SUBITEM_LINE1_H_IN, _NESTED_CARD_SUBITEM_BAR_H_IN,
    _NESTED_CARD_SUBITEM_GAP_IN, _NESTED_CARD_ROW_GAP_IN, _layout_nested_card_grid,
)

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
# A2: garis tepi panel disamakan dgn acuan (#D6DBE3) - kembaran export_pdf.py.
PANEL_BORDER = RGBColor(0xD6, 0xDB, 0xE3)
# PITA KEPALA PANEL: warnanya TIDAK didefinisikan di sini - diturunkan dari warna TEMA
# AKTIF lewat warna_pita_panel() di report_render_logic.py, sama seperti sisi PDF.
# A5: warna label "Catatan:" di acuan.
CATATAN_LABEL = RGBColor(0x00, 0xB0, 0x50)
TITLE_FONT = "Bookman Old Style"
BODY_FONT = "Calibri"

# ── TEMA WARNA (report.theme_color) ─────────────────────────────────────────
# Sama persis dengan export_pdf.py — GREEN_MAIN/BG/CHART & GOLD_MAIN/LIGHT di atas TETAP
# dipakai langsung oleh SEVERITY_COLOR di bawah (warna severity TIDAK ikut tema apa pun).
# THEME_PALETTES murni untuk elemen BRAND/struktural (cover, kicker, badge, border panel,
# header tabel, chart "bar" utama) — nilai HEX identik dengan export_pdf.py/reportTheme.ts.
NAVY_MAIN = RGBColor(0x1E, 0x3A, 0x5F)
NAVY_BG = RGBColor(0x0F, 0x17, 0x2A)
NAVY_CHART = RGBColor(0x3B, 0x6E, 0xA5)
DARK_MAIN = RGBColor(0x1F, 0x29, 0x37)
DARK_BG = RGBColor(0x11, 0x18, 0x27)
DARK_CHART = RGBColor(0x3F, 0x4B, 0x5C)
GOLD_BRONZE_MAIN = RGBColor(0x8A, 0x6A, 0x16)
GOLD_BRONZE_BG = RGBColor(0x4A, 0x39, 0x08)
GOLD_CREAM_LIGHT = RGBColor(0xF3, 0xE3, 0xAE)
GOLD_CREAM_SOFT = RGBColor(0xFB, 0xF3, 0xDC)
# PERMINTAAN USER ("bosan template segitu-gitu aja"): tema warna ke-5, lihat catatan lengkap
# di export_pdf.py — nilai HEX PERSIS sama (0x0F6B64/0x0A3D39/0x35A398).
TEAL_MAIN = RGBColor(0x0F, 0x6B, 0x64)
TEAL_BG = RGBColor(0x0A, 0x3D, 0x39)
TEAL_CHART = RGBColor(0x35, 0xA3, 0x98)

# Warna prioritas/urgensi rekomendasi — SATU sumber dipakai _build_recommendations_slide (SOC)
# & _build_management_action_items_slide (Management), mirror export_pdf.py::URGENCY_COLOR.
# Warna BERMAKNA (status prioritas), BUKAN aksen tema dekoratif — sengaja TIDAK ikut palet
# tema, tetap sama persis apa pun tema laporan yang dipilih.
URGENCY_COLOR = {
    "critical": (RED_CRIT, RED_CRIT_BG),
    "high": (RGBColor(0xEA, 0x58, 0x0C), RGBColor(0xFF, 0xF7, 0xED)),
    "medium": (GOLD_MAIN, GOLD_CREAM_SOFT),
    "low": (RGBColor(0x25, 0x63, 0xEB), RGBColor(0xEF, 0xF6, 0xFF)),
}

THEME_PALETTES: dict[str, dict[str, RGBColor]] = {
    "green": {"main": GREEN_MAIN, "bg": GREEN_BG, "chart": GREEN_CHART, "light": GOLD_MAIN, "soft": GOLD_LIGHT},
    "navy": {"main": NAVY_MAIN, "bg": NAVY_BG, "chart": NAVY_CHART, "light": GOLD_MAIN, "soft": GOLD_LIGHT},
    "dark": {"main": DARK_MAIN, "bg": DARK_BG, "chart": DARK_CHART, "light": GOLD_MAIN, "soft": GOLD_LIGHT},
    "gold": {"main": GOLD_BRONZE_MAIN, "bg": GOLD_BRONZE_BG, "chart": GOLD_MAIN, "light": GOLD_CREAM_LIGHT, "soft": GOLD_CREAM_SOFT},
    "teal": {"main": TEAL_MAIN, "bg": TEAL_BG, "chart": TEAL_CHART, "light": GOLD_MAIN, "soft": GOLD_LIGHT},
}

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
_CROPPED_LOGO_PATH_CACHE: str | None = None
_CROPPED_LOGO_PATH_RESOLVED = False


def _resolve_logo_path() -> str | None:
    """BUG DIPERBAIKI (dilaporkan user, disertai foto — logo PPT kegedean drpd versi PDF utk
    konteks yang sama, "isi"): versi PDF (_resolve_logo_b64 di export_pdf.py) sudah lama
    memotong logo asli (LOGO_PETRO_DANANTARA.png) ke bounding box alpha-nya SEKALI sebelum
    dipakai — file aslinya py padding transparan raksasa di atas/bawah (~54% dari tinggi
    total kosong, cuma ~46% tengahnya benar2 berisi logo). Fungsi ini SEBELUMNYA langsung
    kembalikan path file ASLI (belum dipotong) ke add_logo()/add_picture() — artinya
    width=Ninch di sana menghitung Ninch itu TERMASUK padding kosong, jadi logo yang BENAR2
    kelihatan cuma sebagian dari kotak yang diminta, beda proporsi dgn versi PDF yang sudah
    dipotong duluan. Sekarang dipotong SEKALI persis sama seperti PDF (bbox alpha), disimpan
    ke file sementara & di-cache utk generate berikutnya dlm proses yang sama (file logo
    aslinya statis, tidak berubah selama proses berjalan) — kalau gagal (Pillow/IO error
    apa pun), fallback ke path asli apa adanya (degradasi aman, bukan crash)."""
    global _CROPPED_LOGO_PATH_CACHE, _CROPPED_LOGO_PATH_RESOLVED
    if _CROPPED_LOGO_PATH_RESOLVED:
        return _CROPPED_LOGO_PATH_CACHE

    _CROPPED_LOGO_PATH_RESOLVED = True
    original_path = find_logo_path()
    if not original_path:
        _CROPPED_LOGO_PATH_CACHE = None
        return None
    try:
        import tempfile
        from PIL import Image
        with Image.open(original_path) as im:
            im = im.convert("RGBA")
            alpha_bbox = im.split()[-1].getbbox()
            if alpha_bbox:
                im = im.crop(alpha_bbox)
            fd, tmp_path = tempfile.mkstemp(suffix=".png", prefix="petro_logo_cropped_")
            import os as _os
            _os.close(fd)
            im.save(tmp_path, format="PNG")
            _CROPPED_LOGO_PATH_CACHE = tmp_path
    except Exception:
        _CROPPED_LOGO_PATH_CACHE = original_path
    return _CROPPED_LOGO_PATH_CACHE


# ============================================================================
# Helper visual dasar
# ============================================================================
def _fmt_num(val) -> str:
    """Mirror export_pdf.py::_fmt_num — BUG DIPERBAIKI (ditemukan lewat verifikasi render
    laporan traffic asli): format spec "g" polos diam-diam pindah ke notasi ilmiah begitu
    angkanya jutaan (mis. "1098060" tampil sbg "1.09806e+06") — umum utk data traffic/log
    jaringan. Dipakai pemisah ribuan biasa; dibulatkan kalau memang bilangan bulat."""
    try:
        f = float(val)
    except (TypeError, ValueError):
        return str(val)
    if not render_is_en():
        # Konvensi Indonesia: titik utk ribuan, koma utk desimal (lihat set_render_language).
        text = f"{int(f):,}" if f == int(f) else f"{f:,.1f}"
        return text.translate(str.maketrans(",.", ".,"))
    if f == int(f):
        return f"{int(f):,}"
    return f"{f:,.1f}"


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


# Lebar rata-rata karakter JUDUL COVER, diukur dari render PDF sungguhan (font & ukuran yang
# sama persis): 'Executive Analysis Report' 8,372in/25 kar = 0,548em, 'Laporan Analisis
# Eksekutif' 8,531in/26 kar = 0,537em. Default penaksir 0,60em kelewat lebar ~10%, dan pada
# kotak 9,5in itu membuat judul 26 karakter divonis wrap 2 baris padahal PDF menggambarnya 1
# baris - subtitle di PPTX lalu turun 0,77in dari posisi PDF-nya. 0,56 dipakai: di atas hasil
# ukur (jadi tetap aman/konservatif) tapi tidak sejauh 0,60.
_EM_KARAKTER_JUDUL_COVER = 0.56


def _estimate_wrapped_height_in(text: str, font_pt: float, box_width_in: float,
                                em_per_char: float = 0.6) -> float:
    """Estimasi kasar tinggi (inci) yang dipakai `text` kalau word-wrap dalam box selebar
    `box_width_in` pada ukuran `font_pt` — python-pptx bukan mesin render sungguhan (tidak
    tahu lebar karakter asli tiap font), jadi ini estimasi berbasis rata-rata lebar karakter
    huruf tebal (0.6em). Dipakai supaya elemen SETELAH judul (subtitle, info) tidak pernah
    ketimpa kalau judulnya panjang & wrap ke banyak baris — laporan bisa dari domain apa saja
    (SOC, keuangan, KPI, dll) dengan panjang judul yang jauh berbeda-beda, jadi TIDAK BOLEH
    diasumsikan selalu pendek/selalu 1 baris."""
    if not text:
        return font_pt * 1.25 / 72
    avg_char_width_in = (font_pt * em_per_char) / 72
    chars_per_line = max(int(box_width_in / avg_char_width_in), 1)
    # Pemisah baris EKSPLISIT di dalam teks dipecah dulu. Nilai data dari berkas sumber bisa
    # membawa pemisah barisnya sendiri (sisa pemecahan baris saat PDF sumber dibaca), dan
    # ceil(len/kapasitas) menghitungnya sebagai satu baris panjang - padahal PowerPoint
    # memulai baris baru di tiap pemisah itu. Terukur di kotak Catatan laporan 195: butir
    # ketiga memakai 3 baris sementara perkiraan bilang 2, lalu butir keempat menimpanya.
    line_count = 0
    for potongan in (str(text).splitlines() or [""]):
        line_count += max(1, -(-len(potongan) // chars_per_line))  # ceil division
    return max(1, line_count) * (font_pt * 1.25) / 72


def _no_shadow(shape):
    try:
        shape.shadow.inherit = False
    except Exception:
        pass


def _modest_corner(shape, frac=0.02):
    """PowerPoint memberi ROUNDED_RECTANGLE radius sudut default besar (~1/6 dari sisi
    terpendek) — utk shape yang tidak terlalu tinggi/lebar, itu bikin lengkungan sudut
    memakan inset konten di dekatnya (badge/teks pojok kiri-atas terlihat menempel/tertimpa
    lengkungan, dilaporkan user lewat tangkapan layar). Diturunkan lagi dari 0.06 ke 0.02
    (permintaan user: kotak datar spt referensi, bukan kartu membulat — setara ~2-4px di
    kartu berukuran wajar, cocok dgn border-radius:3px versi PDF). Dipanggil setelah tiap ROUNDED_
    RECTANGLE dibuat (kecuali yang SENGAJA dibuat pil penuh via adjustments[0]=0.5)."""
    try:
        shape.adjustments[0] = frac
    except Exception:
        pass


def _send_to_back(slide, shape):
    sp = shape._element
    spTree = slide.shapes._spTree
    spTree.remove(sp)
    spTree.insert(2, sp)


def add_dark_bg(slide, theme: dict | None = None):
    t = theme or THEME_PALETTES["green"]
    rect = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H)
    rect.fill.solid()
    rect.fill.fore_color.rgb = t["bg"]
    rect.line.fill.background()
    _no_shadow(rect)
    _send_to_back(slide, rect)
    # Ditandai LANGSUNG di objek slide-nya (atribut custom, python-pptx Slide tidak pakai
    # __slots__ jadi aman) — dibaca add_footer() belakangan (dipanggil di 1 loop generik di
    # akhir generate_ppt_report, TIDAK py akses ke `theme`/`dark` block aslinya lagi di titik
    # itu) supaya warna footer bisa menyesuaikan TANPA perlu mengalirkan flag "dark" manual
    # lintas banyak fungsi builder — sumbernya PERSIS di sini, tempat latar gelap SUNGGUHAN
    # digambar, jadi tidak mungkin nyasar/tidak sinkron dgn kenyataan visualnya.
    slide._petro_dark_theme = t
    return rect


def _fill_rect_bg(slide, x, y, w, h, color):
    """Persegi latar penuh (bukan slide utuh) — dipakai cover/penutup varian split-warna
    (`cover_style="split"`) utk 2 kolom warna solid berdampingan, analog `add_dark_bg` tapi
    utk area sebagian slide."""
    rect = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    rect.fill.solid()
    rect.fill.fore_color.rgb = color
    rect.line.fill.background()
    _no_shadow(rect)
    _send_to_back(slide, rect)
    return rect


def add_corner_flourish(slide, corner: str = "bottom_right", area_x=0, area_y=0, area_w=None, area_h=None, theme: dict | None = None):
    """Ornamen lengkung emas tipis (beberapa lingkaran konsentris tanpa isi, diposisikan
    menjorok keluar sudut) — dipakai HANYA di cover & penutup, mendekati motif referensi.

    `area_x/y/w/h` (opsional, default = seluruh slide) membatasi sudut mana yang dipakai
    acuan — dibutuhkan utk cover/penutup varian split-warna (`cover_style="split"`), di mana
    flourish HARUS tetap berada di dalam kolom hijau saja (bukan di sudut fisik slide penuh,
    yang sebagian jatuh di kolom emas kalau corner="bottom_left")."""
    t = theme or THEME_PALETTES["green"]
    area_w = SLIDE_W if area_w is None else area_w
    area_h = SLIDE_H if area_h is None else area_h
    # Radius & inset dikecilkan dari versi awal (dulu sampai 3.25in, base offset 0.8/0.6in) —
    # keluhan nyata dari pengguna: lingkaran terluar menjorok cukup jauh sampai menembus area
    # teks "Diskusi dan pertanyaan dipersilakan" di penutup, mengganggu keterbacaan. Ornamen
    # tetap ada (identitas visual), cuma jangkauannya dipersempit supaya tetap di pojok saja.
    if corner == "bottom_left":
        base_x, base_y = area_x - Inches(0.8), area_y + area_h - Inches(1.0)
    elif corner == "top_right":
        base_x, base_y = area_x + area_w - Inches(1.0), area_y - Inches(0.8)
    else:
        base_x, base_y = area_x + area_w - Inches(1.0), area_y + area_h - Inches(1.0)

    for r in (Inches(1.3), Inches(1.75), Inches(2.2), Inches(2.65)):
        oval = slide.shapes.add_shape(MSO_SHAPE.OVAL, base_x - r, base_y - r, r * 2, r * 2)
        oval.fill.background()
        oval.line.color.rgb = t["light"]
        oval.line.width = Pt(0.75)
        _no_shadow(oval)


def add_kicker(slide, text: str, color=GRAY_TEXT, x=MARGIN_X, y=Inches(0.28), w=Inches(9)):
    # WARNA NETRAL default (bukan aksen tema) — mirror export_pdf.py::_kicker, lihat catatan
    # di sana. Pemanggil dgn latar gelap tetap mengisi color=WHITE eksplisit.
    # PERMINTAAN USER: rampingkan header halaman (referensi mulai konten di ~0.9in, punya kita
    # dulu ~1.9in) — y digeser naik & tinggi box dipangkas ke pas-pasan (sebelumnya 0.3in utk
    # teks 11pt yang tingginya asli cuma ~0.18in, sisanya ruang kosong terbuang).
    box = slide.shapes.add_textbox(x, y, w, Inches(0.22))
    p = box.text_frame.paragraphs[0]
    p.text = text.upper()
    p.alignment = PP_ALIGN.LEFT
    _set_font(p, BODY_FONT, Pt(11), bold=True, color=color)
    return box


def _draw_header_band(slide, x, y, w, text, h=Inches(0.32)):
    """Padanan _panel_header_band (export_pdf.py): pita abu-abu tipis datar berisi judul TEBAL
    warna netral — menggantikan pola lama label kecil huruf kapital berwarna aksen tema di
    dalam kartu insight/tile & panel distribusi. Dipakai HANYA sbg header PANEL/KARTU (bukan
    header slide — itu tetap add_kicker + add_title)."""
    band = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    band.fill.solid()
    band.fill.fore_color.rgb = PANEL_BORDER
    band.line.fill.background()
    _no_shadow(band)
    tf = band.text_frame
    tf.margin_left = Inches(0.08)
    tf.margin_right = Inches(0.08)
    tf.margin_top = Inches(0.01)
    tf.margin_bottom = Inches(0.01)
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.alignment = PP_ALIGN.LEFT
    _set_font(p, BODY_FONT, Pt(9), bold=True, color=TEXT_DARK)
    return band


def add_title(slide, text: str, color=TEXT_DARK, x=MARGIN_X, y=Inches(0.52), w=Inches(11.5), size=Pt(30)):
    """Return: posisi Y (inci) TEPAT DI BAWAH judul ini — WAJIB dipakai pemanggil utk
    memposisikan elemen berikutnya (bukan konstanta tetap seperti Inches(1.45) dst).

    BUG BESAR YANG DIPERBAIKI: box judul SEBELUMNYA selalu Inches(0.75) tinggi tetap,
    diam-diam mengasumsikan judul selalu muat 1 baris. Kalau block["title"]/["heading"]
    panjang (umum utk data non-SOC — nama bulan+tahun, kalimat AI, dst) dan wrap ke 2 baris,
    baris kedua itu VISUAL MELUBER ke luar box (PowerPoint textbox TIDAK auto-reflow shape
    lain di baliknya) dan menabrak elemen berikutnya yang posisinya konstanta tetap (terlihat
    nyata di slide Ringkasan Eksekutif: baris ke-2 judul bertabrakan dgn kartu KPI di
    bawahnya). Tinggi box SEKARANG dihitung dari estimasi wrap sungguhan (_estimate_wrapped_
    height_in, sudah dipakai di file ini utk hal serupa), dan Y bawahnya DIKEMBALIKAN supaya
    tiap slide bisa menggeser elemen berikutnya sesuai tinggi judul yang SEBENARNYA.

    PERMINTAAN USER: rampingkan header halaman — batas bawah tinggi box diturunkan dari 0.75in
    ke 0.5in. 0.75in SEBELUMNYA lebih tinggi drpd kebutuhan asli judul 1 baris (~0.5-0.6in utk
    30pt), jadi floor lama itu MEMBOROSKAN ruang, bukan mengamankan sesuatu — judul yang genuinely
    wrap ke 2+ baris tetap aman krn box_h_in dihitung dari estimasi wrap sungguhan (baris di
    bawah), floor cuma jaring pengaman minimum, bukan patokan tinggi normal."""
    box = slide.shapes.add_textbox(x, y, w, Inches(0.5))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    p.text = text
    _set_font(p, TITLE_FONT, size, bold=True, color=color)
    text_h_in = _estimate_wrapped_height_in(text, size.pt, Emu(w).inches)
    box_h_in = max(0.5, text_h_in + 0.06)
    box.height = Inches(box_h_in)
    return Emu(y).inches + box_h_in


def add_footer(slide, page_num: int, total_pages: int, dark: bool = False, theme: dict | None = None):
    # BUG DIPERBAIKI (drift vs export_pdf.py::_page(), yang pakai `t["soft"]` utk footer di
    # halaman gelap — lihat `color:{GRAY_TEXT if not dark else t["soft"]}` di sana): versi
    # PPT ini SELALU pakai GRAY_TEXT (abu gelap) apa pun latar slide-nya — di slide berlatar
    # gelap (executive_summary/asset_cards gaya podium/conclusion/dst, lihat add_dark_bg),
    # abu gelap di atas latar gelap kontrasnya nyaris nol, nomor halaman jadi nyaris tak
    # kelihatan. `dark`/`theme` opsional (default aman utk pemanggil lama) — pemanggil di
    # generate_ppt_report menurunkan `dark` dari `_petro_dark_theme` yang ditandai
    # add_dark_bg tepat saat latar gelap SUNGGUHAN digambar (lihat catatan di sana), TIDAK
    # perlu mengalirkan flag "dark" manual lintas banyak fungsi builder.
    t = theme or THEME_PALETTES["green"]
    color = t["soft"] if dark else GRAY_TEXT
    box = slide.shapes.add_textbox(MARGIN_X, SLIDE_H - Inches(0.42), CONTENT_W, Inches(0.3))
    p = box.text_frame.paragraphs[0]
    p.text = f"{page_num:02d} / {total_pages:02d}"
    p.alignment = PP_ALIGN.RIGHT
    _set_font(p, BODY_FONT, Pt(9), color=color)


# Bingkai lockup logo di slide berlatar gelap (1e) - kembaran _dark_logo_html di
# export_pdf.py. Padding & radius dipakai angka yang SAMA dgn versi PDF supaya bentuknya
# tidak menyimpang: padding mendatar lebih lebar drpd menegak, radius = setengah tinggi.
_LOGO_PILL_PAD_X_IN = 14 / 96.0
_LOGO_PILL_PAD_Y_IN = 8 / 96.0


def _pasang_bayangan(shape, blur_pt=6.0, jarak_pt=2.0, alpha=28000):
    """Bayangan luar lembut lewat XML - python-pptx belum punya API untuk outerShdw.

    `shape.shadow` yang tersedia hanya bisa MEMATIKAN bayangan warisan (inherit=False);
    tidak ada jalan resmi menyetel blur/jarak/warna. Elemen <a:effectLst><a:outerShdw>
    ditulis langsung ke spPr - inilah yang dipakai PowerPoint sendiri, jadi hasilnya
    bayangan native, bukan gambar tiruan."""
    from pptx.oxml.ns import qn
    spPr = shape._element.spPr
    for lama in spPr.findall(qn('a:effectLst')):
        spPr.remove(lama)
    eff = spPr.makeelement(qn('a:effectLst'), {})
    shdw = spPr.makeelement(qn('a:outerShdw'), {
        'blurRad': str(int(blur_pt * 12700)),
        'dist': str(int(jarak_pt * 12700)),
        'dir': '5400000',          # 90 derajat = lurus ke bawah
        'rotWithShape': '0',
    })
    clr = spPr.makeelement(qn('a:srgbClr'), {'val': '000000'})
    a = spPr.makeelement(qn('a:alpha'), {'val': str(int(alpha))})
    clr.append(a)
    shdw.append(clr)
    eff.append(shdw)
    spPr.append(eff)


def _pill_logo(slide, x_in, y_in, w_in, h_in, theme=None):
    """Kotak putih membulat penuh di BELAKANG lockup logo, dgn bayangan lembut.

    Alasannya terukur di render: di atas hijau tua, teks "PETROKIMIA GRESIK"/"PUPUK
    INDONESIA" di dalam logo nyaris tidak terbaca karena warnanya menyatu dgn latar.
    Dipanggil SEBELUM add_picture supaya logonya berada DI ATAS bingkai.

    ROUNDED_RECTANGLE dipakai (bukan oval): adjustment-nya disetel ke 0,5 = radius
    setengah sisi pendek, yang membuat kedua ujungnya membulat penuh seperti pill."""
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.oxml.ns import qn
    kotak = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x_in), Inches(y_in),
        Inches(w_in), Inches(h_in))
    kotak.fill.solid()
    kotak.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    kotak.line.fill.background()
    kotak.text_frame.text = ''
    # adj 0,5 = radius setengah sisi terpendek -> ujung membulat PENUH
    for av in kotak._element.spPr.findall(qn('a:prstGeom') + '/' + qn('a:avLst')):
        for gd in list(av):
            av.remove(gd)
        gd = av.makeelement(qn('a:gd'), {'name': 'adj', 'fmla': 'val 50000'})
        av.append(gd)
    _pasang_bayangan(kotak)
    return kotak


def add_logo(slide, logo_path, x=None, y=Inches(0.18), width=Inches(2.63), dark=False, pill=False):
    """`dark` sebelumnya menggambar chip/oval putih di belakang logo di slide berlatar
    gelap, tapi PERMINTAAN USER: hasilnya terlihat aneh — sekarang logo tampil polos tanpa
    background treatment apa pun, di latar apa saja.

    BUG DIPERBAIKI (dilaporkan user, disertai foto — logo PPT kegedean drpd versi PDF):
    default sempat digandakan (2.6in -> 5.2in, pemanggil cover/penutup 3.5in -> 7.0in) di
    permintaan sebelumnya, TAPI ukuran logo halaman isi versi PDF (_page() di export_pdf.py)
    belakangan ikut disesuaikan turun (36px ~= 0.375in tinggi) tanpa PPT ikut disesuaikan
    balik — keduanya jadi drift, PPT jauh lebih besar drpd PDF utk konteks yang sama (isi).
    2.63in dihitung PERSIS supaya TINGGI hasilnya (logo asli rasio lebar:tinggi ~7.02:1
    setelah dipotong padding transparannya, lihat export_pdf.py::_resolve_logo_b64) sama
    dgn 36px/96dpi = 0.375in — jadi ukuran visual akhirnya SAMA PERSIS dgn versi PDF di
    halaman isi.

    BUG DIPERBAIKI LAGI (dilaporkan user: "logo di ppt beda sm yg di pdf"): pemanggil
    cover/penutup TETAP pakai width=Inches(6.0) eksplisit stlh perbaikan di atas — waktu itu
    dianggap "di luar scope" krn usernya cuma minta halaman ISI disamakan. TAPI perbaikan di
    atas (motong padding transparan logo, lihat _resolve_logo_path) mengubah RASIO gambar
    yang dipakai add_picture utk SEMUA pemanggil termasuk cover/penutup (bukan cuma isi) —
    width=6.0in yang SAMA jadi menghasilkan TINGGI logo 2x lebih besar drpd sebelum
    pemotongan (rasio lama ~3.52:1 -> rasio baru ~7.02:1 pd width tetap = tinggi menyusut
    stlh dipotong, TAPI 6.0in itu sendiri tidak pernah dihitung ulang dari rasio baru, jadi
    proporsi visualnya jadi salah — bukan "sengaja beda", cuma efek samping yang belum
    ditindaklanjuti). Sekarang width cover/penutup diturunkan ke 2.85in — dihitung PERSIS
    sama polanya spt konten (target tinggi = 39px/96dpi = 0.40625in, ukuran logo cover/
    penutup versi PDF di _page()/_split_cover_td/_split_closing_td di export_pdf.py, dikali
    rasio ~7.02:1)."""
    if not logo_path:
        return
    x = x if x is not None else (SLIDE_W - width - Inches(0.35))
    try:
        if pill:
            # Bingkai digambar DULU supaya logo berada di atasnya. Tingginya dihitung
            # dari rasio gambar sungguhan, bukan ditebak - rasio logo berubah sejak
            # padding transparannya dipotong (lihat catatan panjang di atas).
            from PIL import Image
            with Image.open(logo_path) as _im:
                _rasio = _im.height / float(_im.width or 1)
            _w_in = Emu(width).inches
            _h_in = _w_in * _rasio
            _pill_logo(
                slide,
                Emu(x).inches - _LOGO_PILL_PAD_X_IN,
                Emu(y).inches - _LOGO_PILL_PAD_Y_IN,
                _w_in + 2 * _LOGO_PILL_PAD_X_IN,
                _h_in + 2 * _LOGO_PILL_PAD_Y_IN,
            )
        slide.shapes.add_picture(logo_path, x, y, width=width)
    except Exception:
        pass


def add_badge_circle(slide, x, y, diameter, text, badge_color, text_color=WHITE, font_size=Pt(14)):
    # BUG NYATA DITEMUKAN (tema "gold" khususnya): banyak pemanggil memberi badge_color =
    # peran "light" tema (ctx.accent_light/theme.light) dgn text_color default WHITE — peran
    # "light" cukup gelap utk tema green/navy/dark tapi SANGAT pucat khusus tema "gold"
    # (dirancang sbg teks di atas latar gelap, bukan fill badge), hasilnya angka putih nyaris
    # tak kelihatan. Digelapkan HANYA kalau text_color memang WHITE (kombinasi lain, mis. teks
    # gelap di atas badge pucat, sudah aman apa adanya) — lihat _light_safe/_badge di
    # export_pdf.py utk versi & penjelasan yang sama persis.
    if text_color == WHITE:
        badge_color = _light_safe(badge_color)
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
    """Return: perkiraan tinggi konten (title+detail, dalam inci) — dipakai add_badge_list
    untuk menggeser baris berikutnya sesuai tinggi SEBENARNYA, bukan jarak tetap."""
    add_badge_circle(slide, x, y, badge_d, number_text, badge_color, font_size=Pt(14))
    text_x = x + badge_d + Inches(0.2)
    text_w = w - badge_d - Inches(0.2)
    box = slide.shapes.add_textbox(text_x, y - Inches(0.03), text_w, Inches(0.95))
    tf = box.text_frame
    tf.word_wrap = True
    p1 = tf.paragraphs[0]
    p1.alignment = PP_ALIGN.LEFT
    p1.text = title_text
    _set_font(p1, BODY_FONT, title_size, bold=True, color=(WHITE if on_dark else TEXT_DARK))
    text_w_in = Emu(text_w).inches
    content_height_in = _estimate_wrapped_height_in(title_text, title_size.pt, text_w_in)
    if detail_text:
        p2 = tf.add_paragraph()
        p2.alignment = PP_ALIGN.LEFT
        p2.text = detail_text
        _set_font(p2, BODY_FONT, detail_size, color=(GOLD_LIGHT if on_dark else GRAY_TEXT))
        p2.space_before = Pt(2)
        content_height_in += _estimate_wrapped_height_in(detail_text, detail_size.pt, text_w_in) + 2 / 72
    return content_height_in


def _estimate_badge_row_height_in(w_in, badge_d_in, title_text, detail_text, title_pt, detail_pt):
    """Estimasi tinggi 1 add_badge_row TANPA menggambar apapun (fungsi murni) — dipakai
    add_badge_list utk pre-pass menghitung total tinggi SEMUA item SEBELUM mulai render."""
    text_w_in = w_in - badge_d_in - 0.2
    h = _estimate_wrapped_height_in(title_text, title_pt, text_w_in)
    if detail_text:
        h += _estimate_wrapped_height_in(detail_text, detail_pt, text_w_in) + 2 / 72
    return h


def add_badge_list(slide, x, y, w, items, badge_color=GREEN_MAIN, row_h=Inches(0.95), on_dark=False, max_y=None, cols=1):
    """items: list of (number_or_letter, title, detail). badge_color: RGBColor tetap ATAU
    fungsi(idx, item)->RGBColor supaya bisa mem-variasi warna (mis. merah utk 1 item kritis).
    `row_h` dipakai sebagai jarak MINIMUM antar baris saja — kalau title/detail dari AI
    kebetulan lebih panjang dan wrap ke banyak baris, jaraknya digeser sesuai perkiraan tinggi
    sebenarnya (dulu selalu jarak tetap, baris berikutnya bisa menimpa baris ini).

    `cols` (default 1, backward compat) — BUG NYATA YANG DIPERBAIKI (dilaporkan user): dipanggil
    dengan `w`=CONTENT_W penuh (mis. Temuan Utama, sampai 6 item) menghasilkan baris selebar
    HAMPIR SELURUH slide (~11.8in dari 13.3in) — capek dibaca, apalagi digabung skala-turun font
    di bawah. `cols=2` membelah item jadi grid 2 kolom (lebar per baris otomatis separuh, jauh
    di bawah ambang ~75 karakter/baris yang wajar dibaca), DAN memangkas jumlah BARIS jadi
    separuhnya — dua-duanya mengurangi kebutuhan skala-turun font drastis dibanding 1 kolom
    penuh utk jumlah item yang sama.

    `max_y` (opsional, disarankan selalu diisi) = batas bawah yang TIDAK BOLEH dilewati (mis.
    SLIDE_H dikurangi margin footer). BUG YANG DIPERBAIKI: sebelum ini tidak ada pengecekan
    apapun terhadap tinggi slide — laporan dengan item lebih banyak (mis. 6 Temuan Utama)
    membuat item ke-5/6 punya posisi Y melebihi slide_height, jadi tidak terlihat sama sekali
    saat dibuka di PowerPoint (bukan error, cuma diam-diam hilang). Sekarang total tinggi
    SEMUA BARIS (bukan item — 1 baris bisa berisi `cols` item berjajar) diperkirakan DULU
    (pre-pass, tanpa menggambar) sebelum mulai render — kalau ternyata bakal melebihi `max_y`,
    seluruh baris (badge, judul, detail, jarak antar baris) dikecilkan skalanya secara
    proporsional supaya SEMUA item pasti muat di dalam slide."""
    if not items:
        return y
    row_h_in = row_h.inches
    col_gap_in = 0.4
    col_w_in = (Emu(w).inches - col_gap_in * (cols - 1)) / cols
    col_w = Inches(col_w_in)
    default_badge_d_in = 0.42
    default_title_pt, default_detail_pt = 15, 12
    n_rows = math.ceil(len(items) / cols)

    scale = 1.0
    if max_y is not None:
        available_in = Emu(max_y - y).inches
        row_heights_in = [
            max(
                row_h_in,
                max(
                    _estimate_badge_row_height_in(col_w_in, default_badge_d_in, it[1], it[2], default_title_pt, default_detail_pt) + 0.15
                    for it in items[r * cols: r * cols + cols]
                ),
            )
            for r in range(n_rows)
        ]
        est_total_in = sum(row_heights_in)
        if available_in > 0 and est_total_in > available_in:
            scale = max(available_in / est_total_in, 0.55)

    title_size = Pt(default_title_pt * scale)
    detail_size = Pt(default_detail_pt * scale)
    badge_d = Inches(default_badge_d_in * scale)
    row_h_scaled_in = row_h_in * scale
    row_gap_in = 0.15 * scale

    cur_y = y
    # PERBAIKAN (dilaporkan user berkali-kali — banyak ruang kosong di bawah slide kalau
    # itemnya sedikit, mis. Temuan Utama cuma 2-3 poin): sebelumnya cuma ada jaring pengaman
    # utk kasus KEBANYAKAN konten (skala turun di atas), tidak ada utk kasus KEKURANGAN
    # konten — daftar pendek selalu nempel rapat ke atas (dekat judul), sisa ruang di bawah
    # dibiarkan kosong. Sekarang dites: kalau (setelah skala di atas, biasanya tetap 1.0 utk
    # kasus ini) total tinggi SEMUA baris ternyata masih jauh di bawah `available_in`, titik
    # mulainya digeser turun supaya blok kontennya tertengahkan vertikal di ruang yang
    # tersedia — pola sama persis dgn yg sudah dipakai di cabang grid kartu
    # _build_recommendations_slide.
    if max_y is not None:
        est_total_scaled_in = sum(row_heights_in) * scale if scale != 1.0 else est_total_in
        if available_in > 0 and est_total_scaled_in < available_in:
            cur_y += Inches((available_in - est_total_scaled_in) / 2)
    for r in range(n_rows):
        row_start = r * cols
        row_items = items[row_start:row_start + cols]
        max_content_h_in = 0.0
        for c, item in enumerate(row_items):
            idx = row_start + c
            color = badge_color(idx, item) if callable(badge_color) else badge_color
            cx = x + c * (col_w + Inches(col_gap_in))
            content_height_in = add_badge_row(slide, cx, cur_y, col_w, item[0], item[1], item[2], color,
                                               badge_d=badge_d, on_dark=on_dark,
                                               title_size=title_size, detail_size=detail_size)
            max_content_h_in = max(max_content_h_in, content_height_in)
        cur_y += Inches(max(row_h_scaled_in, max_content_h_in + row_gap_in))
    return cur_y


def add_stat_card_grid(slide, x, y, w, h, items, cols=3, dark=True, theme: dict | None = None):
    """items: list of (value_str, label_str)."""
    t = theme or THEME_PALETTES["green"]
    if not items:
        return y
    rows = math.ceil(len(items) / cols)
    gap = Inches(0.2)
    # card_h dibatasi maksimum — TANPA batas ini, laporan dengan sedikit stat item (mis. cuma 2
    # kartu KPI utk domain yang tidak punya konsep severity/status) membuat 1 baris itu meregang
    # mengisi SELURUH `h` yang dialokasikan pemanggil (mis. 4.3in), kartu raksasa nyaris kosong
    # utk cuma 1 angka + label pendek. Batasnya SEKARANG bertingkat sesuai jumlah baris (dulu
    # konstan 1.6in utk semua kasus) — laporan dengan SEDIKIT baris (ruang per kartu otomatis
    # lebih longgar) dapat kartu lebih tinggi + font lebih besar supaya ruang terasa terisi
    # proporsional, BUKAN cuma dibuat kecil rata utk menghindari kartu raksasa (keluhan nyata
    # dari pengguna: slide "Ringkasan Eksekutif" isinya cuma sepertiga atas, sisanya kosong).
    max_card_h = {1: Inches(2.6), 2: Inches(2.0)}.get(rows, Inches(1.6))
    natural_card_h = (h - gap * (rows - 1)) / rows
    card_h = min(natural_card_h, max_card_h)
    card_h_in = Emu(card_h).inches
    value_pt = 40 if card_h_in >= 2.2 else 36 if card_h_in >= 1.8 else 32
    label_pt = 13 if card_h_in >= 2.2 else 12 if card_h_in >= 1.8 else 11.5
    for idx, (value, label) in enumerate(items):
        r = idx // cols
        row_start = r * cols
        # Lebar kartu dihitung dari JUMLAH ITEM DI BARIS INI, bukan `cols` tetap — supaya
        # baris terakhir yang isinya lebih sedikit dari `cols` (mis. cuma 1 kartu tersisa)
        # melebar mengisi ruang, bukan tampil sempit dengan sisa ruang kosong di sampingnya.
        row_items_count = min(cols, len(items) - row_start)
        c = idx - row_start
        card_w = (w - gap * (row_items_count - 1)) / row_items_count
        cx = x + c * (card_w + gap)
        cy = y + r * (card_h + gap)
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, cy, card_w, card_h)
        card.fill.solid()
        card.fill.fore_color.rgb = t["main"] if dark else IVORY
        card.line.color.rgb = t["light"]
        card.line.width = Pt(0.75)
        _no_shadow(card)
        _modest_corner(card)
        tf = card.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.word_wrap = True
        p1 = tf.paragraphs[0]
        p1.text = str(value)
        p1.alignment = PP_ALIGN.CENTER
        _set_font(p1, TITLE_FONT, Pt(value_pt), bold=True, color=t["light"] if dark else t["main"])
        p2 = tf.add_paragraph()
        p2.text = label
        p2.alignment = PP_ALIGN.CENTER
        _set_font(p2, BODY_FONT, Pt(label_pt), color=WHITE if dark else TEXT_DARK)
        p2.space_before = Pt(6)
    return y + rows * card_h + (rows - 1) * gap


def add_ivory_panel(slide, x, y, w, h, icon_text, title_text, rows, mode="kv", footnote=None, theme: dict | None = None):
    """mode="kv": rows = [(label, value), ...]. mode="legend": rows = [(color, label, pct), ...]."""
    t = theme or THEME_PALETTES["green"]
    panel = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    panel.fill.solid()
    panel.fill.fore_color.rgb = IVORY
    panel.line.color.rgb = PANEL_BORDER
    panel.line.width = Pt(0.75)
    _no_shadow(panel)
    _modest_corner(panel)  # lihat docstring _modest_corner — bug badge menempel border

    pad = Inches(0.3)
    inner_x = x + pad
    inner_w = w - pad * 2
    cur_y = y + Inches(0.26)

    add_badge_circle(slide, inner_x, cur_y, Inches(0.32), icon_text, t["light"], font_size=Pt(11))
    title_box = slide.shapes.add_textbox(inner_x + Inches(0.45), cur_y + Inches(0.02), inner_w - Inches(0.45), Inches(0.32))
    tp = title_box.text_frame.paragraphs[0]
    tp.alignment = PP_ALIGN.LEFT
    tp.text = title_text.upper()
    _set_font(tp, BODY_FONT, Pt(11.5), bold=True, color=t["main"])
    cur_y += Inches(0.55)

    # BUG YANG DIPERBAIKI: dulu tidak ada pengecekan terhadap `h` (tinggi panel tetap dari
    # pemanggil) — panel dengan banyak baris (mis. legend 6 kategori + footnote) berisiko
    # baris terakhirnya meluber ke luar panel. Total tinggi SEMUA baris diperkirakan DULU
    # (pre-pass), lalu kalau bakal melebihi sisa ruang panel, jarak antar baris & ukuran
    # font dikecilkan proporsional supaya semua baris tetap muat di dalam panel.
    available_in = Emu(h).inches - Emu(cur_y - y).inches - 0.2 - (0.3 if footnote else 0)
    scale = 1.0
    inner_w_in = Emu(inner_w).inches
    if mode == "kv":
        est_total_in = sum(max(0.62, 0.22 + _estimate_wrapped_height_in(str(v), 11.5, inner_w_in) + 0.16) for _, v in rows)
    else:
        label_w_in_est = Emu(inner_w - Inches(1.0)).inches
        est_total_in = sum(max(0.34, _estimate_wrapped_height_in(label, 11, label_w_in_est) + 0.06) for _, label, _ in rows)
    if available_in > 0 and est_total_in > available_in:
        scale = max(available_in / est_total_in, 0.55)

    if mode == "kv":
        # Jarak antar baris menyesuaikan tinggi VALUE sebenarnya (bukan 0.62in tetap) — value
        # bisa berisi teks bebas dengan panjang tidak menentu (mis. nama file yang diunggah
        # pengguna), yang tanpa ini berisiko menimpa baris berikutnya kalau kebetulan panjang.
        label_pt, value_pt = 11.5 * scale, 11.5 * scale
        for label, value in rows:
            # BUG YANG DIPERBAIKI (dilaporkan user): alignment tidak pernah di-set eksplisit
            # di sini — label & value jadi berisiko dirender beda pola (mis. label rata tengah,
            # value rata kiri) tergantung default theme, membuat teks tampak zigzag tidak rapi.
            # Keduanya SEKARANG eksplisit rata kiri, pola yang sama, konsisten satu sama lain.
            lbl_box = slide.shapes.add_textbox(inner_x, cur_y, inner_w, Inches(0.24))
            lp = lbl_box.text_frame.paragraphs[0]
            lp.text = label
            lp.alignment = PP_ALIGN.LEFT
            _set_font(lp, BODY_FONT, Pt(label_pt), bold=True, color=t["main"])
            val_box = slide.shapes.add_textbox(inner_x, cur_y + Inches(0.22 * scale), inner_w, Inches(0.42))
            vtf = val_box.text_frame
            vtf.word_wrap = True
            vp = vtf.paragraphs[0]
            vp.text = str(value)
            vp.alignment = PP_ALIGN.LEFT
            _set_font(vp, BODY_FONT, Pt(value_pt), color=GRAY_TEXT)
            value_height_in = _estimate_wrapped_height_in(str(value), value_pt, inner_w_in)
            cur_y += Inches(max(0.62 * scale, (0.22 + value_height_in + 0.16) * scale))
    else:
        label_w_in = Emu(inner_w - Inches(1.0)).inches
        label_pt = 11 * scale
        for color, label, pct in rows:
            sw = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, inner_x, cur_y + Inches(0.03), Inches(0.14), Inches(0.14))
            sw.fill.solid()
            sw.fill.fore_color.rgb = color
            sw.line.fill.background()
            _no_shadow(sw)
            lbl_box = slide.shapes.add_textbox(inner_x + Inches(0.22), cur_y, inner_w - Inches(1.0), Inches(0.28))
            lp = lbl_box.text_frame.paragraphs[0]
            lp.alignment = PP_ALIGN.LEFT
            lp.text = label
            _set_font(lp, BODY_FONT, Pt(label_pt), color=TEXT_DARK)
            val_box = slide.shapes.add_textbox(inner_x + inner_w - Inches(0.8), cur_y, Inches(0.8), Inches(0.28))
            vp = val_box.text_frame.paragraphs[0]
            vp.text = pct
            vp.alignment = PP_ALIGN.RIGHT
            _set_font(vp, BODY_FONT, Pt(label_pt), bold=True, color=t["main"])
            label_height_in = _estimate_wrapped_height_in(label, label_pt, label_w_in)
            cur_y += Inches(max(0.34 * scale, (label_height_in + 0.06) * scale))

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
        fp.alignment = PP_ALIGN.LEFT
        fp.text = footnote
        _set_font(fp, BODY_FONT, Pt(9.5), italic=True, color=GRAY_TEXT)
    return panel


def add_dark_panel(slide, x, y, w, h, theme: dict | None = None):
    t = theme or THEME_PALETTES["green"]
    panel = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    panel.fill.solid()
    panel.fill.fore_color.rgb = t["bg"]
    panel.line.color.rgb = t["light"]
    panel.line.width = Pt(1)
    _no_shadow(panel)
    _modest_corner(panel)
    return panel


def add_critical_highlight_panel(slide, x, y, w, h, pct_text, sub_text, detail_text=None, theme: dict | None = None, value_color=None):
    """`value_color` opsional (default None = t["light"] spt semula) — dipakai kartu tren
    berarah panah (dynamic_section "Trend Analysis", lihat _build_dynamic_section_slide) utk
    mewarnai angka besar sesuai arah naik/turun/datar, TANPA mengubah tampilan pemanggil lain."""
    t = theme or THEME_PALETTES["green"]
    value_color = value_color or t["light"]
    add_dark_panel(slide, x, y, w, h, theme=t)
    pad = Inches(0.3)
    big_box = slide.shapes.add_textbox(x + pad, y + Inches(0.35), w - pad * 2, Inches(1.0))
    bp = big_box.text_frame.paragraphs[0]
    bp.text = pct_text
    bp.alignment = PP_ALIGN.CENTER
    _set_font(bp, TITLE_FONT, Pt(42), bold=True, color=value_color)

    sub_top_in = 1.35
    sub_box = slide.shapes.add_textbox(x + pad, y + Inches(sub_top_in), w - pad * 2, Inches(0.7))
    stf = sub_box.text_frame
    stf.word_wrap = True
    sp = stf.paragraphs[0]
    sp.text = sub_text
    sp.alignment = PP_ALIGN.CENTER
    _set_font(sp, BODY_FONT, Pt(12.5), color=WHITE)

    if detail_text:
        # Posisi detail_text dihitung dari perkiraan tinggi sub_text sebenarnya (bukan y+2.15
        # tetap) — sub_text panjangnya tidak menentu (kalimat dari data), jadi tanpa ini
        # detail_text (daftar kategori insiden Critical, bisa sampai 6 nama) berisiko tertimpa.
        text_w_in = Emu(w - pad * 2).inches
        sub_height_in = _estimate_wrapped_height_in(sub_text, 12.5, text_w_in)
        detail_top_in = max(sub_top_in + sub_height_in + 0.15, 2.15)
        det_box = slide.shapes.add_textbox(x + pad, y + Inches(detail_top_in), w - pad * 2, h - Inches(detail_top_in) - Inches(0.25))
        dtf = det_box.text_frame
        dtf.word_wrap = True
        dp = dtf.paragraphs[0]
        dp.alignment = PP_ALIGN.LEFT
        dp.text = detail_text
        _set_font(dp, BODY_FONT, Pt(10.5), color=t["soft"])


def add_priority_panel(slide, x, y, w, h, title_text, items, theme: dict | None = None):
    """items: list of (letter, text)."""
    t = theme or THEME_PALETTES["green"]
    add_dark_panel(slide, x, y, w, h, theme=t)
    pad = Inches(0.28)
    title_box = slide.shapes.add_textbox(x + pad, y + Inches(0.22), w - pad * 2, Inches(0.32))
    tp = title_box.text_frame.paragraphs[0]
    tp.alignment = PP_ALIGN.LEFT
    tp.text = title_text.upper()
    _set_font(tp, BODY_FONT, Pt(11.5), bold=True, color=t["light"])
    if not items:
        return
    content_start_y_in = Emu(y).inches + 0.7
    available_in = Emu(h).inches - 0.7 - 0.2
    text_box_w_in = Emu(w - pad * 2 - Inches(0.5)).inches

    # BUG YANG DIPERBAIKI: tidak ada pengecekan sebelumnya terhadap tinggi panel `h` (fixed,
    # dari pemanggil) — item yang cukup banyak/panjang bisa membuat baris terakhir meluber ke
    # luar panel (bahkan ke luar slide). Sekarang total tinggi diperkirakan DULU (pre-pass),
    # dan kalau bakal melebihi `h`, badge+teks+jarak antar baris dikecilkan proporsional.
    scale = 1.0
    est_total_in = sum(max(0.62, _estimate_wrapped_height_in(text, 13, text_box_w_in) + 0.2) for _, text in items)
    if available_in > 0 and est_total_in > available_in:
        scale = max(available_in / est_total_in, 0.55)

    badge_d = Inches(0.36 * scale)
    font_pt = 13 * scale
    row_min_in = 0.62 * scale
    cur_y = Inches(content_start_y_in)
    for letter, text in items:
        add_badge_circle(slide, x + pad, cur_y, badge_d, letter, t["light"], font_size=Pt(13 * scale))
        box = slide.shapes.add_textbox(x + pad + Inches(0.5), cur_y + Inches(0.02), w - pad * 2 - Inches(0.5), Inches(0.55))
        btf = box.text_frame
        btf.word_wrap = True
        bp = btf.paragraphs[0]
        bp.alignment = PP_ALIGN.LEFT
        bp.text = text
        _set_font(bp, BODY_FONT, Pt(font_pt), color=WHITE)
        # Baris berikutnya digeser sesuai perkiraan tinggi teks yang SEBENARNYA (bukan jarak
        # tetap) — teks rekomendasi dari AI panjangnya tidak menentu, dan jarak tetap bikin
        # baris berikutnya menimpa baris ini kalau teksnya wrap lebih dari ~2 baris.
        text_height_in = _estimate_wrapped_height_in(text, font_pt, text_box_w_in)
        cur_y += Inches(max(row_min_in, text_height_in * scale + 0.2 * scale))


def add_bullet_lines(slide, x, y, w, text, theme: dict | None = None, font_pt: float = 9.5, numbered: bool = False) -> float:
    """Baris bullet polos (titik warna aksen + teks), TANPA bungkus kotak/judul — dipakai
    add_note_box di bawah (mode penuh, kotak+judul "Catatan:") DAN tile insight_dashboard
    (mode ringkas, tile-nya sudah dibungkus kartu bordered sendiri, jadi kotak-dalam-kotak
    kalau dipakaikan add_note_box utuh lagi di situ). Return tinggi total (inci) yang
    terpakai, supaya pemanggil bisa menaruh elemen berikutnya tepat di bawahnya.

    PERMINTAAN USER: kotak catatan harus bisa memuat BEBERAPA butir bernomor, kalimat UTUH —
    `text` sekarang boleh list/tuple string (1 butir = 1 baris APA ADANYA, `numbered=True`
    menomori 1./2./3.), selain string biasa (perilaku LAMA: dipecah otomatis per kalimat)."""
    t = theme or THEME_PALETTES["green"]
    if isinstance(text, (list, tuple)):
        lines = [str(l).strip() for l in text if str(l or "").strip()]
    else:
        lines = [l for l in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if l]
    if not lines:
        return 0.0
    bullet_w_in = 0.22 if numbered else 0.15
    text_w_in = Emu(w).inches - bullet_w_in
    cur_y_in = Emu(y).inches
    for i, line in enumerate(lines):
        lh = _estimate_wrapped_height_in(line, font_pt, text_w_in) + 0.05
        bullet_box = slide.shapes.add_textbox(x, Inches(cur_y_in), Inches(bullet_w_in), Inches(lh))
        bp = bullet_box.text_frame.paragraphs[0]
        bp.alignment = PP_ALIGN.LEFT
        bp.text = f"{i + 1}." if numbered else "•"
        _set_font(bp, BODY_FONT, Pt(font_pt), bold=True, color=t["main"])
        line_box = slide.shapes.add_textbox(x + Inches(bullet_w_in), Inches(cur_y_in), w - Inches(bullet_w_in), Inches(lh))
        ltf = line_box.text_frame
        ltf.word_wrap = True
        lp = ltf.paragraphs[0]
        lp.alignment = PP_ALIGN.LEFT
        lp.text = line
        _set_font(lp, BODY_FONT, Pt(font_pt), color=GRAY_TEXT)
        cur_y_in += lh
    return cur_y_in - Emu(y).inches


def _note_box_height_in(w_in: float, lines) -> float:
    """Tinggi kotak catatan, DIHITUNG TERPISAH dari penggambarannya.

    BUG NYATA DIPERBAIKI (dilaporkan user dgn koordinat persis dari file PPTX: kotak Catatan
    y=2.17-4.17 menutup total sel heatmap Senin/Selasa/Rabu): dulu tinggi kotak baru diketahui
    SESUDAH digambar, jadi pemanggil tidak punya cara memesan ruang lebih dulu - satu-satunya
    pilihannya menggambar catatan di y yang SAMA dgn chart. Ini bentuk yang sama dgn akar
    Prioritas 1: elemen lahir di luar anggaran tata letak. Dgn tingginya bisa dihitung dulu,
    chart bisa dipendekkan TEPAT sebanyak ruang yang dipakai catatan."""
    lines = [str(l).strip() for l in (lines or []) if str(l or "").strip()]
    if not lines:
        return 0.0
    text_w_in = w_in - 0.15 * 2 - 0.15
    return 0.14 + 0.24 + sum(
        _estimate_wrapped_height_in(line, 10, text_w_in) + 0.05 for line in lines) + 0.1


def add_note_box(slide, x, y, w, text, theme: dict | None = None, title: str | None = None):
    """Kotak "Catatan:" (garis kiri warna aksen + bullet per kalimat, lewat add_bullet_lines
    di atas) — GANTI dari add_ai_insight_strip lama (1 baris italic polos) supaya caption AI
    terasa seperti kotak catatan di laporan referensi, BUKAN paragraf mengalir biasa (temuan
    user: laporan masih terasa "berat kata-kata" meski chart-nya sudah ada). Tinggi kotak
    dihitung dari estimasi wrap tiap baris (_estimate_wrapped_height_in) supaya tidak
    overflow/kependekan kalau captionnya panjang. Return tinggi kotak (inci) supaya
    pemanggil bisa menaruh elemen berikutnya tepat di bawahnya. `text` boleh list/tuple
    (beberapa butir bernomor, kalimat utuh) — lihat add_bullet_lines."""
    # Bawaan ikut BAHASA LAPORAN, bukan Indonesia (kembaran perbaikan di export_pdf.py).
    title = title or ("Notes" if render_is_en() else "Catatan")
    t = theme or THEME_PALETTES["green"]
    numbered = isinstance(text, (list, tuple))
    lines = [str(l).strip() for l in text if str(l or "").strip()] if numbered else [
        l for l in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if l
    ]
    if not lines:
        return 0.0
    pad_in = 0.15
    body_font_pt = 10
    box_h_in = _note_box_height_in(Emu(w).inches, lines)

    box = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, Inches(box_h_in))
    box.fill.solid()
    box.fill.fore_color.rgb = IVORY
    box.line.fill.background()
    _no_shadow(box)
    # WARNA NETRAL (bukan aksen tema) — mirror export_pdf.py::_note_box_html, lihat catatan di
    # sana (rule: warna cuma dipakai utk makna, bukan hiasan kotak catatan).
    accent = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, Inches(0.045), Inches(box_h_in))
    accent.fill.solid()
    accent.fill.fore_color.rgb = GRAY_TEXT
    accent.line.fill.background()
    _no_shadow(accent)

    title_box = slide.shapes.add_textbox(x + Inches(pad_in), y + Inches(0.09), w - Inches(pad_in * 2), Inches(0.22))
    tp = title_box.text_frame.paragraphs[0]
    tp.alignment = PP_ALIGN.LEFT
    tp.text = f"{title}:"
    # A5 (kembaran export_pdf.py): label "Catatan:" HIJAU BOLD ITALIC seperti acuan.
    _set_font(tp, BODY_FONT, Pt(8.5), bold=True, color=CATATAN_LABEL)
    tp.font.italic = True

    add_bullet_lines(
        slide, x + Inches(pad_in), y + Inches(0.14 + 0.24), w - Inches(pad_in * 2), text,
        theme=t, font_pt=body_font_pt, numbered=numbered,
    )
    return box_h_in


def add_pill_stat(slide, x, y, w, h, text, theme: dict | None = None):
    t = theme or THEME_PALETTES["green"]
    pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    try:
        pill.adjustments[0] = 0.5
    except Exception:
        pass
    pill.fill.solid()
    pill.fill.fore_color.rgb = t["main"]
    pill.line.color.rgb = t["light"]
    pill.line.width = Pt(1)
    _no_shadow(pill)
    tf = pill.text_frame
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.text = text
    p.alignment = PP_ALIGN.CENTER
    _set_font(p, BODY_FONT, Pt(13), bold=True, color=t["light"])


def add_asset_card_row(slide, x, y, w, h, items, theme: dict | None = None, scale: float = 1.0):
    """items: list of (badge_num, title, stat_text, desc_text). `h` adalah tinggi ZONA yang
    dialokasikan pemanggil (bisa jauh lebih besar dari kebutuhan konten sebenarnya).

    BUG DIPERBAIKI (ditemukan lewat tes kepadatan halaman, permintaan user lanjutan — "isi
    via konten, bukan jarak"): kartu SEBELUMNYA dipusatkan begitu saja di zona `h` (perbaikan
    lama, docstring asli di bawah) — kalau `h` jauh lebih besar dari kebutuhan konten (solo
    di 1 halaman penuh), sisa ruang jadi MARGIN kosong di atas/bawah, bukan isi. `scale`
    (dari ctx.panel_count di pemanggil, sama pola dgn _build_management_action_items_block)
    membesarkan badge/font/padding scr proporsional supaya kartu terasa disengaja besar,
    bukan kartu kecil mengambang di tengah halaman kosong."""
    t = theme or THEME_PALETTES["green"]
    n = len(items)
    if n == 0:
        return y
    gap = Inches(0.3)
    card_w = (w - gap * (n - 1)) / n
    pad = Inches(0.22 * scale)
    pad_in = 0.22 * scale
    text_w_in = Emu(card_w).inches - pad_in * 2

    # Tinggi kartu ikut kebutuhan konten sebenarnya (badge+judul+stat+deskripsi, DIKALIKAN
    # scale) — baris kartu (SATU tinggi utk semua kartu di baris ini, dari deskripsi
    # TERPANJANG) lalu diposisikan di TENGAH zona `h`, sisa ruang kosong (kalau MASIH ada
    # setelah scale) terbagi rata atas & bawah drpd dipaksa 0.
    max_desc_h_in = max(
        (_estimate_wrapped_height_in(desc, 10.5 * scale, text_w_in) for _, _, _, desc in items),
        default=0,
    )
    content_h_in = 1.77 * scale + max_desc_h_in + pad_in
    card_h_in = min(max(content_h_in, 2.2 * scale), Emu(h).inches)
    card_h = Inches(card_h_in)
    row_y = y + Inches(max(0.0, (Emu(h).inches - card_h_in) / 2))

    badge_d_in = 0.42 * scale
    for idx, (num, title, stat, desc) in enumerate(items):
        cx = x + idx * (card_w + gap)
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, row_y, card_w, card_h)
        card.fill.solid()
        card.fill.fore_color.rgb = t["main"]
        card.line.color.rgb = t["light"]
        card.line.width = Pt(0.75)
        _no_shadow(card)
        _modest_corner(card)
        add_badge_circle(slide, cx + pad, row_y + pad, Inches(badge_d_in), num, t["light"], font_size=Pt(15 * scale))
        # BUG DIPERBAIKI (audit E3, low-confidence tapi murah utk dijaga): title_box/stat_box
        # dulu offset TETAP (0.55in/1.1in) apa pun panjang `title` (nama aset/vendor dari
        # data) — nama yang kebetulan panjang (>2 baris di 15pt bold) bisa menimpa stat_box.
        # title_h_in sekarang ikut estimasi wrap sungguhan (floor 0.55in spy kartu pendek
        # tidak berubah tampilannya sama sekali dari sebelumnya).
        title_h_in = max(0.55 * scale, _estimate_wrapped_height_in(title, 15 * scale, text_w_in))
        title_box = slide.shapes.add_textbox(cx + pad, row_y + pad + Inches(0.55 * scale), card_w - pad * 2, Inches(title_h_in))
        ttf = title_box.text_frame
        ttf.word_wrap = True
        tp = ttf.paragraphs[0]
        tp.alignment = PP_ALIGN.LEFT
        tp.text = title
        _set_font(tp, BODY_FONT, Pt(15 * scale), bold=True, color=WHITE)
        stat_y_in = 0.55 * scale + title_h_in
        stat_box = slide.shapes.add_textbox(cx + pad, row_y + pad + Inches(stat_y_in), card_w - pad * 2, Inches(0.35 * scale))
        sp = stat_box.text_frame.paragraphs[0]
        sp.alignment = PP_ALIGN.LEFT
        sp.text = stat
        _set_font(sp, BODY_FONT, Pt(13 * scale), bold=True, color=t["light"])
        desc_y_in = stat_y_in + 0.45 * scale
        desc_box = slide.shapes.add_textbox(cx + pad, row_y + pad + Inches(desc_y_in), card_w - pad * 2, card_h - Inches(desc_y_in) - pad * 2)
        dtf = desc_box.text_frame
        dtf.word_wrap = True
        dp = dtf.paragraphs[0]
        dp.alignment = PP_ALIGN.LEFT
        dp.text = desc
        _set_font(dp, BODY_FONT, Pt(10.5 * scale), color=RGBColor(0xE8, 0xEC, 0xE6))
    return row_y + card_h


_ASSET_LEVEL_TIERS_PPT = (
    (0.66, ("Tinggi", "High"), RGBColor(0x2E, 0x7D, 0x46)),
    (0.33, ("Sedang", "Medium"), GOLD_MAIN),
    (0.0, ("Rendah", "Low"), GRAY_TEXT),
)


def add_asset_ranked_bars(slide, x, y, w, items, row_h=Inches(1.0), theme: dict | None = None, is_en: bool = False):
    """Alternatif visual KETIGA (selain add_asset_card_row/add_podium_row) — daftar entitas
    berperingkat dengan batang proporsional horizontal per item (badge nomor + nama + badge
    level + batang + angka) — titik variasi tampilan tambahan utk asset_cards (lihat
    `asset_style`). items: list of dict {num,name,stat,count}. Dipakai utk jumlah item BERAPA
    PUN (podium hanya cocok tepat 3).

    PERMINTAAN USER ("kartu bersarang": header berwarna + skor besar + badge level + daftar
    bar mini berlabel dengan garis target) — mirror export_pdf.py::_asset_ranked_bars_html:
    badge level dari posisi RELATIF nilai item ini thd nilai tertinggi, garis target dari
    posisi RATA-RATA seluruh item (bukan angka sembarang)."""
    t = theme or THEME_PALETTES["green"]
    counts = [it.get("count") or 0 for it in items]
    max_count = max(counts) or 1
    avg_count = (sum(counts) / len(counts)) if counts else 0
    avg_frac = (avg_count / max_count) if counts and max_count else 0
    if not items:
        # BUG DIPERBAIKI (audit F2, defense-in-depth): pemanggil saat ini (pick_category())
        # tidak pernah mengembalikan list kosong, TAPI max(counts) di bawah akan ValueError
        # kalau suatu saat itu berubah — dijaga eksplisit spt saudara2nya (add_stat_card_grid
        # dkk) drpd diam2 bergantung pada jaminan pemanggil yang tidak ditegakkan di sini.
        return y
    badge_d = Inches(0.4)
    track_h = Inches(0.16)
    stat_w = Inches(1.1)
    track_x = x + badge_d + Inches(0.18)
    track_w = w - badge_d - Inches(0.18) - stat_w - Inches(0.1)
    cur_y = y
    for idx, it in enumerate(items):
        frac = (it.get("count") or 0) / max_count if max_count else 0
        frac = max(frac, 0.04)
        level_label, level_color = "", GRAY_TEXT
        for threshold, (lbl_id, lbl_en), color in _ASSET_LEVEL_TIERS_PPT:
            if frac >= threshold:
                level_label, level_color = (lbl_en if is_en else lbl_id), color
                break
        add_badge_circle(slide, x, cur_y, badge_d, it["num"], t["light"], font_size=Pt(13))
        name_box = slide.shapes.add_textbox(track_x, cur_y - Inches(0.03), track_w, Inches(0.32))
        ntf = name_box.text_frame
        np_ = ntf.paragraphs[0]
        np_.alignment = PP_ALIGN.LEFT
        name_run = np_.add_run()
        name_run.text = it["name"] + "  "
        _set_font(name_run, BODY_FONT, Pt(13), bold=True, color=WHITE)
        level_run = np_.add_run()
        level_run.text = level_label.upper()
        _set_font(level_run, BODY_FONT, Pt(8), bold=True, color=level_color)
        stat_box = slide.shapes.add_textbox(x + w - stat_w, cur_y - Inches(0.03), stat_w, Inches(0.32))
        sp = stat_box.text_frame.paragraphs[0]
        sp.text = it["stat"]
        sp.alignment = PP_ALIGN.RIGHT
        _set_font(sp, BODY_FONT, Pt(12), bold=True, color=t["light"])

        track_y = cur_y + Inches(0.36)
        track = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, track_x, track_y, track_w, track_h)
        track.fill.solid()
        track.fill.fore_color.rgb = t["chart"]
        track.line.fill.background()
        _no_shadow(track)
        _modest_corner(track, frac=0.5)
        fill_w = Inches(max(Emu(track_w).inches * frac, 0.15))
        fill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, track_x, track_y, fill_w, track_h)
        fill.fill.solid()
        fill.fill.fore_color.rgb = t["light"]
        fill.line.fill.background()
        _no_shadow(fill)
        _modest_corner(fill, frac=0.5)
        target_x = track_x + Inches(Emu(track_w).inches * avg_frac)
        target_line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, target_x, track_y - Inches(0.02), Inches(0.02), track_h + Inches(0.04))
        target_line.fill.solid()
        target_line.fill.fore_color.rgb = WHITE
        target_line.line.color.rgb = TEXT_DARK
        target_line.line.width = Pt(0.5)
        _no_shadow(target_line)
        # PERMINTAAN USER ("angka harus melekat di chart") - kembar dari _asset_ranking_rows
        # di export_pdf.py: garis target dulu tanpa angka sama sekali. Cuma di baris PERTAMA
        # (garisnya sama utk semua baris) & ditaruh DI BAWAH track, di ruang antar baris.
        if idx == 0:
            _avg_lbl = slide.shapes.add_textbox(
                target_x - Inches(0.35), track_y + track_h, Inches(0.7), Inches(0.16))
            _ap = _avg_lbl.text_frame.paragraphs[0]
            _ap.text = ("avg " if is_en else "rata-rata ") + _fmt_num(round(avg_count, 1))
            _ap.alignment = PP_ALIGN.CENTER
            _set_font(_ap, BODY_FONT, Pt(6.5), color=RGBColor(0xC9, 0xCF, 0xC5))
        cur_y += row_h
    footnote_box = slide.shapes.add_textbox(x, cur_y, w, Inches(0.2))
    ftp = footnote_box.text_frame.paragraphs[0]
    ftp.alignment = PP_ALIGN.LEFT
    ftp.text = ("Target line = average" if is_en else "Garis target = rata-rata") + f" ({_fmt_num(round(avg_count, 1))})"
    _set_font(ftp, BODY_FONT, Pt(7.5), color=RGBColor(0xC9, 0xCF, 0xC5))
    return cur_y + Inches(0.22)


def add_podium_row(slide, x, y, w, h, items, theme: dict | None = None):
    """items: TEPAT 3 dict {"num","name","stat"} — analog `_podium_row()` di export_pdf.py.
    Titik variasi tampilan utk asset_cards (lihat `asset_style` di generate_ppt_report),
    alternatif dari `add_asset_card_row` (baris kartu rata) — rank #1 di TENGAH & PALING
    TINGGI, meniru podium juara, dipakai kalau kebetulan item persis 3 (ranking top-3)."""
    t = theme or THEME_PALETTES["green"]
    if len(items) != 3:
        return Emu(y).inches + Emu(h).inches
    order = [1, 0, 2]  # tampil sbg [rank2, rank1, rank3] spy rank1 di tengah
    ranked = [items[i] for i in order]
    height_frac = [0.73, 1.0, 0.55]
    colors = [t["main"], t["light"], t["chart"]]
    gap = Inches(0.35)
    col_w = (w - gap * 2) / 3
    label_zone_in = 1.0
    base_bottom_in = Emu(y).inches + Emu(h).inches
    pedestal_max_h_in = max(0.8, Emu(h).inches - label_zone_in)

    for idx, item in enumerate(ranked):
        cx = x + idx * (col_w + gap)
        ped_h_in = max(0.55, pedestal_max_h_in * height_frac[idx])
        ped_top_in = base_bottom_in - ped_h_in

        name_box = slide.shapes.add_textbox(cx, Inches(ped_top_in - label_zone_in), col_w, Inches(0.32))
        np_ = name_box.text_frame.paragraphs[0]
        np_.text = item["name"]
        np_.alignment = PP_ALIGN.CENTER
        _set_font(np_, BODY_FONT, Pt(13), bold=True, color=TEXT_DARK)

        stat_box = slide.shapes.add_textbox(cx, Inches(ped_top_in - label_zone_in + 0.34), col_w, Inches(0.4))
        stf = stat_box.text_frame
        stf.word_wrap = True
        sp = stf.paragraphs[0]
        sp.text = item["stat"]
        sp.alignment = PP_ALIGN.CENTER
        _set_font(sp, BODY_FONT, Pt(11), color=GRAY_TEXT)

        pedestal = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, Inches(ped_top_in), col_w, Inches(ped_h_in))
        pedestal.fill.solid()
        pedestal.fill.fore_color.rgb = colors[idx]
        pedestal.line.fill.background()
        _no_shadow(pedestal)
        _modest_corner(pedestal, frac=0.1)
        tf = pedestal.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        pnum = tf.paragraphs[0]
        pnum.text = item["num"]
        pnum.alignment = PP_ALIGN.CENTER
        _set_font(pnum, TITLE_FONT, Pt(28), bold=True, color=WHITE)
    return base_bottom_in


def add_recommendation_timeline(slide, x, y, w, h, items, theme: dict | None = None):
    """items: 2-6 dict {"num","title","detail"} — analog `_timeline_html()` di
    export_pdf.py. Titik variasi tampilan utk recommendations (lihat `recommendation_style`
    di generate_ppt_report), alternatif dari grid kartu — garis horizontal di tengah `h`
    dengan node bergantian di ATAS/BAWAH garis, dipakai kalau jumlah item pas 2-6 (bukan
    grid biasa)."""
    t = theme or THEME_PALETTES["green"]
    n = len(items)
    if not (2 <= n <= 6):
        return False
    mid_y = y + h // 2
    # _light_safe: t["light"] SENGAJA pucat di tema "gold" (dirancang utk teks di atas latar
    # gelap) — dipakai apa adanya di sini (garis tipis di atas latar TERANG) nyaris tak
    # kelihatan, lihat _light_safe/_timeline_html di export_pdf.py utk penjelasan yang sama.
    line_color = _light_safe(t["light"])
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, mid_y - Pt(1), w, Pt(2))
    line.fill.solid()
    line.fill.fore_color.rgb = line_color
    line.line.fill.background()
    _no_shadow(line)

    node_d = Inches(0.4)
    slot_w = w // n
    text_w = slot_w - Inches(0.25)
    text_w_in = Emu(text_w).inches

    # PERBAIKAN (dilaporkan user, screenshot — item ganjil/genap kepotong/patah di
    # tengah teks walau ruang di sekitarnya masih kosong): box_h SEBELUMNYA flat
    # 1.5in tanpa peduli panjang teks aktualnya — beda dari _timeline_html (versi
    # PDF, sudah lebih dulu dibenahi) yang menghitung tinggi kontainer dari
    # perkiraan teks TERPANJANG. Sekarang dihitung dgn pola yang sama (memakai
    # _estimate_wrapped_height_in yg sudah dipakai cabang grid kartu di bawah),
    # dibatasi supaya tidak melebihi ruang yg benar2 tersedia (setengah tinggi h).
    def _content_h_in(it):
        height_in = _estimate_wrapped_height_in(it.get("title", ""), 12.5, text_w_in)
        if it.get("detail"):
            height_in += _estimate_wrapped_height_in(it["detail"], 9.5, text_w_in) + 3 / 72
        return height_in

    max_content_in = max((_content_h_in(it) for it in items), default=1.5)
    available_half_in = Emu(h // 2 - node_d // 2 - Inches(0.1)).inches
    box_h = Inches(min(max(1.5, max_content_in + 0.15), max(available_half_in, 1.5)))
    for idx, item in enumerate(items):
        node_cx = x + slot_w * idx + slot_w // 2
        above = (idx % 2 == 0)
        node = slide.shapes.add_shape(MSO_SHAPE.OVAL, node_cx - node_d // 2, mid_y - node_d // 2, node_d, node_d)
        node.fill.solid()
        node.fill.fore_color.rgb = t["main"]
        node.line.color.rgb = line_color
        node.line.width = Pt(1.5)
        _no_shadow(node)
        ntf = node.text_frame
        ntf.vertical_anchor = MSO_ANCHOR.MIDDLE
        ntf.margin_left = ntf.margin_right = ntf.margin_top = ntf.margin_bottom = 0
        np_ = ntf.paragraphs[0]
        np_.text = item["num"]
        np_.alignment = PP_ALIGN.CENTER
        _set_font(np_, BODY_FONT, Pt(13), bold=True, color=WHITE)

        text_x = node_cx - text_w // 2
        if above:
            box_y = mid_y - node_d // 2 - box_h - Inches(0.1)
        else:
            box_y = mid_y + node_d // 2 + Inches(0.1)
        box = slide.shapes.add_textbox(text_x, box_y, text_w, box_h)
        tf = box.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.BOTTOM if above else MSO_ANCHOR.TOP
        p = tf.paragraphs[0]
        p.text = item["title"]
        p.alignment = PP_ALIGN.CENTER
        _set_font(p, BODY_FONT, Pt(12.5), bold=True, color=TEXT_DARK)
        if item.get("detail"):
            p2 = tf.add_paragraph()
            p2.text = item["detail"]
            p2.alignment = PP_ALIGN.CENTER
            _set_font(p2, BODY_FONT, Pt(9.5), color=GRAY_TEXT)
            p2.space_before = Pt(3)
    return True


def add_recommendation_banner_list(slide, x, y, w, items, title_pt=13, detail_pt=10.5, max_y=None, theme: dict | None = None):
    """Alternatif visual KETIGA (selain grid kartu/add_recommendation_timeline) — daftar
    rekomendasi sebagai banner selebar `w` bertumpuk vertikal (badge nomor + judul + detail)
    — titik variasi tampilan tambahan utk recommendations (lihat `recommendation_style`),
    dipakai utk jumlah item BERAPA PUN (timeline dibatasi 2-6). `max_y` opsional — kalau
    total tinggi bakal melebihi, font & tinggi banner dikecilkan proporsional (pola sama
    dengan add_badge_list/add_priority_panel di file ini)."""
    t = theme or THEME_PALETTES["green"]
    if not items:
        return y
    badge_d = Inches(0.4)
    pad = Inches(0.18)
    gap = Inches(0.14)
    text_x = x + badge_d + Inches(0.35)
    text_w_in = Emu(w - badge_d - Inches(0.35) - Inches(0.15)).inches

    def _row_h_in(it, tpt, dpt):
        h = _estimate_wrapped_height_in(it["title"], tpt, text_w_in)
        if it.get("detail"):
            h += _estimate_wrapped_height_in(it["detail"], dpt, text_w_in) + 0.06
        return max(0.62, h + Emu(pad).inches * 2)

    scale = 1.0
    if max_y is not None:
        available_in = Emu(max_y - y).inches
        est_total_in = sum(_row_h_in(it, title_pt, detail_pt) + Emu(gap).inches for it in items) - Emu(gap).inches
        if available_in > 0 and est_total_in > available_in:
            scale = max(available_in / est_total_in, 0.6)

    title_pt_s = title_pt * scale
    detail_pt_s = detail_pt * scale
    cur_y = y
    for it in items:
        row_h_in = _row_h_in(it, title_pt_s, detail_pt_s)
        row_h = Inches(row_h_in)
        banner = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, cur_y, w, row_h)
        banner.fill.solid()
        banner.fill.fore_color.rgb = IVORY
        banner.line.color.rgb = PANEL_BORDER
        banner.line.width = Pt(0.75)
        _no_shadow(banner)
        _modest_corner(banner)
        add_badge_circle(slide, x + pad, cur_y + pad, Inches(0.4 * scale), it["num"], t["light"], font_size=Pt(13 * scale))
        # BUG YANG DIPERBAIKI: title_box dulu tinggi TETAP 0.4in, sementara det_box di bawahnya
        # diposisikan berdasarkan estimasi tinggi KONTEN sebenarnya (title_h_in, sering < 0.4in
        # utk judul 1 baris) — box tetap 0.4in penuh jadi bounding-box-nya menimpa det_box
        # (pola sama yang sudah diperbaiki di beberapa tempat lain file ini). Tinggi title_box
        # sekarang eksplisit mengikuti estimasi yang sama dipakai utk memposisikan det_box.
        title_h_in = _estimate_wrapped_height_in(it["title"], title_pt_s, text_w_in)
        title_box = slide.shapes.add_textbox(text_x, cur_y + pad - Inches(0.02), Inches(text_w_in), Inches(title_h_in + 0.08))
        ttf = title_box.text_frame
        ttf.word_wrap = True
        tp = ttf.paragraphs[0]
        tp.alignment = PP_ALIGN.LEFT
        tp.text = it["title"]
        _set_font(tp, BODY_FONT, Pt(title_pt_s), bold=True, color=TEXT_DARK)
        if it.get("detail"):
            det_box = slide.shapes.add_textbox(text_x, cur_y + pad + Inches(title_h_in + 0.04), Inches(text_w_in), Inches(max(0.3, row_h_in - Emu(pad).inches - title_h_in)))
            dtf = det_box.text_frame
            dtf.word_wrap = True
            dp = dtf.paragraphs[0]
            dp.alignment = PP_ALIGN.LEFT
            dp.text = it["detail"]
            _set_font(dp, BODY_FONT, Pt(detail_pt_s), color=GRAY_TEXT)
        cur_y += row_h + gap
    return cur_y


def _paksa_semua_label_sumbu(axis):
    """Setel c:tickLblSkip=1 - PowerPoint dilarang melewati label kategori.

    Tanpa ini, plot yang pendek membuat PowerPoint diam-diam membuang sebagian nama batang.
    Urutan anak di CT_CatAx ditentukan skema: tickLblSkip harus SEBELUM tickMarkSkip &
    noMultiLvlLbl, jadi disisipkan relatif ke keduanya, bukan di-append begitu saja."""
    from pptx.oxml.ns import qn
    el = axis._element
    ada = el.find(qn("c:tickLblSkip"))
    if ada is not None:
        ada.set("val", "1")
        return
    node = el.makeelement(qn("c:tickLblSkip"), {"val": "1"})
    for nama in ("c:tickMarkSkip", "c:noMultiLvlLbl"):
        sesudah = el.find(qn(nama))
        if sesudah is not None:
            sesudah.addprevious(node)
            return
    el.append(node)


def _emu(v):
    """Bulatkan panjang apa pun jadi EMU bilangan bulat.

    BUG PRE-EXISTING DIPERBAIKI (disetujui user): pembagian `/` Python 3 menghasilkan float,
    dan python-pptx menuliskannya MENTAH ke XML - `x="4523232.0"`. OOXML mensyaratkan EMU
    bilangan bulat, jadi PowerPoint menolak berkasnya & meminta "repair". Terukur di jalur
    Descriptive: 9 atribut pecahan di slide3/4/5/7. Kelas bug yang sama sudah ditambal di
    jalur Management; helper ini menutupnya di SATU pintu masuk - semua chart native lewat
    add_chart()."""
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return v


def add_native_bar_chart(slide, x, y, cx, cy, categories, values, colors=None, horizontal=False,
                         label_pt: float | None = None, jangan_lewati_label: bool = False):
    chart_data = CategoryChartData()
    chart_data.categories = categories
    chart_data.add_series("Jumlah", values)
    chart_type = XL_CHART_TYPE.BAR_CLUSTERED if horizontal else XL_CHART_TYPE.COLUMN_CLUSTERED
    gframe = slide.shapes.add_chart(chart_type, _emu(x), _emu(y), _emu(cx), _emu(cy), chart_data)
    chart = gframe.chart
    chart.has_legend = False
    # BUG YANG DIPERBAIKI (dilaporkan user, disertai tangkapan layar): python-pptx/PowerPoint
    # menampilkan judul chart DEFAULT berupa nama series ("Jumlah") kalau tidak dimatikan
    # eksplisit — nongol polos warna hitam, tidak nyambung sama gaya desain sekitarnya.
    chart.has_title = False

    plot = chart.plots[0]
    plot.has_data_labels = True
    dl = plot.data_labels
    # `label_pt` DITAMBAHKAN belakangan (jalur Management). Default None = 11pt persis spt
    # sebelumnya, supaya jalur Descriptive yang memanggil fungsi ini nol dampak.
    dl.font.size = Pt(label_pt or 11)
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
        # BUG DIPERBAIKI (drift vs export_pdf.py::_bar_chart_html/_grouped_bar_chart_svg —
        # versi PDF TIDAK PERNAH menampilkan skala sumbu angka sama sekali, nilai ditulis
        # sbg data label langsung di/atas tiap batang): sumbu KATEGORI (nama batang) tetap
        # ditampilkan labelnya (itu perlu, sbg satu2nya penanda batang mana punya siapa),
        # tapi tick MARK (garis kecil) & sumbu NILAI (garis+angka+gridline) di sini
        # sebelumnya cuma gridline-nya yang dimatikan — sumbu nilai, tick mark keduanya, dan
        # gridline minor belum ikut dimatikan, jadi PPT masih ada "furniture" chart yang
        # versi PDF-nya sama sekali tidak ada.
        chart.category_axis.has_major_gridlines = False
        chart.category_axis.has_minor_gridlines = False
        chart.category_axis.major_tick_mark = XL_TICK_MARK.NONE
        chart.category_axis.minor_tick_mark = XL_TICK_MARK.NONE
        chart.category_axis.tick_labels.font.size = Pt(label_pt or 11)
        chart.category_axis.tick_labels.font.name = BODY_FONT
        if jangan_lewati_label:
            _paksa_semua_label_sumbu(chart.category_axis)
        chart.value_axis.has_major_gridlines = False
        chart.value_axis.has_minor_gridlines = False
        chart.value_axis.visible = False
    except Exception:
        pass
    return gframe


def add_native_doughnut_chart(
    slide, x, y, cx, cy, categories, values, colors=None, theme: dict | None = None,
    show_data_labels: bool = True, show_center_total: bool = False, total_label: str = "Total",
):
    """Alternatif visual utk distribusi kategori (selain add_native_bar_chart) — titik
    variasi tampilan antar generate (lihat `category_style` di generate_ppt_report), chart
    doughnut NATIVE PowerPoint (bukan gambar statis) supaya tetap bisa diedit user kalau mau,
    konsisten dengan seluruh chart lain di file ini.

    `show_data_labels=False` + `show_center_total=True` (dipakai KHUSUS donut ukuran tile
    dashboard, lihat _build_management_visual_dashboard_slide) — BUG DIPERBAIKI (drift vs
    export_pdf.py::_donut_chart_svg, yang SELALU menampilkan angka TOTAL besar di tengah
    cincin, BUKAN label per-slice): versi PPT ini sebelumnya SELALU nyalakan data label
    per-slice (angka di atas tiap potongan) & TIDAK PERNAH punya angka total di tengah —
    di ukuran donut sekecil tile dashboard, data label per-slice numpuk/tumpang tindih &
    tidak menyampaikan info yang sama dgn versi PDF sama sekali. Pemanggil LAIN (donut
    ukuran penuh/besar) tetap default lama (per-slice label, tanpa total tengah)."""
    t = theme or THEME_PALETTES["green"]
    chart_data = CategoryChartData()
    chart_data.categories = categories
    chart_data.add_series("Jumlah", values)
    gframe = slide.shapes.add_chart(XL_CHART_TYPE.DOUGHNUT, _emu(x), _emu(y), _emu(cx), _emu(cy), chart_data)
    chart = gframe.chart
    chart.has_legend = False
    chart.has_title = False  # lihat catatan sama di add_native_bar_chart soal judul default "Jumlah"

    plot = chart.plots[0]
    plot.has_data_labels = show_data_labels
    if show_data_labels:
        dl = plot.data_labels
        dl.font.size = Pt(11)
        dl.font.name = BODY_FONT
        dl.font.bold = True
        dl.font.color.rgb = WHITE
        try:
            dl.number_format = "0"
            dl.number_format_is_linked = False
        except Exception:
            pass

    series = plot.series[0]
    palette = colors or CATEGORY_COLOR_RAMP
    for i, pt in enumerate(series.points):
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = palette[i % len(palette)]
        pt.format.line.color.rgb = t["bg"]
        pt.format.line.width = Pt(1.5)

    if show_center_total:
        total = sum(values) or 0
        total_str = _fmt_num(total)
        cx_in, cy_in = Emu(cx).inches, Emu(cy).inches
        # Font total menyusut kalau donutnya kecil ATAU angkanya banyak digit — sama
        # prinsipnya dgn _donut_chart_svg::label_font di export_pdf.py, supaya di ukuran
        # tile yang sempit teksnya tidak nembus keluar cincin.
        base_font = cx_in * 15.0  # ~22pt utk donut side ~1.47in, proporsi wajar
        max_font_by_width = (cx_in * 0.55 * 72) / (len(total_str) * 0.62 or 1)
        total_font = max(9.0, min(base_font, max_font_by_width, 26.0))
        box_h_in = min(cy_in * 0.32, total_font / 72 * 1.3)
        total_box = slide.shapes.add_textbox(x, y + Inches(cy_in / 2 - box_h_in / 2), cx, Inches(box_h_in))
        tp = total_box.text_frame.paragraphs[0]
        tp.text = total_str
        tp.alignment = PP_ALIGN.CENTER
        _set_font(tp, TITLE_FONT, Pt(total_font), bold=True, color=TEXT_DARK)
        sub_box = slide.shapes.add_textbox(x, y + Inches(cy_in / 2 - box_h_in / 2) + Inches(box_h_in), cx, Inches(0.16))
        sp = sub_box.text_frame.paragraphs[0]
        sp.text = total_label
        sp.alignment = PP_ALIGN.CENTER
        _set_font(sp, BODY_FONT, Pt(7.5), color=GRAY_TEXT)

    return gframe


_GAUGE_REMAINDER_COLOR = RGBColor(0xEE, 0xEE, 0xEE)


def add_native_gauge(slide, x, y, cx, cy, value, max_value=100, label="", color=None, theme: dict | None = None):
    """Gauge/ring persentase — panel pendukung kecil (dynamic_section/key_findings, lihat
    _build_dynamic_section_slide/_build_key_findings_slide di bawah). python-pptx TIDAK punya
    tipe chart gauge native, jadi didekati dgn doughnut 2-slice (terisi sebesar value/max_value
    + sisa abu-abu) PERSIS pola add_native_doughnut_chart di atas, legend & data label
    dimatikan (beda dari doughnut biasa yang nyalakan data label per slice — di sini angkanya
    ditumpuk sbg textbox besar di tengah, doughnut native tidak punya slot teks tengah)."""
    t = theme or THEME_PALETTES["green"]
    pct = max(0.0, min(1.0, (value / max_value) if max_value else 0.0))
    chart_data = CategoryChartData()
    chart_data.categories = ["Value", "Remainder"]
    chart_data.add_series("Gauge", (pct * 100, (1 - pct) * 100))
    gframe = slide.shapes.add_chart(XL_CHART_TYPE.DOUGHNUT, _emu(x), _emu(y), _emu(cx), _emu(cy), chart_data)
    chart = gframe.chart
    chart.has_legend = False
    chart.has_title = False

    plot = chart.plots[0]
    plot.has_data_labels = False

    series = plot.series[0]
    ring_color = color or t["main"]
    for pt, fill_color in ((series.points[0], ring_color), (series.points[1], _GAUGE_REMAINDER_COLOR)):
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = fill_color
        pt.format.line.color.rgb = WHITE
        pt.format.line.width = Pt(1)

    value_box = slide.shapes.add_textbox(x, y + Emu(int(cy * 0.36)), cx, Emu(int(cy * 0.3)))
    vp = value_box.text_frame.paragraphs[0]
    vp.text = f"{_fmt_num(round(value))}%"
    vp.alignment = PP_ALIGN.CENTER
    _set_font(vp, TITLE_FONT, Pt(22), bold=True, color=TEXT_DARK)

    if label:
        label_box = slide.shapes.add_textbox(x, y + cy + Inches(0.05), cx, Inches(0.3))
        lp = label_box.text_frame.paragraphs[0]
        lp.text = label
        lp.alignment = PP_ALIGN.CENTER
        _set_font(lp, BODY_FONT, Pt(9), color=GRAY_TEXT)
    return gframe


def add_native_bubble_chart(slide, x, y, cx, cy, points, color=None):
    """PERMINTAAN USER (tambah jenis visualisasi baru): titik per entitas diposisikan
    berdasar 2 angka ASLI berbeda sekaligus (jumlah kemunculan & rata-rata numerik, lihat
    data_profiler._compute_category_numeric_pairs) - genuinely beda drpd chart lain di file
    ini yang semuanya cuma 1 angka per kategori. python-pptx punya tipe chart BUBBLE native
    (beda dari XY_SCATTER biasa - bubble menambah 1 dimensi lagi lewat ukuran titik), jadi
    dipakai langsung, TIDAK perlu shape manual spt treemap di bawah."""
    chart_data = BubbleChartData()
    series = chart_data.add_series("Data")
    for p in points:
        series.add_data_point(p["count"], p["avg"], p["count"])
    gframe = slide.shapes.add_chart(XL_CHART_TYPE.BUBBLE, _emu(x), _emu(y), _emu(cx), _emu(cy), chart_data)
    chart = gframe.chart
    chart.has_legend = False
    chart.has_title = False
    plot = chart.plots[0]
    plot.has_data_labels = False
    series_obj = plot.series[0]
    series_obj.format.fill.solid()
    series_obj.format.fill.fore_color.rgb = color or GREEN_MAIN
    try:
        # BUG DIPERBAIKI (drift vs export_pdf.py::_scatter_bubble_svg — versi PDF cuma
        # menggambar 2 garis sumbu polos TANPA angka/gridline/tick sama sekali, titik
        # tertinggi diberi label teks manual): sebelumnya cuma gridline yang dimatikan,
        # ANGKA sumbu (tick label) & tick mark kedua sumbu masih tampil — beda tampilan dgn
        # versi PDF yang benar2 bersih. Kedua sumbu di sini murni skala numerik (bubble/XY
        # chart tidak punya "nama kategori" sungguhan), jadi tick label AMAN dimatikan
        # total di keduanya (beda dgn add_native_bar_chart yang sumbu kategorinya tetap
        # perlu label nama).
        chart.value_axis.has_major_gridlines = False
        chart.value_axis.has_minor_gridlines = False
        chart.value_axis.major_tick_mark = XL_TICK_MARK.NONE
        chart.value_axis.minor_tick_mark = XL_TICK_MARK.NONE
        chart.value_axis.tick_label_position = XL_TICK_LABEL_POSITION.NONE
        chart.category_axis.has_major_gridlines = False
        chart.category_axis.has_minor_gridlines = False
        chart.category_axis.major_tick_mark = XL_TICK_MARK.NONE
        chart.category_axis.minor_tick_mark = XL_TICK_MARK.NONE
        chart.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.NONE
    except Exception:
        pass
    return gframe


def add_treemap_shapes(slide, x, y, cx, cy, labels, values, colors=None, text_color=None):
    """PERMINTAAN USER (tambah jenis visualisasi baru): proporsi banyak kategori sekaligus
    lewat LUAS kotak. python-pptx TIDAK punya tipe chart treemap native (baru ada di Excel
    2016+, belum diekspos python-pptx sama sekali) — didekati dgn shape RECTANGLE
    diposisikan manual, algoritma "slice-and-dice" PERSIS SAMA dgn versi PDF (_treemap_svg di
    export_pdf.py) supaya proporsinya identik di kedua format."""
    ramp = colors or CATEGORY_COLOR_RAMP
    total = sum(values) or 1
    x_in, y_in, w_in, h_in = Emu(x).inches, Emu(y).inches, Emu(cx).inches, Emu(cy).inches
    rects = []
    cur_x, cur_y, cur_w, cur_h = x_in, y_in, w_in, h_in
    horizontal = True
    remaining_total = total
    for label, val in zip(labels, values):
        frac = (val / remaining_total) if remaining_total else 0
        if horizontal:
            seg_w = cur_w * frac
            rects.append((cur_x, cur_y, seg_w, cur_h, label, val))
            cur_x += seg_w
            cur_w -= seg_w
        else:
            seg_h = cur_h * frac
            rects.append((cur_x, cur_y, cur_w, seg_h, label, val))
            cur_y += seg_h
            cur_h -= seg_h
        remaining_total -= val
        horizontal = not horizontal
    for i, (rx, ry, rw, rh, label, val) in enumerate(rects):
        if rw < 0.05 or rh < 0.05:
            continue
        color = ramp[i % len(ramp)]
        shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(rx), Inches(ry), Inches(rw), Inches(rh))
        shape.fill.solid()
        shape.fill.fore_color.rgb = color
        shape.line.color.rgb = WHITE
        shape.line.width = Pt(1.5)
        _no_shadow(shape)
        if rw > 0.9 and rh > 0.5:
            tf = shape.text_frame
            tf.word_wrap = True
            tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
            p1 = tf.paragraphs[0]
            p1.text = str(label)
            p1.alignment = PP_ALIGN.CENTER
            _set_font(p1, BODY_FONT, Pt(9.5), bold=True, color=text_color or WHITE)
            p2 = tf.add_paragraph()
            p2.text = _fmt_num(val)
            p2.alignment = PP_ALIGN.CENTER
            _set_font(p2, BODY_FONT, Pt(8.5), color=text_color or WHITE)


def add_stacked_proportion_bar(slide, x, y, w, values, colors=None, height=Inches(0.5),
                               labels=None, dasar_in: float | None = None):
    """Alternatif visual KETIGA (selain add_native_bar_chart/add_native_doughnut_chart) — satu
    batang penuh dibagi proporsional per kategori (gaya "100% stacked bar").

    PERMINTAAN USER: label legend TERPISAH (_add_mini_legend) dihapus utk chart ini — nama
    kategori + nilai sekarang MENEMPEL langsung di atas segmennya masing2 (mirror
    export_pdf.py::_stacked_proportion_bar_html). Segmen sempit (<8% lebar total) tidak diberi
    label — nama/nilai bakal saling tumpuk kalau dipaksa, sengaja dilewati drpd tidak terbaca."""
    total = sum(values) or 1
    w_in = Emu(w).inches
    label_h_in = 0.32 if labels else 0.0
    top_in = Emu(y).inches
    bar_y_in = top_in + label_h_in
    # Batang digeser ke bawah oleh baris label di atasnya, jadi JEJAKNYA = label + tinggi
    # batang - lebih tinggi dari `height` yang dioper pemanggil. CACAT NYATA (terukur di data
    # berkolom kategorikal 2 nilai): pemanggil sudah memotong `height` agar muat di slotnya,
    # tapi pergeseran label membuat batang tetap berakhir 0,32in di bawah kotak Catatan.
    # `dasar_in` = garis yang tidak boleh dilewati; batang dipendekkan, bukan digeser naik,
    # supaya labelnya tetap menempel di atas batangnya sendiri.
    if dasar_in is not None:
        _sisa_bar_in = dasar_in - bar_y_in
        if Emu(height).inches > _sisa_bar_in:
            height = Inches(max(0.08, _sisa_bar_in))
    cur_x_in = Emu(x).inches
    dd_labels = _dedupe_truncated_labels(labels, 14) if labels else None
    for i, val in enumerate(values):
        frac = (val / total) if total else 0
        seg_w_in = w_in * frac
        if seg_w_in <= 0:
            continue
        color = colors[i] if colors else CATEGORY_COLOR_RAMP[i % len(CATEGORY_COLOR_RAMP)]
        seg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(cur_x_in), Inches(bar_y_in), Inches(seg_w_in), height)
        seg.fill.solid()
        seg.fill.fore_color.rgb = color
        seg.line.color.rgb = WHITE
        seg.line.width = Pt(1)
        _no_shadow(seg)
        # AMBANG 8% DIGANTI PENGUKURAN - kembaran perbaikan di export_pdf.py. "8% lebar"
        # tidak melihat geometri: 8% dari kolom 4.09in cuma 0.33in, sementara "Mendekati
        # Target" butuh ~1in, jadi kotak teks tetangga saling menimpa. Label dipasang hanya
        # kalau teksnya MUAT di lebar segmennya sendiri.
        _teks_in = len(str(dd_labels[i] if dd_labels else "")) * (7.5 / 72.0) * 0.62
        if labels and _teks_in <= seg_w_in:
            lbl_box = slide.shapes.add_textbox(Inches(cur_x_in), Inches(top_in), Inches(seg_w_in), Inches(label_h_in))
            ltf = lbl_box.text_frame
            ltf.word_wrap = False
            lp = ltf.paragraphs[0]
            lp.alignment = PP_ALIGN.CENTER
            label_run = lp.add_run()
            label_run.text = dd_labels[i]
            _set_font(label_run, BODY_FONT, Pt(7.5), bold=True, color=TEXT_DARK)
            lp2 = ltf.add_paragraph()
            lp2.alignment = PP_ALIGN.CENTER
            val_run = lp2.add_run()
            val_run.text = _fmt_num(val)
            _set_font(val_run, BODY_FONT, Pt(7), color=GRAY_TEXT)
        cur_x_in += seg_w_in
    return bar_y_in + Emu(height).inches


def add_native_table(slide, x, y, w, h, headers, rows, highlight_indices=None, theme: dict | None = None):
    t = theme or THEME_PALETTES["green"]
    highlight_indices = highlight_indices or set()
    n_rows = len(rows) + 1
    n_cols = len(headers)
    gframe = slide.shapes.add_table(n_rows, n_cols, x, y, w, h)
    table = gframe.table

    for c, htext in enumerate(headers):
        cell = table.cell(0, c)
        cell.fill.solid()
        cell.fill.fore_color.rgb = t["bg"]
        cell.margin_left = cell.margin_right = Inches(0.08)
        p = cell.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
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
            p.alignment = PP_ALIGN.LEFT
            p.text = str(val)
            is_status_col = c == n_cols - 1
            _set_font(
                p, BODY_FONT, Pt(10.5),
                bold=bool(is_open and is_status_col),
                color=(RED_CRIT if (is_open and is_status_col) else TEXT_DARK),
            )
    return gframe


# ============================================================================
# 5 chart BARU — mirror svg_bar_line/svg_radar/svg_heatmap_grid/svg_grouped_bar/svg_funnel di
# export_pdf.py, versi PPTX (python-pptx TIDAK punya tipe chart combo/heatmap/funnel native,
# jadi digambar tangan pakai shape spt add_stacked_proportion_bar; radar & grouped bar
# tersedia native lewat XL_CHART_TYPE, dipakai langsung spt add_native_bar_chart).
# ============================================================================
def add_native_radar_chart(slide, x, y, cx, cy, axes, values, color=None):
    """Skor multi-indikator — python-pptx PUNYA tipe chart RADAR native (beda dari gauge yang
    harus didekati doughnut 2-slice, lihat add_native_gauge), dipakai langsung."""
    chart_data = CategoryChartData()
    chart_data.categories = axes
    chart_data.add_series("Skor", values)
    gframe = slide.shapes.add_chart(XL_CHART_TYPE.RADAR_MARKERS, _emu(x), _emu(y), _emu(cx), _emu(cy), chart_data)
    chart = gframe.chart
    chart.has_legend = False
    chart.has_title = False
    plot = chart.plots[0]
    plot.has_data_labels = False
    series = plot.series[0]
    line_color = color or GREEN_MAIN
    series.format.line.color.rgb = line_color
    series.format.line.width = Pt(2)
    try:
        chart.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.NONE
        chart.category_axis.tick_labels.font.size = Pt(1)
        chart.value_axis.visible = False
        chart.value_axis.minimum_scale = 0
        chart.value_axis.maximum_scale = 100
    except Exception:
        pass
    # BUG PRE-EXISTING DIPERBAIKI (disetujui user): `cx`/`cy` boleh datang sbg Length
    # (punya .inches) ATAU sbg angka EMU mentah - pemanggil di jalur Descriptive mengoper
    # hasil perhitungan float, dan barisnya langsung meledak dgn
    # AttributeError: 'float' object has no attribute 'inches', menggagalkan SELURUH ekspor
    # PPTX Descriptive untuk data yang punya >=3 kolom numerik. Ini crash, bukan soal gaya.
    # Dinormalkan lewat Emu(int(...)) - pola yang sama sudah dipakai di jalur Management.
    _cx_in = cx.inches if hasattr(cx, "inches") else Emu(int(cx)).inches
    _cy_in = cy.inches if hasattr(cy, "inches") else Emu(int(cy)).inches
    size_px = min(_cx_in, _cy_in) * 96
    label_layout = radar_label_layout(axes, size_px, max(55 * min(size_px / 220, 1.3), 16))
    if label_layout is None:
        return gframe
    for text, label_x, label_y, anchor, font_size in label_layout:
        width_px = max(font_size * 0.52, len(text) * font_size * 0.52)
        left_px = label_x - width_px if anchor == "end" else (label_x - width_px / 2 if anchor == "middle" else label_x)
        # `x`/`y` ikut dinormalkan: kalau keduanya float mentah, penjumlahan dgn Inches()
        # menghasilkan float lagi dan tertulis mentah ke XML sbg EMU pecahan (PowerPoint
        # menolak file-nya & minta "repair") - kelas bug yang sama sudah diperbaiki di
        # jalur Management.
        _x0 = int(x) if not hasattr(x, "inches") else int(x)
        _y0 = int(y) if not hasattr(y, "inches") else int(y)
        label = slide.shapes.add_textbox(
            Emu(_x0 + int(Inches(left_px / 96))),
            Emu(_y0 + int(Inches((label_y - font_size) / 96))),
            Emu(int(Inches(width_px / 96))), Emu(int(Inches(font_size * 1.2 / 96))),
        )
        label.text_frame.word_wrap = False
        paragraph = label.text_frame.paragraphs[0]
        paragraph.text = text
        paragraph.alignment = PP_ALIGN.LEFT if anchor == "start" else (PP_ALIGN.RIGHT if anchor == "end" else PP_ALIGN.CENTER)
        _set_font(paragraph, BODY_FONT, Pt(font_size), color=TEXT_DARK)
    return gframe


def add_grouped_bar_chart(slide, x, y, cx, cy, categories, series_a, series_b, label_a="", label_b="", color_a=None, color_b=None):
    """Perbandingan 2 periode/seri per kategori — python-pptx mendukung multi-series NATIVE
    lewat CategoryChartData.add_series() dipanggil 2x, dipakai langsung spt add_native_bar_chart
    (beda dari add_native_bar_chart yang cuma 1 series)."""
    chart_data = CategoryChartData()
    chart_data.categories = categories
    chart_data.add_series(label_a or "A", series_a)
    chart_data.add_series(label_b or "B", series_b)
    gframe = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, _emu(x), _emu(y), _emu(cx), _emu(cy), chart_data)
    chart = gframe.chart
    chart.has_legend = True
    chart.legend.include_in_layout = False
    chart.legend.font.size = Pt(9)
    chart.legend.font.name = BODY_FONT
    chart.has_title = False
    plot = chart.plots[0]
    # PERMINTAAN USER: tampilkan nilai di tiap bar (referensi menulis angka langsung di atas
    # batangnya) — legend TETAP dipakai di sini (bukan dihapus) krn cuma menyebut 2 NAMA SERI
    # (mis. "Paruh Awal"/"Paruh Akhir"), beda kelasnya dgn legend daftar-kategori panjang yang
    # dihapus di chart batang/donat lain — mirror _grouped_bar_chart_svg (export_pdf.py) yang
    # juga tetap mempertahankan legend 2-seri kecil ini.
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.font.size = Pt(8)
    dl.font.name = BODY_FONT
    dl.font.bold = True
    try:
        dl.number_format = "0"
        dl.number_format_is_linked = False
    except Exception:
        pass
    colors = [color_a or GREEN_MAIN, color_b or GOLD_MAIN]
    for i, series in enumerate(plot.series):
        series.format.fill.solid()
        series.format.fill.fore_color.rgb = colors[i % len(colors)]
    try:
        chart.category_axis.has_major_gridlines = False
        chart.value_axis.has_major_gridlines = False
        chart.category_axis.tick_labels.font.size = Pt(9)
        chart.category_axis.tick_labels.font.name = BODY_FONT
        chart.value_axis.visible = False
    except Exception:
        pass
    return gframe


def add_bar_line_chart(slide, x, y, cx, cy, categories, values, cumulative=None, color=None):
    """Deret waktu -> batang (nilai per periode) + garis kumulatif — python-pptx TIDAK punya
    tipe chart combo (bar+line) native tanpa manipulasi XML manual, jadi batang digambar lewat
    shape (pola sama dgn add_stacked_proportion_bar) & garis lewat add_connector (segmen garis
    lurus antar titik berurutan) + titik bulat kecil di tiap simpul."""
    bar_color = color or GREEN_MAIN
    line_color = GOLD_MAIN
    n = len(categories) or 1
    x_in, y_in, w_in, h_in = Emu(x).inches, Emu(y).inches, Emu(cx).inches, Emu(cy).inches
    label_h_in = 0.22
    # PERMINTAAN USER ("angka harus melekat di chart"): sisi PPT chart ini dulu SAMA SEKALI
    # tidak menampilkan angka - cuma batang, garis & nama kategori (padanan PDF-nya sudah
    # berlabel). Ruang utk labelnya DICADANGKAN dari tinggi yang dijatah (plot dipendekkan),
    # BUKAN digambar di atas y_in - menggambar di luar jatah persis kelas bug yang bikin isi
    # halaman hilang diam-diam sebelumnya.
    value_h_in = 0.16
    plot_h_in = h_in - label_h_in - value_h_in
    col_w_in = w_in / n
    max_val = max(values) if values and max(values) else 1
    max_cum = max(cumulative) if cumulative and max(cumulative) else 0
    points = []
    for i, val in enumerate(values):
        bar_h_in = (val / max_val) * (plot_h_in - 0.1) if max_val else 0
        bx_in = x_in + i * col_w_in + col_w_in * 0.18
        bw_in = col_w_in * 0.64
        by_in = y_in + value_h_in + (plot_h_in - bar_h_in)
        bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(bx_in), Inches(by_in), Inches(max(bw_in, 0.02)), Inches(max(bar_h_in, 0.02)))
        bar.fill.solid()
        bar.fill.fore_color.rgb = bar_color
        bar.line.fill.background()
        _no_shadow(bar)
        if max_cum:
            cy_in = y_in + value_h_in + plot_h_in - ((cumulative[i] / max_cum) * (plot_h_in - 0.05))
            points.append((x_in + i * col_w_in + col_w_in / 2, cy_in))
        # Angka hanya digambar kalau MUAT di lebar kolomnya - kembaran perbaikan di
        # export_pdf.py. Dgn 12 periode di kolom 4in tiap kolom cuma ~0.34in; angka berpemisah
        # ribuan meluber dari kotaknya & menimpa tetangganya (PowerPoint tidak memotong).
        _tval = _fmt_num(val) if val else ""
        if val and len(_tval) * 7 * 0.62 / 72.0 <= col_w_in:
            val_box = slide.shapes.add_textbox(
                Inches(x_in + i * col_w_in), Inches(max(by_in - value_h_in, y_in)),
                Inches(col_w_in), Inches(value_h_in))
            vp = val_box.text_frame.paragraphs[0]
            vp.text = _tval
            vp.alignment = PP_ALIGN.CENTER
            _set_font(vp, BODY_FONT, Pt(7), color=TEXT_DARK)
        label_box = slide.shapes.add_textbox(Inches(x_in + i * col_w_in), Inches(y_in + value_h_in + plot_h_in + 0.02), Inches(col_w_in), Inches(label_h_in))
        lp = label_box.text_frame.paragraphs[0]
        lp.text = str(categories[i])
        lp.alignment = PP_ALIGN.CENTER
        _set_font(lp, BODY_FONT, Pt(7), color=GRAY_TEXT)
    for i in range(len(points) - 1):
        (x1, y1), (x2, y2) = points[i], points[i + 1]
        conn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
        conn.line.color.rgb = line_color
        conn.line.width = Pt(2.25)
    for px, py in points:
        dot = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(px - 0.045), Inches(py - 0.045), Inches(0.09), Inches(0.09))
        dot.fill.solid()
        dot.fill.fore_color.rgb = line_color
        dot.line.fill.background()
        _no_shadow(dot)
    # nilai kumulatif ditempel di titiknya - ruang DI ATAS titik sudah dipakai label angka
    # batang, jadi labelnya di BAWAH titik; kalau titiknya sudah mepet kaki plot, dibalik ke
    # atas supaya tidak menabrak nama kategori. Dilewati kalau kategorinya > 8: di lebar tile
    # sesempit ini label sebanyak itu saling tumpuk & malah tidak terbaca.
    if points and len(points) <= 8:
        _plot_bottom = y_in + value_h_in + plot_h_in
        for (px, py), cval in zip(points, cumulative):
            _ly = py + 0.05 if py + 0.21 < _plot_bottom else py - 0.19
            cbox = slide.shapes.add_textbox(Inches(px - col_w_in / 2), Inches(_ly), Inches(col_w_in), Inches(0.16))
            cp = cbox.text_frame.paragraphs[0]
            cp.text = _fmt_num(cval)
            cp.alignment = PP_ALIGN.CENTER
            _set_font(cp, BODY_FONT, Pt(6.5), color=line_color)


def add_heatmap_grid(slide, x, y, cx, cy, day_labels, hour_labels, grid, color=None):
    """Pola kejadian per hari/blok jam — grid sel warna (RECTANGLE), warna makin pekat makin
    sering kejadian di kombinasi itu (blended warna dgn putih, BUKAN opacity shape — properti
    transparency shape python-pptx tidak selalu didukung utk semua versi PowerPoint)."""
    base = color or GREEN_MAIN
    max_val = max((v for row in grid for v in row), default=0) or 1
    n_rows, n_cols = len(day_labels), len(hour_labels)
    x_in, y_in, w_in, h_in = Emu(x).inches, Emu(y).inches, Emu(cx).inches, Emu(cy).inches
    label_w_in = 0.55
    header_h_in = 0.2
    cell_w_in = (w_in - label_w_in) / max(n_cols, 1)
    cell_h_in = (h_in - header_h_in) / max(n_rows, 1)
    for c, hl in enumerate(hour_labels):
        hb = slide.shapes.add_textbox(Inches(x_in + label_w_in + c * cell_w_in), Inches(y_in), Inches(cell_w_in), Inches(header_h_in))
        hp = hb.text_frame.paragraphs[0]
        hp.text = str(hl)
        hp.alignment = PP_ALIGN.CENTER
        _set_font(hp, BODY_FONT, Pt(6.5), color=GRAY_TEXT)
    for r, day_label in enumerate(day_labels):
        row_y_in = y_in + header_h_in + r * cell_h_in
        lb = slide.shapes.add_textbox(Inches(x_in), Inches(row_y_in), Inches(label_w_in - 0.05), Inches(cell_h_in))
        lbp = lb.text_frame.paragraphs[0]
        lbp.text = str(day_label)
        lbp.alignment = PP_ALIGN.RIGHT
        _set_font(lbp, BODY_FONT, Pt(7), color=TEXT_DARK)
        for c in range(n_cols):
            val = grid[r][c]
            frac = 0.12 + 0.8 * (val / max_val)
            r0, g0, b0 = base[0], base[1], base[2]
            blended = RGBColor(
                round(r0 * frac + 255 * (1 - frac)),
                round(g0 * frac + 255 * (1 - frac)),
                round(b0 * frac + 255 * (1 - frac)),
            )
            cell_x_in = x_in + label_w_in + c * cell_w_in
            cell = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(cell_x_in), Inches(row_y_in), Inches(cell_w_in - 0.02), Inches(cell_h_in - 0.02))
            cell.fill.solid()
            cell.fill.fore_color.rgb = blended
            cell.line.fill.background()
            _no_shadow(cell)
            _modest_corner(cell)
            if val:
                vb = slide.shapes.add_textbox(Inches(cell_x_in), Inches(row_y_in), Inches(cell_w_in - 0.02), Inches(cell_h_in - 0.02))
                vp = vb.text_frame.paragraphs[0]
                vp.text = str(val)
                vp.alignment = PP_ALIGN.CENTER
                _set_font(vp, BODY_FONT, Pt(7), color=(WHITE if frac > 0.5 else TEXT_DARK))


def add_ranked_bar_ternorm(slide, x, y, cx, cy, labels, values, color=None, is_en=False):
    """Kembaran _ranked_bar_ternorm_html di export_pdf.py - lihat catatan lengkap di sana.

    Panjang relatif thd tertinggi, NILAI ASLI di ujung tiap batang, sumbu berlabel eksplisit."""
    if not values:
        return
    warna = color or GREEN_MAIN
    maks = max(values) or 1
    x_in, y_in = Emu(x).inches, Emu(y).inches
    w_in, h_in = Emu(cx).inches, Emu(cy).inches
    # KEPUTUSAN USER: kaki legenda "| relatif terhadap tertinggi - tertinggi X" DIBUANG dari
    # ranked bar ternormalisasi. Bukan karena tidak penting - keterangan skala ini justru
    # wajib supaya panjang batang tidak disalahbaca absolut - tapi karena teks yang SAMA
    # sudah tercetak di pita kepala panel lewat cara_baca_kolom() ("skala relatif thd
    # tertinggi - tertinggi X"), jadi ia muncul dua kali dalam satu panel. Yang di pita
    # dipertahankan karena terbaca SEBELUM chart, sesuai acuan. Kaki grouped_bar_ternorm
    # TIDAK ikut dibuang: isinya peringatan lain ("panjang sama BUKAN berarti nilai sama")
    # yang tidak ada duanya di mana pun.
    # `kaki` = 0.0: tinggi yang tadinya dipesan utk kaki sekarang jatuh ke baris chart.
    lbl_w, val_w, kaki = 1.25, 0.85, 0.0
    track_w = max(0.5, w_in - lbl_w - val_w - 0.15)
    n = max(1, len(values))
    # DISAMAKAN DGN ACUAN (kembaran export_pdf.py): baris 0.35in, bar 0.10in.
    row_h = max(0.16, min(0.35, (h_in - kaki) / n))
    for i, (lbl, val) in enumerate(zip(labels, values)):
        ty = y_in + i * row_h
        tb = slide.shapes.add_textbox(Inches(x_in), Inches(ty), Inches(lbl_w), Inches(row_h))
        tp = tb.text_frame.paragraphs[0]
        tp.text = str(lbl)
        _set_font(tp, BODY_FONT, Pt(7), color=TEXT_DARK)
        trek = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x_in + lbl_w),
                                      Inches(ty + row_h * 0.30), Inches(track_w), Inches(min(0.10, max(0.07, row_h * 0.34))))
        _modest_corner(trek)
        trek.fill.solid(); trek.fill.fore_color.rgb = PANEL_BORDER
        trek.line.fill.background(); _no_shadow(trek)
        frac = max(0.012, float(val) / maks)
        isi = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x_in + lbl_w),
                                     Inches(ty + row_h * 0.30), Inches(max(0.05, track_w * frac)),
                                     Inches(min(0.10, max(0.07, row_h * 0.34))))
        _modest_corner(isi)
        isi.fill.solid(); isi.fill.fore_color.rgb = _as_rgb(warna, GREEN_MAIN)
        isi.line.fill.background(); _no_shadow(isi)
        vb = slide.shapes.add_textbox(Inches(x_in + lbl_w + track_w + 0.06), Inches(ty),
                                      Inches(val_w), Inches(row_h))
        vp = vb.text_frame.paragraphs[0]
        vp.text = _fmt_num(val)
        vp.alignment = PP_ALIGN.RIGHT
        _set_font(vp, BODY_FONT, Pt(9.5), bold=True, color=TEXT_DARK)


def add_grouped_bar_ternorm(slide, x, y, cx, cy, labels, seri_a, seri_b, label_a="", label_b="",
                            color_a=None, color_b=None, is_en=False):
    """Kembaran _grouped_bar_ternorm_html di export_pdf.py - lihat catatan lengkap di sana.

    Tiap deret dinormalkan ke MAKSIMUMNYA SENDIRI, jadi dua batang SAMA PANJANG tidak berarti
    nilainya sama - karena itu tiap deret membawa maksimumnya sendiri di legenda, dan nilai
    asli tetap tertulis di ujung tiap batang."""
    if not labels:
        return
    ca = _as_rgb(color_a, GREEN_MAIN)
    cb = _as_rgb(color_b, GOLD_MAIN)
    maks_a, maks_b = max(seri_a) or 1, max(seri_b) or 1
    x_in, y_in = Emu(x).inches, Emu(y).inches
    w_in, h_in = Emu(cx).inches, Emu(cy).inches
    lbl_w, val_w, kaki = 1.3, 0.95, 0.36
    track_w = max(0.5, w_in - lbl_w - val_w - 0.15)
    n = max(1, len(labels))
    row_h = max(0.22, (h_in - kaki) / n)
    for i, (lbl, va, vb) in enumerate(zip(labels, seri_a, seri_b)):
        ty = y_in + i * row_h
        tb = slide.shapes.add_textbox(Inches(x_in), Inches(ty), Inches(lbl_w), Inches(row_h))
        tp = tb.text_frame.paragraphs[0]
        tp.text = str(lbl)
        _set_font(tp, BODY_FONT, Pt(9), color=TEXT_DARK)
        for j, (val, maks, warna) in enumerate(((va, maks_a, ca), (vb, maks_b, cb))):
            by = ty + 0.02 + j * (row_h * 0.45)
            bh = max(0.07, row_h * 0.34)
            frac = max(0.012, float(val) / maks)
            b = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x_in + lbl_w), Inches(by),
                                       Inches(max(0.05, track_w * frac)), Inches(bh))
            b.fill.solid(); b.fill.fore_color.rgb = warna
            b.line.fill.background(); _no_shadow(b)
            vbx = slide.shapes.add_textbox(Inches(x_in + lbl_w + track_w + 0.05), Inches(by - 0.03),
                                           Inches(val_w), Inches(bh + 0.08))
            vp = vbx.text_frame.paragraphs[0]
            vp.text = _fmt_num(val)
            vp.alignment = PP_ALIGN.RIGHT
            _set_font(vp, BODY_FONT, Pt(7.5), bold=True, color=TEXT_DARK)
    mk = "max" if is_en else "maks"
    lb = slide.shapes.add_textbox(Inches(x_in), Inches(y_in + h_in - kaki), Inches(w_in), Inches(kaki))
    lp = lb.text_frame.paragraphs[0]
    lp.text = "%s (%s %s)   %s (%s %s)" % (label_a, mk, _fmt_num(maks_a), label_b, mk, _fmt_num(maks_b))
    _set_font(lp, BODY_FONT, Pt(7), color=GRAY_TEXT)
    lp2 = lb.text_frame.add_paragraph()
    lp2.text = ("each series relative to its own max - equal lengths are NOT equal values"
                if is_en else
                "tiap deret relatif thd maksimumnya sendiri - panjang sama BUKAN berarti nilai sama")
    _set_font(lp2, BODY_FONT, Pt(7), color=GRAY_TEXT)


def add_funnel_chart(slide, x, y, cx, cy, categories, values, color=None):
    """Alur bertingkat (mis. status penanganan Open -> Investigating -> Resolved) — batang
    melebar/menyempit sesuai proporsi tiap tahap, ditumpuk vertikal dari terbesar ke terkecil
    (RECTANGLE mengecil lebarnya per baris, pola sama dgn add_stacked_proportion_bar)."""
    base = color or GREEN_MAIN
    n = len(categories) or 1
    x_in, y_in, w_in, h_in = Emu(x).inches, Emu(y).inches, Emu(cx).inches, Emu(cy).inches
    max_val = max(values) if values else 1
    row_h_in = h_in / n
    for i, (cat, val) in enumerate(zip(categories, values)):
        frac = (val / max_val) if max_val else 0
        seg_w_in = max(w_in * 0.22, w_in * frac)
        seg_x_in = x_in + (w_in - seg_w_in) / 2
        seg_y_in = y_in + i * row_h_in
        shade = 0.45 + 0.55 * (1 - i / max(n - 1, 1))
        blended = RGBColor(
            round(base[0] * shade + 255 * (1 - shade)),
            round(base[1] * shade + 255 * (1 - shade)),
            round(base[2] * shade + 255 * (1 - shade)),
        )
        seg = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(seg_x_in), Inches(seg_y_in), Inches(seg_w_in), Inches(max(row_h_in - 0.06, 0.1)))
        seg.fill.solid()
        seg.fill.fore_color.rgb = blended
        seg.line.fill.background()
        _no_shadow(seg)
        _modest_corner(seg)
        tb = slide.shapes.add_textbox(Inches(x_in), Inches(seg_y_in), Inches(w_in), Inches(max(row_h_in - 0.06, 0.1)))
        tf = tb.text_frame
        tp = tf.paragraphs[0]
        tp.text = f"{cat} · {_fmt_num(val)}"
        tp.alignment = PP_ALIGN.CENTER
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        _set_font(tp, BODY_FONT, Pt(10), bold=True, color=WHITE)


def add_split_cover_slide(prs, block, flourish_corner, logo_path, theme: dict | None = None):
    """Varian cover 2-kolom warna penuh (emas kiri + hijau kanan, angka hero besar di kolom
    emas) — analog `_split_cover_td()` di export_pdf.py, titik variasi tampilan (lihat
    `cover_style` di generate_ppt_report), alternatif dari cover 1-warna standar."""
    t = theme or THEME_PALETTES["green"]
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    left_w = Inches(13.33 * 0.37)
    right_x = left_w
    right_w = SLIDE_W - left_w
    _fill_rect_bg(slide, 0, 0, left_w, SLIDE_H, t["light"])
    _fill_rect_bg(slide, right_x, 0, right_w, SLIDE_H, t["bg"])
    add_corner_flourish(slide, flourish_corner, area_x=right_x, area_w=right_w, theme=t)
    add_logo(slide, logo_path, width=Inches(2.85), dark=True)

    value, label = block.get("hero_stat") or (str(block.get("total_records", "")), "Total Data")
    hero_kicker = block.get("hero_stat_kicker", "CAPAIAN")

    kicker_box = slide.shapes.add_textbox(Inches(0.45), Inches(0.5), left_w - Inches(0.7), Inches(0.3))
    kp = kicker_box.text_frame.paragraphs[0]
    kp.alignment = PP_ALIGN.LEFT
    kp.text = hero_kicker.upper()
    _set_font(kp, BODY_FONT, Pt(10), bold=True, color=TEXT_DARK)

    value_w_in = Emu(left_w - Inches(0.6)).inches
    value_h_in = _estimate_wrapped_height_in(str(value), 54, value_w_in)
    value_box = slide.shapes.add_textbox(Inches(0.4), Inches(3.15), left_w - Inches(0.6), Inches(value_h_in + 0.1))
    vtf = value_box.text_frame
    vtf.word_wrap = True
    vp = vtf.paragraphs[0]
    vp.alignment = PP_ALIGN.LEFT
    vp.text = str(value)
    _set_font(vp, TITLE_FONT, Pt(54), bold=True, color=t["bg"])

    label_top_in = 3.15 + value_h_in + 0.15
    label_box = slide.shapes.add_textbox(Inches(0.45), Inches(label_top_in), left_w - Inches(0.7), Inches(0.4))
    lp = label_box.text_frame.paragraphs[0]
    lp.alignment = PP_ALIGN.LEFT
    lp.text = label
    _set_font(lp, BODY_FONT, Pt(12), color=TEXT_DARK)

    footer_box = slide.shapes.add_textbox(Inches(0.45), SLIDE_H - Inches(0.7), left_w - Inches(0.7), Inches(0.3))
    fp = footer_box.text_frame.paragraphs[0]
    fp.alignment = PP_ALIGN.LEFT
    fp.text = block["header_title"]
    _set_font(fp, BODY_FONT, Pt(10), bold=True, color=TEXT_DARK)

    title_text = block["title"]
    if len(title_text) > 55:
        title_size_pt = 26
    elif len(title_text) > 40:
        title_size_pt = 30
    elif len(title_text) > 28:
        title_size_pt = 36
    else:
        title_size_pt = 42

    text_x = right_x + Inches(0.5)
    text_w = right_w - Inches(1.0)

    kicker2_box = slide.shapes.add_textbox(text_x, Inches(2.15), text_w, Inches(0.3))
    kp2 = kicker2_box.text_frame.paragraphs[0]
    kp2.alignment = PP_ALIGN.LEFT
    kp2.text = block["kicker"].upper()
    _set_font(kp2, BODY_FONT, Pt(10.5), bold=True, color=t["light"])

    title_top_in = 2.5
    title_height_in = _estimate_wrapped_height_in(title_text, title_size_pt, Emu(text_w).inches)
    title_box = slide.shapes.add_textbox(text_x, Inches(title_top_in), text_w, Inches(title_height_in + 0.1))
    ttf = title_box.text_frame
    ttf.word_wrap = True
    tp = ttf.paragraphs[0]
    tp.alignment = PP_ALIGN.LEFT
    tp.text = title_text
    _set_font(tp, TITLE_FONT, Pt(title_size_pt), bold=True, color=WHITE)

    sub_top_in = max(title_top_in + title_height_in + 0.15, 3.4)
    sub_box = slide.shapes.add_textbox(text_x, Inches(sub_top_in), text_w, Inches(0.5))
    sp = sub_box.text_frame.paragraphs[0]
    sp.alignment = PP_ALIGN.LEFT
    sp.text = block["subtitle"]
    _set_font(sp, BODY_FONT, Pt(14), color=WHITE)

    info_top_in = max(sub_top_in + 0.6, 4.2)
    info_box = slide.shapes.add_textbox(text_x, Inches(info_top_in), text_w, Inches(0.9))
    itf = info_box.text_frame
    itf.word_wrap = True
    p1 = itf.paragraphs[0]
    p1.alignment = PP_ALIGN.LEFT
    p1.text = f'{block["period_label"]} {block["period_text"]}'
    _set_font(p1, BODY_FONT, Pt(12), color=WHITE)
    p2 = itf.add_paragraph()
    p2.alignment = PP_ALIGN.LEFT
    p2.text = block["info_line"]
    _set_font(p2, BODY_FONT, Pt(12), color=t["soft"])
    p2.space_before = Pt(6)

    return slide


def add_split_closing_slide(prs, block, flourish_corner, logo_path=None, theme: dict | None = None):
    """Varian penutup berpasangan dgn `add_split_cover_slide` — angka hero yang SAMA
    ditampilkan lagi di kolom emas kiri (mengulang temuan utama, gaya "bookend" laporan
    eksekutif), analog `_split_closing_td()` di export_pdf.py."""
    t = theme or THEME_PALETTES["green"]
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    left_w = Inches(13.33 * 0.37)
    right_x = left_w
    right_w = SLIDE_W - left_w
    _fill_rect_bg(slide, 0, 0, left_w, SLIDE_H, t["light"])
    _fill_rect_bg(slide, right_x, 0, right_w, SLIDE_H, t["bg"])
    add_corner_flourish(slide, flourish_corner, area_x=right_x, area_w=right_w, theme=t)
    # BUG YANG DIPERBAIKI (dilaporkan user): varian penutup ini sebelumnya tidak punya logo
    # sama sekali (beda dgn add_split_cover_slide yang sudah benar).
    add_logo(slide, logo_path, width=Inches(2.85), dark=True)

    value, label = block.get("hero_stat") or ("", "")
    value_w_in = Emu(left_w - Inches(0.6)).inches
    value_h_in = _estimate_wrapped_height_in(str(value), 42, value_w_in)
    value_box = slide.shapes.add_textbox(Inches(0.4), Inches(3.15), left_w - Inches(0.6), Inches(value_h_in + 0.1))
    vtf = value_box.text_frame
    vtf.word_wrap = True
    vp = vtf.paragraphs[0]
    vp.alignment = PP_ALIGN.LEFT
    vp.text = str(value)
    _set_font(vp, TITLE_FONT, Pt(42), bold=True, color=t["bg"])

    label_top_in = 3.15 + value_h_in + 0.12
    label_box = slide.shapes.add_textbox(Inches(0.45), Inches(label_top_in), left_w - Inches(0.7), Inches(0.4))
    lp = label_box.text_frame.paragraphs[0]
    lp.alignment = PP_ALIGN.LEFT
    lp.text = label
    _set_font(lp, BODY_FONT, Pt(11), color=TEXT_DARK)

    text_x = right_x + Inches(0.5)
    text_w = right_w - Inches(1.0)
    thank_you_h_in = _estimate_wrapped_height_in(block["thank_you"], 38, Emu(text_w).inches)
    title_box = slide.shapes.add_textbox(text_x, Inches(3.0), text_w, Inches(thank_you_h_in + 0.1))
    tp = title_box.text_frame.paragraphs[0]
    tp.alignment = PP_ALIGN.LEFT
    tp.text = block["thank_you"]
    _set_font(tp, TITLE_FONT, Pt(38), bold=True, color=WHITE)

    sub_top_in = max(3.0 + thank_you_h_in + 0.15, 3.85)
    sub_box = slide.shapes.add_textbox(text_x, Inches(sub_top_in), text_w, Inches(0.5))
    stf = sub_box.text_frame
    stf.word_wrap = True
    sp = stf.paragraphs[0]
    sp.alignment = PP_ALIGN.LEFT
    sp.text = block["title"]
    _set_font(sp, BODY_FONT, Pt(13), color=WHITE)

    sub_height_in = _estimate_wrapped_height_in(block["title"], 13, Emu(text_w).inches)
    note_top_in = max(sub_top_in + sub_height_in + 0.1, 4.4)
    note_box = slide.shapes.add_textbox(text_x, Inches(note_top_in), text_w, Inches(0.4))
    np_ = note_box.text_frame.paragraphs[0]
    np_.alignment = PP_ALIGN.LEFT
    np_.text = block["note"]
    _set_font(np_, BODY_FONT, Pt(11), italic=True, color=t["soft"])

    return slide


# ============================================================================
# Konten turunan dari data (bukan dari AI) — deterministik
# ============================================================================


@dataclass
class _PptBlockContext:
    """Kumpulan variabel variasi tampilan (dipilih SEKALI per generate, lihat
    generate_ppt_report) + report/prs/logo_path yang dibutuhkan LEBIH DARI SATU builder
    slide di bawah — dioper ke tiap builder supaya signature-nya seragam (block, ctx)
    alih-alih daftar parameter berbeda-beda per jenis slide. Sebelumnya semua builder ini
    adalah cabang if/elif di dalam SATU fungsi generate_ppt_report sepanjang ~650 baris —
    dipecah jadi fungsi terpisah (murni supaya lebih mudah dibaca/diubah 1 jenis slide
    tanpa perlu scroll baca semuanya), TIDAK ada perubahan HASIL AKHIR sama sekali
    (diverifikasi PPTX yang dihasilkan tetap konsisten sebelum & sesudah pemecahan ini).

    cover_hero_stat DIISI oleh _build_cover_slide, DIBACA oleh _build_closing_slide
    (bookend angka hero yang sama di cover & penutup saat cover_style="split") — satu-
    satunya state yang mengalir ANTAR pemanggilan builder, makanya ctx harus objek yang
    sama dioper ke semua builder dalam 1 kali generate, bukan dibuat ulang tiap slide.

    Beda dari _PdfBlockContext (export_pdf.py): builder di sini TIDAK mengembalikan HTML,
    melainkan langsung menggambar shape ke slide baru di ctx.prs (efek samping), lalu
    me-return objek Slide yang harus di-footer-nomori (None kalau slide itu cover/penutup,
    yang memang selalu dikecualikan dari penomoran — lihat _PPT_BLOCK_BUILDERS di bawah).
    """
    report: Report
    prs: Presentation
    logo_path: object
    panel_side: str
    stat_cols: int
    card_cols: int
    flourish_corner: str
    accent_bar_color: RGBColor
    category_style: str
    status_style: str
    cover_style: str
    asset_style: str
    recommendation_style: str
    kicker_ringkasan: str
    kicker_analisis: str
    # Palet warna tema (report.theme_color) — 5 peran, sama persis dgn export_pdf.py. Dipakai
    # di elemen BRAND/struktural — TIDAK PERNAH di SEVERITY_COLOR/kondisional is_critical.
    accent_main: RGBColor
    accent_bg: RGBColor
    accent_chart: RGBColor
    accent_light: RGBColor
    accent_soft: RGBColor
    theme: dict | None = None
    cover_hero_stat: dict | None = None


def _build_cover_slide(block: dict, ctx: _PptBlockContext):
    ctx.cover_hero_stat = block.get("hero_stat")
    if ctx.cover_style == "split":
        add_split_cover_slide(ctx.prs, block, ctx.flourish_corner, ctx.logo_path, theme=ctx.theme)
        return None
    cover = ctx.prs.slides.add_slide(ctx.prs.slide_layouts[6])
    add_dark_bg(cover, theme=ctx.theme)
    add_corner_flourish(cover, ctx.flourish_corner, theme=ctx.theme)
    # 1e: bingkai pill putih HANYA jalur Visual - di jalur Descriptive cover tidak
    # berubah sedikit pun.
    _mgmt = bool(block.get("is_management"))
    add_logo(cover, ctx.logo_path, width=Inches(2.85), dark=True, pill=_mgmt,
             x=(SLIDE_W - Inches(2.85) - Inches(0.30)) if _mgmt else None,
             y=Inches(0.30) if _mgmt else Inches(0.18))

    # 1b: kicker dilewati kalau kosong - jalur Visual membuangnya, Descriptive tetap.
    if str(block.get("kicker") or "").strip():
        add_kicker(cover, block["kicker"], color=WHITE, y=Inches(1.7))

    # Ukuran font judul menyesuaikan panjangnya (laporan bisa dari domain apa saja
    # - SOC, keuangan, KPI, dll - judulnya bisa jauh lebih panjang/pendek dari
    # contoh mana pun), lalu posisi subtitle & info DIHITUNG dari perkiraan tinggi
    # judul yang sebenarnya — bukan angka tetap — supaya tidak pernah tertimpa
    # berapa pun baris yang dibutuhkan judul untuk wrap.
    title_text = block["title"]
    # Jalur Visual memakai tangga ukuran BERSAMA dgn PDF (satu sumber di
    # report_render_logic) - sebelumnya kedua exporter punya tangganya sendiri dan sudah
    # menyimpang jauh (44/38/32/26 di sini vs 34 tetap di PDF) untuk halaman yang sama.
    if _mgmt:
        title_size_pt = ukuran_judul_cover_mgmt(title_text)
    elif len(title_text) > 55:
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
    tp.alignment = PP_ALIGN.LEFT
    tp.text = title_text
    _set_font(tp, TITLE_FONT, Pt(title_size_pt), bold=True, color=WHITE)

    title_height_in = _estimate_wrapped_height_in(
        title_text, title_size_pt, 9.5,
        em_per_char=_EM_KARAKTER_JUDUL_COVER if _mgmt else 0.6)
    # Lantai posisi jalur Visual diturunkan 0,17in agar sejajar dgn PDF (terukur dari
    # render piksel kedua format). Mekanismenya tidak berubah: tinggi judul yang di-wrap
    # tetap ikut dihitung supaya judul panjang tidak menabrak baris di bawahnya.
    _lantai_sub = 2.72 if _mgmt else 3.05
    _jarak_sub = 0.01 if _mgmt else 0.15
    sub_top_in = max(title_top_in + title_height_in + _jarak_sub, _lantai_sub)
    sub_box = cover.shapes.add_textbox(MARGIN_X, Inches(sub_top_in), Inches(9.5), Inches(0.5))
    sp = sub_box.text_frame.paragraphs[0]
    sp.alignment = PP_ALIGN.LEFT
    sp.text = block["subtitle"]
    _set_font(sp, BODY_FONT, Pt(_MGMT_COVER_SUB_PT if _mgmt else 15), color=WHITE)

    _jarak_info = 0.43 if _mgmt else 0.65
    _lantai_info = 3.17 if _mgmt else 3.9
    info_top_in = max(sub_top_in + _jarak_info, _lantai_info)
    info_box = cover.shapes.add_textbox(MARGIN_X, Inches(info_top_in), Inches(9.5), Inches(0.9))
    itf = info_box.text_frame
    itf.word_wrap = True
    p1 = itf.paragraphs[0]
    p1.alignment = PP_ALIGN.LEFT
    p1.text = f'{block["period_label"]} {block["period_text"]}'
    _set_font(p1, BODY_FONT, Pt(_MGMT_COVER_PERIOD_PT if _mgmt else 12.5), color=WHITE)
    # 1c: baris info DILEWATI kalau kosong - menambah paragraf kosong tetap menyisakan
    # satu baris tinggi di kotak teks, jadi yang terlihat bukan 'baris hilang'.
    if str(block.get("info_line") or "").strip():
        p2 = itf.add_paragraph()
        p2.alignment = PP_ALIGN.LEFT
        p2.text = block["info_line"]
        _set_font(p2, BODY_FONT, Pt(_MGMT_COVER_PERIOD_PT if _mgmt else 12.5),
                  color=ctx.accent_soft)
        p2.space_before = Pt(6)

    _footer_off = 0.42 if _mgmt else 0.55
    footer_l = cover.shapes.add_textbox(MARGIN_X, SLIDE_H - Inches(_footer_off), Inches(5), Inches(0.3))
    flp = footer_l.text_frame.paragraphs[0]
    flp.alignment = PP_ALIGN.LEFT
    flp.text = block["header_title"]
    _set_font(flp, BODY_FONT, Pt(_MGMT_COVER_FOOTER_PT if _mgmt else 10), bold=True, color=WHITE)
    return None


def _build_executive_summary_slide(block: dict, ctx: _PptBlockContext):
    exec_slide = ctx.prs.slides.add_slide(ctx.prs.slide_layouts[6])
    add_dark_bg(exec_slide, theme=ctx.theme)
    add_logo(exec_slide, ctx.logo_path, dark=True)
    add_kicker(exec_slide, ctx.kicker_ringkasan, color=WHITE)
    title_bottom = add_title(exec_slide, block["heading"], color=WHITE)

    # BUG NYATA YANG DIPERBAIKI (dilaporkan user, disertai tangkapan layar): grid
    # kartu KPI SEBELUMNYA selalu mulai di Y=1.7in tetap, menabrak baris ke-2
    # heading kalau heading-nya panjang & wrap (umum utk data non-SOC). grid_y
    # sekarang mengikuti tinggi heading sungguhan; grid_h dikurangi secukupnya
    # supaya grid tidak meluber ke luar slide kalau grid_y ikut turun.
    grid_y_in = max(title_bottom + 0.12, 1.0)
    grid_h_in = max(2.2, 4.3 - (grid_y_in - 1.7))

    # Keluhan nyata dari pengguna: kalau item KPI cuma sedikit (mis. 2 kartu, 1
    # baris), grid+caption cuma menempati sepertiga atas slide, sisanya kosong total
    # sampai footer. Perkirakan DULU tinggi grid+caption yang akan dihasilkan (tanpa
    # menggambar apapun — replikasi kecil rumus di add_stat_card_grid), lalu kalau
    # ternyata jauh lebih pendek dari ruang yang tersedia, geser blok ini ke bawah
    # supaya "kosongnya" terbagi rata di atas & bawah, bukan menumpuk di bawah saja.
    # Tinggi donut+legend pendamping (lihat penjelasan di bawah) diikutkan ke
    # perkiraan content_total_in supaya perhitungan "geser ke bawah utk centering"
    # tetap akurat waktu chart ini ada, bukan cuma menghitung grid+caption saja.
    CHART_BLOCK_H_IN = 2.15
    has_chart = bool(block.get("chart"))

    n_stat_items = len(block["stat_items"])
    if n_stat_items:
        rows_n = math.ceil(n_stat_items / ctx.stat_cols)
        max_card_h_in = {1: 2.6, 2: 2.0}.get(rows_n, 1.6)
        natural_card_h_in = (grid_h_in - 0.2 * (rows_n - 1)) / rows_n
        card_h_in = min(natural_card_h_in, max_card_h_in)
        grid_total_h_in = rows_n * card_h_in + (rows_n - 1) * 0.2
        caption_h_in = _estimate_wrapped_height_in(block["caption"], 11.5, Emu(CONTENT_W).inches)
        purpose_h_est_in = (
            0.1 + _estimate_wrapped_height_in(block["purpose_text"], 10.5, Emu(CONTENT_W).inches) + 0.08
        ) if block.get("purpose_text") else 0
        finding_h_est_in = (
            0.1 + _estimate_wrapped_height_in(block["extra_finding_text"], 10.5, Emu(CONTENT_W).inches) + 0.08
        ) if block.get("extra_finding_text") else 0
        content_total_in = grid_total_h_in + 0.25 + caption_h_in + purpose_h_est_in + finding_h_est_in + (0.3 + CHART_BLOCK_H_IN if has_chart else 0)
        available_in = 6.95 - grid_y_in
        if available_in > content_total_in:
            grid_y_in += (available_in - content_total_in) / 2

    grid_bottom = add_stat_card_grid(exec_slide, MARGIN_X, Inches(grid_y_in), CONTENT_W, Inches(grid_h_in), block["stat_items"], cols=ctx.stat_cols, dark=True, theme=ctx.theme)

    # BUG YANG DIPERBAIKI: box caption dulu tinggi TETAP 0.9in apa pun panjang
    # teksnya — kalau blok grid+caption digeser turun (lihat centering di atas),
    # box tetap 0.9in penuh bisa meluber ke zona footer walau isi captionnya cuma
    # 1 baris pendek. Tinggi box sekarang mengikuti estimasi wrap sungguhan (dibatasi
    # minimum 0.4in), sama seperti perhitungan yang dipakai utk centering di atas.
    slide_bottom_in = Emu(SLIDE_H).inches
    caption_box_h_in = max(0.4, _estimate_wrapped_height_in(block["caption"], 11.5, Emu(CONTENT_W).inches) + 0.1)
    cap_top_in = min(Emu(grid_bottom).inches + 0.25, slide_bottom_in - 0.25)
    cap_top = Inches(cap_top_in)
    caption_box_h_in = min(caption_box_h_in, max(0.2, slide_bottom_in - cap_top_in - 0.05))
    cap_box = exec_slide.shapes.add_textbox(MARGIN_X, cap_top, CONTENT_W, Inches(caption_box_h_in))
    ctf = cap_box.text_frame
    ctf.word_wrap = True
    cp = ctf.paragraphs[0]
    cp.alignment = PP_ALIGN.LEFT
    cp.text = block["caption"]
    _set_font(cp, BODY_FONT, Pt(11.5), italic=True, color=ctx.accent_soft)

    # PERMINTAAN USER: slide terpisah "Latar Belakang dan Tujuan Analisis" dihapus (cuma
    # metadata boilerplate) — kalimat tujuannya digabung ke sini sbg paragraf tambahan.
    content_bottom = cap_box.top + cap_box.height
    purpose_text = block.get("purpose_text")
    if purpose_text:
        purpose_h_in = max(0.3, _estimate_wrapped_height_in(purpose_text, 10.5, Emu(CONTENT_W).inches) + 0.08)
        purpose_top_in = min(Emu(content_bottom).inches + 0.1, slide_bottom_in - 0.25)
        purpose_top = Inches(purpose_top_in)
        purpose_h_in = min(purpose_h_in, max(0.2, slide_bottom_in - purpose_top_in - 0.05))
        purpose_box = exec_slide.shapes.add_textbox(MARGIN_X, purpose_top, CONTENT_W, Inches(purpose_h_in))
        pptf = purpose_box.text_frame
        pptf.word_wrap = True
        ppp = pptf.paragraphs[0]
        ppp.alignment = PP_ALIGN.LEFT
        ppp.text = purpose_text
        _set_font(ppp, BODY_FONT, Pt(10.5), color=WHITE)
        content_bottom = purpose_box.top + purpose_box.height

    # PERMINTAAN USER: kalau Temuan Utama cuma 1 butir, slide terpisahnya dihapus & butir itu
    # ditempel di sini (lihat report_render_logic.py, exec_summary_cand["extra_finding_text"]).
    extra_finding_text = block.get("extra_finding_text")
    if extra_finding_text:
        finding_h_in = max(0.3, _estimate_wrapped_height_in(extra_finding_text, 10.5, Emu(CONTENT_W).inches) + 0.08)
        finding_top_in = min(Emu(content_bottom).inches + 0.1, slide_bottom_in - 0.25)
        finding_top = Inches(finding_top_in)
        finding_h_in = min(finding_h_in, max(0.2, slide_bottom_in - finding_top_in - 0.05))
        finding_box = exec_slide.shapes.add_textbox(MARGIN_X, finding_top, CONTENT_W, Inches(finding_h_in))
        ftf = finding_box.text_frame
        ftf.word_wrap = True
        fp = ftf.paragraphs[0]
        fp.alignment = PP_ALIGN.LEFT
        label_run = fp.add_run()
        label_run.text = f'{block.get("extra_finding_label", "")} '
        _set_font(label_run, BODY_FONT, Pt(10.5), bold=True, color=WHITE)
        text_run = fp.add_run()
        text_run.text = extra_finding_text
        _set_font(text_run, BODY_FONT, Pt(10.5), color=WHITE)
        content_bottom = finding_box.top + finding_box.height

    # PERMINTAAN USER: slide insight_tile/dynamic_section 1-panel yang tipis & gagal disambung
    # ke tetangga (lihat backstop terakhir di _group_candidates_into_pages) dititipkan ke sini
    # sbg beberapa butir bernomor. Dirender manual (bukan add_note_box, yang bertema TERANG)
    # spt purpose_text/extra_finding_text di atas — slide ini gelap.
    orphan_insights = block.get("extra_orphan_insights") or []
    for o in orphan_insights:
        text = f"{o['label']}: {o['text']}" if o.get("label") else o["text"]
        o_h_in = max(0.3, _estimate_wrapped_height_in(text, 10.5, Emu(CONTENT_W).inches) + 0.08)
        orphan_top_in = min(Emu(content_bottom).inches + 0.1, slide_bottom_in - 0.25)
        orphan_top = Inches(orphan_top_in)
        o_h_in = min(o_h_in, max(0.2, slide_bottom_in - orphan_top_in - 0.05))
        o_box = exec_slide.shapes.add_textbox(MARGIN_X, orphan_top, CONTENT_W, Inches(o_h_in))
        otf = o_box.text_frame
        otf.word_wrap = True
        op = otf.paragraphs[0]
        op.alignment = PP_ALIGN.LEFT
        op.text = text
        _set_font(op, BODY_FONT, Pt(10.5), color=WHITE)
        content_bottom = o_box.top + o_box.height

    # Panel ini SATU-SATUNYA kandidat bertema "overview" (lihat report_render_logic.py) —
    # tidak pernah digabung dgn kandidat lain, jadi SELALU jadi slide sendiri. Tanpa donut
    # pendamping ini, slide berisi kartu KPI + 1-2 kalimat caption saja terasa nyaris kosong
    # (dilaporkan user). Ramp warna dari palet tema (bukan CATEGORY_COLOR_RAMP tetap) supaya
    # konsisten dgn tema yang dipilih, sama seperti fix warna kartu KPI/bar management report.
    if has_chart:
        chart = block["chart"]
        ramp = [ctx.accent_light, WHITE, ctx.accent_chart, ctx.accent_soft, GRAY_TEXT]
        colors = ramp[:len(chart["values"])]
        donut_side = Inches(1.75)
        # Keep the optional overview chart inside the fixed slide canvas even when
        # preceding narrative blocks consume more vertical space than estimated.
        chart_y = min(content_bottom + Inches(0.3), SLIDE_H - donut_side - Inches(0.05))
        add_native_doughnut_chart(exec_slide, MARGIN_X, chart_y, donut_side, donut_side, chart["categories"], chart["values"], colors=colors, theme=ctx.theme)
        _add_mini_legend(exec_slide, MARGIN_X + donut_side + Inches(0.35), chart_y + Inches(0.15), CONTENT_W - donut_side - Inches(0.35), chart["categories"], ramp, text_color=WHITE)
    return exec_slide


def _merge_tail_into_other(labels, values, colors, max_items=4, other_label="Lainnya"):
    """Sama persis dgn export_pdf.py::_merge_tail_into_other (2 modul ini tidak saling
    impor internal helper satu sama lain, jadi disalin, bukan bug duplikasi) — kalau item
    lebih dari `max_items`, gabungkan SISA item jadi SATU entri "{other_label}" (nilainya
    dijumlah), dipakai bareng utk donat & legend-nya SEBELUM keduanya digambar. BUG
    DIPERBAIKI: legend compact (lihat _add_mini_legend/_mini_legend_layout) membatasi
    jumlah item yang DITAMPILKAN, tapi donat NATIVE PowerPoint akan tetap menggambar SEMUA
    slice asli kalau datanya tidak ikut dipangkas duluan — slice yang tidak disebut di
    legend jadi warna "yatim" tanpa keterangan apa pun."""
    if len(labels) <= max_items:
        return labels, values, colors
    keep = max_items - 1
    merged_value = sum(values[keep:])
    new_labels = list(labels[:keep]) + [other_label]
    new_values = list(values[:keep]) + [merged_value]
    new_colors = list(colors[:keep]) + [GRAY_TEXT]
    return new_labels, new_values, new_colors


def _mini_legend_layout(categories, w, compact: bool = False):
    """Hitung POSISI (row, x_offset_in, label_text) tiap item legend TANPA menggambar apa
    pun — dipakai BERSAMA oleh mini_legend_rows_needed() (pemanggil perlu tahu tinggi
    legend SEBELUM menentukan ukuran donut, lihat _build_management_visual_dashboard_slide)
    & _add_mini_legend() (yang benar2 menggambar) — WAJIB logika SAMA PERSIS di keduanya,
    kalau tidak perkiraan tinggi dari yang pertama tidak nyambung dgn hasil gambar yang
    kedua. `w` dalam EMU (Emu/Inches object dari pptx.util), `compact=True` membatasi ke 4
    item & pakai ukuran lebih kecil (mirror _mini_legend_html di export_pdf.py)."""
    if compact:
        categories = categories[:4]
    font_pt = 7 if compact else 9
    truncate_len = 14 if compact else 20
    swatch_in = 0.08 if compact else 0.1
    row_h_in = 0.19 if compact else 0.24
    item_gap_in = 0.14
    # Taksiran lebar per karakter (bukan pengukuran font metrik sungguhan — python-pptx
    # tidak expose itu) di font_pt ini, DILEBIHKAN sedikit (drpd kurang) supaya wrap lebih
    # cepat drpd baris kepanjangan/ketiban shape berikutnya.
    char_w_in = font_pt * 0.60 / 96
    w_in = Emu(w).inches if not isinstance(w, (int, float)) else w
    items = []
    cur_x_in, cur_row = 0.0, 0
    dd_categories = _dedupe_truncated_labels(categories, truncate_len)
    for cat in dd_categories:
        label_text = cat
        item_w_in = swatch_in + 0.06 + char_w_in * len(label_text) + item_gap_in
        if cur_x_in > 0 and cur_x_in + item_w_in > w_in:
            cur_x_in, cur_row = 0.0, cur_row + 1
        items.append((cur_row, cur_x_in, label_text))
        cur_x_in += item_w_in
    n_rows = (items[-1][0] + 1) if items else 0
    return items, n_rows, font_pt, swatch_in, row_h_in


def mini_legend_height_needed_in(categories, w, compact: bool = False) -> float:
    """Perkiraan TINGGI total (inci) yang akan dipakai _add_mini_legend utk `categories` ini
    pada lebar `w` — dipanggil pemanggil (mis. donut tile dashboard) SEBELUM menggambar
    chart-nya sendiri, supaya ukuran chart bisa di-clamp menyisakan ruang yang CUKUP utk
    legend di bawahnya (lihat _build_management_visual_dashboard_slide). BUG DIPERBAIKI:
    sebelumnya ukuran donut dihitung TANPA tahu legend bakal makan berapa baris — legend
    yang kepanjangan (banyak item/nama panjang) bisa nembus keluar kartu/nabrak caption di
    bawahnya. row_h_in DIAMBIL dari _mini_legend_layout yang sama persis dipakai
    _add_mini_legend (bukan konstanta duplikat terpisah) — keduanya WAJIB selalu sinkron."""
    _, n_rows, _, _, row_h_in = _mini_legend_layout(categories, w, compact)
    return n_rows * row_h_in


def _add_mini_legend(slide, x, y, w, categories, ramp, text_color=None, compact: bool = False):
    """Legend ringkas (kotak warna kecil + nama, tanpa persentase) utk chart "donut"/"stacked"
    di _add_mini_chart — add_native_doughnut_chart/add_stacked_proportion_bar sendiri TIDAK
    menyertakan legend (lihat docstring add_stacked_proportion_bar: legend memang tanggung
    jawab pemanggil), tanpa ini pembaca tidak tahu warna mana mewakili kategori apa di panel
    kecil ini. Kotak warna pakai add_shape RECTANGLE, pola sama persis dgn segmen
    add_stacked_proportion_bar di atas (bukan API baru). `text_color` opsional (default
    GRAY_TEXT) — dioverride panel berlatar gelap (lihat _build_executive_summary_slide).

    BUG DIPERBAIKI (drift vs export_pdf.py::_mini_legend_html, yang MENGALIR horizontal —
    beberapa item per baris): versi PPT ini sebelumnya SELALU 1 item per baris (bertumpuk
    vertikal), jadi utk N item legend PPT makan N baris sedangkan PDF cuma perlu ~2 baris
    (isi ~3-4 item per baris) — tinggi legend jauh lebih boros drpd versi PDF utk data yang
    sama persis. Sekarang mengalir horizontal juga (wrap ke baris baru kalau kepenuhan,
    lihat _mini_legend_layout), plus `compact=True` (batasi 4 item + font lebih kecil,
    mirror _mini_legend_html) utk konteks dashboard yang padat."""
    if compact:
        categories = categories[:4]
    text_color = text_color or GRAY_TEXT
    items, n_rows, font_pt, swatch_in, row_h_in = _mini_legend_layout(categories, w, compact)
    swatch = Inches(swatch_in)
    for i, (row, x_off_in, label_text) in enumerate(items):
        row_y = y + Inches(row_h_in * row)
        item_x = x + Inches(x_off_in)
        sq = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, item_x, row_y + Inches(row_h_in * 0.22), swatch, swatch)
        sq.fill.solid()
        sq.fill.fore_color.rgb = ramp[i % len(ramp)]
        sq.line.color.rgb = WHITE
        sq.line.width = Pt(0.5)
        _no_shadow(sq)
        label_box = slide.shapes.add_textbox(
            item_x + swatch + Inches(0.05), row_y, Inches(1.4), Inches(row_h_in),
        )
        lp = label_box.text_frame.paragraphs[0]
        lp.text = label_text
        lp.alignment = PP_ALIGN.LEFT
        _set_font(lp, BODY_FONT, Pt(font_pt), color=text_color)
    return Inches(row_h_in * n_rows)


def _add_mini_chart(slide, chart: dict, x, y, w, h, ctx: "_PptBlockContext"):
    """Chart kecil pendukung (block["chart"], lihat _build_dynamic_section_slide/
    _build_key_findings_slide di bawah) — dipakai BERSAMA keduanya, mirror _mini_chart_html
    di export_pdf.py. Ukuran SENGAJA lebih kecil dari slide chart full-size (severity/category
    slide pakai tinggi 4.0-4.6in) — panel pendukung harus terasa sekunder."""
    colors = [SEVERITY_COLOR[k] for k in chart["severity_keys"]] if chart.get("severity_keys") else None
    ramp = colors or CATEGORY_COLOR_RAMP
    if chart["type"] == "gauge":
        side = min(Emu(w).inches, Emu(h).inches)
        add_native_gauge(
            slide, x, y, Inches(side), Inches(side),
            chart["value"], chart.get("max", 100), chart.get("label", ""),
            color=(colors[0] if colors else None), theme=ctx.theme,
        )
    elif chart["type"] == "donut":
        # Sisakan ~25% tinggi panel utk legend di bawah ring — add_native_doughnut_chart
        # sendiri TIDAK menampilkan nama kategori (cuma angka per slice, lihat docstring-nya).
        side = min(Emu(w).inches, Emu(h).inches * 0.72)
        add_native_doughnut_chart(slide, x, y, Inches(side), Inches(side), chart["categories"], chart["values"], colors=colors, theme=ctx.theme)
        _add_mini_legend(slide, x, y + Inches(side) + Inches(0.08), w, chart["categories"], ramp)
    elif chart["type"] == "stacked":
        bar_h = Inches(0.4)
        add_stacked_proportion_bar(slide, x, y, w, chart["values"], colors=colors, height=bar_h, labels=chart["categories"])
    elif chart["type"] == "bar_line":
        add_bar_line_chart(slide, x, y, w, h, chart["categories"], chart["values"], chart.get("cumulative"), color=ctx.accent_main)
    else:
        add_native_bar_chart(slide, x, y, w, h, chart["categories"], chart["values"], colors=colors or [ctx.accent_main], horizontal=True)


def _draw_insight_tile(slide, panel: dict, ctx: "_PptBlockContext", x, y, w, h):
    """Kartu ringkas dipakai BERSAMA oleh panel_kind "insight_tile" (Trend/Severity/Risk
    bawaan AI) DAN "dynamic_section" (section kustom AI) — keduanya bertema "insight" (lihat
    report_render_logic.py) & bisa berbagi 1 slide berdampingan sampai 4 kartu. Menggambar
    LANGSUNG ke `slide` yang SUDAH ADA pada bounding box (x,y,w,h) — BEDA dari builder "slide
    mandiri" lain di file ini yang membuat slide sendiri, supaya bisa dipanggil N kali di 1
    slide yang sama oleh _build_page_slide (lihat di bawah)."""
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    card.fill.solid()
    card.fill.fore_color.rgb = WHITE
    card.line.color.rgb = PANEL_BORDER
    card.line.width = Pt(0.75)
    _no_shadow(card)
    _modest_corner(card)

    pad = Inches(0.22)
    label = panel.get("label") or panel.get("title") or ""
    _draw_header_band(slide, x + pad, y + Inches(0.16), w - pad * 2, label)

    # BUG DIPERBAIKI (dilaporkan user): caption/bullet di bawah SEBELUMNYA dipatok dari SISI
    # BAWAH kartu (`y + h - 1.2`) — kalau tinggi kartu `h` besar (mis. berbagi baris dgn
    # kartu tetangga yang lebih tinggi) TAPI konten visual di atasnya (label/chart/stat)
    # pendek, caption jadi terdorong jauh ke bawah, menyisakan CELAH KOSONG besar di TENGAH
    # kartu antara visual & caption — bukan mengalir wajar dari atas. Sekarang caption
    # SELALU ditaruh tepat di bawah visual_bottom_in (posisi SEBENARNYA konten visual
    # berhenti, dihitung per cabang di bawah) — label -> visual -> caption mengalir
    # berurutan dari atas, TIDAK PERNAH ada celah kosong di tengah apa pun tinggi kartunya.
    visual_top_in = Emu(y).inches + 0.65
    visual_bottom_in = visual_top_in
    w_in = Emu(w).inches
    if panel.get("trend_stat"):
        ts = panel["trend_stat"]
        direction_color = {"up": GREEN_CHART, "down": RED_CRIT, "flat": GRAY_TEXT}[ts["direction"]]
        vbox = slide.shapes.add_textbox(x, Inches(visual_top_in + 0.25), w, Inches(0.6))
        vp = vbox.text_frame.paragraphs[0]
        vp.text = ts["value"]
        vp.alignment = PP_ALIGN.CENTER
        _set_font(vp, TITLE_FONT, Pt(20), bold=True, color=direction_color)
        sub_box = slide.shapes.add_textbox(x + pad, Inches(visual_top_in + 0.85), w - pad * 2, Inches(0.45))
        sp = sub_box.text_frame.paragraphs[0]
        sp.text = ts["label"]
        sp.alignment = PP_ALIGN.CENTER
        _set_font(sp, BODY_FONT, Pt(8.5), color=GRAY_TEXT)
        visual_bottom_in = visual_top_in + 0.85 + 0.45
    elif panel.get("chart"):
        _add_mini_chart(slide, panel["chart"], x + pad, Inches(visual_top_in), w - pad * 2, Inches(2.0), ctx)
        visual_bottom_in = visual_top_in + 2.0
    elif panel.get("aux_stat"):
        value, aux_label = panel["aux_stat"]
        vbox = slide.shapes.add_textbox(x, Inches(visual_top_in + 0.25), w, Inches(0.6))
        vp = vbox.text_frame.paragraphs[0]
        vp.text = value
        vp.alignment = PP_ALIGN.CENTER
        _set_font(vp, TITLE_FONT, Pt(20), bold=True, color=TEXT_DARK)
        sub_box = slide.shapes.add_textbox(x + pad, Inches(visual_top_in + 0.85), w - pad * 2, Inches(0.45))
        sp = sub_box.text_frame.paragraphs[0]
        sp.text = aux_label
        sp.alignment = PP_ALIGN.CENTER
        _set_font(sp, BODY_FONT, Pt(8.5), color=GRAY_TEXT)
        visual_bottom_in = visual_top_in + 0.85 + 0.45
    elif panel.get("aux_list"):
        # PERMINTAAN USER ("panel bertingkat" — chart/angka -> strip KPI -> daftar kotak
        # angka): kalau ada totalnya, tampilkan sbg strip angka kecil DI ATAS daftar — total
        # ini turunan LANGSUNG dari daftar yang sama persis di bawahnya, aman diulang.
        list_top_in = visual_top_in
        if panel.get("aux_list_total"):
            tvbox = slide.shapes.add_textbox(x, Inches(visual_top_in), w, Inches(0.4))
            tvp = tvbox.text_frame.paragraphs[0]
            tvp.text = str(panel["aux_list_total"])
            tvp.alignment = PP_ALIGN.CENTER
            _set_font(tvp, TITLE_FONT, Pt(16), bold=True, color=TEXT_DARK)
            tsub = slide.shapes.add_textbox(x, Inches(visual_top_in + 0.32), w, Inches(0.2))
            tsp = tsub.text_frame.paragraphs[0]
            tsp.text = "Total"
            tsp.alignment = PP_ALIGN.CENTER
            _set_font(tsp, BODY_FONT, Pt(7.5), color=GRAY_TEXT)
            list_top_in = visual_top_in + 0.58
        rows = [(it["label"], it["value"]) for it in panel["aux_list"]]
        _draw_kv_rows(slide, x + pad, Inches(list_top_in), w - pad * 2, rows)
        visual_bottom_in = list_top_in + 0.3 * min(4, len(rows))

    caption_text = panel.get("caption") or panel.get("text") or ""
    caption_top_in = visual_bottom_in + 0.15
    add_bullet_lines(slide, x + pad, Inches(caption_top_in), w - pad * 2, caption_text, theme=ctx.theme, font_pt=8.5)


def _draw_kv_rows(slide, x, y, w, rows):
    """Daftar label-nilai ringkas TANPA bingkai (dipakai _draw_insight_tile utk aux_list) —
    versi sangat ringkas dari add_ivory_panel(mode="kv") tanpa kartu pembungkus, supaya muat
    di ruang kecil dalam kartu insight."""
    row_h_in = 0.3
    for i, (label, value) in enumerate(rows[:4]):
        row_y = y + Inches(i * row_h_in)
        lb = slide.shapes.add_textbox(x, row_y, w, Inches(row_h_in))
        lp = lb.text_frame.paragraphs[0]
        lp.alignment = PP_ALIGN.LEFT
        lp.text = f"{label}: {value}"
        _set_font(lp, BODY_FONT, Pt(9), color=TEXT_DARK)


def _draw_distribution_panel(slide, panel: dict, ctx: "_PptBlockContext", x, y, w, h):
    """Panel "mandiri" (judul sendiri di dalam kontennya) dipakai oleh SEMUA panel_kind
    bertema "distribution": category_distribution, status_distribution, kpi_radar,
    time_heatmap, period_compare — bisa berbagi 1 slide berdampingan sampai 3 kolom, ATAU
    dipanggil sendirian selebar CONTENT_W kalau kandidat lain di temanya tidak ada. Menggambar
    LANGSUNG ke `slide` yang sudah ada (lihat catatan sama di _draw_insight_tile)."""
    # accent_light/accent_soft dilewatkan _light_safe() — kedua peran ini SENGAJA pucat di
    # tema "gold" (lihat docstring _light_safe), tanpa ini segmen ke-3/ke-4 chart di panel
    # BERLATAR TERANG ini nyaris tak kelihatan.
    ramp = [ctx.accent_main, ctx.accent_chart, _light_safe(ctx.accent_light), _light_safe(ctx.accent_soft), GRAY_TEXT]
    w_in = Emu(w).inches
    h_in = Emu(h).inches
    y_in = Emu(y).inches

    title_box = slide.shapes.add_textbox(x, y, w, Inches(0.45))
    ttf = title_box.text_frame
    ttf.word_wrap = True
    tp = ttf.paragraphs[0]
    tp.alignment = PP_ALIGN.LEFT
    tp.text = panel["title"]
    _set_font(tp, TITLE_FONT, Pt(13), bold=True, color=TEXT_DARK)

    # BUG DIPERBAIKI (drift vs export_pdf.py::_build_kpi_radar_block, yang memperlakukan
    # ai_caption/intro sbg SATU slot caption yang SAMA, SELALU di BAWAH chart): versi PPT
    # ini sebelumnya punya 2 jalur caption terpisah — "intro" digambar polos di ATAS chart
    # di sini, "ai_caption" digambar sbg kotak catatan di BAWAH chart (lihat akhir fungsi
    # ini) — kalau keduanya terisi, tampil DOBEL (isinya mirip, di 2 tempat beda gaya);
    # kalau cuma "intro" yang terisi, letaknya beda dari versi PDF (yang selalu di bawah).
    # Digabung jadi SATU sumber (ai_caption diutamakan) & SELALU di bawah chart, persis PDF.
    chart_top_in = y_in + 0.5

    kind = panel["panel_kind"]
    visual_bottom_in = chart_top_in
    if kind in ("category_distribution", "status_distribution"):
        cats = panel["categories"][:4]
        vals = panel["values"][:4]
        total = sum(vals) or 1
        colors = [ramp[j % len(ramp)] for j in range(len(vals))]
        legend_rows = [(colors[j], name, f"{round(val / total * 100, 1)}%") for j, (name, val) in enumerate(zip(cats, vals))]
        style = ctx.category_style if kind == "category_distribution" else ctx.status_style
        if style == "funnel" and kind == "status_distribution":
            order = sorted(range(len(vals)), key=lambda i: -vals[i])
            funnel_h_in = min(2.3, h_in - (chart_top_in - y_in) - 0.3)
            add_funnel_chart(slide, x, Inches(chart_top_in), w, Inches(funnel_h_in), [cats[i] for i in order], [vals[i] for i in order], color=ctx.accent_main)
            visual_bottom_in = chart_top_in + funnel_h_in
        elif style == "donut":
            side = min(w_in, 1.9)
            side_x = x + Inches((w_in - side) / 2)
            add_native_doughnut_chart(slide, side_x, Inches(chart_top_in), Inches(side), Inches(side), cats, vals, colors=colors, theme=ctx.theme)
            visual_bottom_in = chart_top_in + side
        elif style == "stacked":
            bar_h_in = 0.4
            add_stacked_proportion_bar(slide, x, Inches(chart_top_in), w, vals, colors=colors, height=Inches(bar_h_in))
            visual_bottom_in = chart_top_in + bar_h_in
        elif style == "treemap":
            # PERMINTAAN USER (tambah jenis visualisasi baru): mirror export_pdf.py's
            # category/status distribution treemap branch.
            treemap_h_in = min(2.2, h_in - (chart_top_in - y_in) - 0.3)
            add_treemap_shapes(slide, x, Inches(chart_top_in), w, Inches(treemap_h_in), cats, vals, colors=colors)
            visual_bottom_in = chart_top_in + treemap_h_in
        else:
            chart_h_in = 1.8
            add_native_bar_chart(slide, x, Inches(chart_top_in), w, Inches(chart_h_in), list(reversed(cats)), list(reversed(vals)), horizontal=True, colors=[ctx.accent_bar_color])
            visual_bottom_in = chart_top_in + chart_h_in
        legend_top_in = visual_bottom_in + 0.2
        legend_h_in = 0.4 + 0.26 * len(legend_rows)
        legend_title = panel.get("legend_panel_title") or ("Proportion" if is_english(ctx.report) else "Proporsi")
        add_ivory_panel(slide, x, Inches(legend_top_in), w, Inches(legend_h_in), "%", legend_title, legend_rows, mode="legend", theme=ctx.theme)
        visual_bottom_in = legend_top_in + legend_h_in
    else:
        # BUG DIPERBAIKI (ditemukan lewat tes kepadatan halaman, permintaan user): 3 chart
        # native ini dulu dibatasi TETAP 2.6in tinggi apa pun `h_in` (ruang SUNGGUHAN
        # tersedia) — solo di 1 halaman penuh (h_in besar), sisa ruang di bawahnya kosong
        # (chart native python-pptx otomatis meregang mengisi bounding box yang diberikan,
        # beda dari SVG manual di export_pdf.py — cukup perbesar box-nya, bukan reka ulang
        # chart-nya). Cap dinaikkan jadi porsi dari `h_in` sungguhan (sisakan sedikit utk
        # kotak catatan kalau ada), bukan angka tetap.
        has_caption = bool(panel.get("ai_caption") or panel.get("intro"))
        avail_in = h_in - (chart_top_in - y_in) - 0.2
        chart_h_in = max(2.6, avail_in - (1.3 if has_caption else 0.1))
        if kind == "kpi_radar":
            add_native_radar_chart(slide, x, Inches(chart_top_in), w, Inches(chart_h_in), panel["axes"], panel["values"], color=ctx.accent_main)
        elif kind == "time_heatmap":
            add_heatmap_grid(slide, x, Inches(chart_top_in), w, Inches(chart_h_in), panel["day_labels"], panel["hour_labels"], panel["grid"], color=ctx.accent_main)
        elif kind == "period_compare":
            add_grouped_bar_chart(
                slide, x, Inches(chart_top_in), w, Inches(chart_h_in),
                panel["categories"], panel["series_a"], panel["series_b"],
                label_a=panel["label_a"], label_b=panel["label_b"],
                color_a=ctx.accent_main, color_b=_light_safe(ctx.accent_light),
            )
        visual_bottom_in = chart_top_in + chart_h_in

    caption_text = panel.get("ai_caption") or panel.get("intro")
    if caption_text:
        add_note_box(slide, x, Inches(visual_bottom_in + 0.1), w, caption_text, theme=ctx.theme)


def _build_severity_distribution_slide(block: dict, ctx: _PptBlockContext):
    sev_slide = ctx.prs.slides.add_slide(ctx.prs.slide_layouts[6])
    add_logo(sev_slide, ctx.logo_path)
    add_kicker(sev_slide, ctx.kicker_analisis)
    title_bottom = add_title(sev_slide, block["title"])

    intro_y = max(title_bottom + 0.15, 1.45)
    intro_box = sev_slide.shapes.add_textbox(MARGIN_X, Inches(intro_y), CONTENT_W, Inches(0.5))
    itf3 = intro_box.text_frame
    itf3.word_wrap = True
    ip3 = itf3.paragraphs[0]
    ip3.alignment = PP_ALIGN.LEFT
    ip3.text = block["intro"]
    _set_font(ip3, BODY_FONT, Pt(12), color=GRAY_TEXT)

    sev_body_y = intro_y + 0.65
    sev_has_caption = bool(block.get("ai_caption"))
    sev_body_h = Inches(4.0) if sev_has_caption else Inches(4.6)
    sev_colors = [SEVERITY_COLOR[k] for k in block["severity_keys"]]
    # panel_side: chart di kiri+panel di kanan (default) atau dibalik — ukuran
    # kolom tetap sama, cuma posisinya ditukar.
    if ctx.panel_side == "left":
        sev_panel_x, sev_chart_x = MARGIN_X, MARGIN_X + Inches(4.7)
    else:
        sev_chart_x, sev_panel_x = MARGIN_X, MARGIN_X + Inches(8.5)
    add_native_bar_chart(sev_slide, sev_chart_x, Inches(sev_body_y), Inches(8.1), sev_body_h, block["categories"], block["values"], colors=sev_colors)

    add_critical_highlight_panel(
        sev_slide, sev_panel_x, Inches(sev_body_y), Inches(4.3), sev_body_h,
        f'{block["crit_pct"]}', block["panel_text"], block["detail_text"], theme=ctx.theme,
    )
    if sev_has_caption:
        add_note_box(sev_slide, MARGIN_X, Inches(sev_body_y) + sev_body_h + Inches(0.12), CONTENT_W, block["ai_caption"], theme=ctx.theme)
    return sev_slide


def _build_critical_table_slide(block: dict, ctx: _PptBlockContext):
    table_slide = ctx.prs.slides.add_slide(ctx.prs.slide_layouts[6])
    add_logo(table_slide, ctx.logo_path)
    # RED_CRIT TIDAK ikut tema (severity fixed) — cuma cabang "tidak kritis" yang ikut tema.
    kicker_color = RED_CRIT if block["kicker_is_critical"] else GRAY_TEXT
    add_kicker(table_slide, block["kicker"], color=kicker_color)
    title_bottom = add_title(table_slide, block["title"])

    table_y = max(title_bottom + 0.15, 1.55)
    add_native_table(table_slide, MARGIN_X, Inches(table_y), CONTENT_W, Inches(4.9), block["headers"], block["rows"], set(block["highlight_idx"]), theme=ctx.theme)

    if block["caption"]:
        cap_box = table_slide.shapes.add_textbox(MARGIN_X, Inches(table_y) + Inches(4.9) + Inches(0.1), CONTENT_W, Inches(0.4))
        cp2 = cap_box.text_frame.paragraphs[0]
        cp2.alignment = PP_ALIGN.LEFT
        cp2.text = block["caption"]
        _set_font(cp2, BODY_FONT, Pt(10.5), italic=True, color=GRAY_TEXT)
    return table_slide


def _build_asset_cards_slide(block: dict, ctx: _PptBlockContext):
    asset_slide = ctx.prs.slides.add_slide(ctx.prs.slide_layouts[6])
    use_podium = ctx.asset_style == "podium" and len(block["items"]) == 3
    if use_podium:
        # Titik variasi tampilan: ranking podium top-3 (bg TERANG, analog cover
        # normal) — alternatif dari baris kartu gelap standar, lihat add_podium_row.
        add_logo(asset_slide, ctx.logo_path)
        add_kicker(asset_slide, block["kicker"])
        title_bottom = add_title(asset_slide, block["title"], color=TEXT_DARK)
        podium_y = max(title_bottom + 0.15, 1.1)
        add_podium_row(asset_slide, MARGIN_X, Inches(podium_y), CONTENT_W, Inches(max(3.0, 6.5 - podium_y)), block["items"], theme=ctx.theme)
    elif ctx.asset_style == "bars":
        # Titik variasi tampilan: daftar berperingkat dgn batang proporsional (bg
        # GELAP, analog kartu standar) — dipakai utk jumlah item berapa pun (bukan
        # cuma tepat 3 seperti podium), lihat add_asset_ranked_bars.
        add_dark_bg(asset_slide, theme=ctx.theme)
        add_logo(asset_slide, ctx.logo_path, dark=True)
        add_kicker(asset_slide, block["kicker"], color=WHITE)
        title_bottom = add_title(asset_slide, block["title"], color=WHITE)
        bars_y = max(title_bottom + 0.15, 1.1)
        # Sisa ruang di bawah baris terakhir dibagi rata (digeser ke tengah), bukan
        # ditumpuk semua di bawah — pola sama dgn add_asset_card_row (cards).
        bars_row_h_in = 1.0
        bars_content_h_in = len(block["items"]) * bars_row_h_in
        bars_available_in = 6.6 - bars_y
        if bars_available_in > bars_content_h_in:
            bars_y += (bars_available_in - bars_content_h_in) / 2
        add_asset_ranked_bars(asset_slide, MARGIN_X, Inches(bars_y), CONTENT_W, block["items"], row_h=Inches(bars_row_h_in), theme=ctx.theme, is_en=is_english(ctx.report))
    else:
        add_dark_bg(asset_slide, theme=ctx.theme)
        add_logo(asset_slide, ctx.logo_path, dark=True)
        add_kicker(asset_slide, block["kicker"], color=WHITE)
        title_bottom = add_title(asset_slide, block["title"], color=WHITE)

        card_items = [(it["num"], it["name"], it["stat"], it["detail"]) for it in block["items"]]
        cards_y = max(title_bottom + 0.12, 1.05)
        # BUG DIPERBAIKI (tes kepadatan halaman): slide ini SELALU solo (asset_cards ada di
        # _PPT_PANEL_STANDALONE_BUILDERS, tidak pernah berbagi slide) — kartu diperbesar scr
        # proporsional drpd cuma dipusatkan dgn margin kosong di atas/bawah.
        add_asset_card_row(asset_slide, MARGIN_X, Inches(cards_y), CONTENT_W, Inches(max(3.0, 6.5 - cards_y)), card_items, theme=ctx.theme, scale=2.0)
    return asset_slide


def _build_key_findings_slide(block: dict, ctx: _PptBlockContext):
    find_slide = ctx.prs.slides.add_slide(ctx.prs.slide_layouts[6])
    add_logo(find_slide, ctx.logo_path)
    add_kicker(find_slide, block["kicker"])
    title_bottom = add_title(find_slide, block["title"])

    findings_items = [(it["num"], it["title"], it["detail"]) for it in block["items"]]

    # RED_CRIT TIDAK ikut tema (severity fixed) — cuma cabang "tidak kritis" yang ikut tema.
    def _finding_color(idx, item, _items=block["items"]):
        return RED_CRIT if _items[idx]["is_critical"] else TEXT_DARK

    content_top = max(title_bottom + 0.12, 1.0)
    has_chart = bool(block.get("chart"))
    # Panel chart pendukung di samping (kalau ada, lihat build_report_blocks) — sempitkan
    # lebar daftar temuan, pola panel_x/panel_w sama dgn _build_dynamic_section_slide.
    findings_w = Inches(7.3) if has_chart else CONTENT_W
    if has_chart and ctx.panel_side == "left":
        panel_w = CONTENT_W - findings_w - Inches(0.4)
        panel_x = MARGIN_X
        findings_x = panel_x + panel_w + Inches(0.4)
    else:
        findings_x = MARGIN_X
        panel_x = MARGIN_X + findings_w + Inches(0.4)
        panel_w = SLIDE_W - MARGIN_X - panel_x

    # Keluhan nyata dari pengguna: 1 kolom penuh CONTENT_W bikin baris ~11.8in
    # lebar (nyaris selebar slide) sekaligus font kekecilan (9.3pt) kalau itemnya
    # banyak — grid 2 kolom dipakai begitu item > 2 (lihat catatan di add_badge_list).
    # Dipaksa 1 kolom saat ada chart pendukung (lebar cuma 7.3in, 2 kolom di situ terlalu sempit).
    findings_cols = 1 if has_chart else (2 if len(findings_items) > 2 else 1)
    add_badge_list(find_slide, findings_x, Inches(content_top), findings_w, findings_items, badge_color=_finding_color, row_h=Inches(1.0), max_y=SLIDE_H - Inches(0.4), cols=findings_cols)
    if has_chart:
        _add_mini_chart(find_slide, block["chart"], panel_x, Inches(content_top), panel_w, Inches(2.8), ctx)
    return find_slide


def _build_recommendations_slide(block: dict, ctx: _PptBlockContext):
    rec_slide = ctx.prs.slides.add_slide(ctx.prs.slide_layouts[6])
    add_logo(rec_slide, ctx.logo_path)
    add_kicker(rec_slide, block["kicker"])
    title_bottom = add_title(rec_slide, block["title"])

    items = block["items"]
    start_y_rec = Inches(max(title_bottom + 0.12, 1.0))

    # PERBAIKAN KRITIS (dilaporkan user dgn screenshot nyata — teks kepotong/patah,
    # keterangan hilang di node "atas garis"): gaya "timeline" di PPT ini SELALU dipanggil
    # dgn PERSIS 2 item (SOC memaginasi rekomendasi 2/halaman, lihat
    # soc_recommendations_per_page di report_render_logic.py) — kasus PALING LEMAH utk
    # visual timeline (garis waktu idealnya utk urutan lebih panjang, bukan cuma 2 titik),
    # dan cabang ini TIDAK punya jaring pengaman font-scaling/pre-pass tinggi yang sudah
    # terbukti andal di cabang grid kartu di bawah. Daripada terus berjudi dgn 1 gaya yang
    # rapuh utk kasus yang SELALU sama persis, gaya vertikal (grid kartu, terbukti andal +
    # sudah dites) dipakai langsung utk 2 item — variasi "timeline" disimpan hanya utk 3+
    # item (kalau suatu saat ada jalur lain yang mengirim lebih banyak item sekaligus).
    if ctx.recommendation_style == "timeline" and 3 <= len(items) <= 6:
        # Titik variasi tampilan: garis waktu horizontal (analog timeline di
        # export_pdf.py) — alternatif dari grid kartu standar di bawah, dipakai
        # kalau jumlah rekomendasi pas 2-6 (lihat add_recommendation_timeline).
        timeline_h = Inches(max(2.6, 6.9 - Emu(start_y_rec).inches))
        add_recommendation_timeline(rec_slide, MARGIN_X, start_y_rec, CONTENT_W, timeline_h, items, theme=ctx.theme)
        return rec_slide

    if ctx.recommendation_style == "banners":
        # Titik variasi tampilan: daftar banner selebar halaman bertumpuk vertikal
        # (analog _recommendation_banner_list_html di export_pdf.py) — alternatif
        # dari grid kartu, dipakai utk jumlah item BERAPA PUN (beda dari timeline
        # yang dibatasi 2-6).
        add_recommendation_banner_list(rec_slide, MARGIN_X, start_y_rec, CONTENT_W, items, max_y=SLIDE_H - Inches(0.4), theme=ctx.theme)
        return rec_slide

    card_cols = ctx.card_cols
    gap = Inches(0.3)
    rec_rows = math.ceil(len(items) / card_cols)

    # Pre-pass: hitung tinggi SETIAP baris (di skala normal) sebelum menggambar
    # apapun, supaya total tinggi semua baris bisa diketahui DULU. BUG YANG
    # DIPERBAIKI: sebelumnya tidak ada pengecekan terhadap SLIDE_H — laporan
    # dengan 3 baris (6 rekomendasi, 2 kolom) yang detailnya panjang bisa membuat
    # baris terakhir meluber ke luar slide, persis pola yang sama dengan bug
    # Temuan Utama. Kalau totalnya bakal melebihi ruang tersisa, seluruh baris
    # (font & tinggi kartu) dikecilkan proporsional supaya semua rekomendasi
    # tetap tampil penuh di dalam slide.
    def _row_items_and_width(r):
        row_start = r * card_cols
        row_items = items[row_start:row_start + card_cols]
        row_items_count = len(row_items)
        card_w = (CONTENT_W - gap * (row_items_count - 1)) / row_items_count
        return row_items, card_w

    def _estimate_row_height_in(row_items, card_w, title_pt, detail_pt):
        text_w_in = Emu(card_w - Inches(0.4)).inches
        row_height_in = 1.3
        for item in row_items:
            title_h_in = _estimate_wrapped_height_in(item["title"], title_pt, text_w_in)
            content_h_in = 0.62 + title_h_in + 0.25
            if item["detail"]:
                detail_h_in = _estimate_wrapped_height_in(item["detail"], detail_pt, text_w_in)
                content_h_in += detail_h_in + 0.1
            row_height_in = max(row_height_in, content_h_in)
        return row_height_in

    available_in = Emu(SLIDE_H - start_y_rec).inches - 0.4
    est_total_in = sum(
        _estimate_row_height_in(_row_items_and_width(r)[0], _row_items_and_width(r)[1], 13, 10.5) + Emu(gap).inches
        for r in range(rec_rows)
    ) - Emu(gap).inches
    scale = 1.0
    if available_in > 0 and est_total_in > available_in:
        scale = max(available_in / est_total_in, 0.55)
    elif available_in > 0 and est_total_in < available_in:
        # BUG DIPERBAIKI (permintaan user lanjutan — "isi via konten, bukan jarak"): dulu
        # kartu tetap skala 1.0 lalu TITIK AWAL baris pertama digeser ke bawah supaya sisa
        # ruang kosong terbagi rata atas/bawah (jadi MARGIN, bukan isi). Sekarang scale
        # dinaikkan (maks 1.9x) supaya badge/font/kartu genuinely lebih besar & mengisi
        # ruang lapang itu sendiri — mirror _build_key_findings_block/_build_management_
        # action_items_block versi PDF yang sudah py mekanisme sama.
        # Do not enlarge recommendation cards beyond their measured natural size:
        # wrapped text is remeasured after scaling and could make the final card
        # taller than the pre-pass estimate, pushing it below the slide canvas.
        scale = min(1.0, available_in / est_total_in)
    title_pt, detail_pt = 13 * scale, 10.5 * scale
    cur_y_rec = start_y_rec
    for r in range(rec_rows):
        row_items, card_w = _row_items_and_width(r)
        row_height_in = _estimate_row_height_in(row_items, card_w, title_pt, detail_pt)
        card_h = Inches(row_height_in)
        for c, item in enumerate(row_items):
            cx = MARGIN_X + c * (card_w + gap)
            cy = cur_y_rec
            fg, _bg = URGENCY_COLOR.get(item.get("urgency", "low"), (GRAY_TEXT, IVORY))
            card = rec_slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, cy, card_w, card_h)
            card.fill.solid()
            card.fill.fore_color.rgb = IVORY
            card.line.color.rgb = PANEL_BORDER
            card.line.width = Pt(0.75)
            _no_shadow(card)
            _modest_corner(card)
            left_bar = rec_slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, cx, cy, Inches(0.05), card_h)
            left_bar.fill.solid()
            left_bar.fill.fore_color.rgb = fg
            left_bar.line.fill.background()
            _no_shadow(left_bar)
            add_badge_circle(rec_slide, cx + Inches(0.2), cy + Inches(0.18 * scale), Inches(0.36 * scale), item["num"], fg, font_size=Pt(13 * scale))
            title_box = rec_slide.shapes.add_textbox(cx + Inches(0.2), cy + Inches(0.62 * scale), card_w - Inches(0.4), Inches(0.35))
            ttf2 = title_box.text_frame
            ttf2.word_wrap = True
            tp2 = ttf2.paragraphs[0]
            tp2.alignment = PP_ALIGN.LEFT
            tp2.text = item["title"]
            _set_font(tp2, BODY_FONT, Pt(title_pt), bold=True, color=TEXT_DARK)
            if item["detail"]:
                det_box = rec_slide.shapes.add_textbox(cx + Inches(0.2), cy + Inches(0.95 * scale), card_w - Inches(0.4), card_h - Inches(1.0 * scale))
                dtf2 = det_box.text_frame
                dtf2.word_wrap = True
                dp2 = dtf2.paragraphs[0]
                dp2.alignment = PP_ALIGN.LEFT
                dp2.text = item["detail"]
                _set_font(dp2, BODY_FONT, Pt(detail_pt), color=GRAY_TEXT)
            if item.get("urgency"):
                pill = rec_slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE, cx + card_w - Inches(1.1), cy + Inches(0.15), Inches(0.9), Inches(0.26),
                )
                pill.fill.solid()
                pill.fill.fore_color.rgb = fg
                pill.line.fill.background()
                _no_shadow(pill)
                _modest_corner(pill, frac=0.5)
                ptf = pill.text_frame
                ptf.margin_left = ptf.margin_right = Inches(0.02)
                ptf.margin_top = ptf.margin_bottom = 0
                pp = ptf.paragraphs[0]
                pp.text = item["urgency"].upper()
                pp.alignment = PP_ALIGN.CENTER
                _set_font(pp, BODY_FONT, Pt(7.5 * scale), bold=True, color=WHITE)
        cur_y_rec += card_h + gap
    return rec_slide


def _build_conclusion_slide(block: dict, ctx: _PptBlockContext):
    concl_slide = ctx.prs.slides.add_slide(ctx.prs.slide_layouts[6])
    add_dark_bg(concl_slide, theme=ctx.theme)
    add_logo(concl_slide, ctx.logo_path, dark=True)
    add_kicker(concl_slide, block["kicker"], color=WHITE)
    title_bottom = add_title(concl_slide, block["title"], color=WHITE)

    content_top2 = max(title_bottom + 0.1, 1.0)
    priority_items = [(p["letter"], p["text"]) for p in block["priority_items"]]
    # Kalau tidak ada priority_items (rekomendasi sudah tampil di halaman lain, lihat
    # report_render_logic.py), kolom kanan tidak digambar sama sekali — left_w2 TETAP
    # 7.0in dulu di sini bakal menyisakan ~5in kolom kanan kosong total. Lebar teks
    # sekarang mengikuti CONTENT_W penuh saat itu terjadi.
    left_w2 = CONTENT_W if not priority_items else Inches(7.0)
    # panel_side cuma dipakai kalau ada priority_items — kalau kosong, swap ke
    # "left" akan menyisakan kolom kiri kosong & teks malah ke kanan (lebih buruk
    # dari layout defaultnya), sama seperti guard yang sama di export_pdf.py.
    if priority_items and ctx.panel_side == "left":
        text_x2 = MARGIN_X + Inches(4.3) + Inches(0.4)
        panel_x3 = MARGIN_X
    else:
        text_x2 = MARGIN_X
        panel_x3 = MARGIN_X + left_w2 + Inches(0.4)
    # BUG DIPERBAIKI (ditemukan lewat audit E3): tinggi box teks kesimpulan dulu tetap
    # Inches(1.8) & posisi pill di bawahnya dulu offset TETAP (+2.0in) — block["text"] datang
    # dari _shorten_to_caption(conclusion_text, max_sentences=3) TANPA batas karakter, jadi
    # kesimpulan AI yang panjang (400-600+ karakter) bisa wrap lebih dari ~8 baris & pill
    # stat di bawahnya (pill_y) menimpa ekor paragraf itu. Tinggi & posisi pill sekarang
    # dihitung dari estimasi wrap teks sungguhan (_estimate_wrapped_height_in), sama seperti
    # pola yang sudah dipakai di hampir semua builder lain di file ini.
    text_w2_in = Emu(left_w2).inches
    text_h2_in = _estimate_wrapped_height_in(block["text"], 13, text_w2_in)
    para_box2 = concl_slide.shapes.add_textbox(text_x2, Inches(content_top2), left_w2, Inches(max(1.0, text_h2_in + 0.15)))
    ptf2 = para_box2.text_frame
    ptf2.word_wrap = True
    pp2 = ptf2.paragraphs[0]
    pp2.alignment = PP_ALIGN.LEFT
    pp2.text = block["text"]
    _set_font(pp2, BODY_FONT, Pt(13), color=RGBColor(0xE8, 0xEC, 0xE6))

    pill_y = Inches(content_top2 + text_h2_in + 0.35)
    for pill_text in block["pills"][:3]:
        add_pill_stat(concl_slide, text_x2, pill_y, left_w2, Inches(0.6), pill_text, theme=ctx.theme)
        pill_y += Inches(0.75)

    if priority_items:
        add_priority_panel(
            concl_slide, panel_x3, Inches(content_top2), Inches(4.3), Inches(max(3.0, 6.3 - content_top2)),
            block["priority_panel_title"], priority_items, theme=ctx.theme,
        )
    return concl_slide


def _build_closing_summary_slide(block: dict, ctx: _PptBlockContext):
    """PERMINTAAN USER: mirror export_pdf.py::_build_closing_summary_block — Temuan Utama,
    Rekomendasi, dan Kesimpulan digabung jadi 1 slide kalau ketiganya genuinely tipis (lihat
    should_combine_closing di report_render_logic.py). Temuan & Rekomendasi berdampingan
    (urutan kiri/kanan ikut ctx.panel_side, sama spt _build_conclusion_slide), Kesimpulan sbg
    strip gelap tipis penuh lebar di bawah keduanya."""
    slide = ctx.prs.slides.add_slide(ctx.prs.slide_layouts[6])
    add_logo(slide, ctx.logo_path)
    add_kicker(slide, block["kicker"])
    title_bottom = add_title(slide, block["title"])

    # BUG DIPERBAIKI (permintaan user lanjutan — "Kesimpulan" solo jadi penyumbang kegagalan
    # kepadatan TERBANYAK): slide ini dulu SELALU asumsi Temuan & Rekomendasi BERDUA ada (2
    # kolom tetap 50/50) — sekarang salah satu boleh TIDAK ADA (lihat should_combine_closing
    # di report_render_logic.py), kolom yang ada melebar PENUH drpd dipaksa 50% dgn separuh
    # slide kosong di sebelahnya.
    has_findings = block.get("findings_items") is not None
    has_recs = block.get("recommendation_items") is not None
    content_top_in = max(title_bottom + 0.12, 1.0)
    max_y_in = 6.3
    if has_findings and has_recs:
        col_w = (CONTENT_W - Inches(0.4)) / 2
        left_x, right_x = MARGIN_X, MARGIN_X + col_w + Inches(0.4)
        findings_x, rec_x = (right_x, left_x) if ctx.panel_side == "left" else (left_x, right_x)
    else:
        col_w = CONTENT_W
        findings_x = rec_x = MARGIN_X
    content_bottom_in = content_top_in

    if has_findings:
        ftp = slide.shapes.add_textbox(findings_x, Inches(content_top_in), col_w, Inches(0.3))
        fp = ftp.text_frame.paragraphs[0]
        fp.alignment = PP_ALIGN.LEFT
        fp.text = block["findings_title"]
        _set_font(fp, BODY_FONT, Pt(13), bold=True, color=TEXT_DARK)
        findings_items = [(it["num"], it["title"], it["detail"]) for it in block["findings_items"]]

        def _finding_color(idx, item, _items=block["findings_items"]):
            return RED_CRIT if _items[idx]["is_critical"] else TEXT_DARK

        findings_bottom = add_badge_list(
            slide, findings_x, Inches(content_top_in + 0.4), col_w, findings_items,
            badge_color=_finding_color, row_h=Inches(0.75), max_y=Inches(max_y_in),
        )
        content_bottom_in = max(content_bottom_in, Emu(findings_bottom).inches)

    if has_recs:
        rtp = slide.shapes.add_textbox(rec_x, Inches(content_top_in), col_w, Inches(0.3))
        rp = rtp.text_frame.paragraphs[0]
        rp.alignment = PP_ALIGN.LEFT
        rp.text = block["rec_title"]
        _set_font(rp, BODY_FONT, Pt(13), bold=True, color=TEXT_DARK)

        rec_cur_y = content_top_in + 0.4
        # BUG DIPERBAIKI (audit E3): tinggi kartu rekomendasi dulu MURNI hasil bagi rata sisa
        # ruang / jumlah item — tidak peduli seberapa panjang title/detail item itu sendiri
        # (dari AI, bisa jauh lebih panjang dari rata2). Sekarang tinggi kartu adalah MAX
        # antara hasil bagi rata (supaya kartu tetap terasa seragam saat semua item pendek)
        # dgn estimasi wrap teks sungguhan (_estimate_wrapped_height_in) per item — kartu
        # berkonten panjang tidak lagi menimpa kartu tetangganya di bawah.
        rec_text_w_in = Emu(col_w).inches - 0.34
        even_row_h_in = min(0.95, max(0.6, (max_y_in - rec_cur_y) / max(len(block["recommendation_items"]), 1)))
        for it in block["recommendation_items"]:
            fg, _bg = URGENCY_COLOR.get(it.get("urgency", "low"), (GRAY_TEXT, IVORY))
            title_h_in = _estimate_wrapped_height_in(it["title"], 10.5, rec_text_w_in)
            detail_h_in = _estimate_wrapped_height_in(it["detail"], 9, rec_text_w_in) if it.get("detail") else 0
            rec_row_h_in = max(even_row_h_in, title_h_in + detail_h_in + 0.28)
            card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, rec_x, Inches(rec_cur_y), col_w, Inches(rec_row_h_in - 0.1))
            card.fill.solid()
            card.fill.fore_color.rgb = IVORY
            card.line.color.rgb = PANEL_BORDER
            card.line.width = Pt(0.75)
            _no_shadow(card)
            _modest_corner(card)
            left_bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, rec_x, Inches(rec_cur_y), Inches(0.05), Inches(rec_row_h_in - 0.1))
            left_bar.fill.solid()
            left_bar.fill.fore_color.rgb = fg
            left_bar.line.fill.background()
            _no_shadow(left_bar)
            tb = slide.shapes.add_textbox(rec_x + Inches(0.18), Inches(rec_cur_y + 0.06), col_w - Inches(0.34), Inches(rec_row_h_in - 0.22))
            tf = tb.text_frame
            tf.word_wrap = True
            p1 = tf.paragraphs[0]
            p1.alignment = PP_ALIGN.LEFT
            label_run = p1.add_run()
            label_run.text = it["title"]
            _set_font(label_run, BODY_FONT, Pt(10.5), bold=True, color=TEXT_DARK)
            if it.get("urgency"):
                urg_run = p1.add_run()
                urg_run.text = f'  [{it["urgency"].upper()}]'
                _set_font(urg_run, BODY_FONT, Pt(7.5), bold=True, color=fg)
            if it.get("detail"):
                p2 = tf.add_paragraph()
                p2.alignment = PP_ALIGN.LEFT
                p2.text = it["detail"]
                _set_font(p2, BODY_FONT, Pt(9), color=GRAY_TEXT)
            rec_cur_y += rec_row_h_in
        content_bottom_in = max(content_bottom_in, rec_cur_y)

    content_bottom_in += 0.25

    if block.get("conclusion_text"):
        # BUG DIPERBAIKI (audit E3): strip_h_in dulu MURNI dari sisa ruang halaman
        # (6.9 - content_bottom_in) — kalau findings/rekomendasi di atas sudah memakan
        # banyak tempat, strip ini bisa jadi sependek 1.1in apa pun panjang conclusion_text
        # (AI, via _shorten_to_caption max 2 kalimat TANPA batas karakter) — teks lalu
        # menimpa pill stat yang nempel di dasar strip. Tinggi minimum sekarang JUGA
        # mempertimbangkan estimasi wrap teks sungguhan, bukan cuma sisa ruang.
        concl_pills = block.get("conclusion_pills") or []
        concl_text_w_in = Emu(CONTENT_W).inches - 0.5
        concl_text_h_in = _estimate_wrapped_height_in(block["conclusion_text"], 10.5, concl_text_w_in)
        min_strip_h_in = 0.5 + concl_text_h_in + (0.55 if concl_pills else 0.15)
        safe_bottom_in = Emu(SLIDE_H).inches - 0.25
        available_strip_in = max(0.6, safe_bottom_in - content_bottom_in)
        strip_h_in = min(max(1.1, 6.9 - content_bottom_in, min_strip_h_in), available_strip_in)
        strip = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, MARGIN_X, Inches(content_bottom_in), CONTENT_W, Inches(strip_h_in))
        strip.fill.solid()
        strip.fill.fore_color.rgb = ctx.theme["bg"]
        strip.line.color.rgb = ctx.theme["light"]
        strip.line.width = Pt(0.75)
        _no_shadow(strip)
        _modest_corner(strip)

        ctp = slide.shapes.add_textbox(MARGIN_X + Inches(0.25), Inches(content_bottom_in + 0.15), CONTENT_W - Inches(0.5), Inches(0.3))
        cp_title = ctp.text_frame.paragraphs[0]
        cp_title.alignment = PP_ALIGN.LEFT
        cp_title.text = block["conclusion_title"]
        _set_font(cp_title, TITLE_FONT, Pt(13), bold=True, color=WHITE)

        ctxt = slide.shapes.add_textbox(MARGIN_X + Inches(0.25), Inches(content_bottom_in + 0.5), CONTENT_W - Inches(0.5), Inches(max(0.1, strip_h_in - 0.55)))
        ctxt.text_frame.word_wrap = True
        cp_text = ctxt.text_frame.paragraphs[0]
        cp_text.alignment = PP_ALIGN.LEFT
        cp_text.text = block["conclusion_text"]
        _set_font(cp_text, BODY_FONT, Pt(10.5), color=RGBColor(0xE8, 0xEC, 0xE6))

        pills = concl_pills
        if pills:
            pill_y = Inches(content_bottom_in + strip_h_in - 0.45)
            pill_x = MARGIN_X + Inches(0.25)
            for pill_text in pills[:3]:
                pill_w = Inches(max(1.2, 0.12 * len(pill_text) + 0.5))
                pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, pill_x, pill_y, pill_w, Inches(0.32))
                _modest_corner(pill, frac=0.5)
                pill.fill.solid()
                pill.fill.fore_color.rgb = ctx.theme["main"]
                pill.line.color.rgb = ctx.theme["light"]
                pill.line.width = Pt(0.75)
                _no_shadow(pill)
                ptf = pill.text_frame
                ptf.vertical_anchor = MSO_ANCHOR.MIDDLE
                pp = ptf.paragraphs[0]
                pp.text = pill_text
                pp.alignment = PP_ALIGN.CENTER
                _set_font(pp, BODY_FONT, Pt(8.5), bold=True, color=ctx.theme["light"])
                pill_x += pill_w + Inches(0.15)
    return slide


def _build_closing_slide(block: dict, ctx: _PptBlockContext):
    if ctx.cover_style == "split":
        closing_block = {**block, "hero_stat": ctx.cover_hero_stat}
        add_split_closing_slide(ctx.prs, closing_block, ctx.flourish_corner, ctx.logo_path, theme=ctx.theme)
        return None
    closing = ctx.prs.slides.add_slide(ctx.prs.slide_layouts[6])
    add_dark_bg(closing, theme=ctx.theme)
    add_corner_flourish(closing, ctx.flourish_corner, theme=ctx.theme)
    # BUG YANG DIPERBAIKI (dilaporkan user): halaman penutup ("Terima Kasih") SEBELUMNYA
    # sama sekali tidak punya logo — satu-satunya halaman yang benar2 tanpa identitas brand.
    # Ukuran sama besarnya dgn cover (halaman pertama & terakhir yang dilihat, sengaja lebih
    # menonjol drpd slide isi).
    _mgmt = bool(block.get("is_management"))
    add_logo(closing, ctx.logo_path, width=Inches(2.85), dark=True, pill=_mgmt)
    # Teks digeser ke kanan kalau flourish-nya di pojok kiri-bawah (satu-satunya
    # varian yang jangkauannya menjorok ke area teks, yang start dari MARGIN_X) —
    # keluhan nyata dari pengguna: garis lengkung dekoratif menembus teks penutup.
    text_x2 = Inches(2.3) if ctx.flourish_corner == "bottom_left" else MARGIN_X
    text_w2 = Inches(9) - (text_x2 - MARGIN_X)
    text_w2_in = Emu(text_w2).inches
    # Jalur Visual: judul penutup dinaikkan 0,90in agar sejajar dgn PDF (terukur).
    _ty_top = 2.10 if _mgmt else 3.0
    title_box2 = closing.shapes.add_textbox(text_x2, Inches(_ty_top), text_w2, Inches(1.0))
    tp3 = title_box2.text_frame.paragraphs[0]
    tp3.alignment = PP_ALIGN.LEFT
    tp3.text = block["thank_you"]
    _set_font(tp3, TITLE_FONT, Pt(_MGMT_CLOSING_THANKS_PT if _mgmt else 40), bold=True, color=WHITE)
    sub2_top_in = 2.74 if _mgmt else 3.85
    # BUG YANG DIPERBAIKI (dilaporkan user): box ini dulu tinggi TETAP 0.8in,
    # sementara note_box di bawah diposisikan berdasarkan estimasi tinggi KONTEN
    # sebenarnya (sub2_height_in, sering < 0.8in utk judul 1 baris) — box tetap
    # 0.8in penuh jadi meluber menimpa note_box. Tinggi box sekarang eksplisit
    # mengikuti estimasi yang sama dipakai utk memposisikan note_box di bawahnya.
    # 1f: baris yang mengulang judul laporan DILEWATI kalau kosong - jalur Visual
    # membuangnya. Tingginya ikut nol supaya catatan di bawahnya naik, bukan menyisakan
    # celah kosong setinggi satu baris.
    if str(block.get("title") or "").strip():
        sub2_height_in = _estimate_wrapped_height_in(block["title"], 14, text_w2_in)
        sub_box2 = closing.shapes.add_textbox(text_x2, Inches(sub2_top_in), text_w2, Inches(sub2_height_in + 0.1))
        sp2 = sub_box2.text_frame
        sp2.word_wrap = True
        sp2_p = sp2.paragraphs[0]
        sp2_p.alignment = PP_ALIGN.LEFT
        sp2_p.text = block["title"]
        _set_font(sp2_p, BODY_FONT, Pt(14), color=WHITE)
    else:
        sub2_height_in = 0.0
    _lantai_note = 2.74 if _mgmt else 4.4
    note_top_in = max(sub2_top_in + sub2_height_in + 0.1, _lantai_note)
    note_box = closing.shapes.add_textbox(text_x2, Inches(note_top_in), text_w2, Inches(0.4))
    np_ = note_box.text_frame.paragraphs[0]
    np_.alignment = PP_ALIGN.LEFT
    np_.text = block["note"]
    _set_font(np_, BODY_FONT, Pt(_MGMT_CLOSING_NOTE_PT if _mgmt else 11.5), italic=True,
              color=ctx.accent_soft)
    return None


def _hex_to_rgb(hex_str: str) -> RGBColor:
    hex_clean = hex_str.lstrip("#")
    if len(hex_clean) == 3:
        hex_clean = "".join(c * 2 for c in hex_clean)
    if len(hex_clean) == 6:
        r = int(hex_clean[0:2], 16)
        g = int(hex_clean[2:4], 16)
        b = int(hex_clean[4:6], 16)
        return RGBColor(r, g, b)
    return GREEN_MAIN


def _darken(color: RGBColor) -> RGBColor:
    """Mirror _darken di export_pdf.py (lihat docstring di sana utk riwayat 2 revisi lengkap)
    — `color` yang masuk ke sini SUDAH melewati _light_safe(...) di pemanggil (cukup gelap
    utk teks putih), jadi dipakai APA ADANYA di kasus normal. Darken jaring-pengaman
    DIBATASI paling banyak ke factor 0.85 (bukan 0.55 spt sebelumnya) supaya huenya masih
    "terbaca sebagai warna yang sama" kalau pun perlu digelapkan."""
    luminance = (0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]) / 255
    if luminance <= 0.55 or luminance == 0:
        return color
    factor = max(0.85, 0.55 / luminance)
    return RGBColor(round(color[0] * factor), round(color[1] * factor), round(color[2] * factor))


def _blend_with_white(color: RGBColor, frac: float) -> RGBColor:
    """Mirror _blend_with_white di export_pdf.py — campur `color` dgn putih sebesar (1-frac)
    jadi RGBColor baru. Dipakai turunkan shade "chart" utk tema warna KUSTOM (color picker)
    supaya beda dari "main" (lihat pemakaian di generate_ppt_report)."""
    frac = max(0.0, min(1.0, frac))
    r = round(color[0] * frac + 255 * (1 - frac))
    g = round(color[1] * frac + 255 * (1 - frac))
    b = round(color[2] * frac + 255 * (1 - frac))
    return RGBColor(r, g, b)


def _light_safe(color: RGBColor, max_luminance: float = 0.68) -> RGBColor:
    """Mirror _light_safe di export_pdf.py (lihat docstring di sana utk alasan lengkap) —
    pastikan `color` cukup gelap dipakai sbg warna isi/teks di atas latar TERANG (IVORY/
    putih). Peran "light"/"soft" tema (ctx.accent_light/accent_soft) SENGAJA pucat krn
    awalnya cuma dipakai sbg teks di atas latar GELAP — utk tema "gold" khususnya, warna
    pucatnya jauh lebih ekstrem drpd tema lain, nyaris tak kelihatan kalau dipakai ulang apa
    adanya sbg warna bar/kartu di atas latar terang. RGBColor (subclass bytes) diindeks
    langsung [0]/[1]/[2], bukan lstrip/int seperti versi hex di export_pdf.py."""
    # ATURANNYA SATU, di report_render_logic.gelapkan_untuk_latar_terang - fungsi ini tinggal
    # pembungkus tipe (RGBColor). Dulu rumusnya disalin di sini DAN di export_pdf._light_safe.
    r, g, b = gelapkan_untuk_latar_terang(color[0], color[1], color[2], max_luminance)
    return RGBColor(r, g, b)


def _draw_fact_strip_kolom(slide, pasangan: list, x_in: float, y_in: float, w_in: float):
    """A8 sisi PPT - kembaran _fact_strip_kolom_html di export_pdf.py. Isi & penyaringnya
    datang dari report_render_logic.fakta_strip_kolom yang SAMA, jadi kedua format menampilkan
    pasangan yang identik; fungsi ini cuma menggambar. Bentuk ikut jumlah pasangan: satu ->
    strip lebar penuh, dua -> dua kotak bersebelahan. Label ITALIC, nilai BOLD."""
    if not pasangan:
        return
    n = len(pasangan)
    kotak_w = (w_in - 0.08) / n if n > 1 else w_in
    for i, (label, nilai) in enumerate(pasangan):
        bx = x_in + i * (kotak_w + 0.08)
        kotak = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(bx), Inches(y_in),
                                       Inches(kotak_w), Inches(_DASH_COLS_FACT_H_IN))
        _modest_corner(kotak)
        kotak.fill.solid(); kotak.fill.fore_color.rgb = RGBColor(0xF2, 0xF4, 0xF7)
        kotak.line.fill.background(); _no_shadow(kotak)
        tb = slide.shapes.add_textbox(Inches(bx + 0.07), Inches(y_in + 0.06),
                                      Inches(max(0.3, kotak_w - 0.14)),
                                      Inches(_DASH_COLS_FACT_H_IN - 0.12))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        p0 = tf.paragraphs[0]
        r1 = p0.add_run(); r1.text = str(label) + " "
        _set_font(r1, BODY_FONT, Pt(6.5), color=GRAY_TEXT); r1.font.italic = True
        r2 = p0.add_run(); r2.text = str(nilai)
        _set_font(r2, BODY_FONT, Pt(8.5), bold=True, color=TEXT_DARK)


def add_dashboard_title(slide, text: str, x_in: float, w_in: float, color=TEXT_DARK, size_pt: float | None = None) -> float:
    """Judul halaman dashboard Management BARU (permintaan user A2): mulai di y=0, lebar
    penuh, TANPA kicker terpisah di atasnya (dulu kicker "SOROTAN VISUAL" berulang IDENTIK di
    4+ halaman dashboard berturut-turut tanpa memberi info apa pun — dihapus total, lihat
    report_render_logic.py::build_management_report_blocks). Tinggi kotak, ukuran font dan
    zona bebas logo TIDAK lagi dihitung di sini - semuanya datang dari
    report_render_logic.metrik_judul_dashboard supaya sisi PDF & PPT memakai angka yang SAMA.

    Judul yang tidak muat DIKECILKAN ukurannya, tidak dipotong (batasan user: tidak ada teks
    yang boleh terpotong). Versi sebelumnya memakai _hard_truncate di sini."""
    # SATU SUMBER (report_render_logic.metrik_judul_dashboard): lebar teks, ukuran font dan
    # tinggi kotak dihitung di tempat yang SAMA dgn sisi PDF. Sebelumnya fungsi ini memakai
    # font 28pt, zona logo 2.9in, faktor lebar 0.6 ("estimasi kasar" menurut docstring-nya
    # sendiri) dan _hard_truncate - hasilnya 1.072in untuk judul yang sisi PDF hitung 0.844in,
    # dan selisih itu membuat kedua format menggambar jumlah entitas chart yang BERBEDA.
    # _hard_truncate DIHAPUS dari jalur ini: teks tidak boleh terpotong (batasan user), yang
    # dikecilkan ukuran fontnya - persis aturan yang sudah dipakai sisi PDF.
    _mj = metrik_judul_dashboard(text, w_in, size_pt)
    text_w_in = _mj["text_w_in"]
    size_pt = _mj["size_pt"]
    box_h_in = _mj["tinggi_in"]
    fit_text = text
    box = slide.shapes.add_textbox(Inches(x_in), Inches(0), Inches(text_w_in), Inches(box_h_in))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    p.text = fit_text
    _set_font(p, TITLE_FONT, Pt(size_pt), bold=True, color=color)
    return box_h_in


def _draw_fact_strip(slide, x_in: float, y_in: float, w_in: float, fact_strip: list, theme: dict | None = None) -> None:
    """B: "strip fakta" — 1 baris berisi 2 angka {(label, value)} dipisah "|"."""
    if not fact_strip:
        return
    t = theme or THEME_PALETTES["green"]
    box = slide.shapes.add_textbox(Inches(x_in), Inches(y_in), Inches(w_in), Inches(_DASH_FACT_STRIP_H_IN))
    tf = box.text_frame
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    for i, (label, value) in enumerate(fact_strip):
        if i > 0:
            sep = p.add_run()
            sep.text = "   |   "
            _set_font(sep, BODY_FONT, Pt(10), color=PANEL_BORDER)
        val_run = p.add_run()
        val_run.text = f"{value} "
        _set_font(val_run, BODY_FONT, Pt(14), bold=True, color=t["main"])
        lbl_run = p.add_run()
        lbl_run.text = label
        _set_font(lbl_run, BODY_FONT, Pt(9), color=GRAY_TEXT)


def _draw_fact_pair(slide, x_in: float, y_in: float, w_in: float, fact_pair: list, theme: dict | None = None) -> None:
    """B: "kotak fakta berpasangan" — 2 kotak berdampingan, label kecil miring di atas +
    nilai tebal besar di bawah (BUKAN judul berwarna, permintaan user eksplisit)."""
    if not fact_pair:
        return
    t = theme or THEME_PALETTES["green"]
    gap_in = 0.12
    box_w_in = (w_in - gap_in) / 2
    h_in = _DASH_FACT_PAIR_H_IN
    for i, (label, value) in enumerate(fact_pair[:2]):
        bx_in = x_in + i * (box_w_in + gap_in)
        card = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(bx_in), Inches(y_in), Inches(box_w_in), Inches(h_in))
        card.fill.solid()
        card.fill.fore_color.rgb = IVORY
        card.line.color.rgb = PANEL_BORDER
        card.line.width = Pt(0.75)
        _no_shadow(card)
        lbl_box = slide.shapes.add_textbox(Inches(bx_in + 0.12), Inches(y_in + 0.08), Inches(box_w_in - 0.24), Inches(0.22))
        lp = lbl_box.text_frame.paragraphs[0]
        lp.alignment = PP_ALIGN.LEFT
        lp.text = label
        _set_font(lp, BODY_FONT, Pt(8.5), italic=True, color=GRAY_TEXT)
        val_box = slide.shapes.add_textbox(Inches(bx_in + 0.12), Inches(y_in + 0.3), Inches(box_w_in - 0.24), Inches(h_in - 0.36))
        vtf = val_box.text_frame
        vtf.word_wrap = True
        vp = vtf.paragraphs[0]
        vp.alignment = PP_ALIGN.LEFT
        vp.text = value
        _set_font(vp, TITLE_FONT, Pt(16), bold=True, color=t["main"])


def _draw_dashboard_main_visual(slide, tile: dict, ctx: "_PptBlockContext", x_in: float, y_in: float, w_in: float, h_in: float) -> None:
    """Visual utama 1 kolom dashboard Management — dispatch tile_kind PERSIS SAMA dgn
    sebelumnya (diekstrak dari _build_management_visual_dashboard_slide lama tanpa mengubah
    cabangnya sama sekali, cuma parameter posisi/ukurannya sekarang dioper langsung sbg x/y/w/h
    drpd dihitung dari sel grid kartu — lihat _build_management_visual_dashboard_slide baru).
    `compact` grid lama (2+ baris tile kecil) TIDAK ada lagi relevansinya di layout kolom ini
    (tiap kolom sekarang py ruang jauh lebih lapang, 2.5-2.9in+ drpd sel grid lama) — dipanggil
    always compact=False."""
    compact = False
    chart_x, chart_y = Inches(x_in), Inches(y_in)
    chart_w, chart_h = Inches(w_in), Inches(h_in)
    kind = tile["tile_kind"]
    if kind == "risk_heatmap":
        bars = tile.get("bars", [])[:5]
        is_severity = tile.get("mode") == "severity"
        if is_severity:
            color_map = {"red": RED_CRIT, "orange": RGBColor(0xEA, 0x58, 0x0C), "amber": GOLD_MAIN, "blue": RGBColor(0x25, 0x63, 0xEB), "gray": GRAY_TEXT}
        else:
            color_map = {"blue": ctx.accent_main, "green": ctx.accent_chart, "amber": _light_safe(ctx.accent_light), "orange": _light_safe(ctx.accent_soft), "gray": GRAY_TEXT, "red": ctx.accent_main}
        colors = [color_map.get(b.get("color", "gray"), ctx.accent_main) for b in bars]
        labels = [b["label"] for b in bars]
        values = [b["count"] for b in bars]
        # Bentuk visual ikut category_style/status_style SAMA dgn laporan gaya SOC (mirror
        # export_pdf.py::_mgmt_tile_chart_html) — BUG YANG DIPERBAIKI (dilaporkan user,
        # "itu-itu aja"): tile ini dulu SELALU batang polos apa pun kombinasi tampilan yang
        # terkunci utk laporan ini.
        style = tile.get("chart_style") or (ctx.status_style if is_severity else ctx.category_style)
        if style == "donut":
            # BUG DIPERBAIKI (dilaporkan user): ukuran donut sebelumnya dihitung dari
            # rasio TETAP (0.62x tinggi kotak chart) TANPA tahu legend di bawahnya bakal
            # makan berapa baris — legend panjang bisa nembus keluar kartu. Sekarang
            # tinggi legend dihitung LEBIH DULU (mini_legend_height_needed_in), donut
            # baru diberi SISA ruang yang benar2 tersedia setelahnya.
            d_labels, d_values, d_colors = (
                _merge_tail_into_other(labels, values, colors) if compact else (labels, values, colors)
            )
            legend_gap_in = 0.05
            legend_h_in = mini_legend_height_needed_in(d_labels, chart_w, compact) + legend_gap_in
            side = min(Emu(chart_w).inches, max(0.35, Emu(chart_h).inches - legend_h_in))
            side_x = chart_x + Inches((Emu(chart_w).inches - side) / 2)
            add_native_doughnut_chart(
                slide, side_x, chart_y, Inches(side), Inches(side), d_labels, d_values, colors=d_colors,
                theme=ctx.theme, show_data_labels=False, show_center_total=True,
            )
            _add_mini_legend(slide, chart_x, chart_y + Inches(side) + Inches(legend_gap_in), chart_w, d_labels, d_colors, compact=compact)
        elif style == "stacked":
            bar_h = Inches(0.28)
            add_stacked_proportion_bar(slide, chart_x, chart_y, chart_w, values, colors=colors, height=bar_h, labels=labels)
        elif style == "funnel" and is_severity:
            order = sorted(range(len(values)), key=lambda i: -values[i])
            add_funnel_chart(slide, chart_x, chart_y, chart_w, chart_h, [labels[i] for i in order], [values[i] for i in order], color=ctx.accent_main)
        elif style == "treemap":
            add_treemap_shapes(slide, chart_x, chart_y, chart_w, chart_h, labels, values, colors=colors)
        else:
            add_native_bar_chart(slide, chart_x, chart_y, chart_w, chart_h, labels, values, colors=colors, horizontal=True)
    elif kind == "kpi_radar":
        add_native_radar_chart(slide, chart_x, chart_y, chart_w, chart_h, tile["axes"], tile["values"], color=ctx.accent_main)
    elif kind == "status_funnel":
        add_funnel_chart(slide, chart_x, chart_y, chart_w, chart_h, tile["categories"], tile["values"], color=ctx.accent_main)
    elif kind == "period_compare":
        # color_b sengaja pakai accent_chart (BUKAN accent_light) — utk tema "gold"
        # khususnya, accent_main (bronze) & accent_light (krem sangat pucat) kontrasnya
        # rendah kalau berdampingan sbg 2 seri batang.
        add_grouped_bar_chart(
            slide, chart_x, chart_y, chart_w, chart_h,
            tile["categories"], tile["series_a"], tile["series_b"],
            label_a=tile["label_a"], label_b=tile["label_b"],
            color_a=ctx.accent_main, color_b=ctx.accent_chart,
        )
    elif kind == "time_heatmap":
        add_heatmap_grid(slide, chart_x, chart_y, chart_w, chart_h, tile["day_labels"], tile["hour_labels"], tile["grid"], color=ctx.accent_main)
    elif kind == "trend_chart":
        chart = tile["chart"]
        if chart["type"] == "bar_line":
            add_bar_line_chart(slide, chart_x, chart_y, chart_w, chart_h, chart["categories"], chart["values"], chart.get("cumulative"), color=ctx.accent_main)
        else:
            # BUG DIPERBAIKI (drift vs export_pdf.py::_mgmt_tile_chart_html): cabang
            # fallback trend_chart di PDF pakai _bar_chart_html (batang HORIZONTAL,
            # nama kategori di kiri) — versi PPT ini sebelumnya batang VERTIKAL polos
            # (horizontal default False), beda bentuk tampilan utk data yang sama persis.
            add_native_bar_chart(slide, chart_x, chart_y, chart_w, chart_h, chart["categories"], chart["values"], colors=[ctx.accent_main], horizontal=True)
    elif kind == "custom_topic":
        # PERMINTAAN USER (Management Report "harus lebih banyak visualisasi"): section
        # custom tulisan AI yang punya data perbandingan kategori digambar sbg chart
        # sungguhan di sini (mirror export_pdf.py::_mgmt_tile_chart_html), bentuknya
        # gantian bar/donat/susun per tile (lihat "chart_style" dari
        # build_management_report_blocks) spy tidak seragam semua.
        ct_labels, ct_values = tile.get("labels", []), tile.get("values", [])
        ct_ramp = [ctx.accent_main, ctx.accent_chart, _light_safe(ctx.accent_light), _light_safe(ctx.accent_soft), GRAY_TEXT, ctx.accent_main]
        ct_colors = [ct_ramp[i % len(ct_ramp)] for i in range(len(ct_values))]
        ct_style = tile.get("chart_style", "bar")
        if ct_style == "donut":
            ct_d_labels, ct_d_values, ct_d_colors = (
                _merge_tail_into_other(ct_labels, ct_values, ct_colors) if compact else (ct_labels, ct_values, ct_colors)
            )
            legend_gap_in = 0.05
            legend_h_in = mini_legend_height_needed_in(ct_d_labels, chart_w, compact) + legend_gap_in
            side = min(Emu(chart_w).inches, max(0.35, Emu(chart_h).inches - legend_h_in))
            side_x = chart_x + Inches((Emu(chart_w).inches - side) / 2)
            add_native_doughnut_chart(
                slide, side_x, chart_y, Inches(side), Inches(side), ct_d_labels, ct_d_values, colors=ct_d_colors,
                theme=ctx.theme, show_data_labels=False, show_center_total=True,
            )
            _add_mini_legend(slide, chart_x, chart_y + Inches(side) + Inches(legend_gap_in), chart_w, ct_d_labels, ct_d_colors, compact=compact)
        elif ct_style == "stacked":
            bar_h = Inches(0.28)
            add_stacked_proportion_bar(slide, chart_x, chart_y, chart_w, ct_values, colors=ct_colors, height=bar_h, labels=ct_labels)
        elif ct_style == "treemap":
            add_treemap_shapes(slide, chart_x, chart_y, chart_w, chart_h, ct_labels, ct_values, colors=ct_colors)
        else:
            add_native_bar_chart(slide, chart_x, chart_y, chart_w, chart_h, ct_labels, ct_values, colors=ct_colors, horizontal=True)
    elif kind == "kpi_gauge":
        # PERMINTAAN USER (tambah jenis visualisasi baru): mirror export_pdf.py's _gauge_svg
        # — add_native_gauge SUDAH ADA sebelumnya (dipakai key_findings), dipakai ulang di
        # sini tanpa perlu bikin fungsi baru lagi.
        gauge_side = min(Emu(chart_w).inches, Emu(chart_h).inches)
        gauge_x = chart_x + Inches((Emu(chart_w).inches - gauge_side) / 2)
        add_native_gauge(slide, gauge_x, chart_y, Inches(gauge_side), Inches(gauge_side * 0.75), tile["pct"], color=ctx.accent_main, theme=ctx.theme)
    elif kind == "scatter_bubble":
        # PERMINTAAN USER (tambah jenis visualisasi baru): mirror export_pdf.py's
        # _scatter_bubble_svg — 2 angka BERBEDA per entitas via chart BUBBLE native.
        add_native_bubble_chart(slide, chart_x, chart_y, chart_w, chart_h, tile["points"], color=ctx.accent_main)


def _rapatkan_margin(tf, kiri: float = 0.0, kanan: float = 0.0,
                     atas: float | None = None, bawah: float | None = None):
    """Nolkan margin dalam kotak teks, lalu kembalikan lebar yang HILANG karenanya (inci).

    CACAT NYATA YANG DIPERBAIKI (terlihat di ekspor PowerPoint, tidak terlihat dari
    python-pptx): tiap kotak teks python-pptx lahir dengan margin 0,1in di kiri DAN kanan -
    0,2in, setara 14,4pt. Rumus pengepasan font di sini menghitung ruang dari LEBAR KOTAK,
    jadi ia mengira punya 0,2in lebih banyak dari yang sebenarnya ada. Di kartu KPI selebar
    ~0,85in itu bukan selisih kecil: ruang yang diklaim 38pt nyatanya 24pt, dan "26.068"
    pecah jadi "26.0" / "68". Angka yang terbelah terbaca sebagai angka lain - kelas
    kesalahan yang sama seperti angka terpotong.
    Dinolkan, BUKAN dikurangkan dari rumus: kartu ini sudah punya inset sendiri (0,16in tiap
    sisi) dan margin kedua di atasnya cuma menyempitkan tanpa menambah apa pun."""
    hilang = tf.margin_left.inches + tf.margin_right.inches
    tf.margin_left = Inches(kiri)
    tf.margin_right = Inches(kanan)
    if atas is not None:
        tf.margin_top = Inches(atas)
    if bawah is not None:
        tf.margin_bottom = Inches(bawah)
    return hilang - (kiri + kanan)


def _insight_kpi_row(slide, cards: list, x_in: float, total_w_in: float, h_in: float, y_in: float, theme: dict | None = None) -> None:
    """Lapis ringkasan KPI (permintaan user poin 2/6): kartu lebar TAK SAMA (dari isi
    masing2, lihat _kpi_card_widths), label kecil kapital berspasi + nilai besar tebal
    (BUKAN berwarna — "biarkan angkanya yang menonjol")."""
    if not cards:
        return
    gap_in = 0.1
    widths = _kpi_card_widths(cards, total_w_in, gap_in)
    x = x_in
    for card, w in zip(cards, widths):
        box = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y_in), Inches(w), Inches(h_in))
        box.fill.solid()
        box.fill.fore_color.rgb = IVORY
        box.line.color.rgb = PANEL_BORDER
        box.line.width = Pt(0.75)
        _no_shadow(box)
        lbl_box = slide.shapes.add_textbox(Inches(x + 0.16), Inches(y_in + 0.13), Inches(w - 0.32), Inches(0.2))
        _rapatkan_margin(lbl_box.text_frame, atas=0.0, bawah=0.0)
        lp = lbl_box.text_frame.paragraphs[0]
        lp.alignment = PP_ALIGN.LEFT
        lp.text = card["label"]
        _set_font(lp, BODY_FONT, Pt(8), bold=True, color=GRAY_TEXT)
        val_box = slide.shapes.add_textbox(Inches(x + 0.16), Inches(y_in + 0.4), Inches(w - 0.32), Inches(max(0.3, h_in - 0.5)))
        vtf = val_box.text_frame
        _rapatkan_margin(vtf, atas=0.0, bawah=0.0)
        vtf.word_wrap = True
        vp = vtf.paragraphs[0]
        vp.alignment = PP_ALIGN.LEFT
        vp.text = card["value"]
        # Kembar dari _insight_kpi_row_html di export_pdf.py: nilai panjang di kartu sempit
        # dulu tetap 20pt & membungkus keluar kartu. Ukuran mengikuti panjang teks thd lebar.
        _val = str(card["value"])
        _avail_pt = max(1.0, (w - 0.32) * 72.0)
        # faktor 0.56 -> 0.62: terukur dari render, 0.56 masih membiarkan nilai spt
        # "Requests (50%)" membungkus ke baris kedua & TERPOTONG tepi bawah kartu
        # (kasus yang persis dicontohkan user: "(85%)" jatuh di luar rect kartu).
        # PLAFON diturunkan 20pt -> _KPI_VALUE_MAX_PT (15pt), kembaran export_pdf.py:
        # kartu KPI elemen SEKUNDER. Lihat catatan di konstanta (report_render_logic.py).
        # Kembaran export_pdf.py: ukuran dibatasi oleh TOKEN TERPANJANG, bukan panjang
        # seluruh teks - pembungkusan tidak bisa memecah "311221140243,0", jadi rumus yang
        # memakai len(teks) penuh memberi ukuran yang terlalu besar & nilainya meluber keluar
        # kartu. Batas bawah 7pt (bukan 9,5) supaya angka panjang tetap tergambar UTUH:
        # angka yang terpotong terbaca sebagai angka lain yang masuk akal, dan itu jauh lebih
        # berbahaya daripada angka yang kecil.
        # DUA syarat, bukan satu - kembaran persis _insight_kpi_row_html di export_pdf.py.
        # Rumus satu-baris sebelumnya hanya menjamin token TERPANJANG muat lebarnya, jadi
        # nilai yang punya titik pecah ("Tender Terbuka (21,2%)") tetap dapat 15pt, lalu
        # membungkus jadi 3 baris dan tumpah KELUAR kartu ke panel di bawahnya (terlihat di
        # ekspor PowerPoint v19). Yang kurang: jumlah baris hasil wrap SUNGGUHAN harus muat
        # di tinggi sisa kartu. Sisi PDF sudah begini sejak lama; sisi PPT ketinggalan.
        _h_isi_pt = max(10.0, max(0.3, h_in - 0.5) * 72.0 - 4.0)
        _w_isi_px = max(24.0, _avail_pt / 72.0 * 96.0)
        _size_pt = _KPI_VALUE_MAX_PT
        if _val:
            _token_pt = max((len(_t) for _t in _val.split()), default=len(_val)) * 0.62
            for _p_kpi in (15.0, 14.0, 13.0, 12.0, 11.0, 10.0, 9.5, 9.0, 8.0, 7.0):
                _size_pt = _p_kpi
                _muat_tinggi = (wrap_line_count(_val, _w_isi_px, _p_kpi, 0.62)
                                * _p_kpi * 1.15) <= _h_isi_pt
                _muat_lebar = _token_pt * _p_kpi <= _avail_pt
                if _muat_tinggi and _muat_lebar:
                    break
            _size_pt = min(_KPI_VALUE_MAX_PT, _size_pt)
        _set_font(vp, TITLE_FONT, Pt(_size_pt), bold=True, color=TEXT_DARK)
        x += w + gap_in


# PER ENGINE (permintaan user): angka ini DISAMAKAN dgn sisi PDF utk sementara krn belum
# ada pecahan baris nyata dari PPT utk dikalibrasi. Kalau tes tumpang tindih menemukan
# tabrakan yang HANYA muncul di PPT, angka inilah yang pertama harus diperiksa - jangan
# diasumsikan sama selamanya.
_NAMA_KARTU_FAKTOR_LEBAR = 0.80


def _muat_nama_kartu(nama: str, w_in: float, maks_baris: int = 2):
    """(ukuran font pt, jumlah baris SEBENARNYA) - nama tidak pernah dipotong.

    ITEM 3 (permintaan user): jumlah baris kini DIHITUNG lewat wrap_line_count - simulasi
    pembungkusan dgn titik pecah yang sungguhan dipakai perender (spasi, "/", "-", dan "."
    bila diikuti huruf) - BUKAN diperkirakan dari len(nama)/kapasitas. Perkiraan lama
    mengasumsikan baris terisi penuh; nyatanya "/Common/vs.ams.petrokimia-gresik.com" jadi
    TIGA baris, lalu skor & sub-item kartu tertabrak (terukur di laporan 187).

    FAKTOR LEBAR _NAMA_KARTU_FAKTOR_LEBAR DIKALIBRASI dari render sungguhan: pada kotak 173px/9pt, baris
    terpanjang yang benar-benar dihasilkan perender berisi 18 karakter - faktor 0.80 yang
    menghasilkan kapasitas itu (0.55 menghasilkan 26, meleset jauh & itu sumber cacatnya)."""
    if not nama:
        return 9.0, 1
    lebar_px = max(20.0, w_in * 96 - 27)
    for pt in (9.0, 8.0, 7.0, 6.5):
        baris = wrap_line_count(nama, lebar_px, pt, _NAMA_KARTU_FAKTOR_LEBAR)
        if baris <= maks_baris:
            return pt, baris
    return 6.5, wrap_line_count(nama, lebar_px, 6.5, _NAMA_KARTU_FAKTOR_LEBAR)


def _nested_category_card(slide, card: dict, x_in: float, y_in: float, w_in: float, h_in: float, theme: dict | None = None) -> None:
    """Kartu bersarang 1 kategori (permintaan user poin 9): header berwarna (nama + skor
    besar + badge status) + body berisi sub-item pola 2-baris (poin 4: label kiri/nilai
    kanan lalu bar tipis, garis pembanding vertikal di posisi rata-rata — poin 5)."""
    t = theme or THEME_PALETTES["green"]
    # Kembaran _muat_nama_kartu di export_pdf.py - nama SELALU utuh, tidak pernah dipotong.
    _nm_pt, _nm_lines = _muat_nama_kartu(str(card.get("name") or ""), w_in)
    _nm_h_in = _nm_lines * (_nm_pt * 1.15 / 72.0)
    header_h_in = max(min(_NESTED_CARD_HEADER_H_IN, h_in * 0.35),
                      min(_NESTED_CARD_HEADER_MIN_H_IN, h_in),
                      min(h_in, 0.22 + _nm_h_in + 0.30))
    body_h_in = max(0.3, h_in - header_h_in)

    card_shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x_in), Inches(y_in), Inches(w_in), Inches(h_in))
    card_shape.fill.solid()
    card_shape.fill.fore_color.rgb = t["bg"]
    card_shape.line.fill.background()
    _no_shadow(card_shape)

    name_box = slide.shapes.add_textbox(Inches(x_in + 0.12), Inches(y_in + 0.08),
                                        Inches(w_in - 0.24), Inches(max(0.2, _nm_h_in)))
    np_ = name_box.text_frame.paragraphs[0]
    np_.alignment = PP_ALIGN.LEFT
    name_box.text_frame.word_wrap = True
    np_.text = card["name"]
    _set_font(np_, BODY_FONT, Pt(_nm_pt), bold=True, color=WHITE)

    # CACAT NYATA DIPERBAIKI (dilaporkan user: badge menumpuk MENUTUPI sebagian angka):
    # lebar kotak skor dulu dipatok w*0.55 tanpa melihat badge, padahal badge duduk di sudut
    # kanan kartu yang sama. Terukur di kartu selebar 2,2in: kotak skor berakhir di 1,33in
    # sementara badge mulai di 1,18in - bertindih 0,15in, dan nilai yang panjang benar-benar
    # tergambar di bawah kapsulnya. Sekarang lebar kotak skor dihitung MUNDUR dari tepi kiri
    # badge, dan fontnya ikut mengecil kalau angkanya tetap tidak muat.
    _badge_w_prev = (min(0.9, max(0.5, len(str(card.get("badge") or "")) * 0.09 + 0.3))
                     if card.get("badge") else 0.0)
    _skor_w = max(0.6, w_in - 0.12 - (_badge_w_prev + 0.12 + 0.08 if _badge_w_prev else 0.12))
    _skor = str(card["score"])
    _skor_pt = min(16.0, max(9.0, (_skor_w * 72.0) / max(1, len(_skor)) / 0.60))
    score_box = slide.shapes.add_textbox(Inches(x_in + 0.12), Inches(y_in + 0.27), Inches(_skor_w), Inches(0.36))
    _rapatkan_margin(score_box.text_frame, atas=0.0, bawah=0.0)
    score_box.text_frame.word_wrap = False
    sp = score_box.text_frame.paragraphs[0]
    sp.alignment = PP_ALIGN.LEFT
    sp.text = _skor
    _set_font(sp, TITLE_FONT, Pt(_skor_pt), bold=True, color=WHITE)

    # Badge boleh kosong: panel beda-satuan sengaja TIDAK memberi vonis Tinggi/Rendah
    # (lihat "satuan_beragam" di report_render_logic.py). Tanpa penjaga ini yang
    # tergambar adalah kapsul berwarna tanpa teks di sudut kartu.
    if card.get("badge"):
        badge_w_in = min(0.9, max(0.5, len(card["badge"]) * 0.09 + 0.3))
        badge_x_in = x_in + w_in - badge_w_in - 0.12
        badge = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(badge_x_in), Inches(y_in + 0.32), Inches(badge_w_in), Inches(0.22))
        try:
            badge.adjustments[0] = 0.5
        except Exception:
            pass
        badge.fill.solid()
        badge.fill.fore_color.rgb = t["light"]
        badge.line.fill.background()
        _no_shadow(badge)
        btf = badge.text_frame
        btf.margin_left = btf.margin_right = Inches(0.02)
        btf.margin_top = btf.margin_bottom = Inches(0.01)
        bp = btf.paragraphs[0]
        bp.alignment = PP_ALIGN.CENTER
        bp.text = card["badge"]
        _set_font(bp, BODY_FONT, Pt(7.5), bold=True, color=t["bg"])

    # BUG NYATA DIPERBAIKI (permintaan user, koreksi "tidak ada dimensi kedua"): dulu frac/
    # target_frac DIHITUNG ULANG di sini dari `it["value"]` thd max HANYA di antara sub-item
    # kartu INI SENDIRI - valid selama semua sub-item 1 skala sama (severity/status). Sekarang
    # sub-item bisa berasal dari kolom numerik BERBEDA skalanya (lihat _compute_multi_metric_
    # items, report_render_logic.py) - frac/target_frac WAJIB sudah dihitung PER METRIK di
    # lapisan data (thd rentang metrik itu di SEMUA entitas) & dipakai APA ADANYA, bukan
    # diturunkan ulang dari "value" (salah total kalau skalanya beda antar sub-item).
    sub_items = card.get("sub_items") or []
    item_h_in = _NESTED_CARD_SUBITEM_LINE1_H_IN + _NESTED_CARD_SUBITEM_BAR_H_IN + _NESTED_CARD_SUBITEM_GAP_IN
    # BUG NYATA DIPERBAIKI (sub-item terakhir terlihat TERPOTONG separuh di render):
    # potongan 0.12in tidak sepadan dgn padding body yang sebenarnya (6pt atas +
    # 6pt bawah = 0.167in), jadi kapasitas kelebihan hitung ~1 sub-item & baris
    # terakhir digambar melewati tepi bawah kartu.
    max_items = max(0, int((body_h_in - 0.17) / item_h_in)) if item_h_in else 0
    shown = sub_items[:max_items]
    body_x_in = x_in + 0.12
    body_w_in = w_in - 0.24
    cur_y_in = y_in + header_h_in + 0.06
    for it in shown:
        frac = max(0.0, min(1.0, it["frac"]))
        target_frac = it.get("target_frac")
        lbl_box = slide.shapes.add_textbox(Inches(body_x_in), Inches(cur_y_in), Inches(body_w_in * 0.65), Inches(_NESTED_CARD_SUBITEM_LINE1_H_IN))
        lp = lbl_box.text_frame.paragraphs[0]
        lp.alignment = PP_ALIGN.LEFT
        lp.text = it["label"]
        _set_font(lp, BODY_FONT, Pt(9), color=WHITE)
        val_box = slide.shapes.add_textbox(Inches(body_x_in + body_w_in * 0.65), Inches(cur_y_in), Inches(body_w_in * 0.35), Inches(_NESTED_CARD_SUBITEM_LINE1_H_IN))
        vp = val_box.text_frame.paragraphs[0]
        vp.alignment = PP_ALIGN.RIGHT
        vp.text = _fmt_num(it["value"])
        _set_font(vp, BODY_FONT, Pt(9), bold=True, color=WHITE)
        bar_y_in = cur_y_in + _NESTED_CARD_SUBITEM_LINE1_H_IN + 0.02
        track = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(body_x_in), Inches(bar_y_in), Inches(body_w_in), Inches(_NESTED_CARD_SUBITEM_BAR_H_IN))
        track.fill.solid()
        track.fill.fore_color.rgb = _blend_with_white(t["bg"], 0.35)
        track.line.fill.background()
        _no_shadow(track)
        fill_w_in = max(body_w_in * frac, 0.05)
        fill = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(body_x_in), Inches(bar_y_in), Inches(fill_w_in), Inches(_NESTED_CARD_SUBITEM_BAR_H_IN))
        fill.fill.solid()
        fill.fill.fore_color.rgb = t["light"]
        fill.line.fill.background()
        _no_shadow(fill)
        if target_frac is not None:
            marker_h_in = _NESTED_CARD_SUBITEM_BAR_H_IN * 1.4
            extra_in = (marker_h_in - _NESTED_CARD_SUBITEM_BAR_H_IN) / 2
            marker_x_in = body_x_in + body_w_in * max(0.0, min(1.0, target_frac))
            marker = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(marker_x_in), Inches(bar_y_in - extra_in), Inches(0.012), Inches(marker_h_in))
            marker.fill.solid()
            marker.fill.fore_color.rgb = WHITE
            marker.line.fill.background()
            _no_shadow(marker)
        cur_y_in += item_h_in


def _insight_detail_row(slide, cards: list, x_in: float, total_w_in: float, h_in: float, y_in: float, theme: dict | None = None, notes: list | None = None, is_en: bool = False) -> bool:
    """Lapis detail per kategori (permintaan user poin 9, geometri diukur dari referensi):
    kartu bersarang lebar ~2.24in, jarak nyaris 0, disusun 1 baris (sampai 4) atau 2 baris
    (5-8) lewat _layout_nested_card_grid (report_render_logic.py, SATU sumber dipakai kedua
    exporter). Lebar kartu 2.24in x N nyaris SELALU < lebar slide kita (kanvas referensi yg
    diukur user py kolom foto dokumentasi di sisa lebarnya, kita tidak) - sisa lebar itu diisi
    panel catatan di SISI KANAN (permintaan user eksplisit "jangan dibiarkan kosong"), BUKAN
    kartu diregangkan atau dibiarkan sbg margin kosong. Return True kalau `notes` terpakai
    di panel sisi ini (pemanggil TIDAK boleh menggambarnya lagi di bawah kalau begitu)."""
    if not cards:
        return False
    grid = _layout_nested_card_grid(len(cards), total_w_in)
    rows_n = grid["rows"]
    card_w = grid["card_w"]
    side_panel_w = grid["side_panel_w"]
    gap_in = _NESTED_CARD_GAP_IN
    row_h_in = (h_in - _NESTED_CARD_ROW_GAP_IN * (len(rows_n) - 1)) / len(rows_n) if rows_n else h_in
    idx = 0
    y = y_in
    for row_count in rows_n:
        x = x_in
        for _ in range(row_count):
            # Kembaran perbaikan di export_pdf.py: tiap kartu setinggi ISINYA sendiri.
            _kh = min(row_h_in, tinggi_kartu_in(cards[idx]))
            _nested_category_card(slide, cards[idx], x, y, card_w, _kh, theme=theme)
            x += card_w + gap_in
            idx += 1
        y += row_h_in + _NESTED_CARD_ROW_GAP_IN
    if side_panel_w > 0 and notes:
        note_title = "Notes" if is_en else "Catatan"
        panel_x = x_in + total_w_in - side_panel_w
        add_note_box(slide, Inches(panel_x), Inches(y_in), Inches(side_panel_w), notes, theme=theme, title=note_title)
        return True
    return False


_CHART_SIDE_PANEL_MIN_W_IN = 2.5
# Ambang bingkai area chart - HARUS sama dgn _CHART_FRAME_MIN_FILL di export_pdf.py,
# kalau berbeda satu format dapat bingkai & satunya tidak untuk chart yang sama.
_CHART_FRAME_MIN_FILL = 0.70


def _hex_tema(nilai) -> str:
    """RGBColor/str -> "#RRGGBB". Aturan warna pita tinggal di report_render_logic.py yang
    bekerja dgn hex (dipakai bersama sisi PDF); ini cuma jembatan tipe, bukan keputusan warna."""
    if isinstance(nilai, str):
        return nilai if nilai.startswith("#") else "#" + nilai
    return "#%02X%02X%02X" % (nilai[0], nilai[1], nilai[2])


def _as_rgb(nilai, cadangan):
    """Terima RGBColor / string heks ("#4A7C59" atau "4A7C59") -> RGBColor.

    Data tile dibentuk utk sisi PDF (CSS, string heks). python-pptx menolak string mentah
    (ValueError: assigned value must be type RGBColor), jadi tanpa konversi ini seluruh
    laporan gagal digenerate begitu tile ber-warna dipakai di PPT."""
    if isinstance(nilai, RGBColor):
        return nilai
    if isinstance(nilai, str):
        s = nilai.strip().lstrip("#")
        if len(s) == 6:
            try:
                return RGBColor.from_string(s.upper())
            except ValueError:
                pass
    return cadangan


def _label_satu_baris(x) -> str:
    """Ratakan pemisah baris di dalam satu label jadi spasi.

    Lihat scratchpad/patch_label_baris: HTML sudah meratakannya sendiri, PowerPoint tidak -
    jadi tanpa ini label yang sama tampil satu baris di PDF dan dua baris di PPTX."""
    return " ".join(str(x if x is not None else "").split())


def _kat_bar(tile: dict) -> list:
    """Daftar kategori yang akan jadi label sumbu - satu tempat, supaya penghitung ukuran
    font tidak bisa memakai jumlah yang berbeda dari yang benar-benar digambar."""
    return ((tile.get("bars") or [])
            or (tile.get("labels") or [])
            or ((tile.get("chart") or {}).get("categories") or []))


def _pt_label_bar(tinggi_in: float, n_kat: int) -> float:
    """Ukuran font label sumbu yang muat di pita per kategori.

    Tinggi plot dibagi jumlah kategori = tinggi pita; label butuh ~1,35x ukuran fontnya
    (tinggi baris + napas). Dibatasi 6-11pt: 11pt = nilai lama (jangan membesar dari itu),
    6pt = batas masih terbaca saat dicetak."""
    n = max(1, int(n_kat or 1))
    return max(6.0, min(11.0, (float(tinggi_in) * 72.0 / n) / 1.35))


def _insight_main_chart(slide, tile: dict, x_in: float, y_in: float, w_in: float, h_in: float, theme: dict | None = None, notes: list | None = None, is_en: bool = False) -> bool:
    """PERMINTAAN USER ("hapus jalur management_visual_dashboard, semua lewat insight"): tile
    "space-hungry" (kpi_radar/period_compare/time_heatmap, lihat _build_chart_insight_page di
    report_render_logic.py) tidak py daftar entitas utk kartu bersarang - lapis "detail"
    halaman insight-nya diisi CHART NATIVE tile itu sendiri, langsung diskalakan ke box
    w_in/h_in yang tersedia (add_native_radar_chart/add_grouped_bar_chart/add_heatmap_grid
    SUDAH menerima ukuran box scr eksplisit, tidak perlu penyesuaian px spt di PDF).

    BUG NYATA DITEMUKAN (verifikasi visual langsung, versi PDF-nya - lihat catatan sama di
    export_pdf.py::_insight_main_chart_html): kpi_radar BUJURSANGKAR (dibatasi sisi
    TERPENDEK) menyisakan lebar halaman kosong di kiri-kanan kalau cuma ditengahkan di
    halaman lebar. Sisa lebar itu (kalau cukup lapang) SEKARANG diisi panel catatan analitis
    di SISI KANAN, pola sama dgn _insight_detail_row utk kartu bersarang. Return True kalau
    `notes` terpakai di panel ini (pemanggil tidak boleh menggambarnya lagi di bawah)."""
    t = theme or THEME_PALETTES["green"]
    kind = tile["tile_kind"]

    # RAMP KATEGORI DARI TEMA AKTIF (kembaran export_pdf.py::_gambar_chart).
    # CATEGORY_COLOR_RAMP modul-level dievaluasi SAAT IMPORT dari GREEN_MAIN/GOLD_MAIN, jadi
    # chart yang jatuh ke sana tetap hijau-emas walau laporannya bertema navy/teal. Diputar,
    # bukan dipotong, supaya nilai lebih banyak dari 5 tidak meng-index di luar batas.
    # Dilewatkan sbg `colors=`; default None pemanggil lain tidak berubah, jadi jalur
    # Descriptive tetap memakai CATEGORY_COLOR_RAMP persis seperti sebelumnya.
    def _ramp_tema(n: int) -> list:
        _b = [t["main"], t["chart"], t["light"], t["soft"], GRAY_TEXT]
        return [_b[i % len(_b)] for i in range(max(1, n))]

    margin_in = 0.15
    # CACAT NYATA DIPERBAIKI (terukur, bukan dugaan): lantai `max(1.0, ...)` dulu berlaku utk
    # TINGGI juga. Begitu perencana menjatah kurang dari 1,0in + margin - lazim untuk tile
    # KEDUA di kolom bertumpuk - chart tetap digambar 1,0in dan MENEMBUS slotnya, lalu
    # tertimpa kotak Catatan sehingga terlihat terpotong. Di v21 slide 3: Catatan mulai
    # y=5,73in sementara dua chart berakhir 6,02in & 5,84in, dua-duanya tinggi TEPAT 1,00in.
    #
    # Lebar tetap berlantai 1,0in (kolom selalu jauh lebih lebar dari itu, jadi lantainya
    # cuma penjaga nilai degenerate). Tinggi TIDAK boleh melewati jatah: kontraknya milik
    # perencana, yang sudah punya ambang keterbacaan sendiri (chart_min_height_in). Lantai
    # 0,25in disisakan semata-mata supaya tidak pernah ada shape nol/negatif di PPTX.
    # Kalau jatahnya genuinely terlalu kecil, itu dicatat - bukan ditutupi dgn melewati slot.
    cx_in = max(1.0, w_in - 2 * margin_in)
    cy_in = max(0.25, h_in - 2 * margin_in)
    if h_in - 2 * margin_in < 1.0:
        logger.info("tinggi chart %s dijatah %.2fin (area gambar %.2fin) - di bawah 1,0in, "
                    "digambar sesuai jatah supaya tidak menembus kotak catatan",
                    tile.get("tile_kind"), h_in, cy_in)
    chart_w_in = cx_in
    if kind == "kpi_radar":
        chart_w_in = min(cx_in, cy_in)
    side_panel_w = w_in - chart_w_in - 2 * margin_in - 0.15
    notes_consumed = False
    note_title = "Notes" if is_en else "Catatan"
    if side_panel_w >= _CHART_SIDE_PANEL_MIN_W_IN and notes:
        panel_x = x_in + chart_w_in + 2 * margin_in
        add_note_box(slide, Inches(panel_x), Inches(y_in), Inches(side_panel_w), notes, theme=t, title=note_title)
        notes_consumed = True
    elif notes:
        # Panel samping TIDAK MUAT (utk heatmap/period_compare, chart_w_in = seluruh lebar
        # kolom, jadi side_panel_w selalu NEGATIF). Dulu di sini catatan dinyatakan "tidak
        # terpakai" & pemanggil menggambarnya di y yang SAMA dgn chart -> saling menimpa,
        # sel heatmap tertutup rapat. Sekarang catatan turun ke BAWAH chart & tinggi chart
        # dikurangi persis sebanyak tinggi catatannya.
        note_h_in = _note_box_height_in(w_in, notes)
        if note_h_in and (h_in - note_h_in - 0.12) >= 1.2:
            cy_in = max(1.0, h_in - note_h_in - 0.12 - 2 * margin_in)
            if kind == "kpi_radar":
                chart_w_in = min(cx_in, cy_in)
            add_note_box(slide, Inches(x_in), Inches(y_in + h_in - note_h_in), Inches(w_in),
                         notes, theme=t, title=note_title)
            notes_consumed = True
    # ---- BINGKAI AREA CHART (permintaan user; kembaran export_pdf.py) ------------------
    # Aturan keputusan SAMA PERSIS dgn sisi PDF supaya kedua format tidak berbeda: bingkai
    # cuma dipasang kalau chart benar-benar MENGISI kotaknya (>= _CHART_FRAME_MIN_FILL dari
    # lebar). kpi_radar BUJURSANGKAR mengecil mengikuti sisi terpendek - di kolom pendek ia
    # cuma mengisi sepertiga lebar, dan membingkainya berarti membingkai ruang kosong.
    # Digambar DULU (sebelum chart) supaya jadi alas, bukan menutupi chart. Kotaknya TIDAK
    # diisi warna & tidak menambah ukuran apa pun - murni garis di batas area yang sudah
    # dipesan, jadi anggaran tinggi kolom tidak berubah sedikit pun.
    # Napas plot-ke-bingkai di sini SUDAH ada lewat `margin_in` (0.15in, chart digambar di
    # x_in+margin_in) - lebih lega dari 0.08in acuan, jadi TIDAK dirapatkan maupun ditambah.
    if chart_w_in >= w_in * _CHART_FRAME_MIN_FILL:
        _bk = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x_in), Inches(y_in),
                                     Inches(w_in), Inches(h_in))
        _modest_corner(_bk)
        _bk.fill.background()
        _bk.line.color.rgb = PANEL_BORDER
        _bk.line.width = Pt(0.75)
        _no_shadow(_bk)
    x0_in, y0_in = x_in + margin_in, y_in + margin_in
    # DASAR SLOT: tidak ada elemen chart yang boleh digambar melewati garis ini. Dihitung dari
    # y_in + h_in (jatah yang diberikan pemanggil), BUKAN dari cy_in yang punya lantai sendiri
    # - lantai itulah yang membuat batang bertumpuk tetap 0,44in walau slotnya lebih pendek,
    # lalu menembus kotak Catatan (terukur 0,32in pada data berkolom kategorikal 2 nilai).
    _dasar_slot_in = y_in + max(0.0, h_in)
    if kind == "kpi_radar":
        add_native_radar_chart(
            slide, Inches(x0_in), Inches(y0_in), Inches(chart_w_in), Inches(chart_w_in),
            tile["axes"], tile["values"], color=t["main"],
        )
    elif kind == "period_compare":
        add_grouped_bar_chart(
            slide, Inches(x0_in), Inches(y0_in), Inches(cx_in), Inches(cy_in),
            tile["categories"], tile["series_a"], tile["series_b"],
            label_a=tile["label_a"], label_b=tile["label_b"], color_a=t["main"], color_b=t["chart"],
        )
    elif kind == "time_heatmap":
        # Label diratakan jadi satu baris - lihat _label_satu_baris. Tanpa ini nilai data yang
        # membawa pemisah baris sendiri tampil 2 baris di PPTX padahal 1 baris di PDF.
        add_heatmap_grid(
            slide, Inches(x0_in), Inches(y0_in), Inches(cx_in), Inches(cy_in),
            [_label_satu_baris(v) for v in tile["day_labels"]],
            [_label_satu_baris(v) for v in tile["hour_labels"]],
            tile["grid"], color=t["main"],
        )
    # ---- KEMBARAN PERSIS dari _insight_main_chart_html di export_pdf.py (lihat catatan
    # panjang di sana). Diubah BERSAMAAN dalam satu perubahan: divergensi dua engine sudah
    # dua kali jadi sumber bug di berkas ini. ----
    elif kind == "status_funnel":
        add_funnel_chart(slide, Inches(x0_in), Inches(y0_in), Inches(cx_in), Inches(cy_in),
                         [_label_satu_baris(v) for v in tile["categories"]],
                         tile["values"], color=t["main"])
    elif kind == "kpi_gauge":
        _g = min(cx_in, cy_in)
        add_native_gauge(slide, Inches(x0_in), Inches(y0_in), Inches(_g), Inches(_g),
                         tile.get("pct") or 0, max_value=100,
                         label=tile.get("gauge_dim") or "", color=t["main"], theme=t)
    elif kind == "scatter_bubble":
        add_native_bubble_chart(slide, Inches(x0_in), Inches(y0_in), Inches(cx_in), Inches(cy_in),
                                tile["points"], color=t["main"])
    elif kind == "trend_chart":
        _c = tile.get("chart") or {}
        if _c.get("type") == "bar_line" or _c.get("cumulative"):
            add_bar_line_chart(slide, Inches(x0_in), Inches(y0_in), Inches(cx_in), Inches(cy_in),
                               _c.get("categories") or [], _c.get("values") or [],
                               _c.get("cumulative"), color=t["main"])
        else:
            # tanpa dimensi waktu -> ranked bar horizontal, kembaran _bar_chart_html di PDF
            add_native_bar_chart(slide, Inches(x0_in), Inches(y0_in), Inches(cx_in), Inches(cy_in),
                                 _c.get("categories") or [], _c.get("values") or [],
                                 colors=[t["main"]] * len(_c.get("values") or []),
                                 horizontal=True,
                                 label_pt=_pt_label_bar(cy_in, len(_kat_bar(tile))), jangan_lewati_label=True)
    elif kind == "custom_topic":
        _style = (tile.get("chart_style") or "bar").lower()
        _labels, _values = tile.get("labels") or [], tile.get("values") or []
        if _style == "donut":
            # CACAT NYATA DIPERBAIKI (terukur di laporan 195): donat di jalur INI digambar
            # tanpa legend sama sekali, jadi 4 dari 4 nama irisan ("Kantor Pusat", "Gudang
            # Lini I", ...) tidak pernah sampai ke PPTX - pembaca melihat lingkaran berwarna
            # tanpa keterangan apa pun. Cabang donat di _mgmt_tile_chart sudah benar sejak
            # awal; yang ini tertinggal. Aturannya disalin dari sana: ekor digabung dulu
            # (supaya tidak ada irisan yatim tanpa keterangan), tinggi legend dihitung LEBIH
            # DULU, lalu donat diberi SISA ruangnya - bukan sebaliknya.
            _dl, _dv, _dc = _merge_tail_into_other(_labels, _values, _ramp_tema(len(_values)))
            _gap = 0.05
            _lh = mini_legend_height_needed_in(_dl, Inches(cx_in), False) + _gap
            _d = min(cx_in, max(0.35, cy_in - _lh))
            _dx = x0_in + (cx_in - _d) / 2
            add_native_doughnut_chart(slide, Inches(_dx), Inches(y0_in), Inches(_d), Inches(_d),
                                      _dl, _dv, colors=_dc, theme=t)
            _add_mini_legend(slide, Inches(x0_in), Inches(y0_in + _d + _gap), Inches(cx_in),
                             _dl, _dc, compact=False)
        elif _style == "stacked":
            add_stacked_proportion_bar(slide, Inches(x0_in), Inches(y0_in), Inches(cx_in),
                                       _values, labels=_labels,
                                       colors=_ramp_tema(len(_values)),
                                       # Tinggi minimum 0,42in TIDAK boleh melewati slot yang
                                       # tersedia. CACAT NYATA (terukur di data tipis, kolom
                                       # kategorikal 2 nilai): slot chart menyusut jadi 0,12in
                                       # sementara batang tetap digambar 0,44in, menembus
                                       # kotak Catatan tepat 0,32in.
                                       height=Inches(min(max(0.42, min(0.75, cy_in * 0.22)),
                                                         max(0.12, _dasar_slot_in - y0_in - 0.04))),
                                       dasar_in=_dasar_slot_in)
        else:
            add_native_bar_chart(slide, Inches(x0_in), Inches(y0_in), Inches(cx_in), Inches(cy_in),
                                 _labels, _values, colors=[t["main"]] * len(_values),
                                 horizontal=True,
                                 label_pt=_pt_label_bar(cy_in, len(_kat_bar(tile))), jangan_lewati_label=True)
    elif kind == "risk_heatmap":
        _bars = tile.get("bars") or []
        # warna tile datang sbg string heks (dipakai apa adanya di sisi PDF); python-pptx
        # menolak string & butuh RGBColor - dikonversi, bukan dibuang, supaya palet risikonya
        # sama persis di kedua format.
        # kembaran pemetaan warna di export_pdf.py - lihat catatan panjang di sana
        if tile.get("mode") == "severity":
            _cmap = {"red": RED_CRIT, "orange": RGBColor(0xEA, 0x58, 0x0C), "amber": GOLD_MAIN,
                     "blue": RGBColor(0x25, 0x63, 0xEB), "gray": GRAY_TEXT}
        else:
            _cmap = {"blue": t["main"], "green": t["chart"], "amber": t["light"],
                     "orange": t["soft"], "gray": GRAY_TEXT, "red": t["main"]}
        # A7 TIDAK BISA DITERAPKAN DI JALUR INI - alasannya ditulis, bukan didiamkan.
        # Aturan warna label sudah satu (report_render_logic.warna_teks_label) & sisi PDF
        # memakainya. Di sini bar digambar sbg CHART NATIVE PowerPoint: nama entitas muncul
        # sbg label sumbu kategori, dan OOXML cuma menyediakan satu format utk SELURUH label
        # sumbu (chart.category_axis.tick_labels.font) - tidak ada format per-kategori. Yang
        # bisa diwarnai per titik cuma data label (ANGKA), dan angka justru HARUS tetap gelap.
        #
        # Menyetel semua label jadi satu warna akan BERBOHONG: ia menyambungkan tiap nama ke
        # warna yang belum tentu warna batangnya.
        #
        # Jalan keluarnya menggambar bar sbg shape sendiri (spt add_ranked_bar_ternorm) supaya
        # labelnya jadi textbox kita. Itu juga menutup divergensi tata letak yang sudah ada:
        # sisi PDF menaruh label DI ATAS batang (sejak A3/A4), chart native menaruhnya di
        # sumbu kiri. Perubahan itu di luar lingkup A7 dan belum disetujui - dilaporkan ke
        # user sbg keputusan, bukan dikerjakan diam-diam.
        add_native_bar_chart(slide, Inches(x0_in), Inches(y0_in), Inches(cx_in), Inches(cy_in),
                             [b.get("label") for b in _bars], [b.get("count") for b in _bars],
                             colors=[_as_rgb(_cmap.get(b.get("color", "gray")), t["main"]) for b in _bars],
                             horizontal=True,
                             label_pt=_pt_label_bar(cy_in, len(_kat_bar(tile))), jangan_lewati_label=True)
    elif kind == "metric_share":
        # palet DIPUTAR, bukan dipotong - lihat catatan kembarannya di export_pdf.py
        _tv = tile.get("values") or []
        _tbase = [t["main"], t["chart"], t["light"], t["soft"], GRAY_TEXT]
        _tm_h = cy_in - (0.20 if tile.get("catatan_lainnya") else 0.0)
        add_treemap_shapes(slide, Inches(x0_in), Inches(y0_in), Inches(cx_in), Inches(max(0.4, _tm_h)),
                           tile.get("labels") or [], _tv,
                           colors=[_tbase[i % len(_tbase)] for i in range(max(1, len(_tv)))])
        # kembaran keterangan "Lainnya" di export_pdf.py - ruangnya DIPESAN dari tinggi chart
        # (bukan digambar di bawahnya begitu saja), supaya tidak menembus kotak.
        if tile.get("catatan_lainnya"):
            _cb = slide.shapes.add_textbox(Inches(x0_in), Inches(y0_in + _tm_h + 0.02),
                                           Inches(cx_in), Inches(0.18))
            _cp = _cb.text_frame.paragraphs[0]
            _cp.text = tile["catatan_lainnya"]
            _cp.alignment = PP_ALIGN.CENTER
            _set_font(_cp, BODY_FONT, Pt(7), color=GRAY_TEXT)
            # petak warna cocok dgn segmen terakhir - kembaran di export_pdf.py
            _ramp_tm = [_tbase[i % len(_tbase)] for i in range(max(1, len(_tv)))]
            _swp = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, Inches(x0_in + cx_in / 2 - 0.62),
                Inches(y0_in + _tm_h + 0.06), Inches(0.08), Inches(0.08))
            _swp.fill.solid()
            _swp.fill.fore_color.rgb = _as_rgb(_ramp_tm[(len(_tv) - 1) % len(_ramp_tm)], t["main"])
            _swp.line.fill.background()
            _no_shadow(_swp)
    elif kind == "metric_mix":
        # Tinggi minimum 0,44in dibatasi slot yang tersedia - lihat catatan pada batang
        # bertumpuk di cabang custom_topic: tanpa batas ini, slot chart yang menyusut tetap
        # digambar setinggi minimumnya dan menembus kotak Catatan (terukur 0,32in di data
        # dgn kolom kategorikal 2 nilai).
        _mm_h = Inches(min(max(0.44, min(0.8, cy_in * 0.24)),
                       max(0.12, _dasar_slot_in - y0_in - 0.04)))
        _mm_ramp = _ramp_tema(len(tile.get("values") or []))
        add_stacked_proportion_bar(slide, Inches(x0_in), Inches(y0_in), Inches(cx_in),
                                   tile.get("values") or [], labels=tile.get("labels") or [],
                                   colors=_mm_ramp, height=_mm_h, dasar_in=_dasar_slot_in)
        # BUG NYATA DIPERBAIKI (kembaran export_pdf.py): planner sudah menaruh
        # tile["catatan_lainnya"] saat segmen "Lainnya" sendiri terlalu tipis diberi label
        # DI ATAS batang - cabang ini TIDAK PERNAH membacanya, keterangannya dibuang diam2 &
        # label itu hilang tanpa jejak sama sekali. `add_stacked_proportion_bar` TIDAK diberi
        # Petak warna di bawah HARUS warna segmen TERAKHIR yang benar-benar digambar -
        # sekarang batangnya diberi `_mm_ramp` eksplisit, jadi petaknya membaca ramp itu.
        if tile.get("catatan_lainnya"):
            _mm_v = tile.get("values") or []
            _mm_label_h = 0.32 if tile.get("labels") else 0.0
            _mm_bawah = y0_in + _mm_label_h + Emu(_mm_h).inches + 0.03
            _mm_c = _mm_ramp[(len(_mm_v) - 1) % len(_mm_ramp)] if _mm_v else GRAY_TEXT
            _swp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x0_in),
                                          Inches(_mm_bawah + 0.01), Inches(0.08), Inches(0.08))
            _swp.fill.solid(); _swp.fill.fore_color.rgb = _as_rgb(_mm_c, t["main"])
            _swp.line.fill.background(); _no_shadow(_swp)
            _cb = slide.shapes.add_textbox(Inches(x0_in + 0.12), Inches(_mm_bawah),
                                           Inches(max(0.3, cx_in - 0.12)), Inches(0.18))
            _cp = _cb.text_frame.paragraphs[0]
            _cp.text = tile["catatan_lainnya"]
            _set_font(_cp, BODY_FONT, Pt(7), color=GRAY_TEXT)
    elif kind == "metric_compare":
        add_grouped_bar_chart(slide, Inches(x0_in), Inches(y0_in), Inches(cx_in), Inches(cy_in),
                              tile["categories"], tile["series_a"], tile["series_b"],
                              label_a=tile.get("label_a", ""), label_b=tile.get("label_b", ""),
                              color_a=t["main"], color_b=t["chart"])
    elif kind == "ranked_bar_ternormalisasi":
        # kembaran cabang di export_pdf.py. Kaki legenda sudah masuk chart_min_mutlak_in, jadi
        # kalau tile sampai ke sini dia MUAT - peringatannya tidak pernah dipotong.
        add_ranked_bar_ternorm(slide, Inches(x0_in), Inches(y0_in), Inches(cx_in), Inches(cy_in),
                               tile.get("labels") or [], tile.get("values") or [],
                               color=t["main"], is_en=is_en)
    elif kind == "grouped_bar_ternormalisasi":
        add_grouped_bar_ternorm(slide, Inches(x0_in), Inches(y0_in), Inches(cx_in), Inches(cy_in),
                                tile.get("categories") or [], tile.get("series_a") or [],
                                tile.get("series_b") or [], label_a=tile.get("label_a", ""),
                                label_b=tile.get("label_b", ""), color_a=t["main"],
                                color_b=t["chart"], is_en=is_en)
    else:
        # KEPUTUSAN EKSPLISIT, bukan fallback diam - lihat catatan kembarannya di export_pdf.py
        logger.warning("tile_kind %r tidak punya cabang chart di _insight_main_chart - "
                       "chart tidak digambar", kind)
        return notes_consumed
    return notes_consumed


def _build_management_insight_page_slide(block: dict, ctx: _PptBlockContext):
    """PERMINTAAN USER ("Tata letak — ini yang menentukan kepadatan, bukan margin saja"):
    ganti TOTAL slide dashboard grid ("N kolom, tiap kolom 1 topik") jadi "1 slide = 1
    pembahasan mendalam" — lapis fungsi dari atas: judul -> ringkasan KPI (3 kartu lebar
    tak-sama) -> detail per kategori (sampai 4 kartu bersarang) -> catatan. Lapis yang
    datanya kosong dilewati & sisanya diperbesar mengisi slide (lihat _layout_insight_
    layers, report_render_logic.py — SATU sumber dipakai kedua exporter)."""
    slide = ctx.prs.slides.add_slide(ctx.prs.slide_layouts[6])
    add_logo(slide, ctx.logo_path)
    total_w_in = Emu(SLIDE_W).inches - 2 * _DASH_MARGIN_X_IN
    title_bottom_in = add_dashboard_title(slide, block.get("title", ""), _DASH_MARGIN_X_IN, total_w_in)
    avail_h_in = _DASH_CONTENT_BOTTOM_IN - title_bottom_in
    layers = _layout_insight_layers(block, avail_h_in, total_w_in)

    # Gap HANYA ditambahkan DI ANTARA lapis, bukan lagi setelah lapis TERAKHIR ("detail") -
    # lihat catatan bug (halaman kosong di PDF) di export_pdf.py::_build_management_insight_
    # page_block, versi PPT ini diperbaiki sama persis supaya geometrinya tetap identik.
    cur_y_in = title_bottom_in
    notes_consumed = False
    if "kpi" in layers:
        _insight_kpi_row(slide, block["kpi_summary"], _DASH_MARGIN_X_IN, total_w_in, layers["kpi"], cur_y_in, theme=ctx.theme)
        cur_y_in += layers["kpi"]
        if "detail" in layers:
            cur_y_in += layers["gap"]
    if "detail" in layers:
        if block.get("main_chart_tile"):
            notes_consumed = _insight_main_chart(
                slide, block["main_chart_tile"], _DASH_MARGIN_X_IN, cur_y_in, total_w_in, layers["detail"],
                theme=ctx.theme, notes=block.get("notes"), is_en=is_english(ctx.report),
            )
        else:
            notes_consumed = _insight_detail_row(
                slide, block["category_details"], _DASH_MARGIN_X_IN, total_w_in, layers["detail"], cur_y_in,
                theme=ctx.theme, notes=block.get("notes"), is_en=is_english(ctx.report),
            )
        cur_y_in += layers["detail"]
    if block.get("notes") and not notes_consumed:
        note_title = "Notes" if is_english(ctx.report) else "Catatan"
        # Butir DIPOTONG sesuai sisa ruang di bawah lapis isi. Tanpa ini seluruh butir
        # digambar dari cur_y_in apa adanya: terukur di laporan 166 slide 2, lapis isi
        # menghabiskan tinggi sampai batas isi (7,40in) lalu 11 butir catatan digambar dari
        # situ sampai 10,78in - di luar kanvas 7,5in, jadi isinya ada di berkas tapi tidak
        # pernah terlihat pembaca. Kalau satu butir pun tidak muat, kotaknya tidak digambar:
        # kotak kosong yang menjorok keluar lebih buruk drpd tidak ada kotak.
        _sisa_note_in = _DASH_CONTENT_BOTTOM_IN - cur_y_in
        _butir_ins, _tak_muat_ins = muat_catatan(total_w_in, block["notes"], _sisa_note_in)
        if _tak_muat_ins:
            logger.info("catatan halaman insight (PPT): %d dari %d butir tidak muat di sisa "
                        "%.2fin", _tak_muat_ins, len(block["notes"]), _sisa_note_in)
        if _butir_ins:
            add_note_box(slide, Inches(_DASH_MARGIN_X_IN), Inches(cur_y_in), Inches(total_w_in), _butir_ins, theme=ctx.theme, title=note_title)

    return slide


# A1: PANEL MENEMPEL. Di slide acuan keempat panel berbagi tepi persis (x=0.16/2.40/4.64/
# 6.89, masing-masing w=2.24) - nol jarak. Yang membentuk sekat adalah GARIS TEPI #D6DBE3
# yang bersentuhan, bukan ruang kosong. Sebelumnya 0.28in.
_DASH_COLS_GAP_IN = 0.0
# PITA kepala, bukan kotak judul (kembaran export_pdf.py): acuan 0.16in, dipakai 0.20in.
# PITA kepala: LANTAI saja - tinggi sesungguhnya dihitung dari tinggi teks judul +
# _DASH_COLS_TITLE_PAD_IN (0.14in, angka acuan; sebelumnya 0.06in sehingga judul menempel
# tepi atas-bawah pitanya). Kartu KPI: acuan 0.88in (kartu angka besar slide 3, W=2.39
# H=0.88); sebelumnya 0.95in. HARUS sama persis dgn export_pdf.py & report_render_logic.py.
_DASH_COLS_TITLE_H_IN = 0.20
_DASH_COLS_KPI_H_IN = 0.88
# Lebar garis tepi badan panel - HARUS sama dgn export_pdf.py.
_DASH_PANEL_LINE_PT = 0.4


def _build_management_dashboard_columns_slide(block: dict, ctx: _PptBlockContext):
    """Kembaran PPT dari export_pdf.py::_build_management_dashboard_columns_block - beberapa
    topik dikemas jadi KOLOM SEJAJAR di satu slide, memakai ulang helper yang sama persis
    dgn slide insight 1-topik (semuanya sudah menerima x/lebar/tinggi eksplisit)."""
    cols = [c for c in (block.get("columns") or []) if c]
    # kolom yang tile-nya DILEWATI dibuang seluruhnya, sebelum lebar kolom dihitung - supaya
    # sisanya melebar mengisi halaman, bukan menyisakan kolom yatim berisi header + 2 kartu.
    cols = kolom_yang_digambar(cols, 13.333 - 2 * _DASH_MARGIN_X_IN, _DASH_COLS_GAP_IN,
                               _DASH_CONTENT_BOTTOM_IN - _DASH_COLS_TITLE_H_IN
                               - _DASH_COLS_KPI_H_IN - 0.10)
    slide = ctx.prs.slides.add_slide(ctx.prs.slide_layouts[6])
    add_logo(slide, ctx.logo_path)
    total_w_in = 13.333 - 2 * _DASH_MARGIN_X_IN
    title_bottom_in = add_dashboard_title(slide, block.get("title", ""), _DASH_MARGIN_X_IN, total_w_in)
    if not cols:
        return slide
    avail_h_in = _DASH_CONTENT_BOTTOM_IN - title_bottom_in
    is_en = is_english(ctx.report)
    note_title = "Notes" if is_en else "Catatan"
    _y_terendah = 0.0
    # A5 (kembaran export_pdf.py): ruang kotak catatan DIPESAN LEBIH DULU, bukan dicari dari
    # sisa - kolom yang diberi seluruh tinggi menyisakan nol ruang & kotaknya tak pernah ada.
    # Lebar kolom dihitung SEBELUM blok catatan: batas atas kotak catatan diturunkan
    # dari tinggi minimum chart, dan tinggi minimum itu bergantung lebar kolom.
    # PENUMPUKAN TILE (kembaran export_pdf.py): `bentuk_kolom` menyebut berapa seksi yang
    # ditumpuk di tiap kolom visual. `cols` tetap datar; slot vertikalnya dihitung di bawah.
    _bentuk = list(block.get("bentuk_kolom") or [])
    if sum(_bentuk) != len(cols):
        _bentuk = [1] * len(cols)
    n = max(1, len(_bentuk))
    col_w = (total_w_in - _DASH_COLS_GAP_IN * (n - 1)) / n
    # Kembaran export_pdf.py: LEBAR ISI vs LEBAR PANEL. Panel (badan + pita kepalanya)
    # tetap selebar col_w & berbagi tepi dgn panel sebelahnya (A1); seluruh ISI-nya digambar
    # di dalam inset _DASH_COLS_PAD_IN (0.08in, angka acuan). Dulu teks di-inset 0.05-0.06in
    # tapi chart & kartu tidak di-inset sama sekali, jadi menyentuh garis tepi panel.
    col_w_isi = max(0.5, col_w - 2 * _DASH_COLS_PAD_IN)

    # ---- A5 LANJUTAN: TINGGI KOTAK CATATAN DIHITUNG, BUKAN DIPATOK -------------------
    # KEPUTUSAN USER: catatan berisi agregat yang TIDAK BISA dibaca dari chart mana pun
    # (median, rentang, cakupan tak tergambar) - isi paling tidak tergantikan di halaman,
    # jadi ia yang menang saat berebut ruang dgn chart. Tapi tingginya IKUT ISI: kalau
    # butirnya pendek dan 1.02in cukup, kotak tidak ditinggikan. Batas atasnya dihitung dari
    # tinggi MINIMUM chart tiap kolom - chart tidak boleh jatuh di bawah ambang keterbacaan,
    # jadi butir terakhir yang mengalah, bukan chart.
    _catatan_per_kolom: list = [
        [str(x) for x in (c.get("notes") or []) if str(x).strip()] for c in cols
    ]
    _catatan_per_kolom = [k for k in _catatan_per_kolom if k]
    # `bentuk` dioper supaya kolom BERTUMPUK dihitung sbg jumlah seksinya - lihat catatan
    # kembarannya di export_pdf.py.
    _maks_note_in = tinggi_maks_kotak_catatan(
        cols, col_w_isi, avail_h_in, is_english(ctx.report), bentuk=_bentuk)
    _NOTE_HAL_H_IN, _butir_note, _note_tak_muat = tinggi_kotak_catatan_halaman(
        total_w_in, _catatan_per_kolom, _maks_note_in)
    logger.info("kotak catatan halaman: %d butir muat (kotak %.2fin, batas %.2fin), "
                "%d tidak muat, dari %d kolom bercatatan",
                len(_butir_note), _NOTE_HAL_H_IN, _maks_note_in, _note_tak_muat,
                len(_catatan_per_kolom))
    avail_h_in = avail_h_in - _NOTE_HAL_H_IN

    # ---- ALOKASI PROPORSIONAL, BUKAN RATA (kembaran export_pdf.py, aturan SAMA) ---------
    _slot, _pos, _alokasi = [], 0, {}
    for _ki, _cnt in enumerate(_bentuk):
        _seksi = cols[_pos:_pos + _cnt]
        _pos += _cnt
        if not _seksi:
            continue
        _hasil_kol = alokasi_kolom_bertumpuk(_seksi, col_w_isi, avail_h_in, is_english(ctx.report))
        _yy = 0.0
        for _c, _h in zip(_seksi, _hasil_kol):
            _kepala_c = _kepala_seksi_h_in(_c, col_w_isi)
            _footprint = _kepala_c + _h["chart_h"] + (0.10 + _h["cards_h"] if _h["cards"] else 0.0)
            _slot.append((_ki, _c, _yy, _yy + _footprint))
            _alokasi[id(_c)] = _h
            _yy += _footprint + _DASH_TILE_GAP_IN

    for idx, (_kol_i, col, _y_awal, _bawah_rel) in enumerate(_slot):
        x = _DASH_MARGIN_X_IN + _kol_i * (col_w + _DASH_COLS_GAP_IN)
        x_isi = x + _DASH_COLS_PAD_IN
        # BATAS KERAS ke garis kotak Catatan - lihat scratchpad/patch_clamp untuk ukurannya.
        # Akumulasi footprint seksi bisa melampaui anggaran; tanpa batas ini panel kolom
        # digambar menembus kotak Catatan dan keduanya jadi tidak terbaca.
        _bawah_seksi = min(title_bottom_in + _bawah_rel, title_bottom_in + avail_h_in)
        # ---- A1 + A4 (kembaran export_pdf.py): PITA KEPALA berwarna + cara-baca --------
        # Acuan memakai pita ~0.20in berisi judul panel, dgn pita kedua sebaris berisi CARA
        # MEMBACA chart. Sekat di acuan GARIS TEPI, bukan bayangan (141/141 shape bergaris).
        y = title_bottom_in + _y_awal
        _cara = str(col.get("cara_baca") or "")
        # ---- A2 (kembaran export_pdf.py): BADAN PANEL putih bergaris sbg alas ---------
        _badan = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(col_w),
            Inches(max(0.5, _bawah_seksi - y - 0.02)))
        _modest_corner(_badan)
        _badan.fill.solid()
        _badan.fill.fore_color.rgb = WHITE
        _badan.line.color.rgb = PANEL_BORDER
        # Kembaran export_pdf.py: panel bersebelahan nol-jarak membuat garisnya DOBEL
        # (terukur 1,62pt di render PDF, padahal satu border 0,75pt). Yang terbaca sbg
        # "kolom terlalu rapat" itu tebal garisnya, bukan gap yang kurang - _DASH_COLS_GAP_IN
        # tetap 0 sesuai acuan. 0,4pt supaya dua garis bersentuhan kembali setara satu garis.
        _badan.line.width = Pt(_DASH_PANEL_LINE_PT)
        _no_shadow(_badan)
        _judul_w = col_w_isi
        # Kembaran export_pdf.py: font mengecil sampai judul muat, pita ditinggikan kalau
        # pada 5.5pt pun masih lebih dari satu baris. Judul TIDAK dipotong.
        # TINGGI PITA DIHITUNG DULU, sebelum shape-nya dibuat - aturan tetap: tinggi yang
        # bergantung isi harus bisa dihitung sebelum digambar.
        _w_judul_px = max(40.0, _judul_w * 96)
        # PITA KEPALA = LABEL TOPIK PENDEK (kembaran export_pdf.py) - `title` blok tetap
        # kalimat temuan karena dipakai headline halaman. Lihat judul_pendek_kolom.
        _judul_teks = str(col.get("judul_pendek") or col.get("title") or "")
        _jp, _jbaris = 8.5, 1
        for _pt in (8.5, 8.0, 7.5, 7.0, 6.5, 6.0, 5.5):
            _jp = _pt
            _jbaris = wrap_line_count(_judul_teks, _w_judul_px, _pt, 0.80)
            if _jbaris <= 1:
                break
        _pita_h = max(_DASH_COLS_TITLE_H_IN,
                      _jbaris * (_jp * 1.25 / 72.0) + _DASH_COLS_TITLE_PAD_IN)
        # tint pita DARI TEMA AKTIF (kembaran export_pdf.py) - helper mengembalikan hex,
        # python-pptx butuh RGBColor, jadi dikonversi di sini lewat _as_rgb yang sudah ada.
        _bg_hex, _garis_hex, _fg_hex = warna_pita_panel(_hex_tema(ctx.theme["main"]))
        _pita_bg = _as_rgb(_bg_hex, PANEL_BORDER)
        _pita_garis = _as_rgb(_garis_hex, PANEL_BORDER)
        _pita_fg = _as_rgb(_fg_hex, TEXT_DARK)
        _pita = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y),
                                       Inches(col_w), Inches(_pita_h))
        _modest_corner(_pita)
        _pita.fill.solid()
        _pita.fill.fore_color.rgb = _pita_bg
        _pita.line.color.rgb = _pita_garis
        _pita.line.width = Pt(0.5)
        _no_shadow(_pita)
        t_box = slide.shapes.add_textbox(
            Inches(x_isi), Inches(y), Inches(_judul_w), Inches(_pita_h)
        )
        t_tf = t_box.text_frame
        t_tf.word_wrap = True
        t_tf.margin_top = t_tf.margin_bottom = 0
        # judul DITENGAHKAN vertikal di pitanya. Pita sekarang mengikuti tinggi teks +
        # padding acuan (0.14in), jadi ada ruang di atas & di bawah teks yang harus dibagi
        # rata - bukan seluruhnya jatuh di bawah spt pada jangkar atas bawaan.
        t_tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        t_p = t_tf.paragraphs[0]
        t_p.text = _judul_teks
        t_p.font.size = Pt(_jp)
        t_p.font.bold = True
        t_p.font.color.rgb = _pita_fg
        t_p.font.name = TITLE_FONT
        y += _pita_h
        if _cara:
            # A3 (kembaran export_pdf.py): keterangan ITALIC ABU tanpa latar, di bawah pita.
            c_box = slide.shapes.add_textbox(
                Inches(x_isi), Inches(y), Inches(col_w_isi), Inches(0.17))
            c_tf = c_box.text_frame
            c_tf.word_wrap = True
            c_tf.margin_top = c_tf.margin_bottom = 0
            c_p = c_tf.paragraphs[0]
            c_p.text = _cara
            _set_font(c_p, BODY_FONT, Pt(6.5), color=GRAY_TEXT)
            c_p.font.italic = True
            y += 0.18
        # jeda setelah blok judul - HARUS sepadan dgn _kepala_seksi_h_in di perencana &
        # dgn sisi PDF. Lihat catatan di _DASH_COLS_JUDUL_GAP_IN.
        y += 0.04 if _cara else _DASH_COLS_JUDUL_GAP_IN

        kpi = (col.get("kpi_summary") or [])[:2]
        if kpi:
            # Penjaga yang sama dgn chart & kartu: strip KPI seksi kedua bisa jatuh di bawah
            # batas kotak Catatan. Diputuskan sebelum digambar, bukan sesudah.
            if y + _DASH_COLS_KPI_H_IN > _bawah_seksi + 0.02:
                # DILEWATI berarti tidak memakai ruang. CACAT NYATA: sebelumnya tinggi strip
                # tetap dikurangkan dari `y` walau stripnya tidak digambar, jadi chart di
                # bawahnya kehabisan tempat dan ikut dilewati - satu elemen yang tidak muat
                # menyeret elemen lain yang sebenarnya masih muat. Terukur di laporan uji
                # 2-berkas: "chart kolom dilewati: sisa ruang -0,17in".
                logger.info("strip KPI kolom dilewati: butuh sampai %.2fin, batas seksi %.2fin",
                            y + _DASH_COLS_KPI_H_IN, _bawah_seksi)
            else:
                _insight_kpi_row(slide, kpi, x_isi, col_w_isi, _DASH_COLS_KPI_H_IN, y, theme=ctx.theme)
                y += _DASH_COLS_KPI_H_IN + 0.10


        # Lantai tinggi DIHAPUS (lihat catatan panjang di scratchpad/patch_body_h): grid kartu
        # tidak boleh melewati jatah slotnya - begitu kotak Catatan tumbuh, kelebihan itu
        # menembus dan menimpa isinya. Lantai 0,25in cuma penjaga nilai nol/negatif.
        body_h = max(0.25, _bawah_seksi - y - 0.10)
        notes = [str(v) for v in (col.get("notes") or []) if str(v).strip()]
        notes_consumed = False
        # Kembar dari _build_management_dashboard_columns_block di export_pdf.py: chart di ATAS
        # + kartu ringkas di BAWAH dalam satu kolom, porsinya dipesan lebih dulu. Diubah
        # BERSAMAAN dgn sisi PDF - jangan salah satu duluan.
        _tile = col.get("main_chart_tile")
        _has_cards = bool(col.get("category_details"))
        # Catatan TIDAK lagi dipesan per kolom (A5: satu kotak selebar halaman), jadi
        # perencana diberi has_notes=False & seluruh tinggi kolom dipakai isi.
        _dasar_kolom = y
        # SUDAH dihitung sekali oleh alokasi_kolom_bertumpuk di atas (kembaran export_pdf.py)
        _column_layout = _alokasi.get(id(col)) or _layout_dashboard_column_content(
            body_h, col_w_isi, bool(_tile), col.get("category_details"), False, _tile,
            is_english(ctx.report),
        )
        _chart_h = _column_layout["chart_h"]
        # tile yang SUDAH disesuaikan perencana: barisnya dikurangi kalau ruang kurang, ekor
        # segmennya digabung ke "Lainnya", atau None kalau tile-nya DILEWATI (segmen yang
        # lolos ambang label < 2). None berarti chart TIDAK digambar - bukan jatuh kembali ke
        # tile asli; kolomnya dibiarkan tanpa chart, tidak diisi penambal.
        _tile = _column_layout.get("tile")
        if _tile is None:
            _has_cards = bool(col.get("category_details"))
            _chart_h = 0.0
        if _tile and y + _chart_h > _bawah_seksi + 0.02:
            _ruang_chart = _bawah_seksi - y - 0.02
            if _ruang_chart >= 0.30:
                logger.info("chart kolom dipepatkan: %.2fin -> %.2fin (batas seksi %.2fin)",
                            _chart_h, _ruang_chart, _bawah_seksi)
                _chart_h = _ruang_chart
            else:
                logger.info("chart kolom dilewati: sisa ruang %.2fin di bawah 0,30in",
                            _ruang_chart)
                _tile = None
                _chart_h = 0.0
        if _tile:
            notes_consumed = _insight_main_chart(
                slide, _tile, x_isi, y, col_w_isi, _chart_h,
                theme=ctx.theme, notes=None, is_en=is_en,
            )
            if _has_cards:
                y += _chart_h + 0.10
                body_h = max(0.25, _bawah_seksi - y - 0.10)
        if not _tile or _has_cards:
            cards = _column_layout["cards"]
            if cards:
                # Kembar dari _build_management_dashboard_columns_block di export_pdf.py:
                # tinggi kartu dibatasi ke kebutuhan isinya, bukan diregangkan mengisi kolom.
                # KOREKSI USER: batas 2 sub-item DIBATALKAN. Sub-item bersarang justru
                # mesin kepadatan yang kita bangun - memotongnya membuang isi tanpa penanda
                # (E-Katalog kehilangan 2 dari 4 statusnya). Tinggi baris dihitung dari
                # sub-item TERBANYAK yang sungguhan ada; kalau tidak muat, yang dikurangi
                # jumlah kartu per baris, bukan kedalaman kartunya.
                cards_h = _column_layout["cards_h"]
                # BUG NYATA DIPERBAIKI (ditemukan tes luberan yang baru dipasang - 26 shape
                # di luar slide, sampai y=8.63in): kotak Catatan digambar mengalir dari bawah
                # kartu TANPA memeriksa apakah muat. Pola yang sama utk keenam kalinya, dan
                # kali ini di kode yang baru saja saya tulis. Tinggi catatan dihitung DULU;
                # kalau tidak muat, butir paling belakang dilepas satu per satu sampai muat -
                # bukan digambar menembus batas slide di mana pembaca tidak bisa melihatnya.
                _bawah = _bawah_seksi
                if notes:
                    _sisa = _bawah - (y + cards_h + 0.08)
                    while notes and _note_box_height_in(col_w_isi, notes) > _sisa:
                        notes = notes[:-1]
                # Muat atau tidak, DIPUTUSKAN sebelum digambar - aturan yang sama dgn kotak
                # catatan kolom di atas. Tanpa ini strip kartu seksi kedua tergambar menembus
                # kotak Catatan halaman (terukur: laporan 195 slide 4, 5 shape menembus).
                # Margin 0,06in (bukan 0,02): baris sub-item di dalam kartu punya tinggi
                # sendiri yang dibulatkan saat digambar, dan sisa 0,02in terbukti masih
                # menyisakan luberan 0,04in ke kotak Catatan pada data tipis.
                _ruang_kartu = _bawah_seksi - y - 0.06
                if cards_h > _ruang_kartu:
                    if _ruang_kartu >= 0.30:
                        logger.info("kartu kolom dipepatkan: %.2fin -> %.2fin", cards_h, _ruang_kartu)
                        cards_h = _ruang_kartu
                    else:
                        logger.info("kartu kolom dilewati: sisa ruang %.2fin", _ruang_kartu)
                        cards = []
                if cards:
                    notes_consumed = _insight_detail_row(
                        slide, cards, x_isi, col_w_isi, cards_h, y, theme=ctx.theme, notes=None, is_en=is_en,
                    )
                if notes:
                    add_note_box(
                        slide, Inches(x_isi), Inches(y + cards_h + 0.08), Inches(col_w_isi),
                        notes, theme=ctx.theme, title=note_title,
                    )
                    notes_consumed = True
        # Kembar dari export_pdf.py: menggambar catatan di `y` padahal kolom ini punya
        # chart/kartu berarti menumpuk TEPAT di atasnya - inilah bug yang menutup sel heatmap
        # Senin-Rabu. Kalau visualnya ada tapi catatan tetap tidak terpakai, catatan dilewati.
        # DASAR ISI kolom ini, bukan kursor `y`. Perencana sudah menghitungnya sbg
        # note_y (= tepat di bawah chart + kartu); memakai `y` membuat kotak catatan
        # halaman menimpa kartu yang digambar di bawahnya.
        # ---- A8 OPPORTUNISTIK (kembaran export_pdf.py, aturan SAMA) -------------------
        # Strip tidak memesan ruang di depan; digambar cuma kalau SISA tinggi setelah chart &
        # kartu masih cukup. Tidak dikecilkan supaya muat. Lihat catatan lengkap di sisi PDF.
        _fakta, _ = fakta_strip_kolom(col, is_english(ctx.report))
        _dasar_isi = _dasar_kolom + float(_column_layout.get("note_y") or 0.0)
        if _fakta:
            _sisa_in = _bawah_seksi - _dasar_isi - 0.10
            if _sisa_in >= _DASH_COLS_FACT_H_IN:
                _draw_fact_strip_kolom(slide, _fakta, x_isi, _dasar_isi + 0.06, col_w_isi)
                _y_terendah = max(_y_terendah, _dasar_isi + 0.06 + _DASH_COLS_FACT_H_IN)
            else:
                logger.info("A8 strip fakta DILEWATI di kolom %d: sisa tinggi %.3fin, "
                            "strip butuh %.2fin (%s)", idx + 1, _sisa_in,
                            _DASH_COLS_FACT_H_IN,
                            ", ".join("%s=%s" % (l, v) for l, v in _fakta))

        _y_terendah = max(_y_terendah, _dasar_kolom + (_column_layout.get("note_y") or 0.0))

    # ---- A5 (kembaran export_pdf.py): SATU kotak catatan selebar area konten ----------
    # Acuan memakai satu kotak 8.97 x 1.18in terisi penuh; sebelumnya kotak per kolom
    # 6.28 x 0.88in berisi satu butir, dan di slide lain tidak ada sama sekali.
    if _butir_note and _NOTE_HAL_H_IN:
        _note_y = title_bottom_in + avail_h_in + 0.06
        _note_h = _NOTE_HAL_H_IN - 0.06
        # Nomor halaman hidup di y=7,08-7,38in, DI DALAM batas kanvas isi - jadi kotak catatan
        # tidak boleh sampai ke sana. Butir paling belakang dilepas sampai muat, sama seperti
        # yang sudah dilakukan kotak catatan per-kolom. Lihat scratchpad/patch_note_bawah.
        _BATAS_NOTE_BAWAH_IN = 7.02
        _ruang = max(0.0, _BATAS_NOTE_BAWAH_IN - _note_y)
        if _note_h > _ruang:
            while _butir_note and _note_box_height_in(total_w_in, _butir_note) > _ruang:
                _butir_note = _butir_note[:-1]
                _note_tak_muat += 1
            _note_h = min(_note_h, _ruang)
        if _note_h >= 0.40:
            # Butir & tinggi kotak SUDAH diputuskan di atas (tinggi_kotak_catatan_halaman),
            # sebelum kolom dibagi tinggi - tidak dihitung ulang di sini. Butirnya digabung
            # BERGILIRAN antar kolom; potongan tetap [:4] yang dulu membuat catatan kolom
            # kedua dst tidak pernah muncul sudah dibuang.
            _cat, _dibuang = _butir_note, _note_tak_muat
            if _dibuang:
                logger.info("kotak catatan slide: %d butir tidak digambar (ruang %.2fin)",
                            _dibuang, _note_h)
            if _cat:
                add_note_box(slide, Inches(_DASH_MARGIN_X_IN), Inches(_note_y),
                             Inches(total_w_in), _cat, theme=ctx.theme, title=note_title)
    return slide


def _build_management_action_items_slide(block: dict, ctx: _PptBlockContext):
    slide = ctx.prs.slides.add_slide(ctx.prs.slide_layouts[6])
    add_logo(slide, ctx.logo_path)
    add_kicker(slide, block.get("kicker", ""))
    title_bottom = add_title(slide, block.get("title", ""))

    # Block rekomendasi sudah dipaginasi maksimal 6 item oleh report_render_logic.py, sehingga
    # semua item tetap masuk tanpa membuat kartu keluar dari slide.
    items = block.get("items", [])
    start_y = max(title_bottom + 0.12, 1.05)
    gap = 0.15
    n = len(items) or 1
    # BUG NYATA DIPERBAIKI (terukur: 15 dari 28 slide "Tindak Lanjut" py elemen di bawah
    # y=7.5in, sampai 8.76in - blok Kesimpulan tergambar DI LUAR slide, jadi di 15 laporan
    # Kesimpulan tidak terlihat pembaca sama sekali di PPT). Sebabnya tinggi kartu dihitung
    # dari SELURUH sisa slide tanpa memesan ruang utk Kesimpulan, padahal tingginya sudah
    # bisa dihitung dari isinya. Ini pola bug yang sama utk keempat kalinya: elemen yang
    # tingginya bergantung isi tidak dipesan lebih dulu. Sekarang ruangnya dipesan DULU.
    _concl_text = block.get("conclusion_text")
    _concl_pills = block.get("conclusion_pills") or []
    _concl_w_in = Emu(CONTENT_W).inches - 0.5
    _concl_reserve = 0.0
    if _concl_text:
        _concl_reserve = 0.1 + max(
            1.1,
            0.5 + _estimate_wrapped_height_in(_concl_text, 10.5, _concl_w_in)
            + (0.55 if _concl_pills else 0.15),
        )
    available_h = 7.5 - start_y - 0.4 - _concl_reserve
    card_h = min(1.1, max((available_h - gap * (n - 1)) / n, 0.62))

    for i, it in enumerate(items):
        cy = Inches(start_y + i * (card_h + gap))
        fg, bg = URGENCY_COLOR.get(it.get("urgency", "low"), (GRAY_TEXT, IVORY))

        rect = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, MARGIN_X, cy, CONTENT_W, Inches(card_h))
        _modest_corner(rect)
        rect.fill.solid()
        rect.fill.fore_color.rgb = bg
        rect.line.color.rgb = fg
        rect.line.width = Pt(1.2)

        tb = slide.shapes.add_textbox(MARGIN_X + Inches(0.3), cy + Inches(0.1), CONTENT_W - Inches(0.6), Inches(card_h - 0.2))
        tf = tb.text_frame
        tf.word_wrap = True

        p1 = tf.paragraphs[0]
        p1.alignment = PP_ALIGN.LEFT
        p1.text = f"{it.get('number', i+1)}. {it.get('title', '')} [{it.get('urgency', '').upper()}]"
        _set_font(p1, BODY_FONT, Pt(12), bold=True, color=TEXT_DARK)

        if it.get("detail"):
            p2 = tf.add_paragraph()
            p2.alignment = PP_ALIGN.LEFT
            p2.text = it.get("detail", "")
            _set_font(p2, BODY_FONT, Pt(10), color=GRAY_TEXT)

    # PERMINTAAN USER LANJUTAN ("Rekomendasi Prioritas pakai lapis yang sama dgn halaman
    # insight baru... kalau masih ada sisa, tarik Kesimpulan naik ke halaman yang sama"):
    # kalau report_render_logic.py menitipkan Kesimpulan ke chunk TERAKHIR slide ini (lihat
    # build_management_report_blocks), gambar sbg strip gelap di bawah kartu2 action item —
    # BUKAN slide solo terpisah spt sebelumnya (penyumbang kegagalan kepadatan TERBANYAK,
    # ditemukan lewat tes kepadatan halaman).
    if block.get("conclusion_text"):
        strip_top_in = start_y + n * (card_h + gap) + 0.1
        concl_pills = block.get("conclusion_pills") or []
        concl_text_w_in = Emu(CONTENT_W).inches - 0.5
        concl_text_h_in = _estimate_wrapped_height_in(block["conclusion_text"], 10.5, concl_text_w_in)
        min_strip_h_in = 0.5 + concl_text_h_in + (0.55 if concl_pills else 0.15)
        # DIJEPIT ke batas bawah slide: apa pun hasil hitungannya, strip tidak boleh melewati
        # 7.5in - lebih baik terlihat lebih pendek drpd separuhnya jatuh di luar slide.
        strip_h_in = max(1.1, 6.9 - strip_top_in, min_strip_h_in)
        strip_h_in = max(0.6, min(strip_h_in, 7.5 - 0.25 - strip_top_in))
        strip = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, MARGIN_X, Inches(strip_top_in), CONTENT_W, Inches(strip_h_in))
        strip.fill.solid()
        strip.fill.fore_color.rgb = ctx.theme["bg"]
        strip.line.color.rgb = ctx.theme["light"]
        strip.line.width = Pt(0.75)
        _no_shadow(strip)
        _modest_corner(strip)

        ctp = slide.shapes.add_textbox(MARGIN_X + Inches(0.25), Inches(strip_top_in + 0.15), CONTENT_W - Inches(0.5), Inches(0.3))
        cp_title = ctp.text_frame.paragraphs[0]
        cp_title.alignment = PP_ALIGN.LEFT
        cp_title.text = block["conclusion_title"]
        _set_font(cp_title, TITLE_FONT, Pt(13), bold=True, color=WHITE)

        ctxt = slide.shapes.add_textbox(MARGIN_X + Inches(0.25), Inches(strip_top_in + 0.5), CONTENT_W - Inches(0.5), Inches(strip_h_in - 0.55))
        ctxt.text_frame.word_wrap = True
        cp_text = ctxt.text_frame.paragraphs[0]
        cp_text.alignment = PP_ALIGN.LEFT
        cp_text.text = block["conclusion_text"]
        _set_font(cp_text, BODY_FONT, Pt(10.5), color=RGBColor(0xE8, 0xEC, 0xE6))

        if concl_pills:
            pill_y = Inches(strip_top_in + strip_h_in - 0.45)
            pill_x = MARGIN_X + Inches(0.25)
            for pill_text in concl_pills[:3]:
                pill_w = Inches(max(1.2, 0.12 * len(pill_text) + 0.5))
                pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, pill_x, pill_y, pill_w, Inches(0.32))
                _modest_corner(pill, frac=0.5)
                pill.fill.solid()
                pill.fill.fore_color.rgb = ctx.theme["main"]
                pill.line.color.rgb = ctx.theme["light"]
                pill.line.width = Pt(1)
                _no_shadow(pill)
                ptf = pill.text_frame
                ptf.margin_left = ptf.margin_right = Inches(0.08)
                pp_ = ptf.paragraphs[0]
                pp_.alignment = PP_ALIGN.CENTER
                pp_.text = pill_text
                _set_font(pp_, BODY_FONT, Pt(9), bold=True, color=ctx.theme["light"])
                pill_x += pill_w + Inches(0.12)

    return slide


def _build_management_asset_ranking_slide(block: dict, ctx: _PptBlockContext):
    # Versi padat/batang khas Management Report — meniru persis cabang "bars" di
    # _build_asset_cards_slide di atas, tapi TIDAK ikut ctx.asset_style (dipaksa selalu
    # batang, supaya konsisten padat, tidak ikut pengacakan kartu/podium gaya SOC).
    slide = ctx.prs.slides.add_slide(ctx.prs.slide_layouts[6])
    add_dark_bg(slide, theme=ctx.theme)
    add_logo(slide, ctx.logo_path, dark=True)
    add_kicker(slide, block.get("kicker", ""), color=WHITE)
    title_bottom = add_title(slide, block.get("title", ""), color=WHITE)
    items = block.get("items", [])
    bars_y = max(title_bottom + 0.15, 1.1)
    bars_row_h_in = 1.0
    bars_content_h_in = len(items) * bars_row_h_in
    bars_available_in = 6.6 - bars_y
    if bars_available_in > bars_content_h_in:
        bars_y += (bars_available_in - bars_content_h_in) / 2
    add_asset_ranked_bars(slide, MARGIN_X, Inches(bars_y), CONTENT_W, items, row_h=Inches(bars_row_h_in), theme=ctx.theme, is_en=is_english(ctx.report))
    return slide


def _build_management_ai_narrative_slide(block: dict, ctx: _PptBlockContext):
    # Narasi bebas tulisan AI (setara dynamic_section gaya SOC), ditampilkan sbg grid kartu
    # ivory meniru gaya tile _build_management_visual_dashboard_slide di atas — supaya
    # terasa menyatu dgn slide dashboard visual, bukan tempelan gaya SOC.
    slide = ctx.prs.slides.add_slide(ctx.prs.slide_layouts[6])
    add_logo(slide, ctx.logo_path)
    add_kicker(slide, block.get("kicker", ""))
    title_bottom = add_title(slide, block.get("title", ""))

    items = block.get("items", [])
    if not items:
        return slide
    n = len(items)
    # Aturan kolom & skala DISALIN dari _build_management_ai_narrative_block (export_pdf.py),
    # bukan dikarang ulang: 1 atau 3 item -> satu kolom lebar penuh (kalau 2 kolom, item
    # terakhir berdiri sendiri dgn sel kosong di sampingnya); makin sedikit item, makin besar
    # font & padding supaya halaman terisi wajar.
    cols = 1 if n in (1, 3) else 2
    rows = math.ceil(n / cols)
    skala = 1.8 if n <= 1 else (1.3 if n == 2 else (1.15 if n == 3 else 0.82))
    pad_in = (14.0 * (3.0 if n <= 1 else (1.6 if n == 2 else (1.3 if n == 3 else 0.62)))) / 72.0
    pt_judul = 9.5 * skala
    pt_isi = 9.0 * skala
    badge_in = (20.0 * skala) / 96.0

    gap_in = 0.25
    start_y_in = max(title_bottom + 0.15, 1.05)
    margin_x_in = Emu(MARGIN_X).inches
    content_w_in = Emu(CONTENT_W).inches
    content_bottom_in = Emu(SLIDE_H).inches - 0.25
    content_h_in = max(1.2, content_bottom_in - start_y_in)
    card_w_in = (content_w_in - gap_in * (cols - 1)) / cols

    def _butir(teks):
        """Satu kalimat = satu bullet, sama spt _bullet_lines_html di sisi PDF."""
        return [b.strip() for b in re.split(r"(?<=[.!?])\s+", str(teks or "").strip()) if b.strip()]

    def _tinggi_kartu(it):
        """Tinggi yang BENAR-BENAR dibutuhkan isi kartu - bukan jatah kanvas dibagi rata.
        Inilah inti cacatnya: versi lama memakai (tinggi kanvas / jumlah baris), jadi kartu
        berisi tiga kalimat tetap setinggi 5,5in dan sisanya kosong melompong."""
        w_px = max(60.0, (card_w_in - 2 * pad_in - badge_in - 0.10) * 96.0)
        baris = sum(max(1, wrap_line_count(b, w_px, pt_isi, 0.62)) for b in _butir(it.get("content", "")))
        tinggi_isi = baris * (pt_isi * 1.55) / 72.0
        return pad_in * 2 + badge_in + 0.12 + tinggi_isi

    tinggi = [_tinggi_kartu(it) for it in items]
    card_h_in = max(tinggi) if tinggi else 1.0
    # Tetap tidak boleh melewati kanvas: kalau isinya memang banyak, kartu dibatasi & teks
    # yang tidak muat tetap tergambar tapi terpotong tepi kartu - sama spt sisi PDF.
    maks = (content_h_in - gap_in * (rows - 1)) / rows
    card_h_in = min(card_h_in, maks)

    for i, it in enumerate(items):
        r, c = divmod(i, cols)
        cx_in = margin_x_in + c * (card_w_in + gap_in)
        cy_in = start_y_in + r * (card_h_in + gap_in)

        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(cx_in), Inches(cy_in), Inches(card_w_in), Inches(card_h_in))
        card.fill.solid()
        card.fill.fore_color.rgb = IVORY
        card.line.color.rgb = PANEL_BORDER
        card.line.width = Pt(0.75)
        _no_shadow(card)
        _modest_corner(card)

        # Garis aksen kiri - kembaran border_left_colors di card_style sisi PDF.
        aksen = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(cx_in), Inches(cy_in),
                                       Inches(0.045), Inches(card_h_in))
        aksen.fill.solid()
        aksen.fill.fore_color.rgb = TEXT_DARK
        aksen.line.fill.background()
        _no_shadow(aksen)

        add_badge_circle(slide, Inches(cx_in + pad_in), Inches(cy_in + pad_in),
                         Inches(badge_in), str(i + 1), TEXT_DARK, font_size=Pt(9 * skala))

        jx = cx_in + pad_in + badge_in + 0.10
        title_box = slide.shapes.add_textbox(Inches(jx), Inches(cy_in + pad_in - 0.02),
                                             Inches(card_w_in - pad_in - badge_in - 0.20),
                                             Inches(badge_in + 0.06))
        _rapatkan_margin(title_box.text_frame, atas=0.0, bawah=0.0)
        title_box.text_frame.word_wrap = True
        title_box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        tp = title_box.text_frame.paragraphs[0]
        tp.alignment = PP_ALIGN.LEFT
        tp.text = str(it.get("title", "")).upper()
        _set_font(tp, BODY_FONT, Pt(pt_judul), bold=True, color=TEXT_DARK)

        by = cy_in + pad_in + badge_in + 0.12
        body_box = slide.shapes.add_textbox(
            Inches(cx_in + pad_in), Inches(by),
            Inches(card_w_in - pad_in * 2), Inches(max(0.25, card_h_in - (by - cy_in) - pad_in)),
        )
        btf = body_box.text_frame
        _rapatkan_margin(btf, atas=0.0, bawah=0.0)
        btf.word_wrap = True
        for bi, butir in enumerate(_butir(it.get("content", ""))):
            bp = btf.paragraphs[0] if bi == 0 else btf.add_paragraph()
            bp.alignment = PP_ALIGN.LEFT
            # Bullet digambar sbg karakter, bukan penomoran otomatis PowerPoint: penomoran
            # otomatis butuh properti daftar di level XML & gampang hilang saat tema diganti.
            bp.text = "\u2022  " + butir
            bp.space_after = Pt(pt_isi * 0.45)
            _set_font(bp, BODY_FONT, Pt(pt_isi), color=GRAY_TEXT)

    return slide


# Panel yang PRAKTIS SELALU sendirian di halamannya (lihat bobot per panel_kind di
# report_render_logic.py: executive_summary/severity_distribution/critical_table/asset_cards/
# key_findings/recommendations/conclusion bobotnya sengaja tinggi) — kalau memang muncul
# sendirian, dipakai LANGSUNG builder "slide mandiri" aslinya (kualitas visual penuh, sama
# persis sblm refactor ini) alih-alih jalur kolom sempit generik di bawah.
_PPT_PANEL_STANDALONE_BUILDERS = {
    "executive_summary": _build_executive_summary_slide,
    "severity_distribution": _build_severity_distribution_slide,
    "critical_table": _build_critical_table_slide,
    "asset_cards": _build_asset_cards_slide,
    "key_findings": _build_key_findings_slide,
    "recommendations": _build_recommendations_slide,
    "conclusion": _build_conclusion_slide,
}

_PPT_DISTRIBUTION_KINDS = {"category_distribution", "status_distribution", "kpi_radar", "time_heatmap", "period_compare"}
_PPT_INSIGHT_KINDS = {"insight_tile", "dynamic_section"}


def _build_page_slide(block: dict, ctx: _PptBlockContext):
    """Composer generik: 1 slide = 1-4 panel (block["panels"], lihat report_render_logic.py
    tahap 2). 1 panel dari _PPT_PANEL_STANDALONE_BUILDERS -> dipakai LANGSUNG builder aslinya
    (slide sendiri, kualitas penuh). Selain itu (1 panel ATAU beberapa panel bertema sama,
    "distribution" atau "insight") -> 1 slide baru dibuat di sini, panel digambar berdampingan
    N kolom lewat _draw_distribution_panel/_draw_insight_tile (mirror _build_page_block di
    export_pdf.py, sudah menjamin campur "distribution"+"insight" TIDAK PERNAH terjadi di 1
    halaman yang sama — lihat _group_candidates_into_pages)."""
    panels = block["panels"]
    if len(panels) == 1 and panels[0]["panel_kind"] in _PPT_PANEL_STANDALONE_BUILDERS:
        return _PPT_PANEL_STANDALONE_BUILDERS[panels[0]["panel_kind"]](panels[0], ctx)

    slide = ctx.prs.slides.add_slide(ctx.prs.slide_layouts[6])
    dark = block["dark"]
    if dark:
        add_dark_bg(slide, theme=ctx.theme)
    add_logo(slide, ctx.logo_path, dark=dark)
    # BUG DIPERBAIKI (drift vs export_pdf.py::_build_page_block — lihat _PANEL_NEEDS_PAGE_
    # HEADER di sana, gerbang identik dgn _PPT_INSIGHT_KINDS di sini): panel "mandiri"
    # (category_distribution/kpi_radar/dst, digambar _draw_distribution_panel) SUDAH bawa
    # judulnya SENDIRI di dalam kontennya — sebelumnya block["title"]/["kicker"] di sini
    # SELALU digambar juga tanpa syarat, jadi halaman berisi panel mandiri kelihatan
    # PUNYA 2 JUDUL (judul halaman generik + judul panel sendiri di bawahnya). Judul
    # halaman sekarang HANYA digambar kalau salah satu panelnya jenis "insight_tile"/
    # "dynamic_section" (TIDAK bawa judul sendiri, lihat _draw_insight_tile) — persis
    # kondisi yang sama dipakai PDF.
    # PERMINTAAN USER — mirror export_pdf.py::_build_page_block: `all()` bukan `any()`, supaya
    # halaman CAMPURAN (panel mandiri yang sudah bawa judul sendiri + insight_tile hasil
    # sambungan backstop) tidak menggambar judul generik dobel di atas judul panel mandiri itu.
    needs_header = panels and all(p["panel_kind"] in _PPT_INSIGHT_KINDS for p in panels)
    if needs_header and block.get("title"):
        add_kicker(slide, block.get("kicker") or "", color=(WHITE if dark else GRAY_TEXT))
        title_bottom = add_title(slide, block.get("title") or "", color=(WHITE if dark else TEXT_DARK))
        content_top_in = max(title_bottom + 0.15, 1.0)
    else:
        content_top_in = 0.85
    content_h_in = max(2.0, 6.9 - content_top_in)

    n = len(panels)
    gap = Inches(0.35)
    col_w = (CONTENT_W - gap * (n - 1)) / n
    for i, panel in enumerate(panels):
        col_x = MARGIN_X + i * (col_w + gap)
        if panel["panel_kind"] in _PPT_INSIGHT_KINDS:
            _draw_insight_tile(slide, panel, ctx, col_x, Inches(content_top_in), col_w, Inches(content_h_in))
        elif panel["panel_kind"] in _PPT_DISTRIBUTION_KINDS:
            _draw_distribution_panel(slide, panel, ctx, col_x, Inches(content_top_in), col_w, Inches(content_h_in))
        else:
            # BUG DIPERBAIKI: docstring fungsi ini KLAIM campur panel "standalone" (mis.
            # critical_table) dgn panel "distribution"/"insight" di 1 halaman yang sama
            # "sudah dijamin TIDAK PERNAH terjadi" oleh _group_candidates_into_pages di
            # report_render_logic.py — tapi jaminan itu TIDAK DITEGAKKAN di sini sama
            # sekali, cuma diasumsikan. Kalau asumsi itu ternyata salah/berubah di masa
            # depan, panel ini akan DIAM-DIAM HILANG dari slide tanpa jejak apa pun. Warning
            # ini bukan solusi (bukan tempatnya menggambar ulang panel jenis itu di sini),
            # cuma memastikan kalau itu terjadi, ada jejak di log utk diselidiki — bukan
            # bug senyap.
            logger.warning(
                "panel_kind %r tidak dikenali di _build_page_slide (bukan insight/distribution "
                "kind, dan bukan 1-panel standalone) — panel ini TIDAK digambar di slide.",
                panel.get("panel_kind"),
            )
    return slide


_PPT_BLOCK_BUILDERS = {
    "cover": _build_cover_slide,
    "page": _build_page_slide,
    "closing_summary": _build_closing_summary_slide,
    "closing": _build_closing_slide,
    "management_insight_page": _build_management_insight_page_slide,
    "management_dashboard_columns": _build_management_dashboard_columns_slide,
    "management_action_items": _build_management_action_items_slide,
    "management_asset_ranking": _build_management_asset_ranking_slide,
    "management_ai_narrative": _build_management_ai_narrative_slide,
}


class PPTXExporter:
    @classmethod
    def generate_ppt_report(cls, report: Report) -> bytes:
        # Lihat catatan yang sama di export_pdf.py::generate_pdf_report.
        set_render_language(report)
        prs = Presentation()
        prs.slide_width = SLIDE_W
        prs.slide_height = SLIDE_H

        logo_path = _resolve_logo_path()
        _template = (report.template_type or "").strip().lower()
        if "management" in _template:
            blocks = build_management_report_blocks(report)
        else:
            blocks = build_report_blocks(report)

        # Varian tampilan (cover_style, category_style, dst) DIBACA dari report.visual_style,
        # BUKAN di-random di sini lagi — BUG YANG DIPERBAIKI (dilaporkan user): dulu tiap kali
        # generate_ppt_report dipanggil, pilihan acak baru diambil, jadi preview web (yang
        # membaca kombinasi TETAP per laporan lewat endpoint /blocks) bisa menampilkan bentuk
        # yang beda dari file yang benar-benar diunduh. Sekarang preview & export SAMA-SAMA
        # baca report.visual_style yang SUDAH DIKUNCI sekali sewaktu analisis AI berhasil (lihat
        # pick_visual_style() di report_render_logic.py) — dijamin identik utk 1 laporan yang
        # sama, dan React (ReportBlockRenderer.tsx) sekarang genuinely merender SEMUA varian ini
        # (bukan lagi cuma 1 bentuk tetap), jadi preview akurat mencerminkan file yang diunduh.
        vs = get_visual_style(report)
        flourish_corner = vs["flourish_corner"]
        panel_side = vs["panel_side"]
        stat_cols = vs["stat_cols"]
        card_cols = vs["card_cols"]
        category_style = vs["category_style"]
        status_style = vs["status_style"]
        cover_style = vs["cover_style"]
        asset_style = vs["asset_style"]
        recommendation_style = vs["recommendation_style"]
        # Teks kicker TETAP (bukan bagian dari visual_style — cuma variasi kata, bukan bentuk)
        kicker_ringkasan = "Executive Summary" if is_english(report) else "Ringkasan Eksekutif"
        kicker_analisis = "DATA ANALYSIS" if is_english(report) else "ANALISIS DATA"

        # Palet warna tema (report.theme_color)
        theme_key = resolve_theme_color(report)
        if theme_key in THEME_PALETTES:
            palette = THEME_PALETTES[theme_key]
        elif str(theme_key).startswith("#"):
            # 2 BUG DIPERBAIKI (mirror export_pdf.py, lihat catatan lengkap di sana):
            # 1. "soft" sebelumnya RGBColor(0xF3,0xF4,0xF6) (abu-abu nyaris putih, tidak
            #    senada) — MISMATCH dgn preview web (resolveThemeColors pakai GOLD_LIGHT).
            # 2. "chart" sebelumnya = "main" APA ADANYA — 2 seri (mis. grouped bar
            #    "Perbandingan Antar Paruh Periode") jadi TIDAK BISA DIBEDAKAN. "chart"
            #    sekarang tint lebih terang dari warna kustom yang sama, bukan duplikat exact.
            # 3. "bg" (latar cover/penutup) sebelumnya SELALU navy gelap tetap, terlepas dari
            #    warna kustomnya — cover jadi terlihat seperti tidak menerapkan pilihan warna
            #    user sama sekali (lihat docstring _darken).
            #
            # BUG BESAR TAMBAHAN (mirror export_pdf.py, lihat catatan lengkap di sana):
            # "light"/"soft" sekarang KEEMPATNYA diturunkan dari SATU hue kustom yang sama
            # (main=gelap, chart=medium, light=terang, soft=paling terang) — pola RAMP SAMA
            # PERSIS yang sudah dipakai tema "gold" bawaan sendiri — BUKAN tetap GOLD_MAIN/
            # GOLD_LIGHT (aksen emas tak terkait pilihan user, dipakai luas di kicker/pill/
            # badge/panel gelap hampir tiap slide, penyebab utama "warnanya kurang kelihatan").
            # BUG YANG DIPERBAIKI (dilaporkan user): "main" kustom dipakai APA ADANYA tanpa
            # jaminan cukup gelap utk teks putih di atasnya (kartu KPI, cover/penutup) — warna
            # terang (mis. ungu muda #CF87DA) bikin teks nyaris tak kelihatan. _light_safe()
            # dipakai ulang di sini (ambang 0.45, tepat di atas luminance "main" tema gold
            # bawaan ~0.42, tema PALING terang dari 4 tema tetap) supaya "main" kustom SELALU
            # cukup gelap dipakai bersama teks putih.
            # PERMINTAAN USER: ambang dinaikkan 0.45 -> 0.55 spy warna kustom sangat terang
            # (mis. #ADF8FF) tidak digelapkan berlebihan — lihat catatan sama persis di
            # export_pdf.py.
            c = _light_safe(_hex_to_rgb(str(theme_key)), max_luminance=0.55)
            chart_shade = _blend_with_white(c, 0.6)
            light_shade = _blend_with_white(c, 0.3)
            soft_shade = _blend_with_white(c, 0.12)
            palette = {"main": c, "bg": _darken(c), "chart": chart_shade, "light": light_shade, "soft": soft_shade}
        else:
            palette = THEME_PALETTES["green"]
        accent_bar_color = palette["main"]
        # ---- DOMINASI WARNA TEMA (permintaan user, HANYA jalur Visual/Management) --------
        # Diukur dari render: pada tema bawaan non-gold, THEME_PALETTES menyetel
        # "light"/"soft" ke GOLD_MAIN/GOLD_LIGHT - aksen emas yang TIDAK terkait warna tema.
        # Keduanya dipakai di bar sub-item kartu bersarang & badge, jadi emas muncul ~21.000
        # piksel per laporan; pada tema navy selisih hue-nya 169 derajat (praktis komplementer)
        # dan pada teal 130 derajat - bukan "aksen yang serasi", tapi tabrakan.
        # Untuk warna KUSTOM keempat peran sudah diturunkan dari satu hue (lihat cabang di
        # atas); yang tertinggal cuma tema BAWAAN. Di sini ramp yang sama dipakai ulang -
        # frac 0.30/0.12 persis seperti cabang kustom, jadi bukan aturan baru.
        #
        # SENGAJA di sini, bukan di THEME_PALETTES: palet itu dipakai BERSAMA oleh jalur
        # Descriptive yang tidak boleh berubah sedikit pun. Dengan menyalin dict-nya lebih
        # dulu, Descriptive tetap mendapat palet aslinya (emas) apa adanya.
        if "management" in _template:
            palette = dict(palette)
            palette["light"] = _blend_with_white(palette["main"], 0.30)
            palette["soft"] = _blend_with_white(palette["main"], 0.12)
            accent_bar_color = palette["main"]

        content_slides: list = []  # dipakai utk stamping footer di akhir (kecuali cover/penutup)

        ctx = _PptBlockContext(
            report=report,
            prs=prs,
            logo_path=logo_path,
            panel_side=panel_side,
            stat_cols=stat_cols,
            card_cols=card_cols,
            flourish_corner=flourish_corner,
            accent_bar_color=accent_bar_color,
            category_style=category_style,
            status_style=status_style,
            cover_style=cover_style,
            asset_style=asset_style,
            recommendation_style=recommendation_style,
            accent_main=palette["main"],
            accent_bg=palette["bg"],
            accent_chart=palette["chart"],
            accent_light=palette["light"],
            accent_soft=palette["soft"],
            theme=palette,
            kicker_ringkasan=kicker_ringkasan,
            kicker_analisis=kicker_analisis,
        )

        for block in blocks:
            builder = _PPT_BLOCK_BUILDERS.get(block["kind"])
            if builder:
                slide = builder(block, ctx)
                if slide is not None:
                    content_slides.append(slide)

        # -------------------------------------------------------------
        # Footer: nomor halaman, semua slide isi kecuali cover & penutup
        # -------------------------------------------------------------
        total_pages = len(content_slides)
        for idx, s in enumerate(content_slides):
            dark_theme = getattr(s, "_petro_dark_theme", None)
            add_footer(s, idx + 1, total_pages, dark=bool(dark_theme), theme=dark_theme)

        ppt_io = __import__("io").BytesIO()
        prs.save(ppt_io)
        ppt_io.seek(0)
        return ppt_io.read()


