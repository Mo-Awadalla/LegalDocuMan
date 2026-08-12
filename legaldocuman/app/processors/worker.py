"""Durable document job execution and RQ enqueueing."""
from __future__ import annotations

import json
import logging
import os
import socket
import tempfile
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

from flask import current_app
from sqlalchemy import select, update

from legaldocuman.config import Config
from legaldocuman.intake import DocumentIntake
from legaldocuman.storage import get_storage_backend, local_file_for_processing

from ..extensions import db
from ..models import (
    AuditEvent,
    Document,
    DocumentJob,
    DocumentJobAttempt,
    DocumentJobStatus,
    DocumentStatus,
    ReviewStatus,
)

_PRELOADED_INTAKE = None
RETRY_DELAYS = (10, 60)


class ProcessingFailure(Exception):
    code = "processing_failure"
    retryable = False


class TransientProcessingFailure(ProcessingFailure):
    retryable = True


class StorageUnavailable(TransientProcessingFailure):
    code = "storage_unavailable"


class ProcessingTimeout(TransientProcessingFailure):
    code = "processing_timeout"


class InvalidDocument(ProcessingFailure):
    code = "invalid_document"


class DeterministicExtractionFailure(ProcessingFailure):
    code = "extraction_failed"


def preload_pipeline():
    """Initialize the model once before an RQ worker starts forking workhorses."""
    global _PRELOADED_INTAKE
    if _PRELOADED_INTAKE is None:
        _PRELOADED_INTAKE = DocumentIntake()
    return _PRELOADED_INTAKE


def _now():
    return datetime.now(timezone.utc)


def _safe_message(exc):
    messages = {
        "storage_unavailable": "Storage operation temporarily unavailable",
        "processing_timeout": "Document processing timed out",
        "invalid_document": "Document is invalid or unsupported",
        "extraction_failed": "Document content could not be processed",
        "processing_failure": "Document processing failed",
    }
    return messages.get(getattr(exc, "code", ""), f"Processing failed ({exc.__class__.__name__})")


def _event(event, **fields):
    payload = {"event": event, "timestamp": _now().isoformat(), **{k: v for k, v in fields.items() if v is not None}}
    logging.getLogger("legaldocuman.jobs").info(json.dumps(payload, sort_keys=True, default=str))


def process_document_async(job_id):
    backend = current_app.config.get("JOB_BACKEND", "thread")
    if backend == "sync":
        _mark_queued(job_id)
        return _process_document(job_id)
    if backend == "rq":
        return enqueue_rq(job_id)
    app = current_app._get_current_object()
    _mark_queued(job_id)
    thread = threading.Thread(target=_process_with_app, args=(app, job_id), daemon=True)
    thread.start()
    return thread


def enqueue_rq(job_id, *, replace_existing=False):
    try:
        from redis import Redis
        from rq import Queue, Retry
        from rq.job import Job
    except ImportError as exc:
        _mark_terminal(job_id, "queue_unavailable", "RQ backend requires redis and rq")
        raise RuntimeError("RQ backend requires redis and rq packages") from exc

    job = db.session.get(DocumentJob, job_id)
    if not job:
        return None
    rq_id = job.rq_job_id or f"document-job:{job.id}"
    connection = Redis.from_url(current_app.config["REDIS_URL"])
    queue = Queue(current_app.config["RQ_QUEUE"], connection=connection)
    existing = Job.fetch(rq_id, connection=connection) if Job.exists(rq_id, connection=connection) else None
    if existing and not replace_existing:
        _mark_queued(job_id, rq_id=rq_id)
        return existing
    if existing:
        existing.cancel()
        existing.delete()
    rq_job = queue.enqueue(
        "legaldocuman.app.processors.worker.process_document_job",
        job_id,
        job_id=rq_id,
        job_timeout=int(current_app.config["JOB_TIMEOUT_SECONDS"]),
        retry=Retry(max=2, interval=list(RETRY_DELAYS)),
        result_ttl=86400,
        failure_ttl=604800,
        meta={"database_job_id": job_id, "correlation_id": job.correlation_id},
    )
    _mark_queued(job_id, rq_id=rq_id)
    _event("job_queued", job_id=job.id, document_id=job.document_id, correlation_id=job.correlation_id, rq_job_id=rq_id)
    return rq_job


def process_document_job(job_id):
    """RQ import target. Transient failures deliberately escape for RQ Retry."""
    from .. import create_app

    app = create_app()
    with app.app_context():
        return _process_document(job_id)


