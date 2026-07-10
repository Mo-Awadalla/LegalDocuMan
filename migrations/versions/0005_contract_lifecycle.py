"""add contract lifecycle fields and extracted text

Revision ID: 0005_contract_lifecycle
Revises: 0004_saas_query_indexes
Create Date: 2026-07-10 00:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = "0005_contract_lifecycle"
down_revision = "0004_saas_query_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documents", sa.Column("renewal_date", sa.Date(), nullable=True))
    op.add_column("documents", sa.Column("review_date", sa.Date(), nullable=True))
    op.add_column("documents", sa.Column("termination_date", sa.Date(), nullable=True))
    op.add_column("documents", sa.Column("extracted_text", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("documents", "extracted_text")
    op.drop_column("documents", "termination_date")
    op.drop_column("documents", "review_date")
    op.drop_column("documents", "renewal_date")