"""Text extraction from PDF, DOCX, TXT with pluggable OCR backends.

PDFs are processed page-by-page so the SmartReader can progressively widen
the page range without re-rendering.  A single PageRenderer renders pages at
the configured DPI and caches them so the OCR path (front pages) and the
RF-DETR signature path (last pages) share work for short documents.
"""
import logging
import os
from typing import List, Optional, Tuple

from .backends import NvidiaOCRBackend, OCRBackend, TesseractOCRBackend
from .config import Config


class PageRenderer:
    """Render PDF pages to PIL Images and cache them.

    The cache key includes the DPI, so requesting the same page at a different
    DPI does not collide.  We deliberately do *not* use functools.lru_cache on
    instance methods so the cache can be cleared per-document.
    """

    def __init__(self, dpi: Optional[int] = None):
        self.cfg = Config.get()
        self.dpi = dpi or self.cfg.PDF_RENDER_DPI
        self._cache: dict = {}

    def render(self, file_path: str, page_num: int):
        """Render a single 1-indexed page as a PIL Image (cached).

        Returns None if rendering fails.
        """
        key = (os.path.abspath(file_path), page_num, self.dpi)
        if key in self._cache:
            return self._cache[key]
        image = self._render_one(file_path, page_num)
        if image is not None:
            self._cache[key] = image
        return image

    def render_range(self, file_path: str, first_page: int, last_page: int) -> List:
        """Render an inclusive 1-indexed page range.  Failed pages are skipped."""
        images = []
        for n in range(first_page, last_page + 1):
            img = self.render(file_path, n)
            if img is not None:
                images.append(img)
        return images

    def total_pages(self, file_path: str) -> int:
        """Return the number of pages in the PDF, or 0 on error."""
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                return len(pdf.pages)
        except Exception as exc:
            logging.debug(f"total_pages failed for {file_path}: {exc}")
            return 0

    def last_n_offset(self, file_path: str, n: int) -> Tuple[int, int]:
        """Return (first_page_1indexed, page_offset_0indexed) for the last n pages.

        page_offset is the 0-indexed page number of the first returned image
        within the document (used by signature detection for stable page labels).
        """
        total = self.total_pages(file_path)
        if total <= 0:
            return 0, 0
        first_page = max(1, total - n + 1)
        return first_page, first_page - 1

    def _render_one(self, file_path: str, page_num: int):
        try:
            from pdf2image import convert_from_path
        except ImportError:
            logging.debug("pdf2image not installed — cannot render PDF pages")
            return None
        poppler_paths = self.cfg.POPLER_FALLBACK_PATHS.copy()
        if self.cfg.POPLER_PATH:
            poppler_paths.insert(0, self.cfg.POPLER_PATH)
        poppler_paths.append(None)
        for poppler_path in poppler_paths:
            try:
                images = convert_from_path(
                    file_path,
                    dpi=self.dpi,
                    first_page=page_num,
                    last_page=page_num,
                    poppler_path=poppler_path,
                )
                if images:
                    return images[0]
            except Exception:
                continue
        logging.debug(f"Failed to render page {page_num} of {file_path}")
        return None

    def clear_cache(self):
        self._cache.clear()


class TextExtractor:
    """Extract text from various document formats with pluggable OCR.

    For PDFs, extraction is page-by-page:

        list(text_extractor.extract_pages(pdf_path))  # yields (page_num, text)

    The front pages are routed through the shared PageRenderer + OCR backend
    (English only, see Config).  The `extract_text` convenience method still
    returns a single concatenated string and is preserved for back-compat with
    callers that do not need page-level access.
    """

    def __init__(self, ocr_backend: Optional[OCRBackend] = None,
                 page_renderer: Optional[PageRenderer] = None):
        self.cfg = Config.get()
        self.ocr_backend = ocr_backend or self._auto_select_ocr()
        self.ocr_available = self.ocr_backend.is_available() if self.ocr_backend else False
        self.page_renderer = page_renderer or PageRenderer()

    def _auto_select_ocr(self) -> OCRBackend:
        """Pick OCR backend based on env var OCR_BACKEND."""
        backend_name = self.cfg.OCR_BACKEND.lower()
        if backend_name == 'nvidia':
            nvidia = NvidiaOCRBackend()
            if nvidia.is_available():
                return nvidia
            logging.warning("NVIDIA OCR requested but unavailable — falling back to Tesseract")
        return TesseractOCRBackend()

    # ------------------------------------------------------------------
    # Page-by-page PDF access
    # ------------------------------------------------------------------

    def extract_pages(self, file_path: str, max_pages: Optional[int] = None,
                      prefer_ocr: bool = True):
        """Yield (page_num, text) for each page of a PDF.

        Args:
            file_path: Path to the PDF.
            max_pages: Maximum number of pages to yield.
            prefer_ocr: If True, OCR every rendered page (default for the
                SmartReader).  If False, fall back to pdfplumber text and OCR
                only pages that returned no meaningful text — matches the
                legacy behavior of `extract_from_pdf`.
        """
        max_pages = max_pages or self.cfg.PDF_MAX_PAGES
        total = self.page_renderer.total_pages(file_path)
        if total <= 0:
            return
        last_page = min(total, max_pages)
        for page_num in range(1, last_page + 1):
            text = self._extract_one_page(file_path, page_num, prefer_ocr=prefer_ocr)
            yield page_num, text

    def _extract_one_page(self, file_path: str, page_num: int,
                          prefer_ocr: bool = True) -> str:
        """Extract text from a single page, preferring OCR by default."""
        if prefer_ocr and self.ocr_available:
            image = self.page_renderer.render(file_path, page_num)
            if image is not None:
                return self.ocr_backend.image_to_text(image) or ""
            return ""
        # pdfplumber text path — used when OCR is disabled
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                if page_num - 1 < len(pdf.pages):
                    page_text = pdf.pages[page_num - 1].extract_text() or ""
                    if page_text.strip():
                        return page_text
        except Exception as exc:
            logging.debug(f"pdfplumber failed on page {page_num}: {exc}")
        if self.ocr_available:
            image = self.page_renderer.render(file_path, page_num)
            if image is not None:
                return self.ocr_backend.image_to_text(image) or ""
        return ""

    # ------------------------------------------------------------------
    # Legacy interfaces (kept for backward compat)
    # ------------------------------------------------------------------

    def extract_from_pdf(self, file_path, max_pages=None,
                         prefer_ocr: bool = False) -> str:
        """Extract text from PDF.  Returns concatenated text up to TEXT_OUTPUT_LIMIT.

        `prefer_ocr` defaults to False here so the legacy callers keep their
        existing behavior (pdfplumber-first, OCR fallback).  The SmartReader
        uses extract_pages with prefer_ocr=True instead.
        """
        max_pages = max_pages or self.cfg.PDF_MAX_PAGES
        pieces = []
        for _page_num, text in self.extract_pages(file_path, max_pages=max_pages,
                                                  prefer_ocr=prefer_ocr):
            if text and len(text.strip()) > self.cfg.MIN_PAGE_TEXT_LENGTH:
                pieces.append(text)
        text = "\n".join(pieces)
        if (not text or len(text.strip()) < self.cfg.MIN_MEANINGFUL_TEXT_LENGTH) \
                and self.ocr_available and not prefer_ocr:
            text = self.ocr_backend.pdf_to_text(
                file_path,
                first_page=1,
                last_page=min(max_pages, self.cfg.OCR_MAX_PAGES),
            )
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
