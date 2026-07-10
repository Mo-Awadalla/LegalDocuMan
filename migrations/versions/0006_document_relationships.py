"""add document relationships

Revision ID: 0006_document_relationships
Revises: 0005_contract_lifecycle
Create Date: 2026-07-10 00:00:01
"""
from alembic import op
import sqlalchemy as sa


revision = "0006_document_relationships"
down_revision = "0005_contract_lifecycle"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "document_relationships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("source_document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relationship_type", sa.String(length=50), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("source_document_id <> target_document_id", name="ck_document_relationship_distinct"),
        sa.UniqueConstraint("source_document_id", "target_document_id", name="uq_document_relationship_pair"),
    )
    op.create_index("ix_document_relationships_tenant_id", "document_relationships", ["tenant_id"])
    op.create_index("ix_document_relationships_tenant_source", "document_relationships", ["tenant_id", "source_document_id"])
    op.create_index("ix_document_relationships_tenant_target", "document_relationships", ["tenant_id", "target_document_id"])


def downgrade():
    op.drop_index("ix_document_relationships_tenant_target", table_name="document_relationships")
    op.drop_index("ix_document_relationships_tenant_source", table_name="document_relationships")
    op.drop_index("ix_document_relationships_tenant_id", table_name="document_relationships")
    op.drop_table("document_relationships")