"""Stable identifiers shared by PostgreSQL jobs and RQ."""


def rq_job_id(database_job_id):
    """Return an RQ-compatible deterministic ID for a database job."""
    return f"document-job-{database_job_id}"
