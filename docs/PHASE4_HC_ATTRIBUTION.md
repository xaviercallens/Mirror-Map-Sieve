# Phase 4 — H-C refinement & attribution: the gain is *learnability*, not Calabi–Yau

After the autoresearch sweep found that a **learnable per-head γ** "Holonomic-ALiBi"
bias beats baselines, we asked the question that decides what we actually learned:
**is the gain from the Calabi–Yau curve shape, or just from making the slope
learnable?** Two runs answer it (2026-06-22).

## Result 1 — v2 GPU full run confirms the gain is REAL and holds at scale (PASS)

Regularized (γ-L2 + val early-stop + 8M-char corpus), 8000 steps, real WikiText-2:

| scheme | val ppl@512 |
|---|---|
| **holo_ladder_pos** | **3.324** |
| holo_ladder | 3.336 |
| holo_tiny | 3.576 |
| learned (baseline) | 3.617 |
| sliding (baseline) | 3.702 |

holo_ladder_pos vs best baseline = **+8.1%**. The v1 overfitting inversion is gone;
the learnable Holonomic bias genuinely beats the baselines at scale. **The original
§5 KILL is overturned — this configuration PASSES.**

## Result 2 — attribution (local, controlled): it's LEARNABILITY, not the CY shape

A nested bias $\text{bias}_h(d) = -a_h\,d + b_h\log d$ ($a,b$ learnable per head)
lets us separate the linear slope from the log-curvature, with controls:

| scheme | ppl@512 | vs fixed ALiBi | isolates |
|---|---|---|---|
| **nested_curv0** | **8.548** | **+6.9%** | learnable slope + free log-curvature (linear init) |
| nested_free | 8.680 | +5.5% | learnable slope + free curvature (CY init) |
| **alibi_learn** | 8.835 | **+3.8%** | learnable slope, **no curvature** (control) |
| holo_fixed | 8.998 | +2.0% | fixed CY shape (the autoresearch "winner") |
| log_only | 8.998 | +2.0% | fixed CY shape (exact tiered) |
| alibi (fixed) | 9.181 | — | baseline |

**Three conclusions, stated plainly:**

1. **Learnability is the driver, not the geometry.** A plain *learnable* ALiBi slope
   with zero Calabi–Yau content (`alibi_learn`, +3.8%) beats the fixed holonomic
   bias (`holo_fixed`, +2.0%). The headline "CY-Sieve beats ALiBi" was really
   "learnable beats fixed."

2. **Given freedom, the model moves AWAY from the CY curvature.** `nested_free`
   starts at the Calabi–Yau prior (log-curvature $b=\beta=2$ per unit slope) and
   gradient descent drives $b$ **negative** ($b\approx-0.2$). The $\beta=2$
   curvature is not what the data wants — the geometry was a prior, and not a
   well-pointed one.

3. **The actual best bias drops the holonomic sequence entirely.** `nested_curv0`
   (+6.9%) — a learnable linear slope plus a small *learned* log-correction — wins,
   and needs no $S_{20}$, no recurrence, no Calabi–Yau structure. It is essentially
   **learnable-ALiBi + a learnable log term**.

## Honest consolidation — what H-C actually is

- **A real, modest quality win exists** (+6.9% local / +8.1% at GPU scale vs
  baselines) and it is **shippable** — but its source is *parameterizing the
  positional slope (and a log term) as learnable per-head*, a known-good idea in the
  ALiBi/learnable-bias family. The Calabi–Yau sequence is **not** the source and is
  best dropped.
- **No memory win** (see `CYSIEVE_FUTURE_DIRECTIONS.md`): a learnable per-head
  scalar bias is O(1) state and O(L) to apply — same as ALiBi — so there is nothing
  to save over FlashAttention+ALiBi.
- **The most defensible contribution** from this whole applied arc is therefore a
  small, honest one: *a learnable per-head linear+log positional bias that edges
  ALiBi by a few %, with stable length-extrapolation.* We will not attach the
  Calabi–Yau story to it, because the controlled experiment says the geometry does
  not earn its place.

## What to ship / next

- **Ship `nested_curv0` (learnable slope + learnable log term)** as the positional
  scheme, named for what it is (not "CY-Sieve"). Re-run it at GPU scale alongside
  learnable-ALiBi to confirm the local ranking.
- The Calabi–Yau mathematics remains the project's real contribution; the attention
  kernel is, honestly, *a learnable-bias result that the geometry inspired but does
  not explain*.
