# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# S20 Spectral Attention Kernel — Benchmark Suite
"""
Benchmark suite for the S20 Spectral Attention kernel.

Modules:
    benchmark_latency  — Raw kernel microbenchmark (GPU timing, latency percentiles)
    benchmark_mmlu     — End-to-end MMLU accuracy evaluation via lm-evaluation-harness
    benchmark_tpot     — Time-Per-Output-Token + energy measurement
"""

__all__ = [
    "benchmark_latency",
    "benchmark_mmlu",
    "benchmark_tpot",
]
