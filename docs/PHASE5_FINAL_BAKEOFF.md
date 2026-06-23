# Phase 5 — final bake-off: learnable-ALiBi wins; exact QK needs an exact softmax

Two autoresearch experiments (2026-06-23) close the applied attention arc with
clear, partly humbling, answers.

## A. Positional-bias family bake-off — GPU head-to-head is decisive

We tested learnable bias families and, critically, re-ran the leading candidates
**at GPU scale** (4000 steps, 16M-char WikiText-2, d512/L8, val early-stop). The
GPU result **overturns the small-scale local screen**:

| scheme (GPU, ppl@512) | result | vs winner |
|---|---|---|
| **alibi\_learn** (learnable slope, *no* log term) | **3.617** | — winner |
| holo\_fixed (fixed CY shape) | 3.647 | −0.8% |
| nested\_free (slope + free log-curvature) | 3.662 | −1.3% |
| alibi (fixed slopes) | 3.697 | −2.2% |
| nested\_curv0 (slope + learnable log) | 3.718 | −2.8% |
| learned\_pos (learned absolute) | 4.859 | −34% |

Local 800-step screen (for contrast): fourier +7.1%, linlog/nested\_curv0 +6.9%,
alibi\_learn +3.8%, hybrid −29%. **The small-scale leads came from extra
parameters and do not survive scale** — at GPU scale the plainest scheme wins and
the log/curvature term *hurts*.

**Conclusions (now firmly established):**
1. **The winner is learnable-ALiBi: one learnable linear slope per head, no log
   term, no sequence.** It matches the +8% PASS we reported and is the honest
   final form.
2. **Extra expressiveness does not help at scale.** The log-curvature, the
   Calabi–Yau shape, and Fourier features all either fail to beat, or lose to, a
   single learnable slope once the model is properly trained. `nested_free`'s
   learned curvature goes **strongly negative** (b ≈ −0.5…−0.85), i.e. the optimizer
   actively pushes *away* from the positive CY curvature.
3. **`exp_decay` ≡ `alibi_learn` exactly** — confirming "exponential decay
   $e^{-\lambda d}$" is just a learnable linear slope in additive log-space.
4. **`hybrid` (local window + tail) failed** as implemented (soft-gate degenerate);
   not pursued.

> Net: *adaptability beats elegance* — exactly the S20 lesson, now quantified. The
> shippable scheme is learnable per-head ALiBi; everything fancier is removed.

## B. Exact-attention kernel — Rescaled-Integer wins; the softmax is the bottleneck

Numerical fidelity vs an FP64 reference (CPU proxy of a Triton kernel), max
relative error:

| scheme | L=128 | L=512 | L=2048 |
|---|---|---|---|
| fp32 | 1.8e-07 | 2.0e-07 | 3.1e-07 |
| **rescaled\_int** (exact INT64 $QK^\top$ + FP softmax) | 1.4e-05 | 1.5e-05 | **1.6e-05** |
| mixed (INT $QK$ + FP16 softmax) | 3.2e-04 | 2.4e-04 | 3.1e-04 |
| fp16 (baseline) | 2.9e-04 | 2.4e-04 | 5.3e-04 |

**Conclusions:**
1. **Rescaled-Integer is the accuracy winner — ~34× more exact than FP16** at
   L=2048 (1.6e-05 vs 5.3e-04), and its error stays **flat in $L$** (integer
   accumulation carries no rounding; only input quantization remains). FP16's error
   grows with context — exactly where exactness matters.
2. **Mixed precision (★★★★★ on paper) under-delivers (~1.7× over FP16):** the
   exact integer $QK^\top$ is wasted because the **FP16 softmax + FP16 $V$ matmul
   re-introduce the error**. The bottleneck is the softmax, not the dot-product.
3. **Therefore the real near-term target is "exact $QK^\top$ + a higher-precision
   (FP32) softmax,"** not INT-QK-plus-FP16-softmax. Pure INT64/INT128 end-to-end is
   feasible for research but the softmax/exp is the hard part.

## Recommended retry — leverage both findings (and pivot off S20)

A single combined experiment that benchmarks the *winners*, with the same
train-from-scratch §5 protocol used for S20:

- **Bias:** ship and benchmark **learnable-ALiBi** (the winner) as the default;
  keep `nested_free` only as an attribution control. Drop CY/log/Fourier/hybrid.
- **Kernel:** implement **rescaled-INT $QK^\top$ + FP32 softmax** in Triton and
  measure quality (does exactness change perplexity?) and latency vs FP16 SDPA.
- **Sequence pivot:** the holonomic sequence is no longer in the bias at all, so
  S20's role here is finished. If a future variant wants a *fixed* shape, prefer a
  **slower-growing, lower-order member** (e.g. the (3,1)/(2,1) Apéry-like siblings
  with proven modularity) — but the evidence says a learnable slope makes the
  choice moot.

> The headline of the whole applied arc: a learnable per-head linear positional
> bias (a known-good idea) is the robust winner; exact integer $QK^\top$ is a real
> accuracy lever bottlenecked by the softmax. Neither result needs the Calabi–Yau
> sequence — its value was as the inspiration that led us to run the experiments.
