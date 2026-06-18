# Mirror Map Sieve — Honest Assessment & Project Journal

## Executive Verdict

**The core mathematics is real and independently verifiable.** The sequence $S(n) = \sum_{k=0}^n \binom{n}{k}^4\binom{n+k}{k}$ is correctly computed, the recurrence polynomials are genuine outputs of a legitimate $\mathbb{Q}$-nullspace computation, the mirror map integrality check passes with exact rational arithmetic, and the Lean 4 proofs are genuinely sorry-free. The sequence does not appear in OEIS — the novelty claim is valid.

**However, the repository has significant structural weaknesses, several overstatements in its claims, and missing infrastructure that would undermine credibility with expert reviewers.** Below is a component-by-component breakdown.

---

## Component Scorecard

| Component | Verdict | Grade | Key Issue |
|-----------|---------|-------|-----------|
| **Sequence definition** | Correct, novel, first principles | **A** | Not yet in OEIS |
| **Q-nullspace solver** | Real computation, reproducible | **A-** | Doesn't write JSON directly |
| **Recurrence polynomials** | Verified at n=0,1,2,3,4 independently | **A** | 60 coefficients, all correct |
| **SageMath/WZ script** | Real code but untested in repo | **B-** | No evidence it actually ran |
| **Lean 4 proofs** | Genuinely sorry-free | **A** | Only verifies n=0,1 (finite) |
| **Mirror map verifier** | Exact arithmetic, matches paper | **A** | Solid |
| **Diagonal search** | Honest research code | **A-** | Header has wrong first values |
| **AI hardware kernels** | Functional but arbitrary | **C+** | S20(d) decay not motivated |
| **Test suite** | Does not exist | **F** | No tests/ directory |
| **CI/CD** | Runs scripts, not tests | **C** | No assertions |
| **Data integrity** | 80 terms correct | **A** | Old name in s20_terms.json |
| **README accuracy** | Contains overstatements | **C+** | Still says "Callens-ALIX" |
| **Paper (v3)** | Camera-ready quality | **A-** | Well-structured |

---

## Critical Issues

### 1. Lean 4 Claim is Overstated
README badge says "Verified 0 Axioms" and prose says the recurrence was "formally verified."
**Reality**: Lean verifies n=0 and n=1 base cases + 8 sequence values. NOT the general recurrence.
**Fix**: Clarify scope in README.

### 2. No Test Suite
No tests/ directory, no pytest, no unit tests. CI runs scripts but can't detect silent failures.

### 3. Self-Eponymy Remnants
README still says "Callens-ALIX" in glossary, breakthroughs, benchmarks. s20_terms.json too.

### 4. Missing Proof Artifacts
extracted_polynomials.json references proof_artifacts/sage_zeilberger_gcp.log — file doesn't exist.

### 5. Version Mismatch
lean-toolchain says v4.31.0, extracted_polynomials.json says v4.14.0.

### 6. AI Hardware Section is Scientifically Weak
Using S20(d) as decay is arbitrary. Any growing sequence works. "Topological" claim unjustified.

### 7. Benchmarks are CPU-Only
README features GPU names (L4/T4/A100) but benchmark_results.json says hardware: "CPU".

### 8. Solver Doesn't Write Output
guess_s20_recurrence_int.py prints to stdout, doesn't produce extracted_polynomials.json.

---

## Genuine Strengths

1. Mathematical novelty is real — S(n) is not in OEIS
2. All computation from first principles — no hardcoded primary truth
3. Mirror map verification is exemplary
4. Diagonal search is honest (labels itself research code, reports failures)
5. Lean proofs genuine within their stated scope
6. Zenodo DOI and v3 paper are solid
