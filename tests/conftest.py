"""
Pytest configuration and mocks for LegalDocuMan tests.
Must mock external dependencies BEFORE legaldocuman is imported.
"""
import sys
from unittest.mock import MagicMock, patch
import pytest

# ------------------------------------------------------------------
# Mock all heavy external deps before any import of legaldocuman
# ------------------------------------------------------------------

# Mock pdfplumber
mock_pdfplumber = MagicMock()
sys.modules['pdfplumber'] = mock_pdfplumber

# Mock docx
mock_docx = MagicMock()
sys.modules['docx'] = mock_docx

# Mock pandas
mock_pd = MagicMock()
sys.modules['pandas'] = mock_pd
sys.modules['pd'] = mock_pd

# Mock dateparser
mock_dateparser = MagicMock()
sys.modules['dateparser'] = mock_dateparser
mock_dateparser.search = MagicMock()
sys.modules['dateparser.search'] = mock_dateparser.search

# Mock pytesseract (optional OCR)
mock_pytesseract = MagicMock()
sys.modules['pytesseract'] = mock_pytesseract

# Mock pdf2image
mock_pdf2image = MagicMock()
sys.modules['pdf2image'] = mock_pdf2image
mock_pdf2image.convert_from_path = MagicMock()

# Mock PIL
mock_pil = MagicMock()
sys.modules['PIL'] = mock_pil
sys.modules['PIL.Image'] = mock_pil

# Prevent side-effect logging setup from touching filesystem
import pathlib
import logging

_original_home = pathlib.Path.home
_original_basicConfig = logging.basicConfig

def _fake_home():
    return pathlib.Path('/tmp/fake_home')

pathlib.Path.home = _fake_home
logging.basicConfig = lambda *args, **kwargs: None

# Now safe to import legaldocuman
import legaldocuman as ld
from legaldocuman import Config
from legaldocuman.utils import (
    normalize_vendor_name,
    clean_vendor_for_filename,
    setup_directories,
    safe_move_file,
    get_unique_filename,
    clean_filename,
    format_file_size,
    get_file_info,
    count_files_by_extension,
    backup_file,
)

# Restore after import
pathlib.Path.home = _original_home
logging.basicConfig = _original_basicConfig


@pytest.fixture
def temp_dir(tmp_path):
    """Provide a temporary directory for file operations."""
    return tmp_path


@pytest.fixture
def sample_pdf_path(temp_dir):
    """Create a dummy PDF file path."""
    p = temp_dir / "sample.pdf"
    p.write_text("dummy pdf content")
    return str(p)


@pytest.fixture
def sample_docx_path(temp_dir):
    """Create a dummy DOCX file path."""
    p = temp_dir / "sample.docx"
    p.write_text("dummy docx content")
    return str(p)


@pytest.fixture
def mock_registry():
    """Return a sample backend tracking registry."""
    return {
        "total_documents": 3,
        "documents_with_expiration": 2,
        "expiration_tracking": [
            {
                "tracking_id": "DOC-001",
                "vendor": "Acme Corp",
                "document_type": "MSA",
                "filename": "AcmeCorp_MSA_2024-01-15.pdf",
                "expiration_date": "2025-06-01",
                "retention_category": "Contracts",
                "contract_value": 50000,
            },
            {
                "tracking_id": "DOC-002",
                "vendor": "Beta LLC",
                "document_type": "SOW",
                "filename": "BetaLLC_SOW_2023-12-01.pdf",
                "expiration_date": "2024-03-15",
                "retention_category": "SOWs",
                "contract_value": 12000,
            },
            {
                "tracking_id": "DOC-003",
                "vendor": "Gamma Inc",
                "document_type": "NDA",
                "filename": "GammaInc_NDA_2024-02-10.pdf",
                "expiration_date": None,
                "retention_category": "NDAs",
                "contract_value": 0,
            },
        ],
    }
