"""Document intake pipeline — extraction, classification, and naming behind a single interface."""
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .config import Config
from .classifiers import DocumentTypeClassifier, DocumentStatusClassifier
from .dates import DateExtractor
from .extractors import TextExtractor
from .vendors import VendorExtractor
from .utils import clean_vendor_for_filename


@dataclass
class DocumentRecord:
    """Result of analysing a single document through the intake pipeline."""
    vendor: str
    clean_vendor: str
    doc_type: str
    status: str
    date_str: str
    date_metadata: Dict[str, Any]
    signature_analysis: Dict[str, Any]
    text_content: str
    error: Optional[str] = None


class DocumentIntake:
    """Document intake: extract, classify, name.

    Stateless — same inputs always produce the same record.
    File movement, metadata persistence, and registry updates
    are the caller's responsibility.
    """

    def __init__(
        self,
        text_extractor: Optional[TextExtractor] = None,
        date_extractor: Optional[DateExtractor] = None,
        doc_type_classifier: Optional[DocumentTypeClassifier] = None,
        status_classifier: Optional[DocumentStatusClassifier] = None,
        vendor_master_list: Optional[list] = None,
        ocr_backend=None,
    ):
        self.text_extractor = text_extractor or TextExtractor(ocr_backend=ocr_backend)
        self.date_extractor = date_extractor or DateExtractor()
        self.doc_type_classifier = doc_type_classifier or DocumentTypeClassifier()
        self.status_classifier = status_classifier or DocumentStatusClassifier()
        self.vendor_extractor = VendorExtractor(vendor_master_list)

    # -- public interface --------------------------------------------------

    def analyze(self, file_path: str, vendor_folder: str) -> DocumentRecord:
        """Extract, classify, and analyse a single document.

        Args:
            file_path: Path to the document file.
            vendor_folder: Name of the vendor folder containing the file.

        Returns:
            DocumentRecord with analysis results, or with error set if processing failed.
        """
        filename = os.path.basename(file_path)

        try:
            # 1. Extract text
            text_content = self.text_extractor.extract_text(file_path)

            # 2-3. Vendor extraction and matching
            vendor_name = self.vendor_extractor.extract_vendor_from_folder(vendor_folder)
            if not vendor_name:
                vendor_name = self.vendor_extractor.extract_vendor_from_text(text_content)
            if not vendor_name:
                vendor_name = self.vendor_extractor.extract_vendor_from_filename(filename)
            if self.vendor_extractor.vendor_master_list:
                vendor_name, _ = self.vendor_extractor.match_vendor_against_master_list(vendor_name)
            clean_vendor = clean_vendor_for_filename(vendor_name)

            # 4. Classify document type
            doc_type = self.doc_type_classifier.identify_type(text_content, filename)

            # 5-6. Signature analysis + execution status
            sig_analysis = self.status_classifier.get_signature_analysis(
                text_content, file_path=file_path
            )
            status = self.status_classifier.classify_status(
                filename, text_content, file_path=file_path
            )

            # 7. Extract dates
            date_str = self.date_extractor.extract_date_from_text(text_content, filename)
            date_metadata = self.date_extractor.extract_dates_with_metadata(text_content)

            logging.info(
                f"Intake analysis complete: {filename} "
                f"(vendor={vendor_name}, type={doc_type}, status={status})"
            )

            return DocumentRecord(
                vendor=vendor_name,
                clean_vendor=clean_vendor,
                doc_type=doc_type,
                status=status,
                date_str=date_str,
                date_metadata=date_metadata,
                signature_analysis=sig_analysis,
                text_content=text_content,
            )

        except Exception as e:
            logging.error(f"Intake analysis failed for {filename}: {e}")
            return DocumentRecord(
                vendor="",
                clean_vendor="",
                doc_type="",
                status="",
                date_str="",
                date_metadata={},
                signature_analysis={},
                text_content="",
                error=str(e),
            )

    def generate_filename(
        self,
        record: DocumentRecord,
        unique_id: int,
        naming_format: str = "enhanced",
    ) -> str:
        """Generate a filename for the analysed document.

        Separated from analyse() so the caller can manage the unique-ID counter
        (which depends on vendor + doc_type, only known after analysis).
        """
        if naming_format == "enhanced":
            return self._enhanced_filename(
                record.clean_vendor, record.doc_type,
                record.text_content,  # not used but kept for signature
                unique_id,
            )
        else:
            return self._simple_filename(
                record.clean_vendor,
                record.text_content,  # will be replaced by caller with original filename
                record.date_str,
            )

    def generate_filename_from_original(
        self,
        record: DocumentRecord,
        original_filename: str,
        unique_id: int,
        naming_format: str = "enhanced",
    ) -> str:
        """Generate a filename, given the original filename for extension extraction."""
        if naming_format == "enhanced":
            return self._enhanced_filename(
                record.clean_vendor, record.doc_type,
                original_filename, unique_id,
            )
        else:
            return self._simple_filename(
                record.clean_vendor, original_filename, record.date_str,
            )

    # -- internal helpers --------------------------------------------------

    def _enhanced_filename(self, clean_vendor, doc_type, original_filename, unique_id) -> str:
        """K_Vendor_type_001.ext"""
        cfg = Config.get()
        abbreviation = cfg.TYPE_ABBREVIATIONS.get(doc_type, "K")
        type_desc = cfg.TYPE_DESCRIPTIONS.get(doc_type, "document")
        file_ext = os.path.splitext(original_filename)[1]
        return f"{abbreviation}_{clean_vendor}_{type_desc}_{unique_id:03d}{file_ext}"

    def _simple_filename(self, clean_vendor, original_filename, date_str) -> str:
        """YYYYMMDD_Vendor_OriginalFile.ext"""
        prefix = f"{date_str}_{clean_vendor}_" if date_str else f"{clean_vendor}_"
        return f"{prefix}{original_filename}"
