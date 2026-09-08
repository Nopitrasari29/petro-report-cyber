"""
Tes parity export PDF vs PPT — memastikan KEDUA exporter (export_pdf.py &
export_ppt.py) benar-benar merender SEMUA elemen visual (tiap tile_kind/panel_kind)
dari block plan yang SAMA (report_render_logic.py, sumber tunggal dibaca keduanya),
bukan diam-diam melewatkan salah satu elemen di salah satu format tanpa jejak error
apa pun — persis kelas bug yang ditemukan & diperbaiki lewat verifikasi manual di
sesi perbaikan dashboard overflow (lihat catatan panjang di
_build_management_visual_dashboard_block/_slide, export_pdf.py & export_ppt.py).

Ditulis TANPA bergantung pytest (belum jadi dependency proyek ini) — jalankan
langsung:
    venv/Scripts/python.exe backend/tests/test_export_parity.py
Kalau pytest ditambahkan belakangan, fungsi test_*() di sini otomatis ikut
ke-collect tanpa perubahan apa pun (nama & signature sudah konvensi pytest).

Dipakai laporan SUNGGUHAN dari database (bukan data sintetis) supaya kombinasi
tile/panel yang dites benar-benar mencerminkan yang muncul di produksi — diambil
dinamis (bukan ID hardcode) supaya tes ini tidak basi begitu laporan lama dihapus.
"""
import inspect
import io
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import fitz
from pptx import Presentation
from pptx.util import Emu

from app.db.session import SessionLocal
from app.models.report import Report
from app.services import export_pdf as ep
from app.services import export_ppt as eppt
from app.services.report_render_logic import (
    build_management_report_blocks, build_report_blocks,
    _insight_page_entity_set, _entity_set_overlap, _INSIGHT_PAGE_OVERLAP_THRESHOLD,
)

# Maks berapa laporan per gaya (Management/SOC) yang dites — dites lebih dari 1 laporan
# per gaya supaya cakupan tile/panel-nya lebih luas (tiap laporan punya kombinasi acak
# category_style/status_style/dst, lihat pick_visual_style()), TANPA membuat tes ini
# lambat kalau laporan di database sudah sangat banyak.
MAX_REPORTS_PER_STYLE = 4


def _normalize_ws(text: str) -> str:
    """Ratakan SEMUA whitespace (spasi/newline/tab) jadi 1 spasi — BUG DIPERBAIKI (ditemukan
    lewat false-positive di tes ini sendiri, report id 167): judul tile yang panjang wrap
    ke BEBERAPA BARIS di kartu sempit (mis. "Trend Analysis of Authentication Failures" jadi
    4 baris terpisah) — PyMuPDF/python-pptx mengekstrak tiap baris wrap itu DIPISAH "\n",
    bukan spasi biasa. Needle pencarian yang dibentuk dari string judul ASLI (pakai spasi
    biasa) jadi TIDAK PERNAH cocok dgn teks hasil ekstrak (pakai newline) walau kontennya
    genuinely ADA & benar di render-nya — false alarm "hilang", padahal cuma soal
    normalisasi whitespace di tes-nya sendiri, bukan bug di exporter."""
    return re.sub(r"\s+", " ", text).strip()


