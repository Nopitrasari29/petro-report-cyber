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
import logging
import math
import re
from dataclasses import dataclass

from app.models.report import Report
from app.services.report_render_logic import build_report_blocks, build_management_report_blocks, is_english, find_logo_path, get_visual_style, resolve_theme_color

logger = logging.getLogger(__name__)

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

# xhtml2pdf (fallback engine kalau WeasyPrint tak tersedia di sistem) tidak bisa merender
# <svg> inline dgn andal — 5 chart BARU (bar+line, radar, heatmap grid, grouped bar, funnel,
# lihat svg_radar dkk di bawah) SENGAJA punya jalur non-SVG (tabel/div HTML polos) yang dipakai
# kalau SVG_SUPPORTED False. Chart LAMA (bar/donut/gauge) TIDAK disentuh/tidak diberi fallback
# ini — sudah berjalan apa adanya sebelum perubahan ini, di luar cakupan.
SVG_SUPPORTED = WEASYPRINT_AVAILABLE

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

# ── TEMA WARNA (report.theme_color) ─────────────────────────────────────────
# GREEN_MAIN/BG/CHART & GOLD_MAIN/LIGHT di atas TETAP ada apa adanya (dipakai langsung oleh
# SEVERITY_COLOR & kondisional is_critical di bawah — warna severity TIDAK boleh ikut berubah
# oleh tema apa pun, itu konvensi semantik cyber-security yang tetap). THEME_PALETTES di bawah
# ini murni untuk elemen BRAND/struktural (cover, kicker, badge, border panel, header tabel,
# chart "bar" utama) — "green" memakai nilai HEX yang sama persis dgn di atas supaya tema
# default/laporan lama tetap identik visual dengan sebelum tema ini ada.
NAVY_MAIN = "#1E3A5F"
NAVY_BG = "#0F172A"
NAVY_CHART = "#3B6EA5"
DARK_MAIN = "#1F2937"
DARK_BG = "#111827"
DARK_CHART = "#3F4B5C"
GOLD_BRONZE_MAIN = "#8A6A16"
GOLD_BRONZE_BG = "#4A3908"
GOLD_CREAM_LIGHT = "#F3E3AE"
GOLD_CREAM_SOFT = "#FBF3DC"

THEME_PALETTES: dict[str, dict[str, str]] = {
    "green": {"main": GREEN_MAIN, "bg": GREEN_BG, "chart": GREEN_CHART, "light": GOLD_MAIN, "soft": GOLD_LIGHT},
    "navy": {"main": NAVY_MAIN, "bg": NAVY_BG, "chart": NAVY_CHART, "light": GOLD_MAIN, "soft": GOLD_LIGHT},
    "dark": {"main": DARK_MAIN, "bg": DARK_BG, "chart": DARK_CHART, "light": GOLD_MAIN, "soft": GOLD_LIGHT},
    "gold": {"main": GOLD_BRONZE_MAIN, "bg": GOLD_BRONZE_BG, "chart": GOLD_MAIN, "light": GOLD_CREAM_LIGHT, "soft": GOLD_CREAM_SOFT},
}
FONT_ATTR_QUOTE_BUG_NOTE = """
BUG BESAR YANG DIPERBAIKI (ditemukan lewat isolasi render+sampling langsung, bukan cuma baca
dokumentasi): TITLE_FONT/BODY_FONT SEBELUMNYA memakai tanda kutip DOBEL di sekeliling nama font
(mis. '"Bookman Old Style", Georgia, serif'). Setiap kali nilai ini disisipkan ke atribut HTML
style="..." (yang JUGA dibatasi kutip dobel), kutip dobel yang tertanam itu MENUTUP atribut
style secara prematur di titik itu juga - persis seperti <div style="color:"red";">. Sisa
deklarasi CSS setelahnya (termasuk font-size/font-weight/color/margin kalau font-family
ditulis PALING AWAL, pola paling umum di file ini) jadi teks bukan-atribut yang diabaikan
parser HTML, sehingga elemen itu SAMA SEKALI KEHILANGAN semua styling-nya (font 34pt bold jadi
teks kecil polos, dst) - inilah sebab utama judul cover, judul tiap halaman, angka besar kartu
statistik, dan judul highlight tampil kecil/tidak berbobot di PDF yang dihasilkan sebelumnya.
Nama font sekarang dibungkus kutip TUNGGAL saja (CSS sah menerima keduanya) supaya tidak pernah
bentrok dengan kutip dobel pembungkus atribut style="..." di mana pun nilai ini dipakai.
"""
TITLE_FONT = "'Bookman Old Style', Georgia, serif"
BODY_FONT = "Calibri, 'Segoe UI', sans-serif"

CATEGORY_COLOR_RAMP = [GREEN_MAIN, GREEN_CHART, GOLD_MAIN, GOLD_LIGHT, GRAY_TEXT]
SEVERITY_COLOR = {
    "critical": RED_CRIT, "high": GOLD_MAIN, "medium": GREEN_MAIN,
    "low": GREEN_CHART, "informational": GRAY_TEXT,
}


def _resolve_logo_b64() -> str | None:
    p = find_logo_path()
    if not p:
        return None
    try:
        with open(p, "rb") as f:
            return base64_encode(f.read())
    except Exception:
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
    #
    # BUG NYATA DITEMUKAN (tema "gold" khususnya): teks angka di dalam badge SELALU putih
    # (fixed) — banyak pemanggil di file ini memberi `color` = peran "light" tema (t["light"]/
    # ctx.accent_light), yang cukup gelap utk tema green/navy/dark (badge tetap kebaca) tapi
    # SANGAT pucat khusus utk tema "gold" (dirancang sbg teks di atas latar gelap, bukan fill
    # badge) — hasilnya angka putih nyaris tak kelihatan di atas badge krem pucat. _light_safe
    # dipanggil DI SINI (bukan di tiap titik panggil) supaya SEMUA pemanggil badge terlindungi
    # otomatis, warna yang sudah cukup gelap (mayoritas pemanggil) tidak berubah sama sekali.
    color = _light_safe(color)
    return (
        f'<div style="display:inline-block;width:{size};height:{size};line-height:{size};'
        f'border-radius:50%;background:{color};text-align:center;color:#fff;font-weight:700;'
        f'font-size:{font_size};font-family:{BODY_FONT};">{_esc(text)}</div>'
    )


def _badge_row(number, title, detail, color=GREEN_MAIN, on_dark=False, scale=1.0) -> str:
    # xhtml2pdf (fallback engine kalau WeasyPrint tak tersedia) TIDAK support flexbox —
    # dipakai <table> supaya badge+teks sejajar konsisten di kedua engine.
    #
    # RANCANG ULANG (target WeasyPrint, lihat catatan di _ivory_panel): height eksplisit
    # dihapus — baris sepadat kontennya (detail panjang wrap bebas tanpa risiko kepotong/
    # numpuk), jarak antar baris dinaikkan sedikit (14px) supaya senapas dengan spacing
    # generous di panel-panel lain.
    # `scale` (PERMINTAAN USER, berkali-kali): dipakai _build_key_findings_block utk
    # memperbesar baris ini kalau jumlah temuannya sedikit (1.0 = ukuran normal).
    title_color = WHITE if on_dark else TEXT_DARK
    detail_color = GOLD_LIGHT if on_dark else GRAY_TEXT
    badge_d = round(28 * scale)
    detail_html = f'<div style="font-size:{9.5*scale:.1f}pt;color:{detail_color};margin-top:{round(3*scale)}px;">{_esc(detail)}</div>' if detail else ""
    return (
        f'<table style="width:100%;border-collapse:collapse;margin-bottom:{round(14*scale)}px;" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="width:{badge_d + 12}px;vertical-align:top;padding:0 12px 0 0;">{_badge(number, color, size=f"{badge_d}px", font_size=f"{11*scale:.1f}pt")}</td>'
        f'<td style="vertical-align:top;padding:0;">'
        f'<div style="font-weight:700;font-size:{11.5*scale:.1f}pt;color:{title_color};">{_esc(title)}</div>{detail_html}'
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
    #
    # RANCANG ULANG (target WeasyPrint, lihat catatan di _ivory_panel): height eksplisit &
    # larangan padding vertikal DIHAPUS — WeasyPrint mengukur tinggi baris dari konten asli,
    # jadi padding di sini AMAN dipakai lagi (dan malah dibutuhkan supaya jarak antar bar
    # lapang, bukan mepet). Kolom label dilebarkan 100px -> 150px supaya label 2 kata umum
    # (mis. "Pengadaan Langsung") muat 1 baris — SEBELUMNYA wrap jadi 2 baris & bikin baris
    # antar-bar terlihat tidak sejajar/rapi.
    max_val = max(values) if values else 1
    rows = []
    for i, (cat, val) in enumerate(zip(categories, values)):
        pct = round(val / max_val * 100, 1) if max_val else 0
        pct = max(pct, 1.5) if val else 0
        color = colors[i] if colors else GREEN_MAIN
        fill_html = (
            f'<table style="width:{pct}%;" cellpadding="0" cellspacing="0"><tr>'
            f'<td style="background:{color};height:18px;border-radius:4px;font-size:1px;line-height:18px;">&nbsp;</td>'
            f'</tr></table>'
            if pct else ""
        )
        rows.append(
            f'<tr>'
            f'<td style="width:150px;font-size:9.5pt;color:{TEXT_DARK};vertical-align:middle;padding:7pt 10pt 7pt 0;">{_esc(cat)}</td>'
            f'<td style="vertical-align:middle;padding:7pt 10pt 7pt 0;">'
            f'<div style="background:#EEEEEE;border-radius:4px;">{fill_html}</div>'
            f'</td>'
            f'<td style="width:36px;text-align:right;font-weight:700;font-size:9.5pt;color:{TEXT_DARK};vertical-align:middle;padding:7pt 0;">{val:g}</td>'
            f'</tr>'
        )
    return f'<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0">{"".join(rows)}</table>'


def _vertical_bar_chart_html(categories, values, color=None, height_pt=90) -> str:
    """Kolom vertikal per periode (mis. per bulan/minggu) — BEDA dari _bar_chart_html di atas
    (baris horizontal, cocok utk ranking kategori) karena data deret waktu lebih wajar dibaca
    kiri-ke-kanan mengikuti urutan waktu, bukan ditumpuk per baris. Tinggi tiap bar dihitung
    eksplisit dlm PT (bukan CSS %) — angkanya dihitung di Python lalu ditempel sbg nilai
    literal, pola yang sama dipakai konsisten di seluruh file ini, supaya tidak butuh flexbox
    (tidak didukung xhtml2pdf) atau parent dgn height eksplisit yang rumit di table cell."""
    max_val = max(values) if values else 1
    bar_color = color or GREEN_MAIN
    n = len(categories) or 1
    col_w = round(100 / n, 3)
    bar_cells = []
    label_cells = []
    for cat, val in zip(categories, values):
        bar_h = round((val / max_val) * (height_pt - 16), 1) if max_val else 0
        bar_h = max(bar_h, 2) if val else 0
        bar_cells.append(
            f'<td style="width:{col_w}%;text-align:center;vertical-align:bottom;height:{height_pt}pt;padding:0 3pt;">'
            f'<div style="font-size:7.5pt;font-weight:700;color:{TEXT_DARK};margin-bottom:3pt;">{val:g}</div>'
            f'<div style="background:{bar_color};height:{bar_h}pt;border-radius:3px 3px 0 0;"></div>'
            f'</td>'
        )
        label_cells.append(
            f'<td style="width:{col_w}%;text-align:center;font-size:7pt;color:{GRAY_TEXT};padding-top:4pt;">{_esc(cat)}</td>'
        )
    return (
        f'<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0">'
        f'<tr>{"".join(bar_cells)}</tr>'
        f'<tr>{"".join(label_cells)}</tr>'
        f'</table>'
    )


def _stacked_proportion_bar_html(values, colors=None, height_px=46) -> str:
    """Alternatif visual KETIGA (selain _bar_chart_html/_donut_chart_svg) — satu batang
    penuh dibagi proporsional per kategori (gaya "100% stacked bar"), dipasangkan dengan
    panel legend eksternal (sama seperti pola donut, lihat pemanggilnya) — titik variasi
    tampilan tambahan supaya laporan tidak melulu bar-per-baris atau donut. Segmen dibangun
    dari <table style="width:{pct}%"> BERJAJAR SATU BARIS (trik lebar-persen yang sama
    dengan _bar_chart_html — BUKAN flexbox, yang belum pernah dites di file ini)."""
    total = sum(values) or 1
    cells = []
    for i, val in enumerate(values):
        pct = (val / total * 100) if total else 0
        color = colors[i] if colors else CATEGORY_COLOR_RAMP[i % len(CATEGORY_COLOR_RAMP)]
        if pct > 0:
            cells.append(
                f'<td style="width:{pct:.3f}%;background:{color};height:{height_px}px;'
                f'font-size:1px;line-height:1px;">&nbsp;</td>'
            )
    bar_html = (
        f'<div style="border-radius:10px;overflow:hidden;">'
        f'<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0">'
        f'<tr>{"".join(cells)}</tr></table></div>'
    )
    return f'<div style="padding:14pt 0;">{bar_html}</div>'


def _donut_chart_svg(values, colors=None, size=210, stroke_w=36, label_color=None, sub_color=None) -> str:
    """Alternatif visual utk distribusi kategori (selain _bar_chart_html) — titik variasi
    tampilan antar generate (lihat `category_style` di generate_pdf_report), BUKAN
    penggantian permanen. Donut cincin dibangun dari beberapa <circle> bertumpuk dengan
    stroke-dasharray/-dashoffset (trik SVG standar), bukan wedge/pie asli — lebih sederhana &
    hasilnya tetap rapi utk kategori sampai ~6 nilai. SVG dirender native oleh WeasyPrint,
    tidak perlu library chart eksternal (Kaleido/Plotly SENGAJA tidak dipakai lagi di file
    ini, lihat docstring atas). `label_color`/`sub_color` opsional (default TEXT_DARK/GRAY_TEXT
    cocok utk panel terang) — dipakai panel BERLATAR GELAP (mis. Ringkasan Eksekutif) supaya
    label pusat tidak nyaris tak kelihatan di atas latar gelap."""
    label_color = label_color or TEXT_DARK
    sub_color = sub_color or GRAY_TEXT
    total = sum(values) or 1
    r = (size - stroke_w) / 2
    cx = cy = size / 2
    circumference = 2 * math.pi * r
    segments = []
    offset = 0.0
    for i, val in enumerate(values):
        frac = val / total if total else 0
        dash = frac * circumference
        color = colors[i] if colors else CATEGORY_COLOR_RAMP[i % len(CATEGORY_COLOR_RAMP)]
        if dash > 0:
            segments.append(
                f'<circle cx="{cx}" cy="{cy}" r="{r:.2f}" fill="none" stroke="{color}" '
                f'stroke-width="{stroke_w}" stroke-dasharray="{dash:.2f} {circumference - dash:.2f}" '
                f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 {cx} {cy})" />'
            )
        offset += dash
    labels = (
        f'<text x="{cx}" y="{cy - 4}" text-anchor="middle" font-size="28" font-weight="700" '
        f'fill="{label_color}" font-family="{BODY_FONT}">{total:g}</text>'
        f'<text x="{cx}" y="{cy + 18}" text-anchor="middle" font-size="10.5" fill="{sub_color}" '
        f'font-family="{BODY_FONT}">Total</text>'
    )
    svg = (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" '
        f'xmlns="http://www.w3.org/2000/svg">{"".join(segments)}{labels}</svg>'
    )
    return f'<div style="text-align:center;padding:14pt 0;">{svg}</div>'


def _gauge_chart_svg(value, max_value=100, label="", color=None, size=150, stroke_w=22) -> str:
    """Gauge/ring persentase — panel pendukung kecil (dynamic_section/key_findings, lihat
    _build_dynamic_section_block/_build_key_findings_block di bawah), TEKNIK SAMA PERSIS dgn
    _donut_chart_svg di atas (SVG circle + stroke-dasharray), cuma 2 segmen TETAP (terisi
    sebesar value/max_value + sisa abu-abu), bukan N kategori, dan label tengahnya angka
    persen besar (bukan total)."""
    pct = max(0.0, min(1.0, (value / max_value) if max_value else 0.0))
    r = (size - stroke_w) / 2
    cx = cy = size / 2
    circumference = 2 * math.pi * r
    dash = pct * circumference
    ring_color = color or GREEN_MAIN
    segments = (
        f'<circle cx="{cx}" cy="{cy}" r="{r:.2f}" fill="none" stroke="#EEEEEE" stroke-width="{stroke_w}" />'
        f'<circle cx="{cx}" cy="{cy}" r="{r:.2f}" fill="none" stroke="{ring_color}" stroke-width="{stroke_w}" '
        f'stroke-linecap="round" stroke-dasharray="{dash:.2f} {circumference - dash:.2f}" '
        f'transform="rotate(-90 {cx} {cy})" />'
    )
    value_text = (
        f'<text x="{cx}" y="{cy + 8}" text-anchor="middle" font-size="26" font-weight="700" '
        f'fill="{TEXT_DARK}" font-family="{BODY_FONT}">{round(value):g}%</text>'
    )
    svg = (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" '
        f'xmlns="http://www.w3.org/2000/svg">{segments}{value_text}</svg>'
    )
    label_html = (
        f'<div style="font-size:9pt;color:{GRAY_TEXT};margin-top:4pt;">{_esc(label)}</div>' if label else ""
    )
    return f'<div style="text-align:center;padding:10pt 0;">{svg}{label_html}</div>'


