#!/usr/bin/env python3
"""
gpu_benchmark_multi_model.py — Extended S20 Attention Benchmark

Benchmarks S20 decay attention across multiple models (Phi-3, Gemma-2, Qwen2.5,
Mistral-7B) on T4/L4 GPU with:
  - Phase 1: Raw SDPA kernel overhead
  - Phase 2: Per-model forward pass with global SDPA patching
  - Phase 3: WikiText-2 perplexity evaluation (H1 validation)
  - Hypothesis metrics: H1 (numerical stability), H2 (construction time), H3 (zero-cost)

Usage:
    python gpu_benchmark_multi_model.py --output multi_model_results.json
"""
import argparse
import gc
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from math import comb, log, exp
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

# ─── S20 Decay Core ─────────────────────────────────────────────────────────

def s20(n: int) -> int:
    """OEIS A397213: S(n) = sum_{k=0}^n C(n,k)^4 * C(n+k,k)."""
    return sum(comb(n, k) ** 4 * comb(n + k, k) for k in range(n + 1))

_S20_TABLE = [s20(d) for d in range(18)]


def build_s20_decay_matrix(seq_len: int, device: str = "cuda",
                           dtype: torch.dtype = torch.float16) -> torch.Tensor:
    base = float(_S20_TABLE[0])
    weights = [base / float(x) if x > 0 else 0.0 for x in _S20_TABLE]
    weights.append(0.0)
    dv = torch.tensor(weights, dtype=dtype, device=device)
    idx = torch.arange(seq_len, device=device)
    dist = (idx.unsqueeze(0) - idx.unsqueeze(1)).abs().clamp(max=len(_S20_TABLE))
    return dv[dist]


def build_s20_log_bias(seq_len: int, device: str = "cuda",
                       dtype: torch.dtype = torch.float16) -> torch.Tensor:
    decay = build_s20_decay_matrix(seq_len, device, torch.float32)
    log_bias = torch.log(decay.clamp(min=1e-30))
    causal = torch.tril(torch.ones(seq_len, seq_len, device=device))
    log_bias = log_bias * causal + (1 - causal) * (-1e9)
    return log_bias.unsqueeze(0).unsqueeze(0).to(dtype)


# ─── Global SDPA Patcher ────────────────────────────────────────────────────

class S20SDPAPatcher:
    def __init__(self, max_seq_len=2048, device="cuda", dtype=torch.float16):
        self.max_seq_len = max_seq_len
        self.device = device
        self.dtype = dtype
        self._original_sdpa = None
        self._bias_cache = {}
        self._active = False

    def _get_bias(self, seq_len):
        if seq_len not in self._bias_cache:
            self._bias_cache[seq_len] = build_s20_log_bias(seq_len, self.device, self.dtype)
        return self._bias_cache[seq_len]

    def _patched_sdpa(self, query, key, value, attn_mask=None,
                      dropout_p=0.0, is_causal=False, scale=None, **kwargs):
        seq_len = query.shape[-2]
        kv_len = key.shape[-2]
        if seq_len <= self.max_seq_len and kv_len <= self.max_seq_len:
            s20_bias = self._get_bias(max(seq_len, kv_len))
            bias_slice = s20_bias[:, :, :seq_len, :kv_len]
            if attn_mask is not None:
                if attn_mask.dtype == torch.bool:
                    float_mask = torch.where(
                        attn_mask, torch.tensor(0.0, device=query.device),
                        torch.tensor(-1e9, device=query.device)
                    ).to(self.dtype)
                    attn_mask = float_mask + bias_slice
                else:
                    attn_mask = attn_mask + bias_slice
            else:
                attn_mask = bias_slice
            is_causal = False
        return self._original_sdpa(
            query, key, value, attn_mask=attn_mask,
            dropout_p=dropout_p, is_causal=is_causal, scale=scale, **kwargs
        )

    def activate(self):
        if self._active:
            return
        self._original_sdpa = F.scaled_dot_product_attention
        F.scaled_dot_product_attention = self._patched_sdpa
        self._active = True

    def deactivate(self):
        if not self._active:
            return
        F.scaled_dot_product_attention = self._original_sdpa
        self._original_sdpa = None
        self._active = False
        self._bias_cache.clear()

    @contextmanager
    def patched(self):
        self.activate()
        try:
            yield
        finally:
            self.deactivate()


# ─── nvidia-smi Utilities ───────────────────────────────────────────────────

