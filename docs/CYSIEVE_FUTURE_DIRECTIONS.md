# CY-Sieve — where the real memory win could be (deep dive)

A strategic analysis after the GPU-phase arc (KILL → overfit false-negative →
provisional ~2% over ALiBi with learnable γ). Written while the v2 full run trains.
**Goal: be honest about where the genuine leverage is, not where it is convenient.**

## 0. The reframe we must lead with (or we fool ourselves)

Our headline — "$\mathcal{O}(L)$ bias vs $\mathcal{O}(L^2)$ table, 8192×" — is
measured against a **materialized $[L,L]$ bias table that no competent system uses.**
The real baseline, **FlashAttention + ALiBi**, already computes its bias on the fly
(`-m·(i-j)`, a couple of FMAs) and stores **zero** $\mathcal{O}(L^2)$ bytes. So:

- Against the *true* SOTA, our **positional-bias memory advantage ≈ 0.**
- Worse: the holonomic *recurrence* is over-engineering for the bias — beyond the
  exact $d\le13$ window the bias is the closed form $-\gamma(d\log\lambda-\beta\log d)$,
  pure FMAs, no recurrence needed. The recurrence only earns its keep if the thing
  being generated is **not expressible in closed form** and is **large**.

**Therefore the on-the-fly $\mathcal{O}(L)$-generation idea is only valuable if we
point it at a memory target far bigger than the positional bias.** The two biggest
memory consumers in LLM inference/training are: (1) the **KV cache** (grows with
context, dominates long-context serving), and (2) **optimizer state / weights**
(training). Everything below is judged by whether it attacks one of those.

---

## The hypothesis portfolio

