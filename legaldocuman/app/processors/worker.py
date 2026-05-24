import logging
import os
import threading
from datetime import datetime, timezone

from legaldocuman.intake import DocumentIntake, DocumentRecord
from legaldocuman.config import Config

from ..extensions import db
from ..models import Document, DocumentStatus


def process_document_async(doc_id):
    thread = threading.Thread(target=_process, args=(doc_id,), daemon=True)
    thread.start()
    return thread


def _process(doc_id):
    app = _get_app()
    with app.app_context():
        doc = db.session.get(Document, doc_id)
        if not doc:
            return

        try:
            doc.status = DocumentStatus.PROCESSING
            db.session.commit()

            # Single intake call replaces the entire extraction + classification chain
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

            doc.generated_filename = intake.generate_filename_from_original(
                record, doc.original_name, unique_id=0  # DB-backed, no sequential ID needed
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
            doc.status = DocumentStatus.COMPLETED
            db.session.commit()

        except Exception as e:
            logging.error("Processing failed for document %s: %s", doc_id, e)
            doc.status = DocumentStatus.FAILED
            doc.error_message = str(e)
            db.session.commit()


def _determine_retention(doc_type, date_metadata):
    has_expiration = bool(date_metadata.get("expiration_date"))
    return Config.get().get_retention_category(doc_type, has_expiration)


_app = None


def _get_app():
    global _app
    if _app is None:
        from .. import create_app
        _app = create_app()
    return _app
