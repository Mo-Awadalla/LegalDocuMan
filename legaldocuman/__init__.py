"""
LegalDocuMan - Document Processing Suite v2.1.0
Refactored with pluggable OCR backends and no import-time side effects.
"""

__version__ = "2.1.0"

from .classifiers import DocumentStatusClassifier, DocumentTypeClassifier
from .config import Config
from .dates import DateExtractor
from .extractors import PageRenderer, TextExtractor
from .intake import DocumentIntake, DocumentRecord
from .ml_model import SmallLMModel
from .processor import DocumentProcessor
from .smart_reader import SmartReader
from .vendors import VendorExtractor

__all__ = [
    "Config",
    "TextExtractor",
    "PageRenderer",
    "DocumentTypeClassifier",
    "DocumentStatusClassifier",
    "DateExtractor",
    "VendorExtractor",
    "SmallLMModel",
    "SmartReader",
    "DocumentProcessor",
    "DocumentIntake",
    "DocumentRecord",
]
