"""External, revision-independent HTTP benchmark driver for LegalDocuMan."""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import statistics
import subprocess
import threading
import time
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path


def percentile(values, fraction):
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int(len(ordered) * fraction + 0.999) - 1))]


def parse_bytes(value):
    match = re.fullmatch(r"([0-9.]+)\s*([A-Za-z]+)", value.strip())
    if not match:
        raise ValueError(f"unrecognized byte value: {value}")
    number, unit = match.groups()
    factors = {"B": 1, "kB": 1000, "KB": 1000, "KiB": 1024, "MB": 1000**2, "MiB": 1024**2,
               "GB": 1000**3, "GiB": 1024**3}
    return float(number) * factors.get(unit, 1)


def monitor_containers(stop, samples):
    while not stop.wait(1):
        try:
            rows = []
            for service in ("app", "worker"):
                output = subprocess.check_output(
                    ["docker", "compose", "stats", "--no-stream", "--format", "json", service], text=True
                )
                rows.extend(json.loads(line) for line in output.splitlines() if line.strip())
            cpu = sum(float(row["CPUPerc"].rstrip("%")) for row in rows)
            rss = sum(parse_bytes(row["MemUsage"].split("/")[0].strip()) for row in rows)
            samples.append((cpu, rss))
        except (FileNotFoundError, subprocess.SubprocessError, KeyError, ValueError, json.JSONDecodeError):
            return


def dependency_versions():
    code = (
        "import importlib.metadata as m, json; "
        "print(json.dumps({p:m.version(p) for p in "
        "['rq','redis','Flask','SQLAlchemy','pdfplumber','pytesseract','pdf2image','rfdetr','torch']}))"
    )
    try:
        return json.loads(subprocess.check_output(
            ["docker", "compose", "exec", "-T", "app", "python", "-c", code], text=True
        ))
    except (FileNotFoundError, subprocess.SubprocessError, json.JSONDecodeError):
        return {"python": platform.python_version()}


def processing_seconds(job):
    """Read processing time from both the baseline and durable-job APIs."""
    attempts = job.get("attempt_history")
    if attempts is not None:
        return sum((attempt.get("duration_ms") or 0) for attempt in attempts) / 1000
    if job.get("started_at") and job.get("finished_at"):
        started = datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))
        finished = datetime.fromisoformat(job["finished_at"].replace("Z", "+00:00"))
        return max(0.0, (finished - started).total_seconds())
    return 0.0


def result_identity(job):
    """Return the strongest result identity exposed by the target revision."""
    document = job["document"]
    return (
        document.get("result_storage_key")
        or document.get("generated_filename")
        or f"document-{document['id']}"
    )


