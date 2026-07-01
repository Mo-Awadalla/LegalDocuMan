# Security Notes

LegalDocuMan processes legal documents that may contain privileged, confidential, or regulated data. Treat every deployment as sensitive.

## Secrets

- Never commit `.env`, API keys, database passwords, cloud keys, or real bootstrap credentials.
- Use `.env.example`, docs, and compose defaults for placeholders only.
- Generate unique `SECRET_KEY` and `API_KEY` values per environment.
- Store production secrets in the platform secret manager and restrict read access.

## Authentication and authorization

- Keep `ALLOW_OPEN_DEV_MODE=0` outside local development.
- Require authenticated users or `API_KEY` for API routes.
- Remove or rotate bootstrap admin credentials after initial setup.
- Use short-lived download tokens with `DOWNLOAD_TOKEN_TTL_SECONDS`.

## Network and browser controls

- Serve production traffic over HTTPS only.
- Set `CORS_ORIGINS` to exact origins; avoid wildcards.
- Place the app behind a reverse proxy/load balancer with request size limits matching `MAX_UPLOAD_MB`.

## Data protection

- Prefer local/offline OCR for sensitive data. The default Tesseract/RF-DETR path keeps documents in your infrastructure.
- If enabling `OCR_BACKEND=nvidia`, review data-transfer and vendor terms first and provide `NVIDIA_API_KEY` only through secrets.
- Encrypt database, Redis, and document storage at rest where supported.
- Back up PostgreSQL and document storage; test restores.
- Limit log retention and avoid logging document content.

## CI security checks

The CI workflow includes:

- frontend high-severity `npm audit`,
- informational Python dependency audit via `pip-audit`,
- gitleaks secret scanning for committed credentials.

Treat CI findings as release blockers unless explicitly triaged.