def rq_exception_handler(rq_job, exc_type, exc_value, traceback):
    """Record failures delivered outside the workhorse, notably hard timeouts."""
    database_job_id = (rq_job.meta or {}).get("database_job_id")
    if not database_job_id:
        return True
    from .. import create_app

    app = create_app()
    with app.app_context():
        job = db.session.get(DocumentJob, database_job_id)
        if not job or job.status != DocumentJobStatus.PROCESSING:
            return True
        now = _now()
        error_name = getattr(exc_type, "__name__", "worker_interrupted")
        code = "processing_timeout" if "Timeout" in error_name else "worker_lost"
        attempt = DocumentJobAttempt.query.filter_by(job_id=job.id, attempt_number=job.attempts).first()
        retryable = job.attempts < job.max_attempts
        if attempt:
            attempt.status = "retry_scheduled" if retryable else "failed"
            attempt.finished_at = now
            attempt.retryable = retryable
            attempt.error_code = code
            attempt.error_message = "Workhorse timed out" if code == "processing_timeout" else "Workhorse interrupted"
            attempt.termination_reason = code
            comparable_now = now.replace(tzinfo=None) if attempt.started_at.tzinfo is None else now
            attempt.duration_ms = max(0, int((comparable_now - attempt.started_at).total_seconds() * 1000))
        job.failure_kind = code
        job.last_error = "Processing attempt timed out" if code == "processing_timeout" else "Worker was interrupted"
        job.heartbeat_at = None
        job.lease_token = None
        if retryable:
            job.status = DocumentJobStatus.RETRY_SCHEDULED
            delay = RETRY_DELAYS[min(job.attempts - 1, len(RETRY_DELAYS) - 1)]
            job.retry_at = now + timedelta(seconds=delay)
            job.document.status = DocumentStatus.PENDING
        else:
            job.status = DocumentJobStatus.FAILED
            job.finished_at = now
            job.document.status = DocumentStatus.FAILED
            job.document.error_message = job.last_error
        db.session.commit()
    return True


def rq_workhorse_killed_handler(rq_job, retpid, ret_val, rusage):
    """RQ parent-process callback for SIGKILL, OOM, and other workhorse loss."""
    worker_lost = type("WorkerLost", (Exception,), {})
    rq_exception_handler(rq_job, worker_lost, worker_lost(), None)


def _process_with_app(app, job_id):
    with app.app_context():
        try:
            return _process_document(job_id)
        except TransientProcessingFailure:
            return None


def _worker_name():
    try:
        from rq import get_current_job
        rq_job = get_current_job()
        if rq_job and rq_job.worker_name:
            return f"{rq_job.worker_name}:{os.getpid()}"
    except Exception:
        pass
    return f"{socket.gethostname()}:{os.getpid()}"


def _rq_attempt_number(max_attempts):
    try:
        from rq import get_current_job

        rq_job = get_current_job()
        if rq_job and rq_job.retries_left is not None:
            return max_attempts - int(rq_job.retries_left)
    except Exception:
        pass
    return None


def _heartbeat(app, job_id, attempt_id, lease_token, interval, stop):
    while not stop.wait(interval):
        now = _now()
        with app.app_context():
            db.session.execute(
                update(DocumentJob).where(DocumentJob.id == job_id, DocumentJob.lease_token == lease_token).values(heartbeat_at=now)
            )
            db.session.execute(
                update(DocumentJobAttempt).where(
                    DocumentJobAttempt.id == attempt_id, DocumentJobAttempt.lease_token == lease_token
                ).values(heartbeat_at=now)
            )
            db.session.commit()


def _start_attempt(job, doc):
    now = _now()
    lease_token = uuid.uuid4().hex
    job.attempts += 1
    job.status = DocumentJobStatus.PROCESSING
    job.started_at = job.started_at or now
    job.heartbeat_at = now
    job.lease_token = lease_token
    job.retry_at = None
    job.failure_kind = None
    job.last_error = None
    doc.status = DocumentStatus.PROCESSING
    doc.error_message = None
    attempt = DocumentJobAttempt(
        job_id=job.id,
        attempt_number=job.attempts,
        worker_name=_worker_name(),
        status="processing",
        lease_token=lease_token,
        started_at=now,
        heartbeat_at=now,
    )
    db.session.add(attempt)
    db.session.commit()
    return attempt, lease_token


def _result_exists(doc):
    key = doc.result_storage_key
    if not key:
        return False
    try:
        return get_storage_backend().exists(key) if key.startswith("s3://") else os.path.exists(key)
    except Exception:
        return False


