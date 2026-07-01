import csv
import io
import os
import zipfile
from datetime import datetime, timezone

from flask import Blueprint, Response, current_app, jsonify, request, send_file
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from legaldocuman.storage import get_storage_backend

from ..auth import api_key_authenticated, audit, auth_required, authenticate_request, current_tenant_id, current_user, issue_download_token, issue_token, load_download_token
from ..extensions import db
from ..models import AuditEvent, Document, DocumentJob, DocumentJobStatus, DocumentStatus, ReviewStatus, ScanStatus, Tenant, User, UserRole
from ..processors.worker import process_document_async
from ..security import MalwareScanner

api_bp = Blueprint("api", __name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}
DOCUMENT_TYPES = {"MSA", "SOW", "NDA", "PO", "AMD", "LICENSE", "CONTRACT", "AGREEMENT", "OTHER"}
EXECUTION_STATUSES = {"draft", "final", "signed", "unsigned", "partially_executed", "unknown"}
RETENTION_CATEGORIES = {"short_term", "long_term", "indefinite", "tied_to_parent", "contracts", "review_required"}
MAX_REVIEW_NOTES = 4000


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def _doc_query():
    query = Document.query
    tenant_id = current_tenant_id()
    if tenant_id:
        query = query.filter(Document.tenant_id == tenant_id)
    elif api_key_authenticated():
        query = query.filter(Document.tenant_id.is_(None))
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




def _job_to_dict(job):
    return {
        "id": job.id,
        "document_id": job.document_id,
        "tenant_id": job.tenant_id,
        "status": job.status.value,
        "backend": job.backend,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "last_error": job.last_error,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "document": _doc_to_dict(job.document) if job.document else None,
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


def _user_to_dict(user):
    return {"id": user.id, "tenant_id": user.tenant_id, "email": user.email, "name": user.name, "role": user.role.value, "is_active": user.is_active}


def _tenant_to_dict(tenant):
    return {"id": tenant.id, "name": tenant.name, "slug": tenant.slug, "created_at": tenant.created_at.isoformat() if tenant.created_at else None}


def _parse_date(value, field):
    if value in (None, ""):
        return None, None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date(), None
    except (TypeError, ValueError):
        return None, f"{field} must be YYYY-MM-DD"


def _validate_local_upload(filepath, ext):
    if not filepath or filepath.startswith("s3://"):
        return None
    if not os.path.exists(filepath) or os.path.getsize(filepath) <= 0:
        return "Uploaded file is empty"
    with open(filepath, "rb") as handle:
        head = handle.read(8)
    if ext == ".pdf" and not head.startswith(b"%PDF"):
        return "Uploaded file content does not match .pdf extension"
    if ext == ".docx" and not zipfile.is_zipfile(filepath):
        return "Uploaded file content does not match .docx extension"
    if ext == ".txt" and b"\x00" in head:
        return "Uploaded file content does not match .txt extension"
    return None


@api_bp.route("/config/public")
def public_config():
    return jsonify({
        "max_upload_mb": int(current_app.config.get("MAX_UPLOAD_MB", 20)),
        "allowed_extensions": sorted(current_app.config.get("ALLOWED_EXTENSIONS", ALLOWED_EXTENSIONS)),
    })


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


@api_bp.route("/tenant", methods=["GET"])
@auth_required()
def get_tenant():
    tenant_id = current_tenant_id()
    if not tenant_id:
        return jsonify({"error": "Tenant not available"}), 404
    tenant = db.session.get(Tenant, tenant_id)
    return jsonify(_tenant_to_dict(tenant))


@api_bp.route("/tenant", methods=["PATCH"])
@auth_required([UserRole.ADMIN])
def update_tenant():
    tenant = db.session.get(Tenant, current_tenant_id())
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404
    data = request.get_json(silent=True) or {}
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "name is required"}), 400
        existing = Tenant.query.filter(Tenant.name == name, Tenant.id != tenant.id).first()
        if existing:
            return jsonify({"error": "Tenant name already exists"}), 409
        tenant.name = name
    if "slug" in data:
        slug = (data.get("slug") or "").strip()
        if not slug:
            return jsonify({"error": "slug is required"}), 400
        existing = Tenant.query.filter(Tenant.slug == slug, Tenant.id != tenant.id).first()
        if existing:
            return jsonify({"error": "Tenant slug already exists"}), 409
        tenant.slug = slug
    audit("tenant.update", details={"tenant_id": tenant.id})
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Tenant name or slug already exists"}), 409
    return jsonify(_tenant_to_dict(tenant))


