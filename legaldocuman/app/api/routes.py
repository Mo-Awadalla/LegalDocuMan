import os

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import func

from legaldocuman.storage import LocalStorageBackend

from ..extensions import db
from ..models import Document, DocumentStatus
from ..processors.worker import process_document_async

api_bp = Blueprint("api", __name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}


def _doc_to_dict(doc):
    return {
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
        "processed_folder": doc.processed_folder,
        "file_size": doc.file_size,
        "error_message": doc.error_message,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


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

    return jsonify(_doc_to_dict(doc))


@api_bp.route("/documents")
def list_documents():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    status = request.args.get("status")
    doc_type = request.args.get("type")
    vendor = request.args.get("vendor")
    search = request.args.get("search")

    query = Document.query

    if status:
        try:
            query = query.filter(Document.status == DocumentStatus(status))
        except ValueError:
            pass
    if doc_type:
        query = query.filter(Document.document_type == doc_type)
    if vendor:
        query = query.filter(Document.vendor.ilike(f"%{vendor}%"))
    if search:
        query = query.filter(
            Document.original_name.ilike(f"%{search}%")
            | Document.vendor.ilike(f"%{search}%")
        )

    query = query.order_by(Document.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "documents": [_doc_to_dict(doc) for doc in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    })


@api_bp.route("/documents/<int:doc_id>")
def get_document(doc_id):
    doc = db.session.get(Document, doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    result = _doc_to_dict(doc)
    result["metadata_json"] = doc.metadata_json
    return jsonify(result)


@api_bp.route("/documents/stats")
def document_stats():
    total = Document.query.count()
    by_status = dict(
        db.session.query(Document.status, func.count(Document.id))
        .group_by(Document.status)
        .all()
    )
    by_type = dict(
        db.session.query(Document.document_type, func.count(Document.id))
        .filter(Document.document_type.isnot(None))
        .group_by(Document.document_type)
        .all()
    )
    by_execution = dict(
        db.session.query(Document.execution_status, func.count(Document.id))
        .filter(Document.execution_status.isnot(None))
        .group_by(Document.execution_status)
        .all()
    )

    return jsonify({
        "total": total,
        "by_status": {k.value if hasattr(k, "value") else k: v for k, v in by_status.items()},
        "by_type": by_type,
        "by_execution_status": by_execution,
    })
