"""add SaaS query indexes

Revision ID: 0004_saas_query_indexes
Revises: 0003_document_jobs
Create Date: 2026-07-01 00:00:00
"""
from alembic import op


revision = "0004_saas_query_indexes"
down_revision = "0003_document_jobs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_documents_tenant_status_created", "documents", ["tenant_id", "status", "created_at"])
    op.create_index("ix_documents_tenant_review_created", "documents", ["tenant_id", "review_status", "created_at"])
    op.create_index("ix_audit_events_tenant_created", "audit_events", ["tenant_id", "created_at"])
    op.create_index("ix_document_jobs_tenant_status_created", "document_jobs", ["tenant_id", "status", "created_at"])


def downgrade():
    op.drop_index("ix_document_jobs_tenant_status_created", table_name="document_jobs")
    op.drop_index("ix_audit_events_tenant_created", table_name="audit_events")
    op.drop_index("ix_documents_tenant_review_created", table_name="documents")
    op.drop_index("ix_documents_tenant_status_created", table_name="documents")
