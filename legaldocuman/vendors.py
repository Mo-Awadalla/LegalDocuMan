"""Vendor name extraction and fuzzy matching."""
import logging
import re
from difflib import SequenceMatcher
from typing import List, Optional, Tuple

from .utils import normalize_vendor_name


class VendorExtractor:
    """Extract and normalize vendor names."""

    def __init__(self, vendor_master_list=None):
        self.vendor_master_list = vendor_master_list or []

    def extract_vendor_from_folder(self, folder_name):
        """Extract vendor name from folder name."""
        if not folder_name:
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
