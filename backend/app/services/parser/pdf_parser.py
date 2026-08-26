import re
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, cast
import numpy as np
import pandas as pd
from app.services.parser.base import BaseParser
from app.services.period_detector import find_date_column, _parse_dates

# Dipakai _row_looks_like_data() — cocok untuk angka polos ("594"), desimal ("3.5"/"3,5"),
# dan persentase ("42%"). Sengaja SEDERHANA (bukan validasi angka penuh) karena cuma dipakai
# sbg heuristik "baris ini lebih mirip data atau header", bukan sumber kebenaran kritis.
_NUMERIC_CELL_RE = re.compile(r"^-?\d+([.,]\d+)?%?$")

# Dipakai _extract_period_hint() — token tanggal ISO ("2026-07-13") ATAU D/M/Y umum
# ("13/07/2026"), keduanya boleh diikuti jam opsional. Dicocokkan dlm pola "From ... To ..."
# (case-insensitive, boleh beda baris — lihat DOTALL) yang UMUM dipakai laporan
# traffic/log security (mis. email gateway) sbg keterangan rentang waktu laporan, letaknya
# TERPISAH dari tabel datanya sendiri (makanya tidak pernah ikut kebaca sbg kolom tabel).
_DATE_TOKEN = (
    r"\d{4}-\d{1,2}-\d{1,2}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?"
    r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?"
)
_PERIOD_TEXT_RE = re.compile(
    r"from\s*[:\-]?\s*(?P<start>" + _DATE_TOKEN + r")\b.{0,80}?\bto\s*[:\-]?\s*(?P<end>" + _DATE_TOKEN + r")\b",
    re.IGNORECASE | re.DOTALL,
)

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    pdfplumber = None
    PDFPLUMBER_AVAILABLE = False


