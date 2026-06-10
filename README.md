# LegalDocuMan

Intelligent document processing for contracts, agreements, and legal documents. Extracts text, classifies document types, detects execution status, and organizes files automatically — via CLI or REST API.

## TL;DR — Docker (Fastest)

```bash
git clone https://github.com/Mo-Awadalla/LegalDocuMan.git
cd LegalDocuMan
docker compose up --build
```

Then upload a document:

```bash
curl -X POST http://localhost:5000/api/v1/upload \
  -F "file=@/path/to/your/contract.pdf"
```

Check processing status:

```bash
curl http://localhost:5000/api/v1/jobs/<job_id>
```

## Features

- **Document Classification** — auto-detects MSA, SOW, NDA, PO, Amendment, License
- **Execution Status Detection** — deterministic regex + RF-DETR visual signature detection to distinguish executed (`_final`) from non-executed (`_supporting`) documents. RF-DETR is core to the classification pipeline — the model checkpoint is downloaded at Docker build time from [huggingface.co/Mo-Awadalla/legaldocuman-rfdetr](https://huggingface.co/Mo-Awadalla/legaldocuman-rfdetr) (or must be provided at `models/checkpoint_best_total.pth` for local development).
- **Smart Naming** — `K_VendorName_documentType_001.pdf` or `YYYYMMDD_Vendor_Original.pdf`
- **Folder Organization** — `_final` (executed) vs `_supporting` (unsigned / draft / exhibit)
- **Date Extraction** — effective, expiration, renewal, and review dates from content
- **Vendor Matching** — fuzzy match against a master vendor list
- **Pluggable OCR Backends** — Tesseract (default, local) or NVIDIA (NeMo / Triton / TAO, stub ready)
- **Retention Category Mapping** — auto-assigns retention policies (long_term, indefinite, short_term, tied_to_parent)
- **REST API** — upload documents, poll job status, retrieve metadata (type, vendor, execution status, dates, retention category, generated filename)
- **PostgreSQL persistence** — all document records stored with checksum, file size, and full metadata
- **Docker-ready** — single `docker compose up` spins up the app + database

## Manual Install

```bash
git clone https://github.com/Mo-Awadalla/LegalDocuMan.git
cd LegalDocuMan
pip install -r requirements.txt
```

### Quick local development (no Docker)

For the fastest non-Docker loop, run the Flask app with SQLite:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
DATABASE_URL=sqlite:///legaldocuman.db \
UPLOAD_FOLDER=./uploads \
PROCESSED_FOLDER=./processed \
SECRET_KEY=dev-local-secret \
.venv/Scripts/python run.py
```

Open `http://localhost:5000`. Build the React app first if you want Flask to serve the latest frontend:

```bash
cd frontend
npm ci
npm run build
cd ..
```

SQLite is for local development only. Use PostgreSQL for shared environments and pilots.

### Pilot deployment hardening switches

Set these before sharing an instance with anyone else:

```bash
SECRET_KEY=<strong-random-secret>
API_KEY=<private-pilot-api-key>
CORS_ORIGINS=https://your-domain.example
JOB_BACKEND=rq
REDIS_URL=redis://localhost:6379/0
AUTO_CREATE_DB=0
```

With `API_KEY` set, API clients must send `X-API-Key: <key>` or
`Authorization: Bearer <key>`. Browser downloads may also use `?api_key=<key>`.
For a simple private pilot frontend build, set `VITE_API_KEY=<key>` before
`npm run build`.

For durable background processing, use Redis Queue and run a worker:

```bash
rq worker documents
```

For database schema management, use Flask-Migrate/Alembic instead of relying on
startup table creation:

```bash
AUTO_CREATE_DB=0 flask --app run.py db upgrade
```


### Customer-readiness features

The app now includes the first customer-grade controls beyond the private API key gate:

- User accounts with tenant scoping and roles: `admin`, `reviewer`, `user`.
- Bootstrap the first admin with `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` before first startup.
- Login endpoint: `POST /api/v1/auth/login`; use the returned bearer token for API calls.
- Manual review/correction endpoint and UI on the document detail page.
- Audit trail events for login, upload, processing, and manual updates.
- Built-in malware scanning for empty/EICAR files, plus optional `MALWARE_SCANNER=clamav`.
- Object storage abstraction with `STORAGE_BACKEND=s3` when `boto3` and AWS credentials are configured.
- Redis/RQ worker process via `python -m legaldocuman.app.worker` and docker-compose `worker` service.

For a shared deployment, use migrations and a queue worker:

```bash
AUTO_CREATE_DB=0 flask --app run.py db upgrade
JOB_BACKEND=rq python run.py
python -m legaldocuman.app.worker
```

### Prerequisites

**Tesseract OCR + Poppler** (required for PDF text extraction):
```bash
# macOS
brew install tesseract poppler

# Ubuntu/Debian
sudo apt-get install tesseract-ocr poppler-utils

# Windows — download from https://github.com/UB-Mannheim/tesseract/wiki
# Then set the path in .env: TESSERACT_PATH=C:\\Program Files\\Tesseract-OCR\\tesseract.exe
```

**NVIDIA OCR** (interface only; implementation still required before use):
```bash
# The backend intentionally reports unavailable until image_to_text/pdf_to_text
# are implemented with a real NVIDIA client.
export OCR_BACKEND=nvidia
export NVIDIA_API_KEY=nvapi-your-key-here
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
| `NVIDIA_API_KEY` | — | Your NVIDIA API key (required only if `OCR_BACKEND=nvidia`) |
| `NVIDIA_API_BASE_URL` | `https://integrate.api.nvidia.com/v1` | NVIDIA API endpoint |
| `NVIDIA_OCR_MODEL` | `nvidia/nemotron-ocr-v2` | Model identifier |
| `TESSERACT_PATH` | auto-detect | Override Tesseract binary path |
| `POPLER_PATH` | auto-detect | Override Poppler binary path (pdf2image) |

`.env` is gitignored — never commit it.

## Web API

Start the server:

```bash
docker compose up       # Docker
# or
python run.py           # Manual — requires PostgreSQL running
```

**Upload a document:**
```bash
curl -X POST http://localhost:5000/api/v1/upload \
  -F "file=@/path/to/contract.pdf"
```

Response:
```json
{"id": 1, "job_id": 1, "status": "pending", "job_status": "completed"}
```

**Check job status:**
```bash
curl http://localhost:5000/api/v1/jobs/1
```

Response:
```json
{
  "id": 1,
  "original_name": "contract.pdf",
  "status": "completed",
  "document_type": "MSA",
  "vendor": "Acme Corp",
  "execution_status": "executed",
  "effective_date": "2024-01-01",
  "expiration_date": "2026-12-31",
  "retention_category": "long_term",
  "generated_filename": "K_AcmeCorp_MasterServiceAgreement_001.pdf",
  "created_at": "2026-05-24T10:00:00"
}
```

## CLI Usage

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
│   ├── intake.py              # DocumentIntake pipeline (stateless)
│   ├── storage.py             # StorageBackend abstraction
│   ├── utils.py               # File ops, naming, hashing
│   ├── run.py                 # Flask app entry point
│   └── backends/              # Pluggable OCR backends
│       ├── base.py            # OCRBackend ABC
│       ├── tesseract.py       # Tesseract + pdf2image
│       ├── nvidia.py          # NVIDIA OCR stub
│       └── rfdetr_signature.py # RF-DETR visual signature detector
├── legaldocuman/app/          # Flask web application
│   ├── __init__.py            # create_app() factory
│   ├── config_loader.py       # Env var → Flask config
│   ├── extensions.py          # Flask-SQLAlchemy db instance
│   ├── models.py              # Document SQLAlchemy model
│   ├── main/routes.py         # Main blueprint routes
│   ├── api/routes.py          # Upload + job status API
│   └── processors/
│       └── worker.py           # Background document processor
├── models/                    # RF-DETR checkpoint
├── tests/                     # Pytest suite
├── Dockerfile                 # Container definition
├── docker-compose.yml         # App + PostgreSQL orchestration
├── .env.example               # Env var template
├── requirements.txt          # Dependencies
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

This system was productized from a script originally built for processing large volumes of legal contracts containing privileged party names, signatures, and sensitive terms. The architecture reflects lessons learned from that domain:

- **Regex + visual ML, not either/or** — Document type classification is pure regex (explainable in audits). Execution status uses both regex (fast, text-based) and RF-DETR (slow but visually detects signature strokes). The regex layer flags execution language; RF-DETR confirms presence of ink signatures on the page. Every decision is traceable: regex matches are logged, RF-DETR detections include confidence scores and bounding boxes.

- **No third-party cloud ML** — Sensitive legal documents should never leave your infrastructure. All processing (OCR, classification, visual signature detection) runs locally — no external API calls to OpenAI, cloud CV services, or third-party providers.

- **Runs on commodity hardware** — No GPU required. Tesseract OCR runs on CPU. RF-DETR works with CPU-only PyTorch (the Docker image ships the CPU wheel). The system is designed to work on a standard laptop or a modest cloud VM.

- **Pluggable backend architecture** — The `OCRBackend` abstract base class and `NvidiaOCRBackend` stub are wired so you can swap in a GPU-backed OCR backend without touching the pipeline. Same pattern for storage: swap `LocalStorageBackend` for S3 or GCS with zero pipeline changes.

- **Retention category mapping** — Auto-assigns retention policies (long_term, indefinite, short_term, tied_to_parent) to support records-management and destruction-scheduling workflows.

- **Stateless intake pipeline** — `DocumentIntake` is a pure function from `(file_path, vendor_folder) → DocumentRecord`. File movement, metadata persistence, and registry updates are the caller's responsibility. This makes the core analysis logic easy to test, replay, and compose into larger workflows.

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

## Further Improvements

The following are planned enhancements not yet implemented:

1. **In-file rename support** — Currently the system extracts metadata and reports it via the API, but does not rename the uploaded file on disk. A post-processing step should rename the file to its generated filename (e.g. `K_VendorName_MasterServiceAgreement_001.pdf`) and update `stored_path` in the database accordingly.

2. **Front-end refinements** — The Flask web UI (upload form, job list, job detail) is functional but minimal. Areas for improvement: drag-and-drop file upload, real-time job status polling via SSE or WebSocket, batch upload with per-file status feedback, and a dashboard summary view (total processed, breakdown by document type, execution status pie chart).

3. **Async / threaded batch processing** — The `process_document_async` worker runs synchronously per document. RF-DETR inference is the slowest step in the pipeline, and sequential processing means large batches (100+ files) can take minutes. Thread-based or `asyncio`-based concurrency — with a worker pool bounded by CPU/GPU cores or a configurable concurrency limit — would significantly improve throughput for bulk uploads.

## Known Limitations

- **Execution status detection combines regex + visual ML** — The system uses two signals: (1) deterministic regex scans extracted text for execution-language keywords ("in witness whereof", signature blocks, e-signature platform markers) to classify a document as executed or supporting, and (2) RF-DETR (a fine-tuned computer vision model) detects handwritten signature strokes in document images for a second confidence layer. RF-DETR requires the checkpoint at `models/checkpoint_best_total.pth` — if unavailable the system falls back to regex-only mode. The regex layer cannot distinguish between a draft that mentions signatures and a fully executed contract; visual detection helps close that gap but is not definitive on its own.

- **Unit tests only, no integration tests** — The test suite mocks all external dependencies (pdfplumber, Tesseract, PIL, dateparser). This means the tests verify internal logic but do not verify that the system works end-to-end with real PDFs or DOCX files on your machine. Integration tests (creating real documents and running the full pipeline) are the next step.

- **NVIDIA backend is a stub** — The `NvidiaOCRBackend` class has the interface wired but the actual API calls are not implemented. Fill in `image_to_text()` and `pdf_to_text()` with your NVIDIA API client when ready.

## License

MIT