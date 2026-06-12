"""RF-DETR visual signature detection backend."""
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class SignatureDetectorBackend(ABC):
    """Pluggable visual signature detector interface."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this backend is ready."""
        ...

    @abstractmethod
    def detect(self, images: list, page_offset: int = 0) -> List[Dict[str, Any]]:
        """Run inference on PIL Images.

        Returns list of dicts: {"page": int, "confidence": float, "bbox": [x1,y1,x2,y2], "source": str}
        Only detections above the configured threshold are returned.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable backend name."""
        ...


class RFDETRSignatureBackend(SignatureDetectorBackend):
    """Signature detector backed by a fine-tuned RF-DETR model.

    Loads the model eagerly at instantiation so per-document inference
    has zero startup latency.
    """

    def __init__(self, model_path: str, detection_threshold: float = 0.35):
        self._threshold = detection_threshold
        self._model = None
        self._load(model_path)

    def _load(self, model_path: str) -> None:
        if not os.path.exists(model_path):
            logging.error(f"RF-DETR model not found: {model_path}")
            return
        try:
            from rfdetr import from_checkpoint
            # rfdetr manages device placement internally via ModelContext;
            # do not call .to() or .eval() on the returned object.
            self._model = from_checkpoint(str(model_path))
            logging.info(f"RF-DETR signature detector loaded from {model_path}")
        except Exception as exc:
            logging.error(f"RF-DETR model load failed: {exc}")

    def is_available(self) -> bool:
        return self._model is not None

    @property
    def name(self) -> str:
        return "rfdetr"

    def detect(self, images: list, page_offset: int = 0) -> List[Dict[str, Any]]:
        """Detect handwritten signatures in a list of PIL Images.

        Args:
            images: PIL Images for the pages to inspect (e.g. last 5 pages).
            page_offset: 0-indexed page number of images[0] in the source document.

        Returns:
            Detections above self._threshold, each as:
            {"page": int, "confidence": float, "bbox": [x1, y1, x2, y2], "source": "rfdetr"}
        """
        if not self.is_available():
            return []

        results = []
        for i, img in enumerate(images):
            page_num = page_offset + i
            try:
                dets = self._model.predict(
                    img,
                    threshold=self._threshold,
                    include_source_image=False,
                )
                if dets is None or len(dets) == 0:
                    continue
                for j in range(len(dets.xyxy)):
                    results.append({
                        "page": page_num,
                        "confidence": round(float(dets.confidence[j]), 4),
                        "bbox": [round(v, 2) for v in dets.xyxy[j].tolist()],
                        "source": "rfdetr",
                    })
            except Exception as exc:
                logging.warning(f"RF-DETR inference failed on page {page_num}: {exc}")
        return results

    def detect_with_renderer(self, file_path: str, page_renderer, last_n: int) -> List[Dict[str, Any]]:
        """Convenience wrapper that uses a shared PageRenderer.

        Renders the last `last_n` pages through `page_renderer` (so the
        same rendered image is reused if the SmartReader already rendered
        it for OCR) and runs the detector.
        """
        if not self.is_available() or page_renderer is None:
            return []
        first_page, page_offset = page_renderer.last_n_offset(file_path, last_n)
        if first_page == 0:
            return []
        images = page_renderer.render_range(file_path, first_page, first_page + last_n - 1)
        return self.detect(images, page_offset=page_offset)
