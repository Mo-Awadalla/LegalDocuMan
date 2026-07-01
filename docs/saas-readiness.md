# SaaS Readiness Checklist

Use this checklist before running LegalDocuMan as a shared pilot or SaaS service. The repository defaults are safe placeholders only; put real values in `.env`, CI/CD secrets, or your hosting secret manager.

## Environment and configuration

- Set `APP_ENV=staging` or `APP_ENV=production` outside local development.
- Replace `SECRET_KEY` and `API_KEY` with strong random values; never commit them.
- Configure `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD`, and `BOOTSTRAP_TENANT_NAME` for first-run admin setup, then rotate/remove bootstrap values after the admin exists.
- Set exact HTTPS `CORS_ORIGINS` for the deployed frontend/API origins.
- Keep `ALLOW_OPEN_DEV_MODE=0` for every shared environment.
- Use PostgreSQL via `DATABASE_URL`; SQLite is local-development only.
- Use Redis/RQ for background jobs with `JOB_BACKEND=rq` and `REDIS_URL=redis://...`.
- Choose storage intentionally: `STORAGE_BACKEND=local` with durable mounted volumes, or `STORAGE_BACKEND=s3` with cloud credentials supplied by the runtime.

## Operational checks

- Run database migrations before serving traffic: `flask --app run.py db upgrade`.
- Start at least one worker: `python -m legaldocuman.app.worker`.
- Verify upload, job polling, document detail, and download-token flows with a non-sensitive test document.
- Confirm upload size limits with `MAX_UPLOAD_MB`.
- Confirm logs do not print secrets, document contents, or privileged legal terms unnecessarily.
- Back up PostgreSQL and uploaded/processed document storage before pilot users upload real material.

## Security controls

- Require API keys or authenticated users for `/api/v1` routes.
- Keep `RATE_LIMIT_ENABLED=1`; tune auth/upload limits for expected pilot traffic.
- Use TLS at the load balancer/reverse proxy.
- Store secrets in a secret manager; `.env.example` and `docker-compose.yml` must contain placeholders only.
- Run CI security jobs (`npm audit`, pip-audit informational, gitleaks) on pull requests.

## Launch gate

Do not share a deployment until all of the following are true:

- [ ] Secrets are unique and stored outside git.
- [ ] PostgreSQL, Redis, app, and worker health are verified.
- [ ] Admin login and API key access are tested.
- [ ] CORS permits only intended origins.
- [ ] Backups and restore steps are documented/tested.
- [ ] A support owner knows how to triage failed jobs and user access issues.
