"""Real API → PostgreSQL → Redis/RQ → OCR/RF-DETR → download smoke test."""
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("RUN_REAL_E2E") != "1", reason="set RUN_REAL_E2E=1")
BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:3000")
API_KEY = os.environ.get("E2E_API_KEY", "change-me-in-production")
FIXTURES = Path(__file__).parents[1] / "fixtures"


def request(path, *, method="GET", data=None, content_type=None):
    headers = {"X-API-Key": API_KEY, "X-Correlation-ID": "e2e-smoke-correlation"}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(BASE_URL + path, method=method, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.status, dict(response.headers), response.read()


def upload(path):
    boundary = f"----legaldocuman-{uuid.uuid4().hex}"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
        "Content-Type: application/pdf\r\n\r\n"
    ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    status, headers, payload = request("/api/v1/upload", method="POST", data=body,
                                       content_type=f"multipart/form-data; boundary={boundary}")
    return status, headers, json.loads(payload)


def wait_for_job(job_id, timeout=900):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _, _, payload = request(f"/api/v1/jobs/{job_id}")
        job = json.loads(payload)
        if job["status"] in {"completed", "failed"}:
            return job
        time.sleep(2)
    raise AssertionError(f"job {job_id} did not drain within {timeout}s")


def test_real_signed_msa_smoke():
    status, headers, uploaded = upload(FIXTURES / "Synthetic_Acme_LLC_scanned_signed_MSA.pdf")
    assert status == 201
    assert headers["X-Correlation-Id"] == "e2e-smoke-correlation"
    job = wait_for_job(uploaded["job_id"])
    assert job["status"] == "completed", job
    assert job["correlation_id"] == "e2e-smoke-correlation"
    assert job["rq_job_id"] == f"document-job:{job['id']}"
    assert len(job["attempt_history"]) == 1
    assert job["attempt_history"][0]["status"] == "completed"

    document = job["document"]
    assert document["document_type"] == "MSA"
    assert "Synthetic" in document["vendor"]
    assert document["execution_status"] == "final"
    assert document["source_storage_key"]
    assert document["result_storage_key"]
    assert document["source_storage_key"] != document["result_storage_key"]
    _, _, detail_payload = request(f"/api/v1/documents/{document['id']}")
    detail = json.loads(detail_payload)
    detections = detail["metadata_json"]["signature_analysis"]["detections"]
    assert detections and all(detection["source"] == "rfdetr" for detection in detections)

    _, download_headers, result = request(f"/api/v1/documents/{document['id']}/download")
    assert result.startswith(b"%PDF")
    assert document["generated_filename"] in download_headers.get("Content-Disposition", "")


def test_corrupt_pdf_is_terminal_without_retry():
    _, _, uploaded = upload(FIXTURES / "corrupt.pdf")
    job = wait_for_job(uploaded["job_id"])
    assert job["status"] == "failed"
    assert job["failure_kind"] == "extraction_failed"
    assert len(job["attempt_history"]) == 1
    assert job["attempt_history"][0]["retryable"] is False
