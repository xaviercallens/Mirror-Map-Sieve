#!/usr/bin/env python3
"""
gpu_benchmark_s20.py — S20 Attention Kernel GPU Benchmark with Global SDPA Patching

Benchmarks the S20 decay attention mechanism on GPU (L4/T4/A100) using
forward-hook based global SDPA patching. Tests against Phi-3-mini-4k-instruct
and measures latency, throughput, and nvidia-smi energy consumption.

Forward Hook Option A: Patches torch.nn.functional.scaled_dot_product_attention
at the module level by hooking every attention module's forward method to inject
the S20 decay bias into the attention score computation.

Usage:
    python gpu_benchmark_s20.py [--model microsoft/Phi-3-mini-4k-instruct]
                                [--seq_lens 64 128 256 512 1024]
                                [--output gpu_benchmark_results.json]
"""
import argparse
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from math import comb
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

# ─── S20 Decay Core ─────────────────────────────────────────────────────────

def s20(n: int) -> int:
    """S(n) = sum_{k=0}^n C(n,k)^4 * C(n+k,k)."""
    return sum(comb(n, k) ** 4 * comb(n + k, k) for k in range(n + 1))

_S20_TABLE = [s20(d) for d in range(18)]


def build_s20_decay_matrix(seq_len: int, device: str = "cuda",
                           dtype: torch.dtype = torch.float16) -> torch.Tensor:
    """
    Vectorized S20 Toeplitz decay matrix.
    Returns: (seq_len, seq_len) tensor of decay weights in [0, 1].
    """
    base = float(_S20_TABLE[0])
    weights = [base / float(x) if x > 0 else 0.0 for x in _S20_TABLE]
    weights.append(0.0)  # sentinel for dist > 17
    dv = torch.tensor(weights, dtype=dtype, device=device)

    idx = torch.arange(seq_len, device=device)
    dist = (idx.unsqueeze(0) - idx.unsqueeze(1)).abs()
    dist = dist.clamp(max=len(_S20_TABLE))
    return dv[dist]


def build_s20_log_bias(seq_len: int, device: str = "cuda",
                       dtype: torch.dtype = torch.float16) -> torch.Tensor:
    """
    Log-space S20 bias for additive injection into attention scores.
    Returns: (1, 1, seq_len, seq_len) broadcast-ready tensor.
    """
    decay = build_s20_decay_matrix(seq_len, device, torch.float32)
    log_bias = torch.log(decay.clamp(min=1e-30))
    # Apply causal mask
    causal = torch.tril(torch.ones(seq_len, seq_len, device=device))
    log_bias = log_bias * causal + (1 - causal) * (-1e9)
    return log_bias.unsqueeze(0).unsqueeze(0).to(dtype)


# ─── Global SDPA Patching (Forward Hook Option A) ───────────────────────────

class S20SDPAPatcher:
    """
    Globally patches all attention modules in a model to inject S20 decay
    bias into their scaled_dot_product_attention calls via forward hooks.

    Strategy: We monkey-patch torch.nn.functional.scaled_dot_product_attention
    to intercept the (query, key, value, attn_mask) call and add our log-space
    S20 bias to the attn_mask parameter.
    """

    def __init__(self, max_seq_len: int = 2048, device: str = "cuda",
                 dtype: torch.dtype = torch.float16):
        self.max_seq_len = max_seq_len
        self.device = device
        self.dtype = dtype
        self._original_sdpa = None
        self._bias_cache: dict[int, torch.Tensor] = {}
        self._active = False

    def _get_bias(self, seq_len: int) -> torch.Tensor:
        """Cached log-bias retrieval."""
        if seq_len not in self._bias_cache:
            self._bias_cache[seq_len] = build_s20_log_bias(
                seq_len, self.device, self.dtype
            )
        return self._bias_cache[seq_len]

    def _patched_sdpa(self, query, key, value, attn_mask=None,
                      dropout_p=0.0, is_causal=False, scale=None,
                      enable_gqa=False):
        """
        Drop-in replacement for F.scaled_dot_product_attention that injects
        the S20 log-bias into the attention mask.
        """
        seq_len = query.shape[-2]
        kv_len = key.shape[-2]

        if seq_len <= self.max_seq_len and kv_len <= self.max_seq_len:
            s20_bias = self._get_bias(max(seq_len, kv_len))
            # Slice to match actual dimensions
            bias_slice = s20_bias[:, :, :seq_len, :kv_len]

            if attn_mask is not None:
                if attn_mask.dtype == torch.bool:
                    # Convert bool mask to float and add bias
                    float_mask = torch.where(
                        attn_mask, torch.tensor(0.0, device=query.device),
                        torch.tensor(-1e9, device=query.device)
                    ).to(self.dtype)
                    attn_mask = float_mask + bias_slice
                else:
                    attn_mask = attn_mask + bias_slice
            else:
                attn_mask = bias_slice

            # With explicit attn_mask, disable is_causal (already in bias)
            is_causal = False

        return self._original_sdpa(
            query, key, value, attn_mask=attn_mask,
            dropout_p=dropout_p, is_causal=is_causal,
            scale=scale, enable_gqa=enable_gqa
        )

    def activate(self):
        """Monkey-patch F.scaled_dot_product_attention globally."""
        if self._active:
            return
        self._original_sdpa = F.scaled_dot_product_attention
        F.scaled_dot_product_attention = self._patched_sdpa
        self._active = True

    def deactivate(self):
        """Restore original SDPA."""
        if not self._active:
            return
        F.scaled_dot_product_attention = self._original_sdpa
        self._original_sdpa = None
        self._active = False
        self._bias_cache.clear()

    @contextmanager
    def patched(self):
        """Context manager for scoped patching."""
        self.activate()
        try:
            yield
        finally:
            self.deactivate()


