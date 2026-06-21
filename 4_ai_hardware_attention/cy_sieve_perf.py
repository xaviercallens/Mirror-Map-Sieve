#!/usr/bin/env python3
"""
cy_sieve_perf.py — tests.md §6, performance of the CY-Sieve Triton kernel.

ONLY meaningful if §5 (cy_sieve_quality_gate.py) passes; T6.3 forbids reporting a
speed number without the matching quality result. This benchmark measures, on a
single named GPU:

  * T6.2 prefill latency / throughput of the CY-Sieve Triton kernel vs:
      - torch SDPA dense (the standard fused baseline)
      - an explicit additive-bias SDPA carrying a full [L,L] bias *table* in HBM
        (the "RoPE/ALiBi materialized-bias" cost model — the thing CY-Sieve's
         on-the-fly Tier-1/Tier-3 bias is supposed to avoid paying for)
  * T6.1 bias-path HBM traffic: bytes the bias path must read from HBM.
      CY-Sieve Tier-1/Tier-3 reads a length-L vector (O(L) floats), NOT the
      O(L^2) materialized matrix the table baseline reads — that gap is the
      core memory-bandwidth claim, reported as measured bytes.

This replaces the old run_full_benchmark.py (which benchmarked the earlier
exploratory s20_* kernels, graded "arbitrary" in the audit). It benchmarks the
actual shipped kernel: cy_sieve_triton.cy_sieve_attention_triton.

Author: SocrateAI Laboratory (X. Callens) + Claude (Opus 4.8). License: MIT.
"""
from __future__ import annotations
import argparse, json, math, os, sys, time

sys.path.insert(0, os.path.dirname(__file__))
import cy_sieve_reference as cy
import cy_sieve_triton as tri


def _sync(device):
    if device == "cuda":
        import torch
        torch.cuda.synchronize()


def _time(fn, n_warmup=5, n_runs=30, device="cuda"):
    for _ in range(n_warmup):
        fn()
    _sync(device)
    t0 = time.perf_counter()
    for _ in range(n_runs):
        fn()
    _sync(device)
    return (time.perf_counter() - t0) / n_runs * 1000.0     # ms/run


def sdpa_dense(Q, K, V):
    """torch fused SDPA, causal, no positional bias (pure attention cost)."""
    import torch
    return torch.nn.functional.scaled_dot_product_attention(
        Q[None, None], K[None, None], V[None, None], is_causal=True)[0, 0]


def sdpa_table_bias(Q, K, V, bias_mat):
    """SDPA with an explicit [L,L] additive bias matrix materialized in HBM —
    the cost model for a positional scheme that stores its bias as a table."""
    import torch
    return torch.nn.functional.scaled_dot_product_attention(
        Q[None, None], K[None, None], V[None, None], attn_mask=bias_mat[None, None])[0, 0]


