# Document pipeline benchmarks

The benchmark compares the pre-upgrade single worker at revision `19f0b63` with the current durable pipeline at one and two workers. Results are meaningful only when every configuration runs on the same CPU-only host from clean PostgreSQL, Redis, upload, and result volumes.

## What the driver verifies

Each configuration gets one warm-up document followed by batches of 10, 50, and 100 synthetic PDFs. The external HTTP driver records:

- revision and image identity, host CPU/RAM/OS, and dependency versions;
- fixture mix and configured/observed concurrency;
- documents/minute, queue-drain time, and average/p95 processing and end-to-end latency;
- average/peak app-and-worker CPU and RSS;
- retries, failures, unique result identities, and successful PDF downloads.

Timing is informational. A run fails when the queue does not drain, a job fails, observed concurrency exceeds its bound, result identities are duplicated, or a successful document cannot be downloaded as a PDF.

## Reproducible procedure

Run configurations sequentially on an otherwise idle host. Do not compare GitHub matrix artifacts as if they came from one physical host.

For the current revision, build once and run both concurrency settings. The commands use host port 15000 to avoid common local port-5000 conflicts:

```bash
docker compose down -v --remove-orphans
APP_PORT=15000 WORKER_CONCURRENCY=1 docker compose up -d --build --wait

for size in 10 50 100; do
  python3 scripts/benchmark_pipeline.py \
    --base-url http://localhost:15000 \
    --batch-size "$size" \
    --configured-concurrency 1 \
    --revision "$(git rev-parse HEAD)" \
    --image-digest "$(docker inspect --format='{{.Image}}' "$(docker compose ps -q app)")" \
    --output "benchmarks/raw/upgraded-one-worker-${size}.json"
done

docker compose down -v --remove-orphans
APP_PORT=15000 WORKER_CONCURRENCY=2 docker compose up -d --build --wait

for size in 10 50 100; do
  python3 scripts/benchmark_pipeline.py \
    --base-url http://localhost:15000 \
    --batch-size "$size" \
    --configured-concurrency 2 \
    --revision "$(git rev-parse HEAD)" \
    --image-digest "$(docker inspect --format='{{.Image}}' "$(docker compose ps -q app)")" \
    --output "benchmarks/raw/upgraded-two-workers-${size}.json"
done

docker compose down -v --remove-orphans
```

Run the baseline from a separate worktree after the upgraded stack is down. The baseline Compose file exposes port 3000 and already uses one worker:

```bash
benchmark_root="$(pwd)"
git worktree add ../LegalDocuMan-baseline 19f0b63
cd ../LegalDocuMan-baseline
docker compose down -v --remove-orphans
docker compose up -d --build

for size in 10 50 100; do
  python3 "$benchmark_root/scripts/benchmark_pipeline.py" \
    --base-url http://localhost:3000 \
    --batch-size "$size" \
    --configured-concurrency 1 \
    --revision 19f0b63 \
    --image-digest "$(docker inspect --format='{{.Image}}' "$(docker compose ps -q app)")" \
    --output "$benchmark_root/benchmarks/raw/baseline-one-worker-${size}.json"
done

docker compose down -v --remove-orphans
```

The driver supports both the baseline job response and the durable attempt-history response and writes baseline results directly into the current worktree. The synthetic fixtures are committed under `tests/fixtures/`; no real legal documents or third-party downloads are used.

The manual benchmark workflow measures the current revision at one and two workers and uploads raw JSON artifacts. It is useful for individual runs, but its matrix jobs are not a same-host baseline comparison.

## Measured comparison

No throughput claim is published until all nine comparison runs have been collected on the same host. Replace `pending` only with values computed from the checked-in raw JSON; never use estimates or results from different machines.

| Configuration | Batch | Docs/min | Avg / p95 processing | Avg / p95 E2E | Drain | Max concurrency | Result |
|---|---:|---:|---:|---:|---:|---:|---|
| Baseline `19f0b63`, 1 worker | 10/50/100 | pending | pending | pending | pending | pending | pending |
| Upgraded, 1 worker | 10/50/100 | pending | pending | pending | pending | pending | pending |
| Upgraded, 2 workers | 10/50/100 | pending | pending | pending | pending | pending | pending |

Once measured, add this README bullet with the actual same-batch values: “Reworked document processing with bounded workers and idempotent retries, increasing throughput from X to Y documents per minute while preserving recoverable job state.”