def _process_document(job_id):
    job = db.session.execute(
        select(DocumentJob).where(DocumentJob.id == job_id).with_for_update()
    ).scalar_one_or_none()
    if not job:
        return None
    doc = db.session.get(Document, job.document_id)
    if not doc:
        _mark_terminal(job_id, "document_missing", "Document not found")
        return None
    if job.status == DocumentJobStatus.COMPLETED and _result_exists(doc):
        return doc.id
    if job.status == DocumentJobStatus.FAILED:
        return None
    if job.status == DocumentJobStatus.RETRY_SCHEDULED:
        # Persist the scheduled → queued boundary even when a ready worker
        # dequeues the retry before the periodic reconciler observes it.
        job.status = DocumentJobStatus.QUEUED
        job.queued_at = _now()
        job.retry_at = None
        db.session.commit()
        job = db.session.execute(
            select(DocumentJob).where(DocumentJob.id == job_id).with_for_update()
        ).scalar_one()
        doc = db.session.get(Document, job.document_id)
    lease_cutoff = _now() - timedelta(seconds=int(current_app.config["JOB_LEASE_SECONDS"]))
    comparable_cutoff = (
        lease_cutoff.replace(tzinfo=None) if job.heartbeat_at and job.heartbeat_at.tzinfo is None else lease_cutoff
    )
    if job.status == DocumentJobStatus.PROCESSING and job.heartbeat_at and job.heartbeat_at >= comparable_cutoff:
        expected_attempt = _rq_attempt_number(job.max_attempts)
        if expected_attempt is None or expected_attempt <= job.attempts:
            # Duplicate delivery while another fenced attempt owns the lease.
            db.session.rollback()
            return None
        # RQ is delivering a later retry after a database outage prevented the
        # prior workhorse from recording its failure. Fence and abandon it.
        prior = DocumentJobAttempt.query.filter_by(job_id=job.id, attempt_number=job.attempts).first()
        if prior and prior.status == "processing":
            prior.status = "abandoned"
            prior.finished_at = _now()
            prior.retryable = True
            prior.error_code = "worker_lost"
            prior.error_message = "Superseded by a later RQ retry"
            prior.termination_reason = "retry_reclaimed"
        job.lease_token = None
        job.heartbeat_at = None

    attempt, lease_token = _start_attempt(job, doc)
    app = current_app._get_current_object()
    stop = threading.Event()
    heartbeat = threading.Thread(
        target=_heartbeat,
        args=(app, job.id, attempt.id, lease_token, int(current_app.config["JOB_HEARTBEAT_SECONDS"]), stop),
        daemon=True,
    )
    heartbeat.start()
    started = time.monotonic()
    _event("job_started", job_id=job.id, document_id=doc.id, correlation_id=job.correlation_id,
           attempt=attempt.attempt_number, worker=attempt.worker_name, stage="analysis")
    try:
        result = _analyze_and_publish(job, doc, lease_token)
        duration = int((time.monotonic() - started) * 1000)
        attempt.status = "completed"
        attempt.finished_at = _now()
        attempt.duration_ms = duration
        attempt.retryable = False
        job.status = DocumentJobStatus.COMPLETED
        job.finished_at = _now()
        job.heartbeat_at = None
        job.lease_token = None
        doc.status = DocumentStatus.COMPLETED
        db.session.add(AuditEvent(tenant_id=job.tenant_id, document_id=doc.id, action="document.processed",
                                  details={"job_id": job.id, "attempt": attempt.attempt_number}))
        db.session.commit()
        _event("job_finished", job_id=job.id, document_id=doc.id, correlation_id=job.correlation_id,
               attempt=attempt.attempt_number, worker=attempt.worker_name, duration_ms=duration, outcome="completed")
        return result
    except Exception as raw_exc:
        exc = _classify_exception(raw_exc)
        duration = int((time.monotonic() - started) * 1000)
        retryable = exc.retryable and job.attempts < job.max_attempts
        attempt.status = "retry_scheduled" if retryable else "failed"
        attempt.finished_at = _now()
        attempt.duration_ms = duration
        attempt.retryable = retryable
        attempt.error_code = exc.code
        attempt.error_message = _safe_message(exc)
        attempt.termination_reason = "transient_failure" if retryable else "terminal_failure"
        job.last_error = _safe_message(exc)
        job.failure_kind = exc.code
        job.heartbeat_at = None
        job.lease_token = None
        if retryable:
            delay = RETRY_DELAYS[min(job.attempts - 1, len(RETRY_DELAYS) - 1)]
            job.status = DocumentJobStatus.RETRY_SCHEDULED
            job.retry_at = _now() + timedelta(seconds=delay)
            doc.status = DocumentStatus.PENDING
        else:
            job.status = DocumentJobStatus.FAILED
            job.finished_at = _now()
            doc.status = DocumentStatus.FAILED
            doc.error_message = _safe_message(exc)
        db.session.commit()
        _event("job_finished", job_id=job.id, document_id=doc.id, correlation_id=job.correlation_id,
               attempt=attempt.attempt_number, worker=attempt.worker_name, duration_ms=duration,
               retry_count=max(0, job.attempts - 1), outcome=attempt.status, error_type=exc.code)
        if retryable:
            raise exc
        return None
    finally:
        stop.set()
        heartbeat.join(timeout=2)


