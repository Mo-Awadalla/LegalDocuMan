"""SmartReader: progressive page-by-page OCR with regex-based region finding.

The SmartReader does two things in one pass:

1. It walks the front of the document starting at page 1, reading 2 pages
   at a time, OCR-ing each one through the shared `PageRenderer` and
   `TextExtractor`.  This guarantees the same rendered image is reused by
   the RF-DETR signature detector on the last pages — no double work for
   short documents.

2. It runs the existing vendor preamble regex over the running text.  As
   soon as the regex finds a match (or the cumulative text crosses the
   configured length threshold), it stops widening.  This keeps the LM
   input within the 512-token window and avoids burning OCR cycles on
   boilerplate that doesn't carry vendor signal.

The output is a focused text snippet ready to be fed to the SmallLMModel.
"""
import logging
import os
import re
from typing import Optional, Tuple

from .config import Config
from .extractors import PageRenderer, TextExtractor

# Vendor preamble regex patterns lifted from the legacy VendorExtractor.
# They are reused here as a *region finder* — wherever any of these
# patterns match, we keep the surrounding text for the LM.  We are not
# asking the regex for the final answer anymore; the LM will do that.
_REGION_PATTERNS = [
    re.compile(
        r'and\s+((?:[A-Z][A-Za-z0-9&\s,\.\']+?){1,8}?)[,\s]+hereinafter\s+(?:called|referred)',
        re.IGNORECASE,
    ),
    re.compile(
        r'between[^.]{0,300}?and\s+((?:[A-Z][A-Za-z0-9&\s,\.\']+?){1,6}?)\s*\(',
        re.IGNORECASE,
    ),
    re.compile(
        r'((?:[A-Z][A-Z0-9&\s,\.\']{4,60}?)),\s+a\s+\w+\s+(?:corporation|company|llc|partnership|limited)',
        re.IGNORECASE,
    ),
    # Doc-type title-line patterns (kept short — the LM is the source of truth).
    re.compile(
        r'(master\s+service\s+agreement|statement\s+of\s+work|non[-\s]?disclosure\s+agreement|'
        r'purchase\s+order|amendment|license\s+agreement)',
        re.IGNORECASE,
    ),
]


class SmartReader:
    """Progressively OCR a PDF's front pages and return a focused snippet.

    Returns a tuple (text, region_found, pages_read) where:
        text          — concatenated OCR text from the pages we read
        region_found  — True if any preamble/title regex matched
        pages_read    — number of pages actually OCR'd
    """

    def __init__(self, text_extractor: Optional[TextExtractor] = None,
                 page_renderer: Optional[PageRenderer] = None):
        self.cfg = Config.get()
        self.text_extractor = text_extractor or TextExtractor(page_renderer=page_renderer)
        # Reuse the extractor's renderer so we share cache with signature detection.
        self.page_renderer = page_renderer or self.text_extractor.page_renderer

    def read(self, file_path: str) -> Tuple[str, bool, int]:
        """Read the front pages of a PDF, widening until signal is found."""
        if not file_path or not os.path.exists(file_path):
            return "", False, 0
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.pdf':
            return self._read_pdf(file_path)
        # DOCX/TXT: read once, no progressive widening.
        if ext in ('.docx', '.doc'):
            text = self.text_extractor.extract_from_docx(file_path)
            return text, self._has_region(text), 0
        if ext == '.txt':
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()[:self.cfg.TXT_OUTPUT_LIMIT]
            except Exception as exc:
                logging.debug("TXT read failed (error_type=%s)", exc.__class__.__name__)
                return "", False, 0
            return text, self._has_region(text), 0
        return "", False, 0

    def _read_pdf(self, file_path: str) -> Tuple[str, bool, int]:
        total = self.page_renderer.total_pages(file_path)
        if total <= 0:
            return "", False, 0

        max_pages = min(self.cfg.SMALL_LM_MAX_PAGES, total)
        initial = min(self.cfg.SMALL_LM_INITIAL_PAGES, max_pages)
        min_text = self.cfg.SMALL_LM_MIN_TEXT_LENGTH

        accumulated = ""
        region_found = False
        pages_read = 0

        # Progressive widening: read `initial` pages, check signal, widen
        # by 1 page at a time if we have not found a region and the text
        # is below `min_text`.  This matches the spec — start with 2,
        # widen up to ~7.
        next_stop = initial
        last_page = 0
        while last_page < max_pages:
            stop = min(next_stop, max_pages)
            for page_num in range(last_page + 1, stop + 1):
                _pn, text = next(self.text_extractor.extract_pages(
                    file_path, max_pages=stop, prefer_ocr=True
                )) if False else self._extract_one(file_path, page_num)
                pages_read += 1
                if text:
                    accumulated += text + "\n"
            last_page = stop

            if not accumulated.strip():
                # OCR produced nothing — keep widening to the end.
                if stop >= max_pages:
                    break
                next_stop = stop + 1
                continue

            region_found = self._has_region(accumulated)
            if region_found:
                break
            if len(accumulated.strip()) >= min_text and stop >= initial:
                # Enough text to give the LM a shot, even if no explicit
                # preamble was found.
                break
            if stop >= max_pages:
                break
            next_stop = stop + 1

        return accumulated.strip(), region_found, pages_read

    def _extract_one(self, file_path: str, page_num: int) -> Tuple[int, str]:
        """Read a single page and return (page_num, text)."""
        image = self.page_renderer.render(file_path, page_num)
        if image is None or not self.text_extractor.ocr_available:
            return page_num, ""
        ocr = getattr(self.text_extractor.ocr_backend, "ocr_page", None)
        if ocr is None:
            ocr = self.text_extractor.ocr_backend.image_to_text
        try:
            return page_num, ocr(image) or ""
        except Exception as exc:
            logging.debug("OCR failed on page %s (error_type=%s)", page_num, exc.__class__.__name__)
            return page_num, ""

    @staticmethod
    def _has_region(text: str) -> bool:
        if not text:
            return False
        for pattern in _REGION_PATTERNS:
            if pattern.search(text):
                return True
        return False
