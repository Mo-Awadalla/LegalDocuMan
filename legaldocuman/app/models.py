import enum
import hashlib
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentJobStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    RETRY_SCHEDULED = "retry_scheduled"
    COMPLETED = "completed"
    FAILED = "failed"


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    REVIEWER = "reviewer"
    USER = "user"


class ReviewStatus(str, enum.Enum):
    NOT_REQUIRED = "not_required"
    NEEDS_REVIEW = "needs_review"
    REVIEWED = "reviewed"


class ScanStatus(str, enum.Enum):
    PENDING = "pending"
    CLEAN = "clean"
    INFECTED = "infected"
    ERROR = "error"


class Tenant(db.Model):
    __tablename__ = "tenants"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    slug = db.Column(db.String(100), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    name = db.Column(db.String(200), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(UserRole, create_type=False), default=UserRole.USER, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    tenant = db.relationship("Tenant", backref="users")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Document(db.Model):
    __tablename__ = "documents"
    __table_args__ = (
        db.Index("ix_documents_tenant_status_created", "tenant_id", "status", "created_at"),
        db.Index("ix_documents_tenant_review_created", "tenant_id", "review_status", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=True, index=True)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    original_name = db.Column(db.String(500), nullable=False)
    stored_path = db.Column(db.String(1000), nullable=False)
    storage_backend = db.Column(db.String(50), default="local", nullable=False)
    storage_key = db.Column(db.String(1000))
    source_storage_key = db.Column(db.String(1000))
    result_storage_key = db.Column(db.String(1000))
    file_size = db.Column(db.Integer)
    checksum = db.Column(db.String(64))
    status = db.Column(db.Enum(DocumentStatus, create_type=False), default=DocumentStatus.PENDING, nullable=False)
    error_message = db.Column(db.Text)

    scan_status = db.Column(db.Enum(ScanStatus, create_type=False), default=ScanStatus.PENDING, nullable=False)
    scan_message = db.Column(db.Text)
    scanned_at = db.Column(db.DateTime)

    review_status = db.Column(db.Enum(ReviewStatus, create_type=False), default=ReviewStatus.NOT_REQUIRED, nullable=False)
    review_notes = db.Column(db.Text)
    reviewed_at = db.Column(db.DateTime)

    document_type = db.Column(db.String(50))
    vendor = db.Column(db.String(200))
    effective_date = db.Column(db.Date)
    expiration_date = db.Column(db.Date)
    renewal_date = db.Column(db.Date)
    review_date = db.Column(db.Date)
    termination_date = db.Column(db.Date)
    retention_category = db.Column(db.String(50))
    execution_status = db.Column(db.String(20))
    generated_filename = db.Column(db.String(500))
    processed_folder = db.Column(db.String(20))
    metadata_json = db.Column(db.JSON)
    extracted_text = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    tenant = db.relationship("Tenant")
    uploaded_by = db.relationship("User", foreign_keys=[uploaded_by_id])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])

    @classmethod
    def compute_checksum(cls, filepath):
        sha = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)
        return sha.hexdigest()


class DocumentRelationship(db.Model):
    __tablename__ = "document_relationships"
    __table_args__ = (
        db.UniqueConstraint("source_document_id", "target_document_id", name="uq_document_relationship_pair"),
        db.CheckConstraint("source_document_id <> target_document_id", name="ck_document_relationship_distinct"),
        db.Index("ix_document_relationships_tenant_source", "tenant_id", "source_document_id"),
        db.Index("ix_document_relationships_tenant_target", "tenant_id", "target_document_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    source_document_id = db.Column(db.Integer, db.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    target_document_id = db.Column(db.Integer, db.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    relationship_type = db.Column(db.String(50), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    source_document = db.relationship("Document", foreign_keys=[source_document_id])
    target_document = db.relationship("Document", foreign_keys=[target_document_id])
    created_by = db.relationship("User")


class AuditEvent(db.Model):
    __tablename__ = "audit_events"
    __table_args__ = (db.Index("ix_audit_events_tenant_created", "tenant_id", "created_at"),)

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=True, index=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.JSON)
    ip_address = db.Column(db.String(100))
    user_agent = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    tenant = db.relationship("Tenant")
    user = db.relationship("User")
    document = db.relationship("Document")



class DocumentJob(db.Model):
    __tablename__ = "document_jobs"
    __table_args__ = (db.Index("ix_document_jobs_tenant_status_created", "tenant_id", "status", "created_at"),)

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=True, index=True)
    status = db.Column(
        db.Enum(DocumentJobStatus, create_type=False), default=DocumentJobStatus.PENDING, nullable=False, index=True
    )
    backend = db.Column(db.String(50), nullable=False)
    attempts = db.Column(db.Integer, default=0, nullable=False)
    max_attempts = db.Column(db.Integer, default=3, nullable=False)
    last_error = db.Column(db.Text)
    failure_kind = db.Column(db.String(100))
    correlation_id = db.Column(db.String(100), nullable=False, index=True)
    rq_job_id = db.Column(db.String(200), unique=True)
    parent_job_id = db.Column(db.Integer, db.ForeignKey("document_jobs.id"), nullable=True)
    queued_at = db.Column(db.DateTime)
    retry_at = db.Column(db.DateTime, index=True)
    heartbeat_at = db.Column(db.DateTime)
    lease_token = db.Column(db.String(64))
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    document = db.relationship("Document", backref="jobs")
    tenant = db.relationship("Tenant")
    parent_job = db.relationship("DocumentJob", remote_side=[id], backref="redrives")
    attempt_history = db.relationship(
        "DocumentJobAttempt", back_populates="job", order_by="DocumentJobAttempt.attempt_number",
        cascade="all, delete-orphan",
    )


class DocumentJobAttempt(db.Model):
    __tablename__ = "document_job_attempts"
    __table_args__ = (db.UniqueConstraint("job_id", "attempt_number", name="uq_job_attempt_number"),)

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("document_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_number = db.Column(db.Integer, nullable=False)
    worker_name = db.Column(db.String(200))
    status = db.Column(db.String(50), nullable=False)
    lease_token = db.Column(db.String(64), nullable=False)
    started_at = db.Column(db.DateTime, nullable=False)
    heartbeat_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    duration_ms = db.Column(db.Integer)
    retryable = db.Column(db.Boolean)
    error_code = db.Column(db.String(100))
    error_message = db.Column(db.String(500))
    termination_reason = db.Column(db.String(100))

    job = db.relationship("DocumentJob", back_populates="attempt_history")