def run(seq_lens, head_dim, seq="S20", tau=128.0, output=None,
        block_n=32, num_stages=1):
    import torch
    if not tri.HAS_TRITON:
        print("Triton/CUDA unavailable — §6 perf requires a GPU. "
              "Run on the L4/A100 box (see GPU_SETUP.md).")
        res = {"error": "no_cuda_triton", "note": "run on GPU"}
        if output:
            json.dump(res, open(output, "w"), indent=2)
        return res

    device = "cuda"
    gpu = torch.cuda.get_device_name(0)
    props = torch.cuda.get_device_properties(0)
    print("=" * 74)
    print(f"  CY-Sieve §6 PERF — {gpu} ({props.total_memory/1e9:.0f} GB) | "
          f"D={head_dim}, tau={tau}")
    print("  (speed is only meaningful alongside the §5 quality verdict — T6.3)")
    print("=" * 74)
    fp = torch.float16

    rows = []
    for L in seq_lens:
        g = torch.Generator(device=device).manual_seed(L)
        Q = torch.randn(L, head_dim, device=device, dtype=fp, generator=g)
        K = torch.randn(L, head_dim, device=device, dtype=fp, generator=g)
        V = torch.randn(L, head_dim, device=device, dtype=fp, generator=g)
        bias_vec = torch.tensor(cy.build_bias_vector(L, seq, tau)[:L],
                                device=device, dtype=torch.float32)

        # Materialized [L,L] bias table (the HBM-heavy baseline). Guard memory:
        # the construction peaks well above one L² tensor (int32 index grid 4B +
        # fp16 table 2B + SDPA's own L² scores 2B ≈ 8 B/elem), so budget the PEAK
        # at ~0.30·VRAM. Skipping a too-large L is reported, not silently dropped.
        table_ms = table_bytes = None
        if L * L * 8 <= 0.30 * props.total_memory:
            idx = torch.arange(L, device=device, dtype=torch.int32)
            d = idx[:, None] - idx[None, :]                       # int32 [L,L]
            mat = bias_vec[d.clamp(min=0)].to(fp)                 # fp16 [L,L]
            mat.masked_fill_(d < 0, float("-inf"))               # causal, in place
            del d
            table_bytes = mat.numel() * mat.element_size()
            table_ms = _time(lambda: sdpa_table_bias(Q, K, V, mat), device=device)
            del mat
            if device == "cuda":
                torch.cuda.empty_cache()
        else:
            print(f"  [skip] L={L}: materialized-table baseline exceeds VRAM "
                  f"budget (need ~{L*L*8/1e9:.1f} GB peak); CY-Sieve path still timed.")

        dense_ms = _time(lambda: sdpa_dense(Q, K, V), device=device)
        cy_ms = _time(lambda: tri.cy_sieve_attention_triton(
            Q, K, V, bias_vec, causal=True, block_n=block_n,
            num_stages=num_stages), device=device)

        # T6.1 bias-path HBM: CY-Sieve reads the O(L) vector; the table baseline
        # reads the O(L^2) matrix. Report both so the gap is explicit.
        cy_bias_bytes = bias_vec.numel() * bias_vec.element_size()
        row = {
            "seq_len": L,
            "cy_sieve_ms": round(cy_ms, 4),
            "sdpa_dense_ms": round(dense_ms, 4),
            "sdpa_table_bias_ms": round(table_ms, 4) if table_ms else None,
            "cy_bias_hbm_bytes": cy_bias_bytes,
            "table_bias_hbm_bytes": table_bytes,
            "bias_hbm_reduction_x": (round(table_bytes / cy_bias_bytes, 1)
                                     if table_bytes else None),
            "cy_vs_dense_ratio": round(cy_ms / dense_ms, 3),
        }
        rows.append(row)
        tb = f"{table_ms:7.3f}" if table_ms else "   n/a "
        print(f"  L={L:<7} cy_sieve={cy_ms:7.3f}ms  dense={dense_ms:7.3f}ms  "
              f"table_bias={tb}ms  bias_HBM={cy_bias_bytes:>9}B vs "
              f"{table_bytes if table_bytes else 'n/a'}B")

    out = {"hardware": gpu, "head_dim": head_dim, "seq": seq, "tau": tau,
           "block_n": block_n, "num_stages": num_stages,
           "torch": torch.__version__, "cuda": torch.version.cuda,
           "rows": rows,
           "note": "T6.3: report ONLY beside the §5 quality verdict; "
                   "speed alone is not a contribution."}
    if output:
        json.dump(out, open(output, "w"), indent=2)
        print(f"\n  results -> {output}")
    return out


def main():
    ap = argparse.ArgumentParser(description="CY-Sieve §6 perf benchmark")
    ap.add_argument("--seq_lens", type=int, nargs="+",
                    default=[1024, 2048, 4096, 8192, 16384])
    ap.add_argument("--head_dim", type=int, default=64)
    ap.add_argument("--seq", default="S20")
    ap.add_argument("--tau", type=float, default=128.0)
    ap.add_argument("--block_n", type=int, default=32)
    ap.add_argument("--num_stages", type=int, default=1)
    ap.add_argument("--output", default="cy_sieve_perf_results.json")
    args = ap.parse_args()
    run(args.seq_lens, args.head_dim, args.seq, args.tau, args.output,
        args.block_n, args.num_stages)


if __name__ == "__main__":
    main()
