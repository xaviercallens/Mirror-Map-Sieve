# Mirror Map Sieve — Vision

## What This Project Is

A rigorous, reproducible computational mathematics laboratory that:
1. Discovered a **genuinely new** integer sequence $S(n) = \sum_{k=0}^n \binom{n}{k}^4 \binom{n+k}{k}$
2. Proved it satisfies a minimal **order-4**, degree-13 holonomic recurrence — now established for all $n$ by a creative-telescoping certificate (Phase 1)
3. Showed its mirror map coefficients are integers (Lian-Yau integrality, exact rational arithmetic, d ≤ 16)
4. Provided sorry-free Lean 4 kernel verification of base cases and sequence values
5. Published all artifacts under a citable DOI (Zenodo 10.5281/zenodo.20747943)

## Applied direction: the CY-Sieve attention kernel (a falsifiable engineering bet)

> **Honest stance.** This is an *engineering hypothesis*, not a proven win, and
> not the project's core contribution (that is the mathematics). We pursue it
> because it is close to our actual expertise — a human number-theorist
> (X. Callens) and an LLM coding assistant (Claude) — and because the holonomic
> structure of $S_{20}$ maps cleanly onto a real hardware bottleneck. We commit
> to **killing any tier that fails its quality gate** (see `tests.md`).

**The one defensible core idea.** Modern accelerators are bound by **memory
bandwidth**, not integer ALU compute. A positional-bias scheme whose values are
generated *on the fly* from a short linear recurrence costs **zero HBM** for a
bias table — that is a genuine, measurable advantage *if and only if* model
quality is preserved. $S_{20}$ obeys a proved order-4 holonomic recurrence
(see `docs/PHASE1_FINDINGS.md`), so it is exactly such a sequence.

**What we verified before planning (numbers, not assertions — see `tests.md`):**
- **INT64 limit is real.** $S_{20}(d)$ overflows signed INT64 at **$d=14$**
  (safe through $d=13$); the slower sibling $S_{15}(n)=\sum_k\binom nk^3\binom{n+k}k$
  is safe through **$d=16$**. The proposal's $d\le13$ window is correct.
- **The mod-$p$ "sparse router" fails as proposed.** With $p=251$, only
  **0.8%** of distances satisfy $S_{20}(d)\equiv0$, and the nearest kept distance
  is **226** — a token would attend to *nothing* between $d=14$ and $d=226$.
  As a keep-rule this destroys local context. We therefore treat Tier 2 as a
  **research question, not a feature** (it needs a different rule, e.g. residue
  *classes* or a much smaller modulus, and must beat a sliding-window baseline).
