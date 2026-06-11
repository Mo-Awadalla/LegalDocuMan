# Contributing

Thanks for helping improve LegalDocuMan. This project is a Flask API/web app with a React frontend for legal document intake and processing.

## Workflow

1. Create a branch from the current integration branch.
2. Keep changes focused and avoid mixing app code, docs, and generated files in one PR unless necessary.
3. Do not commit secrets, `.env` files, uploads, processed documents, model checkpoints, local databases, or privileged/customer documents.
4. Add or update tests for behavior changes.
5. Open a pull request using the PR template.

## Local setup

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
DATABASE_URL=sqlite:///legaldocuman.db \
UPLOAD_FOLDER=./uploads \
PROCESSED_FOLDER=./processed \
SECRET_KEY=dev-local-secret \
.venv/Scripts/python run.py
```

For frontend changes:

```bash
cd frontend
npm ci
npm run build
```

## Validation

Run the relevant checks before requesting review:

```bash
pytest tests/ -v
```

For React/frontend changes, also run the available npm build or test scripts from `frontend/`.

## Code and data expectations

- Keep document-processing logic deterministic and auditable where possible.
- Prefer environment variables for deployment-specific settings.
- Use PostgreSQL, Redis/RQ, strong secrets, explicit CORS, and migrations for shared pilots or production.
- Treat uploaded legal documents, metadata, extracted text, party names, signatures, and dates as sensitive data.
