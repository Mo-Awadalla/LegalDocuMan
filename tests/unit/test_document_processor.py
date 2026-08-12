"""Tests for legaldocuman classes and functions."""
import os
import re
from datetime import datetime
from unittest.mock import MagicMock, patch, mock_open
import pytest

import legaldocuman as ld
from legaldocuman.config import Config
from legaldocuman.extractors import TextExtractor
from legaldocuman.classifiers import DocumentTypeClassifier, DocumentStatusClassifier
from legaldocuman.dates import DateExtractor
from legaldocuman.vendors import VendorExtractor
from legaldocuman.processor import DocumentProcessor
from legaldocuman.utils import normalize_vendor_name, clean_vendor_for_filename


# =====================================================================
# UTILITY FUNCTIONS
# =====================================================================

class TestNormalizeVendorName:
    @pytest.mark.parametrize("raw,expected", [
        ("Acme Corp", "acme"),
        ("Acme Corporation Inc.", "acme"),
        ("Beta LLC", "beta"),
        ("Gamma Ltd.", "gamma"),
        ("Delta & Sons, Co.", "delta sons"),
        ("", ""),
        (None, ""),
        ("The Widget Company PLC", "the widget"),
        # Omega L.L.P. now correctly returns "omega" (fixed regex)
        ("Omega L.L.P.", "omega"),
    ])
    def test_normalization(self, raw, expected):
        assert normalize_vendor_name(raw) == expected


class TestCleanVendorForFilename:
    @pytest.mark.parametrize("raw,expected", [
        ("Acme Corp", "AcmeCorp"),
        ("Beta LLC", "BetaLLC"),
        ("Gamma-Soft", "GammaSoft"),
        ("Delta & Co.", "DeltaCo"),
        ("", "UnknownVendor"),
        (None, "UnknownVendor"),
        ("Widget Co.", "WidgetCo"),
    ])
    def test_cleaning(self, raw, expected):
        assert clean_vendor_for_filename(raw) == expected


# =====================================================================
# TEXT EXTRACTOR
# =====================================================================

class TestTextExtractor:
    def test_init_sets_ocr_flag(self):
        te = TextExtractor()
        assert hasattr(te, 'ocr_available')

    def test_extract_text_delegates_to_pdf_for_pdfs(self, sample_pdf_path, monkeypatch):
        te = TextExtractor()
        mock_pdf = MagicMock(return_value="pdf text")
        monkeypatch.setattr(te, 'extract_from_pdf', mock_pdf)
        result = te.extract_text(sample_pdf_path)
        mock_pdf.assert_called_once_with(sample_pdf_path, None)
        assert result == "pdf text"

    def test_extract_text_delegates_to_docx_for_docx(self, sample_docx_path, monkeypatch):
        te = TextExtractor()
        mock_docx = MagicMock(return_value="docx text")
        monkeypatch.setattr(te, 'extract_from_docx', mock_docx)
        result = te.extract_text(sample_docx_path)
        mock_docx.assert_called_once_with(sample_docx_path)
        assert result == "docx text"

    def test_extract_text_returns_empty_for_unsupported(self, temp_dir):
        te = TextExtractor()
        p = str(temp_dir / "file.xyz")
        open(p, 'w').close()
        assert te.extract_text(p) == ""

    def test_extract_from_pdf_with_mocked_pdfplumber(self, temp_dir):
        te = TextExtractor()
        p = str(temp_dir / "test.pdf")
        open(p, 'w').close()
        result = te.extract_from_pdf(p)
        assert isinstance(result, str)

    def test_extract_from_docx_with_mocked_docx(self, temp_dir):
        te = TextExtractor()
        p = str(temp_dir / "test.docx")
        open(p, 'w').close()
        result = te.extract_from_docx(p)
        assert isinstance(result, str)


# =====================================================================
# DOCUMENT TYPE CLASSIFIER
# =====================================================================

