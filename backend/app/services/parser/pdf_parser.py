from typing import Any, BinaryIO, Dict, List, Optional, cast
import numpy as np
import pandas as pd
from app.services.parser.base import BaseParser

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
    """

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
        header: Optional[List[str]] = None
        rows: List[Dict[str, Any]] = []

        def _clean_cell(c: Any) -> str:
            return "" if c is None else str(c).strip()

        try:
            with pdfplumber.open(cast(Any, file_content)) as pdf:
                for page in pdf.pages:
                    for table in page.extract_tables():
                        for raw_row in table:
                            if not any(_clean_cell(cell) for cell in raw_row):
                                continue  # baris kosong total, lewati

                            if header is None:
                                header = [
                                    (_clean_cell(cell) or f"column_{i + 1}")
                                    for i, cell in enumerate(raw_row)
                                ]
                                continue

                            normalized_row = [_clean_cell(cell) for cell in raw_row]
                            if normalized_row == header:
                                continue  # header yang berulang di halaman/tabel berikutnya

                            row_dict: Dict[str, Any] = {}
                            for col_idx, col_name in enumerate(header):
                                value = raw_row[col_idx] if col_idx < len(raw_row) else None
                                row_dict[col_name] = value.strip() if isinstance(value, str) else value
                            rows.append(row_dict)

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
