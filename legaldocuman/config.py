"""
Configuration constants and runtime settings for LegalDocuMan.
All previously hardcoded values live here.
"""
import os
from dataclasses import dataclass, field
from typing import List, Optional

# Load .env file if python-dotenv is installed
try:
    from dotenv import load_dotenv
    _dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(_dotenv_path):
        load_dotenv(_dotenv_path)
    else:
        load_dotenv()  # try cwd
except ImportError:
    pass  # python-dotenv not installed; rely on system env vars


@dataclass(frozen=True)
class Config:
    """Centralized configuration — immutable after creation."""

    # ------------------------------------------------------------------
    # Date validation
    # ------------------------------------------------------------------
    MIN_YEAR: int = 1990
    MAX_YEAR: int = 2040
    MAX_YEAR_FILENAME: int = 2035

    # ------------------------------------------------------------------
    # Text extraction limits
    # ------------------------------------------------------------------
    PDF_MAX_PAGES: int = 5
    OCR_MAX_PAGES: int = 3
    TEXT_OUTPUT_LIMIT: int = 5000
    TXT_OUTPUT_LIMIT: int = 3000
    MIN_MEANINGFUL_TEXT_LENGTH: int = 50
    MIN_PAGE_TEXT_LENGTH: int = 10

    # ------------------------------------------------------------------
    # Signature detection
    # ------------------------------------------------------------------
    SIGNATURE_CONTEXT_WINDOW: int = 200
    HIGH_CONFIDENCE_SIGNATURE_THRESHOLD: int = 3
    MEDIUM_CONFIDENCE_SIGNATURE_THRESHOLD: int = 1
    MAX_SIGNATURES_LOGGED: int = 5

    # ------------------------------------------------------------------
    # File naming
    # ------------------------------------------------------------------
    UNIQUE_ID_PADDING: int = 3
    CONFLICT_COUNTER_PADDING: int = 2

    # ------------------------------------------------------------------
    # Year sorting
    # ------------------------------------------------------------------
    YEAR_SORT_THRESHOLD: int = 2017

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------
    LOG_DIR_NAME: str = "DocumentProcessorLogs"
    LOG_FILE_NAME: str = "document_processor.log"
    CONFIG_FILE_NAME: str = "config.json"
    ERROR_SUBDIR: str = "_errors"
    BACKUP_SUBDIR: str = "_backup"
    REGISTRY_FILE_NAME: str = "_backend_tracking_registry.json"

    # ------------------------------------------------------------------
    # Tesseract / OCR tool paths (override via env vars)
    # ------------------------------------------------------------------
    TESSERACT_PATH: Optional[str] = field(
        default_factory=lambda: os.environ.get("TESSERACT_PATH")
    )
    POPLER_PATH: Optional[str] = field(
        default_factory=lambda: os.environ.get("POPLER_PATH")
    )

    # Fallback Tesseract locations (Windows + PATH)
    TESSERACT_FALLBACK_PATHS: List[str] = field(default_factory=lambda: [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        r'tesseract',
    ])

    # Fallback Poppler locations
    POPLER_FALLBACK_PATHS: List[str] = field(default_factory=lambda: [
        os.path.expanduser(r"~/Documents/poppler-24.08.0/Library/bin"),
        os.path.expanduser(r"~/poppler-24.08.0/Library/bin"),
    ])

    # ------------------------------------------------------------------
    # NVIDIA OCR settings
    # ------------------------------------------------------------------
    NVIDIA_OCR_MODEL: str = field(
        default_factory=lambda: os.environ.get("NVIDIA_OCR_MODEL", "nvidia/nemotron-ocr-v2")
    )
    NVIDIA_API_BASE_URL: str = field(
        default_factory=lambda: os.environ.get("NVIDIA_API_BASE_URL", "")
    )
    NVIDIA_API_KEY: Optional[str] = field(
        default_factory=lambda: os.environ.get("NVIDIA_API_KEY")
    )
    OCR_BACKEND: str = field(
        default_factory=lambda: os.environ.get("OCR_BACKEND", "tesseract")
    )

    # ------------------------------------------------------------------
    # Document type abbreviations & descriptions
    # ------------------------------------------------------------------
    TYPE_ABBREVIATIONS: dict = field(default_factory=lambda: {
        'MSA': 'AGMT', 'SOW': 'AGMT', 'NDA': 'AGMT', 'PO': 'K',
        'AMD': 'AMD', 'LICENSE': 'K', 'CONTRACT': 'K', 'AGREEMENT': 'AGMT',
    })

    TYPE_DESCRIPTIONS: dict = field(default_factory=lambda: {
        'MSA': 'masterServiceAgreement',
        'SOW': 'statementOfWork',
        'NDA': 'nonDisclosureAgreement',
        'PO': 'purchaseOrder',
        'AMD': 'amendment',
        'LICENSE': 'licenseAgreement',
        'CONTRACT': 'serviceAgreement',
        'AGREEMENT': 'serviceAgreement',
    })

    # ------------------------------------------------------------------
    # Supported file extensions
    # ------------------------------------------------------------------
    SUPPORTED_EXTENSIONS: List[str] = field(default_factory=lambda: [
        '.pdf', '.docx', '.doc', '.txt'
    ])
    SORT_SUPPORTED_EXTENSIONS: List[str] = field(default_factory=lambda: [
        '.pdf', '.docx', '.doc'
    ])

    # ------------------------------------------------------------------
    # Regex: vendor suffixes
    # ------------------------------------------------------------------
    VENDOR_SUFFIX_PATTERNS: List[str] = field(default_factory=lambda: [
        r'(?<!\w)llc(?!\w)', r'(?<!\w)l\.l\.c\.(?!\w)',
        r'(?<!\w)inc(?!\w)', r'(?<!\w)inc\.(?!\w)', r'(?<!\w)incorporated(?!\w)',
        r'(?<!\w)corp(?!\w)', r'(?<!\w)corp\.(?!\w)', r'(?<!\w)corporation(?!\w)',
        r'(?<!\w)ltd(?!\w)', r'(?<!\w)ltd\.(?!\w)', r'(?<!\w)limited(?!\w)',
        r'(?<!\w)co(?!\w)', r'(?<!\w)co\.(?!\w)', r'(?<!\w)company(?!\w)',
        r'(?<!\w)llp(?!\w)', r'(?<!\w)l\.l\.p\.(?!\w)', r'(?<!\w)plc(?!\w)',
    ])

    # ------------------------------------------------------------------
    # Retention categories
    # ------------------------------------------------------------------
    def get_retention_category(self, doc_type: str, has_expiration: bool) -> str:
        dt = (doc_type or '').upper()
        if dt in ('MSA', 'CONTRACT', 'AGREEMENT'):
            return 'long_term' if has_expiration else 'indefinite'
        if dt in ('NDA', 'LICENSE'):
            return 'indefinite'
        if dt in ('PO', 'INVOICE'):
            return 'short_term'
        if dt == 'AMD':
            return 'tied_to_parent'
        if dt == 'SOW':
            return 'contracts'
        return 'review_required'

    # Singleton accessor
    _instance = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
