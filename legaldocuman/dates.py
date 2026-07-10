"""Date extraction from documents and filenames."""
import logging
import re
from datetime import datetime
from typing import Optional, List, Tuple

from .config import Config


class DateExtractor:
    """Extract dates from documents and filenames."""

    def __init__(self):
        self.cfg = Config.get()
        self.date_patterns = [
            r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b',
            r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b',
            r'\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b',
            r'\beffective\s+(?:date\s+)?(?:of\s+)?(?:as\s+of\s+)?(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b',
            r'\b(20[0-3][0-9]|19[9][0-9])\b'  # Years 1990-2039
        ]

    def extract_date_from_text(self, text, filename=None):
        """Extract date using dateparser for better accuracy."""
        try:
            from dateparser.search import search_dates
        except ImportError:
            logging.warning("dateparser not installed — date extraction limited")
            return None

        candidates = []

        if text:
            results = search_dates(text, settings={'PREFER_DAY_OF_MONTH': 'first'})
            if results:
                candidates.extend([dt for _, dt in results])

        if filename:
            results = search_dates(filename, settings={'PREFER_DAY_OF_MONTH': 'first'})
            if results:
                candidates.extend([dt for _, dt in results])

        candidates = [dt.replace(tzinfo=None) if dt.tzinfo else dt for dt in candidates]
        candidates = [
            dt for dt in candidates
            if self.cfg.MIN_YEAR <= dt.year <= self.cfg.MAX_YEAR_FILENAME
        ]

        if candidates:
            best_date = max(candidates)
            return best_date.strftime('%Y%m%d')

        return None

    def extract_dates_with_metadata(self, text):
        """Extract dates with additional metadata for backend record keeping."""
        try:
            import dateparser
        except ImportError:
            logging.warning("dateparser not installed — metadata extraction limited")
            return {
                'effective_date': None, 'expiration_date': None,
                'signature_date': None, 'renewal_date': None,
                'termination_date': None, 'review_date': None
            }

        metadata = {
            'effective_date': None, 'expiration_date': None,
            'signature_date': None, 'renewal_date': None,
            'termination_date': None, 'review_date': None
        }

        effective_patterns = [
            r'effective\s+(?:date\s+)?(?:of\s+)?(?:as\s+of\s+)?([^\.;\n]+)',
            r'commencing\s+(?:on\s+)?([^\.;\n]+)',
            r'beginning\s+(?:on\s+)?([^\.;\n]+)',
            r'starts?\s+(?:on\s+)?([^\.;\n]+)',
            r'in\s+effect\s+(?:as\s+of\s+)?([^\.;\n]+)'
        ]

        expiration_patterns = [
            r'expir(?:es|ation)\s+(?:date\s+)?(?:on\s+)?([^\.;\n]+)',
            r'terminat(?:es|ion)\s+(?:date\s+)?(?:on\s+)?([^\.;\n]+)',
            r'end(?:s|ing)\s+(?:on\s+)?([^\.;\n]+)',
            r'shall\s+(?:expire|terminate)\s+(?:on\s+)?([^\.;\n]+)',
            r'valid\s+(?:through|until)\s+([^\.;\n]+)',
            r'term\s+(?:expires|ends)\s+(?:on\s+)?([^\.;\n]+)',
            r'contract\s+(?:expires|terminates)\s+(?:on\s+)?([^\.;\n]+)',
            r'agreement\s+(?:expires|terminates)\s+(?:on\s+)?([^\.;\n]+)',
            r'this\s+agreement\s+shall\s+remain\s+in\s+effect\s+until\s+([^\.;\n]+)'
        ]

        renewal_patterns = [
            r'renew(?:al|s)?\s+(?:date\s+)?(?:on\s+)?([^\.;\n]+)',
            r'automatically\s+renew(?:s|ed)?\s+(?:on\s+)?([^\.;\n]+)',
            r'renewal\s+period\s+(?:begins|starts)\s+([^\.;\n]+)'
        ]

        termination_patterns = [
            r'termination\s+date\s+(?:is\s+|of\s+|on\s+)?([^\.;\n]+)',
            r'shall\s+terminate\s+on\s+([^\.;\n]+)',
            r'terminates\s+on\s+([^\.;\n]+)'
        ]

        review_patterns = [
            r'review\s+(?:date\s+)?(?:on\s+)?([^\.;\n]+)',
            r'shall\s+be\s+reviewed\s+(?:on\s+)?([^\.;\n]+)',
            r'subject\s+to\s+review\s+(?:on\s+)?([^\.;\n]+)'
        ]

        metadata['effective_date'] = self._extract_first_date(text, effective_patterns, dateparser)
        metadata['expiration_date'] = self._extract_first_date(text, expiration_patterns, dateparser)
        metadata['renewal_date'] = self._extract_first_date(text, renewal_patterns, dateparser)
        metadata['termination_date'] = self._extract_first_date(text, termination_patterns, dateparser)
        metadata['review_date'] = self._extract_first_date(text, review_patterns, dateparser)

        dates_found = [k for k, v in metadata.items() if v is not None]
        if dates_found:
            logging.info(f"📋 Backend tracking dates captured: {', '.join(dates_found)}")
        else:
            logging.warning("⚠️  No dates found for backend tracking")

        return metadata

    def _extract_first_date(self, text, patterns, dateparser_module, max_matches=3):
        """Helper: extract the first valid date from a list of regex patterns."""
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:max_matches]:
                parsed = dateparser_module.parse(match.strip())
                if parsed and self.cfg.MIN_YEAR <= parsed.year <= self.cfg.MAX_YEAR:
                    return parsed.strftime('%Y-%m-%d')
        return None
