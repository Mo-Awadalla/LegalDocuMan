# Security Policy

LegalDocuMan processes legal documents that may contain confidential terms, signatures, party names, and business data. Treat all uploads, processed files, extracted text, metadata, logs, and databases as sensitive.

## Reporting a vulnerability

Please report suspected vulnerabilities privately to the project maintainers. Do not open a public issue with exploit details, secrets, customer data, or sample privileged documents.

Include:

- A concise description of the issue and impact.
- Steps to reproduce, if safe to share.
- Affected routes, configuration, or dependencies.
- Suggested mitigation, if known.

## Deployment guidance

For any shared pilot or production deployment:

- Set a strong `SECRET_KEY` and private `API_KEY`.
- Restrict `CORS_ORIGINS` to trusted origins.
- Use PostgreSQL instead of SQLite.
- Use Redis/RQ for background processing.
- Run database migrations explicitly; do not rely on automatic startup table creation.
- Store uploads and processed files outside the repo and back them up according to your retention policy.
- Keep `.env` files, uploaded documents, processed documents, local databases, and model artifacts out of git.
- Review logs before sharing; they may contain document names or processing metadata.

## Dependency and data handling

- Keep Python and npm dependencies updated through normal review.
- Do not introduce third-party cloud document or OCR services without an explicit privacy/security review.
- Use redacted fixtures for tests; never commit real customer or privileged legal documents.