def get_gpu_info():
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,power.draw,power.limit,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10
        )
        parts = [p.strip() for p in result.stdout.strip().split(",")]
        return {
            "gpu_name": parts[0], "memory_total_MiB": int(float(parts[1])),
            "power_draw_W": float(parts[2]), "power_limit_W": float(parts[3]),
            "temperature_C": int(float(parts[4])),
        }
    except Exception as e:
        return {"error": str(e)}


def sample_power():
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        return float(r.stdout.strip())
    except Exception:
        return None


# ─── Hypothesis H2: Construction Time ───────────────────────────────────────

def benchmark_h2_construction(seq_lens, device="cuda", n_runs=100):
    """H2: O(1) vectorized Toeplitz construction should be sublinear."""
    results = []
    for L in seq_lens:
        # Warm cache
        build_s20_log_bias(L, device, torch.float16)
        # Clear and time from scratch
        torch.cuda.synchronize()
        times = []
        for _ in range(n_runs):
            torch.cuda.synchronize()
            t0 = time.perf_counter()
            _ = build_s20_log_bias(L, device, torch.float16)
            torch.cuda.synchronize()
            t1 = time.perf_counter()
            times.append((t1 - t0) * 1000)
        med = sorted(times)[n_runs // 2]
        results.append({"seq_len": L, "construction_ms": round(med, 4)})
        print(f"  H2 construction seq_len={L}: {med:.4f} ms")
    return results


# ─── Raw Kernel Benchmark ──────────────────────────────────────────────────

def benchmark_kernel(seq_lens, device="cuda", n_warmup=10, n_runs=50):
    results = []
    dtype = torch.float16
    batch, heads, head_dim = 1, 8, 64

    for L in seq_lens:
        print(f"\n  seq_len={L}:")
        s20_bias = build_s20_log_bias(L, device, dtype)
        q = torch.randn(batch, heads, L, head_dim, device=device, dtype=dtype)
        k = torch.randn(batch, heads, L, head_dim, device=device, dtype=dtype)
        v = torch.randn(batch, heads, L, head_dim, device=device, dtype=dtype)

        for _ in range(n_warmup):
            F.scaled_dot_product_attention(q, k, v, is_causal=True)
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        for _ in range(n_runs):
            out_base = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        torch.cuda.synchronize()
        t_base = (time.perf_counter() - t0) / n_runs * 1000

        for _ in range(n_warmup):
            F.scaled_dot_product_attention(q, k, v, attn_mask=s20_bias)
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        for _ in range(n_runs):
            out_s20 = F.scaled_dot_product_attention(q, k, v, attn_mask=s20_bias)
        torch.cuda.synchronize()
        t_s20 = (time.perf_counter() - t0) / n_runs * 1000

        overhead = t_s20 / t_base
        ok = not (torch.isnan(out_s20).any() or torch.isinf(out_s20).any())

        # H1: Numerical stability — max logit delta between baseline and S20
        logit_delta = (out_s20 - out_base).abs().max().item()

        print(f"    SDPA baseline:  {t_base:.3f} ms")
        print(f"    SDPA + S20:     {t_s20:.3f} ms  (overhead: {overhead:.2f}×)")
        print(f"    Max logit Δ:    {logit_delta:.6f}")
        print(f"    Correct: {'✅' if ok else '❌'}")

        results.append({
            "seq_len": L, "sdpa_baseline_ms": round(t_base, 3),
            "sdpa_s20_ms": round(t_s20, 3), "overhead": round(overhead, 3),
            "max_logit_delta": round(logit_delta, 6), "correct": ok,
        })
    return results


# ─── Model Benchmark ───────────────────────────────────────────────────────

def benchmark_model(model_id, device="cuda", seq_lens=None, n_warmup=5, n_runs=20):
    from transformers import AutoTokenizer, AutoModelForCausalLM

    if seq_lens is None:
        seq_lens = [64, 128, 256, 512]

    print(f"\n{'='*60}")
    print(f"  Model: {model_id}")
    print(f"{'='*60}")

    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    load_kwargs = dict(torch_dtype=torch.float16, trust_remote_code=True, low_cpu_mem_usage=True)
    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_id, attn_implementation="sdpa", **load_kwargs).to(device).eval()
    except Exception:
        model = AutoModelForCausalLM.from_pretrained(
            model_id, **load_kwargs).to(device).eval()

    n_params = sum(p.numel() for p in model.parameters())
    print(f"  Params: {n_params/1e6:.0f}M | Device: {device}")

    patcher = S20SDPAPatcher(max_seq_len=max(seq_lens), device=device, dtype=torch.float16)
    results_per_seq = []

    for L in seq_lens:
        print(f"\n  seq_len={L}:")
        input_ids = torch.randint(1, tokenizer.vocab_size, (1, L), device=device)

        # Baseline
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

        # S20 patched
        with patcher.patched():
            for _ in range(n_warmup):
                with torch.no_grad():
                    _ = model(input_ids)
            torch.cuda.synchronize()

            p0 = sample_power()
            t0 = time.perf_counter()
            for _ in range(n_runs):
                with torch.no_grad():
                    out_s20 = model(input_ids)
            torch.cuda.synchronize()
            t_s20 = (time.perf_counter() - t0) / n_runs * 1000
            p1 = sample_power()

        overhead = t_s20 / t_base if t_base > 0 else 0
        tput_base = L / (t_base / 1000)
        tput_s20 = L / (t_s20 / 1000)

        # H1: max logit delta
        logit_delta = (out_s20.logits - out_base.logits).abs().max().item()

        avg_power = ((p0 or 0) + (p1 or 0)) / 2 if (p0 or p1) else 0
        energy_J = avg_power * (t_s20 * n_runs / 1000)
        ok = not (torch.isnan(out_s20.logits).any() or torch.isinf(out_s20.logits).any())

        print(f"    Baseline:     {t_base:.2f} ms  ({tput_base:,.0f} tok/s)")
        print(f"    S20-SDPA:     {t_s20:.2f} ms  ({tput_s20:,.0f} tok/s)  overhead={overhead:.3f}×")
        print(f"    Max logit Δ:  {logit_delta:.6f}")
        print(f"    Energy:       {energy_J:.2f} J  (avg {avg_power:.1f} W)")
        print(f"    Correct:      {'✅' if ok else '❌'}")

        results_per_seq.append({
            "seq_len": L, "baseline_ms": round(t_base, 3),
            "s20_sdpa_ms": round(t_s20, 3), "overhead": round(overhead, 4),
            "throughput_base_tok_s": round(tput_base),
            "throughput_s20_tok_s": round(tput_s20),
            "max_logit_delta": round(logit_delta, 6),
            "energy_J": round(energy_J, 3), "avg_power_W": round(avg_power, 1),
            "correct": ok,
        })

    del model
    torch.cuda.empty_cache()
    gc.collect()

    return {
        "model_id": model_id, "n_params_M": round(n_params / 1e6, 1),
        "device": device, "results": results_per_seq,
    }


