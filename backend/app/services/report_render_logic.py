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
import contextvars
import datetime
import itertools
import logging
import math
import os
import random
import re
import unicodedata

import pandas as pd

logger = logging.getLogger(__name__)

from app.crud.report import get_parsed_data
from app.services.ai_engine.data_profiler import compute_statistics, _classify_severity_value
from app.services.ai_engine.ollama_client import normalize_recommendations, sanitize_text, coerce_finding_text, coerce_narrative_text

SEVERITY_ORDER = ["critical", "high", "medium", "low", "informational"]
SEVERITY_LABEL = {
    "critical": "Critical", "high": "High", "medium": "Medium",
    "low": "Low", "informational": "Info",
}


def _balanced_chunks(items: list, max_per_page: int) -> list[list]:
    """Bagi `items` jadi beberapa halaman TANPA PERNAH menyisakan 1 halaman terakhir berisi
    cuma 1 item sendirian (kalau totalnya >= 2) — BUG NYATA YANG DIPERBAIKI (dilaporkan user,
    disertai screenshot): chunking naif `range(0, len(items), max_per_page)` pada rekomendasi
    (3 item, max 2/halaman) menghasilkan 2+1 — halaman pertama (2 item) memenuhi syarat gaya
    "timeline" (butuh >=2 item), tapi halaman KEDUA (cuma 1 item leftover) tidak, jadi
    otomatis jatuh ke gaya kartu biasa — 1 laporan yang sama jadi terlihat gonta-ganti gaya di
    tengah jalan, padahal report.visual_style seharusnya konsisten SATU gaya per laporan.
    Jumlah HALAMAN dihitung dulu (ceil(total/max_per_page)), baru total item diratakan
    SEBISA MUNGKIN ke semua halaman itu (bukan selalu isi penuh max_per_page dulu baru sisa
    dibuang ke halaman baru) — cara ini matematis TIDAK PERNAH menghasilkan halaman berisi 1
    item sendirian selama total>=2 & max_per_page>=2."""
    total = len(items)
    if total == 0:
        return []
    num_pages = math.ceil(total / max_per_page)
    base, extra = divmod(total, num_pages)
    chunks = []
    cursor = 0
    for page_idx in range(num_pages):
        size = base + 1 if page_idx < extra else base
        chunks.append(items[cursor:cursor + size])
        cursor += size
    return chunks


def best_grid_cols(n: int, min_cols: int = 2, max_cols: int = 3, max_rows: int = 3) -> int:
    """Pilih jumlah kolom grid dashboard visual (Management Report — tile chart macam-macam
    ditumpuk berdampingan, lihat build_management_report_blocks/visual_tiles) yang
    MEMINIMALKAN ruang kosong di baris terakhir. PERMINTAAN USER: boleh cuma sedikit tile per
    halaman (tidak harus selalu dipaksa banyak-banyak), TAPI baris terakhir tidak boleh
    menyisakan banyak slot kosong (mis. 3 tile dgn 2 kolom tetap menyisakan 1 slot kosong di
    baris kedua) — dicari kolom yang HABIS DIBAGI RATA dulu (mis. 3 tile -> 3 kolom, 1 baris
    penuh), kalau tidak ada yang pas, pilih kolom yang baris terakhirnya PALING PENUH terisi.
    Dipakai BERSAMA oleh export_pdf.py & export_ppt.py supaya keduanya konsisten.

    BUG DIPERBAIKI (dilaporkan user): utk n=7, versi lama memilih 2 kolom — baris TERAKHIR
    dgn 2 kolom (7%2=1, isi 1/2=50%) kebetulan "lebih penuh" drpd 3 kolom (7%3=1, isi 1/3=
    33%), tapi itu cuma menghitung kepenuhan baris TERAKHIR, tidak pernah mempertimbangkan
    berapa BANYAK baris totalnya — 2 kolom utk 7 tile berarti 4 BARIS (tile kecil2
    berdempetan, makin rawan tinggi total melebihi 1 halaman), padahal 3 kolom cuma perlu
    3 baris (3+3+1). Kolom yang menghasilkan `rows > max_rows` (default 3) SEKARANG tidak
    pernah dipilih sama sekali (kecuali TIDAK ADA pilihan lain di [min_cols, max_cols] yang
    memenuhi itu — fallback ke max_cols, paling sedikit barisnya yang masih bisa dicapai)."""
    if n <= 0:
        return min_cols
    if n <= min_cols:
        return n

    def _rows_for(cols: int) -> int:
        return math.ceil(n / cols)

    candidates = [c for c in range(min_cols, max_cols + 1) if _rows_for(c) <= max_rows]
    if not candidates:
        return max_cols

    for cols in range(max_cols, min_cols - 1, -1):
        if cols in candidates and n % cols == 0:
            return cols
    best_cols, best_fill = max(candidates), -1.0
    for cols in candidates:
        remainder = n % cols
        fill = 1.0 if remainder == 0 else remainder / cols
        if fill > best_fill:
            best_fill, best_cols = fill, cols
    return best_cols


# PERMINTAAN USER (A5, lanjutan): tile chart yang genuinely butuh ruang (banyak sumbu/sel/
# kategori) TIDAK boleh dipaksa ikut grid padat dashboard Management sama spt tile bar/donut
# kecil biasa — sama semangatnya dgn bobot 1.0 utk kpi_radar/time_heatmap di
# build_report_blocks (gaya SOC) yang membuatnya SELALU jadi halaman sendiri.
_SPACE_HUNGRY_TILE_KINDS = {"kpi_radar", "time_heatmap", "period_compare"}


def _chunk_visual_tiles(tiles: list, max_per_page: int = 2) -> list:
    """Pecah `tiles` (topik "tipis" — lihat _is_rich_insight_page/_build_column_dashboard_
    blocks) jadi beberapa halaman kolom — normalnya maks `max_per_page` topik/halaman, TAPI
    begitu 1 tile "space-hungry" (_SPACE_HUNGRY_TILE_KINDS) masuk ke satu chunk, chunk itu
    langsung ditutup SENDIRIAN (tile hungry itu jadi 1 halaman penuh) — chunk berikutnya
    mulai dari nol lagi, tidak ikut menumpuk tile lain bersamanya."""
    chunks: list = []
    current: list = []
    current_has_hungry = False
    for t in tiles:
        is_hungry = t.get("tile_kind") in _SPACE_HUNGRY_TILE_KINDS
        if current and (is_hungry or current_has_hungry or len(current) >= max_per_page):
            chunks.append(current)
            current, current_has_hungry = [], False
        current.append(t)
        if is_hungry:
            current_has_hungry = True
    if current:
        chunks.append(current)
    return chunks


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


def _shorten_to_caption(text: str, max_sentences: int = 2) -> str:
    """Ambil N kalimat pertama dari paragraf AI, jadi caption singkat dipasangkan dgn chart
    kecil di build_report_blocks (lihat blok dynamic_section/key_findings) — dipanggil HANYA
    saat assign block["text"], TIDAK pernah mengubah ai_summary itu sendiri, supaya tab Edit
    Text (baca ai_summary langsung, bukan lewat sini) tetap menampilkan teks AI penuh apa
    adanya. Pakai regex batas kalimat (bukan idiom `.partition(". ")` yang dipakai di tempat
    lain file ini) karena sanitize_text() menyambung ulang kalimat dgn SATU SPASI terlepas
    kalimat itu diakhiri "."/"!"/"?" — `.partition(". ")` bisa diam-diam gagal memotong kalau
    kalimat pertama diakhiri "!" atau "?"."""
    if not text:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[:max_sentences]).strip()


def _hard_truncate(text: str, max_chars: int) -> str:
    """Potong keras ke batas KARAKTER (bukan kalimat) — dipakai KHUSUS caption tile dashboard
    Management (visual_tiles) yang tile-nya ditumpuk padat (sampai 6 per halaman, lihat
    _build_management_visual_dashboard_block). BUG DIPERBAIKI (ditemukan lewat isolasi
    render+bisection langsung, bukan dugaan): _shorten_to_caption() SAJA (batas per KALIMAT)
    kadang tetap menghasilkan 1 kalimat majemuk Bahasa Indonesia yang panjang (100+ karakter,
    mis. kalimat berkonjungsi "namun"/"meski"/"sehingga") — beberapa caption sepanjang itu
    berdampingan dlm 1 baris grid TERBUKTI memicu bug WeasyPrint yang membuat SATU sel tile
    gagal dirender sama sekali (hilang total, bukan cuma terpotong) tanpa exception apa pun di
    sisi Python. Caption tile SEKARANG dijaga tetap pendek scr karakter juga, bukan cuma
    kalimat, sekaligus sejalan dgn permintaan user: narasi tiap tile tidak wajib panjang."""
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    # BUG DIPERBAIKI (dilaporkan user): potong-di-batas-kata (rsplit) bisa membuang HAMPIR
    # SELURUH string kalau spasi TERAKHIR sebelum batas max_chars kebetulan ada di dekat
    # AWAL teks — mis. "▣ /Common/vs.pekapg.petrokimia-gresik.com" cuma py 1 spasi (tepat
    # setelah simbol pertama), rsplit(" ", 1)[0] potong di situ & hasilnya jadi "▣…" doang,
    # membuang praktis SELURUH nama host yang justru bagian pentingnya. Ini terjadi kalau
    # ada 1 token PANJANG TANPA SPASI (URL/hostname/path) yang menembus batas max_chars.
    # Sekarang: kalau hasil potong-di-kata ternyata kurang dari 60% panjang yang diminta
    # (sinyal kuat kasus di atas), dibuang & diganti potong KERAS di karakter (persis di
    # posisi max_chars) — lebih baik terpotong mid-word drpd kehilangan mayoritas konten.
    word_cut = text[:max_chars].rsplit(" ", 1)[0].rstrip(",;:-– ")
    if len(word_cut) < max_chars * 0.6:
        word_cut = text[:max_chars].rstrip(",;:-– ")
    return word_cut + "…"


def _dedupe_truncated_labels(labels: list, max_chars: int) -> list:
    """_hard_truncate() per label di LIST (dipakai bareng di 1 chart/legend yang sama —
    mini legend donut, batang stacked-proporsi, treemap). BUG NYATA ditemukan di laporan
    produksi (id 161/162/165, lihat check_dup_titles.py): label kategori BEDA yang berbagi
    prefix panjang (mis. "Departemen Pemeliharaan II" & "Departemen Produksi III") sama2
    kepotong jadi "Departemen…" persis sama krn prefix umumnya saja sudah menghabiskan
    hampir seluruh jatah max_chars — pembaca chart tidak bisa lagi membedakan mana yang
    mana walau count-nya beda (4 vs 4, kebetulan sama, memperparah kebingungan). Label yang
    BENTROK setelah dipotong diperpanjang bertahap (+6 karakter) sampai unik lagi di antara
    label lain pada list yang SAMA, dibatasi 3x max_chars supaya tidak meledak panjang kalau
    memang ada 2 kategori dgn nama SUNGGUH identik (dibiarkan sama, itu bukan bug potongan)."""
    truncated = [_hard_truncate(str(lbl), max_chars) for lbl in labels]
    for i, lbl in enumerate(labels):
        step = max_chars
        while truncated.count(truncated[i]) > 1 and step < max_chars * 3:
            step += 6
            truncated[i] = _hard_truncate(str(lbl), step)
    return truncated


_RENDER_IS_EN: "contextvars.ContextVar[bool]" = contextvars.ContextVar("render_is_en", default=True)


def set_render_language(report) -> None:
    """Setel konvensi angka utk SATU proses render laporan (dipanggil sekali di awal
    generate_pdf_report/generate_ppt_report). Dipakai helper format angka yang letaknya
    DALAM sekali di pohon pemanggilan (SVG chart, kartu bersarang, dst) yang tidak punya
    akses ke `report` sama sekali - menyalurkan parameter bahasa ke 15+ fungsi helper itu
    berarti membongkar banyak signature tanpa manfaat lain.

    Dipakai ContextVar (BUKAN variabel modul biasa) supaya AMAN saat beberapa laporan
    dirender bersamaan: tiap thread/task async punya nilainya sendiri, tidak saling timpa."""
    _RENDER_IS_EN.set(is_english(report))


def render_is_en() -> bool:
    return _RENDER_IS_EN.get()


def _fmt_count(val, is_en: bool | None = None) -> str:
    """Mirror _fmt_num di export_pdf.py/export_ppt.py (dipisah krn report_render_logic.py
    tidak boleh import dari exporter — arah dependensi terbalik, exporter yang import dari
    sini) — dibulatkan kalau bilangan bulat.

    BUG NYATA DIPERBAIKI (dilaporkan user): pemisah ribuan SEBELUMNYA SELALU gaya Inggris
    (koma) apa pun bahasa laporannya — "2,675" bagi pembaca Indonesia terbaca "dua koma enam
    tujuh lima", jadi angkanya SALAH DIBACA, bukan sekadar terlihat asing. Sekarang mengikuti
    BAHASA LAPORAN: Indonesia = titik utk ribuan & koma utk desimal, Inggris = koma utk ribuan
    & titik utk desimal."""
    if is_en is None:
        is_en = render_is_en()
    try:
        f = float(val)
    except (TypeError, ValueError):
        return str(val)
    text = f"{int(f):,}" if f == int(f) else f"{f:,.1f}"
    if is_en:
        return text
    # Tukar pemisah ke konvensi Indonesia (lewat penanda sementara supaya tidak saling timpa).
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _fmt_count_unit(val, unit: str | None, is_en: bool | None = None) -> str:
    """_fmt_count(, _ien) + satuan (persen/Rupiah) - PERMINTAAN USER: kolom persentase/Rupiah yang
    sekarang genuinely masuk report_stats (lihat data_profiler.py::_coerce_indo_numeric_columns)
    HARUS tampil dgn satuannya di narasi/placeholder, bukan angka polos ("65" padahal "65%")."""
    formatted = _fmt_count(val, is_en)
    if unit == "percent":
        return f"{formatted}%"
    if unit == "currency":
        return f"Rp {formatted}"
    return formatted


def _tile_rank_items(tile: dict) -> list | None:
    """Daftar (label, angka) dari data MENTAH tile ini sendiri (bukan analisis baru) — dipakai
    _build_insight_page() utk lapis ringkasan KPI/detail per kategori/catatan. Tile
    "space-hungry" (kpi_radar/period_compare/time_heatmap — lihat _SPACE_HUNGRY_TILE_KINDS)
    sengaja TIDAK dicakup di sini: ketiganya SELALU dapat halaman solo penuh gaya lama
    (_layout_dashboard_column), tidak pernah lewat _build_insight_page."""
    kind = tile.get("tile_kind")
    if kind == "risk_heatmap":
        return [(b["label"], b["count"]) for b in tile.get("bars", [])]
    if kind == "status_funnel":
        return list(zip(tile.get("categories", []), tile.get("values", [])))
    if kind == "scatter_bubble":
        # PERMINTAAN USER (hapus jalur management_visual_dashboard, semua lewat insight):
        # "count" (jumlah kemunculan baris) SERING seragam/1 utk semua entitas (1 baris per
        # aset) - tidak berguna sbg dasar ranking kartu (semua kartu "seri", badge/skor jadi
        # tidak bermakna). "avg" (rata-rata metrik numerik sungguhan tiap entitas) dipakai
        # sbg ranking di sini SEBAGAI GANTINYA - TIDAK memengaruhi chart scatter/bubble visual
        # itu sendiri (baca tile["points"] langsung, bukan lewat fungsi ini).
        return [(p.get("label", ""), p.get("avg", 0)) for p in tile.get("points", [])]
    if kind == "trend_chart":
        chart = tile.get("chart") or {}
        return list(zip(chart.get("categories", []), chart.get("values", [])))
    if kind == "custom_topic":
        return list(zip(tile.get("labels", []), tile.get("values", [])))
    return None


def _attach_column_facts(tile: dict, report, sec_domain: bool) -> None:
    """Turunan fact_strip/fact_pair/notes (dibaca _layout_dashboard_column/render kolom lama)
    utk topik "tipis" yang tidak lolos _is_rich_insight_page — digabung dgn topik lain lewat
    _build_column_dashboard_blocks drpd dipaksa jadi halaman insight mandiri yang separuh
    kosong. SEMUA angka derivatif LANGSUNG dari data yang sama persis sudah digambar tile
    ini sendiri (via _tile_rank_items), sama prinsipnya dgn _build_insight_page."""
    _ien = is_english(report)
    unit = _L(report, "kejadian", "events") if sec_domain else _L(report, "data", "entries")
    items = _tile_rank_items(tile)
    if items:
        items = sorted(items, key=lambda kv: -kv[1])
        total = sum(v for _, v in items) or 1
        tile["fact_strip"] = [
            (_L(report, "Total", "Total"), _fmt_count(total, _ien)),
            (_L(report, "Kategori", "Categories"), str(len(items))),
        ]
        if len(items) >= 2:
            tile["fact_pair"] = [(name, f"{_fmt_count(val, _ien)} ({round(val / total * 100)}%)") for name, val in items[:2]]
        rest = items[2:6]
        if rest:
            tile["notes"] = [
                _L(
                    report,
                    f"{name} mencatat {_fmt_count(val, _ien)} {unit} ({round(val / total * 100)}% dari total).",
                    f"{name} recorded {_fmt_count(val, _ien)} {unit} ({round(val / total * 100)}% of the total).",
                )
                for name, val in rest
            ]
    elif tile.get("tile_kind") == "kpi_gauge":
        pct = tile.get("pct", 0)
        tile["fact_strip"] = [
            (_L(report, "Pencapaian", "Achievement"), f"{pct}%"),
            (_L(report, "Sisa", "Remaining"), f"{max(0, 100 - pct)}%"),
        ]


def _dedupe_chunk_tile_facts(chunk: list) -> None:
    """BUG NYATA DITEMUKAN sebelumnya (check_dup_titles.py, laporan produksi id 166/167): 2
    topik "tipis" digabung 1 halaman bisa kebetulan derivatif dari data kategori yang SAMA
    PERSIS (chart-nya beda bentuk, tapi fact_strip/pair/notes jadi identik). Kolom KEDUA dst
    yang blok fakta-nya identik dgn kolom SEBELUMNYA (dalam chunk/halaman yang SAMA)
    dikosongkan (chart tetap tampil, cuma tanpa blok fakta yang jadi duplikat itu)."""
    seen = []
    for tile in chunk:
        fingerprint = (
            tuple(tile.get("fact_strip") or ()),
            tuple(tile.get("fact_pair") or ()),
            tuple(tile.get("notes") or ()),
        )
        if fingerprint == ((), (), ()):
            continue
        if fingerprint in seen:
            tile.pop("fact_strip", None)
            tile.pop("fact_pair", None)
            tile.pop("notes", None)
        else:
            seen.append(fingerprint)


# CATATAN: _build_column_dashboard_blocks DIHAPUS (audit jalur render) - tidak pernah
# dipanggil dari mana pun sejak jalur management_visual_dashboard ditinggalkan, jadi
# satu-satunya penghasil blok jenis itu sudah tidak ada.
# PERMINTAAN USER (A3 + B): geometri 1 kolom dashboard Management (dipakai HANYA utk tile
# "space-hungry" — kpi_radar/period_compare/time_heatmap, lihat _SPACE_HUNGRY_TILE_KINDS —
# yang tetap solo 1 halaman penuh; tile lain sekarang lewat _build_insight_page di bawah).
# Satu sumber dipakai KEDUA exporter supaya tinggi tiap blok
# (pita judul/visual utama/strip fakta/kotak fakta/kotak catatan) identik antara PDF & PPT
# dari block plan yang sama, bukan diam2 dihitung ulang beda2 di tiap exporter.
_DASH_TITLE_BAND_H_IN = 0.34
_DASH_FACT_STRIP_H_IN = 0.46
_DASH_FACT_PAIR_H_IN = 0.74
_DASH_MAIN_VISUAL_RANGE_IN = (2.5, 2.9)
_DASH_NOTE_BOX_RANGE_IN = (1.4, 1.7)
# Geometri HALAMAN dashboard (A) — margin kiri/kanan 0.25in KHUSUS halaman ini (permintaan
# user A1, TIDAK mengubah MARGIN_X/CONTENT_W global dipakai semua halaman lain), judul y=0
# tinggi maks 1.12in (A2), konten kolom mengisi sampai y=7.4 dari tinggi slide/halaman 7.5in
# (A3), jarak antar kolom 0.42in (B).
_DASH_MARGIN_X_IN = 0.25
_DASH_COL_GAP_IN = 0.42
_DASH_TITLE_MAX_H_IN = 1.12
# CATATAN (hasil uji langsung, supaya tidak diulang): sempat diduga batas 7.4in inilah yang
# membuat nomor halaman hilang (7.4in memang menyentuh zona footer di ~7.09in). Dugaan itu
# DIUJI dgn menyapu nilai 6.95/6.8/6.6/6.4/6.2 - nomor halaman TETAP hilang di halaman yang
# sama pada SEMUA nilai, jadi budget ini TERBUKTI BUKAN penyebabnya & dikembalikan ke 7.4
# (menurunkannya cuma mengorbankan kepadatan tanpa memperbaiki apa pun). Penyebab sebenarnya
# ada di export_pdf.py::_insight_main_chart_html - kotak catatan dirender DI LUAR budget tata
# letak; lihat catatan akar masalah di sana.
_DASH_CONTENT_BOTTOM_IN = 7.4
_DASH_GAP_RANGE_IN = (0.1, 0.5)
_DASH_GAP_DEFAULT_IN = 0.2


def _layout_dashboard_column(tile: dict, avail_h_in: float) -> dict:
    """Hitung tinggi (inci) tiap blok dlm 1 kolom dashboard Management SEBELUM digambar
    (permintaan user A3: "jangan biarkan panel berukuran tetap lalu meninggalkan ruang
    kosong — kalau ada sisa >0.5in, tinggikan panel2nya scr proporsional"). Blok TETAP:
    pita judul (0.34in), strip fakta (0.46in, kalau tile["fact_strip"] ada), kotak fakta
    berpasangan (0.74in, kalau tile["fact_pair"] ada). Blok FLEKSIBEL (rentang, tumbuh
    mengisi sisa ruang): visual utama (2.5-2.9in, SELALU ada) & kotak catatan (1.4-1.7in,
    kalau tile["notes"] ada). Blok yang field datanya kosong DILEWATI SELURUHNYA (tidak ikut
    dihitung sbg baris) — kolom yang kehilangan 1-2 blok opsional otomatis lebih lapang utk
    blok yang tersisa, bukan menyisakan celah kosong di tengah.

    Return: {"gap": ..., "title_band": 0.34, "main_visual": ..., "fact_strip": ... atau tidak
    ada key-nya kalau dilewati, dst}. Nilai "note_box" di sini HANYA estimasi perencanaan
    (dipakai menghitung berapa sisa ruang utk main_visual) — tinggi SUNGGUHAN kotak catatan
    tetap dihitung dari isi teks aslinya saat digambar (add_note_box/_note_box_html sudah
    dinamis dari dulu, lihat catatan E3 di export_ppt.py/export_pdf.py), supaya tidak
    kependekan/overflow kalau realisasinya beda dari estimasi rentang di sini."""
    has_strip = bool(tile.get("fact_strip"))
    has_pair = bool(tile.get("fact_pair"))
    has_notes = bool(tile.get("notes"))
    blocks = ["title_band", "main_visual"]
    if has_strip:
        blocks.append("fact_strip")
    if has_pair:
        blocks.append("fact_pair")
    if has_notes:
        blocks.append("note_box")
    n = len(blocks)
    gap = _DASH_GAP_DEFAULT_IN
    fixed_h = {"title_band": _DASH_TITLE_BAND_H_IN, "fact_strip": _DASH_FACT_STRIP_H_IN, "fact_pair": _DASH_FACT_PAIR_H_IN}
    flex_ranges = {"main_visual": _DASH_MAIN_VISUAL_RANGE_IN}
    if has_notes:
        flex_ranges["note_box"] = _DASH_NOTE_BOX_RANGE_IN
    heights = {b: fixed_h.get(b) or flex_ranges[b][0] for b in blocks}
    min_total = sum(heights.values()) + gap * (n - 1)
    max_total = sum(fixed_h.get(b) or flex_ranges[b][1] for b in blocks) + gap * (n - 1)
    leftover = avail_h_in - min_total
    if leftover <= 0:
        pass  # kolom padat (mis. 5 blok sekaligus) — pakai minimum apa adanya, wajar rapat.
    elif avail_h_in <= max_total:
        total_range = sum(hi - lo for lo, hi in flex_ranges.values())
        for b, (lo, hi) in flex_ranges.items():
            share = (hi - lo) / total_range if total_range else 0
            heights[b] = lo + leftover * share
    else:
        for b, (_lo, hi) in flex_ranges.items():
            heights[b] = hi
        extra = avail_h_in - max_total
        gap_room = (_DASH_GAP_RANGE_IN[1] - gap) * (n - 1)
        if n > 1 and extra <= gap_room:
            gap = gap + extra / (n - 1)
        else:
            gap = _DASH_GAP_RANGE_IN[1]
            # Sisa lewat batas atas gap JUGA: dorong semua ke main_visual (chart aman
            # diperbesar; kotak catatan JANGAN diregangkan lewat isi teksnya sendiri).
            heights["main_visual"] += max(0.0, extra - gap_room)
    return {"gap": gap, **heights}


# ============================================================================
# PERMINTAAN USER ("Tata letak — ini yang menentukan kepadatan, bukan margin saja"):
# halaman dashboard Management (utk tile NON "space-hungry" — lihat _SPACE_HUNGRY_TILE_KINDS,
# yang 3 itu TETAP pakai _layout_dashboard_column di atas) diganti TOTAL dari "kolom per
# topik" jadi "1 halaman = 1 pembahasan mendalam", disusun sbg LAPIS FUNGSI dari atas:
# judul -> ringkasan angka kunci (3 kartu lebar tak-sama) -> detail per kategori (sampai 4
# kartu bersarang berjajar) -> catatan. Konstanta di sini SATU SUMBER dipakai KEDUA exporter
# (sama spt _layout_dashboard_column) supaya geometrinya identik persis di PDF & PPT.
# ============================================================================
_INSIGHT_TITLE_H_IN = 1.1
# REGRESI DIPERBAIKI (dilaporkan user dari pemeriksaan cetak: kartu "TOTAL 42" ~60% kosong di
# hal.01-06): tinggi 1.8in dipilih saat kartu KPI masih dipakai bareng tata letak lama. Isi
# kartunya cuma 2 baris (label 8pt + angka 20pt) + padding 14pt atas-bawah = ~0,95in - sisanya
# rongga. Diturunkan mengikuti ISI. Ruang yang dibebaskan TIDAK jadi elemen tak-terhitung:
# untuk halaman ber-chart utama, "detail" memang dihitung sbg SISA ruang (avail - kpi) jadi
# otomatis menyerapnya; untuk halaman berkartu, sisanya masuk ke `gap` antar lapis yang sudah
# dibatasi 0,6in - keduanya tetap di dalam anggaran yang sama, tidak ada yang lahir di luar.
_INSIGHT_KPI_H_IN = 1.05
_INSIGHT_DETAIL_H_IN = 3.0
_INSIGHT_NOTES_H_IN = 1.1
_INSIGHT_GAP_KPI_DETAIL_IN = 0.3
_INSIGHT_GAP_DETAIL_NOTES_IN = 0.1
# PERMINTAAN USER (diukur langsung dari file referensi, kanvas 13.333x7.5in SAMA persis dgn
# kita — jadi bukan soal beda ukuran kanvas): kartu bersarang referensi lebar 2.24in, jarak
# antar kartu nyaris 0 (0.00-0.01in, bukan 0.10in lama), & pitch sub-item (label+bar+jarak)
# 0.35in (0.21+0.10+0.04, bukan +0.06 lama). Referensi juga MENUNJUKKAN sampai 8 kartu (2
# baris x 4) ketika kategorinya sebanyak itu (bukan dipotong ke 4 spt sebelumnya) — leftover
# lebar kalau kategorinya <=4 (kartu 2.24in x N tidak sampai memenuhi lebar halaman) diisi
# panel catatan di sisi kanan, BUKAN dibiarkan kosong (lihat _layout_nested_card_grid).
_NESTED_CARD_GAP_IN = 0.01
_NESTED_CARD_HEADER_H_IN = 0.70
# BUG NYATA DIPERBAIKI (terlihat di render kolom dasbor setelah tinggi kartu dibatasi ke
# kebutuhan isi): header dijepit `h_in * 0.35`, jadi begitu kartunya pendek (~1.2in) jatah
# header cuma 0.42in - padahal ISI header (nama + skor 16pt + padding) butuh ~0.62in, jadi
# baris skor menabrak sub-item di bawahnya. Ini LANTAI tinggi header: jepitan 0.35 tetap
# berlaku utk kartu tinggi (supaya header tidak memakan body), tapi tidak boleh menjepit
# header sampai lebih kecil dari isinya sendiri.
_NESTED_CARD_HEADER_MIN_H_IN = 0.62
_NESTED_CARD_SUBITEM_LINE1_H_IN = 0.21
_NESTED_CARD_SUBITEM_BAR_H_IN = 0.10
_NESTED_CARD_SUBITEM_GAP_IN = 0.04
_NESTED_CARD_TARGET_W_IN = 2.24
_NESTED_CARD_ROW_GAP_IN = 0.08
# Lebar minimum kartu bersarang yang masih terbaca (nama + skor + badge di header).
# Di bawah ini badge mulai terpotong - terukur dari render kolom dasbor 1.05in.
_NESTED_CARD_MIN_W_IN = 1.85
_NESTED_CARD_MAX_PER_ROW = 4
_NESTED_CARD_MAX_TOTAL = 8
_NESTED_CARD_SIDE_PANEL_MIN_W_IN = 2.0

_RELATIVE_TIERS = ((0.66, ("Tinggi", "High")), (0.33, ("Sedang", "Medium")), (0.0, ("Rendah", "Low")))


def _classify_relative_tier(frac: float, report) -> str:
    """Badge status (Tinggi/Sedang/Rendah) dari posisi RELATIF nilai ini thd nilai TERTINGGI
    di daftar yang sama — pola yang sama persis dgn _ASSET_LEVEL_TIERS (export_pdf.py/
    export_ppt.py), dipindah ke sini (data layer) supaya badge-nya IDENTIK di kedua
    exporter, bukan dihitung ulang terpisah 2x."""
    for threshold, (lbl_id, lbl_en) in _RELATIVE_TIERS:
        if frac >= threshold:
            return _L(report, lbl_id, lbl_en)
    return _L(report, "Rendah", "Low")


def _compute_secondary_breakdown(parsed_data: list, cat_col: str | None, cat_val, secondary_col: str | None, limit: int = 6) -> list:
    """Cross-tab SUNGGUHAN dari data mentah (bukan dikarang) — utk 1 nilai kategori PRIMER
    (mis. departemen "SDM"), hitung breakdown baris yang cocok berdasar kolom SEKUNDER (mis.
    severity/status) — dipakai isi "sub-item" kartu bersarang (permintaan user poin 9).
    Return [] (bukan error) kalau salah satu kolom tidak diketahui/tidak ada datanya —
    kartu bersarang tetap tampil (header+skor+badge), cuma tanpa body sub-item, sesuai
    prinsip "blok tanpa data dilewati" yang sama dipakai di seluruh file ini."""
    if not parsed_data or not cat_col or not secondary_col:
        return []
    counter: dict = {}
    for row in parsed_data:
        if str(row.get(cat_col, "")) != str(cat_val):
            continue
        raw = row.get(secondary_col)
        if raw in (None, ""):
            continue
        key = str(raw)
        counter[key] = counter.get(key, 0) + 1
    return sorted(counter.items(), key=lambda kv: -kv[1])[:limit]


def _norm_col_name(name) -> str:
    """Whitespace/underscore/case-insensitive - dipakai menyamakan nama kolom ASLI (mis.
    "Authentication\\nFailure", "vendor_name") dgn versi yang AI lihat & salin di "chart_source"
    (SECTIONS_BATCH_SYSTEM_PROMPT), yang teksnya sudah lewat _humanize_stats_label di
    data_profiler.py (newline->spasi, underscore->spasi, title-case) - tanpa normalisasi ini,
    kolom yang butuh humanisasi (mis. category_N di-mapping ke nama kolom asli berunderscore)
    bisa gagal dicocokkan _find_breakdown_entry walau sebenarnya kolom yang sama."""
    return re.sub(r"[\s_]+", " ", str(name or "")).strip().lower()


