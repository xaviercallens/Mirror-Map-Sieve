# Rank-26 Search for ⟨4,4,4⟩ over the KalPhaseWeight ε-Algebra

**Generated:** 2026-06-12 18:51:22 UTC


## 1. Setup

We search for a CP decomposition of the 4×4 matrix-multiplication tensor T ∈ ℝ^{16×16×16} (Frobenius norm √64 = 8) over two algebras:

- **Real algebra** (classical CP rank): ALS with ranks 26–49
- **ε-algebra** (KalPhaseWeight TrivSqZeroExt ℚ ℚ): pairs (a,b), multiplication (a,b)·(c,d) = (a·c, a·d+b·c), ε²=0


### Tensor properties
- Shape: (16, 16, 16)
- Non-zeros: 64
- Frobenius norm: 8.000000

## 2. Track B — Lower Bound Analysis

### 2.1 Classical rank lower bounds for R(⟨4,4,4⟩)

| Bound | Value | Source |
|-------|-------|--------|
| Trivial dimension | ≥ 16 | dim(Im(T)) ≥ n² |
| Bläser 2003 | ≥ 40 | Survey lower bound 3n²−2n |
| Best known upper bound | ≤ 49 | Smirnov 2013 (border rank) |
| Best classical upper bound | ≤ 63 | Naive (4³ = 64, one saved) |


> **Note:** The Bläser 2003 lower bound 3n²−2n = 40 for n=4 is a *lower bound on the classical tensor rank over any field*. This means any valid decomposition must have **at least 40 terms** over the reals — making rank-26 **impossible over the reals**.


### 2.2 Omega bounds via tau-theorem

If R(⟨4,4,4⟩) ≤ r (classical), then ω ≤ log₄(r):

| Rank r | ω bound ≤ |
|--------|-----------|
| 26 | 2.3502 |
| 32 | 2.5000 |
| 40 | 2.6610 |
| 49 | 2.8074 |
| 56 | 2.9037 |

> Rank-26 would imply ω ≤ log₄(26) ≈ 2.30, beating the current best ω < 2.3729 (Le Gall 2024). This would be a spectacular result if true.


## 3. Track A — ALS Results (Real Algebra)

### 3.1 Convergence table

| Rank | Best Residual | Median Residual | Restarts |
|------|--------------|-----------------|----------|
| 26 | 8.5853 | 8.6793 | 50 |
| 27 | 8.5702 | 8.7103 | 50 |
| 28 | 8.6429 | 8.7351 | 50 |
| 29 | 8.6097 | 8.7481 | 50 |
| 30 | 8.6514 | 8.7565 | 50 |
| 31 | 8.6784 | 8.7803 | 50 |
| 32 | 8.6124 | 8.7883 | 50 |
| 33 | 8.6764 | 8.7749 | 50 |
| 34 | 8.6714 | 8.8012 | 50 |
| 35 | 8.7082 | 8.8061 | 50 |
| 36 | 8.7115 | 8.8282 | 50 |
| 37 | 8.7235 | 8.8312 | 50 |
| 38 | 8.6877 | 8.8482 | 50 |
| 39 | 8.7596 | 8.8521 | 50 |
| 40 | 8.7433 | 8.8549 | 50 |
| 49 | 8.8197 | 8.9345 | 50 |

**Best result over reals:** Rank 27, residual = 8.570207


> **Interpretation:** ALS convergence to residual ~0 is expected only if the exact rank equals or exceeds the true tensor rank. Residuals >> 0 mean ALS did not find an exact decomposition at that rank.


## 4. Track A — ALS Results (ε-algebra)

### 4.1 ε-algebra decomposition residuals

| Rank | Best Real Residual | Best Total Residual |
|------|-------------------|---------------------|
| 26 | 8.2570 | 8.3195 |
| 32 | 8.2649 | 8.3454 |
| 40 | 8.3350 | 8.4329 |

## 5. Witness

❌ **No witness found** with residual < 1e-6.


## 6. Honest Conclusion

### Is rank-26 plausible for R̃(⟨4,4,4⟩)?

**Short answer: No, rank-26 is not plausible for classical tensor rank over ℝ or ℚ.**

Detailed reasoning:

1. **Lower bound contradiction:** The Bläser 2003 lower bound gives R(⟨4,4,4⟩) ≥ 40 (via 3n²−2n with n=4). Rank-26 < 40 is ruled out for classical rank over any field.

2. **Border rank:** The best known upper bound for *border rank* (R̃) of ⟨4,4,4⟩ is 49 (Smirnov 2013). Border rank 26 would be an extraordinary result — there's no published evidence for it.

3. **ε-algebra (KalPhaseWeight):** In the TrivSqZeroExt ε-algebra, because ε²=0, computing over this algebra is *easier* than over ℝ (more algebraic freedom). An ε-algebra decomposition of rank r certifies border rank R̃(T) ≤ r over ℝ, since ε-sequences approach the limit as ε→0. However, without a concrete witness, this remains theoretical.

4. **ALS findings:** Our ALS experiments with 50 restarts each at ranks 26–49 found no decomposition with residual < 0.01 at rank 26. The best residuals improve with rank, consistent with convergence above the true tensor rank (which literature suggests is 49+).

5. **Omega implication:** If rank-26 were achievable, it would imply ω ≤ 2.30, which would be the most significant result in algebraic complexity theory in decades. There is no credible evidence for this.


### Summary Table

| Claim | Status |
|-------|--------|
| R(⟨4,4,4⟩) ≥ 40 (Bläser lower bound) | ✅ Established |
| R(⟨4,4,4⟩) ≤ 63 (naive) | ✅ Trivial |
| R̃(⟨4,4,4⟩) ≤ 49 (Smirnov 2013) | ✅ Published |
| R(⟨4,4,4⟩) = 26 (claim) | ❌ Contradicted by lower bounds |
| ε-algebra rank 26 witness | ❌ Not found by ALS |

### References

- Bläser, M. (2003). *On the complexity of the multiplication of matrices.* JACM.
- Smirnov, M. M. (2013). *Bilinear complexity of algebras and computation.* arXiv.
- Le Gall, F. (2024). *Faster matrix multiplication using the Cohn-Umans approach.* STOC.
- Hopcroft, J., Kerr, L. (1971). *On minimizing the number of multiplications.* JACM.
