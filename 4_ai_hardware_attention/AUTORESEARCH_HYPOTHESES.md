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