def _analyze_and_publish(job, doc, lease_token):
    source_key = doc.source_storage_key or doc.storage_key or doc.stored_path
    # Upload storage uses random isolation directories; never treat that UUID as vendor metadata.
    vendor_folder = ""
    intake = preload_pipeline()
    try:
        with local_file_for_processing(source_key) as source_path:
            record = intake.analyze(source_path, vendor_folder)
    except (TimeoutError,) as exc:
        raise ProcessingTimeout(str(exc)) from exc
    except (OSError, ConnectionError) as exc:
        raise StorageUnavailable(str(exc)) from exc
    if record.error:
        raise DeterministicExtractionFailure(record.error)

    doc.document_type = record.doc_type
    doc.execution_status = record.status
    doc.vendor = record.vendor or "Unknown"
    doc.retention_category = _determine_retention(record.doc_type, record.date_metadata)
    if record.date_metadata.get("effective_date"):
        doc.effective_date = datetime.strptime(record.date_metadata["effective_date"], "%Y-%m-%d").date()
    if record.date_metadata.get("expiration_date"):
        doc.expiration_date = datetime.strptime(record.date_metadata["expiration_date"], "%Y-%m-%d").date()
    for field in ("renewal_date", "review_date", "termination_date"):
        if record.date_metadata.get(field):
            setattr(doc, field, datetime.strptime(record.date_metadata[field], "%Y-%m-%d").date())
    doc.extracted_text = record.text_content
    filename = intake.generate_filename_from_original(record, doc.original_name, unique_id=doc.id)
    doc.metadata_json = {
        "document_type": record.doc_type, "execution_status": record.status, "vendor": record.vendor,
        "date_str": record.date_str, "date_metadata": record.date_metadata,
        "signature_analysis": record.signature_analysis, "retention_category": doc.retention_category,
    }
    doc.generated_filename = filename
    if record.signature_analysis and record.signature_analysis.get("review_required"):
        doc.review_status = ReviewStatus.NEEDS_REVIEW

    # A job-scoped staging file makes a partially-written artifact unpublishable.
    suffix = os.path.splitext(filename)[1]
    with tempfile.NamedTemporaryFile(prefix=f"job-{job.id}-attempt-{job.attempts}-", suffix=suffix, delete=False) as staged:
        staged_path = staged.name
    try:
        with local_file_for_processing(source_key) as source_path, open(source_path, "rb") as source, open(staged_path, "wb") as target:
            while chunk := source.read(1024 * 1024):
                target.write(chunk)
        db.session.refresh(job)
        if job.lease_token != lease_token or job.status != DocumentJobStatus.PROCESSING:
            raise TransientProcessingFailure("attempt lease is no longer active")
        result_key = get_storage_backend().publish_result(staged_path, doc.id, filename)
    except (OSError, ConnectionError) as exc:
        raise StorageUnavailable(str(exc)) from exc
    finally:
        if os.path.exists(staged_path):
            os.remove(staged_path)
    doc.result_storage_key = result_key
    doc.stored_path = result_key
    doc.storage_key = result_key
    doc.processed_folder = record.status
    return doc.id


def _classify_exception(exc):
    if isinstance(exc, ProcessingFailure):
        return exc
    if isinstance(exc, (TimeoutError,)):
        return ProcessingTimeout(str(exc))
    if isinstance(exc, (OSError, ConnectionError)):
        return StorageUnavailable(str(exc))
    return DeterministicExtractionFailure(str(exc))


def _mark_queued(job_id, rq_id=None):
    job = db.session.get(DocumentJob, job_id)
    if not job:
        return
    job.status = DocumentJobStatus.QUEUED
    job.queued_at = _now()
    job.retry_at = None
    job.rq_job_id = rq_id or job.rq_job_id or f"document-job:{job.id}"
    db.session.commit()


def _mark_terminal(job_id, code, message):
    job = db.session.get(DocumentJob, job_id)
    if not job:
        return
    doc = db.session.get(Document, job.document_id)
    job.status = DocumentJobStatus.FAILED
    job.failure_kind = code
    job.last_error = message[:500]
    job.finished_at = _now()
    if doc:
        doc.status = DocumentStatus.FAILED
        doc.error_message = message[:500]
    db.session.commit()


def _determine_retention(doc_type, date_metadata):
    return Config.get().get_retention_category(doc_type, bool(date_metadata.get("expiration_date")))
