# LegalDocuMan

Intelligent document processing for contracts, agreements, and legal documents. Extracts text, classifies document types, detects signatures, and organizes files automatically.

## Features

- **Document Classification** — auto-detects MSA, SOW, NDA, PO, Amendment, License
- **Signature Detection** — keyword-based scanning for digital, physical, and e-signature platforms
- **Smart Naming** — `K_VendorName_documentType_001.pdf` or `YYYYMMDD_Vendor_Original.pdf`
- **Folder Organization** — `_final` (signed) vs `_supporting` (unsigned)
- **Date Extraction** — effective, expiration, renewal, and review dates from content
- **Vendor Matching** — fuzzy match against a master vendor list
- **Pluggable OCR Backends** — Tesseract (default) or NVIDIA (NeMo / Triton / TAO)
- **Backend Tracking** — JSON registry with expiration tracking and retention categories

## Install

```bash
git clone https://github.com/Mo-Awadalla/LegalDocuMan.git
cd LegalDocuMan
pip install -r requirements.txt
```

### Optional: OCR support

**Tesseract (local, free):**
```bash
# macOS
brew install tesseract poppler

# Ubuntu/Debian
sudo apt-get install tesseract-ocr poppler-utils

# Then uncomment OCR lines in requirements.txt and reinstall
pip install pytesseract pdf2image Pillow
```

**NVIDIA OCR (API-based):**
```bash
# 1. Uncomment requests in requirements.txt
# 2. Set your API key in .env
pip install -r requirements.txt
```

## Configuration

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OCR_BACKEND` | `tesseract` | `tesseract` or `nvidia` |
| `NVIDIA_API_KEY` | — | Your NVIDIA API key |
| `NVIDIA_API_BASE_URL` | `https://integrate.api.nvidia.com/v1` | NVIDIA API endpoint |
| `NVIDIA_OCR_MODEL` | `nvidia/nemotron-ocr-v2` | Model identifier |
| `TESSERACT_PATH` | auto-detect | Override Tesseract binary path |
| `POPLER_PATH` | auto-detect | Override Poppler binary path |

`.env` is gitignored — never commit it.

## Usage

```python
from legaldocuman import DocumentProcessor

processor = DocumentProcessor("/path/to/contracts")
processor.process_contracts_enhanced()
processor.print_summary()
```

### With NVIDIA OCR

```python
from legaldocuman import DocumentProcessor
from legaldocuman.backends import NvidiaOCRBackend

ocr = NvidiaOCRBackend()
processor = DocumentProcessor("/path/to/contracts", ocr_backend=ocr)
processor.process_contracts_enhanced()
```

Or set the env var:
```bash
export OCR_BACKEND=nvidia
export NVIDIA_API_KEY=nvapi-your-key-here
python your_script.py
```

### Sort files by year

```python
processor = DocumentProcessor("/path/to/contracts")
processor.sort_files_by_year("/path/to/archive", year_threshold=2017)
```

## Project Structure

```
LegalDocuMan/
├── legaldocuman/              # Main package
│   ├── config.py              # Centralized config (env vars, constants)
│   ├── processor.py           # DocumentProcessor orchestrator
│   ├── extractors.py          # TextExtractor (PDF, DOCX, TXT + OCR)
│   ├── classifiers.py         # DocumentTypeClassifier + DocumentStatusClassifier
│   ├── dates.py               # DateExtractor
│   ├── vendors.py             # VendorExtractor
│   ├── utils.py               # File ops, naming, hashing
│   └── backends/              # Pluggable OCR backends
│       ├── base.py            # OCRBackend ABC
│       ├── tesseract.py       # Tesseract + pdf2image
│       └── nvidia.py          # NVIDIA OCR stub (fill in your API calls)
├── tests/                     # Pytest suite (129 tests)
├── .env.example               # Env var template
├── requirements.txt           # Dependencies
└── README.md                  # This file
```

## Running Tests

```bash
pytest tests/ -v
```

All tests mock heavy dependencies (Tesseract, pdfplumber, PIL) so they run fast without system installs.

## Document Types

| Type | Abbreviation | Description |
|------|-------------|-------------|
| MSA | AGMT | Master Service Agreement |
| SOW | AGMT | Statement of Work |
| NDA | AGMT | Non-Disclosure Agreement |
| PO | K | Purchase Order |
| AMD | AMD | Amendment |
| LICENSE | K | License Agreement |
| CONTRACT | K | General Contract |

## Retention Categories

| Category | Document Types | Duration |
|----------|---------------|----------|
| `long_term` | MSA / Contract / Agreement (with expiration) | 7+ years |
| `indefinite` | NDA, License | Permanent |
| `contracts` | SOW | Tied to parent MSA |
| `short_term` | PO, Invoice | 3-7 years |
| `tied_to_parent` | Amendment | Same as parent |
| `review_required` | Unknown / uncategorized | Manual review |

## License

MIT
