import json
from typing import List, Dict, Any, BinaryIO
from app.services.parser.base import BaseParser

class JSONParser(BaseParser):
    def parse(self, file_content: BinaryIO) -> List[Dict[str, Any]]:
        file_content.seek(0)
        # Parse data JSON dari byte stream
        data = json.loads(file_content.read().decode('utf-8'))
        
        # Standarisasi output menjadi list of dicts
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
        else:
            raise ValueError("Struktur data JSON tidak didukung. Harus berupa Array atau Object.")
