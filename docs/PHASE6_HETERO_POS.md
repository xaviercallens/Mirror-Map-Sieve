# Phase 6 — heterogeneous positional bias: content–position balance ties, the temperature knob hurts

A final orthogonal probe (2026-06-23) closes the applied attention arc by testing
the *only* axis the earlier bake-offs had not: per-head **content↔position
balance**. The verdict re-confirms the Phase-5 selection — **learnable-ALiBi (one
learnable linear slope per head, nothing else) is the hypothesis to ship.**

## Why this experiment

The GPU bake-off winner, learnable-ALiBi, learned per-head slopes spanning ~125×
(0.68 → 0.005), with the flattest heads going essentially NoPE-like. So its +8%
was never "a better distance curve" — it was the model **self-organizing into
sharp-local heads plus near-global content-only heads**. Every variant that added
more *distance shape* (Calabi–Yau curve, log-curvature, Fourier features) overfit
and lost at scale. The untried, orthogonal axis is to make that local↔global
mixture **explicit**: give each head a learnable content scale `c_h` so it can
choose how much weight the content score `q·k` carries relative to the positional
penalty `−a_h·d`:

```
score_h(i,j) = c_h · (q_i · k_j)/√D  −  a_h · (i − j)        [content_balance]
```

**Hypothesis:** making the local↔NoPE mixture explicit (learnable slope `a_h`
*and* learnable content scale `c_h`) should modestly improve perplexity and — the
real prize — improve **length extrapolation**, without the overfit that killed
"more shape". A per-head softmax temperature `τ_h` was added as an extra-knob
ablation. **Pre-committed KILL:** if `content_balance` gives no extrapolation gain
over `alibi_learn`.

Schemes: `alibi_fixed` (baseline), `alibi_learn` (the bake-off winner / control),
`nope` (content-only sanity), `content_balance` (the hypothesis), `cb_softmax_temp`
(content_balance + per-head temperature).

## GPU result (NVIDIA L4, 2026-06-23, full preset)

Trained from scratch on real WikiText-2 (`Salesforce/wikitext`, wikitext-2-raw-v1),
d_model 512 / 8 layers / 8 heads, ctx 512, 4000 steps, batch 24, γ-L2 1e-3, val
early-stop. **Primary metric: validation perplexity at 1×/2×/4×/8× the training
context (length extrapolation; lower is better).**

| mode | 1× (512) | 2× (1024) | 4× (2048) | 8× (4096) |
|---|---|---|---|---|
| `alibi_fixed` | 3.705 | 3.623 | 3.577 | 3.513 |
| **`alibi_learn`** (control / winner) | 3.651 | 3.559 | 3.500 | 3.429 |
| `nope` | 10.290 | 10.845 | 11.571 | 12.311 |
| **`content_balance`** (hypothesis) | 3.642 | 3.548 | **3.488** | **3.428** |
| `cb_softmax_temp` (+ temperature) | 3.732 | 3.659 | 3.599 | 3.548 |

`content_balance` vs `alibi_learn` @4×: **+0.35%** (and +0.17% @8×).

## Verdict — KILL the extra knobs; learnable-ALiBi stands

1. **`content_balance` ties `alibi_learn` within noise** (+0.35% @4×, +0.17% @8×).
   The learnable content scales settled near 1.0 with a mild upward drift toward
   the flatter/global heads (`c` ≈ 0.79 → 0.93 across the slope-ordered heads) —
   the model *does* want global heads to lean a little more on content, but the
   effect is marginal and does not clear a meaningful margin. **KILL per the
   pre-committed criterion** (no extrapolation gain over `alibi_learn`).
2. **The softmax-temperature knob *regresses*** — `cb_softmax_temp` is worse than
   plain `alibi_learn` at every length (3.732 vs 3.651 @1×). This is the recurring
   Phase-4/5 pattern once more: **extra parameters hurt at scale.** Notably the
   *local* screen (d128/L3, 800 steps) had crowned `cb_softmax_temp` the best
   scheme — another instance of a short, small screen rewarding the highest-capacity
   variant that then loses when properly trained.
3. **`nope` collapses and gets *worse* with length** (10.3 → 12.3), the expected
   sanity check that the positional penalty is doing real work.

## What this adds to the arc

Phase 6 was the last orthogonal axis left to try — not *more distance shape*
(Phases 4–5 closed that), but *content/position mixing*. It lands in the same
place: **adaptability beats added structure, but only up to the single learnable
slope.** Once each head can pick its own slope, an explicit content-balance knob is
redundant (the model already realizes the local↔global split through the slope
alone) and a temperature knob is actively harmful.

> **Selected hypothesis (final):** a **learnable per-head linear positional bias**
> (learnable-ALiBi) — one slope per head, no log-curvature, no Calabi–Yau sequence,
> no content scale, no temperature. It is the robust GPU-scale winner across every
> bake-off (Phases 4, 5, 6), passes the §5 gate at +8.1% over the best baseline,
> and extrapolates flat where learned-absolute positions collapse.

Artifacts: `4_ai_hardware_attention/cy_sieve_hetero_pos.py` (experiment),
`gpu_phase_runs/hetero_pos_gpu_20260623.json` + `.log` (GPU run),
`gpu_phase_runs/hetero_pos_local_20260623.json` (local screen). See also
`PHASE5_FINAL_BAKEOFF.md` and `CYSIEVE_JOURNEY.md`.
