import pandas as pd
from typing import List, Dict, Any, BinaryIO
from app.services.parser.base import BaseParser
import io

class ExcelParser(BaseParser):
    def parse(self, file_content: BinaryIO) -> List[Dict[str, Any]]:
        file_content.seek(0)
        # Gunakan pandas dengan engine openpyxl untuk membaca data Excel
        df = pd.read_excel(io.BytesIO(file_content.read()), engine="openpyxl")
        # Ubah NaN ke None
        df = df.where(pd.notnull(df), None)
        return df.to_dict(orient="records")
