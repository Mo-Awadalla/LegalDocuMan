"""Job reconciliation, redrive, and operational CLI commands."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import click
from flask import current_app
from flask.cli import AppGroup

from .extensions import db
from .job_ids import rq_job_id
from .models import AuditEvent, Document, DocumentJob, DocumentJobAttempt, DocumentJobStatus, DocumentStatus
from .processors.worker import enqueue_rq

ACTIVE_STATUSES = {
    DocumentJobStatus.PENDING,
    DocumentJobStatus.QUEUED,
    DocumentJobStatus.PROCESSING,
    DocumentJobStatus.RETRY_SCHEDULED,
}


def utcnow():
    return datetime.now(timezone.utc)


def redrive_job(job):
    if job.status != DocumentJobStatus.FAILED:
        raise ValueError("Only failed jobs can be retried")
    active_child = DocumentJob.query.filter(
        DocumentJob.parent_job_id == job.id, DocumentJob.status.in_(ACTIVE_STATUSES)
    ).order_by(DocumentJob.id.desc()).first()
    if active_child:
        return active_child, False
    child = DocumentJob(
        document_id=job.document_id,
        tenant_id=job.tenant_id,
        backend=job.backend,
        status=DocumentJobStatus.PENDING,
        max_attempts=job.max_attempts,
        correlation_id=job.correlation_id,
        parent_job_id=job.id,
    )
    db.session.add(child)
    db.session.flush()
    child.rq_job_id = rq_job_id(child.id)
    document = db.session.get(Document, job.document_id)
    if document:
        document.status = DocumentStatus.PENDING
        document.error_message = None
    db.session.add(AuditEvent(
        tenant_id=job.tenant_id, document_id=job.document_id, action="job.redrive",
        details={"parent_job_id": job.id, "job_id": child.id},
    ))
    db.session.commit()
    if child.backend == "rq":
        enqueue_rq(child.id)
    return child, True


def _rq_state(job):
    try:
        from redis import Redis
        from rq.job import Job
        connection = Redis.from_url(current_app.config["REDIS_URL"])
        if not job.rq_job_id or not Job.exists(job.rq_job_id, connection=connection):
            return None
        status = Job.fetch(job.rq_job_id, connection=connection).get_status(refresh=True)
        return status.value if hasattr(status, "value") else status
    except Exception:
        return None


def reconcile_jobs():
    """Repair committed-but-not-enqueued and abandoned leased jobs."""
    now = utcnow()
    lease_cutoff = now - timedelta(seconds=int(current_app.config["JOB_LEASE_SECONDS"]))
    counts = {"enqueued": 0, "requeued": 0, "failed": 0, "state_repaired": 0}
    candidates = DocumentJob.query.filter(DocumentJob.status.in_(ACTIVE_STATUSES)).order_by(DocumentJob.id).all()
    for job in candidates:
        heartbeat = job.heartbeat_at
        comparable_cutoff = lease_cutoff.replace(tzinfo=None) if heartbeat and heartbeat.tzinfo is None else lease_cutoff
        processing_is_stale = job.status == DocumentJobStatus.PROCESSING and (
            heartbeat is None or heartbeat < comparable_cutoff
        )
        if processing_is_stale:
            attempt = DocumentJobAttempt.query.filter_by(job_id=job.id, attempt_number=job.attempts).first()
            if attempt and attempt.status == "processing":
                attempt.status = "abandoned"
                attempt.finished_at = now
                attempt.retryable = job.attempts < job.max_attempts
                attempt.error_code = "worker_lost"
                attempt.error_message = "Worker heartbeat lease expired"
                attempt.termination_reason = "worker_lost"
                comparable_now = now.replace(tzinfo=None) if attempt.started_at.tzinfo is None else now
                attempt.duration_ms = max(0, int((comparable_now - attempt.started_at).total_seconds() * 1000))
            job.heartbeat_at = None
            job.lease_token = None
            if job.attempts >= job.max_attempts:
                job.status = DocumentJobStatus.FAILED
                job.failure_kind = "worker_lost"
                job.last_error = "Worker heartbeat lease expired after all attempts"
                job.finished_at = now
                job.document.status = DocumentStatus.FAILED
                job.document.error_message = job.last_error
                counts["failed"] += 1
            else:
                job.status = DocumentJobStatus.PENDING
                db.session.commit()
                enqueue_rq(job.id, replace_existing=True)
                counts["requeued"] += 1
            db.session.add(AuditEvent(
                tenant_id=job.tenant_id, document_id=job.document_id, action="job.recovered",
                details={"job_id": job.id, "outcome": job.status.value, "reason": "worker_lost"},
            ))
            db.session.commit()
            continue

        rq_state = _rq_state(job) if job.backend == "rq" else "local"
        if job.status == DocumentJobStatus.PENDING and job.backend == "rq":
            enqueue_rq(job.id, replace_existing=rq_state is None)
            counts["enqueued"] += 1
        elif job.status == DocumentJobStatus.QUEUED and job.backend == "rq" and rq_state is None:
            enqueue_rq(job.id, replace_existing=True)
            counts["requeued"] += 1
        elif job.status == DocumentJobStatus.RETRY_SCHEDULED and rq_state in {"queued", "deferred"}:
            job.status = DocumentJobStatus.QUEUED
            job.queued_at = now
            job.retry_at = None
            db.session.commit()
            counts["state_repaired"] += 1
    return counts


jobs_cli = AppGroup("jobs", help="Inspect and recover durable document jobs.")


@jobs_cli.command("retry")
@click.argument("job_id", type=int)
def retry_command(job_id):
    job = db.session.get(DocumentJob, job_id)
    if not job:
        raise click.ClickException("Job not found")
    try:
        child, created = redrive_job(job)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"job_id={child.id} created={str(created).lower()}")


@jobs_cli.command("reconcile")
def reconcile_command():
    counts = reconcile_jobs()
    click.echo(" ".join(f"{key}={value}" for key, value in counts.items()))


@jobs_cli.command("health")
def health_command():
    from .worker import worker_health
    ok, detail = worker_health()
    click.echo(detail)
    if not ok:
        raise click.ClickException(detail)