@api_bp.route("/users")
@auth_required([UserRole.ADMIN])
def list_users():
    users = User.query.filter_by(tenant_id=current_tenant_id()).order_by(User.email.asc()).all()
    return jsonify({"users": [_user_to_dict(user) for user in users]})


@api_bp.route("/users", methods=["POST"])
@auth_required([UserRole.ADMIN])
def create_user():

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    name = (data.get("name") or email).strip()
    role = data.get("role") or UserRole.USER.value
    if role not in {r.value for r in UserRole}:
        return jsonify({"error": "Invalid role"}), 400
    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400
    if len(password) < 8:
        return jsonify({"error": "password must be at least 8 characters"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "User already exists"}), 409
    tenant_id = current_tenant_id()
    if not tenant_id:
        return jsonify({"error": "Tenant not available"}), 400
    user = User(tenant_id=tenant_id, email=email, name=name, role=UserRole(role))
    user.set_password(password)
    db.session.add(user)
    audit("user.create", details={"email": email, "role": role})
    db.session.commit()
    return jsonify({"id": user.id, "email": user.email, "role": user.role.value}), 201


@api_bp.route("/users/<int:user_id>", methods=["PATCH"])
@auth_required([UserRole.ADMIN])
def update_user(user_id):
    user = User.query.filter_by(id=user_id, tenant_id=current_tenant_id()).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    data = request.get_json(silent=True) or {}
    if "name" in data:
        user.name = (data.get("name") or "").strip() or user.name
    if "role" in data:
        role = data.get("role")
        if role not in {r.value for r in UserRole}:
            return jsonify({"error": "Invalid role"}), 400
        user.role = UserRole(role)
    if "is_active" in data:
        user.is_active = bool(data.get("is_active"))
    if "password" in data:
        password = data.get("password") or ""
        if len(password) < 8:
            return jsonify({"error": "password must be at least 8 characters"}), 400
        user.set_password(password)
    audit("user.update", details={"user_id": user.id})
    db.session.commit()
    return jsonify(_user_to_dict(user))


@api_bp.route("/users/<int:user_id>/deactivate", methods=["POST"])
@auth_required([UserRole.ADMIN])
def deactivate_user(user_id):
    user = User.query.filter_by(id=user_id, tenant_id=current_tenant_id()).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    user.is_active = False
    audit("user.deactivate", details={"user_id": user.id})
    db.session.commit()
    return jsonify(_user_to_dict(user))


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
    validation_error = _validate_local_upload(filepath, ext)
    if validation_error:
        storage.delete(filepath)
        return jsonify({"error": validation_error}), 400
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
    job = DocumentJob(
        document_id=doc.id,
        tenant_id=doc.tenant_id,
        backend=current_app.config.get("JOB_BACKEND", "thread"),
        status=DocumentJobStatus.PENDING,
    )
    db.session.add(job)
    db.session.flush()
    audit("document.upload", document_id=doc.id, details={"filename": original_name, "storage_backend": storage.name, "job_id": job.id})
    db.session.commit()

    process_document_async(job.id)
    db.session.refresh(doc)
    db.session.refresh(job)

    return jsonify({"id": doc.id, "job_id": job.id, "status": doc.status.value, "job_status": job.status.value}), 201


