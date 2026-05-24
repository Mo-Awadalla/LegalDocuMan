"""Vendor name extraction and fuzzy matching."""
import logging
import re
from difflib import SequenceMatcher
from typing import List, Optional, Tuple

from .utils import normalize_vendor_name

_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE,
)


class VendorExtractor:
    """Extract and normalize vendor names."""

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
            logging.info(f"Extracted vendor '{vendor_name}' from folder '{folder_name}'")
            return vendor_name

        return folder_name

    def extract_vendor_from_text(self, text: str) -> Optional[str]:
        """Extract the counterparty name from contract body text.

        Searches the opening preamble (first 3 000 chars) for the most common
        patterns used to introduce parties in professional-services and vendor
        agreements.  Returns the first plausible match, or None.
        """
        if not text:
            return None

        preamble = text[:3000]

        patterns = [
            # "and ACME CORP, hereinafter called …"
            r'and\s+((?:[A-Z][A-Za-z0-9&\s,\.\']+?){1,8}?)[,\s]+hereinafter\s+(?:called|referred)',
            # "between … and ACME CORP ("
            r'between[^.]{0,300}?and\s+((?:[A-Z][A-Za-z0-9&\s,\.\']+?){1,6}?)\s*\(',
            # "ACME CORP, a California corporation"
            r'((?:[A-Z][A-Z0-9&\s,\.\']{4,60}?)),\s+a\s+\w+\s+(?:corporation|company|llc|partnership|limited)',
        ]

        for pattern in patterns:
            match = re.search(pattern, preamble)
            if match:
                candidate = match.group(1).strip().rstrip(',').strip()
                words = candidate.split()
                if len(words) >= 1 and len(candidate) > 3:
                    logging.info(f"Extracted vendor '{candidate}' from document text")
                    return candidate

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
