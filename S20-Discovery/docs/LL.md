# LESSONS_LEARNT.md — SocrateAI Scientific Agora

**Last Updated**: 2026-06-17 22:38 CET  
**Author**: Xavier Callens / Socrate AI Lab

---

## Lesson #1: A Single-Point Verification Is Not a Proof

**Date**: 2026-06-17  
**Source**: S15 Deep Audit  

**What we claimed**: "0 axioms, 0 sorry — the recurrence is Lean 4 kernel-verified."  

**What was actually proven**: The Lean 4 `decide` tactic verified that:
$$P_0(0) \cdot S_{20}(0) + P_1(0) \cdot S_{20}(1) + \cdots + P_5(0) \cdot S_{20}(5) = 0$$
This is **one numerical identity** involving 6 specific integers. It does not prove the recurrence holds for all $n$.

**What a referee would require**: Either:
- (a) A **creative telescoping certificate** — the explicit polynomial proof object from Zeilberger's algorithm, or
- (b) Verification at **>= order + degree + 1 = 15** initial values (by the identity principle for polynomial recurrences), or
- (c) A Lean 4 proof with `induction` or `omega`, not `decide` at one point.

**Resolution**: Run exact-arithmetic verification at n = 0, 1, ..., 19 (20 points). If all pass, the recurrence is proven by the identity principle (a polynomial of degree 9 vanishing at 20 points is identically zero). Script: `scratch/verify_recurrence_exact.py`.

**Severity**: CRITICAL — undermines the central mathematical claim.

---

## Lesson #2: Unvalidated "Applications" Are Hand-Waving, Not Applied Science

**Date**: 2026-06-17  
**Source**: S15 Mathematical Novelty Review  

**What we claimed**: "The sequence optimizes airfoil drag and characterizes quantum walk localization."

**What was actually done**:
- **Aeronautics**: Zero CFD simulations. The drag optimization claim is an assertion.
- **Quantum walks**: Zero quantum simulations. The P(t) ~ t^{-9/5} power-law is stated without derivation.
- **Cryptography**: Zero cryptographic analysis. The security claim is a trivial observation about growth rate.

**What a referee would say**: "Remove these sections entirely. They are speculation, not applied science."

**Resolution**: Strip ALL application sections from any publication draft. The sequence's mathematical properties (recurrence, integrality, diagonal representation) stand on their own. Applications require their own dedicated papers with actual simulations.

**Severity**: HIGH — could cause rejection at any reputable venue.

---

## Lesson #3: "Contribution" != "Breakthrough" — Calibrate Language to Reality

**Date**: 2026-06-17  
**Source**: S15 Mathematical Novelty Review  

**What we claimed**: "Shifted from discovery to breakthrough."

**Reality**: The sequence sum_k C(n,k)^4 * C(n+k,k) is the **next obvious member** of the family sum_k C(n,k)^a * C(n+k,k)^b that Zagier, Almkvist, Zudilin, and Cooper have systematically explored since 2006. A real "breakthrough" would be:
- Proving the integrality conjecture **in general**
- Finding unexpected modularity (connection to a specific modular form)
- Resolving Zudilin's supercongruence conjectures

**Resolution**: In all documents, replace "breakthrough" with "contribution." Replace "discovery" with "cataloging" where appropriate. The honest framing: "We computed the next natural member of a well-studied family and verified its properties. This is incremental but legitimate."

**Severity**: MEDIUM — credibility risk if peers perceive overclaiming.

---

## Lesson #4: Integer Mirror Map != "Found a New Calabi-Yau Manifold"

**Date**: 2026-06-17  
**Source**: S15 Mathematical Novelty Review  

**What we claimed**: "Every integer mirror map flag means we've found a new Calabi-Yau manifold."

**Why this is wrong**:
1. The manifold is **defined by the rational function** we write down. We don't "find" it — we construct it.
2. Christol's theorem guarantees that **any** sequence satisfying a linear recurrence with polynomial coefficients arises as the diagonal of some rational function. Existence is automatic.
3. The interesting question is whether the resulting variety is **smooth**, **geometrically interesting**, and has the right **Hodge numbers**. This requires actual algebraic geometry computations.
4. Integer mirror map coefficients are a **property** of the geometry, not a **discovery** of it.

**Resolution**: Replace "found a new Calabi-Yau manifold" with "computed the mirror map for a specific (a,b) family and verified integrality, providing empirical evidence for the Lian-Yau conjecture."

**Severity**: MEDIUM — mathematically misleading.

---

## Lesson #5: Match Publication Venue to Actual Content

**Date**: 2026-06-17  
**Source**: S15 Mathematical Novelty Review  

**What was suggested**: "Submit to Communications in Mathematical Physics."

**Why this is wrong**: CMP publishes rigorous mathematical physics with **full proofs**. An experimental observation about one integer sequence would not meet their standards.

**Correct venues**:
| Content | Venue | Readiness |
|---------|-------|-----------|
| The sequence S20 itself | **OEIS** | Ready now |
| Mirror map integrality observation | **Experimental Mathematics** | After independent verification |
| Lean 4 formalization methodology | **ITP** or **CPP** | After complete `lake build` |
| Real GPU benchmark results | **MLSys** or **ISCA** | After actual measurements |

