# backend/app/services/parser/factory.py
import os
from typing import Dict
from app.services.parser.base import BaseParser
from app.services.parser.csv_parser import CSVParser
from app.services.parser.excel_parser import ExcelParser
from app.services.parser.json_parser import JSONParser
from app.services.parser.pdf_parser import PDFParser


class ParserFactory:
    _parsers: Dict[str, BaseParser] = {
        ".csv": CSVParser(),
        ".json": JSONParser(),
        ".xlsx": ExcelParser(),
        ".xls": ExcelParser(),
        ".pdf": PDFParser()
    }

    @classmethod
    def get_parser(cls, filename: str) -> BaseParser:
        _, ext = os.path.splitext(filename.lower())
        if ext in cls._parsers:
            return cls._parsers[ext]
        raise ValueError(f"Format file '{ext}' tidak didukung. Harap gunakan file .csv, .json, .xlsx/.xls, atau .pdf.")