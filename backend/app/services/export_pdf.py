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
from app.services.report_render_logic import (
    render_is_en, set_render_language,
    build_report_blocks, build_management_report_blocks, is_english, find_logo_path, get_visual_style,
    resolve_theme_color, best_grid_cols, _hard_truncate, _dedupe_truncated_labels, _layout_dashboard_column,
    _DASH_FACT_STRIP_H_IN, _DASH_FACT_PAIR_H_IN, _DASH_MAIN_VISUAL_RANGE_IN, _DASH_MARGIN_X_IN, _DASH_COL_GAP_IN,
    _DASH_TITLE_MAX_H_IN, _DASH_CONTENT_BOTTOM_IN, _layout_insight_layers, _layout_dashboard_column_content,
    tinggi_kartu_in, wrap_line_count, muat_catatan, kolom_yang_digambar, _kpi_card_widths,
    metrik_judul_dashboard,
    gelapkan_untuk_latar_terang, warna_teks_label, label_menempel_pada_bentuk,
    fakta_strip_kolom, _DASH_COLS_FACT_H_IN, kumpulkan_catatan_halaman,
    alokasi_kolom_bertumpuk, _kepala_seksi_h_in,
    label_box_does_not_overlap, radar_label_layout,
    tinggi_kotak_catatan_halaman, tinggi_maks_kotak_catatan, _DASH_COLS_KEPALA_H_IN,
    _DASH_TILE_GAP_IN, tinggi_kolom_tersedia_in,
    _NESTED_CARD_GAP_IN, _NESTED_CARD_HEADER_H_IN, _NESTED_CARD_HEADER_MIN_H_IN, _NESTED_CARD_SUBITEM_LINE1_H_IN, _NESTED_CARD_SUBITEM_BAR_H_IN,
    _NESTED_CARD_SUBITEM_GAP_IN, _NESTED_CARD_ROW_GAP_IN, _layout_nested_card_grid,
)

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
# A2: garis tepi panel disamakan dgn acuan (#D6DBE3) - inilah yang membentuk sekat
# antar panel yang bersentuhan, jadi nilainya menentukan tampilan, bukan dekoratif.
PANEL_BORDER = "#D6DBE3"
# A4: palet kotak KPI dari acuan - latar & angka berubah menurut nilainya.
KPI_BG_NETRAL = "#F4F6F9"
KPI_BG_BAIK = "#DFF0E6"
KPI_FG_NETRAL = "#1F3864"
KPI_FG_BAIK = "#1E7A4D"
KPI_LABEL = "#5A6472"
# A6: warna nama topik di judul halaman (acuan #002060).
TITLE_TOPIK = "#002060"


def _kpi_nilai_baik(card: dict) -> bool:
    """Apakah KPI ini bernilai BAIK, dibaca dari nilainya sendiri - bukan dari nama kartunya.

    Acuan memberi warna hijau pada capaian yang memenuhi target. Yang bisa dinilai tanpa
    mengarang: persentase >= 75%, atau label yang menyebut pencapaian/target."""
    try:
        teks = str(card.get("value") or "")
    except Exception:
        return False
    if "%" in teks:
        angka = "".join(c for c in teks if c.isdigit() or c in ",.").replace(".", "").replace(",", ".")
        try:
            return float(angka) >= 75.0
        except ValueError:
            return False
    return False
# A5: warna label "Catatan:" di acuan.
CATATAN_LABEL = "#00B050"
# PERMINTAAN USER (C2): latar halaman ISI (terang) TIDAK boleh diberi rona warna tema apa
# pun — dulu pakai t["soft"] (utk tema kustom = tint dari warna pilihan user sendiri, mis.
# #ecf4f0 dari hijau #60a481; utk tema bernama = GOLD_LIGHT) — kedua kasus menambah warna
# KEDUA/KETIGA ke dokumen yang semestinya cuma py 1 warna merek. Abu sangat netral (R=G=B)
# sekarang dipakai, BUKAN IVORY (dipakai kartu/panel DI ATAS halaman ini — kalau bg halaman
# disamakan ke IVORY, kartu jadi tidak kontras sama sekali dgn latarnya).
PAGE_BG_NEUTRAL = "#FAFAFA"

# Warna prioritas/urgensi rekomendasi — dipakai badge & pill di _build_recommendations_block
# (SOC) dan _build_management_action_items_block (Management), SATU sumber SUPAYA konsisten
# antar keduanya. Ini warna BERMAKNA (status prioritas), BUKAN aksen tema dekoratif — sengaja
# TIDAK ikut palet tema (accent_main dkk), tetap sama persis apa pun tema laporan yang dipilih.
URGENCY_COLOR = {
    "critical": (RED_CRIT, RED_CRIT_BG),
    "high": ("#EA580C", "#FFF7ED"),
    "medium": (GOLD_MAIN, "#FBF3DC"),
    "low": ("#2563EB", "#EFF6FF"),
}

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
# PERMINTAAN USER ("bosan template segitu-gitu aja"): tema warna ke-5 di luar 4 yang sudah
# ada (hijau/navy/dark/emas semua condong hangat/gelap netral) — teal (biru-kehijauan) dipilih
# krn masih terasa korporat/profesional tapi genuinely beda nuansa drpd 4 lainnya. "light"/
# "soft" TETAP pakai GOLD_MAIN/GOLD_LIGHT yang sama (pola sama dgn navy/dark) — sudah terbukti
# kontras baik di atas latar gelap apa pun, tidak perlu warna aksen baru lagi.
TEAL_MAIN = "#0F6B64"
TEAL_BG = "#0A3D39"
TEAL_CHART = "#35A398"

