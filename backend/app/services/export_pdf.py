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
    return (
        f'<div style="display:inline-block;width:{size};height:{size};line-height:{size};'
        f'border-radius:50%;background:{color};text-align:center;color:#fff;font-weight:700;'
        f'font-size:{font_size};font-family:{BODY_FONT};">{_esc(text)}</div>'
    )


def _badge_row(number, title, detail, color=GREEN_MAIN, on_dark=False) -> str:
    # xhtml2pdf (fallback engine kalau WeasyPrint tak tersedia) TIDAK support flexbox —
    # dipakai <table> supaya badge+teks sejajar konsisten di kedua engine.
    #
    # RANCANG ULANG (target WeasyPrint, lihat catatan di _ivory_panel): height eksplisit
    # dihapus — baris sepadat kontennya (detail panjang wrap bebas tanpa risiko kepotong/
    # numpuk), jarak antar baris dinaikkan sedikit (14px) supaya senapas dengan spacing
    # generous di panel-panel lain.
    title_color = WHITE if on_dark else TEXT_DARK
    detail_color = GOLD_LIGHT if on_dark else GRAY_TEXT
    detail_html = f'<div style="font-size:9.5pt;color:{detail_color};margin-top:3px;">{_esc(detail)}</div>' if detail else ""
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


def _donut_chart_svg(values, colors=None, size=210, stroke_w=36) -> str:
    """Alternatif visual utk distribusi kategori (selain _bar_chart_html) — titik variasi
    tampilan antar generate (lihat `category_style` di generate_pdf_report), BUKAN
    penggantian permanen. Donut cincin dibangun dari beberapa <circle> bertumpuk dengan
    stroke-dasharray/-dashoffset (trik SVG standar), bukan wedge/pie asli — lebih sederhana &
    hasilnya tetap rapi utk kategori sampai ~6 nilai. SVG dirender native oleh WeasyPrint,
    tidak perlu library chart eksternal (Kaleido/Plotly SENGAJA tidak dipakai lagi di file
    ini, lihat docstring atas)."""
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
        f'fill="{TEXT_DARK}" font-family="{BODY_FONT}">{total:g}</text>'
        f'<text x="{cx}" y="{cy + 18}" text-anchor="middle" font-size="10.5" fill="{GRAY_TEXT}" '
        f'font-family="{BODY_FONT}">Total</text>'
    )
    svg = (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" '
        f'xmlns="http://www.w3.org/2000/svg">{"".join(segments)}{labels}</svg>'
    )
    return f'<div style="text-align:center;padding:14pt 0;">{svg}</div>'


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


def _critical_highlight_panel(pct_text, sub_text, detail_text=None, theme: dict | None = None) -> str:
    t = theme or THEME_PALETTES["green"]
    detail_html = f'<div style="font-size:9.5pt;color:{t["soft"]};margin-top:14px;">{_esc(detail_text)}</div>' if detail_text else ""
    inner = (
        f'<div style="text-align:center;font-family:{TITLE_FONT};font-weight:700;font-size:34pt;color:{t["light"]};">{_esc(pct_text)}</div>'
        f'<div style="text-align:center;font-size:10.5pt;color:#fff;margin-top:6px;">{_esc(sub_text)}</div>'
        f'{detail_html}'
    )
    return _dark_panel(inner, theme=theme)


