import os
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, send_file
from sqlalchemy import func
from werkzeug.utils import secure_filename

from legaldocuman.storage import get_storage_backend

from ..auth import audit, auth_required, current_tenant_id, current_user, issue_token
from ..extensions import db
from ..models import AuditEvent, Document, DocumentStatus, ReviewStatus, ScanStatus, Tenant, User, UserRole
from ..processors.worker import process_document_async
from ..security import MalwareScanner

api_bp = Blueprint("api", __name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def _doc_query():
    query = Document.query
    tenant_id = current_tenant_id()
    if tenant_id:
        query = query.filter(Document.tenant_id == tenant_id)
    return query


def _get_doc_or_404(doc_id):
    doc = _doc_query().filter(Document.id == doc_id).first()
    return doc


def _doc_to_dict(doc):
    return {
        "id": doc.id,
        "tenant_id": doc.tenant_id,
        "uploaded_by_id": doc.uploaded_by_id,
        "reviewed_by_id": doc.reviewed_by_id,
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
        "storage_backend": doc.storage_backend,
        "file_size": doc.file_size,
        "checksum": doc.checksum,
        "scan_status": doc.scan_status.value,
        "scan_message": doc.scan_message,
        "scanned_at": doc.scanned_at.isoformat() if doc.scanned_at else None,
        "review_status": doc.review_status.value,
        "review_notes": doc.review_notes,
        "reviewed_at": doc.reviewed_at.isoformat() if doc.reviewed_at else None,
        "error_message": doc.error_message,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


def _audit_to_dict(event):
    return {
        "id": event.id,
        "action": event.action,
        "document_id": event.document_id,
        "user_id": event.user_id,
        "tenant_id": event.tenant_id,
        "details": event.details,
        "ip_address": event.ip_address,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


@api_bp.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    user = User.query.filter_by(email=email).first()
    if not user or not user.is_active or not user.check_password(password):
        return jsonify({"error": "Invalid email or password"}), 401
    audit("auth.login", details={"email": email})
    db.session.commit()
    return jsonify({
        "token": issue_token(user),
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role.value,
            "tenant_id": user.tenant_id,
        },
    })


@api_bp.route("/auth/me")
@auth_required()
def me():
    user = current_user()
    if not user:
        return jsonify({"user": None, "auth_mode": "api_key_or_dev"})
    return jsonify({
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role.value,
            "tenant_id": user.tenant_id,
        }
    })


@api_bp.route("/users", methods=["POST"])
@auth_required([UserRole.ADMIN])
def create_user():
    actor = current_user()
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    name = (data.get("name") or email).strip()
    role = data.get("role") or UserRole.USER.value
    if role not in {r.value for r in UserRole}:
        return jsonify({"error": "Invalid role"}), 400
    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "User already exists"}), 409
    tenant_id = actor.tenant_id if actor else data.get("tenant_id")
    if not tenant_id:
        tenant = Tenant(name=data.get("tenant_name") or "Default Tenant", slug=data.get("tenant_slug") or "default")
        db.session.add(tenant)
        db.session.flush()
        tenant_id = tenant.id
    user = User(tenant_id=tenant_id, email=email, name=name, role=UserRole(role))
    user.set_password(password)
    db.session.add(user)
    audit("user.create", details={"email": email, "role": role})
    db.session.commit()
    return jsonify({"id": user.id, "email": user.email, "role": user.role.value}), 201


