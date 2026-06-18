#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# S20 Spectral Attention Kernel — Full Benchmark Orchestrator
"""
Orchestrates the complete S20 benchmark suite:

    Step 1: Precompute decay tables (S₂₀ and S₁₅), verify first 5 values
    Step 2: Run kernel latency benchmark
    Step 3: Run MMLU evaluation (if --mmlu flag set)
    Step 4: Run TPOT + energy measurement (if --tpot flag set)
    Step 5: Generate summary JSON combining all results

All results are saved to output/s20_benchmarks/ with timestamp.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Ensure parent is on path
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_KERNEL_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------
def _check_torch() -> bool:
    try:
        import torch
        return True
    except ImportError:
        print(
            "[FATAL] PyTorch is required.\n"
            "  pip install torch"
        )
        return False


def _print_system_info() -> dict[str, Any]:
    """Print and return system information."""
    import torch

    info: dict[str, Any] = {
        "python_version": platform.python_version(),
        "torch_version": torch.__version__,
        "platform": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
    }

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║        S20 Spectral Attention — Full Benchmark Suite        ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print(f"  Python:   {info['python_version']}")
    print(f"  PyTorch:  {info['torch_version']}")
    print(f"  Platform: {info['platform']}")

    if torch.cuda.is_available():
        info["cuda_version"] = torch.version.cuda
        info["gpu_name"] = torch.cuda.get_device_name(0)
        info["gpu_count"] = torch.cuda.device_count()
        props = torch.cuda.get_device_properties(0)
        info["gpu_memory_gb"] = round(props.total_memory / (1024**3), 2)
        print(f"  CUDA:     {info['cuda_version']}")
        print(f"  GPU:      {info['gpu_name']} ({info['gpu_memory_gb']} GB)")
        print(f"  GPU(s):   {info['gpu_count']}")
    else:
        info["cuda_version"] = None
        info["gpu_name"] = "CPU-only"
        print("  GPU:      None (CPU-only mode)")
        print()
        print("  ⚠  No CUDA GPU detected.")
        print("     Kernel latency benchmark will run on CPU.")
        print("     MMLU and TPOT benchmarks require a GPU for meaningful results.")

    print()
    return info


# ---------------------------------------------------------------------------
# Step 1: Precompute decay tables
# ---------------------------------------------------------------------------
def _step1_decay_tables() -> dict[str, Any]:
    """Compute S₂₀ and S₁₅ decay tables and verify first 5 values."""
    print("─" * 60)
    print("STEP 1: Precompute decay tables")
    print("─" * 60)

    result: dict[str, Any] = {"status": "skipped"}

    try:
        from s15_kernel.sequence import compute_s20, compute_decay_table  # type: ignore

        import torch
        # S20 table
        print("  Computing S₂₀ decay table …")
        s20_table = compute_decay_table("s20", max_d=64, dtype=torch.float32)
        s20_first5 = [round(float(v), 8) for v in s20_table[:5]]
        print(f"  S₂₀ first 5 values: {s20_first5}")

        # S15 table
        print("  Computing S₁₅ decay table …")
        s15_table = compute_decay_table("s15", max_d=64, dtype=torch.float32)
        s15_first5 = [round(float(v), 8) for v in s15_table[:5]]
        print(f"  S₁₅ first 5 values: {s15_first5}")

        # Verify monotonic decay
        s20_monotonic = all(s20_table[i] >= s20_table[i + 1] for i in range(min(len(s20_table) - 1, 10)))
        s15_monotonic = all(s15_table[i] >= s15_table[i + 1] for i in range(min(len(s15_table) - 1, 10)))

        result = {
            "status": "ok",
            "s20_first5": s20_first5,
            "s15_first5": s15_first5,
            "s20_length": len(s20_table),
            "s15_length": len(s15_table),
            "s20_monotonic_first10": s20_monotonic,
            "s15_monotonic_first10": s15_monotonic,
        }

        if s20_monotonic and s15_monotonic:
            print("  ✓ Both tables are monotonically decreasing (first 10 entries)")
        else:
            print("  ⚠ Monotonicity check failed — verify sequence implementation")

    except ImportError:
        print("  ⚠ s15_kernel.sequence not available — skipping decay table verification.")
        print("    Build the kernel first: the other agent is working on this.")
        result = {"status": "import_error", "message": "s15_kernel.sequence not importable"}
    except Exception as exc:
        print(f"  ✗ Error: {exc}")
        result = {"status": "error", "message": str(exc)}

    print()
    return result


# ---------------------------------------------------------------------------
# Step 2: Kernel latency benchmark
# ---------------------------------------------------------------------------
def _step2_latency(seq_lens: list[int] | None = None) -> dict[str, Any]:
    """Run the kernel latency microbenchmark."""
    print("─" * 60)
    print("STEP 2: Kernel latency benchmark")
    print("─" * 60)

    try:
        from s15_kernel.benchmarks.benchmark_latency import run_latency_sweep
    except ImportError as exc:
        msg = f"Could not import benchmark_latency: {exc}"
        print(f"  ✗ {msg}")
        return {"status": "import_error", "message": msg}

    try:
        data = run_latency_sweep(seq_lens=seq_lens)
        print("  ✓ Latency benchmark complete")
        print()
        return {"status": "ok", "data": data}
    except Exception as exc:
        print(f"  ✗ Error: {exc}")
        traceback.print_exc()
        return {"status": "error", "message": str(exc)}


# ---------------------------------------------------------------------------
# Step 3: MMLU evaluation
# ---------------------------------------------------------------------------
def _step3_mmlu(
    model_name: str = "google/gemma-2-2b-it",
    limit: int | None = None,
) -> dict[str, Any]:
    """Run MMLU evaluation (baseline + S20)."""
    print("─" * 60)
    print("STEP 3: MMLU evaluation")
    print("─" * 60)

    try:
        from s15_kernel.benchmarks.benchmark_mmlu import run_mmlu
    except ImportError as exc:
        msg = f"Could not import benchmark_mmlu: {exc}"
        print(f"  ✗ {msg}")
        return {"status": "import_error", "message": msg}

    results: dict[str, Any] = {}

    # Baseline
    print("\n  --- Baseline ---")
    try:
        results["baseline"] = run_mmlu(
            model_name=model_name, mode="baseline", limit=limit,
        )
    except Exception as exc:
        print(f"  ✗ Baseline failed: {exc}")
        results["baseline"] = {"status": "error", "message": str(exc)}

    # S20
    print("\n  --- S20 ---")
    try:
        results["s20"] = run_mmlu(
            model_name=model_name, mode="s20", limit=limit,
        )
    except Exception as exc:
        print(f"  ✗ S20 failed: {exc}")
        results["s20"] = {"status": "error", "message": str(exc)}

    # Delta
    b_acc = results.get("baseline", {}).get("overall_accuracy")
    s_acc = results.get("s20", {}).get("overall_accuracy")
    if b_acc is not None and s_acc is not None:
        results["delta_accuracy"] = round(s_acc - b_acc, 4)
        results["delta_accuracy_pct"] = round(100 * (s_acc - b_acc) / b_acc, 2) if b_acc else None
        print(f"\n  Accuracy delta: {results['delta_accuracy']:+.4f} ({results['delta_accuracy_pct']:+.2f}%)")

    print()
    return {"status": "ok", **results}


# ---------------------------------------------------------------------------
# Step 4: TPOT + energy
# ---------------------------------------------------------------------------
def _step4_tpot(
    model_name: str = "google/gemma-2-2b-it",
    max_tokens: int = 256,
) -> dict[str, Any]:
    """Run TPOT + energy measurement."""
    print("─" * 60)
    print("STEP 4: TPOT + Energy measurement")
    print("─" * 60)

    try:
        from s15_kernel.benchmarks.benchmark_tpot import run_comparative
    except ImportError as exc:
        msg = f"Could not import benchmark_tpot: {exc}"
        print(f"  ✗ {msg}")
        return {"status": "import_error", "message": msg}

    try:
        data = run_comparative(
            model_name=model_name,
            max_new_tokens=max_tokens,
        )
        print("  ✓ TPOT benchmark complete")
        print()
        return {"status": "ok", "data": data}
    except Exception as exc:
        print(f"  ✗ Error: {exc}")
        traceback.print_exc()
        return {"status": "error", "message": str(exc)}


# ---------------------------------------------------------------------------
# Step 5: Summary
# ---------------------------------------------------------------------------
def _print_final_summary(summary: dict[str, Any]) -> None:
    """Print a formatted summary table."""
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║                    BENCHMARK SUMMARY                        ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    # Decay tables
    dt = summary.get("step1_decay_tables", {})
    status = dt.get("status", "?")
    icon = "✓" if status == "ok" else "⚠" if status == "import_error" else "✗"
    print(f"\n  {icon} Step 1 — Decay Tables: {status}")
    if status == "ok":
        print(f"         S₂₀ first 5: {dt.get('s20_first5', [])}")
        print(f"         S₁₅ first 5: {dt.get('s15_first5', [])}")

    # Latency
    lat = summary.get("step2_latency", {})
    status = lat.get("status", "?")
    icon = "✓" if status == "ok" else "⚠" if status == "import_error" else "✗"
    print(f"\n  {icon} Step 2 — Kernel Latency: {status}")
    if status == "ok" and "data" in lat:
        n = len(lat["data"].get("results", []))
        print(f"         {n} configurations benchmarked")

    # MMLU
    mmlu = summary.get("step3_mmlu", {})
    status = mmlu.get("status", "skipped")
    icon = "✓" if status == "ok" else "–" if status == "skipped" else "✗"
    print(f"\n  {icon} Step 3 — MMLU: {status}")
    if status == "ok":
        b_acc = mmlu.get("baseline", {}).get("overall_accuracy")
        s_acc = mmlu.get("s20", {}).get("overall_accuracy")
        if b_acc is not None:
            print(f"         Baseline accuracy: {b_acc:.4f}")
        if s_acc is not None:
            print(f"         S20 accuracy:      {s_acc:.4f}")
        if mmlu.get("delta_accuracy") is not None:
            print(f"         Delta:             {mmlu['delta_accuracy']:+.4f}")

    # TPOT
    tpot = summary.get("step4_tpot", {})
    status = tpot.get("status", "skipped")
    icon = "✓" if status == "ok" else "–" if status == "skipped" else "✗"
    print(f"\n  {icon} Step 4 — TPOT + Energy: {status}")
    if status == "ok" and "data" in tpot:
        delta = tpot["data"].get("delta", {})
        if delta.get("median_tpot_delta_pct") is not None:
            print(f"         TPOT delta: {delta['median_tpot_delta_pct']:+.2f}%")
        if delta.get("j_per_token_delta") is not None:
            print(f"         J/token delta: {delta['j_per_token_delta']:+.6f}")

    out_path = summary.get("output_path", "?")
    print(f"\n  📁 Full results: {out_path}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="S20 Spectral Attention — Full Benchmark Orchestrator"
    )
    parser.add_argument(
        "--mmlu",
        action="store_true",
        help="Run MMLU evaluation (skipped by default for quick runs)",
    )
    parser.add_argument(
        "--tpot",
        action="store_true",
        help="Run TPOT + energy benchmark (skipped by default)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all benchmarks (equivalent to --mmlu --tpot)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="google/gemma-2-2b-it",
        help="HuggingFace model for MMLU/TPOT benchmarks",
    )
    parser.add_argument(
        "--mmlu-limit",
        type=int,
        default=None,
        help="Limit examples per MMLU task (for fast debugging)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=256,
        help="Max tokens to generate for TPOT benchmark",
    )
    parser.add_argument(
        "--seq-lens",
        type=int,
        nargs="+",
        default=None,
        help="Sequence lengths for latency sweep (default: 512 1024 2048 4096)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory (default: output/s20_benchmarks/)",
    )
    args = parser.parse_args()

    if args.all:
        args.mmlu = True
        args.tpot = True

    # --- System checks ---
    if not _check_torch():
        sys.exit(1)

    system_info = _print_system_info()

    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    if args.output_dir:
        out_dir = Path(args.output_dir)
    else:
        out_dir = _REPO_ROOT / "output" / "s20_benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "benchmark_suite": "S20 Spectral Attention",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "system_info": system_info,
    }

    wall_start = time.perf_counter()

    # --- Step 1: Decay tables ---
    summary["step1_decay_tables"] = _step1_decay_tables()

    # --- Step 2: Latency ---
    summary["step2_latency"] = _step2_latency(seq_lens=args.seq_lens)

    # Save latency data separately
    lat_data = summary["step2_latency"].get("data")
    if lat_data:
        lat_path = out_dir / f"latency_{ts}.json"
        with open(lat_path, "w") as fh:
            json.dump(lat_data, fh, indent=2, default=str)
        print(f"  Latency results → {lat_path}")

    # --- Step 3: MMLU ---
    if args.mmlu:
        summary["step3_mmlu"] = _step3_mmlu(
            model_name=args.model,
            limit=args.mmlu_limit,
        )
        mmlu_data = summary["step3_mmlu"]
        mmlu_path = out_dir / f"mmlu_{ts}.json"
        with open(mmlu_path, "w") as fh:
            json.dump(mmlu_data, fh, indent=2, default=str)
        print(f"  MMLU results → {mmlu_path}")
    else:
        summary["step3_mmlu"] = {"status": "skipped"}
        print("\n  ─ Step 3 (MMLU) skipped. Use --mmlu to enable.\n")

    # --- Step 4: TPOT ---
    if args.tpot:
        summary["step4_tpot"] = _step4_tpot(
            model_name=args.model,
            max_tokens=args.max_tokens,
        )
        tpot_data = summary["step4_tpot"]
        tpot_path = out_dir / f"tpot_{ts}.json"
        with open(tpot_path, "w") as fh:
            json.dump(tpot_data, fh, indent=2, default=str)
        print(f"  TPOT results → {tpot_path}")
    else:
        summary["step4_tpot"] = {"status": "skipped"}
        print("\n  ─ Step 4 (TPOT) skipped. Use --tpot to enable.\n")

    # --- Step 5: Combined summary ---
    wall_elapsed = time.perf_counter() - wall_start
    summary["wall_time_s"] = round(wall_elapsed, 2)

    summary_path = out_dir / f"summary_{ts}.json"
    summary["output_path"] = str(summary_path)
    with open(summary_path, "w") as fh:
        json.dump(summary, fh, indent=2, default=str)

    _print_final_summary(summary)
    print(f"Total wall time: {wall_elapsed:.1f}s")
    print(f"Summary saved to {summary_path}")


if __name__ == "__main__":
    main()
