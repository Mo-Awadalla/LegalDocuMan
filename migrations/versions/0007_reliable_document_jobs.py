"""reliable document job state and immutable storage keys

Revision ID: 0007_reliable_jobs
Revises: 0006_document_relationships
"""
from alembic import op
import sqlalchemy as sa


revision = "0007_reliable_jobs"
down_revision = "0006_document_relationships"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE documentjobstatus ADD VALUE IF NOT EXISTS 'RETRY_SCHEDULED'")
    with op.batch_alter_table("documents") as batch:
        batch.add_column(sa.Column("source_storage_key", sa.String(1000)))
        batch.add_column(sa.Column("result_storage_key", sa.String(1000)))
    op.execute("""
        UPDATE documents SET
          source_storage_key = COALESCE(storage_key, stored_path),
          result_storage_key = CASE WHEN status = 'COMPLETED' THEN COALESCE(storage_key, stored_path) ELSE NULL END
    """)
    with op.batch_alter_table("document_jobs") as batch:
        batch.add_column(sa.Column("failure_kind", sa.String(100)))
        batch.add_column(sa.Column("correlation_id", sa.String(100)))
        batch.add_column(sa.Column("rq_job_id", sa.String(200)))
        batch.add_column(sa.Column("parent_job_id", sa.Integer(), sa.ForeignKey("document_jobs.id")))
        batch.add_column(sa.Column("queued_at", sa.DateTime()))
        batch.add_column(sa.Column("retry_at", sa.DateTime()))
        batch.add_column(sa.Column("heartbeat_at", sa.DateTime()))
        batch.add_column(sa.Column("lease_token", sa.String(64)))
    op.execute("UPDATE document_jobs SET correlation_id = 'legacy-' || id::text, rq_job_id = 'document-job:' || id::text")
    op.alter_column("document_jobs", "correlation_id", nullable=False)
    op.create_index("ix_document_jobs_status", "document_jobs", ["status"])
    op.create_index("ix_document_jobs_retry_at", "document_jobs", ["retry_at"])
    op.create_index("ix_document_jobs_correlation_id", "document_jobs", ["correlation_id"])
    op.create_unique_constraint("uq_document_jobs_rq_job_id", "document_jobs", ["rq_job_id"])
    op.create_table(
        "document_job_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("document_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("worker_name", sa.String(200)),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("lease_token", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime()),
        sa.Column("finished_at", sa.DateTime()),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("retryable", sa.Boolean()),
        sa.Column("error_code", sa.String(100)),
        sa.Column("error_message", sa.String(500)),
        sa.Column("termination_reason", sa.String(100)),
        sa.UniqueConstraint("job_id", "attempt_number", name="uq_job_attempt_number"),
    )
    op.create_index("ix_document_job_attempts_job_id", "document_job_attempts", ["job_id"])


def downgrade():
    op.drop_index("ix_document_job_attempts_job_id", table_name="document_job_attempts")
    op.drop_table("document_job_attempts")
    op.drop_constraint("uq_document_jobs_rq_job_id", "document_jobs", type_="unique")
    op.drop_index("ix_document_jobs_correlation_id", table_name="document_jobs")
    op.drop_index("ix_document_jobs_retry_at", table_name="document_jobs")
    op.drop_index("ix_document_jobs_status", table_name="document_jobs")
    with op.batch_alter_table("document_jobs") as batch:
        for column in ("lease_token", "heartbeat_at", "retry_at", "queued_at", "parent_job_id", "rq_job_id", "correlation_id", "failure_kind"):
            batch.drop_column(column)
    with op.batch_alter_table("documents") as batch:
        batch.drop_column("result_storage_key")
        batch.drop_column("source_storage_key")
    # PostgreSQL enum values intentionally remain; removing one requires recreating the type.