### H-A. Holonomic KV-cache eviction / compression schedule
**Idea.** Use the holonomic decay $S_{20}(d)$ (or a learned-γ variant) not as an
attention *bias* but as a **deterministic, parameter-free schedule for which KV
entries to keep at full precision vs evict/quantize** as they age. The recurrence
generates the keep/decay weight for token at distance $d$ on the fly in SRAM — no
stored importance table.
**Pro:** attacks the KV cache, the *actual* long-context memory wall (10s of GB at
128k). A principled, monotone, cheap-to-generate decay is exactly what streaming /
H2O-style eviction needs. O(L) generation is genuinely useful here (the schedule is
per-position and unbounded). Composes with any attention kernel.
**Con:** KV eviction quality is dominated by *content* (attention mass), not pure
*distance* — pure-distance schedules (StreamingLLM's "attention sink + recent
window") are already strong and hard to beat with a fixed curve. Risk of
reinventing sliding-window again.
**Verdict: HIGH potential** — it moves the fight to the real memory target, and the
"generate the schedule, don't store it" framing finally fits.

### H-B. Holonomic low-rank / structured KV compression
**Idea.** Project KV onto a basis whose coefficients decay holonomically, keeping
$\mathcal{O}(\log L)$ or $\mathcal{O}(1)$ coefficients per head — the recurrence
defines the basis decay.
**Pro:** directly shrinks KV bytes; trendy area (MLA, KV low-rank).
**Con:** the holonomic sequence has no obvious reason to be the *right* basis;
DeepSeek-MLA already does learned low-rank well. We'd be bolting a number-theoretic
prior onto a problem that wants a *learned* one. Weak motivation.
**Verdict: LOW** — memory target right, but the math link is decorative.

### H-C. Learnable-γ Holonomic-ALiBi as a shipped positional scheme (the current path)
**Idea.** Finish v2: a competitive-with-ALiBi positional bias that also extrapolates.
**Pro:** real, measured, ~2% screen win; flat length-extrapolation; trivial to drop
into any model; the honest "modest contribution" we can actually stand behind today.
**Con:** the memory win is ~0 vs FA+ALiBi (see §0). It's a *quality/extrapolation*
contribution, not a *memory* one. Ceiling is "as good as ALiBi, plus a CY-shaped
prior," which a reviewer will call incremental.
**Verdict: MEDIUM** — ship it as what it is (an extrapolation-friendly bias), but
do **not** sell it as a memory win.

### H-D. Holonomic on-the-fly generation of a *large* structured mask (MoE/router/sparsity)
**Idea.** Use the recurrence to generate, on the fly, a large **block-sparsity or
expert-routing pattern** that would otherwise be a stored $\mathcal{O}(L^2)$ or
$\mathcal{O}(L\cdot E)$ table.
**Pro:** sparsity patterns *are* big and *are* often tabulated; O(L)-generation
could be real memory. Connects to the parked "Tier-2 mod-p router".
**Con:** our own earlier finding killed the mod-p router (0.8% kept, nearest 226) —
holonomic residues make terrible routers. Would need a fundamentally new rule.
**Verdict: LOW-MEDIUM** — right memory target, but our prior evidence is negative.

### H-E. Fuse the bias into FlashAttention (Stage B′) — convert HBM saving to latency
**Idea.** The orthogonal engineering track: fuse Tier-1 table + Tier-3 FMA into the
FA inner loop so the (small) bias work is free and the kernel matches FA latency.
**Pro:** necessary for *any* of the above to be deployable; turns "4–6× slower" into
"on par". Concrete, low-risk.
**Con:** doesn't by itself create a *new* win — it removes a penalty. Table-stakes,
not a contribution.
**Verdict: MEDIUM (enabler)** — required infrastructure, do it regardless.

### H-F. Holonomic positional scheme for *state-space / linear-attention* decay
**Idea.** Linear-attention / SSM models (Mamba, RetNet, GLA) use a per-channel
**decay gate** $\alpha\in(0,1)$. Initialize / structure those decays from the
holonomic curve (geometry-as-prior on the forget gate), generated O(L).
**Pro:** linear-attention is **already $\mathcal{O}(L)$ memory** — so a
holonomic decay there is *natively* a memory-efficient regime, no fight against FA.
The decay gate is the model's core inductive bias and is exactly a "monotone
decay" — our curve has a legitimate role. Hot research area.
**Con:** these decays are per-channel learned; a fixed CY prior may not beat learned
init. Requires a different codebase (SSM, not SDPA).
**Verdict: HIGH potential** — best *conceptual* fit: O(L) is the home turf, and the
decay gate genuinely wants a structured monotone prior.

### H-G. Multi-sequence "holonomic family" as a learnable bias *dictionary*
**Idea.** Instead of one $S_{20}$ curve, expose a small **dictionary** of holonomic
shapes ($S_{15}, S_{20}$, Apéry, …) and let each head learn a mixture weight + γ.
**Pro:** richer hypothesis space at O(L) cost (a few scalars/head); directly extends
the v2 winner; cheap to test.
**Con:** more knobs → more overfitting risk (we just got burned by that); marginal
over a single learnable γ.
**Verdict: MEDIUM** — a natural v3 ablation, low cost, bounded upside.

---

## Selection — the highest-property directions

Ranked by (memory leverage × conceptual fit × tractability), being honest that
"memory leverage" requires escaping the FA+ALiBi trap of §0:

1. **H-A — Holonomic KV-cache decay schedule.** The one direction where O(L)
   on-the-fly generation attacks the *real* memory wall (KV cache at long context)
   and the "generate, don't store" framing is finally load-bearing. Biggest
   potential genuine memory win.
2. **H-F — Holonomic decay prior for linear-attention/SSM gates.** Best conceptual
   fit: linear attention is already O(L) memory, and its forget-gate is precisely a
   monotone decay that wants a structured prior. Cleanest place for the geometry to
   matter.
3. **H-C + H-E (consolidate & ship the honest result).** Finish v2 (learnable-γ
   Holonomic-ALiBi) and the FA fusion, and publish it **as what it is**: an
   extrapolation-friendly positional bias competitive with ALiBi — a modest, real,
   shippable contribution, explicitly **not** a memory claim.

**De-prioritized:** H-B, H-D, H-G (decorative math link, prior negative evidence, or
marginal-with-overfit-risk respectively).

## Local experiment results (2026-06-22, CPU, ctx 512, WikiText-2)

All three selected directions were tested locally (`cy_sieve_memory_experiments.py`,
results `gpu_phase_runs/memory_experiments_20260622.json`):

- **H-C (quality) — CONFIRMED.** holo_ladder_pos 8.998 vs ALiBi 9.181 = **+2.0%**,
  reproducing the GPU screen gain on a fresh model. Real and robust.
- **H-A (KV eviction) — NO ADVANTAGE (locally).** At budget B=64/128 vs L=512, the
  holonomic-strided deep-past policy ties a plain recent window AND sink+recent
  (all within 0.05% of full attention). WikiText@512 has too little long-range
  dependency to exercise the deep-past benefit — a fair test needs a real
  long-range/retrieval benchmark (NIAH, PG-19, repo-code), not runnable locally.
  **Not refuted, but not validated** — do not claim a KV memory win on this evidence.
- **H-F (SSM decay prior) — WORSE.** holo_init 16.26 > retnet_fixed 16.06 > uniform
  0.95 15.06. The geometry prior did not help the forget-gate; gates converged to
  α≈0.95–0.99 regardless of init, so the init barely mattered. De-prioritized.

**Selection: H-C is the only one with a measurable gain — ship it as a quality/
extrapolation contribution, NOT a memory win.** H-A remains the *only* path to a
genuine memory win but is unproven and needs a long-range benchmark before any
claim. The honest current position: +2% over ALiBi on quality; memory win
**unrealized**.

## The one-line strategic conclusion

> The positional-bias memory win is illusory against FlashAttention+ALiBi. The
> defensible memory win, if one exists, is to redirect the holonomic
> $\mathcal{O}(L)$ "generate-don't-store" idea at the **KV cache** (H-A) or to plant
> the CY decay where $\mathcal{O}(L)$ is already native — **linear-attention/SSM
> gates** (H-F). Meanwhile, ship the learnable-γ bias honestly as a competitive,
> extrapolation-friendly positional scheme (H-C), not as a memory breakthrough.
