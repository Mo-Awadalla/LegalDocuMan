"""NVIDIA OCR backend stub — wire in your actual NVIDIA API here."""
import logging
import os
from typing import Optional

from .base import OCRBackend
from ..config import Config


class NvidiaOCRBackend(OCRBackend):
    """NVIDIA OCR backend.

    Default wiring targets NVIDIA's inference APIs (NeMo, Triton, TAO, etc.).
    Set env vars before use:
        export NVIDIA_API_KEY="your_key"
        export NVIDIA_API_BASE_URL="https://api.nvidia.com/v1/..."
        export NVIDIA_OCR_MODEL="nvidia/nemotron-ocr-v2"

    TODO: Replace the stubbed methods below with real NVIDIA API calls.
    """

    def __init__(self, config: Optional[Config] = None):
        self.cfg = config or Config.get()
        self._client = None
        self._available = False
        self._init_client()

    def _init_client(self):
        """Try to initialise the NVIDIA client."""
        # TODO: import your actual NVIDIA SDK here
        # Example:
        #   from nvidia_ocr import NvidiaOCRClient
        #   self._client = NvidiaOCRClient(
        #       api_key=self.cfg.NVIDIA_API_KEY,
        #       base_url=self.cfg.NVIDIA_API_BASE_URL,
        #       model=self.cfg.NVIDIA_OCR_MODEL,
        #   )
        #   self._available = True
        if not self.cfg.NVIDIA_API_KEY:
            logging.warning("NVIDIA_API_KEY not set — NVIDIA OCR unavailable")
            return
        # Stub: pretend available for demo purposes
        self._available = True
        logging.info("NVIDIA OCR backend initialised (stub mode)")

    # ------------------------------------------------------------------
    # OCRBackend implementation
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        return self._available

    @property
    def name(self) -> str:
        return f"NVIDIA ({self.cfg.NVIDIA_OCR_MODEL})"

    def image_to_text(self, image) -> str:
        if not self._available:
            return ""
        # TODO: Replace with real NVIDIA image OCR call
        # Example:
        #   return self._client.ocr_image(image)
        logging.debug("NvidiaOCRBackend.image_to_text() called (stub)")
        return ""

    def pdf_to_text(self, file_path: str, first_page: int = 1, last_page: Optional[int] = None) -> str:
        if not self._available:
            return ""
        # TODO: Replace with real NVIDIA PDF OCR call
        # Options:
        #   1. Convert PDF to images locally (Poppler) then batch-OCR via NVIDIA API
        #   2. Upload PDF directly if the API supports it
        #   3. Use NVIDIA Triton with an ONNX/TensorRT OCR model
        logging.debug("NvidiaOCRBackend.pdf_to_text() called (stub)")
        return ""
