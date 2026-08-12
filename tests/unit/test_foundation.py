"""Tests for pilot-readiness foundation behavior."""

from legaldocuman.backends.nvidia import NvidiaOCRBackend
from legaldocuman.vendors import VendorExtractor


def test_vendor_can_be_inferred_from_upload_filename():
    extractor = VendorExtractor()
    assert extractor.extract_vendor_from_filename("Acme_Corp_MSA_2024.pdf") == "Acme Corp"
    assert extractor.extract_vendor_from_filename("Globex-NDA-final.docx") == "Globex"


def test_nvidia_backend_is_not_available_until_implemented(monkeypatch):
    from legaldocuman.config import Config

    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    Config._instance = None
    backend = NvidiaOCRBackend()
    assert backend.is_available() is False
    assert backend.pdf_to_text("dummy.pdf") == ""
