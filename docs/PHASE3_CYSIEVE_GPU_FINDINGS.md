# CY-Sieve GPU-Phase Findings (2026-06-22, COMPLETE)

**Status: complete. The quality gate returned a NEGATIVE result (KILL).** On real
WikiText-2, trained from scratch, CY-Sieve's positional bias is **+10.15% worse**
than the best baseline at the training context — past the >5% kill threshold. The
kernel is *correct* (§4 PASS) and its memory claim is *confirmed* (§6, 8192× less
bias HBM), but the **positional scheme fails its quality gate and is reported as a
negative result, not shipped** — exactly as `tests.md` requires. Raw artifacts:
`4_ai_hardware_attention/gpu_phase_runs/run3_20260622_*`.

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

| L | CY-Sieve (ms) | dense SDPA (ms) | table-bias SDPA (ms) | bias-HBM reduction |
|---|---|---|---|---|
| 1024 | 0.055 | 0.054 | 0.060 | 512× |
| 2048 | 0.105 | 0.053 | 0.116 | 1024× |
| 4096 | 0.260 | 0.060 | 0.268 | 2048× |
| 8192 | 1.084 | 0.288 | 0.805 | 4096× |
| 16384 | 4.156 | 1.016 | 3.938 | **8192×** |
| 32768 | 15.28 | 2.51 | (skipped: >VRAM) | 16384× |

(run-3 numbers; the materialized-table baseline is skipped at 32768 because its
[L,L] tensor exceeds the VRAM budget — itself a demonstration of the O(L²) wall
that CY-Sieve's O(L) bias avoids.)

- ✅ **Bias-path HBM — the central thesis — confirmed and measured.** CY-Sieve's
  positional bias reads **O(L)** bytes (a length-L vector from the recurrence) vs
  **O(L²)** for a materialized bias table: **8192× less at L=16384** (64 KB vs
  512 MB), and the gap *widens* with context length.
- ❌ **Not yet a wall-clock win.** The current (unfused) Triton kernel is ~4× *slower*
  than fused dense SDPA at 16K (4.16 vs 1.02 ms) and ~6× at 32K (15.3 vs 2.5 ms),
  only matching the table-bias SDPA. The HBM saving is real but not yet *converted*
  into latency — cuDNN's SDPA is far more tuned. Reported as-is per the `tests.md`
  T6.3 honesty guard; speed is never presented without this caveat.
- **Moot given §5:** with §5 = KILL, T6.3 forbids presenting these speed/HBM numbers
  as a contribution at all. They are recorded as engineering measurements only.

**Net:** the win is **memory traffic at long context**, not raw speed. The case is
for bandwidth-bound / very-long-context regimes; turning the HBM saving into time
requires fusing the bias deeper into the FlashAttention loop.

## §5 — Quality gate: **KILL (negative result)** (final, real WikiText-2)

The decisive test, done the only honest way — **train small GPTs from scratch**,
identical arch/data/compute, one per scheme — on real WikiText-2
(`Salesforce/wikitext`), byte-level. Validation perplexity at the training context
(512) and at 2×/4× extrapolation:

| scheme | @512 (train) | @1024 (2×) | @2048 (4×) |
|---|---|---|---|
| **learned-absolute** | **4.22** | 12.10 | 20.82 |
| ALiBi | 10.74 | 11.73 | 11.35 |
| **sliding-window** | **4.99** | **5.07** | **5.03** |
| CY-Sieve τ-ladder | 11.33 | 12.31 | 12.05 |
| CY-Sieve τ=20 | 16.02 | 16.81 | 16.49 |
| CY-Sieve τ=128 | 6.80 | 7.12 | 7.00 |
| CY-Sieve τ=512 | 4.65 | 6.08 | 10.62 |

**Verdict: KILL.** Best baseline (learned-absolute) = 4.22; best CY-Sieve (τ=512) =
4.65 → **+10.15%**, well past the >5% kill threshold. CY-Sieve as designed does not
meet the quality bar.

**Honest reading:**
- **The "great extrapolation" seen earlier was an artifact** of the
  trivially-memorized synthetic corpus (ppl≈1.0 everywhere — a bug, since fixed).
  On real text the picture inverts.
- **Sliding-window is the clear winner here** — 4.99 essentially flat across
  512→2048 (best extrapolation *and* near-best train ppl). A plain local window
  beats every CY-Sieve variant.
- **CY-Sieve exposes a real tension:** the geometry-fixed steep decay
  (log λ=3.762) is too aggressive — no single τ gives *both* good absolute quality
  and stable extrapolation. τ=512 is best at the train context but degrades
  4.65→10.62 at 4×; τ=128 is stable but +61% worse than the baseline; the τ-ladder
  meant to resolve this lands at ~11–12 (poor on both axes).
- This is a **genuine negative result for the positional scheme**, reported per the
  project's own rules. The HBM advantage (§6) is real but irrelevant if quality
  fails — a fast kernel that hurts the model is a failed kernel.

**What this does NOT kill:** §4 correctness and the §6 O(L)-vs-O(L²) HBM property
stand on their own. The negative is specifically about *this bias function* as a
drop-in positional scheme. See "Improvement directions" below.

## Improvement directions (post-KILL)

The kill is informative, not terminal — it points at specific, testable fixes:
1. **Decouple the slope from the geometry.** logλ=3.762 is the *growth rate of
   S₂₀*, but there's no law that the best *attention* slope equals it. Treat the
   per-head slope as a learnable/tunable parameter initialized from the geometry,
   à la learnable-ALiBi — the geometry sets the prior, not the value.
2. **Hybrid with a local window.** Sliding-window won; combine an exact local
   window (Tier 1, which CY-Sieve already has) with a *much gentler* long-range
   tail, instead of one steep curve everywhere.
3. **Re-examine the β=2 log-curvature** contribution separately from the linear
   slope — ablate whether the log term helps or hurts at these lengths.
4. **Only then** is the O(L) HBM advantage worth re-claiming — and only if a
   redesigned bias clears the +5% gate.

---

## Reproducibility

```bash
pip install -r 4_ai_hardware_attention/requirements-gpu.txt
python 4_ai_hardware_attention/run_gpu_phase.py     # §4 + §5 + §6 → one JSON
```
On GCP the same is driven unattended by `4_ai_hardware_attention/gcp_startup.sh`
(an L4 that clones, runs, uploads to GCS, and self-terminates).
