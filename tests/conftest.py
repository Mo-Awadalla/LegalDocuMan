"""Fixtures shared by unit and integration tests.

Heavy dependencies are intentionally not mocked here: integration collection must
exercise the real PDF/OCR/image/RF-DETR import graph.
"""
import pytest


@pytest.fixture
def temp_dir(tmp_path):
    return tmp_path


@pytest.fixture
def sample_pdf_path(temp_dir):
    path = temp_dir / "sample.pdf"
    path.write_text("dummy pdf content")
    return str(path)


@pytest.fixture
def sample_docx_path(temp_dir):
    path = temp_dir / "sample.docx"
    path.write_text("dummy docx content")
    return str(path)


@pytest.fixture
def mock_registry():
    return {
        "total_documents": 3,
        "documents_with_expiration": 2,
        "expiration_tracking": [
            {"tracking_id": "DOC-001", "vendor": "Acme Corp", "document_type": "MSA",
             "filename": "AcmeCorp_MSA_2024-01-15.pdf", "expiration_date": "2025-06-01",
             "retention_category": "Contracts", "contract_value": 50000},
            {"tracking_id": "DOC-002", "vendor": "Beta LLC", "document_type": "SOW",
             "filename": "BetaLLC_SOW_2023-12-01.pdf", "expiration_date": "2024-03-15",
             "retention_category": "SOWs", "contract_value": 12000},
            {"tracking_id": "DOC-003", "vendor": "Gamma Inc", "document_type": "NDA",
             "filename": "GammaInc_NDA_2024-02-10.pdf", "expiration_date": None,
             "retention_category": "NDAs", "contract_value": 0},
        ],
    }
