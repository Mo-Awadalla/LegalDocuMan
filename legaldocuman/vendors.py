"""Vendor name extraction and fuzzy matching.

The SmallLMModel is now the primary vendor extractor — see ml_model.py
and intake.py.  This module keeps the legacy folder/filename cascade and
fuzzy master-list matching as a fallback when the LM is disabled or
returns an empty result.
"""
import logging
import re
from difflib import SequenceMatcher
from typing import Optional

from .utils import normalize_vendor_name

_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE,
)


class VendorExtractor:
    """Folder- and filename-based vendor heuristics + master-list fuzzy match."""

    def __init__(self, vendor_master_list=None):
        self.vendor_master_list = vendor_master_list or []

    def extract_vendor_from_folder(self, folder_name):
        """Extract vendor name from folder name."""
        if not folder_name:
            return None

        # UUID-named folders (e.g. web-upload staging dirs) carry no vendor signal
        if _UUID_RE.match(folder_name.strip()):
            return None

        folder_lower = folder_name.lower().strip()

        generic_folders = [
            'contracts', 'agreements', 'documents', 'files', 'scans', 'pdfs',
            'archive', 'backup', 'temp', 'old', 'new', 'draft', 'final'
        ]
        if folder_lower in generic_folders:
            return None

        suffixes = [
            'contract', 'contracts', 'agreement', 'agreements', 'folder', 'folders',
            'documents', 'docs', 'files', 'archive', 'backup'
        ]

        words = re.split(r'[\s_-]+', folder_lower)
        vendor_words = [word for word in words if word not in suffixes and word.strip()]

        if vendor_words:
            vendor_name = ' '.join(vendor_words)
            logging.info("Vendor metadata inferred from folder")
            return vendor_name

        return folder_name

    def extract_vendor_from_filename(self, filename: str) -> Optional[str]:
        """Best-effort vendor signal from upload filenames such as Acme_MSA_2024.pdf."""
        if not filename:
            return None
        base = re.sub(r'\.[A-Za-z0-9]+$', '', filename)
        tokens = [t for t in re.split(r'[\s_\-]+', base) if t]
        stop = {
            'msa', 'sow', 'nda', 'po', 'contract', 'agreement', 'amendment',
            'license', 'final', 'signed', 'executed', 'draft', 'copy'
        }
        vendor_tokens = []
        for token in tokens:
            if token.lower() in stop or re.fullmatch(r'\d{2,4}', token):
                break
            vendor_tokens.append(token)
        if vendor_tokens:
            return ' '.join(vendor_tokens)
        return None

    def match_vendor_against_master_list(self, vendor_name, threshold=80):
        """Match vendor against master list using fuzzy matching."""
        if not vendor_name or not self.vendor_master_list:
            return vendor_name, 0

        normalized_vendor = normalize_vendor_name(vendor_name)
        best_match = vendor_name
        best_score = 0

        for master_vendor in self.vendor_master_list:
            normalized_master = normalize_vendor_name(master_vendor)
            score = SequenceMatcher(None, normalized_vendor, normalized_master).ratio() * 100

            if normalized_vendor == normalized_master:
                return master_vendor, 100

            if score > best_score and score >= threshold:
                best_match = master_vendor
                best_score = score

        return best_match, best_score

    # ------------------------------------------------------------------
    # Legacy text-pattern extractor — kept as a public alias so callers
    # that imported it (e.g. tests) still work.  The new pipeline uses
    # the SmartReader + SmallLMModel instead.
    # ------------------------------------------------------------------

    def extract_vendor_from_text(self, text: str) -> Optional[str]:
        """Deprecated.  Use SmartReader + SmallLMModel instead."""
        logging.debug("extract_vendor_from_text is deprecated — use SmartReader + SmallLMModel")
        return None
