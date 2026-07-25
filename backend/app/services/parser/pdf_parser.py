from typing import Any, BinaryIO, Dict, List, Optional
import pdfplumber
import pandas as pd
from app.services.parser.base import BaseParser


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

    def parse(self, file_content: BinaryIO) -> List[Dict[str, Any]]:
        file_content.seek(0)
        header: Optional[List[str]] = None
        rows: List[Dict[str, Any]] = []

        try:
            with pdfplumber.open(file_content) as pdf:
                for page in pdf.pages:
                    for table in page.extract_tables():
                        for raw_row in table:
                            if not any(cell is not None and str(cell).strip() for cell in raw_row):
                                continue  # baris kosong total, lewati

                            if header is None:
                                header = [
                                    (str(cell).strip() if cell is not None and str(cell).strip() else f"column_{i + 1}")
                                    for i, cell in enumerate(raw_row)
                                ]
                                continue

                            normalized_row = [str(cell).strip() if cell is not None else "" for cell in raw_row]
                            if normalized_row == header:
                                continue  # header yang berulang di halaman/tabel berikutnya

                            row_dict: Dict[str, Any] = {}
                            for col_idx, col_name in enumerate(header):
                                value = raw_row[col_idx] if col_idx < len(raw_row) else None
                                row_dict[col_name] = value.strip() if isinstance(value, str) else value
                            rows.append(row_dict)
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
        df = df.where(pd.notnull(df), None)
        return df.to_dict(orient="records")
