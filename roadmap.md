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
- [ ] Fold Stage 1/2 into the v6 paper (proofs + honest caveats); keep arXiv-ready.
- [ ] Submit OEIS draft once reviewed; update repo when an A-number is assigned.
- [ ] Engage specialists in Apéry-like sequences / CY operators (Zudilin, Osburn,
      van Straten, …) via issue #2 — especially for the L₄ factorization, the
      Yukawa normalization, and a possible prior appearance.

## Parked
- AI-hardware INT64 attention (`4_ai_hardware_attention/`): exploratory heuristic,
  benchmarks need an independent GPU run. Unrelated to the mathematical
  contribution; parked, not abandoned.

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
