"""Text extraction from PDF, DOCX, TXT with pluggable OCR backends."""
import logging
import os
from typing import Optional

from .config import Config
from .backends import OCRBackend, TesseractOCRBackend, NvidiaOCRBackend


class TextExtractor:
    """Extract text from various document formats with pluggable OCR."""

    def __init__(self, ocr_backend: Optional[OCRBackend] = None):
        self.cfg = Config.get()
        self.ocr_backend = ocr_backend or self._auto_select_ocr()
        self.ocr_available = self.ocr_backend.is_available() if self.ocr_backend else False

    def _auto_select_ocr(self) -> OCRBackend:
        """Pick OCR backend based on env var OCR_BACKEND."""
        backend_name = self.cfg.OCR_BACKEND.lower()
        if backend_name == 'nvidia':
            nvidia = NvidiaOCRBackend()
            if nvidia.is_available():
                return nvidia
            logging.warning("NVIDIA OCR requested but unavailable — falling back to Tesseract")
        return TesseractOCRBackend()

    def extract_from_pdf(self, file_path, max_pages=None):
        """Extract text from PDF using pdfplumber with OCR fallback."""
        max_pages = max_pages or self.cfg.PDF_MAX_PAGES
        text = ""
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                num_pages = min(len(pdf.pages), max_pages)
                for page_num in range(num_pages):
                    try:
                        page = pdf.pages[page_num]
                        page_text = page.extract_text()
                        if page_text and len(page_text.strip()) > self.cfg.MIN_PAGE_TEXT_LENGTH:
                            text += page_text + "\n"
                    except Exception as e:
                        logging.debug(f"Error extracting from page {page_num}: {e}")
                        continue

                # If no meaningful text found, try OCR
                if len(text.strip()) < self.cfg.MIN_MEANINGFUL_TEXT_LENGTH and self.ocr_available:
                    logging.info(f"Attempting OCR for {os.path.basename(file_path)}")
                    text = self.ocr_backend.pdf_to_text(
                        file_path,
                        first_page=1,
                        last_page=min(max_pages, self.cfg.OCR_MAX_PAGES)
                    )
        except Exception as e:
            logging.error(f"Error processing PDF {file_path}: {e}")
            if self.ocr_available:
                logging.info(f"PDF processing failed, trying OCR for {os.path.basename(file_path)}")
                return self.ocr_backend.pdf_to_text(
                    file_path,
                    first_page=1,
                    last_page=min(max_pages, self.cfg.OCR_MAX_PAGES)
                )
            return ""

        return text[:self.cfg.TEXT_OUTPUT_LIMIT]

    def extract_from_docx(self, file_path):
        """Extract text from DOCX files."""
        try:
            import docx
            document = docx.Document(file_path)
            text = ""
            for paragraph in document.paragraphs:
                text += paragraph.text + "\n"
            return text[:self.cfg.TEXT_OUTPUT_LIMIT]
        except Exception as e:
            logging.error(f"Error processing DOCX {file_path}: {e}")
            return ""

    def extract_text(self, file_path, max_pages=None):
        """Universal text extraction method."""
        file_ext = os.path.splitext(file_path)[1].lower()

        if file_ext == '.pdf':
            return self.extract_from_pdf(file_path, max_pages)
        elif file_ext in ('.docx', '.doc'):
            return self.extract_from_docx(file_path)
        elif file_ext == '.txt':
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()[:self.cfg.TXT_OUTPUT_LIMIT]
            except Exception as e:
                logging.error(f"Error reading text file {file_path}: {e}")
                return ""
        else:
            return ""
