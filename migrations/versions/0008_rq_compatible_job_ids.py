"""make deterministic RQ job IDs compatible with RQ 2.x

Revision ID: 0008_rq_job_ids
Revises: 0007_reliable_jobs
"""
from alembic import op


revision = "0008_rq_job_ids"
down_revision = "0007_reliable_jobs"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE document_jobs "
        "SET rq_job_id = replace(rq_job_id, 'document-job:', 'document-job-') "
        "WHERE rq_job_id LIKE 'document-job:%'"
    )


def downgrade():
    op.execute(
        "UPDATE document_jobs "
        "SET rq_job_id = replace(rq_job_id, 'document-job-', 'document-job:') "
        "WHERE rq_job_id LIKE 'document-job-%'"
    )
