# LegalDocuMan

Intelligent document processing for contracts, agreements, and legal documents. Extracts text, classifies document types, detects execution status, and organizes files automatically.

## Features

- **Document Classification** — auto-detects MSA, SOW, NDA, PO, Amendment, License
- **Execution Status Detection** — deterministic regex-based classifier using execution-language patterns ("in witness whereof", "digitally signed by", signature blocks, e-signature platforms) to distinguish executed (`_final`) from non-executed (`_supporting`) documents
- **Smart Naming** — `K_VendorName_documentType_001.pdf` or `YYYYMMDD_Vendor_Original.pdf`
- **Folder Organization** — `_final` (executed) vs `_supporting` (unsigned / draft / exhibit)
- **Date Extraction** — effective, expiration, renewal, and review dates from content
- **Vendor Matching** — fuzzy match against a master vendor list
- **Pluggable OCR Backends** — Tesseract (default, local) or NVIDIA (NeMo / Triton / TAO, stub ready)
- **Retention Category Mapping** — auto-assigns retention policies (long_term, indefinite, short_term, tied_to_parent)

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
├── tests/                     # Pytest suite (106 tests, 69% coverage)
├── .env.example               # Env var template
├── requirements.txt           # Dependencies
└── README.md                  # This file
```

## Running Tests

```bash
pytest tests/ -v
```

Coverage report:
```bash
pytest tests/ --cov=legaldocuman --cov-report=term-missing
```

All tests mock heavy dependencies (Tesseract, pdfplumber, PIL) so they run fast without system installs. See [Known Limitations](#known-limitations) for integration test status.

## Design Decisions

This system was built for **NYCEM (New York City Emergency Management)**, processing 16,000+ real legal contracts containing privileged party names, signatures, and sensitive terms. The architecture reflects the institutional constraints of a government agency:

- **Deterministic classifiers over ML models** — Regex-based document type and execution status detection were chosen because every classification decision must be explainable and defensible in a government audit. A CNN that says "this looks signed" is not auditable; a rule that says "the text contains 'IN WITNESS WHEREOF' and a signature block" is.

- **No third-party cloud ML** — Data governance policy prohibited sending legal documents to external ML APIs (OpenAI, cloud CV services). All processing runs locally on agency infrastructure.

- **No ML infrastructure** — The agency had no GPUs, model versioning, or ML ops pipeline. Building and maintaining a computer vision model was not feasible.

- **Pluggable backend architecture** — The `OCRBackend` abstract base class and `NvidiaOCRBackend` stub exist so that when data governance policy eventually permits external ML services (or the agency acquires internal ML infrastructure), the OCR backend can be swapped without rewriting the pipeline.

- **Retention category mapping** — Auto-assigns retention policies (long_term, indefinite, short_term, tied_to_parent) to support records-management and destruction-scheduling workflows required by government records officers.

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

## Known Limitations

- **Execution status detection is heuristic, not ML** — It scans extracted text for execution-language keywords and signature block patterns. It will not detect a hand-drawn signature image in a scanned PDF if OCR fails to extract text from it. It also cannot distinguish between "this contract requires a signature" (draft mentioning signatures) and "this contract was signed" (executed document).

- **Unit tests only, no integration tests** — The test suite mocks all external dependencies (pdfplumber, Tesseract, PIL, dateparser). This means the tests verify internal logic but do not verify that the system works end-to-end with real PDFs or DOCX files on your machine. Integration tests (creating real documents and running the full pipeline) are the next step.

- **NVIDIA backend is a stub** — The `NvidiaOCRBackend` class has the interface wired but the actual API calls are not implemented. Fill in `image_to_text()` and `pdf_to_text()` with your NVIDIA API client when ready.

## License

MIT
