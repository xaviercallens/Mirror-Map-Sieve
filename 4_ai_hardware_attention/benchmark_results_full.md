## S20 Attention Kernel Benchmark Results

**Hardware**: CPU  
**Device**: cpu  
**Config**: batch=1, heads=8, head_dim=64

| Seq Len | FP16-SDPA | ALIX-v1 (legacy) | ALIX-v2 (vectorized) | LIA-v2 (vectorized) | Speedup v1→v2 | Overhead vs SDPA |
|---------|-----------|------------------|----------------------|---------------------|---------------|-----------------|
|      64 |    0.30 ms |                — |           0.22 ms |            0.21 ms |             — |      0.74× |
|     128 |    1.04 ms |                — |           0.37 ms |            0.36 ms |             — |      0.35× |
|     256 |    3.64 ms |                — |           0.78 ms |            0.73 ms |             — |      0.21× |
|     512 |   12.89 ms |                — |           2.11 ms |            2.08 ms |             — |      0.16× |
|    1024 |   44.10 ms |                — |           8.38 ms |            8.42 ms |             — |      0.19× |
|    2048 |  132.41 ms |                — |          26.69 ms |           26.64 ms |             — |      0.20× |

> **Methodology**: 3 warmup runs, 20 timed runs. Decay matrix pre-built (not included in per-call timing).
> **Correctness**: Verified by attention row-sum check (tol=1e-4) and NaN/Inf detection.