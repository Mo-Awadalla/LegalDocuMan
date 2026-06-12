"""Tesseract + pdf2image OCR backend."""
import logging
import os
from typing import Optional

from ..config import Config
from .base import OCRBackend


class TesseractOCRBackend(OCRBackend):
    """OCR via Tesseract + pdf2image + Poppler."""

    def __init__(self, config: Optional[Config] = None):
        self.cfg = config or Config.get()
        self._tesseract = None
        self._convert_from_path = None
        self._available = False
        self._init_tesseract()

    def _init_tesseract(self):
        """Try to import and configure Tesseract."""
        try:
            import pytesseract
            from pdf2image import convert_from_path
            self._tesseract = pytesseract
            self._convert_from_path = convert_from_path
            self._configure_tesseract(pytesseract)
            self._available = True
        except ImportError:
            logging.debug("Tesseract/pytesseract not installed")
            self._available = False

    def _configure_tesseract(self, pytesseract):
        """Set Tesseract command path from env or fallbacks."""
        if self.cfg.TESSERACT_PATH and os.path.exists(self.cfg.TESSERACT_PATH):
            pytesseract.pytesseract.tesseract_cmd = self.cfg.TESSERACT_PATH
            return
        for path in self.cfg.TESSERACT_FALLBACK_PATHS:
            try:
                if path == 'tesseract' or os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    return
            except Exception:
                continue

    # ------------------------------------------------------------------
    # OCRBackend implementation
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        return self._available

    @property
    def name(self) -> str:
        return "Tesseract"

    def image_to_text(self, image) -> str:
        if not self._available:
            return ""
        try:
            return self._tesseract.image_to_string(image) or ""
        except Exception as e:
            logging.debug(f"Tesseract OCR error on image: {e}")
            return ""

    def ocr_page(self, image) -> str:
        """Alias for image_to_text — used by the SmartReader's per-page loop."""
        return self.image_to_text(image)

    def pdf_to_text(self, file_path: str, first_page: int = 1, last_page: Optional[int] = None) -> str:
        if not self._available:
            return ""

        images = self._convert_pdf_to_images(file_path, first_page, last_page)
        if images is None:
            return ""

        texts = []
        for img in images:
            try:
                page_text = self.image_to_text(img)
                texts.append(page_text)
            except Exception as e:
                logging.debug(f"Tesseract OCR error on page: {e}")
                continue
        return "\n".join(texts)

    def _convert_pdf_to_images(self, file_path: str, first_page: int, last_page: Optional[int]):
        """Try Poppler paths until one works."""
        poppler_paths = self.cfg.POPLER_FALLBACK_PATHS.copy()
        if self.cfg.POPLER_PATH:
            poppler_paths.insert(0, self.cfg.POPLER_PATH)
        poppler_paths.append(None)  # Let pdf2image auto-find

        for poppler_path in poppler_paths:
            try:
                return self._convert_from_path(
                    file_path,
                    poppler_path=poppler_path,
                    first_page=first_page,
                    last_page=last_page,
                )
            except Exception:
                continue
        logging.error("Could not convert PDF to images — check Poppler installation")
        return None
