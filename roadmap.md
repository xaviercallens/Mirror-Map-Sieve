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
- [ ] GPU half: port the online-softmax recurrence to a **Triton** kernel
      (Tier 1 L1 table + Tier 3 FMA penalty; defer Tier 2); Triton-vs-NumPy
      FP16/BF16 parity (`tests.md` §4 T4.1). **Needs GPU.**

**Stage C — the gate that decides everything: quality, not just speed:**
- [ ] Zero-shot **perplexity** on WikiText-2 / a long-context eval, CY-Sieve vs
      **RoPE, ALiBi, and sliding-window** baselines at matched compute.
- [ ] Throughput / HBM-traffic measurement on a real GPU (the bandwidth claim).
- [ ] **Kill criteria:** if perplexity regresses beyond the `tests.md` threshold
      vs the best baseline, the tier (or the whole kernel) is reported as a
      negative result — not shipped.

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