- **The asymptotic tier is sound but the proposal's constants are wrong.** The
  growth constant is $\lambda\approx43.044$ (so $\log\lambda\approx3.762$, **not**
  the proposal's $2.456$). The sub-exponential exponent fits $\beta\approx1.99$,
  i.e. **$\beta=2$** — which is exactly the $n^{-2}$ tail predicted by the
  **rank-4 MUM Calabi–Yau-3-fold** structure found in Phase 2. *This is the real
  conceptual payoff:* the long-range log-space penalty
  $-d\log\lambda+2\log d-\log C$ is not a heuristic — its exponent is dictated by
  the geometry.

**The CY-Sieve architecture (corrected, three tiers):**
1. **Tier 1 — exact INT64 local anchor ($d\le13$, or $\le16$ for $S_{15}$):**
   preloaded exact reciprocal-decay table in L1/registers; zero float drift,
   zero HBM. This is the solid, shippable piece.
2. **Tier 2 — mid-range routing (research, currently failing):** a finite-field
   rule from the holonomic recurrence mod a small modulus. Must be redesigned
   and must beat sliding-window/local attention on quality before it ships.
3. **Tier 3 — asymptotic log-space penalty ($d>$ window), with a temperature
   $\tau$:** the BF16/FP8 FMA $\tfrac1\tau(-d\log\lambda+\beta\log d)$ with
   $\lambda=43.044$, $\beta=2$ — a geometry-fixed blend of ALiBi (linear) and log
   penalties. **The $\tau$ is not optional.** Applied raw ($\tau=1$) the slope
   $\log\lambda=3.762$ is so steep that $\exp(\text{penalty})$ underflows FP16 to
   $0$ by $d\approx6$ — it would collapse the model into a $\sim$6-token sliding
   window and destroy long-range retrieval (it might still pass a perplexity gate
   on local n-grams, which is exactly the trap). The fix is a per-head
   temperature ($\tau_h=\log\lambda/m_h$ matched to ALiBi slopes $m_h$), i.e. the
   bias of $S(d)^{1/\tau}$: it preserves the linear slope and the $\beta=2$
   curvature while compressing the decay into a survivable, multi-scale range
   (steep heads ≈ local syntax, shallow heads reach $>1000$ tokens). Cheap,
   HBM-free, and tested (`tests.md` §3T).

**Strategic claims we deliberately downgrade to hypotheses:** "zero-parameter MoE
routing", "infinite extrapolation with zero degradation", and LPU-specific
dominance are *speculative* until a perplexity/accuracy benchmark says otherwise.
We will not repeat them as facts.

**The decisive test, now running (2026-06-21, NVIDIA L4).** The GPU phase
(`run_gpu_phase.py`: `tests.md` §4 parity → §5 quality → §6 perf) is executing.
§4 (Triton↔reference FP16 parity) **passed**. §5 is the gate that decides
everything, and we run it the only honest way: **train small GPTs from scratch**,
identical architecture/data/compute, one per positional scheme (learned-absolute,
ALiBi, sliding-window, CY-Sieve per-head τ-ladder + a single-τ sweep), then compare
validation perplexity at the training context **and** at 2×/4× length
extrapolation. (We explicitly rejected zero-shot-swapping the scheme into a frozen
model — it collapses every scheme equally and measures train/test mismatch, not the
bias.)

> **Anticipated improvement (a hypothesis we are about to confirm or kill).** If the
> geometry-fixed bias — slope $\log\lambda=3.762$, curvature $\beta=2$ from the
> rank-4 MUM Calabi–Yau-3-fold tail, spread across heads by the τ-ladder — carries
> real positional signal, we expect CY-Sieve to sit **within +1% of the best
> baseline's perplexity** with **no worse length extrapolation**. Combined with
> §6's structural advantage — the bias path reads **O(L)** values generated on the
> fly versus **O(L²)** for a materialized bias table — that is the entire case for
> the kernel: *equal quality, strictly less bias-memory traffic.* **We commit in
> advance to the kill criterion: a >5% perplexity regression vs the best baseline,
> or an extrapolation collapse, is reported as a negative result and the tier is
> not shipped.** No verdict is asserted until the L4 run completes and the numbers
> are in `gs://gen-lang-client-0625573011-cy-sieve-bench/cy_sieve/`.

### Mathematical depth (the actual core)
- **Prove the supercongruences** — these are the highest-impact open problems in this project
- **Submit to OEIS** — the sequence needs an A-number to become a permanent part of mathematics
- **Find the diagonal representation** — this is the deepest open problem (Christol guarantees existence; finding it is research)

### Phase 4: Community Recognition
- **arXiv submission** with proper cross-listings (math.AG, math.NT, cs.SC)
- **Submit to NeurIPS 2026** — "Holonomic INT64 Attention: Bypassing SoftMax with Exact Calabi-Yau Geometries"
- **Submit to a journal** — Experimental Mathematics or Journal of Number Theory are the natural targets

### What This Project Should NOT Be
- ❌ A branding exercise (self-eponymy undermines scientific credibility)
- ❌ A claim of formal proof for something only computationally verified at finite points

## Guiding Principles
1. **Understate rather than overstate.** Let the mathematics speak for itself.
2. **Reproducibility is non-negotiable.** Every claim must be verifiable by running code.
3. **Separate speculation from proof.** Conjectures are clearly labeled. Verified results are clearly stated.
4. **Standard mathematical practice.** OEIS submission, arXiv, peer-reviewed journal. No shortcuts.