@api_bp.route("/jobs/<int:job_id>")
@auth_required()
def job_status(job_id):
    query = DocumentJob.query.filter(DocumentJob.id == job_id)
    tenant_id = current_tenant_id()
    if tenant_id:
        query = query.filter(DocumentJob.tenant_id == tenant_id)
    job = query.first()
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(_job_to_dict(job))


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


@api_bp.route("/documents/review-queue")
@auth_required([UserRole.ADMIN, UserRole.REVIEWER])
def review_queue():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    query = _doc_query().filter(Document.review_status == ReviewStatus.NEEDS_REVIEW).order_by(Document.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "documents": [_doc_to_dict(doc) for doc in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    })


@api_bp.route("/documents/export.csv")
@auth_required()
def export_documents_csv():
    output = io.StringIO()
    fields = ["id", "original_name", "document_type", "vendor", "execution_status", "effective_date", "expiration_date", "retention_category", "review_status", "created_at"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for doc in _doc_query().order_by(Document.created_at.desc()).all():
        row = _doc_to_dict(doc)
        writer.writerow({field: row.get(field) for field in fields})
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=documents.csv"})


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
    changes = {}

    if "document_type" in data:
        value = (data.get("document_type") or "").upper()
        if value and value not in DOCUMENT_TYPES:
            return jsonify({"error": "Invalid document_type"}), 400
        changes["document_type"] = {"old": doc.document_type, "new": value or None}
        doc.document_type = value or None
    if "execution_status" in data:
        value = (data.get("execution_status") or "").lower()
        if value and value not in EXECUTION_STATUSES:
            return jsonify({"error": "Invalid execution_status"}), 400
        changes["execution_status"] = {"old": doc.execution_status, "new": value or None}
        doc.execution_status = value or None
    if "retention_category" in data:
        value = (data.get("retention_category") or "").lower()
        if value and value not in RETENTION_CATEGORIES:
            return jsonify({"error": "Invalid retention_category"}), 400
        changes["retention_category"] = {"old": doc.retention_category, "new": value or None}
        doc.retention_category = value or None
    if "vendor" in data:
        doc.vendor = (data.get("vendor") or "").strip() or None
        changes["vendor"] = doc.vendor
    if "review_notes" in data:
        notes = data.get("review_notes") or ""
        if len(notes) > MAX_REVIEW_NOTES:
            return jsonify({"error": "review_notes is too long"}), 400
        doc.review_notes = notes
        changes["review_notes"] = True
    if "effective_date" in data:
        value, error = _parse_date(data.get("effective_date"), "effective_date")
        if error:
            return jsonify({"error": error}), 400
        doc.effective_date = value
        changes["effective_date"] = data.get("effective_date")
    if "expiration_date" in data:
        value, error = _parse_date(data.get("expiration_date"), "expiration_date")
        if error:
            return jsonify({"error": error}), 400
        doc.expiration_date = value
        changes["expiration_date"] = data.get("expiration_date")
    if doc.effective_date and doc.expiration_date and doc.expiration_date < doc.effective_date:
        return jsonify({"error": "expiration_date cannot be before effective_date"}), 400
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
def download_document(doc_id):
    download_token = request.args.get("download_token", "")
    if download_token:
        token_data = load_download_token(download_token)
        if not token_data or token_data.get("document_id") != doc_id:
            return jsonify({"error": "Invalid or expired download token"}), 401
        doc = Document.query.filter(Document.id == doc_id, Document.tenant_id == token_data.get("tenant_id")).first()
    else:
        auth_error = authenticate_request()
        if auth_error:
            return auth_error
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


@api_bp.route("/documents/<int:doc_id>/download-token", methods=["POST"])
@auth_required()
def mint_download_token(doc_id):
    doc = _get_doc_or_404(doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    user = current_user()
    token = issue_download_token(doc.id, doc.tenant_id, user.id if user else None)
    audit("document.download_token", document_id=doc.id)
    db.session.commit()
    return jsonify({
        "download_token": token,
        "expires_in": int(current_app.config.get("DOWNLOAD_TOKEN_TTL_SECONDS", 300)),
    })


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
