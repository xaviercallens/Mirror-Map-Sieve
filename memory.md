# Mirror Map Sieve — Project Memory (Post-Audit)

## Project Identity
- **Sequence**: $S(n) = \sum_{k=0}^{n} \binom{n}{k}^4 \binom{n+k}{k}$ (Weight-5 Apéry-like, catalog index S₂₀)
- **Zenodo DOI**: 10.5281/zenodo.20747943
- **GitHub**: https://github.com/xaviercallens/Mirror-Map-Sieve (latest release **v3.0.0**, 2026-06-20)
- **v3.0.0 contents**: de-eponymized; OEIS-pending honesty; 3 Lean theorems (cubic supercongruence,
  Wolstenholme, NEW Apéry-style S(p-1)≡1 mod p — all axiom-clean); v6 paper with full human proofs
  (paper/mirror_map_sieve_arxiv_v6.tex+pdf); python/verify_all.py (stdlib, exits 0);
  VERIFICATION_REPORT.md; CI consolidated to ci.yml (python-tests + lean-build both green).
- **GitHub push note**: repo owner account is `xaviercallens` (gh); the other logged-in account
  `pxcallen_amadeus` has read-only access. Switch with `gh auth switch --user xaviercallens` to push.
- **OEIS Status**: DRAFT A397213 submitted but NOT YET APPROVED by editors. A397213 is a
  pending placeholder, not an accepted OEIS entry. Do not cite it as accepted.
- **Naming**: All eponymous names ("S_20"/-Alix/-Al/-Lia) removed. Use the descriptive
  mathematical name "weight-5 Apéry-like sequence S₂₀(n)". Author byline "Xavier Callens" kept.

## What Is Verified (Independently Confirmed June 18, 2026)
1. ✅ First 10 terms: 1, 3, 55, 1155, 29751, 852753, 26097499, 840454275, 28064517175, 964417304253
2. ✅ Recurrence holds at n=0,1,2,3,4 (all 60 polynomial coefficients correct)
3. ✅ Mirror map q_d ∈ ℤ for d=1,...,6 (run from first principles, matches paper)
4. ✅ Lean 4 proofs are sorry-free, admit-free (grep-confirmed)
5. ✅ All Python scripts compute from binomial formula, no hardcoded primary truth
6. ✅ OEIS search returns 0 results — novelty confirmed

## Cubic Supercongruence — FULLY PROVEN (June 20, 2026)
- ✅ **S₂₀(p) ≡ 3 (mod p³) for all primes p ≥ 5 — UNCONDITIONAL, sorry-free, axiom-clean.**
  - `Supercongruence.supercongruence_unconditional` in S20Supercongruence.lean
  - Axiom audit: only [propext, Classical.choice, Quot.sound] (no sorryAx, no custom axiom)
- Two ingredients, both formalized in-project:
  1. The collapse `S₂₀(p) ≡ 1 + C(2p,p) (mod p³)` (`s20_collapse`) — novel step
  2. Wolstenholme `C(2p,p) ≡ 2 (mod p³)` (`Wolstenholme.wolstenholme`) — proved from
     first principles (was previously an external hypothesis). Proof path stays entirely
     in ZMod p: absorption `C(p,k)/p ≡ k⁻¹·(-1)^(k-1)`, squaring kills the sign, harmonic
     core `Σ k⁻² = Σ_{x:ZMod p} x² = 0` via `FiniteField.sum_pow_lt_card_sub_one`.
- Also: `supercongruence_mod_sq` (unconditional mod p², all primes, via Babbage).

## Picard–Fuchs Research Program — Phase 1 & 2 (June 20, 2026)
See docs/RESEARCH_PLAN.md, docs/PHASE1_FINDINGS.md, docs/PHASE2_FINDINGS.md.
- ✅ **Minimal recurrence order = 4, degree 13** — PROVED for all n. Four independent
  derivations (pure-Python GF(p) nullspace, exact ℚ reconstruction verified on 101 terms,
  ore_algebra `guess` on GCP/SageMath, Maxima `Zeilberger`); orders 2,3 impossible.
- ✅ **Creative-telescoping certificate** obtained (Maxima Zeilberger, GCP Cloud Build
  project agora-autoresearch-001) → recurrence proved for ALL n. This CLOSES the old
  "WZ certificate never ran" gap. Archived: src/picard_fuchs/maxima_telescoper_certificate.txt,
  phase1_gcp_result.json.
