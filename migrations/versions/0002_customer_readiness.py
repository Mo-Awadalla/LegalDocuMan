"""add tenants users audit review scan storage fields

Revision ID: 0002_customer_readiness
Revises: 0001_create_documents
Create Date: 2026-06-10 00:00:01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002_customer_readiness"
down_revision = "0001_create_documents"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE TYPE userrole AS ENUM ('ADMIN', 'REVIEWER', 'USER')")
    op.execute("CREATE TYPE reviewstatus AS ENUM ('NOT_REQUIRED', 'NEEDS_REVIEW', 'REVIEWED')")
    op.execute("CREATE TYPE scanstatus AS ENUM ('PENDING', 'CLEAN', 'INFECTED', 'ERROR')")
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", postgresql.ENUM(name="userrole", create_type=False), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    with op.batch_alter_table("documents") as batch:
        batch.add_column(sa.Column("tenant_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("uploaded_by_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("reviewed_by_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("storage_backend", sa.String(length=50), nullable=False, server_default="local"))
        batch.add_column(sa.Column("storage_key", sa.String(length=1000), nullable=True))
        batch.add_column(sa.Column("scan_status", postgresql.ENUM(name="scanstatus", create_type=False), nullable=False, server_default="CLEAN"))
        batch.add_column(sa.Column("scan_message", sa.Text(), nullable=True))
        batch.add_column(sa.Column("scanned_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("review_status", postgresql.ENUM(name="reviewstatus", create_type=False), nullable=False, server_default="NOT_REQUIRED"))
        batch.add_column(sa.Column("review_notes", sa.Text(), nullable=True))
        batch.add_column(sa.Column("reviewed_at", sa.DateTime(), nullable=True))
        batch.create_foreign_key("fk_documents_tenant_id", "tenants", ["tenant_id"], ["id"])
        batch.create_foreign_key("fk_documents_uploaded_by_id", "users", ["uploaded_by_id"], ["id"])
        batch.create_foreign_key("fk_documents_reviewed_by_id", "users", ["reviewed_by_id"], ["id"])
    op.create_index("ix_documents_tenant_id", "documents", ["tenant_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=100), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_audit_events_tenant_id", "audit_events", ["tenant_id"])
    op.create_index("ix_audit_events_document_id", "audit_events", ["document_id"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade():
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_document_id", table_name="audit_events")
    op.drop_index("ix_audit_events_tenant_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_documents_tenant_id", table_name="documents")
    with op.batch_alter_table("documents") as batch:
        batch.drop_constraint("fk_documents_reviewed_by_id", type_="foreignkey")
        batch.drop_constraint("fk_documents_uploaded_by_id", type_="foreignkey")
        batch.drop_constraint("fk_documents_tenant_id", type_="foreignkey")
        batch.drop_column("reviewed_at")
        batch.drop_column("review_notes")
        batch.drop_column("review_status")
        batch.drop_column("scanned_at")
        batch.drop_column("scan_message")
        batch.drop_column("scan_status")
        batch.drop_column("storage_key")
        batch.drop_column("storage_backend")
        batch.drop_column("reviewed_by_id")
        batch.drop_column("uploaded_by_id")
        batch.drop_column("tenant_id")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_table("tenants")
    op.execute("DROP TYPE IF EXISTS scanstatus")
    op.execute("DROP TYPE IF EXISTS reviewstatus")
    op.execute("DROP TYPE IF EXISTS userrole")