class PDFParser(BaseParser):
    """
    Ekstraksi tabel dari PDF pakai pdfplumber (pure-Python, tidak butuh dependency eksternal
    seperti Java/Ghostscript yang dibutuhkan camelot/tabula — penting karena target deploy
    termasuk Windows lokal).

    Asumsi: baris pertama dari tabel pertama yang ditemukan di seluruh PDF adalah header
    kolom. Tabel bisa mencakup banyak baris dan lebih dari satu halaman — semua digabung
    jadi satu list. Baris di halaman/tabel manapun yang identik dengan header dilewati
    sebagai header yang berulang (umum terjadi kalau tabel di-export/print lebih dari
    1 halaman, mis. hasil export Google Sheets).

    Kolom yang SELURUH nilainya berhasil diparse sebagai angka dikonversi ke tipe numerik
    (lihat _coerce_numeric_columns), SUPAYA KONSISTEN dengan pd.read_csv/pd.read_excel yang
    dipakai CSVParser/ExcelParser — keduanya otomatis mendeteksi kolom angka bawaan pandas.
    pdfplumber selalu mengembalikan teks mentah tanpa pengecualian, jadi tanpa langkah ini
    kolom seperti "Inbound_Mbps"/"Outbound_Mbps" tetap jadi string, ChartGenerator gagal
    mendeteksi kolom numerik sama sekali, dan chart jatuh ke fallback "hitung jumlah baris
    per tanggal" (selalu flat di nilai 1, karena tiap baris punya timestamp unik) alih-alih
    tren nilai yang sesungguhnya. Kolom persentase (mis. "42%") sengaja TETAP string karena
    simbol "%"-nya bikin parse angka gagal — sama seperti pandas juga tidak otomatis
    menghilangkan "%" dari kolom CSV/Excel bertipe teks.

    `detected_period_hint` (diisi SETELAH parse() dipanggil, opsional dibaca pemanggil yang
    butuh — lihat upload.py::_parse_uploaded_file_for_preview) — BUG DIPERBAIKI (dilaporkan
    user, laporan traffic email PDF-nya PUNYA keterangan rentang tanggal "From ... To ..."
    tapi teks itu di LUAR tabel, jadi period_start/period_end laporan tidak pernah otomatis
    terisi dari file spt ini, harus diisi manual terus). Diisi HANYA kalau (1) tabel yang
    berhasil diekstrak SAMA SEKALI tidak punya kolom tanggal yang genuinely valid, DAN (2)
    ditemukan pola "From <tanggal> ... To <tanggal>" di teks bebas PDF-nya (lihat
    _extract_period_hint) — supaya /detect-period tetap bisa mengisi Report Period otomatis
    utk jenis file ini juga, bukan selalu kosong."""

    detected_period_hint: Optional[Tuple[str, str]] = None

    @staticmethod
    def _extract_period_hint(full_text: str) -> Optional[Tuple[str, str]]:
        match = _PERIOD_TEXT_RE.search(full_text or "")
        if not match:
            return None
        start_parsed = _parse_dates([match.group("start")]).iloc[0]
        end_parsed = _parse_dates([match.group("end")]).iloc[0]
        if pd.isna(start_parsed) or pd.isna(end_parsed):
            return None
        return start_parsed.strftime("%Y-%m-%d"), end_parsed.strftime("%Y-%m-%d")

    @staticmethod
    def _row_looks_like_data(cells: List[str]) -> bool:
        """Heuristik "baris ini lebih mirip DATA atau HEADER" — dipakai KHUSUS saat baris
        pertama sebuah tabel (hasil find_tables()) TERNYATA bukan header genuine, melainkan
        lanjutan data dari tabel sebelumnya yang terpotong ke halaman baru TANPA header
        berulang (beda dari kasus umum yang SUDAH ditangani, header berulang persis). Header
        asli hampir selalu berisi label teks; baris data mayoritas berisi angka polos. Kalau
        LEBIH DARI SETENGAH sel non-kosong terlihat seperti angka, baris ini dianggap data,
        BUKAN header baru."""
        non_empty = [c for c in cells if c]
        if not non_empty:
            return False
        numeric_like = sum(1 for c in non_empty if _NUMERIC_CELL_RE.match(c))
        return numeric_like > len(non_empty) / 2

    @staticmethod
    def _coerce_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
        for col in df.columns:
            original_null_count = df[col].isna().sum()
            coerced = pd.to_numeric(df[col], errors="coerce")
            # Cuma dikonversi kalau SEMUA nilai non-kosong berhasil diparse jadi angka —
            # kalau ada satu saja nilai teks asli (bukan kosong) yang gagal, coerced.isna()
            # akan lebih besar dari original_null_count, jadi kolom dibiarkan apa adanya.
            if coerced.notna().sum() > 0 and coerced.isna().sum() == original_null_count:
                df[col] = coerced
        return df

    @staticmethod
    def _extract_borderless_rows(pdf: Any) -> List[List[str]]:
        """
        Fallback KHUSUS untuk PDF tabel tanpa garis (borderless) — dipanggil HANYA kalau
        page.extract_tables() (strategi garis, metode utama) sama sekali tidak menemukan
        tabel di seluruh dokumen.

        pdfplumber/pymupdf strategi "text" bawaan mendeteksi kolom dari CELAH SPASI antar
        kata — terbukti gagal (diuji langsung ke PDF hasil reproduksi kasus nyata) kalau satu
        sel berisi beberapa kata (mis. "03/01/2025 12:00" atau "Departemen Pemeliharaan III"):
        kata keduanya malah dianggap kolom baru sendiri karena celahnya kebetulan lebih lebar
        dari celah ke kolom sungguhan berikutnya.

        Solusi di sini: pakai posisi X kata-kata di BARIS HEADER (baris pertama halaman
        pertama yang punya teks) sebagai batas kiri tiap kolom — bukan celah spasi. Kolom ke-i
        dianggap mencakup rentang [x0 header kolom ke-i, x0 header kolom ke-(i+1)), jadi kata
        apapun pada baris data yang x0-nya jatuh di rentang itu digabung jadi satu sel, tidak
        peduli berapa banyak kata di dalamnya. Diuji terhadap reproduksi PDF Realisasi Anggaran
        milik user (borderless) — hasilnya benar persis, semua sel multi-kata tergabung utuh.

        Batas antar kolom dihitung SEKALI dari header, dipakai konsisten ke SEMUA halaman
        (asumsi: satu tabel dengan tata letak kolom yang sama across halaman) — supaya halaman
        lanjutan yang headernya tidak berulang tetap konsisten posisinya.
        """
        boundaries: Optional[List[float]] = None
        ncols = 0
        out_rows: List[List[str]] = []

        for page in pdf.pages:
            words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            if not words:
                continue

            # Kelompokkan kata jadi baris berdasarkan posisi vertikal ('top') yang berdekatan.
            rows: List[List[dict]] = []
            for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
                if rows and abs(w["top"] - rows[-1][0]["top"]) <= 3.0:
                    rows[-1].append(w)
                else:
                    rows.append([w])

            for row_words in rows:
                row_words = sorted(row_words, key=lambda w: w["x0"])
                if boundaries is None:
                    # Baris pertama yang ditemukan (halaman pertama) dianggap header —
                    # tentukan batas kolom dari sini, dipakai konsisten seterusnya.
                    header_x0 = [w["x0"] for w in row_words]
                    ncols = len(header_x0)
                    boundaries = (
                        [header_x0[0] - 1e6]
                        + [x - 2.0 for x in header_x0[1:]]
                        + [1e9]
                    )
                    out_rows.append([w["text"] for w in row_words])
                    continue

                cells: List[List[str]] = [[] for _ in range(ncols)]
                for w in row_words:
                    col_idx = ncols - 1
                    for i in range(ncols):
                        if boundaries[i] <= w["x0"] < boundaries[i + 1]:
                            col_idx = i
                            break
                    cells[col_idx].append(w["text"])
                out_rows.append([" ".join(c) for c in cells])

        return out_rows

    def parse(self, file_content: BinaryIO) -> List[Dict[str, Any]]:
        if not PDFPLUMBER_AVAILABLE or pdfplumber is None:
            raise ValueError(
                "Modul 'pdfplumber' belum terinstal di lingkungan virtualenv Python backend. "
                "Silakan jalankan 'pip install pdfplumber' atau 'pip install -r requirements.txt'."
            )

        file_content.seek(0)
        rows: List[Dict[str, Any]] = []

        def _clean_cell(c: Any) -> str:
            return "" if c is None else str(c).strip()

        try:
            with pdfplumber.open(cast(Any, file_content)) as pdf:
                # BUG DIPERBAIKI (dilaporkan user, PDF laporan traffic email berisi 2 tabel
                # SEKALIGUS dgn struktur kolom BERBEDA — "Outbound Traffic" & "Inbound
                # Traffic"): versi lama menggabungkan SEMUA tabel di file pakai HEADER TABEL
                # PERTAMA yang ditemukan (extract_tables() dirata begitu saja) — tabel kedua
                # (kolom beda, mis. "Blocked: Bad Recipient" bukan "Blocked: Policy") ikut
                # "dipaksa" masuk ke kolom tabel pertama scr POSISI, datanya nyasar total
                # (dibuktikan lewat reproduksi: nilai "Total Received" tabel kedua malah
                # tersimpan sbg "Redirected"). Sekarang tiap tabel dibaca via find_tables()
                # (bukan extract_tables()) supaya BATAS tiap tabel & posisinya di halaman
                # (bbox) diketahui — struktur kolom yang BERBEDA dikenali sbg "grup" terpisah
                # (dicocokkan by HEADER PERSIS SAMA, bukan cuma tabel pertama), grup dgn
                # header identik (kasus umum: tabel yang sama diekspor lebih dari 1 halaman)
                # tetap digabung seperti sebelumnya.
                groups: List[Dict[str, Any]] = []
                header_key_to_group: Dict[Tuple[str, ...], int] = {}

                for page in pdf.pages:
                    text_lines_cache: Optional[list] = None

                    def _nearest_heading_above(top_y: float) -> Optional[str]:
                        # Cari baris teks TEPAT DI ATAS tabel (jarak <=45pt) — pola umum
                        # laporan yang tiap tabelnya dikasih judul (mis. "Outbound Traffic")
                        # persis sebelum tabelnya sendiri. Dipakai SEBAGAI LABEL kolom
                        # "Section" kalau ternyata file ini punya >1 struktur tabel berbeda.
                        nonlocal text_lines_cache
                        if text_lines_cache is None:
                            text_lines_cache = page.extract_text_lines()
                        best_line, best_gap = None, None
                        for line in text_lines_cache:
                            gap = top_y - line["bottom"]
                            if 0 <= gap <= 45 and (best_gap is None or gap < best_gap):
                                best_gap, best_line = gap, line["text"].strip()
                        return best_line or None

                    try:
                        found_tables = page.find_tables()
                    except Exception:
                        found_tables = []

                    for table_obj in found_tables:
                        try:
                            raw_rows = table_obj.extract()
                        except Exception:
                            raw_rows = []
                        if not raw_rows:
                            continue

                        header_row_cells = [_clean_cell(c) for c in raw_rows[0]]
                        if not any(header_row_cells):
                            continue

                        # Baris pertama tabel ini TERLIHAT SEPERTI DATA (mayoritas angka),
                        # bukan header baru genuine — kemungkinan besar lanjutan tabel
                        # sebelumnya yang terpotong ke halaman baru TANPA header berulang.
                        # Gabung ke grup TERAKHIR (kalau jumlah kolomnya cocok) & JANGAN buang
                        # baris pertamanya (itu data sungguhan, bukan header).
                        group_idx: Optional[int] = None
                        data_start = 1
                        if groups and self._row_looks_like_data(header_row_cells):
                            last_idx = len(groups) - 1
                            if len(header_row_cells) == len(groups[last_idx]["header"]):
                                group_idx, data_start = last_idx, 0

                        if group_idx is None:
                            header_key = tuple(header_row_cells)
                            if header_key in header_key_to_group:
                                group_idx = header_key_to_group[header_key]
                            else:
                                this_header = [
                                    (c or f"column_{i + 1}") for i, c in enumerate(header_row_cells)
                                ]
                                # Label dicari utk SEMUA grup termasuk yang pertama (bukan
                                # cuma grup ke-2+) — waktu grup pertama diproses, belum tentu
                                # ketahuan bakal ada grup lain menyusul, jadi labelnya tetap
                                # disiapkan dari awal (baru DIPAKAI belakangan kalau ternyata
                                # len(groups) > 1, lihat di bawah).
                                section_label = _nearest_heading_above(table_obj.bbox[1])
                                groups.append({"header": this_header, "rows": [], "section_label": section_label})
                                group_idx = len(groups) - 1
                                header_key_to_group[header_key] = group_idx

                        header = groups[group_idx]["header"]
                        for raw_row in raw_rows[data_start:]:
                            if not any(_clean_cell(c) for c in raw_row):
                                continue  # baris kosong total, lewati
                            normalized_row = [_clean_cell(c) for c in raw_row]
                            if normalized_row == header:
                                continue  # header yang berulang di halaman/tabel berikutnya

                            row_dict: Dict[str, Any] = {}
                            for col_idx, col_name in enumerate(header):
                                value = raw_row[col_idx] if col_idx < len(raw_row) else None
                                row_dict[col_name] = value.strip() if isinstance(value, str) else value
                            groups[group_idx]["rows"].append(row_dict)

                if len(groups) == 1:
                    rows = groups[0]["rows"]
                elif len(groups) > 1:
                    # >1 struktur tabel berbeda genuinely ditemukan — gabung jadi 1 dataset,
                    # ditandai kolom "Section" (isinya judul tabel masing2, mis. "Outbound
                    # Traffic"/"Inbound Traffic") supaya (1) kolom yang beda antar tabel TIDAK
                    # tercampur/nyasar (baris dari tabel lain otomatis None utk kolom yang
                    # bukan miliknya, ditangani pd.DataFrame di bawah), (2) "Section" ini bisa
                    # langsung dipakai analisis/chart sbg kategori pembanding (mis. grafik
                    # inbound vs outbound per jam).
                    for g in groups:
                        label = g["section_label"] or "Table"
                        for row_dict in g["rows"]:
                            rows.append({"Section": label, **row_dict})

                # Metode utama (strategi garis) sama sekali tidak menemukan tabel — biasanya
                # PDF tabel BORDERLESS (tanpa garis vektor sungguhan, cuma teks berkolom rapi).
                # Coba fallback berbasis posisi kata, TAPI cuma diterima kalau hasilnya benar-
                # benar terlihat seperti tabel asli (lihat validasi di bawah) — supaya tidak
                # diam-diam menyimpan data yang salah tanpa disadari user.
                if not rows:
                    fallback_rows = self._extract_borderless_rows(pdf)
                    fb_header: Optional[List[str]] = None
                    for raw_row in fallback_rows:
                        if not any(_clean_cell(c) for c in raw_row):
                            continue
                        if fb_header is None:
                            fb_header = [
                                (_clean_cell(c) or f"column_{i + 1}")
                                for i, c in enumerate(raw_row)
                            ]
                            continue
                        normalized_row = [_clean_cell(c) for c in raw_row]
                        if normalized_row == fb_header:
                            continue
                        row_dict = {
                            col_name: (raw_row[col_idx].strip() if isinstance(raw_row[col_idx], str) else raw_row[col_idx])
                            for col_idx, col_name in enumerate(fb_header)
                            if col_idx < len(raw_row)
                        }
                        rows.append(row_dict)

                    # Validasi: tolak hasil fallback kalau terlihat tidak andal (kolom kurang
                    # dari 2, baris data kurang dari 2 — 1 baris kebetulan bisa cocok dengan
                    # teks naratif biasa yang bukan tabel sama sekali, atau mayoritas sel
                    # kosong yang menandakan batas kolom yang terdeteksi kemungkinan salah)
                    # daripada diam-diam menyimpan data yang berantakan.
                    if fb_header and len(fb_header) >= 2 and len(rows) >= 2:
                        total_cells = len(rows) * len(fb_header)
                        empty_cells = sum(
                            1 for r in rows for v in r.values() if not _clean_cell(v)
                        )
                        if total_cells == 0 or (empty_cells / total_cells) > 0.6:
                            rows = []
                    else:
                        rows = []

                # Fallback deteksi periode dari teks BEBAS (di luar tabel) — HANYA kalau tabel
                # yang berhasil diekstrak SAMA SEKALI tidak punya kolom tanggal yang valid
                # (lihat docstring detected_period_hint di atas). Dicek pakai find_date_column
                # yang SAMA PERSIS dipakai detect_period() supaya kriteria "valid"-nya
                # konsisten (termasuk penolakan kolom jam polos spt "Hour").
                self.detected_period_hint = None
                if rows:
                    try:
                        existing_date_col, _ = find_date_column(rows)
                    except Exception:
                        existing_date_col = None
                    if existing_date_col is None:
                        try:
                            full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
                            self.detected_period_hint = self._extract_period_hint(full_text)
                        except Exception:
                            self.detected_period_hint = None

        except ValueError:
            raise
        except Exception as e:
            raise ValueError(
                f"Gagal membaca berkas PDF: {str(e)}. Pastikan file tidak corrupt atau terenkripsi."
            )

        if not rows:
            raise ValueError(
                "Tidak ditemukan tabel yang bisa diekstrak dari PDF ini. "
                "Pastikan PDF berisi tabel data terstruktur, atau gunakan format CSV/XLSX sebagai alternatif."
            )

        df = pd.DataFrame(rows)
        df = self._coerce_numeric_columns(df)
        # Bersihkan NaN hasil coercion jadi None agar serialize ke JSON tidak error,
        # konsisten dengan pola yang sama di CSVParser/ExcelParser.
        records: List[Dict[str, Any]] = cast(
            List[Dict[str, Any]],
            df.astype(object).replace({np.nan: None}).to_dict(orient="records")
        )
        return records