**Resolution**: Do not submit to CMP. Target OEIS (immediate), Experimental Mathematics (after verification), and ITP/CPP (after `lake build`).

**Severity**: MEDIUM — wastes time and damages credibility if submitted to wrong venue.

---

## Meta-Lesson: AI-Generated Self-Assessments Are Worthless

Every one of these 5 lessons stems from the same root cause: **the AI system generated results, then generated a glowing assessment of its own results.** The feedback loop of self-congratulation produced:
- Inflated significance claims ("breakthrough")
- Missing verification steps (single-point proof)
- Speculative applications presented as established science
- Wrong publication venues
- Confusing definitions with discoveries

**The fix**: Every claim must be reviewed by an adversarial process — not the same system that generated it. The deep audit methodology (falsification-first) must be applied to every output, not just mathematical theorems.

---

## Lesson #6: ~~Always Independently Verify Published Numerical Values~~ → Verify the Verifier

**Date**: 2026-06-17  
**Source**: Mirror Map Integrality Verification  
**Status**: ~~CRITICAL~~ → **RETRACTED AND CORRECTED**

**Original claim**: "Every single published q_d value in the paper is WRONG."

**Correction**: The paper's q_d values are **CORRECT**. Our verification script v1 had a bug: it used $H_k$ instead of $H_{n-k}$ in the B20 formula. When corrected (v2), all 15 values match exactly.

**What actually happened**:
1. The paper defines B20(n) with $3H_n + H_{n+k} - 4H_{n-k}$
2. Our v1 script used $3H_n + H_{n+k} - 4H_k$ (H_k ≠ H_{n-k})
3. The buggy formula produced different but still-integer q_d values (q_2=5 instead of 9)
4. We incorrectly reported the paper as wrong

**The deeper lesson**: Independent verification is necessary, but the verifier itself must be verified. A single typo in the verification script ($H_k$ vs $H_{n-k}$) produced a false alarm that would have led to incorrectly retracting correct results.

**Interesting finding**: Both the correct ($H_{n-k}$) and incorrect ($H_k$) formulas produce integer mirror map coefficients. The integrality property appears to be robust under this specific perturbation, which is itself a potentially interesting mathematical observation.

**Severity**: MEDIUM — false alarm that was caught before any corrections were made to the paper

---

## Lesson #7: The Calabi-Yau Diagonal Representation Was Fabricated

**Date**: 2026-06-17  
**Source**: Diagonal Extraction Verification  

**What the paper claimed**: S20(n) = [x1^n...x5^n] 1/(1 - x1(1-x2)(1-x3)(1-x4)(1-x5) - x1*x2*x3*x4*x5)

**What the verification proved**: The diagonal of this rational function is 2^n, NOT S20(n).
- n=0: claimed 1, actual 1 (coincidence)
- n=1: claimed 3, actual 2 (WRONG)
- n=2: claimed 55, actual 4 (WRONG)
- n=7: claimed 840454275, actual 128 (WRONG)

**Algebraic proof of falsification**: The diagonal decomposes as sum_{j=0}^n C(n,j) * (-1)^{4j} = sum C(n,j) = 2^n. The (-1)^{4j} = 1 factor means the 4-fold product of (1-x_l) coefficients always collapses to 1.

**Root cause**: The rational function was likely guessed by analogy with known Apery diagonal representations (e.g., 1/(1-x(1-y)(1-z)-xyz) for sum C(n,k)^2*C(n+k,k)) without verification. The AI system generated the formula and never checked it.

**Resolution**: 
1. Remove the Calabi-Yau diagonal claim from the paper entirely
2. State honestly: "The correct rational function whose diagonal produces S20(n) remains unknown"
3. Finding the correct representation is a legitimate open problem

**Severity**: CRITICAL — the central geometric claim of the paper is false.

---

### 8. GCP Serverless for CAS Execution (2026-06-18)
**Severity**: MEDIUM  
**Trigger**: Local macOS ran out of disk space (< 3GB free), Docker and conda both failed.  
**Resolution**: Used Google Cloud Build + Cloud Run Jobs to execute SageMath and Python verification in the cloud. Zero local dependencies needed.  
**Rule**: When local resources are constrained, deploy compute to the cloud. GCP Cloud Run Jobs are ideal for one-shot mathematical computations.

### 9. Cross-Check Inline Text Against Computed Tables (2026-06-18)
**Severity**: HIGH  
**Trigger**: Paper v2 had '1, 6, 166, 7826...' in the introduction (line 102) but the table correctly showed '1, 3, 55, 1155...'. The inline text was never updated after the table was corrected.  
**Resolution**: Always grep for ALL occurrences of numerical values across the full document.  
**Rule**: After any correction, search the entire document for ALL instances of the old value.


## 11. Falsification-First Benchmarking
**Date:** 2026-06-18
**Lesson:** Never trust simulated or hardcoded results. Always build an end-to-end measurement pipeline on real hardware before analyzing metrics.
**Action:** Replaced simulated S15 benchmark data with a true PyTorch implementation measured via nvidia-smi and real tokens.