@api_bp.route("/upload", methods=["POST"])
@auth_required()
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    original_name = secure_filename(file.filename)
    if not original_name:
        return jsonify({"error": "Invalid filename"}), 400

    ext = os.path.splitext(original_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type: {ext}"}), 400

    storage = get_storage_backend()
    filepath = storage.save(file, original_name)
    scan = MalwareScanner().scan(filepath) if not filepath.startswith("s3://") else ScanStatus.CLEAN and type("R", (), {"status":"clean", "message":"Scan deferred for object storage", "clean": True})()
    if not scan.clean:
        storage.delete(filepath)
        return jsonify({"error": "Malware scan failed", "scan_status": scan.status, "scan_message": scan.message}), 400
    checksum = Document.compute_checksum(filepath) if not filepath.startswith("s3://") else None

    user = current_user()
    doc = Document(
        tenant_id=user.tenant_id if user else None,
        uploaded_by_id=user.id if user else None,
        original_name=original_name,
        stored_path=filepath,
        storage_backend=storage.name,
        storage_key=filepath,
        file_size=os.path.getsize(filepath) if not filepath.startswith("s3://") else None,
        checksum=checksum,
        scan_status=ScanStatus(scan.status),
        scan_message=scan.message,
        scanned_at=datetime.now(timezone.utc),
    )
    db.session.add(doc)
    db.session.flush()
    audit("document.upload", document_id=doc.id, details={"filename": original_name, "storage_backend": storage.name})
    db.session.commit()

    process_document_async(doc.id)

    return jsonify({"id": doc.id, "status": doc.status.value}), 201


@api_bp.route("/jobs/<int:doc_id>")
@auth_required()
def job_status(doc_id):
    doc = _get_doc_or_404(doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    return jsonify(_doc_to_dict(doc))


@api_bp.route("/documents")
@auth_required()
def list_documents():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    status = request.args.get("status")
    doc_type = request.args.get("type")
    vendor = request.args.get("vendor")
    search = request.args.get("search")

    query = _doc_query()

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
@auth_required()
def get_document(doc_id):
    doc = _get_doc_or_404(doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    result = _doc_to_dict(doc)
    result["metadata_json"] = doc.metadata_json
    return jsonify(result)


@api_bp.route("/documents/<int:doc_id>", methods=["PATCH"])
@auth_required([UserRole.ADMIN, UserRole.REVIEWER])
def update_document(doc_id):
    doc = _get_doc_or_404(doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    data = request.get_json(silent=True) or {}
    editable = ["document_type", "vendor", "execution_status", "retention_category", "review_notes"]
    changes = {}
    for field in editable:
        if field in data:
            old = getattr(doc, field)
            new = data[field]
            setattr(doc, field, new)
            changes[field] = {"old": old, "new": new}
    if "effective_date" in data:
        doc.effective_date = datetime.strptime(data["effective_date"], "%Y-%m-%d").date() if data["effective_date"] else None
        changes["effective_date"] = data["effective_date"]
    if "expiration_date" in data:
        doc.expiration_date = datetime.strptime(data["expiration_date"], "%Y-%m-%d").date() if data["expiration_date"] else None
        changes["expiration_date"] = data["expiration_date"]
    if data.get("mark_reviewed"):
        user = current_user()
        doc.review_status = ReviewStatus.REVIEWED
        doc.reviewed_by_id = user.id if user else None
        doc.reviewed_at = datetime.now(timezone.utc)
        changes["review_status"] = ReviewStatus.REVIEWED.value
    audit("document.update", document_id=doc.id, details={"changes": changes})
    db.session.commit()
    return jsonify(_doc_to_dict(doc))


@api_bp.route("/documents/<int:doc_id>/download")
@auth_required()
def download_document(doc_id):
    doc = _get_doc_or_404(doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    storage = get_storage_backend() if doc.stored_path.startswith("s3://") else None
    if storage:
        if not storage.exists(doc.stored_path):
            return jsonify({"error": "Stored file not found"}), 404
        handle = storage.read(doc.stored_path)
        return send_file(handle, as_attachment=True, download_name=doc.generated_filename or doc.original_name)
    if not os.path.exists(doc.stored_path):
        return jsonify({"error": "Stored file not found"}), 404
    return send_file(doc.stored_path, as_attachment=True, download_name=doc.generated_filename or doc.original_name)


@api_bp.route("/documents/<int:doc_id>/audit")
@auth_required([UserRole.ADMIN, UserRole.REVIEWER])
def document_audit(doc_id):
    doc = _get_doc_or_404(doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    query = AuditEvent.query.filter_by(document_id=doc.id).order_by(AuditEvent.created_at.desc())
    return jsonify({"events": [_audit_to_dict(e) for e in query.limit(100).all()]})


@api_bp.route("/audit")
@auth_required([UserRole.ADMIN])
def audit_events():
    query = AuditEvent.query
    tenant_id = current_tenant_id()
    if tenant_id:
        query = query.filter(AuditEvent.tenant_id == tenant_id)
    events = query.order_by(AuditEvent.created_at.desc()).limit(200).all()
    return jsonify({"events": [_audit_to_dict(e) for e in events]})


@api_bp.route("/documents/stats")
@auth_required()
def document_stats():
    query = _doc_query()
    total = query.count()
    by_status = dict(query.with_entities(Document.status, func.count(Document.id)).group_by(Document.status).all())
    by_type = dict(query.with_entities(Document.document_type, func.count(Document.id)).filter(Document.document_type.isnot(None)).group_by(Document.document_type).all())
    by_execution = dict(query.with_entities(Document.execution_status, func.count(Document.id)).filter(Document.execution_status.isnot(None)).group_by(Document.execution_status).all())
    by_review = dict(query.with_entities(Document.review_status, func.count(Document.id)).group_by(Document.review_status).all())

    return jsonify({
        "total": total,
        "by_status": {_enum_value(k): v for k, v in by_status.items()},
        "by_type": by_type,
        "by_execution_status": by_execution,
        "by_review_status": {_enum_value(k): v for k, v in by_review.items()},
    })
