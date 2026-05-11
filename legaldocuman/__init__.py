"""
LegalDocuMan - Document Processing Suite v2.0
Refactored with pluggable OCR backends and no import-time side effects.
"""

__version__ = "2.1.0"

from .config import Config
from .extractors import TextExtractor
from .classifiers import DocumentTypeClassifier, DocumentStatusClassifier
from .dates import DateExtractor
from .vendors import VendorExtractor
from .processor import DocumentProcessor

__all__ = [
    "Config",
    "TextExtractor",
    "DocumentTypeClassifier",
    "DocumentStatusClassifier",
    "DateExtractor",
    "VendorExtractor",
    "DocumentProcessor",
]