class TestDocumentTypeClassifier:
    def test_identify_msa_from_text(self):
        dtc = DocumentTypeClassifier()
        text = "This Master Service Agreement governs the relationship."
        assert dtc.identify_type(text) == "MSA"

    def test_identify_msa_from_filename(self):
        dtc = DocumentTypeClassifier()
        assert dtc.identify_type("", "contract msa 2024.pdf") == "MSA"

    def test_identify_msa_from_underscore_filename(self):
        dtc = DocumentTypeClassifier()
        assert dtc.identify_type("", "Synthetic_Acme_scanned_signed_MSA.pdf") == "MSA"

    def test_identify_sow(self):
        dtc = DocumentTypeClassifier()
        text = "Statement of Work for consulting services."
        assert dtc.identify_type(text) == "SOW"

    def test_identify_nda(self):
        dtc = DocumentTypeClassifier()
        text = "Non-Disclosure Agreement between parties."
        assert dtc.identify_type(text) == "NDA"

    def test_identify_po(self):
        dtc = DocumentTypeClassifier()
        text = "Purchase Order #12345 for hardware."
        assert dtc.identify_type(text) == "PO"

    def test_identify_amendment(self):
        dtc = DocumentTypeClassifier()
        text = "This amendment modifies the original agreement."
        assert dtc.identify_type(text) == "AMD"

    def test_identify_license(self):
        dtc = DocumentTypeClassifier()
        text = "Software License Agreement for enterprise use."
        assert dtc.identify_type(text) == "LICENSE"

    def test_defaults_to_contract(self):
        dtc = DocumentTypeClassifier()
        assert dtc.identify_type("some random text without keywords") == "CONTRACT"

    def test_filename_boosts_score(self):
        dtc = DocumentTypeClassifier()
        result = dtc.identify_type("hello world", "msa final.pdf")
        assert result == "MSA"


# =====================================================================
# DOCUMENT STATUS CLASSIFIER
# =====================================================================

class TestDocumentStatusClassifier:
    def test_one_high_confidence_visual_signature_is_final(self, monkeypatch):
        dsc = DocumentStatusClassifier()
        dsc.signature_detector = object()
        monkeypatch.setattr(dsc, "_detect_signatures_visual", lambda _path: [{"confidence": 0.85}])

        assert dsc.classify_status("signed_msa.pdf", "", file_path="signed_msa.pdf") == "final"

    def test_final_with_digital_signature(self):
        dsc = DocumentStatusClassifier()
        text = "This agreement was digitally signed by John Smith on 12/15/2023."
        assert dsc.classify_status("contract.pdf", text) == "final"

    def test_final_with_execution_language(self):
        dsc = DocumentStatusClassifier()
        text = "IN WITNESS WHEREOF, the parties have executed this Agreement."
        assert dsc.classify_status("contract.pdf", text) == "final"

    def test_final_with_docusign(self):
        dsc = DocumentStatusClassifier()
        text = "DocuSign Envelope ID: 12345-ABCD-6789"
        assert dsc.classify_status("contract.pdf", text) == "final"

    def test_final_with_witness(self):
        dsc = DocumentStatusClassifier()
        text = "Witnessed by: Jane Doe, Notary Public"
        assert dsc.classify_status("contract.pdf", text) == "final"

    def test_blank_signature_block_is_supporting(self):
        dsc = DocumentStatusClassifier()
        text = "By: _________________    Date: ___________"
        assert dsc.classify_status("contract.pdf", text) == "supporting"

    def test_supporting_without_signatures(self):
        dsc = DocumentStatusClassifier()
        text = "This is a draft agreement pending review."
        assert dsc.classify_status("contract.pdf", text) == "supporting"

    def test_supporting_for_main_contract_no_sigs(self):
        dsc = DocumentStatusClassifier()
        text = "Master Service Agreement between parties."
        assert dsc.classify_status("msa.pdf", text) == "supporting"

    def test_supporting_for_exhibit(self):
        dsc = DocumentStatusClassifier()
        text = "Exhibit A - Statement of Work"
        assert dsc.classify_status("exhibit_a.pdf", text) == "supporting"

    def test_empty_content_is_supporting(self):
        dsc = DocumentStatusClassifier()
        assert dsc.classify_status("file.pdf", "") == "supporting"

    def test_get_signature_analysis_detects_signatures(self):
        dsc = DocumentStatusClassifier()
        text = "digitally signed by John Smith"
        analysis = dsc.get_signature_analysis(text)
        assert analysis["has_signatures"] is True
        assert analysis["signature_count"] >= 1
        assert analysis["is_final"] is True
        assert analysis["confidence"] in ("medium", "high")

    def test_get_signature_analysis_no_signatures(self):
        dsc = DocumentStatusClassifier()
        analysis = dsc.get_signature_analysis("just some normal text")
        assert analysis["has_signatures"] is False
        assert analysis["signature_count"] == 0
        assert analysis["confidence"] == "none"

    def test_get_signature_analysis_high_confidence_patterns(self):
        dsc = DocumentStatusClassifier()
        text = "IN WITNESS WHEREOF the parties have executed this in duplicate."
        analysis = dsc.get_signature_analysis(text)
        assert analysis["confidence"] == "high"

    def test_get_signature_analysis_empty_string(self):
        dsc = DocumentStatusClassifier()
        analysis = dsc.get_signature_analysis("")
        assert analysis["has_signatures"] is False

    def test_detect_signatures_finds_multiple(self):
        dsc = DocumentStatusClassifier()
        text = (
            "Signed by: John Smith\n"
            "Date: 2024-01-15\n"
            "Authorized signature: Jane Doe\n"
            "DocuSign Envelope ID: ABC123"
        )
        sigs = dsc._detect_signatures(text.lower())
        assert len(sigs) >= 1