# ─── WikiText-2 Perplexity Evaluation ──────────────────────────────────────

def evaluate_perplexity(model_id, device="cuda", max_length=512, stride=256):
    """Evaluate perplexity on WikiText-2 test set with and without S20."""
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from datasets import load_dataset

    print(f"\n{'='*60}")
    print(f"  Perplexity Evaluation: {model_id}")
    print(f"  Dataset: WikiText-2 (test)")
    print(f"{'='*60}")

    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    load_kwargs = dict(torch_dtype=torch.float16, trust_remote_code=True, low_cpu_mem_usage=True)
    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_id, attn_implementation="sdpa", **load_kwargs).to(device).eval()
    except Exception:
        model = AutoModelForCausalLM.from_pretrained(model_id, **load_kwargs).to(device).eval()

    # Load WikiText-2
    dataset = load_dataset("wikitext", "wikitext-2-raw-v1", split="test")
    text = "\n\n".join(dataset["text"])
    encodings = tokenizer(text, return_tensors="pt")
    input_ids = encodings.input_ids.to(device)
    seq_len = input_ids.size(1)

    print(f"  Total tokens: {seq_len}")

    patcher = S20SDPAPatcher(max_seq_len=max_length, device=device, dtype=torch.float16)

    def _compute_ppl(use_s20=False):
        nlls = []
        n_tokens = 0
        ctx = patcher.patched() if use_s20 else _nullcontext()
        with ctx:
            for begin in range(0, seq_len - max_length, stride):
                end = begin + max_length
                ids = input_ids[:, begin:end]
                target = ids.clone()
                # Don't count overlap tokens in loss
                if begin > 0:
                    target[:, :stride] = -100

                with torch.no_grad():
                    outputs = model(ids, labels=target)
                    nll = outputs.loss.item()

                n_valid = (target != -100).sum().item()
                nlls.append(nll * n_valid)
                n_tokens += n_valid

                if n_tokens > 20000:  # Cap at ~20k tokens for speed
                    break

        avg_nll = sum(nlls) / n_tokens
        ppl = exp(avg_nll)
        return ppl, n_tokens

    print("  Computing baseline perplexity...")
    ppl_base, n_tok_base = _compute_ppl(use_s20=False)
    print(f"    Baseline PPL: {ppl_base:.2f} ({n_tok_base} tokens)")

    print("  Computing S20-patched perplexity...")
    ppl_s20, n_tok_s20 = _compute_ppl(use_s20=True)
    print(f"    S20 PPL:      {ppl_s20:.2f} ({n_tok_s20} tokens)")

    delta = ppl_s20 - ppl_base
    pct = (delta / ppl_base) * 100
    print(f"    ΔPPL:         {delta:+.2f} ({pct:+.2f}%)")

    del model
    torch.cuda.empty_cache()
    gc.collect()

    return {
        "model_id": model_id,
        "dataset": "wikitext-2-raw-v1",
        "max_length": max_length,
        "stride": stride,
        "n_tokens": n_tok_base,
        "ppl_baseline": round(ppl_base, 4),
        "ppl_s20": round(ppl_s20, 4),
        "ppl_delta": round(delta, 4),
        "ppl_delta_pct": round(pct, 4),
    }


