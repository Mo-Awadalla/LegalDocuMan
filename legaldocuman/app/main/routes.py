import os

from flask import Blueprint, Response, current_app, jsonify, render_template, send_file, send_from_directory
from sqlalchemy import text

from ..extensions import db
from ..models import DocumentJob, DocumentJobAttempt, DocumentJobStatus

main_bp = Blueprint("main", __name__)

FRONTEND_DIST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "frontend", "dist",
)


def _serve_spa():
    index_path = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.exists(index_path):
        return send_file(index_path)
    return render_template("upload.html")


@main_bp.route("/assets/<path:filename>")
def serve_static(filename):
    return send_from_directory(os.path.join(FRONTEND_DIST, "assets"), filename)


@main_bp.route("/")
def index():
    return _serve_spa()


@main_bp.route("/upload")
@main_bp.route("/documents")
@main_bp.route("/documents/<int:doc_id>")
def spa_routes(**kwargs):
    return _serve_spa()


@main_bp.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@main_bp.route("/readyz")
def readyz():
    checks = {}
    try:
        db.session.execute(text("select 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
    if current_app.config.get("JOB_BACKEND") == "rq":
        try:
            from redis import Redis

            from ..worker import ready_worker_count

            redis = Redis.from_url(current_app.config["REDIS_URL"])
            redis.ping()
            checks["redis"] = "ok"
            checks["ready_workers"] = ready_worker_count(redis)
            checks["workers"] = "ok" if checks["ready_workers"] >= 1 else "error"
        except Exception:
            checks.update(redis="error", workers="error", ready_workers=0)
    else:
        checks.update(redis="not_required", workers="not_required", ready_workers=0)
    try:
        from legaldocuman.storage import get_storage_backend
        storage = get_storage_backend()
        if storage.name == "local":
            checks["storage"] = "ok" if os.access(storage.base_dir, os.R_OK | os.W_OK) else "error"
        else:
            storage.client.head_bucket(Bucket=storage.bucket)
            checks["storage"] = "ok"
    except Exception:
        checks["storage"] = "error"
    required = ("database", "storage") if current_app.config.get("JOB_BACKEND") != "rq" else (
        "database", "redis", "storage", "workers"
    )
    ok = all(checks.get(name) == "ok" for name in required)
    return jsonify({"status": "ok" if ok else "error", **checks}), 200 if ok else 503


def _metric(name, help_text, metric_type, samples):
    lines = [f"# HELP {name} {help_text}", f"# TYPE {name} {metric_type}"]
    lines.extend(f"{name}{labels} {value}" for labels, value in samples)
    return lines


@main_bp.route("/metrics")
def metrics():
    """Multiprocess-safe metrics derived from shared PostgreSQL and Redis state."""
    from redis import Redis
    from rq import Queue
    from rq.registry import ScheduledJobRegistry

    from ..worker import ready_worker_count

    redis = Redis.from_url(current_app.config["REDIS_URL"])
    queue = Queue(current_app.config["RQ_QUEUE"], connection=redis)
    scheduled = ScheduledJobRegistry(queue=queue).count
    active = DocumentJob.query.filter(DocumentJob.status == DocumentJobStatus.PROCESSING).count()
    retries = DocumentJobAttempt.query.filter(DocumentJobAttempt.status.in_(["retry_scheduled", "abandoned"])).count()
    successes = DocumentJob.query.filter(DocumentJob.status == DocumentJobStatus.COMPLETED).count()
    failures = DocumentJob.query.filter(DocumentJob.status == DocumentJobStatus.FAILED).count()
    durations = [row[0] / 1000.0 for row in db.session.query(DocumentJobAttempt.duration_ms).filter(
        DocumentJobAttempt.status == "completed", DocumentJobAttempt.duration_ms.isnot(None)
    ).all()]
    lines = []
    lines += _metric("legaldocuman_queue_depth", "Queued document jobs.", "gauge", [("", queue.count)])
    lines += _metric("legaldocuman_scheduled_depth", "Scheduled retry jobs.", "gauge", [("", scheduled)])
    lines += _metric("legaldocuman_active_jobs", "Currently processing jobs.", "gauge", [("", active)])
    lines += _metric("legaldocuman_workers", "Worker process counts.", "gauge", [
        ('{state="ready"}', ready_worker_count(redis)),
        ('{state="configured"}', int(current_app.config["WORKER_CONCURRENCY"])),
    ])
    lines += _metric("legaldocuman_job_retries_total", "Retryable or abandoned attempts.", "counter", [("", retries)])
    lines += _metric("legaldocuman_jobs_total", "Terminal document jobs.", "counter", [
        ('{outcome="success"}', successes), ('{outcome="failure"}', failures),
    ])
    buckets = (10, 30, 60, 120, 300, 600, 900)
    histogram = [(f'{{le="{bucket}"}}', sum(value <= bucket for value in durations)) for bucket in buckets]
    histogram.append(('{le="+Inf"}', len(durations)))
    lines.extend([
        "# HELP legaldocuman_processing_duration_seconds Completed attempt duration.",
        "# TYPE legaldocuman_processing_duration_seconds histogram",
    ])
    lines.extend(f"legaldocuman_processing_duration_seconds_bucket{labels} {value}" for labels, value in histogram)
    lines.append(f"legaldocuman_processing_duration_seconds_count {len(durations)}")
    lines.append(f"legaldocuman_processing_duration_seconds_sum {sum(durations):.3f}")
    return Response("\n".join(lines) + "\n", mimetype="text/plain; version=0.0.4")
