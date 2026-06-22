# CY-Sieve autoresearch — 10 hypotheses to overturn the §5 KILL

The §5 gate killed the fixed CY-Sieve bias: its geometry-fixed slope
$\log\lambda=3.762$ is a brick wall that blinds the model past ~6 tokens, and a
plain sliding window beat it (4.99 ppl). These 10 hypotheses bridge the
mathematical rigidity (the O(L) recurrence-generated shape) to linguistic
flexibility, anchored on two ideas:

- **Direction A — Holonomic-ALiBi (learnable γ):** keep the pristine $S_{20}$ curve
  *shape* but decouple the slope: $\text{bias}_h(d) = -\gamma_h\,\log S_{20}(d)$ with
  $\gamma_h$ a **learnable per-head scalar**. Gradient descent flattens the
  Calabi–Yau wall to whatever steepness each head needs; O(L) generation preserved.
- **Direction B — Comet attention (dense local + CY tail):** exact unpenalized
  attention for $d\le W$ (grammar), then a cheap CY decay
  $-\gamma_h\log S_{20}(d-W)$ for $d>W$ (graceful, not black, deep past).

| # | name | shape | γ | notes |
|---|------|-------|---|-------|
| H1 | `holo_ladder` | pure $-\log S_{20}(d)$ | learnable, init = ALiBi τ-ladder | Direction A, principled init |
| H2 | `holo_tiny` | pure | learnable, init γ=0.02 (uniform) | A — start nearly flat, let GD steepen |
| H3 | `comet512_fixed` | comet W=512 | fixed γ=1/128 | B alone (no learning) — isolates the window |
| H4 | `comet512_learn` | comet W=512 | learnable, init 1/128 | **A×B combined — the headline bet** |
| H5 | `comet256_learn` | comet W=256 | learnable | B, smaller window |
| H6 | `comet1024_learn` | comet W=1024 | learnable | B, larger window |
| H7 | `holo_curv` | curvature-only $-\beta\log d$ (no linear slope) | learnable, ladder | ablate: does the β=2 log-curvature alone help? |
| H8 | `comet_perhead_W` | per-head windows {64,128,256,512,1024,…} | learnable | B, multi-scale local windows |
| H9 | `holo_ladder_pos` | pure | learnable, init ladder, **clamped γ≥0** | A — forbid sign flip (keep it a decay) |
| H10 | `comet512_soft` | comet W=512 with linear ramp 384→512 | learnable | B — smooth onset, no hard cliff at 513 |

**Baselines re-trained in the same sweep:** `learned-absolute`, `alibi`,
`sliding-window` (the run-3 winner) — so rankings are directly comparable.

**Protocol (autoresearch, Karpathy-style propose→screen→select):**
1. **Screen** all 13 schemes at reduced budget (≈1200 steps, ctx 512) on one L4.
2. **Select** the top-3 CY variants by val perplexity @train context (tie-break on
   2×/4× extrapolation).
3. **Full run** the top-3 + key baselines at full budget (6000 steps); emit the
   verdict vs the best baseline (PASS within +1%, KILL if >5%).

All learnable schemes keep the **O(L) bias-generation** property — γ is just H
scalars; the shape is still the recurrence-generated vector.

---

## Screen-phase results (2026-06-22, NVIDIA L4, 1200 steps, real WikiText-2)

| rank | scheme | ppl@512 | note |
|---|---|---|---|
| 1 | **holo_ladder** | **5.89** | learnable-γ Holonomic-ALiBi — **beats every baseline** |
| 2 | holo_ladder_pos | 5.96 | γ clamped ≥0 |
| 3 | alibi (baseline) | 6.15 | best baseline |
| 4 | holo_tiny | 6.99 | learnable-γ, flat init |
| 5 | holo_curv | 11.33 | β-curvature only — weak |
| 6–12 | comet_* | 11.7–12.4 | Direction B underperformed at this budget |
| — | learned / sliding | 12.24 / 12.54 | baselines |

**Key finding: Direction A (learnable per-head γ) works** — the top two schemes
beat the best baseline (ALiBi 6.15) at screen scale, overturning the fixed-bias
KILL *at this budget*. Decoupling the slope from the sequence (γ learnable,
geometry fixes only the shape) is the decisive change, and O(L) generation is
preserved. **Direction B (Comet) disappointed here** — likely too few steps for
the learnable tail to find signal; revisit at longer context.

**Selected top-3 for the full 6000-step run:** `holo_ladder`, `holo_ladder_pos`,
`holo_tiny` (vs `learned` + `sliding`).

## Full-run results (2026-06-22, 6000 steps, d_model=512/L=8) — the screen REVERSED

| scheme | train loss | **val ppl@512** | @1024 | @2048 |
|---|---|---|---|---|
| **learned** (baseline) | 1.17 | **4.28** | 12.16 | 20.63 |
| **sliding** (baseline) | 1.31 | **4.62** | 8.66 | 13.03 |
| holo_ladder_pos | 0.42 | 12.72 | 13.55 | 13.30 |
| holo_tiny | 0.47 | 13.64 | 14.35 | 14.07 |
| holo_ladder | 0.42 | 13.90 | 14.96 | 14.88 |

**Verdict: still KILL** — best CY (holo_ladder_pos 12.72) vs best baseline (learned
4.28) is **+197%**, far past the 5% threshold.

**Diagnosis — overfitting confound, NOT a clean refutation.** The holonomic schemes
drove train loss **3× lower** (0.42 vs 1.17) but val **3× worse** — a textbook
overfitting signature. The setup over-trains: 6000×24×512 ≈ **74 M tokens over a
2 MB corpus ≈ 37 epochs**. The expressive learnable bias memorized the train text
hardest; at the 1200-step screen (before overfitting) the same scheme *beat* the
baselines (5.89 vs 6.15). Also telling: γ drifted **up** (max 0.13→0.21, steeper),
the opposite of the intended flattening — with no regularization it used a sharp
bias to memorize.

**One signal survives:** the holonomic schemes **extrapolate flat** (holo_ladder_pos
12.7→13.3 over 512→2048) while `learned` collapses (4.3→20.6). The CY shape gives
stable length-extrapolation; it's just uniformly mediocre at this (over-trained)
budget.

**Honest status: UNCONFIRMED, not refuted.** Right next steps before re-judging:
(1) more data / far fewer epochs (or a held-out early-stop on val); (2) **regularize
γ** (weight-decay / cap growth — it ran steeper, not flatter); (3) re-screen at a
budget that doesn't over-train. The screen→full inversion is itself the lesson:
expressive positional biases need a generalization budget, not just a fit budget.
