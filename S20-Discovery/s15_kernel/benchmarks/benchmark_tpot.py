#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# S20 Spectral Attention Kernel — TPOT + Energy Benchmark
"""
Time-Per-Output-Token (TPOT) measurement with GPU energy tracking.

Generates 256 tokens from a fixed benchmark prompt, measuring per-token
latency with torch.cuda.synchronize() + time.perf_counter_ns().

Energy tracking:
    Background thread polls nvidia-smi at ~100ms intervals for power draw,
    GPU utilisation, and memory usage.  If nvidia-smi is unavailable the
    energy metrics are skipped with a warning.

Reports:
    Median TPOT (ms), p50/p95/p99 TPOT, tokens/sec, avg GPU power (W),
    total energy (J), J/token.

Runs both baseline and S20-patched, reports delta.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import statistics
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------
try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
except ImportError as _imp_err:
    print(
        "[ERROR] PyTorch and transformers are required.\n"
        "  pip install torch transformers"
    )
    raise SystemExit(1) from _imp_err

# ---------------------------------------------------------------------------
# S20 kernel import
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
BENCHMARK_PROMPT = (
    "The Riemann Hypothesis, first proposed in 1859, states that all "
    "non-trivial zeros of the Riemann zeta function have real part equal "
    "to one-half. This conjecture has profound implications for the "
    "distribution of prime numbers. In this essay we explore the key "
    "developments in analytic number theory that followed Riemann's "
    "original insight, beginning with"
)

DEFAULT_MAX_NEW_TOKENS = 256
ENERGY_POLL_INTERVAL_S = 0.1  # 100ms


# ---------------------------------------------------------------------------
# nvidia-smi power sampler (background thread)
# ---------------------------------------------------------------------------
class NvidiaSmiSampler:
    """Polls nvidia-smi for power, utilisation, and memory in a bg thread."""

    def __init__(self, interval_s: float = ENERGY_POLL_INTERVAL_S):
        self.interval = interval_s
        self.samples: list[dict[str, float]] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.available = self._probe()

    def _probe(self) -> bool:
        """Check whether nvidia-smi is reachable."""
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=power.draw",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            return r.returncode == 0
        except Exception:
            return False

    def _poll(self) -> None:
        while not self._stop.is_set():
            t0 = time.perf_counter()
            try:
                r = subprocess.run(
                    [
                        "nvidia-smi",
                        "--query-gpu=power.draw,utilization.gpu,memory.used",
                        "--format=csv,noheader,nounits",
                    ],
                    capture_output=True, text=True, timeout=2,
                )
                if r.returncode == 0:
                    parts = r.stdout.strip().split(",")
                    if len(parts) >= 3:
                        self.samples.append({
                            "time_s": time.perf_counter(),
                            "power_w": float(parts[0].strip()),
                            "gpu_util_pct": float(parts[1].strip()),
                            "mem_used_mb": float(parts[2].strip()),
                        })
            except Exception:
                pass
            elapsed = time.perf_counter() - t0
            sleep_time = max(0, self.interval - elapsed)
            self._stop.wait(sleep_time)

    def start(self) -> None:
        if not self.available:
            return
        self.samples.clear()
        self._stop.clear()
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None:
            return
        self._stop.set()
        self._thread.join(timeout=5)
        self._thread = None

    def summarise(self) -> dict[str, Any]:
        """Compute energy metrics from collected samples."""
        if not self.samples or len(self.samples) < 2:
            return {"warning": "Insufficient nvidia-smi samples"}

        powers = [s["power_w"] for s in self.samples]
        utils = [s["gpu_util_pct"] for s in self.samples]
        mems = [s["mem_used_mb"] for s in self.samples]

        # Trapezoidal integration for energy
        total_energy_j = 0.0
        for i in range(1, len(self.samples)):
            dt = self.samples[i]["time_s"] - self.samples[i - 1]["time_s"]
            avg_power = (self.samples[i]["power_w"] + self.samples[i - 1]["power_w"]) / 2
            total_energy_j += avg_power * dt

        wall_time_s = self.samples[-1]["time_s"] - self.samples[0]["time_s"]

        return {
            "avg_power_w": round(statistics.mean(powers), 2),
            "max_power_w": round(max(powers), 2),
            "avg_gpu_util_pct": round(statistics.mean(utils), 1),
            "avg_mem_used_mb": round(statistics.mean(mems), 1),
            "peak_mem_used_mb": round(max(mems), 1),
            "total_energy_j": round(total_energy_j, 3),
            "wall_time_s": round(wall_time_s, 3),
            "n_samples": len(self.samples),
        }


# ---------------------------------------------------------------------------
# S20 patching (re-uses strategy from benchmark_mmlu)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Hardware metadata
# ---------------------------------------------------------------------------
def _gather_metadata(model_name: str, mode: str) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "torch_version": torch.__version__,
        "model": model_name,
        "mode": mode,
        "platform": platform.platform(),
        "max_new_tokens": DEFAULT_MAX_NEW_TOKENS,
    }
    if torch.cuda.is_available():
        meta["cuda_version"] = torch.version.cuda
        meta["gpu_name"] = torch.cuda.get_device_name(0)
        props = torch.cuda.get_device_properties(0)
        meta["gpu_memory_gb"] = round(props.total_mem / (1024**3), 2)
    return meta


# ---------------------------------------------------------------------------
# Per-token timing via generate hook
# ---------------------------------------------------------------------------
def _generate_with_tpot(
    model: torch.nn.Module,
    tokenizer: "AutoTokenizer",
    prompt: str,
    max_new_tokens: int,
    device: torch.device,
) -> tuple[list[float], str]:
    """
    Generate tokens one at a time, measuring per-token latency.

    Returns (list_of_tpot_ns, generated_text).
    """
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    input_ids = inputs["input_ids"]

    tpot_ns: list[float] = []
    generated_ids = input_ids.clone()

    with torch.no_grad():
        # Prefill (first token)
        if device.type == "cuda":
            torch.cuda.synchronize()

        for _ in range(max_new_tokens):
            t0 = time.perf_counter_ns()

            outputs = model(input_ids=generated_ids)
            next_token_logits = outputs.logits[:, -1, :]
            next_token_id = torch.argmax(next_token_logits, dim=-1, keepdim=True)

            if device.type == "cuda":
                torch.cuda.synchronize()
            t1 = time.perf_counter_ns()

            tpot_ns.append(t1 - t0)
            generated_ids = torch.cat([generated_ids, next_token_id], dim=-1)

            # Stop on EOS
            if next_token_id.item() == tokenizer.eos_token_id:
                break

    text = tokenizer.decode(generated_ids[0, input_ids.shape[1]:], skip_special_tokens=True)
    return tpot_ns, text


def _summarise_tpot(tpot_ns: list[float]) -> dict[str, Any]:
    """Compute TPOT summary statistics."""
    tpot_ms = [t / 1e6 for t in tpot_ns]
    s = sorted(tpot_ms)
    n = len(s)
    if n == 0:
        return {"error": "No tokens generated"}

    total_time_s = sum(tpot_ns) / 1e9
    tokens_per_sec = n / total_time_s if total_time_s > 0 else 0

    return {
        "n_tokens": n,
        "median_ms": round(statistics.median(s), 4),
        "mean_ms": round(statistics.mean(s), 4),
        "p50_ms": round(s[int(n * 0.50)], 4),
        "p95_ms": round(s[min(int(n * 0.95), n - 1)], 4),
        "p99_ms": round(s[min(int(n * 0.99), n - 1)], 4),
        "min_ms": round(s[0], 4),
        "max_ms": round(s[-1], 4),
        "std_ms": round(statistics.stdev(s), 4) if n > 1 else 0.0,
        "total_time_s": round(total_time_s, 4),
        "tokens_per_sec": round(tokens_per_sec, 2),
    }


# ---------------------------------------------------------------------------
# Single run
# ---------------------------------------------------------------------------
def run_tpot(
    model_name: str,
    mode: str = "baseline",
    window_size: int = 16,
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
    device_str: str | None = None,
    prompt: str = BENCHMARK_PROMPT,
) -> dict[str, Any]:
    """Run TPOT + energy measurement for one configuration."""
    if device_str is None:
        device_str = "cuda" if torch.cuda.is_available() else "cpu"
    device = torch.device(device_str)

    metadata = _gather_metadata(model_name, mode)
    metadata["max_new_tokens"] = max_new_tokens
    metadata["prompt_length_chars"] = len(prompt)

    print(f"\n{'='*60}")
    print(f"TPOT Benchmark — Mode: {mode.upper()}")
    print(f"Model: {model_name}  |  Device: {device}")
    print(f"Max new tokens: {max_new_tokens}")
    print(f"{'='*60}\n")

    # --- Load model ---
    print("[1/4] Loading model + tokenizer …")
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16 if device.type == "cuda" else torch.float32,
        device_map=device_str if device.type == "cuda" else None,
        trust_remote_code=True,
    )
    model.eval()

    if device.type != "cuda" and device_str != "cpu":
        model = model.to(device)

    # --- Optionally patch ---
    if mode == "s20":
        print("[2/4] Patching with S20 attention …")
        from s15_kernel.patching import patch_model_with_s20
        patch_model_with_s20(model, window_size=window_size)
        print(f"      Globally patched SDPA")
        metadata["layers_patched"] = "global"
    else:
        print("[2/4] Using unmodified baseline …")

    # --- Start energy sampler ---
    sampler = NvidiaSmiSampler()
    if sampler.available:
        print("[3/4] Starting nvidia-smi power sampler …")
        sampler.start()
    else:
        print("[3/4] nvidia-smi not available — skipping energy measurement")

    # --- Generate ---
    print(f"[4/4] Generating {max_new_tokens} tokens …")
    tpot_ns, generated_text = _generate_with_tpot(
        model, tokenizer, prompt, max_new_tokens, device,
    )

    # --- Stop sampler ---
    sampler.stop()

    # --- Summarise ---
    tpot_summary = _summarise_tpot(tpot_ns)
    energy_summary = sampler.summarise() if sampler.available else {"warning": "nvidia-smi not available"}

    # Compute J/token if energy data available
    if "total_energy_j" in energy_summary and tpot_summary.get("n_tokens", 0) > 0:
        energy_summary["j_per_token"] = round(
            energy_summary["total_energy_j"] / tpot_summary["n_tokens"], 6
        )

    result = {
        "metadata": metadata,
        "tpot": tpot_summary,
        "energy": energy_summary,
        "generated_text_preview": generated_text[:200],
    }

    # --- Print summary ---
    print(f"\n{'='*60}")
    print(f"Results ({mode}):")
    print(f"  Tokens generated: {tpot_summary.get('n_tokens', 0)}")
    print(f"  Median TPOT:      {tpot_summary.get('median_ms', 'N/A')} ms")
    print(f"  p95 TPOT:         {tpot_summary.get('p95_ms', 'N/A')} ms")
    print(f"  Tokens/sec:       {tpot_summary.get('tokens_per_sec', 'N/A')}")
    if "avg_power_w" in energy_summary:
        print(f"  Avg power:        {energy_summary['avg_power_w']} W")
        print(f"  Total energy:     {energy_summary['total_energy_j']} J")
        print(f"  J/token:          {energy_summary.get('j_per_token', 'N/A')}")
    print(f"{'='*60}\n")

    # Cleanup
    del model, tokenizer
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    if mode == "s20":
        from s15_kernel.patching import unpatch_model
        unpatch_model()

    return result


# ---------------------------------------------------------------------------
# Comparative run (baseline vs S20)
# ---------------------------------------------------------------------------
def run_comparative(
    model_name: str,
    window_size: int = 16,
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
    device_str: str | None = None,
) -> dict[str, Any]:
    """Run both baseline and S20, compute deltas."""
    baseline = run_tpot(
        model_name, mode="baseline",
        max_new_tokens=max_new_tokens, device_str=device_str,
    )
    s20 = run_tpot(
        model_name, mode="s20", window_size=window_size,
        max_new_tokens=max_new_tokens, device_str=device_str,
    )

    delta: dict[str, Any] = {}
    b_tpot = baseline.get("tpot", {})
    s_tpot = s20.get("tpot", {})

    if b_tpot.get("median_ms") and s_tpot.get("median_ms"):
        delta["median_tpot_delta_ms"] = round(
            s_tpot["median_ms"] - b_tpot["median_ms"], 4
        )
        delta["median_tpot_delta_pct"] = round(
            100 * (s_tpot["median_ms"] - b_tpot["median_ms"]) / b_tpot["median_ms"], 2
        )
    if b_tpot.get("tokens_per_sec") and s_tpot.get("tokens_per_sec"):
        delta["tokens_per_sec_delta"] = round(
            s_tpot["tokens_per_sec"] - b_tpot["tokens_per_sec"], 2
        )

    b_energy = baseline.get("energy", {})
    s_energy = s20.get("energy", {})
    if b_energy.get("j_per_token") and s_energy.get("j_per_token"):
        delta["j_per_token_delta"] = round(
            s_energy["j_per_token"] - b_energy["j_per_token"], 6
        )

    return {
        "baseline": baseline,
        "s20": s20,
        "delta": delta,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="S20 Spectral Attention — TPOT + Energy Benchmark"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="google/gemma-2-2b-it",
        help="HuggingFace model name or path",
    )
    parser.add_argument(
        "--mode",
        choices=["baseline", "s20", "compare"],
        default="compare",
        help="Run mode: baseline, s20, or compare (both)",
    )
    parser.add_argument(
        "--window-size",
        type=int,
        default=16,
        help="S20 window size (default: 16)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_NEW_TOKENS,
        help=f"Number of tokens to generate (default: {DEFAULT_MAX_NEW_TOKENS})",
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

    if args.mode == "s20" and not _S20_AVAILABLE:
        print(
            "[WARN] S20SpectralAttention not importable — "
            "S20 mode will fail. Build the kernel first."
        )

    try:
        if args.mode == "compare":
            data = run_comparative(
                model_name=args.model,
                window_size=args.window_size,
                max_new_tokens=args.max_tokens,
                device_str=args.device,
            )
        else:
            data = run_tpot(
                model_name=args.model,
                mode=args.mode,
                window_size=args.window_size,
                max_new_tokens=args.max_tokens,
                device_str=args.device,
            )
    except Exception as exc:
        print(f"[ERROR] TPOT benchmark failed: {exc}")
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
            / f"tpot_{args.mode}_{ts}.json"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump(data, fh, indent=2, default=str)
    print(f"Results saved to {out_path}")


if __name__ == "__main__":
    main()
