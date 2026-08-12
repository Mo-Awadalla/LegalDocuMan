"""Unit-only isolation for optional/heavy document dependencies."""
import sys
from unittest.mock import MagicMock

for module in ("pdfplumber", "docx", "pandas", "pytesseract", "pdf2image", "PIL", "PIL.Image"):
    sys.modules.setdefault(module, MagicMock())

dateparser = sys.modules.setdefault("dateparser", MagicMock())
sys.modules.setdefault("dateparser.search", dateparser.search)
