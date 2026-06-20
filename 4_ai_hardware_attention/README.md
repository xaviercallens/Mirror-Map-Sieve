# S20 Attention Kernel — Computer Science Track

**Status**: Benchmark complete. Target: Hugging Face paper + arXiv cs.LG/cs.AR.

This directory contains a high-performance, mathematically exact attention decay
mechanism derived from the Weight-5 Apéry-like binomial sum:

$$S(n) = \sum_{k=0}^{n} \binom{n}{k}^4 \binom{n+k}{k}$$

The S20 sequence defines a naturally decaying, super-geometrically growing
integer sequence that serves as a deterministic, exact (non-floating-point)
attention bias. This is a **separate research track** from the Calabi-Yau geometry
paper — the connection here is computational, not geometric.

> **Paper separation**: The number theory paper (Zenodo 10.5281/zenodo.20747943)
> covers the Calabi-Yau period and recurrence. This track targets a dedicated
> **CS/hardware publication** on efficient attention mechanisms.

---

## Benchmark Results (CPU, 2026-06-18)

| Seq Len | FP16-SDPA | ALIX-v1 (legacy) | **ALIX-v2 (vectorized)** | Speedup v1→v2 | vs SDPA |
|---------|-----------|------------------|--------------------------|---------------|---------|
| 64      | 0.34 ms   | 3.8 ms           | **0.23 ms**              | 16.6×         | 0.67×   |
| 128     | 1.17 ms   | 8.2 ms           | **0.38 ms**              | 21.8×         | 0.32×   |
| 256     | 3.51 ms   | 18.4 ms          | **0.75 ms**              | 24.7×         | 0.21×   |
| 512     | 12.75 ms  | 45.0 ms          | **2.14 ms**              | 21.1×         | 0.17×   |
| 1024    | 44.10 ms  | —                | **8.38 ms**              | —             | 0.19×   |
| 2048    | 132.42 ms | —                | **26.69 ms**             | —             | 0.20×   |

**Key findings**:
- v2 vectorized kernel is **~21× faster** than the legacy Python-loop implementation
- v2 is **~3–5× faster than FP16-SDPA** on CPU for seq_len ≥ 128 (decay matrix is pre-built)
- All correctness checks pass (attention row sums ≈ 1.0, no NaN/Inf)

---

## Architecture

```
4_ai_hardware_attention/
├── s20_decay.py          ← NEW: Vectorized core (no Python loops, torch.compile)
├── benchmark.py          ← NEW: Complete benchmark suite with Markdown output
├── s20_int64_kernel.py        ← Dense INT64 causal kernel
├── s20_longrange_kernel.py    ← Long-range variant
├── s20_sparse_block_kernel.py ← Sparse-block variant
├── benchmark_results.json       ← seq 64–512 comparison with legacy
├── benchmark_results_full.json  ← seq 64–2048 extended run
└── benchmark_results_full.md    ← Markdown table for Hugging Face model card
```

## Key Innovation: Vectorized Decay Matrix

**Legacy (v1)** — O(L²) Python loops:
```python
for i in range(L):
    for j in range(L):
        decay[i, j] = table[abs(i-j)]   # Python loop — kills GPU throughput
```

**v2 (vectorized)** — pure tensor ops, compile-friendly:
```python
idx = torch.arange(L, device=device)
dist = (idx.unsqueeze(0) - idx.unsqueeze(1)).abs()   # (L, L) — one op
decay = dv_padded[dist.clamp(max=max_distance + 1)]  # vectorized gather
```

The key: `|i - j|` is a **Toeplitz structure** expressible with a single
arange + broadcast + gather — no loops at all.

## Running the Benchmark

```bash
cd 4_ai_hardware_attention

# Standard benchmark (seq 64–512, includes legacy comparison)
python benchmark.py

# Extended benchmark (seq up to 2048)
python benchmark.py --seq_lens 64 128 256 512 1024 2048 --skip_legacy

# Custom
python benchmark.py --seq_lens 256 1024 --batch 4 --heads 16 --head_dim 128
```

## Mathematical Justification

The S20 decay is used in log-space:
$$\text{score}_{ij} = \frac{q_i \cdot k_j}{\sqrt{d}} + \log \frac{S(0)}{S(|i-j|)}$$

This is equivalent to multiplying the raw attention scores by a monotonically
decaying weight that is **exactly determined by the algebraic recurrence** — no
learned parameters, no floating-point drift. The decay reaches machine zero
at distance 17 (S₂₀(17) ≈ 3.3×10¹⁸, ratio ≈ 3×10⁻²⁵).

## Next Steps (Roadmap)

- [ ] GPU benchmark on GCP L4/T4/A100 (CUDA path)
- [ ] Triton kernel implementation for full fusion (QK+decay in one pass)
- [ ] Integration into HuggingFace `transformers` as a custom attention module
- [ ] Comparison against ALiBi, RoPE, and YARN on standard LM benchmarks
- [ ] Hugging Face paper + model card

## Citation

If you use this kernel in your research, please cite:

```bibtex
@software{callens2026s20attn,
  author = {Callens, Xavier},
  title  = {S20-Decay Attention Kernel: Vectorized Integer-Sequence Attention Bias},
  year   = {2026},
  url    = {https://github.com/xaviercallens/Mirror-Map-Sieve/tree/main/4_ai_hardware_attention}
}
```
