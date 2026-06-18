# Benchmarks

Benchmarking suite for the SocrateAI Scientific Agora.

## Metrics

| Metric | Description |
|--------|-------------|
| Accuracy | Correct answer rate with Wilson confidence intervals |
| Cost | USD per experiment / per query |
| Latency | End-to-end response time (p50, p95, p99) |
| Solver perf | ODE function evals, Jacobian evals, steps |
| Convergence | Dialectic cycles to convergence |

## Running Benchmarks

```bash
python benchmarks/runners/run_benchmark.py \
    --suite all \
    --output benchmarks/results/

python benchmarks/runners/analyze_results.py \
    --input benchmarks/results/ \
    --report benchmarks/results/report.md
```

## Benchmark Suites

1. **ODE Solver** — Robertson, Lorenz, Lotka-Volterra accuracy & perf
2. **Data Integrity** — False positive/negative rates on synthetic data
3. **Dialectic** — Convergence rate and cycle count
4. **Budget** — Cost accuracy and enforcement reliability
5. **NIM** — NVIDIA model latency and invariant check accuracy

## Patent

US-PAT-PEND-2026-0525