def _find_breakdown_entry(breakdown_list: list, numeric_col, category_col) -> dict | None:
    """Cari entri stats["category_numeric_breakdown"] (dihitung pandas, lihat data_profiler.py
    ::_compute_category_numeric_breakdown) yang cocok dgn "chart_source" AI — SATU-SATUNYA jalur
    chart section custom AI sekarang (lihat pemanggil di bawah): AI cuma menunjuk PASANGAN NAMA
    KOLOM, tidak pernah menulis angka chart-nya sendiri lagi — kalau tidak ketemu (nama kolom
    salah/tidak cocok), return None & pemanggil TIDAK menampilkan chart sama sekali (fallback
    narasi) drpd menampilkan chart dari sumber yang tidak bisa diverifikasi."""
    if not breakdown_list or not numeric_col:
        return None
    target_num, target_cat = _norm_col_name(numeric_col), _norm_col_name(category_col)
    for entry in breakdown_list:
        if _norm_col_name(entry.get("numeric_col")) != target_num:
            continue
        if target_cat and _norm_col_name(entry.get("category_label")) != target_cat and _norm_col_name(entry.get("category_col")) != target_cat:
            continue
        return entry
    return None


def _find_count_breakdown_entry(breakdown_list: list, category_col) -> dict | None:
    """Sama spt _find_breakdown_entry, tapi utk stats["category_count_breakdown"] (JUMLAH
    BARIS per kategori, TANPA kolom angka - lihat data_profiler.py::
    _compute_category_count_breakdown) - dipakai kontrak "metric":"count" di
    _resolve_templated_narrative di bawah."""
    if not breakdown_list or not category_col:
        return None
    target_cat = _norm_col_name(category_col)
    for entry in breakdown_list:
        if _norm_col_name(entry.get("category_label")) == target_cat or _norm_col_name(entry.get("category_col")) == target_cat:
            return entry
    return None


_VALUE_PLACEHOLDER_ALT = r"(?:peak_value|lowest_value|mean_value)"


def _strip_redundant_unit_symbols(template: str) -> str:
    """Buang simbol satuan (%, Rp, IDR) yang AI tempel SENDIRI TEPAT di sebelum/sesudah
    placeholder nilai ({peak_value}/{lowest_value}/{mean_value}) - _fmt_count_unit() SUDAH
    menambahkan satuan yang benar di titik itu kalau kolomnya genuinely persen/Rupiah
    (report_stats["_numeric_units"]), jadi simbol yang ditempel AI SELALU jadi DOBEL & SALAH
    ("{peak_value}%" -> tampil "92.4%%", "Rp {peak_value}" -> tampil "Rp 2.850.000.000 Rp").
    Instruksi prompt sudah eksplisit melarang ini (lihat prompts.py) TAPI TERBUKTI tidak cukup
    dipatuhi model kecil (dibuktikan lewat verifikasi 8 laporan live, bukan dugaan) - dibersihkan
    di sini scr deterministik, konsisten dgn filosofi Grup A: kode yang menjamin kebenaran
    format, bukan berharap instruksi prompt dipatuhi sempurna. Aman diterapkan tanpa perlu tahu
    unit kolom-nya dulu (kalau kolomnya genuinely BUKAN persen/Rupiah, _fmt_count_unit tidak
    menambahkan apa-apa di titik itu juga - tidak ada yang hilang, cuma simbol yang salah/dobel
    yang dicegah)."""
    # "Rp"/"Rp."/"IDR" TEPAT sebelum placeholder (dgn spasi opsional).
    template = re.sub(rf"(?:Rp\.?|IDR)\s*(\{{{_VALUE_PLACEHOLDER_ALT}\}})", r"\1", template, flags=re.IGNORECASE)
    # "%" TEPAT sesudah placeholder.
    template = re.sub(rf"(\{{{_VALUE_PLACEHOLDER_ALT}\}})%+", r"\1", template)
    # "Rp"/"IDR" TEPAT sesudah placeholder.
    template = re.sub(rf"(\{{{_VALUE_PLACEHOLDER_ALT}\}})\s*(?:Rp\.?|IDR)\b", r"\1", template, flags=re.IGNORECASE)
    return template


def _resolve_templated_narrative(raw_value, report_stats: dict, report=None):
    """Grup A (perbaikan Prioritas 2, pola sama seperti "chart_source"): AI kadang menulis
    angka/nama entitas SENDIRI di field naratif ("trend_analysis") tanpa jaminan angka itu
    genuinely cocok dgn topiknya (bug nyata yg sudah dikonfirmasi - lihat komentar "Prioritas
    2 poin 8" di pemanggil). Kontrak baru (OPSIONAL, AI bisa tetap kirim string bebas spt
    sebelumnya) - TIGA BENTUK:
      1. {"template": "...", "numeric_col": "...", "category_col": "..."} - nilai SUATU KOLOM
         ANGKA per kategori (mis. total nilai kontrak per vendor).
      2. {"template": "...", "category_col": "...", "metric": "count"} - JUMLAH KEMUNCULAN per
         kategori (mis. vendor mana paling sering dipakai) - TIDAK butuh kolom angka sama
         sekali. Ditambahkan (perbaikan Grup A poin 1) krn bentuk (1) tidak punya jalan sah utk
         pertanyaan frekuensi ini - AI yang genuinely ingin membahas ini dulu TERPAKSA
         mengarang nama kolom angka palsu ("Total records", BUKAN AI berhalusinasi - kontraknya
         yang belum lengkap).
      3. {"template": "...", "date_col": "..."} - JUMLAH DATA PER WAKTU (mis. tanggal/bulan mana
         paling sibuk) - dijawab lewat jalur time_series yang SUDAH ADA (data_profiler.py::
         _compute_time_series, granularitas harian/mingguan/bulanan dipilih OTOMATIS dari
         rentang data, bukan diminta ke AI). Ditambahkan (perbaikan Grup A poin 2) krn residu
         "AI menunjuk kolom tanggal sbg category_col" TERNYATA BUKAN AI menebak sembarangan -
         ia genuinely ingin membahas pola waktu (pertanyaan SAH, sistem MEMANG punya analisis
         tren waktu), cuma kontraknya belum menyediakan jalan mengungkapkan itu - PERSIS pola
         yang sama dgn "Total records" sebelum metric":"count" ditambahkan.
    AI TETAP menulis prosa sebab-akibat penuh, HANYA angka/nama entitas spesifik diganti
    placeholder; kode di sini mengisi placeholder itu dari report_stats (pandas asli, sama
    sumbernya dgn chart_source), TIDAK PERNAH dari angka yang ditulis AI sendiri.

    - Kalau raw_value BUKAN dict berkontrak baru (mis. masih string bebas gaya lama, atau dict
      bentuk lain) -> dikembalikan APA ADANYA, tidak disentuh (kompatibel mundur penuh).
    - Kalau kontraknya dikenali TAPI metrik/dimensi yang ditunjuk tidak ketemu di breakdown,
      atau templatenya salah bentuk -> return None (kalimat DIBUANG, bukan ditampilkan asal-
      asalan) - pemanggil wajib memperlakukan None sbg "tidak ada narasi utk topik ini"."""
    if not isinstance(raw_value, dict) or "template" not in raw_value:
        return raw_value
    template = raw_value.get("template")
    category_col = raw_value.get("category_col")
    numeric_col = raw_value.get("numeric_col")
    date_col = raw_value.get("date_col")
    is_count_metric = str(raw_value.get("metric") or "").strip().lower() == "count"
    if not isinstance(template, str) or not template.strip():
        return None
    _ien = is_english(report)
    # BUG NYATA DITEMUKAN (dibuktikan lewat verifikasi 8 laporan live): instruksi prompt
    # "jangan tempel sendiri %/Rp di sekitar placeholder" TIDAK CUKUP DIPATUHI model kecil -
    # tetap menulis "{peak_value}%" (hasil akhir dobel "92.4%%") atau "Rp {peak_value}"/
    # "{peak_value} Rp" (hasil akhir "Rp 2.850.000.000 Rp") pada beberapa kasus MESKIPUN sudah
    # diberi contoh SALAH eksplisit. Konsisten dgn filosofi seluruh pola Grup A (kode yang
    # menjamin kebenaran, AI cuma menunjuk) - dibersihkan DI SINI scr deterministik drpd
    # berharap instruksi prompt dipatuhi sempurna.
    template = _strip_redundant_unit_symbols(template)

    if date_col:
        # BENTUK 3: AI hanya menunjuk KOLOM TANGGAL-nya - granularitas (harian/mingguan/
        # bulanan) BUKAN pilihan AI, ikut apa adanya dari time_series yang sudah dihitung
        # sekali per laporan (auto dari rentang data, lihat _compute_time_series) - dicek DULU
        # kolom yang ditunjuk itu genuinely kolom tanggal yang SAMA yang dipakai sistem (bukan
        # kolom lain yang kebetulan namanya mirip), baru dipakai.
        real_date_col = (report_stats.get("_source_columns") or {}).get("date")
        if not real_date_col or _norm_col_name(date_col) != _norm_col_name(real_date_col):
            return None
        ts = report_stats.get("time_series") or {}
        labels, counts = ts.get("labels") or [], ts.get("counts") or []
        if len(labels) < 2 or len(labels) != len(counts):
            return None
        items = [{"label": lbl, "value": c} for lbl, c in zip(labels, counts)]
        metric_label = _L(report, "jumlah data", "record count")
        unit = None
    elif is_count_metric:
        if not category_col:
            return None
        entry = _find_count_breakdown_entry(report_stats.get("category_count_breakdown") or [], category_col)
        if not entry:
            return None
        items = [it for it in (entry.get("items") or []) if isinstance(it.get("value"), (int, float))]
        if not items:
            return None
        metric_label = _L(report, "jumlah data", "record count")
        unit = None
    else:
        if not numeric_col:
            return None
        entry = _find_breakdown_entry(report_stats.get("category_numeric_breakdown") or [], numeric_col, category_col)
        if not entry:
            return None
        items = [it for it in (entry.get("items") or []) if isinstance(it.get("value"), (int, float))]
        if not items:
            return None
        metric_label = humanize_label(str(entry.get("numeric_col") or numeric_col))
        unit = (report_stats.get("_numeric_units") or {}).get(entry.get("numeric_col") or numeric_col)

    peak_it = max(items, key=lambda it: it["value"])
    low_it = min(items, key=lambda it: it["value"])
    mean_val = sum(it["value"] for it in items) / len(items)
    fill = {
        "metric": metric_label,
        "peak_category": peak_it["label"],
        "peak_value": _fmt_count_unit(peak_it["value"], unit, _ien),
        "lowest_category": low_it["label"],
        "lowest_value": _fmt_count_unit(low_it["value"], unit, _ien),
        "mean_value": _fmt_count_unit(round(mean_val, 2), unit, _ien),
    }
    try:
        filled = template.format(**fill).strip()
    except (KeyError, IndexError, ValueError):
        return None
    return filled or None


# ============================================================================
# Grup B (perbaikan Prioritas 2, MELENGKAPI Grup A di atas): "executive_summary" &
# "conclusion" nilainya JUSTRU ADA di narasinya sendiri (bukan satu angka tunggal yang bisa
# diwakili placeholder) - dipaksa jadi template akan membuatnya kaku & seragam (permintaan
# eksplisit user). Sebagai gantinya, teks bebas AI diverifikasi PER KALIMAT SETELAH ditulis:
# kalimat yang genuinely tidak menyebut angka/entitas lolos apa adanya (murni kualitatif,
# aman by definition) - kalimat yang menyebut angka/entitas dicocokkan ke report_stats
# (dgn toleransi pembulatan & normalisasi satuan Rupiah/persen/skala kata "juta"/"ribu")
# sebelum dianggap sah ditampilkan.
# ============================================================================

_ABBREV_STEMS = ("vs", "dll", "dsb", "dst", "tsb", "mis", "dr", "sdr", "sdri", "no", "jl")
_ABBREV_END_RE = re.compile(r"\b(?:" + "|".join(_ABBREV_STEMS) + r")\.\s*$", re.IGNORECASE)
_SENT_SPLIT_SAFE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý])")
_DIGIT_DOT_PLACEHOLDER = ""


def _split_sentences_for_verification(text: str) -> list:
    """Pemisah kalimat dgn 2 pengecualian eksplisit yang diminta user: (1) singkatan umum
    (vs./dll./dsb./dst./dst.) TIDAK dianggap akhir kalimat - digabung ke bagian berikutnya;
    (2) titik DI ANTARA DUA DIGIT (mis. "40.000.000", "1.049") TIDAK PERNAH dianggap batas
    kalimat, dilindungi dulu sebelum split (defensif - format angka standar tanpa spasi di
    sekitar titik-nya sebenarnya sudah aman dgn sendirinya krn split mensyaratkan whitespace
    SEGERA sesudah titik, tapi dilindungi eksplisit jaga-jaga thd spasi tidak wajar hasil
    ekstraksi PDF/OCR)."""
    if not text:
        return []
    protected = re.sub(r"(?<=\d)\.(?=\d)", _DIGIT_DOT_PLACEHOLDER, text)
    raw_parts = _SENT_SPLIT_SAFE_RE.split(protected)
    sentences, buf = [], ""
    for part in raw_parts:
        part = part.replace(_DIGIT_DOT_PLACEHOLDER, ".")
        if buf:
            part = buf + " " + part
            buf = ""
        if _ABBREV_END_RE.search(part):
            buf = part
            continue
        part = part.strip()
        if part:
            sentences.append(part)
    if buf.strip():
        sentences.append(buf.strip())
    return sentences


_NUM_TOKEN_RE = re.compile(
    r"(?<![\w.,])(?:Rp\.?\s*)?(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
    r"\s*(ribu|juta|milyar|miliar|triliun)?\s*(%)?",
    re.IGNORECASE,
)
_SCALE_MULT = {
    "ribu": 1_000, "juta": 1_000_000, "milyar": 1_000_000_000,
    "miliar": 1_000_000_000, "triliun": 1_000_000_000_000,
}

_MONTH_NAMES = (
    r"Jan(?:uari|uary)?|Feb(?:ruari|ruary)?|Mar(?:et|ch)?|Apr(?:il)?|Mei|May|Jun[ei]?|"
    r"Jul[i]?|Agu(?:stus)?|Aug(?:ust)?|Sep(?:tember)?|Okt(?:ober)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Des(?:ember)?|Dec(?:ember)?"
)
_DATE_SPAN_RE = re.compile(
    r"\b\d{4}-\d{1,2}-\d{1,2}\b"                                  # ISO: 2026-07-13
    r"|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"                          # 20/11/2024
    rf"|\b\d{{1,2}}\s+(?:{_MONTH_NAMES})\.?\s+\d{{4}}\b"           # 20 November 2024
    rf"|\b(?:{_MONTH_NAMES})\.?\s+\d{{1,2}},?\s+\d{{4}}\b",        # November 20, 2024
    re.IGNORECASE,
)


def _strip_date_spans(sentence: str) -> str:
    """PERMINTAAN USER (toleransi pembulatan & normalisasi satuan) - ditemukan lewat replay 30
    laporan: tanggal periode laporan (mis. "2026-07-13", "20 November 2024") kalau tidak
    dibuang dulu, komponen angkanya (hari/bulan/tahun) ikut dianggap KLAIM ANGKA yang harus
    cocok ke report_stats - padahal itu cuma keterangan RENTANG WAKTU laporan, bukan fakta
    data yang perlu diverifikasi, dan otomatis GAGAL cocok (report_stats tidak menyimpan
    "2024"/"07"/"13" sbg angka tersendiri) - kalimat yang genuinely benar ikut terbuang
    gara-gara ini. Dibuang HANYA utk keperluan deteksi klaim angka (bukan utk teks final yang
    ditampilkan - `sent` asli tetap utuh)."""
    return _DATE_SPAN_RE.sub(" ", sentence)


def _extract_number_candidates(token: str) -> list:
    """Dari SATU token angka mentah (mis. "1.049", "40.000.000", "3,14") - hasilkan SEMUA
    tafsiran yang mungkin benar. BEDA dari _classify_indo_numeric_column (itu keputusan SEKALI
    utk SELURUH KOLOM data sumber, ada konteks banyak baris sejenis utk diputuskan bersama) -
    di sini SATU kalimat lepas TIDAK punya konteks kolom sama sekali, jadi ambiguitas titik/
    koma diselesaikan dgn cara BEDA: coba SEMUA tafsiran, cocokkan ke report_stats, salah satu
    cocok = lolos. Ini konsisten dgn arahan user "toleransi pembulatan, jangan cocokkan persis"
    - permisif di sisi penafsiran, ketat di sisi apakah HASILNYA genuinely ada di data."""
    candidates = set()
    try:
        candidates.add(float(re.sub(r"[.,]", "", token)))
    except ValueError:
        pass
    try:
        candidates.add(float(token.replace(".", "").replace(",", ".")))
    except ValueError:
        pass
    if token.count(".") <= 1 and "," not in token:
        try:
            candidates.add(float(token))
        except ValueError:
            pass
    # Tafsiran tambahan (ditemukan lewat replay 30 laporan): AI kadang menulis angka CAMPURAN
    # - pemisah ribuan pakai titik, TAPI desimal terakhir JUGA kebetulan pakai titik alih2 koma
    # (mis. "66.548.91" utk 66548.91) - bukan format baku manapun, tapi genuinely muncul.
    # Grup terakhir yang JUMLAH DIGITNYA BUKAN 3 dianggap desimal, grup2 SEBELUMNYA (yang semua
    # persis 3 digit) dianggap pemisah ribuan.
    parts = re.split(r"[.,]", token)
    if len(parts) >= 2 and all(len(p) == 3 for p in parts[1:-1]) and len(parts[-1]) != 3 and len(parts[0]) <= 3:
        try:
            candidates.add(float("".join(parts[:-1]) + "." + parts[-1]))
        except ValueError:
            pass
    return list(candidates)


def _sentence_number_claims(sentence: str) -> list:
    """Semua klaim angka dlm 1 kalimat -> list (kandidat_nilai, is_persen)."""
    claims = []
    for m in _NUM_TOKEN_RE.finditer(sentence):
        num_str, scale_word, pct = m.groups()
        if not num_str:
            continue
        cands = _extract_number_candidates(num_str)
        if not cands:
            continue
        if scale_word:
            mult = _SCALE_MULT.get(scale_word.lower())
            if mult:
                cands = [c * mult for c in cands]
        claims.append((cands, bool(pct)))
    return claims


def _collect_known_numbers(report_stats: dict) -> tuple:
    """Kumpulkan SEMUA angka yang genuinely ada di report_stats - dipisah 2 himpunan (angka
    mentah, persentase-dari-total) supaya klaim "%" di kalimat dicocokkan ke skala yang tepat
    (persentase jarang sekali kebetulan sama skalanya dgn angka mentah puluhan juta)."""
    raw_vals, pct_vals = set(), set()
    total = report_stats.get("total_records") or 0

    def add_raw(v):
        try:
            if v is not None:
                raw_vals.add(round(float(v), 4))
        except (TypeError, ValueError):
            pass

    def add_pct(v):
        try:
            if v is not None:
                pct_vals.add(round(float(v), 4))
        except (TypeError, ValueError):
            pass

    add_raw(total)
    for v in (report_stats.get("severity_distribution") or {}).values():
        add_raw(v)
        if total:
            add_pct(v / total * 100)
    for items in (report_stats.get("top_categories") or {}).values():
        for it in items or []:
            add_raw(it.get("count"))
            if total and it.get("count") is not None:
                add_pct(it["count"] / total * 100)
    for s in (report_stats.get("numeric_summary") or {}).values():
        add_raw(s.get("min"))
        add_raw(s.get("max"))
        add_raw(s.get("mean"))
    for p in (report_stats.get("category_numeric_pairs") or {}).get("points", []) or []:
        add_raw(p.get("count"))
        add_raw(p.get("avg"))
    for entry in (report_stats.get("category_numeric_breakdown") or []):
        for it in entry.get("items") or []:
            add_raw(it.get("value"))
    for entry in (report_stats.get("category_count_breakdown") or []):
        v = None
        for it in entry.get("items") or []:
            v = it.get("value")
            add_raw(v)
            if total and v is not None:
                add_pct(v / total * 100)
    tp = report_stats.get("time_pattern") or {}
    add_raw(tp.get("peak_hour"))
    trend = tp.get("trend") or {}
    add_raw(trend.get("first_half_count"))
    add_raw(trend.get("second_half_count"))
    add_raw(trend.get("pct_change"))
    ts = report_stats.get("time_series") or {}
    for v in ts.get("counts") or []:
        add_raw(v)
    for v in ts.get("cumulative") or []:
        add_raw(v)
    return raw_vals, pct_vals


def _number_matches_known(value: float, known: set) -> bool:
    if not known:
        return False
    # PERMINTAAN USER: toleransi pembulatan - report_stats simpan nilai penuh (1048.88),
    # narasi sering membulatkan ("1.049", atau "sekitar 1.000" - beda ~4.7%). Toleransi
    # relatif 8% menampung kedua gaya pembulatan itu; ambang absolut 2 utk angka kecil
    # (hitungan/count) drpd relatif 8% dari angka kecil jadi terlalu ketat (mis. 8 vs 7 count).
    tol = max(2.0, abs(value) * 0.08)
    return any(abs(value - k) <= tol for k in known)


def _claim_matches(candidates: list, is_pct: bool, raw_vals: set, pct_vals: set) -> bool:
    """PERMINTAAN USER (satuan yang baru aktif - Rupiah/persen): angka yang sama bisa ditulis
    narasi sbg "40.000.000" polos ATAU "65%" - dicek ke himpunan yang SESUAI penandanya dulu,
    tapi kalau tidak cocok tetap dicoba ke himpunan lain sbg cadangan (mis. "%"-nya cuma
    penekanan gaya bahasa, bukan literal persen-dari-total) - bias PERMISIF spy kalimat benar
    tidak ikut terbuang gara2 penandaan longgar."""
    pool_primary, pool_secondary = (pct_vals, raw_vals) if is_pct else (raw_vals, pct_vals)
    if any(_number_matches_known(c, pool_primary) for c in candidates):
        return True
    return any(_number_matches_known(c, pool_secondary) for c in candidates)


_ENTITY_PREFIX_RE = re.compile(
    r"\b(?:PT|CV|Departemen|Dept\.?|Unit|Divisi|Kantor|Pabrik|Bagian|Bidang|Kategori|Belanja|"
    r"Vendor|Server|Cabang|Wilayah)\s+[A-Za-z][\w./-]*(?:\s+[A-Za-z][\w./-]*){0,4}"
)
_TITLECASE_RUN_RE = re.compile(r"\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){1,4}\b")
_ENTITY_STOPWORDS = {
    "hal", "ini", "namun", "selain", "dengan", "karena", "meski", "meskipun", "oleh",
    "untuk", "dari", "pada", "dalam", "secara", "berdasarkan", "sebagai", "kondisi",
    "tren", "data", "total", "sementara", "artinya", "sebaliknya", "sedangkan", "adapun",
    "sehingga", "akibatnya", "seiring", "meningkat", "menurun", "hasil", "temuan",
    "this", "that", "these", "those", "however", "meanwhile", "overall", "based",
    "the", "a", "an", "such", "with", "while", "during", "across", "among",
}


def _extract_entity_candidates(sentence: str) -> list:
    """Cari SPAN yang BENTUKNYA seperti nama entitas (2+ kata berawalan huruf besar berturut2,
    atau berawalan prefiks umum spt "Departemen"/"PT"/"Unit") - heuristik best-effort (bukan
    NLP formal), sengaja dibuat agak longgar drpd terlalu ketat (kalimat starter berhuruf besar
    yang genuinely bukan entitas dibuang via daftar stopword, bukan analisis gramatikal utuh)."""
    found = set()
    for m in _ENTITY_PREFIX_RE.finditer(sentence):
        found.add(m.group().strip())
    for m in _TITLECASE_RUN_RE.finditer(sentence):
        span = m.group().strip()
        if span.split()[0].lower() in _ENTITY_STOPWORDS:
            continue
        found.add(span)
    result = []
    for cand in sorted(found, key=len, reverse=True):
        if not any(cand != other and cand.lower() in other.lower() for other in result):
            result.append(cand)
    return result


def _collect_raw_text_values(parsed_data, max_unique_per_col: int = 500) -> set:
    """Pelengkap _collect_known_entities: SEMUA nilai teks di SELURUH kolom object DATA MENTAH
    (bukan cuma kolom yang KEBETULAN terpilih jadi salah satu dari maks 5 "kategori utama" di
    compute_statistics()). BUG NYATA DITEMUKAN (replay 30 laporan, dibuktikan langsung ke data
    asli): kolom nama entitas yang nilainya NYARIS UNIK PER BARIS (mis. "Nama_Aset", 50 nilai
    utk 50 baris) SENGAJA dikecualikan dari deteksi kategori (rasio unik terlalu tinggi utk
    jadi kategori chart yang bermakna, lihat _rank_categorical_candidates) - itu keputusan yang
    BENAR utk kebutuhan chart, TAPI tidak berarti nilainya tidak sah disebut narasi (nama aset
    spesifik WAJAR disebut satu per satu). Tanpa fallback ini, kalimat yang genuinely benar
    (menyebut nama aset ASLI persis dari data) ikut dibuang krn tidak pernah masuk
    known_entities yang cuma bersumber dari kategori-kategori terkurasi.

    Dibatasi `max_unique_per_col` per kolom (skip kolom teks bebas/deskripsi panjang yang
    hampir semua nilainya unik - itu genuinely bukan "daftar entitas", cuma teks naratif)."""
    if not parsed_data:
        return set()
    values = set()
    sample = parsed_data[0] if isinstance(parsed_data[0], dict) else {}
    for col in sample.keys():
        col_values = set()
        for row in parsed_data:
            v = row.get(col)
            if v is None or v == "":
                continue
            col_values.add(str(v).strip().lower())
            if len(col_values) > max_unique_per_col:
                break
        if len(col_values) <= max_unique_per_col:
            values |= col_values
    return values


def _collect_known_entities(report_stats: dict, parsed_data=None) -> set:
    labels = set()

    def add(v):
        if v:
            labels.add(str(v).strip().lower())

    for items in (report_stats.get("top_categories") or {}).values():
        for it in items or []:
            add(it.get("value"))
    for entry in (report_stats.get("category_numeric_breakdown") or []):
        for it in entry.get("items") or []:
            add(it.get("label"))
    for entry in (report_stats.get("category_count_breakdown") or []):
        for it in entry.get("items") or []:
            add(it.get("label"))
    for p in (report_stats.get("category_numeric_pairs") or {}).get("points", []) or []:
        add(p.get("label"))
    for k in (report_stats.get("severity_distribution") or {}).keys():
        add(k)
    for lbl in (report_stats.get("time_series") or {}).get("labels") or []:
        add(lbl)
    # PERMINTAAN USER (ditemukan lewat replay 30 laporan): narasi kadang menyebut NAMA KOLOM
    # (mis. "Legal Requests", "Authentication Failure" sbg metrik yang dibahas), bukan cuma
    # NILAI kategori - itu sah, bukan fabrikasi, tapi sebelum ini tidak ada di known_entities
    # (yang cuma kumpulan NILAI kategori) sehingga selalu dianggap "entitas tidak dikenal" &
    # kalimatnya salah dibuang. Nama kolom asli (numeric_col/category_col) ditambahkan di sini
    # supaya menyebut nama METRIK/KOLOM tidak keliru dianggap menyebut ENTITAS palsu.
    for col in (report_stats.get("numeric_summary") or {}).keys():
        add(col)
        add(str(col).replace("_", " ").replace("\n", " "))
    for k, v in (report_stats.get("_source_columns") or {}).items():
        if k != "date":
            add(v)
            if v:
                add(str(v).replace("_", " "))
    if parsed_data:
        labels |= _collect_raw_text_values(parsed_data)
    return labels


def _entity_matches_known(candidate: str, known: set, sentence: str = "") -> bool:
    cand_norm = candidate.strip().lower()
    if not cand_norm or not known:
        return False
    if any(cand_norm == k or cand_norm in k or k in cand_norm for k in known):
        return True
    # PERMINTAAN USER (ditemukan lewat replay 30 laporan): AI kadang menulis istilah Inggris/
    # terjemahan diikuti nama ASLI dlm kurung TEPAT SESUDAHNYA (mis. "Department of Human
    # Resources (Departemen SDM)") - kalau isi kurung itu cocok ke data asli, kandidat di depan
    # kurung dianggap SUDAH diberi anotasi rujukan oleh AI sendiri (bukan entitas baru yang
    # perlu diverifikasi terpisah), bukan fabrikasi.
    if sentence:
        idx = sentence.find(candidate)
        if idx != -1:
            after = sentence[idx + len(candidate):idx + len(candidate) + 80].strip()
            m = re.match(r"\(([^)]{2,60})\)", after)
            if m:
                inner = m.group(1).strip().lower()
                if any(inner == k or inner in k or k in inner for k in known):
                    return True
    return False


_BACKREF_PREFIXES = (
    "hal ini", "hal tersebut", "hal itu", "ini menunjukkan", "ini menandakan",
    "ini mengindikasikan", "ini berarti", "kondisi ini", "kondisi tersebut",
    "situasi ini", "situasi tersebut", "keadaan ini", "temuan ini", "dengan demikian",
    "oleh karena itu", "hal ini menunjukkan", "hal ini mengindikasikan",
    "this indicates", "this suggests", "this shows", "this means", "this condition",
    "this situation", "such a condition", "these findings", "as a result", "thus,",
)


def _starts_with_backreference(sentence: str) -> bool:
    s = sentence.strip().lower()
    return any(s.startswith(p) for p in _BACKREF_PREFIXES)


def _verify_narrative_sentences(text: str, report_stats: dict, field_name: str = "", report_id=None, parsed_data=None) -> tuple:
    """Grup B: verifikasi PER KALIMAT utk field naratif bebas (executive_summary/conclusion)
    yang TIDAK cocok dipaksa jadi template (nilainya ADA di narasinya sendiri, bukan 1 angka
    tunggal yang bisa diwakili placeholder - template akan membuatnya kaku/seragam, permintaan
    eksplisit user). Alur: kalimat TANPA angka/entitas lolos apa adanya (kualitatif, aman by
    definition) - kalimat DGN angka/entitas dicocokkan ke report_stats (toleran pembulatan &
    satuan) - tidak cocok = dibuang & dicatat log. Kalimat lanjutan yang cuma merujuk balik ke
    kalimat yg baru dibuang ("Hal ini menunjukkan...") ikut dibuang spy tidak menggantung.

    Return (teks_bersih, daftar_kalimat_dibuang). teks_bersih == "" kalau SEMUA kalimat
    dibuang - pemanggil WAJIB memperlakukan itu sbg "jangan tampilkan blok ini sama sekali"."""
    if not text or not text.strip():
        return text, []
    raw_vals, pct_vals = _collect_known_numbers(report_stats)
    known_entities = _collect_known_entities(report_stats, parsed_data=parsed_data)
    sentences = _split_sentences_for_verification(text)
    kept, dropped = [], []
    prev_dropped = False
    for sent in sentences:
        if prev_dropped and _starts_with_backreference(sent):
            dropped.append(sent)
            continue
        num_claims = _sentence_number_claims(_strip_date_spans(sent))
        entity_claims = _extract_entity_candidates(sent)
        if not num_claims and not entity_claims:
            kept.append(sent)
            prev_dropped = False
            continue
        ok = all(_claim_matches(cands, is_pct, raw_vals, pct_vals) for cands, is_pct in num_claims)
        if ok:
            ok = all(_entity_matches_known(cand, known_entities, sentence=sent) for cand in entity_claims)
        if ok:
            kept.append(sent)
            prev_dropped = False
        else:
            dropped.append(sent)
            prev_dropped = True
    if dropped:
        logger.info(
            "Grup B: %d/%d kalimat dibuang dari '%s'%s: %s",
            len(dropped), len(sentences), field_name,
            f" (report {report_id})" if report_id is not None else "",
            " | ".join(dropped),
        )
    return " ".join(kept).strip(), dropped


_AFFIX_BOUNDARY_CHARS = set("/.-_ ")


