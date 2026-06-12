"""add document jobs

Revision ID: 0003_document_jobs
Revises: 0002_customer_readiness
Create Date: 2026-06-10 00:00:02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0003_document_jobs"
down_revision = "0002_customer_readiness"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE TYPE documentjobstatus AS ENUM ('PENDING', 'QUEUED', 'PROCESSING', 'COMPLETED', 'FAILED')")
    op.create_table(
        "document_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("status", postgresql.ENUM(name="documentjobstatus", create_type=False), nullable=False),
        sa.Column("backend", sa.String(length=50), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_document_jobs_document_id", "document_jobs", ["document_id"])
    op.create_index("ix_document_jobs_tenant_id", "document_jobs", ["tenant_id"])
    op.create_index("ix_document_jobs_created_at", "document_jobs", ["created_at"])


def downgrade():
    op.drop_index("ix_document_jobs_created_at", table_name="document_jobs")
    op.drop_index("ix_document_jobs_tenant_id", table_name="document_jobs")
    op.drop_index("ix_document_jobs_document_id", table_name="document_jobs")
    op.drop_table("document_jobs")
    op.execute("DROP TYPE IF EXISTS documentjobstatus")
