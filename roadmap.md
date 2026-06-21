# Mirror Map Sieve — Roadmap

This roadmap reflects the **mathematics research program** (`docs/RESEARCH_PLAN.md`)
as the priority. It is an honest, falsifiable plan — not a promise of results.
We claim no discovery; the goal is rigorous, expert-reviewable progress.

## Stage 0: Discovery & honest re-baselining ✅ COMPLETE
- [x] Define S(n) = Σ C(n,k)⁴ C(n+k,k); compute & verify the first ~80 terms.
- [x] Mirror-map integrality q_d ∈ ℤ for d ≤ 16 (exact rational arithmetic).
- [x] Lean 4 base-case verification (sorry-free).
- [x] Zenodo DOI 10.5281/zenodo.20747943; GitHub releases through v3.0.0.
- [x] De-eponymize; mark OEIS A397213 as a **pending draft** (not accepted);
      add honest-scope framing and an expert-review call (issue #2).

## Stage 1: Certified Picard–Fuchs recurrence ✅ DONE (Lean re-check open)
- [x] Minimal recurrence order = **4**, degree 13 (four independent derivations;
      orders 2–3 impossible).
- [x] Exact operator over ℚ; verified on 101 terms.
- [x] Creative-telescoping **certificate** (Maxima Zeilberger, GCP/SageMath) ⇒
      recurrence proved **for all n**.
- [ ] Lean 4 kernel re-check of the certificate identity (gold standard).

## Stage 2: Calabi–Yau period identification 🔶 IN PROGRESS
- [x] Minimal **ODE** order of f(z) = **6**, degree 15 (exact nullspace).
- [x] Indicial equation at z=0: −715·s⁴(s−1)² ⇒ **order-4 MUM block**
      (Calabi–Yau **3-fold** evidence) + order-2 apparent singularity.
      → resolves the old "weight-5 / CY 4-fold" inconsistency in favour of a **3-fold**.
- [ ] Exhibit the factorization L₆ = L₄·L₂ with L₄ irreducible
      (**blocked** on a version-matched Sage + ore_algebra).
- [ ] Correct CY-3 Yukawa coupling from L₄ → **instanton-number integrality**
      (placeholder normalization gave non-integers — unresolved, flagged).
- [ ] Operator-level match against AESZ / van Straten databases (novelty + ID).

## Stage 3: Modularity 🔒 GATED on L₄
- [ ] Locate rigid / conifold fibers (roots of L₄'s leading coefficient).
- [ ] Frobenius traces a_p; search LMFDB S₄(Γ₀(N)) for a matching **weight-4
      newform**.
- [ ] Formulate + test a Beukers/Atkin–Swinnerton-Dyer-type supercongruence
      relating S to the newform.

## Arithmetic of S(n) (supercongruences) — runs alongside
- [x] S(p) ≡ 3 (mod p³), p ≥ 5 — **proved, Lean-verified** (elementary).
- [x] S(p−1) ≡ 1 (mod p) — **proved, Lean-verified**.
- [ ] **Conjecture** S(p−1) ≡ 1 (mod p³), p ≥ 5 (numeric to p=200; open).
- [ ] **Conjecture** Lucas: S(mp+r) ≡ S(m)S(r) (mod p) (numeric; open).

## Community & publication
- [x] Fold Stage 1/2 into the v6 paper (new Picard–Fuchs section, proofs +
      honest caveats). TODO: refresh the v3.0.0 release PDF asset to the 9-page build.
- [ ] Submit OEIS draft once reviewed; update repo when an A-number is assigned.
- [ ] Engage specialists in Apéry-like sequences / CY operators (Zudilin, Osburn,
      van Straten, …) via issue #2 — especially for the L₄ factorization, the
      Yukawa normalization, and a possible prior appearance.

## Applied track: the CY-Sieve attention kernel 🧪 EXPERIMENTAL (falsifiable)

A real implementation of the $S_{20}$/$S_{15}$ holonomic structure as a
memory-bandwidth-free positional-bias kernel. **Engineering hypothesis, not a
claimed win** — each tier has a quality gate in `tests.md` and is killed if it
fails. See `vision.md` for the corrected architecture and the verified numbers.

**Verified pre-conditions (done):**
- [x] INT64 crossover: $S_{20}$ safe to $d=13$, $S_{15}$ to $d=16$ (overflow at
      14 / 17). Tier-1 window confirmed.
- [x] Asymptotic constants: $\lambda=43.044$ ($\log\lambda=3.762$, **not** the
      proposal's 2.456) and $\beta\approx2$ — the $n^{-2}$ tail predicted by the
      rank-4 MUM Calabi–Yau-3-fold structure (links Phase 2 to the kernel).
- [x] mod-$p$ router (p=251) measured: only **0.78%** of distances kept, nearest
      kept distance **226** ⇒ the proposed keep-rule fails; Tier 2 reclassified
      as open research, not a feature.

**Stage A — CPU reference + numerics (no GPU needed): ✅ DONE**
- [x] `cy_sieve_reference.py`: exact INT64 Tier-1 table; recurrence-mod-$p$
      generator; Tier-3 log-space penalty with $\lambda,\beta$ from theory; the
      per-head $\tau$ ladder (fixing the native FP16 collapse).
- [x] Unit tests (`tests.md` §1–§3 + §3T): 35 tests; caught the $2^{32}$
      underflow bug and asserted the native-$\tau$ retrieval collapse.

**Stage B — kernel + parity:**
- [x] CPU half: `cy_sieve_attention.py` — dense SDPA + FlashAttention
      online-softmax variant with the bias; reference-vs-reference parity
      $\sim$3e-16; CPU needle-retrieval proxy. 13 tests (`tests.md` §4 + §5-proxy).
- [x] GPU half: `cy_sieve_triton.py` Triton kernel (Tier 1 L1 table + Tier 3 FMA
      penalty; Tier 2 deferred). **Triton-vs-reference FP16 parity (`tests.md` §4
      T4.1) PASSED on an NVIDIA L4** (2026-06-21, project SocrateAI) — the GPU
      orchestrator advanced past §4 to §5. block_n=32/num_stages=1 keeps SMEM
      under the L4's ~100KB.

**Stage C — the gate that decides everything: quality, not just speed:**
- [~] **In flight on the L4 (run started 2026-06-21).** `cy_sieve_quality_gate.py`
      + `cy_sieve_perf.py`, driven by `run_gpu_phase.py`; results upload to
      `gs://gen-lang-client-0625573011-cy-sieve-bench/cy_sieve/`.
- **Methodology correction (important):** the gate does **not** zero-shot-swap the
      positional scheme on a *frozen* pretrained model — that was tried and is
      invalid (it collapses **every** scheme equally: native ppl 32.5 vs ALiBi
      1641, sliding 2529, CY-Sieve ~7180 on WikiText-2 — pure train/test mismatch,
      not the scheme). Instead it follows the **ALiBi-paper methodology: train small
      GPTs from scratch**, identical arch/data/compute, one per scheme
      (learned-abs / ALiBi / sliding-window / CY-Sieve τ-ladder + single-τ sweep),
      then compare validation perplexity at the train context **and 2×/4×
      length-extrapolation** perplexity.
- **Anticipated outcome (hypothesis, not a result):** if the geometry-fixed
      β=2 / per-head-τ bias carries genuine positional signal, CY-Sieve val
      perplexity lands **within +1% of the best baseline** with **no worse
      length-extrapolation** — which, paired with §6's **O(L) vs O(L²) bias-HBM
      reduction**, is the whole case for the kernel. **Kill criterion (unchanged):
      >5% perplexity regression vs the best baseline ⇒ negative result, not
      shipped.** No verdict is claimed until the run completes.
- [x] Throughput / HBM-traffic on the L4 (`cy_sieve_perf.py`, §6) **MEASURED**
      (2026-06-21; see `docs/PHASE3_CYSIEVE_GPU_FINDINGS.md`): bias-path HBM is
      **O(L) vs O(L²) — 8192× less at L=16384** (the core claim, confirmed). Honest
      caveat: the *unfused* kernel is ~3.7× **slower** than fused dense SDPA in
      wall-clock — an HBM-traffic win, **not yet a latency win** (reported per T6.3).

**Stage B′ — kernel optimization (NEW, the work §6 revealed):**
- [ ] **Fuse the bias generation into the FlashAttention inner loop** so the O(L)
      HBM saving becomes a *latency* saving (currently the bias is a precomputed
      vector load; fold Tier-1 table + Tier-3 FMA into the score computation).
- [ ] Autotune `block_n` / `num_stages` / `num_warps` per arch (L4 SMEM ≈ 100 KB
      forced block_n=32; A100/H100 allow larger). Compare against FlashAttention-2/3.
- [ ] Add a BF16 path; re-measure latency vs dense SDPA and vs RoPE at 8K–128K.
- [ ] **Target:** match or beat fused dense SDPA latency *while* keeping the O(L)
      bias HBM — only then is "HBM-free positional bias" a wall-clock contribution.

**Stage D — research hypotheses (only if Stage C passes):** redesign Tier 2 (a
useful finite-field router), test "MoE routing via $S_{15}(d)\bmod E$" for load
balance, and measure extrapolation 4K→long-context. All explicitly speculative.

---

## Honest milestone notes (no dates promised)

| Milestone | Status | Impact if achieved |
|-----------|--------|--------------------|
| Order-4 recurrence proved (certificate) | **done** | Settles the holonomic structure |
| CY 3-fold identification (L₄ + Yukawa) | in progress | A (likely modest) AESZ-style entry |
| Lean re-check of certificate | open | Fully machine-checked recurrence |
| Weight-4 newform / modularity | gated | Deepest potential result |
| S(p−1) ≡ 1 (mod p³) proof | open | Strengthens the arithmetic picture |
| OEIS A-number assigned | pending editor | Permanence (after acceptance) |

These are research aims, not commitments; several may fail or turn out already
known. Corrections and expert review are welcome.