def _strip_common_affix(labels: list) -> list:
    """PERMINTAAN USER: label kartu bersarang sempit (~1.74in) - nama aset F5 BIG-IP mentah
    (mis. "/Common/vs.bimbingankp.petrokimia-gresik.com") jauh lebih panjang dari itu, DILARANG
    dipotong dgn "..." (kehilangan makna). Buang bagian yang SAMA PERSIS di SEMUA label yang
    ditampilkan BERSAMAAN (prefix "/Common/" & suffix ".petrokimia-gresik.com" di contoh di
    atas), sisakan bagian PEMBEDA-nya ("vs.bimbingankp").

    Prefix/suffix umum dihitung per KARAKTER (longest common prefix/suffix di antara SEMUA
    label), lalu ditarik mundur ke BATAS TERAKHIR (/ . - _ spasi) yang masih di dalam batas
    umum itu - supaya tidak memotong di tengah token yang genuinely jadi pembeda. Cth: LCP
    karakter dari 2 nama di atas adalah "/Common/vs." (termasuk titik setelah "vs") - ditarik
    mundur ke "/" TERAKHIR di dalamnya ("/Common/") supaya "vs." (bagian bermakna "virtual
    server") tetap ikut ditampilkan, bukan ikut terbuang.

    Cuma memangkas kalau prefix/suffix umum itu CUKUP panjang (>=4 karakter) - biar tidak
    memangkas 1-2 karakter sepele yang hasilnya kelihatan aneh/tidak jelas alasannya.

    BUG NYATA DITEMUKAN (verifikasi visual langsung — render PDF sungguhan, bukan cuma unit
    test data bersih): kalau SATU SAJA label dlm batch tidak ikut pola umum (mis. label
    "Aggregated" nyempil di antara nama2 "/Common/vs.XXX...") LCP-nya jatuh ke NOL karakter
    (semua label harus cocok utk dianggap "umum") - akibatnya SEMUA kartu (termasuk 5 yang
    genuinely sama pola) gagal dipangkas & balik ke CSS ellipsis "..." - PERSIS yang dilarang.
    Diperbaiki: kalau LCP/LCS gabungan semua label < 4 karakter, coba lagi setelah membuang
    SAMPAI 2 label yang PALING mengganggu pola (dicoba satu-satu, disimpan yang hasilnya
    terpanjang) — prefix/suffix HASIL AKHIR lalu diterapkan PER LABEL SECARA independen (kalau
    suatu label kebetulan tidak cocok pola itu, mis. si outlier yang dibuang tadi, label itu
    TETAP ditampilkan penuh apa adanya, TIDAK ikut batal semua)."""
    labels = [str(lbl) for lbl in labels]
    if len(labels) < 2:
        return labels

    def _lcp(strs: list) -> str:
        if not strs:
            return ""
        shortest = min(strs, key=len)
        for i, ch in enumerate(shortest):
            if any(s[i] != ch for s in strs):
                return shortest[:i]
        return shortest

    def _best_common_affix(strs: list, max_outliers: int = 2) -> str:
        candidates = list(strs)
        for _ in range(max_outliers):
            if len(_lcp(candidates)) >= 4 or len(candidates) < 3:
                break
            best_removal_idx, best_len = None, len(_lcp(candidates))
            for i in range(len(candidates)):
                trial = candidates[:i] + candidates[i + 1:]
                trial_len = len(_lcp(trial))
                if trial_len > best_len:
                    best_len, best_removal_idx = trial_len, i
            if best_removal_idx is None:
                break
            candidates.pop(best_removal_idx)
        return _lcp(candidates)

    prefix = _best_common_affix(labels)
    suffix = _best_common_affix([s[::-1] for s in labels])[::-1]

    def _trim_prefix_to_boundary(p: str) -> str:
        # "/" DIUTAMAKAN drpd batas lain (. - _ spasi) kalau ADA di dalam prefix umum: "/"
        # menandai SEGMEN PATH (mis. "/Common/") - batas struktural yang lebih besar drpd "."
        # yang bisa jadi bagian dari SATU token bermakna (mis. "vs." utk "virtual server").
        # Tanpa prioritas ini, LCP "/Common/vs." (yang kebetulan berakhir di ".") akan ditarik
        # mundur ke "." itu sendiri (tidak mundur sama sekali) & "vs." ikut terbuang - PERSIS
        # bug yang ditemukan & diperbaiki di sini. Baru kalau TIDAK ADA "/" sama sekali di
        # prefix umum, jatuh ke batas lain (mis. data non-path spt "Vendor_A"/"Vendor_B").
        last_slash = p.rfind("/")
        if last_slash != -1:
            return p[:last_slash + 1]
        last_boundary = max((i for i, ch in enumerate(p) if ch in _AFFIX_BOUNDARY_CHARS), default=-1)
        return p[:last_boundary + 1]

    def _trim_suffix_to_boundary(s: str) -> str:
        first_boundary = next((i for i, ch in enumerate(s) if ch in _AFFIX_BOUNDARY_CHARS), None)
        return s[first_boundary:] if first_boundary is not None else ""

    prefix = _trim_prefix_to_boundary(prefix) if len(prefix) >= 4 else ""
    suffix = _trim_suffix_to_boundary(suffix) if len(suffix) >= 4 else ""
    if not prefix and not suffix:
        return labels

    stripped = []
    for lbl in labels:
        # Diterapkan PER LABEL: label yang tidak cocok pola (mis. outlier yang dibuang saat
        # menghitung _best_common_affix) TETAP tampil penuh apa adanya — TIDAK membatalkan
        # pemangkasan utk label LAIN yang genuinely cocok (lihat catatan bug di atas).
        s = lbl[len(prefix):] if prefix and lbl.startswith(prefix) else lbl
        s = s[:len(s) - len(suffix)] if suffix and s.endswith(suffix) else s
        stripped.append(s if s.strip() else lbl)
    return stripped


def _compute_multi_metric_items(breakdown_list: list, cat_col_name: str | None, report) -> dict:
    """PERMINTAAN USER (koreksi eksplisit atas alasan "tidak ada dimensi kedua"): utk kategori
    berupa ENTITAS (mis. aset/virtual server) yang punya BEBERAPA kolom numerik sebanding (mis.
    Illegal Requests, Legal Requests, Requests - SEMUANYA metrik per-aset dari data yang SAMA),
    dimensi kedua itu SUDAH ADA - bukan butuh kolom kategorikal sekunder (severity/status) spt
    _compute_secondary_breakdown, yang cuma cocok utk data SOC. Di sini, tiap kolom numerik
    LAIN (bukan cross-tab kategorikal) jadi 1 baris sub-item.

    Beda penting dari _compute_secondary_breakdown: sub-item DI SINI berasal dari kolom2
    BERBEDA (skala beda2, mis. Illegal Requests puluhan vs Requests jutaan) - jadi frac/target
    setiap metrik dihitung SENDIRI2 thd rentang metrik itu (max & rata-rata SEMUA entitas utk
    metrik itu, BUKAN cuma yang tampil di kartu), bukan 1 target_frac dibagi rata ke semua
    sub-item spt versi lama (yang cuma valid kalau semua sub-item 1 skala yang sama).

    Return {label_entitas: [{"label","value","frac","target_frac"}, ...]} - urutan sub-item
    mengikuti urutan kolom di breakdown_list (stabil, sama di semua kartu) - dict kosong kalau
    cat_col_name tidak dikenali sama sekali di breakdown_list (data genuinely tidak py metrik
    sebanding lain - fallback ke kartu tanpa sub-item, prinsip yang sama dipakai di seluruh
    file ini)."""
    if not breakdown_list or not cat_col_name:
        return {}
    matching = [e for e in breakdown_list if _norm_col_name(e.get("category_col")) == _norm_col_name(cat_col_name)]
    if len(matching) < 1:
        return {}
    by_label: dict = {}
    for entry in matching:
        items = entry.get("items") or []
        if len(items) < 2:
            continue
        values = [it["value"] for it in items]
        metric_max = max(values) or 1
        metric_avg = sum(values) / len(values)
        target_frac = min(1.0, metric_avg / metric_max) if metric_max else None
        metric_label = _L(report, entry["numeric_col"].replace("\n", " ").strip(), entry["numeric_col"].replace("\n", " ").strip())
        for it in items:
            by_label.setdefault(str(it["label"]), []).append({
                "label": metric_label,
                "value": it["value"],
                "frac": max(it["value"] / metric_max, 0.02) if metric_max else 0.02,
                "target_frac": target_frac,
            })
    return by_label


