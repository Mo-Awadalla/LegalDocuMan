"""Bounded RQ worker supervisor.

Runs exactly WORKER_CONCURRENCY worker processes and replaces unexpected exits.
"""
from __future__ import annotations

import json
import multiprocessing
import os
import signal
import socket
import threading
import time

from redis import Redis
from rq import Queue, Worker

from legaldocuman.app import create_app
from legaldocuman.app.processors.worker import (
    preload_pipeline,
    rq_exception_handler,
    rq_workhorse_killed_handler,
)

HEARTBEAT_PREFIX = "legaldocuman:worker:"


class CapableWorker(Worker):
    """Refresh the readiness capability key with RQ's native heartbeat."""

    def __init__(self, *args, capability_ttl=75, capabilities=None, **kwargs):
        name = kwargs.get("name")
        self.capability_ttl = capability_ttl
        self.capability_key = f"{HEARTBEAT_PREFIX}{name}"
        self.capability_payload = json.dumps(
            {"worker": name, "pid": os.getpid(), **(capabilities or {})}
        )
        super().__init__(*args, **kwargs)

    def heartbeat(self, timeout=None, pipeline=None):
        result = super().heartbeat(timeout=timeout, pipeline=pipeline)
        connection = pipeline if pipeline is not None else self.connection
        connection.setex(self.capability_key, self.capability_ttl, self.capability_payload)
        return result


def _run_worker(slot, shutdown=None):
    app = create_app()
    with app.app_context():
        connection = Redis.from_url(app.config["REDIS_URL"])
        queue = Queue(app.config["RQ_QUEUE"], connection=connection)
        name = f"{socket.gethostname()}-{slot}-{os.getpid()}"
        # RQ forks workhorses on Linux; this initialized model is inherited copy-on-write.
        capabilities = {"ocr": False, "signature": False}
        while not (shutdown and shutdown.is_set()):
            pipeline = preload_pipeline()
            capabilities = {
                "ocr": bool(pipeline.text_extractor.ocr_available),
                "signature": bool(pipeline.status_classifier.signature_detector),
            }
            if capabilities["ocr"] and capabilities["signature"]:
                break
            app.logger.error("worker capability initialization failed", extra={"capabilities": capabilities})
            if shutdown:
                shutdown.wait(30)
            else:
                time.sleep(30)
        if not (capabilities["ocr"] and capabilities["signature"]):
            return
        worker = CapableWorker(
            [queue], connection=connection, name=name,
            maintenance_interval=int(app.config["JOB_MAINTENANCE_SECONDS"]),
            exception_handlers=[rq_exception_handler],
            work_horse_killed_handler=rq_workhorse_killed_handler,
            capability_ttl=int(app.config["WORKER_HEARTBEAT_TTL_SECONDS"]),
            capabilities=capabilities,
            worker_ttl=45,
        )
        worker.heartbeat()
        try:
            worker.work(with_scheduler=True)
        finally:
            connection.delete(worker.capability_key)


def _reconcile_loop(stop):
    app = create_app()
    interval = int(app.config["JOB_MAINTENANCE_SECONDS"])
    while not stop.is_set():
        with app.app_context():
            try:
                from .jobs import reconcile_jobs
                reconcile_jobs()
            except Exception:
                app.logger.exception("job reconciliation failed")
        stop.wait(interval)


def ready_worker_count(connection):
    count = 0
    for key in connection.scan_iter(f"{HEARTBEAT_PREFIX}*"):
        try:
            capabilities = json.loads(connection.get(key) or "{}")
            if capabilities.get("ocr") and capabilities.get("signature"):
                count += 1
        except (TypeError, ValueError):
            continue
    return count


def worker_health():
    app = create_app()
    try:
        connection = Redis.from_url(app.config["REDIS_URL"])
        connection.ping()
        count = ready_worker_count(connection)
    except Exception as exc:
        return False, f"redis=error ready_workers=0 error={exc.__class__.__name__}"
    configured = int(app.config["WORKER_CONCURRENCY"])
    return count >= 1, f"redis=ok ready_workers={count} configured_workers={configured}"


def main():
    app = create_app()
    concurrency = int(app.config["WORKER_CONCURRENCY"])
    if concurrency < 1:
        raise SystemExit("WORKER_CONCURRENCY must be at least 1")
    stop = multiprocessing.Event()
    children = {}

    def request_stop(signum, frame):
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    for slot in range(concurrency):
        process = multiprocessing.Process(target=_run_worker, args=(slot, stop), name=f"document-worker-{slot}")
        process.start()
        children[slot] = process
    reconciler = threading.Thread(target=_reconcile_loop, args=(stop,), daemon=True)
    reconciler.start()
    try:
        while not stop.wait(1):
            for slot, process in list(children.items()):
                if not process.is_alive():
                    process.join(timeout=1)
                    replacement = multiprocessing.Process(target=_run_worker, args=(slot, stop), name=f"document-worker-{slot}")
                    replacement.start()
                    children[slot] = replacement
    finally:
        stop.set()
        for process in children.values():
            if process.is_alive():
                process.terminate()
        for process in children.values():
            process.join(timeout=10)
            if process.is_alive():
                process.kill()
        reconciler.join(timeout=2)


if __name__ == "__main__":
    main()