# =====================================================================
# DATE EXTRACTOR
# =====================================================================

class TestDateExtractor:
    def test_init_has_patterns(self):
        de = DateExtractor()
        assert len(de.date_patterns) > 0

    def test_extract_date_from_text_with_mock(self, monkeypatch):
        de = DateExtractor()
        mock_dt = datetime(2024, 3, 15)
        monkeypatch.setattr(
            'dateparser.search.search_dates',
            lambda text, settings=None: [("March 15, 2024", mock_dt)]
        )
        result = de.extract_date_from_text("Effective March 15, 2024")
        assert result == "20240315"

    def test_extract_date_from_text_returns_none_when_no_dates(self, monkeypatch):
        de = DateExtractor()
        monkeypatch.setattr(
            'dateparser.search.search_dates',
            lambda text, settings=None: None
        )
        assert de.extract_date_from_text("no dates here") is None

    def test_extract_dates_with_metadata_finds_effective_date(self, monkeypatch):
        de = DateExtractor()
        fake_date = datetime(2024, 6, 1)
        monkeypatch.setattr('dateparser.parse', lambda x: fake_date)
        meta = de.extract_dates_with_metadata("Effective date: June 1, 2024")
        assert meta["effective_date"] == "2024-06-01"

    def test_extract_dates_with_metadata_finds_expiration(self, monkeypatch):
        de = DateExtractor()
        fake_date = datetime(2025, 12, 31)
        monkeypatch.setattr('dateparser.parse', lambda x: fake_date)
        meta = de.extract_dates_with_metadata("This agreement expires on December 31, 2025")
        assert meta["expiration_date"] == "2025-12-31"

    def test_extract_dates_with_metadata_finds_renewal(self, monkeypatch):
        de = DateExtractor()
        fake_date = datetime(2025, 1, 1)
        monkeypatch.setattr('dateparser.parse', lambda x: fake_date)
        meta = de.extract_dates_with_metadata("Automatically renews on January 1, 2025")
        assert meta["renewal_date"] == "2025-01-01"

    def test_extract_dates_with_metadata_finds_review(self, monkeypatch):
        de = DateExtractor()
        fake_date = datetime(2024, 7, 15)
        monkeypatch.setattr('dateparser.parse', lambda x: fake_date)
        meta = de.extract_dates_with_metadata("Subject to review on July 15, 2024")
        assert meta["review_date"] == "2024-07-15"

    def test_extract_dates_with_metadata_returns_none_for_missing(self, monkeypatch):
        de = DateExtractor()
        monkeypatch.setattr('dateparser.parse', lambda x: None)
        meta = de.extract_dates_with_metadata("no relevant dates")
        assert meta["effective_date"] is None
        assert meta["expiration_date"] is None
        assert meta["renewal_date"] is None
        assert meta["review_date"] is None


# =====================================================================
# VENDOR EXTRACTOR
# =====================================================================