class Client:
    def __init__(self, base_url, api_key):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def call(self, path, method="GET", body=None, content_type=None):
        headers = {"X-API-Key": self.api_key, "X-Correlation-ID": str(uuid.uuid4())}
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(self.base_url + path, method=method, data=body, headers=headers)
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read()
            return json.loads(data) if data else None

    def upload(self, path):
        boundary = f"----benchmark-{uuid.uuid4().hex}"
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
            "Content-Type: application/pdf\r\n\r\n"
        ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        return self.call("/api/v1/upload", "POST", body, f"multipart/form-data; boundary={boundary}")

    def download(self, document_id):
        request = urllib.request.Request(
            self.base_url + f"/api/v1/documents/{document_id}/download",
            headers={"X-API-Key": self.api_key, "X-Correlation-ID": str(uuid.uuid4())},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()


def wait_batch(client, jobs, timeout):
    pending = dict(jobs)
    finished = {}
    maximum_active = 0
    deadline = time.monotonic() + timeout
    while pending and time.monotonic() < deadline:
        active = 0
        for job_id, uploaded_at in list(pending.items()):
            job = client.call(f"/api/v1/jobs/{job_id}")
            if job["status"] == "processing":
                active += 1
            if job["status"] in {"completed", "failed"}:
                job["end_to_end_seconds"] = time.monotonic() - uploaded_at
                finished[job_id] = job
                del pending[job_id]
        maximum_active = max(maximum_active, active)
        if pending:
            time.sleep(1)
    if pending:
        raise RuntimeError(f"queue did not drain: {len(pending)} jobs remain")
    return list(finished.values()), maximum_active


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:5000")
    parser.add_argument("--api-key", default=os.environ.get("E2E_API_KEY", "change-me-in-production"))
    parser.add_argument("--batch-size", type=int, choices=(10, 50, 100), required=True)
    parser.add_argument("--configured-concurrency", type=int, required=True)
    parser.add_argument("--revision")
    parser.add_argument("--image-digest", default="unknown")
    parser.add_argument("--timeout", type=int, default=7200)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    client = Client(args.base_url, args.api_key)
    fixture_dir = Path(__file__).parents[1] / "tests" / "fixtures"
    fixtures = [fixture_dir / "Synthetic_Acme_LLC_scanned_signed_MSA.pdf",
                fixture_dir / "Synthetic_Acme_LLC_scanned_unsigned_agreement.pdf"]

    # Identical warm-up for each implementation/concurrency configuration.
    warmup = client.upload(fixtures[0])
    wait_batch(client, {warmup["job_id"]: time.monotonic()}, args.timeout)
    batch_started = time.monotonic()
    resource_samples = []
    monitor_stop = threading.Event()
    monitor = threading.Thread(target=monitor_containers, args=(monitor_stop, resource_samples), daemon=True)
    monitor.start()
    jobs = {}
    for index in range(args.batch_size):
        uploaded = client.upload(fixtures[index % len(fixtures)])
        jobs[uploaded["job_id"]] = time.monotonic()
    results, maximum_active = wait_batch(client, jobs, args.timeout)
    drain_seconds = time.monotonic() - batch_started
    monitor_stop.set()
    monitor.join(timeout=2)
    if not resource_samples:
        raise RuntimeError("no Docker resource samples were collected for app and worker")

    successful = [job for job in results if job["status"] == "completed"]
    processing = [processing_seconds(job) for job in results]
    e2e = [job["end_to_end_seconds"] for job in results]
    result_keys = [result_identity(job) for job in successful]
    retries = sum(max(0, len(job.get("attempt_history", [])) - 1) for job in results)
    download_failures = []
    for job in successful:
        try:
            content = client.download(job["document"]["id"])
            if not content.startswith(b"%PDF"):
                download_failures.append({"document_id": job["document"]["id"], "error": "invalid_pdf"})
        except Exception as exc:
            download_failures.append({"document_id": job["document"]["id"], "error": exc.__class__.__name__})
    report = {
        "revision": args.revision or subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "image_digest": args.image_digest,
        "host": {
            "cpu_count": os.cpu_count(),
            "ram_bytes": os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") if hasattr(os, "sysconf") else None,
            "os": platform.platform(),
        },
        "dependency_versions": dependency_versions(),
        "fixture_mix": {fixtures[0].name: (args.batch_size + 1) // 2, fixtures[1].name: args.batch_size // 2},
        "configured_concurrency": args.configured_concurrency,
        "batch_size": args.batch_size,
        "documents_per_minute": len(successful) / drain_seconds * 60,
        "processing_latency_seconds": {"average": statistics.mean(processing), "p95": percentile(processing, 0.95)},
        "end_to_end_latency_seconds": {"average": statistics.mean(e2e), "p95": percentile(e2e, 0.95)},
        "cpu_percent": {
            "average": statistics.mean(sample[0] for sample in resource_samples),
            "peak": max(sample[0] for sample in resource_samples),
        },
        "rss_bytes": {
            "average": statistics.mean(sample[1] for sample in resource_samples),
            "peak": max(sample[1] for sample in resource_samples),
        },
        "retries": retries,
        "failures": len(results) - len(successful),
        "queue_drain_seconds": drain_seconds,
        "maximum_observed_concurrency": maximum_active,
        "unique_result_count": len(set(result_keys)),
        "downloadable_result_count": len(successful) - len(download_failures),
        "download_failures": download_failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if (report["failures"] or download_failures or len(result_keys) != len(set(result_keys))
            or maximum_active > args.configured_concurrency):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