# ─── nvidia-smi Energy Monitor ──────────────────────────────────────────────

def get_gpu_info() -> dict:
    """Query nvidia-smi for GPU name, memory, power draw."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,power.draw,power.limit,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10
        )
        parts = [p.strip() for p in result.stdout.strip().split(",")]
        return {
            "gpu_name": parts[0],
            "memory_total_MiB": int(float(parts[1])),
            "power_draw_W": float(parts[2]),
            "power_limit_W": float(parts[3]),
            "temperature_C": int(float(parts[4])),
        }
    except Exception as e:
        return {"error": str(e)}


def measure_energy(func, *args, sample_interval_ms=50, **kwargs):
    """
    Run func(*args) while sampling nvidia-smi power draw.
    Returns: (result, energy_J, avg_power_W, peak_power_W, n_samples).
    """
    power_samples = []

    def _sample_power():
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            return float(r.stdout.strip())
        except Exception:
            return None

    # Pre-sample
    p0 = _sample_power()
    if p0 is not None:
        power_samples.append(p0)

    t0 = time.perf_counter()
    result = func(*args, **kwargs)
    t1 = time.perf_counter()

    # Post-sample
    p1 = _sample_power()
    if p1 is not None:
        power_samples.append(p1)

    elapsed_s = t1 - t0
    avg_power = sum(power_samples) / len(power_samples) if power_samples else 0.0
    peak_power = max(power_samples) if power_samples else 0.0
    energy_J = avg_power * elapsed_s

    return result, energy_J, avg_power, peak_power, len(power_samples)


# ─── Core Kernel Benchmark ──────────────────────────────────────────────────

def benchmark_kernel(seq_lens: list[int], batch: int = 1, heads: int = 8,
                     head_dim: int = 64, device: str = "cuda",
                     n_warmup: int = 10, n_runs: int = 50) -> list[dict]:
    """Benchmark raw S20 decay matrix construction + SDPA vs vanilla SDPA."""
    results = []
    dtype = torch.float16

    for L in seq_lens:
        print(f"\n  seq_len={L}:")

        # Pre-build decay
        s20_bias = build_s20_log_bias(L, device, dtype)

        q = torch.randn(batch, heads, L, head_dim, device=device, dtype=dtype)
        k = torch.randn(batch, heads, L, head_dim, device=device, dtype=dtype)
        v = torch.randn(batch, heads, L, head_dim, device=device, dtype=dtype)

        # ── Baseline: vanilla SDPA ──
        for _ in range(n_warmup):
            _ = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        torch.cuda.synchronize()

        t0 = time.perf_counter()
        for _ in range(n_runs):
            out_base = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        torch.cuda.synchronize()
        t_base = (time.perf_counter() - t0) / n_runs * 1000

        # ── S20-biased SDPA ──
        for _ in range(n_warmup):
            _ = F.scaled_dot_product_attention(q, k, v, attn_mask=s20_bias)
        torch.cuda.synchronize()

        t0 = time.perf_counter()
        for _ in range(n_runs):
            out_s20 = F.scaled_dot_product_attention(q, k, v, attn_mask=s20_bias)
        torch.cuda.synchronize()
        t_s20 = (time.perf_counter() - t0) / n_runs * 1000

        overhead = t_s20 / t_base
        # Correctness: check no NaN/Inf
        ok = not (torch.isnan(out_s20).any() or torch.isinf(out_s20).any())

        print(f"    SDPA baseline:  {t_base:.3f} ms")
        print(f"    SDPA + S20:     {t_s20:.3f} ms  (overhead: {overhead:.2f}×)")
        print(f"    Correct: {'✅' if ok else '❌'}")

        results.append({
            "seq_len": L,
            "sdpa_baseline_ms": round(t_base, 3),
            "sdpa_s20_ms": round(t_s20, 3),
            "overhead": round(overhead, 3),
            "correct": ok,
        })

    return results


# ─── Full Model Benchmark with Global SDPA Patch ────────────────────────────

def benchmark_model_sdpa_patch(model_id: str, device: str = "cuda",
                               seq_lens: list[int] = [64, 128, 256, 512],
                               n_warmup: int = 5, n_runs: int = 20) -> dict:
    """
    Benchmark a real model with and without S20 global SDPA patching.
    Uses Forward Hook Option A: monkey-patching F.scaled_dot_product_attention.
    """
    from transformers import AutoTokenizer, AutoModelForCausalLM

    print(f"\n{'='*60}")
    print(f"  Model: {model_id}")
    print(f"{'='*60}")

    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        dtype=torch.float16,
        trust_remote_code=True,
        attn_implementation="sdpa",
    ).to(device).eval()

    n_params = sum(p.numel() for p in model.parameters())
    print(f"  Params: {n_params/1e6:.0f}M | Device: {device}")

    patcher = S20SDPAPatcher(
        max_seq_len=max(seq_lens),
        device=device,
        dtype=torch.float16,
    )

    results_per_seq = []

    for L in seq_lens:
        print(f"\n  seq_len={L}:")

        # Generate dummy input of exact length L
        input_ids = torch.randint(1, tokenizer.vocab_size, (1, L), device=device)

        # ── Baseline (no S20) ──
        for _ in range(n_warmup):
            with torch.no_grad():
                _ = model(input_ids)
        torch.cuda.synchronize()

        t0 = time.perf_counter()
        for _ in range(n_runs):
            with torch.no_grad():
                out_base = model(input_ids)
        torch.cuda.synchronize()
        t_base = (time.perf_counter() - t0) / n_runs * 1000

        # ── S20 patched (global SDPA hook) ──
        with patcher.patched():
            for _ in range(n_warmup):
                with torch.no_grad():
                    _ = model(input_ids)
            torch.cuda.synchronize()

            # Energy measurement on the timed runs
            def _run_patched():
                for _ in range(n_runs):
                    with torch.no_grad():
                        out = model(input_ids)
                torch.cuda.synchronize()
                return out

            _, energy_J, avg_power, peak_power, n_samples = measure_energy(
                _run_patched
            )
            t_s20_total = energy_J / avg_power * 1000 if avg_power > 0 else 0
            t_s20 = t_s20_total / n_runs if n_runs > 0 else 0

            # Also time directly
            torch.cuda.synchronize()
            t0 = time.perf_counter()
            for _ in range(n_runs):
                with torch.no_grad():
                    out_s20 = model(input_ids)
            torch.cuda.synchronize()
            t_s20 = (time.perf_counter() - t0) / n_runs * 1000

        overhead = t_s20 / t_base if t_base > 0 else 0
        throughput_base = L / (t_base / 1000)
        throughput_s20 = L / (t_s20 / 1000)

        # Correctness: logits should be finite
        ok = not (torch.isnan(out_s20.logits).any() or
                  torch.isinf(out_s20.logits).any())

        print(f"    Baseline:  {t_base:.2f} ms  ({throughput_base:,.0f} tok/s)")
        print(f"    S20-SDPA:  {t_s20:.2f} ms  ({throughput_s20:,.0f} tok/s)  "
              f"overhead={overhead:.2f}×")
        print(f"    Energy:    {energy_J:.2f} J  (avg {avg_power:.1f} W, "
              f"peak {peak_power:.1f} W)")
        print(f"    Correct:   {'✅' if ok else '❌'}")

        results_per_seq.append({
            "seq_len": L,
            "baseline_ms": round(t_base, 3),
            "s20_sdpa_ms": round(t_s20, 3),
            "overhead": round(overhead, 3),
            "throughput_base_tok_s": round(throughput_base),
            "throughput_s20_tok_s": round(throughput_s20),
            "energy_J": round(energy_J, 3),
            "avg_power_W": round(avg_power, 1),
            "peak_power_W": round(peak_power, 1),
            "correct": ok,
        })

    del model
    torch.cuda.empty_cache()

    return {
        "model_id": model_id,
        "n_params_M": round(n_params / 1e6, 1),
        "device": device,
        "results": results_per_seq,
    }


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="S20 GPU Benchmark")
    parser.add_argument("--model", default="microsoft/Phi-3-mini-4k-instruct",
                        help="HuggingFace model ID")
    parser.add_argument("--seq_lens", nargs="+", type=int,
                        default=[64, 128, 256, 512, 1024],
                        help="Sequence lengths to benchmark")
    parser.add_argument("--output", default="gpu_benchmark_results.json")
    parser.add_argument("--kernel_only", action="store_true",
                        help="Only run raw kernel benchmark (no model)")
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device != "cuda":
        print("WARNING: No CUDA device found. Results will not be representative.")
        print("         Run this on a GCP L4/T4/A100 instance.")

    gpu_info = get_gpu_info()
    print("=" * 70)
    print("  S20 Attention Kernel — GPU Benchmark Suite")
    print(f"  GPU:    {gpu_info.get('gpu_name', 'N/A')}")
    print(f"  VRAM:   {gpu_info.get('memory_total_MiB', 'N/A')} MiB")
    print(f"  Power:  {gpu_info.get('power_draw_W', 'N/A')} W / "
          f"{gpu_info.get('power_limit_W', 'N/A')} W limit")
    print(f"  Temp:   {gpu_info.get('temperature_C', 'N/A')}°C")
    print(f"  PyTorch: {torch.__version__} | CUDA: {torch.version.cuda}")
    print("=" * 70)

    all_results = {"gpu_info": gpu_info, "pytorch_version": torch.__version__}

    # ── Phase 1: Raw kernel benchmark ──
    print("\n[Phase 1] Raw Kernel Benchmark (SDPA ± S20 bias)")
    kernel_results = benchmark_kernel(args.seq_lens, device=device)
    all_results["kernel_benchmark"] = kernel_results

    if not args.kernel_only:
        # ── Phase 2: Full model with global SDPA patching ──
        print(f"\n[Phase 2] Model Benchmark: {args.model}")
        model_results = benchmark_model_sdpa_patch(
            args.model, device=device, seq_lens=args.seq_lens
        )
        all_results["model_benchmark"] = model_results

    # ── Save results ──
    with open(args.output, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n✅ Results saved → {args.output}")

    # ── Print markdown table ──
    print("\n## Raw Kernel Results (GPU)\n")
    print("| Seq Len | SDPA Baseline | SDPA + S20 | Overhead | Correct |")
    print("|---------|---------------|------------|----------|---------|")
    for r in kernel_results:
        print(f"| {r['seq_len']:>5} | {r['sdpa_baseline_ms']:.3f} ms | "
              f"{r['sdpa_s20_ms']:.3f} ms | {r['overhead']:.2f}× | "
              f"{'✅' if r['correct'] else '❌'} |")

    if not args.kernel_only and "model_benchmark" in all_results:
        mr = all_results["model_benchmark"]
        print(f"\n## Model Results: {mr['model_id']} ({mr['n_params_M']}M)\n")
        print("| Seq Len | Baseline | S20-SDPA | Overhead | Base tok/s | S20 tok/s | Energy (J) |")
        print("|---------|----------|----------|----------|------------|-----------|------------|")
        for r in mr["results"]:
            print(f"| {r['seq_len']:>5} | {r['baseline_ms']:.2f} ms | "
                  f"{r['s20_sdpa_ms']:.2f} ms | {r['overhead']:.2f}× | "
                  f"{r['throughput_base_tok_s']:>10,} | {r['throughput_s20_tok_s']:>9,} | "
                  f"{r['energy_J']:.2f} |")


if __name__ == "__main__":
    main()
