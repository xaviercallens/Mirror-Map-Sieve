#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# S20 Spectral Attention Kernel — Kernel Latency Microbenchmark
"""
Measures raw kernel latency for S20 spectral attention vs standard softmax
attention (torch.nn.functional.scaled_dot_product_attention).

Timing:
    GPU  → torch.cuda.Event(enable_timing=True)
    CPU  → time.perf_counter_ns()

Warmup: 10 runs (discarded), then 100 timed runs.
Reports: median, mean, p95, p99 latency in milliseconds.

Parameter sweep:
    seq_len    ∈ {512, 1024, 2048, 4096}
    n_heads    = 32
    d_head     = 128
    window_size ∈ {4, 8, 16, 32, 64}
    batch_size = 1
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F

# ---------------------------------------------------------------------------
# Import S20 kernel (may not be built yet)
# ---------------------------------------------------------------------------
_S20_AVAILABLE = False
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from s15_kernel.attention import S20SpectralAttention  # type: ignore
    _S20_AVAILABLE = True
except ImportError:
    S20SpectralAttention = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WARMUP_RUNS = 10
TIMED_RUNS = 100

SEQ_LENS = [512, 1024, 2048, 4096]
N_HEADS = 32
D_HEAD = 128
WINDOW_SIZES = [4, 8, 16, 32, 64]
BATCH_SIZE = 1


# ---------------------------------------------------------------------------
# Hardware metadata
# ---------------------------------------------------------------------------
def _gather_hw_metadata() -> dict[str, Any]:
    """Collect hardware + software metadata for reproducibility."""
    meta: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "torch_version": torch.__version__,
        "platform": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
    }
    if torch.cuda.is_available():
        meta["cuda_version"] = torch.version.cuda
        meta["cudnn_version"] = str(torch.backends.cudnn.version())
        meta["gpu_name"] = torch.cuda.get_device_name(0)
        meta["gpu_count"] = torch.cuda.device_count()
        props = torch.cuda.get_device_properties(0)
        meta["gpu_memory_gb"] = round(props.total_mem / (1024**3), 2)
        # Try to get driver version via nvidia-smi
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                meta["driver_version"] = result.stdout.strip()
        except Exception:
            pass
    else:
        meta["cuda_version"] = None
        meta["gpu_name"] = "CPU-only"
    meta["s20_kernel_available"] = _S20_AVAILABLE
    return meta


# ---------------------------------------------------------------------------
# Timing helpers
# ---------------------------------------------------------------------------
def _time_gpu(fn, n_warmup: int, n_runs: int) -> list[float]:
    """Time *fn* on CUDA using cuda Events. Returns list of ms."""
    for _ in range(n_warmup):
        fn()
    torch.cuda.synchronize()

    times_ms: list[float] = []
    for _ in range(n_runs):
        start = torch.cuda.Event(enable_timing=True)
        end = torch.cuda.Event(enable_timing=True)
        start.record()
        fn()
        end.record()
        torch.cuda.synchronize()
        times_ms.append(start.elapsed_time(end))
    return times_ms


def _time_cpu(fn, n_warmup: int, n_runs: int) -> list[float]:
    """Time *fn* on CPU using perf_counter_ns. Returns list of ms."""
    for _ in range(n_warmup):
        fn()

    times_ms: list[float] = []
    for _ in range(n_runs):
        t0 = time.perf_counter_ns()
        fn()
        t1 = time.perf_counter_ns()
        times_ms.append((t1 - t0) / 1e6)
    return times_ms


def _summarise(times_ms: list[float]) -> dict[str, float]:
    """Compute summary statistics from a list of latencies (ms)."""
    s = sorted(times_ms)
    n = len(s)
    return {
        "median_ms": round(statistics.median(s), 4),
        "mean_ms": round(statistics.mean(s), 4),
        "std_ms": round(statistics.stdev(s), 4) if n > 1 else 0.0,
        "min_ms": round(s[0], 4),
        "max_ms": round(s[-1], 4),
        "p95_ms": round(s[int(n * 0.95)], 4),
        "p99_ms": round(s[int(n * 0.99)], 4),
        "n_runs": n,
    }


# ---------------------------------------------------------------------------
# Benchmark runners
# ---------------------------------------------------------------------------
def _run_sdpa_baseline(
    batch: int, seq_len: int, n_heads: int, d_head: int, device: torch.device
) -> dict[str, Any]:
    """Benchmark torch scaled_dot_product_attention."""
    q = torch.randn(batch, n_heads, seq_len, d_head, device=device)
    k = torch.randn(batch, n_heads, seq_len, d_head, device=device)
    v = torch.randn(batch, n_heads, seq_len, d_head, device=device)

    def _fn():
        F.scaled_dot_product_attention(q, k, v, is_causal=True)

    timer = _time_gpu if device.type == "cuda" else _time_cpu
    raw = timer(_fn, WARMUP_RUNS, TIMED_RUNS)
    return _summarise(raw)


def _run_s20_attention(
    batch: int,
    seq_len: int,
    n_heads: int,
    d_head: int,
    window_size: int,
    device: torch.device,
) -> dict[str, Any]:
    """Benchmark S20SpectralAttention forward pass."""
    if not _S20_AVAILABLE:
        return {"error": "S20SpectralAttention not available (kernel not built yet)"}

    attn = S20SpectralAttention(
        d_model=n_heads * d_head,
        n_heads=n_heads,
        window_size=window_size,
    ).to(device).eval()

    x = torch.randn(batch, seq_len, n_heads * d_head, device=device)

    def _fn():
        with torch.no_grad():
            attn(x)

    timer = _time_gpu if device.type == "cuda" else _time_cpu
    raw = timer(_fn, WARMUP_RUNS, TIMED_RUNS)
    return _summarise(raw)


# ---------------------------------------------------------------------------
# Full sweep
# ---------------------------------------------------------------------------
def run_latency_sweep(
    device: torch.device | None = None,
    seq_lens: list[int] | None = None,
    window_sizes: list[int] | None = None,
) -> dict[str, Any]:
    """Execute the full parameter sweep and return structured results."""
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if seq_lens is None:
        seq_lens = SEQ_LENS
    if window_sizes is None:
        window_sizes = WINDOW_SIZES

    metadata = _gather_hw_metadata()
    metadata["device"] = str(device)

    results: list[dict[str, Any]] = []
    total = len(seq_lens) * (1 + len(window_sizes))
    step = 0

    for seq_len in seq_lens:
        # --- Baseline (SDPA) ---
        step += 1
        print(
            f"  [{step}/{total}] SDPA baseline  seq_len={seq_len:>5}  ...",
            end="",
            flush=True,
        )
        baseline = _run_sdpa_baseline(BATCH_SIZE, seq_len, N_HEADS, D_HEAD, device)
        baseline.update(
            kernel="sdpa_baseline",
            seq_len=seq_len,
            n_heads=N_HEADS,
            d_head=D_HEAD,
            batch_size=BATCH_SIZE,
            window_size=None,
        )
        results.append(baseline)
        print(f"  {baseline.get('median_ms', 'N/A')} ms (median)")

        # --- S20 for each window size ---
        for ws in window_sizes:
            step += 1
            print(
                f"  [{step}/{total}] S20 attention  seq_len={seq_len:>5}  W={ws:<3} ...",
                end="",
                flush=True,
            )
            s20 = _run_s20_attention(BATCH_SIZE, seq_len, N_HEADS, D_HEAD, ws, device)
            s20.update(
                kernel="s20_spectral",
                seq_len=seq_len,
                n_heads=N_HEADS,
                d_head=D_HEAD,
                batch_size=BATCH_SIZE,
                window_size=ws,
            )
            results.append(s20)
            print(f"  {s20.get('median_ms', s20.get('error', 'N/A'))} ms (median)")

    return {"metadata": metadata, "results": results}


# ---------------------------------------------------------------------------
# Pretty-print table
# ---------------------------------------------------------------------------
def _print_table(data: dict[str, Any]) -> None:
    """Print a human-readable summary table to stdout."""
    results = data["results"]
    header = (
        f"{'Kernel':<18} {'SeqLen':>6} {'W':>4} "
        f"{'Median':>9} {'Mean':>9} {'p95':>9} {'p99':>9} {'Std':>9}"
    )
    print("\n" + "=" * len(header))
    print("S20 Spectral Attention — Kernel Latency Benchmark")
    print(f"Device: {data['metadata'].get('gpu_name', 'CPU')}")
    print(f"Torch:  {data['metadata']['torch_version']}")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for r in results:
        if "error" in r:
            print(
                f"{r['kernel']:<18} {r['seq_len']:>6} "
                f"{str(r.get('window_size', '')):>4}  "
                f"  ** {r['error']} **"
            )
            continue
        ws_str = str(r["window_size"]) if r["window_size"] is not None else "-"
        print(
            f"{r['kernel']:<18} {r['seq_len']:>6} {ws_str:>4} "
            f"{r['median_ms']:>8.3f}ms {r['mean_ms']:>8.3f}ms "
            f"{r['p95_ms']:>8.3f}ms {r['p99_ms']:>8.3f}ms "
            f"{r['std_ms']:>8.3f}ms"
        )
    print("=" * len(header) + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="S20 Spectral Attention — Kernel Latency Microbenchmark"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to write JSON results (default: output/s20_benchmarks/latency_<ts>.json)",
    )
    parser.add_argument(
        "--seq-lens",
        type=int,
        nargs="+",
        default=SEQ_LENS,
        help="Sequence lengths to sweep",
    )
    parser.add_argument(
        "--window-sizes",
        type=int,
        nargs="+",
        default=WINDOW_SIZES,
        help="Window sizes to sweep",
    )
    parser.add_argument(
        "--cpu",
        action="store_true",
        help="Force CPU even if CUDA is available",
    )
    args = parser.parse_args()

    device = torch.device("cpu") if args.cpu else None

    print("=" * 60)
    print("S20 Spectral Attention — Kernel Latency Benchmark")
    print("=" * 60)
    if not _S20_AVAILABLE:
        print(
            "[WARN] S20SpectralAttention not importable — "
            "S20 rows will report errors. Build the kernel first."
        )

    data = run_latency_sweep(
        device=device,
        seq_lens=args.seq_lens,
        window_sizes=args.window_sizes,
    )
    _print_table(data)

    # --- Save JSON ---
    if args.output:
        out_path = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        out_path = (
            Path(__file__).resolve().parent.parent.parent
            / "output"
            / "s20_benchmarks"
            / f"latency_{ts}.json"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump(data, fh, indent=2, default=str)
    print(f"Results saved to {out_path}")


if __name__ == "__main__":
    main()
