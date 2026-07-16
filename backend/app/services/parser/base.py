from abc import ABC, abstractmethod
from typing import List, Dict, Any, BinaryIO

class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_content: BinaryIO) -> List[Dict[str, Any]]:
        """
        Menerima file binary stream dan mengembalikan list dictionary
        dengan format seragam/terstruktur.
        """
        pass
