# Document pipeline benchmark

Baseline revision: `19f0b63` (the one-worker implementation immediately before this upgrade).

Run the same external driver against the baseline image with one worker, the upgraded image with one worker, and the upgraded image with two workers. Use CPU-only Docker limits, one warm-up document, and batch sizes 10, 50, and 100:

```bash
python3 scripts/benchmark_pipeline.py --batch-size 10 --configured-concurrency 2 \
  --revision "$(git rev-parse HEAD)" --image-digest "<digest>" \
  --output benchmarks/raw/upgraded-two-workers-10.json
```

Raw JSON captures revision/image identity, host information, dependency versions, fixture mix, throughput, average/p95 processing and end-to-end latency, sampled average/peak container CPU and RSS, retries, failures, drain time, and maximum observed concurrency. Timing is informational; correctness requires a complete drain, no failures, bounded observed concurrency, and one unique result per successful document.

## Measured comparison

No numbers are checked in until the three configurations have been run on the same host. Do not add the README resume bullet or fill throughput values from estimates. Docker was unavailable in the implementation environment, so this table is intentionally awaiting measurements.

| Configuration | Batch | Docs/min | Avg / p95 processing | Avg / p95 E2E | Drain | Max concurrency | Result |
|---|---:|---:|---:|---:|---:|---:|---|
| Baseline `19f0b63`, 1 worker | 10/50/100 | pending | pending | pending | pending | pending | pending |
| Upgraded, 1 worker | 10/50/100 | pending | pending | pending | pending | pending | pending |
| Upgraded, 2 workers | 10/50/100 | pending | pending | pending | pending | pending | pending |
