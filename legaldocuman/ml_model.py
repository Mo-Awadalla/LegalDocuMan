"""Small LM for document type + vendor extraction.

Wraps a local FLAN-T5-small (or fine-tuned derivative) checkpoint.  The
model is text-to-text: given a focused text snippet, it emits a single
short line that we parse into a {"doc_type", "vendor"} dict.

Design notes
------------
* Local-first: the model is loaded from `Config.SMALL_LM_MODEL_NAME` (a
  fine-tuned checkpoint directory).  If the directory does not exist we
  fall back to `Config.SMALL_LM_BASE_MODEL` (HuggingFace id).  This lets
  the system run out-of-the-box before fine-tuning has happened.
* Lazy load: the model is loaded on first call to `analyze()` to keep
  import-time side effects to a minimum.
* Graceful failure: any error during inference (missing weights, OOM,
  malformed output) returns a dict with empty values so the caller can
  fall back to the legacy regex pipeline.
"""
import json
import logging
import os
import re
from typing import Any, Dict, Optional

from .config import Config

# The labels the LM is allowed to emit for doc_type.  Kept in sync with
# Config.TYPE_ABBREVIATIONS keys.
_VALID_DOC_TYPES = {"MSA", "SOW", "NDA", "PO", "AMD", "LICENSE", "CONTRACT"}

# Prompt — kept short so it leaves room for the snippet inside the
# 512-token FLAN-T5 window.  Tested on the base model; the fine-tuned
# model should learn to ignore the prompt entirely and emit the answer
# in the same form it was trained on.
_INSTRUCTION = (
    "Extract the document type and vendor name from the contract text. "
    "Reply as JSON with keys doc_type and vendor. doc_type is one of "
    "MSA, SOW, NDA, PO, AMD, LICENSE, CONTRACT. "
    "Text: "
)


class SmallLMModel:
    """Wrapper around a local seq2seq model for {doc_type, vendor} prediction."""

    def __init__(self, model_name: Optional[str] = None,
                 base_model: Optional[str] = None,
                 enabled: Optional[bool] = None):
        self.cfg = Config.get()
        self.model_name = model_name or self.cfg.SMALL_LM_MODEL_NAME
        self.base_model = base_model or self.cfg.SMALL_LM_BASE_MODEL
        self.enabled = enabled if enabled is not None else self.cfg.SMALL_LM_ENABLED
        self._tokenizer = None
        self._model = None
        self._load_error: Optional[str] = None

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return True if the model is loaded (or loadable) and enabled."""
        if not self.enabled:
            return False
        if self._model is not None:
            return True
        try:
            self._ensure_loaded()
        except Exception:
            return False
        return self._model is not None

    def _resolve_checkpoint(self) -> str:
        """Prefer the local fine-tuned checkpoint, fall back to the HF base model."""
        if self.model_name and os.path.isdir(self.model_name):
            return self.model_name
        return self.base_model

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        if not self.enabled:
            return
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as exc:
            self._load_error = (
                "transformers/torch not installed — small LM disabled"
            )
            logging.error(self._load_error + f" ({exc})")
            return

        checkpoint = self._resolve_checkpoint()
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(checkpoint)
            self._model = AutoModelForSeq2SeqLM.from_pretrained(checkpoint)
            self._model.eval()
            logging.info("Small language model loaded")
        except Exception as exc:
            self._load_error = f"Failed to load small LM from {checkpoint}: {exc}"
            logging.error(self._load_error)
            self._model = None
            self._tokenizer = None

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def analyze(self, text: str) -> Dict[str, Any]:
        """Run inference on `text` and return {"doc_type": str, "vendor": str}.

        Returns empty strings on any failure so the caller can fall back
        to the legacy regex pipeline.
        """
        if not self.enabled or not text:
            return {"doc_type": "", "vendor": ""}
        try:
            self._ensure_loaded()
        except Exception as exc:
            logging.debug(f"SmallLMModel load failed: {exc}")
            return {"doc_type": "", "vendor": ""}
        if self._model is None or self._tokenizer is None:
            return {"doc_type": "", "vendor": ""}

        snippet = self._truncate(text, self.cfg.SMALL_LM_MAX_INPUT_CHARS)
        prompt = _INSTRUCTION + snippet
        try:
            import torch
            inputs = self._tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=512,
            )
            with torch.no_grad():
                output_ids = self._model.generate(
                    **inputs,
                    max_new_tokens=64,
                    num_beams=4,
                    early_stopping=True,
                )
            raw = self._tokenizer.decode(output_ids[0], skip_special_tokens=True)
        except Exception as exc:
            logging.debug(f"SmallLMModel inference failed: {exc}")
            return {"doc_type": "", "vendor": ""}

        return self._parse_output(raw)

    @staticmethod
    def _truncate(text: str, max_chars: int) -> str:
        if not text or len(text) <= max_chars:
            return text or ""
        return text[:max_chars]

    @staticmethod
    def _parse_output(raw: str) -> Dict[str, str]:
        """Parse the model's free-form text into a structured dict.

        Tries JSON first, then falls back to a regex over common forms the
        fine-tuned model is expected to emit.
        """
        if not raw:
            return {"doc_type": "", "vendor": ""}
        candidate = raw.strip()

        # 1) Strict JSON
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                doc_type = str(data.get("doc_type", "")).strip().upper()
                vendor = str(data.get("vendor", "")).strip()
                if doc_type in _VALID_DOC_TYPES or doc_type == "":
                    return {"doc_type": doc_type, "vendor": vendor}
        except (ValueError, TypeError):
            pass

        # 2) JSON-ish substring (e.g. "{\"doc_type": "MSA", "vendor": ...}")
        match = re.search(r"\{[^}]*\}", candidate)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, dict):
                    doc_type = str(data.get("doc_type", "")).strip().upper()
                    vendor = str(data.get("vendor", "")).strip()
                    if doc_type in _VALID_DOC_TYPES or doc_type == "":
                        return {"doc_type": doc_type, "vendor": vendor}
            except (ValueError, TypeError):
                pass

        # 3) Key/value regex — handles the fine-tuned format and the
        #    base model's natural-language responses.
        doc_type = ""
        vendor = ""
        type_match = re.search(
            r"doc[_\s-]?type\s*[:=]\s*([A-Za-z]+)", candidate, re.IGNORECASE
        )
        if type_match:
            doc_type = type_match.group(1).strip().upper()
        vendor_match = re.search(
            r"vendor\s*[:=]\s*([^\n,;]+)", candidate, re.IGNORECASE
        )
        if vendor_match:
            vendor = vendor_match.group(1).strip().strip('"').strip("'").rstrip(".")

        if doc_type and doc_type not in _VALID_DOC_TYPES:
            doc_type = ""
        return {"doc_type": doc_type, "vendor": vendor}