# ============================================================================
# 5 chart BARU — bentuk visual dipilih sesuai KARAKTER data (bukan default bar/donut utk
# semua, lihat report_render_logic.py): deret waktu -> bar+line kumulatif, skor multi-domain
# -> radar, pola per hari/jam -> heatmap grid, perbandingan 2 periode -> grouped bar, alur
# bertingkat -> funnel. Tiap fungsi punya jalur non-SVG (SVG_SUPPORTED=False, lihat definisi
# di atas) utk xhtml2pdf yang tidak bisa merender <svg> inline dgn andal.
# ============================================================================
def _darken(hex_color: str, factor: float = 0.55) -> str:
    """Skala RGB `hex_color` turun sebesar `factor` (menuju hitam, BUKAN blend ke abu-abu) —
    dipakai turunkan "bg" (latar halaman gelap penuh: cover/penutup) dari warna KUSTOM yang
    dipilih user (color picker), mengikuti pola yang sama dgn 4 tema bernama (mis. GREEN_BG
    ~0.5-0.6x GREEN_MAIN, lihat THEME_PALETTES). BUG NYATA DITEMUKAN (dilaporkan user, "kok
    ga diterapkan"): "bg" tema kustom SEBELUMNYA SELALU "#111827" (navy gelap generik) apa
    pun warna yang dipilih — halaman cover/penutup (kesan PERTAMA laporan, yang paling
    mungkin dilihat user duluan) jadi terlihat sama sekali tidak terpengaruh pilihan
    warnanya, padahal halaman isi (kartu KPI, chart) sebenarnya SUDAH ikut warna kustom."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"#{round(r * factor):02x}{round(g * factor):02x}{round(b * factor):02x}"


def _blend_with_white(hex_color: str, frac: float) -> str:
    """Campur `hex_color` dgn putih sebesar (1-frac) jadi warna solid baru — dipakai fallback
    heatmap non-SVG (warna blended SUNGGUHAN, bukan CSS `opacity` yang tidak selalu didukung
    xhtml2pdf)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    frac = max(0.0, min(1.0, frac))
    r = round(r * frac + 255 * (1 - frac))
    g = round(g * frac + 255 * (1 - frac))
    b = round(b * frac + 255 * (1 - frac))
    return f"#{r:02x}{g:02x}{b:02x}"