- ✅ **Minimal ODE for f(z): order 6, degree 15** (exact). Indicial eq. at z=0 = −715·s⁴(s−1)²
  ⇒ order-4 MUM block (CY 3-fold hallmark) + order-2 apparent singularity. RESOLVES the
  recurrence-4-vs-ODE-6 puzzle and the old "CY 4-fold" inconsistency → it's a **3-fold**.
- ✅ Mirror map q_d ∈ ℤ for d ≤ 16 (exact) — independent CY-3fold corroboration.
- ⚠️ **Instanton numbers UNRESOLVED**: placeholder Yukawa gave non-integers (denominators ∼d³,
  a normalization artifact, NOT a refutation). Correct coupling needs the isolated L₄.
- GCP/Sage tooling: ore_algebra NOT pip-installable; :latest builds it but its .factor()
  hits sage.rings.abc.SymbolicRing; 10.4 won't compile its Cython (FLINT slong). Maxima route
  is version-robust. Sage script: src/picard_fuchs/gcp_phase1_sage.py + Dockerfile.sage_ore.

## REMAINING TASKS (canonical — also in roadmap.md / todo.md)
1. ⏳ **Lean 4 re-check** of the Zeilberger certificate's finite rational identity
   (clear denominators → ring/linear_combination). Gold-standard closure of the recurrence.
2. ⛔ **Exhibit L₆ = L₄·L₂** with L₄ irreducible (the CY operator). BLOCKED on a
   version-matched Sage + ore_algebra pair; pin a maintainer-blessed combo.
3. ⏳ **Correct CY-3 Yukawa coupling** K_zzz from L₄ → genuine instanton-integrality test.
4. ⏳ **AESZ/van Straten operator-level match** of L₄ (novelty + 3-fold ID); textual prescreen
   of asz_sequences.json found no exact Σ C(n,k)⁴C(n+k,k) — operator match is decisive.
5. ⛔ **Phase 3 modularity** (gated on L₄): rigid/conifold fibers → Frobenius traces a_p →
   LMFDB weight-4 newform → Beukers/ASD-type supercongruence.
6. ⏳ **Conjecture** S(p−1) ≡ 1 (mod p³), p≥5 (numeric to p=200; mod p IS proved+Lean).
7. ⏳ **Conjecture** Lucas: S(mp+r) ≡ S(m)S(r) (mod p) (numeric).
8. ⏳ Submit OEIS draft once an editor reviews (A397213 still pending).
9. 🅿️ AI-hardware INT64 attention — PARKED (exploratory; benchmarks need real GPU run).

## Stale items now FIXED (for the record)
- GPU benchmarks were CPU-labelled, AI kernels overstated → now relabelled exploratory.
- Test suite: python/verify_all.py (stdlib, exits 0) + CI ci.yml green.

## Critical Knowledge for Next Session
- **Self-eponymy**: DONE — eponymous names removed repo-wide (June 20, 2026); author byline kept.
- **Recurrence scope (UPDATED)**: the order-4 recurrence is now PROVED for all n via the
  Maxima Zeilberger certificate. The remaining formal gap is only the *Lean re-check* of that
  certificate (Lean still only kernel-checks base cases directly). The cubic & Apéry-mod-p
  supercongruences ARE fully Lean-proven.
- **Geometry**: it is a CY **3-fold** (order-4 MUM block), NOT a 4-fold. "weight-5" was just a
  binomial-factor count, never a Hodge invariant.
- **Instantons**: do NOT claim integrality — placeholder normalization; unresolved.
- **AI kernels**: exploratory/parked; clearly labelled.
- **OEIS**: A397213 is a DRAFT pending editor approval — never describe it as accepted.
- **Highest-impact next steps**: (1) isolate L₄ via a version-matched Sage/ore_algebra,
  (2) correct Yukawa → instanton test, (3) Lean certificate re-check. See REMAINING TASKS above.
- **Naming convention**: "weight-5 Apéry-like sequence S₂₀(n)" everywhere; symbol S₂₀(n) or S(n).
- **GCP**: account callensxavier@gmail.com, project agora-autoresearch-001; Sage runs via
  `gcloud builds submit --config=src/picard_fuchs/cloudbuild_phase1_sage.yaml`.