class TestVendorExtractor:
    def test_extract_vendor_from_folder_simple(self):
        ve = VendorExtractor()
        assert ve.extract_vendor_from_folder("Acme Corp") == "acme corp"

    def test_extract_vendor_from_folder_removes_suffixes(self):
        ve = VendorExtractor()
        assert ve.extract_vendor_from_folder("Acme Corp Contracts") == "acme corp"

    def test_extract_vendor_from_folder_generic_returns_none(self):
        ve = VendorExtractor()
        assert ve.extract_vendor_from_folder("contracts") is None
        assert ve.extract_vendor_from_folder("documents") is None
        assert ve.extract_vendor_from_folder("temp") is None

    def test_extract_vendor_from_folder_empty(self):
        ve = VendorExtractor()
        assert ve.extract_vendor_from_folder("") is None

    def test_match_vendor_exact_match(self):
        ve = VendorExtractor(["Acme Corporation", "Beta LLC"])
        match, score = ve.match_vendor_against_master_list("Acme Corporation")
        assert match == "Acme Corporation"
        assert score == 100

    def test_match_vendor_fuzzy_match(self):
        ve = VendorExtractor(["Acme Corporation Inc", "Beta LLC"])
        match, score = ve.match_vendor_against_master_list("Acme Corp")
        assert match == "Acme Corporation Inc"
        assert score > 50

    def test_match_vendor_no_match_below_threshold(self):
        ve = VendorExtractor(["XYZ Enterprises"])
        match, score = ve.match_vendor_against_master_list("Completely Different")
        assert score < 80

    def test_match_vendor_empty_list(self):
        ve = VendorExtractor()
        match, score = ve.match_vendor_against_master_list("Acme")
        assert match == "Acme"
        assert score == 0

    def test_match_vendor_none_name(self):
        ve = VendorExtractor(["Acme"])
        match, score = ve.match_vendor_against_master_list(None)
        assert match is None
        assert score == 0


# =====================================================================
# DOCUMENT PROCESSOR
# =====================================================================