def _light_safe(hex_color: str, max_luminance: float = 0.68) -> str:
    """Pastikan `hex_color` cukup gelap dipakai sbg WARNA ISI/teks di atas latar TERANG
    (IVORY/putih). BUG NYATA DITEMUKAN (dilaporkan user, tema "gold" khususnya): peran
    "light"/"soft" tiap tema (ctx.accent_light/accent_soft) SENGAJA pucat krn awalnya cuma
    dipakai sbg teks di atas latar GELAP (mis. kicker cover) — utk tema green/navy/dark,
    "light"=GOLD_MAIN & "soft"=GOLD_LIGHT (lumayan gelap, kontras tetap oke dipakai ulang di
    latar terang). Tapi utk tema "gold" sendiri, "light"/"soft"-nya (GOLD_CREAM_LIGHT/SOFT)
    JAUH lebih pucat drpd tema lain (dirancang utk kontras di atas latar gelap coklat-emas
    tema itu) — dipakai ulang apa adanya sbg warna bar/segmen chart di atas kartu IVORY hasilnya
    nyaris tak kelihatan (2 warna pucat berdempetan). Cuma menggelapkan PROPORSIONAL (hue
    tetap sama) kalau luminance-nya di atas ambang — TIDAK mengubah apa pun utk warna yang
    sudah cukup gelap (green/navy/dark tetap identik seperti sebelumnya)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    if luminance <= max_luminance or luminance == 0:
        return hex_color
    frac = max_luminance / luminance
    return f"#{round(r * frac):02x}{round(g * frac):02x}{round(b * frac):02x}"


def _bar_line_chart_html_fallback(categories, values, cumulative, color) -> str:
    return _vertical_bar_chart_html(categories, values, color=color or GREEN_MAIN, height_pt=90)


def _bar_line_chart_svg(categories, values, cumulative=None, color=None, size_w=480, size_h=180) -> str:
    """Deret waktu -> batang (nilai per periode) + garis kumulatif. Kedua seri dinormalisasi
    ke tinggi chart yang SAMA scr independen (bukan 2 sumbu numerik sungguhan) — cukup utk
    menunjukkan bentuk tren & akumulasi bersamaan tanpa kerumitan sumbu ganda."""
    if not SVG_SUPPORTED:
        return _bar_line_chart_html_fallback(categories, values, cumulative, color)
    bar_color = color or GREEN_MAIN
    line_color = GOLD_MAIN
    n = len(categories) or 1
    # pad_t dinaikkan (12 -> 22) supaya ada ruang utk label angka di atas batang tertinggi
    # (BUG YANG DIPERBAIKI, dilaporkan user: chart ini dulu sama sekali tidak menampilkan
    # angka, beda dgn chart lain di laporan yang sudah menampilkan nilainya).
    pad_l, pad_r, pad_t, pad_b = 8, 8, 22, 22
    plot_w, plot_h = size_w - pad_l - pad_r, size_h - pad_t - pad_b
    col_w = plot_w / n
    max_val = max(values) if values and max(values) else 1
    max_cum = max(cumulative) if cumulative and max(cumulative) else 0
    bars, points, labels = [], [], []
    for i, (cat, val) in enumerate(zip(categories, values)):
        bar_h = (val / max_val) * (plot_h - 8) if max_val else 0
        x = pad_l + i * col_w
        y = pad_t + (plot_h - bar_h)
        bars.append(f'<rect x="{x + col_w*0.18:.1f}" y="{y:.1f}" width="{col_w*0.64:.1f}" height="{bar_h:.1f}" fill="{bar_color}" rx="2" />')
        if val:
            bars.append(f'<text x="{x + col_w/2:.1f}" y="{max(y - 4, 10):.1f}" text-anchor="middle" font-size="7.5" fill="{TEXT_DARK}" font-family="{BODY_FONT}">{val}</text>')
        if max_cum:
            cy = pad_t + plot_h - ((cumulative[i] / max_cum) * (plot_h - 4))
            points.append((x + col_w / 2, cy))
        labels.append(f'<text x="{x + col_w/2:.1f}" y="{size_h - 6}" text-anchor="middle" font-size="7.5" fill="{GRAY_TEXT}" font-family="{BODY_FONT}">{_esc(cat)}</text>')
    line_html = dots = ""
    if points:
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        line_html = f'<polyline points="{poly}" fill="none" stroke="{line_color}" stroke-width="2.5" />'
        dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="{line_color}" />' for x, y in points)
    svg = (
        f'<svg width="{size_w}" height="{size_h}" viewBox="0 0 {size_w} {size_h}" xmlns="http://www.w3.org/2000/svg">'
        f'{"".join(bars)}{line_html}{dots}{"".join(labels)}</svg>'
    )
    return f'<div style="text-align:center;">{svg}</div>'


def _radar_chart_html_fallback(axes, values, color=None) -> str:
    return _bar_chart_html(axes, values, colors=[color or GREEN_MAIN] * len(values))


def _radar_chart_svg(axes, values, color=None, size=360, label_margin=100) -> str:
    """Skor multi-indikator (nilai 0-100, sudah dinormalisasi di report_render_logic.py) —
    tiap sumbu ditarik dari pusat, poligon menghubungkan titik nilai tiap sumbu. Margin label
    (size/2 - r_max) SENGAJA lapang (default 100px) — label sumbu (mis. "Skor Ketepatan
    Waktu") bisa cukup panjang & SVG tidak membungkus teks otomatis, kalau margin terlalu
    sempit teks kepotong di tepi viewBox (bug nyata yang pernah terjadi sebelum nilai ini
    diperbesar). `label_margin` bisa dikecilkan (lihat tile dashboard management report di
    _mgmt_tile_chart_html) supaya ring tetap punya radius wajar di kanvas yang lebih kecil —
    WAJIB size/2 > label_margin, kalau tidak r_max negatif & chart-nya rusak/terbalik."""
    if not SVG_SUPPORTED:
        return _radar_chart_html_fallback(axes, values, color)
    n = len(axes)
    if n < 3:
        return ""
    ring_color = color or GREEN_MAIN
    cx = cy = size / 2
    r_max = size / 2 - label_margin

    def _angle(i):
        return (-90 + i * 360 / n) * math.pi / 180

    rings = "".join(
        f'<polygon points="{" ".join(f"{cx + r_max*frac*math.cos(_angle(i)):.1f},{cy + r_max*frac*math.sin(_angle(i)):.1f}" for i in range(n))}" '
        f'fill="none" stroke="{PANEL_BORDER}" stroke-width="1" />'
        for frac in (0.25, 0.5, 0.75, 1.0)
    )
    spokes = "".join(
        f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{cx + r_max*math.cos(_angle(i)):.1f}" y2="{cy + r_max*math.sin(_angle(i)):.1f}" '
        f'stroke="{PANEL_BORDER}" stroke-width="1" />'
        for i in range(n)
    )
    pts = [(cx + r_max * (max(0.0, min(100.0, v)) / 100) * math.cos(_angle(i)), cy + r_max * (max(0.0, min(100.0, v)) / 100) * math.sin(_angle(i))) for i, v in enumerate(values)]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    shape = f'<polygon points="{poly}" fill="{ring_color}" fill-opacity="0.25" stroke="{ring_color}" stroke-width="2" />'
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{ring_color}" />' for x, y in pts)
    labels = []
    for i, ax in enumerate(axes):
        lx, ly = cx + (r_max + 20) * math.cos(_angle(i)), cy + (r_max + 20) * math.sin(_angle(i))
        anchor = "start" if math.cos(_angle(i)) > 0.3 else ("end" if math.cos(_angle(i)) < -0.3 else "middle")
        labels.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" font-size="8.5" fill="{TEXT_DARK}" font-family="{BODY_FONT}">{_esc(ax)}</text>')
    svg = (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">'
        f'{rings}{spokes}{shape}{dots}{"".join(labels)}</svg>'
    )
    return f'<div style="text-align:center;padding:6pt 0;">{svg}</div>'


def _heatmap_grid_html_fallback(day_labels, hour_labels, grid, color=None) -> str:
    base = color or GREEN_MAIN
    max_val = max((v for row in grid for v in row), default=0) or 1
    header = "".join(f'<th style="font-size:7pt;color:{GRAY_TEXT};padding:2pt;font-weight:400;">{_esc(hl)}</th>' for hl in hour_labels)
    rows = []
    for day_label, row_vals in zip(day_labels, grid):
        cells = []
        for val in row_vals:
            blended = _blend_with_white(base, 0.15 + 0.85 * (val / max_val))
            text_color = "#fff" if (val / max_val) > 0.45 else TEXT_DARK
            cells.append(f'<td style="background:{blended};text-align:center;font-size:7pt;color:{text_color};padding:6pt 2pt;border-radius:3px;">{val or ""}</td>')
        rows.append(f'<tr><td style="font-size:7.5pt;color:{TEXT_DARK};padding:2pt 6pt 2pt 0;text-align:right;white-space:nowrap;">{_esc(day_label)}</td>{"".join(cells)}</tr>')
    return f'<table style="border-collapse:separate;border-spacing:2px;margin:0 auto;"><tr><td></td>{header}</tr>{"".join(rows)}</table>'


def _heatmap_grid_svg(day_labels, hour_labels, grid, color=None, cell=32) -> str:
    """Grid hari x blok jam — warna sel makin pekat makin sering kejadian di kombinasi
    hari/jam itu (skala linear thd nilai maksimum grid), dipakai utk pola per hari/jam."""
    if not SVG_SUPPORTED:
        return _heatmap_grid_html_fallback(day_labels, hour_labels, grid, color)
    base = color or GREEN_MAIN
    max_val = max((v for row in grid for v in row), default=0) or 1
    label_w, n_cols, n_rows = 46, len(hour_labels), len(day_labels)
    w, h = label_w + n_cols * cell, 16 + n_rows * cell
    parts = [f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">']
    for c, hl in enumerate(hour_labels):
        x = label_w + c * cell + cell / 2
        parts.append(f'<text x="{x:.1f}" y="10" text-anchor="middle" font-size="7" fill="{GRAY_TEXT}" font-family="{BODY_FONT}">{_esc(hl)}</text>')
    for r, day_label in enumerate(day_labels):
        y = 16 + r * cell
        parts.append(f'<text x="{label_w - 6}" y="{y + cell/2 + 3:.1f}" text-anchor="end" font-size="7.5" fill="{TEXT_DARK}" font-family="{BODY_FONT}">{_esc(day_label)}</text>')
        for c in range(n_cols):
            val = grid[r][c]
            opacity = 0.1 + 0.8 * (val / max_val)
            x = label_w + c * cell
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell-2}" height="{cell-2}" rx="3" fill="{base}" fill-opacity="{opacity:.2f}" />')
            if val:
                tc = "#fff" if opacity > 0.5 else TEXT_DARK
                parts.append(f'<text x="{x+cell/2-1:.1f}" y="{y+cell/2+2:.1f}" text-anchor="middle" font-size="7.5" fill="{tc}" font-family="{BODY_FONT}">{val}</text>')
    parts.append("</svg>")
    return f'<div style="text-align:center;">{"".join(parts)}</div>'


def _grouped_bar_chart_html_fallback(categories, series_a, series_b, label_a, label_b, color_a, color_b) -> str:
    ca, cb = color_a or GREEN_MAIN, color_b or GOLD_MAIN
    max_val = max([*series_a, *series_b], default=0) or 1
    rows = []
    for cat, a, b in zip(categories, series_a, series_b):
        pa = max(round(a / max_val * 100, 1), 2) if a else 0
        pb = max(round(b / max_val * 100, 1), 2) if b else 0
        rows.append(
            f'<tr><td style="font-size:8pt;color:{TEXT_DARK};padding:8pt 8pt 0 0;">{_esc(cat)}</td></tr>'
            f'<tr><td style="padding:0 0 6pt 0;">'
            f'<div style="background:{ca};height:10px;width:{pa}%;border-radius:3px;margin-bottom:2px;"></div>'
            f'<div style="background:{cb};height:10px;width:{pb}%;border-radius:3px;"></div>'
            f'</td></tr>'
        )
    legend = (
        f'<div style="font-size:8pt;color:{GRAY_TEXT};margin-top:4pt;">'
        f'<span style="display:inline-block;width:8px;height:8px;background:{ca};margin-right:4px;"></span>{_esc(label_a)}'
        f'<span style="display:inline-block;width:8px;height:8px;background:{cb};margin:0 4px 0 14px;"></span>{_esc(label_b)}</div>'
    )
    return f'<table style="width:100%;border-collapse:collapse;">{"".join(rows)}</table>{legend}'


def _grouped_bar_chart_svg(categories, series_a, series_b, label_a="", label_b="", color_a=None, color_b=None, size_w=480, size_h=190) -> str:
    """Perbandingan 2 periode/seri per kategori (mis. paruh awal vs paruh akhir) — 2 batang
    berdampingan per kategori, BUKAN ditumpuk (stacked), supaya perbandingan besarannya
    langsung terlihat sejajar."""
    if not SVG_SUPPORTED:
        return _grouped_bar_chart_html_fallback(categories, series_a, series_b, label_a, label_b, color_a, color_b)
    ca, cb = color_a or GREEN_MAIN, color_b or GOLD_MAIN
    n = len(categories) or 1
    # pad_t dinaikkan (10 -> 20) supaya ada ruang utk label angka di atas tiap batang (BUG
    # YANG DIPERBAIKI, dilaporkan user: chart perbandingan periode ini dulu tidak
    # menampilkan angka sama sekali, cuma bentuk batang tanpa nilai).
    pad_l, pad_r, pad_t, pad_b = 8, 8, 20, 22
    plot_w, plot_h = size_w - pad_l - pad_r, size_h - pad_t - pad_b
    group_w = plot_w / n
    bar_w = group_w * 0.32
    max_val = max([*series_a, *series_b], default=0) or 1
    parts = [f'<svg width="{size_w}" height="{size_h}" viewBox="0 0 {size_w} {size_h}" xmlns="http://www.w3.org/2000/svg">']
    for i, cat in enumerate(categories):
        gx = pad_l + i * group_w
        ha = (series_a[i] / max_val) * (plot_h - 6) if max_val else 0
        hb = (series_b[i] / max_val) * (plot_h - 6) if max_val else 0
        xa = gx + group_w * 0.14
        xb = xa + bar_w + 4
        ya, yb = pad_t + plot_h - ha, pad_t + plot_h - hb
        parts.append(f'<rect x="{xa:.1f}" y="{ya:.1f}" width="{bar_w:.1f}" height="{ha:.1f}" fill="{ca}" rx="2" />')
        parts.append(f'<rect x="{xb:.1f}" y="{yb:.1f}" width="{bar_w:.1f}" height="{hb:.1f}" fill="{cb}" rx="2" />')
        if series_a[i]:
            parts.append(f'<text x="{xa + bar_w/2:.1f}" y="{max(ya - 4, 10):.1f}" text-anchor="middle" font-size="7" fill="{TEXT_DARK}" font-family="{BODY_FONT}">{series_a[i]}</text>')
        if series_b[i]:
            parts.append(f'<text x="{xb + bar_w/2:.1f}" y="{max(yb - 4, 10):.1f}" text-anchor="middle" font-size="7" fill="{TEXT_DARK}" font-family="{BODY_FONT}">{series_b[i]}</text>')
        parts.append(f'<text x="{gx + group_w/2:.1f}" y="{size_h - 6}" text-anchor="middle" font-size="7.5" fill="{GRAY_TEXT}" font-family="{BODY_FONT}">{_esc(cat)}</text>')
    parts.append("</svg>")
    legend = (
        f'<div style="font-size:8pt;color:{GRAY_TEXT};margin-top:4pt;">'
        f'<span style="display:inline-block;width:8px;height:8px;background:{ca};margin-right:4px;"></span>{_esc(label_a)}'
        f'<span style="display:inline-block;width:8px;height:8px;background:{cb};margin:0 4px 0 14px;"></span>{_esc(label_b)}</div>'
    )
    return f'<div style="text-align:center;">{"".join(parts)}{legend}</div>'


def _funnel_chart_html_fallback(categories, values, color=None) -> str:
    return _bar_chart_html(categories, values, colors=[color or GREEN_MAIN] * len(values))


def _funnel_chart_svg(categories, values, color=None, size_w=320, size_h=200) -> str:
    """Alur bertingkat (mis. status penanganan Open -> Investigating -> Resolved) — batang
    melebar/menyempit sesuai proporsi tiap tahap, ditumpuk vertikal dari terbesar ke terkecil."""
    if not SVG_SUPPORTED:
        return _funnel_chart_html_fallback(categories, values, color)
    base = color or GREEN_MAIN
    n = len(categories) or 1
    max_val = max(values) if values else 1
    row_h = (size_h - 10) / n
    parts = [f'<svg width="{size_w}" height="{size_h}" viewBox="0 0 {size_w} {size_h}" xmlns="http://www.w3.org/2000/svg">']
    for i, (cat, val) in enumerate(zip(categories, values)):
        frac = (val / max_val) if max_val else 0
        w = max(size_w * 0.22, size_w * frac)
        x, y = (size_w - w) / 2, i * row_h
        opacity = 0.45 + 0.55 * (1 - i / max(n - 1, 1))
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{row_h - 6:.1f}" fill="{base}" fill-opacity="{opacity:.2f}" rx="4" />')
        parts.append(
            f'<text x="{size_w/2:.1f}" y="{y + row_h/2 - 1:.1f}" text-anchor="middle" font-size="9" font-weight="700" '
            f'fill="#fff" font-family="{BODY_FONT}">{_esc(cat)} &#183; {val:g}</text>'
        )
    parts.append("</svg>")
    return f'<div style="text-align:center;">{"".join(parts)}</div>'


def _ivory_panel(icon_text, title_text, rows_html, footnote=None, theme: dict | None = None) -> str:
    t = theme or THEME_PALETTES["green"]
    # RANCANG ULANG (target WeasyPrint, engine utama sejak WeasyPrint aktif — lihat
    # FONT_ATTR_QUOTE_BUG_NOTE di atas untuk riwayat kenapa file ini tadinya penuh workaround
    # height eksplisit): dikonfirmasi lewat isolasi render+sampling bahwa WeasyPrint (BEDA dari
    # xhtml2pdf) menangani tabel bersarang TANPA height eksplisit dengan BENAR — tiap baris
    # tingginya mengikuti konten aslinya (baris pendek tetap pendek, baris dengan value panjang
    # wrap otomatis jadi lebih tinggi), dan TIDAK diregangkan mengisi sisa halaman. Jadi seluruh
    # height eksplisit/row_budget dihapus di sini — panel jadi SEPADAT kontennya sendiri (bukan
    # dipaksa setinggi anggaran terburuk), sekaligus menghindari kelas bug shrink xhtml2pdf sama
    # sekali karena tidak ada lagi kombinasi padding+height eksplisit di mana pun dalam fungsi ini.
    footnote_html = ""
    if footnote:
        footnote_html = (
            f'<div style="border-top:1px solid {PANEL_BORDER};margin-top:12px;padding-top:10px;'
            f'font-size:8.5pt;font-style:italic;color:{GRAY_TEXT};">{_esc(footnote)}</div>'
        )
    header_html = (
        f'<table style="width:100%;margin-bottom:10px;" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="width:30px;vertical-align:middle;">{_badge(icon_text, t["light"], size="22px", font_size="9pt")}</td>'
        f'<td style="vertical-align:middle;padding:0 0 0 6px;">'
        f'<span style="font-weight:700;font-size:10.5pt;color:{t["main"]};text-transform:uppercase;">{_esc(title_text)}</span>'
        f'</td></tr></table>'
    )
    # BUG BESAR YANG DIPERBAIKI: atribut HTML `cellpadding` TERBUKTI (isolasi render+sampling,
    # ekstraksi posisi teks aktual dari PDF) TIDAK dihormati WeasyPrint di sini — konten panel
    # menempel rata ke tepi border/rounded-corner (inset 0), bukan diberi jarak 16px seperti
    # diminta. Diganti CSS `padding` langsung pada <td> (didukung penuh & terverifikasi benar).
    return (
        f'<table style="width:100%;background:{IVORY};border:1px solid {PANEL_BORDER};border-radius:10px;">'
        f'<tr><td style="vertical-align:top;padding:16pt;">{header_html}{rows_html}{footnote_html}</td></tr></table>'
    )


def _ivory_kv_rows(rows, theme: dict | None = None) -> str:
    t = theme or THEME_PALETTES["green"]
    # RANCANG ULANG: SEBELUMNYA label & value ditumpuk 2 baris per row (judul tebal, lalu value
    # di baris baru) — makan 2x tinggi vertikal dibanding perlu, dan bikin panel terlihat lebih
    # kosong/boros dibanding referensi. Sekarang label & value SEJAJAR dalam SATU baris (kolom
    # label lebar tetap, kolom value mengisi sisa lebar & wrap alami kalau panjang) — pola
    # "spec sheet" yang jauh lebih padat & rapi, sekaligus otomatis lebih pendek utk value
    # singkat (mis. "42 data") tanpa perlu tinggi baris tetap yang boros.
    trs = "".join(
        f'<tr>'
        f'<td style="width:118px;vertical-align:top;padding:5pt 10pt 5pt 0;font-size:9.5pt;font-weight:700;color:{t["main"]};">{_esc(label)}</td>'
        f'<td style="vertical-align:top;padding:5pt 0;font-size:9.5pt;color:{GRAY_TEXT};">{_esc(value)}</td>'
        f'</tr>'
        for label, value in rows
    )
    return f'<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0">{trs}</table>'


def _legend_rows(rows, theme: dict | None = None) -> str:
    t = theme or THEME_PALETTES["green"]
    parts = []
    for color, label, pct in rows:
        parts.append(
            f'<tr>'
            f'<td style="width:16px;vertical-align:middle;padding:6pt 0;">'
            f'<table cellpadding="0" cellspacing="0"><tr><td style="width:12px;height:12px;background:{color};font-size:1px;line-height:1px;">&nbsp;</td></tr></table>'
            f'</td>'
            f'<td style="padding:6pt 8pt;font-size:9.5pt;color:{TEXT_DARK};vertical-align:middle;">{_esc(label)}</td>'
            f'<td style="text-align:right;font-weight:700;font-size:9.5pt;color:{t["main"]};vertical-align:middle;padding:6pt 0;">{_esc(pct)}</td>'
            f'</tr>'
        )
    return f'<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0">{"".join(parts)}</table>'


def _dark_panel(inner_html, w="100%", theme: dict | None = None) -> str:
    # RANCANG ULANG (target WeasyPrint) — height eksplisit dihapus, panel sepadat kontennya.
    # cellpadding (atribut HTML) diganti CSS `padding` langsung — lihat catatan di _ivory_panel
    # soal cellpadding TERBUKTI tidak dihormati WeasyPrint (konten menempel ke border).
    t = theme or THEME_PALETTES["green"]
    return (
        f'<table style="width:{w};background:{t["bg"]};border:1px solid {t["light"]};border-radius:10px;">'
        f'<tr><td style="vertical-align:top;padding:18pt;">{inner_html}</td></tr></table>'
    )


def _critical_highlight_panel(pct_text, sub_text, detail_text=None, theme: dict | None = None, value_color=None) -> str:
    """`value_color` opsional (default None = t["light"] spt semula) — dipakai kartu tren
    berarah panah (dynamic_section "Trend Analysis", lihat _build_dynamic_section_block) utk
    mewarnai angka besar sesuai arah naik/turun/datar, TANPA mengubah tampilan pemanggil lain
    (severity_distribution, aux_stat biasa) yang tetap pakai t["light"] default."""
    t = theme or THEME_PALETTES["green"]
    value_color = value_color or t["light"]
    detail_html = f'<div style="font-size:9.5pt;color:{t["soft"]};margin-top:14px;">{_esc(detail_text)}</div>' if detail_text else ""
    inner = (
        f'<div style="text-align:center;font-family:{TITLE_FONT};font-weight:700;font-size:34pt;color:{value_color};">{_esc(pct_text)}</div>'
        f'<div style="text-align:center;font-size:10.5pt;color:#fff;margin-top:6px;">{_esc(sub_text)}</div>'
        f'{detail_html}'
    )
    return _dark_panel(inner, theme=theme)


def _bullet_lines_html(text, theme: dict | None = None, font_pt=9) -> str:
    """Baris bullet polos (titik warna aksen + teks), TANPA bungkus kotak/judul — dipakai
    _note_box_html di bawah (mode penuh) DAN tile insight_dashboard (mode ringkas, sudah
    dibungkus kartu bordered sendiri, kotak-dalam-kotak kalau dipakaikan _note_box_html utuh
    lagi di situ)."""
    t = theme or THEME_PALETTES["green"]
    lines = [l for l in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if l]
    if not lines:
        return ""
    rows = "".join(
        f'<tr>'
        f'<td style="width:11pt;vertical-align:top;padding:2pt 4pt 2pt 0;color:{t["main"]};font-weight:700;font-size:{font_pt}pt;">&#8226;</td>'
        f'<td style="vertical-align:top;padding:2pt 0;font-size:{font_pt}pt;color:{GRAY_TEXT};">{_esc(line)}</td>'
        f'</tr>'
        for line in lines
    )
    return f'<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0">{rows}</table>'


def _note_box_html(text, theme: dict | None = None, title: str | None = None) -> str:
    """Kotak "Catatan:" (border kiri warna aksen + bullet per kalimat) — GANTI dari
    _ai_insight_strip lama (1 baris italic polos) supaya caption AI terasa seperti kotak
    catatan di laporan referensi, BUKAN paragraf mengalir biasa (temuan user: laporan masih
    terasa "berat kata-kata" meski chart-nya sudah ada). Dipakai di SEMUA titik caption chart
    (kategori/severity/status) & dynamic_section."""
    t = theme or THEME_PALETTES["green"]
    rows_html = _bullet_lines_html(text, theme=t)
    if not rows_html:
        return ""
    label = title or "Catatan"
    return (
        f'<div style="background:{IVORY};border-left:3px solid {t["main"]};border-radius:6px;padding:9pt 12pt;margin-top:10pt;">'
        f'<div style="font-size:8pt;font-weight:700;text-transform:uppercase;letter-spacing:0.6px;color:{t["main"]};margin-bottom:4pt;">{_esc(label)}:</div>'
        f'{rows_html}'
        f'</div>'
    )


def _priority_panel(title_text, items, theme: dict | None = None) -> str:
    # RANCANG ULANG (target WeasyPrint, lihat catatan di _ivory_panel) — height eksplisit
    # dihapus di semua level, padding antar baris dipakai langsung (aman sekarang karena tidak
    # ada lagi height eksplisit yang bisa dikombinasikan jadi trigger shrink xhtml2pdf), dan
    # panel dibangun lewat `_dark_panel()` yang sama dipakai panel gelap lain (konsisten).
    t = theme or THEME_PALETTES["green"]
    rows = "".join(
        f'<tr>'
        f'<td style="width:32px;vertical-align:top;padding:9pt 0;">{_badge(letter, t["light"], size="24px", font_size="10pt")}</td>'
        f'<td style="vertical-align:top;padding:9pt 0 9pt 10px;font-size:10.5pt;color:#fff;">{_esc(text)}</td>'
        f'</tr>'
        for letter, text in items
    )
    rows_table = f'<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0">{rows}</table>'
    inner = (
        f'<div style="font-size:9.5pt;font-weight:700;letter-spacing:1px;text-transform:uppercase;'
        f'color:{t["light"]};margin-bottom:6px;">{_esc(title_text)}</div>{rows_table}'
    )
    return _dark_panel(inner, theme=theme)


def _pill(text, theme: dict | None = None) -> str:
    t = theme or THEME_PALETTES["green"]
    return (
        f'<div style="background:{t["main"]};border:1px solid {t["light"]};border-radius:999px;'
        f'padding:10px 16px;text-align:center;font-weight:700;font-size:10.5pt;color:{t["light"]};margin-bottom:10px;">'
        f'{_esc(text)}</div>'
    )


def _card_grid(cell_inner_htmls: list, cols: int) -> str:
    """Susun daftar HTML kartu jadi grid N kolom pakai <table> (bukan flexbox/grid CSS —
    tidak didukung xhtml2pdf, fallback engine kalau WeasyPrint tak tersedia).

    RANCANG ULANG (target WeasyPrint, lihat catatan di _ivory_panel): height eksplisit &
    workaround gap-lewat-row_height DIHAPUS — cukup andalkan perilaku standar tabel HTML:
    tiap baris otomatis setinggi kartu TERTINGGI di baris itu (bukan tinggi tetap sepihak),
    dan kartu-kartu dengan konten pendek TIDAK LAGI dipaksa setinggi kartu dengan konten
    terpanjang yang mungkin pernah ada — mengurangi ruang kosong raksasa dalam kartu jauh
    lebih baik daripada budget height tetap manapun. Jarak antar baris dari margin-bottom
    pada kartu itu sendiri (lihat _stat_card_grid/_asset_card_row), bukan dari grid ini.
    """
    # BUG DIPERBAIKI: kartu dengan jumlah item < cols (mis. tepat 1 rekomendasi/1 stat) dulu
    # tetap dihitung sebagai 1-dari-N kolom (mis. 33% lebar utk grid 3-kolom), menyisakan
    # sel kosong di sampingnya — kartu jadi sempit di tengah ruang lebar yang tidak terisi.
    # effective_cols dihitung dari jumlah item SEBENARNYA (dibatasi max `cols`) supaya kartu
    # melebar mengisi ruang yang tersedia kalau totalnya lebih sedikit dari kolom yang diminta.
    effective_cols = min(cols, len(cell_inner_htmls)) or cols
    col_w = round(100 / effective_cols, 3)
    cells = [f'<td style="width:{col_w}%;padding:0 6px;vertical-align:top;">{inner}</td>' for inner in cell_inner_htmls]
    rows = []
    for i in range(0, len(cells), effective_cols):
        row_cells = cells[i:i + effective_cols]
        while len(row_cells) < effective_cols:
            row_cells.append(f'<td style="width:{col_w}%;"></td>')
        rows.append(f'<tr>{"".join(row_cells)}</tr>')
    return f'<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0">{"".join(rows)}</table>'


def _stat_card_grid(items, cols=3, dark=True, theme: dict | None = None) -> str:
    t = theme or THEME_PALETTES["green"]
    bg = t["main"] if dark else IVORY
    label_color = WHITE if dark else TEXT_DARK
    cell_htmls = [
        f'<table style="width:100%;min-height:1.15in;margin-bottom:12pt;background:{bg};border:1px solid {t["light"]};border-radius:10px;"><tr><td style="text-align:center;vertical-align:middle;padding:14pt;">'
        f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:22pt;color:{t["light"]};">{_esc(value)}</div>'
        f'<div style="font-size:9pt;color:{label_color};margin-top:6px;">{_esc(label)}</div>'
        f'</td></tr></table>'
        for value, label in items
    ]
    return _card_grid(cell_htmls, cols)


def _asset_card_row(items, theme: dict | None = None) -> str:
    t = theme or THEME_PALETTES["green"]
    n = len(items) or 1
    cell_htmls = [
        f'<table style="width:100%;background:{t["main"]};border:1px solid {t["light"]};border-radius:10px;"><tr><td style="vertical-align:top;padding:18pt;">'
        f'{_badge(num, t["light"], size="34px", font_size="13pt")}'
        f'<div style="font-weight:700;font-size:12.5pt;color:#fff;margin-top:12px;">{_esc(title)}</div>'
        f'<div style="font-weight:700;font-size:10.5pt;color:{t["light"]};margin-top:4px;">{_esc(stat)}</div>'
        f'<div style="font-size:9pt;color:#E8ECE6;margin-top:10px;">{_esc(desc)}</div>'
        f'</td></tr></table>'
        for num, title, stat, desc in items
    ]
    return _card_grid(cell_htmls, n)


def _asset_ranked_bars_html(items, theme: dict | None = None) -> str:
    """Alternatif visual KETIGA (selain _asset_card_row/_podium_row) — daftar entitas
    berperingkat dengan batang proporsional horizontal per item (badge nomor + nama + batang
    + angka), BUKAN kartu kotak atau podium — titik variasi tampilan tambahan utk asset_cards
    (lihat `asset_style`). Dipakai utk jumlah item BERAPA PUN (podium hanya cocok tepat 3)."""
    t = theme or THEME_PALETTES["green"]
    max_count = max((it.get("count") or 0) for it in items) or 1
    rows = []
    for it in items:
        pct = round((it.get("count") or 0) / max_count * 100, 1)
        pct = max(pct, 4)
        rows.append(
            f'<tr><td style="padding:12pt 0;">'
            f'<table style="width:100%;" cellpadding="0" cellspacing="0"><tr>'
            f'<td style="width:40px;vertical-align:middle;">{_badge(it["num"], t["light"], size="32px", font_size="12pt")}</td>'
            f'<td style="vertical-align:middle;padding:0 14pt;">'
            f'<div style="font-weight:700;font-size:12pt;color:#fff;margin-bottom:8px;">{_esc(it["name"])}</div>'
            f'<table style="width:100%;background:{t["chart"]};border-radius:5px;" cellpadding="0" cellspacing="0"><tr>'
            f'<td style="width:{pct}%;">'
            f'<table style="width:100%;" cellpadding="0" cellspacing="0"><tr>'
            f'<td style="background:{t["light"]};height:12px;border-radius:5px;font-size:1px;line-height:1px;">&nbsp;</td>'
            f'</tr></table></td>'
            f'<td></td>'
            f'</tr></table>'
            f'</td>'
            f'<td style="width:95px;text-align:right;vertical-align:middle;font-weight:700;font-size:12pt;color:{t["light"]};">{_esc(it["stat"])}</td>'
            f'</tr></table>'
            f'</td></tr>'
        )
    return f'<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0">{"".join(rows)}</table>'


def _podium_row(items, theme: dict | None = None) -> str:
    """Alternatif visual utk top-3 entitas (asset_cards) — titik variasi tampilan (lihat
    `asset_style` di generate_pdf_report), BUKAN penggantian permanen. items: list of dict
    {"num","name","stat"} — dirender sebagai podium (rank 1 di tengah & paling tinggi, gaya
    "sorotan performa" mirip laporan KPI/produksi), bukan 3 kartu sejajar sama besar."""
    t = theme or THEME_PALETTES["green"]
    ranked = sorted(items, key=lambda it: int(it["num"]))[:3]
    if len(ranked) == 3:
        ranked = [ranked[1], ranked[0], ranked[2]]  # tampil: 2, 1, 3 (podium)
    heights_pt = {"1": 130, "2": 95, "3": 72}
    colors = {"1": t["light"], "2": t["main"], "3": t["chart"]}
    col_pct = round(100 / max(len(ranked), 1), 3)
    cells = []
    for it in ranked:
        h = heights_pt.get(it["num"], 80)
        color = colors.get(it["num"], t["main"])
        cells.append(
            f'<td style="width:{col_pct}%;vertical-align:bottom;text-align:center;padding:0 10pt;">'
            f'<div style="font-weight:700;font-size:12pt;color:{TEXT_DARK};">{_esc(it["name"])}</div>'
            f'<div style="font-weight:700;font-size:13pt;color:{t["main"]};margin-bottom:12pt;">{_esc(it["stat"])}</div>'
            f'<div style="background:{color};border-radius:8pt 8pt 0 0;height:{h}pt;">'
            f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:30pt;color:#fff;'
            f'text-align:center;line-height:{h}pt;">{_esc(it["num"])}</div>'
            f'</div></td>'
        )
    return f'<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0"><tr>{"".join(cells)}</tr></table>'


def _estimate_text_lines(text: str, font_pt: float, width_pt: float) -> int:
    """Estimasi kasar jumlah baris kalau `text` di-word-wrap dlm lebar `width_pt` pada ukuran
    `font_pt` — estimasi pra-render murni (WeasyPrint tidak dipanggil di sini), pola sama dgn
    `_estimate_wrapped_height_in` di export_ppt.py, dipakai `_timeline_html` di bawah utk
    menentukan tinggi kontainer SEBELUM HTML dirender."""
    if not text:
        return 0
    avg_char_w = font_pt * 0.52
    chars_per_line = max(int(width_pt / avg_char_w), 1)
    return max(1, -(-len(text) // chars_per_line))


def _timeline_html(items, container_h_pt=None, theme: dict | None = None) -> str:
    """Alternatif visual utk daftar rekomendasi (kartu grid) — titik variasi tampilan (lihat
    `recommendation_style` di generate_pdf_report). items: list of dict {"num","title",
    "detail"}, dirender sebagai roadmap horizontal: garis + node bulat bernomor, label
    berselang-seling di atas/bawah garis (gaya "tindak lanjut" laporan eksekutif). Posisi
    dihitung via CSS transform:translate (dikonfirmasi didukung WeasyPrint lewat isolasi
    render+sampling), BUKAN <table> — perlu node yang duduk TEPAT di tengah satu garis
    horizontal kontinu, sesuatu yang tidak bisa dicapai rapi dengan tabel kolom.

    `container_h_pt`: kalau None (default), dihitung otomatis dari perkiraan tinggi
    title+detail TERPANJANG di antara items — BUG YANG DIPERBAIKI (dilaporkan user): dulu
    SELALU 230pt tetap terlepas dari panjang teksnya, jadi rekomendasi dgn teks agak panjang
    kepotong visual (kotak kontennya tidak pernah menyesuaikan). Pola estimasi sama dgn
    perbaikan serupa yang sudah lebih dulu dilakukan di export_ppt.py."""
    t = theme or THEME_PALETTES["green"]
    # _light_safe: t["light"] SENGAJA pucat di tema "gold" (dirancang utk teks di atas latar
    # gelap) — dipakai apa adanya di sini (garis & node PERTAMA di atas latar TERANG) bikin
    # keduanya nyaris tak kelihatan (garis pucat di atas putih, angka putih di atas node pucat).
    line_color = _light_safe(t["light"])
    n = len(items) or 1
    stem_h = 20
    col_w_pt = 900 / n  # lebar konten halaman (13.333in - 2*0.5in margin) dibagi jumlah item
    text_w_pt = col_w_pt * 0.85

    def _content_h_pt(it):
        h = _estimate_text_lines(it.get("title", ""), 10, text_w_pt) * 10 * 1.3
        if it.get("detail"):
            h += _estimate_text_lines(it["detail"], 8.5, text_w_pt) * 8.5 * 1.3 + 3
        return h

    if container_h_pt is None:
        max_content_h = max((_content_h_pt(it) for it in items), default=0)
        container_h_pt = max(230, 2 * (max_content_h + stem_h + 14))
    line_y = container_h_pt / 2
    parts = [f'<div style="position:relative;height:{container_h_pt}pt;margin-top:10pt;">']
    parts.append(
        f'<div style="position:absolute;left:3%;right:3%;top:{line_y}pt;height:2pt;background:{line_color};"></div>'
    )
    col_w_pct = 100 / n
    for i, it in enumerate(items):
        cx_pct = round((i + 0.5) / n * 100, 3)
        above = (i % 2 == 0)
        node_color = line_color if i == 0 else t["main"]
        parts.append(
            f'<div style="position:absolute;left:{cx_pct}%;top:{line_y}pt;transform:translate(-50%,-50%);'
            f'width:24pt;height:24pt;border-radius:50%;background:{node_color};color:#fff;text-align:center;'
            f'line-height:24pt;font-weight:700;font-size:10.5pt;">{_esc(it["num"])}</div>'
        )
        detail_html = f'<div style="font-size:8.5pt;color:{GRAY_TEXT};margin-top:3pt;">{_esc(it["detail"])}</div>' if it.get("detail") else ""
        content_html = f'<div style="font-weight:700;font-size:10pt;color:{TEXT_DARK};">{_esc(it["title"])}</div>{detail_html}'
        if above:
            parts.append(
                f'<div style="position:absolute;left:{cx_pct}%;top:{line_y - stem_h}pt;height:{stem_h}pt;'
                f'width:1pt;background:{PANEL_BORDER};transform:translateX(-50%);"></div>'
            )
            parts.append(
                f'<div style="position:absolute;left:{cx_pct}%;top:0;width:{col_w_pct}%;height:{line_y - stem_h - 4}pt;'
                f'transform:translateX(-50%);text-align:center;display:table;">'
                f'<div style="display:table-cell;vertical-align:bottom;">{content_html}</div></div>'
            )
        else:
            parts.append(
                f'<div style="position:absolute;left:{cx_pct}%;top:{line_y}pt;height:{stem_h}pt;'
                f'width:1pt;background:{PANEL_BORDER};transform:translateX(-50%);"></div>'
            )
            parts.append(
                f'<div style="position:absolute;left:{cx_pct}%;top:{line_y + stem_h + 4}pt;width:{col_w_pct}%;'
                f'transform:translateX(-50%);text-align:center;">{content_html}</div>'
            )
    parts.append("</div>")
    return "".join(parts)


def _recommendation_banner_list_html(items, theme: dict | None = None) -> str:
    """Alternatif visual KETIGA (selain grid kartu/_timeline_html) — daftar rekomendasi
    sebagai banner selebar halaman bertumpuk vertikal (badge nomor + judul + detail),
    berselang-seling warna latar tipis — titik variasi tampilan tambahan utk recommendations
    (lihat `recommendation_style`), dipakai utk jumlah item BERAPA PUN (timeline dibatasi 2-6)."""
    t = theme or THEME_PALETTES["green"]
    rows = []
    for idx, it in enumerate(items):
        bg = IVORY if idx % 2 == 0 else WHITE
        detail_html = (
            f'<div style="font-size:10pt;color:{GRAY_TEXT};margin-top:4px;">{_esc(it["detail"])}</div>'
            if it.get("detail") else ""
        )
        rows.append(
            f'<table style="width:100%;background:{bg};border-left:4px solid {_light_safe(t["light"])};margin-bottom:10pt;" cellpadding="0" cellspacing="0">'
            f'<tr><td style="width:52px;vertical-align:top;padding:14pt 0 14pt 16pt;">{_badge(it["num"], t["main"], size="32px", font_size="12pt")}</td>'
            f'<td style="vertical-align:top;padding:14pt 16pt 14pt 12pt;">'
            f'<div style="font-weight:700;font-size:12.5pt;color:{TEXT_DARK};">{_esc(it["title"])}</div>'
            f'{detail_html}'
            f'</td></tr></table>'
        )
    return "".join(rows)


def _two_col(left_html, right_html, left_pct=58) -> str:
    """Layout 2-kolom pakai <table> (bukan flexbox — tidak didukung xhtml2pdf).

    RANCANG ULANG (target WeasyPrint, lihat catatan di _ivory_panel): height eksplisit
    dihapus — dulu WAJIB karena xhtml2pdf men-shrink isi kolom tanpa height eksplisit di sini
    (dibuktikan lewat isolasi render+sampling), tapi WeasyPrint mengukur tinggi baris tabel
    dari konten kedua kolom secara normal (tanpa shrink/stretch), jadi kolom sekarang setinggi
    kontennya sendiri — kalau salah satu kolom lebih pendek (mis. panel ivory vs bar chart
    panjang), itu wajar & lebih rapi daripada dipaksa sama tinggi dengan ruang kosong."""
    right_pct = 100 - left_pct
    return (
        f'<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="width:{left_pct}%;vertical-align:top;padding-right:16px;">{left_html}</td>'
        f'<td style="width:{right_pct}%;vertical-align:top;">{right_html}</td>'
        f'</tr></table>'
    )


def _main_panel_pair(main_html, panel_html, main_pct, side) -> str:
    """Susun pasangan (konten utama, panel pendamping) lewat _two_col — `side` menentukan
    panel ada di kiri atau kanan halaman (titik variasi tampilan antar generate, lihat
    `panel_side` di generate_pdf_report). Dipakai supaya urutan kiri/kanan bisa ditukar tanpa
    tiap pemanggil menghitung ulang persentase kolom sendiri-sendiri."""
    if side == "left":
        return _two_col(panel_html, main_html, left_pct=100 - main_pct)
    return _two_col(main_html, panel_html, left_pct=main_pct)


def _critical_table(headers, rows, highlight_idx, theme: dict | None = None) -> str:
    # RANCANG ULANG (target WeasyPrint, lihat catatan di _ivory_panel) — height eksplisit
    # dihapus di semua level, padding vertikal dipakai langsung (aman sekarang, lihat catatan
    # di _ivory_kv_rows) untuk baris yang lebih lapang & natural.
    t = theme or THEME_PALETTES["green"]
    thead = "".join(f'<th style="background:{t["bg"]};color:#fff;padding:9px;text-align:left;font-size:9pt;vertical-align:middle;">{_esc(h)}</th>' for h in headers)
    trows = []
    for i, row_vals in enumerate(rows):
        is_open = i in highlight_idx
        row_bg = RED_CRIT_BG if is_open else (IVORY if i % 2 == 0 else WHITE)
        cells = []
        for c, val in enumerate(row_vals):
            is_status_col = c == len(row_vals) - 1
            style = "padding:9px;font-size:9pt;vertical-align:middle;"
            if is_open and is_status_col:
                style += f"color:{RED_CRIT};font-weight:700;"
            cells.append(f'<td style="{style}">{_esc(val)}</td>')
        trows.append(f'<tr style="background:{row_bg};">{"".join(cells)}</tr>')
    return (
        f'<table style="width:100%;border-collapse:collapse;font-family:{BODY_FONT};" cellpadding="0" cellspacing="0">'
        f'<thead><tr>{thead}</tr></thead><tbody>{"".join(trows)}</tbody></table>'
    )


def _flourish_html(corner="bottom_right", theme: dict | None = None) -> str:
    t = theme or THEME_PALETTES["green"]
    pos = {
        "bottom_right": "bottom:-70px;right:-70px;",
        "top_right": "top:-70px;right:-70px;",
        "bottom_left": "bottom:-70px;left:-70px;",
    }.get(corner, "bottom:-70px;right:-70px;")
    circles = "".join(
        f'<div style="position:absolute;{pos}width:{140+ i*55}px;height:{140+i*55}px;'
        f'border-radius:50%;border:1px solid {t["light"]};"></div>'
        for i in range(4)
    )
    # BUG BESAR YANG DIPERBAIKI: dulu pakai shorthand CSS `inset:0` — TERBUKTI (isolasi
    # render+sampling) TIDAK didukung WeasyPrint, div pembungkus jadi collapse ke ukuran 0x0
    # dan `overflow:hidden` memotong SEMUA lingkaran ornamen di dalamnya (flourish sama sekali
    # tidak pernah muncul di PDF manapun sebelumnya). Diganti top/right/bottom/left:0 eksplisit
    # (didukung penuh) — hasilnya identik secara CSS, cuma lebih verbose.
    return f'<div style="position:absolute;top:0;right:0;bottom:0;left:0;overflow:hidden;pointer-events:none;">{circles}</div>'


def _split_cover_td(block, flourish_corner, logo_b64=None, theme: dict | None = None) -> str:
    """Varian cover 2-kolom warna penuh (emas kiri + hijau kanan, angka hero besar di kolom
    emas) — titik variasi tampilan (lihat `cover_style` di generate_pdf_report), alternatif
    dari cover 1-warna standar. Dikembalikan sebagai dua <td> LENGKAP (dipakai lewat
    `_page(..., raw=True)`, lihat catatan di sana) karena masing-masing kolom perlu warna
    latar SENDIRI penuh 1 halaman — tidak bisa dicapai dengan satu <td> background tunggal
    seperti pola cover biasa."""
    t = theme or THEME_PALETTES["green"]
    value, label = block.get("hero_stat") or (str(block.get("total_records", "")), "Total Data")
    hero_kicker = block.get("hero_stat_kicker", "CAPAIAN")
    left_w_pct = 37
    # BUG BESAR YANG DIPERBAIKI: `position:absolute` dgn `top` PERSENTASE atau `bottom` bukan-
    # nol TERBUKTI (isolasi render+sampling) salah dihitung WeasyPrint kalau leluhur
    # `position:relative`-nya LANGSUNG sebuah <td> — elemen malah muncul di urutan flow biasa
    # (offset diabaikan), BUKAN di posisi yang diminta (nyata: angka hero "menimpa" footer di
    # pojok kiri-atas, bukan di tengah & bawah seperti seharusnya). Pola aman TERBUKTI: bungkus
    # SATU <div style="position:relative;height:...;"> eksplisit di dalam <td> (BUKAN taruh
    # position:relative langsung di <td>-nya) — offset absolute di dalamnya baru dihitung benar.
    left_td = (
        f'<td style="width:{left_w_pct}%;background:{t["light"]};color:{TEXT_DARK};'
        f'height:7.5in;vertical-align:top;font-family:{BODY_FONT};">'
        f'<div style="position:relative;height:7.5in;">'
        f'<div style="margin:0.5in 0.45in;">'
        f'<div style="font-size:9pt;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;">{_esc(hero_kicker)}</div>'
        f'</div>'
        f'<div style="position:absolute;left:0.45in;right:0.3in;top:3.15in;">'
        f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:58pt;color:{t["bg"]};line-height:1;">{_esc(value)}</div>'
        f'<div style="font-size:11pt;margin-top:10px;">{_esc(label)}</div>'
        f'</div>'
        # BUG WEASYPRINT LAIN: `position:absolute;bottom:...` (bukan `top:...`) di dalam <td>
        # yang punya saudara kandung block-normal-flow (kicker) + absolute lain (hero stat)
        # TERBUKTI (isolasi render+sampling) bikin elemennya HILANG TOTAL dari output — bukan
        # cuma salah posisi (footer "PT PETROKIMIA GRESIK" lenyap tanpa error). Pola `top:...`
        # eksplisit di sebelahnya justru konsisten & linear di struktur yang sama, jadi footer
        # ditaruh pakai `top` (dihitung dari tinggi halaman 7.5in) alih-alih `bottom`.
        f'<div style="position:absolute;left:0.45in;top:6.6in;font-size:9pt;font-weight:700;">{_esc(block["header_title"])}</div>'
        f'</div></td>'
    )
    title_text = block["title"]
    title_size_pt = 26 if len(title_text) > 55 else 32 if len(title_text) > 40 else 38 if len(title_text) > 28 else 44
    # PERMINTAAN USER: logo cover/penutup lebih besar lagi drpd halaman konten biasa (halaman
    # pertama/terakhir yg paling dilihat) — 126px, bukan cuma 84px spt halaman dark biasa.
    logo_html = _dark_logo_html(logo_b64, size_px=126, top="0.28in") if logo_b64 else ""
    right_td = (
        f'<td style="width:{100 - left_w_pct}%;background:{t["bg"]};color:#fff;position:relative;'
        f'height:7.5in;vertical-align:top;font-family:{BODY_FONT};overflow:hidden;">'
        f'{_flourish_html(flourish_corner, theme=t)}'
        f'{logo_html}'
        f'<div style="position:relative;margin:0.5in;">'
        f'<div style="height:1.6in;font-size:1px;line-height:1px;">&nbsp;</div>'
        f'{_kicker(block["kicker"], t["light"])}'
        f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:{title_size_pt}pt;color:#fff;margin-bottom:10px;">{_esc(title_text)}</div>'
        f'<div style="font-size:12.5pt;color:#fff;margin-bottom:20px;">{_esc(block["subtitle"])}</div>'
        f'<div style="font-size:10.5pt;color:#fff;">{_esc(block["period_label"])} {_esc(block["period_text"])}</div>'
        f'<div style="font-size:10.5pt;color:{t["soft"]};margin-top:6px;">{_esc(block["info_line"])}</div>'
        f'</div></td>'
    )
    return left_td + right_td


def _split_closing_td(block, flourish_corner="bottom_right", logo_b64=None, theme: dict | None = None) -> str:
    """Varian penutup berpasangan dgn _split_cover_td — angka hero yang SAMA ditampilkan lagi
    di kolom emas kiri (mengulang temuan utama di penutup, gaya "bookend" laporan
    eksekutif), kolom kanan tetap "Terima Kasih" seperti biasa."""
    t = theme or THEME_PALETTES["green"]
    value, label = block.get("hero_stat") or ("", "")
    left_w_pct = 37
    # Lihat catatan panjang di _split_cover_td soal kenapa position:relative TIDAK boleh
    # langsung di <td> kalau ada anak position:absolute beroffset non-nol/persentase.
    left_td = (
        f'<td style="width:{left_w_pct}%;background:{t["light"]};color:{TEXT_DARK};'
        f'height:7.5in;vertical-align:top;font-family:{BODY_FONT};">'
        f'<div style="position:relative;height:7.5in;">'
        f'<div style="position:absolute;left:0.45in;right:0.3in;top:3.15in;">'
        f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:46pt;color:{t["bg"]};line-height:1;">{_esc(value)}</div>'
        f'<div style="font-size:10.5pt;margin-top:8px;">{_esc(label)}</div>'
        f'</div></div></td>'
    )
    # PERMINTAAN USER: logo cover/penutup lebih besar lagi drpd halaman konten biasa.
    logo_html = _dark_logo_html(logo_b64, size_px=126, top="0.28in") if logo_b64 else ""
    right_td = (
        f'<td style="width:{100 - left_w_pct}%;background:{t["bg"]};color:#fff;position:relative;'
        f'height:7.5in;vertical-align:top;font-family:{BODY_FONT};overflow:hidden;">'
        f'{_flourish_html(flourish_corner, theme=t)}'
        f'{logo_html}'
        f'<div style="position:relative;margin:0.5in;">'
        f'<div style="height:1.6in;font-size:1px;line-height:1px;">&nbsp;</div>'
        f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:30pt;color:#fff;margin-bottom:10px;">{_esc(block["thank_you"])}</div>'
        f'<div style="font-size:12pt;color:#fff;margin-bottom:8px;">{_esc(block["title"])}</div>'
        f'<div style="font-size:10.5pt;font-style:italic;color:{t["soft"]};">{_esc(block["note"])}</div>'
        f'</div></td>'
    )
    return left_td + right_td


def _dark_logo_html(logo_b64, size_px=84, top="0.3in", right="0.3in") -> str:
    """Logo di atas latar GELAP — PERMINTAAN USER: sebelumnya dibungkus kotak putih solid
    bersudut (kontras aman, tapi terlihat seperti stiker ditempel). Diganti glow putih lembut
    (radial-gradient, memudar ke tepi, tanpa sudut/kotak keras) — tetap kontras krn logo
    aslinya berwarna gelap, tapi menyatu dgn latar, bukan kotak asing di atasnya."""
    pad = round(size_px * 0.28)
    return (
        f'<div style="position:absolute;top:{top};right:{right};padding:{pad}px;line-height:0;'
        f'background:radial-gradient(circle, rgba(255,255,255,0.92) 0%, rgba(255,255,255,0.55) 50%, rgba(255,255,255,0) 78%);">'
        f'<img src="data:image/png;base64,{logo_b64}" style="height:{size_px}px;display:block;" /></div>'
    )


def _page(inner_html, dark=False, flourish=None, page_num=None, total_pages=None, logo_b64=None, last=False, raw=False, theme: dict | None = None, center=False) -> str:
    t = theme or THEME_PALETTES["green"]
    break_style = "" if last else "page-break-after:always;"
    if raw:
        # `raw=True`: `inner_html` SUDAH berupa satu/lebih <td> lengkap (mis. cover/penutup
        # varian split-warna, 2 kolom background beda) — dipakai sebagai isi <tr> APA ADANYA,
        # tanpa background/margin-inset/flourish tunggal standar di bawah ini (pemanggil yang
        # bertanggung jawab penuh atas seluruh isi <tr>, termasuk warnanya sendiri).
        return f'<table style="width:13.333in;{break_style}" cellpadding="0" cellspacing="0"><tr>{inner_html}</tr></table>'
    bg = t["bg"] if dark else t["soft"]
    color = WHITE if dark else TEXT_DARK
    flourish_html = _flourish_html(flourish, theme=t) if flourish else ""
    if logo_b64 and dark:
        # Logo aslinya berwarna gelap/hitam (lihat frontend/public/LOGO_PETRO_DANANTARA.png)
        # — perlu treatment kontras di halaman berlatar gelap (cover/penutup/panel dark)
        # supaya tetap kontras, bukan tenggelam di latar gelap yang sama (lihat
        # _dark_logo_html). PERMINTAAN USER: ukuran logo digandakan (42 -> 84px).
        logo_html = _dark_logo_html(logo_b64, size_px=84)
    elif logo_b64:
        # PERMINTAAN USER: ukuran logo digandakan (54 -> 108px).
        logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="position:absolute;top:0.22in;right:0.3in;height:108px;" />'
    else:
        logo_html = ""
    footer_html = ""
    if page_num is not None:
        footer_html = (
            f'<div style="position:absolute;bottom:0.3in;right:0.3in;font-size:8pt;color:{GRAY_TEXT if not dark else t["soft"]};'
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
    # `center=True` (dipakai halaman "page"/"intro", lihat generate_pdf_report) — konten
    # ditengahkan VERTIKAL di dalam <td> (bukan nempel atas) supaya halaman yang kontennya
    # secara wajar tidak sampai memenuhi tinggi 6.5in (mis. cuma 1-2 panel ringkas) tidak
    # menyisakan area kosong raksasa di bawah, tanpa perlu memaksa halaman lain digabung lagi
    # cuma demi mengisi ruang. Cover/Penutup TIDAK dipengaruhi (selalu `center=False`, lihat
    # docstring atas) — layout keduanya sudah bespoke posisi absolut dari tepi atas/bawah.
    valign = "middle" if center else "top"
    # BUG KRITIS KEDUA DIPERBAIKI (satu paket dgn perbaikan `center=False` hardcode di
    # generate_pdf_report): variabel `valign` di atas SUDAH benar dihitung dari `center`,
    # TAPI baris <td> di bawah selama ini menulis literal "vertical-align:top" APA ADANYA,
    # tidak pernah benar2 memakai variabel `{valign}` ini — jadi walau `center=True` sudah
    # benar terkirim sampai sini, hasil akhirnya TETAP top-align, tidak pernah ketengahan.
    # Inilah 2 lapis bug yang sama2 harus diperbaiki spy fitur "tengahkan vertikal" ini
    # akhirnya benar2 aktif.
    # PERBAIKAN (dilaporkan user): logo & nomor halaman "ikut naik-turun" kalau isi 1 blok
    # kebetulan lebih tinggi dari 1 halaman fisik (7.5in) — WeasyPrint memperlakukan tinggi
    # <td> di atas sbg MINIMUM, bukan batas tegas, jadi baris tabel ini diam-diam terpecah
    # jadi 2+ halaman fisik; logo/nomor halaman (position:absolute) dihitung relatif ke
    # wrapper yang jadi lebih tinggi dari 7.5in itu, sehingga posisinya ikut bergeser.
    # break-inside:avoid MEMAKSA WeasyPrint memindah SELURUH blok ke halaman fisik
    # berikutnya kalau tidak muat, bukan memotongnya di tengah — wrapper jadi TETAP persis
    # 7.5in tiap kali dirender, jadi posisi logo/nomor halaman tidak pernah lagi bergantung
    # pada tinggi konten.
    # BUG KRITIS KETIGA (satu paket dgn 2 perbaikan di atas): TERNYATA `vertical-align` di
    # <td> di atas TIDAK PERNAH bisa efektif sama sekali — wrapper div persis di bawahnya
    # (`height:7.5in` tegas) SELALU memenuhi 100% tinggi <td>, jadi tidak ada sisa ruang
    # apa pun utk didistribusikan oleh vertical-align (anaknya sudah pas 7.5in juga). Div
    # biasa (position:relative) JUGA tidak merespon vertical-align sama sekali (properti itu
    # cuma berlaku utk elemen table-cell/inline). Konten SEKARANG dibungkus display:table +
    # display:table-cell (pola yang SAMA PERSIS sudah dipakai & terbukti jalan di WeasyPrint
    # utk _timeline_html di file ini) — supaya vertical-align BENAR-BENAR mengambang-tengahkan
    # tinggi konten ASLI (bukan wrapper 7.5in tegas) di dalam ruang yang tersedia.
    # CSS display:table pada <div> TERNYATA tidak cukup andal di WeasyPrint utk kasus ini
    # (baris/sel anonim tidak konsisten meregang ke `height` yg diminta kalau kontennya lebih
    # pendek — sudah dicoba & TERBUKTI tidak berefek). Dipakai <table> SUNGGUHAN sebagai
    # gantinya — pola PERSIS sama dgn wrapper TERLUAR (di bawah) yang SUDAH TERBUKTI berhasil
    # memenuhi <td height:7.5in> secara konsisten di semua halaman (itulah caranya warna latar
    # tiap halaman sudah selalu benar mengisi penuh 7.5in selama ini).
    content_html = (
        f'<table style="width:13.333in;height:7.5in;" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="height:7.5in;vertical-align:{valign};">'
        f'<div style="position:relative;margin:0.5in;">{inner_html}</div>'
        f'</td></tr></table>'
    )
    return (
        f'<table style="width:13.333in;{break_style}" cellpadding="0" cellspacing="0">'
        f'<tr><td style="background:{bg};color:{color};height:7.5in;vertical-align:top;'
        f'break-inside:avoid;page-break-inside:avoid;font-family:{BODY_FONT};">'
        f'<div style="position:relative;width:13.333in;height:7.5in;overflow:hidden;">'
        f'{flourish_html}{logo_html}'
        f'{content_html}'
        f'{footer_html}</div></td></tr></table>'
    )


@dataclass
class _PdfBlockContext:
    """Kumpulan variabel variasi tampilan (dipilih SEKALI per generate, lihat
    generate_pdf_report) + report itu sendiri, yang dibutuhkan LEBIH DARI SATU builder block
    di bawah — dioper ke tiap builder supaya signature-nya seragam (block, ctx) alih-alih
    daftar parameter berbeda-beda per jenis block. Sebelumnya semua builder ini adalah
    cabang if/elif di dalam SATU fungsi generate_pdf_report sepanjang ~300 baris — dipecah
    jadi fungsi terpisah (murni supaya lebih mudah dibaca/diubah 1 jenis block tanpa perlu
    scroll baca semuanya), TIDAK ada perubahan HASIL AKHIR sama sekali (diverifikasi PDF
    yang dihasilkan identik sebelum & sesudah pemecahan ini).

    cover_hero_stat DIISI oleh _build_cover_block, DIBACA oleh _build_closing_block (bookend
    angka hero yang sama di cover & penutup saat cover_style="split") — satu-satunya state
    yang mengalir ANTAR pemanggilan builder, makanya ctx harus objek yang sama dioper ke
    semua builder dalam 1 kali generate, bukan dibuat ulang tiap block.
    """
    report: Report
    stat_cols: int
    card_cols: int
    flourish_corner: str
    panel_side: str
    accent_bar_color: str
    category_style: str
    status_style: str
    cover_style: str
    asset_style: str
    recommendation_style: str
    logo_b64: str | None
    kicker_ringkasan: str
    kicker_analisis: str
    # Palet warna tema (report.theme_color) — 5 peran, resolusi lihat resolve_theme_color()/
    # THEME_PALETTES di atas. "accent_main" dkk dipakai di elemen BRAND/struktural (cover,
    # kicker, badge, border panel, header tabel, chart bar utama) — TIDAK PERNAH dipakai di
    # SEVERITY_COLOR/kondisional is_critical, itu tetap warna semantik severity yang fixed.
    accent_main: str
    accent_bg: str
    accent_chart: str
    accent_light: str
    accent_soft: str
    # Sama persis dgn 5 field accent_* di atas, dikemas jadi 1 dict {"main","bg","chart",
    # "light","soft"} — kemudahan utk dioper sebagai parameter `theme=` ke helper murni
    # (_ivory_panel, _stat_card_grid, dkk) yang tidak butuh field ctx lain.
    theme: dict | None = None
    cover_hero_stat: dict | None = None
    # Diisi _build_page_block SEBELUM memanggil builder tiap panel di halaman itu — dibaca
    # _mini_chart_html (lihat catatan di sana) supaya chart pendukung tahu apakah dia
    # sendirian selebar halaman atau berbagi kolom dgn panel lain, BUKAN selalu diasumsikan
    # sempit (BUG YANG DIPERBAIKI, dilaporkan user: chart kecil dibiarkan kecil walau
    # kebetulan sendirian di halaman lebar, menyisakan banyak ruang kosong).
    panel_count: int = 1


def _build_cover_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    ctx.cover_hero_stat = block.get("hero_stat")  # dipakai lagi di "closing" (bookend)
    if ctx.cover_style == "split":
        # Varian 2-kolom warna penuh (lihat _split_cover_td) — dipakai via
        # _page(..., raw=True) karena tiap kolom butuh background sendiri penuh
        # 1 halaman, bukan satu warna latar tunggal seperti varian "solid".
        return (_split_cover_td(block, ctx.flourish_corner, logo_b64=ctx.logo_b64, theme=ctx.theme), True, None, False, True)
    else:
        # BUG BESAR YANG DIPERBAIKI: `margin-top` pada <div> PEMBUNGKUS (bukan pada
        # dirinya sendiri) terbukti (isolasi render+sampling) TIDAK diterapkan ke child
        # PERTAMA di dalamnya — child pertama malah dirender di y negatif (KEPOTONG DI
        # LUAR halaman, terlihat nyata di slide Penutup "Terima Kasih" yang judulnya
        # hilang separuh ke atas), sedangkan child KEDUA dst tetap memakai posisi
        # seolah margin-top itu diterapkan (makanya subtitle terlihat "benar" tapi
        # judul di atasnya hilang). Diganti <div> SPACER berheight eksplisit sebagai
        # SIBLING (bukan parent) sebelum kicker — height eksplisit pada div sendiri
        # (bukan margin pada parent) terbukti aman di posisi manapun dalam alur.
        inner = (
            f'<div style="height:1.6in;font-size:1px;line-height:1px;">&nbsp;</div>'
            f'{_kicker(block["kicker"], ctx.accent_light)}'
            f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:34pt;color:#fff;margin-bottom:10px;">{_esc(block["title"])}</div>'
            f'<div style="font-size:12.5pt;color:#fff;margin-bottom:20px;">{_esc(block["subtitle"])}</div>'
            f'<div style="font-size:10.5pt;color:#fff;">{_esc(block["period_label"])} {_esc(block["period_text"])}</div>'
            f'<div style="font-size:10.5pt;color:{ctx.accent_soft};margin-top:6px;">{_esc(block["info_line"])}</div>'
            # BUG YANG DIPERBAIKI (dilaporkan user): "bottom:0" di sini dulu terlihat benar
            # SECARA KEBETULAN (parent belum position:relative saat itu, jadi malah escape ke
            # tepi FISIK kertas). Setelah parent diperbaiki jadi position:relative (lihat
            # _page()), "bottom:0" berubah makna jadi "bawah DIV KONTEN" (yang tingginya cuma
            # sebatas kicker+judul+subjudul, bukan setinggi halaman) — nama perusahaan jadi
            # tumpang tindih dgn baris info di atasnya. Diganti "top:6.6in" (offset tetap dari
            # atas div, POLA SAMA yang sudah dipakai _split_cover_td utk elemen serupa, TIDAK
            # bergantung tinggi konten di atasnya).
            f'<div style="position:absolute;top:6.6in;left:0;font-size:9pt;font-weight:700;color:#fff;">{_esc(block["header_title"])}</div>'
        )
        return (inner, True, ctx.flourish_corner, False)


def _build_intro_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    objectives_html = "".join([
        _badge_row(o["num"], o["title"], o["detail"], ctx.accent_main) for o in block["objectives"]
    ])
    scope = block["scope"]
    scope_rows = _ivory_kv_rows([
        (scope["period_label"], scope["period_text"]),
        (scope["total_event_label"], scope["total_records_text"]),
        (scope["source_file_label"], scope["input_file_name"]),
        (scope["data_type_label_label"], scope["data_type_label"]),
    ], theme=ctx.theme)
    scope_panel = _ivory_panel("i", scope["panel_title"], scope_rows, footnote=scope["footnote"], theme=ctx.theme)
    bg_left = f'<div style="font-size:11pt;color:{GRAY_TEXT};margin-bottom:18px;">{block["purpose_text"]}</div>{objectives_html}'
    inner = (
        _kicker(block["kicker"], ctx.accent_main) + _title(block["title"]) +
        _main_panel_pair(bg_left, scope_panel, 58, ctx.panel_side)
    )
    return (inner, False, None, False)


def _build_executive_summary_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    # Panel ini SEBELUMNYA cuma kartu KPI + 1 paragraf caption — solo page bertema "overview"
    # (satu-satunya kandidat bertema ini, lihat _group_candidates_into_pages) jadi TIDAK
    # PERNAH digabung dgn kandidat lain, hasilnya banyak ruang kosong kalau jumlah kartu
    # sedikit. Donut kategori/status (data yang SAMA dgn aux_list_items, sudah dihitung di
    # report_render_logic.py) ditambahkan sbg pendamping visual supaya halaman ini terasa
    # sepadat halaman lain, bukan cuma teks pendek + banyak ruang kosong.
    chart_html = ""
    if block.get("chart"):
        chart_html = (
            f'<div style="margin-top:22px;padding-top:18px;border-top:1px solid {ctx.accent_soft};">'
            f'{_dark_donut_chart_html(block["chart"], ctx)}'
            f'</div>'
        )
    inner = (
        _kicker(ctx.kicker_ringkasan, ctx.accent_light) +
        f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:20pt;color:#fff;margin-bottom:18px;">{_esc(block["heading"])}</div>' +
        _stat_card_grid(block["stat_items"], cols=ctx.stat_cols, dark=True, theme=ctx.theme) +
        # max-width dibatasi ~9.5in (bukan full CONTENT_W ~12.3in) — paragraf
        # selebar halaman penuh di kertas widescreen 13.333in menghasilkan baris
        # >150 karakter, jauh melebihi lebar baca nyaman (~75-90 karakter); versi
        # referensi selalu membatasi teks naratif ke lebar yang lebih wajar.
        f'<div style="font-size:10.5pt;font-style:italic;color:{ctx.accent_soft};margin-top:18px;max-width:9.5in;">{_esc(block["caption"])}</div>' +
        chart_html
    )
    return (inner, True, None, False)


def _mini_legend_html(categories, ramp, text_color=None) -> str:
    """Legend ringkas (titik warna + nama, tanpa persentase) utk chart "donut"/"stacked" di
    _mini_chart_html — _donut_chart_svg/_stacked_proportion_bar_html sendiri MURNI grafik
    (beda dari React DonutChart/StackedBar yang legend-nya sudah menyatu di komponennya),
    tanpa ini pembaca tidak tahu warna mana mewakili kategori apa di panel kecil ini.
    `text_color` opsional (default GRAY_TEXT) — dioverride panel berlatar gelap."""
    text_color = text_color or GRAY_TEXT
    dots = "".join(
        f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{ramp[i % len(ramp)]};margin-right:4px;"></span>'
        f'<span style="font-size:8pt;color:{text_color};margin-right:10px;">{_esc(cat)}</span>'
        for i, cat in enumerate(categories)
    )
    return f'<div style="margin-top:8pt;line-height:2;">{dots}</div>'


def _dark_donut_chart_html(chart: dict, ctx: "_PdfBlockContext") -> str:
    """Donut kategori/status utk panel BERLATAR GELAP (Ringkasan Eksekutif) — _donut_chart_svg
    & _mini_legend_html defaultnya dirancang utk panel terang (label pusat/legend pakai
    TEXT_DARK/GRAY_TEXT, nyaris tak kelihatan di atas hijau tua). Ramp warna SENGAJA dari
    palet tema (ctx.accent_*), bukan CATEGORY_COLOR_RAMP yang tetap hijau/emas apa pun
    temanya — konsisten dgn fix konsistensi warna tema di kartu KPI/bar management report."""
    ramp = [ctx.accent_light, WHITE, ctx.accent_chart, ctx.accent_soft, GRAY_TEXT]
    svg = _donut_chart_svg(chart["values"], colors=ramp[:len(chart["values"])], size=190, stroke_w=32, label_color=WHITE, sub_color=ctx.accent_soft)
    legend = _mini_legend_html(chart["categories"], ramp, text_color=WHITE)
    return (
        f'<table cellpadding="0" cellspacing="0"><tr>'
        f'<td style="vertical-align:middle;">{svg}</td>'
        f'<td style="vertical-align:middle;padding-left:20px;">{legend}</td>'
        f'</tr></table>'
    )


def _mini_chart_html(chart: dict, ctx: "_PdfBlockContext") -> str:
    """Chart kecil pendukung (block["chart"], lihat _build_dynamic_section_block/
    _build_key_findings_block di bawah) — dipakai BERSAMA keduanya supaya dispatch
    bar/donut/stacked/gauge tidak diduplikasi 2x. Ukuran SENGAJA lebih kecil dari chart
    full-size (_build_category_distribution_block dkk pakai size=210) — panel pendukung
    harus terasa sekunder, bukan bersaing dgn chart analisis utama di halaman lain."""
    colors = [SEVERITY_COLOR[k] for k in chart["severity_keys"]] if chart.get("severity_keys") else None
    if chart["type"] == "gauge":
        gauge_color = colors[0] if colors else None
        return _gauge_chart_svg(chart["value"], chart.get("max", 100), chart.get("label", ""), color=gauge_color, size=150, stroke_w=22)
    ramp = colors or CATEGORY_COLOR_RAMP
    if chart["type"] == "donut":
        return _donut_chart_svg(chart["values"], colors=colors, size=140, stroke_w=24) + _mini_legend_html(chart["categories"], ramp)
    if chart["type"] == "stacked":
        return _stacked_proportion_bar_html(chart["values"], colors=colors, height_px=28) + _mini_legend_html(chart["categories"], ramp)
    if chart["type"] == "bar_line":
        # Lebar menyesuaikan berapa panel yang berbagi halaman ini (ctx.panel_count, diisi
        # _build_page_block SEBELUM memanggil builder tiap panel) — BUG YANG DIPERBAIKI
        # (dilaporkan user): dulu SELALU 300x130 tetap, jadi kalau kandidat "Analisis Tren"
        # ini kebetulan berakhir SENDIRIAN selebar halaman (umum, bukan cuma teori — lihat
        # 1 panel -> lebar penuh di _build_page_block), chart kecilnya menyisakan banyak
        # ruang kosong di kanan-kiri. Tinggi tetap 130 (batas visual_wrap 1.4in di
        # _panel_insight_card, biar tidak overflow vertikal).
        size_w = {1: 700, 2: 460}.get(ctx.panel_count, 300)
        return _bar_line_chart_svg(chart["categories"], chart["values"], chart.get("cumulative"), color=ctx.accent_main, size_w=size_w, size_h=130)
    return _bar_chart_html(chart["categories"], chart["values"], colors=colors or [ctx.accent_main] * len(chart["values"]))


_DIRECTION_COLOR = {"up": GREEN_CHART, "down": RED_CRIT, "flat": GRAY_TEXT}


def _panel_insight_card(panel: dict, ctx: _PdfBlockContext) -> tuple:
    """Kartu ringkas dipakai BERSAMA oleh 2 panel_kind ("insight_tile" — Trend/Severity/Risk
    bawaan AI, DAN "dynamic_section" — section kustom AI): keduanya bertema "insight" (lihat
    report_render_logic.py) & bisa berbagi 1 halaman berdampingan sampai 3 kartu, jadi
    kontennya SENGAJA kompak (label kecil + chart/kartu-panah/angka + catatan pendek) alih-alih
    asumsi lebar 1 halaman penuh — supaya tetap aman & terbaca di lebar kolom sempit."""
    label = panel.get("label") or panel.get("title") or ""
    if panel.get("trend_stat"):
        ts = panel["trend_stat"]
        visual_html = (
            f'<div style="text-align:center;">'
            f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:22pt;color:{_DIRECTION_COLOR[ts["direction"]]};">{_esc(ts["value"])}</div>'
            f'<div style="font-size:8.5pt;color:{GRAY_TEXT};margin-top:4pt;">{_esc(ts["label"])}</div>'
            f'</div>'
        )
    elif panel.get("chart"):
        visual_html = _mini_chart_html(panel["chart"], ctx)
    elif panel.get("aux_stat"):
        value, aux_label = panel["aux_stat"]
        visual_html = (
            f'<div style="text-align:center;">'
            f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:22pt;color:{ctx.accent_main};">{_esc(value)}</div>'
            f'<div style="font-size:8.5pt;color:{GRAY_TEXT};margin-top:4pt;">{_esc(aux_label)}</div>'
            f'</div>'
        )
    elif panel.get("aux_list"):
        visual_html = _ivory_kv_rows([(it["label"], it["value"]) for it in panel["aux_list"]], theme=ctx.theme)
    else:
        visual_html = ""
    # Tengah horizontal+vertikal via <table><td valign=middle> (BUKAN flexbox — tidak didukung
    # xhtml2pdf, konvensi yang sama dipakai di seluruh file ini).
    visual_wrap = (
        f'<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0">'
        f'<tr><td style="height:1.4in;text-align:center;vertical-align:middle;">{visual_html}</td></tr></table>'
        if visual_html else ""
    )
    caption_text = panel.get("caption") or panel.get("text") or ""
    inner = (
        f'<div style="border:1px solid {PANEL_BORDER};border-radius:12px;padding:14pt;height:100%;">'
        f'<div style="font-size:8pt;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;color:{ctx.accent_main};margin-bottom:10pt;">{_esc(label)}</div>'
        f'{visual_wrap}'
        f'<div style="margin-top:10pt;">{_bullet_lines_html(caption_text, theme=ctx.theme, font_pt=8.5)}</div>'
        f'</div>'
    )
    return (inner, False, None, False)


def _build_kpi_radar_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    """Skor multi-indikator (radar) — panel MANDIRI (judul sendiri di dalam kontennya, lihat
    catatan di _build_page_block), sama pola dgn category_distribution dkk."""
    chart_html = _radar_chart_svg(block["axes"], block["values"], color=ctx.accent_main)
    caption_html = _note_box_html(block.get("ai_caption") or block.get("intro"), theme=ctx.theme) if (block.get("ai_caption") or block.get("intro")) else ""
    inner = (
        _kicker(ctx.kicker_analisis, ctx.accent_main) + _title(block["title"]) +
        f'<div style="text-align:center;">{chart_html}</div>' + caption_html
    )
    return (inner, False, None, False)


def _build_time_heatmap_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    """Pola kejadian per hari/jam (heatmap grid) — panel MANDIRI, sama pola dgn
    category_distribution dkk."""
    chart_html = _heatmap_grid_svg(block["day_labels"], block["hour_labels"], block["grid"], color=ctx.accent_main)
    caption_html = _note_box_html(block.get("intro"), theme=ctx.theme) if block.get("intro") else ""
    inner = (
        _kicker(ctx.kicker_analisis, ctx.accent_main) + _title(block["title"]) +
        f'<div style="text-align:center;">{chart_html}</div>' + caption_html
    )
    return (inner, False, None, False)


def _build_period_compare_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    """Perbandingan antar paruh periode (grouped bar) — panel MANDIRI, sama pola dgn
    category_distribution dkk."""
    # color_b sengaja pakai _light_safe(accent_light), BUKAN accent_light apa adanya — di
    # atas latar TERANG panel ini, tema "gold" khususnya bikin 2 batang berdampingan nyaris
    # tak beda warna (lihat docstring _light_safe).
    # size_w eksplisit menyesuaikan ctx.panel_count (diisi _build_page_block SEBELUM
    # memanggil builder tiap panel di halaman ini) — KOREKSI: panel ini TIDAK selalu
    # sendirian selebar halaman seperti asumsi awal fix ini (bobotnya 0.45, di bawah
    # MIN_FULL backstop 0.6, jadi sering digabung dgn panel "distribution" lain spt
    # category_distribution/time_heatmap di halaman yang sama — size_w=760 tetap akan
    # overflow keluar kolomnya kalau dipaksa selalu dipakai). BUG ASLI YANG DIPERBAIKI
    # (dilaporkan user): ukuran default lama (480x190) kecil & menyisakan ruang kosong
    # kalau kebetulan sendirian.
    size_w, size_h = {1: (760, 230), 2: (480, 200)}.get(ctx.panel_count, (340, 170))
    chart_html = _grouped_bar_chart_svg(
        block["categories"], block["series_a"], block["series_b"],
        label_a=block["label_a"], label_b=block["label_b"],
        color_a=ctx.accent_main, color_b=_light_safe(ctx.accent_light),
        size_w=size_w, size_h=size_h,
    )
    caption_html = _note_box_html(block.get("intro"), theme=ctx.theme) if block.get("intro") else ""
    inner = (
        _kicker(ctx.kicker_analisis, ctx.accent_main) + _title(block["title"]) +
        f'<div style="text-align:center;">{chart_html}</div>' + caption_html
    )
    return (inner, False, None, False)


def _build_category_distribution_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    # Ramp warna kategori/status DITURUNKAN dari tema (report.theme_color), bukan konstanta
    # hijau/emas tetap — supaya chart multi-segmen (donut/stacked) ikut tema, sama seperti
    # bar chart utama. GRAY_TEXT tetap sebagai warna ke-5 (netral, dipakai kalau kategori > 4).
    # accent_light/accent_soft dilewatkan _light_safe() — kedua peran ini SENGAJA pucat di
    # tema "gold" (dirancang utk teks di atas latar gelap, lihat docstring _light_safe),
    # tanpa ini segmen ke-3/ke-4 chart di panel BERLATAR TERANG ini nyaris tak kelihatan.
    ramp = [ctx.accent_main, ctx.accent_chart, _light_safe(ctx.accent_light), _light_safe(ctx.accent_soft), GRAY_TEXT]
    legend = _legend_rows([
        (ramp[l["color_index"] % len(ramp)], l["name"], f"{l['pct']}%") for l in block["legend"]
    ], theme=ctx.theme)
    legend_panel = _ivory_panel("%", block["legend_panel_title"], legend, footnote=block["footnote"], theme=ctx.theme)
    # Titik variasi tampilan: bar horizontal (warna accent hijau/emas gantian per
    # generate), donut ring multi-warna, ATAU batang proporsi 100% bersegmen (lihat
    # category_style/accent_bar_color di generate_pdf_report) — datanya identik,
    # cuma cara visualnya beda tiap generate.
    if ctx.category_style == "donut":
        # size dinaikkan dari default 210 — panel ini selebar 58% halaman (_main_panel_pair),
        # donut kecil menyisakan ruang kosong besar di kanan-kirinya (kelas masalah sama dgn
        # chart lain yang sudah diperbesar, dilaporkan user).
        chart_html = _donut_chart_svg(block["values"], colors=[ramp[l["color_index"] % len(ramp)] for l in block["legend"]], size=280, stroke_w=44)
    elif ctx.category_style == "stacked":
        seg_colors = [ramp[l["color_index"] % len(ramp)] for l in block["legend"]]
        chart_html = _stacked_proportion_bar_html(block["values"], colors=seg_colors)
    else:
        chart_html = _bar_chart_html(block["categories"], block["values"], colors=[ctx.accent_bar_color] * len(block["values"]))
    caption_html = _note_box_html(block["ai_caption"], theme=ctx.theme) if block.get("ai_caption") else ""
    # "stacked" DITUMPUK VERTIKAL (batang lebar penuh, lalu panel legend penuh di
    # bawahnya) — BUKAN dipasangkan 2-kolom seperti bar/donut. Batang proporsi cuma
    # setinggi ~46px, kalau dipaksa sejajar dgn panel legend yang jauh lebih tinggi
    # (side-by-side) bakal menyisakan ruang kosong besar di sampingnya — persis kelas
    # masalah "ruang kosong tidak proporsional" yang sudah diperbaiki di bagian lain.
    if ctx.category_style == "stacked":
        body = chart_html + legend_panel
    else:
        body = _main_panel_pair(chart_html, legend_panel, 58, ctx.panel_side)
    inner = (
        _kicker(ctx.kicker_analisis, ctx.accent_main) + _title(block["title"]) +
        f'<div style="font-size:11pt;color:{GRAY_TEXT};margin-bottom:16px;max-width:9.5in;">{_esc(block["intro"])}</div>' +
        body + caption_html
    )
    return (inner, False, None, False)


def _build_severity_distribution_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    # SEVERITY_COLOR TIDAK PERNAH ikut tema — warna severity (critical=merah, high=emas, dst)
    # adalah konvensi semantik cyber-security yang fixed, terlepas dari theme_color laporan.
    sev_colors = [SEVERITY_COLOR[k] for k in block["severity_keys"]]
    chart_html = _bar_chart_html(block["categories"], block["values"], colors=sev_colors)
    panel = _critical_highlight_panel(f'{block["crit_pct"]}%', block["panel_text"], block["detail_text"], theme=ctx.theme)
    caption_html = _note_box_html(block["ai_caption"], theme=ctx.theme) if block.get("ai_caption") else ""
    inner = (
        _kicker(ctx.kicker_analisis, ctx.accent_main) + _title(block["title"]) +
        f'<div style="font-size:11pt;color:{GRAY_TEXT};margin-bottom:16px;max-width:9.5in;">{_esc(block["intro"])}</div>' +
        _main_panel_pair(chart_html, panel, 62, ctx.panel_side) + caption_html
    )
    return (inner, False, None, False)


def _build_status_distribution_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    caption_html = _note_box_html(block["ai_caption"], theme=ctx.theme) if block.get("ai_caption") else ""
    intro_html = f'<div style="font-size:11pt;color:{GRAY_TEXT};margin-bottom:16px;max-width:9.5in;">{_esc(block["intro"])}</div>'
    # accent_light/accent_soft dilewatkan _light_safe() — kedua peran ini SENGAJA pucat di
    # tema "gold" (dirancang utk teks di atas latar gelap, lihat docstring _light_safe),
    # tanpa ini segmen ke-3/ke-4 chart di panel BERLATAR TERANG ini nyaris tak kelihatan.
    ramp = [ctx.accent_main, ctx.accent_chart, _light_safe(ctx.accent_light), _light_safe(ctx.accent_soft), GRAY_TEXT]
    # Titik variasi tampilan (independen dari category_style — lihat status_style di
    # generate_pdf_report): donut butuh panel legend berdampingan (warna donut tidak
    # ber-label sendiri, beda dari bar chart yang sumbu kategorinya sudah jadi label),
    # jadi strukturnya digeser ke pola _main_panel_pair yang sama dgn category_distribution.
    if ctx.status_style == "funnel":
        # Status penanganan = alur bertingkat (Open -> Investigating -> Resolved, dst) —
        # funnel cocok scr karakter data (bukan cuma proporsi kategori lepas), diurutkan dari
        # jumlah terbesar ke terkecil supaya bentuk funnel-nya wajar (mengecil ke bawah).
        order = sorted(range(len(block["values"])), key=lambda i: -block["values"][i])
        cats_sorted = [block["categories"][i] for i in order]
        vals_sorted = [block["values"][i] for i in order]
        body = _funnel_chart_svg(cats_sorted, vals_sorted, color=ctx.accent_main)
    elif ctx.status_style in ("donut", "stacked"):
        status_total = sum(block["values"]) or 1
        status_colors = [ramp[i % len(ramp)] for i in range(len(block["values"]))]
        legend_rows_html = _legend_rows([
            (status_colors[i], name, f"{round(val / status_total * 100, 1)}%")
            for i, (name, val) in enumerate(zip(block["categories"], block["values"]))
        ], theme=ctx.theme)
        legend_title = "Status Proportion" if is_english(ctx.report) else "Proporsi Status"
        legend_panel = _ivory_panel("%", legend_title, legend_rows_html, theme=ctx.theme)
        if ctx.status_style == "donut":
            chart_html = _donut_chart_svg(block["values"], colors=status_colors, size=280, stroke_w=44)
            body = _main_panel_pair(chart_html, legend_panel, 58, ctx.panel_side)
        else:
            # "stacked" ditumpuk vertikal (bukan berdampingan) — lihat catatan sama
            # di category_distribution soal kenapa batang pendek tidak dipasangkan
            # sejajar dengan panel legend yang jauh lebih tinggi.
            chart_html = _stacked_proportion_bar_html(block["values"], colors=status_colors)
            body = chart_html + legend_panel
    else:
        body = _bar_chart_html(block["categories"], block["values"], colors=[ctx.accent_bar_color] * len(block["values"]))
    inner = (
        _kicker(ctx.kicker_analisis, ctx.accent_main) + _title(block["title"]) +
        intro_html + body + caption_html
    )
    return (inner, False, None, False)


def _build_critical_table_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    table_html = _critical_table(block["headers"], block["rows"], set(block["highlight_idx"]), theme=ctx.theme)
    caption_html = ""
    if block["caption"]:
        caption_html = (
            f'<div style="font-size:9.5pt;font-style:italic;color:{GRAY_TEXT};margin-top:12px;">'
            f'{_esc(block["caption"])}</div>'
        )
    # RED_CRIT TIDAK ikut tema (severity fixed) — cuma cabang "tidak kritis" yang ikut tema.
    kicker_color = RED_CRIT if block["kicker_is_critical"] else ctx.accent_main
    inner = (
        _kicker(block["kicker"], kicker_color) + _title(block["title"]) +
        table_html + caption_html
    )
    return (inner, False, None, False)


def _build_asset_cards_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    # Podium (lihat _podium_row) BUTUH tepat 3 entitas & latar terang (blok podium
    # berwarna dirancang menonjol di atas putih, seperti referensi "Sorotan
    # Performa") — kartu sejajar biasa tetap dipakai kalau bukan 3 atau kalau
    # asset_style="cards" kepilih.
    if ctx.asset_style == "podium" and len(block["items"]) == 3:
        podium_items = [{"num": it["num"], "name": it["name"], "stat": it["stat"]} for it in block["items"]]
        inner = (
            _kicker(block["kicker"], ctx.accent_main) + _title(block["title"]) +
            f'<div style="margin-top:20pt;">{_podium_row(podium_items, theme=ctx.theme)}</div>'
        )
        return (inner, False, None, False)
    elif ctx.asset_style == "bars":
        bar_items = [
            {"num": it["num"], "name": it["name"], "stat": it["stat"], "count": it.get("count", 0)}
            for it in block["items"]
        ]
        inner = (
            _kicker(block["kicker"], ctx.accent_light) +
            f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:20pt;color:#fff;margin-bottom:14px;">{_esc(block["title"])}</div>' +
            f'<div style="margin-top:8pt;">{_asset_ranked_bars_html(bar_items, theme=ctx.theme)}</div>'
        )
        return (inner, True, None, False)
    else:
        card_items = [(it["num"], it["name"], it["stat"], it["detail"]) for it in block["items"]]
        inner = (
            _kicker(block["kicker"], ctx.accent_light) +
            f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:20pt;color:#fff;margin-bottom:18px;">{_esc(block["title"])}</div>' +
            _asset_card_row(card_items, theme=ctx.theme)
        )
        return (inner, True, None, False)


def _build_key_findings_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    # PERMINTAAN USER (berkali-kali — halaman sudah ditengahkan tapi tetap terasa kosong
    # kalau isinya cuma 1-3 temuan singkat): baris temuan diperbesar proporsional saat
    # jumlahnya sedikit, bukan cuma dibiarkan kecil-kecil ditengah ruang lapang.
    n_items = len(block["items"])
    row_scale = 1.35 if n_items <= 2 else (1.15 if n_items == 3 else 1.0)
    # RED_CRIT TIDAK ikut tema (severity fixed) — cuma cabang "tidak kritis" yang ikut tema.
    findings_html_parts = [
        _badge_row(it["num"], it["title"], it["detail"], RED_CRIT if it["is_critical"] else ctx.accent_main, scale=row_scale)
        for it in block["items"]
    ]
    findings_html = "".join(findings_html_parts)
    if block.get("chart"):
        chart_html = _mini_chart_html(block["chart"], ctx)
        body = _main_panel_pair(findings_html, chart_html, 62, ctx.panel_side)
    else:
        body = findings_html
    inner = _kicker(block["kicker"], ctx.accent_main) + _title(block["title"]) + body
    return (inner, False, None, False)


def _build_recommendations_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    # Timeline (lihat _timeline_html) cocok utk jumlah item sedang (2-6) — kalau
    # lebih banyak, node/label jadi terlalu sempit & kartu grid tetap lebih rapi.
    if ctx.recommendation_style == "timeline" and 2 <= len(block["items"]) <= 6:
        inner = _kicker(block["kicker"], ctx.accent_main) + _title(block["title"]) + _timeline_html(block["items"], theme=ctx.theme)
    elif ctx.recommendation_style == "banners":
        inner = (
            _kicker(block["kicker"], ctx.accent_main) + _title(block["title"]) +
            f'<div style="margin-top:8pt;">{_recommendation_banner_list_html(block["items"], theme=ctx.theme)}</div>'
        )
    else:
        # Height eksplisit dihapus (lihat catatan di _card_grid) — kartu sepadat
        # kontennya, baris otomatis setinggi kartu terpanjang di baris itu saja.
        cell_htmls = []
        for it in block["items"]:
            detail_html = f'<div style="font-size:9.5pt;color:{GRAY_TEXT};margin-top:6px;">{_esc(it["detail"])}</div>' if it["detail"] else ""
            cell_htmls.append(
                f'<table style="width:100%;margin-bottom:12pt;background:{IVORY};border:1px solid {PANEL_BORDER};border-radius:10px;"><tr><td style="vertical-align:top;padding:14pt;">'
                f'{_badge(it["num"], ctx.accent_light, size="28px")}'
                f'<div style="font-weight:700;font-size:11pt;color:{TEXT_DARK};margin-top:10px;">{_esc(it["title"])}</div>'
                f'{detail_html}</td></tr></table>'
            )
        inner = _kicker(block["kicker"], ctx.accent_main) + _title(block["title"]) + _card_grid(cell_htmls, ctx.card_cols)
    return (inner, False, None, False)


def _build_conclusion_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    pills_html = "".join(_pill(p, theme=ctx.theme) for p in block["pills"])
    priority_items = [(p["letter"], p["text"]) for p in block["priority_items"]]
    priority_html = _priority_panel(block["priority_panel_title"], priority_items, theme=ctx.theme) if priority_items else ""
    concl_left = (
        f'<div style="font-size:11pt;color:#E8ECE6;margin-bottom:18px;max-width:{"9.5in" if not priority_html else "100%"};">{_esc(block["text"])}</div>'
        f'{pills_html}'
    )
    header_html = (
        _kicker(block["kicker"], ctx.accent_light) +
        f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:20pt;color:#fff;margin-bottom:16px;">{_esc(block["title"])}</div>'
    )
    if priority_html:
        # panel_side cuma dipakai kalau priority_html benar-benar ada isinya — kalau
        # kosong (tidak ada rekomendasi BARU, lihat report_render_logic.py), 2 kolom
        # (58/42) menyisakan kolom kanan kosong — lebih buruk daripada teks lebar penuh.
        inner = header_html + _main_panel_pair(concl_left, priority_html, 58, ctx.panel_side)
    else:
        inner = header_html + concl_left
    return (inner, True, None, False)


def _build_closing_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    if ctx.cover_style == "split":
        # Bookend dgn cover: panel kiri warna emas mengulang angka hero yang sama.
        closing_block = {**block, "hero_stat": ctx.cover_hero_stat}
        return (_split_closing_td(closing_block, ctx.flourish_corner, logo_b64=ctx.logo_b64, theme=ctx.theme), True, None, True, True)
    else:
        # Spacer sibling, bukan margin-top pada div pembungkus — lihat catatan panjang
        # di slide "cover" di atas (bug yang sama persis, ini slide yang jadi bukti
        # nyatanya: judul "Terima Kasih" hilang kepotong ke atas halaman sebelum fix).
        inner = (
            f'<div style="height:1.6in;font-size:1px;line-height:1px;">&nbsp;</div>'
            f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:30pt;color:#fff;margin-bottom:10px;">{_esc(block["thank_you"])}</div>'
            f'<div style="font-size:12pt;color:#fff;margin-bottom:8px;">{_esc(block["title"])}</div>'
            f'<div style="font-size:10.5pt;font-style:italic;color:{ctx.accent_soft};">{_esc(block["note"])}</div>'
        )
        return (inner, True, ctx.flourish_corner, True)


def _build_management_kpi_grid_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    items = block.get("items", [])
    cell_htmls = []
    # BUG DIPERBAIKI (dilaporkan user): "blue"/"green"/"amber" SEBELUMNYA warna literal tetap
    # (biru/hijau/emas baku), sama sekali tidak ikut report.theme_color — laporan yang temanya
    # navy/dark/gold tetap tampil kartu biru-hijau-emas yang tidak nyambung. Ketiganya (netral/
    # capaian-baik/sorotan, BUKAN status bahaya) sekarang diturunkan dari palet tema, sama
    # seperti elemen lain di laporan. "red"/"orange"/"gray" TETAP warna semantik tetap (bahaya/
    # peringatan/netral-pasif) — konvensi yang sama dgn SEVERITY_COLOR di tempat lain, TIDAK
    # boleh ikut tema supaya makna "kritis" tetap konsisten dikenali di tema apa pun.
    color_map = {
        "blue": ctx.accent_main,
        "green": ctx.accent_chart,
        "amber": _light_safe(ctx.accent_light),
        "red": RED_CRIT,
        "orange": "#EA580C",
        "gray": GRAY_TEXT,
    }
    # PERMINTAAN USER (berkali-kali — "kalau masih kosong di bawah, GEDEIN aja fontnya/
    # kotaknya"): kartu SEBELUMNYA selalu ukuran tetap (angka 34pt, padding 16pt) apa pun
    # jumlah kartunya — kalau cuma 2-3 kartu (1 baris), sisa halaman di bawah grid kosong
    # total walau sudah ditengahkan vertikal. Sekarang ukuran ikut jumlah BARIS (bukan cuma
    # posisinya) — makin sedikit baris, kartu (& angka di dalamnya) makin besar, pola sama
    # dgn yg sudah dipakai di add_stat_card_grid versi PPT.
    grid_cols = 2 if len(items) in (2, 4) else 3
    rows = math.ceil(len(items) / grid_cols) if items else 1
    scale = {1: 1.55, 2: 1.2}.get(rows, 1.0)
    # padding dinaikkan LEBIH agresif drpd font (padding "gratis" mengisi ruang tanpa bikin
    # angka terlihat aneh raksasa) — kartu jadi benar2 lebih TINGGI, bukan cuma angkanya besar.
    pad_scale = {1: 2.6, 2: 1.5}.get(rows, 1.0)
    value_pt = round(34 * scale)
    label_pt = round(9.5 * scale)
    pad_pt = round(16 * pad_scale)
    dot_px = round(10 * scale)
    for item in items:
        col = color_map.get(item.get("color", "blue"), ctx.accent_main)
        delta_html = f'<div style="font-size:{round(9*scale)}pt;font-weight:600;color:{GRAY_TEXT};margin-top:{round(6*scale)}px;">{_esc(item["delta"])}</div>' if item.get("delta") else ""
        # Kartu KPI diperbesar (angka 34pt, dot warna, padding lapang) — identitas "Visual
        # tinggi, KPI ringkas" template ini, beda dgn kartu di SOC Technical Report yang lebih
        # sedang ukurannya krn di sana angka cuma salah satu elemen, bukan sorotan utama.
        cell_htmls.append(
            f'<table style="width:100%;margin-bottom:14pt;background:{IVORY};border:1.5px solid {col}40;border-radius:14px;"><tr><td style="vertical-align:top;padding:{pad_pt}pt;">'
            f'<table cellpadding="0" cellspacing="0"><tr>'
            f'<td style="width:{dot_px}px;height:{dot_px}px;background:{col};border-radius:{round(dot_px/2)}px;font-size:1px;">&nbsp;</td>'
            f'<td style="padding-left:8px;font-size:{label_pt}pt;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:{col};">{_esc(item["label"])}</td>'
            f'</tr></table>'
            f'<div style="font-family:{TITLE_FONT};font-size:{value_pt}pt;font-weight:900;color:{col};margin-top:8px;">{_esc(item["value"])}</div>'
            f'{delta_html}'
            f'</td></tr></table>'
        )
    # Kolom grid menyesuaikan JUMLAH kartu sungguhan — dulu SELALU 3 kolom apa pun jumlah
    # kartunya, kalau totalnya mis. 4 (bukan kelipatan 3), baris terakhir cuma terisi 1 dari
    # 3 sel (2 sel kosong lebar), halaman jadi terlihat timpang/kurang padat.
    inner = _kicker(block.get("kicker", ""), ctx.accent_main) + _title(block.get("title", "")) + _card_grid(cell_htmls, grid_cols)
    return (inner, False, None, False)


def _mgmt_tile_chart_html(tile: dict, ctx: "_PdfBlockContext") -> str:
    """Chart KOMPAK per tile dashboard (_build_management_visual_dashboard_block di bawah) —
    ukuran sengaja lebih kecil drpd versi 1-halaman-penuh yang dulu dipakai builder terpisah
    (mis. radar dulu size=300 -> 190, heatmap cell dulu 32 -> 20) supaya 4-6 tile muat
    berdampingan dlm 1 halaman, konsisten dgn permintaan user: laporan "Visual tinggi"
    ditumpuk banyak chart macam-macam dlm 1 halaman, BUKAN 1 chart per halaman."""
    kind = tile["tile_kind"]
    if kind == "risk_heatmap":
        bars = tile.get("bars", [])[:5]
        is_severity = tile.get("mode") == "severity"
        if is_severity:
            # Severity TETAP warna semantik tetap (konvensi sama dgn SEVERITY_COLOR di
            # seluruh file ini) — TIDAK boleh ikut tema.
            color_map = {"red": RED_CRIT, "orange": "#EA580C", "amber": GOLD_MAIN, "blue": "#2563EB", "gray": GRAY_TEXT}
        else:
            color_map = {"blue": ctx.accent_main, "green": ctx.accent_chart, "amber": _light_safe(ctx.accent_light), "orange": _light_safe(ctx.accent_soft), "gray": GRAY_TEXT, "red": ctx.accent_main}
        colors = [color_map.get(b.get("color", "gray"), ctx.accent_main) for b in bars]
        labels = [b["label"] for b in bars]
        values = [b["count"] for b in bars]
        # Bentuk visual ikut category_style/status_style yang SAMA dgn laporan gaya SOC
        # (mode kategori pakai category_style, mode severity pakai status_style) — BUG YANG
        # DIPERBAIKI (dilaporkan user, "itu-itu aja"): tile ini dulu SELALU batang polos apa
        # pun kombinasi tampilan yang terkunci utk laporan ini, beda dari laporan SOC yang
        # sudah bervariasi (donat/susun/corong bergantian tiap generate). Ukuran tetap
        # kompak (bukan versi 1-halaman-penuh) supaya tetap muat berdampingan di grid tile.
        style = ctx.status_style if is_severity else ctx.category_style
        if style == "donut":
            return _donut_chart_svg(values, colors=colors, size=150, stroke_w=24) + _mini_legend_html(labels, colors)
        if style == "stacked":
            return _stacked_proportion_bar_html(values, colors=colors, height_px=24) + _mini_legend_html(labels, colors)
        if style == "funnel" and is_severity:
            order = sorted(range(len(values)), key=lambda i: -values[i])
            return _funnel_chart_svg([labels[i] for i in order], [values[i] for i in order], color=ctx.accent_main)
        return _bar_chart_html(labels, values, colors=colors)
    if kind == "kpi_radar":
        # label_margin dikecilkan (100 -> 55) khusus di sini — di ukuran kompak tile ini,
        # margin default 100px akan bikin r_max negatif (chart rusak), lihat docstring
        # _radar_chart_svg.
        return _radar_chart_svg(tile["axes"], tile["values"], color=ctx.accent_main, size=220, label_margin=55)
    if kind == "status_funnel":
        return _funnel_chart_svg(tile["categories"], tile["values"], color=ctx.accent_main, size_w=260, size_h=165)
    if kind == "period_compare":
        return _grouped_bar_chart_svg(
            tile["categories"], tile["series_a"], tile["series_b"],
            label_a=tile["label_a"], label_b=tile["label_b"],
            color_a=ctx.accent_main, color_b=ctx.accent_chart, size_w=320, size_h=165,
        )
    if kind == "time_heatmap":
        return _heatmap_grid_svg(tile["day_labels"], tile["hour_labels"], tile["grid"], color=ctx.accent_main, cell=20)
    if kind == "trend_chart":
        chart = tile["chart"]
        if chart["type"] == "bar_line":
            return _bar_line_chart_svg(chart["categories"], chart["values"], chart.get("cumulative"), color=ctx.accent_main, size_w=320, size_h=150)
        return _bar_chart_html(chart["categories"], chart["values"], colors=[ctx.accent_main] * len(chart["values"]))
    if kind == "custom_topic":
        # PERMINTAAN USER (Management Report "harus lebih banyak visualisasi"): section
        # custom tulisan AI yang punya data perbandingan kategori (field "chart" dari AI,
        # lihat get_analysis_prompt) digambar sbg chart sungguhan di sini, bukan kartu teks —
        # bentuknya gantian bar/donat/susun per tile (lihat _custom_chart_styles di
        # build_management_report_blocks) supaya tidak seragam semua.
        labels, values = tile.get("labels", []), tile.get("values", [])
        ramp = [ctx.accent_main, ctx.accent_chart, _light_safe(ctx.accent_light), _light_safe(ctx.accent_soft), GRAY_TEXT, ctx.accent_main]
        colors = [ramp[i % len(ramp)] for i in range(len(values))]
        style = tile.get("chart_style", "bar")
        if style == "donut":
            return _donut_chart_svg(values, colors=colors, size=150, stroke_w=24) + _mini_legend_html(labels, colors)
        if style == "stacked":
            return _stacked_proportion_bar_html(values, colors=colors, height_px=24) + _mini_legend_html(labels, colors)
        return _bar_chart_html(labels, values, colors=colors)
    return ""


def _build_management_visual_dashboard_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    # PERMINTAAN USER: sebelumnya tiap jenis chart (peta risiko/radar/funnel/perbandingan
    # periode/heatmap waktu/tren) jadi halamannya sendiri-sendiri — "1 chart per halaman"
    # berkali-kali, bukan benar2 padat. Sekarang ditumpuk jadi 1 grid (4/5/lebih tile
    # sekaligus, macam-macam bentuk chart), keterangan tiap tile dipangkas jadi 1 kalimat
    # (lihat "caption" per tile, dibangun di build_management_report_blocks).
    tiles = block.get("tiles", [])
    cell_htmls = []
    for t in tiles:
        caption_html = f'<div style="font-size:8.5pt;color:{GRAY_TEXT};margin-top:8px;line-height:1.5;">{_esc(t["caption"])}</div>' if t.get("caption") else ""
        cell_htmls.append(
            f'<table style="width:100%;background:{IVORY};border:1px solid {PANEL_BORDER};border-radius:12px;"><tr><td style="vertical-align:top;padding:14pt;">'
            f'<div style="font-size:9.5pt;font-weight:800;text-transform:uppercase;letter-spacing:0.04em;color:{ctx.accent_main};margin-bottom:8px;">{_esc(t.get("title", ""))}</div>'
            f'{_mgmt_tile_chart_html(t, ctx)}'
            f'{caption_html}'
            f'</td></tr></table>'
        )
    # 3 kolom kalau tile-nya banyak (5-6, chart kompak masih cukup lega), 2 kolom kalau
    # sedikit (2-4, chart dapat ruang lebih lapang) — sama prinsipnya dgn grid_cols adaptif
    # di _build_management_kpi_grid_block.
    cols = 3 if len(tiles) >= 5 else 2
    inner = _kicker(block.get("kicker", ""), ctx.accent_main) + _title(block.get("title", "")) + _card_grid(cell_htmls, cols)
    return (inner, False, None, False)


def _build_management_action_items_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    urgency_color = {
        "critical": (RED_CRIT, RED_CRIT_BG),
        "high": ("#EA580C", "#FFF7ED"),
        "medium": (GOLD_MAIN, GOLD_CREAM_SOFT),
        "low": ("#2563EB", "#EFF6FF"),
    }
    cards_html = ""
    for it in block.get("items", []):
        fg, bg = urgency_color.get(it.get("urgency", "low"), (ctx.accent_main, IVORY))
        detail = f'<div style="font-size:9pt;color:{GRAY_TEXT};margin-top:4px;line-height:1.4;">{_esc(it.get("detail", ""))}</div>' if it.get("detail") else ""
        cards_html += (
            f'<table style="width:100%;margin-bottom:8pt;background:{bg};border:1px solid {fg}35;border-radius:10px;"><tr>'
            f'<td style="width:36px;vertical-align:middle;text-align:center;padding:8pt;">'
            f'<div style="width:26px;height:26px;line-height:26px;border-radius:13px;background:{fg};color:#fff;font-weight:900;font-size:10pt;margin:0 auto;">{it.get("number", 1)}</div>'
            f'</td>'
            f'<td style="vertical-align:middle;padding:8pt 8pt 8pt 0;">'
            f'<div style="font-weight:800;font-size:10.5pt;color:{TEXT_DARK};">{_esc(it.get("title", ""))}</div>'
            f'{detail}'
            f'</td>'
            f'<td style="width:80px;vertical-align:middle;text-align:right;padding-right:12pt;">'
            f'<span style="display:inline-block;padding:2px 8px;border-radius:10px;background:{fg};color:#fff;font-size:7.5pt;font-weight:800;text-transform:uppercase;">{_esc(it.get("urgency", ""))}</span>'
            f'</td>'
            f'</tr></table>'
        )
    inner = _kicker(block.get("kicker", ""), ctx.accent_main) + _title(block.get("title", "")) + cards_html
    return (inner, False, None, False)


def _build_management_asset_ranking_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    # Versi padat/batang khas Management Report — meniru persis cabang "bars" di
    # _build_asset_cards_block di atas, tapi TIDAK ikut ctx.asset_style (dipaksa selalu
    # batang, supaya konsisten padat, tidak ikut pengacakan kartu/podium gaya SOC).
    bar_items = [
        {"num": it["num"], "name": it["name"], "stat": it["stat"], "count": it.get("count", 0)}
        for it in block.get("items", [])
    ]
    inner = (
        _kicker(block.get("kicker", ""), ctx.accent_light) +
        f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:20pt;color:#fff;margin-bottom:14px;">{_esc(block.get("title", ""))}</div>' +
        f'<div style="margin-top:8pt;">{_asset_ranked_bars_html(bar_items, theme=ctx.theme)}</div>'
    )
    return (inner, True, None, False)


def _build_management_ai_narrative_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    # Narasi bebas tulisan AI (setara dynamic_section gaya SOC), ditampilkan sbg grid kartu
    # ivory meniru gaya tile _build_management_visual_dashboard_block di atas — supaya
    # terasa menyatu dgn halaman dashboard visual, bukan tempelan gaya SOC.
    # PERMINTAAN USER: (1) halaman ini terasa "cuma tulisan" utk gaya Management yang
    # seharusnya lebih visual — ditambah aksen bar warna + badge nomor bulat di tiap kartu,
    # senada dgn kartu KPI/dashboard tile di halaman lain (bukan cuma teks polos berbaris).
    # (2) kalau itemnya sedikit, kartu & fontnya diperbesar DAN grid dipaksa 1 kolom (lebar
    # penuh) supaya tidak menyisakan kolom kosong di samping.
    items = block.get("items", [])
    n = len(items)
    cols = 1 if n <= 1 else 2
    scale = 1.3 if n <= 2 else 1.0
    cell_htmls = []
    for idx, it in enumerate(items):
        badge_html = _badge(str(idx + 1), ctx.accent_main, size=f"{round(20*scale)}px", font_size=f"{9*scale:.1f}pt")
        cell_htmls.append(
            f'<table style="width:100%;background:{IVORY};border:1px solid {PANEL_BORDER};'
            f'border-left:4px solid {ctx.accent_main};border-radius:10px;"><tr><td style="vertical-align:top;padding:{round(14*scale)}pt;">'
            f'<table cellpadding="0" cellspacing="0"><tr>'
            f'<td style="width:{round(20*scale)+10}px;vertical-align:middle;">{badge_html}</td>'
            f'<td style="vertical-align:middle;font-size:{9.5*scale:.1f}pt;font-weight:800;text-transform:uppercase;letter-spacing:0.04em;color:{ctx.accent_main};">{_esc(it.get("title", ""))}</td>'
            f'</tr></table>'
            f'<div style="margin-top:{round(8*scale)}px;">{_bullet_lines_html(it.get("content", ""), theme=ctx.theme, font_pt=round(9*scale))}</div>'
            f'</td></tr></table>'
        )
    inner = _kicker(block.get("kicker", ""), ctx.accent_main) + _title(block.get("title", "")) + _card_grid(cell_htmls, cols)
    return (inner, False, None, False)


# Panel-builder registry (dikunci per "panel_kind", BUKAN per "kind" halaman) — 1 halaman
# (kind="page", lihat build_report_blocks tahap 2 di report_render_logic.py) bisa berisi 1-3
# panel yang dirender lewat registry ini, disusun otomatis oleh _build_page_block di bawah.
# Semua fungsi di sini "mandiri" (judul kicker+title sendiri di dalam kontennya) KECUALI
# _panel_insight_card (dipakai insight_tile & dynamic_section, TIDAK punya judul sendiri —
# judulnya dari halaman, lihat _group_candidates_into_pages/_page_from_panels yg menjaga
# panel bertema "insight" tidak pernah tercampur dgn panel mandiri di 1 halaman yang sama).
_PDF_PANEL_BUILDERS = {
    "executive_summary": _build_executive_summary_block,
    "insight_tile": _panel_insight_card,
    "dynamic_section": _panel_insight_card,
    "category_distribution": _build_category_distribution_block,
    "status_distribution": _build_status_distribution_block,
    "severity_distribution": _build_severity_distribution_block,
    "kpi_radar": _build_kpi_radar_block,
    "time_heatmap": _build_time_heatmap_block,
    "period_compare": _build_period_compare_block,
    "critical_table": _build_critical_table_block,
    "asset_cards": _build_asset_cards_block,
    "key_findings": _build_key_findings_block,
    "recommendations": _build_recommendations_block,
    "conclusion": _build_conclusion_block,
}

_PANEL_NEEDS_PAGE_HEADER = {"insight_tile", "dynamic_section"}


def _build_page_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    """Composer generik: 1 halaman = 1-3 panel (block["panels"], lihat report_render_logic.py
    tahap 2). Panel "mandiri" (category_distribution dkk) sudah bawa kicker+title sendiri di
    kontennya — dipakai APA ADANYA. Panel "insight_tile"/"dynamic_section" TIDAK bawa judul
    sendiri (kartu ringkas, lihat _panel_insight_card) — kalau salah satu panel di halaman ini
    jenis itu, judul halaman (block["kicker"]/["title"], hasil _page_from_panels) ditambahkan
    SEKALI di atas grid panel. 1 panel -> lebar penuh (sama seperti sebelum refactor ini,
    dark diambil dari HASIL RENDER panel itu sendiri, bukan cuma block["dark"] — beberapa
    panel mis. asset_cards bisa override dark tergantung gaya kartu yang kepilih, lihat
    _build_asset_cards_block). >1 panel -> disusun berdampingan N kolom (pola yang sama
    dgn distribution_dashboard/insight_dashboard versi lama, cuma digeneralisasi)."""
    panels = block["panels"]
    htmls, dark = [], block["dark"]
    needs_header = any(p["panel_kind"] in _PANEL_NEEDS_PAGE_HEADER for p in panels)
    ctx.panel_count = len(panels)
    for p in panels:
        builder = _PDF_PANEL_BUILDERS.get(p["panel_kind"])
        if not builder:
            continue
        html, panel_dark, _flourish, _last = builder(p, ctx)
        htmls.append(html)
        if len(panels) == 1:
            dark = panel_dark
    if not htmls:
        return ("", dark, None, False)
    header = ""
    if needs_header and block.get("title"):
        if dark:
            header = (
                _kicker(block.get("kicker"), ctx.accent_light) +
                f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:20pt;color:#fff;margin-bottom:16px;">{_esc(block["title"])}</div>'
            )
        else:
            header = _kicker(block.get("kicker"), ctx.accent_main) + _title(block["title"])
    if len(htmls) == 1:
        body = htmls[0]
    else:
        col_w = round(100 / len(htmls), 3)
        cells = "".join(
            f'<td style="width:{col_w}%;vertical-align:top;{"padding-right:20pt;" if i < len(htmls) - 1 else ""}">{h}</td>'
            for i, h in enumerate(htmls)
        )
        body = f'<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0"><tr>{cells}</tr></table>'
    return (header + body, dark, None, False)


_PDF_BLOCK_BUILDERS = {
    "cover": _build_cover_block,
    "intro": _build_intro_block,
    "page": _build_page_block,
    "closing": _build_closing_block,
    "management_kpi_grid": _build_management_kpi_grid_block,
    "management_visual_dashboard": _build_management_visual_dashboard_block,
    "management_action_items": _build_management_action_items_block,
    "management_asset_ranking": _build_management_asset_ranking_block,
    "management_ai_narrative": _build_management_ai_narrative_block,
}


class PDFExporter:
    @classmethod
    def generate_pdf_report(cls, report: Report) -> bytes:
        if not WEASYPRINT_AVAILABLE and not XHTML2PDF_AVAILABLE:
            raise RuntimeError(
                "Pustaka sistem PDF (WeasyPrint dan xhtml2pdf) tidak ditemukan di sistem Anda. "
                "Silakan install xhtml2pdf atau jalankan aplikasi dengan WeasyPrint terinstal."
            )

        logo_b64 = _resolve_logo_b64()
        _template = (report.template_type or "").strip().lower()
        if "management" in _template:
            blocks = build_management_report_blocks(report)
        else:
            blocks = build_report_blocks(report)

        # Varian tampilan (cover_style, category_style, dst) DIBACA dari report.visual_style,
        # BUKAN di-random di sini lagi — lihat catatan sama di export_ppt.py generate_ppt_report
        # (dan pick_visual_style() di report_render_logic.py) utk alasan lengkapnya: dulu tiap
        # export dapat kombinasi acak baru, sekarang preview web & PDF/PPTX yang diunduh
        # SAMA-SAMA baca kombinasi yang SUDAH DIKUNCI sekali sewaktu analisis AI berhasil, jadi
        # dijamin identik utk 1 laporan yang sama.
        vs = get_visual_style(report)
        flourish_corner = vs["flourish_corner"]
        stat_cols = vs["stat_cols"]
        card_cols = vs["card_cols"]
        panel_side = vs["panel_side"]
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
            # 2 BUG DIPERBAIKI di sini (ditemukan lewat render+sampling langsung, tema
            # kustom belum pernah dicek visual sebelumnya):
            # 1. "soft" sebelumnya "#F3F4F6" (abu-abu nyaris putih, tidak senada) — MISMATCH
            #    dgn preview web (resolveThemeColors di reportTheme.ts pakai GOLD_LIGHT).
            #    "light"/"soft" tetap pasangan gold tetap (sama spt 4 tema bernama).
            # 2. "chart" sebelumnya = "main" APA ADANYA (warna kustom yang SAMA PERSIS) — chart
            #    2-seri (mis. grouped bar "Perbandingan Antar Paruh Periode") & ramp kategori
            #    yang menyelingi accent_main/accent_chart jadi TIDAK BISA DIBEDAKAN sama sekali
            #    (2 batang bersebelahan warnanya identik). "chart" sekarang tint LEBIH TERANG
            #    dari warna kustom yang sama (via _blend_with_white), bukan duplikat exact.
            # 3. "bg" (latar cover/penutup) sebelumnya SELALU "#111827" tetap, terlepas dari
            #    warna kustomnya — cover jadi terlihat seperti tidak menerapkan pilihan warna
            #    user sama sekali (lihat docstring _darken).
            #
            # BUG BESAR TAMBAHAN DIPERBAIKI (dilaporkan user, "warna itu muncul tp ga banyak" +
            # ditemukan lewat render+sampling: pill/badge nyaris tak terbaca kalau warna kustom
            # user KEBETULAN senada dgn gold tetap ini, mis. user pilih kuning/emas sendiri):
            # "light"/"soft" SEBELUMNYA tetap GOLD_MAIN/GOLD_LIGHT (aksen emas TAK TERKAIT warna
            # kustom sama sekali) — dipakai LUAS di kicker/pill/badge/panel gelap di HAMPIR
            # SETIAP halaman, jadi mayoritas aksen laporan tetap emas walau user pilih warna lain
            # sama sekali (persis keluhan "warnanya kurang kelihatan"). Sekarang KEEMPAT peran
            # diturunkan dari SATU hue kustom yang sama (main=gelap, chart=medium, light=terang,
            # soft=paling terang) — pola RAMP SAMA PERSIS yang sudah dipakai tema "gold" bawaan
            # sendiri (GOLD_BRONZE_MAIN -> GOLD_MAIN -> GOLD_CREAM_LIGHT -> GOLD_CREAM_SOFT),
            # cuma huenya ikut pilihan user. Kontras badge/teks tetap terjaga karena _light_safe
            # tetap menggelapkan "light"/"soft" lagi khusus di titik pakai yang butuh (badge fill
            # + teks putih, dst) — di sini cukup pastikan progresi terang MENANJAK & konsisten.
            # BUG YANG DIPERBAIKI (dilaporkan user): "main" kustom dipakai APA ADANYA tanpa
            # jaminan cukup gelap utk teks putih di atasnya (kartu KPI, cover/penutup) — warna
            # terang (mis. ungu muda #CF87DA) bikin teks nyaris tak kelihatan (bg kartu terang +
            # teks putih = kontras nyaris nol). _light_safe() dipakai ulang di sini (ambang 0.45,
            # tepat di atas luminance "main" tema gold bawaan ~0.42, tema PALING terang dari 4
            # tema tetap) supaya "main" kustom SELALU cukup gelap, sebelum jadi basis turunan
            # chart/light/soft di bawah.
            safe_main = _light_safe(theme_key, max_luminance=0.45)
            chart_shade = _blend_with_white(safe_main, 0.6)
            light_shade = _blend_with_white(safe_main, 0.3)
            soft_shade = _blend_with_white(safe_main, 0.12)
            palette = {"main": safe_main, "bg": _darken(safe_main), "chart": chart_shade, "light": light_shade, "soft": soft_shade}
        else:
            palette = THEME_PALETTES["green"]
        accent_bar_color = palette["main"]

        pages = []  # list of (html, dark, flourish, is_last)

        ctx = _PdfBlockContext(
            report=report,
            stat_cols=stat_cols,
            card_cols=card_cols,
            flourish_corner=flourish_corner,
            panel_side=panel_side,
            accent_bar_color=accent_bar_color,
            category_style=category_style,
            status_style=status_style,
            cover_style=cover_style,
            asset_style=asset_style,
            recommendation_style=recommendation_style,
            logo_b64=logo_b64,
            accent_main=palette["main"],
            accent_bg=palette["bg"],
            accent_chart=palette["chart"],
            accent_light=palette["light"],
            accent_soft=palette["soft"],
            theme=palette,
            kicker_ringkasan=kicker_ringkasan,
            kicker_analisis=kicker_analisis,
        )

        page_kinds = []
        for block in blocks:
            builder = _PDF_BLOCK_BUILDERS.get(block["kind"])
            if builder:
                pages.append(builder(block, ctx))
                page_kinds.append(block["kind"])

        # ---------------- Rakit halaman jadi 1 dokumen HTML ----------------
        total_pages = len(pages) - 2  # tidak termasuk cover & penutup di penomoran
        page_html_parts = []
        content_idx = 0
        for i, page_tuple in enumerate(pages):
            # 5-tuple (dgn `raw=True`) dipakai cover/penutup varian split-warna (lihat
            # _split_cover_td/_split_closing_td) — <td> lengkap sudah dibangun sendiri,
            # _page() cuma membungkusnya tanpa background/margin-inset standar.
            if len(page_tuple) == 5:
                inner, dark, flourish, is_last, raw = page_tuple
            else:
                inner, dark, flourish, is_last = page_tuple
                raw = False
            is_cover_or_closing = i == 0 or i == len(pages) - 1
            page_num = None
            if not is_cover_or_closing:
                content_idx += 1
                page_num = content_idx
            # Ditengahkan vertikal HANYA halaman "intro"/"page" (lihat catatan panjang di
            # _page()) — cover/penutup (raw ATAU tidak) tetap posisi absolut aslinya dari atas.
            # BUG KRITIS DIPERBAIKI (dilaporkan user berkali-kali — banyak ruang kosong di
            # bawah halaman): variabel ini SEBELUMNYA hardcode `False` TANPA SYARAT di sini —
            # padahal `_page()` (baris ~1249) sudah lengkap mendukung `center=True` dan
            # komentar di baris ini sendiri sudah menyatakan niatnya, tapi tidak pernah benar2
            # disambungkan ke `block["kind"]`. Akibatnya SEMUA halaman "page"/"intro" (bukan
            # cuma yang baru2 ini diperbaiki) selalu nempel rapat ke atas & menyisakan area
            # kosong di bawah kalau kontennya wajar tidak sampai memenuhi 1 halaman penuh.
            # Diperluas jg ke beberapa kind Management Report (KPI grid/insight AI/action
            # items/ranking aset) — sama-sama daftar/grid berjumlah variabel yang bisa pendek.
            center = page_kinds[i] in (
                "page", "intro", "management_kpi_grid", "management_ai_narrative",
                "management_action_items", "management_asset_ranking",
            )
            # BUG YANG DIPERBAIKI (dilaporkan user): logo dulu sengaja disembunyikan di
            # cover/penutup (logo_b64=None), padahal exporter PPT (add_logo dipanggil di
            # SEMUA slide termasuk cover/penutup, lihat export_ppt.py) sudah benar — jadi
            # PDF jadi satu-satunya tempat identitas brand hilang justru di halaman
            # pembuka & penutup. Disamakan: logo SELALU tampil, nomor halaman saja yang
            # tetap dilewati utk cover/penutup (halaman itu memang tidak diberi nomor).
            page_html_parts.append(_page(
                inner, dark=dark, flourish=flourish,
                page_num=page_num, total_pages=total_pages,
                logo_b64=logo_b64,
                last=is_last, raw=raw, theme=ctx.theme, center=center,
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
                logger.warning(f"WeasyPrint gagal merender: {weasy_err}. Menggunakan fallback xhtml2pdf.")
                if not XHTML2PDF_AVAILABLE:
                    raise weasy_err

        pdf_io = io.BytesIO()
        pisa_status = pisa.CreatePDF(html_content, dest=pdf_io)
        if pisa_status.err:
            raise RuntimeError(f"Gagal mengonversi HTML ke PDF menggunakan xhtml2pdf: {pisa_status.err}")
        return pdf_io.getvalue()
