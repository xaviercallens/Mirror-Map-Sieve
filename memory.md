# Mirror Map Sieve — Project Memory (Post-Audit)

## Project Identity
- **Sequence**: $S(n) = \sum_{k=0}^{n} \binom{n}{k}^4 \binom{n+k}{k}$ (Weight-5 Apéry-like, catalog index S₂₀)
- **Zenodo DOI**: 10.5281/zenodo.20747943
- **GitHub**: https://github.com/xaviercallens/Mirror-Map-Sieve (v1.0.0)
- **OEIS Status**: NOT YET SUBMITTED — sequence is confirmed absent from OEIS

## What Is Verified (Independently Confirmed June 18, 2026)
1. ✅ First 10 terms: 1, 3, 55, 1155, 29751, 852753, 26097499, 840454275, 28064517175, 964417304253
2. ✅ Recurrence holds at n=0,1,2,3,4 (all 60 polynomial coefficients correct)
3. ✅ Mirror map q_d ∈ ℤ for d=1,...,6 (run from first principles, matches paper)
4. ✅ Lean 4 proofs are sorry-free, admit-free (grep-confirmed)
5. ✅ All Python scripts compute from binomial formula, no hardcoded primary truth
6. ✅ OEIS search returns 0 results — novelty confirmed

## What Is NOT Verified
1. ❌ General recurrence for all n (Lean only checks n=0,1; rest relies on WZ certificate)
2. ❌ WZ certificate from SageMath (zeilberger_s20.sage code exists but no evidence it ran)
3. ❌ GCP execution logs (proof_artifacts/sage_zeilberger_gcp.log referenced but missing)
4. ❌ GPU benchmarks (results say "CPU", README says L4/T4/A100)
5. ❌ Test suite (none exists)

## Critical Knowledge for Next Session
- **Self-eponymy**: README still contains "Callens-ALIX" in multiple places — must be cleaned
- **Lean scope**: Only base cases verified. Do NOT claim full formal verification of recurrence
- **AI kernels**: Section is scientifically weak. Consider removing or drastically reducing
- **Immediate priority**: Fix credibility issues BEFORE arXiv submission
- **Highest-impact work**: Proving the supercongruences (especially S(p) ≡ 3 mod p³)
- **Naming convention**: Use "Weight-5 Apéry-like binomial sum S(n)" everywhere
