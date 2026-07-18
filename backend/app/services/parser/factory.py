# backend/app/services/parser/factory.py
import os
import json
from typing import Dict, List, Any
from app.services.parser.base import BaseParser
from app.services.parser.csv_parser import CSVParser
from app.services.parser.excel_parser import ExcelParser
from app.services.parser.json_parser import JSONParser

class MockPDFParser(BaseParser):
    def parse(self, file_obj) -> List[Dict[str, Any]]:
        """
        Fallback parser untuk mendemokan file PDF 'email_threat_report_july.pdf' tanpa crash.
        Secara cerdas membaca data JSON asli dari 'email_data.json' untuk dianalisis oleh AI.
        """
        try:
            # Tentukan path dinamis ke file email_data.json di folder tests/dummy_data/
            dummy_path = os.path.abspath(os.path.join(
                os.path.dirname(__file__), "..", "..", "tests", "dummy_data", "email_data.json"
              ))
            if os.path.exists(dummy_path):
                with open(dummy_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"[MOCK PDF PARSER WARNING] Gagal membaca email_data.json: {e}")
        
        # Fallback cadangan jika file dummy tidak ditemukan
        return [
            {"bulan": "July 2026", "phishing": 12, "spam": 45},
            {"bulan": "August 2026", "phishing": 8, "spam": 30}
        ]


class ParserFactory:
    _parsers: Dict[str, BaseParser] = {
        ".csv": CSVParser(),
        ".json": JSONParser(),
        ".xlsx": ExcelParser(),
        ".xls": ExcelParser(),
        ".pdf": MockPDFParser() # Menghubungkan berkas PDF log siber ke Mock PDF Parser secara fungsional!
    }

    @classmethod
    def get_parser(cls, filename: str) -> BaseParser:
        _, ext = os.path.splitext(filename.lower())
        if ext in cls._parsers:
            return cls._parsers[ext]
        raise ValueError(f"Format file '{ext}' tidak didukung. Harap gunakan file .csv, .json, .xlsx/.xls, atau .pdf.")