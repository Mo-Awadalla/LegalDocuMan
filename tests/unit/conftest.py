"""Unit-only isolation for optional/heavy document dependencies."""
import sys
from unittest.mock import MagicMock

for module in ("pdfplumber", "docx", "pandas", "pytesseract", "pdf2image", "PIL", "PIL.Image"):
    sys.modules.setdefault(module, MagicMock())

# Explicit attributes survive pytest monkeypatch undo on Python 3.11; lazily
# generated MagicMock children are deleted after the first patched test.
dateparser = sys.modules.setdefault(
    "dateparser", MagicMock(parse=MagicMock(), search=MagicMock(search_dates=MagicMock()))
)
sys.modules.setdefault("dateparser.search", dateparser.search)
