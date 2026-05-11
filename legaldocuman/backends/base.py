"""Abstract base class for OCR backends."""
from abc import ABC, abstractmethod
from typing import List, Optional


class OCRBackend(ABC):
    """Pluggable OCR backend interface.

    Implementations must provide:
      - image_to_text(image) → str
      - pdf_to_text(file_path, first_page, last_page) → str
      - is_available() → bool
    """

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this backend is installed and ready."""
        ...

    @abstractmethod
    def image_to_text(self, image) -> str:
        """Run OCR on a single PIL Image and return extracted text."""
        ...

    @abstractmethod
    def pdf_to_text(self, file_path: str, first_page: int = 1, last_page: Optional[int] = None) -> str:
        """Convert PDF pages to images and OCR them. Return concatenated text."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable backend name."""
        ...
