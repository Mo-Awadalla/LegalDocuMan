# Deployment Guide

This guide describes a practical private-pilot deployment path for LegalDocuMan.

## 1. Prepare configuration

Copy the example file and replace placeholders locally or in your hosting platform's secret manager:

```bash
cp .env.example .env
```

Minimum shared-environment values:

```bash
APP_ENV=production
SECRET_KEY=<generate-a-strong-random-value>
API_KEY=<generate-a-private-pilot-api-key>
BOOTSTRAP_ADMIN_EMAIL=<admin-email>
BOOTSTRAP_ADMIN_PASSWORD=<one-time-strong-password>
CORS_ORIGINS=https://your-domain.example
DATABASE_URL=postgresql://<user>:<password>@<host>:5432/legaldocuman
JOB_BACKEND=rq
REDIS_URL=redis://<redis-host>:6379/0
STORAGE_BACKEND=local
UPLOAD_FOLDER=/project/uploads
PROCESSED_FOLDER=/project/processed
```

Do not commit `.env` or any generated secrets.

## 2. Local Docker Compose smoke

The compose file uses placeholder defaults so local developers can run the stack without adding secrets to git:

```bash
docker compose config
docker compose up --build
```

Open `http://localhost:5000`. For local Docker, the app service runs migrations before starting Gunicorn.

## 3. Production topology

Recommended components:

- Reverse proxy/load balancer terminating TLS.
- Flask/Gunicorn app container.
- One or more worker containers running `python -m legaldocuman.app.worker`.
- Managed PostgreSQL.
- Managed Redis.
- Durable document storage: mounted volume for private pilots or S3-compatible storage for multi-node deployments.

## 4. Release procedure

1. Run CI on the target commit.
2. Build and tag the container image.
3. Apply migrations: `flask --app run.py db upgrade`.
4. Deploy app and worker with the same image and environment.
5. Smoke test:
   - admin login/token flow,
   - test upload,
   - job completion,
   - download token,
   - worker logs.
6. Rotate bootstrap credentials after first admin setup if no longer needed.

## 5. Rollback

- Keep the previous image tag available.
- Take database/storage backups before migrations.
- Roll back app and worker image together.
- If a migration is not reversible, restore from the backup taken before deployment.
