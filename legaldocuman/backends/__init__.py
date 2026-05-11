"""Pluggable OCR backends for LegalDocuMan."""
from .base import OCRBackend
from .tesseract import TesseractOCRBackend
from .nvidia import NvidiaOCRBackend

__all__ = ["OCRBackend", "TesseractOCRBackend", "NvidiaOCRBackend"]