def _ai_insight_strip(text) -> str:
    return (
        f'<div style="font-size:9.5pt;font-style:italic;color:{GRAY_TEXT};margin-top:10px;">'
        f'\U0001F4A1 {_esc(text)}</div>'
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


def _timeline_html(items, container_h_pt=230, theme: dict | None = None) -> str:
    """Alternatif visual utk daftar rekomendasi (kartu grid) — titik variasi tampilan (lihat
    `recommendation_style` di generate_pdf_report). items: list of dict {"num","title",
    "detail"}, dirender sebagai roadmap horizontal: garis + node bulat bernomor, label
    berselang-seling di atas/bawah garis (gaya "tindak lanjut" laporan eksekutif). Posisi
    dihitung via CSS transform:translate (dikonfirmasi didukung WeasyPrint lewat isolasi
    render+sampling), BUKAN <table> — perlu node yang duduk TEPAT di tengah satu garis
    horizontal kontinu, sesuatu yang tidak bisa dicapai rapi dengan tabel kolom."""
    t = theme or THEME_PALETTES["green"]
    n = len(items) or 1
    line_y = container_h_pt / 2
    parts = [f'<div style="position:relative;height:{container_h_pt}pt;margin-top:10pt;">']
    parts.append(
        f'<div style="position:absolute;left:3%;right:3%;top:{line_y}pt;height:2pt;background:{t["light"]};"></div>'
    )
    col_w_pct = 100 / n
    for i, it in enumerate(items):
        cx_pct = round((i + 0.5) / n * 100, 3)
        above = (i % 2 == 0)
        node_color = t["light"] if i == 0 else t["main"]
        parts.append(
            f'<div style="position:absolute;left:{cx_pct}%;top:{line_y}pt;transform:translate(-50%,-50%);'
            f'width:24pt;height:24pt;border-radius:50%;background:{node_color};color:#fff;text-align:center;'
            f'line-height:24pt;font-weight:700;font-size:10.5pt;">{_esc(it["num"])}</div>'
        )
        detail_html = f'<div style="font-size:8.5pt;color:{GRAY_TEXT};margin-top:3pt;">{_esc(it["detail"])}</div>' if it.get("detail") else ""
        content_html = f'<div style="font-weight:700;font-size:10pt;color:{TEXT_DARK};">{_esc(it["title"])}</div>{detail_html}'
        stem_h = 20
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
            f'<table style="width:100%;background:{bg};border-left:4px solid {t["light"]};margin-bottom:10pt;" cellpadding="0" cellspacing="0">'
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


def _split_cover_td(block, flourish_corner, theme: dict | None = None) -> str:
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
    right_td = (
        f'<td style="width:{100 - left_w_pct}%;background:{t["bg"]};color:#fff;position:relative;'
        f'height:7.5in;vertical-align:top;font-family:{BODY_FONT};overflow:hidden;">'
        f'{_flourish_html(flourish_corner, theme=t)}'
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


def _split_closing_td(block, flourish_corner="bottom_right", theme: dict | None = None) -> str:
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
    right_td = (
        f'<td style="width:{100 - left_w_pct}%;background:{t["bg"]};color:#fff;position:relative;'
        f'height:7.5in;vertical-align:top;font-family:{BODY_FONT};overflow:hidden;">'
        f'{_flourish_html(flourish_corner, theme=t)}'
        f'<div style="position:relative;margin:0.5in;">'
        f'<div style="height:1.6in;font-size:1px;line-height:1px;">&nbsp;</div>'
        f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:30pt;color:#fff;margin-bottom:10px;">{_esc(block["thank_you"])}</div>'
        f'<div style="font-size:12pt;color:#fff;margin-bottom:8px;">{_esc(block["title"])}</div>'
        f'<div style="font-size:10.5pt;font-style:italic;color:{t["soft"]};">{_esc(block["note"])}</div>'
        f'</div></td>'
    )
    return left_td + right_td


def _page(inner_html, dark=False, flourish=None, page_num=None, total_pages=None, logo_b64=None, last=False, raw=False, theme: dict | None = None) -> str:
    t = theme or THEME_PALETTES["green"]
    break_style = "" if last else "page-break-after:always;"
    if raw:
        # `raw=True`: `inner_html` SUDAH berupa satu/lebih <td> lengkap (mis. cover/penutup
        # varian split-warna, 2 kolom background beda) — dipakai sebagai isi <tr> APA ADANYA,
        # tanpa background/margin-inset/flourish tunggal standar di bawah ini (pemanggil yang
        # bertanggung jawab penuh atas seluruh isi <tr>, termasuk warnanya sendiri).
        return f'<table style="width:13.333in;{break_style}" cellpadding="0" cellspacing="0"><tr>{inner_html}</tr></table>'
    bg = t["bg"] if dark else WHITE
    color = WHITE if dark else TEXT_DARK
    flourish_html = _flourish_html(flourish, theme=t) if flourish else ""
    logo_html = (
        f'<img src="data:image/png;base64,{logo_b64}" style="position:absolute;top:0.3in;right:0.3in;height:40px;" />'
        if logo_b64 else ""
    )
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
    return (
        f'<table style="width:13.333in;{break_style}" cellpadding="0" cellspacing="0">'
        f'<tr><td style="position:relative;background:{bg};color:{color};height:7.5in;vertical-align:top;'
        f'font-family:{BODY_FONT};">'
        f'{flourish_html}{logo_html}'
        f'<div style="margin:0.5in;">{inner_html}</div>'
        f'{footer_html}</td></tr></table>'
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


def _build_cover_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    ctx.cover_hero_stat = block.get("hero_stat")  # dipakai lagi di "closing" (bookend)
    if ctx.cover_style == "split":
        # Varian 2-kolom warna penuh (lihat _split_cover_td) — dipakai via
        # _page(..., raw=True) karena tiap kolom butuh background sendiri penuh
        # 1 halaman, bukan satu warna latar tunggal seperti varian "solid".
        return (_split_cover_td(block, ctx.flourish_corner, theme=ctx.theme), True, None, False, True)
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
            f'<div style="position:absolute;bottom:0;left:0;font-size:9pt;font-weight:700;color:#fff;">{_esc(block["header_title"])}</div>'
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
    inner = (
        _kicker(ctx.kicker_ringkasan, ctx.accent_light) +
        f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:20pt;color:#fff;margin-bottom:18px;">{_esc(block["heading"])}</div>' +
        _stat_card_grid(block["stat_items"], cols=ctx.stat_cols, dark=True, theme=ctx.theme) +
        # max-width dibatasi ~9.5in (bukan full CONTENT_W ~12.3in) — paragraf
        # selebar halaman penuh di kertas widescreen 13.333in menghasilkan baris
        # >150 karakter, jauh melebihi lebar baca nyaman (~75-90 karakter); versi
        # referensi selalu membatasi teks naratif ke lebar yang lebih wajar.
        f'<div style="font-size:10.5pt;font-style:italic;color:{ctx.accent_soft};margin-top:18px;max-width:9.5in;">{_esc(block["caption"])}</div>'
    )
    return (inner, True, None, False)


def _build_dynamic_section_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    text_html = f'<div style="font-size:11.5pt;color:{GRAY_TEXT};max-width:9.5in;">{_esc(block["text"])}</div>'
    if block.get("aux_stat"):
        value, label = block["aux_stat"]
        panel_html = _critical_highlight_panel(value, label, theme=ctx.theme)
        body = _main_panel_pair(text_html, panel_html, 62, ctx.panel_side)
    elif block.get("aux_list"):
        rows_html = _ivory_kv_rows([(it["label"], it["value"]) for it in block["aux_list"]], theme=ctx.theme)
        panel_title = "Data Highlight" if is_english(ctx.report) else "Sorotan Data"
        panel_html = _ivory_panel("i", panel_title, rows_html, theme=ctx.theme)
        body = _main_panel_pair(text_html, panel_html, 62, ctx.panel_side)
    else:
        body = text_html
    inner = _kicker(block["kicker"], ctx.accent_main) + _title(block["title"]) + body
    return (inner, False, None, False)


def _build_category_distribution_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    # Ramp warna kategori/status DITURUNKAN dari tema (report.theme_color), bukan konstanta
    # hijau/emas tetap — supaya chart multi-segmen (donut/stacked) ikut tema, sama seperti
    # bar chart utama. GRAY_TEXT tetap sebagai warna ke-5 (netral, dipakai kalau kategori > 4).
    ramp = [ctx.accent_main, ctx.accent_chart, ctx.accent_light, ctx.accent_soft, GRAY_TEXT]
    legend = _legend_rows([
        (ramp[l["color_index"] % len(ramp)], l["name"], f"{l['pct']}%") for l in block["legend"]
    ], theme=ctx.theme)
    legend_panel = _ivory_panel("%", block["legend_panel_title"], legend, footnote=block["footnote"], theme=ctx.theme)
    # Titik variasi tampilan: bar horizontal (warna accent hijau/emas gantian per
    # generate), donut ring multi-warna, ATAU batang proporsi 100% bersegmen (lihat
    # category_style/accent_bar_color di generate_pdf_report) — datanya identik,
    # cuma cara visualnya beda tiap generate.
    if ctx.category_style == "donut":
        chart_html = _donut_chart_svg(block["values"], colors=[ramp[l["color_index"] % len(ramp)] for l in block["legend"]])
    elif ctx.category_style == "stacked":
        seg_colors = [ramp[l["color_index"] % len(ramp)] for l in block["legend"]]
        chart_html = _stacked_proportion_bar_html(block["values"], colors=seg_colors)
    else:
        chart_html = _bar_chart_html(block["categories"], block["values"], colors=[ctx.accent_bar_color] * len(block["values"]))
    caption_html = _ai_insight_strip(block["ai_caption"]) if block.get("ai_caption") else ""
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
    caption_html = _ai_insight_strip(block["ai_caption"]) if block.get("ai_caption") else ""
    inner = (
        _kicker(ctx.kicker_analisis, ctx.accent_main) + _title(block["title"]) +
        f'<div style="font-size:11pt;color:{GRAY_TEXT};margin-bottom:16px;max-width:9.5in;">{_esc(block["intro"])}</div>' +
        _main_panel_pair(chart_html, panel, 62, ctx.panel_side) + caption_html
    )
    return (inner, False, None, False)


def _build_status_distribution_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    caption_html = _ai_insight_strip(block["ai_caption"]) if block.get("ai_caption") else ""
    intro_html = f'<div style="font-size:11pt;color:{GRAY_TEXT};margin-bottom:16px;max-width:9.5in;">{_esc(block["intro"])}</div>'
    ramp = [ctx.accent_main, ctx.accent_chart, ctx.accent_light, ctx.accent_soft, GRAY_TEXT]
    # Titik variasi tampilan (independen dari category_style — lihat status_style di
    # generate_pdf_report): donut butuh panel legend berdampingan (warna donut tidak
    # ber-label sendiri, beda dari bar chart yang sumbu kategorinya sudah jadi label),
    # jadi strukturnya digeser ke pola _main_panel_pair yang sama dgn category_distribution.
    if ctx.status_style in ("donut", "stacked"):
        status_total = sum(block["values"]) or 1
        status_colors = [ramp[i % len(ramp)] for i in range(len(block["values"]))]
        legend_rows_html = _legend_rows([
            (status_colors[i], name, f"{round(val / status_total * 100, 1)}%")
            for i, (name, val) in enumerate(zip(block["categories"], block["values"]))
        ], theme=ctx.theme)
        legend_title = "Status Proportion" if is_english(ctx.report) else "Proporsi Status"
        legend_panel = _ivory_panel("%", legend_title, legend_rows_html, theme=ctx.theme)
        if ctx.status_style == "donut":
            chart_html = _donut_chart_svg(block["values"], colors=status_colors)
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
    # RED_CRIT TIDAK ikut tema (severity fixed) — cuma cabang "tidak kritis" yang ikut tema.
    findings_html_parts = [
        _badge_row(it["num"], it["title"], it["detail"], RED_CRIT if it["is_critical"] else ctx.accent_main)
        for it in block["items"]
    ]
    inner = _kicker(block["kicker"], ctx.accent_main) + _title(block["title"]) + "".join(findings_html_parts)
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
        f'<div style="font-size:11pt;color:#E8ECE6;margin-bottom:18px;">{_esc(block["text"])}</div>'
        f'{pills_html}'
    )
    # panel_side cuma dipakai kalau priority_html benar-benar ada isinya — kalau
    # kosong (tidak ada rekomendasi), swap ke "left" akan menyisakan kolom kiri
    # kosong & teks Kesimpulan malah ke kanan, lebih buruk dari layout defaultnya.
    concl_side = ctx.panel_side if priority_html else "right"
    inner = (
        _kicker(block["kicker"], ctx.accent_light) +
        f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:20pt;color:#fff;margin-bottom:16px;">{_esc(block["title"])}</div>' +
        _main_panel_pair(concl_left, priority_html, 58, concl_side)
    )
    return (inner, True, None, False)


def _build_closing_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    if ctx.cover_style == "split":
        # Bookend dgn cover: panel kiri warna emas mengulang angka hero yang sama.
        closing_block = {**block, "hero_stat": ctx.cover_hero_stat}
        return (_split_closing_td(closing_block, ctx.flourish_corner, theme=ctx.theme), True, None, True, True)
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
    color_map = {
        "blue": "#2563EB",
        "red": RED_CRIT,
        "orange": "#EA580C",
        "green": GREEN_MAIN,
        "amber": GOLD_MAIN,
        "gray": GRAY_TEXT,
    }
    for item in items:
        col = color_map.get(item.get("color", "blue"), ctx.accent_main)
        delta_html = f'<div style="font-size:8.5pt;font-weight:600;color:{GRAY_TEXT};margin-top:4px;">{_esc(item["delta"])}</div>' if item.get("delta") else ""
        cell_htmls.append(
            f'<table style="width:100%;margin-bottom:12pt;background:{IVORY};border:1.5px solid {col}35;border-radius:12px;"><tr><td style="vertical-align:top;padding:12pt;">'
            f'<div style="font-size:9pt;font-weight:800;text-transform:uppercase;letter-spacing:0.08em;color:{col};">{_esc(item["label"])}</div>'
            f'<div style="font-family:{TITLE_FONT};font-size:24pt;font-weight:900;color:{col};margin-top:6px;">{_esc(item["value"])}</div>'
            f'{delta_html}'
            f'</td></tr></table>'
        )
    inner = _kicker(block.get("kicker", ""), ctx.accent_main) + _title(block.get("title", "")) + _card_grid(cell_htmls, 3)
    return (inner, False, None, False)


def _build_management_risk_heatmap_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    bars = block.get("severity_bars", [])
    color_map = {
        "red": RED_CRIT,
        "orange": "#EA580C",
        "amber": GOLD_MAIN,
        "blue": "#2563EB",
        "gray": GRAY_TEXT,
    }
    rows_html = ""
    for bar in bars:
        col = color_map.get(bar.get("color", "gray"), ctx.accent_main)
        pct = max(bar.get("pct", 0), 2)
        rows_html += (
            f'<tr style="font-size:10pt;">'
            f'<td style="width:110px;font-weight:800;color:{col};padding:8px 0;">{_esc(bar["label"])}</td>'
            f'<td style="padding:8px 12px;">'
            f'<div style="height:14px;background:#F0F2ED;border-radius:7px;overflow:hidden;">'
            f'<div style="height:100%;width:{pct}%;background:{col};border-radius:7px;"></div>'
            f'</div>'
            f'</td>'
            f'<td style="width:90px;text-align:right;font-weight:700;color:{col};padding:8px 0;">{bar["count"]} <span style="font-size:8.5pt;font-weight:400;color:{GRAY_TEXT};">({bar["pct"]}%)</span></td>'
            f'</tr>'
        )
    summary_html = f'<div style="font-size:10pt;color:{GRAY_TEXT};line-height:1.6;margin-top:14pt;padding:10pt 14pt;background:{IVORY};border-left:3px solid {ctx.accent_main};border-radius:4px;">{_esc(block.get("summary_text", ""))}</div>' if block.get("summary_text") else ""
    inner = (
        _kicker(block.get("kicker", ""), ctx.accent_main) +
        _title(block.get("title", "")) +
        f'<table style="width:100%;border-collapse:collapse;margin-top:12pt;">{rows_html}</table>' +
        summary_html
    )
    return (inner, False, None, False)


def _build_management_trend_chart_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    narrative_html = f'<div style="font-size:10.5pt;color:{TEXT_DARK};line-height:1.6;margin-bottom:14pt;">{_esc(block.get("narrative", ""))}</div>' if block.get("narrative") else ""
    trend_cards = ""
    for item in block.get("trend_items", []):
        pills = "".join(f'<span style="display:inline-block;padding:3px 8px;margin:2px 4px 2px 0;background:{ctx.accent_soft};color:{ctx.accent_main};border-radius:12px;font-size:8.5pt;font-weight:700;">{_esc(v)}</span>' for v in item.get("top_values", []))
        trend_cards += (
            f'<div style="margin-bottom:10pt;padding:10pt 12pt;background:{IVORY};border:1px solid {PANEL_BORDER};border-radius:10px;">'
            f'<div style="font-size:9.5pt;font-weight:800;text-transform:uppercase;color:{ctx.accent_main};margin-bottom:6px;">{_esc(item.get("category", ""))}</div>'
            f'<div>{pills}</div>'
            f'</div>'
        )
    inner = (
        _kicker(block.get("kicker", ""), ctx.accent_main) +
        _title(block.get("title", "")) +
        narrative_html +
        f'<div>{trend_cards}</div>'
    )
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


_PDF_BLOCK_BUILDERS = {
    "cover": _build_cover_block,
    "intro": _build_intro_block,
    "executive_summary": _build_executive_summary_block,
    "dynamic_section": _build_dynamic_section_block,
    "category_distribution": _build_category_distribution_block,
    "severity_distribution": _build_severity_distribution_block,
    "status_distribution": _build_status_distribution_block,
    "critical_table": _build_critical_table_block,
    "asset_cards": _build_asset_cards_block,
    "key_findings": _build_key_findings_block,
    "recommendations": _build_recommendations_block,
    "conclusion": _build_conclusion_block,
    "closing": _build_closing_block,
    "management_kpi_grid": _build_management_kpi_grid_block,
    "management_risk_heatmap": _build_management_risk_heatmap_block,
    "management_trend_chart": _build_management_trend_chart_block,
    "management_action_items": _build_management_action_items_block,
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
            palette = {"main": theme_key, "bg": "#111827", "chart": theme_key, "light": "#C9A227", "soft": "#F3F4F6"}
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
            builder = _PDF_BLOCK_BUILDERS.get(block["kind"])
            if builder:
                pages.append(builder(block, ctx))

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
            page_html_parts.append(_page(
                inner, dark=dark, flourish=flourish,
                page_num=page_num, total_pages=total_pages,
                logo_b64=(logo_b64 if not is_cover_or_closing else None),
                last=is_last, raw=raw, theme=ctx.theme,
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
