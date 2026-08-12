"""Nightly destructive-in-container worker-loss scenario for the RQ supervisor."""
import argparse
import json
import subprocess
import time
from pathlib import Path

from benchmark_pipeline import Client, wait_batch


def worker_pids(kind):
    code = (
        "from redis import Redis; from rq import Worker; import os; "
        "r=Redis.from_url(os.environ['REDIS_URL']); "
        f"print(' '.join(str(w.{kind}) for w in Worker.all(connection=r) "
        f"if w.{kind} and os.path.exists('/proc/'+str(w.{kind}))))"
    )
    output = subprocess.check_output(
        ["docker", "compose", "exec", "-T", "worker", "python", "-c", code], text=True
    )
    return [int(value) for value in output.split() if value.isdigit()]


def kill_in_worker(pid):
    subprocess.run(["docker", "compose", "exec", "-T", "worker", "sh", "-c", f"kill -9 {pid}"], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:5000")
    parser.add_argument("--api-key", default="change-me-in-production")
    parser.add_argument("--configured-concurrency", type=int, default=2)
    args = parser.parse_args()
    client = Client(args.base_url, args.api_key)
    fixture = Path(__file__).parents[1] / "tests/fixtures/Synthetic_Acme_LLC_scanned_signed_MSA.pdf"
    uploaded = client.upload(fixture)
    deadline = time.monotonic() + 300
    victim = None
    while time.monotonic() < deadline:
        job = client.call(f"/api/v1/jobs/{uploaded['job_id']}")
        attempts = job.get("attempt_history") or []
        worker_name = attempts[-1].get("worker") if attempts else None
        if job["status"] == "processing" and worker_name:
            candidate = worker_name.rsplit(":", 1)[-1]
            if candidate.isdigit():
                victim = int(candidate)
                break
        time.sleep(0.5)
    if not victim:
        raise RuntimeError("No active RQ worker observed")
    kill_in_worker(victim)
    results, _ = wait_batch(client, {uploaded["job_id"]: time.monotonic()}, 900)
    recovered = results[0]
    if recovered["status"] != "completed" or len(recovered["attempt_history"]) < 2:
        raise RuntimeError(f"SIGKILL job did not recover: {json.dumps(recovered)}")
    if not any(a["error_code"] == "worker_lost" for a in recovered["attempt_history"][:-1]):
        raise RuntimeError("Recovered job did not record worker_lost")
    if not recovered["document"]["result_storage_key"]:
        raise RuntimeError("Recovered job has no result")

    # Kill one idle RQ worker process and verify the supervisor restores the bound.
    pids = worker_pids("pid")
    kill_in_worker(pids[0])
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        ready_pids = worker_pids("pid")
        if len(ready_pids) >= args.configured_concurrency:
            print(json.dumps({"job_id": recovered["id"], "attempts": len(recovered["attempt_history"]),
                              "ready_workers": len(ready_pids)}))
            return
        time.sleep(1)
    raise RuntimeError("Supervisor did not restore configured worker concurrency")


if __name__ == "__main__":
    main()
