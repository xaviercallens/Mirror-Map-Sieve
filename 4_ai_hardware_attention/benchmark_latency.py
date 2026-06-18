#!/usr/bin/env python3
"""
benchmark_latency.py — Single-run Callens-ALIX latency benchmark

Quick latency test for the Callens-ALIX, Callens-LIA, and Callens-AL kernels.
Targets L4/T4/A100 GPUs, falls back to CPU.

Usage:
    python benchmark_latency.py --seq_len 256
"""
import sys
import argparse
import time

sys.path.insert(0, ".")
from callens_alix_kernel import callens_alix_attention, build_int64_decay_table, callens_alix_s20

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seq_len", type=int, default=256)
    parser.add_argument("--head_dim", type=int, default=64)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--heads", type=int, default=8)
    args = parser.parse_args()

    # Always verify S_20 arithmetic first
    print("Verifying Callens-ALIX S_20 arithmetic:")
    for n in range(10):
        v = callens_alix_s20(n)
        print(f"  S_20({n}) = {v}")

    table = build_int64_decay_table(17)
    print(f"\nINT64 decay table (d=0..5): {table[:6]}")

    if not HAS_TORCH:
        print("\n⚠️  PyTorch not available — GPU benchmark skipped")
        return

    device = "cuda" if torch.cuda.is_available() else "cpu"
    gpu = torch.cuda.get_device_name(0) if device == "cuda" else "CPU"
    print(f"\nHardware: {gpu} | Device: {device}")

    torch.manual_seed(42)
    q = torch.randn(args.batch, args.heads, args.seq_len, args.head_dim, device=device)
    k = torch.randn(args.batch, args.heads, args.seq_len, args.head_dim, device=device)
    v = torch.randn(args.batch, args.heads, args.seq_len, args.head_dim, device=device)

    # Warmup
    for _ in range(5):
        out, _ = callens_alix_attention(q, k, v, args.seq_len, args.head_dim)
    if device == "cuda":
        torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(50):
        out, attn = callens_alix_attention(q, k, v, args.seq_len, args.head_dim)
        if device == "cuda":
            torch.cuda.synchronize()
    ms = (time.perf_counter() - t0) / 50 * 1000

    print(f"\nCallens-ALIX latency: {ms:.3f} ms")
    print(f"Output shape: {list(out.shape)}")
    print(f"Row-sum check: {attn[0,0,0].sum().item():.6f} (should be 1.0)")
    print("✅ Benchmark complete.")


if __name__ == "__main__":
    main()
