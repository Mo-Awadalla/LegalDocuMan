import io
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from legaldocuman.app import create_app
from legaldocuman.app.extensions import db
from legaldocuman.app.models import Document, DocumentJob, DocumentJobStatus
from legaldocuman.config import Config


class FakeIntake:
    def __init__(self, error=None, exception=None):
        self.error = error
        self.exception = exception

    def analyze(self, path, vendor_folder):
        if self.exception:
            raise self.exception
        return SimpleNamespace(
            error=self.error,
            doc_type="MSA",
            status="final",
            vendor="Synthetic Acme LLC",
            clean_vendor="SyntheticAcmeLLC",
            date_str="2025-01-15",
            date_metadata={"effective_date": "2025-01-15", "expiration_date": "2027-01-15"},
            signature_analysis={"visual_signatures": 2, "review_required": False},
            text_content="Synthetic master services agreement",
        )

    def generate_filename_from_original(self, record, original_name, unique_id=None):
        return f"AGMT_SyntheticAcmeLLC_{unique_id:03d}.txt"


def make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'jobs.db'}")
    monkeypatch.setenv("AUTO_CREATE_DB", "1")
    monkeypatch.setenv("UPLOAD_FOLDER", str(tmp_path / "uploads"))
    monkeypatch.setenv("PROCESSED_FOLDER", str(tmp_path / "processed"))
    monkeypatch.setenv("JOB_BACKEND", "sync")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "password123")
    monkeypatch.setenv("ALLOW_OPEN_DEV_MODE", "0")
    Config._instance = None
    app = create_app()
    app.config.update(TESTING=True)
    return app


def login(client):
    response = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "password123"})
    return response.get_json()["token"]


def upload(client, token, correlation="test-correlation"):
    return client.post(
        "/api/v1/upload",
        headers={"Authorization": f"Bearer {token}", "X-Correlation-ID": correlation},
        data={"file": (io.BytesIO(b"synthetic agreement contents"), "synthetic.txt")},
        content_type="multipart/form-data",
    )


def test_source_is_immutable_result_is_deterministic_and_duplicate_delivery_is_safe(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    import legaldocuman.app.processors.worker as worker
    monkeypatch.setattr(worker, "preload_pipeline", lambda: FakeIntake())
    client = app.test_client()
    token = login(client)
    response = upload(client, token)
    assert response.status_code == 201
    assert response.headers["X-Correlation-ID"] == "test-correlation"
    assert response.get_json()["correlation_id"] == "test-correlation"

    with app.app_context():
        job = db.session.get(DocumentJob, response.get_json()["job_id"])
        document = db.session.get(Document, response.get_json()["id"])
        source = document.source_storage_key
        result = document.result_storage_key
        assert job.status == DocumentJobStatus.COMPLETED
        assert len(job.attempt_history) == 1
        assert source != result
        assert os.path.exists(source)
        assert os.path.exists(result)
        assert f"{os.sep}results{os.sep}{document.id}{os.sep}" in result
        worker._process_document(job.id)
        db.session.refresh(job)
        assert len(job.attempt_history) == 1
        assert document.result_storage_key == result


def test_transient_failure_schedules_retry_and_terminal_failure_does_not(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    import legaldocuman.app.processors.worker as worker
    client = app.test_client()
    token = login(client)

    monkeypatch.setattr(worker, "preload_pipeline", lambda: FakeIntake(exception=OSError("temporary storage outage")))
    transient = upload(client, token, "transient-correlation").get_json()
    with app.app_context():
        transient_job = db.session.get(DocumentJob, transient["job_id"])
        assert transient_job.status == DocumentJobStatus.RETRY_SCHEDULED
        assert transient_job.retry_at is not None
        assert 8 <= (transient_job.retry_at.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).total_seconds() <= 10
        assert transient_job.attempt_history[0].retryable is True
        assert transient_job.failure_kind == "storage_unavailable"

    monkeypatch.setattr(worker, "preload_pipeline", lambda: FakeIntake(error="corrupt document"))
    terminal = upload(client, token, "terminal-correlation").get_json()
    with app.app_context():
        terminal_job = db.session.get(DocumentJob, terminal["job_id"])
        assert terminal_job.status == DocumentJobStatus.FAILED
        assert terminal_job.attempt_history[0].retryable is False
        assert terminal_job.failure_kind == "extraction_failed"


def test_admin_redrive_preserves_history_and_is_idempotent(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    import legaldocuman.app.processors.worker as worker
    monkeypatch.setattr(worker, "preload_pipeline", lambda: FakeIntake(error="corrupt document"))
    client = app.test_client()
    token = login(client)
    failed = upload(client, token).get_json()
    headers = {"Authorization": f"Bearer {token}"}

    first = client.post(f"/api/v1/jobs/{failed['job_id']}/retry", headers=headers)
    second = client.post(f"/api/v1/jobs/{failed['job_id']}/retry", headers=headers)
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.get_json()["id"] == second.get_json()["id"]
    assert first.get_json()["parent_job_id"] == failed["job_id"]
    assert first.get_json()["correlation_id"] == failed["correlation_id"]
    with app.app_context():
        parent = db.session.get(DocumentJob, failed["job_id"])
        assert len(parent.attempt_history) == 1


def test_stale_lease_is_terminal_after_attempt_exhaustion(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    import legaldocuman.app.processors.worker as worker
    from legaldocuman.app.jobs import reconcile_jobs

    monkeypatch.setattr(worker, "preload_pipeline", lambda: FakeIntake(error="initial terminal state"))
    client = app.test_client()
    failed = upload(client, login(client)).get_json()
    with app.app_context():
        job = db.session.get(DocumentJob, failed["job_id"])
        attempt = job.attempt_history[0]
        job.status = DocumentJobStatus.PROCESSING
        job.attempts = job.max_attempts
        job.heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=120)
        job.lease_token = attempt.lease_token
        attempt.attempt_number = job.max_attempts
        attempt.status = "processing"
        attempt.finished_at = None
        db.session.commit()
        counts = reconcile_jobs()
        db.session.refresh(job)
        assert counts["failed"] == 1
        assert job.status == DocumentJobStatus.FAILED
        assert job.failure_kind == "worker_lost"
        assert attempt.termination_reason == "worker_lost"
