"""Document intake pipeline — extraction, classification, and naming behind a single interface.

Pipeline (per document):
  1. SmartReader.progressively_ocr_front_pages() → focused text snippet
     - Renders pages 1..N through a shared PageRenderer
     - Widens the page range until a vendor preamble / title-line is found
       or the cumulative text crosses SMALL_LM_MIN_TEXT_LENGTH
     - Stops at SMALL_LM_MAX_PAGES
  2. SmallLMModel.analyze(snippet) → {"doc_type": ..., "vendor": ...}
     - When SMALL_LM_ENABLED is false or the model is unavailable, the
       legacy regex-based DocumentTypeClassifier and VendorExtractor
       cascade is used as a fallback.
  3. (unchanged) DocumentStatusClassifier for final/supporting via
     RF-DETR on the last pages + regex fallback.
  4. (unchanged) DateExtractor for effective/expiration/renewal/review dates.

The SmartReader and the signature detector share the same PageRenderer,
so a 1-page addendum is rendered exactly once.
"""
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .classifiers import DocumentStatusClassifier, DocumentTypeClassifier
from .config import Config
from .dates import DateExtractor
from .extractors import TextExtractor
from .ml_model import SmallLMModel
from .smart_reader import SmartReader
from .utils import clean_vendor_for_filename
from .vendors import VendorExtractor


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
        small_lm: Optional[SmallLMModel] = None,
        smart_reader: Optional[SmartReader] = None,
        ocr_backend=None,
    ):
        # One TextExtractor → one shared PageRenderer for both SmartReader
        # and the signature detector.  Pass the same instance into both.
        self.text_extractor = text_extractor or TextExtractor(ocr_backend=ocr_backend)
        self.date_extractor = date_extractor or DateExtractor()
        self.doc_type_classifier = doc_type_classifier or DocumentTypeClassifier()
        self.status_classifier = status_classifier or DocumentStatusClassifier()
        self.vendor_extractor = VendorExtractor(vendor_master_list)
        self.small_lm = small_lm or SmallLMModel()
        self.smart_reader = smart_reader or SmartReader(
            text_extractor=self.text_extractor,
            page_renderer=self.text_extractor.page_renderer,
        )

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
            # 1. Progressive OCR of the front pages through the shared renderer
            text_content, region_found, pages_read = self.smart_reader.read(file_path)
            if pages_read:
                logging.debug(
                    f"SmartReader consumed {pages_read} page(s) "
                    f"(region_found={region_found}) for {filename}"
                )

            # 2. Doc type + vendor via the small LM (or legacy fallback)
            doc_type, vendor_name = self._classify_with_lm(
                text_content, filename, vendor_folder
            )

            # 3. Apply master-list fuzzy match if configured
            if vendor_name and self.vendor_extractor.vendor_master_list:
                vendor_name, _ = self.vendor_extractor.match_vendor_against_master_list(
                    vendor_name
                )
            clean_vendor = clean_vendor_for_filename(vendor_name)

            # 4. Signature analysis + execution status (reuses the shared
            #    PageRenderer — see _render_pdf_pages in classifiers.py)
            sig_analysis = self.status_classifier.get_signature_analysis(
                text_content, file_path=file_path
            )
            status = self.status_classifier.classify_status(
                filename, text_content, file_path=file_path
            )

            # 5. Extract dates
            date_str = self.date_extractor.extract_date_from_text(text_content, filename)
            date_metadata = self.date_extractor.extract_dates_with_metadata(text_content)

            logging.info("Intake analysis complete (type=%s, status=%s)", doc_type, status)

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
            logging.error("Intake analysis failed (error_type=%s)", e.__class__.__name__)
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

    def _classify_with_lm(
        self, text_content: str, filename: str, vendor_folder: str
    ):
        """Run the small LM and fall back to the legacy cascade on any failure."""
        cfg = Config.get()

        # Try the small LM first
        lm_result = None
        if cfg.SMALL_LM_ENABLED and self.small_lm.is_available() and text_content:
            try:
                lm_result = self.small_lm.analyze(text_content)
            except Exception as exc:
                logging.debug(f"SmallLMModel.analyze failed: {exc}")
                lm_result = None

        doc_type = ""
        vendor_name = ""
        if lm_result:
            doc_type = (lm_result.get("doc_type") or "").upper().strip()
            vendor_name = (lm_result.get("vendor") or "").strip()

        # Legacy fallback for doc type
        if not doc_type:
            doc_type = self.doc_type_classifier.identify_type(text_content, filename)

        # Legacy fallback cascade for vendor: folder → filename.
        # (extract_vendor_from_text is deprecated in the new pipeline.)
        if not vendor_name:
            vendor_name = self.vendor_extractor.extract_vendor_from_folder(vendor_folder) or ""
        if not vendor_name:
            vendor_name = self.vendor_extractor.extract_vendor_from_filename(filename) or ""

        return doc_type or "CONTRACT", vendor_name

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
