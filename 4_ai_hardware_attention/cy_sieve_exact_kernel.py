#!/usr/bin/env python3
"""
cy_sieve_exact_kernel.py — autoresearch on the top-2 EXACT-attention approaches:

  1. Mixed Precision   (INT64/INT32 QK accumulation + FP16 softmax)   ★★★★★
  2. Rescaled Integer  (QK in INT64 scaled by 2^k, exact dot-product) ★★★★

We measure NUMERICAL FIDELITY (max/mean abs error of attention output vs an FP64
reference) and a simple speed proxy, across precisions, plus the plain FP16 and
FP32 baselines. This is a CPU-runnable proxy of what a Triton kernel would do; the
question is whether higher-precision QK accumulation meaningfully reduces softmax
error at long context (where FP16 dot-products lose bits).

No model training here — pure kernel arithmetic fidelity. The headline question:
does Mixed/Rescaled-INT give a materially more *exact* attention than FP16, cheaply?

Author: SocrateAI Laboratory (X. Callens) + Claude (Opus 4.8). License: MIT.
"""
from __future__ import annotations
import argparse, json, math, time
import numpy as np


def softmax_rows(x):
    m = np.max(x, axis=-1, keepdims=True)
    e = np.exp(x - m); return e / np.sum(e, axis=-1, keepdims=True)


def attn_reference(Q, K, V):
    """FP64 ground-truth causal attention."""
    L, D = Q.shape
    s = (Q @ K.T) / math.sqrt(D)
    s = np.where(np.tril(np.ones((L, L), bool)), s, -np.inf)
    return softmax_rows(s) @ V


def attn_fp16(Q, K, V):
    Qh, Kh, Vh = (X.astype(np.float16) for X in (Q, K, V))
    L, D = Q.shape
    s = (Qh.astype(np.float32) @ Kh.T.astype(np.float32)) / math.sqrt(D)
    s = np.where(np.tril(np.ones((L, L), bool)), s, -np.inf)
    return (softmax_rows(s).astype(np.float16).astype(np.float32) @ Vh.astype(np.float32))


def attn_fp32(Q, K, V):
    L, D = Q.shape
    s = (Q.astype(np.float32) @ K.T.astype(np.float32)) / math.sqrt(D)
    s = np.where(np.tril(np.ones((L, L), bool)), s, -np.inf)
    return softmax_rows(s).astype(np.float32) @ V.astype(np.float32)


def attn_rescaled_int(Q, K, V, bits=14):
    """Rescaled INT: quantize Q,K to int by scaling 2^bits, do EXACT int64 dot
    products, rescale, then FP softmax (★★★★). The QK^T accumulation carries no
    floating rounding — only the input quantization error remains."""
    L, D = Q.shape
    scale = (1 << bits)
    Qi = np.round(Q * scale).astype(np.int64)
    Ki = np.round(K * scale).astype(np.int64)
    # exact integer dot products (int64; guard overflow: D*max^2 << 2^63 for bits<=15)
    dots = Qi @ Ki.T                                   # int64 [L,L], EXACT
    s = dots.astype(np.float64) / (scale * scale * math.sqrt(D))
    s = np.where(np.tril(np.ones((L, L), bool)), s, -np.inf)
    return softmax_rows(s) @ V


def attn_mixed(Q, K, V, bits=14):
    """Mixed precision (★★★★★): exact-ish INT QK accumulation (as rescaled int)
    + FP16 softmax + FP16 V matmul — the production-friendly compromise."""
    L, D = Q.shape
    scale = (1 << bits)
    Qi = np.round(Q * scale).astype(np.int64); Ki = np.round(K * scale).astype(np.int64)
    dots = Qi @ Ki.T
    s = (dots.astype(np.float32) / (scale * scale * math.sqrt(D)))
    s = np.where(np.tril(np.ones((L, L), bool)), s, -np.inf)
    p = softmax_rows(s).astype(np.float16).astype(np.float32)
    return p @ V.astype(np.float16).astype(np.float32)


KERNELS = {"fp32": attn_fp32, "fp16": attn_fp16,
           "rescaled_int": attn_rescaled_int, "mixed_int_fp16": attn_mixed}


def run(seq_lens, D=64, seed=0, output=None):
    rng = np.random.default_rng(seed)
    rows = []
    print(f"EXACT-KERNEL fidelity (vs FP64 ref) | D={D}")
    for L in seq_lens:
        Q = rng.standard_normal((L, D)); K = rng.standard_normal((L, D)); V = rng.standard_normal((L, D))
        ref = attn_reference(Q, K, V)
        ref_norm = np.max(np.abs(ref)) + 1e-9
        row = {"seq_len": L}
        print(f"  L={L}:")
        for name, fn in KERNELS.items():
            t0 = time.perf_counter()
            out = fn(Q, K, V)
            ms = (time.perf_counter() - t0) * 1000
            rel = float(np.max(np.abs(out - ref)) / ref_norm)
            mean_rel = float(np.mean(np.abs(out - ref)) / ref_norm)
            row[name] = {"max_rel_err": rel, "mean_rel_err": mean_rel, "ms": round(ms, 2)}
            print(f"    {name:>15}: max_rel_err {rel:.2e}  mean {mean_rel:.2e}  ({ms:.1f}ms)")
        rows.append(row)
    out_obj = {"D": D, "rows": rows,
               "note": "rescaled_int QK^T is exact integer accumulation; mixed adds "
                       "FP16 softmax/V. Compare both vs fp16 (the production baseline)."}
    if output:
        json.dump(out_obj, open(output, "w"), indent=2)
        print(f"\n-> {output}")
    # verdict
    if rows:
        big = rows[-1]
        print(f"\n  At L={big['seq_len']}: fp16 max_rel_err {big['fp16']['max_rel_err']:.2e} vs "
              f"mixed {big['mixed_int_fp16']['max_rel_err']:.2e} vs "
              f"rescaled {big['rescaled_int']['max_rel_err']:.2e}")
    return out_obj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq_lens", type=int, nargs="+", default=[128, 512, 2048])
    ap.add_argument("--head_dim", type=int, default=64)
    ap.add_argument("--output", default="exact_kernel_results.json")
    args = ap.parse_args()
    run(args.seq_lens, args.head_dim, output=args.output)


if __name__ == "__main__":
    main()
