#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# S20 Spectral Attention Kernel — MMLU Evaluation Benchmark
"""
End-to-end MMLU accuracy evaluation using lm-evaluation-harness.

Modes:
    --baseline  Run the unmodified model on MMLU.
    --s20       Run the model with S20 attention monkey-patched in.

Default model: google/gemma-2-2b-it  (small, fast iteration).
Standard 5-shot MMLU evaluation.
Tracks GPU memory usage during evaluation.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------
def _check_lm_eval() -> bool:
    """Return True if lm_eval is importable, else print instructions."""
    try:
        import lm_eval  # noqa: F401
        return True
    except ImportError:
        print(
            "\n"
            "╔══════════════════════════════════════════════════════════════╗\n"
            "║  lm-evaluation-harness is required but not installed.      ║\n"
            "║                                                            ║\n"
            "║  Install with:                                             ║\n"
            "║    pip install lm-eval[vllm]                               ║\n"
            "║  or from source:                                           ║\n"
            "║    pip install git+https://github.com/EleutherAI/          ║\n"
            "║      lm-evaluation-harness.git                             ║\n"
            "╚══════════════════════════════════════════════════════════════╝\n"
        )
        return False


def _check_torch() -> bool:
    try:
        import torch  # noqa: F401
        return True
    except ImportError:
        print("[ERROR] PyTorch is required. Install with: pip install torch")
        return False


# ---------------------------------------------------------------------------
# S20 kernel import (may not be built yet)
# ---------------------------------------------------------------------------
_S20_AVAILABLE = False
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from s15_kernel.attention import S20SpectralAttention  # type: ignore
    _S20_AVAILABLE = True
except ImportError:
    S20SpectralAttention = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Monkey-patching S20 attention into a HuggingFace model
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# GPU memory tracking
# ---------------------------------------------------------------------------
def _get_gpu_memory_mb() -> dict[str, float]:
    """Return current GPU memory stats in MB."""
    import torch
    if not torch.cuda.is_available():
        return {}
    return {
        "allocated_mb": round(torch.cuda.memory_allocated() / (1024**2), 2),
        "reserved_mb": round(torch.cuda.memory_reserved() / (1024**2), 2),
        "max_allocated_mb": round(torch.cuda.max_memory_allocated() / (1024**2), 2),
    }


# ---------------------------------------------------------------------------
# Hardware metadata
# ---------------------------------------------------------------------------
def _gather_metadata(model_name: str, mode: str) -> dict[str, Any]:
    import torch
    meta: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "torch_version": torch.__version__,
        "model": model_name,
        "mode": mode,
        "platform": platform.platform(),
    }
    if torch.cuda.is_available():
        meta["cuda_version"] = torch.version.cuda
        meta["gpu_name"] = torch.cuda.get_device_name(0)
        props = torch.cuda.get_device_properties(0)
        meta["gpu_memory_gb"] = round(props.total_mem / (1024**3), 2)
    return meta


# ---------------------------------------------------------------------------
# Run MMLU evaluation
# ---------------------------------------------------------------------------
def run_mmlu(
    model_name: str,
    mode: str = "baseline",
    window_size: int = 16,
    num_fewshot: int = 5,
    limit: int | None = None,
    device: str | None = None,
) -> dict[str, Any]:
    """
    Run MMLU evaluation and return results dict.

    Args:
        model_name: HuggingFace model identifier.
        mode: "baseline" or "s20".
        window_size: S20 window size (only used when mode="s20").
        num_fewshot: Number of few-shot examples (standard = 5).
        limit: Limit number of examples per task (for debugging).
        device: Device string override.
    """
    import torch
    import lm_eval
    from lm_eval.models.huggingface import HFLM

    metadata = _gather_metadata(model_name, mode)
    metadata["num_fewshot"] = num_fewshot
    metadata["window_size"] = window_size if mode == "s20" else None
    metadata["limit"] = limit

    # Reset peak memory tracking
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()

    print(f"\n{'='*60}")
    print(f"MMLU Evaluation — Mode: {mode.upper()}")
    print(f"Model: {model_name}")
    print(f"Few-shot: {num_fewshot}")
    if limit:
        print(f"Limit: {limit} examples/task")
    print(f"{'='*60}\n")

    # --- Load model ---
    print("[1/3] Loading model …")
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    lm = HFLM(
        pretrained=model_name,
        device=device,
        batch_size="auto",
        trust_remote_code=True,
    )

    memory_after_load = _get_gpu_memory_mb()
    metadata["memory_after_load"] = memory_after_load
    print(f"      GPU memory after load: {memory_after_load}")

    # --- Optionally patch with S20 ---
    if mode == "s20":
        print("[2/3] Patching model with S20 attention …")
        from s15_kernel.patching import patch_model_with_s20
        patch_model_with_s20(lm.model, window_size=window_size)
        print(f"      Globally patched SDPA")
        metadata["layers_patched"] = "global"
    else:
        print("[2/3] Running unmodified baseline …")

    # --- Run evaluation ---
    print("[3/3] Running MMLU evaluation …")
    task_manager = lm_eval.tasks.TaskManager()
    eval_results = lm_eval.simple_evaluate(
        model=lm,
        tasks=["mmlu"],
        num_fewshot=num_fewshot,
        limit=limit,
        task_manager=task_manager,
    )

    memory_after_eval = _get_gpu_memory_mb()
    metadata["memory_after_eval"] = memory_after_eval

    # --- Extract results ---
    raw_results = eval_results.get("results", {})
    per_subject: dict[str, float] = {}
    overall_acc = None

    for task_name, task_data in raw_results.items():
        if isinstance(task_data, dict):
            acc = task_data.get("acc,none") or task_data.get("acc_norm,none")
            if acc is not None:
                per_subject[task_name] = round(float(acc), 4)
            if task_name == "mmlu":
                overall_acc = acc

    output = {
        "metadata": metadata,
        "overall_accuracy": round(float(overall_acc), 4) if overall_acc else None,
        "per_subject": per_subject,
        "raw_results": {k: v for k, v in raw_results.items() if isinstance(v, (dict, float, int))},
    }

    print(f"\n{'='*60}")
    print(f"Overall MMLU accuracy ({mode}): {output['overall_accuracy']}")
    print(f"GPU peak memory: {memory_after_eval.get('max_allocated_mb', 'N/A')} MB")
    print(f"{'='*60}\n")

    # Cleanup
    del lm
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    if mode == "s20":
        from s15_kernel.patching import unpatch_model
        unpatch_model()

    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    if not _check_torch():
        sys.exit(1)
    if not _check_lm_eval():
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="S20 Spectral Attention — MMLU Evaluation Benchmark"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="google/gemma-2-2b-it",
        help="HuggingFace model name or path",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--baseline",
        action="store_true",
        help="Run unmodified model",
    )
    group.add_argument(
        "--s20",
        action="store_true",
        help="Run with S20 attention patched in",
    )
    parser.add_argument(
        "--window-size",
        type=int,
        default=16,
        help="S20 window size (default: 16)",
    )
    parser.add_argument(
        "--num-fewshot",
        type=int,
        default=5,
        help="Number of few-shot examples (default: 5)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit examples per MMLU task (for fast debugging)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to write JSON results",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Device override (cuda / cpu)",
    )
    args = parser.parse_args()

    mode = "s20" if args.s20 else "baseline"

    if mode == "s20" and not _S20_AVAILABLE:
        print(
            "[WARN] S20SpectralAttention not importable — "
            "S20 mode will fail. Build the kernel first."
        )

    try:
        data = run_mmlu(
            model_name=args.model,
            mode=mode,
            window_size=args.window_size,
            num_fewshot=args.num_fewshot,
            limit=args.limit,
            device=args.device,
        )
    except Exception as exc:
        print(f"[ERROR] MMLU evaluation failed: {exc}")
        traceback.print_exc()
        sys.exit(1)

    # --- Save JSON ---
    if args.output:
        out_path = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        out_path = (
            Path(__file__).resolve().parent.parent.parent
            / "output"
            / "s20_benchmarks"
            / f"mmlu_{mode}_{ts}.json"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump(data, fh, indent=2, default=str)
    print(f"Results saved to {out_path}")


if __name__ == "__main__":
    main()