THEME_PALETTES: dict[str, dict[str, str]] = {
    "green": {"main": GREEN_MAIN, "bg": GREEN_BG, "chart": GREEN_CHART, "light": GOLD_MAIN, "soft": GOLD_LIGHT},
    "navy": {"main": NAVY_MAIN, "bg": NAVY_BG, "chart": NAVY_CHART, "light": GOLD_MAIN, "soft": GOLD_LIGHT},
    "dark": {"main": DARK_MAIN, "bg": DARK_BG, "chart": DARK_CHART, "light": GOLD_MAIN, "soft": GOLD_LIGHT},
    "gold": {"main": GOLD_BRONZE_MAIN, "bg": GOLD_BRONZE_BG, "chart": GOLD_MAIN, "light": GOLD_CREAM_LIGHT, "soft": GOLD_CREAM_SOFT},
    "teal": {"main": TEAL_MAIN, "bg": TEAL_BG, "chart": TEAL_CHART, "light": GOLD_MAIN, "soft": GOLD_LIGHT},
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
    # BUG DIPERBAIKI (dilaporkan user — logo cover/penutup dikodekan LEBIH BESAR drpd halaman
    # biasa (126px vs 84px) tapi kalau dilihat malah kalah menonjol drpd judul besar di
    # sampingnya): file logo asli (LOGO_PETRO_DANANTARA.png) ternyata py padding transparan
    # raksasa di atas/bawah (diukur: ~54% dari tinggi gambar KOSONG total, cuma ~46% tengahnya
    # yang benar2 berisi logo). `height:Npx` pada <img> menghitung Npx itu TERMASUK padding
    # kosong itu, jadi logo yang BENAR-BENAR kelihatan cuma ~46% dari ukuran yang diminta di
    # SEMUA pemakaian (bukan cuma cover). Dipotong SEKALI di sini ke bounding box alpha
    # (konten asli, bukan kotak transparannya) supaya height:Npx di semua pemanggil
    # (_dark_logo_html/_page/dll) akhirnya sesuai ukuran visual sebenarnya.
    try:
        from PIL import Image
        import io
        with Image.open(p) as im:
            im = im.convert("RGBA")
            alpha_bbox = im.split()[-1].getbbox()
            if alpha_bbox:
                im = im.crop(alpha_bbox)
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            return base64_encode(buf.getvalue())
    except Exception:
        pass
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


def _fmt_num(val) -> str:
    """Format angka utk ditampilkan di chart/label — BUG DIPERBAIKI (ditemukan lewat
    verifikasi render laporan traffic asli): format spec "g" polos (dipakai di seluruh file
    ini sblm perbaikan ini) diam-diam pindah ke notasi ilmiah begitu angkanya jutaan (mis.
    volume request traffic "1098060" tampil sbg "1.09806e+06") — umum kejadian utk data
    traffic/log jaringan, bukan kasus langka. Dipakai pemisah ribuan biasa; dibulatkan kalau
    memang bilangan bulat (kasus paling umum: count/jumlah event)."""
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


def _badge_row(number, title, detail, color=GREEN_MAIN, on_dark=False, scale=1.0) -> str:
    # xhtml2pdf (fallback engine kalau WeasyPrint tak tersedia) TIDAK support flexbox —
    # dipakai <table> supaya badge+teks sejajar konsisten di kedua engine.
    #
    # RANCANG ULANG (target WeasyPrint, lihat catatan di _ivory_panel): height eksplisit
    # dihapus — baris sepadat kontennya (detail panjang wrap bebas tanpa risiko kepotong/
    # numpuk), jarak antar baris dinaikkan sedikit (14px) supaya senapas dengan spacing
    # generous di panel-panel lain.
    # `scale` (PERMINTAAN USER, berkali-kali): dipakai pemanggil utk memperbesar baris ini
    # kalau jumlahnya sedikit (1.0 = ukuran normal).
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


def _kicker(text, color=GRAY_TEXT) -> str:
    # WARNA NETRAL (bukan aksen tema): referensi desain user memakai warna cuma utk makna
    # (status tercapai/target/level), bukan hiasan label kicker — accent_main/accent_light
    # sudah DIHAPUS dari semua pemanggil kicker (lihat grep call sites), default di sini
    # jadi jaring pengaman kalau ada pemanggil baru lupa mengisi warna eksplisit.
    # PERMINTAAN USER: rampingkan header halaman — margin-bottom diturunkan (6px->4px) supaya
    # jarak kicker->judul lebih pas, bukan longgar tanpa alasan.
    return (
        f'<div style="font-size:9pt;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;'
        f'color:{color};margin-bottom:4px;font-family:{BODY_FONT};">{_esc(text)}</div>'
    )


def _title(text, color=TEXT_DARK, size="20pt") -> str:
    # PERMINTAAN USER: margin-bottom diturunkan (14px->8px) — konten panel mulai lebih cepat
    # setelah judul, sama semangatnya dgn pemangkasan header di export_ppt.py.
    return f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:{size};color:{color};margin-bottom:8px;">{_esc(text)}</div>'


def _panel_header_band(text, margin_bottom_pt: float = 10) -> str:
    """Header panel gaya "pita" (rujukan desain user, mis. panel "Uptime Server Aplikasi &
    Layanan TI"): pita abu-abu tipis datar berisi judul TEBAL warna netral — menggantikan pola
    lama label kecil huruf kapital berwarna aksen tema di dalam kartu insight/tile. Dipakai
    HANYA sbg header PANEL/KARTU (bukan header halaman — itu tetap _kicker + _title)."""
    return (
        f'<div style="background:{PANEL_BORDER};border-radius:2px;padding:5pt 9pt;margin-bottom:{margin_bottom_pt}pt;">'
        f'<span style="font-weight:700;font-size:9pt;color:{TEXT_DARK};">{_esc(text)}</span></div>'
    )


def _bar_chart_html(categories, values, colors=None, compact=False) -> str:
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
    # `compact=True` (dipakai KHUSUS tile dashboard Management yang padat, lihat
    # _mgmt_tile_chart_html) — BUG DIPERBAIKI (ditemukan lewat isolasi render+bisection di
    # laporan sungguhan, report id 165): tile "bar" dgn 6 item (batas maksimum, lihat
    # labels[:6] di build_management_report_blocks) makan ~2.3in tinggi di ukuran baseline —
    # ikut menyumbang total tinggi grid dashboard (2 baris) melebihi tinggi halaman tetap
    # (7.5in), lalu bagian yang kelebihan itu diam-diam terpotong oleh overflow:hidden di
    # wrapper halaman. Baris dipadatkan (padding & tinggi bar dikecilkan) KHUSUS di konteks
    # ini — pemanggil lain (halaman penuh gaya SOC dst, yang memang punya ruang lapang)
    # TIDAK terpengaruh (default compact=False, tampilan lama persis).
    # DISAMAKAN DGN SLIDE ACUAN (diukur dari berkas acuan, bukan selera):
    #   jarak baris 0.35in = teks 0.21 + bar 0.10 + jeda 0.04  (188 sebelumnya 0.444in)
    #   tinggi bar  0.10in = 9.6px                              (188 sebelumnya 18px)
    #   font baris  7.0pt                                        (188 sebelumnya 9.5pt)
    # Bar 0.20in tidak menyampaikan apa pun lebih banyak drpd 0.10in; yang hilang cuma ruang.
    pad = "1.5pt 8pt 1.5pt 0" if compact else "2.5pt 8pt 2.5pt 0"
    bar_h = 6 if compact else 7
    font_pt = 6.5 if compact else 7.0
    if compact:
        # Batasi ke 5 item (sejalan dgn bars[:5] risk_heatmap di tile lain) — item ke-6 SAJA
        # (di atas padding+tinggi bar yang sudah dipadatkan) masih cukup utk mendorong caption
        # tile ini melewati batas 7.5in di kasus terpadat (6 item + caption 100 karakter).
        categories, values = categories[:5], values[:5]
    max_val = max(values) if values else 1
    # BUG DIPERBAIKI (dilaporkan user): lebar batang dulu SELALU linear thd nilai (val/
    # max_val) — kalau rentang nilainya jomplang jauh (mis. 9 vs 0.2, rasio >20x), nilai
    # kecil jadi batang nyaris tak kelihatan (nyaris 0 lebar) walau angkanya tetap ditulis
    # di kanan, kesan visualnya seolah "kosong". Skala LOG dipakai KHUSUS saat rasio
    # max/min(bukan-nol) > 20 — memampatkan rentang biar nilai kecil tetap kelihatan
    # proporsinya scr visual (bar tetap lebih pendek dari yang besar, urutannya tetap
    # benar, cuma tidak linear murni lagi) drpd nyaris menghilang total.
    nonzero_vals = [v for v in values if v and v > 0]
    min_nonzero = min(nonzero_vals) if nonzero_vals else 0
    use_log = bool(min_nonzero) and max_val > 0 and (max_val / min_nonzero) > 20
    log_max = math.log(max_val + 1) if use_log else 0
    rows = []
    for i, (cat, val) in enumerate(zip(categories, values)):
        if use_log and val and val > 0 and log_max:
            pct = round(math.log(val + 1) / log_max * 100, 1)
        else:
            pct = round(val / max_val * 100, 1) if max_val else 0
        pct = max(pct, 1.5) if val else 0
        color = colors[i] if colors else GREEN_MAIN
        fill_html = (
            f'<table style="width:{pct}%;" cellpadding="0" cellspacing="0"><tr>'
            f'<td style="background:{color};height:{bar_h}px;border-radius:4px;font-size:1px;line-height:{bar_h}px;">&nbsp;</td>'
            f'</tr></table>'
            if pct else ""
        )
        # LABEL DI ATAS BAR (kembaran _ranked_bar_ternorm_html): nama entitas memakai
        # LEBAR KOLOM PENUH, jadi nama utuh muat tanpa dipendekkan. Kolom label samping
        # 150px itulah yang dulu memaksa pemendekan.
        # A7: LABEL MENEMPEL PADA BENTUKNYA (tepat di atas batangnya) -> teksnya ikut
        # berwarna, jadi mata menyambungkan nama ke batang tanpa penanda tambahan. Warna
        # diambil lewat warna_teks_label: kalau warna batang terlalu terang, dipakai varian
        # GELAPNYA - bukan warna persis batang - supaya tetap terbaca di atas putih.
        # ANGKA tidak ikut berwarna: kolom angka harus terbaca sbg satu kolom.
        _warna_label = warna_teks_label(color) if label_menempel_pada_bentuk("bar") else TEXT_DARK
        rows.append(
            f'<tr><td style="padding:1pt 0 0 0;">'
            f'<table style="width:100%;" cellpadding="0" cellspacing="0"><tr>'
            f'<td style="font-size:{font_pt}pt;color:{_warna_label};line-height:1.15;">{_esc(cat)}</td>'
            f'<td style="width:70px;text-align:right;font-weight:700;font-size:{font_pt}pt;'
            f'color:{TEXT_DARK};line-height:1.15;">{_fmt_num(val)}</td></tr></table>'
            f'<div style="background:#EEEEEE;border-radius:3px;margin:1pt 0 2pt 0;">{fill_html}</div>'
            f'</td></tr>'
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
            f'<div style="font-size:7.5pt;font-weight:700;color:{TEXT_DARK};margin-bottom:3pt;">{_fmt_num(val)}</div>'
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


def _stacked_proportion_bar_html(values, colors=None, height_px=46, labels=None, w_in=4.0) -> str:
    """Alternatif visual KETIGA (selain _bar_chart_html/_donut_chart_svg) — satu batang
    penuh dibagi proporsional per kategori (gaya "100% stacked bar"). Segmen dibangun
    dari <table style="width:{pct}%"> BERJAJAR SATU BARIS (trik lebar-persen yang sama
    dengan _bar_chart_html — BUKAN flexbox, yang belum pernah dites di file ini).

    PERMINTAAN USER: label legend TERPISAH (_mini_legend_html) dihapus utk chart ini — nama
    kategori + nilai sekarang MENEMPEL langsung di atas segmennya masing2 (posisi horizontal
    ikut PUSAT segmen via position:absolute;left:{pct}%, WeasyPrint mendukung ini). Segmen yang
    genuinely sempit (<8% lebar total) TIDAK diberi label (nama/nilai bakal saling tumpuk kalau
    dipaksa) — sengaja diam2 dilewati drpd tulisan bertumpuk tidak terbaca, sama semangatnya dgn
    `_merge_tail_into_other` yg sudah menggabung sisa kecil jadi "Lainnya" sebelum sampai sini."""
    total = sum(values) or 1
    cells = []
    label_divs = []
    cum_pct = 0.0
    dd_labels = _dedupe_truncated_labels(labels, 16) if labels else None
    for i, val in enumerate(values):
        pct = (val / total * 100) if total else 0
        color = colors[i] if colors else CATEGORY_COLOR_RAMP[i % len(CATEGORY_COLOR_RAMP)]
        if pct > 0:
            cells.append(
                f'<td style="width:{pct:.3f}%;background:{color};height:{height_px}px;'
                f'font-size:1px;line-height:1px;">&nbsp;</td>'
            )
            # AMBANG 8% DIGANTI PENGUKURAN (bug nyata, uji tumpang-tindih laporan
            # 152/153/157/164): "8% lebar" tidak melihat geometri sama sekali - 8% dari kolom
            # 4in cuma 0.32in, sementara "Mendekati Target" butuh ~1in. Labelnya tetap
            # digambar & menimpa tetangganya (44% tertutup). Sekarang label dipasang hanya
            # kalau teksnya MUAT di lebar segmennya sendiri, diukur dgn faktor lebar yang
            # sama dipakai pengukur lain di berkas ini. Yang tidak muat dilewati - itu sudah
            # jadi perilaku yang disengaja di fungsi ini, ambangnya saja yang salah.
            _seg_in = (pct / 100.0) * float(w_in or 4.0)
            _teks_in = len(str(dd_labels[i] if dd_labels else "")) * (7.5 / 72.0) * 0.62
            if labels and _teks_in <= _seg_in:
                label_divs.append(
                    f'<div style="position:absolute;left:{cum_pct + pct / 2:.3f}%;top:0;'
                    f'transform:translateX(-50%);text-align:center;white-space:nowrap;">'
                    f'<div style="font-size:7.5pt;font-weight:700;color:{TEXT_DARK};">{_esc(dd_labels[i])}</div>'
                    f'<div style="font-size:7pt;color:{GRAY_TEXT};">{_fmt_num(val)}</div>'
                    f'</div>'
                )
        cum_pct += pct
    bar_html = (
        f'<div style="border-radius:10px;overflow:hidden;">'
        f'<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0">'
        f'<tr>{"".join(cells)}</tr></table></div>'
    )
    labels_html = f'<div style="position:relative;height:20pt;margin-bottom:3pt;">{"".join(label_divs)}</div>' if label_divs else ""
    return f'<div style="padding:14pt 0;">{labels_html}{bar_html}</div>'


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
    # BUG DIPERBAIKI (dilaporkan user): font label tengah dulu TETAP 28px apa pun ukuran
    # donut & panjang angka totalnya — donut kecil (mode compact dashboard, size ~111px)
    # jadi angkanya kelihatan ketabrak/nembus cincinnya sendiri, angka total berdigit
    # banyak (mis. "28410") juga bisa lebih lebar drpd diameter dalam cincin. Sekarang
    # diturunkan dari `size` (rasio 28/210 dipertahankan sbg baseline) DAN dari panjang
    # teks totalnya (lebar taksiran per digit bold ~0.62x font-size, dikecilkan lagi kalau
    # ternyata masih lebih lebar drpd diameter dalam cincin = size - stroke_w*2).
    total_str = _fmt_num(total)
    base_font = size * (28 / 210)
    inner_d = max(size - stroke_w * 2, 10)
    max_font_by_width = inner_d / (len(total_str) * 0.62)
    label_font = max(9.0, min(base_font, max_font_by_width))
    sub_font = max(6.5, label_font * (10.5 / 28))
    label_y = cy + label_font * (-4 / 28)
    sub_y = cy + label_font * (18 / 28)
    labels = (
        f'<text x="{cx}" y="{label_y:.1f}" text-anchor="middle" font-size="{label_font:.1f}" font-weight="700" '
        f'fill="{label_color}" font-family="{BODY_FONT}">{total_str}</text>'
        f'<text x="{cx}" y="{sub_y:.1f}" text-anchor="middle" font-size="{sub_font:.1f}" fill="{sub_color}" '
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
        f'fill="{TEXT_DARK}" font-family="{BODY_FONT}">{_fmt_num(round(value))}%</text>'
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
def _darken(hex_color: str) -> str:
    """Latar halaman gelap penuh (cover/penutup) utk tema KUSTOM — riwayat 2 revisi:
    (1) BUG NYATA DITEMUKAN (dilaporkan user, "kok ga diterapkan"): dulu SELALU "#111827"
    (navy generik) apa pun warna yang dipilih — cover (kesan pertama laporan) jadi terlihat
    tidak terpengaruh pilihan warna user. Diperbaiki dgn menggelapkan warna kustom (factor
    tetap 0.55) mengikuti pola 4 tema bernama.
    (2) PERMINTAAN USER LANJUTAN: factor 0.55 TETAP ternyata mengubah HUE-nya sendiri terlalu
    jauh drpd yang dipilih (mis. user pilih #60a481, cover jadi #355a47 — dianggap "hijau
    lain", bukan warna yang sama lagi). `hex_color` yang masuk ke sini SUDAH melewati
    _light_safe(theme_key, max_luminance=0.55) di pemanggil (lihat komentar di sana) — SUDAH
    dijamin cukup gelap utk teks putih besar/tebal di cover, jadi TIDAK perlu digelapkan lagi
    di kasus normal (dipakai APA ADANYA). Darken cuma dipakai sbg jaring pengaman kalau
    somehow luminance-nya masih di atas ambang itu, DIBATASI paling banyak ke factor 0.85
    (bukan 0.55 lagi) — supaya kalau pun perlu digelapkan, huenya masih cukup mirip utk
    "terbaca sebagai warna yang sama"."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    if luminance <= 0.55 or luminance == 0:
        return hex_color
    factor = max(0.85, 0.55 / luminance)
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
    # ATURANNYA SATU, di report_render_logic.gelapkan_untuk_latar_terang - fungsi ini tinggal
    # pembungkus tipe (hex). Dulu rumusnya disalin di sini DAN di export_ppt._light_safe.
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return hex_color
    r, g, b = gelapkan_untuk_latar_terang(
        int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), max_luminance)
    return f"#{r:02x}{g:02x}{b:02x}"


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
    bars, points, labels, bar_label_ys = [], [], [], []
    for i, (cat, val) in enumerate(zip(categories, values)):
        bar_h = (val / max_val) * (plot_h - 8) if max_val else 0
        x = pad_l + i * col_w
        y = pad_t + (plot_h - bar_h)
        bars.append(f'<rect x="{x + col_w*0.18:.1f}" y="{y:.1f}" width="{col_w*0.64:.1f}" height="{bar_h:.1f}" fill="{bar_color}" rx="2" />')
        # DUA BUG NYATA DIPERBAIKI di satu tempat (terukur lewat uji tumpang-tindih, laporan
        # 164/157): (1) nilainya dicetak MENTAH - "1696.6100000000001" muncul apa adanya di
        # laporan, sementara seluruh angka lain sudah lewat _fmt_num; (2) labelnya selalu
        # digambar di tengah tiap batang tanpa memeriksa apakah muat - dgn 12 periode di kolom
        # 4in, teks tetangga saling menimpa (84% tertutup). Sekarang: diformat, dan hanya
        # digambar kalau lebarnya MUAT di kolomnya sendiri. Lebar teks diperkirakan dgn faktor
        # yang sama yang dipakai pengukur lebar lain di berkas ini.
        _teks_val = _fmt_num(val) if val else ""
        _muat_val = _teks_val and (len(_teks_val) * 7.5 * 0.62) <= col_w * 0.98
        if val and _muat_val:
            _bly = max(y - 4, 10)
            bar_label_ys.append(_bly)
            bars.append(f'<text x="{x + col_w/2:.1f}" y="{_bly:.1f}" text-anchor="middle" font-size="7.5" fill="{TEXT_DARK}" font-family="{BODY_FONT}">{_esc(_teks_val)}</text>')
        else:
            bar_label_ys.append(None)
        if max_cum:
            cy = pad_t + plot_h - ((cumulative[i] / max_cum) * (plot_h - 4))
            points.append((x + col_w / 2, cy))
        # KEPUTUSAN DIBALIK (uji label: gerbang "muat" di sini menghapus 12 dari 12 tanggal
        # di laporan 180 & 183 - kehilangan DIAM, yang lebih buruk daripada tumpang tindih
        # yang setidaknya terlihat). Label kategori SELALU digambar; yang dibatasi adalah
        # JUMLAH PERIODE, di hulu saat kandidat dibentuk (lihat _semua_kandidat), supaya
        # yang sampai ke sini memang sudah pasti muat.
        labels.append(f'<text x="{x + col_w/2:.1f}" y="{size_h - 6}" text-anchor="middle" font-size="7.5" fill="{GRAY_TEXT}" font-family="{BODY_FONT}">{_esc(cat)}</text>')
    line_html = dots = ""
    if points:
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        line_html = f'<polyline points="{poly}" fill="none" stroke="{line_color}" stroke-width="2.5" />'
        dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="{line_color}" />' for x, y in points)
        # PERMINTAAN USER ("angka harus melekat di chart"): batangnya sudah berlabel angka,
        # garis kumulatifnya belum - pembaca melihat garis naik tanpa tahu naik ke BERAPA.
        # Label ditaruh DI BAWAH titik (cy + 8) krn ruang di ATAS titik sudah dipakai label
        # angka batang; kalau titiknya terlalu dekat dasar plot, dibalik ke atas titik supaya
        # tidak menabrak label kategori di kaki chart. Dilewati kalau kategorinya banyak
        # (> 8) - di lebar chart tile, label sebanyak itu saling tumpuk & malah tidak terbaca.
        if len(points) <= 8:
            _cum_labels = []
            # Label kumulatif dijauhkan dari label nilai BATANG di kolom yang sama - keduanya
            # dulu bisa jatuh di pita y yang sama & saling menimpa (terukur tes span: 25
            # tabrakan, mis. "5" x "26" beririsan 49%). Posisi label batang diketahui persis
            # (bar_label_y di bawah), jadi tabrakannya dihindari, bukan diperkecil peluangnya.
            for (cx, cy), cval, _bly in zip(points, cumulative, bar_label_ys):
                ly = cy + 8 if cy + 8 < pad_t + plot_h - 2 else cy - 5
                if _bly is not None and abs(ly - _bly) < 11:
                    ly = _bly + 13 if ly >= _bly else _bly - 13
                    ly = min(max(ly, 8), pad_t + plot_h - 2)
                _cum_labels.append(
                    f'<text x="{cx:.1f}" y="{ly:.1f}" text-anchor="middle" font-size="6.5" '
                    f'fill="{line_color}" font-family="{BODY_FONT}">{_esc(_fmt_num(cval))}</text>'
                )
            dots += "".join(_cum_labels)
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
    label_layout = radar_label_layout(axes, size, label_margin)
    if label_layout is None:
        return ""
    labels = [
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-size="{font_size:.1f}" '
        f'fill="{TEXT_DARK}" font-family="{BODY_FONT}">{_esc(text)}</text>'
        for text, x, y, anchor, font_size in label_layout
    ]
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
        # PERMINTAAN USER: tampilkan nilai di tiap bar (referensi menulis angka langsung di
        # atas/di ujung batangnya) — sebelumnya cuma lebar proporsional tanpa angka sama sekali.
        rows.append(
            f'<tr><td style="font-size:8pt;color:{TEXT_DARK};padding:8pt 8pt 0 0;">{_esc(cat)}</td></tr>'
            f'<tr><td style="padding:0 0 6pt 0;">'
            f'<table style="width:100%;" cellpadding="0" cellspacing="0"><tr>'
            f'<td style="background:{ca};height:10px;width:{pa}%;border-radius:3px;"></td>'
            f'<td style="font-size:7pt;color:{GRAY_TEXT};padding-left:4pt;white-space:nowrap;">{_fmt_num(a)}</td>'
            f'</tr></table>'
            f'<table style="width:100%;margin-top:2px;" cellpadding="0" cellspacing="0"><tr>'
            f'<td style="background:{cb};height:10px;width:{pb}%;border-radius:3px;"></td>'
            f'<td style="font-size:7pt;color:{GRAY_TEXT};padding-left:4pt;white-space:nowrap;">{_fmt_num(b)}</td>'
            f'</tr></table>'
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
    # BUG DIPERBAIKI (dilaporkan user, laporan sungguhan report id 165): font label kategori
    # dulu SELALU 7.5pt tetap apa pun size_w — begitu tile dashboard dipadatkan (size_w
    # dikecilkan, lihat _mgmt_tile_chart_html compact=True), label kategori 2-3 kata (mis.
    # "Penunjukan Langsung") jadi lebih lebar drpd slot kolomnya sendiri & tumpang tindih
    # dgn kolom sebelah. Font label sekarang ikut menyusut proporsional dgn size_w (skala thd
    # ukuran baseline 320px yang terbukti pas), dgn batas bawah 6pt supaya tetap terbaca.
    font_scale = min(1.0, size_w / 320)
    val_font = max(5.5, round(7 * font_scale, 1))
    cat_font = max(6.0, round(7.5 * font_scale, 1))
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
            # Sama dgn _bar_line_chart_svg: angka DIFORMAT (mentah "1696.6100000000001"
            # pernah muncul apa adanya) & hanya digambar kalau MUAT di lebar batangnya,
            # krn dua deret berdampingan membuat jaraknya separuh lebih sempit.
            _ta = _fmt_num(series_a[i])
            if len(_ta) * val_font * 0.62 <= bar_w * 1.8:
                parts.append(f'<text x="{xa + bar_w/2:.1f}" y="{max(ya - 4, 10):.1f}" text-anchor="middle" font-size="{val_font}" fill="{TEXT_DARK}" font-family="{BODY_FONT}">{_esc(_ta)}</text>')
        if series_b[i]:
            # Sama dgn _bar_line_chart_svg: angka DIFORMAT (mentah "1696.6100000000001"
            # pernah muncul apa adanya) & hanya digambar kalau MUAT di lebar batangnya,
            # krn dua deret berdampingan membuat jaraknya separuh lebih sempit.
            _tb = _fmt_num(series_b[i])
            if len(_tb) * val_font * 0.62 <= bar_w * 1.8:
                parts.append(f'<text x="{xb + bar_w/2:.1f}" y="{max(yb - 4, 10):.1f}" text-anchor="middle" font-size="{val_font}" fill="{TEXT_DARK}" font-family="{BODY_FONT}">{_esc(_tb)}</text>')
        parts.append(f'<text x="{gx + group_w/2:.1f}" y="{size_h - 6}" text-anchor="middle" font-size="{cat_font}" fill="{GRAY_TEXT}" font-family="{BODY_FONT}">{_esc(cat)}</text>')
    parts.append("</svg>")
    legend = (
        f'<div style="font-size:8pt;color:{GRAY_TEXT};margin-top:4pt;">'
        f'<span style="display:inline-block;width:8px;height:8px;background:{ca};margin-right:4px;"></span>{_esc(label_a)}'
        f'<span style="display:inline-block;width:8px;height:8px;background:{cb};margin:0 4px 0 14px;"></span>{_esc(label_b)}</div>'
    )
    return f'<div style="text-align:center;">{"".join(parts)}{legend}</div>'


def _funnel_chart_html_fallback(categories, values, color=None) -> str:
    return _bar_chart_html(categories, values, colors=[color or GREEN_MAIN] * len(values))


def _treemap_html_fallback(labels, values, colors=None) -> str:
    return _bar_chart_html(labels, values, colors=colors)


def _treemap_svg(labels, values, colors=None, size_w=320, size_h=200) -> str:
    """PERMINTAAN USER (tambah jenis visualisasi baru): proporsi banyak kategori sekaligus
    lewat LUAS kotak — lebih terbaca drpd donat/bar kalau kategorinya banyak (>5-6), krn
    kotak sekecil apa pun tetap kelihatan proporsinya scr visual, beda dgn potongan donat
    tipis yang gampang tumpang tindih labelnya. Algoritma "slice-and-dice" sederhana (potong
    horizontal/vertikal bergantian sesuai proporsi nilai tersisa) — BUKAN squarified treemap
    penuh (jauh lebih rumit implementasinya), tapi cukup rapi utk <=8 kategori yang dipakai
    di laporan ini."""
    if not SVG_SUPPORTED:
        return _treemap_html_fallback(labels, values, colors)
    ramp = colors or CATEGORY_COLOR_RAMP
    total = sum(values) or 1
    dd_labels = _dedupe_truncated_labels(labels, 14)
    rects = []
    x, y, w, h = 0.0, 0.0, float(size_w), float(size_h)
    horizontal = True
    remaining_total = total
    for label, val in zip(dd_labels, values):
        frac = (val / remaining_total) if remaining_total else 0
        if horizontal:
            seg_w = w * frac
            rects.append((x, y, seg_w, h, label, val))
            x += seg_w
            w -= seg_w
        else:
            seg_h = h * frac
            rects.append((x, y, w, seg_h, label, val))
            y += seg_h
            h -= seg_h
        remaining_total -= val
        horizontal = not horizontal
    parts = [f'<svg width="{size_w}" height="{size_h}" viewBox="0 0 {size_w} {size_h}" xmlns="http://www.w3.org/2000/svg">']
    for i, (rx, ry, rw, rh, short_label, val) in enumerate(rects):
        if rw < 1 or rh < 1:
            continue
        color = ramp[i % len(ramp)]
        parts.append(f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{rw:.1f}" height="{rh:.1f}" fill="{color}" stroke="#fff" stroke-width="2" />')
        if rw > 44 and rh > 24:
            parts.append(
                f'<text x="{rx + rw/2:.1f}" y="{ry + rh/2 - 4:.1f}" text-anchor="middle" font-size="8" font-weight="700" '
                f'fill="#fff" font-family="{BODY_FONT}">{_esc(short_label)}</text>'
            )
            parts.append(
                f'<text x="{rx + rw/2:.1f}" y="{ry + rh/2 + 9:.1f}" text-anchor="middle" font-size="7.5" '
                f'fill="#fff" font-family="{BODY_FONT}">{_fmt_num(val)}</text>'
            )
    parts.append("</svg>")
    return f'<div style="text-align:center;">{"".join(parts)}</div>'


def _gauge_svg(pct, caption=None, color=None, size=200) -> str:
    """PERMINTAAN USER (tambah jenis visualisasi baru): meteran radial (arc setengah
    lingkaran) utk 1 angka pencapaian vs target (mis. % SLA/selesai) — posisi arc yang
    terisi langsung "dibaca sekilas" scr visual, beda dgn angka polos yang butuh dibaca
    dulu baru dipahami besar/kecilnya. Dipakai `stroke-dasharray`/`stroke-dashoffset` pada
    SATU path setengah lingkaran yang SAMA (bukan menghitung ulang titik akhir arc per
    persentase) — jauh lebih aman drpd itung manual sudut/large-arc-flag yang gampang salah.
    """
    pct = max(0.0, min(100.0, float(pct)))
    if not SVG_SUPPORTED:
        cap_html = f'<div style="font-size:8pt;color:{GRAY_TEXT};margin-top:4px;">{_esc(caption)}</div>' if caption else ""
        return f'<div style="text-align:center;font-size:22pt;font-weight:800;color:{color or GREEN_MAIN};">{pct:.0f}%{cap_html}</div>'
    base = color or GREEN_MAIN
    canvas_h = round(size * 0.66)
    cx, cy, r = size / 2, size * 0.56, size * 0.4
    stroke_w = size * 0.13
    arc_len = math.pi * r
    dash_offset = arc_len * (1 - pct / 100)
    path_d = f"M {cx - r:.1f} {cy:.1f} A {r:.1f} {r:.1f} 0 0 1 {cx + r:.1f} {cy:.1f}"
    cap_html = ""
    if caption:
        cap_html = (
            f'<text x="{cx:.1f}" y="{cy + size*0.14:.1f}" text-anchor="middle" font-size="{size*0.045:.0f}" '
            f'fill="{GRAY_TEXT}" font-family="{BODY_FONT}">{_esc(caption)}</text>'
        )
    svg = (
        f'<svg width="{size}" height="{canvas_h}" viewBox="0 0 {size} {canvas_h}" xmlns="http://www.w3.org/2000/svg">'
        f'<path d="{path_d}" fill="none" stroke="{PANEL_BORDER}" stroke-width="{stroke_w:.1f}" stroke-linecap="round" />'
        f'<path d="{path_d}" fill="none" stroke="{base}" stroke-width="{stroke_w:.1f}" stroke-linecap="round" '
        f'stroke-dasharray="{arc_len:.1f}" stroke-dashoffset="{dash_offset:.1f}" />'
        f'<text x="{cx:.1f}" y="{cy - size*0.02:.1f}" text-anchor="middle" font-size="{size*0.16:.0f}" font-weight="800" '
        f'fill="{TEXT_DARK}" font-family="{TITLE_FONT}">{pct:.0f}%</text>'
        f'{cap_html}</svg>'
    )
    return f'<div style="text-align:center;">{svg}</div>'


def _scatter_bubble_html_fallback(points, x_key, y_key, color=None) -> str:
    labels = [p.get("label", "") for p in points]
    values = [p.get(y_key, 0) for p in points]
    return _bar_chart_html(labels, values, colors=[color or GREEN_MAIN] * len(values))


def _scatter_bubble_svg(points, x_key="count", y_key="avg", size_key=None, color=None, size_w=340, size_h=200, x_label="", y_label="") -> str:
    _label_terpasang: list = []
    """PERMINTAAN USER (tambah jenis visualisasi baru): titik per entitas (mis. tiap vendor)
    diposisikan berdasar 2 angka ASLI BERBEDA sekaligus (lihat
    data_profiler._compute_category_numeric_pairs) — genuinely beda drpd chart lain di
    laporan ini yang semuanya cuma 1 angka per kategori. Ukuran titik (bubble) ikut
    `size_key` kalau diisi (biasanya sama dgn x_key, jadi titik yang "lebih sering muncul"
    juga tergambar lebih besar) — kalau tidak, semua titik ukurannya sama (scatter polos)."""
    if not SVG_SUPPORTED:
        return _scatter_bubble_html_fallback(points, x_key, y_key, color)
    base = color or GREEN_MAIN
    pad_l, pad_r, pad_t, pad_b = 30, 14, 14, 26
    plot_w, plot_h = size_w - pad_l - pad_r, size_h - pad_t - pad_b
    xs = [p.get(x_key, 0) for p in points]
    ys = [p.get(y_key, 0) for p in points]
    x_max = max(xs) if xs and max(xs) else 1
    y_max = max(ys) if ys and max(ys) else 1
    sizes = [p.get(size_key, 1) for p in points] if size_key else [1] * len(points)
    size_max = max(sizes) if sizes and max(sizes) else 1
    parts = [f'<svg width="{size_w}" height="{size_h}" viewBox="0 0 {size_w} {size_h}" xmlns="http://www.w3.org/2000/svg">']
    parts.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{size_h - pad_b}" stroke="{PANEL_BORDER}" stroke-width="1.2" />')
    parts.append(f'<line x1="{pad_l}" y1="{size_h - pad_b}" x2="{size_w - pad_r}" y2="{size_h - pad_b}" stroke="{PANEL_BORDER}" stroke-width="1.2" />')
    top_idx = max(range(len(points)), key=lambda i: xs[i]) if points else None
    for i, (p, x_val, y_val, sz) in enumerate(zip(points, xs, ys, sizes)):
        cx = pad_l + (x_val / x_max) * plot_w
        cy = size_h - pad_b - (y_val / y_max) * plot_h
        r = 4 + (sz / size_max) * 9
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{base}" fill-opacity="0.7" stroke="{base}" stroke-width="1" />')
        if i == top_idx:
            label = str(p.get("label", ""))
            # BATASAN USER: label TIDAK dipotong - ukuran font-nya yang menyesuaikan panjang
            # label terpanjang (dihitung di _funnel_chart_svg), jadi nama utuh selalu tampil.
            short_label = label
            # BUG NYATA DIPERBAIKI (uji tumpang-tindih, laporan 158/164/157): label titik
            # digambar di ATAS tiap gelembung tanpa memeriksa tetangganya sama sekali. Dua
            # entitas yang nilainya berdekatan -> label bertumpuk, 95% tertutup ("PKG" di
            # balik "PKG-AS-25"). Label TIDAK dipotong (aturan tetap) - yang bertabrakan
            # DILEWATI, krn nama separuh tertutup lebih buruk daripada nama yang tidak
            # digambar: yang tertutup terbaca SALAH, yang absen cuma absen.
            _lw = len(short_label) * 7 * 0.62
            _kotak = (cx - _lw / 2, cy - r - 11, cx + _lw / 2, cy - r - 1)
            _bentrok = not label_box_does_not_overlap(_kotak, _label_terpasang)
            if _bentrok:
                continue
            _label_terpasang.append(_kotak)
            parts.append(
                f'<text x="{cx:.1f}" y="{cy - r - 4:.1f}" text-anchor="middle" font-size="7" font-weight="700" '
                f'fill="{TEXT_DARK}" font-family="{BODY_FONT}">{_esc(short_label)}</text>'
            )
    parts.append(f'<text x="{pad_l}" y="{size_h - 6}" font-size="7" fill="{GRAY_TEXT}" font-family="{BODY_FONT}">{_esc(x_label)}</text>')
    parts.append("</svg>")
    return f'<div style="text-align:center;">{"".join(parts)}</div>'


def _ranked_bar_ternorm_html(labels, values, color=None, is_en=False) -> str:
    """Ranked bar TERNORMALISASI - panjang relatif, angka tetap absolut.

    Dipakai saat batang terkecil < 2% dari terbesar: di bawah itu batangnya praktis garis &
    panjangnya tidak bisa dibedakan. Skala log SENGAJA TIDAK dipakai - pembaca non-teknis
    membaca panjang batang sbg besaran, dan log memutus hubungan itu DIAM-DIAM (kelas
    kesalahan yang sama dgn pemotongan diam: pembaca tidak punya cara tahu).

    TIGA SYARAT yang membuat normalisasi jujur:
      1. tiap nilai dinormalkan ke MAKSIMUM deret ini;
      2. sumbu diberi label EKSPLISIT ("relatif terhadap tertinggi"), tidak tersirat;
      3. NILAI ASLI tertulis di ujung tiap batang - tanpa ini normalisasi jadi pemotongan
         diam dalam bentuk lain."""
    if not values:
        return ""
    warna = color or GREEN_MAIN
    maks = max(values) or 1
    baris = []
    # LABEL DI ATAS BAR, bukan di kolom samping. Terukur: nama entitas UTUH (rata-rata 38
    # karakter) muat SATU baris pada 7pt di lebar kolom penuh, dan tinggi entrinya 0.26in -
    # lebih pendek drpd 0.35in baris label-di-samping. Kolom label samping 1.33in itulah yang
    # dulu memaksa pemendekan, bukan panjang namanya: 12 baris x 7 karakter (79) menjadi
    # 16 baris x 37 karakter (595).
    # Nama TIDAK dipendekkan, TIDAK dielipsis, TIDAK ada overflow:hidden - kalau ada nama yang
    # tetap tidak muat satu baris, ia membungkus dan barisnya jadi lebih tinggi apa adanya.
    for lbl, val in zip(labels, values):
        pct = max(1.2, (float(val) / maks) * 100.0)
        baris.append(
            f'<tr><td style="padding:1pt 0 0 0;">'
            f'<table style="width:100%;" cellpadding="0" cellspacing="0"><tr>'
            f'<td style="font-size:7pt;color:{TEXT_DARK};line-height:1.15;">{_esc(str(lbl))}</td>'
            f'<td style="width:74px;text-align:right;font-size:7pt;font-weight:700;'
            f'color:{TEXT_DARK};line-height:1.15;">{_fmt_num(val)}</td></tr></table>'
            f'<table style="width:100%;background:{PANEL_BORDER};border-radius:3px;'
            f'margin:1pt 0 2pt 0;" cellpadding="0" cellspacing="0"><tr>'
            f'<td style="width:{pct:.2f}%;background:{warna};height:7px;border-radius:3px;'
            f'font-size:1px;line-height:1px;">&nbsp;</td><td></td></tr></table>'
            f'</td></tr>'
        )
    sumbu = "relative to highest" if is_en else "relatif terhadap tertinggi"
    return (
        f'<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0">'
        f'{"".join(baris)}</table>'
        f'<div style="font-size:7pt;color:{GRAY_TEXT};margin-top:3pt;">'
        f'| {_esc(sumbu)} &mdash; {_esc("highest" if is_en else "tertinggi")} {_fmt_num(maks)}</div>'
    )


def _grouped_bar_ternorm_html(labels, seri_a, seri_b, label_a="", label_b="",
                              color_a=None, color_b=None, is_en=False) -> str:
    """Grouped bar TERNORMALISASI - tiap deret ke MAKSIMUMNYA SENDIRI.

    Dipakai saat rasio antar metrik >= 20x. Ambang 20x sengaja TIDAK dilonggarkan: rasio
    100x berarti batang terkecil 1% dari terbesar, sementara 2% sudah ditetapkan sbg ambang
    keterbacaan ranked bar - melonggarkannya berarti dua standar berbeda utk masalah visual
    yang sama.

    BAHAYA KHAS BENTUK INI (permintaan user, ditangani eksplisit): karena tiap deret
    dinormalkan ke maksimumnya SENDIRI, dua batang bersebelahan yang SAMA PANJANG TIDAK
    berarti nilainya sama. Satu label sumbu tidak cukup menyampaikan itu - jadi tiap deret
    membawa MAKSIMUMNYA SENDIRI di legenda ("Illegal (maks 66)", "Legal (maks 71.034)"),
    supaya panjang batang bisa dibaca sbg proporsi thd angka yang tertulis. Dan nilai ASLI
    tetap tertulis di ujung tiap batang."""
    if not labels:
        return ""
    ca, cb = color_a or GREEN_MAIN, color_b or GOLD_MAIN
    maks_a = max(seri_a) or 1
    maks_b = max(seri_b) or 1
    baris = []
    for lbl, va, vb in zip(labels, seri_a, seri_b):
        pa = max(1.2, (float(va) / maks_a) * 100.0)
        pb = max(1.2, (float(vb) / maks_b) * 100.0)
        sel = []
        for pct, val, warna in ((pa, va, ca), (pb, vb, cb)):
            sel.append(
                f'<table style="width:100%;background:{PANEL_BORDER};border-radius:3px;margin-bottom:2pt;" cellpadding="0" cellspacing="0"><tr>'
                f'<td style="width:{pct:.2f}%;background:{warna};height:8px;border-radius:3px;font-size:1px;line-height:1px;">&nbsp;</td>'
                f'<td style="text-align:right;font-size:7.5pt;font-weight:700;color:{TEXT_DARK};'
                f'padding-left:5px;white-space:nowrap;">{_fmt_num(val)}</td></tr></table>'
            )
        baris.append(
            f'<tr><td style="width:112px;padding:2pt 6pt 2pt 0;font-size:7pt;color:{TEXT_DARK};'
            f'vertical-align:middle;">{_esc(str(lbl))}</td>'
            f'<td style="vertical-align:middle;padding:2pt 0;">{"".join(sel)}</td></tr>'
        )
    mk = "max" if is_en else "maks"
    legenda = (
        f'<div style="font-size:7pt;color:{GRAY_TEXT};margin-top:3pt;">'
        f'<span style="display:inline-block;width:7px;height:7px;background:{ca};margin-right:4px;"></span>'
        f'{_esc(label_a)} ({mk} {_fmt_num(maks_a)}) &nbsp;&nbsp;'
        f'<span style="display:inline-block;width:7px;height:7px;background:{cb};margin-right:4px;"></span>'
        f'{_esc(label_b)} ({mk} {_fmt_num(maks_b)})<br>'
        f'{_esc("each series relative to its own max - equal lengths are NOT equal values" if is_en else "tiap deret relatif thd maksimumnya sendiri - panjang sama BUKAN berarti nilai sama")}'
        f'</div>'
    )
    return (f'<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0">'
            f'{"".join(baris)}</table>{legenda}')


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
            f'fill="#fff" font-family="{BODY_FONT}">{_esc(cat)} &#183; {_fmt_num(val)}</text>'
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
        f'<span style="font-weight:700;font-size:10.5pt;color:{TEXT_DARK};text-transform:uppercase;">{_esc(title_text)}</span>'
        f'</td></tr></table>'
    )
    # BUG BESAR YANG DIPERBAIKI: atribut HTML `cellpadding` TERBUKTI (isolasi render+sampling,
    # ekstraksi posisi teks aktual dari PDF) TIDAK dihormati WeasyPrint di sini — konten panel
    # menempel rata ke tepi border/rounded-corner (inset 0), bukan diberi jarak 16px seperti
    # diminta. Diganti CSS `padding` langsung pada <td> (didukung penuh & terverifikasi benar).
    return (
        f'<table style="width:100%;background:{IVORY};border:1px solid {PANEL_BORDER};border-radius:3px;">'
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
        f'<table style="width:{w};background:{t["bg"]};border:1px solid {t["light"]};border-radius:3px;">'
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


def _bullet_lines_html(text, theme: dict | None = None, font_pt=9, numbered: bool = False) -> str:
    """Baris bullet polos (titik warna aksen + teks), TANPA bungkus kotak/judul — dipakai
    _note_box_html di bawah (mode penuh) DAN tile insight_dashboard (mode ringkas, sudah
    dibungkus kartu bordered sendiri, kotak-dalam-kotak kalau dipakaikan _note_box_html utuh
    lagi di situ).

    PERMINTAAN USER: kotak catatan harus bisa memuat BEBERAPA butir bernomor, kalimat UTUH
    (bukan dipotong regex per kalimat) — `text` sekarang boleh berupa list/tuple string (1
    butir = 1 baris APA ADANYA, `numbered=True` menomori 1./2./3.), selain string biasa
    (perilaku LAMA tetap: dipecah otomatis per kalimat pakai regex, bullet titik)."""
    t = theme or THEME_PALETTES["green"]
    if isinstance(text, (list, tuple)):
        lines = [str(l).strip() for l in text if str(l or "").strip()]
    else:
        lines = [l for l in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if l]
    if not lines:
        return ""
    marker_w = "16pt" if numbered else "11pt"
    rows = "".join(
        f'<tr>'
        f'<td style="width:{marker_w};vertical-align:top;padding:2pt 4pt 2pt 0;color:{t["main"]};font-weight:700;font-size:{font_pt}pt;">{f"{i + 1}." if numbered else "&#8226;"}</td>'
        f'<td style="vertical-align:top;padding:2pt 0;font-size:{font_pt}pt;color:{GRAY_TEXT};">{_esc(line)}</td>'
        f'</tr>'
        for i, line in enumerate(lines)
    )
    return f'<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0">{rows}</table>'


def _note_box_html(text, theme: dict | None = None, title: str | None = None) -> str:
    """Kotak "Catatan:" (border kiri warna aksen + bullet per kalimat) — GANTI dari
    _ai_insight_strip lama (1 baris italic polos) supaya caption AI terasa seperti kotak
    catatan di laporan referensi, BUKAN paragraf mengalir biasa (temuan user: laporan masih
    terasa "berat kata-kata" meski chart-nya sudah ada). Dipakai di SEMUA titik caption chart
    (kategori/severity/status) & dynamic_section. `text` boleh list/tuple (mis. beberapa temuan
    terpisah) — dinomori otomatis, lihat _bullet_lines_html."""
    t = theme or THEME_PALETTES["green"]
    numbered = isinstance(text, (list, tuple))
    rows_html = _bullet_lines_html(text, theme=t, numbered=numbered)
    if not rows_html:
        return ""
    # Bawaan ikut BAHASA LAPORAN, bukan Indonesia. Pemanggil yang lupa mengoper judul
    # dulu menghasilkan "Catatan:" di laporan berbahasa Inggris.
    label = title or ("Notes" if render_is_en() else "Catatan")
    return (
        f'<div style="background:{IVORY};border-left:3px solid {GRAY_TEXT};border-radius:3px;padding:9pt 12pt;margin-top:10pt;">'
        # A5: label "Catatan:" HIJAU BOLD ITALIC seperti acuan (#00B050), bukan abu polos
        # huruf-besar-semua. Ini salah satu dari dua hal yang acuan pakai untuk membuat
        # kotak catatan terbaca sebagai catatan, bukan sebagai blok teks lain.
        f'<div style="font-size:8.5pt;font-weight:700;font-style:italic;color:{CATATAN_LABEL};margin-bottom:4pt;">{_esc(label)}:</div>'
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


def _card_grid(cell_inner_htmls: list, cols: int, card_style: dict | None = None) -> str:
    """Susun daftar HTML kartu jadi grid N kolom pakai <table> (bukan flexbox/grid CSS —
    tidak didukung xhtml2pdf, fallback engine kalau WeasyPrint tak tersedia).

    RANCANG ULANG (target WeasyPrint, lihat catatan di _ivory_panel): height eksplisit &
    workaround gap-lewat-row_height DIHAPUS — cukup andalkan perilaku standar tabel HTML:
    tiap baris otomatis setinggi kartu TERTINGGI di baris itu (bukan tinggi tetap sepihak),
    dan kartu-kartu dengan konten pendek TIDAK LAGI dipaksa setinggi kartu dengan konten
    terpanjang yang mungkin pernah ada — mengurangi ruang kosong raksasa dalam kartu jauh
    lebih baik daripada budget height tetap manapun. Jarak antar baris dari margin-bottom
    pada kartu itu sendiri (lihat _stat_card_grid/_asset_card_row), bukan dari grid ini.

    `card_style` (opsional, dict {"bg","border_color","radius","pad_pt"}) — BUG DIPERBAIKI
    (dilaporkan user: kartu dashboard dgn panjang konten beda-beda antar tile kelihatan beda
    TINGGI dlm 1 baris yang sama). Sebelumnya SEMUA pemanggil menaruh background/border/
    padding kartu di TABEL BERSARANG di dalam <td> — <td> pembungkusnya sendiri MEMANG
    dijamin standar HTML table selalu meregang penuh ke tinggi baris tertinggi, TAPI tabel
    bersarang di dalamnya TIDAK ikut otomatis meregang ke tinggi <td> itu (beda box, height
    tetap sesuai kontennya sendiri) — kartu yang kontennya lebih pendek jadi kelihatan
    berhenti lebih awal drpd tetangganya di baris yang sama walau tingginya kolom sudah sama.
    Kalau `card_style` diisi, background/border/radius/padding dipasang LANGSUNG di <td> itu
    sendiri (TANPA tabel bersarang lagi) — <td> otomatis penuh, background/border-nya ikut
    penuh juga. `cell_inner_htmls` dlm mode ini WAJIB berisi KONTEN MENTAH saja (title/chart/
    caption), BUKAN <table> kartu lengkap seperti mode lama. Jarak antar kartu (dulu dari
    padding horizontal per-<td>, tidak bisa dipakai lagi krn background sekarang mengisi
    penuh <td>) diganti `cellspacing` tabel (border-collapse:separate WAJIB menyertainya,
    collapse mengabaikan cellspacing) — otomatis dapat jarak vertikal antar baris juga
    (sebelumnya nihil, cuma horizontal).

    Pemanggil LAIN yang belum dipindah ke mode ini (card_style=None, default) TETAP jalan
    PERSIS seperti sebelumnya, nol perubahan perilaku — migrasi dilakukan bertahap per
    pemanggil, bukan sekaligus semua, supaya risikonya kecil per langkah.

    KEBIJAKAN BARIS TERAKHIR (BUG DIPERBAIKI, drift vs export_ppt.py::add_stat_card_grid):
    dulu baris terakhir yang isinya kurang dari `cols` (mis. 5 item dgn cols=3 -> baris
    terakhir cuma 2) diisi <td> KOSONG TAK TERLIHAT sbg pengganjal (lebar kartu asli tetap
    1/cols, sisa slot menganggur kosong) — beda kebijakan dgn add_stat_card_grid (PPT) yang
    melebarkan kartu SISA itu mengisi penuh baris (row_items_count dihitung per-baris, bukan
    lebar tetap). Disamakan ke kebijakan PPT (melebar mengisi) di sini — lebar kartu
    SEKARANG dihitung PER BARIS dari jumlah item SEBENARNYA di baris itu, bukan cols global;
    baris terakhir yang lebih sedikit otomatis melebar penuh, TIDAK ADA LAGI <td> pengganjal
    kosong sama sekali."""
    if card_style:
        bg = card_style.get("bg", IVORY)
        border_color = card_style.get("border_color", PANEL_BORDER)
        radius = card_style.get("radius", 3)
        pad_pt = card_style.get("pad_pt", 14)
        # `border_left_colors` (opsional, list sepanjang cell_inner_htmls) — PERMINTAAN USER
        # (E1, "tinggi kartu 1 baris harus seragam"): beberapa pemanggil (rekomendasi
        # berbadge prioritas, KPI grid berwarna status) butuh border-left BEDA WARNA per
        # kartu (mis. merah utk urgency critical) — tetap bisa lewat mode card_style (uniform
        # height via <td>) dgn override 1 sisi ini, TANPA perlu balik ke tabel bersarang lama.
        border_left_colors = card_style.get("border_left_colors")
        # `valign`/`align` (opsional) — PERMINTAAN USER (lanjutan E1): kartu angka ringkas
        # (_stat_card_grid dkk) butuh konten DITENGAHKAN (angka besar + label pendek terasa
        # simetris), beda dgn kartu berisi teks/daftar yang harus rata kiri-atas seperti biasa
        # — default TETAP "top"/"left" (perilaku lama, nol perubahan utk pemanggil lain).
        valign = card_style.get("valign", "top")
        align = card_style.get("align", "left")
        rows = []
        for i in range(0, len(cell_inner_htmls), cols):
            row_items = cell_inner_htmls[i:i + cols]
            row_col_w = round(100 / len(row_items), 3)
            row_cells = []
            for j, inner in enumerate(row_items):
                left_color = border_left_colors[i + j] if border_left_colors else None
                border_css = (
                    f'border-top:1px solid {border_color};border-right:1px solid {border_color};'
                    f'border-bottom:1px solid {border_color};border-left:3px solid {left_color};'
                ) if left_color else f'border:1px solid {border_color};'
                row_cells.append(
                    f'<td style="width:{row_col_w}%;vertical-align:{valign};text-align:{align};background:{bg};{border_css}'
                    f'border-radius:{radius}px;padding:{pad_pt}pt;">{inner}</td>'
                )
            rows.append(f'<tr>{"".join(row_cells)}</tr>')
        return f'<table style="width:100%;border-collapse:separate;" cellpadding="0" cellspacing="12">{"".join(rows)}</table>'

    rows = []
    for i in range(0, len(cell_inner_htmls), cols):
        row_items = cell_inner_htmls[i:i + cols]
        row_col_w = round(100 / len(row_items), 3)
        row_cells = [f'<td style="width:{row_col_w}%;padding:0 6px;vertical-align:top;">{inner}</td>' for inner in row_items]
        rows.append(f'<tr>{"".join(row_cells)}</tr>')
    return f'<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0">{"".join(rows)}</table>'


def _stat_card_grid(items, cols=3, dark=True, theme: dict | None = None) -> str:
    # PERMINTAAN USER (E1, lanjutan — tinggi kartu 1 baris harus seragam): dipindah ke
    # card_style (background/border langsung di <td>, bukan tabel bersarang) spt pemanggil
    # lain yang sudah dimigrasi — lihat catatan panjang di _card_grid.
    t = theme or THEME_PALETTES["green"]
    bg = t["main"] if dark else IVORY
    label_color = WHITE if dark else TEXT_DARK
    cell_htmls = [
        f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:22pt;color:{t["light"]};">{_esc(value)}</div>'
        f'<div style="font-size:9pt;color:{label_color};margin-top:6px;">{_esc(label)}</div>'
        for value, label in items
    ]
    card_style = {"bg": bg, "border_color": t["light"], "radius": 3, "pad_pt": 14, "valign": "middle", "align": "center"}
    return _card_grid(cell_htmls, cols, card_style=card_style)


def _asset_card_row(items, theme: dict | None = None, scale: float = 1.0) -> str:
    # PERMINTAAN USER (E1, lanjutan): dipindah ke card_style spt _stat_card_grid di atas.
    # BUG DIPERBAIKI (ditemukan lewat tes kepadatan halaman, permintaan user): font/badge/
    # padding dulu TETAP apa pun ruang yang tersedia — solo di 1 halaman penuh (3 kartu
    # kecil di tengah halaman lapang), sisa ruang di atas/bawah cuma jadi margin kosong,
    # bukan isi (`scale` dinaikkan dari ctx.panel_count di pemanggil, sama pola dgn
    # _build_management_action_items_block/_build_key_findings_block)."""
    t = theme or THEME_PALETTES["green"]
    n = len(items) or 1
    badge_px = round(34 * scale)
    cell_htmls = [
        f'{_badge(num, t["light"], size=f"{badge_px}px", font_size=f"{13*scale:.1f}pt")}'
        f'<div style="font-weight:700;font-size:{12.5*scale:.1f}pt;color:#fff;margin-top:{round(12*scale)}px;">{_esc(title)}</div>'
        f'<div style="font-weight:700;font-size:{10.5*scale:.1f}pt;color:{t["light"]};margin-top:{round(4*scale)}px;">{_esc(stat)}</div>'
        f'<div style="font-size:{9*scale:.1f}pt;color:#E8ECE6;margin-top:{round(10*scale)}px;line-height:1.5;">{_esc(desc)}</div>'
        for num, title, stat, desc in items
    ]
    card_style = {"bg": t["main"], "border_color": t["light"], "radius": 3, "pad_pt": round(18 * scale)}
    return _card_grid(cell_htmls, n, card_style=card_style)


_ASSET_LEVEL_TIERS = (
    (66, ("Tinggi", "High"), "#2E7D46"),
    (33, ("Sedang", "Medium"), GOLD_MAIN),
    (0, ("Rendah", "Low"), GRAY_TEXT),
)


def _asset_ranked_bars_html(items, theme: dict | None = None, is_en: bool = False) -> str:
    """Alternatif visual KETIGA (selain _asset_card_row/_podium_row) — daftar entitas
    berperingkat dengan batang proporsional horizontal per item (badge nomor + nama + badge
    level + batang + angka), BUKAN kartu kotak atau podium — titik variasi tampilan tambahan
    utk asset_cards (lihat `asset_style`). Dipakai utk jumlah item BERAPA PUN (podium hanya
    cocok tepat 3).

    PERMINTAAN USER ("kartu bersarang": header berwarna + skor besar + badge level + daftar
    bar mini berlabel dengan garis target): badge level (Tinggi/Sedang/Rendah, dari posisi
    RELATIF nilai item ini thd nilai TERTINGGI di daftar — bukan ambang tetap) & garis target
    (posisi RATA-RATA seluruh item di daftar, position:absolute di atas track bar) ditambahkan
    di sini — target = rata-rata, tolok ukur netral yang genuinely dari data, bukan angka
    sembarang."""
    if not items:
        # BUG DIPERBAIKI (audit F2, defense-in-depth): pemanggil saat ini (pick_category())
        # tidak pernah mengembalikan list kosong, TAPI max(counts) di bawah akan ValueError
        # kalau suatu saat itu berubah — dijaga eksplisit spt saudara2nya (add_stat_card_grid
        # dkk) drpd diam2 bergantung pada jaminan pemanggil yang tidak ditegakkan di sini.
        return ""
    t = theme or THEME_PALETTES["green"]
    counts = [it.get("count") or 0 for it in items]
    max_count = max(counts) or 1
    avg_count = (sum(counts) / len(counts)) if counts else 0
    avg_pct = min(round(avg_count / max_count * 100, 1), 100)
    # PERMINTAAN USER ("angka harus melekat di chart"): garis target dulu cuma garis putih
    # tanpa angka - pembaca lihat ADA tolok ukur tapi tidak tahu tolok ukurnya BERAPA, jadi
    # harus menerka dari catatan kaki. Nilainya ditempel langsung di garisnya. Ditaruh DI
    # BAWAH track (top:14px) yang jatuh di padding 12pt milik barisnya - bukan di atas, di
    # mana tidak ada ruang & teks akan terpotong. Cuma di baris PERTAMA: garisnya sama utk
    # semua baris, mengulang angka yang sama di tiap baris cuma jadi bising.
    # Posisi label dijepit 6-88% supaya teksnya tidak menjorok keluar tepi track saat
    # rata-ratanya mepet ujung; GARISNYA sendiri tetap di avg_pct yang sebenarnya.
    avg_label_pct = min(max(avg_pct, 6.0), 88.0)
    avg_marker_label = (
        f'<div style="position:absolute;left:{avg_label_pct}%;top:14px;transform:translateX(-50%);'
        f'font-size:6.5pt;color:#C9CFC5;white-space:nowrap;">'
        f'{"avg" if is_en else "rata-rata"} {_esc(_fmt_num(round(avg_count, 1)))}</div>'
    )
    rows = []
    for it in items:
        pct = round((it.get("count") or 0) / max_count * 100, 1)
        pct = max(pct, 4)
        level_label, level_color = "", GRAY_TEXT
        for threshold, (lbl_id, lbl_en), color in _ASSET_LEVEL_TIERS:
            if pct >= threshold:
                level_label, level_color = (lbl_en if is_en else lbl_id), color
                break
        level_badge = (
            f'<span style="display:inline-block;margin-left:8px;padding:1px 8px;border-radius:10px;'
            f'background:{level_color};color:#fff;font-size:7pt;font-weight:800;text-transform:uppercase;'
            f'vertical-align:middle;">{_esc(level_label)}</span>'
        )
        rows.append(
            f'<tr><td style="padding:12pt 0;">'
            f'<table style="width:100%;" cellpadding="0" cellspacing="0"><tr>'
            f'<td style="width:40px;vertical-align:middle;">{_badge(it["num"], t["light"], size="32px", font_size="12pt")}</td>'
            f'<td style="vertical-align:middle;padding:0 14pt;">'
            f'<div style="font-weight:700;font-size:12pt;color:#fff;margin-bottom:8px;">{_esc(it["name"])}{level_badge}</div>'
            f'<div style="position:relative;">'
            f'<table style="width:100%;background:{t["chart"]};border-radius:5px;" cellpadding="0" cellspacing="0"><tr>'
            f'<td style="width:{pct}%;">'
            f'<table style="width:100%;" cellpadding="0" cellspacing="0"><tr>'
            f'<td style="background:{t["light"]};height:12px;border-radius:5px;font-size:1px;line-height:1px;">&nbsp;</td>'
            f'</tr></table></td>'
            f'<td></td>'
            f'</tr></table>'
            f'<div style="position:absolute;left:{avg_pct}%;top:-2px;width:2px;height:16px;background:#fff;border:1px solid {TEXT_DARK};"></div>'
            f'{avg_marker_label if not rows else ""}'
            f'</div>'
            f'</td>'
            f'<td style="width:95px;text-align:right;vertical-align:middle;font-weight:700;font-size:12pt;color:{t["light"]};">{_esc(it["stat"])}</td>'
            f'</tr></table>'
            f'</td></tr>'
        )
    footnote = (
        f'<div style="font-size:7.5pt;color:#C9CFC5;margin-top:2pt;">'
        f'{"| Target line = average" if is_en else "| Garis target = rata-rata"}'
        f' ({_esc(_fmt_num(round(avg_count, 1)))})</div>'
    )
    return f'<table style="width:100%;border-collapse:collapse;" cellpadding="0" cellspacing="0">{"".join(rows)}</table>{footnote}'


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
            f'<div style="background:{color};border-radius:3pt 3pt 0 0;height:{h}pt;">'
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
    logo_html = _dark_logo_html(logo_b64, size_px=39, top="0.28in") if logo_b64 else ""
    right_td = (
        f'<td style="width:{100 - left_w_pct}%;background:{t["bg"]};color:#fff;position:relative;'
        f'height:7.5in;vertical-align:top;font-family:{BODY_FONT};overflow:hidden;">'
        f'{_flourish_html(flourish_corner, theme=t)}'
        f'{logo_html}'
        f'<div style="position:relative;margin:0.5in;">'
        f'<div style="height:1.6in;font-size:1px;line-height:1px;">&nbsp;</div>'
        f'{_kicker(block["kicker"], WHITE)}'
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
    logo_html = _dark_logo_html(logo_b64, size_px=39, top="0.28in") if logo_b64 else ""
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
    """Logo di atas latar GELAP — PERMINTAAN USER: sempat dibungkus kotak putih solid, lalu
    glow radial, akhirnya keduanya dianggap aneh/mengganggu. Sekarang tampil polos tanpa
    background treatment apa pun, sama seperti logo di halaman terang."""
    return (
        f'<div style="position:absolute;top:{top};right:{right};line-height:0;">'
        f'<img src="data:image/png;base64,{logo_b64}" style="height:{size_px}px;display:block;" /></div>'
    )


def _page(inner_html, dark=False, flourish=None, page_num=None, total_pages=None, logo_b64=None, last=False, raw=False, theme: dict | None = None, center=False, logo_size_px=None) -> str:
    t = theme or THEME_PALETTES["green"]
    break_style = "" if last else "page-break-after:always;"
    if raw:
        # `raw=True`: `inner_html` SUDAH berupa satu/lebih <td> lengkap (mis. cover/penutup
        # varian split-warna, 2 kolom background beda) — dipakai sebagai isi <tr> APA ADANYA,
        # tanpa background/margin-inset/flourish tunggal standar di bawah ini (pemanggil yang
        # bertanggung jawab penuh atas seluruh isi <tr>, termasuk warnanya sendiri).
        return f'<table style="width:13.333in;{break_style}" cellpadding="0" cellspacing="0"><tr>{inner_html}</tr></table>'
    # BUG DIPERBAIKI (permintaan user, C2): dulu t["soft"] (tint warna tema, beda2 per
    # laporan) — sekarang abu netral TETAP, lihat docstring PAGE_BG_NEUTRAL.
    bg = t["bg"] if dark else PAGE_BG_NEUTRAL
    color = WHITE if dark else TEXT_DARK
    flourish_html = _flourish_html(flourish, theme=t) if flourish else ""
    if logo_b64 and dark:
        # Logo aslinya berwarna gelap/hitam (lihat frontend/public/LOGO_PETRO_DANANTARA.png)
        # — perlu treatment kontras di halaman berlatar gelap (cover/penutup/panel dark)
        # supaya tetap kontras, bukan tenggelam di latar gelap yang sama (lihat
        # _dark_logo_html).
        # BUG DIPERBAIKI (dilaporkan user, disertai screenshot — logo halaman KONTEN biasa
        # jadi kegedean, malah lebih besar drpd cover): 84px di sini SEBELUMNYA dihitung waktu
        # file logo asli MASIH py padding transparan raksasa (_resolve_logo_b64 belum
        # memotongnya) — cuma ~46% dari 84px itu yang benar2 terlihat sbg logo (~39px efektif),
        # itulah ukuran yang user sudah setujui sbg "pas". Begitu _resolve_logo_b64 memotong
        # padding itu (lihat catatan panjang di sana), 84px yang SAMA jadi 100% terlihat —
        # otomatis ~2.2x lebih besar drpd sebelumnya TANPA maksud disengaja begitu, khusus di
        # SEMUA halaman konten biasa (bukan cuma cover/penutup yang memang sengaja diperbesar).
        # Diturunkan ke 39px (84 * rasio bbox lama ~0.462) supaya ukuran VISUAL akhirnya
        # kembali PERSIS sama seperti sebelum logo dipotong — cover/penutup TETAP di
        # `logo_size_px` besar (126, lihat generate_pdf_report) krn itu memang sengaja mau
        # lebih menonjol, TIDAK terkena regresi yang sama.
        # BUG DIPERBAIKI LAGI (dilaporkan user, disertai foto): halaman isi (bukan
        # cover/penutup) TERNYATA punya 2 ukuran logo berbeda tanpa disengaja — cabang GELAP
        # ini defaultnya 28px, sedangkan cabang TERANG di bawah 36px (hardcode, tidak ikut
        # `logo_size_px` sama sekali) — jadi halaman isi berlatar gelap (mis. Kesimpulan)
        # logonya kelihatan lebih kecil drpd halaman isi berlatar terang (mis. dashboard
        # visual), padahal keduanya sama2 "isi", harusnya konsisten. Disamakan ke 36px
        # (ukuran yang LEBIH BESAR dari 2 itu, sesuai pilihan user) utk kedua cabang.
        logo_html = _dark_logo_html(logo_b64, size_px=logo_size_px or 36)
    elif logo_b64:
        # BUG DIPERBAIKI (sama persis dgn cabang dark di atas): 108px dihitung sblm logo
        # dipotong dari padding transparannya — diturunkan ke 50px (108 * rasio ~0.462) supaya
        # ukuran visual akhirnya sama seperti sebelum dipotong. Sekarang ikut `logo_size_px`
        # juga (dulu hardcode 36px, mengabaikan parameter ini sama sekali) — konsisten dgn
        # cabang gelap di atas, cover/penutup gaya "solid" yang kebetulan terang tetap bisa
        # dapat ukuran 39px-nya, bukan diam2 dipaksa 36px.
        logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="position:absolute;top:0.22in;right:0.3in;height:{logo_size_px or 36}px;" />'
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
            f'{_kicker(block["kicker"], WHITE)}'
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
    # PERMINTAAN USER: halaman terpisah "Latar Belakang dan Tujuan Analisis" dihapus (cuma
    # metadata boilerplate, tidak layak jadi halaman sendiri) — kalimat tujuannya digabung ke
    # sini sbg paragraf tambahan (bukan italic spt caption, supaya beda peran: caption =
    # insight temuan, purpose_text = konteks/tujuan analisis).
    purpose_html = (
        f'<div style="font-size:10.5pt;color:{WHITE};margin-top:14px;max-width:9.5in;">{_esc(block["purpose_text"])}</div>'
    ) if block.get("purpose_text") else ""
    # PERMINTAAN USER: kalau Temuan Utama cuma 1 butir, halaman terpisahnya dihapus & butir
    # itu ditempel di sini (lihat report_render_logic.py, exec_summary_cand["extra_finding_text"]).
    extra_finding_html = (
        f'<div style="font-size:10.5pt;color:{WHITE};margin-top:10px;max-width:9.5in;">'
        f'<b>{_esc(block.get("extra_finding_label", ""))}</b> {_esc(block["extra_finding_text"])}</div>'
    ) if block.get("extra_finding_text") else ""
    # PERMINTAAN USER: halaman insight_tile/dynamic_section 1-panel yang tipis & gagal
    # disambung ke tetangga (lihat backstop terakhir di _group_candidates_into_pages) dititipkan
    # ke sini sbg beberapa butir bernomor, kalimat utuh — pakai _note_box_html mode list
    # (lihat catatan panjang di sana) drpd dipaksa jadi halaman sendiri yang nyaris kosong.
    # Halaman ini GELAP (dark=True) — _note_box_html/_bullet_lines_html didesain utk latar
    # TERANG (ivory+teks gelap), dipakai persis di sini bakal kontras aneh dgn sisa halaman.
    # Dirender manual, gaya sama dgn purpose_html/extra_finding_html di atas (teks putih polos
    # bernomor), bukan pakai komponen kotak catatan yang bertema terang.
    orphan_insights = block.get("extra_orphan_insights") or []
    orphan_html = "".join(
        f'<div style="font-size:10.5pt;color:{WHITE};margin-top:10px;max-width:9.5in;">'
        f'{_esc(str(i + 1) + ".")} <b>{_esc(o["label"])}</b> {_esc(o["text"])}</div>' if o.get("label")
        else f'<div style="font-size:10.5pt;color:{WHITE};margin-top:10px;max-width:9.5in;">{_esc(str(i + 1) + ".")} {_esc(o["text"])}</div>'
        for i, o in enumerate(orphan_insights)
    )
    inner = (
        _kicker(ctx.kicker_ringkasan, WHITE) +
        f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:20pt;color:#fff;margin-bottom:18px;">{_esc(block["heading"])}</div>' +
        _stat_card_grid(block["stat_items"], cols=ctx.stat_cols, dark=True, theme=ctx.theme) +
        # max-width dibatasi ~9.5in (bukan full CONTENT_W ~12.3in) — paragraf
        # selebar halaman penuh di kertas widescreen 13.333in menghasilkan baris
        # >150 karakter, jauh melebihi lebar baca nyaman (~75-90 karakter); versi
        # referensi selalu membatasi teks naratif ke lebar yang lebih wajar.
        f'<div style="font-size:10.5pt;font-style:italic;color:{ctx.accent_soft};margin-top:18px;max-width:9.5in;">{_esc(block["caption"])}</div>' +
        purpose_html +
        extra_finding_html +
        orphan_html +
        chart_html
    )
    return (inner, True, None, False)


def _mini_legend_html(categories, ramp, text_color=None, compact=False) -> str:
    """Legend ringkas (titik warna + nama, tanpa persentase) utk chart "donut"/"stacked" di
    _mini_chart_html — _donut_chart_svg/_stacked_proportion_bar_html sendiri MURNI grafik
    (beda dari React DonutChart/StackedBar yang legend-nya sudah menyatu di komponennya),
    tanpa ini pembaca tidak tahu warna mana mewakili kategori apa di panel kecil ini.
    `text_color` opsional (default GRAY_TEXT) — dioverride panel berlatar gelap."""
    # BUG DIPERBAIKI (ditemukan lewat verifikasi otomatis di banyak laporan sungguhan, bukan
    # cuma 1 kasus — report id 165, tile "Procurement Service Category Insights"): nama
    # kategori/label di sini datang APA ADANYA dari data/AI (mis. "Kalibrasi Alat Ukur
    # Laboratorium", 33 karakter) — TIDAK ADA batas panjang sebelumnya, jadi label yang
    # panjang bikin legend ini melebar jadi 3-4 BARIS (bukan 1-2 baris spt asumsi desain
    # awal), menambah tinggi tile dashboard tanpa terkontrol & bisa mendorong konten di
    # bawahnya (caption) melewati batas tinggi halaman lalu terpotong overflow:hidden (lihat
    # catatan panjang di _mgmt_tile_chart_html/_build_management_visual_dashboard_block).
    # Label sekarang dibatasi keras scr karakter (bukan sekadar dipangkas kalimat) supaya
    # tinggi legend ini SELALU bisa diprediksi, tidak lagi bergantung penuh pada seberapa
    # panjang nama kategori aslinya.
    # `compact=True` (dipakai saat grid dashboard 2+ baris, lihat _mgmt_tile_chart_html) —
    # item DIBATASI JUMLAHNYA (bukan cuma panjang teksnya) & font/line-height diperkecil lagi
    # supaya tinggi legend BENAR2 bisa diprediksi (label 6 item x 20 karakter ternyata MASIH
    # bisa melebar 2-3 baris & memicu overflow yang sama, ditemukan lewat verifikasi ulang).
    if compact:
        categories = categories[:4]
    text_color = text_color or GRAY_TEXT
    font_pt = 7 if compact else 8
    truncate_len = 14 if compact else 20
    line_height = 1.65 if compact else 2
    margin_top = 5 if compact else 8
    dd_categories = _dedupe_truncated_labels(categories, truncate_len)
    dots = "".join(
        f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{ramp[i % len(ramp)]};margin-right:4px;"></span>'
        f'<span style="font-size:{font_pt}pt;color:{text_color};margin-right:10px;">{_esc(cat)}</span>'
        for i, cat in enumerate(dd_categories)
    )
    return f'<div style="margin-top:{margin_top}pt;line-height:{line_height};">{dots}</div>'


def _merge_tail_into_other(labels, values, colors, max_items=4, other_label=None):
    # other_label bawaan ikut BAHASA LAPORAN (dulu "Lainnya" apa adanya).
    """Kalau item lebih dari `max_items`, gabungkan SISA item (indeks max_items-1 dan
    seterusnya) jadi SATU entri "{other_label}" (nilainya dijumlah) — dipakai bareng utk
    donat & legend-nya SEBELUM keduanya digambar (bukan 2 pemotongan terpisah).

    BUG DIPERBAIKI (dilaporkan user): _mini_legend_html (compact=True) sebelumnya cuma
    MEMOTONG label yang DITAMPILKAN (categories[:4]) TANPA mengubah data donat-nya sama
    sekali — donat tetap menggambar SEMUA slice asli (mis. 6), padahal legend cuma
    menyebutkan 4 nama pertama, jadi 2 slice sisanya kelihatan di chart TANPA keterangan
    warna apa pun (warnanya "yatim", pembaca tidak tahu itu apa). Dipanggil di sini —
    SEBELUM _donut_chart_svg maupun _mini_legend_html — supaya jumlah slice yang digambar
    SELALU sama persis dgn jumlah nama yang disebut di legend."""
    if len(labels) <= max_items:
        return labels, values, colors
    keep = max_items - 1
    merged_value = sum(values[keep:])
    other_label = other_label or ("Others" if render_is_en() else "Lainnya")
    new_labels = list(labels[:keep]) + [other_label]
    new_values = list(values[:keep]) + [merged_value]
    new_colors = list(colors[:keep]) + [GRAY_TEXT]
    return new_labels, new_values, new_colors


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
        return _stacked_proportion_bar_html(chart["values"], colors=colors, height_px=28, labels=chart["categories"])
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
            f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:22pt;color:{TEXT_DARK};">{_esc(value)}</div>'
            f'<div style="font-size:8.5pt;color:{GRAY_TEXT};margin-top:4pt;">{_esc(aux_label)}</div>'
            f'</div>'
        )
    elif panel.get("aux_list"):
        # PERMINTAAN USER ("panel bertingkat" — chart/angka -> strip KPI -> daftar kotak
        # angka): kalau ada totalnya, tampilkan sbg strip angka kecil DI ATAS daftar (bukan
        # cuma daftar sendirian) — total ini turunan LANGSUNG dari daftar yang sama persis di
        # bawahnya (bukan angka global tak terkait), jadi aman diulang tanpa terasa "tempelan".
        total_strip = (
            f'<div style="text-align:center;margin-bottom:8pt;">'
            f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:18pt;color:{TEXT_DARK};">{_esc(panel["aux_list_total"])}</div>'
            f'<div style="font-size:7.5pt;color:{GRAY_TEXT};">Total</div>'
            f'</div>'
        ) if panel.get("aux_list_total") else ""
        visual_html = total_strip + _ivory_kv_rows([(it["label"], it["value"]) for it in panel["aux_list"]], theme=ctx.theme)
    else:
        visual_html = ""
    # BUG DIPERBAIKI (dilaporkan user, sama akarnya dgn _draw_insight_tile di export_ppt.py):
    # pembungkus visual ini dulu dipatok height:1.4in TETAP (via <td> — height <td> jadi
    # MINIMUM, bukan maksimum, di WeasyPrint) apa pun tinggi ASLI kontennya — visual yang
    # genuinely pendek (mis. trend_stat cuma 2 baris teks) tetap "dipaksa" menempati slot
    # 1.4in penuh, mendorong caption di bawahnya turun & menyisakan celah kosong di antara
    # keduanya yang tidak perlu. Dihapus jadi <div> polos TANPA height dipatok — tinggi
    # sekarang MURNI dari konten aslinya (label -> visual -> caption mengalir wajar
    # berurutan dari atas, TIDAK ADA lagi celah paksaan di tengah).
    visual_wrap = f'<div style="text-align:center;">{visual_html}</div>' if visual_html else ""
    caption_text = panel.get("caption") or panel.get("text") or ""
    inner = (
        f'<div style="border:1px solid {PANEL_BORDER};border-radius:3px;padding:14pt;height:100%;">'
        f'{_panel_header_band(label)}'
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
        _kicker(ctx.kicker_analisis) + _title(block["title"]) +
        f'<div style="text-align:center;">{chart_html}</div>' + caption_html
    )
    return (inner, False, None, False)


def _build_time_heatmap_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    """Pola kejadian per hari/jam (heatmap grid) — panel MANDIRI, sama pola dgn
    category_distribution dkk.

    BUG DIPERBAIKI (ditemukan lewat tes kepadatan halaman, permintaan user): ukuran sel
    grid dulu SELALU 32px tetap apa pun ctx.panel_count — solo di 1 halaman penuh, grid
    kecil ini menyisakan banyak ruang kosong (mirror perbaikan yang sama di
    _build_period_compare_block, cuma di sana sudah ada skala panel_count sejak awal)."""
    cell = {1: 58, 2: 42}.get(ctx.panel_count, 32)
    chart_html = _heatmap_grid_svg(block["day_labels"], block["hour_labels"], block["grid"], color=ctx.accent_main, cell=cell)
    caption_html = _note_box_html(block.get("intro"), theme=ctx.theme) if block.get("intro") else ""
    inner = (
        _kicker(ctx.kicker_analisis) + _title(block["title"]) +
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
    # BUG DIPERBAIKI (ditemukan lewat tes kepadatan halaman, permintaan user): ukuran solo
    # (panel_count==1) dulu 760x230 — TERBUKTI masih menyisakan banyak ruang kosong (halaman
    # cuma terisi ~60%). Dinaikkan lagi (tinggi 230->340, lebar mengikuti proporsi yang sama)
    # supaya chart genuinely mengisi lebih banyak ruang lapang yang tersedia saat solo.
    size_w, size_h = {1: (900, 340), 2: (480, 200)}.get(ctx.panel_count, (340, 170))
    chart_html = _grouped_bar_chart_svg(
        block["categories"], block["series_a"], block["series_b"],
        label_a=block["label_a"], label_b=block["label_b"],
        color_a=ctx.accent_main, color_b=_light_safe(ctx.accent_light),
        size_w=size_w, size_h=size_h,
    )
    caption_html = _note_box_html(block.get("intro"), theme=ctx.theme) if block.get("intro") else ""
    inner = (
        _kicker(ctx.kicker_analisis) + _title(block["title"]) +
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
    elif ctx.category_style == "treemap":
        # PERMINTAAN USER (tambah jenis visualisasi baru): proporsi lewat luas kotak,
        # variasi tampilan baru di luar bar/donut/stacked yang sudah ada.
        chart_html = _treemap_svg(block["categories"], block["values"], colors=[ramp[l["color_index"] % len(ramp)] for l in block["legend"]], size_w=280, size_h=210)
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
        _kicker(ctx.kicker_analisis) + _title(block["title"]) +
        f'<div style="font-size:11pt;color:{GRAY_TEXT};margin-bottom:16px;max-width:9.5in;">{_esc(block["intro"])}</div>' +
        body + caption_html
    )
    return (inner, False, None, False)


def _build_severity_distribution_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    # SEVERITY_COLOR TIDAK PERNAH ikut tema — warna severity (critical=merah, high=emas, dst)
    # adalah konvensi semantik cyber-security yang fixed, terlepas dari theme_color laporan.
    sev_colors = [SEVERITY_COLOR[k] for k in block["severity_keys"]]
    chart_html = _bar_chart_html(block["categories"], block["values"], colors=sev_colors)
    panel = _critical_highlight_panel(f'{block["crit_pct"]}', block["panel_text"], block["detail_text"], theme=ctx.theme)
    caption_html = _note_box_html(block["ai_caption"], theme=ctx.theme) if block.get("ai_caption") else ""
    inner = (
        _kicker(ctx.kicker_analisis) + _title(block["title"]) +
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
    elif ctx.status_style == "treemap":
        # PERMINTAAN USER (tambah jenis visualisasi baru): sama prinsipnya dgn treemap di
        # category_distribution di atas.
        status_colors = [ramp[i % len(ramp)] for i in range(len(block["values"]))]
        legend_rows_html = _legend_rows([
            (status_colors[i], name, f"{round(val / (sum(block['values']) or 1) * 100, 1)}%")
            for i, (name, val) in enumerate(zip(block["categories"], block["values"]))
        ], theme=ctx.theme)
        legend_title = "Status Proportion" if is_english(ctx.report) else "Proporsi Status"
        legend_panel = _ivory_panel("%", legend_title, legend_rows_html, theme=ctx.theme)
        chart_html = _treemap_svg(block["categories"], block["values"], colors=status_colors, size_w=280, size_h=210)
        body = _main_panel_pair(chart_html, legend_panel, 58, ctx.panel_side)
    else:
        body = _bar_chart_html(block["categories"], block["values"], colors=[ctx.accent_bar_color] * len(block["values"]))
    inner = (
        _kicker(ctx.kicker_analisis) + _title(block["title"]) +
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
    kicker_color = RED_CRIT if block["kicker_is_critical"] else GRAY_TEXT
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
            _kicker(block["kicker"]) + _title(block["title"]) +
            f'<div style="margin-top:20pt;">{_podium_row(podium_items, theme=ctx.theme)}</div>'
        )
        return (inner, False, None, False)
    elif ctx.asset_style == "bars":
        bar_items = [
            {"num": it["num"], "name": it["name"], "stat": it["stat"], "count": it.get("count", 0)}
            for it in block["items"]
        ]
        inner = (
            _kicker(block["kicker"], WHITE) +
            f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:20pt;color:#fff;margin-bottom:14px;">{_esc(block["title"])}</div>' +
            f'<div style="margin-top:8pt;">{_asset_ranked_bars_html(bar_items, theme=ctx.theme, is_en=is_english(ctx.report))}</div>'
        )
        return (inner, True, None, False)
    else:
        card_items = [(it["num"], it["name"], it["stat"], it["detail"]) for it in block["items"]]
        card_scale = 2.0 if ctx.panel_count == 1 else 1.0
        inner = (
            _kicker(block["kicker"], WHITE) +
            f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:20pt;color:#fff;margin-bottom:18px;">{_esc(block["title"])}</div>' +
            _asset_card_row(card_items, theme=ctx.theme, scale=card_scale)
        )
        return (inner, True, None, False)


def _build_key_findings_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    n_items = len(block["items"])
    # BUG DIPERBAIKI (dilaporkan user — halaman sudah ditengahkan tapi tetap terasa kosong
    # kalau isinya cuma 1-3 temuan singkat): sempat dicoba perbesar jarak ANTAR baris polos
    # (margin-bottom) supaya menyebar mengisi halaman — TERBUKTI SALAH lewat isolasi test
    # WeasyPrint langsung: baris makin renggang memang menaikkan total tinggi konten (jadi
    # SECARA MATEMATIS lebih memenuhi halaman), tapi SECARA VISUAL cuma terlihat spt teks
    # polos mengambang dgn jarak aneh, bukan spt desain yang disengaja. Sekarang tiap temuan
    # dibungkus KARTU ivory berbatas (border-left aksen warna, sama gaya dgn kartu di
    # _build_management_ai_narrative_block/rekomendasi) kalau jumlahnya sedikit (<=3, TANPA
    # chart di sampingnya) — padding lapang di dalam kartu terasa spt ruang yang disengaja,
    # bukan kekosongan tak terjelaskan. n_items>=4 ATAU ada chart pendamping tetap pakai baris
    # polos asli (sudah cukup padat/proporsional, tidak perlu diubah).
    if n_items <= 3 and not block.get("chart"):
        pad_scale = 3.2 if n_items <= 2 else 2.0
        row_scale = 1.5 if n_items <= 2 else 1.2
        cell_htmls = []
        for it in block["items"]:
            color = RED_CRIT if it["is_critical"] else TEXT_DARK
            badge_html = _badge(it["num"], color, size=f"{round(28*row_scale)}px", font_size=f"{11*row_scale:.1f}pt")
            detail_html = (
                f'<div style="font-size:{10*row_scale:.1f}pt;color:{GRAY_TEXT};margin-top:{round(6*row_scale)}px;line-height:1.5;">{_esc(it["detail"])}</div>'
                if it["detail"] else ""
            )
            cell_htmls.append(
                f'<table style="width:100%;margin-bottom:{round(14*pad_scale)}px;background:{IVORY};border:1px solid {PANEL_BORDER};'
                f'border-left:4px solid {color};border-radius:3px;"><tr><td style="vertical-align:top;padding:{round(14*pad_scale)}pt;">'
                f'<table cellpadding="0" cellspacing="0"><tr>'
                f'<td style="width:{round(28*row_scale)+12}px;vertical-align:top;">{badge_html}</td>'
                f'<td style="vertical-align:top;font-weight:700;font-size:{12.5*row_scale:.1f}pt;color:{TEXT_DARK};">{_esc(it["title"])}</td>'
                f'</tr></table>{detail_html}</td></tr></table>'
            )
        findings_html = "".join(cell_htmls)
        inner = _kicker(block["kicker"]) + _title(block["title"]) + findings_html
        return (inner, False, None, False)
    findings_html_parts = [
        _badge_row(it["num"], it["title"], it["detail"], RED_CRIT if it["is_critical"] else TEXT_DARK)
        for it in block["items"]
    ]
    findings_html = "".join(findings_html_parts)
    if block.get("chart"):
        chart_html = _mini_chart_html(block["chart"], ctx)
        body = _main_panel_pair(findings_html, chart_html, 62, ctx.panel_side)
    else:
        body = findings_html
    inner = _kicker(block["kicker"]) + _title(block["title"]) + body
    return (inner, False, None, False)


def _build_recommendations_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    # Timeline (lihat _timeline_html) cocok utk jumlah item sedang (2-6) — kalau
    # lebih banyak, node/label jadi terlalu sempit & kartu grid tetap lebih rapi.
    if ctx.recommendation_style == "timeline" and 2 <= len(block["items"]) <= 6:
        inner = _kicker(block["kicker"]) + _title(block["title"]) + _timeline_html(block["items"], theme=ctx.theme)
    elif ctx.recommendation_style == "banners":
        inner = (
            _kicker(block["kicker"]) + _title(block["title"]) +
            f'<div style="margin-top:8pt;">{_recommendation_banner_list_html(block["items"], theme=ctx.theme)}</div>'
        )
    else:
        # BUG DIPERBAIKI (ditemukan lewat tes kepadatan halaman, permintaan user): badge/
        # font/padding dulu TETAP apa pun jumlah item — solo di 1 halaman penuh dgn 1-3
        # rekomendasi pendek, sisa halaman kosong (sama kelas bug dgn _build_key_findings_
        # block/_build_management_action_items_block, keduanya sudah py mekanisme scale ini).
        n_rec_items = len(block["items"])
        rscale = 1.7 if n_rec_items <= 2 else (1.35 if n_rec_items == 3 else 1.0)
        # Height eksplisit dihapus (lihat catatan di _card_grid) — kartu sepadat
        # kontennya, baris otomatis setinggi kartu terpanjang di baris itu saja.
        cell_htmls = []
        left_colors = []
        for it in block["items"]:
            fg, bg = URGENCY_COLOR.get(it.get("urgency", "low"), (GRAY_TEXT, IVORY))
            left_colors.append(fg)
            detail_html = (
                f'<div style="font-size:{9.5*rscale:.1f}pt;color:{GRAY_TEXT};margin-top:{round(6*rscale)}px;line-height:1.5;">{_esc(it["detail"])}</div>'
                if it["detail"] else ""
            )
            urgency_pill = (
                f'<span style="display:inline-block;padding:{round(2*rscale)}px {round(8*rscale)}px;border-radius:10px;background:{fg};'
                f'color:#fff;font-size:{7*rscale:.1f}pt;font-weight:800;text-transform:uppercase;margin-top:{round(10*rscale)}px;">{_esc(it["urgency"])}</span>'
            ) if it.get("urgency") else ""
            cell_htmls.append(
                f'{_badge(it["num"], fg, size=f"{round(28*rscale)}px")}'
                f'<div style="font-weight:700;font-size:{11*rscale:.1f}pt;color:{TEXT_DARK};margin-top:{round(10*rscale)}px;">{_esc(it["title"])}</div>'
                f'{detail_html}{urgency_pill}'
            )
        # PERMINTAAN USER (E1, "tinggi kartu 1 baris harus seragam"): card_style dipakai (bg/
        # border/radius/padding langsung di <td>, bukan tabel bersarang) — lihat catatan di
        # _card_grid; border_left_colors mempertahankan warna urgency per kartu yang beda2.
        rec_cols = 1 if n_rec_items <= 2 else ctx.card_cols
        card_style = {"bg": IVORY, "border_color": PANEL_BORDER, "radius": 3, "pad_pt": round(14 * rscale), "border_left_colors": left_colors}
        inner = _kicker(block["kicker"]) + _title(block["title"]) + _card_grid(cell_htmls, rec_cols, card_style=card_style)
    return (inner, False, None, False)


def _build_conclusion_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    priority_items = [(p["letter"], p["text"]) for p in block["priority_items"]]
    priority_html = _priority_panel(block["priority_panel_title"], priority_items, theme=ctx.theme) if priority_items else ""
    # PERMINTAAN USER: kolom tunggal (tanpa priority panel di kanan, tidak ada rekomendasi
    # BARU) isinya cuma kicker+judul+1 paragraf+pill — jauh lebih sedikit drpd versi 2 kolom,
    # jadi walau sudah ditengahkan vertikal, sisa ruang atas/bawah masih terasa kosong.
    # Diperbesar (bukan cuma ditengahkan) supaya benar2 mengisi lebih banyak halaman.
    scale = 1.5 if not priority_html else 1.0
    text_pt = round(11 * scale, 1)
    title_pt = round(20 * scale)
    pills_html = "".join(
        f'<div style="background:{ctx.theme["main"]};border:1px solid {ctx.theme["light"]};border-radius:999px;'
        f'padding:{round(10*scale)}px {round(16*scale)}px;text-align:center;font-weight:700;'
        f'font-size:{round(10.5*scale, 1)}pt;color:{ctx.theme["light"]};margin-bottom:{round(10*scale)}px;">'
        f'{_esc(p)}</div>' for p in block["pills"]
    )
    concl_left = (
        f'<div style="font-size:{text_pt}pt;line-height:1.6;color:#E8ECE6;margin-bottom:{round(18*scale)}px;max-width:{"9.5in" if not priority_html else "100%"};">{_esc(block["text"])}</div>'
        f'{pills_html}'
    )
    header_html = (
        _kicker(block["kicker"], WHITE) +
        f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:{title_pt}pt;color:#fff;margin-bottom:{round(16*scale)}px;">{_esc(block["title"])}</div>'
    )
    if priority_html:
        # panel_side cuma dipakai kalau priority_html benar-benar ada isinya — kalau
        # kosong (tidak ada rekomendasi BARU, lihat report_render_logic.py), 2 kolom
        # (58/42) menyisakan kolom kanan kosong — lebih buruk daripada teks lebar penuh.
        inner = header_html + _main_panel_pair(concl_left, priority_html, 58, ctx.panel_side)
    else:
        inner = header_html + concl_left
    return (inner, True, None, False)


def _build_closing_summary_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    """PERMINTAAN USER: Temuan Utama, Rekomendasi, dan Kesimpulan digabung jadi 1 halaman
    kalau ketiganya genuinely tipis (lihat should_combine_closing di report_render_logic.py)
    — drpd 3 halaman terpisah yang masing2 terisi < 1/4 halaman. Temuan & Rekomendasi
    berdampingan (urutan kiri/kanan ikut ctx.panel_side, konsisten dgn panel lain di laporan
    ini), Kesimpulan sbg strip gelap tipis penuh lebar di bawah keduanya."""
    # BUG DIPERBAIKI (permintaan user lanjutan — "Kesimpulan" solo jadi penyumbang kegagalan
    # kepadatan TERBANYAK): halaman ini dulu SELALU asumsi Temuan & Rekomendasi BERDUA ada
    # (2 kolom tetap 50/50) — sekarang salah satu boleh TIDAK ADA (lihat should_combine_
    # closing di report_render_logic.py, kini cukup minimal 2 dari 3 hadir), kolom yang ada
    # melebar penuh drpd dipaksa 50% dgn separuh halaman kosong di sebelahnya.
    findings_col = None
    if block.get("findings_items") is not None:
        findings_html = "".join(
            _badge_row(it["num"], it["title"], it["detail"], RED_CRIT if it["is_critical"] else TEXT_DARK, scale=0.82)
            for it in block["findings_items"]
        )
        findings_col = (
            f'<div style="font-weight:700;font-size:11pt;color:{TEXT_DARK};margin-bottom:10pt;">{_esc(block["findings_title"])}</div>'
            f'{findings_html}'
        )

    rec_col = None
    if block.get("recommendation_items") is not None:
        rec_cards = []
        for it in block["recommendation_items"]:
            fg, _bg = URGENCY_COLOR.get(it.get("urgency", "low"), (GRAY_TEXT, IVORY))
            detail_html = f'<div style="font-size:9pt;color:{GRAY_TEXT};margin-top:4px;">{_esc(it["detail"])}</div>' if it.get("detail") else ""
            urgency_pill = (
                f'<span style="display:inline-block;padding:1px 7px;border-radius:10px;background:{fg};'
                f'color:#fff;font-size:6.5pt;font-weight:800;text-transform:uppercase;margin-top:6px;">{_esc(it["urgency"])}</span>'
            ) if it.get("urgency") else ""
            rec_cards.append(
                f'<div style="margin-bottom:10pt;padding:10pt;background:{IVORY};border:1px solid {PANEL_BORDER};'
                f'border-left:3px solid {fg};border-radius:3px;">'
                f'<div style="font-weight:700;font-size:10pt;color:{TEXT_DARK};">{_esc(it["title"])}</div>'
                f'{detail_html}{urgency_pill}</div>'
            )
        rec_col = (
            f'<div style="font-weight:700;font-size:11pt;color:{TEXT_DARK};margin-bottom:10pt;">{_esc(block["rec_title"])}</div>'
            f'{"".join(rec_cards)}'
        )

    if findings_col is not None and rec_col is not None:
        top_html = _main_panel_pair(findings_col, rec_col, 50, ctx.panel_side)
    else:
        top_html = findings_col or rec_col or ""

    strip_html = ""
    if block.get("conclusion_text"):
        pills_html = "".join(
            f'<td style="padding-right:10pt;"><span style="display:inline-block;background:{ctx.theme["main"]};'
            f'border:1px solid {ctx.theme["light"]};border-radius:999px;padding:6px 14px;font-weight:700;'
            f'font-size:9pt;color:{ctx.theme["light"]};white-space:nowrap;">{_esc(p)}</span></td>'
            for p in (block.get("conclusion_pills") or [])
        )
        pills_row = f'<table cellpadding="0" cellspacing="0"><tr>{pills_html}</tr></table>' if pills_html else ""
        strip_html = (
            f'<table style="width:100%;background:{ctx.theme["bg"]};border:1px solid {ctx.theme["light"]};border-radius:3px;margin-top:20pt;">'
            f'<tr><td style="padding:16pt;">'
            f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:14pt;color:#fff;margin-bottom:8pt;">{_esc(block["conclusion_title"])}</div>'
            f'<div style="font-size:10pt;color:#E8ECE6;line-height:1.5;margin-bottom:{"10pt" if pills_row else "0"};">{_esc(block["conclusion_text"])}</div>'
            f'{pills_row}'
            f'</td></tr></table>'
        )

    inner = _kicker(block["kicker"]) + _title(block["title"]) + top_html + strip_html
    return (inner, False, None, False)


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
    left_colors = []
    for item in items:
        col = color_map.get(item.get("color", "blue"), ctx.accent_main)
        left_colors.append(col)
        delta_html = f'<div style="font-size:{round(9*scale)}pt;font-weight:600;color:{GRAY_TEXT};margin-top:{round(6*scale)}px;">{_esc(item["delta"])}</div>' if item.get("delta") else ""
        # Kartu KPI diperbesar (angka 34pt, dot warna, padding lapang) — identitas "Visual
        # tinggi, KPI ringkas" template ini, beda dgn kartu di SOC Technical Report yang lebih
        # sedang ukurannya krn di sana angka cuma salah satu elemen, bukan sorotan utama.
        cell_htmls.append(
            f'<table cellpadding="0" cellspacing="0"><tr>'
            f'<td style="width:{dot_px}px;height:{dot_px}px;background:{col};border-radius:{round(dot_px/2)}px;font-size:1px;">&nbsp;</td>'
            f'<td style="padding-left:8px;font-size:{label_pt}pt;font-weight:800;text-transform:uppercase;letter-spacing:0.06em;color:{col};">{_esc(item["label"])}</td>'
            f'</tr></table>'
            f'<div style="font-family:{TITLE_FONT};font-size:{value_pt}pt;font-weight:900;color:{col};margin-top:8px;">{_esc(item["value"])}</div>'
            f'{delta_html}'
        )
    # Kolom grid menyesuaikan JUMLAH kartu sungguhan — dulu SELALU 3 kolom apa pun jumlah
    # kartunya, kalau totalnya mis. 4 (bukan kelipatan 3), baris terakhir cuma terisi 1 dari
    # 3 sel (2 sel kosong lebar), halaman jadi terlihat timpang/kurang padat.
    # PERMINTAAN USER (E1, "tinggi kartu 1 baris harus seragam"): card_style dipakai — lihat
    # catatan di _card_grid/_build_recommendations_block.
    card_style = {"bg": IVORY, "border_color": PANEL_BORDER, "radius": 3, "pad_pt": pad_pt, "border_left_colors": left_colors}
    inner = _kicker(block.get("kicker", "")) + _title(block.get("title", "")) + _card_grid(cell_htmls, grid_cols, card_style=card_style)
    return (inner, False, None, False)


def _mgmt_tile_chart_html(tile: dict, ctx: "_PdfBlockContext", compact: bool = False, scale: float | None = None) -> str:
    """Chart KOMPAK per tile dashboard (_build_management_visual_dashboard_block di bawah) —
    ukuran sengaja lebih kecil drpd versi 1-halaman-penuh yang dulu dipakai builder terpisah
    (mis. radar dulu size=300 -> 190, heatmap cell dulu 32 -> 20) supaya 4-6 tile muat
    berdampingan dlm 1 halaman, konsisten dgn permintaan user: laporan "Visual tinggi"
    ditumpuk banyak chart macam-macam dlm 1 halaman, BUKAN 1 chart per halaman.

    `compact=True` (dipakai KHUSUS saat grid dashboard genuinely 2+ baris, lihat pemanggil) —
    BUG DIPERBAIKI (ditemukan lewat isolasi render+bisection langsung di laporan sungguhan,
    report id 165): ukuran "kompak" di atas TERNYATA masih cukup besar sehingga total tinggi
    2 baris tile (ditambah caption yang panjangnya bervariasi dari data/AI) bisa melebihi
    tinggi halaman tetap (7.5in) — bagian yang kelebihan itu diam-diam terpotong oleh
    overflow:hidden di wrapper halaman (lihat _page()), membuat SATU tile (tile mana pun,
    tergantung baris ke-2 punya siapa) terlihat "hilang total" di PDF walau HTML/datanya
    sendiri lengkap & benar. Semua dimensi chart diperkecil lagi ~22% KHUSUS saat compact
    (grid 1 baris tetap ukuran penuh, masih py ruang lapang).

    `scale` (permintaan user B, kolom bertingkat dashboard): override langsung drpd
    `compact`, dipakai _build_management_visual_dashboard_block versi kolom BARU utk
    menyesuaikan ukuran chart ke tinggi kolom yang SUNGGUHAN dihitung _layout_dashboard_
    column (report_render_logic.py) — supaya chart mengisi ruang yang disediakan, bukan
    selalu 1 dari 2 ukuran tetap (compact/tidak) apa pun tinggi kolom sebenarnya."""
    if scale is None:
        scale = 0.74 if compact else 1.0

    def sz(n):
        return round(n * scale)

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
        style = tile.get("chart_style") or (ctx.status_style if is_severity else ctx.category_style)
        if style == "donut":
            d_labels, d_values, d_colors = (
                _merge_tail_into_other(labels, values, colors) if compact else (labels, values, colors)
            )
            return _donut_chart_svg(d_values, colors=d_colors, size=sz(150), stroke_w=sz(24)) + _mini_legend_html(d_labels, d_colors, compact=compact)
        if style == "stacked":
            return _stacked_proportion_bar_html(values, colors=colors, height_px=sz(24), labels=labels)
        if style == "funnel" and is_severity:
            order = sorted(range(len(values)), key=lambda i: -values[i])
            return _funnel_chart_svg([labels[i] for i in order], [values[i] for i in order], color=ctx.accent_main)
        if style == "treemap":
            return _treemap_svg(labels, values, colors=colors, size_w=sz(290), size_h=sz(155))
        return _bar_chart_html(labels, values, colors=colors, compact=compact)
    if kind == "kpi_radar":
        # label_margin dikecilkan (100 -> 55) khusus di sini — di ukuran kompak tile ini,
        # margin default 100px akan bikin r_max negatif (chart rusak), lihat docstring
        # _radar_chart_svg. Diskalakan proporsional dgn size supaya rasio (& amannya r_max>0)
        # tetap terjaga saat compact.
        # BUG DIPERBAIKI (ditemukan lewat tes kepadatan halaman, permintaan user — tile ini
        # SELALU dapat kolom solo yang tumbuh jauh lebih besar dari ukuran dasar, lihat
        # _SPACE_HUNGRY_TILE_KINDS/_build_dashboard_column_html): label_margin dulu ikut
        # scale PENUH sama spt size — teks label sumbu sendiri font-size-nya TETAP (8.5pt,
        # tidak ikut scale), jadi margin tidak PERLU ikut membesar sebesar itu, cuma r_max
        # (cincin yang genuinely terlihat) yang jadi korban krn separuh `size` tetap
        # dialokasikan ke margin yang proporsinya sudah kadung tetap dari skala kompak.
        # Pertumbuhan margin DIBATASI (maks 1.3x dari skala dasar) begitu chart-nya diskalakan
        # jauh lebih besar dari ukuran tile kompak — sisa pembesaran `size` sepenuhnya
        # menambah r_max (cincin terlihat), bukan ruang kosong di sekitar teks label.
        label_scale = min(scale, 1.3)
        return _radar_chart_svg(tile["axes"], tile["values"], color=ctx.accent_main, size=sz(220), label_margin=round(55 * label_scale))
    if kind == "status_funnel":
        return _funnel_chart_svg(tile["categories"], tile["values"], color=ctx.accent_main, size_w=sz(260), size_h=sz(165))
    if kind == "period_compare":
        return _grouped_bar_chart_svg(
            tile["categories"], tile["series_a"], tile["series_b"],
            label_a=tile["label_a"], label_b=tile["label_b"],
            color_a=ctx.accent_main, color_b=ctx.accent_chart, size_w=sz(320), size_h=sz(165),
        )
    if kind == "time_heatmap":
        return _heatmap_grid_svg(tile["day_labels"], tile["hour_labels"], tile["grid"], color=ctx.accent_main, cell=sz(20))
    if kind == "trend_chart":
        chart = tile["chart"]
        if chart["type"] == "bar_line":
            return _bar_line_chart_svg(chart["categories"], chart["values"], chart.get("cumulative"), color=ctx.accent_main, size_w=sz(320), size_h=sz(150))
        return _bar_chart_html(chart["categories"], chart["values"], colors=[ctx.accent_main] * len(chart["values"]), compact=compact)
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
            ct_d_labels, ct_d_values, ct_d_colors = (
                _merge_tail_into_other(labels, values, colors) if compact else (labels, values, colors)
            )
            return _donut_chart_svg(ct_d_values, colors=ct_d_colors, size=sz(150), stroke_w=sz(24)) + _mini_legend_html(ct_d_labels, ct_d_colors, compact=compact)
        if style == "stacked":
            return _stacked_proportion_bar_html(values, colors=colors, height_px=sz(24), labels=labels)
        if style == "treemap":
            return _treemap_svg(labels, values, colors=colors, size_w=sz(290), size_h=sz(155))
        return _bar_chart_html(labels, values, colors=colors, compact=compact)
    if kind == "kpi_gauge":
        # PERMINTAAN USER (tambah jenis visualisasi baru): meteran radial utk 1 angka
        # pencapaian vs target (mis. % top kategori dari total) — lihat
        # build_management_report_blocks utk data aslinya (persentase genuinely dihitung
        # dari top_categories, bukan dikarang).
        return _gauge_svg(tile["pct"], caption=tile.get("caption"), color=ctx.accent_main, size=sz(190))
    if kind == "scatter_bubble":
        # PERMINTAAN USER (tambah jenis visualisasi baru): 2 angka BERBEDA per entitas
        # (lihat data_profiler._compute_category_numeric_pairs) - genuinely beda drpd chart
        # lain yang cuma 1 angka per kategori.
        return _scatter_bubble_svg(
            tile["points"], size_key="count", color=ctx.accent_main, size_w=sz(300), size_h=sz(160),
            x_label=tile.get("x_label", ""),
        )
    return ""


def _fact_strip_kolom_html(pasangan: list, w_in: float) -> str:
    """A8: strip fakta di kolom dashboard - bentuknya IKUT ACUAN & IKUT JUMLAH PASANGAN.

    Satu pasangan -> strip lebar penuh berlatar abu muda. Dua pasangan -> dua kotak kecil
    bersebelahan. Label ITALIC, nilai BOLD. Isi & penyaringnya diputuskan di
    report_render_logic.fakta_strip_kolom (satu aturan, dipakai sisi PPT juga); fungsi ini
    cuma menggambar. Kalau `pasangan` kosong strip TIDAK digambar sama sekali - ruang kosong
    yang jujur lebih baik daripada strip yang mengulang KPI/catatan."""
    if not pasangan:
        return ""
    sel = []
    n = len(pasangan)
    kotak_w = (w_in - 0.08) / n if n > 1 else w_in
    for label, nilai in pasangan:
        sel.append(
            f'<td style="width:{kotak_w}in;background:#F2F4F7;border-radius:3px;'
            f'padding:4pt 7pt;vertical-align:middle;">'
            f'<span style="font-style:italic;font-size:6.5pt;color:{GRAY_TEXT};">{_esc(label)}</span>'
            f'<span style="font-weight:700;font-size:8.5pt;color:{TEXT_DARK};">&nbsp;{_esc(nilai)}</span>'
            f'</td>'
        )
    pemisah = '<td style="width:0.08in;"></td>' if n > 1 else ""
    isi = pemisah.join(sel) if n > 1 else sel[0]
    return (f'<table style="width:100%;border-collapse:separate;" cellpadding="0" '
            f'cellspacing="0"><tr>{isi}</tr></table>')


def _dashboard_title_html(text: str, w_in: float, size_pt: float | None = None,
                          judul_topik: str | None = None) -> tuple:
    """Judul halaman dashboard Management BARU (permintaan user A2): y=0 (lihat negative-
    margin escape-hatch di _build_management_visual_dashboard_block), lebar penuh, TANPA
    kicker terpisah di atasnya (dulu kicker "SOROTAN VISUAL" berulang IDENTIK di 4+ halaman
    dashboard berturut-turut tanpa memberi info apa pun — dihapus total, lihat
    report_render_logic.py::build_management_report_blocks). max-height CSS + overflow:hidden
    jadi jaring pengaman PASTI thd batas 1.12in/2-baris (beda dari export_ppt.py yang punya
    _estimate_wrapped_height_in utk truncate presisi — PDF murni CSS flow, tidak py fungsi
    wrap-estimate yang sama, jadi dipakai perkiraan kasar cuma utk MERENCANAKAN sisa ruang
    kolom di bawahnya; hasil visual akhir tetap PASTI tidak pernah melebihi 1.12in krn CSS
    clip-nya, terlepas dari akurat/tidaknya perkiraan ini)."""
    # BUG DIPERBAIKI (ditemukan lewat verifikasi render langsung): judul "lebar penuh"
    # SEBELUMNYA menembus zona logo pojok kanan-atas (top:0.22in;right:0.3in) — judul yang
    # wrap ke 2 baris terlihat menabrak logo. w_in dipersempit ~2.6in dari kanan (perkiraan
    # lebar zona 3 logo) KHUSUS utk estimasi wrap & lebar div judul, bukan mengubah lebar
    # kolom di bawahnya (yang tetap lebar penuh, mulai di bawah logo).
    # SATU SUMBER: metrik judul (lebar teks, ukuran font final, tinggi kotak) dihitung di
    # report_render_logic.metrik_judul_dashboard supaya sisi PPT memakai angka yang SAMA.
    # Sebelumnya sisi PDF & PPT menghitung sendiri-sendiri dgn font, zona logo, faktor lebar
    # dan minimum yang berbeda - selisih 0.23in mengalir ke tinggi chart & membuat kedua
    # format menggambar JUMLAH ENTITAS yang berbeda (lihat catatan panjang di sumber itu).
    _mj = metrik_judul_dashboard(text, w_in, size_pt)
    text_w_in = _mj["text_w_in"]
    size_pt = _mj["size_pt"]
    height_in = _mj["tinggi_in"]
    # A6: nama topik BOLD warna gelap di depan, sisa kalimat ukuran SAMA tapi TIDAK bold -
    # persis pembagian di slide acuan. Tanpa judul_topik, seluruh teks bold seperti dulu.
    if judul_topik and text.startswith(judul_topik):
        _sisa = text[len(judul_topik):]
        _judul_isi = (f'<span style="font-weight:700;color:{TITLE_TOPIK};">{_esc(judul_topik)}</span>'
                      f'<span style="font-weight:400;">{_esc(_sisa)}</span>')
    else:
        _judul_isi = f'<span style="font-weight:700;">{_esc(text)}</span>' 
    # AKAR MASALAH (dilaporkan user, dibuktikan dari artefak render sendiri): SEBELUM ini
    # kotak judul dipasang `max-height` — artinya tingginya di ALIRAN DOKUMEN masih BOLEH
    # TUMBUH sampai max_h_in kalau teksnya ternyata wrap lebih dari perkiraan, SEMENTARA
    # seluruh isi halaman di bawahnya diposisikan memakai `height_in` (perkiraan 1 baris,
    # dihitung dari tebakan lebar rata-rata karakter). Begitu perkiraan itu meleset walau
    # sedikit (judul wrap jadi 2 baris - TERBUKTI di laporan 176 hal.03: teks hasil render-nya
    # sendiri mengandung ganti baris), tinggi judul + wrapper melewati batas halaman dan
    # WeasyPrint MEMBUANG seluruh isi halaman tanpa exception apa pun.
    #
    # Perbaikan sebelumnya (potong teks ke ~1 baris) cuma menutup SATU PEMICU (judul berisi 2
    # URL panjang) - pemicunya bisa apa saja yang membuat perkiraan lebar karakter meleset
    # (tanda panah "→", karakter lebar, tanda baca, dst), jadi mengejar pemicu satu per satu
    # tidak akan pernah tuntas. Yang diperbaiki di sini AKARNYA: tinggi kotak judul DIKUNCI
    # PERSIS ke `height_in` (bukan lagi `max-height` yang bisa tumbuh), jadi berapa pun baris
    # yang SEBENARNYA dihasilkan WeasyPrint, kotaknya TIDAK PERNAH bisa menggeser apa pun di
    # bawahnya - aritmetika tata letaknya jadi pasti-benar scr konstruksi, tidak lagi
    # bergantung pada akurasi tebakan lebar teks. Kelebihan baris dipotong scr visual
    # (overflow:hidden) - jauh lebih baik daripada kehilangan SELURUH isi halaman.
    html = (
        f'<div style="font-family:{TITLE_FONT};font-size:{size_pt}pt;color:{TEXT_DARK};'
        f'line-height:1.25;height:{height_in}in;max-height:{height_in}in;overflow:hidden;'
        f'width:{text_w_in}in;">{_judul_isi}</div>'
    )
    return html, height_in


def _fact_strip_html(fact_strip: list, theme: dict | None = None) -> str:
    """B: "strip fakta" — 1 baris berisi 2 angka {(label, value)} dipisah "|"."""
    if not fact_strip:
        return ""
    t = theme or THEME_PALETTES["green"]
    parts = []
    for i, (label, value) in enumerate(fact_strip):
        if i > 0:
            parts.append(f'<span style="color:{PANEL_BORDER};font-size:10pt;margin:0 10px;">|</span>')
        parts.append(f'<span style="font-size:14pt;font-weight:700;color:{t["main"]};">{_esc(value)} </span>')
        parts.append(f'<span style="font-size:9pt;color:{GRAY_TEXT};">{_esc(label)}</span>')
    pad_top_pt = round((_DASH_FACT_STRIP_H_IN * 72 - 16) / 2)
    return f'<div style="height:{_DASH_FACT_STRIP_H_IN}in;padding-top:{pad_top_pt}pt;white-space:nowrap;">{"".join(parts)}</div>'


def _fact_pair_html(fact_pair: list, theme: dict | None = None) -> str:
    """B: "kotak fakta berpasangan" — 2 kotak berdampingan, label kecil miring di atas +
    nilai tebal besar di bawah (BUKAN judul berwarna, permintaan user eksplisit)."""
    if not fact_pair:
        return ""
    t = theme or THEME_PALETTES["green"]
    cells = []
    for label, value in fact_pair[:2]:
        cells.append(
            f'<td style="width:50%;background:{IVORY};border:0.75pt solid {PANEL_BORDER};border-radius:3px;'
            f'padding:8pt 10pt;vertical-align:top;">'
            f'<div style="font-size:8.5pt;font-style:italic;color:{GRAY_TEXT};margin-bottom:4pt;">{_esc(label)}</div>'
            f'<div style="font-family:{TITLE_FONT};font-size:16pt;font-weight:700;color:{t["main"]};">{_esc(value)}</div>'
            f'</td>'
        )
    return (
        f'<table style="width:100%;height:{_DASH_FACT_PAIR_H_IN}in;border-collapse:separate;border-spacing:0;" cellpadding="0" cellspacing="0">'
        f'<tr>{cells[0]}<td style="width:12pt;"></td>{cells[1]}</tr></table>'
    )


def _build_dashboard_column_html(tile: dict, ctx: "_PdfBlockContext", col_w_in: float, avail_h_in: float) -> str:
    """1 kolom dashboard Management (permintaan user B, "kolom bertingkat"): pita judul +
    visual utama + (opsional) strip fakta + kotak fakta berpasangan + kotak catatan bernomor,
    tersusun vertikal via CSS flow biasa (BUKAN grid kartu seragam spt sebelumnya). Beda dari
    export_ppt.py (shape diposisikan absolut, WAJIB tahu y tiap blok dulu): di sini blok
    tinggal ditumpuk berurutan, CSS document flow yang mengatur posisi — _layout_dashboard_
    column HANYA dipakai utk menentukan tinggi VISUAL UTAMA (chart-nya sendiri dikontrol
    parameter `scale` eksplisit, lihat _mgmt_tile_chart_html) & kotak catatan tetap dinamis
    dari isi teksnya sendiri (_note_box_html sudah begitu dari dulu, TIDAK dipaksa ke
    estimasi rentang di sini — mirror alasan yang sama dgn versi PPT)."""
    heights = _layout_dashboard_column(tile, avail_h_in)
    gap_pt = round(heights["gap"] * 72)
    parts = [_panel_header_band(tile.get("title", ""), margin_bottom_pt=gap_pt)]
    chart_scale = heights["main_visual"] / _DASH_MAIN_VISUAL_RANGE_IN[1]
    # Chart (radar/gauge/dst — biasanya proporsi PERSEGI) ditengahkan VERTIKAL dlm kotak
    # main_visual (bisa jauh lebih tinggi dari chart-nya sendiri kalau kolom ini sendirian/
    # tanpa fact_strip-pair-notes, lihat _layout_dashboard_column's "tumbuh mengisi sisa
    # ruang") via <table>+vertical-align:middle SUNGGUHAN (bukan flexbox, belum pernah
    # dites aman di file ini) — TABEL DI SINI AMAN krn berada DI DALAM div kolom yang
    # posisinya position:absolute (lihat _build_management_visual_dashboard_block), BUKAN
    # anak langsung dari div bermargin negatif itu sendiri (itu yang TERBUKTI merusak
    # render WeasyPrint, lihat catatan panjang di sana).
    parts.append(
        f'<table style="width:100%;height:{heights["main_visual"]}in;border-collapse:collapse;margin-bottom:{gap_pt}pt;" cellpadding="0" cellspacing="0">'
        f'<tr><td style="height:{heights["main_visual"]}in;vertical-align:middle;text-align:center;overflow:hidden;">'
        f'{_mgmt_tile_chart_html(tile, ctx, scale=chart_scale)}</td></tr></table>'
    )
    if "fact_strip" in heights:
        parts.append(f'<div style="margin-bottom:{gap_pt}pt;">{_fact_strip_html(tile.get("fact_strip"), theme=ctx.theme)}</div>')
    if "fact_pair" in heights:
        parts.append(f'<div style="margin-bottom:{gap_pt}pt;">{_fact_pair_html(tile.get("fact_pair"), theme=ctx.theme)}</div>')
    if "note_box" in heights and tile.get("notes"):
        note_title = "Notes" if is_english(ctx.report) else "Catatan"
        parts.append(_note_box_html(tile["notes"], theme=ctx.theme, title=note_title))
    return "".join(parts)


def _build_management_visual_dashboard_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    """PERMINTAAN USER (B, "kolom bertingkat" — ganti pola grid seragam 'satu kartu satu
    chart'): halaman sekarang 2 kolom (biasanya), tiap kolom = pita judul + visual utama +
    (opsional) strip fakta + kotak fakta berpasangan + kotak catatan bernomor, tersusun
    vertikal — BUKAN grid uniform sampai 6 kartu kecil identik bentuknya spt sebelumnya.
    Geometri halaman (A): TANPA kicker terpisah, judul y=0 lebar penuh maks 1.12in, konten
    kolom mengisi sampai y=7.4in, margin kiri/kanan 0.25in KHUSUS halaman ini — dicapai lewat
    negative-margin "escape hatch" (div pembungkus dgn margin negatif persis sebesar inset
    _page() yang berlaku utk SEMUA halaman lain, 0.5in) supaya konten halaman INI bisa punya
    geometri sendiri TANPA mengubah margin global (_page()) yang dipakai halaman lain."""
    tiles = block.get("tiles", [])
    total_w_in = 13.333 - 2 * _DASH_MARGIN_X_IN
    title_html, title_h_in = _dashboard_title_html(block.get("title", ""), total_w_in)
    if not tiles:
        # BUG DIPERBAIKI (audit F2, defense-in-depth): saudara PPT-nya sudah punya guard
        # eksplisit ini; di sini belum ada sebelumnya.
        return (title_html, False, None, False)
    n_cols = len(tiles)
    col_w_in = (total_w_in - _DASH_COL_GAP_IN * (n_cols - 1)) / n_cols
    avail_h_in = _DASH_CONTENT_BOTTOM_IN - title_h_in
    # BUG DIPERBAIKI (ditemukan lewat isolasi render+sampling langsung, bukan dugaan):
    # <table> utk kolom di dalam div bermargin NEGATIF (escape-hatch geometri halaman ini,
    # lihat `inner` di bawah) TERBUKTI membuat WeasyPrint gagal merender SELURUH isi tabel
    # itu (hilang total tanpa exception apa pun — kelas bug yang sama semangatnya dgn "1 sel
    # hilang total" yang sudah didokumentasikan panjang lebar di _mgmt_tile_chart_html, cuma
    # trigger-nya beda: di sana kombinasi caption+treemap tertentu, di sini margin
    # negatif+table). Kolom SEKARANG diposisikan position:absolute (pola yang SUDAH TERBUKTI
    # aman dipakai luas di file ini, mis. cover/penutup _split_cover_td) drpd <table>.
    col_divs = [
        f'<div style="position:absolute;left:{i * (col_w_in + _DASH_COL_GAP_IN)}in;top:0;width:{col_w_in}in;">'
        f'{_build_dashboard_column_html(t, ctx, col_w_in, avail_h_in)}</div>'
        for i, t in enumerate(tiles)
    ]
    columns_html = f'<div style="position:relative;">{"".join(col_divs)}</div>'
    # Negative-margin escape hatch: _page() membungkus `inner` di <div style="margin:0.5in">
    # (dipakai SEMUA halaman lain) — di sini digeser balik ke (0.25in kiri/kanan, 0in atas)
    # KHUSUS utk halaman ini saja, tanpa menyentuh margin default itu sama sekali.
    inner = f'<div style="margin:-0.5in -0.25in 0 -0.25in;">{title_html}{columns_html}</div>'
    return (inner, False, None, False)


def _insight_kpi_row_html(cards: list, total_w_in: float, h_in: float, y_in: float, theme: dict | None = None) -> str:
    """Lapis ringkasan KPI (permintaan user poin 2/6): kartu lebar TAK SAMA (dari isi
    masing2, lihat _kpi_card_widths), label kecil kapital berspasi + nilai besar tebal
    (BUKAN berwarna — "biarkan angkanya yang menonjol")."""
    if not cards:
        return ""
    t = theme or THEME_PALETTES["green"]
    gap_in = 0.1
    widths = _kpi_card_widths(cards, total_w_in, gap_in)
    parts = []
    x = 0.0
    for card, w in zip(cards, widths):
        # BUG NYATA DIPERBAIKI (terlihat di render halaman dasbor berkolom): ukuran nilai
        # dulu SELALU 20pt, jadi nilai panjang ("CV Surya Elektrik Industri (9)") membungkus
        # ke baris kedua & baris itu TUMPAH KELUAR kartu - kartunya ber-height tetap tanpa
        # overflow guard. Ukuran font sekarang mengecil mengikuti seberapa panjang teksnya
        # thd lebar kartu, & luapan sisa dipotong di dalam kartu, bukan dicetak di luarnya.
        _val = str(card["value"])
        _avail_pt = max(1.0, (w - 32.0 / 72.0) * 72.0)  # lebar dalam, dikurangi padding kiri+kanan
        # faktor 0.56 -> 0.62: terukur dari render, 0.56 masih membiarkan nilai spt
        # "Requests (50%)" membungkus ke baris kedua & TERPOTONG tepi bawah kartu
        # (kasus yang persis dicontohkan user: "(85%)" jatuh di luar rect kartu).
        _size_pt = min(20.0, max(9.5, _avail_pt / (len(_val) * 0.62) if _val else 20.0))
        # A4: latar DAN warna angka berubah menurut NILAINYA - acuan memakai #F4F6F9 netral
        # / #DFF0E6 kalau nilainya baik, dgn angka #1F3864 / #1E7A4D. "Baik" dibaca dari
        # persentase yang tinggi atau kata kunci pencapaian; selain itu netral.
        _kpi_baik = _kpi_nilai_baik(card)
        _kpi_bg = KPI_BG_BAIK if _kpi_baik else KPI_BG_NETRAL
        _kpi_fg = KPI_FG_BAIK if _kpi_baik else KPI_FG_NETRAL
        parts.append(
            f'<div style="position:absolute;left:{x}in;top:{y_in}in;width:{w}in;height:{h_in}in;'
            f'background:{_kpi_bg};border:0.9pt solid {PANEL_BORDER};border-radius:3px;padding:10pt 12pt;'
            f'box-sizing:border-box;overflow:hidden;">'
            f'<div style="font-size:8pt;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:{KPI_LABEL};margin-bottom:6pt;">{_esc(card["label"])}</div>'
            f'<div style="font-family:{TITLE_FONT};font-size:{_size_pt:.1f}pt;font-weight:700;color:{_kpi_fg};line-height:1.15;">{_esc(_val)}</div>'
            f'</div>'
        )
        x += w + gap_in
    return "".join(parts)


# Dikalibrasi dari render PDF (WeasyPrint) - lihat _muat_nama_kartu.
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


def _nested_category_card_html(card: dict, w_in: float, h_in: float, x_in: float, y_in: float, theme: dict | None = None) -> str:
    """Kartu bersarang 1 kategori (permintaan user poin 9): header berwarna (nama + skor
    besar + badge status) + body berisi sub-item pola 2-baris (poin 4: label kiri/nilai
    kanan lalu bar tipis, garis pembanding vertikal di posisi rata-rata — poin 5). Sub-item
    yang tidak muat di tinggi body TERSEDIA (bukan dipaksa mengecil) sengaja dipotong drpd
    dijejalkan sampai tidak terbaca.

    BUG NYATA DIPERBAIKI (permintaan user, koreksi "tidak ada dimensi kedua"): dulu frac/
    target_frac DIHITUNG ULANG di sini dari `it["value"]` thd max HANYA di antara sub-item
    kartu INI SENDIRI — valid selama semua sub-item 1 skala sama (severity/status, cross-tab
    lama). Sekarang sub-item BISA berasal dari kolom numerik BERBEDA-BEDA skalanya (mis.
    Illegal Requests puluhan vs Requests jutaan, lihat _compute_multi_metric_items) - frac/
    target_frac WAJIB sudah dihitung PER METRIK di lapisan data (thd rentang metrik itu di
    SEMUA entitas, bukan cuma yang tampil di kartu ini) & dipakai APA ADANYA di sini, bukan
    diturunkan ulang dari "value" spt sebelumnya (itu akan salah total kalau skalanya beda)."""
    t = theme or THEME_PALETTES["green"]
    # BATASAN USER: "tidak ada teks yang boleh berakhir '…' atau terpotong, di mana pun".
    # Nama kategori dulu dipotong CSS (white-space:nowrap + text-overflow:ellipsis) - terukur
    # 57 teks berakhir elipsis di laporan Visual. Sekarang nama SELALU tampil utuh: ukuran
    # font-nya diturunkan sampai muat, & boleh 2 baris. Tinggi header DIHITUNG dari jumlah
    # baris yang dihasilkan, sebelum kartunya digambar - bukan tinggi tetap yang lalu
    # memotong isinya.
    _nm_pt, _nm_lines = _muat_nama_kartu(str(card.get("name") or ""), w_in)
    _nm_h_in = _nm_lines * (_nm_pt * 1.15 / 72.0)
    header_h_in = max(min(_NESTED_CARD_HEADER_H_IN, h_in * 0.35),
                      min(_NESTED_CARD_HEADER_MIN_H_IN, h_in),
                      min(h_in, 0.22 + _nm_h_in + 0.30))
    body_h_in = max(0.3, h_in - header_h_in)
    sub_items = card.get("sub_items") or []
    item_h_in = _NESTED_CARD_SUBITEM_LINE1_H_IN + _NESTED_CARD_SUBITEM_BAR_H_IN + _NESTED_CARD_SUBITEM_GAP_IN
    # BUG NYATA DIPERBAIKI (sub-item terakhir terlihat TERPOTONG separuh di render):
    # potongan 0.12in tidak sepadan dgn padding body yang sebenarnya (6pt atas +
    # 6pt bawah = 0.167in), jadi kapasitas kelebihan hitung ~1 sub-item & baris
    # terakhir digambar melewati tepi bawah kartu.
    max_items = max(0, int((body_h_in - 0.17) / item_h_in)) if item_h_in else 0
    shown = sub_items[:max_items]
    rows = []
    for it in shown:
        frac = max(0.0, min(1.0, it["frac"]))
        target_frac = it.get("target_frac")
        marker_html = ""
        if target_frac is not None:
            marker_h_pt = _NESTED_CARD_SUBITEM_BAR_H_IN * 72 * 1.4
            extra_pt = (marker_h_pt - _NESTED_CARD_SUBITEM_BAR_H_IN * 72) / 2
            marker_html = (
                f'<div style="position:absolute;left:{max(0.0, min(1.0, target_frac)) * 100:.1f}%;top:-{extra_pt:.1f}pt;'
                f'width:1px;height:{marker_h_pt:.1f}pt;background:{WHITE};"></div>'
            )
        rows.append(
            f'<div style="height:{_NESTED_CARD_SUBITEM_LINE1_H_IN}in;font-size:9pt;color:{WHITE};overflow:hidden;white-space:nowrap;">'
            f'<span style="float:left;">{_esc(it["label"])}</span>'
            f'<span style="float:right;font-weight:700;">{_fmt_num(it["value"])}</span>'
            f'</div>'
            f'<div style="position:relative;height:{_NESTED_CARD_SUBITEM_BAR_H_IN}in;background:rgba(255,255,255,0.2);border-radius:2px;margin-top:2pt;">'
            f'<div style="height:100%;width:{frac * 100:.1f}%;background:{t["light"]};border-radius:2px;"></div>{marker_html}</div>'
            f'<div style="height:{_NESTED_CARD_SUBITEM_GAP_IN}in;"></div>'
        )
    body_content = "".join(rows)
    return (
        f'<div style="position:absolute;left:{x_in}in;top:{y_in}in;width:{w_in}in;height:{h_in}in;'
        f'background:{t["bg"]};border-radius:3px;overflow:hidden;box-sizing:border-box;">'
        f'<div style="height:{header_h_in}in;padding:8pt 10pt;box-sizing:border-box;">'
        f'<div style="font-size:{_nm_pt:.1f}pt;line-height:1.15;font-weight:700;color:{WHITE};">{_esc(card["name"])}</div>'
        f'<div style="font-family:{TITLE_FONT};font-size:16pt;font-weight:700;color:{WHITE};margin-top:2pt;">{_esc(card["score"])}'
        f'<span style="font-size:7.5pt;font-weight:700;background:{t["light"]};color:{t["bg"]};border-radius:8pt;padding:2pt 7pt;margin-left:8pt;">{_esc(card["badge"])}</span></div>'
        f'</div>'
        f'<div style="padding:6pt 10pt;box-sizing:border-box;">{body_content}</div>'
        f'</div>'
    )


def _insight_detail_row_html(cards: list, total_w_in: float, h_in: float, y_in: float, ctx: "_PdfBlockContext", notes: list | None = None) -> str:
    """Lapis detail per kategori (permintaan user poin 9, geometri diukur dari referensi):
    kartu bersarang lebar ~2.24in, jarak nyaris 0, disusun 1 baris (sampai 4) atau 2 baris
    (5-8) lewat _layout_nested_card_grid (report_render_logic.py, SATU sumber dipakai kedua
    exporter). Lebar kartu 2.24in x N nyaris SELALU < lebar halaman kita (kanvas referensi yg
    diukur user py kolom foto dokumentasi di sisa lebarnya, kita tidak) - sisa lebar itu diisi
    panel catatan di SISI KANAN (permintaan user eksplisit "jangan dibiarkan kosong"), BUKAN
    kartu diregangkan atau dibiarkan sbg margin kosong."""
    if not cards:
        return ""
    grid = _layout_nested_card_grid(len(cards), total_w_in)
    rows_n = grid["rows"]
    card_w = grid["card_w"]
    side_panel_w = grid["side_panel_w"]
    gap_in = _NESTED_CARD_GAP_IN
    row_h_in = (h_in - _NESTED_CARD_ROW_GAP_IN * (len(rows_n) - 1)) / len(rows_n) if rows_n else h_in
    parts = []
    idx = 0
    y = y_in
    for row_count in rows_n:
        x = 0.0
        for _ in range(row_count):
            # TIAP KARTU setinggi ISINYA sendiri (dibatasi tinggi baris), bukan diregangkan
            # ke tinggi baris. Rumusnya SATU, dipakai perencana juga - lihat tinggi_kartu_in.
            _kh = min(row_h_in, tinggi_kartu_in(cards[idx]))
            parts.append(_nested_category_card_html(cards[idx], card_w, _kh, x, y, theme=ctx.theme))
            x += card_w + gap_in
            idx += 1
        y += row_h_in + _NESTED_CARD_ROW_GAP_IN
    notes_consumed = False
    if side_panel_w > 0 and notes:
        note_title = "Notes" if is_english(ctx.report) else "Catatan"
        note_html = _note_box_html(notes, theme=ctx.theme, title=note_title)
        panel_x = total_w_in - side_panel_w
        parts.append(
            f'<div style="position:absolute;left:{panel_x}in;top:{y_in}in;width:{side_panel_w}in;'
            f'height:{h_in}in;overflow:hidden;">{note_html}</div>'
        )
        notes_consumed = True
    return "".join(parts), notes_consumed


_CHART_SIDE_PANEL_MIN_W_IN = 2.5


# Padding-top pembungkus chart (10pt di dua cabang, 6pt di cabang catatan-di-bawah).
# Dipotong dari tinggi SEBELUM SVG diskalakan - lihat catatan di _insight_main_chart_html.
_CHART_WRAP_PAD_IN = 10.0 / 72.0


def _insight_main_chart_html(tile: dict, ctx: "_PdfBlockContext", w_in: float, h_in: float, notes: list | None = None, report=None) -> tuple:
    """PERMINTAAN USER ("hapus jalur management_visual_dashboard, semua lewat insight"): tile
    "space-hungry" (kpi_radar/period_compare/time_heatmap, lihat _build_chart_insight_page di
    report_render_logic.py) tidak py daftar entitas utk kartu bersarang - lapis "detail"
    halaman insight-nya diisi CHART ASLI tile itu sendiri, DISKALAKAN LANGSUNG ke ukuran
    w_in/h_in yang tersedia (bukan lewat _mgmt_tile_chart_html yang basisnya "tile kompak
    dashboard grid", ukuran dasarnya jauh lebih kecil dari 1 halaman penuh).

    BUG NYATA DITEMUKAN (verifikasi visual langsung — render PDF sungguhan): kpi_radar itu
    BUJURSANGKAR (dibatasi sisi TERPENDEK dari w_in/h_in) - di halaman lebar (~12.8in) tapi
    "detail" cuma setinggi ~4.8in, chart jadi persegi ~4.4in & MENYISAKAN puluhan persen
    lebar halaman kosong di kiri-kanannya kalau cuma ditengahkan. Sisa lebar itu (kalau cukup
    lapang, >=_CHART_SIDE_PANEL_MIN_W_IN) SEKARANG diisi panel catatan analitis di SISI KANAN
    (pola yang SAMA dgn _insight_detail_row_html utk kartu bersarang) - bukan dibiarkan
    kosong. Return (html, notes_consumed)."""
    kind = tile["tile_kind"]
    # AKAR MASALAH (dilaporkan user "nomor halaman hilang", dibuktikan lewat bisection
    # bertahap): kalau sisa lebar TIDAK cukup utk panel catatan di kanan, fungsi ini dulu
    # mengembalikan notes_consumed=False - pemanggil (_build_management_insight_page_block)
    # lalu merender kotak catatan DI LUAR wrapper tata letak, PADAHAL tinggi wrapper itu
    # SUDAH menghabiskan seluruh jatah halaman. Tinggi kotak catatan tidak pernah ikut
    # dihitung di budget manapun -> halaman melewati batas fisik -> WeasyPrint membuang
    # elemen paling belakang (nomor halaman), dan pada kasus lebih parah seluruh isi halaman.
    # Sekaligus efek buruk kedua: keempat catatan analitis halaman itu TIDAK PERNAH TAMPIL
    # sama sekali (dibuang diam-diam krn panel kanannya tidak muat).
    # Sekarang catatan SELALU dikonsumsi DI DALAM wrapper: kalau tidak muat di kanan,
    # ditaruh DI BAWAH chart dgn chart digambar ulang lebih pendek - tidak ada lagi elemen
    # yang lahir di luar budget tata letak.
    reserve_notes_below = False
    notes_h_in = 0.0
    if notes:
        notes_h_in = min(max(1.0, h_in * 0.3), h_in * 0.45)
    # SATU SUMBER penggambaran chart. Sebelumnya rantai cabang ini DIDUPLIKASI di bawah utk
    # kasus "catatan ditaruh di bawah chart", dan salinan itu cuma menangani 3 jenis lama dgn
    # `else` telanjang yang mengasumsikan heatmap - begitu jenis tile bertambah, tile apa pun
    # yang punya catatan & tidak muat panel sampingnya langsung KeyError 'hour_labels' &
    # SELURUH laporan gagal digenerate (terukur: 11 dari 29 laporan Visual). Sekarang satu
    # definisi dipakai kedua tempat, jadi jenis baru tidak bisa lagi lupa disalin.
    def _gambar_chart(avail_w_px: float, avail_h_px: float):
        chart_w_in = w_in
        if kind == "kpi_radar":
            size = int(min(avail_w_px, avail_h_px) * 0.92)
            label_scale = min(size / 220, 1.3)
            chart_html = _radar_chart_svg(tile["axes"], tile["values"], color=ctx.accent_main, size=size, label_margin=round(55 * label_scale))
            chart_w_in = size / 96
        elif kind == "period_compare":
            size_w = int(avail_w_px * 0.9)
            size_h = int(avail_h_px * 0.85)
            chart_html = _grouped_bar_chart_svg(
                tile["categories"], tile["series_a"], tile["series_b"],
                label_a=tile["label_a"], label_b=tile["label_b"],
                color_a=ctx.accent_main, color_b=ctx.accent_chart, size_w=size_w, size_h=size_h,
            )
            chart_w_in = size_w / 96
        elif kind == "time_heatmap":
            n_cols, n_rows = len(tile["hour_labels"]), len(tile["day_labels"])
            # REGRESI DIPERBAIKI (dilaporkan user: kotak "Minggu" menyentuh tepi bawah halaman &
            # nyaris terpotong): heatmap mengisi HAMPIR SELURUH jatah tingginya (cuma menyisakan
            # 16px) sementara chart lain di fungsi ini menyisakan margin (~0.85 dari jatah). Baris
            # terakhir grid karenanya jatuh persis di zona footer. Disamakan: pakai headroom yang
            # sama supaya baris terakhir selalu berhenti di atas zona footer. Ini TIDAK menambah
            # elemen/tinggi apa pun - cuma menggambar lebih kecil di dalam kotak yang sama.
            cell_w = (avail_w_px - 46) / max(n_cols, 1)
            cell_h = (avail_h_px * 0.85 - 16) / max(n_rows, 1)
            cell = max(16, int(min(cell_w, cell_h)))
            chart_html = _heatmap_grid_svg(tile["day_labels"], tile["hour_labels"], tile["grid"], color=ctx.accent_main, cell=cell)
            chart_w_in = (46 + n_cols * cell) / 96
        # ---- TEMUAN USER (terverifikasi): 6 dari 9 tile_kind di bawah ini SEBELUMNYA jatuh ke
        # `else: return "", False` - chart-nya tidak pernah digambar & halamannya berubah jadi
        # grid kartu. Renderer-nya sudah ada & teruji, cuma tidak pernah dipanggil dari jalur
        # Visual. Bentuk chart mengikuti karakter datanya, bukan dipilih acak. ----
        elif kind == "status_funnel":
            # tahapan berurutan dgn nilai menyusut -> funnel
            size_w = int(avail_w_px * 0.92)
            size_h = int(avail_h_px * 0.88)
            chart_html = _funnel_chart_svg(tile["categories"], tile["values"], color=ctx.accent_main,
                                           size_w=size_w, size_h=size_h)
            chart_w_in = size_w / 96
        elif kind == "kpi_gauge":
            # satu angka pencapaian thd 100% -> gauge
            size = int(min(avail_w_px, avail_h_px) * 0.9)
            chart_html = _gauge_chart_svg(tile.get("pct") or 0, max_value=100,
                                          label=tile.get("gauge_dim") or "", color=ctx.accent_main,
                                          size=size, stroke_w=max(14, int(size * 0.14)))
            chart_w_in = size / 96
        elif kind == "scatter_bubble":
            # dua angka BERBEDA per entitas -> sebaran 2 dimensi
            size_w = int(avail_w_px * 0.92)
            size_h = int(avail_h_px * 0.88)
            chart_html = _scatter_bubble_svg(tile["points"], color=ctx.accent_main,
                                             size_w=size_w, size_h=size_h,
                                             x_label=tile.get("x_label") or "")
            chart_w_in = size_w / 96
        elif kind == "trend_chart":
            _c = tile.get("chart") or {}
            if _c.get("type") == "bar_line" or _c.get("cumulative"):
                # ada deret waktu -> batang per periode + garis kumulatif
                size_w = int(avail_w_px * 0.92)
                size_h = int(avail_h_px * 0.85)
                chart_html = _bar_line_chart_svg(_c.get("categories") or [], _c.get("values") or [],
                                                 _c.get("cumulative"), color=ctx.accent_main,
                                                 size_w=size_w, size_h=size_h)
                chart_w_in = size_w / 96
            else:
                # tidak ada dimensi waktu -> ranked bar, jangan dipaksa jadi garis
                chart_html = _bar_chart_html(_c.get("categories") or [], _c.get("values") or [],
                                             colors=[ctx.accent_main] * len(_c.get("values") or []))
                chart_w_in = w_in
        elif kind == "custom_topic":
            _style = (tile.get("chart_style") or "bar").lower()
            _labels, _values = tile.get("labels") or [], tile.get("values") or []
            if _style == "donut":
                _size = int(min(avail_w_px * 0.62, avail_h_px * 0.92))
                # BUG NYATA DIPERBAIKI (laporan 162 GAGAL digenerate seluruhnya, IndexError):
                # palet dipotong `_ramp[:len(_values)]` - kalau nilainya LEBIH BANYAK dari 5 warna
                # yang tersedia, daftar warnanya jadi lebih pendek dari nilainya & renderer meng-
                # index di luar batas. Paletnya DIPUTAR mengikuti jumlah nilai, bukan dipotong.
                _base = [ctx.accent_main, ctx.accent_chart, ctx.accent_light, ctx.accent_soft, GRAY_TEXT]
                _ramp = [_base[i % len(_base)] for i in range(max(1, len(_values)))]
                chart_html = (
                    f'<table cellpadding="0" cellspacing="0" style="margin:0 auto;"><tr>'
                    f'<td style="vertical-align:middle;">'
                    f'{_donut_chart_svg(_values, colors=_ramp, size=_size, stroke_w=max(18, int(_size * 0.17)))}</td>'
                    f'<td style="vertical-align:middle;padding-left:14px;">'
                    f'{_mini_legend_html(_labels, _ramp)}</td></tr></table>'
                )
                chart_w_in = w_in
            elif _style == "stacked":
                chart_html = _stacked_proportion_bar_html(_values, labels=_labels,
                                                          height_px=max(40, int(avail_h_px * 0.22)),
                                                          w_in=w_in)
                chart_w_in = w_in
            else:
                chart_html = _bar_chart_html(_labels, _values, colors=[ctx.accent_main] * len(_values))
                chart_w_in = w_in
        elif kind == "risk_heatmap":
            _bars = tile.get("bars") or []
            # BUG NYATA (terlihat di render pertama: satu batang KOSONG, sisanya biru/hijau/oranye
            # yang tabrakan dgn palet laporan): field `color` tile ini TOKEN SEMANTIK
            # ("red"/"orange"/"amber"/"blue"/"gray"), bukan nilai warna - dan "amber" bukan nama
            # warna CSS yang sah, jadi batangnya tidak terisi sama sekali. Pemetaannya diambil
            # dari jalur lama (rujukan renderer, BUKAN jalurnya): mode severity memakai warna
            # semantik TETAP supaya makna "kritis" konsisten di tema apa pun; mode kategori
            # diturunkan dari palet tema krn warnanya di situ tidak membawa makna bahaya.
            if tile.get("mode") == "severity":
                _cmap = {"red": RED_CRIT, "orange": "#EA580C", "amber": GOLD_MAIN,
                         "blue": "#2563EB", "gray": GRAY_TEXT}
            else:
                _cmap = {"blue": ctx.accent_main, "green": ctx.accent_chart,
                         "amber": _light_safe(ctx.accent_light), "orange": _light_safe(ctx.accent_soft),
                         "gray": GRAY_TEXT, "red": ctx.accent_main}
            chart_html = _bar_chart_html(
                [b.get("label") for b in _bars], [b.get("count") for b in _bars],
                colors=[_cmap.get(b.get("color", "gray"), ctx.accent_main) for b in _bars])
            chart_w_in = w_in
        elif kind == "metric_share":
            # pangsa satu metrik antar entitas -> treemap (luas = besaran, tanpa masalah skala)
            size_w = int(avail_w_px * 0.94)
            size_h = int(avail_h_px * 0.88)
            _tv = tile.get("values") or []
            _tbase = [ctx.accent_main, ctx.accent_chart, ctx.accent_light, ctx.accent_soft, GRAY_TEXT]
            _ramp_tm = [_tbase[i % len(_tbase)] for i in range(max(1, len(_tv)))]
            chart_html = _treemap_svg(tile.get("labels") or [], _tv,
                                      colors=_ramp_tm,
                                      size_w=size_w, size_h=size_h)
            # keterangan "Lainnya" saat segmennya terlalu tipis utk diberi label DI DALAM
            # chart - dibawa perencana lewat tile["catatan_lainnya"], tidak dihitung ulang
            # di sini. Sisi PDF sering tidak membutuhkannya (kotaknya lebih tinggi drpd
            # PPT), tapi tetap dipasang supaya tidak bergantung pada kebetulan itu.
            if tile.get("catatan_lainnya"):
                # PETAK WARNA cocok dgn segmen terakhir treemap: tanpa itu pembaca melihat
                # satu kotak tanpa nama & satu baris teks yang tidak bisa dipetakan ke kotak
                # mana pun - masalah lama dalam bentuk baru.
                _sw = _ramp_tm[(len(_tv) - 1) % len(_ramp_tm)] if _tv else ctx.accent_main
                chart_html += (f'<div style="font-size:7pt;color:{GRAY_TEXT};margin-top:3pt;'
                               f'text-align:center;">'
                               f'<span style="display:inline-block;width:7px;height:7px;'
                               f'background:{_sw};border-radius:1px;margin-right:4px;"></span>'
                               f'{_esc(tile["catatan_lainnya"])}</div>')
            chart_w_in = size_w / 96
        elif kind == "metric_mix":
            # komposisi antar metrik -> proporsi, jujur meski skalanya beda jauh
            chart_html = _stacked_proportion_bar_html(tile.get("values") or [],
                                                      labels=tile.get("labels") or [],
                                                      height_px=max(44, int(avail_h_px * 0.24)),
                                                      w_in=w_in)
            # BUG NYATA DIPERBAIKI: planner (report_render_logic) sudah menghitung & menaruh
            # tile["catatan_lainnya"] saat segmen "Lainnya" sendiri terlalu tipis utk diberi
            # label DI ATAS batang (kembaran mekanisme metric_share di atas) - tapi cabang ini
            # TIDAK PERNAH membacanya, jadi keterangannya dibuang diam2 & label itu hilang
            # tanpa jejak sama sekali. Kotak warna dicocokkan dgn WARNA segmen terakhir.
            if tile.get("catatan_lainnya"):
                # _stacked_proportion_bar_html TIDAK diberi `colors` di jalur ini (dipanggil
                # tanpa param itu di atas), jadi ia jatuh ke CATEGORY_COLOR_RAMP internal
                # sendiri - warna petak di sini HARUS mengikuti fallback yang SAMA, bukan
                # `colors` yang tidak ada di scope ini.
                _mm_v = tile.get("values") or []
                _mm_c = CATEGORY_COLOR_RAMP[(len(_mm_v) - 1) % len(CATEGORY_COLOR_RAMP)] if _mm_v else GRAY_TEXT
                chart_html += (f'<div style="font-size:7pt;color:{GRAY_TEXT};margin-top:3pt;'
                               f'text-align:left;">'
                               f'<span style="display:inline-block;width:7px;height:7px;'
                               f'background:{_mm_c};border-radius:1px;margin-right:4px;"></span>'
                               f'{_esc(tile["catatan_lainnya"])}</div>')
            chart_w_in = w_in
        elif kind == "metric_compare":
            size_w = int(avail_w_px * 0.9)
            size_h = int(avail_h_px * 0.85)
            chart_html = _grouped_bar_chart_svg(
                tile["categories"], tile["series_a"], tile["series_b"],
                label_a=tile.get("label_a", ""), label_b=tile.get("label_b", ""),
                color_a=ctx.accent_main, color_b=ctx.accent_chart, size_w=size_w, size_h=size_h,
            )
            chart_w_in = size_w / 96
        elif kind == "ranked_bar_ternormalisasi":
            # panjang batang relatif thd maksimum deretnya sendiri; nilai ASLI di ujung batang.
            # Kaki legenda sudah masuk chart_min_mutlak_in, jadi kalau sampai di sini dia MUAT.
            chart_html = _ranked_bar_ternorm_html(tile.get("labels") or [], tile.get("values") or [],
                                                  color=ctx.accent_main, is_en=is_english(report))
            chart_w_in = w_in
        elif kind == "grouped_bar_ternormalisasi":
            chart_html = _grouped_bar_ternorm_html(
                tile.get("categories") or [], tile.get("series_a") or [], tile.get("series_b") or [],
                label_a=tile.get("label_a", ""), label_b=tile.get("label_b", ""),
                color_a=ctx.accent_main, color_b=ctx.accent_chart, is_en=is_english(report))
            chart_w_in = w_in
        else:
            # KEPUTUSAN EKSPLISIT, bukan fallback diam: tile_kind yang tidak dikenali TIDAK
            # digambar - tapi dicatat, supaya jenis tile baru yang lupa diberi cabang ketahuan
            # dari log & bukan menghilang tanpa jejak (persis yang terjadi selama ini pada 6
            # tile_kind di atas). Semua tile_kind yang ada saat ini sudah punya cabang.
            logger.warning("tile_kind %r tidak punya cabang chart di _insight_main_chart_html - "
                           "chart tidak digambar", kind)
            return "", False
        return chart_html, chart_w_in

    # SVG DIUKUR DARI (TINGGI KOTAK - PADDING PEMBUNGKUS), bukan dari tinggi kotak penuh.
    # Ketiga pembungkus di bawah memasang padding-top (10pt/10pt/6pt); kalau SVG diskalakan
    # dari h_in penuh, ia digambar setinggi ~0.92*h_in lalu DIDORONG TURUN oleh padding
    # sehingga tepi bawahnya melewati kotak. Itulah sebabnya luberannya tidak pernah hilang
    # meski tinggi minimum dinaikkan: 1.45->1.59->1.70->1.80 tanpa henti. Sekarang padding
    # dipotong DULU, jadi kebutuhan <= jatah dan angkanya konvergen.
    chart_html, chart_w_in = _gambar_chart(w_in * 96, max(0.2, h_in - _CHART_WRAP_PAD_IN) * 96)
    if not chart_html:
        return "", False
    avail_w_px, avail_h_px = w_in * 96, h_in * 96
    side_panel_w = w_in - chart_w_in - 0.3
    if side_panel_w >= _CHART_SIDE_PANEL_MIN_W_IN and notes:
        note_title = "Notes" if is_english(report) else "Catatan"
        note_html = _note_box_html(notes, theme=ctx.theme, title=note_title)
        html = (
            f'<div style="position:relative;height:{h_in}in;">'
            f'<div style="position:absolute;left:0;top:0;width:{chart_w_in + 0.3}in;height:{h_in}in;'
            f'box-sizing:border-box;text-align:center;padding-top:10pt;">{chart_html}</div>'
            f'<div style="position:absolute;left:{chart_w_in + 0.3}in;top:0;width:{side_panel_w}in;height:{h_in}in;overflow:hidden;">{note_html}</div>'
            f'</div>'
        )
        return html, True
    # Panel kanan tidak muat. Kalau ADA catatan, catatan ditaruh DI BAWAH chart TAPI TETAP DI
    # DALAM wrapper ber-tinggi-tetap ini (lihat catatan akar masalah di awal fungsi) - chart
    # digambar ULANG lebih pendek supaya keduanya muat tanpa terpotong, dan pemanggil TIDAK
    # perlu lagi merender kotak catatan di luar budget tata letak.
    if notes:
        reserve_notes_below = True
        chart_h_in = max(1.0, h_in - notes_h_in)
        inner_h_px = max(0.2, chart_h_in - _CHART_WRAP_PAD_IN) * 96
        # digambar ULANG lebih pendek lewat fungsi yang SAMA - bukan salinan rantai cabang
        chart_html, _ = _gambar_chart(avail_w_px, inner_h_px)
        note_title = "Notes" if is_english(report) else "Catatan"
        note_html = _note_box_html(notes, theme=ctx.theme, title=note_title)
        html = (
            f'<div style="position:relative;height:{h_in}in;">'
            # overflow:hidden SENGAJA TIDAK DIPASANG di pembungkus chart (aturan tetap: memotong
            # diam-diam lebih buruk drpd terlihat meluber). Chart-nya sudah digambar ULANG dgn
            # tinggi chart_h_in di atas, jadi kalau ia masih meluber itu cacat perhitungan yang
            # HARUS kelihatan di uji tumpang-tindih & uji elemen-di-luar-slide, bukan disembunyikan.
            f'<div style="position:absolute;left:0;top:0;width:{w_in}in;height:{chart_h_in}in;'
            f'box-sizing:border-box;text-align:center;padding-top:6pt;">{chart_html}</div>'
            f'<div style="position:absolute;left:0;top:{chart_h_in}in;width:{w_in}in;'
            f'height:{h_in - chart_h_in}in;overflow:hidden;">{note_html}</div>'
            f'</div>'
        )
        return html, True
    return (
        # AKAR NON-KONVERGENSI (terukur, bukan dugaan): tanpa box-sizing:border-box,
        # `padding-top` DITAMBAHKAN DI LUAR `height`, jadi tinggi nyata elemen selalu
        # h_in + 10pt (0.139in) berapa pun h_in-nya. Itulah sebabnya menaikkan tinggi
        # minimum tidak pernah menyelesaikan luberan: 1.45->1.59->1.70->1.80 tanpa henti.
        # Bukan rumus SVG yang salah & bukan konstanta yang kurang - padding yang jatuh di
        # luar kotak. border-box memasukkannya ke dalam tinggi yang sudah dipesan.
        f'<div style="position:relative;height:{h_in}in;box-sizing:border-box;'
        f'text-align:center;padding-top:10pt;">{chart_html}</div>'
    ), False


def _build_management_insight_page_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    """PERMINTAAN USER ("Tata letak — ini yang menentukan kepadatan, bukan margin saja"):
    ganti TOTAL halaman dashboard grid ("N kolom, tiap kolom 1 topik") jadi "1 halaman = 1
    pembahasan mendalam" — lapis fungsi dari atas: judul -> ringkasan KPI (3 kartu lebar
    tak-sama) -> detail per kategori (sampai 4 kartu bersarang) -> catatan. Lapis yang
    datanya kosong dilewati & sisanya diperbesar mengisi halaman (lihat
    _layout_insight_layers, report_render_logic.py — SATU sumber dipakai kedua exporter).
    Geometri halaman (margin 0.25in, judul y=0) SAMA PERSIS dgn _build_management_visual_
    dashboard_block via negative-margin escape hatch yang sama."""
    total_w_in = 13.333 - 2 * _DASH_MARGIN_X_IN
    title_html, title_h_in = _dashboard_title_html(block.get("title", ""), total_w_in)
    avail_h_in = _DASH_CONTENT_BOTTOM_IN - title_h_in
    layers = _layout_insight_layers(block, avail_h_in, total_w_in)

    # BUG NYATA DITEMUKAN (verifikasi visual langsung — render PDF sungguhan jadi halaman
    # KOSONG total): `gap` ditambahkan ke cur_y_in SETELAH TIAP lapis termasuk lapis TERAKHIR
    # ("detail") — padahal tidak ada apa pun SETELAH lapis terakhir di DALAM wrapper ini
    # (catatan/notes_html dirender TERPISAH di luar wrapper, lihat di bawah). Gap "ekstra" di
    # ujung itu SIA-SIA nambah tinggi wrapper tanpa alasan — dulu nyaris tak kelihatan efeknya
    # (gap lama tetap ~0.2in), tapi sekarang `gap` bisa tumbuh sampai 0.6in (lihat
    # _layout_insight_layers) - tinggi wrapper jadi OVER-ESTIMATE sampai +0.6in, cukup utk
    # mendorong total (judul + wrapper) lewat batas halaman & WeasyPrint gagal me-render
    # konten itu sama sekali (halaman kosong, tanpa exception apa pun). Gap HANYA ditambahkan
    # DI ANTARA lapis (bukan setelah lapis terakhir).
    parts = []
    cur_y_in = 0.0
    notes_consumed = False
    if "kpi" in layers:
        parts.append(_insight_kpi_row_html(block["kpi_summary"], total_w_in, layers["kpi"], cur_y_in, theme=ctx.theme))
        cur_y_in += layers["kpi"]
        if "detail" in layers:
            cur_y_in += layers["gap"]
    if "detail" in layers:
        if block.get("main_chart_tile"):
            chart_inner_html, notes_consumed = _insight_main_chart_html(
                block["main_chart_tile"], ctx, total_w_in, layers["detail"], notes=block.get("notes"), report=ctx.report,
            )
            detail_html = (
                f'<div style="position:absolute;left:0;top:{cur_y_in}in;width:{total_w_in}in;'
                f'height:{layers["detail"]}in;">{chart_inner_html}</div>'
            )
        else:
            detail_html, notes_consumed = _insight_detail_row_html(
                block["category_details"], total_w_in, layers["detail"], cur_y_in, ctx, notes=block.get("notes"),
            )
        parts.append(detail_html)
        cur_y_in += layers["detail"]
    absolute_layers_html = f'<div style="position:relative;height:{cur_y_in}in;">{"".join(parts)}</div>'

    notes_html = ""
    if block.get("notes") and not notes_consumed:
        note_title = "Notes" if is_english(ctx.report) else "Catatan"
        notes_html = _note_box_html(block["notes"], theme=ctx.theme, title=note_title)

    inner = f'<div style="margin:-0.5in -0.25in 0 -0.25in;">{title_html}{absolute_layers_html}{notes_html}</div>'
    return (inner, False, None, False)


# A1: PANEL MENEMPEL. Di slide acuan keempat panel berbagi tepi persis (x=0.16/2.40/4.64/
# 6.89, masing-masing w=2.24) - nol jarak. Yang membentuk sekat adalah GARIS TEPI #D6DBE3
# yang bersentuhan, bukan ruang kosong. Sebelumnya 0.28in.
_DASH_COLS_GAP_IN = 0.0
# PITA kepala, bukan kotak judul: acuan 0.16in, dipakai 0.20in supaya judul 8.5pt tetap
# muat satu baris. Sebelumnya 0.52in - tiga kali tinggi yang diperlukan.
_DASH_COLS_TITLE_H_IN = 0.20
_DASH_COLS_KPI_H_IN = 0.95


def _build_management_dashboard_columns_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    """PERMINTAAN USER (perombakan kepadatan): berhenti membuat SATU halaman utk SATU visual.
    Beberapa topik dikemas jadi KOLOM SEJAJAR di satu halaman - tiap kolom membawa blok
    lengkapnya sendiri (judul topik -> strip KPI ringkas -> visual/kartu -> catatan), meniru
    cara laporan referensi menaruh beberapa topik berbeda di satu halaman.

    Dibangun dgn MEMAKAI ULANG helper yang sama persis dgn halaman insight 1-topik (semuanya
    sudah menerima x/lebar/tinggi eksplisit) - jadi tidak ada jalur render baru yang perlu
    dijaga terpisah, cuma penempatannya yang berbeda. Tinggi tiap lapis DIHITUNG & DIKUNCI di
    sini (pola sama dgn perbaikan akar Prioritas 1): tidak ada elemen yang tingginya lahir di
    luar anggaran halaman."""
    cols = [c for c in (block.get("columns") or []) if c]
    # kolom yang tile-nya DILEWATI dibuang seluruhnya, sebelum lebar kolom dihitung - supaya
    # sisanya melebar mengisi halaman, bukan menyisakan kolom yatim berisi header + 2 kartu.
    cols = kolom_yang_digambar(cols, 13.333 - 2 * _DASH_MARGIN_X_IN, _DASH_COLS_GAP_IN,
                               _DASH_CONTENT_BOTTOM_IN - _DASH_COLS_TITLE_H_IN
                               - _DASH_COLS_KPI_H_IN - 0.10)
    if not cols:
        return ("", False, None, False)
    total_w_in = 13.333 - 2 * _DASH_MARGIN_X_IN
    title_html, title_h_in = _dashboard_title_html(block.get("title", ""), total_w_in)
    avail_h_in = _DASH_CONTENT_BOTTOM_IN - title_h_in

    # ---- PENUMPUKAN TILE: satu kolom memuat BEBERAPA seksi ----------------------------
    # `bentuk_kolom` dari perencana menyebut berapa seksi yang ditumpuk di tiap kolom visual,
    # mis. [2, 1, 1]. `cols` tetap daftar DATAR; di sini dikelompokkan jadi slot vertikal.
    # Kalau bentuknya tidak lagi cocok dgn jumlah kolom (mis. kolom_yang_digambar membuang
    # kolom yang tile-nya dilewati), jatuh balik ke satu seksi per kolom - bukan menebak.
    _bentuk = list(block.get("bentuk_kolom") or [])
    if sum(_bentuk) != len(cols):
        _bentuk = [1] * len(cols)
    n = max(1, len(_bentuk))
    col_w = (total_w_in - _DASH_COLS_GAP_IN * (n - 1)) / n
    parts = []
    _y_terendah = 0.0
    # ---- A5: RUANG KOTAK CATATAN DIPESAN LEBIH DULU -------------------------------------
    # Aturan tetap: tinggi yang bergantung isi harus bisa dihitung SEBELUM penempatan.
    # Sebelumnya kolom diberi SELURUH tinggi lalu kotak catatan dicari ruang sisa - hasilnya
    # nol ruang & kotaknya tidak pernah tergambar (terukur: 188/hal2 0% catatan padahal
    # kolomnya menghasilkan 4 & 2 butir).
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
    _maks_note_in = tinggi_maks_kotak_catatan(
        cols, col_w, avail_h_in - _DASH_COLS_KEPALA_H_IN, is_english(ctx.report))
    _NOTE_HAL_H_IN, _butir_note, _note_tak_muat = tinggi_kotak_catatan_halaman(
        total_w_in, _catatan_per_kolom, _maks_note_in)
    logger.info("kotak catatan halaman: %d butir muat (kotak %.2fin, batas %.2fin), "
                "%d tidak muat, dari %d kolom bercatatan",
                len(_butir_note), _NOTE_HAL_H_IN, _maks_note_in, _note_tak_muat,
                len(_catatan_per_kolom))
    avail_h_in = avail_h_in - _NOTE_HAL_H_IN
    # ---- SLOT DIBANGUN SETELAH avail_h_in DIKURANGI catatan (URUTAN DIPERBAIKI) ---------
    # BUG NYATA (ditemukan lewat pengukuran, dilaporkan sbg dugaan lalu dibuktikan): versi
    # pertama penumpukan membangun _slot dari avail_h_in SEBELUM kotak catatan mengurangi
    # jatahnya - setiap slot (termasuk _bawah_seksi tile ke-2/3 dalam satu kolom bertumpuk)
    # jadi TERLALU BESAR persis sebesar _NOTE_HAL_H_IN (terukur report 188: stale 6.289in vs
    # benar 5.269in, selisih 1.020in = NOTE_H persis). Utk kolom SATU tile ini tidak
    # kelihatan (chart bentuk tetap cuma dpt ruang kosong ekstra di bawahnya, tidak overlap
    # apa pun) - itulah sebabnya 182/184/187/188 (semua satu tile/kolom) tidak pernah gagal
    # uji tumpang tindih. Tapi utk kolom BERTUMPUK, tile KEDUA diposisikan mulai di
    # `_bagi + gap` yang staleness itu ikut membesar - tile kedua mulai ~1in lebih rendah
    # dari seharusnya & bertindih kotak catatan yang diposisikan dari avail_h_in yang BENAR.
    # ---- ALOKASI PROPORSIONAL, BUKAN RATA (koreksi user atas equal-split) ---------------
    # BUG NYATA: _bagi dulu SAMA utk semua seksi bertumpuk dalam satu kolom (avail/n) -
    # padahal perencana (_pack_tiles_into_columns) memutuskan kolom "muat" dgn MENJUMLAHKAN
    # kebutuhan tiap seksi (bisa tidak sama besar). Seksi yg kebutuhannya di atas rata-rata
    # jatah dapat KURANG dari minimumnya sendiri & di-drop, walau totalnya muat dlm budget
    # kolom. Terukur laporan 190: risk_heatmap 2.17in + kpi_radar 2.68in = 4.95in (muat dlm
    # 5.26in), tapi dibagi rata 2.58in/2.58in - kpi_radar kurang 0.10in & didrop SELURUHNYA,
    # bahkan menghapus satu topik total dari laporan (test_management_reports_render_
    # every_tile_in_both_formats, laporan 189/190).
    #
    # alokasi_kolom_bertumpuk (report_render_logic, SATU fungsi dipakai planner & KEDUA
    # exporter) menghitung ulang: tiap seksi dijamin kebutuhannya, sisa dibagi lewat ANTREAN
    # [chart_1, kartu_1, chart_2, kartu_2, ...] - bukan rata, bukan pemenang-ambil-semua.
    _slot, _pos, _alokasi = [], 0, {}
    for _ki, _cnt in enumerate(_bentuk):
        _seksi = cols[_pos:_pos + _cnt]
        _pos += _cnt
        if not _seksi:
            continue
        _hasil_kol = alokasi_kolom_bertumpuk(_seksi, col_w, avail_h_in, is_english(ctx.report))
        _y = 0.0
        for _c, _h in zip(_seksi, _hasil_kol):
            _kepala_c = _kepala_seksi_h_in(_c, col_w)
            _footprint = _kepala_c + _h["chart_h"] + (0.10 + _h["cards_h"] if _h["cards"] else 0.0)
            _slot.append((_ki, _c, _y, _y + _footprint))
            _alokasi[id(_c)] = _h
            _y += _footprint + _DASH_TILE_GAP_IN
    for idx, (_kol_i, col, _y_awal, _bawah_seksi) in enumerate(_slot):
        x = _kol_i * (col_w + _DASH_COLS_GAP_IN)
        y = _y_awal
        col_parts = []

        # BATASAN USER: judul kolom TIDAK dipotong. Ukurannya dikecilkan sampai muat 2 baris.
        col_title = str(col.get("title") or "")
        _ct_pt = 10.5
        for _p in (10.5, 9.5, 8.5, 7.5):
            if len(col_title) <= 2 * max(12, int(col_w * 96 / (_p * 0.62))):
                _ct_pt = _p
                break
        else:
            _ct_pt = 7.5
        # ---- A2: BADAN PANEL putih bergaris, digambar lebih dulu sbg alas -------------
        # Acuan: badan w=2.24 h=2.95 fill #FFFFFF line #D6DBE3 0.75pt, dgn pita kepala
        # bertumpuk di posisi yang sama. Panel bersebelahan berbagi tepi (A1), jadi garis
        # inilah yang membentuk sekat antar kolom.
        col_parts.append(
            f'<div style="position:absolute;left:{x}in;top:{y}in;width:{col_w}in;'
            f'height:{_bawah_seksi - (y - title_h_in) - 0.02}in;background:{WHITE};'
            f'border:0.75pt solid {PANEL_BORDER};border-radius:2px;"></div>'
        )

        # ---- A1 + A4: PITA KEPALA, bukan kotak judul setinggi 0.52in ------------------
        # Slide acuan memakai pita kepala berwarna ~0.20in yang memuat judul panel, DAN pita
        # kedua sebaris berisi CARA MEMBACA chart di bawahnya. 188 memakai kotak 0.52in
        # berisi nama saja - tiga kali tinggi yang perlu, tanpa penjelasan.
        # Sekat di acuan adalah GARIS TEPI (141/141 shape bergaris, nol shadow), jadi seluruh
        # panel di bawah ini dibungkus kartu bergaris.
        _cara_baca = str(col.get("cara_baca") or "")
        _judul_w = col_w
        # BATASAN TETAP: judul TIDAK dipotong. Fontnya yang mengecil sampai muat, dan kalau
        # pada batas bawah acuan (5.5pt) masih belum muat satu baris, PITANYA yang ditinggikan.
        # overflow:hidden di sini SEMPAT memotong judul panjang diam-diam - tertangkap uji
        # paritas ("PDF tidak menemukan [checked_topic] 'Analysis of Blocked Spam by Section'").
        _w_judul_px = max(40.0, (_judul_w - 0.12) * 96)
        _jp, _jbaris = 8.5, 1
        for _p in (8.5, 8.0, 7.5, 7.0, 6.5, 6.0, 5.5):
            _jp = _p
            _jbaris = wrap_line_count(col_title, _w_judul_px, _p, 0.80)
            if _jbaris <= 1:
                break
        _pita_h = max(_DASH_COLS_TITLE_H_IN, _jbaris * (_jp * 1.25 / 72.0) + 0.06)
        col_parts.append(
            f'<div style="position:absolute;left:{x}in;top:{y}in;width:{col_w}in;'
            f'height:{_pita_h}in;background:{ctx.accent_main};'
            f'border:0.5pt solid {ctx.accent_main};border-radius:2px;"></div>'
            f'<div style="position:absolute;left:{x + 0.06}in;top:{y + 0.02}in;'
            f'width:{_judul_w - 0.12}in;'
            f'font-family:{TITLE_FONT};font-size:{_jp}pt;'
            f'font-weight:700;color:{WHITE};line-height:1.25;">{_esc(col_title)}</div>'
        )
        y += _pita_h
        if _cara_baca:
            # A3: keterangan cara-baca ITALIC ABU di latar transparan, SEJAJAR di bawah pita
            # judul - bukan teks putih di dalam pita berwarna. Pita berwarna itu KEPALA PANEL
            # (A2); keterangan cara membaca di acuan justru italic abu tanpa latar.
            col_parts.append(
                f'<div style="position:absolute;left:{x + 0.06}in;top:{y + 0.01}in;'
                f'width:{col_w - 0.12}in;height:0.16in;'
                f'font-size:6.5pt;font-style:italic;color:{GRAY_TEXT};'
                f'line-height:1.15;">{_esc(_cara_baca)}</div>'
            )
            y += 0.18
        y += 0.04

        kpi = (col.get("kpi_summary") or [])[:2]
        if kpi:
            # _insight_kpi_row_html TIDAK punya parameter x (dibuat utk halaman 1-topik lebar
            # penuh, selalu menggambar mulai x=0) - dibungkus container ber-posisi supaya tiap
            # kolom benar-benar jatuh di kolomnya sendiri. Tanpa ini ketiga kolom menimpa di
            # kiri (terlihat langsung waktu render diperiksa).
            col_parts.append(
                f'<div style="position:absolute;left:{x}in;top:{y}in;width:{col_w}in;'
                f'height:{_DASH_COLS_KPI_H_IN}in;">'
                f'<div style="position:relative;height:{_DASH_COLS_KPI_H_IN}in;">'
                f'{_insight_kpi_row_html(kpi, col_w, _DASH_COLS_KPI_H_IN, 0.0, theme=ctx.theme)}'
                f'</div></div>'
            )
            y += _DASH_COLS_KPI_H_IN + 0.10


        body_h = max(1.2, _bawah_seksi - y - 0.10)
        notes = [str(x_) for x_ in (col.get("notes") or []) if str(x_).strip()]
        notes_consumed = False
        # PERMINTAAN USER (bagian 2): chart & kartu JANGAN saling meniadakan. Dulu pilihannya
        # biner - chart penuh ATAU grid kartu - sehingga begitu tile mulai membawa chart
        # (bagian 1), kartunya hilang & kepadatan halaman justru TURUN. Satu kolom sekarang
        # memuat chart di ATAS + kartu ringkas di BAWAH. Porsinya dipesan lebih dulu, jadi
        # tinggi kartu dihitung dari sisa yang benar-benar tersedia, bukan dari seluruh kolom.
        _tile = col.get("main_chart_tile")
        _has_cards = bool(col.get("category_details"))
        # Catatan TIDAK lagi dipesan per kolom (A5: satu kotak selebar halaman), jadi
        # perencana diberi has_notes=False & seluruh tinggi kolom dipakai isi.
        _dasar_kolom = y
        # SUDAH dihitung sekali oleh alokasi_kolom_bertumpuk di atas (bukan dihitung ulang
        # di sini) - _layout_dashboard_column_content dgn body_h gabungan akan memicu lagi
        # "langkah 3" internalnya & menggembungkan chart_h memakai ruang yg SUDAH dijatahkan
        # ke kartu oleh alokasi_kolom_bertumpuk (bug nyata yg sama persis ditemukan &
        # diperbaiki di dalam fungsi itu sendiri).
        _column_layout = _alokasi.get(id(col)) or _layout_dashboard_column_content(
            body_h, col_w, bool(_tile), col.get("category_details"), False, _tile,
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
        if _tile:
            # A5: catatan TIDAK lagi diserap chart per kolom - semuanya dikumpulkan ke SATU
            # kotak selebar halaman di dasar (lihat akhir fungsi). Dua jalur menggambar
            # catatan yang sama membuat kotaknya bertumpuk (terukur: uji tumpang-tindih
            # menemukan dua "CATATAN:" persis bertindih di laporan 186/187/189).
            inner, _nc = _insight_main_chart_html(
                _tile, ctx, col_w, _chart_h, notes=None, report=ctx.report,
            )
            if inner:
        # PERMINTAAN USER: overflow:hidden DIBUANG dari pembungkus chart. Ia memotong TANPA
        # penanda apa pun - pembaca melihat treemap 2 label & mengira memang cuma ada 2
        # entitas (terukur: 182 metric_share 4 dari 6 label hilang, 184 custom_topic 5 dari
        # 8). Lebih buruk dari elipsis, dan menyembunyikan salah-hitung tinggi dari tes
        # maupun dari kita. Tanpa ini, salah hitung akan TERLIHAT (menonjol/menimpa) &
        # tertangkap tes tumpang tindih level span.
                col_parts.append(
                    f'<div style="position:absolute;left:{x}in;top:{y}in;width:{col_w}in;'
                    f'height:{_chart_h}in;">{inner}</div>'
                )
                if _has_cards:
                    y += _chart_h + 0.10
                    body_h = max(1.0, _bawah_seksi - y - 0.10)
            elif _has_cards:
                # chart tidak jadi digambar -> kartu memakai kembali seluruh tinggi kolom
                _chart_h = 0.0
        if not _tile or (_has_cards and _chart_h >= 0.0):
            cards = _column_layout["cards"]
            if cards:
                # Tinggi kartu DIBATASI ke kebutuhan isinya, bukan diregangkan mengisi kolom:
                # kartu peringkat/bulan cuma py header + 1 sub-item, kalau diregangkan jadi
                # kotak berwarna setinggi 2.2in dgn separuh bawahnya hampa (terlihat langsung
                # di render). Ruang sisanya jatuh ke kotak catatan / dibiarkan sbg ruang di
                # BAWAH kolom - itu terbaca sbg akhir kolom, bukan sbg kartu bolong.
                # KOREKSI USER: batas 2 sub-item DIBATALKAN. Sub-item bersarang justru
                # mesin kepadatan yang kita bangun - memotongnya membuang isi tanpa penanda
                # (E-Katalog kehilangan 2 dari 4 statusnya). Tinggi baris dihitung dari
                # sub-item TERBANYAK yang sungguhan ada; kalau tidak muat, yang dikurangi
                # jumlah kartu per baris, bukan kedalaman kartunya.
                cards_h = _column_layout["cards_h"]
                inner, notes_consumed = _insight_detail_row_html(cards, col_w, cards_h, 0.0, ctx, notes=None)
                col_parts.append(
                    f'<div style="position:absolute;left:{x}in;top:{y}in;width:{col_w}in;'
                    f'height:{cards_h}in;overflow:hidden;"><div style="position:relative;height:{cards_h}in;">{inner}</div></div>'
                )
                if False:  # catatan per kolom DIMATIKAN - lihat catatan A5 di atas
                    note_y = y + cards_h + 0.08
                    note_h = max(0.0, _bawah_seksi - note_y)
                    # Butir catatan dibuang dari BELAKANG sampai muat - sebelumnya kotaknya
                    # mengalir melewati jatah & menimpa nomor halaman (laporan 143).
                    notes, _dibuang_note = muat_catatan(col_w, notes, note_h)
                    if _dibuang_note:
                        logger.info("tata letak kolom: %d butir catatan tidak digambar "
                                    "(ruang tersisa %.2fin)", _dibuang_note, note_h)
                    col_parts.append(
                        f'<div style="position:absolute;left:{x}in;top:{note_y}in;width:{col_w}in;'
                        f'height:{note_h}in;overflow:hidden;">{_note_box_html(notes, theme=ctx.theme)}</div>'
                    )
                    notes_consumed = True
        # HANYA kalau kolom ini memang tidak punya visual apa pun - kalau ada chart/kartu,
        # menggambar catatan di `y` berarti menumpuk TEPAT di atasnya (bug nyata di sisi PPT:
        # kotak catatan menutup total sel heatmap Senin-Rabu). Kalau visualnya ada tapi
        # catatannya tetap tidak terpakai, catatan DILEWATI - lebih baik hilang scr sadar
        # drpd menutupi isi yang pembaca tidak tahu ada di baliknya.

        # ---- A8: STRIP FAKTA BERSIFAT OPPORTUNISTIK ---------------------------------
        # KEPUTUSAN USER: strip TIDAK memesan ruang di depan. Memesan 0.46in TETAP terlepas
        # dari apakah kolomnya punya ruang adalah bentuk lain dari angka tetap yang sudah tiga
        # kali dibuang di proyek ini (mgmt_narrative_per_page = 4, konstanta anggaran narasi,
        # batas 6 entitas).
        #
        # Strip itu PELENGKAP: chart & kartu yang membawa data, strip cuma menambah satu
        # angka. Jadi strip yang mengalah saat sempit, bukan chart. Keputusannya diambil dari
        # SISA TINGGI setelah chart & kartu dapat bagiannya - bukan ambang tetap "kalau kolom
        # lebih dari X". Dan strip TIDAK dikecilkan supaya muat: kalau 0.46in tidak ada,
        # tidak digambar.
        _fakta, _ = fakta_strip_kolom(col, is_english(ctx.report))
        if _fakta:
            _dasar_isi = _dasar_kolom + float(_column_layout.get("note_y") or 0.0)
            _sisa_in = _bawah_seksi - _dasar_isi - 0.10
            if _sisa_in >= _DASH_COLS_FACT_H_IN:
                col_parts.append(
                    f'<div style="position:absolute;left:{x}in;top:{_dasar_isi + 0.06}in;'
                    f'width:{col_w}in;height:{_DASH_COLS_FACT_H_IN}in;">'
                    f'{_fact_strip_kolom_html(_fakta, col_w)}</div>'
                )
                _y_terendah = max(_y_terendah, _dasar_isi + 0.06 + _DASH_COLS_FACT_H_IN)
            else:
                logger.info("A8 strip fakta DILEWATI di kolom %d: sisa tinggi %.3fin, "
                            "strip butuh %.2fin (%s)", idx + 1, _sisa_in,
                            _DASH_COLS_FACT_H_IN,
                            ", ".join("%s=%s" % (l, v) for l, v in _fakta))

        parts.extend(col_parts)
        # DASAR ISI kolom ini, bukan kursor `y`. Perencana sudah menghitungnya sbg
        # note_y (= tepat di bawah chart + kartu); memakai `y` membuat kotak catatan
        # halaman menimpa kartu yang digambar di bawahnya.
        _y_terendah = max(_y_terendah, _dasar_kolom + (_column_layout.get("note_y") or 0.0))

    # ---- A5: SATU kotak catatan selebar area konten, di dasar halaman ------------------
    # Slide acuan memakai satu kotak 8.97 x 1.18in terisi penuh; 188 memakai kotak per kolom
    # 6.28 x 0.88in berisi SATU butir, dan di halaman lain tidak ada sama sekali. Catatan
    # dari SELURUH kolom dikumpulkan ke sini (tanpa duplikat) lalu dibuang dari belakang
    # sampai muat - jadi kotaknya terisi, bukan hampir kosong.
    if _butir_note and _NOTE_HAL_H_IN:
        _note_y = avail_h_in + 0.06
        _note_h = _NOTE_HAL_H_IN - 0.06
        if _note_h >= 0.40:
            # Butir & tinggi kotak SUDAH diputuskan di atas (tinggi_kotak_catatan_halaman),
            # sebelum kolom dibagi tinggi - tidak dihitung ulang di sini. Butirnya digabung
            # BERGILIRAN antar kolom; potongan tetap [:4] yang dulu membuat catatan kolom
            # kedua dst tidak pernah muncul sudah dibuang.
            _cat, _dibuang = _butir_note, _note_tak_muat
            if _dibuang:
                logger.info("kotak catatan halaman: %d butir tidak digambar (ruang %.2fin)",
                            _dibuang, _note_h)
            if _cat:
                parts.append(
                    f'<div style="position:absolute;left:0in;top:{_note_y}in;'
                    f'width:{total_w_in}in;height:{_note_h}in;">'
                    f'{_note_box_html(_cat, theme=ctx.theme)}</div>'
                )

    inner_html = f'<div style="position:relative;height:{avail_h_in + _NOTE_HAL_H_IN}in;">{"".join(parts)}</div>'
    return (f'<div style="margin:-0.5in -0.25in 0 -0.25in;">{title_html}{inner_html}</div>', False, None, False)


def _build_management_action_items_block(block: dict, ctx: _PdfBlockContext) -> tuple:
    # PERMINTAAN USER (halaman "Priority Recommendations"/action items 1-3 poin masih terasa
    # kosong walau sudah ditengahkan): kartu diperbesar (padding+font+badge) saat jumlahnya
    # sedikit — sama prinsipnya dgn _build_key_findings_block.
    n_items = len(block.get("items", []))
    scale = 2.2 if n_items <= 2 else (1.5 if n_items == 3 else 1.0)
    cards_html = ""
    for it in block.get("items", []):
        fg, bg = URGENCY_COLOR.get(it.get("urgency", "low"), (GRAY_TEXT, IVORY))
        detail = (
            f'<div style="font-size:{9*scale:.1f}pt;color:{GRAY_TEXT};margin-top:{round(4*scale)}px;line-height:1.4;">{_esc(it.get("detail", ""))}</div>'
            if it.get("detail") else ""
        )
        badge_d = round(26 * scale)
        cards_html += (
            f'<table style="width:100%;margin-bottom:{round(8*scale)}pt;background:{bg};border:1px solid {fg}35;border-radius:3px;"><tr>'
            f'<td style="width:{badge_d+10}px;vertical-align:middle;text-align:center;padding:{round(8*scale)}pt;">'
            f'<div style="width:{badge_d}px;height:{badge_d}px;line-height:{badge_d}px;border-radius:{round(badge_d/2)}px;background:{fg};color:#fff;font-weight:900;font-size:{10*scale:.1f}pt;margin:0 auto;">{it.get("number", 1)}</div>'
            f'</td>'
            f'<td style="vertical-align:middle;padding:{round(8*scale)}pt {round(8*scale)}pt {round(8*scale)}pt 0;">'
            f'<div style="font-weight:800;font-size:{10.5*scale:.1f}pt;color:{TEXT_DARK};">{_esc(it.get("title", ""))}</div>'
            f'{detail}'
            f'</td>'
            f'<td style="width:{round(80*scale)}px;vertical-align:middle;text-align:right;padding-right:12pt;">'
            f'<span style="display:inline-block;padding:{round(2*scale)}px {round(8*scale)}px;border-radius:10px;background:{fg};color:#fff;font-size:{7.5*scale:.1f}pt;font-weight:800;text-transform:uppercase;">{_esc(it.get("urgency", ""))}</span>'
            f'</td>'
            f'</tr></table>'
        )
    # PERMINTAAN USER LANJUTAN ("Rekomendasi Prioritas pakai lapis yang sama dgn halaman
    # insight baru... kalau masih ada sisa, tarik Kesimpulan naik ke halaman yang sama"):
    # kalau report_render_logic.py menitipkan Kesimpulan ke chunk TERAKHIR halaman ini
    # (lihat build_management_report_blocks), gambar sbg strip gelap di bawah kartu2 action
    # item — BUKAN halaman solo terpisah spt sebelumnya (penyumbang kegagalan kepadatan
    # TERBANYAK, ditemukan lewat tes kepadatan halaman).
    strip_html = ""
    if block.get("conclusion_text"):
        pills_html = "".join(
            f'<td style="padding-right:10pt;"><span style="display:inline-block;background:{ctx.theme["main"]};'
            f'border:1px solid {ctx.theme["light"]};border-radius:999px;padding:6px 14px;font-weight:700;'
            f'font-size:9pt;color:{ctx.theme["light"]};white-space:nowrap;">{_esc(p)}</span></td>'
            for p in (block.get("conclusion_pills") or [])
        )
        pills_row = f'<table cellpadding="0" cellspacing="0"><tr>{pills_html}</tr></table>' if pills_html else ""
        strip_html = (
            f'<table style="width:100%;background:{ctx.theme["bg"]};border:1px solid {ctx.theme["light"]};border-radius:3px;margin-top:16pt;">'
            f'<tr><td style="padding:16pt;">'
            f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:14pt;color:#fff;margin-bottom:8pt;">{_esc(block["conclusion_title"])}</div>'
            f'<div style="font-size:10pt;color:#E8ECE6;line-height:1.5;margin-bottom:{"10pt" if pills_row else "0"};">{_esc(block["conclusion_text"])}</div>'
            f'{pills_row}'
            f'</td></tr></table>'
        )
    inner = _kicker(block.get("kicker", "")) + _title(block.get("title", "")) + cards_html + strip_html
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
        _kicker(block.get("kicker", ""), WHITE) +
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
    # BUG DIPERBAIKI (dilaporkan user, halaman "Additional Insights (Continued)" masih
    # kosong di bawah): chunking per halaman maksimal 4 item (lihat mgmt_narrative_per_page
    # di build_management_report_blocks), jadi n cuma bisa 1-4 per halaman. n==3 dgn cols=2
    # SEBELUMNYA menyisakan 1 kartu sendirian di baris terakhir (lebar cuma separuh, sisa
    # separuh baris kosong) — dipaksa 1 kolom (lebar penuh) juga spt kasus n==1, supaya tidak
    # ada sel kosong menganggur di samping kartu terakhir.
    cols = 1 if n in (1, 3) else 2
    # PERMINTAAN USER: kartu 1.3x SAJA masih terasa kecil kalau cuma 1 kartu lebar penuh —
    # padding dinaikkan JAUH lebih agresif drpd font (sama prinsipnya dgn pad_scale di
    # _build_management_kpi_grid_block) supaya kartu benar2 lebih TINGGI, bukan cuma teksnya
    # sedikit lebih besar, saat topiknya sedikit.
    # A2/A6: kartu narasi dulu 10pt isi & padding 14pt - di ATAS seluruh tangga font yang
    # baru diturunkan (baris data 7pt, nilai 7.5pt). Basisnya diturunkan supaya lebih banyak
    # butir muat per halaman (A6: ruang kosong diisi baris, bukan dibiarkan). Pembesaran saat
    # kartunya sedikit TETAP - halaman berisi 1-2 kartu memang harus mengisi halaman.
    scale = 1.8 if n <= 1 else (1.3 if n == 2 else (1.15 if n == 3 else 0.82))
    pad_scale = 3.0 if n <= 1 else (1.6 if n == 2 else (1.3 if n == 3 else 0.62))
    cell_htmls = []
    for idx, it in enumerate(items):
        badge_html = _badge(str(idx + 1), TEXT_DARK, size=f"{round(20*scale)}px", font_size=f"{9*scale:.1f}pt")
        cell_htmls.append(
            f'<table cellpadding="0" cellspacing="0"><tr>'
            f'<td style="width:{round(20*scale)+10}px;vertical-align:middle;">{badge_html}</td>'
            f'<td style="vertical-align:middle;font-size:{9.5*scale:.1f}pt;font-weight:800;text-transform:uppercase;letter-spacing:0.04em;color:{TEXT_DARK};">{_esc(it.get("title", ""))}</td>'
            f'</tr></table>'
            f'<div style="margin-top:{round(8*scale)}px;">{_bullet_lines_html(it.get("content", ""), theme=ctx.theme, font_pt=round(9*scale))}</div>'
        )
    # PERMINTAAN USER (E1, "tinggi kartu 1 baris harus seragam"): card_style dipakai (bg/
    # border/radius/padding LANGSUNG di <td>, bukan tabel bersarang lagi) — <td> standar HTML
    # table SELALU meregang penuh ke tinggi baris tertinggi, tabel bersarang TIDAK.
    card_style = {"bg": IVORY, "border_color": PANEL_BORDER, "radius": 3, "pad_pt": round(14 * pad_scale),
                  "border_left_colors": [TEXT_DARK] * len(cell_htmls)}
    inner = _kicker(block.get("kicker", "")) + _title(block.get("title", "")) + _card_grid(cell_htmls, cols, card_style=card_style)
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
    # PERMINTAAN USER (izinkan halaman "insight" tunggal/tipis disambung ke halaman TETANGGA
    # apa pun temanya, bukan cuma sesama "insight" — lihat backstop di report_render_logic.py
    # ::_group_candidates_into_pages): kalau halaman ini CAMPURAN (mis. 1 category_distribution
    # yang sudah bawa judul sendiri + 1 insight_tile hasil sambungan), pakai `all()` bukan
    # `any()` — header level-halaman generik HANYA digambar kalau SEMUA panel di halaman ini
    # jenis headerless (insight_tile/dynamic_section); begitu ada 1 saja panel "mandiri" yang
    # sudah bawa judulnya sendiri, header generik ini dimatikan total supaya tidak dobel judul
    # — panel insight yang ikut nebeng cukup memakai label kecilnya sendiri (_panel_header_band).
    needs_header = panels and all(p["panel_kind"] in _PANEL_NEEDS_PAGE_HEADER for p in panels)
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
                _kicker(block.get("kicker"), WHITE) +
                f'<div style="font-family:{TITLE_FONT};font-weight:700;font-size:20pt;color:#fff;margin-bottom:16px;">{_esc(block["title"])}</div>'
            )
        else:
            header = _kicker(block.get("kicker")) + _title(block["title"])
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
    "page": _build_page_block,
    "closing_summary": _build_closing_summary_block,
    "closing": _build_closing_block,
    "management_insight_page": _build_management_insight_page_block,
    "management_dashboard_columns": _build_management_dashboard_columns_block,
    "management_action_items": _build_management_action_items_block,
    "management_asset_ranking": _build_management_asset_ranking_block,
    "management_ai_narrative": _build_management_ai_narrative_block,
}


class PDFExporter:
    @classmethod
    def generate_pdf_report(cls, report: Report) -> bytes:
        # Konvensi angka (titik/koma ribuan) mengikuti BAHASA LAPORAN - disetel SEKALI di sini
        # supaya helper format angka yang letaknya dalam sekali (SVG chart/kartu bersarang)
        # ikut benar tanpa perlu membongkar 15+ signature. Lihat set_render_language().
        set_render_language(report)
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
            # PERMINTAAN USER: warna kustom yang SANGAT terang (mis. #ADF8FF) sebelumnya
            # digelapkan TERLALU jauh (ambang 0.45) sampai nyaris tak mirip lagi dgn warna
            # yang dipilih — dinaikkan ke 0.55 (masih cukup gelap utk teks putih besar/tebal
            # di cover tetap terbaca, WCAG large-text AA longgar di kontras ~3:1) supaya hue
            # aslinya lebih terasa/dikenali. TIDAK bisa dibuat identik 100% dgn warna aslinya
            # selama teks di atasnya tetap putih (light+putih = kontras nyaris nol, itu batas
            # keras, bukan pilihan) — lihat balasan ke user soal batasan ini.
            safe_main = _light_safe(theme_key, max_luminance=0.55)
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
            # PERMINTAAN USER (revisi): halaman "page" (dashboard analisis/distribusi SOC)
            # TIDAK lagi ditengahkan vertikal — konten sekarang harus mulai dekat atas
            # (referensi mulai konten di ~0.9in), bukan digeser turun oleh centering. Batch
            # perbaikan sebelumnya di TAHAP 2 report_render_logic.py (panel/halaman insight
            # naik ke 4/halaman, halaman tipis digabung/di-backstop) sudah mengurangi jauh
            # frekuensi halaman "page" yang genuinely pendek, jadi risiko ruang kosong di
            # bawah dari perubahan ini jauh lebih kecil drpd waktu centering ini pertama kali
            # ditambahkan. Kind Management (grid/daftar KPI dkk, masih rawan pendek krn jumlah
            # itemnya bisa cuma 1-2) TETAP ditengahkan seperti semula.
            center = page_kinds[i] in (
                "management_kpi_grid", "management_ai_narrative",
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
                logo_size_px=39 if is_cover_or_closing else None,
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
            # KEGAGALAN WEASYPRINT = GAGAL, BUKAN MUNDUR KE MESIN LAIN (keputusan user).
            # Fallback xhtml2pdf dulu menangkap galat ini, mencatat logger.warning, lalu tetap
            # MENGEMBALIKAN PDF - dirender mesin berbeda dgn tata letak berbeda dari yang
            # direncanakan. Itu kelas kegagalan terburuk di proyek ini: keluaran terlihat
            # normal, pembaca tidak punya cara tahu tata letaknya bukan yang dimaksud, dan
            # tidak ada uji yang membedakan keduanya. logger.warning tidak sampai ke pembaca
            # laporan. Laporan bertata-letak salah lebih berbahaya drpd tidak ada laporan.
            #
            # Diperiksa SEBELUM diubah (permintaan user): seluruh 135 laporan di basis data
            # digenerate, WeasyPrint gagal NOL kali. Jadi perubahan ini tidak mematikan jalur
            # yang sedang dipakai siapa pun - ia cuma menutup jalur diam yang belum terpakai.
            return HTML(string=html_content).write_pdf()

        pdf_io = io.BytesIO()
        pisa_status = pisa.CreatePDF(html_content, dest=pdf_io)
        if pisa_status.err:
            raise RuntimeError(f"Gagal mengonversi HTML ke PDF menggunakan xhtml2pdf: {pisa_status.err}")
        return pdf_io.getvalue()
