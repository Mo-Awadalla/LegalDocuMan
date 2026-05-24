import os

from flask import Blueprint, current_app, jsonify, request

from legaldocuman.storage import LocalStorageBackend

from ..extensions import db
from ..models import Document
from ..processors.worker import process_document_async

api_bp = Blueprint("api", __name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}


@api_bp.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type: {ext}"}), 400

    storage = LocalStorageBackend(current_app.config["UPLOAD_FOLDER"])
    filepath = storage.save(file, file.filename)
    checksum = Document.compute_checksum(filepath)

    doc = Document(
        original_name=file.filename,
        stored_path=filepath,
        file_size=os.path.getsize(filepath),
        checksum=checksum,
    )
    db.session.add(doc)
    db.session.commit()

    process_document_async(doc.id)

    return jsonify({"id": doc.id, "status": doc.status.value}), 201


@api_bp.route("/jobs/<int:doc_id>")
def job_status(doc_id):
    doc = db.session.get(Document, doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    return jsonify({
        "id": doc.id,
        "original_name": doc.original_name,
        "status": doc.status.value,
        "document_type": doc.document_type,
        "vendor": doc.vendor,
        "execution_status": doc.execution_status,
        "effective_date": doc.effective_date.isoformat() if doc.effective_date else None,
        "expiration_date": doc.expiration_date.isoformat() if doc.expiration_date else None,
        "retention_category": doc.retention_category,
        "generated_filename": doc.generated_filename,
        "error_message": doc.error_message,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    })