def _layout_nested_card_grid(n_cards: int, total_w_in: float, max_rows: int | None = None) -> dict:
    """PERMINTAAN USER (diukur dari referensi): kartu bersarang lebar TETAP ~2.24in, jarak
    nyaris 0 - BUKAN "lebar dibagi rata dari jumlah kartu" spt sebelumnya. Sampai
    _NESTED_CARD_MAX_PER_ROW (4) kartu -> 1 baris. Lebih dari itu (sampai
    _NESTED_CARD_MAX_TOTAL, 8) -> 2 baris (dibagi rata: 8->4+4, 7->4+3, 6->3+3, 5->3+2),
    MASIH lebar ~2.24in per kartu (bukan diregangkan).

    Lebar TERPAKAI kartu (N kartu terbanyak di 1 baris x lebar target) hampir pasti < lebar
    halaman penuh (kanvas kita 13.333in, kartu 4x2.24in cuma ~9in) - SISA lebar itu jadi
    "side_panel_w" (diisi panel catatan di export_pdf.py/export_ppt.py, BUKAN dibiarkan
    kosong - permintaan user eksplisit). Kalau sisa itu TERLALU SEMPIT utk jadi panel yang
    berguna (<_NESTED_CARD_SIDE_PANEL_MIN_W_IN), kartu diregangkan mengisi lebar penuh
    sebagai gantinya (tidak ada panel, tidak ada sisa terbuang percuma di kasus itu)."""
    if n_cards <= 0:
        return {"rows": [], "card_w": 0.0, "side_panel_w": 0.0}
    # BUG NYATA DIPERBAIKI (terlihat langsung di render halaman dasbor berkolom): jumlah
    # baris dulu ditentukan MURNI dari jumlah kartu, buta thd lebar yang tersedia. Di halaman
    # 1-topik selebar 13.3in itu tidak pernah terasa, tapi di KOLOM dasbor selebar ~4.2in,
    # 4 kartu tetap dipaksa sebaris -> tiap kartu jadi ~1.05in (referensi: 2.24in) & badge
    # "Tinggi/Sedang" di header terpotong tepi kartu. Sekarang berapa kartu yang muat sebaris
    # DIHITUNG dari lebar nyata, dgn lebar minimum yang masih terbaca; kalau lebarnya penuh,
    # hasilnya persis sama dgn perilaku lama (batas 4/baris tetap yang mengikat).
    per_row = max(1, int((total_w_in + _NESTED_CARD_GAP_IN)
                         / (_NESTED_CARD_MIN_W_IN + _NESTED_CARD_GAP_IN)))
    per_row = min(_NESTED_CARD_MAX_PER_ROW, per_row)
    # Halaman lebar penuh: tetap maksimal 2 baris (= _NESTED_CARD_MAX_TOTAL, 4x2). Kolom
    # dasbor yang SEMPIT tapi TINGGI boleh 3 baris - dgn 2 baris, sepertiga bawah kolom
    # tinggal kosong (terlihat di render) sementara kategorinya sebenarnya masih ada; ruang
    # itu lebih baik diisi data yang memang ada drpd diisi kartu yang diregangkan hampa.
    # `max_rows` boleh ditentukan pemanggil dari TINGGI yang benar-benar tersedia (lihat
    # _build_management_dashboard_columns_block): tanpa itu, baris bisa dipaksa 3 padahal
    # tingginya cuma cukup utk header - sub-item tiap kartu lalu hilang DIAM-DIAM (kartu jadi
    # kotak berisi angka saja). Lebih baik kartunya lebih sedikit tapi utuh isinya.
    max_rows = max_rows or (2 if per_row >= _NESTED_CARD_MAX_PER_ROW else 3)
    n_cards = min(n_cards, per_row * max_rows)
    n_rows = min(max_rows, -(-n_cards // per_row))
    base, extra = divmod(n_cards, n_rows)
    rows = [base + (1 if i < extra else 0) for i in range(n_rows)]
    max_row_n = max(rows)
    natural_w = max_row_n * _NESTED_CARD_TARGET_W_IN + (max_row_n - 1) * _NESTED_CARD_GAP_IN
    leftover = total_w_in - natural_w
    if leftover >= _NESTED_CARD_SIDE_PANEL_MIN_W_IN:
        card_w = _NESTED_CARD_TARGET_W_IN
        # Dibatasi (mis. cuma 1-2 kartu -> leftover bisa >10in) - panel catatan selebar itu
        # kelihatan aneh (kotak pendek yang sangat lebar) drpd terasa "kolom di sisi kanan".
        # Sisa di luar batas ini dibiarkan sbg margin kanan (kasus langka, kategori sedikit).
        side_panel_w = min(leftover - _NESTED_CARD_ROW_GAP_IN, 4.5)
    else:
        card_w = (total_w_in - (max_row_n - 1) * _NESTED_CARD_GAP_IN) / max_row_n
        side_panel_w = 0.0
    return {"rows": rows, "card_w": card_w, "side_panel_w": max(0.0, side_panel_w)}


def _kpi_card_widths(cards: list, total_w_in: float, gap_in: float) -> list:
    """Lebar tiap kartu ringkasan KPI (permintaan user poin 2: "Tentukan lebar dari jumlah
    dan panjang isi tiap kolom" — BUKAN dibagi rata) — proporsional dari estimasi panjang
    label+nilai kartu itu sendiri, dgn lantai minimum (18% lebar tersedia) supaya kartu
    berisi pendek tidak collapse terlalu sempit. Fungsi bersama (bukan dihitung ulang
    masing2 exporter) supaya lebar kartu IDENTIK persis di PDF & PPT dari kartu yang sama."""
    n = len(cards)
    if n == 0:
        return []
    weights = [max(10.0, len(c.get("label", "")) + len(str(c.get("value", ""))) * 1.6) for c in cards]
    total_weight = sum(weights)
    avail = total_w_in - gap_in * (n - 1)
    min_w = avail * 0.18
    widths = [max(min_w, avail * w / total_weight) for w in weights]
    scale = avail / sum(widths) if sum(widths) else 1.0
    return [w * scale for w in widths]


_INSIGHT_LAYER_GAP_IN = 0.2


def _layout_insight_layers(block: dict, avail_h_in: float, total_w_in: float) -> dict:
    """Tinggi (inci) lapis "kpi" & "detail" halaman insight (permintaan user poin 1 — lapis
    "notes" TIDAK dihitung di sini: mengalir normal SETELAH keduanya lewat _note_box_html/
    add_note_box, yang sudah dinamis dari isi teksnya sendiri sejak perbaikan E3, jadi tidak
    perlu dipaksa masuk rencana tinggi tetap di sini). "kpi" tinggi TETAP (_INSIGHT_KPI_H_IN)
    — BUG DIPERBAIKI (ditemukan lewat verifikasi render langsung): sempat dicoba diregangkan
    scr proporsional utk "mengisi sisa halaman", hasilnya kartu KPI jadi kotak nyaris kosong
    raksasa kalau isinya cuma 1 baris angka. "detail" (kartu bersarang) tingginya dari
    KEBUTUHAN SUNGGUHAN (header + jumlah sub-item TERBANYAK di antara kartu, dibatasi
    3.0in) — bukan dipaksa 3.0in penuh walau sub-itemnya cuma 1-2, alasan sama (kartu jadi
    berongga kosong di bawah sub-item kalau dipaksakan). Sisa ruang (kalau ada, setelah kedua
    lapis di atas dapat tinggi WAJAR-nya) dipakai melebarkan JARAK antar lapis (maks 0,6in)
    supaya halaman tetap terasa penuh/seimbang TANPA meregangkan isi kartu jadi berongga."""
    has_kpi = bool(block.get("kpi_summary"))
    cat_details = block.get("category_details") or []
    main_chart_tile = block.get("main_chart_tile")
    has_detail = bool(cat_details) or bool(main_chart_tile)
    heights = {}
    if has_kpi:
        heights["kpi"] = _INSIGHT_KPI_H_IN
    if main_chart_tile:
        # PERMINTAAN USER ("hapus jalur management_visual_dashboard, semua lewat insight"):
        # tile "space-hungry" (radar/heatmap/period_compare, lihat _build_chart_insight_page)
        # TIDAK py kartu/sub-item utk dihitung kebutuhan tingginya - HANYA 1 chart tunggal yang
        # SECARA ALAMI bisa diskalakan mengisi berapa pun ruang yang tersisa (lewat parameter
        # `scale`, lihat _mgmt_tile_chart_html) - jadi "detail" di sini SELALU mengambil semua
        # sisa ruang stlh jatah "kpi", bukan dihitung dari kebutuhan konten spt kartu.
        reserved_for_kpi = heights.get("kpi", 0.0) + (_INSIGHT_LAYER_GAP_IN if has_kpi else 0.0)
        heights["detail"] = max(_INSIGHT_DETAIL_H_IN, avail_h_in - reserved_for_kpi)
    elif has_detail:
        # PERMINTAAN USER (sampai 8 kartu, 2 baris x 4 kalau kategorinya banyak - lihat
        # _layout_nested_card_grid): tinggi "detail" sekarang PER-BARIS dikali jumlah baris
        # (bukan cuma 1 baris spt sebelumnya) - supaya kartu di grid 2 baris dapat tinggi
        # SUNGGUHAN yang mencerminkan berapa banyak baris yang perlu muat, bukan menghitung
        # seolah selalu 1 baris lalu diam2 kartu jadi terlalu pendek/terpotong saat digambar
        # 2 baris nyatanya (grid & tinggi HARUS dari sumber yang sama, dilihat berdampingan).
        max_items = max((len(c.get("sub_items") or []) for c in cat_details), default=0)
        item_h_in = _NESTED_CARD_SUBITEM_LINE1_H_IN + _NESTED_CARD_SUBITEM_BAR_H_IN + _NESTED_CARD_SUBITEM_GAP_IN
        n_rows = len(_layout_nested_card_grid(len(cat_details), total_w_in)["rows"]) or 1
        per_card_natural = _NESTED_CARD_HEADER_H_IN + max_items * item_h_in + 0.24
        per_card_min = _NESTED_CARD_HEADER_H_IN + 0.3
        natural_total = per_card_natural * n_rows + _NESTED_CARD_ROW_GAP_IN * (n_rows - 1)
        min_total = per_card_min * n_rows + _NESTED_CARD_ROW_GAP_IN * (n_rows - 1)
        # BUG NYATA DITEMUKAN (verifikasi visual langsung — render PDF sungguhan): plafon TETAP
        # _INSIGHT_DETAIL_H_IN (3.0in) dulu dipakai APA ADANYA tanpa peduli n_rows - utk grid 2
        # baris (5-8 kartu), 3.0in dibagi 2 baris cuma nyisakan ~1.4in/kartu, KURANG utk 3
        # sub-item metrik (permintaan poin 2: semua kolom numerik sebanding tampil) - sub-item
        # ke-3 dst KEPOTONG walau halaman MASIH py ruang kosong berlimpah di bawahnya (kartu
        # dipotong duluan, bukan krn ruang genuinely habis). Plafon SEKARANG dinamis: minimal
        # tetap 3.0in (drpd 1 baris yang sudah pas jadi lebih sempit), tapi BOLEH tumbuh sampai
        # SISA ruang halaman stlh jatah "kpi" (& jarak ke situ) kalau kebutuhan naturalnya
        # genuinely lebih dari 3.0in - detail BOLEH pakai semua sisa itu drpd dipotong plafon
        # yang lebih sempit dari ruang yang benar2 tersedia.
        reserved_for_kpi = heights.get("kpi", 0.0) + (_INSIGHT_LAYER_GAP_IN if has_kpi else 0.0)
        dynamic_cap = max(_INSIGHT_DETAIL_H_IN, avail_h_in - reserved_for_kpi)
        heights["detail"] = min(dynamic_cap, max(natural_total, min_total))
    n = len(heights)
    if n == 0:
        return {"gap": _INSIGHT_LAYER_GAP_IN}
    gap = _INSIGHT_LAYER_GAP_IN
    leftover = avail_h_in - sum(heights.values()) - gap * (n - 1)
    if n > 1 and leftover > 0:
        gap = min(0.6, gap + leftover / (n - 1))
    return {"gap": gap, **heights}


def _title_matches_displayed(headline, entity_names: list, dim_label: str | None) -> bool:
    """True kalau judul genuinely menyinggung DIMENSI atau ENTITAS yang benar-benar
    ditampilkan di halaman ini."""
    if not headline:
        return False
    low = str(headline).lower()
    if dim_label and str(dim_label).lower() in low:
        return True
    return any(n and str(n).lower() in low for n in entity_names[:8])


def _synth_insight_title(report, dim_label: str | None, items: list, total: int) -> str:
    """Judul SINTESIS dihitung dari dimensi & angka yang BENAR-BENAR digambar di halaman ini.

    BUG NYATA DIPERBAIKI (dilaporkan user dari pemeriksaan laporan langsung): judul halaman
    diambil dari kalimat AI utk tile itu (`tile["caption"]`), sementara kartu-kartunya diisi
    dimensi lain yang genuinely dihitung ulang di sini - hasilnya judul bicara "vendor CV
    Surya Elektrik Industri" padahal kartunya berisi METODE PENGADAAN, atau judul bicara
    "Departemen SDM" padahal kartunya berisi BULAN. Kalimat AI dipertahankan HANYA kalau
    genuinely menyinggung dimensi/entitas yang ditampilkan (lihat _title_matches_displayed);
    kalau tidak, judul dibangun dari data yang tampil - sekaligus otomatis pendek (permintaan
    user: judul jangan dipotong "..." lagi)."""
    top_name, top_val = items[0]
    pct = round(top_val / total * 100) if total else 0
    dim = dim_label or _L(report, "kategori", "categories")
    return _L(
        report,
        f"{top_name} memimpin {dim} dengan {pct}% dari {_fmt_count(total, False)} data",
        f"{top_name} leads {dim} with {pct}% of {_fmt_count(total, True)} records",
    )


def _build_insight_page(tile: dict, report, sec_domain: bool, parsed_data: list, severity_col: str | None, status_col: str | None, numeric_breakdown: list | None = None) -> dict | None:
    """Bangun 1 halaman "insight" mendalam dari 1 visual tile (permintaan user, ganti total
    halaman dashboard grid): lapis ringkasan KPI (3 kartu) + lapis detail per kategori (sampai
    8 kartu bersarang, 2 baris x 4 kalau kategorinya banyak — lihat _layout_nested_card_grid)
    + lapis catatan (kategori sisanya, kalimat utuh). Return None kalau tile ini genuinely
    tidak punya daftar kategori sama sekali (mis. kpi_gauge tanpa breakdown apa pun) DAN
    bukan kpi_gauge — dilewati sepenuhnya, bukan halaman kosong.

    Sub-item tiap kartu (permintaan user, koreksi eksplisit atas alasan "tidak ada dimensi
    kedua" yang keliru): dicoba DUA sumber, urutan prioritas —
    (1) cross-tab kategorikal SUNGGUHAN (_compute_secondary_breakdown, severity/status) kalau
        kolom sekundernya diketahui (jalur SOC lama, tidak berubah).
    (2) kalau (1) kosong (severity/status tidak ada — lazim di data operasional NON-SOC spt
        BIG-IP): kolom NUMERIK LAIN yang sebanding utk entitas yang sama (mis. Illegal
        Requests/Legal Requests/Requests per aset — SEMUANYA metrik asli dari data yang sama,
        dimensi kedua yang genuinely sudah ada, bukan dikarang) via
        _compute_multi_metric_items(numeric_breakdown, ...)."""
    items = _tile_rank_items(tile)
    _ien = is_english(report)
    unit = _L(report, "kejadian", "events") if sec_domain else _L(report, "data", "entries")
    headline = _shorten_to_caption(tile["caption"], max_sentences=1) if tile.get("caption") else tile.get("title")
    if not items:
        if tile.get("tile_kind") == "kpi_gauge":
            pct = tile.get("pct", 0)
            # PERMINTAAN USER (pengecualian kepadatan HANYA sah kalau py catatan analitis
            # genuinely ada): dulu "notes" selalu [] di sini (data tile ini sebelumnya cuma
            # "pct") - sekarang tile membawa data pendukung asli (gauge_dim/top_value/
            # top_count/total_records/second_item, lihat pemanggil di build_management_
            # report_blocks), dipakai bangun >=1 catatan GENUINE, bukan dikarang.
            gauge_dim = tile.get("gauge_dim")
            top_value, top_count = tile.get("top_value"), tile.get("top_count")
            total = tile.get("total_records")
            notes = []
            if gauge_dim and top_value is not None and total:
                notes.append(_L(
                    report,
                    f"{top_value} tercatat {_fmt_count(top_count, _ien)} dari {_fmt_count(total, _ien)} total data pada dimensi {gauge_dim}.",
                    f"{top_value} recorded {_fmt_count(top_count, _ien)} of {_fmt_count(total, _ien)} total records on the {gauge_dim} dimension.",
                ))
            second_item = tile.get("second_item")
            if second_item and total:
                second_pct = round(second_item["count"] / total * 100)
                notes.append(_L(
                    report,
                    f"Di posisi kedua, {second_item['value']} mencatat {_fmt_count(second_item['count'], _ien)} data ({second_pct}%).",
                    f"In second place, {second_item['value']} recorded {_fmt_count(second_item['count'], _ien)} records ({second_pct}%).",
                ))
            return {
                "kind": "management_insight_page",
                "title": headline,
                "kpi_summary": [
                    {"label": _L(report, "PENCAPAIAN", "ACHIEVEMENT"), "value": f"{pct}%"},
                    {"label": _L(report, "SISA", "REMAINING"), "value": f"{max(0, 100 - pct)}%"},
                ],
                "category_details": [],
                # PERMINTAAN USER (hal.05 mengulang hal.01): halaman gauge ini TIDAK punya
                # category_details, jadi himpunan entitasnya kosong & pemeriksa irisan entitas
                # (_insight_page_entity_set) tidak pernah bisa mencocokkannya dgn halaman lain -
                # halaman yang isinya SUDAH tampil di halaman lain ("E-Katalog 38%") tetap lolos
                # jadi halaman penuh sendiri. Entitas & persentasenya disimpan eksplisit di sini
                # supaya bisa ikut diperiksa (lihat _merge_overlapping_insight_pages).
                "gauge_entity": top_value,
                "gauge_pct": pct,
                "notes": notes,
                "chart_category_count": 1,
            }
        return None
    items = sorted(items, key=lambda kv: -kv[1])
    total = sum(v for _, v in items) or 1
    _dim_label = humanize_label(tile.get("cat_col_name") or "", None) if tile.get("cat_col_name") else None
    if not _title_matches_displayed(headline, [n for n, _ in items], _dim_label):
        headline = _synth_insight_title(report, _dim_label, items, total)
    kpi_summary = [
        {"label": _L(report, "TOTAL", "TOTAL"), "value": _fmt_count(total, _ien)},
        {"label": _L(report, "TERATAS", "TOP"), "value": f"{items[0][0]} ({round(items[0][1] / total * 100)}%)"},
        {"label": _L(report, "KATEGORI", "CATEGORIES"), "value": str(len(items))},
    ]

    cat_col = tile.get("cat_col_name")
    if cat_col and cat_col == severity_col:
        secondary_col = status_col
    elif cat_col and cat_col == status_col:
        secondary_col = severity_col
    else:
        secondary_col = severity_col or status_col

    multi_metric_by_label = _compute_multi_metric_items(numeric_breakdown or [], cat_col, report)

    max_val = items[0][1] or 1
    shown_items = items[:_NESTED_CARD_MAX_TOTAL]
    display_names = _strip_common_affix([name for name, _ in shown_items])
    category_details = []
    for (name, val), display_name in zip(shown_items, display_names):
        frac = val / max_val
        sub_items: list = []
        breakdown = _compute_secondary_breakdown(parsed_data, cat_col, name, secondary_col)
        if breakdown:
            sub_max = breakdown[0][1] or 1
            target_frac = (sum(v for _, v in breakdown) / len(breakdown)) / sub_max
            sub_items = [
                {"label": sub_name, "value": sub_val, "frac": sub_val / sub_max, "target_frac": target_frac}
                for sub_name, sub_val in breakdown
            ]
        elif multi_metric_by_label.get(name):
            sub_items = multi_metric_by_label[name]
        category_details.append({
            "name": display_name, "score": _fmt_count(val, _ien),
            "badge": _classify_relative_tier(frac, report),
            "sub_items": sub_items,
            # "raw_name"/"value" TIDAK dipakai render (cuma "name"/"score" yang dipakai) -
            # dipertahankan mentah (sebelum _strip_common_affix/_fmt_count) khusus utk
            # _merge_overlapping_insight_pages & _compute_merged_page_extra_notes di bawah,
            # yang butuh identitas entitas & angka ASLI yang bisa dibandingkan lintas halaman/
            # dihitung ulang - bukan versi tampilan yang sudah diformat/disingkat.
            "raw_name": name, "value": val,
        })

    rest = items[_NESTED_CARD_MAX_TOTAL:_NESTED_CARD_MAX_TOTAL + 4]
    notes = [
        _L(
            report,
            f"{name} mencatat {_fmt_count(val, _ien)} {unit} ({round(val / total * 100)}% dari total).",
            f"{name} recorded {_fmt_count(val, _ien)} {unit} ({round(val / total * 100)}% of the total).",
        )
        for name, val in rest
    ]
    return {
        "kind": "management_insight_page", "title": headline,
        "kpi_summary": kpi_summary, "category_details": category_details, "notes": notes,
    }


def _build_chart_insight_page(tile: dict, report) -> dict | None:
    """Varian halaman insight KHUSUS tile "space-hungry" (kpi_radar/time_heatmap/
    period_compare, lihat _SPACE_HUNGRY_TILE_KINDS) — PERMINTAAN USER ("hapus jalur
    management_visual_dashboard, arahkan semuanya ke jalur insight"): 3 jenis tile ini TIDAK
    punya daftar ENTITAS yang bisa dijadikan kartu bersarang (radar cuma beberapa SUMBU/
    indikator, heatmap grid hari x jam, period_compare 2 deret angka) — jadi dipakai bentuk
    halaman insight yang SAMA (judul -> ringkasan KPI -> visual utama -> catatan) tapi lapis
    "detail"-nya berisi CHART ASLI tile itu sendiri (radar/heatmap/grouped-bar, digambar
    _mgmt_tile_chart_html/native chart PPT yang SUDAH ada, cuma diposisikan ulang), bukan
    grid kartu. Ringkasan KPI & catatan dihitung deterministik dari data chart yang SAMA
    persis yang digambar (bukan analisis baru) — pola yang sama dipakai _build_insight_page."""
    _ien = is_english(report)
    kind = tile["tile_kind"]
    headline = _shorten_to_caption(tile["caption"], max_sentences=1) if tile.get("caption") else tile.get("title")
    if kind == "kpi_radar":
        axes, values = tile.get("axes") or [], tile.get("values") or []
        if len(axes) < 3:
            return None
        category_count = len(axes)
        avg = sum(values) / len(values)
        top_i = max(range(len(values)), key=lambda i: values[i])
        low_i = min(range(len(values)), key=lambda i: values[i])
        kpi_summary = [
            {"label": _L(report, "RATA-RATA", "AVERAGE"), "value": f"{avg:.1f}"},
            {"label": _L(report, "TERTINGGI", "HIGHEST"), "value": f"{axes[top_i]} ({values[top_i]:.0f})"},
            {"label": _L(report, "INDIKATOR", "INDICATORS"), "value": str(len(axes))},
        ]
        # PERMINTAAN USER: tiap sumbu radar ini SUDAH dinormalisasi ke skala 0-100 (rata-rata
        # sbg % dari nilai maksimum kolom itu sendiri, lihat _compute_kpi_radar) SUPAYA
        # indikator berbeda satuan (mis. Rupiah vs persentase) bisa dibandingkan di 1 chart yang
        # sama - TAPI tanpa keterangan, "78"/"30" bisa disalahartikan sbg nilai Rupiah/persen
        # ASLI (terutama di laporan yang halaman lainnya genuinely menampilkan Rupiah/persen
        # asli, spt insight per-kategori) — BUKAN bug baru, cuma belum pernah diberi label.
        # Catatan ini SELALU ditampilkan (bukan cuma kalau satuannya kebetulan campuran) krn
        # "rata-rata sbg % dari maksimum sendiri" bukan nilai asli even utk sesama kolom
        # bersatuan sama. Ini beda dari & TIDAK digantikan oleh aturan max/min>10 di
        # _compute_kpi_radar (itu jaga BENTUK radar dari sumbu yang nyaris kosong secara visual
        # - keduanya soal berbeda, radar bisa bentuknya valid & tetap butuh label ini).
        notes = [_L(
            report,
            "Nilai pada radar ini adalah skor relatif 0-100 (rata-rata sbg persentase dari nilai maksimum tiap indikator), BUKAN nilai asli dalam satuan aslinya (Rupiah/persen/dst).",
            "Values on this radar are relative 0-100 scores (each indicator's average as a percentage of its own maximum), NOT the raw value in its native unit (currency/percent/etc.).",
        )]
        notes.append(_L(
            report,
            f"{axes[top_i]} mencatat skor tertinggi ({values[top_i]:.0f}), sementara {axes[low_i]} paling rendah ({values[low_i]:.0f}) — selisih {values[top_i] - values[low_i]:.0f} poin.",
            f"{axes[top_i]} recorded the highest score ({values[top_i]:.0f}), while {axes[low_i]} was the lowest ({values[low_i]:.0f}) — a gap of {values[top_i] - values[low_i]:.0f} points.",
        ))
        # PERMINTAAN USER (density: halaman insight bertopik chart tunggal, tanpa kartu
        # bersarang, genuinely lebih tipis drpd halaman berkartu — bukan alasan utk kosong):
        # sebut skor tiap SUMBU scr eksplisit sbg kalimat (bukan cuma tersirat lewat bentuk
        # poligon radar) - informasi ASLI yang sama dgn yang digambar, cuma dinyatakan scr
        # tekstual di sini, kartu manapun (di halaman ini tidak ada kartu) belum menyebutnya.
        for i, ax in enumerate(axes):
            if i in (top_i, low_i):
                continue
            dev = values[i] - avg
            arah = _L(report, "di atas", "above") if dev >= 0 else _L(report, "di bawah", "below")
            notes.append(_L(
                report,
                f"{ax} mencatat skor {values[i]:.0f}, {abs(round(dev))} poin {arah} rata-rata seluruh indikator.",
                f"{ax} scored {values[i]:.0f}, {abs(round(dev))} points {arah} the average across all indicators.",
            ))
    elif kind == "period_compare":
        cats = tile.get("categories") or []
        series_a, series_b = tile.get("series_a") or [], tile.get("series_b") or []
        if not cats:
            return None
        category_count = len(cats)
        total_a, total_b = sum(series_a), sum(series_b)
        pct_change = round((total_b - total_a) / total_a * 100, 1) if total_a else 0.0
        swing_i = max(range(len(cats)), key=lambda i: abs(series_b[i] - series_a[i]))
        kpi_summary = [
            {"label": tile.get("label_a", "A").upper(), "value": _fmt_count(total_a, _ien)},
            {"label": tile.get("label_b", "B").upper(), "value": _fmt_count(total_b, _ien)},
            {"label": _L(report, "PERUBAHAN", "CHANGE"), "value": f"{pct_change:+.1f}%"},
        ]
        notes = [_L(
            report,
            f"{cats[swing_i]} mengalami perubahan terbesar antar 2 periode ({_fmt_count(series_a[swing_i], _ien)} → {_fmt_count(series_b[swing_i], _ien)}).",
            f"{cats[swing_i]} saw the largest change between the two periods ({_fmt_count(series_a[swing_i], _ien)} → {_fmt_count(series_b[swing_i], _ien)}).",
        )]
        # PERMINTAAN USER (density): sebut perubahan tiap kategori LAIN scr eksplisit juga
        # (bukan cuma yang terbesar) - angka ASLI yang sama dgn yang digambar chart-nya.
        for i, cat in enumerate(cats):
            if i == swing_i:
                continue
            delta = series_b[i] - series_a[i]
            arah = _L(report, "naik", "up") if delta > 0 else (_L(report, "turun", "down") if delta < 0 else _L(report, "stabil", "unchanged"))
            notes.append(_L(
                report,
                f"{cat} {arah} dari {_fmt_count(series_a[i], _ien)} menjadi {_fmt_count(series_b[i], _ien)} antar 2 periode.",
                f"{cat} went {arah} from {_fmt_count(series_a[i], _ien)} to {_fmt_count(series_b[i], _ien)} between the two periods.",
            ))
    elif kind == "time_heatmap":
        day_labels, hour_labels, grid = tile.get("day_labels") or [], tile.get("hour_labels") or [], tile.get("grid") or []
        if not grid:
            return None
        category_count = sum(1 for row in grid if sum(row) > 0)
        total = sum(sum(row) for row in grid) or 1
        peak_r, peak_c = max(
            ((r, c) for r in range(len(grid)) for c in range(len(grid[r]))),
            key=lambda rc: grid[rc[0]][rc[1]],
        )
        kpi_summary = [
            {"label": _L(report, "TOTAL", "TOTAL"), "value": _fmt_count(total, _ien)},
            {"label": _L(report, "PUNCAK", "PEAK"), "value": f"{day_labels[peak_r]} {hour_labels[peak_c]}"},
            {"label": _L(report, "HARI DIPANTAU", "DAYS TRACKED"), "value": str(len(day_labels))},
        ]
        peak_val = grid[peak_r][peak_c]
        notes = [_L(
            report,
            f"Kombinasi {day_labels[peak_r]} pukul {hour_labels[peak_c]} paling padat, {_fmt_count(peak_val, _ien)} dari {_fmt_count(total, _ien)} data ({round(peak_val / total * 100)}%).",
            f"{day_labels[peak_r]} at {hour_labels[peak_c]} is the busiest combination, {_fmt_count(peak_val, _ien)} of {_fmt_count(total, _ien)} records ({round(peak_val / total * 100)}%).",
        )]
        # PERMINTAAN USER (density): sebut total tiap HARI scr eksplisit (bukan cuma 1 sel
        # terpadat) - angka ASLI yang sama dgn baris grid yang digambar heatmap-nya.
        day_totals = [(day_labels[r], sum(grid[r])) for r in range(len(day_labels)) if r != peak_r]
        for day_label, day_total in sorted(day_totals, key=lambda dt: -dt[1]):
            if day_total <= 0:
                continue
            notes.append(_L(
                report,
                f"{day_label} mencatat {_fmt_count(day_total, _ien)} data ({round(day_total / total * 100)}% dari total).",
                f"{day_label} recorded {_fmt_count(day_total, _ien)} records ({round(day_total / total * 100)}% of the total).",
            ))
    else:
        return None
    return {
        "kind": "management_insight_page", "title": headline,
        "kpi_summary": kpi_summary, "category_details": [], "notes": notes,
        "main_chart_tile": tile,
        # PERMINTAAN USER (pengecualian kepadatan berbasis DATA, bukan JENIS chart - "radar
        # dgn 8 kategori tetap harus penuh"): jumlah kategori/sumbu ASLI yang mendasari chart
        # ini, dipakai tes kepadatan menilai apakah halaman ini LAYAK jadi pengecualian
        # (<5 kategori) atau harus tetap dipadatkan spt biasa (>=5).
        "chart_category_count": category_count,
    }


def _is_rich_insight_page(page: dict) -> bool:
    """Kriteria "topik ini layak dapat halaman insight mendalam sendiri" (PERMINTAAN USER
    LANJUTAN: "tujuan utamanya kepadatan, bukan kedalaman per halaman" — versi sebelumnya
    SETIAP topik dapat halaman sendiri tanpa syarat, banyak yang berakhir separuh kosong krn
    detailnya genuinely tipis): minimal 3 kartu kategori DI LAPIS DETAIL, DAN mayoritas
    (>50%) kartu itu py rincian sub-kategori nyata (dari cross-tab sungguhan, lihat
    _compute_secondary_breakdown) — bukan cuma header+skor+badge kosongan. Topik yang tidak
    lolos digabung ke halaman kolom lain (_build_column_dashboard_blocks) drpd berdiri
    sendiri stengah kosong."""
    cat_details = page.get("category_details") or []
    if len(cat_details) < 3:
        return False
    with_sub_items = sum(1 for c in cat_details if c.get("sub_items"))
    return with_sub_items > len(cat_details) / 2


_INSIGHT_PAGE_OVERLAP_THRESHOLD = 0.7


def _insight_page_entity_set(page: dict) -> frozenset:
    """Himpunan entitas (nama ASLI, lihat "raw_name" di _build_insight_page) yang ditampilkan
    sbg kartu di 1 halaman insight — dipakai _merge_overlapping_insight_pages/tes kepadatan
    utk mendeteksi 2 halaman yang KEBETULAN menampilkan set entitas yang (nyaris) sama persis,
    cuma disusun ulang beda urutan/metrik (PERMINTAAN USER, dibuktikan lewat audit nyata: 6
    halaman "insight" berbeda topik ternyata menampilkan 8 aset yang PERSIS sama - elemen yang
    banyak itu pengulangan, bukan kepadatan sungguhan)."""
    return frozenset(c.get("raw_name") for c in (page.get("category_details") or []) if c.get("raw_name"))


def _entity_set_overlap(set_a: frozenset, set_b: frozenset) -> float:
    """Jaccard similarity (irisan/gabungan) - 1.0 kalau identik persis, 0.0 kalau tidak
    beririsan sama sekali. Dipilih drpd "irisan/set terkecil" (containment) supaya 2 halaman
    yang salah satunya py 1-2 entitas TAMBAHAN di luar yang lain tidak otomatis dianggap
    "sama" cuma krn subset kecil-nya penuh terkandung - Jaccard menghukum PERBEDAAN UKURAN
    himpunan juga, lebih ketat & lebih sesuai maksud "himpunan kategori yang SAMA"."""
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union else 0.0


def _compute_merged_page_extra_notes(category_details: list, report) -> list:
    """PERMINTAAN USER: setelah halaman duplikat digabung, isi ruang catatan dgn INFORMASI
    YANG BENAR-BENAR BARU (bukan mengulang angka yang sudah ada di kartu) — kriterianya
    eksplisit: "layak ditambahkan hanya kalau isinya tidak bisa dibaca dari kartu yang sudah
    ada". Dua turunan GENUINELY baru dihitung di sini (bukan dikarang, murni dari angka yang
    SAMA persis dgn yang sudah ada di sub_items tiap kartu, cuma DIOLAH jadi sudut pandang
    yang belum eksplisit tertulis di kartu manapun):

    (1) RASIO antar 2 metrik pertama tiap entitas (mis. Illegal:Legal) - kartu menampilkan
        KEDUA angka mentahnya berdampingan, tapi tidak menyebut rasionya scr eksplisit -
        pembaca harus menghitung sendiri kalau mau tahu. Entitas dgn rasio TERTINGGI disebut.
    (2) PENYIMPANGAN terbesar dari rata-rata utk metrik utama (skor/badge kartu) - tiap bar
        SUDAH menampilkan garis penanda rata-rata scr visual, tapi tidak ada satu pun kartu
        yang secara eksplisit menyatakan "yang paling menyimpang adalah X sebesar Y%" sbg
        kalimat - ini sudut pandang RANKING lintas-kartu, bukan properti 1 kartu individual.

    Return [] (bukan error) kalau datanya tidak cukup utk salah satu turunan (mis. cuma 1
    entitas, atau sub_items kurang dari 2 metrik) — prinsip yang sama dipakai di seluruh file
    ini: JANGAN memaksakan blok yang datanya tidak genuinely ada."""
    notes = []
    if len(category_details) < 2:
        return notes

    # (1) Rasio metrik pertama:kedua tiap entitas dgn >=2 sub_items metrik.
    ratios = []
    for c in category_details:
        subs = c.get("sub_items") or []
        if len(subs) >= 2 and subs[1]["value"]:
            ratios.append((c["name"], subs[0]["label"], subs[1]["label"], subs[0]["value"] / subs[1]["value"]))
    if len(ratios) >= 2:
        top_name, num_label, den_label, top_ratio = max(ratios, key=lambda r: r[3])
        notes.append(_L(
            report,
            f"{top_name} mencatat rasio {num_label}:{den_label} tertinggi ({top_ratio:.2f}) di antara seluruh entitas yang ditampilkan.",
            f"{top_name} recorded the highest {num_label}:{den_label} ratio ({top_ratio:.2f}) among all entities shown.",
        ))

    # (2) Penyimpangan terbesar dari garis rata-rata (target_frac) utk metrik UTAMA kartu
    # (frac dihitung thd nilai tertinggi, disimpan di "value"/badge - dipakai ulang sub_items[0]
    # sbg proksi krn itu metrik yang SAMA dipakai di seluruh kartu halaman ini).
    deviations = []
    for c in category_details:
        subs = c.get("sub_items") or []
        if subs and subs[0].get("target_frac") is not None:
            dev = subs[0]["frac"] - subs[0]["target_frac"]
            deviations.append((c["name"], subs[0]["label"], dev))
    if len(deviations) >= 2:
        top_name, metric_label, top_dev = max(deviations, key=lambda d: abs(d[2]))
        arah = _L(report, "di atas", "above") if top_dev > 0 else _L(report, "di bawah", "below")
        notes.append(_L(
            report,
            f"{top_name} menyimpang paling jauh dari rata-rata {metric_label} seluruh entitas, {abs(round(top_dev * 100))}% {arah} rata-rata.",
            f"{top_name} deviates the most from the average {metric_label} across all entities, {abs(round(top_dev * 100))}% {arah} average.",
        ))
    return notes


_DASH_TOPICS_PER_PAGE = 3
_DASH_MIN_VISUALS_PER_PAGE = 3


def _note_is_readable_from_visual(note: str, column: dict) -> bool:
    """PERMINTAAN USER (poin 4): butir catatan DIBUANG kalau isinya bisa dibaca langsung dari
    visual di halaman yang sama - mis. heatmap sudah menunjukkan "Selasa 6", lalu catatannya
    menulis "Selasa mencatat 6 data". Catatan seharusnya berisi hal yang TIDAK terlihat di
    chart (sebab, tindak lanjut, konteks), bukan membacakan ulang kotak di sebelahnya.

    Dideteksi scr konservatif: butir dibuang HANYA kalau ia menyebut nama entitas/label yang
    memang sudah tergambar DAN angkanya juga sudah tergambar - bukan sekadar mirip."""
    text = str(note or "").strip().lower()
    if not text:
        return True
    # `column` boleh SATU kolom atau SELURUH kolom di halaman yang sama. Sejak beberapa topik
    # dikemas berdampingan, catatan di kolom 2 bisa membacakan ulang apa yang tergambar di
    # kolom 1/3 - dari sisi PEMBACA itu tetap "sudah terlihat di halaman ini", jadi yang
    # dibandingkan harus semua yang tergambar di halaman, bukan cuma kolom asal catatannya.
    _cols = column if isinstance(column, list) else [column]
    drawn_labels, drawn_values = set(), set()

    def _tambah_total(nilai_kolom):
        # TOTAL nilai satu kolom ikut dianggap "sudah terlihat": catatan spt "10 dari 42 data"
        # menyebut 42 yang memang bukan salah satu sel, tapi jumlah SELURUH sel di visual itu -
        # pembaca tidak mendapat apa pun yang baru. Dijumlahkan PER KOLOM, bukan lintas halaman:
        # menjumlahkan semua kolom sekaligus menghasilkan angka yang tidak berarti apa-apa &
        # penyaringnya jadi meleset (terbukti waktu dicoba: catatan heatmap tetap lolos).
        angka = []
        for v in nilai_kolom:
            try:
                angka.append(int(v))
            except ValueError:
                pass
        if angka:
            drawn_values.add(str(sum(angka)))

    for column in _cols:
      # DAFTAR, bukan himpunan: nilai yang kembar (heatmap laporan 183 py TIGA sel bernilai 6)
      # harus ikut terhitung semua waktu dijumlahkan. Dgn himpunan, totalnya jadi 25 bukan 42
      # & catatan "10 dari 42 data" tetap lolos - persis yang terjadi waktu pertama dicoba.
      _nilai_kolom = []
      for c in (column.get("category_details") or []):
          if c.get("raw_name"):
              drawn_labels.add(str(c["raw_name"]).lower())
          if c.get("value") is not None:
              _nilai_kolom.append(re.sub(r"[^\d]", "", f"{c['value']}"))
              drawn_values.add(re.sub(r"[^\d]", "", f"{c['value']}"))
      tile = column.get("main_chart_tile") or {}
      for key in ("categories", "axes", "day_labels"):
          for lbl in (tile.get(key) or []):
              drawn_labels.add(str(lbl[0] if isinstance(lbl, (list, tuple)) else lbl).lower())
      for key in ("values", "series_a", "series_b"):
          for v in (tile.get(key) or []):
              _nilai_kolom.append(re.sub(r"[^\d]", "", f"{v}"))
              drawn_values.add(re.sub(r"[^\d]", "", f"{v}"))
      for row in (tile.get("grid") or []):
          for v in row:
              _nilai_kolom.append(re.sub(r"[^\d]", "", f"{v}"))
              drawn_values.add(re.sub(r"[^\d]", "", f"{v}"))
      _tambah_total([v for v in _nilai_kolom if v])
    drawn_values.discard("")
    label_hit = any(lbl and lbl in text for lbl in drawn_labels)
    if not label_hit:
        return False
    # PERSENTASE dibuang dari pemeriksaan: "6 data (14% dari total)" - 14 itu 6 dibagi total,
    # bukan angka baru. Menghitungnya sbg angka yang belum tergambar membuat SETIAP catatan
    # berpersentase lolos, padahal justru bentuk itu yang paling sering membacakan ulang chart.
    text_wo_pct = re.sub(r"\d+(?:[.,]\d+)?\s*%", " ", text)
    nums_in_note = set(re.findall(r"\d+", text_wo_pct))
    return bool(nums_in_note) and nums_in_note.issubset(drawn_values | {"100"})


def _potong_di_batas_kata(teks: str, maks: int) -> str:
    """Potong di spasi terdekat & beri elipsis - JANGAN di tengah kata.

    KOREKSI USER (terlihat di render: "PT Sarana Instrumentasi Utam"): potongan keras di
    posisi ke-N menghilangkan huruf tanpa penanda apa pun, jadi pembaca tidak tahu namanya
    terpotong & bisa salah membaca nama entitasnya."""
    teks = teks.strip()
    if len(teks) <= maks:
        return teks
    potong = teks[:maks].rstrip()
    spasi = potong.rfind(" ")
    if spasi >= maks * 0.5:
        potong = potong[:spasi]
    return potong.rstrip(" ,.-") + "…"


def _pack_insight_pages_into_columns(blocks: list, report) -> list:
    """PERMINTAAN USER (perombakan kepadatan): berhenti membuat 1 halaman utk 1 visual.
    Halaman insight berturut-turut dikemas jadi SATU halaman berisi 2-3 kolom topik.

    Sekalian menegakkan 2 aturan lain di titik yang sama, karena keduanya baru bisa diputuskan
    ketika beberapa topik SUDAH berada di satu halaman / satu laporan:
      - poin 2: kotak KPI yang angkanya SUDAH pernah muncul di halaman lain dibuang (referensi
        tidak pernah mencetak angka yang sama dua kali).
      - poin 4: butir catatan yang isinya bisa dibaca langsung dari visual di kolomnya sendiri
        dibuang (lihat _note_is_readable_from_visual)."""
    # PERMINTAAN USER: "asset_ranking 34 elemen di PPT - kalau topik ini masuk ke halaman
    # dasbor sebagai satu kolom, masalahnya hilang sendiri". Peringkat entitas memang SATU
    # topik setara topik lain (nama + nilai + urutan), cuma selama ini dibungkus jenis blok
    # sendiri. Diubah jadi bentuk kolom di sini supaya ikut dikemas - sekaligus membuat sisa
    # pembagian jadi genap (5 topik + 1 peringkat = 3+3), bukan 3+2 yang timpang.
    #
    # HANYA kalau ada topik lain yang menemani: kalau tidak, halaman peringkat berdiri
    # SENDIRI & konversi ini cuma menukar tampilan baris peringkat (lengkap dgn garis target
    # berlabel) jadi satu kolom kurus di halaman kosong - lebih buruk, bukan lebih baik.
    if len([1 for b in blocks if b.get("kind") == "management_insight_page"]) >= 2:
        for i, b in enumerate(blocks):
            if b.get("kind") != "management_asset_ranking":
                continue
            items = b.get("items") or []
            if not items:
                continue
            top = max((it.get("count") or 0) for it in items) or 1
            _rank_avg = sum((it.get("count") or 0) for it in items) / len(items)
            blocks[i] = {
                "kind": "management_insight_page",
                "title": b.get("title") or "",
                # KPI SENGAJA pendek: nama entitas ditaruh di kartu peringkat di bawahnya,
                # bukan diulang sbg nilai KPI - nilai sepanjang itu di kartu selebar kolom
                # membungkus & terlihat sesak sekalipun ukurannya sudah otomatis mengecil.
                # KOREKSI USER: label "TOTAL" SALAH - angkanya jumlah beberapa entitas
                # teratas saja, bukan total seluruh data laporan (42 vs 27). Labelnya
                # menyebutkan berapa entitas yang dijumlahkan, jadi angkanya tidak bisa
                # disalahbaca sbg total laporan.
                "kpi_summary": [
                    {"label": _L(report, f"{len(items[:6])} TERATAS", f"TOP {len(items[:6])}"),
                     "value": _fmt_count(sum((it.get("count") or 0) for it in items[:6]), is_english(report))},
                    {"label": _L(report, "PERINGKAT 1", "RANK 1"),
                     "value": _fmt_count(items[0].get("count") or 0, is_english(report))},
                ],
                "category_details": [{
                    # KOREKSI USER: dulu dipotong keras di 28 karakter, jadi "PT Sarana
                    # Instrumentasi Utama" tampil "...Utam" - huruf hilang tanpa penanda apa
                    # pun. Sekarang dipotong di BATAS KATA & diberi elipsis, jadi pembaca
                    # tahu namanya masih ada lanjutannya.
                    "name": _potong_di_batas_kata(str(it.get("name") or ""), 28),
                    "raw_name": it.get("name"),
                    "score": _fmt_count(it.get("count") or 0, is_english(report)),
                    "badge": _L(report, "Tinggi", "High") if (it.get("count") or 0) >= top * 0.6 else _L(report, "Sedang", "Medium"),
                    "value": it.get("count") or 0,
                    "frac": (it.get("count") or 0) / top,
                    # sub-item diisi jalur umum di bawah (satu perlakuan utk semua kolom)
                    "sub_items": [],
                } for it in items[:6]],
                "notes": [],
            }

    idxs = [i for i, b in enumerate(blocks) if b.get("kind") == "management_insight_page"]
    if len(idxs) < 2:
        return blocks

    seen_values: set = set()
    for i in idxs:
        col = blocks[i]
        kept_kpi = []
        for card in (col.get("kpi_summary") or []):
            val = str(card.get("value", "")).strip()
            if val and val in seen_values:
                continue
            seen_values.add(val)
            kept_kpi.append(card)
        col["kpi_summary"] = kept_kpi

        # Kartu TANPA sub-item jadi kotak berwarna tinggi yang kosong melompong (terlihat di
        # render: kartu bulan "Mar 2025 / Des 2024 / ..." isinya cuma angka lalu ruang hampa
        # sampai dasar kartu). Diisi satu sub-item yang datanya SUDAH ADA di kartu itu -
        # nilainya sendiri, dgn penanda RATA-RATA seluruh kartu di kolom itu sbg pembanding.
        # Tidak ada angka baru yang dikarang: nilai & rata-rata dua-duanya turunan langsung.
        _cards = col.get("category_details") or []
        if _cards and not any(c.get("sub_items") for c in _cards):
            _vals = [c.get("value") for c in _cards if isinstance(c.get("value"), (int, float))]
            if len(_vals) >= 2:
                _top = max(_vals) or 1
                _avg = sum(_vals) / len(_vals)
                for c in _cards:
                    if not isinstance(c.get("value"), (int, float)):
                        continue
                    c["sub_items"] = [{
                        "label": _L(report, "vs rata-rata", "vs average"),
                        "value": c["value"],
                        "frac": c["value"] / _top,
                        "target_frac": _avg / _top,
                    }]

    # PERMINTAAN USER ("pastikan tidak ada halaman yang lebih renggang dari yang lain"):
    # dikemas berurutan apa adanya, isi halaman bisa timpang jauh (terukur: 167 elemen vs 87)
    # karena BOBOT tiap topik beda jauh - satu topik dgn 4 kartu x 15 sub-item bersarang
    # menyumbang elemen berkali lipat topik yg cuma punya chart. Jadi topik dibagi rata
    # berdasarkan bobot isinya, bukan urutannya: yg terberat disebar lebih dulu ke halaman
    # yang saat itu paling ringan. Urutan tile bergeser, tapi halaman ini memang halaman
    # "Sorotan Data" gabungan beberapa topik - bukan alur naratif berurutan.
    # Koefisien DIKALIBRASI dari render nyata (laporan 183, hitung elemen per kolom langsung
    # dari PDF): kolom 4 kartu/15 sub-item = 96 elemen, 4 kartu/4 sub = 41, chart+2 KPI = 31,
    # 6 kartu polos = 35, 5 kartu polos = 26. Sub-item jauh lebih mahal drpd kartu induknya -
    # itu sebabnya menebak bobot dari "kartu vs chart" saja meleset jauh.
    def _topic_weight(b):
        cards = b.get("category_details") or []
        subs = sum(len(c.get("sub_items") or []) for c in cards)
        has_chart = bool(b.get("main_chart_tile") or b.get("chart_png") or b.get("chart_spec"))
        return (8 + 3 * len(cards) + 4 * subs + 3 * len(b.get("kpi_summary") or [])
                + len(b.get("notes") or []) + (14 if has_chart else 0))

    # KOREKSI USER: RATAKAN JUMLAH DULU, BARU BOBOT. Sebelumnya ukuran keranjang lahir dari
    # cara membaginya (2 halaman -> selalu 3 di depan; >2 halaman -> serakah per bobot), jadi
    # 4 topik jadi 1+3 & 7 topik jadi 3+3+1 - keranjang berisi SATU, yang lalu dirender lewat
    # jalur halaman-tunggal lama (terbukti: 6 dari 25 laporan Visual masih py halaman solo,
    # semuanya laporan bertopik 7). Sekarang ukurannya ditetapkan lebih dulu sebagai pembagian
    # serata mungkin (4->2+2, 7->3+2+2, 10->3+3+2+2), baru ISI tiap keranjang dipilih supaya
    # bobotnya seimbang. Aturan keras: tidak ada keranjang berisi kurang dari 2 topik.
    n_pages = max(1, -(-len(idxs) // _DASH_TOPICS_PER_PAGE))
    _base, _extra = divmod(len(idxs), n_pages)
    sizes = sorted([_base + (1 if i < _extra else 0) for i in range(n_pages)], reverse=True)
    if len(idxs) >= 2 and min(sizes) < 2:
        # tidak terjadi utk pembagian per 3 (sisa 1 selalu terserap ke keranjang lain), tapi
        # ditegakkan eksplisit supaya aturannya tidak bergantung pada nilai _DASH_TOPICS_PER_PAGE
        sizes[sizes.index(min(sizes))] += 1
        sizes[0] -= 1
        sizes = sorted(sizes, reverse=True)

    if n_pages == 1:
        buckets = [list(idxs)]
    elif n_pages == 2:
        # Jumlah topiknya kecil (<=6), jadi semua kemungkinan pembagian pada UKURAN yang sudah
        # ditetapkan diperiksa & yang paling rata bobotnya dipakai. Serakah terbukti tidak
        # optimal di sini (satu topik bisa memegang ~37% seluruh elemen halaman).
        best = None
        for combo in itertools.combinations(idxs, sizes[0]):
            rest = [i for i in idxs if i not in combo]
            gap = abs(sum(_topic_weight(blocks[i]) for i in combo)
                      - sum(_topic_weight(blocks[i]) for i in rest))
            if best is None or gap < best[0]:
                best = (gap, list(combo), rest)
        buckets = [best[1], best[2]]
    else:
        buckets = [[] for _ in range(n_pages)]
        loads = [0] * n_pages
        for i in sorted(idxs, key=lambda i: -_topic_weight(blocks[i])):
            cand = min((k for k in range(n_pages) if len(buckets[k]) < sizes[k]),
                       key=lambda k: (loads[k], k))
            buckets[cand].append(i)
            loads[cand] += _topic_weight(blocks[i])

    # BUG NYATA DIPERBAIKI: perakitan halaman dulu MEMOTONG ULANG idxs per
    # _DASH_TOPICS_PER_PAGE, jadi ukuran keranjang yang baru saja diratakan di atas dibuang
    # begitu saja & 7 topik tetap jadi 3+3+1. Sekarang keranjangnya dipakai APA ADANYA -
    # satu keranjang = satu halaman.
    buckets.sort(key=lambda b: -len(b))

    packed, consumed = [], set()
    for bucket in buckets:
        group = sorted(bucket)
        if not group:
            continue
        consumed.update(group)
        cols = [blocks[i] for i in group]
        if len(cols) == 1:
            cols[0]["notes"] = [n for n in (cols[0].get("notes") or [])
                                if not _note_is_readable_from_visual(n, cols[0])]
            packed.append((group[0], cols[0]))
            continue
        for c in cols:
            c["notes"] = [n for n in (c.get("notes") or [])
                          if not _note_is_readable_from_visual(n, cols)]
        titles = [str(c.get("title") or "").strip() for c in cols if c.get("title")]
        packed.append((group[0], {
            "kind": "management_dashboard_columns",
            "title": _L(report, "Sorotan Data", "Data Highlights") if len(titles) != 1 else titles[0],
            "columns": cols,
        }))

    out, done = [], set()
    for i, b in enumerate(blocks):
        if i in consumed:
            for pos, page in packed:
                if pos == i and pos not in done:
                    out.append(page)
                    done.add(pos)
            continue
        out.append(b)
    return out


def _merge_overlapping_insight_pages(blocks: list, report) -> list:
    """PERMINTAAN USER (temuan langsung dari audit: 6 halaman "insight" topik berbeda ternyata
    menampilkan 8 entitas yang PERSIS sama, cuma disusun ulang - "itu bukan kepadatan, itu
    pengulangan yang kebetulan menghasilkan angka elemen tinggi"): halaman
    "management_insight_page" yang himpunan entitasnya (lihat _insight_page_entity_set)
    beririsan >=70% (_entity_set_overlap) dgn halaman LAIN digabung jadi SATU - hanya
    kemunculan PERTAMA (posisi aslinya di `blocks` dipertahankan, menjaga urutan narasi) yang
    disimpan, sisanya DIBUANG SELURUHNYA (bukan cuma disembunyikan) drpd menumpuk berulang.

    Karena tiap kartu SUDAH menampilkan semua metrik sebanding sbg sub-item (lihat
    _compute_multi_metric_items), halaman yang disimpan TIDAK PERLU pembangunan ulang apa pun
    utk kartunya sendiri - yang ditambahkan cuma "notes" (lihat _compute_merged_page_extra_
    notes) berisi sudut pandang analitis yang genuinely belum ada di kartu manapun, mengisi
    ruang yang tadinya terisi 5 halaman duplikat penuh kartu yang sama."""
    insight_indices = [i for i, b in enumerate(blocks) if b.get("kind") == "management_insight_page"]
    if len(insight_indices) < 2:
        return blocks
    entity_sets = {i: _insight_page_entity_set(blocks[i]) for i in insight_indices}

    # Greedy clustering: tiap halaman baru dicek thd REPRESENTATIF (halaman pertama) tiap
    # grup yang sudah ada - cukup utk kasus nyata (semua kandidat beririsan tinggi dgn SATU
    # set entitas yang sama), tanpa kerumitan pairwise-lengkap yang tidak diperlukan di sini.
    groups: list = []  # list of list[index]
    for i in insight_indices:
        placed = False
        for group in groups:
            rep_set = entity_sets[group[0]]
            if _entity_set_overlap(entity_sets[i], rep_set) >= _INSIGHT_PAGE_OVERLAP_THRESHOLD:
                group.append(i)
                placed = True
                break
        if not placed:
            groups.append([i])

    to_drop: set = set()

    # PERMINTAAN USER (hal.05 mengulang hal.01, dibuktikan dari laporan cetak): halaman GAUGE
    # entitas-tunggal ("E-Katalog mendominasi dengan 38% dari total") tidak pernah tertangkap
    # aturan Jaccard di atas - himpunan entitasnya kosong (tidak py category_details), dan
    # bahkan kalau diisi 1 entitas pun Jaccard-nya cuma 1/N thd halaman berkartu banyak, jauh
    # di bawah ambang. Padahal isinya SUDAH tampil utuh di halaman lain (kartu "E-Katalog" +
    # ringkasan "TERATAS: E-Katalog (38%)"). Diperiksa terpisah dgn kriteria CONTAINMENT
    # (bukan Jaccard): halaman gauge dibuang kalau entitasnya SUDAH ada di halaman lain -
    # catatannya tetap dipindahkan ke halaman itu supaya tidak ada isi yang hilang.
    for i in insight_indices:
        page = blocks[i]
        gauge_entity = page.get("gauge_entity")
        if not gauge_entity or page.get("category_details"):
            continue
        for j in insight_indices:
            if j == i or j in to_drop:
                continue
            # Kriteria (permintaan user): entitas teratas DAN persentasenya sama-sama sudah
            # tampil di halaman lain - bukan cuma entitasnya. Halaman gauge yang entitasnya
            # kebetulan sama TAPI metrik/angkanya berbeda genuinely menambah informasi, jadi
            # TIDAK dibuang.
            host_kpi_text = " ".join(str(k.get("value", "")) for k in (blocks[j].get("kpi_summary") or []))
            pct_shown = f"{page.get('gauge_pct')}%" in host_kpi_text
            entity_shown = gauge_entity in entity_sets[j] or gauge_entity in host_kpi_text
            if entity_shown and pct_shown:
                host = blocks[j]
                moved = [n for n in (page.get("notes") or []) if n not in (host.get("notes") or [])]
                if moved:
                    host["notes"] = (host.get("notes") or []) + moved
                to_drop.add(i)
                break

    for group in groups:
        if len(group) < 2:
            continue
        keep_idx = group[0]
        kept_page = blocks[keep_idx]
        extra_notes = _compute_merged_page_extra_notes(kept_page.get("category_details") or [], report)
        # PERMINTAAN USER (poin 3 - narasi tipis dititipkan sbg "notes" ke halaman insight
        # TERAKHIR sebelum tahap ini berjalan, lihat pemanggil): kalau halaman TITIPAN itu
        # ternyata bukan `keep_idx` (dibuang di grup ini), notes-nya TIDAK BOLEH ikut hilang -
        # digabung dulu ke kept_page sebelum halaman sumbernya dibuang.
        dropped_notes = [n for i in group[1:] for n in (blocks[i].get("notes") or [])]
        if dropped_notes:
            kept_page["notes"] = [*(kept_page.get("notes") or []), *dropped_notes]
        if extra_notes:
            kept_page["notes"] = [*(kept_page.get("notes") or []), *extra_notes]
        to_drop.update(group[1:])

    if not to_drop:
        return blocks
    return [b for i, b in enumerate(blocks) if i not in to_drop]


def _stable_color_index(name: str, n: int = 5) -> int:
    """Indeks warna berdasarkan NAMA kategori (bukan posisi urutannya di list top-N) —
    BUG YANG DIPERBAIKI (dilaporkan user): dulu `color_index = i % n` murni dari urutan
    ranking chart itu sendiri, jadi kategori yang sama (mis. "Pabrik II B") bisa dapat
    warna berbeda di grafik lain kalau kebetulan urutan/top-N nya beda. Hash sederhana
    (bukan hash() bawaan Python — hash string di-randomize per proses) supaya 1 nama
    kategori SELALU jatuh ke indeks warna yang sama di seluruh laporan yang sama."""
    return sum(ord(c) for c in str(name)) % n


# Dipakai laporan LAMA (dibuat sebelum kolom report.visual_style ada, jadi NULL) — satu set
# tetap yang cocok dgn styling default sebelumnya (cover split, chart bar, kartu grid biasa),
# supaya laporan lama tidak pernah error/berubah tampilan sendiri gara-gara migrasi ini.
DEFAULT_VISUAL_STYLE = {
    # PERMINTAAN USER: cover 2-kolom warna-penuh + angka besar ("split") dihapus dari opsi
    # yang bisa dipilih — dianggap terlalu ramai/tidak umum utk cover laporan. "solid" (latar
    # gelap penuh + kicker/judul/periode, tanpa angka besar) jadi SATU-SATUNYA gaya cover
    # dipakai mulai sekarang. Kode _split_cover_td/_build_split_cover_slide/CoverSplit TETAP
    # ada (TIDAK dihapus) — laporan LAMA yang sudah terlanjur terkunci ke "split" di
    # report.visual_style tidak boleh berubah tampilan sendiri (lihat catatan panjang di
    # pick_visual_style soal laporan lama tidak pernah berubah bentuk sendiri).
    "cover_style": "solid",
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
        "cover_style": "solid",
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
        "cover_style": "solid",
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
            "cover_style": "solid",  # "split" dihapus dari opsi acak, lihat catatan di DEFAULT_VISUAL_STYLE
            "category_style": rnd.choice(["bar", "donut", "stacked", "treemap"]),
            "status_style": rnd.choice(["bar", "donut", "stacked", "funnel", "treemap"]),
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


VALID_THEME_COLORS = ("green", "navy", "dark", "gold", "teal")


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
    # PERMINTAAN USER (F5): pastikan tanggal mulai <= tanggal selesai — dipakai di SEMUA
    # tempat period_text ditampilkan (cover, Ringkasan Eksekutif, panel scope, dst, lihat
    # pemanggil format_period di file ini), jadi 1 penjagaan di sini otomatis menutup ketiganya
    # sekaligus. Sumber report.period_start/period_end BISA terbalik (mis. diisi manual oleh
    # user lewat form, atau dari jalur deteksi lain yang tidak selalu menjamin urutan) — beda
    # dgn detect_period() di period_detector.py sendiri yang sudah aman krn pakai .min()/.max()
    # eksplisit, field DB ini tidak WAJIB berasal dari situ.
    joiner = " to " if is_english(report) else " sampai "
    if report.period_start and report.period_end:
        start, end = report.period_start, report.period_end
        if start > end:
            start, end = end, start
        if start == end:
            return format_report_date(end, report.language)
        return f"{format_report_date(start, report.language)}{joiner}{format_report_date(end, report.language)}"
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


def _strip_decorative_symbols(text: str) -> str:
    """Salinan LOKAL dari app.services.parser.pdf_parser::_strip_decorative_symbols (2 modul
    ini sengaja TIDAK saling impor — pdf_parser.py itu parser, bergantung ke sini malah
    kebalik arah dependensinya; report_render_logic.py juga sengaja tidak bergantung ke
    parser mana pun, lihat docstring modul ini). Buang simbol dekoratif (▼ ▲ ▣ ■ • dst —
    penanda urut/bullet VISUAL, BUKAN bagian nama kolom sungguhan) dari AWAL & AKHIR teks —
    lapis pertahanan KEDUA di sini (lapis pertama sudah di pdf_parser.py saat kolom pertama
    kali dibaca) utk jaga2 nama kolom bersimbol nyasar dari jalur lain (mis. CSV/Excel yang
    header-nya kebetulan disalin dari tampilan web/PDF, bukan ditulis manual)."""
    chars = list(text)
    start = 0
    while start < len(chars) and (chars[start].isspace() or unicodedata.category(chars[start]) in ("So", "Sk")):
        start += 1
    end = len(chars)
    while end > start and (chars[end - 1].isspace() or unicodedata.category(chars[end - 1]) in ("So", "Sk")):
        end -= 1
    return "".join(chars[start:end])


def humanize_label(label: str, source_cols: dict | None = None) -> str:
    """Ubah label internal (nama niat seperti "location", atau label generik "category_2")
    jadi teks tampilan yang manusiawi. Untuk label generik "category_N", PRIORITASKAN nama
    kolom ASLI dari file yang diupload (mis. "Kategori", "Unit_Kerja") lewat `source_cols`
    (report_stats["_source_columns"]) — bukan lagi tampil sebagai "Kategori 2" yang tidak
    bermakna apa-apa (bug yang sebelumnya kejadian bahkan untuk kolom yang nama aslinya
    sendiri sudah "Kategori", cuma tidak cocok kata kunci niat manapun)."""
    label = _strip_decorative_symbols(label)
    if source_cols and label.startswith("category_"):
        real_name = source_cols.get(label)
        if real_name:
            return _strip_decorative_symbols(str(real_name)).replace("_", " ").strip().title()
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
            # BUG DIPERBAIKI (dilaporkan user): "kategori teratas" dgn count<=1 bukan temuan
            # yang genuinely bermakna (top-nya cuma muncul 1x, artinya TIDAK ADA konsentrasi/
            # pola apa pun di kolom itu — bisa jadi kebetulan urutan pertama tabel, bukan
            # dominasi sungguhan) — dilewati drpd ditulis seolah itu insight penting.
            if items and items[0]["count"] > 1:
                label_text = humanize_label(label, source_cols_for_findings)
                findings.append(_L(
                    report,
                    f"Kategori teratas pada {label_text} adalah {items[0]['value']} dengan {items[0]['count']} kejadian." if is_security_domain(report)
                    else f"Kategori teratas pada {label_text} adalah {items[0]['value']} dengan {items[0]['count']} data.",
                    f"The top category in {label_text} is {items[0]['value']} with {items[0]['count']} occurrences.",
                ))
        # BUG NYATA DITEMUKAN (dilaporkan user, terlihat langsung di halaman jadi): kalau
        # SEMUA sumber di atas (AI, severity, top_categories) genuinely tidak menghasilkan
        # apa pun, dulu di sini DITAMBAHKAN 1 kalimat "Key findings could not be automatically
        # derived from this data." sbg pengganti - itu PESAN KEGAGALAN SISTEM, bukan temuan,
        # tapi ditampilkan APA ADANYA ke pembaca seolah itu hasil analisis. Sekarang findings
        # dibiarkan KOSONG kalau genuinely tidak ada apa pun - pemanggil (build_report_blocks/
        # build_management_report_blocks) SUDAH mengecek `if key_findings` sebelum membuat
        # panel/halaman "Temuan Utama" sama sekali, jadi list kosong di sini otomatis berarti
        # halaman itu TIDAK dibuat - prinsip yang sama dipakai di seluruh file ini ("blok tanpa
        # data dilewati", bukan ditampilkan sbg pesan kosong/gagal).
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
# Perhitungan tambahan KHUSUS bentuk visual baru (radar/heatmap/perbandingan periode) —
# SEMUA membaca `parsed_data`/`report_stats` yang SUDAH dihasilkan compute_statistics(),
# TIDAK PERNAH mengubah/menambah isi compute_statistics() itu sendiri (data_profiler.py
# tetap apa adanya). Dipisah jadi fungsi kecil sendiri (bukan inline di build_report_blocks)
# supaya gampang dites & gampang dibaca alurnya.
# ============================================================================
def _compute_kpi_radar(numeric_summary: dict, source_cols: dict | None) -> dict | None:
    """Radar skor multi-indikator — dipakai HANYA kalau data punya >=3 kolom numerik (mis.
    beberapa skor KPI/nilai capaian sekaligus). Tiap sumbu dinormalisasi jadi "rata-rata
    sebagai % dari nilai maksimum kolom itu sendiri" — supaya kolom dengan skala beda-beda
    (mis. skor 0-5 vs nilai kontrak jutaan rupiah) tetap bisa dibandingkan di 1 radar yang
    sama tanpa perlu tahu skala aslinya masing-masing."""
    axes, values = [], []
    for col, nstats in list(numeric_summary.items())[:6]:
        mx = nstats.get("max")
        mean = nstats.get("mean")
        if not mx or mean is None:
            continue
        axes.append(humanize_label(col, source_cols))
        values.append(max(0.0, min(100.0, round(mean / mx * 100, 1))))
    if len(axes) < 3:
        return None
    # BUG DIPERBAIKI (dilaporkan user): nilai tiap sumbu SUDAH dinormalisasi ke skala 0-100
    # (rata-rata sbg % dari nilai maksimum kolom itu sendiri) SUPAYA kolom beda skala tetap
    # bisa dibandingkan — TAPI normalisasi ini tidak menjamin rentang ANTAR sumbu jadi wajar:
    # 1 sumbu bisa tetap ~90 (rata2 dekat maksimumnya sendiri) sementara sumbu lain ~3 (rata2
    # jauh di bawah maksimumnya, mis. data timpang/outlier ekstrem). Sumbu bernilai kecil di
    # radar jadi titik nyaris di pusat (nyaris tak beda dari "kosong"), bentuk radar-nya
    # menyesatkan. Kalau rasio nilai terbesar:terkecil (bukan nol) > 10x, radar TIDAK dipakai
    # sama sekali (return None, pemanggil fallback ke bentuk visual lain) drpd memaksakan
    # bentuk yang timpang & sulit dibaca.
    nonzero_values = [v for v in values if v > 0]
    if nonzero_values and (max(values) / min(nonzero_values)) > 10:
        return None
    return {"axes": axes, "values": values}


def _compute_day_hour_pattern(parsed_data: list, date_col: str | None) -> dict | None:
    """Grid pola kejadian per hari-dalam-minggu x blok jam (6 blok @4 jam) — dipakai utk
    heatmap. Butuh kolom tanggal terdeteksi & minimal 20 baris bertanggal valid supaya
    polanya bermakna (bukan cuma 1-2 sel terisi di tengah grid kosong)."""
    if not date_col or not parsed_data:
        return None
    try:
        dates = pd.to_datetime(pd.Series([row.get(date_col) for row in parsed_data]), errors="coerce")
        dates = dates.dropna()
        if len(dates) < 20:
            return None
        day_labels = [
            ("Senin", "Mon"), ("Selasa", "Tue"), ("Rabu", "Wed"), ("Kamis", "Thu"),
            ("Jumat", "Fri"), ("Sabtu", "Sat"), ("Minggu", "Sun"),
        ]
        hour_labels = ["00-04", "04-08", "08-12", "12-16", "16-20", "20-24"]
        grid = [[0] * 6 for _ in range(7)]
        for ts in dates:
            grid[int(ts.dayofweek)][min(int(ts.hour) // 4, 5)] += 1
        if sum(sum(row) for row in grid) == 0:
            return None
        # Data sumber yang cuma punya TANGGAL tanpa jam (umum di laporan produksi harian)
        # selalu ter-parse jam=00:00 — semua baris numpuk di kolom "00-04", 5 kolom lain
        # kosong permanen. Tabel 6 kolom yang 5-nya kosong tidak informatif, jadi kalau
        # cuma 1 kolom jam yang benar-benar terisi, tampilkan total per-hari saja (1 kolom)
        # drpd grid bolong.
        active_hour_cols = sum(1 for c in range(6) if any(grid[r][c] for r in range(7)))
        if active_hour_cols <= 1:
            day_totals = [[sum(row)] for row in grid]
            return {"day_labels": day_labels, "hour_labels": ["Total"], "grid": day_totals, "total": int(len(dates))}
        return {"day_labels": day_labels, "hour_labels": hour_labels, "grid": grid, "total": int(len(dates))}
    except Exception:
        return None


def _compute_period_compare(parsed_data: list, date_col: str | None, cat_col: str | None, top_values: list) -> dict | None:
    """Bandingkan jumlah kejadian per kategori teratas antara paruh awal vs paruh akhir
    periode data (dibagi di median tanggal) — dipakai utk grouped bar. Butuh kolom tanggal +
    kolom kategori yang sama-sama terdeteksi & minimal 12 baris bertanggal valid."""
    if not date_col or not cat_col or not parsed_data or not top_values:
        return None
    try:
        dates = pd.to_datetime(pd.Series([row.get(date_col) for row in parsed_data]), errors="coerce")
        valid = dates.dropna()
        if len(valid) < 12:
            return None
        median = valid.median()
        first = {v: 0 for v in top_values}
        second = {v: 0 for v in top_values}
        for i in valid.index:
            val = str(parsed_data[i].get(cat_col, ""))
            if val not in first:
                continue
            (first if dates[i] <= median else second)[val] += 1
        series_a = [first[v] for v in top_values]
        series_b = [second[v] for v in top_values]
        if sum(series_a) + sum(series_b) == 0:
            return None
        return {"categories": top_values, "series_a": series_a, "series_b": series_b}
    except Exception:
        return None


_STOP_WORDS = {
    "yang", "dan", "atau", "dari", "pada", "untuk", "dengan", "adalah", "akan", "telah",
    "masih", "perlu", "dapat", "juga", "para", "tersebut", "menjadi", "secara", "dalam",
    "this", "that", "with", "from", "have", "been", "will", "should", "need", "most", "into",
    "over", "than", "such", "were", "there", "their", "about", "across",
}


def _text_tokens(text: str) -> set:
    return {w for w in re.findall(r"[a-zA-ZÀ-ɏ]{4,}", (text or "").lower()) if w not in _STOP_WORDS}


def _conclusion_adds_new_insight(conclusion_text: str, prior_texts: list) -> bool:
    """Kesimpulan bukan section wajib — cek dulu apakah isinya menambah insight baru di luar
    yang sudah tersampaikan di halaman lain, bukan cuma mengulang. Heuristik sederhana &
    deterministik (tanpa panggilan AI baru): bandingkan kata-kata bermakna (>=4 huruf, bukan
    kata umum) di teks kesimpulan dgn gabungan kata-kata di SEMUA teks/caption yang sudah
    tampil sebelumnya — kalau porsi kata BARU terlalu kecil, isinya dianggap pengulangan &
    di-skip. Teks pendek (<5 kata bermakna) selalu dianggap lolos (terlalu pendek utk dinilai
    andal, lebih aman ditampilkan daripada salah membuang kesimpulan yang genuinely singkat)."""
    concl_tokens = _text_tokens(conclusion_text)
    if len(concl_tokens) < 5:
        return True
    seen_tokens: set = set()
    for t in prior_texts:
        seen_tokens |= _text_tokens(t)
    new_tokens = concl_tokens - seen_tokens
    return (len(new_tokens) / len(concl_tokens)) >= 0.3


def _candidate(panel_kind: str, theme_tag: str, weight: float, dark: bool, kicker, title, **payload) -> dict:
    """Satu "kandidat" konten (tahap 1) — 1 topik apa adanya, LENGKAP dgn saran bentuk visual
    (field-field di `payload`, mis. "chart"/"categories"/"values"), sebelum diputuskan (tahap
    2, lihat _group_candidates_into_pages) bakal jadi halaman sendiri atau digabung dgn
    kandidat lain yang temanya nyambung. `weight` = perkiraan kasar seberapa "penuh" 1 halaman
    kalau kandidat ini sendirian (skala 0-1, 1.0 = sepadat halaman penuh) — dipakai murni utk
    keputusan penggabungan, BUKAN dipakai renderer."""
    return {
        "panel_kind": panel_kind, "theme_tag": theme_tag, "weight": weight, "dark": dark,
        "kicker": kicker, "title": title, **payload,
    }


_GROUP_HEADING = {
    "insight": (("ANALISIS", "ANALYSIS"), ("Ringkasan Analisis", "Analysis Summary")),
    "distribution": (("ANALISIS DATA", "DATA ANALYSIS"), ("Distribusi & Pola Data", "Data Distribution & Patterns")),
    "action": (("TINDAK LANJUT", "FOLLOW-UP"), ("Rekomendasi & Kesimpulan", "Recommendations & Conclusion")),
    "overview": (("RINGKASAN", "SUMMARY"), ("Ringkasan Eksekutif", "Executive Summary")),
}


def _panel_headline(panel: dict) -> str | None:
    """PERMINTAAN USER: judul halaman harus memuat temuan BERANGKA (mis. "Trafik terkonsentrasi
    pada 2 virtual server (71% dari total)"), bukan label generik. Tiap jenis panel menyimpan
    kalimat sintesis 1-kalimat-nya sendiri di field beda2 (caption/text/ai_caption/intro,
    tergantung panel_kind) — dicoba berurutan, dipakai APA ADANYA (sudah 1 kalimat pendek
    berangka, lihat prompts.py & _shorten_to_caption(...,max_sentences=1))."""
    for key in ("caption", "text", "ai_caption", "intro"):
        val = panel.get(key)
        if val:
            # Dipotong 1 kalimat SAJA di sini — sumbernya (mis. caption insight_tile) kadang
            # sudah berisi 2-3 kalimat (pas jadi caption di bawah chart), tapi sbg JUDUL
            # HALAMAN harus tetap 1 baris pendek, bukan ikut sepanjang caption aslinya.
            return _shorten_to_caption(val, max_sentences=1)
    return None


def _page_from_panels(panels: list, report, sec_domain: bool) -> dict:
    """Bungkus 1+ panel (kandidat yang sudah diputuskan tahap 2) jadi 1 dict halaman.

    BUG DIPERBAIKI (ditemukan sendiri lewat verifikasi render — cocok dgn keluhan user "judul
    ditulis dua kali"): dua sumber duplikasi teks yang TERNYATA berbeda akar, sama2 diperbaiki
    di sini:
    (1) Panel bertema "insight" (insight_tile/dynamic_section) SUDAH menampilkan caption/
    text-nya sendiri sbg isi kartu (_panel_insight_card/_draw_insight_tile membaca field
    caption/text yang SAMA PERSIS) — kalau field itu JUGA dipakai jadi judul HALAMAN (lewat
    _panel_headline), kalimat yang SAMA muncul 2x. _panel_headline HANYA dipakai utk tema
    SELAIN "insight".
    (2) Kasus SOLO 1-panel bertema "insight" — SEBELUM perbaikan ini, judul HALAMAN dipatok
    ke `panel["title"]` (mis. "Analisis Tren") APA ADANYA, padahal panel itu SENDIRI (via
    _panel_header_band/_draw_header_band) SUDAH menampilkan label yang SAMA PERSIS di dalam
    kartunya (`label = panel.get("label") or panel.get("title")`) — "Analisis Tren" muncul
    besar di atas halaman DAN kecil lagi di dalam kartu, persis di bawahnya. Kartu tunggal
    bertema "insight" SEKARANG selalu pakai judul GENERIK tema (_GROUP_HEADING["insight"],
    sama seperti kasus gabungan >1 panel) drpd mengulang judul/label kartunya sendiri."""
    dark = panels[0]["dark"]
    theme = panels[0]["theme_tag"]
    if len(panels) == 1 and theme != "insight":
        p = panels[0]
        return {"kind": "page", "dark": dark, "kicker": p.get("kicker"), "title": p.get("title"), "panels": panels}
    if theme == "highlight":
        kicker = (_L(report, "SOROTAN INSIDEN", "INCIDENT HIGHLIGHT") if sec_domain
                  else _L(report, "SOROTAN DATA", "DATA HIGHLIGHT"))
        title = _L(report, "Sorotan Utama", "Key Highlights")
    elif theme in _GROUP_HEADING:
        (kicker_id, kicker_en), (title_id, title_en) = _GROUP_HEADING[theme]
        kicker = _L(report, kicker_id, kicker_en)
        title = _L(report, title_id, title_en)
    else:
        kicker, title = panels[0].get("kicker"), panels[0].get("title")
    # _panel_headline HANYA utk tema SELAIN "insight" — lihat (1) di atas.
    headline = None if theme == "insight" else _panel_headline(panels[0])
    return {"kind": "page", "dark": dark, "kicker": kicker, "title": headline or title, "panels": panels}


def _group_candidates_into_pages(candidates: list, report, sec_domain: bool) -> list:
    """Tahap 2 dari build_report_blocks: gabungkan daftar kandidat jadi daftar HALAMAN.
    Kandidat "kaya" (weight tinggi, mis. severity_distribution/critical_table) otomatis
    berakhir sendirian di halamannya sendiri (weight-nya sendiri sudah nyaris/melebihi
    kapasitas 1 halaman). Kandidat kecil digabung BERURUTAN (urutan narasi tetap dijaga)
    selama: (a) tema gabungannya sama (theme_tag), (b) warna latarnya sama (dark), (c) total
    bobot belum melewati kapasitas halaman, (d) jumlah panel belum melebihi batas aman (3).

    Setelah pengelompokan awal, ada 1 langkah tambahan (backstop): halaman 1-panel yang masih
    terlalu tipis (<60% kapasitas) dicoba disambung paksa ke halaman TETANGGA (warna latar
    tetap harus sama, tema boleh beda) — supaya tidak ada halaman kosong/tipis dibiarkan
    sendirian begitu saja, sesuai prinsip "larangan (a)" dari spesifikasi tata letak."""
    # PERMINTAAN USER (revisi — sebelumnya sempat dibatasi 2/halaman, lihat riwayat di git):
    # kartu insight (trend/severity/risk/dynamic_section) SEKARANG jauh lebih pendek sejak
    # celah kosong tengah kartu dihapus (lihat _draw_insight_tile/_panel_insight_card) & caption
    # dibatasi tinggi CSS-nya (bukan lagi teks panjang mentah) — halaman yang cuma diisi 2 kartu
    # kecil terasa BOROS ruang kosong dibanding referensi. Dinaikkan lagi ke 4/halaman (bobot
    # per-kartu ikut diturunkan, lihat _candidate("insight_tile"/"dynamic_section", ...) di
    # bawah) supaya halaman insight terasa padat spt referensi, TANPA mengubah tata letak baris
    # tunggal N-kolom yang sudah terbukti aman dibaca (beda dgn grid tile dashboard Management).
    PAGE_CAP_BY_THEME = {"insight": 1.0}
    MAX_PANELS_BY_THEME = {"insight": 4}
    DEFAULT_PAGE_CAP = 1.05
    DEFAULT_MAX_PANELS = 3
    MIN_FULL = 0.6

    pages: list = []
    bucket: list = []
    bucket_w = 0.0
    bucket_theme = None
    bucket_dark = None

    def flush():
        nonlocal bucket, bucket_w, bucket_theme, bucket_dark
        if bucket:
            pages.append(_page_from_panels(bucket, report, sec_domain))
        bucket, bucket_w, bucket_theme, bucket_dark = [], 0.0, None, None

    for cand in candidates:
        page_cap = PAGE_CAP_BY_THEME.get(bucket_theme, DEFAULT_PAGE_CAP)
        max_panels = MAX_PANELS_BY_THEME.get(bucket_theme, DEFAULT_MAX_PANELS)
        fits = (
            bucket
            and cand["theme_tag"] == bucket_theme
            and cand["dark"] == bucket_dark
            and bucket_w + cand["weight"] <= page_cap
            and len(bucket) < max_panels
        )
        if fits:
            bucket.append(cand)
            bucket_w += cand["weight"]
        else:
            flush()
            bucket, bucket_w, bucket_theme, bucket_dark = [cand], cand["weight"], cand["theme_tag"], cand["dark"]
    flush()

    idx = 0
    while idx < len(pages):
        page = pages[idx]
        panels = page["panels"]
        thin = len(panels) == 1 and panels[0]["weight"] < MIN_FULL
        if not thin:
            idx += 1
            continue
        panel = panels[0]
        merged = False
        for neighbor_idx, append_at_end in ((idx - 1, True), (idx + 1, False)):
            if 0 <= neighbor_idx < len(pages) and neighbor_idx != idx:
                neighbor = pages[neighbor_idx]
                n_weight = sum(p["weight"] for p in neighbor["panels"])
                # CATATAN: sebelumnya dibatasi `same_header_style` (halaman "insight" tipis
                # cuma boleh disambung ke sesama "insight") krn campur panel mandiri (category_
                # distribution dkk, sudah bawa judul sendiri) + insight_tile (headerless) bisa
                # menghasilkan judul dobel. Sekarang AMAN disambung ke tema apa pun — lihat
                # _build_page_block (export_pdf.py) / _build_page_slide (export_ppt.py):
                # header level-halaman generik dipakai `all()` bukan `any()`, jadi begitu 1 saja
                # panel di halaman gabungan sudah bawa judul sendiri, header generik otomatis
                # dimatikan (panel insight yang nebeng cukup pakai label kecilnya sendiri).
                # PERMINTAAN USER: halaman insight_tile/dynamic_section tunggal yang tipis tidak
                # boleh dibiarkan berdiri sendiri kalau ADA tetangga yang masih muat, apa pun
                # temanya — inilah perbaikannya (sebelumnya bisa gagal disambung kalau satu2nya
                # tetangga yang muat temanya beda).
                n_theme = neighbor["panels"][0]["theme_tag"]
                n_cap = PAGE_CAP_BY_THEME.get(n_theme, DEFAULT_PAGE_CAP)
                n_max = MAX_PANELS_BY_THEME.get(n_theme, DEFAULT_MAX_PANELS)
                if neighbor["dark"] == page["dark"] and n_weight + panel["weight"] <= n_cap and len(neighbor["panels"]) < n_max:
                    merged_panels = (neighbor["panels"] + [panel]) if append_at_end else ([panel] + neighbor["panels"])
                    pages[neighbor_idx] = _page_from_panels(merged_panels, report, sec_domain)
                    pages.pop(idx)
                    merged = True
                    break
        if not merged:
            idx += 1

    # PERMINTAAN USER: backstop di atas cuma coba sambung ke TETANGGA — kalau satu2nya
    # tetangga yang ada ternyata sudah penuh/beda warna latar (kasus jarang, mis. halaman
    # tipis ini persis di ujung awal/akhir laporan), halaman 1-butir masih bisa lolos berdiri
    # sendiri. Langkah TERAKHIR ini menyisir SISA halaman insight 1-panel yang masih tipis &
    # gagal disambung ke tetangga, lalu menitipkannya ke Ringkasan Eksekutif (kalau ada) —
    # sama persis prinsipnya dgn Temuan Utama 1-butir yang sudah lebih dulu ditangani begitu.
    exec_page = next(
        (pg for pg in pages if len(pg["panels"]) == 1 and pg["panels"][0]["panel_kind"] == "executive_summary"),
        None,
    )
    if exec_page is not None:
        idx = 0
        while idx < len(pages):
            page = pages[idx]
            panels = page["panels"]
            thin = (
                len(panels) == 1
                and panels[0]["theme_tag"] == "insight"
                and panels[0]["weight"] < MIN_FULL
                and page is not exec_page
            )
            if not thin:
                idx += 1
                continue
            panel = panels[0]
            headline = panel.get("caption") or panel.get("text")
            if headline:
                exec_cand = exec_page["panels"][0]
                extra = exec_cand.setdefault("extra_orphan_insights", [])
                extra.append({"label": panel.get("label") or panel.get("title") or "", "text": headline})
            pages.pop(idx)
    return pages


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
#
# DUA TAHAP (rombak dari versi lama yang langsung blocks.append per topik):
#   Tahap 1 — kumpulkan tiap topik jadi 1 "kandidat" (_candidate(...)), LENGKAP
#   dgn saran bentuk visual & perkiraan "bobot" halaman (lihat catatan di
#   _candidate/_group_candidates_into_pages). Statistik/angka yang dihitung tiap
#   topik PERSIS SAMA seperti versi lama, tidak ada logika hitung yang berubah.
#   Tahap 2 — _group_candidates_into_pages() memutuskan kandidat mana jadi
#   halaman sendiri vs digabung dgn kandidat lain yang temanya nyambung &
#   sama-sama ringkas, sehingga tata letak tiap halaman proporsional dgn
#   isinya. Cover/Pendahuluan/Penutup TETAP di luar sistem ini (selalu halaman
#   sendiri, isinya juga selalu berukuran tetap terlepas dari data).
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
    date_col = source_cols.get("date")
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
            return sanitize_text(coerce_narrative_text(val)) if val else fallback
        if isinstance(_raw_chart_captions, list):
            captions = [sanitize_text(coerce_narrative_text(c)) for c in _raw_chart_captions if c]
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
    cover_block = {
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
    }

    # ---------------- Latar Belakang & Tujuan (Domain & Language Aware) ----------------
    # PERMINTAAN USER: halaman terpisah "Latar Belakang dan Tujuan Analisis" DIHAPUS —
    # isinya cuma metadata boilerplate (kalimat tujuan generik per domain + scope
    # periode/total data yg SUDAH ada di cover & Ringkasan Eksekutif) & sering berakhir
    # nyaris kosong, tidak layak jadi halaman sendiri. Kalimat tujuannya (`purpose_text`)
    # sekarang ditempelkan sbg paragraf tambahan di Ringkasan Eksekutif (lihat
    # candidates.append("executive_summary", ...) di bawah) — sisanya (3 tujuan bernomor,
    # panel scope terpisah) dibuang total krn isinya sudah terwakili di tempat lain.
    if domain == "financial":
        data_name = "financial transactions" if is_en else "data transaksi & operasional keuangan"
    elif domain == "kpi_hr":
        data_name = "KPI & performance evaluation data" if is_en else "data penilaian KPI & kinerja SDM/mitra"
    elif domain == "soc_security":
        data_name = "cybersecurity log events" if is_en else "sistem keamanan siber"
    else:
        data_name = "operational data records" if is_en else "data operasional"

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

    # ---------------- TAHAP 1: kumpulkan kandidat (bukan langsung blocks.append) ----------------
    candidates: list = []
    prior_texts: list = [purpose_text]

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

        _exec_raw = sanitize_text(coerce_narrative_text(ai_summary.get("executive_summary")))
        _exec_verified, _ = _verify_narrative_sentences(
            _exec_raw, report_stats, field_name="executive_summary", report_id=getattr(report, "id", None),
            parsed_data=parsed_data,
        )
        caption = _shorten_to_caption(_exec_verified or (key_findings[0] if key_findings else ""))
        prior_texts.append(caption)
        # Panel "overview" ini SATU-SATUNYA kandidat bertema "overview" — tidak pernah
        # digabung dgn kandidat lain (lihat _group_candidates_into_pages: gabung mensyaratkan
        # theme_tag SAMA), jadi SELALU jadi halaman sendiri berapa pun isinya. Tanpa donut
        # pendamping ini, halaman berisi kartu KPI + 1-2 kalimat caption saja terasa nyaris
        # kosong (dilaporkan user). Dipakai DONUT (bukan bar, sudah dipakai Temuan Utama di
        # bawah — lihat `chart=severity_gauge or category_chart or status_chart`) supaya
        # bentuk visualnya tidak berulang persis dgn panel lain di laporan yang sama.
        exec_chart = None
        if category_pick:
            _ec_items = category_pick[1][:5]
            exec_chart = {"type": "donut", "categories": [it["value"] for it in _ec_items], "values": [it["count"] for it in _ec_items]}
        elif status_items:
            _ec_items = status_items[:5]
            exec_chart = {"type": "donut", "categories": [it["value"] for it in _ec_items], "values": [it["count"] for it in _ec_items]}
        candidates.append(_candidate(
            "executive_summary", "overview", min(0.95, 0.4 + 0.09 * len(stat_items)), True,
            kicker=None, title=_L(report, "Ringkasan Eksekutif", "Executive Summary"),
            heading=heading, stat_items=stat_items, caption=caption, chart=exec_chart,
            purpose_text=purpose_text,
        ))

    # ---------------- Data visual pendukung utk insight tiles/dynamic_section/key_findings ----------------
    # 3 bentuk visual TAMBAHAN (di luar aux_stat/aux_list generik) supaya section narasi AI
    # (Trend/Severity/Risk/kustom) & Temuan Utama ditemani chart/gauge kecil yang BENAR-BENAR
    # relevan dgn topiknya. Semua dihitung dari data yang SUDAH ADA (category_pick/status_items/
    # severity/report_stats) — tidak ada statistik baru. Jenis chart SENGAJA TETAP per sumber
    # data (bukan ikut visual_style acak laporan) — panel-panel ini panel PENDUKUNG kecil.
    aux_stat_value = hero_stat
    # PERMINTAAN USER ("panel bertingkat" — 1 kartu boleh memuat strip KPI + daftar kotak
    # angka, bukan cuma 1 visual): dulu cuma 1 varian aux_list (kategori ATAU status, if/elif)
    # dipakai bergantian ganjil/genap utk dynamic_section, jadi separuh kartu section custom
    # tidak kebagian visual APA PUN (teks polos). Sekarang kategori & status DIHITUNG
    # terpisah (kalau dua2nya ada) jadi ada 2 varian visual independen utk dirotasi, ditambah
    # "total" tiap daftar (dijumlah dari count aslinya, BUKAN angka global yang diulang-ulang
    # spt aux_stat_value lama — nilai ini genuinely turunan langsung dari daftar yang sama
    # persis ditampilkan di bawahnya) sbg strip KPI kecil di atas daftarnya.
    aux_list_items = None
    aux_list_total = None
    aux_list_items_2 = None
    aux_list_total_2 = None
    if category_pick:
        cat_total = sum(i["count"] for i in category_pick[1]) or 1
        aux_list_items = [
            {"label": it["value"], "value": f"{round(it['count'] / cat_total * 100, 1)}%"}
            for it in category_pick[1][:4]
        ]
        aux_list_total = str(cat_total)
    if status_items:
        status_total = sum(i["count"] for i in status_items) or 1
        status_list = [
            {"label": it["value"], "value": f"{round(it['count'] / status_total * 100, 1)}%"}
            for it in status_items[:4]
        ]
        if aux_list_items is None:
            aux_list_items, aux_list_total = status_list, str(status_total)
        else:
            aux_list_items_2, aux_list_total_2 = status_list, str(status_total)
    # Pool visual bersama utk insight_tile (Tren/Severity/Risiko yang tidak punya chart
    # genuine sendiri) MAUPUN dynamic_section — tiap entri (aux_list, aux_list_total) berbeda
    # sumber data (kategori vs status). Dipakai HABIS SEKALI PAKAI lewat _take_pool_item()
    # (indeks bersama, bukan dirotasi ulang) — PERMINTAAN USER (C5, "panel bertingkat" — chart/
    # angka boleh ditumpuk dgn daftar kategori di BAWAHNYA dlm 1 kartu, bukan cuma dynamic_
    # section) SEKALIGUS menghindari kelas bug G1 (2 kartu topik beda menampilkan daftar yang
    # PERSIS SAMA) krn tiap entri pool cuma boleh diambil SATU kartu saja, siapa pun duluan.
    _dyn_visual_pool = [
        (items, total) for items, total in ((aux_list_items, aux_list_total), (aux_list_items_2, aux_list_total_2))
        if items
    ]
    _pool_cursor = [0]

    def _take_pool_item():
        if _pool_cursor[0] < len(_dyn_visual_pool):
            item = _dyn_visual_pool[_pool_cursor[0]]
            _pool_cursor[0] += 1
            return item
        return (None, None)

    category_chart = None
    if category_pick:
        _cc_items = category_pick[1][:4]
        category_chart = {"type": "bar", "categories": [it["value"] for it in _cc_items], "values": [it["count"] for it in _cc_items]}

    status_chart = None
    if status_items:
        _sc_items = status_items[:4]
        status_chart = {"type": "donut", "categories": [it["value"] for it in _sc_items], "values": [it["count"] for it in _sc_items]}

    # severity_gauge — persentase Critical+High dari seluruh event berseverity.
    severity_gauge = None
    if total_sev:
        crit_high_pct = round((severity.get("critical", 0) + severity.get("high", 0)) / total_sev * 100, 1)
        severity_gauge = {
            "type": "gauge", "value": crit_high_pct, "max": 100,
            "label": _L(report, "Critical + High", "Critical + High"), "severity_keys": ["critical"],
        }

    # trend_stat/trend_series_chart — kartu panah 2-titik ATAU chart batang+garis kumulatif per
    # PERIODE ASLI (deret waktu -> "bar+line kumulatif" sesuai karakter datanya), lihat
    # _compute_time_series di data_profiler.py (unit/labels/counts/cumulative, TIDAK berubah).
    trend_data = (report_stats.get("time_pattern") or {}).get("trend")
    trend_stat = None
    if trend_data:
        _pct = trend_data["pct_change"]
        _arrow = "▲" if _pct > 0 else ("▼" if _pct < 0 else "→")
        trend_stat = {
            "value": f"{_arrow} {abs(_pct)}%",
            "label": _L(
                report,
                f"dari {trend_data['first_half_count']} ke {trend_data['second_half_count']} event",
                f"from {trend_data['first_half_count']} to {trend_data['second_half_count']} events",
            ),
            "direction": "up" if _pct > 0 else ("down" if _pct < 0 else "flat"),
        }

    _time_series = report_stats.get("time_series") or {}
    trend_series_chart = None
    if len(_time_series.get("counts") or []) >= 3:
        # Dipotong ke 8 bucket TERAKHIR (dari maks 12 yang dihitung data_profiler.py) — tile
        # ini cuma sebagian lebar halaman, kolom lebih dari 8 mulai susah dibaca labelnya.
        trend_series_chart = {
            "type": "bar_line",
            "categories": _time_series["labels"][-8:],
            "values": _time_series["counts"][-8:],
            "cumulative": (_time_series.get("cumulative") or [])[-8:],
        }

    # ---------------- Ringkasan Analisis: Trend + Severity + Risk (tiap tile = 1 kandidat) ----
    # 3 dari 6 field WAJIB yang AI SELALU tulis & bisa diedit user di tab Edit Text. Sebelumnya
    # dipaksa 1 block "insight_dashboard" berisi tiles — sekarang tiap tile jadi kandidat
    # SENDIRI (tema "insight") supaya bisa juga bergabung dgn dynamic_section AI lain yang
    # temanya sama (analisis naratif + chart pendukung kecil), bukan cuma sesama tile bawaan.
    # RANCANG ULANG (permintaan user): chart di tile-tile ini SEBELUMNYA punya fallback
    # "pinjam" category_chart/status_chart kalau chart genuine topiknya sendiri tidak ada —
    # akibatnya breakdown kategori yang SAMA bisa muncul berulang kali dlm bentuk berbeda-beda
    # (bar/donut/stacked) di halaman yang berdekatan, terasa "kebanyakan grafik" tanpa
    # menambah informasi baru. Sekarang HANYA chart yang genuinely topiknya sendiri yang
    # dipakai (trend_series_chart utk tren, severity_gauge utk severity) — kalau tidak ada,
    # tile tampil TEKS SAJA (caption lebih panjang, 2 kalimat bukan 1) drpd memaksakan chart
    # daur ulang.
    _trend_narrative_resolved = _resolve_templated_narrative(ai_summary.get("trend_analysis"), report_stats, report=report)
    if is_included("trend_analysis") and _trend_narrative_resolved:
        caption = _shorten_to_caption(sanitize_text(coerce_narrative_text(_trend_narrative_resolved)), max_sentences=2)
        prior_texts.append(caption)
        _has_own_visual = bool(trend_stat or trend_series_chart)
        # PERMINTAAN USER (C5, "panel bertingkat"): kalau tile ini TIDAK punya chart/angka
        # genuine topiknya sendiri, coba tumpuk daftar kategori dari pool bersama (lihat
        # _take_pool_item) drpd tampil teks polos kosong.
        # BUG NYATA DITEMUKAN (Prioritas 2 poin 8, dilaporkan user dgn bukti konkret): sampai
        # baris ini SAJA yang masih jatuh ke `aux_stat_value` (= hero_stat, lihat definisinya —
        # cuma "kolom numerik PERTAMA menurut urutan dict", TIDAK ADA hubungan apa pun dgn
        # topik "Analisis Tren") kalau _pool_items juga kosong — panel "Trend Analysis" bisa
        # menampilkan angka rata-rata kolom X besar-besar sementara caption/bullet-nya (tulisan
        # AI) membahas kolom Y sama sekali. Panel severity_analysis/risk_assessment SUDAH
        # diperbaiki lebih dulu ke `aux_stat=None` tetap (lihat komentar "F4" di bawah) - panel
        # ini disamakan skr: TIDAK PERNAH lagi menampilkan aux_stat_value. Kalau metrik yang
        # genuinely relevan dgn topik "tren" tidak bisa dipastikan (belum ada penunjuk
        # metrik/dimensi eksplisit dari AI, lihat rencana placeholder Tahap 3), angka itu
        # LEBIH BAIK TIDAK ditampilkan sama sekali drpd menampilkan angka yang salah topik.
        _pool_items, _pool_total = (None, None) if _has_own_visual else _take_pool_item()
        candidates.append(_candidate(
            "insight_tile", "insight", 0.22, False,
            kicker=_L(report, "ANALISIS", "ANALYSIS"), title=_L(report, "Analisis Tren", "Trend Analysis"),
            label=_L(report, "Analisis Tren", "Trend Analysis"),
            trend_stat=None if trend_series_chart else trend_stat,
            chart=trend_series_chart,
            aux_stat=None,
            aux_list=_pool_items, aux_list_total=_pool_total,
            caption=caption,
        ))

    # BUG DIPERBAIKI (dilaporkan user): "Severity"/"Penilaian Risiko" SEBELUMNYA SELALU
    # muncul asal AI menulis teksnya, apa pun jenis datanya — utk domain yang genuinely tidak
    # punya konsep severity/risiko keamanan (mis. data keuangan/KPI TANPA kolom severity),
    # 2 tile ini cuma memaksakan istilah yang tidak relevan. Sekarang HANYA muncul kalau
    # datanya domain keamanan ATAU genuinely punya data severity terdeteksi (total_sev > 0)
    # — sama seperti syarat halaman severity_distribution di bawah, supaya konsisten.
    _severity_relevant = sec_domain or total_sev > 0
    if _severity_relevant and is_included("severity_analysis") and ai_summary.get("severity_analysis"):
        sev_label = _L(report, "Tingkat Keparahan", "Severity") if sec_domain else _L(report, "Distribusi & Prioritas", "Distribution & Priority")
        caption = _shorten_to_caption(sanitize_text(coerce_narrative_text(ai_summary.get("severity_analysis"))), max_sentences=2)
        prior_texts.append(caption)
        # PERMINTAAN USER (F4, mirror perbaikan aux_stat dynamic_section di bawah): kalau tile
        # ini tidak punya chart genuine topiknya sendiri, JANGAN jatuh ke aux_stat_value (angka
        # global tidak selalu nyambung dgn topik "Severity"). Dicoba tumpuk daftar kategori
        # dari pool bersama (C5, "panel bertingkat") sbg gantinya drpd teks polos kosong.
        _sev_pool_items, _sev_pool_total = (None, None) if severity_gauge else _take_pool_item()
        candidates.append(_candidate(
            "insight_tile", "insight", 0.22, False,
            kicker=_L(report, "ANALISIS", "ANALYSIS"), title=sev_label,
            label=sev_label, trend_stat=None, chart=severity_gauge,
            aux_stat=None, aux_list=_sev_pool_items, aux_list_total=_sev_pool_total, caption=caption,
        ))

    if _severity_relevant and is_included("risk_assessment") and ai_summary.get("risk_assessment"):
        caption = _shorten_to_caption(sanitize_text(coerce_narrative_text(ai_summary.get("risk_assessment"))), max_sentences=2)
        prior_texts.append(caption)
        # PERMINTAAN USER (F4 + C5): sama dgn severity_analysis — tile ini tidak punya chart
        # genuine sama sekali, coba tumpuk daftar kategori dari pool bersama drpd aux_stat_value
        # (angka global) atau teks polos kosong.
        _risk_pool_items, _risk_pool_total = _take_pool_item()
        candidates.append(_candidate(
            "insight_tile", "insight", 0.22, False,
            kicker=_L(report, "ANALISIS", "ANALYSIS"), title=_L(report, "Penilaian Risiko", "Risk Assessment"),
            label=_L(report, "Penilaian Risiko", "Risk Assessment"),
            trend_stat=None, chart=None,
            aux_stat=None, aux_list=_risk_pool_items, aux_list_total=_risk_pool_total, caption=caption,
        ))

    # dynamic_section (section kustom AI) SEKARANG SELALU TEKS SAJA (tanpa chart daur ulang)
    # — ini narasi topik spesifik tulisan AI, lebih pas diberi ruang teks penuh drpd dipaksa
    # ditemani chart generik yang seringnya kebetulan sama dgn chart di halaman lain.
    dynamic_sections = [s for s in (ai_summary.get("sections") or []) if isinstance(s, dict)]
    # BUG DIPERBAIKI (dilaporkan user, disertai perbandingan checklist Include Sections vs
    # laporan jadi — topik order 0 hilang total): section PERTAMA (order 0) SEBELUMNYA selalu
    # dilewati di sini dgn asumsi isinya "ringkasan eksekutif tingkat tinggi" yang sudah
    # ditampilkan di kandidat Ringkasan Eksekutif lewat caption di atas — asumsi itu TIDAK
    # SELALU benar (topik order 0 bisa genuinely spesifik & berbeda, mis. "Overview of
    # Production Performance" yang dicentang user tapi tidak pernah muncul sama sekali).
    # Permintaan user JELAS: SEMUA topik yang dicentang HARUS masuk laporan, jadi section 0
    # SEKARANG ikut diproses sama seperti section lainnya.
    # BUG DIPERBAIKI (dilaporkan user): `aux_stat_value` (hero_stat — 1 angka GLOBAL laporan,
    # mis. "38% E-Katalog") SEBELUMNYA ditempel ke SETIAP kartu dynamic_section yang topiknya
    # TIDAK kebagian aux_list (idx genap) — angka yang SAMA PERSIS jadi muncul berulang di
    # banyak kartu section custom AI yang topiknya beda-beda (mis. "Overview of Procurement
    # Activities" DAN "Analysis of Vendor Performance" sama2 menampilkan "38% E-Katalog"),
    # padahal angka itu genuinely tidak ada hubungannya dgn topik section-nya masing2 — TIDAK
    # ADA cara andal utk tahu metrik mana yang genuinely relevan dgn topik bebas tulisan AI
    # (beda dgn aux_list, yang breakdown kategori generik & netral thd topik apa pun). Section
    # yang tidak kebagian aux_list SEKARANG kirim aux_stat=None — kartunya teks saja, bukan
    # dipaksa nempel angka yang belum tentu nyambung.
    for idx, sec in enumerate(dynamic_sections):
        sec_title = sanitize_text(coerce_narrative_text(sec.get("title")))
        sec_content = sanitize_text(coerce_narrative_text(sec.get("content")))
        if not sec_title or not sec_content:
            continue
        # BUG DIPERBAIKI (ditemukan sendiri lewat verifikasi render — 2 kartu topik BEDA,
        # "Overview of Traffic Patterns" & "Analysis of Blocked Traffic", tampil dgn breakdown
        # jam yang PERSIS SAMA "00:00: 10.0%" dst): rotasi dgn toleransi 2x/varian TERNYATA
        # masih menghasilkan "angka yang sama di kartu tidak nyambung" — kelas bug sama persis
        # yang coba dihindari (lihat catatan aux_stat_value). Pool SEKARANG dipakai lewat
        # _take_pool_item() — indeks BERSAMA dgn insight_tile (Tren/Severity/Risiko) di atas,
        # jadi 1 entri pool TIDAK PERNAH terpakai 2x oleh kartu manapun, topik apapun.
        pick_items, pick_total = _take_pool_item()
        text = _shorten_to_caption(sec_content, max_sentences=3)
        prior_texts.append(text)
        candidates.append(_candidate(
            "dynamic_section", "insight", 0.25, False,
            kicker=_L(report, "ANALISIS", "ANALYSIS"), title=sec_title,
            text=text, chart=None,
            aux_stat=None,
            aux_list=pick_items, aux_list_total=pick_total,
        ))

    # ---------------- Distribusi Kategori/Status/Radar KPI/Pola Waktu (tiap panel = 1 kandidat) --
    # Data DIHITUNG PERSIS sama seperti sebelumnya (tidak ada perubahan angka/logika) — yang
    # berubah cuma cara dikumpulkannya (kandidat lepas, bukan langsung dipaksa 1 block
    # "distribution_dashboard" tetap 2 kolom). severity_distribution TETAP condong jadi halaman
    # sendiri (bobotnya sengaja tinggi) karena sudah cukup padat: chart + panel highlight crit%.
    if category_pick and is_included("category_distribution"):
        label, items = category_pick
        top_items = items[:6]
        cat_total = sum(i["count"] for i in items) or 1
        # PERMINTAAN USER: grouped bar dgn BANYAK kategori jangan dipaksa berbagi halaman dgn
        # panel lain (kolom jadi sempit, label kategori kepotong/tumpang tindih) — kalau
        # kategorinya sedikit (<=5), tetap boleh berdampingan spt sebelumnya (bobot wajar).
        cat_dist_weight = 0.42 if len(top_items) <= 5 else 1.0
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
            {"color_index": _stable_color_index(it["value"]), "name": it["value"], "pct": round(it["count"] / cat_total * 100, 1)}
            for i, it in enumerate(top_items)
        ]
        ai_caption = _get_chart_caption("category", fallback=sanitize_text(_L(
            report,
            f"{top_items[0]['value']} mencatat volume tertinggi dengan {top_items[0]['count']} dari {cat_total} data "
            f"({round(top_items[0]['count']/cat_total*100,1)}%). Konsentrasi pada kategori ini bisa jadi dasar "
            f"evaluasi kebijakan atau alokasi sumber daya operasional ke depan.",
            f"{top_items[0]['value']} recorded the highest volume with {top_items[0]['count']} of {cat_total} records "
            f"({round(top_items[0]['count']/cat_total*100,1)}%). This concentration can guide policy evaluation or "
            f"operational resource allocation going forward.",
        )))
        prior_texts += [intro, ai_caption]
        candidates.append(_candidate(
            "category_distribution", "distribution", cat_dist_weight, False,
            kicker=_L(report, "ANALISIS DATA", "DATA ANALYSIS"),
            title=_L(report, f"Distribusi Event Berdasarkan {humanize_label(label, source_cols)}", f"Event Distribution by {humanize_label(label, source_cols)}") if sec_domain
            else _L(report, f"Distribusi Data Berdasarkan {humanize_label(label, source_cols)}", f"Data Distribution by {humanize_label(label, source_cols)}"),
            label=humanize_label(label, source_cols), raw_label=label,
            categories=[i["value"] for i in top_items], values=[i["count"] for i in top_items],
            legend=legend, legend_panel_title=_L(report, "Proporsi Kategori", "Category Proportion"),
            intro=intro,
            footnote=sanitize_text(_L(
                report,
                f"{top_items[0]['value']} menjadi kontributor volume terbesar pada kategori ini.",
                f"{top_items[0]['value']} is the largest volume contributor in this category.",
            )),
            ai_caption=ai_caption,
        ))

    if status_items and is_included("status_distribution"):
        status_total = sum(i["count"] for i in status_items) or 1
        top_status = status_items[0]
        status_intro = sanitize_text(_L(
            report,
            f"{round(top_status['count']/status_total*100,1)}% event berstatus {top_status['value']}. "
            f"Sebagian kecil masih memerlukan tindak lanjut aktif.",
            f"{round(top_status['count']/status_total*100,1)}% of events are in {top_status['value']} status. "
            f"A small portion still requires active follow-up.",
        ))
        top_status_items = status_items[:8]
        # Sama spt category_distribution di atas — status dgn banyak varian jangan dipaksa
        # berbagi kolom sempit dgn panel lain.
        status_dist_weight = 0.42 if len(top_status_items) <= 5 else 1.0
        status_caption = sanitize_text(_L(
            report,
            f"{round(top_status['count']/status_total*100,1)}% dari {status_total} event berstatus {top_status['value']}. "
            f"Sisanya tersebar di status lain yang perlu terus dipantau agar tidak menumpuk jadi backlog.",
            f"{round(top_status['count']/status_total*100,1)}% of {status_total} events are in {top_status['value']} status. "
            f"The remainder is spread across other statuses that need ongoing monitoring to avoid becoming a backlog.",
        ))
        prior_texts += [status_intro, status_caption]
        candidates.append(_candidate(
            "status_distribution", "distribution", status_dist_weight, False,
            kicker=_L(report, "ANALISIS DATA", "DATA ANALYSIS"),
            title=_L(report, "Status Penanganan Insiden", "Incident Handling Status"),
            categories=[i["value"] for i in top_status_items], values=[i["count"] for i in top_status_items],
            intro=status_intro, ai_caption=_get_chart_caption("status", fallback=status_caption),
        ))

    radar_data = _compute_kpi_radar(report_stats.get("numeric_summary") or {}, source_cols)
    if radar_data and is_included("kpi_radar"):
        top_axis_idx = max(range(len(radar_data["values"])), key=lambda i: radar_data["values"][i])
        radar_intro = sanitize_text(_L(
            report,
            f"{radar_data['axes'][top_axis_idx]} mencatat capaian tertinggi di antara {len(radar_data['axes'])} indikator yang dibandingkan.",
            f"{radar_data['axes'][top_axis_idx]} recorded the highest achievement among the {len(radar_data['axes'])} indicators compared.",
        ))
        prior_texts.append(radar_intro)
        # REGRESI DIPERBAIKI (dilaporkan user: halaman ini 19 elemen/180 karakter, jauh di
        # bawah ambang). Halaman radar SENGAJA selalu solo (butuh ruang, lihat catatan bobot
        # 1.0 di bawah) - jadi menggabungkannya justru menyempitkan chart yang memang perlu
        # ruang. Yang kurang bukan ruangnya, tapi ISINYA: jalur Management (
        # _build_chart_insight_page) SUDAH menurunkan catatan per-sumbu dari data yang SAMA,
        # sementara jalur SOC ini cuma punya 1 kalimat. Catatan yang sama diturunkan di sini -
        # angka ASLI yang memang sudah digambar chart-nya, bukan teks pengisi.
        _r_axes, _r_vals = radar_data["axes"], radar_data["values"]
        _r_avg = sum(_r_vals) / len(_r_vals)
        _r_low = min(range(len(_r_vals)), key=lambda i: _r_vals[i])
        radar_notes = [
            # Sama seperti versi Management: angka radar adalah skor ternormalisasi, WAJIB
            # dinyatakan supaya tidak dikira nilai asli dalam satuan aslinya.
            _L(report,
               "Nilai pada radar ini adalah skor relatif 0-100 (rata-rata sbg persentase dari nilai maksimum tiap indikator), BUKAN nilai asli dalam satuan aslinya.",
               "Values on this radar are relative 0-100 scores (each indicator's average as a percentage of its own maximum), NOT raw values in their native unit."),
            radar_intro,
        ]
        # Kalau seluruh sumbu praktis SETARA (selisih tertinggi-terendah <1 poin), kalimat
        # "tertinggi" & "terendah" jadi menunjuk sumbu yang SAMA dgn selisih 0 - kontradiktif &
        # tidak memberi informasi apa pun. Kasus itu dinyatakan apa adanya sbg SATU fakta.
        _r_spread = max(_r_vals) - min(_r_vals)
        if _r_spread < 1:
            radar_notes = [radar_notes[0], _L(
                report,
                f"Ketiga indikator berada pada tingkat yang setara (~{_r_avg:.0f} dari 100), tidak ada yang menonjol di atas yang lain."
                if len(_r_axes) == 3 else
                f"Seluruh {len(_r_axes)} indikator berada pada tingkat yang setara (~{_r_avg:.0f} dari 100).",
                f"All {len(_r_axes)} indicators sit at a comparable level (~{_r_avg:.0f} of 100), none stands out above the others.",
            )]
        elif len(_r_axes) > 1:
            radar_notes.append(_L(
                report,
                f"{_r_axes[_r_low]} paling rendah ({_r_vals[_r_low]:.0f}), selisih {_r_vals[top_axis_idx] - _r_vals[_r_low]:.0f} poin dari yang tertinggi.",
                f"{_r_axes[_r_low]} is the lowest ({_r_vals[_r_low]:.0f}), a gap of {_r_vals[top_axis_idx] - _r_vals[_r_low]:.0f} points from the highest.",
            ))
        for _i, _ax in enumerate(_r_axes):
            if _r_spread < 1 or _i in (top_axis_idx, _r_low):
                continue
            _dev = _r_vals[_i] - _r_avg
            _arah = _L(report, "di atas", "above") if _dev >= 0 else _L(report, "di bawah", "below")
            radar_notes.append(_L(
                report,
                f"{_ax} mencatat skor {_r_vals[_i]:.0f}, {abs(round(_dev))} poin {_arah} rata-rata seluruh indikator.",
                f"{_ax} scored {_r_vals[_i]:.0f}, {abs(round(_dev))} points {_arah} the average across all indicators.",
            ))
        # Bobot 1.0 = SELALU halaman sendiri (radar butuh ruang: banyak sumbu + label
        # berputar). TAPI itu cuma beralasan kalau radarnya genuinely punya yang ditunjukkan.
        # REGRESI DIPERBAIKI (dilaporkan user: halaman ini 19 elemen/180 karakter): kalau
        # SELURUH sumbu praktis setara (_r_spread < 1), radar itu tidak membandingkan apa pun -
        # bentuknya segitiga sama sisi kecil di tengah. Halaman penuh utk itu jelas boros, jadi
        # bobotnya diturunkan supaya BOLEH berbagi halaman dgn panel lain (isinya tetap tampil
        # utuh, cuma tidak lagi memakan 1 halaman sendiri). Kalau radarnya genuinely bervariasi,
        # perilaku lama (halaman sendiri) TIDAK berubah.
        _radar_weight = 0.45 if _r_spread < 1 else 1.0
        candidates.append(_candidate(
            "kpi_radar", "distribution", _radar_weight, False,
            kicker=_L(report, "ANALISIS DATA", "DATA ANALYSIS"),
            title=_L(report, "Perbandingan Capaian Multi-Indikator", "Multi-Indicator Achievement Comparison"),
            axes=radar_data["axes"], values=radar_data["values"], intro=radar_notes,
        ))

    heatmap_data = _compute_day_hour_pattern(parsed_data, date_col)
    if heatmap_data and is_included("time_heatmap"):
        heatmap_intro = sanitize_text(_L(
            report,
            f"Pola kejadian dipetakan dari {heatmap_data['total']} baris bertanggal valid, membantu mengenali hari/jam dengan aktivitas terpadat.",
            f"The event pattern is mapped from {heatmap_data['total']} validly dated rows, helping identify the busiest day/hour combinations.",
        ))
        prior_texts.append(heatmap_intro)
        candidates.append(_candidate(
            # PERMINTAAN USER: heatmap grid (7 hari x 24 jam) butuh ruang penuh spy tiap sel
            # tetap terbaca — jangan dipaksa berbagi halaman, SELALU jadi halaman sendiri.
            "time_heatmap", "distribution", 1.0, False,
            kicker=_L(report, "ANALISIS DATA", "DATA ANALYSIS"),
            title=_L(report, "Pola Kejadian per Hari & Jam", "Event Pattern by Day & Hour"),
            day_labels=[_L(report, id_, en_) for id_, en_ in heatmap_data["day_labels"]], hour_labels=heatmap_data["hour_labels"],
            grid=heatmap_data["grid"], intro=heatmap_intro,
        ))

    if category_pick and date_col and is_included("period_compare"):
        compare_data = _compute_period_compare(parsed_data, date_col, source_cols.get(category_pick[0]), [it["value"] for it in category_pick[1][:4]])
        if compare_data:
            compare_intro = sanitize_text(_L(
                report,
                "Perbandingan jumlah kejadian antara paruh awal dan paruh akhir periode data, per kategori teratas.",
                "Comparison of event counts between the first and second half of the data period, by top category.",
            ))
            prior_texts.append(compare_intro)
            candidates.append(_candidate(
                "period_compare", "distribution", 0.45, False,
                kicker=_L(report, "ANALISIS DATA", "DATA ANALYSIS"),
                title=_L(report, "Perbandingan Antar Paruh Periode", "Period-over-Period Comparison"),
                categories=compare_data["categories"], series_a=compare_data["series_a"], series_b=compare_data["series_b"],
                label_a=_L(report, "Paruh Awal", "First Half"), label_b=_L(report, "Paruh Akhir", "Second Half"),
                intro=compare_intro,
            ))

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
        sev_caption = sanitize_text(_L(
            report,
            f"Critical mencapai {crit_pct}% dan High {high_pct}% dari seluruh {total_sev} event. "
            f"Gabungan proporsi setinggi ini perlu diprioritaskan penanganannya agar tidak berdampak lebih luas ke operasional.",
            f"Critical accounts for {crit_pct}% and High {high_pct}% of all {total_sev} events. "
            f"This combined high proportion should be prioritized to avoid broader operational impact.",
        ))
        prior_texts += [intro, sev_caption]
        candidates.append(_candidate(
            "severity_distribution", "distribution", 0.8, False,
            kicker=_L(report, "ANALISIS DATA", "DATA ANALYSIS"),
            title=_L(report, "Distribusi Tingkat Keparahan (Severity)", "Severity Distribution"),
            categories=[SEVERITY_LABEL[k] for k in SEVERITY_ORDER], values=[severity.get(k, 0) for k in SEVERITY_ORDER],
            severity_keys=list(SEVERITY_ORDER), intro=intro, crit_pct=crit_pct,
            panel_text=_L(report, "dari seluruh event berstatus Critical Severity", "of all events at Critical severity"),
            detail_text=detail_text, ai_caption=_get_chart_caption("severity", fallback=sev_caption),
        ))

    # ---------------- Tabel Insiden Critical/Prioritas Tinggi ----------------
    if severity_col and parsed_data:
        critical_rows = [row for row in parsed_data if _classify_severity_value(str(row.get(severity_col, ""))) == "critical"]
        if len(critical_rows) < 5:
            critical_rows += [row for row in parsed_data if _classify_severity_value(str(row.get(severity_col, ""))) == "high"]
        critical_rows = critical_rows[:12]

        if critical_rows and is_included("critical_table"):
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

            candidates.append(_candidate(
                "critical_table", "highlight", 1.0, False,
                kicker=_L(report, "SOROTAN INSIDEN", "INCIDENT HIGHLIGHT") if sec_domain else _L(report, "SOROTAN DATA", "DATA HIGHLIGHT"),
                title=_L(report, f"{len(critical_rows)} Insiden Prioritas Tinggi", f"{len(critical_rows)} High-Priority Incidents") if sec_domain
                else _L(report, f"{len(critical_rows)} Item Prioritas Tinggi", f"{len(critical_rows)} High-Priority Items"),
                headers=headers, rows=rows_out, highlight_idx=highlight_idx, open_count=open_count,
                kicker_is_critical=bool(open_count),
                caption=sanitize_text(_L(
                    report,
                    f"Baris merah menandai {open_count} insiden yang masih dalam proses penanganan per akhir periode data.",
                    f"Red rows mark {open_count} incidents still in progress as of the end of the data period.",
                ) if sec_domain else _L(
                    report,
                    f"Baris merah menandai {open_count} item yang masih dalam proses per akhir periode data.",
                    f"Red rows mark {open_count} items still in progress as of the end of the data period.",
                )) if open_count else None,
            ))

    # ---------------- Aset Paling Sering Menjadi Sasaran ----------------
    if asset_pick and is_included("asset_cards"):
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
        candidates.append(_candidate(
            "asset_cards", "highlight", 0.68, True,
            kicker=_L(report, "SOROTAN INSIDEN", "INCIDENT HIGHLIGHT") if sec_domain else _L(report, "SOROTAN DATA", "DATA HIGHLIGHT"),
            title=_L(
                report,
                f"{humanize_label(label, source_cols)} yang Paling Sering Menjadi Sasaran",
                f"Most Frequently Affected {humanize_label(label, source_cols)}",
            ) if sec_domain else _L(
                report,
                f"{humanize_label(label, source_cols)} Paling Sering Muncul",
                f"Most Frequent {humanize_label(label, source_cols)}",
            ),
            label=humanize_label(label, source_cols), items=card_items,
        ))

    # ---------------- Temuan Utama, Rekomendasi, Kesimpulan ----------------
    # PERMINTAAN USER: 3 halaman penutup ini (Temuan Utama/Rekomendasi/Kesimpulan) sering
    # berakhir masing2 terisi < 1/4 halaman. Datanya dihitung DULU (tanpa langsung ditambahkan
    # sbg candidate halaman terpisah) supaya bisa diputuskan belakangan: kalau KETIGANYA
    # genuinely tipis, satukan jadi 1 halaman "closing_summary" (temuan kiri, rekomendasi
    # berbadge prioritas kanan, kesimpulan sbg strip bawah). Kalau salah satu genuinely
    # "berisi" (rekomendasi banyak & narasinya panjang, mis.), biarkan 3 halaman terpisah spt
    # semula — keputusan dari VOLUME isi, bukan aturan tetap.

    findings_items = None
    if key_findings and is_included("key_findings"):
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
        # Halaman "Temuan Utama" yang cuma berisi SATU butir tidak layak berdiri sendiri
        # (halaman nyaris kosong) — gabungkan ke Ringkasan Eksekutif (kalau panel itu ada di
        # laporan ini) drpd dipaksa jadi halaman/kandidat closing_summary. Kalau Ringkasan
        # Eksekutif TIDAK disertakan user, tidak ada tempat menampung — tetap ikut alur
        # normal di bawah (jadi halaman sendiri, atau ikut closing_summary kalau memenuhi).
        exec_summary_cand = next((c for c in candidates if c["panel_kind"] == "executive_summary"), None)
        if len(findings_items) == 1 and exec_summary_cand is not None:
            only = findings_items[0]
            exec_summary_cand["extra_finding_label"] = _L(report, "Temuan:", "Finding:")
            exec_summary_cand["extra_finding_text"] = sanitize_text(f"{only['title']} {only['detail']}".strip())
            findings_items = None
        else:
            prior_texts += key_findings

    recommendations_shown = bool(is_included("recommendations") and recommendations)
    rec_items = None
    if recommendations_shown:
        rec_items = []
        # AI menuliskan rekomendasi urut prioritas TERTINGGI dulu (lihat prompts.py) — bukan
        # dihitung dari data, jadi levelnya didekati dari URUTAN kemunculan (index), sama
        # persis pola build_management_report_blocks::urgency_map di bawah supaya kedua gaya
        # laporan konsisten (badge prioritas di kartu rekomendasi, lihat export_pdf.py
        # URGENCY_COLOR / export_ppt.py padanannya).
        _urgency_map = ["critical", "high", "medium", "low"]
        for idx, item in enumerate(recommendations):
            raw_title = item.get("title")
            raw_detail = item.get("detail") or ""
            if raw_title:
                title_txt = raw_title
                detail_txt = raw_detail or None
            else:
                # Tidak ada title terpisah — ambil kalimat pertama sebagai judul lewat batas
                # kalimat alami (". "), BUKAN potongan jumlah karakter tetap.
                title_txt, _, rest = raw_detail.partition(". ")
                detail_txt = rest.strip() or None
                if not title_txt:
                    title_txt = raw_detail
                elif not detail_txt and len(title_txt) > 70:
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
                "urgency": _urgency_map[min(idx, len(_urgency_map) - 1)],
            })
        prior_texts += [r["title"] for r in rec_items] + [r["detail"] for r in rec_items if r["detail"]]

    conclusion_text = None
    conclusion_pills: list = []
    conclusion_priority_items: list = []
    if is_included("conclusion") and ai_summary.get("conclusion"):
        _raw_conclusion = sanitize_text(coerce_narrative_text(ai_summary.get("conclusion")))
        _raw_conclusion, _ = _verify_narrative_sentences(
            _raw_conclusion, report_stats, field_name="conclusion", report_id=getattr(report, "id", None),
            parsed_data=parsed_data,
        )
        if _raw_conclusion and _conclusion_adds_new_insight(_raw_conclusion, prior_texts):
            conclusion_text = _raw_conclusion
            if total_sev and status_col:
                resolved_pct = round((total_sev - open_count) / total_sev * 100, 1)
                conclusion_pills.append(_L(
                    report,
                    f"{resolved_pct}% event tertangani" if sec_domain else f"{resolved_pct}% data tertangani",
                    f"{resolved_pct}% of events resolved",
                ))
            if category_pick:
                conclusion_pills.append(_L(
                    report,
                    f"{category_pick[1][0]['value']} jadi prioritas perhatian",
                    f"{category_pick[1][0]['value']} is the top priority",
                ))
            if open_count:
                conclusion_pills.append(_L(
                    report,
                    f"{open_count} insiden masih berjalan" if sec_domain else f"{open_count} item masih berjalan",
                    f"{open_count} incidents still in progress" if sec_domain else f"{open_count} items still in progress",
                ))
            # BUG DIPERBAIKI (dilaporkan user): kalau halaman "Rekomendasi Mitigasi" SUDAH
            # tampil, daftar "Prioritas Berikutnya" ini mengambil item PERTAMA dari
            # `recommendations` YANG SAMA PERSIS — hasilnya 2 halaman berurutan menampilkan
            # rekomendasi yang identik. Diisi HANYA kalau Rekomendasi Mitigasi tidak tampil
            # (baik sbg halaman sendiri MAUPUN sbg bagian closing_summary gabungan).
            if not recommendations_shown:
                for idx, rec in enumerate(recommendations):
                    letter = chr(ord("a") + idx) if idx < 26 else str(idx + 1)
                    rec_title = rec.get("title") or (rec.get("detail") or "").partition(". ")[0] or rec.get("detail") or ""
                    conclusion_priority_items.append({"letter": letter, "text": sanitize_text(rec_title)})

    # PERMINTAAN USER EKSPLISIT: "Keputusannya dari volume isi, bukan dari aturan tetap" —
    # dihitung 1 skor estimasi total "tinta" (karakter teks + overhead tetap per-item utk
    # badge/padding/jarak antar kartu), BUKAN aturan kaku spt "maks N item" atau "maks N
    # karakter/item" terpisah. Efeknya otomatis menangkap kasus yang disebutkan user: 5
    # rekomendasi PENDEK tetap boleh gabung (total tintanya kecil), sebaliknya 3 rekomendasi
    # yang MASING-MASING narasinya panjang tetap dipisah (total tintanya besar) walau
    # jumlah itemnya sedikit.
    findings_volume = (
        sum(len(it["title"]) + len(it["detail"] or "") for it in findings_items) + len(findings_items) * 35
    ) if findings_items is not None else 0
    rec_volume = (
        sum(len(it["title"]) + len(it.get("detail") or "") for it in rec_items) + len(rec_items) * 45
    ) if rec_items is not None else 0
    conclusion_preview = _shorten_to_caption(conclusion_text, max_sentences=2) if conclusion_text is not None else None
    conclusion_volume = (
        len(conclusion_preview) + len(conclusion_pills) * 45 + 60
    ) if conclusion_preview is not None else 0

    # PERMINTAAN USER LANJUTAN (tes kepadatan halaman menemukan "Kesimpulan" solo jadi
    # penyumbang kegagalan TERBANYAK, 53 dari 146): dulu digabung HANYA kalau Temuan &
    # Rekomendasi SAMA-SAMA ada — laporan yang cuma menyertakan SALAH SATU (mis. checklist
    # "Include Sections" user tidak mencentang Rekomendasi) selalu berakhir Kesimpulan solo,
    # padahal SATU dari keduanya SUDAH cukup jadi teman gabung yang genuinely mengisi
    # halaman. Sekarang cukup MINIMAL 2 dari 3 (Temuan/Rekomendasi/Kesimpulan) hadir —
    # _build_closing_summary_block/_slide digeneralisasi jadi 1-atau-2-kolom (lihat di sana).
    # Kalau Kesimpulan genuinely SENDIRIAN (Temuan & Rekomendasi berdua tidak ada sama
    # sekali), tidak ada yang bisa digabung — dibiarkan solo spt biasa (sudah dinamis dari
    # isi teksnya sendiri, lihat perbaikan E3 sebelumnya di _build_conclusion_block/_slide).
    COMBINE_VOLUME_BUDGET = 1300
    # REGRESI DIPERBAIKI (dilaporkan user, laporan 181 hal.05: 4 elemen - DI BAWAH lantai
    # keras). Budget di atas ada utk mencegah 1 halaman terlalu penuh, TAPI ketika Kesimpulan
    # sendirian genuinely TIPIS, alternatif "dipisah" justru menghasilkan halaman berisi judul
    # + satu paragraf saja. Kasus nyatanya cuma lewat 49-139 poin dari budget (1349-1439),
    # sementara halaman hasil pisahnya 4 elemen/331 karakter. Jadi ketika Kesimpulan sendirian
    # tipis, budget digeser ke ambang yang lebih longgar - BUKAN dihapus, supaya kombinasi yang
    # genuinely berat tetap dipisah spt semula.
    _CONCLUSION_SOLO_THIN_VOLUME = 700
    _COMBINE_BUDGET_THIN_CONCLUSION = 1600
    _budget = (
        _COMBINE_BUDGET_THIN_CONCLUSION
        if 0 < conclusion_volume <= _CONCLUSION_SOLO_THIN_VOLUME
        else COMBINE_VOLUME_BUDGET
    )
    _closing_present_count = sum(x is not None for x in (findings_items, rec_items, conclusion_text))
    should_combine_closing = (
        _closing_present_count >= 2
        and (findings_items is None or len(findings_items) <= 6)
        and (rec_items is None or len(rec_items) <= 6)
        and (findings_volume + rec_volume + conclusion_volume) <= _budget
    )

    closing_summary_block = None
    if should_combine_closing:
        if findings_items is not None and rec_items is not None:
            combined_title = _L(report, "Temuan, Rekomendasi & Kesimpulan", "Findings, Recommendations & Conclusion")
        elif findings_items is not None:
            combined_title = _L(report, "Temuan Utama & Kesimpulan", "Key Findings & Conclusion")
        else:
            combined_title = _L(report, "Rekomendasi & Kesimpulan", "Recommendations & Conclusion")
        closing_summary_block = {
            "kind": "closing_summary", "dark": False,
            "kicker": _L(report, "RINGKASAN AKHIR", "FINAL SUMMARY"),
            "title": combined_title,
            "findings_title": _L(report, "Temuan Utama", "Key Findings") if findings_items is not None else None,
            "findings_items": findings_items,
            "rec_title": _L(report, "Rekomendasi", "Recommendations") if rec_items is not None else None,
            "recommendation_items": rec_items,
            "conclusion_title": _L(report, "Kesimpulan", "Conclusion") if conclusion_preview is not None else None,
            "conclusion_text": conclusion_preview,
            "conclusion_pills": conclusion_pills if conclusion_preview is not None else [],
        }
    else:
        if findings_items is not None:
            # BUG DIPERBAIKI (permintaan user — tes kepadatan halaman menemukan "Temuan
            # Utama" jadi penyumbang kegagalan #2 terbanyak): weight dulu TETAP 0.7 apa pun
            # jumlah butirnya — halaman 2-3 butir pendek lolos ambang backstop MIN_FULL(0.6)
            # padahal renderannya genuinely tipis. Diskalakan dari JUMLAH butir (pola sama
            # dgn "recommendations" di bawah) supaya backstop merge (_group_candidates_into_
            # pages) benar2 mengenali halaman tipis & menyambungnya ke tetangga.
            candidates.append(_candidate(
                "key_findings", "highlight", min(0.9, 0.3 + 0.13 * len(findings_items)), False,
                kicker=_L(report, "ANALISIS", "ANALYSIS"), title=_L(report, "Temuan Utama", "Key Findings"),
                items=findings_items,
                # Panel visual pendukung — pakai ulang persis data yang sudah dihitung di atas.
                chart=severity_gauge or category_chart or status_chart,
            ))
        if rec_items is not None:
            # SOC memakai maksimal 4 rekomendasi per halaman agar judul dan keterangan panjang
            # tetap terbaca (dinaikkan dari 2 — lihat _balanced_chunks di atas utk alasan
            # lengkap kenapa batas SEBELUMNYA 2 justru menyebabkan gaya visual gonta-ganti di
            # tengah laporan). _balanced_chunks meratakan jumlah HALAMAN dulu baru itemnya,
            # jadi tidak akan pernah ada 1 halaman leftover berisi cuma 1 item selama
            # totalnya >= 2.
            for chunk_index, chunk in enumerate(_balanced_chunks(rec_items, 4)):
                continuation = chunk_index > 0
                candidates.append(_candidate(
                    "recommendations", "action", min(0.9, 0.35 + 0.09 * len(chunk)), False,
                    kicker=_L(report, "TINDAK LANJUT", "FOLLOW-UP"),
                    title=_L(report, "Rekomendasi Mitigasi" if not continuation else "Rekomendasi Mitigasi (Lanjutan)", "Mitigation Recommendations" if not continuation else "Mitigation Recommendations (Continued)"),
                    items=chunk,
                ))
        if conclusion_text is not None:
            candidates.append(_candidate(
                "conclusion", "action", 0.62, True,
                kicker=_L(report, "RINGKASAN AKHIR", "FINAL SUMMARY"), title=_L(report, "Kesimpulan", "Conclusion"),
                text=_shorten_to_caption(conclusion_text, max_sentences=3), pills=conclusion_pills,
                priority_panel_title=_L(report, "Prioritas Berikutnya", "Next Priorities"),
                priority_items=conclusion_priority_items,
            ))

    # ---------------- TAHAP 2: kelompokkan kandidat jadi halaman ----------------
    pages = _group_candidates_into_pages(candidates, report, sec_domain)
    if closing_summary_block is not None:
        pages.append(closing_summary_block)

    # ---------------- Penutup ----------------
    closing_block = {
        "kind": "closing",
        "dark": True,
        "title": report.title,
        "thank_you": _L(report, "Terima Kasih", "Thank You"),
        "note": _L(report, "Diskusi dan pertanyaan dipersilakan.", "Questions and discussion are welcome."),
        "hero_stat": hero_stat,
        "header_title": (report.header_title or "PT PETROKIMIA GRESIK").upper(),
    }

    return [cover_block, *pages, closing_block]


# ==============================================================================
# Management Report Template
# Template khusus untuk laporan eksekutif/manajemen — lebih banyak grafis,
# KPI cards, risk heatmap, dan action items daripada narasi panjang.
# Dipakai ketika report.template_type == "Management Report"
# ==============================================================================

def build_management_report_blocks(report) -> list[dict]:
    """
    Blok laporan untuk template Management Report — "Visual tinggi, KPI ringkas, peta risiko
    & action items eksekutif" (lihat label di Step2Settings.tsx), pasangan dari
    build_report_blocks() ("SOC Technical Report" — analisis mendalam). Bedanya BUKAN "ada
    chart vs tanpa chart" (dua-duanya sama-sama pakai chart), tapi PORSI & KEPADATAN: di sini
    kartu angka besar-besar + chart jadi sorotan utama, teks penjelasan dipangkas seperlunya
    saja (1-2 kalimat per bagian) — bukan dihilangkan total.

    RANCANG ULANG (permintaan user): 3 BUG NYATA diperbaiki di sini (ditemukan lewat laporan
    sungguhan yang gagal/aneh saat diuji) —
    1. KPI grid & label "Peta Risiko" SEBELUMNYA hardcode istilah keamanan siber (Critical
       Threats/SLA/Insiden) apa pun jenis datanya — utk data non-keamanan (KPI/keuangan/dst)
       semua kartu tampil 0/tidak nyambung. Sekarang ikut menyesuaikan jenis data, sama seperti
       build_report_blocks() (pakai ulang is_security_domain/pick_category/numeric_summary).
    2. "Tren & Pola" SEBELUMNYA menampilkan representasi dict Python mentah sbg teks
       (mis. "{'value': 'Belanja TI', 'count': 8}") krn kode mengasumsikan tiap item
       top_categories berupa tuple/list, padahal isinya dict {"value","count"}.
    3. "Rekomendasi Prioritas" SEBELUMNYA menampilkan judul & detail dgn ISI SAMA PERSIS
       berulang (detail seharusnya SISA kalimat setelah judul diambil, bukan teks penuh lagi).
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

    sec_domain = is_security_domain(report)
    source_cols = report_stats.get("_source_columns") or {}
    generic_category_keys = sorted(k for k in top_categories if k.startswith("category_"))
    used_labels: set = set()
    category_pick = pick_category(top_categories, ["action", *generic_category_keys, "location", "destination_port"], used_labels)
    asset_pick = pick_category(top_categories, ["asset", "destination_port", "location", *generic_category_keys], used_labels)
    numeric_summary = report_stats.get("numeric_summary") or {}
    # BUG YANG DIPERBAIKI (dilaporkan user): fungsi ini SEBELUMNYA tidak pernah memanggil
    # is_section_included() sama sekali — ceklis "Include Sections" di wizard nol pengaruh
    # ke gaya laporan Management Report. Pola & kunci section SAMA PERSIS dgn
    # build_report_blocks() di atas (mis. "period_compare"/"kpi_radar"/"time_heatmap") supaya
    # 1 ceklis konsisten mengontrol konsep yang sama di kedua gaya laporan.
    included = report.included_sections or {}
    is_included = lambda key: is_section_included(key, included)

    critical_count = report.threat_count_critical or severity.get("critical", 0)
    high_count = report.threat_count_high or severity.get("high", 0)

    # SLA hanya bermakna utk data yang genuinely punya konsep SLA/insiden (domain keamanan
    # DENGAN data severity) — dipaksakan ke SEMUA jenis data sebelumnya jadi angka "100%" palsu
    # yang tidak berarti apa-apa utk mis. data anggaran/KPI.
    sla_met = getattr(report, "sla_met", True)
    sla_pct = 100 if sla_met else max(0, 100 - round((getattr(report, "processing_time_sec", 0) or 0) / 3))

    status_col = source_cols.get("status")
    severity_col = source_cols.get("severity")
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
    key_findings = build_key_findings(ai_summary, report_stats, open_count, sanitize_text, report=report)

    blocks = []

    # ---- Cover ----
    _mgmt_period_text = format_period(report)
    blocks.append({
        "kind": "cover",
        "dark": True,
        # BUG YANG DIPERBAIKI: dict ini sebelumnya tidak menyertakan "kicker"/"period_label"/
        # "period_text"/"info_line" — field WAJIB dibaca _build_cover_block/_split_cover_td
        # (export_pdf.py) & _build_cover_slide/add_split_cover_slide (export_ppt.py), sama
        # persis skema yang dipakai build_report_blocks() di file ini. Tanpa field ini, ekspor
        # PDF/PPT utk template "Management Report" gagal dgn KeyError begitu blok cover dirender.
        "kicker": L("LAPORAN MANAJEMEN", "MANAGEMENT REPORT"),
        "title": report.title,
        "subtitle": L("Laporan Eksekutif — Management Report", "Executive Report — Management Report"),
        "date": format_report_date(report.created_at, report.language),
        "period": _mgmt_period_text,
        "period_text": _mgmt_period_text,
        "period_label": L("Periode data.", "Data period."),
        "total_records": total_records,
        "category_count": len(top_categories),
        "critical_count": critical_count,
        "info_line": L(
            f"{total_records} data, {critical_count} kategori kritis",
            f"{total_records} records, {critical_count} critical categories",
        ),
        "hero_stat": (str(total_records), L("Total Data", "Total Records")),
        "hero_stat_kicker": L("CAPAIAN KESELURUHAN", "OVERALL FIGURE"),
        "header_title": (report.header_title or "PT PETROKIMIA GRESIK").upper(),
        "header_subtitle": report.header_subtitle or "Sistem Otomasi Laporan & Eksekutif Presentasi Berbasis AI",
        "cover_style": "split",
        "theme_color": resolve_theme_color(report),
        "is_management": True,
    })

    # PERMINTAAN USER: halaman "Indikator Kinerja Utama" (grid KPI ringkas) DIHAPUS — user
    # merasa isinya tidak jelas gunanya & redundan dgn halaman dashboard visual persis
    # setelahnya (visual_tiles di bawah sudah menampilkan angka yang sama scr lebih detail/
    # visual). Kalau perlu dikembalikan lagi nanti, lihat riwayat git commit sebelum ini.

    # PERMINTAAN USER: template "Visual tinggi" ini SEBELUMNYA menaruh tiap jenis
    # visualisasi (peta risiko, radar, funnel, perbandingan periode, heatmap waktu, tren) di
    # HALAMANNYA SENDIRI-SENDIRI — hasilnya "1 chart per halaman" berkali-kali, bukan benar2
    # padat/visual. visual_tiles menampung SEMUA jenis chart yang tersedia (bukan cuma yang
    # ada datanya) lalu ditumpuk jadi 1 (atau lebih, lihat loop chunking di bawah) halaman
    # dashboard grid — beberapa jenis visual sekaligus, keterangan tiap tile dipangkas jadi
    # 1 kalimat saja (bukan pengganti, tetap chart SUNGGUHAN per jenis data, cuma lebih ringkas).
    visual_tiles: list = []

    # ---- Distribusi Risiko/Kategori — severity kalau ada, kalau tidak pakai ranking kategori
    # teratas (dulu SELALU severity bars, tampil kosong total 0% utk data non-keamanan) ----
    if total_sev:
        bars = []
        for sev_key in ["critical", "high", "medium", "low", "informational"]:
            count = severity.get(sev_key, 0)
            pct = round(count / max(total_sev, 1) * 100)
            bars.append({
                "label": sev_key.title(), "count": count, "pct": pct,
                "color": {"critical": "red", "high": "orange", "medium": "amber", "low": "blue", "informational": "gray"}.get(sev_key, "gray"),
            })
        risk_title = L("Peta Risiko Keamanan", "Security Risk Map") if sec_domain else L("Peta Distribusi Prioritas", "Priority Distribution Map")
        risk_mode = "severity"
        risk_cat_col = severity_col
        # BUG DIPERBAIKI: sebelumnya narasi halaman "risiko" ini diambil dari
        # threat_analysis/trend_analysis (topik TREN, bukan risiko) — teks yang tampil sering
        # tidak nyambung dgn judul halamannya sendiri. Diganti prioritas field yang genuinely
        # membahas risiko/severity.
        risk_narrative = ai_summary.get("risk_assessment") or ai_summary.get("severity_analysis") or ai_summary.get("threat_analysis")
    else:
        bars = []
        risk_title = L("Peta Distribusi Kategori", "Category Distribution Map")
        risk_mode = "category"
        risk_narrative = ai_summary.get("risk_assessment") or ai_summary.get("severity_analysis")
        risk_cat_col = source_cols.get(category_pick[0]) if category_pick else None
        if category_pick:
            label, items = category_pick
            cat_total = sum(i["count"] for i in items) or 1
            palette = ["blue", "green", "amber", "orange", "gray", "red"]
            for i, item in enumerate(items[:6]):
                bars.append({
                    "label": item["value"], "count": item["count"],
                    "pct": round(item["count"] / cat_total * 100), "color": palette[i % len(palette)],
                })
    # Tile ini di-SKIP kalau memang tidak ada apa pun utk ditampilkan (bars kosong) —
    # jumlah/kehadiran tile FLEKSIBEL mengikuti data yang tersedia, bukan struktur tetap
    # (prinsip yang sama dipakai build_report_blocks(): tata letak proporsional dgn isinya).
    if bars and is_included("severity_analysis" if risk_mode == "severity" else "category_distribution"):
        visual_tiles.append({
            "tile_kind": "risk_heatmap",
            "kicker": L("DISTRIBUSI RISIKO", "RISK DISTRIBUTION") if risk_mode == "severity" else L("DISTRIBUSI DATA", "DATA DISTRIBUTION"),
            "title": risk_title,
            "mode": risk_mode,
            "bars": bars,
            "cat_col_name": risk_cat_col,
            # BUG DIPERBAIKI: model AI kadang "mengarang struktur" (list/dict bersarang, mis.
            # [{"id":"high_risk","description":...,"count":...}]) utk field yang kontraknya
            # SEHARUSNYA kalimat polos — tanpa coerce_narrative_text(), repr Python mentahnya
            # ("{'risk_assessment': [...]}") tampil apa adanya di laporan. sanitize_text() SENDIRI
            # cuma str(x), tidak meratakan struktur — coerce_narrative_text() WAJIB dipanggil
            # duluan (pola yang sama sudah dipakai di semua field naratif lain di file ini).
            # BUG DIPERBAIKI (ditemukan lewat isolasi render+bisection langsung di laporan
            # sungguhan, report id 165): _shorten_to_caption() SAJA (batas per KALIMAT) tetap
            # bisa menghasilkan 1 kalimat AI yang panjang (100+ karakter) — caption tile
            # SEPANJANG itu terbukti bikin TOTAL TINGGI grid dashboard (2 baris x 3 tile)
            # melebihi tinggi halaman tetap (7.5in), lalu diam-diam terpotong oleh
            # overflow:hidden di wrapper halaman (lihat _page() di export_pdf.py) — SATU tile
            # (bisa yang mana pun, tergantung tile mana yang jatuh di baris ke-2) jadi terlihat
            # "hilang total" di PDF/PPT padahal HTML/datanya sendiri benar & lengkap.
            # AKAR MASALAH SEKARANG DIPERBAIKI DI 2 TEMPAT LAIN, BUKAN DI SINI LAGI: (1) prompt
            # AI (prompts.py) sekarang diarahkan menulis kalimat PERTAMA tiap narasi analisis
            # tetap ringkas (~90 karakter) — caption ini ambil kalimat pertama itu apa adanya,
            # (2) tinggi area caption di export_pdf.py/export_ppt.py sekarang dibatasi CSS
            # (max-height + overflow, BUKAN memotong teksnya) sbg jaring pengaman kalau AI
            # tetap menulis lebih panjang dari yang diminta. Memotong teks secara paksa di
            # sini (_hard_truncate) DIHAPUS — itu mengobati gejala (tinggi grid), bukan akar
            # masalahnya, dan bisa memotong makna kalimat di tengah jalan.
            "caption": _shorten_to_caption(sanitize_text(coerce_narrative_text(risk_narrative)), max_sentences=1) if risk_narrative else None,
        })

    # ---- Perbandingan Multi-Indikator (radar) — HANYA kalau data punya >=3 kolom numerik
    # genuinely sebanding (skor/nilai KPI dst).
    radar_data = _compute_kpi_radar(numeric_summary, source_cols)
    if radar_data and is_included("kpi_radar"):
        top_axis_idx = max(range(len(radar_data["values"])), key=lambda i: radar_data["values"][i])
        visual_tiles.append({
            "tile_kind": "kpi_radar",
            "kicker": L("PERBANDINGAN INDIKATOR", "INDICATOR COMPARISON"),
            "title": L("Perbandingan Capaian Multi-Indikator", "Multi-Indicator Achievement Comparison"),
            "axes": radar_data["axes"],
            "values": radar_data["values"],
            "caption": L(
                f"{radar_data['axes'][top_axis_idx]} mencatat capaian tertinggi.",
                f"{radar_data['axes'][top_axis_idx]} recorded the highest achievement.",
            ),
        })

    # ---- Alur Status (funnel) — HANYA kalau data punya kolom status genuinely terdeteksi
    # (Open/Investigating/Resolved dst) — bentuk visual dipilih sesuai KARAKTER data (alur
    # bertingkat -> funnel), bukan ranked-bar yang sama dipakai di tile Distribusi.
    status_items = top_categories.get("status") or []
    if status_items and is_included("status_distribution"):
        order = sorted(status_items, key=lambda it: -it["count"])[:6]
        # PERMINTAAN USER: tiap visualisasi harus disertai narasi singkat yang menjelaskan
        # hasilnya (jangan biarkan chart tanpa keterangan sama sekali) — dihitung deterministik
        # dari data ASLI di sini (bukan AI), grounded pada angka yang SAMA dgn yang digambar.
        status_total = sum(it["count"] for it in order) or 1
        top_status = order[0]
        visual_tiles.append({
            "tile_kind": "status_funnel",
            "kicker": L("STATUS PENANGANAN", "HANDLING STATUS"),
            "title": L("Alur Status Penanganan", "Handling Status Flow"),
            "categories": [it["value"] for it in order],
            "values": [it["count"] for it in order],
            "cat_col_name": status_col,
            "caption": L(
                f"{top_status['value']} mendominasi alur ini ({top_status['count']} dari {status_total} data, {round(top_status['count']/status_total*100)}%).",
                f"{top_status['value']} dominates this flow ({top_status['count']} of {status_total} records, {round(top_status['count']/status_total*100)}%).",
            ),
        })

    # ---- Perbandingan Antar Paruh Periode (grouped bar) — HANYA kalau ada kolom tanggal +
    # kategori genuinely terdeteksi. Bentuk visual dipilih sesuai KARAKTER data (perbandingan
    # 2 periode -> grouped bar), bukan ranked-bar yang sama dipakai di tile Distribusi.
    date_col = source_cols.get("date")
    if category_pick and date_col and is_included("period_compare"):
        _label, _items = category_pick
        compare_data = _compute_period_compare(parsed_data, date_col, source_cols.get(_label), [it["value"] for it in _items[:4]])
        if compare_data:
            # PERMINTAAN USER: tiap visualisasi harus disertai narasi singkat — dihitung
            # deterministik dari angka yang SAMA persis yang digambar di chart-nya.
            total_a = sum(compare_data["series_a"]) or 0
            total_b = sum(compare_data["series_b"]) or 0
            if total_a == total_b:
                arah_id, arah_en = "stabil", "stable"
            elif total_b > total_a:
                arah_id, arah_en = "naik", "up"
            else:
                arah_id, arah_en = "turun", "down"
            visual_tiles.append({
                "tile_kind": "period_compare",
                "kicker": L("PERBANDINGAN PERIODE", "PERIOD COMPARISON"),
                "title": L("Perbandingan Antar Paruh Periode", "Period-over-Period Comparison"),
                "categories": compare_data["categories"],
                "series_a": compare_data["series_a"], "series_b": compare_data["series_b"],
                "label_a": L("Paruh Awal", "First Half"), "label_b": L("Paruh Akhir", "Second Half"),
                "caption": L(
                    f"Aktivitas {arah_id} dari paruh awal ke paruh akhir ({total_a} → {total_b} kejadian pada kategori teratas).",
                    f"Activity trended {arah_en} from the first half to the second ({total_a} → {total_b} events across top categories).",
                ),
            })

    # ---- Pola Kejadian per Hari/Jam (heatmap) — HANYA kalau kolom tanggal genuinely
    # terdeteksi & datanya cukup padat (min. 20 baris bertanggal valid, lihat
    # _compute_day_hour_pattern). Bentuk visual dipilih sesuai KARAKTER data (pola per
    # hari/jam -> heatmap grid), bukan bar/ranking yang sudah dipakai di tile lain.
    heatmap_data = _compute_day_hour_pattern(parsed_data, date_col)
    if heatmap_data and is_included("time_heatmap"):
        # PERMINTAAN USER: tiap visualisasi harus disertai narasi singkat — hari terpadat
        # dihitung dari grid yang SAMA persis yang digambar sbg heatmap (jumlah tiap baris).
        _day_totals = [sum(row) for row in heatmap_data["grid"]]
        _peak_day_idx = max(range(len(_day_totals)), key=lambda i: _day_totals[i]) if _day_totals else 0
        peak_day_id, peak_day_en = heatmap_data["day_labels"][_peak_day_idx]
        visual_tiles.append({
            "tile_kind": "time_heatmap",
            "kicker": L("POLA WAKTU", "TIME PATTERN"),
            "title": L("Pola Kejadian per Hari & Jam", "Event Pattern by Day & Hour"),
            "day_labels": [L(id_, en_) for id_, en_ in heatmap_data["day_labels"]],
            "hour_labels": heatmap_data["hour_labels"],
            "grid": heatmap_data["grid"],
            "caption": L(
                f"Hari {peak_day_id} tercatat paling padat, {_day_totals[_peak_day_idx]} dari {heatmap_data['total']} data.",
                f"{peak_day_en} is the busiest day, {_day_totals[_peak_day_idx]} of {heatmap_data['total']} records.",
            ),
        })

    # ---- Meteran Pencapaian (gauge) — PERMINTAAN USER (tambah jenis visualisasi baru):
    # HANYA kalau ada kategori teratas yang genuinely terdeteksi, supaya persentase yang
    # ditampilkan sbg meteran benar2 angka asli (share kategori teratas dari total data),
    # bukan dikarang.
    if category_pick and total_records and is_included("category_distribution"):
        _gauge_label, _gauge_items = category_pick
        top_item = _gauge_items[0]
        top_pct = round(top_item["count"] / total_records * 100)
        gauge_dim = humanize_label(_gauge_label, source_cols)
        visual_tiles.append({
            "tile_kind": "kpi_gauge",
            "kicker": L("PANGSA TERBESAR", "LARGEST SHARE"),
            "title": L(f"Pangsa {gauge_dim} Teratas", f"Top {gauge_dim} Share"),
            "pct": top_pct,
            "caption": L(
                f"{top_item['value']} mendominasi dengan {top_pct}% dari total.",
                f"{top_item['value']} dominates with {top_pct}% of the total.",
            ),
            # PERMINTAAN USER (halaman gauge tunggal wajib py catatan analitis kalau mau jadi
            # pengecualian kepadatan yang sah - lihat _build_insight_page's kpi_gauge branch):
            # data pendukung DITAMBAHKAN di sini (bukan cuma "pct") supaya ada bahan GENUINE
            # utk >=1 catatan, bukan halaman kosong beralasan "tidak ada apa-apa lagi".
            "gauge_dim": gauge_dim, "top_value": top_item["value"], "top_count": top_item["count"],
            "total_records": total_records, "second_item": _gauge_items[1] if len(_gauge_items) > 1 else None,
        })

    # ---- Sebaran 2 Dimensi (scatter/bubble) — PERMINTAAN USER (tambah jenis visualisasi
    # baru): HANYA kalau ada pasangan kategori+angka numerik genuinely terkelompokkan (lihat
    # data_profiler._compute_category_numeric_pairs) — 2 angka BERBEDA per entitas, bukan
    # cuma 1 angka seperti tile lain di atas.
    pairs = report_stats.get("category_numeric_pairs")
    if pairs and is_included("category_distribution"):
        pair_cat_label = humanize_label(pairs["category_label"], source_cols)
        pair_num_label = humanize_label(pairs["numeric_label"], source_cols)
        visual_tiles.append({
            "tile_kind": "scatter_bubble",
            "kicker": L("SEBARAN DATA", "DATA SPREAD"),
            "title": L(f"{pair_cat_label} vs {pair_num_label}", f"{pair_cat_label} vs {pair_num_label}"),
            "points": pairs["points"],
            "x_label": L("Jumlah kemunculan", "Occurrence count"),
            "caption": L(
                f"Tiap titik mewakili satu {pair_cat_label.lower()}, diposisikan berdasarkan jumlah kemunculan dan rata-rata {pair_num_label.lower()}.",
                f"Each point represents one {pair_cat_label.lower()}, positioned by occurrence count and average {pair_num_label.lower()}.",
            ),
            # PERMINTAAN USER (hapus jalur management_visual_dashboard, semua lewat insight):
            # sama spt custom_topic, kartu bersarang di halaman insight butuh kolom kategori
            # ASLI entitas ini spy bisa mencocokkan kolom numerik sebanding lain sbg sub-item.
            "cat_col_name": pairs.get("category_col"),
        })

    # ---- Tren & Pola — chart SUNGGUHAN (bar+line utk deret waktu, atau bar ranking kalau
    # tidak ada data tanggal) ----
    _time_series = report_stats.get("time_series") or {}
    trend_chart = None
    if len(_time_series.get("counts") or []) >= 3:
        trend_chart = {
            "type": "bar_line",
            "categories": _time_series["labels"][-8:],
            "values": _time_series["counts"][-8:],
            "cumulative": (_time_series.get("cumulative") or [])[-8:],
        }
    elif category_pick:
        _items = category_pick[1][:6]
        trend_chart = {"type": "bar", "categories": [i["value"] for i in _items], "values": [i["count"] for i in _items]}
    trend_narrative = _resolve_templated_narrative(ai_summary.get("trend_analysis"), report_stats, report=report) or ai_summary.get("executive_summary")
    # Tile ini di-SKIP kalau tidak ada chart SAMA SEKALI — beda dari sebelumnya (yang tetap
    # tampil kalau ada trend_items/narasi walau tanpa chart), krn kartu naratif tanpa chart
    # kurang cocok jadi tile dashboard (identitas tumpukan "visual", bukan tumpukan teks).
    if trend_chart and is_included("trend_analysis"):
        visual_tiles.append({
            "tile_kind": "trend_chart",
            "kicker": L("TREN & POLA", "TRENDS & PATTERNS"),
            "title": L("Analisis Tren Periode Ini", "Trend Analysis This Period"),
            "chart": trend_chart,
            # Sama seperti risk_heatmap di atas — narasi bebas AI, panjangnya sekarang
            # diarahkan lewat prompt (kalimat pertama ringkas), bukan dipotong paksa di sini;
            # tinggi area caption dibatasi CSS di export_pdf.py/export_ppt.py sbg jaring
            # pengaman.
            "caption": _shorten_to_caption(sanitize_text(coerce_narrative_text(trend_narrative)), max_sentences=1) if trend_narrative else None,
        })

    # PERMINTAAN USER: section custom AI ("Insight Tambahan") sebelumnya SELALU jadi kartu
    # teks, padahal Management Report harusnya "lebih banyak visualisasi". Sekarang: kalau
    # section-nya menyertakan data perbandingan kategori (field opsional "chart" dari AI,
    # lihat get_analysis_prompt), diubah jadi TILE chart sungguhan & digabung ke visual_tiles
    # SEBELUM ditumpuk jadi halaman dashboard (baris di bawah) — supaya ikut aturan "maks 6
    # visualisasi per halaman" & bentuknya bervariasi (gantian bar/donat/susun), bukan halaman
    # teks terpisah. Section TANPA data kategori (chart:null, murni narasi kualitatif) tetap
    # jadi kartu teks di management_ai_narrative (lihat di bawah, setelah action items).
    # BUG DIPERBAIKI (ditemukan lewat isolasi render+bisection langsung — bukan dugaan, sudah
    # dikonfirmasi reproducible): "treemap" SENGAJA DIKELUARKAN dari rotasi khusus di sini.
    # custom_topic (tile ini) bisa jatuh di BARIS KE-2+ grid dashboard (posisi bergantung
    # urutan & jumlah tile lain, tidak selalu baris pertama) — pada kombinasi tertentu (baris
    # pertama berisi caption panjang + tile treemap persis di kolom pertama baris kedua),
    # WeasyPrint TERBUKTI gagal me-render SATU SEL itu sama sekali (hilang total, title dan
    # semuanya, tanpa exception apa pun di sisi Python — root cause pastinya belum ditemukan
    # walau sudah ditelusuri sampai ke tingkat menghapus/mengganti tiap elemen satu per satu).
    # "treemap" TETAP dipakai aman di category_style/status_style (risk_heatmap SELALU jadi
    # tile PERTAMA/baris pertama, & versi SOC-nya selalu 1 halaman penuh sendirian, keduanya
    # TIDAK pernah berisiko jatuh di baris ke-2+ grid padat spt custom_topic).
    _custom_chart_styles = ["bar", "donut", "stacked"]
    _custom_chart_idx = 0
    dynamic_sections_all = [s for s in (ai_summary.get("sections") or []) if isinstance(s, dict)]
    narrative_items = []
    # BUG DIPERBAIKI (dilaporkan user, disertai perbandingan checklist Include Sections vs
    # laporan jadi — topik order 0 hilang total): SEBELUMNYA section PERTAMA (order 0) selalu
    # dilewati di sini dgn asumsi isinya "ringkasan eksekutif tingkat tinggi" yang sudah
    # terwakili executive_summary bawaan — asumsi itu TIDAK SELALU benar (topik order 0 bisa
    # genuinely spesifik, mis. "Overview of Production Performance" yang dicentang user tapi
    # tidak pernah muncul sama sekali). Permintaan user JELAS: SEMUA topik yang dicentang HARUS
    # masuk laporan, jadi section 0 SEKARANG ikut diproses sama seperti section lainnya.
    for sec in dynamic_sections_all:
        sec_title = sanitize_text(coerce_narrative_text(sec.get("title")))
        sec_content = sanitize_text(coerce_narrative_text(sec.get("content")))
        if not sec_title or not sec_content:
            continue
        # ARSITEKTUR DIPERBAIKI (bukan sekadar memperbaiki prompt lagi — lihat riwayat kerja
        # panjang soal chart "Authentication Failure Trend" yang pernah salah): AI TIDAK PERNAH
        # lagi jadi sumber angka/label chart. Sebelumnya field "chart" ({"labels","values"})
        # ditulis LANGSUNG oleh AI & dipakai APA ADANYA di sini — walau sudah dibantu tabel
        # ground-truth di prompt, jalur ini TETAP bergantung AI menyalin dgn benar, jadi TETAP
        # bisa salah (angka asli, cuma tertukar slot). Sekarang AI cuma menunjuk PASANGAN NAMA
        # KOLOM lewat "chart_source" (lihat SECTIONS_BATCH_SYSTEM_PROMPT) - labels/values chart
        # SELALU diambil langsung dari report_stats["category_numeric_breakdown"] (dihitung
        # pandas dari parsed_data di awal fungsi ini, lihat data_profiler.py
        # ::_compute_category_numeric_breakdown) via _find_breakdown_entry, BUKAN dari respons
        # AI - AI tidak lagi punya kesempatan menukar/salah tulis angka apa pun di chart ini.
        # Kalau AI menunjuk nama kolom yang tidak cocok apa pun (salah tulis, atau topiknya
        # genuinely tidak punya breakdown), chart_entry None -> section jadi narasi biasa
        # (fallback aman, BUKAN chart dari sumber tak-terverifikasi).
        #
        # Nilai yang genuinely SERAGAM (mis. 5 bucket sama-sama bernilai 2 krn data memang rata)
        # kini otomatis TETAP tampil apa adanya - datang langsung dari agregasi asli, bukan lagi
        # rawan dicurigai/disaring sbg "kelihatan seperti kesalahan AI" (heuristik semacam itu
        # sudah dihapus total, lihat riwayat kerja) - keseragaman data asli adalah temuan sah.
        chart_source = sec.get("chart_source") if isinstance(sec.get("chart_source"), dict) else None
        chart_entry = None
        if chart_source:
            chart_entry = _find_breakdown_entry(
                report_stats.get("category_numeric_breakdown") or [],
                chart_source.get("numeric_col"), chart_source.get("category_col"),
            )
        # Format LAMA ("chart":{"labels","values"} ditulis AI langsung) - dukungan mundur HANYA
        # utk laporan yang SUDAH tersimpan sebelum perbaikan ini (ai_summary lama tidak punya
        # "chart_source" sama sekali) supaya tidak tiba-tiba kehilangan chart-nya saat dirender
        # ulang. Laporan BARU tidak pernah lagi mengisi field "chart" (lihat ollama_client.py
        # ::_attempt_sections_batch) - jalur ini murni transisi, TIDAK dipakai laporan baru.
        legacy_chart = sec.get("chart") if (not chart_entry and isinstance(sec.get("chart"), dict)) else None
        legacy_labels = legacy_chart.get("labels") if legacy_chart else None
        legacy_values = legacy_chart.get("values") if legacy_chart else None
        has_valid_legacy_chart = (
            isinstance(legacy_labels, list) and isinstance(legacy_values, list)
            and len(legacy_labels) >= 2 and len(legacy_labels) == len(legacy_values)
            and all(isinstance(v, (int, float)) for v in legacy_values)
        )
        tile_cat_col = None
        # PERMINTAAN USER (koreksi eksplisit — "datanya punya 8 aset, kesepakatannya 2 baris x
        # 4 kartu"): batas di sini dulu 6 (peninggalan asumsi LAMA "chart bar/donat maks 6
        # kategori spy terbaca") — sekarang ikut dipakai jadi sumber `category_details`
        # halaman insight juga (sampai 8 kartu, lihat _NESTED_CARD_MAX_TOTAL), jadi batas 6 di
        # sini DIAM2 memotong 2 kartu terakhir SEBELUM sempat sampai ke _build_insight_page
        # sama sekali - bukan "baris kedua terisi sebagian", tapi kandidatnya sendiri sudah
        # kepotong duluan di tahap ini. Disamakan ke _NESTED_CARD_MAX_TOTAL (8) supaya
        # kapasitas kartu insight TIDAK dibatasi lagi oleh asumsi lama chart bar/donat.
        if chart_entry:
            items = chart_entry["items"][:_NESTED_CARD_MAX_TOTAL]
            tile_labels = [sanitize_text(str(it["label"])) for it in items]
            tile_values = [float(it["value"]) for it in items]
            # PERMINTAAN USER: kartu bersarang di halaman insight (_build_insight_page) butuh
            # tahu kolom kategori ASLI entitas ini (mis. "Virtual Server") supaya bisa
            # mencocokkan kolom numerik LAIN yang sebanding (Illegal/Legal Requests dst) sbg
            # sub-item — sudah tersedia langsung dari chart_entry, tidak perlu deteksi ulang.
            tile_cat_col = chart_entry.get("category_col")
        elif has_valid_legacy_chart:
            tile_labels = [sanitize_text(str(lbl)) for lbl in legacy_labels[:_NESTED_CARD_MAX_TOTAL]]
            tile_values = [float(v) for v in legacy_values[:_NESTED_CARD_MAX_TOTAL]]
        else:
            tile_labels = tile_values = None
        if tile_labels:
            style = _custom_chart_styles[_custom_chart_idx % len(_custom_chart_styles)]
            _custom_chart_idx += 1
            visual_tiles.append({
                "tile_kind": "custom_topic",
                "chart_style": style,
                "kicker": L("INSIGHT AI", "AI INSIGHT"),
                "title": sec_title,
                "labels": tile_labels,
                "values": tile_values,
                "caption": _shorten_to_caption(sec_content, max_sentences=1),
                "cat_col_name": tile_cat_col,
            })
        else:
            narrative_items.append({"title": sec_title, "content": _shorten_to_caption(sec_content, max_sentences=3)})

    # Tumpuk SEMUA tile visual yang tersedia jadi 1 halaman dashboard (bisa 4/5/lebih
    # sekaligus, macam-macam jenis chart, keterangan tiap tile cuma 1 kalimat) — kalau
    # jumlahnya lebih dari 6 (bisa terjadi sekarang krn tile custom topic bisa nambah banyak),
    # PERMINTAAN USER ("hapus jalur management_visual_dashboard, arahkan semuanya ke jalur
    # insight — jalur insight sudah terbukti menghasilkan 143 elemen, jalur lama menghasilkan
    # 17 dan 27"): jalur "kolom" lama (_build_column_dashboard_blocks/_layout_dashboard_column)
    # DIHENTIKAN PEMAKAIANNYA di sini (fungsinya TIDAK dihapus dari file, cuma tidak dipanggil
    # lagi dari loop ini — cukup utk mengganti PERILAKU, penghapusan kode mati itu sendiri
    # masih utang kebersihan terpisah). SETIAP tile sekarang jadi halaman insight sendiri:
    # tile "space-hungry" (radar/heatmap/period_compare, tidak py daftar entitas) lewat
    # _build_chart_insight_page (chart asli jadi lapis "detail", bukan kartu), tile lain lewat
    # _build_insight_page spt sebelumnya - TANPA gerbang "kaya/tipis" lagi (_is_rich_insight_
    # page tidak dipanggil di sini lagi): kartu bersarang SEKARANG hampir selalu berisi
    # sub-item nyata (multi-metrik, lihat _compute_multi_metric_items), jadi hampir semua
    # topik genuinely layak halaman sendiri; topik yang KEBETULAN masih menghasilkan himpunan
    # entitas yang sama dgn topik lain tetap ditangkap & digabung oleh
    # _merge_overlapping_insight_pages di akhir fungsi ini (bukan gerbang di sini).
    for tile in visual_tiles:
        if tile["tile_kind"] in _SPACE_HUNGRY_TILE_KINDS:
            page = _build_chart_insight_page(tile, report)
        else:
            page = _build_insight_page(
                tile, report, sec_domain, parsed_data, severity_col, status_col,
                numeric_breakdown=report_stats.get("category_numeric_breakdown"),
            )
        if page:
            blocks.append(page)

    # ---- Temuan Utama (setara build_report_blocks() — reuse builder PDF/PPT yang sama,
    # dibungkus "page"+panels 1-panel supaya lewat jalur "panel mandiri" apa adanya, lihat
    # _build_page_block/_build_page_slide) ----
    # BUG DIPERBAIKI (permintaan user poin 2 — "halaman yang isinya satu butir jangan
    # berdiri sendiri"): "Temuan Utama" gaya Management dulu SELALU halaman "page" 1-panel
    # sendiri, tidak pernah lewat sistem bobot/backstop gabung yang dipakai gaya SOC (beda
    # fungsi, build_management_report_blocks vs build_report_blocks) — Temuan Utama 1-2
    # butir jadi thin GENUINELY tidak pernah tersambung ke apa pun. Panel-nya dibungkus DULU
    # (bukan langsung append) supaya bisa digabung 1 halaman dgn panel "critical_table" tepat
    # di bawah ini (builder generic _build_page_block/_build_page_slide SUDAH mendukung 2+
    # panel berdampingan di 1 halaman, dipakai ulang di sini) kalau Temuan-nya genuinely tipis
    # (<=2 butir) & critical_table memang ada.
    findings_panel = None
    if key_findings and is_included("key_findings"):
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
        findings_panel = {
            "panel_kind": "key_findings",
            "kicker": L("ANALISIS", "ANALYSIS"), "title": L("Temuan Utama", "Key Findings"),
            "items": findings_items, "chart": None,
        }

    # ---- Tabel Item Prioritas/Kritis (data dihitung persis sama seperti build_report_blocks(),
    # reuse builder PDF/PPT yang sama lewat "page"+panels) ----
    critical_table_panel = None
    if severity_col and parsed_data and is_included("critical_table"):
        critical_rows = [row for row in parsed_data if _classify_severity_value(str(row.get(severity_col, ""))) == "critical"]
        if len(critical_rows) < 5:
            critical_rows += [row for row in parsed_data if _classify_severity_value(str(row.get(severity_col, ""))) == "high"]
        critical_rows = critical_rows[:12]
        if critical_rows:
            ct_headers = [L("No", "No")]
            if category_pick:
                ct_headers.append(humanize_label(category_pick[0], source_cols))
            ct_headers.append("Severity")
            if status_col:
                ct_headers.append(L("Status", "Status"))
            cat_col_name = source_cols.get(category_pick[0]) if category_pick else None
            ct_rows = []
            ct_highlight_idx = []
            for idx, row in enumerate(critical_rows):
                row_vals = [str(idx + 1)]
                if category_pick:
                    row_vals.append(str(row.get(cat_col_name, "-")) if cat_col_name else "-")
                row_vals.append(_classify_severity_value(str(row.get(severity_col, ""))).capitalize())
                if status_col:
                    status_val = row.get(status_col, "-")
                    row_vals.append(str(status_val))
                    if classify_open_status(status_val) is True:
                        ct_highlight_idx.append(idx)
                ct_rows.append(row_vals)
            critical_table_panel = {
                "panel_kind": "critical_table",
                "kicker": L("SOROTAN INSIDEN", "INCIDENT HIGHLIGHT") if sec_domain else L("SOROTAN DATA", "DATA HIGHLIGHT"),
                "title": L(f"{len(critical_rows)} Insiden Prioritas Tinggi", f"{len(critical_rows)} High-Priority Incidents") if sec_domain
                else L(f"{len(critical_rows)} Item Prioritas Tinggi", f"{len(critical_rows)} High-Priority Items"),
                "headers": ct_headers, "rows": ct_rows, "highlight_idx": ct_highlight_idx, "open_count": open_count,
                "kicker_is_critical": bool(open_count),
                "caption": sanitize_text(L(
                    f"Baris merah menandai {open_count} insiden yang masih dalam proses penanganan per akhir periode data.",
                    f"Red rows mark {open_count} incidents still in progress as of the end of the data period.",
                ) if sec_domain else L(
                    f"Baris merah menandai {open_count} item yang masih dalam proses per akhir periode data.",
                    f"Red rows mark {open_count} items still in progress as of the end of the data period.",
                )) if open_count else None,
            }

    # Gabung Temuan Utama + Tabel Kritis jadi 1 halaman (2 panel berdampingan, builder generic
    # yang sama dipakai gaya SOC utk kasus serupa) KALAU Temuan-nya genuinely tipis (<=2
    # butir) & Tabel Kritis memang ada — drpd 2 halaman terpisah yang salah satunya separuh
    # kosong. Selain itu (Temuan >2 butir, atau salah satu tidak ada), tetap 2 halaman
    # terpisah spt sebelumnya.
    # REGRESI DIPERBAIKI (dilaporkan user: hal.07 "Temuan Utama" cuma 4 butir lalu 75% kosong):
    # halaman ini dulu SELALU jadi halaman solo kalau tidak ada tabel kritis utk menemaninya -
    # 4 butir teks pendek tidak pernah cukup mengisi 1 halaman penuh. Pola yang dipakai SAMA
    # PERSIS dgn penggabungan narasi tipis di bawah (_MGMT_NARRATIVE_SOLO_THRESHOLD): temuan
    # disisipkan sbg catatan di halaman insight TERAKHIR, bukan bikin halaman sendiri. Tidak ada
    # elemen baru yang lahir di luar anggaran - "notes" memang lapis yang sudah ada di halaman
    # itu (dan utk halaman ber-chart, sudah dipastikan dirender DI DALAM wrapper, lihat catatan
    # akar masalah di export_pdf.py::_insight_main_chart_html).
    _MGMT_FINDINGS_SOLO_THRESHOLD = 4
    # KOREKSI (audit jalur render): syarat "critical_table_panel is None" DILEPAS. Temuan
    # Utama yang cukup ringkas selalu bisa menumpang halaman insight - kehadiran tabel kritis
    # di blok LAIN tidak ada hubungannya dgn muat/tidaknya temuan itu. Syarat itu satu-satunya
    # alasan laporan 158 merender halaman lewat pembangun jalur Deskriptif, padahal isinya
    # konten Management: dua cara merender hal yang sama = sumber divergensi.
    if (
        findings_panel is not None
        and len(findings_panel["items"]) <= _MGMT_FINDINGS_SOLO_THRESHOLD
    ):
        _host = next((b for b in reversed(blocks) if b.get("kind") == "management_insight_page"), None)
        if _host is not None:
            _extra = [
                (f"{it['title']}. {it['detail']}" if it.get("detail") else it["title"])
                for it in findings_panel["items"]
            ]
            _host["notes"] = [*(_host.get("notes") or []), *_extra]
            findings_panel = None

    if findings_panel is not None and critical_table_panel is not None and len(findings_panel["items"]) <= 2:
        blocks.append({"kind": "page", "dark": False, "panels": [findings_panel, critical_table_panel]})
    else:
        if findings_panel is not None:
            blocks.append({"kind": "page", "dark": False, "panels": [findings_panel]})
        if critical_table_panel is not None:
            blocks.append({"kind": "page", "dark": False, "panels": [critical_table_panel]})

    # ---- Ranking Entitas/Aset Tersering (versi padat/batang, khas Management Report — TIDAK
    # ikut pengacakan gaya kartu/podium SOC, lihat _build_management_asset_ranking_block/slide) ----
    if asset_pick and is_included("asset_cards"):
        asset_label, asset_pick_items = asset_pick
        bar_items = []
        for idx, item in enumerate(asset_pick_items[:5]):
            bar_items.append({
                "num": str(idx + 1),
                "name": item["value"],
                "count": item["count"],
                "stat": L(f"{item['count']} event", f"{item['count']} events") if sec_domain
                else L(f"{item['count']} data", f"{item['count']} entries"),
            })
        blocks.append({
            "kind": "management_asset_ranking",
            "kicker": L("SOROTAN INSIDEN", "INCIDENT HIGHLIGHT") if sec_domain else L("SOROTAN DATA", "DATA HIGHLIGHT"),
            "title": L(
                f"{humanize_label(asset_label, source_cols)} yang Paling Sering Menjadi Sasaran",
                f"Most Frequently Affected {humanize_label(asset_label, source_cols)}",
            ) if sec_domain else L(
                f"{humanize_label(asset_label, source_cols)} Paling Sering Muncul",
                f"Most Frequent {humanize_label(asset_label, source_cols)}",
            ),
            "items": bar_items,
        })

    # ---- Insight/Narasi Bebas AI TANPA data kategori (dihitung di atas, sebelum tile
    # dashboard — lihat narrative_items/_custom_chart_styles) — TIDAK dikontrol checkbox
    # "Include Sections", otomatis muncul kalau AI menulis narasi tambahan di luar section
    # baku; dirender sbg grid kartu, lihat _build_management_ai_narrative_block/slide) ----
    # PERMINTAAN USER (poin 3 — "kalau isinya genuinely cuma 1-2 kalimat, jangan beri
    # halaman sendiri... yang tidak boleh: satu halaman penuh utk dua kalimat"): topik
    # SEDIKIT (<=2) TIDAK lagi dapat halaman "management_ai_narrative" solo — digabung sbg
    # catatan tambahan ke halaman "management_insight_page" TERAKHIR yang sudah ada (posisi
    # narasi paling relevan dgn topik yang baru dibahas), bukan halaman kosong beralasan.
    # Kalau genuinely tidak ada satu pun halaman insight utk disisipi (laporan tanpa tile
    # visual sama sekali - kasus langka), jatuh kembali ke halaman solo lama (jaring
    # pengaman, tidak pernah lebih buruk dari sebelumnya).
    _MGMT_NARRATIVE_SOLO_THRESHOLD = 2
    if narrative_items and len(narrative_items) <= _MGMT_NARRATIVE_SOLO_THRESHOLD:
        target_insight_page = next((b for b in reversed(blocks) if b.get("kind") == "management_insight_page"), None)
        if target_insight_page is not None:
            extra_notes = [
                _shorten_to_caption(f"{item['title']}. {item['content']}" if item.get("title") else item["content"], max_sentences=2)
                for item in narrative_items
            ]
            target_insight_page["notes"] = [*(target_insight_page.get("notes") or []), *extra_notes]
            narrative_items = []

    mgmt_narrative_per_page = 4
    for chunk_index in range(0, len(narrative_items), mgmt_narrative_per_page):
        chunk = narrative_items[chunk_index:chunk_index + mgmt_narrative_per_page]
        continuation = chunk_index > 0
        blocks.append({
            "kind": "management_ai_narrative",
            "kicker": L("ANALISIS", "ANALYSIS"),
            "title": L("Insight Tambahan" if not continuation else "Insight Tambahan (Lanjutan)", "Additional Insights" if not continuation else "Additional Insights (Continued)"),
            "items": chunk,
        })

    # ---- Action Items / Rekomendasi dengan Urgensi ----
    action_items = []
    urgency_map = ["critical", "high", "medium", "low"]
    for idx, rec in enumerate(recommendations if is_included("recommendations") else []):
        raw_title = rec.get("title")
        raw_detail = rec.get("detail") or ""
        # BUG DIPERBAIKI: sebelumnya `detail` SELALU diisi teks penuh `raw_detail` apa
        # adanya, terlepas apakah `title` di atas sudah "mencuri" kalimat pertamanya lewat
        # partition(". ") — hasilnya judul & detail tampil dgn isi yang SAMA PERSIS berulang
        # di kartu. Sekarang detail = SISA kalimat setelah judul diambil (partition
        # mengembalikan bagian sebelum & sesudah pemisah), kosong kalau tidak ada sisa.
        if raw_title:
            title = sanitize_text(raw_title)
            detail = sanitize_text(raw_detail) if raw_detail else None
        else:
            title_part, _, rest = raw_detail.partition(". ")
            title = sanitize_text(title_part or raw_detail)
            detail = sanitize_text(rest.strip()) if rest.strip() else None
        if detail:
            detail = _shorten_to_caption(detail, max_sentences=1)
        urgency = urgency_map[min(idx, len(urgency_map) - 1)]
        action_items.append({
            "number": idx + 1,
            "title": title,
            "detail": detail,
            "urgency": urgency,
        })
    # ---- Kesimpulan — datanya dihitung DULU (permintaan user lanjutan: "Rekomendasi
    # Prioritas pakai lapis yang sama dgn halaman insight baru... kalau masih ada sisa,
    # tarik Kesimpulan naik ke halaman yang sama") — supaya bisa diputuskan digabung ke
    # chunk TERAKHIR "Rekomendasi Prioritas" (kalau chunk itu genuinely py sisa ruang, lihat
    # _mgmt_action_conclusion_fits di bawah) drpd SELALU jadi halaman solo terpisah spt
    # sebelumnya (BUG NYATA ditemukan lewat tes kepadatan halaman: "Kesimpulan" solo adalah
    # penyumbang kegagalan kepadatan TERBANYAK di seluruh laporan).
    mgmt_conclusion_text = None
    mgmt_pills: list = []
    mgmt_priority_items: list = []
    if is_included("conclusion") and ai_summary.get("conclusion"):
        _raw_mgmt_conclusion = sanitize_text(coerce_narrative_text(ai_summary.get("conclusion")))
        _raw_mgmt_conclusion, _ = _verify_narrative_sentences(
            _raw_mgmt_conclusion, report_stats, field_name="conclusion", report_id=getattr(report, "id", None),
            parsed_data=parsed_data,
        )
        if _raw_mgmt_conclusion:
            mgmt_conclusion_text = _raw_mgmt_conclusion
            if total_sev and status_col:
                mgmt_resolved_pct = round((total_sev - open_count) / total_sev * 100, 1)
                mgmt_pills.append(L(
                    f"{mgmt_resolved_pct}% event tertangani" if sec_domain else f"{mgmt_resolved_pct}% data tertangani",
                    f"{mgmt_resolved_pct}% of events resolved",
                ))
            if category_pick:
                mgmt_pills.append(L(
                    f"{category_pick[1][0]['value']} jadi prioritas perhatian",
                    f"{category_pick[1][0]['value']} is the top priority",
                ))
            if open_count:
                mgmt_pills.append(L(
                    f"{open_count} insiden masih berjalan" if sec_domain else f"{open_count} item masih berjalan",
                    f"{open_count} incidents still in progress" if sec_domain else f"{open_count} items still in progress",
                ))
            mgmt_recommendations_shown = bool(is_included("recommendations") and recommendations)
            if not mgmt_recommendations_shown:
                for idx, rec in enumerate(recommendations):
                    letter = chr(ord("a") + idx) if idx < 26 else str(idx + 1)
                    rec_title = rec.get("title") or (rec.get("detail") or "").partition(". ")[0] or rec.get("detail") or ""
                    mgmt_priority_items.append({"letter": letter, "text": sanitize_text(rec_title)})

    # Digabung ke chunk TERAKHIR "Rekomendasi Prioritas" HANYA kalau chunk itu genuinely
    # tidak terlalu penuh sendiri (<=4 item — chunk 5-6 item biasanya sudah cukup mengisi
    # halaman tanpa Kesimpulan) — sama semangat volume-budget dgn should_combine_closing
    # gaya SOC, cuma disederhanakan (item Rekomendasi Prioritas relatif seragam ukurannya,
    # beda dgn Temuan/Rekomendasi SOC yang narasinya bisa jauh lebih panjang).
    conclusion_used = False
    for chunk_index in range(0, len(action_items), 6):
        chunk = action_items[chunk_index:chunk_index + 6]
        if not chunk:
            continue
        continuation = chunk_index > 0
        is_last_chunk = (chunk_index + 6) >= len(action_items)
        block = {
            "kind": "management_action_items",
            "kicker": L("TINDAK LANJUT", "ACTION ITEMS"),
            "title": L("Rekomendasi Prioritas" if not continuation else "Rekomendasi Prioritas (Lanjutan)", "Priority Recommendations" if not continuation else "Priority Recommendations (Continued)"),
            "items": chunk,
        }
        if is_last_chunk and mgmt_conclusion_text and len(chunk) <= 4:
            block["conclusion_title"] = L("Kesimpulan", "Conclusion")
            block["conclusion_text"] = _shorten_to_caption(mgmt_conclusion_text, max_sentences=2)
            block["conclusion_pills"] = mgmt_pills
            conclusion_used = True
        blocks.append(block)

    # Kesimpulan TETAP jadi halaman solo (gaya lama, sudah dinamis dari isi teksnya sendiri
    # sejak perbaikan E3) kalau tidak ada "Rekomendasi Prioritas" utk digabung sama sekali,
    # ATAU chunk terakhirnya sudah terlalu penuh (>4 item) utk menampung Kesimpulan juga.
    if mgmt_conclusion_text and not conclusion_used:
        blocks.append({
            "kind": "page",
            "dark": True,
            "panels": [{
                "panel_kind": "conclusion",
                "kicker": L("RINGKASAN AKHIR", "FINAL SUMMARY"), "title": L("Kesimpulan", "Conclusion"),
                "text": _shorten_to_caption(mgmt_conclusion_text, max_sentences=3), "pills": mgmt_pills,
                "priority_panel_title": L("Prioritas Berikutnya", "Next Priorities"),
                "priority_items": mgmt_priority_items,
            }],
        })

    # ---- Closing ----
    blocks.append({
        "kind": "closing",
        "dark": True,
        "title": report.title,
        "thank_you": L("Terima Kasih", "Thank You"),
        "note": L("Laporan ini disiapkan untuk keperluan manajemen.", "This report is prepared for management use."),
        "hero_stat": (str(total_records), L("Total Data", "Total Records")),
        "header_title": (report.header_title or "PT PETROKIMIA GRESIK").upper(),
    })

    # PERMINTAAN USER (temuan dari audit langsung: 6 halaman insight topik berbeda ternyata
    # menampilkan 8 entitas yang PERSIS sama) - dijalankan PALING AKHIR (stlh SEMUA blok,
    # termasuk closing, terbentuk) supaya penggabungan melihat gambaran lengkap 1 laporan.
    blocks = _merge_overlapping_insight_pages(blocks, report)
    # PERMINTAAN USER (perombakan kepadatan): dijalankan SETELAH penggabungan halaman berulang
    # supaya yang dikemas jadi kolom cuma topik yang genuinely berbeda - bukan duplikat yang
    # seharusnya dibuang lebih dulu.
    blocks = _pack_insight_pages_into_columns(blocks, report)

    return blocks
