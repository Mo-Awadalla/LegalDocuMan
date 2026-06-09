import enum
import hashlib
from datetime import datetime, timezone

from .extensions import db


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    original_name = db.Column(db.String(500), nullable=False)
    stored_path = db.Column(db.String(1000), nullable=False)
    file_size = db.Column(db.Integer)
    checksum = db.Column(db.String(64))
    status = db.Column(db.Enum(DocumentStatus), default=DocumentStatus.PENDING, nullable=False)
    error_message = db.Column(db.Text)

    document_type = db.Column(db.String(50))
    vendor = db.Column(db.String(200))
    effective_date = db.Column(db.Date)
    expiration_date = db.Column(db.Date)
    retention_category = db.Column(db.String(50))
    execution_status = db.Column(db.String(20))
    generated_filename = db.Column(db.String(500))
    processed_folder = db.Column(db.String(20))
    metadata_json = db.Column(db.JSON)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    @classmethod
    def compute_checksum(cls, filepath):
        sha = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)
        return sha.hexdigest()
