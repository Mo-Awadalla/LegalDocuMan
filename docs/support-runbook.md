# Support Runbook

Use this runbook for private-pilot operations and first-response triage.

## Health checks

- App reachable: open `/` or the configured health endpoint if one is added.
- Database reachable: app can run `flask --app run.py db upgrade` without connection errors.
- Worker running: worker logs show it connected to Redis/RQ.
- Redis reachable: uploads create jobs and workers consume them.
- Storage writable: uploads appear in `UPLOAD_FOLDER`; processed outputs appear in `PROCESSED_FOLDER`.

## Common incidents

### Upload fails

1. Check request size against `MAX_UPLOAD_MB` and reverse proxy limits.
2. Confirm API key/auth header is present for protected routes.
3. Check app logs for validation, malware scanner, or storage errors.
4. Confirm upload volume/object storage has free space and write permission.

### Job stays pending

1. Confirm `JOB_BACKEND=rq` in app and worker.
2. Confirm app and worker use the same `REDIS_URL`.
3. Restart the worker and watch for import/model errors.
4. Check whether RF-DETR checkpoint is present; missing checkpoint should fall back, but model path errors may indicate misconfiguration.

### Download fails

1. Generate a fresh download token; tokens expire via `DOWNLOAD_TOKEN_TTL_SECONDS`.
2. Confirm the document record exists and points to a valid processed/stored path.
3. Check storage permissions and object existence.

### Login/API access issue

1. Verify bootstrap admin was created for the expected tenant.
2. Confirm `API_KEY` matches the calling client if API-key access is used.
3. Check rate-limit logs; temporarily lower traffic or tune `RATE_LIMIT_*` values if legitimate users are throttled.

## Escalation packet

Collect this information without including document contents or secrets:

- timestamp and environment,
- request path and status code,
- job/document ID,
- app and worker log snippets with secrets redacted,
- current image/version/commit,
- whether PostgreSQL/Redis/storage health checks passed.

## Routine maintenance

- Review CI security findings before every release.
- Rotate API keys and admin credentials periodically.
- Verify backups and restore procedure at least once per pilot phase.
- Monitor disk/object storage growth and database size.
