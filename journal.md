# Mirror Map Sieve — Honest Assessment & Project Journal

## 2026-06-20 — Phase 1 & 2 research log (Picard–Fuchs operator)

This entry records the research-program work (see `docs/RESEARCH_PLAN.md`,
`docs/PHASE1_FINDINGS.md`, `docs/PHASE2_FINDINGS.md`). Every claim is tagged
**proved / computed / conjectural / open**.

**Phase 1 — minimal recurrence order (PROVED for all n).**
- The minimal holonomic recurrence for $S(n)$ has **order 4, degree 13**;
  orders 2 and 3 are impossible. Established by **four independent derivations**:
  pure-Python exact GF($p$) nullspace (two primes), exact $\mathbb{Q}$
  reconstruction (verified on 101 terms), `ore_algebra` `guess` on GCP/SageMath
  (recovered the *identical* exact operator), and Maxima `Zeilberger`.
- Maxima's `Zeilberger` produced an order-4 **telescoper + certificate** $R(n,k)$
  (run on Google Cloud Build, project `agora-autoresearch-001`). The certificate
  proves the recurrence **for all $n$** — closing the finite-vs-infinite gap that
  the original journal (below) flagged as unformalized. Its leading coefficient
  equals our $P_4(n)=(n+3)^2(n+4)^4(\dots)$ exactly. **Still open:** a Lean 4
  re-check of the certificate identity.

**Phase 2 — operator structure & Calabi–Yau evidence.**
- The minimal **differential** operator for $f(z)=\sum S(n)z^n$ has order **6**
  (exact nullspace; matches `ore_algebra`). This is *not* a contradiction with
  the order-4 recurrence: the indicial equation at $z=0$ is
  $-715\,s^4(s-1)^2$, i.e. exponents $\{0,0,0,0,1,1\}$ — an **order-4 MUM block**
  (Calabi–Yau 3-fold hallmark) plus an order-2 **apparent-singularity** factor.
- Mirror-map coefficients $q_d\in\mathbb{Z}$ for $d\le16$ (exact). Two
  independent strands of **CY 3-fold evidence** (MUM-4 + integrality), consistent
  with the proved order-4 recurrence.
- **Honest negative:** with a placeholder Yukawa normalization the instanton
  numbers $n_d$ are **non-integer** (denominators $\sim d^3$) — a normalization
  artifact, not a refutation. **Instanton integrality is unresolved.**
- **Geometry verdict:** the long-standing "weight-5 / CY 4-fold" phrasing is
  wrong; the evidence points to a **CY 3-fold**, but the identification remains
  **conjectural** pending the explicit factorization $L_6=L_4\cdot L_2$ and the
  correct Yukawa coupling.

**Phase 3 (modularity):** not started — gated on extracting $L_4$ and its rigid
fibers.

---

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
| **README accuracy** | Contains overstatements | **C+** | Still says "S_20" |
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
README still says "S_20" in glossary, breakthroughs, benchmarks. s20_terms.json too.

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
