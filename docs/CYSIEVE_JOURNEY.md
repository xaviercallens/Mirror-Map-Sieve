# The CY-Sieve attention journey — a case study in honest applied research

This documents the full arc of the applied "CY-Sieve" attention experiment, end to
end, because the *method* is the achievement as much as any number. It is a worked
example of falsification discipline: a bold hypothesis, a pre-committed kill
criterion, a near-miss false positive caught, a real result confirmed at scale, and
an attribution experiment that corrected our own narrative. Nothing here is the
project's core (that is the Calabi–Yau mathematics); this is the honest record of an
engineering side-quest the geometry inspired.

## The hypothesis

Modern accelerators are memory-bandwidth bound. A positional-attention bias whose
values are *generated on the fly* from the proved order-4 holonomic recurrence of
$S_{20}(n)=\sum_k\binom nk^4\binom{n+k}k$ would cost $\mathcal{O}(L)$ memory instead
of an $\mathcal{O}(L^2)$ table — *if* it preserves model quality. We set a
pre-committed quality gate (`tests.md` §5): PASS within +1% of the best baseline,
KILL at >5% regression.

## The arc (chronological, all on real WikiText-2, trained from scratch)

| stage | result | what we learned |
|---|---|---|
| **§4 kernel parity** | PASS (4/4, FP16) | the Triton kernel is numerically correct |
| **§6 memory** | $\mathcal{O}(L)$ vs $\mathcal{O}(L^2)$, 8192×@16K | the bias-HBM claim is real **vs a stored table** |
| **§5 quality v1 (fixed bias)** | **KILL +10.15%** | the geometry-fixed slope ($\log\lambda{=}3.762$) is too steep; a sliding window won |
| **autoresearch screen** (1200 steps) | learnable-γ **beat baselines** (5.89 vs 6.15) | making the slope **learnable** flips the result |
| **autoresearch full v1** (6000 steps) | **inverted → KILL** (12.7 vs 4.3) | overfitting: ~37 epochs/2 MB; γ ran *steeper*, not flatter |
| **autoresearch full v2** (regularized) | **PASS +8.1%** (3.32 vs 3.62) | γ-L2 + val early-stop + bigger corpus fix it; the gain is real at scale |
| **attribution** (nested $-a d + b\log d$) | gain is **learnability, not CY** | learnable-ALiBi (+3.8%) > fixed-CY (+2%); free curvature $b\to$ **negative**, away from the CY $\beta{=}2$ |

## What we can honestly claim

1. **A real, reproducible quality result.** A *learnable* per-head positional bias
   beats fixed ALiBi by **~4–8%** perplexity on WikiText-2 (from scratch), with
   **stable length-extrapolation** where learned-absolute positions collapse. This
   PASSES the pre-committed gate at GPU scale.

2. **The source is learnability, not the Calabi–Yau geometry.** A controlled,
   nested-parameterization experiment shows a plain learnable-ALiBi slope (zero CY
   content) already beats the fixed holonomic bias, and that when the log-curvature
   is made free the model moves it *away* from the CY value $\beta=2$. The geometry
   was an inspiring prior; it does not earn its place in the final bias. We renamed
   the shipped scheme accordingly and dropped the $S_{20}$/recurrence machinery.

3. **No memory win over real SOTA.** Against a materialized bias table the
   $\mathcal{O}(L)$ generation saves 8192×; against **FlashAttention+ALiBi (which
   already generates its bias on the fly)** the saving is ~0. A learnable per-head
   scalar bias is $\mathcal{O}(1)$ state, identical to ALiBi. We do **not** claim a
   memory breakthrough.

## What we explicitly do NOT claim

- Not "Calabi–Yau geometry improves attention" — the attribution refutes it.
- Not "infinite extrapolation / zero degradation / LPU dominance" — earlier such
  phrasings are retracted (they came from an invalid frozen-model method).
- Not a memory contribution beyond a stored-table strawman.

## The achievement, stated plainly

> A disciplined, falsifiable applied-research loop that took a bold geometric
> hypothesis from KILL, through a caught overfitting false-positive, to a confirmed
> +8% quality result at GPU scale — and then used a controlled attribution
> experiment to correct its own story, concluding that the win is from
> **learnable per-head positional bias** (a known-good idea, modestly improved),
> not the Calabi–Yau structure. The negative and null results are reported as
> prominently as the positive one.

Honest, modest, reproducible — and we would value expert review of the attribution
methodology and a fair comparison against learnable-ALiBi / NoPE / RoPE-scaling on
a real long-range benchmark.

— Artifacts: `docs/PHASE3_CYSIEVE_GPU_FINDINGS.md` (gate), `PHASE4_HC_ATTRIBUTION.md`
(attribution), `CYSIEVE_FUTURE_DIRECTIONS.md` (memory analysis),
`4_ai_hardware_attention/gpu_phase_runs/` (raw runs), and the
[HF benchmark dataset](https://huggingface.co/datasets/callensxavier/cy-sieve-attention-benchmark).