def _pdf_text(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    return _normalize_ws("\n".join(p.get_text() for p in doc).upper())


def _ppt_text(ppt_bytes: bytes) -> str:
    prs = Presentation(io.BytesIO(ppt_bytes))
    chunks = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                chunks.append(shape.text_frame.text)
            if getattr(shape, "has_chart", False):
                try:
                    for cat in shape.chart.plots[0].categories:
                        chunks.append(str(cat))
                except Exception:
                    pass
    return _normalize_ws("\n".join(chunks).upper())


def _titled_elements(report: Report) -> list:
    """[(kind, title)] utk tiap tile/panel di block plan report ini — SUMBER TUNGGAL
    yang dibaca KEDUA exporter, jadi kalau salah satu exporter melewatkan satu elemen
    ini, itu genuinely bug parity antar-format, bukan sekadar beda data sumber."""
    template = (report.template_type or "").strip().lower()
    blocks = build_management_report_blocks(report) if "management" in template else build_report_blocks(report)
    elements = []
    for b in blocks:
        for t in (b.get("tiles") or []):
            title = t.get("title")
            if title:
                elements.append((t.get("tile_kind", "?"), title))
        for p in (b.get("panels") or []):
            title = p.get("title") or p.get("heading")
            if title:
                elements.append((p.get("panel_kind", "?"), title))
        # PERMINTAAN USER ("Tata letak — ini yang menentukan kepadatan"): halaman
        # "management_insight_page" (lapis KPI/detail per kategori/catatan, BUKAN
        # tiles/panels) — dicek terpisah supaya tes ini genuinely memverifikasi elemen
        # barunya, bukan diam2 tidak mengecek apa pun krn skema dict-nya beda.
        if b.get("kind") == "management_insight_page":
            for card in (b.get("kpi_summary") or []):
                elements.append(("insight_kpi", str(card.get("value", ""))))
            for cd in (b.get("category_details") or []):
                elements.append(("insight_category", cd.get("name", "")))
    return elements


def _run_parity_check(report_ids: list) -> list:
    """Return list of failure message strings (kosong kalau semua lolos)."""
    db = SessionLocal()
    failures = []
    try:
        for rid in report_ids:
            report = db.get(Report, rid)
            if report is None:
                continue
            elements = _titled_elements(report)
            if not elements:
                continue  # laporan tanpa tile/panel bertitel apa pun, tidak relevan utk tes ini

            pdf_bytes = ep.PDFExporter.generate_pdf_report(report)
            ppt_bytes = eppt.PPTXExporter.generate_ppt_report(report)
            pdf_text = _pdf_text(pdf_bytes)
            ppt_text = _ppt_text(ppt_bytes)

            for kind, title in elements:
                # 30 karakter pertama cukup jadi penanda unik tanpa rapuh thd
                # perbedaan word-wrap/pemotongan ellipsis di ujung judul panjang.
                needle = _normalize_ws(str(title)[:30].upper())
                if needle not in pdf_text:
                    failures.append(f"report {rid}: PDF tidak menemukan [{kind}] {title!r}")
                if needle not in ppt_text:
                    failures.append(f"report {rid}: PPT tidak menemukan [{kind}] {title!r}")

            # PERMINTAAN USER (G4): "utk tiap panel_kind dan tile_kind, pastikan kedua exporter
            # menghasilkan jumlah elemen visual yang sama dari block plan yang sama" — dicoba
            # lewat invariant struktural yang PASTI (bukan tebak-tebakan cocok teks): block plan
            # yang SAMA (1 block = 1 halaman/slide fisik di KEDUA exporter, lihat _page()/
            # add_slide() dipanggil 1x per block di masing2) HARUS menghasilkan jumlah HALAMAN
            # PDF == jumlah SLIDE PPT persis sama. Kalau salah satu exporter diam2 menggabung/
            # memecah/melewati 1 block yang seharusnya 1 halaman, ketidaksamaan ini ketahuan
            # tanpa perlu tahu kind/judul spesifik mana yang bermasalah.
            pdf_page_count = len(fitz.open(stream=pdf_bytes, filetype="pdf"))
            ppt_slide_count = len(Presentation(io.BytesIO(ppt_bytes)).slides)
            if pdf_page_count != ppt_slide_count:
                failures.append(
                    f"report {rid}: jumlah halaman PDF ({pdf_page_count}) != jumlah slide PPT "
                    f"({ppt_slide_count}) dari block plan yang sama"
                )
    finally:
        db.rollback()
        db.close()
    return failures


def _sample_report_ids(template_contains: str, limit: int | None) -> list:
    """`limit=None` -> AMBIL SEMUA.

    KOREKSI USER: pemeriksaan kepadatan dulu cuma mengambil 8 laporan teratas per gaya, & itu
    yang membuat laporan 171 (halaman insight solo, 30 elemen) lolos berbulan-bulan - bukan
    karena tesnya salah menilai, tapi karena laporan itu TIDAK PERNAH DIPERIKSA. "Setiap kali
    cakupan pengukuran diperlebar, selalu ada yang muncul" - jadi cakupan yang sempit itu
    masalah yang lebih besar daripada bug yang disembunyikannya."""
    db = SessionLocal()
    try:
        query = db.query(Report.id)
        if template_contains:
            query = query.filter(Report.template_type.ilike(f"%{template_contains}%"))
        else:
            query = query.filter(~Report.template_type.ilike("%management%"))
        query = query.order_by(Report.id.desc())
        rows = (query.limit(limit) if limit else query).all()
        return [r[0] for r in rows]
    finally:
        db.rollback()
        db.close()


def test_management_reports_render_every_tile_in_both_formats():
    report_ids = _sample_report_ids("management", MAX_REPORTS_PER_STYLE)
    failures = _run_parity_check(report_ids)
    assert not failures, "Parity export PDF/PPT (Management) gagal:\n" + "\n".join(failures)


def test_soc_reports_render_every_panel_in_both_formats():
    report_ids = _sample_report_ids("", MAX_REPORTS_PER_STYLE)
    failures = _run_parity_check(report_ids)
    assert not failures, "Parity export PDF/PPT (SOC) gagal:\n" + "\n".join(failures)


def test_panel_kind_and_tile_kind_dispatch_parity():
    """PERMINTAAN USER (G4): "utk tiap panel_kind dan tile_kind, pastikan kedua exporter
    menghasilkan jumlah elemen visual yang sama dari block plan yang sama". Cek page/slide-COUNT
    di atas cuma menjamin STRUKTUR (jumlah halaman) sama, TIDAK menjamin ISI tiap panel/tile di
    dalamnya benar2 digambar kedua exporter — kalau salah satu ketinggalan menambah dispatch utk
    1 panel_kind/tile_kind baru, panel/tile itu DIAM2 tidak digambar apa pun di exporter itu
    (lihat `_build_page_slide`'s else-branch & rantai if/elif tile_kind di
    `_build_management_visual_dashboard_slide`/`_mgmt_tile_chart_html` — keduanya TIDAK melempar
    error kalau kind tidak dikenali) tanpa exception apa pun yang ketahuan dari cek page-count
    saja. Didekati lewat INTROSPEKSI REGISTRY/SOURCE (bukan parse teks hasil render — PDF/PPT
    TIDAK menyimpan metadata "kind" apa pun di elemen visual hasil render, lihat catatan
    _titled_elements di atas), supaya tes ini SELALU lengkap (bukan cuma kind yang kebetulan
    muncul di laporan sample) & otomatis ikut update kalau ada kind baru ditambah salah satu
    exporter (regex, bukan daftar kind di-hardcode manual)."""
    pdf_panel_kinds = set(ep._PDF_PANEL_BUILDERS.keys())
    ppt_panel_kinds = set(eppt._PPT_PANEL_STANDALONE_BUILDERS.keys()) | eppt._PPT_DISTRIBUTION_KINDS | eppt._PPT_INSIGHT_KINDS
    missing_in_ppt = pdf_panel_kinds - ppt_panel_kinds
    missing_in_pdf = ppt_panel_kinds - pdf_panel_kinds
    assert not missing_in_ppt, f"panel_kind ada builder PDF-nya tapi TIDAK dikenali dispatch PPT (bakal hilang diam2 di PPT): {missing_in_ppt}"
    assert not missing_in_pdf, f"panel_kind dikenali dispatch PPT tapi TIDAK ada builder PDF-nya: {missing_in_pdf}"

    kind_pattern = re.compile(r'kind == "([a-z_]+)"')
    pdf_tile_kinds = set(kind_pattern.findall(inspect.getsource(ep._mgmt_tile_chart_html)))
    ppt_tile_kinds = set(kind_pattern.findall(inspect.getsource(eppt._draw_dashboard_main_visual)))
    assert pdf_tile_kinds, "regex tidak menemukan tile_kind apa pun di _mgmt_tile_chart_html -- pola dispatch source berubah, perbaiki regex tes ini"
    assert pdf_tile_kinds == ppt_tile_kinds, (
        f"dispatch tile_kind PDF vs PPT beda -- hanya di PDF: {pdf_tile_kinds - ppt_tile_kinds}, "
        f"hanya di PPT: {ppt_tile_kinds - pdf_tile_kinds}"
    )


_PAGE_NUM_RE = re.compile(r"^\d{1,2}\s*/\s*\d{1,2}$")
_DENSITY_EXCLUDE_KINDS = {"cover", "closing"}
# PERMINTAAN USER (koreksi eksplisit — tes versi lama cuma mengecek 2 jenis halaman ini,
# "berarti tes kepadatannya hanya diterapkan ke halaman insight, bukan ke seluruh laporan"):
# SEKARANG SEMUA jenis halaman isi dicek (apa pun `kind`-nya, KECUALI cover/closing di
# _DENSITY_EXCLUDE_KINDS) — supaya angkanya mencerminkan laporan yang sebenarnya, bukan cuma
# bagian yang dirombak sesi ini. Konstanta ini DIPERTAHANKAN (bukan dihapus) krn beberapa
# komentar lama di file ini masih merujuknya - definisinya sekarang murni "bukan exclude",
# dipakai di _CHECKED lewat pengecualian di bawah.
_DENSITY_CHECKED_KINDS = None  # None = semua kind DICEK kecuali _DENSITY_EXCLUDE_KINDS

# PERMINTAAN USER (poin 1): halaman chart tunggal (radar/gauge/dst, lihat
# _build_chart_insight_page & kpi_gauge branch di report_render_logic.py) BOLEH jadi
# pengecualian kepadatan yang SAH — TAPI HANYA kalau data yang mendasarinya genuinely sedikit
# ("chart_category_count" < ambang ini) DAN halaman itu py catatan analitis (`notes`) — bukan
# pengecualian berdasar JENIS chart (radar dgn 8 kategori tetap harus penuh spt kartu biasa).
_CHART_EXEMPTION_MAX_CATEGORIES = 5


def _di_dalam(bbox, daftar_bbox) -> bool:
    """Apakah bbox berada di dalam salah satu bbox tabel (toleransi 2pt)."""
    if not bbox or not daftar_bbox:
        return False
    x0, y0, x1, y1 = bbox
    for tx0, ty0, tx1, ty1 in daftar_bbox:
        if x0 >= tx0 - 2 and y0 >= ty0 - 2 and x1 <= tx1 + 2 and y1 <= ty1 + 2:
            return True
    return False


def _pdf_page_density(pdf_bytes: bytes, block_kinds: list, table_pages: set | None = None) -> list:
    """[(page_index, kind, n_elements, n_chars)] — GANTI TOTAL dari metrik lama (posisi batas
    bawah elemen terjauh / tinggi halaman).

    BUG NYATA DITEMUKAN (dilaporkan user, dgn angka pembanding persis dihitung langsung dari
    file PPTX): metrik posisi itu BUTA thd KEPADATAN sungguhan — semua halaman hasil berakhir
    di y=7.38-7.40in (~98% "terisi") krn lapis fungsi halaman insight (_layout_insight_layers)
    SELALU meregangkan GAP antar lapis mengisi sisa tinggi kalau kontennya tidak sampai penuh
    (lihat catatan di sana) - jadi elemen TERAKHIR (mis. catatan/gap) nyaris selalu ada di
    dekat batas bawah halaman APAPUN jumlah/kepadatan KONTEN sungguhan di atasnya. Laporan
    nyata: halaman radar cuma 5 elemen/95 karakter tetap lolos "98% terisi" krn radar-nya
    sendiri (1 elemen SVG) diregangkan tinggi lewat CSS, bukan krn genuinely padat konten.

    Metrik baru: JUMLAH ELEMEN (blok teks + drawing + gambar, minus background halaman penuh &
    nomor halaman - pengecualian yang SAMA dgn versi lama, itu bagian yang sudah benar) & TOTAL
    KARAKTER teks di halaman itu - keduanya tidak peduli DI MANA elemen itu diposisikan
    (langsung sensitif thd "seberapa BANYAK yang sungguhan ditampilkan", bukan "sejauh mana
    ruang kosong DIREGANGKAN")."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if len(doc) == 0:
        return []
    page_w, page_h = doc[0].rect.width, doc[0].rect.height
    results = []
    for i, page in enumerate(doc):
        kind = block_kinds[i] if i < len(block_kinds) else "?"
        if kind in _DENSITY_EXCLUDE_KINDS:
            continue
        n_elements = 0
        n_chars = 0
        # Penghitungan per-sel HANYA di halaman yang datanya MEMANG berisi tabel (dari blok,
        # lewat `table_pages`) - BUKAN dari deteksi geometris.
        #
        # BUG ALAT UKUR HAMPIR LOLOS: page.find_tables() salah mengenali grid KARTU halaman
        # dasbor sbg tabel (5-6 "tabel" per halaman). Karena blok teks & drawing di dalam
        # bbox tabel dilewati agar tidak terhitung dua kali, elemen asli halaman ikut
        # tertelan: laporan 183 hal. 2 terbaca 68 elemen padahal 136. Angka itu terlihat
        # wajar & akan membuat halaman TERPADAT ditandai renggang lalu "diperbaiki".
        if i in (table_pages or set()):
            try:
                tabel_terdeteksi = list(page.find_tables().tables)
            except Exception:
                tabel_terdeteksi = []
        else:
            tabel_terdeteksi = []
        tabel_bbox = [tuple(t.bbox) for t in tabel_terdeteksi]
        for block in page.get_text("dict").get("blocks", []):
            text = "".join(span.get("text", "") for line in block.get("lines", []) for span in line.get("spans", [])).strip()
            if not text or _PAGE_NUM_RE.match(text):
                continue
            if _di_dalam(block.get("bbox"), tabel_bbox):
                continue
            n_elements += 1
            n_chars += len(text)
        # TABEL dihitung PER SEL, sama spt sisi PPT. Tanpa ini kedua sisi mengukur tabel dgn
        # cara BERBEDA: PDF per baris teks (9 blok), PPT per sel (36) - terukur selisih 16
        # elemen utk isi yang identik, murni dari cara mengukur. Blok teks & drawing yang
        # jatuh DI DALAM bbox tabel dilewati supaya tidak terhitung dua kali (garis/isian sel
        # muncul sbg drawing tersendiri).
        for t in tabel_terdeteksi:
            for row in t.extract():
                for cell in row:
                    n_elements += 1
                    n_chars += len(str(cell or ""))
        for d in page.get_drawings():
            rect = d["rect"]
            w, h = rect[2] - rect[0], rect[3] - rect[1]
            if w >= 0.95 * page_w and h >= 0.95 * page_h:
                continue
            if _di_dalam(tuple(rect), tabel_bbox):
                continue
            n_elements += 1
        for img in page.get_image_info():
            bbox = img["bbox"]
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            if w >= 0.95 * page_w and h >= 0.95 * page_h:
                continue
            n_elements += 1
        results.append((i, kind, n_elements, n_chars))
    return results


def _ppt_page_density(ppt_bytes: bytes, block_kinds: list) -> list:
    """Padanan _pdf_page_density utk PPT — [(slide_index, kind, n_elements, n_chars)]. Dihitung
    PERSIS dgn cara yang sama dipakai user mengukur file referensi (jumlah SHAPE & total
    karakter, langsung dari file PPTX) — supaya angka dari tes ini bisa dibandingkan apple-to-
    apple dgn angka referensi yang sudah diukur user scr manual."""
    prs = Presentation(io.BytesIO(ppt_bytes))
    slide_w, slide_h = Emu(prs.slide_width).inches, Emu(prs.slide_height).inches
    results = []
    for i, slide in enumerate(prs.slides):
        kind = block_kinds[i] if i < len(block_kinds) else "?"
        if kind in _DENSITY_EXCLUDE_KINDS:
            continue
        n_elements = 0
        n_chars = 0
        for shape in slide.shapes:
            if shape.has_text_frame and _PAGE_NUM_RE.match(shape.text_frame.text.strip()):
                continue
            try:
                left_in, top_in = Emu(shape.left).inches, Emu(shape.top).inches
                w_in, h_in = Emu(shape.width).inches, Emu(shape.height).inches
            except Exception:
                left_in = top_in = 0.0
                w_in = h_in = 0.0
            if left_in <= 0.05 and top_in <= 0.05 and w_in >= 0.95 * slide_w and h_in >= 0.95 * slide_h:
                continue
            # BUG ALAT UKUR DIPERBAIKI (ditemukan waktu menyelidiki "5 elemen/131 karakter"
            # di halaman tabel laporan 158 - dikira isi hilang, ternyata TABELNYA ada, 12.33
            # x 4.90in berisi 8 baris): shape TABLE py has_text_frame False & teksnya ada di
            # dalam SEL, jadi tabel seberapa pun besarnya dulu terhitung 1 elemen/0 karakter.
            # Metrik yang buta thd tabel akan menandai halaman yang genuinely padat sbg
            # renggang - persis kebalikan dari gunanya metrik ini.
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    for cell in row.cells:
                        n_elements += 1
                        n_chars += len(cell.text)
                continue
            n_elements += 1
            if shape.has_text_frame:
                n_chars += len(shape.text_frame.text)
        results.append((i, kind, n_elements, n_chars))
    return results


# PERMINTAAN USER (setelah melihat hasil nyata): ambang elemen diturunkan 40 -> 35. Alasannya
# BUKAN "supaya lulus", tapi karena ambang yang IDENTIK utk PDF & PPTX memang tidak adil -
# keduanya menggambar isi yang SAMA dgn jumlah objek berbeda (contoh nyata laporan 180 hal.05:
# 50 elemen di PPTX vs 30 di PDF utk konten yang sama persis). Selisih 1 elemen dari ambang
# (hal.06: 39 vs 40) juga menandakan ambangnya yang kaku, bukan halamannya yang kurang isi.
# Ambang KARAKTER (800) TIDAK diturunkan, dan lantai keras 5 elemen tetap berlaku - jadi
# halaman yang genuinely kosong/rusak tetap tertangkap.
_DENSITY_MIN_ELEMENTS = 35
_DENSITY_MIN_CHARS = 800
# PERMINTAAN USER (lantai keras, setelah pengecualian chart terbukti meloloskan halaman yang
# isinya lenyap saat render): halaman dgn elemen SANGAT sedikit SELALU gagal - tidak ada
# pengecualian apa pun (chart tunggal maupun lainnya) yang boleh menutupinya. 2 elemen bukan
# "chart tunggal yang sah", itu sisa halaman yang kontennya hilang.
_DENSITY_ABSOLUTE_MIN_ELEMENTS = 5
# PERMINTAAN USER (setelah perombakan pengemasan): halaman DASBOR multi-kolom membawa 2-3
# topik sekaligus, jadi ambangnya tidak lagi sama dgn halaman biasa - minimal 90 elemen.
# Angkanya realistis, bukan aspirasi: halaman hasil pengemasan pertama terukur 98 elemen.
# KEPUTUSAN USER (revisi dari ambang per HALAMAN): ambang halaman dasbor dihitung PER KOLOM,
# bukan per halaman. Ambang 90 dulu dikalibrasi dari halaman 3 kolom, jadi halaman 2 kolom
# secara matematis tidak mungkin mencapainya dgn topik yang sama - bukan karena renggang,
# tapi karena kolomnya memang cuma dua. 30 per kolom: 2 kolom = 60, 3 kolom = 90.
_DENSITY_DASHBOARD_MIN_PER_COLUMN = 30
_DASHBOARD_PAGE_KINDS = {"management_dashboard_columns"}

# KEPUTUSAN USER: halaman REKOMENDASI & SECTION NARATIF py ambang SENDIRI - "isinya memang
# rekomendasi bernarasi, bukan visual", jadi memaksanya mencapai ambang dasbor salah sasaran.
# Dinilai dari KARAKTER saja: jumlah elemennya melekat pada bentuknya (tiap rekomendasi =
# 1-2 elemen), jadi 30 elemen bukan tanda renggang. Terukur dari 28 halaman rekomendasi &
# 4 halaman naratif di SELURUH laporan Visual: 719-1.709 karakter, median 956. Ambang 600
# kira-kira setara 4 rekomendasi; di bawah itu halamannya genuinely kosong, bukan bergaya teks.
_NARRATIVE_PAGE_KINDS = {"management_action_items", "management_ai_narrative"}
_DENSITY_NARRATIVE_MIN_CHARS = 600


def _expected_column_sizes(n_topics: int, per_page: int = 3) -> list:
    """Ukuran halaman yang SEHARUSNYA - pembagian serata mungkin, tanpa keranjang berisi satu.

    SYARAT USER: halaman 2 kolom hanya SAH kalau jumlah topiknya memang tidak cukup utk 3
    kolom. Tanpa ini, pembagi bisa "lolos" ambang cuma dgn memilih 2 kolom (ambangnya lebih
    rendah) padahal topiknya cukup utk 3 - lubang yang persis sebaliknya dari yang mau
    ditutup. Jadi ukuran halaman nyata dibandingkan dgn pembagian yang seharusnya."""
    if n_topics <= 0:
        return []
    n_pages = max(1, -(-n_topics // per_page))
    base, extra = divmod(n_topics, n_pages)
    return sorted([base + (1 if i < extra else 0) for i in range(n_pages)], reverse=True)


def _page_is_chart_exempt(block: dict) -> bool:
    """PERMINTAAN USER (poin 1 — "tandai sebagai pengecualian sah, HANYA kalau data yang
    mendasarinya <5 kategori, DAN halaman itu wajib punya catatan analitis. Jangan jadikan
    pengecualian berdasarkan jenis chart"): dicek dari FAKTA DATA yang disimpan block-nya
    sendiri (chart_category_count, diisi report_render_logic.py::_build_chart_insight_page
    & kpi_gauge branch di _build_insight_page) — BUKAN dari `kind`/tile_kind. Radar/gauge/dst
    dgn kategori >=5 TIDAK lolos syarat ini & tetap harus padat spt halaman lain.

    BATAS KERAS TAMBAHAN (dilaporkan user, dibuktikan dari laporan 176 hal.03): pengecualian
    ini pernah MELOLOSKAN halaman RUSAK - blok-nya memang py chart & catatan di RENCANA
    laporan (jadi syarat di atas terpenuhi), TAPI isinya lenyap saat render (cuma judul +
    logo tersisa, 2 elemen/79 karakter). Krn syarat pengecualian dihitung dari RENCANA
    sementara kepadatan diukur dari HASIL RENDER, kegagalan render justru berubah jadi tiket
    lolos otomatis. Ambang keras `_DENSITY_ABSOLUTE_MIN_ELEMENTS` di pemanggil menutup celah
    itu: berapa pun alasannya, halaman dgn elemen di bawah ambang itu SELALU gagal - tidak ada
    pengecualian apa pun yang bisa menutupinya."""
    cat_count = block.get("chart_category_count")
    if cat_count is None or cat_count >= _CHART_EXEMPTION_MAX_CATEGORIES:
        return False
    return bool(block.get("notes"))


def test_management_dashboard_pages_are_densely_filled():
    """PERMINTAAN USER (koreksi bertahap, 3 putaran — lihat riwayat kerja panjang):
    1. Kepadatan diukur dari JUMLAH ELEMEN & TOTAL KARAKTER per halaman (metrik posisi lama
       terbukti BUTA, lihat docstring _pdf_page_density).
    2. Halaman lolos kalau SALAH SATU ambang terpenuhi (>=40 elemen ATAU >=800 karakter) -
       halaman naratif padat teks (elemen sedikit, karakter tinggi) genuinely lolos lewat
       jalur karakter, bukan cacat.
    3. SEMUA jenis halaman isi dicek (bukan cuma management_visual_dashboard/
       management_insight_page lagi) - baik laporan Management maupun SOC/deskriptif.
    4. Halaman chart tunggal yang datanya genuinely <5 kategori DAN py catatan analitis
       (lihat _page_is_chart_exempt) ditandai PENGECUALIAN SAH - dilaporkan terpisah,
       TIDAK dihitung sbg kegagalan tes."""
    db = SessionLocal()
    failures = []
    exemptions = []
    try:
        # SELURUH laporan Visual (bukan 8 teratas) - lihat catatan di _sample_report_ids.
        # Sisi Deskriptif masih dicuplik: jalur itu belum dikerjakan (ditunda user), jadi
        # memeriksa 101 laporan di sana cuma memperpanjang daftar gagal yang sudah diketahui.
        report_ids = [(rid, "management") for rid in _sample_report_ids("management", None)]
        report_ids += [(rid, "soc") for rid in _sample_report_ids("", 8)]
        for rid, style in report_ids:
            report = db.get(Report, rid)
            if report is None:
                continue
            blocks = build_management_report_blocks(report) if style == "management" else build_report_blocks(report)
            block_kinds = [b.get("kind") for b in blocks]
            pdf_bytes = ep.PDFExporter.generate_pdf_report(report)
            ppt_bytes = eppt.PPTXExporter.generate_ppt_report(report)
            dash_sizes = [len(b.get("columns") or []) for b in blocks if b.get("kind") in _DASHBOARD_PAGE_KINDS]
            expected_sizes = _expected_column_sizes(sum(dash_sizes))
            if dash_sizes and sorted(dash_sizes, reverse=True) != expected_sizes:
                failures.append(
                    f"report {rid} pembagian kolom {sorted(dash_sizes, reverse=True)} "
                    f"!= seharusnya {expected_sizes} utk {sum(dash_sizes)} topik"
                )
            table_pages = {
                idx for idx, b in enumerate(blocks)
                if any((p or {}).get("panel_kind") == "critical_table" for p in (b.get("panels") or []))
            }
            for i, kind, n_el, n_ch in _pdf_page_density(pdf_bytes, block_kinds, table_pages):
                if kind in _DASHBOARD_PAGE_KINDS:
                    n_cols = len(blocks[i].get("columns") or []) if i < len(blocks) else 3
                    ambang = _DENSITY_DASHBOARD_MIN_PER_COLUMN * max(1, n_cols)
                    if n_el < ambang:
                        failures.append(
                            f"report {rid} PDF page {i} (dasbor {n_cols} kolom): {n_el} elemen "
                            f"(< {ambang}), {n_ch} karakter"
                        )
                    continue
                if kind in _NARRATIVE_PAGE_KINDS:
                    if n_ch < _DENSITY_NARRATIVE_MIN_CHARS:
                        failures.append(
                            f"report {rid} PDF page {i} (naratif): {n_ch} karakter "
                            f"(< {_DENSITY_NARRATIVE_MIN_CHARS}), {n_el} elemen"
                        )
                    continue
                if kind in _DENSITY_EXCLUDE_KINDS or n_el >= _DENSITY_MIN_ELEMENTS or n_ch >= _DENSITY_MIN_CHARS:
                    continue
                if n_el >= _DENSITY_ABSOLUTE_MIN_ELEMENTS and i < len(blocks) and _page_is_chart_exempt(blocks[i]):
                    exemptions.append(f"report {rid} PDF page {i} ({kind}): {n_el} elemen, {n_ch} karakter - pengecualian sah (<{_CHART_EXEMPTION_MAX_CATEGORIES} kategori + py catatan)")
                    continue
                failures.append(f"report {rid} PDF page {i} ({kind}): {n_el} elemen, {n_ch} karakter")
            for i, kind, n_el, n_ch in _ppt_page_density(ppt_bytes, block_kinds):
                if kind in _NARRATIVE_PAGE_KINDS:
                    if n_ch < _DENSITY_NARRATIVE_MIN_CHARS:
                        failures.append(
                            f"report {rid} PPT slide {i} (naratif): {n_ch} karakter "
                            f"(< {_DENSITY_NARRATIVE_MIN_CHARS}), {n_el} elemen"
                        )
                    continue
                if kind in _DENSITY_EXCLUDE_KINDS or n_el >= _DENSITY_MIN_ELEMENTS or n_ch >= _DENSITY_MIN_CHARS:
                    continue
                if n_el >= _DENSITY_ABSOLUTE_MIN_ELEMENTS and i < len(blocks) and _page_is_chart_exempt(blocks[i]):
                    exemptions.append(f"report {rid} PPT slide {i} ({kind}): {n_el} elemen, {n_ch} karakter - pengecualian sah (<{_CHART_EXEMPTION_MAX_CATEGORIES} kategori + py catatan)")
                    continue
                failures.append(f"report {rid} PPT slide {i} ({kind}): {n_el} elemen, {n_ch} karakter")
    finally:
        db.rollback()
        db.close()
    if exemptions:
        print("Pengecualian kepadatan sah (chart kategori sedikit + py catatan):\n" + "\n".join(exemptions))
    assert not failures, (
        f"Halaman kurang dari {_DENSITY_MIN_ELEMENTS} elemen DAN kurang dari "
        f"{_DENSITY_MIN_CHARS} karakter (bukan pengecualian sah):\n" + "\n".join(failures)
    )


def test_insight_pages_are_not_duplicated_by_entity_set():
    """PERMINTAAN USER (temuan langsung dari audit: 6 halaman "management_insight_page" topik
    BERBEDA ternyata menampilkan 8 entitas yang PERSIS SAMA, cuma disusun ulang beda urutan/
    metrik - "itu bukan kepadatan, itu pengulangan yang kebetulan menghasilkan angka elemen
    tinggi"). _merge_overlapping_insight_pages (report_render_logic.py) SEHARUSNYA sudah
    menggabung halaman semacam itu jadi satu SEBELUM sampai ke tes ini - tes ini jadi
    JARING PENGAMAN REGRESI: gagalkan kalau ADA DUA halaman insight (dlm 1 laporan) yang
    himpunan entitasnya masih beririsan >=70% (_INSIGHT_PAGE_OVERLAP_THRESHOLD) - jumlah
    elemen yang tinggi TIDAK BOLEH dicapai lewat pengulangan kartu yang sama."""
    db = SessionLocal()
    failures = []
    try:
        report_ids = _sample_report_ids("management", 15)
        for rid in report_ids:
            report = db.get(Report, rid)
            if report is None:
                continue
            blocks = build_management_report_blocks(report)
            insight_pages = [b for b in blocks if b.get("kind") == "management_insight_page"]
            if len(insight_pages) < 2:
                continue
            entity_sets = [(p.get("title"), _insight_page_entity_set(p)) for p in insight_pages]
            for i in range(len(entity_sets)):
                for j in range(i + 1, len(entity_sets)):
                    title_a, set_a = entity_sets[i]
                    title_b, set_b = entity_sets[j]
                    overlap = _entity_set_overlap(set_a, set_b)
                    if overlap >= _INSIGHT_PAGE_OVERLAP_THRESHOLD:
                        failures.append(
                            f"report {rid}: halaman '{(title_a or '')[:40]}' vs "
                            f"'{(title_b or '')[:40]}' beririsan entitas {overlap * 100:.0f}% "
                            f"(>= {_INSIGHT_PAGE_OVERLAP_THRESHOLD * 100:.0f}%) - seharusnya "
                            "sudah digabung _merge_overlapping_insight_pages"
                        )
    finally:
        db.rollback()
        db.close()
    assert not failures, "Halaman insight duplikat (himpunan entitas sama) belum digabung:\n" + "\n".join(failures)


def _walk_numbers(obj):
    """Jalan rekursif ke seluruh dict/list bersarang, kumpulkan tiap nilai int/float yang
    ditemukan — dipakai test di bawah utk mencari angka "racun" di MANA PUN dlm hasil block
    plan, tanpa perlu tahu persis lewat jalur mana (tile dashboard biasa ATAU kartu halaman
    insight — keduanya jalur yang sah, block plan bisa memilih salah satu tergantung datanya
    "kaya" atau tidak, lihat _is_rich_insight_page)."""
    found = []
    if isinstance(obj, dict):
        for v in obj.values():
            found.extend(_walk_numbers(v))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            found.extend(_walk_numbers(v))
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        found.append(obj)
    return found


def test_custom_topic_chart_values_come_from_pandas_not_ai():
    """PERMINTAAN USER: chart section custom AI (tile_kind="custom_topic") TIDAK BOLEH lagi
    mengambil angka dari teks yang ditulis AI sendiri - HARUS langsung dari agregasi pandas
    (report_stats["category_numeric_breakdown"], lihat data_profiler.py
    ::_compute_category_numeric_breakdown & report_render_logic.py::_find_breakdown_entry).
    Bug NYATA yang memotivasi perubahan ini (dibuktikan lewat generate ulang sungguhan, laporan
    "Authentication Failure Trend"): AI menuliskan sendiri array "values" & kadang menukar
    nilai MAKSIMUM/RATA-RATA satu kolom ke slot per-bucket yang salah - angkanya ASLI, cuma
    tertukar slot, jadi tidak cukup dites via "apakah angkanya kelihatan masuk akal", HARUS
    dibandingkan PERSIS dgn hasil hitung ulang pandas scr independen.

    Dites dgn menyuntikkan SATU section palsu yang py("chart_source") MENUNJUK entri breakdown
    ASLI, BERDAMPINGAN dgn field "chart" gaya LAMA berisi angka "racun" (999999...) yang SENGAJA
    salah - kalau HASIL block plan (di MANA PUN — tile dashboard biasa, atau kartu halaman
    insight kalau datanya kebetulan "kaya", lihat _is_rich_insight_page) ternyata memuat 999999,
    berarti kode masih (sebagian) mempercayai angka tulisan AI drpd cuma menunjuk nama kolom.
    Dicek scr REKURSIF (_walk_numbers) drpd mengasumsikan 1 struktur tile tetap — supaya tes
    ini tidak rapuh thd jalur mana yang dipilih block plan utk data spesifik yang kebetulan
    ditarik _sample_report_ids. Murni verifikasi kode (tidak memanggil AI sama sekali - >15
    menit di mesin CPU-only), jadi bisa dijalankan berulang kali dgn cepat kapan pun ada
    perubahan di jalur ini."""
    from app.crud.report import get_parsed_data
    from app.services.ai_engine.data_profiler import compute_statistics

    db = SessionLocal()
    checked = 0
    try:
        report_ids = _sample_report_ids("management", 15)
        for rid in report_ids:
            if checked >= 3:
                break
            report = db.get(Report, rid)
            if report is None:
                continue
            pdata = get_parsed_data(report)
            if not pdata:
                continue
            fresh_stats = compute_statistics(pdata, report.data_type)
            breakdown = fresh_stats.get("category_numeric_breakdown") or []
            entry = next((e for e in breakdown if len(e["items"]) >= 3), None)
            if not entry:
                continue
            checked += 1

            poisoned_values = [999999.0] * len(entry["items"])
            original_ai_summary = report.ai_summary or {}
            report.ai_summary = {
                **original_ai_summary,
                "sections": [{
                    "id": "__test_injected__",
                    "title": "__Test Injected Topic__",
                    "content": "Kalimat uji - diabaikan tes ini.",
                    "chart_source": {"numeric_col": entry["numeric_col"], "category_col": entry["category_col"]},
                    "chart": {"labels": [it["label"] for it in entry["items"]], "values": poisoned_values},
                }],
            }
            try:
                blocks = build_management_report_blocks(report)
            finally:
                report.ai_summary = original_ai_summary  # jangan biarkan suntikan nyangkut di object session

            all_numbers = _walk_numbers(blocks)
            assert 999999.0 not in all_numbers, (
                f"report {rid}: block plan masih memuat angka 'racun' dari field 'chart' gaya "
                "lama - berarti chart_source belum benar2 diprioritaskan di atas format lama"
            )
            first_real_value = entry["items"][0]["value"]
            assert first_real_value in all_numbers, (
                f"report {rid}: nilai asli pertama ({first_real_value}) dari agregasi pandas "
                "tidak ditemukan di block plan sama sekali - data hasil injeksi malah hilang "
                "total, bukan cuma salah sumber"
            )
        assert checked > 0, "tidak ada laporan management dgn category_numeric_breakdown utk diuji"
    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"[PASS] {name}")
        except AssertionError as e:
            failed += 1
            print(f"[FAIL] {name}\n{e}")
    sys.exit(1 if failed else 0)


# Pola angka BERKELOMPOK RIBUAN dgn konvensi masing-masing bahasa. Dicek dari TEKS HASIL
# RENDER (bukan block plan) supaya yang diuji genuinely yang DIBACA pembaca - nilai internal
# (mis. `frac` 0.666 utk lebar bar) tidak pernah ikut terbaca di sini.
_EN_GROUPED_RE = re.compile(r"\d,\d{3}(?!\d)")   # 2,675 -> gaya Inggris
_ID_GROUPED_RE = re.compile(r"\d\.\d{3}(?!\d)")   # 2.675 -> gaya Indonesia


def test_number_format_follows_report_language():
    """PERMINTAAN USER (setelah menemukan "Rp 2,300,000,000" di laporan Indonesia): pemisah
    ribuan HARUS mengikuti BAHASA LAPORAN - Indonesia titik-ribuan/koma-desimal, Inggris
    koma-ribuan/titik-desimal. Bukan soal selera: pembaca Indonesia membaca "2,675" sebagai
    "dua koma enam tujuh lima", jadi angkanya SALAH DIBACA.

    Diuji dari TEKS PDF HASIL RENDER (bukan pemeriksaan manual & bukan block plan) - persis
    krn kesalahan pelaporan manual sebelumnya membuktikan angka salah-baca gampang terlewat."""
    db = SessionLocal()
    problems = []
    try:
        for lang, wrong_re, label in (
            ("Indonesian", _EN_GROUPED_RE, "gaya Inggris (koma ribuan)"),
            ("English", _ID_GROUPED_RE, "gaya Indonesia (titik ribuan)"),
        ):
            rows = (
                db.query(Report.id)
                .filter(Report.language == lang, Report.ai_summary.isnot(None))
                .order_by(Report.id.desc())
                .limit(3)
                .all()
            )
            for (rid,) in rows:
                report = db.get(Report, rid)
                if report is None:
                    continue
                pdf_bytes = ep.PDFExporter.generate_pdf_report(report)
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                try:
                    for pno in range(len(doc)):
                        text = doc[pno].get_text()
                        for m in wrong_re.finditer(text):
                            snippet = _normalize_ws(text[max(0, m.start() - 25):m.end() + 15])
                            problems.append(
                                f"report {rid} ({lang}) hal {pno + 1}: '{m.group()}' {label} -> ...{snippet}..."
                            )
                finally:
                    doc.close()
    finally:
        db.rollback()
        db.close()
    assert not problems, (
        "Angka berformat SALAH BACA utk bahasa laporannya:\n" + "\n".join(problems[:25])
    )


def test_text_splitters_do_not_corrupt_legitimate_sentences():
    """PERMINTAAN USER (setelah 3 bug pemotongan teks ditemukan & direproduksi): memindai
    laporan yang KEBETULAN bersih TIDAK membuktikan apa pun - kerusakannya bergantung pemicu.
    Tes ini memasukkan teks yang MENGANDUNG ketiga pemicu itu ke pemroses yang sebenarnya,
    lalu memastikan hasilnya UTUH: tidak tersambung salah, tidak terbelah, dan TIDAK DIBUANG.

    Ketiga pemicu (semuanya bug sisi KODE, bukan tulisan AI):
      1. angka berkurung di tengah kalimat  -> " 42) " dimakan pembuang penomoran
      2. rentang jam berakhiran ".00"       -> " 00. " dianggap penanda daftar
      3. singkatan berakhiran titik          -> "vs." dianggap akhir kalimat
    """
    from app.services.ai_engine.ollama_client import (
        _clean_recommendation_text, _split_multi_action_string,
    )

    utuh_kurung = (
        "Analisis penyebab pembatalan kontrak (15 dari 42) untuk mengidentifikasi masalah "
        "dalam proses pengadaan."
    )
    utuh_jam = "Aktivitas terfokus pada jam 00:00 hingga 02:00. Ini akan membantu tim memantau beban."
    utuh_singkatan = "Legal Requests are 835 vs. Illegal Requests of 107 for this asset."

    problems = []

    # 1. Pembersih rekomendasi tidak boleh mengubah kalimat sah sama sekali.
    for teks in (utuh_kurung, utuh_singkatan):
        hasil = _clean_recommendation_text(teks)
        if hasil != teks:
            problems.append(f"_clean_recommendation_text mengubah kalimat sah: IN={teks!r} OUT={hasil!r}")
        if not hasil:
            problems.append(f"_clean_recommendation_text MEMBUANG kalimat sah: {teks}")

    # 2. Pemecah tindakan tidak boleh memecah/menyambung kalimat sah.
    if _split_multi_action_string(utuh_kurung) != [utuh_kurung]:
        problems.append(f"_split_multi_action_string memecah kalimat berkurung angka: {_split_multi_action_string(utuh_kurung)}")
    if _split_multi_action_string(utuh_singkatan) != [utuh_singkatan]:
        problems.append(f"_split_multi_action_string memecah di singkatan: {_split_multi_action_string(utuh_singkatan)}")
    jam_parts = _split_multi_action_string(utuh_jam)
    if any(p.rstrip().endswith(":") or p.rstrip().endswith("02:") for p in jam_parts):
        problems.append(f"_split_multi_action_string memotong rentang jam: {jam_parts}")
    if "00:00 hingga 02:00." not in " ".join(jam_parts):
        problems.append(f"rentang jam rusak setelah dipecah: {jam_parts}")

    # 3. Perilaku yang MEMANG diinginkan harus tetap jalan (bukan sekadar mematikan pemisah).
    daftar = "1) Audit vendor utama. 2) Perbaiki proses pembatalan. 3) Distribusikan kontrak."
    if len(_split_multi_action_string(daftar)) != 3:
        problems.append(f"daftar bernomor asli tidak lagi terpecah benar: {_split_multi_action_string(daftar)}")
    if _clean_recommendation_text("1) Audit vendor utama.") != "Audit vendor utama.":
        problems.append("penomoran di AWAL teks tidak lagi dibuang")

    assert not problems, "Pemotong teks merusak kalimat sah:\n" + "\n".join(problems)


def test_dashboard_titles_are_not_clipped_by_content_below():
    """REGRESI DIPERBAIKI (dilaporkan user dari pemeriksaan cetak): kotak judul dipatok
    setinggi 1 BARIS sementara teksnya wrap jadi 2 - baris kedua terpotong separuh, TANPA
    penanda apa pun (bukan "..."), jadi pembaca kehilangan teks tanpa tahu. Batas karakter di
    prompt saja TIDAK cukup: judul 59 karakter pun terbukti wrap.

    Yang memotong adalah kotak judulnya SENDIRI (tinggi tetap + overflow:hidden), BUKAN kartu
    KPI di bawahnya - jadi yang diuji: tinggi kotak yang DIPESAN harus cukup menampung tinggi
    teks yang BENAR-BENAR digambar WeasyPrint. (Versi pertama tes ini membandingkan judul vs
    posisi kartu KPI dan TERBUKTI tidak menangkap bug-nya saat diuji-mutasi - diganti.)"""
    from app.services.report_render_logic import _DASH_MARGIN_X_IN

    db = SessionLocal()
    problems = []
    total_w_in = 13.333 - 2 * _DASH_MARGIN_X_IN
    try:
        for rid in _sample_report_ids("management", 4):
            report = db.get(Report, rid)
            if report is None:
                continue
            blocks = build_management_report_blocks(report)
            pdf_bytes = ep.PDFExporter.generate_pdf_report(report)
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            try:
                for i, block in enumerate(blocks):
                    if block.get("kind") != "management_insight_page" or i >= len(doc):
                        continue
                    title = block.get("title") or ""
                    if not title.strip():
                        continue
                    _, box_h_in = ep._dashboard_title_html(title, total_w_in)
                    text_blocks = [b for b in doc[i].get_text("blocks") if b[4].strip()]
                    if not text_blocks:
                        continue
                    tb = min(text_blocks, key=lambda b: b[1])
                    drawn_h_in = (tb[3] - tb[1]) / 72
                    if drawn_h_in > box_h_in + 0.06:
                        problems.append(
                            f"report {rid} hal {i + 1}: teks judul setinggi {drawn_h_in:.2f}in "
                            f"TAPI kotaknya cuma {box_h_in:.2f}in (terpotong) - "
                            f"{_normalize_ws(tb[4])[:60]!r}"
                        )
            finally:
                doc.close()
    finally:
        db.rollback()
        db.close()
    assert not problems, "Judul terpotong oleh kotaknya sendiri:\n" + "\n".join(problems[:15])


def test_single_entity_gauge_pages_do_not_duplicate_other_pages():
    """PERMINTAAN USER (hal.05 mengulang hal.01 di laporan cetak): halaman gauge entitas-tunggal
    ("E-Katalog mendominasi dengan 38% dari total") memakai SATU halaman penuh utk angka yang
    SUDAH tampil di halaman lain. Pemeriksa irisan entitas lama tidak mencakupnya - halaman
    gauge tidak punya category_details, jadi himpunan entitasnya kosong & Jaccard selalu 0.

    Diperiksa dari block plan: tidak boleh ada halaman gauge yang entitasnya SUDAH muncul sbg
    kartu di halaman insight lain. Catatannya wajib ikut pindah (tidak boleh ada isi hilang)."""
    db = SessionLocal()
    problems = []
    try:
        for rid in _sample_report_ids("management", 6):
            report = db.get(Report, rid)
            if report is None:
                continue
            blocks = build_management_report_blocks(report)
            insight = [b for b in blocks if b.get("kind") == "management_insight_page"]
            for page in insight:
                ent = page.get("gauge_entity")
                if not ent or page.get("category_details"):
                    continue
                for other in insight:
                    if other is page:
                        continue
                    if ent in _insight_page_entity_set(other):
                        problems.append(
                            f"report {rid}: halaman gauge {ent!r} mengulang entitas yang sudah "
                            f"tampil di halaman {(other.get('title') or '')[:50]!r}"
                        )
                        break
    finally:
        db.rollback()
        db.close()
    assert not problems, "Halaman gauge mengulang halaman lain:\n" + "\n".join(problems[:15])
