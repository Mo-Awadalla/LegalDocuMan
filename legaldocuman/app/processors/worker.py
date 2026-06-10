import logging
import os
import shutil
import threading
from datetime import datetime

from flask import current_app

from legaldocuman.config import Config
from legaldocuman.intake import DocumentIntake
from legaldocuman.utils import resolve_filename_conflict

from ..extensions import db
from ..models import Document, DocumentStatus


def process_document_async(doc_id):
    """Submit document processing using the configured job backend.

    JOB_BACKEND=thread (default): in-process daemon thread for local dev.
    JOB_BACKEND=sync: run immediately, useful for tests and scripts.
    JOB_BACKEND=rq: enqueue into Redis/RQ for pilot/production workers.
    """
    backend = current_app.config.get("JOB_BACKEND", "thread")

    if backend == "sync":
        return process_document_job(doc_id)

    if backend == "rq":
        return _enqueue_rq(doc_id)

    app = current_app._get_current_object()
    thread = threading.Thread(target=_process_with_app, args=(app, doc_id), daemon=True)
    thread.start()
    return thread


def _enqueue_rq(doc_id):
    try:
        from redis import Redis
        from rq import Queue
    except ImportError as exc:
        _mark_failed(doc_id, "RQ backend requires redis and rq packages")
        raise RuntimeError("RQ backend requires redis and rq packages") from exc

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    queue_name = os.environ.get("RQ_QUEUE", "documents")
    queue = Queue(queue_name, connection=Redis.from_url(redis_url))
    return queue.enqueue("legaldocuman.app.processors.worker.process_document_job", doc_id)


def process_document_job(doc_id):
    """RQ-safe job entrypoint."""
    from .. import create_app

    app = create_app()
    return _process_with_app(app, doc_id)


def _process_with_app(app, doc_id):
    with app.app_context():
        return _process_document(doc_id)


def _process_document(doc_id):
    doc = db.session.get(Document, doc_id)
    if not doc:
        return None

    try:
        doc.status = DocumentStatus.PROCESSING
        doc.error_message = None
        db.session.commit()

        vendor_folder = os.path.basename(os.path.dirname(doc.stored_path))
        intake = DocumentIntake()
        record = intake.analyze(doc.stored_path, vendor_folder)

        if record.error:
            raise RuntimeError(record.error)

        doc.document_type = record.doc_type
        doc.execution_status = record.status
        doc.vendor = record.vendor or "Unknown"
        doc.retention_category = _determine_retention(record.doc_type, record.date_metadata)

        if record.date_metadata.get("effective_date"):
            doc.effective_date = datetime.strptime(record.date_metadata["effective_date"], "%Y-%m-%d").date()
        if record.date_metadata.get("expiration_date"):
            doc.expiration_date = datetime.strptime(record.date_metadata["expiration_date"], "%Y-%m-%d").date()

        generated_filename = intake.generate_filename_from_original(
            record, doc.original_name, unique_id=doc.id
        )
        doc.metadata_json = {
            "document_type": record.doc_type,
            "execution_status": record.status,
            "vendor": record.vendor,
            "date_str": record.date_str,
            "date_metadata": record.date_metadata,
            "signature_analysis": record.signature_analysis,
            "retention_category": doc.retention_category,
        }

        if record.status in ("final", "supporting"):
            vendor_folder = record.clean_vendor or "UnknownVendor"
            target_dir = os.path.abspath(os.path.join(
                Config.get().PROCESSED_FOLDER,
                f"{vendor_folder}_{record.status}",
            ))
            os.makedirs(target_dir, exist_ok=True)

            target_path = os.path.join(target_dir, generated_filename)
            target_path = resolve_filename_conflict(target_path)
            shutil.move(doc.stored_path, target_path)

            doc.stored_path = target_path
            doc.generated_filename = os.path.basename(target_path)
            doc.processed_folder = record.status
        else:
            doc.generated_filename = generated_filename

        doc.status = DocumentStatus.COMPLETED
        db.session.commit()
        return doc.id

    except Exception as e:
        logging.error("Processing failed for document %s: %s", doc_id, e)
        doc.status = DocumentStatus.FAILED
        doc.error_message = str(e)
        db.session.commit()
        return None


def _mark_failed(doc_id, message):
    doc = db.session.get(Document, doc_id)
    if not doc:
        return
    doc.status = DocumentStatus.FAILED
    doc.error_message = message
    db.session.commit()


def _determine_retention(doc_type, date_metadata):
    has_expiration = bool(date_metadata.get("expiration_date"))
    return Config.get().get_retention_category(doc_type, has_expiration)
