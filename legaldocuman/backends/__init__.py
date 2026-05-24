"""Pluggable OCR and signature-detection backends for LegalDocuMan."""
from .base import OCRBackend
from .tesseract import TesseractOCRBackend
from .nvidia import NvidiaOCRBackend
from .rfdetr_signature import SignatureDetectorBackend, RFDETRSignatureBackend

__all__ = [
    "OCRBackend",
    "TesseractOCRBackend",
    "NvidiaOCRBackend",
    "SignatureDetectorBackend",
    "RFDETRSignatureBackend",
]
