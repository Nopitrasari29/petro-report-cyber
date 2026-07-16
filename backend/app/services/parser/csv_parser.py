import pandas as pd
from typing import List, Dict, Any, BinaryIO
from app.services.parser.base import BaseParser
import io

class CSVParser(BaseParser):
    def parse(self, file_content: BinaryIO) -> List[Dict[str, Any]]:
        file_content.seek(0)
        # Gunakan io.BytesIO untuk membaca file stream binary
        df = pd.read_csv(io.BytesIO(file_content.read()))
        # Bersihkan data: ubah NaN/NaT menjadi None agar serialize ke JSON tidak error
        df = df.where(pd.notnull(df), None)
        return df.to_dict(orient="records")