class TestDocumentProcessor:
    def test_init_creates_error_folder(self, temp_dir):
        input_path = str(temp_dir / "input")
        DocumentProcessor(input_path)
        assert os.path.exists(temp_dir / "input" / "_errors")

    def test_init_with_custom_error_folder(self, temp_dir):
        input_path = str(temp_dir / "input")
        error_path = str(temp_dir / "custom_errors")
        processor = DocumentProcessor(input_path, error_path)
        assert processor.error_folder == error_path

    def test_init_initializes_components(self, temp_dir):
        input_path = str(temp_dir / "input")
        processor = DocumentProcessor(input_path)
        assert processor.intake.text_extractor is not None
        assert processor.intake.date_extractor is not None
        assert processor.intake.doc_type_classifier is not None
        assert processor.intake.status_classifier is not None
        assert processor.intake.vendor_extractor is not None

    def test_init_with_vendor_list(self, temp_dir):
        input_path = str(temp_dir / "input")
        processor = DocumentProcessor(input_path, vendor_master_list=["Acme", "Beta"])
        assert processor.intake.vendor_extractor.vendor_master_list == ["Acme", "Beta"]

    def test_generate_enhanced_filename(self, temp_dir):
        input_path = str(temp_dir / "input")
        processor = DocumentProcessor(input_path)
        fn = processor.intake._enhanced_filename("AcmeCorp", "MSA", "old.pdf", 1)
        assert "AcmeCorp" in fn
        assert "AGMT" in fn
        assert "masterServiceAgreement" in fn
        assert "001" in fn
        assert ".pdf" in fn

    def test_generate_simple_filename(self, temp_dir):
        input_path = str(temp_dir / "input")
        processor = DocumentProcessor(input_path)
        fn = processor.intake._simple_filename("AcmeCorp", "old.pdf", "20240115")
        assert fn.startswith("20240115")
        assert "AcmeCorp" in fn

    def test_get_unique_id_increments(self, temp_dir):
        input_path = str(temp_dir / "input")
        processor = DocumentProcessor(input_path)
        id1 = processor._get_unique_id("Acme", "MSA")
        id2 = processor._get_unique_id("Acme", "MSA")
        assert id2 != id1
        assert int(id2) == int(id1) + 1

    def test_handle_filename_conflict_appends_counter(self, temp_dir):
        from legaldocuman.utils import resolve_filename_conflict
        target = str(temp_dir / "file.txt")
        open(target, 'w').close()
        result = resolve_filename_conflict(target)
        assert "_conflict01" in result

    def test_create_metadata_structure(self, temp_dir):
        input_path = str(temp_dir / "input")
        processor = DocumentProcessor(input_path)
        file_path = str(temp_dir / "file.pdf")
        open(file_path, 'w').close()
        from legaldocuman.intake import DocumentRecord
        record = DocumentRecord(
            vendor="Acme",
            clean_vendor="Acme",
            doc_type="MSA",
            status="final",
            date_str="20240115",
            date_metadata={},
            signature_analysis={},
            text_content="test content",
        )
        processor._create_metadata(file_path, record, "AGMT_Acme_masterServiceAgreement_001.pdf")
        meta_file = str(temp_dir / "file.metadata.json")
        assert os.path.exists(meta_file)
        with open(meta_file) as f:
            import json
            meta = json.load(f)
        assert meta["original_filename"] == "file.pdf"
        assert meta["vendor"] == "Acme"
        assert meta["document_type"] == "MSA"
        assert "metadata_created_timestamp" in meta
        assert "tracking_id" in meta

    def test_determine_retention_category_contract_with_expiration(self, temp_dir):
        input_path = str(temp_dir / "input")
        processor = DocumentProcessor(input_path)
        cfg = Config.get()
        assert cfg.get_retention_category("MSA", True) == "long_term"
        assert cfg.get_retention_category("SOW", False) == "contracts"

    def test_determine_retention_category_nda(self, temp_dir):
        cfg = Config.get()
        assert cfg.get_retention_category("NDA", False) == "indefinite"

    def test_determine_retention_category_license(self, temp_dir):
        cfg = Config.get()
        assert cfg.get_retention_category("LICENSE", True) == "indefinite"

    def test_determine_retention_category_po(self, temp_dir):
        cfg = Config.get()
        assert cfg.get_retention_category("PO", False) == "short_term"

    def test_determine_retention_category_amendment(self, temp_dir):
        cfg = Config.get()
        assert cfg.get_retention_category("AMD", True) == "tied_to_parent"

    def test_determine_retention_category_default(self, temp_dir):
        cfg = Config.get()
        assert cfg.get_retention_category("UNKNOWN", False) == "review_required"

    def test_move_to_error_folder(self, temp_dir):
        input_path = str(temp_dir / "input")
        processor = DocumentProcessor(input_path)
        src = temp_dir / "test_file.txt"
        src.write_text("x")
        processor._move_to_error_folder(str(src), "test error")
        error_dir = temp_dir / "input" / "_errors"
        assert any("test_file" in f for f in os.listdir(error_dir))

    def test_sort_files_by_year_moves_old_files(self, temp_dir, monkeypatch):
        input_path = str(temp_dir / "input")
        os.makedirs(input_path, exist_ok=True)
        processor = DocumentProcessor(input_path)
        monkeypatch.setattr(processor.intake.date_extractor, 'extract_date_from_text', lambda text, filename: "20150101")
        src = os.path.join(input_path, "Contract_2015.pdf")
        open(src, 'w').close()
        archive_dir = str(temp_dir / "archive")
        processor.sort_files_by_year(archive_dir)
        assert os.path.exists(os.path.join(archive_dir, "Contract_2015.pdf"))

    def test_sort_files_by_year_keeps_new_files(self, temp_dir, monkeypatch):
        input_path = str(temp_dir / "input")
        os.makedirs(input_path, exist_ok=True)
        processor = DocumentProcessor(input_path)
        monkeypatch.setattr(processor.intake.date_extractor, 'extract_date_from_text', lambda text, filename: "20230101")
        src = os.path.join(input_path, "Contract_2023.pdf")
        open(src, 'w').close()
        archive_dir = str(temp_dir / "archive")
        processor.sort_files_by_year(archive_dir)
        assert os.path.exists(os.path.join(input_path, "Contract_2023.pdf"))
