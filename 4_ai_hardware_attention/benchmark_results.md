## S20 Attention Kernel Benchmark Results

**Hardware**: CPU  
**Device**: cpu  
**Config**: batch=1, heads=8, head_dim=64

| Seq Len | FP16-SDPA | ALIX-v1 (legacy) | ALIX-v2 (vectorized) | LIA-v2 (vectorized) | Speedup v1→v2 | Overhead vs SDPA |
|---------|-----------|------------------|----------------------|---------------------|---------------|-----------------|
|      64 |    0.34 ms |           3.8 ms |           0.23 ms |            0.22 ms |         16.6× |      0.67× |
|     128 |    1.17 ms |           8.2 ms |           0.38 ms |            0.35 ms |         21.8× |      0.32× |
|     256 |    3.51 ms |          18.4 ms |           0.75 ms |            0.74 ms |         24.7× |      0.21× |
|     512 |   12.75 ms |          45.0 ms |           2.14 ms |            2.30 ms |         21.1× |      0.17× |

> **Methodology**: 3 warmup runs, 20 timed runs. Decay matrix pre-built (not included in per-call timing).
> **Correctness**: Verified by attention row-sum check (tol=1e-4) and NaN/Inf detection.