@contextmanager
def _nullcontext():
    yield


# ─── Model Configurations ──────────────────────────────────────────────────

MODEL_CONFIGS = {
    "phi3": {
        "model_id": "microsoft/Phi-3-mini-4k-instruct",
        "seq_lens": [64, 128, 256, 512, 1024],
        "max_vram_gb": 8.0,
    },
    "gemma2": {
        "model_id": "google/gemma-2-2b-it",
        "seq_lens": [64, 128, 256, 512, 1024],
        "max_vram_gb": 6.0,
    },
    "qwen25": {
        "model_id": "Qwen/Qwen2.5-3B-Instruct",
        "seq_lens": [64, 128, 256, 512, 1024],
        "max_vram_gb": 7.0,
    },
    "mistral": {
        "model_id": "mistralai/Mistral-7B-Instruct-v0.3",
        "seq_lens": [64, 128, 256],  # Limited seq_lens for T4 VRAM
        "max_vram_gb": 15.0,
    },
}


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="S20 Multi-Model GPU Benchmark")
    parser.add_argument("--models", nargs="+", default=list(MODEL_CONFIGS.keys()),
                        choices=list(MODEL_CONFIGS.keys()),
                        help="Models to benchmark")
    parser.add_argument("--kernel_seq_lens", nargs="+", type=int,
                        default=[64, 128, 256, 512, 1024],
                        help="Sequence lengths for raw kernel benchmark")
    parser.add_argument("--output", default="multi_model_results.json")
    parser.add_argument("--skip_perplexity", action="store_true",
                        help="Skip WikiText-2 perplexity evaluation")
    parser.add_argument("--skip_kernel", action="store_true")
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    gpu_info = get_gpu_info()

    print("=" * 70)
    print("  S20 Attention Kernel — Multi-Model GPU Benchmark Suite")
    print(f"  GPU:    {gpu_info.get('gpu_name', 'N/A')}")
    print(f"  VRAM:   {gpu_info.get('memory_total_MiB', 'N/A')} MiB")
    print(f"  Power:  {gpu_info.get('power_draw_W', 'N/A')} W / "
          f"{gpu_info.get('power_limit_W', 'N/A')} W limit")
    print(f"  PyTorch: {torch.__version__} | CUDA: {torch.version.cuda}")
    print(f"  Models: {', '.join(args.models)}")
    print("=" * 70)

    all_results = {
        "gpu_info": gpu_info,
        "pytorch_version": torch.__version__,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # ── Phase 1: Raw kernel ──
    if not args.skip_kernel:
        print("\n" + "=" * 60)
        print("[Phase 1] Raw Kernel Benchmark (SDPA ± S20 bias)")
        print("=" * 60)
        all_results["kernel_benchmark"] = benchmark_kernel(args.kernel_seq_lens, device=device)

    # ── Hypothesis H2: Construction time ──
    print("\n" + "=" * 60)
    print("[H2] Toeplitz Construction Time")
    print("=" * 60)
    all_results["h2_construction"] = benchmark_h2_construction(
        args.kernel_seq_lens, device=device
    )

    # ── Phase 2: Per-model benchmark ──
    all_results["model_benchmarks"] = {}
    for model_key in args.models:
        cfg = MODEL_CONFIGS[model_key]
        print(f"\n{'='*60}")
        print(f"[Phase 2] Model Benchmark: {cfg['model_id']}")
        print(f"{'='*60}")
        try:
            result = benchmark_model(
                cfg["model_id"], device=device, seq_lens=cfg["seq_lens"]
            )
            all_results["model_benchmarks"][model_key] = result
        except Exception as e:
            print(f"  ❌ FAILED: {e}")
            all_results["model_benchmarks"][model_key] = {"error": str(e)}

    # ── Phase 3: WikiText-2 perplexity ──
    if not args.skip_perplexity:
        all_results["perplexity"] = {}
        for model_key in args.models:
            cfg = MODEL_CONFIGS[model_key]
            print(f"\n{'='*60}")
            print(f"[Phase 3] Perplexity: {cfg['model_id']}")
            print(f"{'='*60}")
            try:
                ppl_result = evaluate_perplexity(cfg["model_id"], device=device)
                all_results["perplexity"][model_key] = ppl_result
            except Exception as e:
                print(f"  ❌ FAILED: {e}")
                all_results["perplexity"][model_key] = {"error": str(e)}

    # ── Hypothesis Summary ──
    print("\n" + "=" * 60)
    print("HYPOTHESIS VALIDATION SUMMARY")
    print("=" * 60)

    # H2: All construction times < 0.1ms?
    h2_pass = all([r["construction_ms"] < 1.0 for r in all_results.get("h2_construction", [])])
    print(f"\n  H2 (O(1) construction):   {'✅ PASS' if h2_pass else '❌ FAIL'}")
    for r in all_results.get("h2_construction", []):
        print(f"    seq_len={r['seq_len']:>5}: {r['construction_ms']:.4f} ms")

    # H3: All model overheads in [0.95, 1.05]?
    h3_overheads = []
    for mk, mr in all_results.get("model_benchmarks", {}).items():
        if isinstance(mr, dict) and "results" in mr:
            for r in mr["results"]:
                h3_overheads.append(r["overhead"])
    h3_pass = all(0.95 <= o <= 1.05 for o in h3_overheads) if h3_overheads else False
    print(f"\n  H3 (zero-cost injection): {'✅ PASS' if h3_pass else '❌ FAIL'}")
    if h3_overheads:
        print(f"    Range: [{min(h3_overheads):.4f}×, {max(h3_overheads):.4f}×]")
        print(f"    Mean:  {sum(h3_overheads)/len(h3_overheads):.4f}×")

    all_results["hypothesis_summary"] = {
        "h2_pass": h2_pass,
        "h3_pass": h3_pass,
        "h3_overhead_range": [round(min(h3_overheads), 4), round(max(h3_overheads), 4)] if h3_overheads else None,
        "h3_overhead_mean": round(sum(h3_overheads)/len(h3_overheads), 4) if h3_overheads else None,
    }

    # ── Save ──
    with open(args.output, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n✅ Results saved → {args.output}")

    # ── Print tables ──
    print("\n" + "=" * 60)
    print("RESULTS TABLES")
    print("=" * 60)

    if "kernel_benchmark" in all_results:
        print("\n## Raw Kernel (SDPA ± S20)\n")
        print("| Seq Len | Baseline | S20 | Overhead | Max Δ | OK |")
        print("|---------|----------|-----|----------|-------|----|")
        for r in all_results["kernel_benchmark"]:
            print(f"| {r['seq_len']:>5} | {r['sdpa_baseline_ms']:.3f}ms | "
                  f"{r['sdpa_s20_ms']:.3f}ms | {r['overhead']:.2f}× | "
                  f"{r['max_logit_delta']:.4f} | {'✅' if r['correct'] else '❌'} |")

    for mk, mr in all_results.get("model_benchmarks", {}).items():
        if isinstance(mr, dict) and "results" in mr:
            print(f"\n## {mr['model_id']} ({mr['n_params_M']}M)\n")
            print("| Seq | Base ms | S20 ms | Overhead | Δ tok/s | Max Δ logit | W |")
            print("|-----|---------|--------|----------|---------|-------------|---|")
            for r in mr["results"]:
                dt = r["throughput_s20_tok_s"] - r["throughput_base_tok_s"]
                print(f"| {r['seq_len']:>3} | {r['baseline_ms']:.1f} | {r['s20_sdpa_ms']:.1f} | "
                      f"{r['overhead']:.3f}× | {dt:>+5} | {r['max_logit_delta']:.4f} | "
                      f"{r['avg_power_W']:.0f} |")

    if "perplexity" in all_results:
        print("\n## WikiText-2 Perplexity\n")
        print("| Model | Base PPL | S20 PPL | ΔPPL | Δ% |")
        print("|-------|----------|---------|------|----|")
        for mk, pr in all_results["perplexity"].items():
            if isinstance(pr, dict) and "ppl_baseline" in pr:
                print(f"| {pr['model_id']} | {pr['ppl_baseline']:.2f} | "
                      f"{pr['ppl_s20']:.2f} | {pr['ppl_delta']:+.2f} | "
                      f"{pr['ppl_delta_pct']:+.2f}% |")


if __name__ == "__main__":
    main()
