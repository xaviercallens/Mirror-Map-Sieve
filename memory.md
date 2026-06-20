# Mirror Map Sieve — Project Memory (Post-Audit)

## Project Identity
- **Sequence**: $S(n) = \sum_{k=0}^{n} \binom{n}{k}^4 \binom{n+k}{k}$ (Weight-5 Apéry-like, catalog index S₂₀)
- **Zenodo DOI**: 10.5281/zenodo.20747943
- **GitHub**: https://github.com/xaviercallens/Mirror-Map-Sieve (v1.0.0)
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

## What Is NOT Verified
1. ❌ General recurrence for all n (Lean only checks n=0,1; rest relies on WZ certificate)
2. ❌ WZ certificate from SageMath (zeilberger_s20.sage code exists but no evidence it ran)
3. ❌ GCP execution logs (proof_artifacts/sage_zeilberger_gcp.log referenced but missing)
4. ❌ GPU benchmarks (results say "CPU", README says L4/T4/A100)
5. ❌ Test suite (none exists)

## Critical Knowledge for Next Session
- **Self-eponymy**: DONE — eponymous names removed repo-wide (June 20, 2026); author byline kept.
- **Lean scope**: Only base cases verified for the recurrence. Do NOT claim full formal
  verification of the general recurrence. (The cubic supercongruence, however, IS fully proven.)
- **AI kernels**: Scientifically weak / exploratory. Now clearly labelled as such in README + headers.
- **OEIS**: A397213 is a DRAFT pending editor approval — never describe it as accepted.
- **Highest-impact work**: a self-contained verified recurrence certificate (WZ/creative telescoping).
- **Naming convention**: "weight-5 Apéry-like sequence S₂₀(n)" everywhere; symbol S₂₀(n) or S(n).
