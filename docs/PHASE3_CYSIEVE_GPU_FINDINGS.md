# CY-Sieve GPU-Phase Findings (intermediary, 2026-06-21)

**Status: intermediary. Honest and reproducible, but incomplete.** The decisive
quality number (§5 on real WikiText-2) was still computing when this was written;
this document records what the GPU runs on an **NVIDIA L4** have *already*
established, and is updated when the quality gate completes. Raw artifacts:
`4_ai_hardware_attention/gpu_phase_runs/`.

Hardware: NVIDIA L4 (24 GB), PyTorch 2.9.1+cu129, Triton 3.5.1, project SocrateAI.
Driver: `run_gpu_phase.py` → `tests.md` §4 (parity) / §5 (quality) / §6 (perf).

---

## §4 — Kernel correctness: **PASS** (final)

The Triton CY-Sieve kernel (`cy_sieve_triton.py`) reproduces the CPU reference
(`cy_sieve_attention.flash_sdpa_with_bias`, itself ~3e-16 from dense softmax) to
within FP16 tolerance (rel-err < 2⁻⁸): **4/4 tests passed** across
(L, D, τ) ∈ {(128,64,20), (256,64,128), (256,128,480)} + a smoke test.

**Reading.** The fused GPU path — online-softmax with the per-distance bias
(Tier-1 exact INT64 table + Tier-3 log penalty) generated *inside* the kernel —
computes the same attention as the dense reference. The on-the-fly bias is
implemented correctly; downstream measurements test the design, not a bug.
(`block_n=32`, `num_stages=1` keep SMEM under the L4's ~100 KB.)

## §6 — Performance: **core memory claim holds; latency claim does not** (final)

L4, D=64, fp16, τ=128, causal (run 1 measured 1K–16K before an OOM at 32768²,
now guarded):

| L | CY-Sieve (ms) | dense SDPA (ms) | table-bias SDPA (ms) | CY bias HBM | table bias HBM |
|---|---|---|---|---|---|
| 1024 | 0.056 | 0.054 | 0.060 | 4 KB | 2 MB |
| 2048 | 0.104 | 0.054 | 0.117 | 8 KB | 8 MB |
| 4096 | 0.259 | 0.060 | 0.270 | 16 KB | 32 MB |
| 8192 | 1.166 | 0.316 | 0.805 | 32 KB | 128 MB |
| 16384 | 3.969 | 1.063 | 3.862 | 64 KB | 512 MB |

- ✅ **Bias-path HBM — the central thesis — confirmed and measured.** CY-Sieve's
  positional bias reads **O(L)** bytes (a length-L vector from the recurrence) vs
  **O(L²)** for a materialized bias table: **8192× less at L=16384** (64 KB vs
  512 MB), and the gap *widens* with context length.
- ❌ **Not yet a wall-clock win.** The current (unfused) Triton kernel is ~3.7×
  *slower* than fused dense SDPA at 16K and only matches the table-bias SDPA. The
  HBM saving is real but not yet *converted* into latency — cuDNN's SDPA is far
  more tuned. Reported as-is per the `tests.md` T6.3 honesty guard; speed is never
  presented without this caveat.

**Net:** the win is **memory traffic at long context**, not raw speed. The case is
for bandwidth-bound / very-long-context regimes; turning the HBM saving into time
requires fusing the bias deeper into the FlashAttention loop.

## §5 — Quality gate: methodology fixed; verdict pending

This is the test that decides whether the kernel is worth anything, and the part
that took the most iteration to do *honestly*:

1. **Rejected** zero-shot-swapping the positional scheme into a *frozen* GPT-2 —
   it is invalid: every alternative scheme collapses equally (native ppl 32.5 vs
   ALiBi 1641, sliding 2529, CY-Sieve ~7180 on WikiText-2). It measures train/test
   mismatch, not the scheme.
2. **Adopted** the ALiBi-paper methodology: **train small GPTs from scratch**,
   identical arch/data/compute, one per scheme (learned-absolute / ALiBi /
   sliding-window / CY-Sieve per-head-τ ladder + a single-τ sweep), then compare
   validation perplexity at the train context **and 2×/4× length extrapolation**.

**Early directional signal (from a synthetic-corpus shakedown — NOT a verdict):**
length extrapolation already discriminated the schemes —

| scheme | @512 (train) | @1024 (2×) | @2048 (4×) |
|---|---|---|---|
| learned-absolute | 1.007 | **2495** | **251818** |
| ALiBi | 1.008 | 1.004 | 1.002 |
| sliding-window | 1.006 | 1.003 | 1.002 |
| **CY-Sieve τ-ladder** | 1.006 | 1.003 | 1.002 |
| CY-Sieve τ=512 | 1.007 | 2.73 | 6.27 |

Even on a trivial corpus this reproduces the textbook result — learned-absolute
positions blow up past the training length — while **CY-Sieve (τ-ladder, τ≤128)
extrapolates as cleanly as ALiBi/sliding**, and an over-shallow τ=512 degrades.
This is *mechanism* evidence for the per-head-τ design, not a quality claim. The
absolute ppl≈1.0 reflects the trivially-memorized synthetic corpus (a bug, since
fixed); the real-WikiText-2 run is what produces a citable verdict.

**Anticipated (a falsifiable hypothesis, no verdict claimed):** if the
geometry-fixed bias (slope log λ=3.762, curvature β=2 from the rank-4 MUM
Calabi–Yau-3-fold tail, spread across heads by the τ-ladder) carries real
positional signal, CY-Sieve val perplexity lands **within +1% of the best
baseline** with no worse extrapolation — which, paired with the 8192× bias-HBM
reduction, is the whole case. **Kill criterion (unchanged): >5% regression vs the
best baseline, or extrapolation collapse ⇒ negative result, not shipped.**

---

## Reproducibility

```bash
pip install -r 4_ai_hardware_attention/requirements-gpu.txt
python 4_ai_hardware_attention/run_gpu_phase.py     # §4 + §5 + §6 → one JSON
```
On GCP the same is driven unattended by `4_ai_hardware_attention/gcp_startup.sh`
(an L4 that clones, runs, uploads to GCS, and self-terminates).
