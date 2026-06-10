"""create documents table

Revision ID: 0001_create_documents
Revises:
Create Date: 2026-06-10 00:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_create_documents"
down_revision = None
branch_labels = None
depends_on = None


document_status = sa.Enum(
    "PENDING",
    "PROCESSING",
    "COMPLETED",
    "FAILED",
    name="documentstatus",
)


def upgrade():
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("original_name", sa.String(length=500), nullable=False),
        sa.Column("stored_path", sa.String(length=1000), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("status", document_status, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("document_type", sa.String(length=50), nullable=True),
        sa.Column("vendor", sa.String(length=200), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column("retention_category", sa.String(length=50), nullable=True),
        sa.Column("execution_status", sa.String(length=20), nullable=True),
        sa.Column("generated_filename", sa.String(length=500), nullable=True),
        sa.Column("processed_folder", sa.String(length=20), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("documents")
    document_status.drop(op.get_bind(), checkfirst=True)
