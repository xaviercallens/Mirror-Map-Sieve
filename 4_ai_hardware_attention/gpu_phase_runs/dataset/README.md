---
license: mit
tags:
- attention
- positional-encoding
- benchmark
- negative-result
- calabi-yau
- number-theory
pretty_name: CY-Sieve Attention — GPU Quality/Perf Benchmark (NVIDIA L4)
configs:
- config_name: quality_perplexity
  data_files: quality_perplexity.csv
- config_name: perf_hbm
  data_files: perf_hbm.csv
---

# CY-Sieve Attention — GPU benchmark results (NVIDIA L4, 2026-06-22)

Benchmark artifacts for the **CY-Sieve positional-attention kernel**, a falsifiable
engineering experiment from the [Mirror-Map-Sieve](https://github.com/xaviercallens/Mirror-Map-Sieve)
project. The bias derives from the weight-5 Apéry-like sequence
$S_{20}(n)=\sum_k \binom{n}{k}^4\binom{n+k}{k}$ (a Calabi–Yau **3-fold** period;
the geometry fixes the long-range decay slope $\log\lambda=3.762$ and curvature
$\beta=2$).

## ⚠️ Headline: this is a documented NEGATIVE result

On real WikiText-2, trained from scratch, the positional scheme **failed its
quality gate (KILL, +10.15%)** — a plain sliding window beat every CY-Sieve
variant. The kernel is numerically correct and has a real memory advantage, but a
fast kernel that hurts model quality is a failed kernel. We publish the negative
result deliberately; it is the science working as intended.

## Files

| file | contents |
|---|---|
| `quality_perplexity.csv` | §5 quality gate — val perplexity per positional scheme × context (the decisive result) |
| `perf_hbm.csv` | §6 — kernel latency + bias-path HBM bytes per sequence length |
| `run3_20260622_l4_quality.json` | raw §5 output (corpus, config, verdict) |
| `run3_20260622_l4_perf.json` | raw §6 output |
| `run3_20260622_l4_gpu_phase.json` | orchestrator summary (§4/§5/§6 headline) |
| `run3_20260622_l4.log` | full run log |
| `PHASE3_CYSIEVE_GPU_FINDINGS.md` | the complete findings writeup + redesign directions |

## §5 — Quality gate (the decisive result)

Methodology: train small GPTs **from scratch**, identical arch/data/compute, one
per positional scheme, on real WikiText-2 (`Salesforce/wikitext`), byte-level.
(Zero-shot-swapping the scheme on a *frozen* model was tried and rejected as
invalid — it collapses every scheme equally.) Validation perplexity:

| scheme | @512 (train) | @1024 (2×) | @2048 (4×) |
|---|---|---|---|
| **learned-absolute** | **4.22** | 12.10 | 20.82 |
| ALiBi | 10.74 | 11.73 | 11.35 |
| **sliding-window** | **4.99** | **5.07** | **5.03** |
| CY-Sieve τ-ladder | 11.33 | 12.31 | 12.05 |
| CY-Sieve τ=20 | 16.02 | 16.81 | 16.49 |
| CY-Sieve τ=128 | 6.80 | 7.12 | 7.00 |
| CY-Sieve τ=512 | 4.65 | 6.08 | 10.62 |

**Verdict: KILL.** Best baseline 4.22 (learned-absolute); best CY-Sieve 4.65
(τ=512) → **+10.15%**, past the >5% kill threshold. The geometry-fixed slope is too
steep for a drop-in scheme: no single τ balances absolute quality against
extrapolation, and the τ-ladder lands at ~11–12.

## §6 — Performance + memory (NVIDIA L4, D=64, fp16, causal)

| L | CY-Sieve (ms) | dense SDPA (ms) | bias-HBM reduction |
|---|---|---|---|
| 4096 | 0.26 | 0.06 | 2048× |
| 8192 | 1.08 | 0.29 | 4096× |
| 16384 | 4.16 | 1.02 | **8192×** |
| 32768 | 15.28 | 2.51 | 16384× |

The bias-path HBM claim is **confirmed** — O(L) bytes (recurrence-generated) vs
O(L²) for a materialized table. But the unfused kernel is **~4–6× slower** than
fused dense SDPA: a memory-traffic win, **not** a latency win. Per the project's
honesty rule, with §5 failing these numbers are *not* presented as a contribution.

## Hardware / reproducibility

NVIDIA L4 (24 GB), PyTorch 2.9.1+cu129, Triton 3.5.1. §4 Triton↔reference parity:
PASS (4/4). Full method: `PHASE3_CYSIEVE_GPU_FINDINGS.md` and
[the repo](https://github.com/xaviercallens/Mirror-Map-Sieve).

## Citation

```bibtex
@misc{callens2026cysieve,
  author = {Callens, Xavier},
  title  = {CY-Sieve Attention: a Calabi--Yau positional bias and its negative quality result},
  year   = {2026},
  url    = {https://github.com/xaviercallens/Mirror-Map-Sieve},
  doi    = {10.5281/zenodo.20747943}
}
```
