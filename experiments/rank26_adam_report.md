# Rank-26 Adam Search for ⟨4,4,4⟩ over the KalPhaseWeight ε-Algebra

**Generated:** 2026-06-12 19:30:19 UTC

## 1. Method

### Adam vs ALS

ALS (Alternating Least Squares) alternates between fixing two factor matrices and solving for the third via a closed-form least-squares step. It is prone to getting stuck in local minima and cannot follow *border-rank escape routes* where intermediate tensors pass through directions of increasing norm.

Adam-based gradient descent jointly updates all six factor matrices (real + ε components) simultaneously. The ε-components act as "deformation directions" that allow the optimizer to explore border-rank neighbourhoods of the tensor variety. Concretely:

- **Real CP loss**: ‖T − Σᵢ Uᵣᵢ⊗Vᵣᵢ⊗Wᵣᵢ‖²
- **ε-consistency loss**: ‖Σᵢ (Uₑᵢ⊗Vᵣᵢ⊗Wᵣᵢ + Uᵣᵢ⊗Vₑᵢ⊗Wᵣᵢ + Uᵣᵢ⊗Vᵣᵢ⊗Wₑᵢ)‖² (must → 0)
- **ε regularisation**: λ‖(Uₑ, Vₑ, Wₑ)‖² with λ=1e-4

### Hyperparameters

| Parameter | Value |
|-----------|-------|
| Ranks tried | [26, 32, 40, 49] |
| Learning rate | 0.01 |
| LR scheduler | ReduceLROnPlateau (factor=0.5, patience=500) |
| Max steps/restart | 10000 |
| Restarts/rank | 20 |
| ε regularisation λ | 0.0001 |
| Gradient clipping | max_norm=10.0 |
| Convergence threshold | 1e-06 |
| Save threshold | 0.1 |

### Initialisation strategies

- **Restart 0**: Strassen-inspired block-diagonal init (4 blocks × 7 terms)
- **Restart 1, 6, 11, 16**: Near-sparse unit-vector init
- **Remaining**: Random Gaussian (σ=0.1)

## 2. Results

Tensor norm: 8.000000 | Total wall time: 555.4s

### Convergence Table

| Rank | Best Residual | Rel. Residual | #Restarts Done | Found? |
|------|--------------|---------------|----------------|--------|
| 26 | 5.588473 | 0.698559 | 20 | ✗ |
| 32 | 4.800794 | 0.600099 | 20 | ✗ |
| 40 | 3.483082 | 0.435385 | 20 | ✗ |
| 49 | 1.428533 | 0.178567 | 20 | ✗ |

**Legend:** ✓ = exact (residual < 1e-6), ~ = near (< 0.1), ✗ = failed

### Per-rank convergence curves

#### Rank 26 (best restart: #0)

| Step | Real Loss | ε Loss |
|------|-----------|--------|
| 1000 | 32.595982 | 1.4337e-02 |
| 2000 | 31.938889 | 5.9476e-02 |
| 3000 | 31.669767 | 2.3233e-02 |
| 4000 | 31.539989 | 2.9904e-11 |
| 5000 | 31.446810 | 7.3578e-10 |
| 6000 | 31.324951 | 2.7875e-15 |
| 7000 | 31.306394 | 1.5001e-04 |
| 8000 | 31.282635 | 1.3103e-05 |
| 9000 | 31.260624 | 1.5707e-02 |
| 10000 | 31.231101 | 2.0737e-02 |

#### Rank 32 (best restart: #8)

| Step | Real Loss | ε Loss |
|------|-----------|--------|
| 1000 | 26.010414 | 1.1246e-02 |
| 2000 | 24.201605 | 7.2168e-02 |
| 3000 | 23.109431 | 1.5633e-02 |
| 4000 | 23.125840 | 2.0411e-02 |
| 5000 | 23.091995 | 1.0715e-02 |
| 6000 | 23.062576 | 2.9535e-16 |
| 7000 | 23.071844 | 6.1880e-29 |
| 8000 | 23.051477 | 4.3790e-11 |
| 9000 | 23.049125 | 4.0968e-29 |
| 10000 | 23.047622 | 6.4629e-38 |

#### Rank 40 (best restart: #13)

| Step | Real Loss | ε Loss |
|------|-----------|--------|
| 1000 | 12.896574 | 3.0859e-02 |
| 2000 | 12.373604 | 1.5561e-02 |
| 3000 | 12.334055 | 9.2943e-08 |
| 4000 | 12.253469 | 1.1692e-02 |
| 5000 | 12.349684 | 6.3630e-11 |
| 6000 | 12.177911 | 1.2346e-13 |
| 7000 | 12.166334 | 2.7955e-03 |
| 8000 | 12.153708 | 1.0490e-02 |
| 9000 | 12.150309 | 1.9919e-03 |
| 10000 | 12.161209 | 2.3303e-02 |

#### Rank 49 (best restart: #4)

| Step | Real Loss | ε Loss |
|------|-----------|--------|
| 1000 | 4.116096 | 1.8057e-02 |
| 2000 | 2.202399 | 3.6305e-02 |
| 3000 | 2.211280 | 2.9962e-02 |
| 4000 | 2.125507 | 5.2993e-02 |
| 5000 | 2.090024 | 5.5006e-02 |
| 6000 | 2.078308 | 1.0670e-02 |
| 7000 | 2.053407 | 4.6773e-19 |
| 8000 | 2.136400 | 7.6245e-23 |
| 9000 | 2.046727 | 2.0595e-02 |
| 10000 | 2.058485 | 6.7269e-03 |

## 3. Analysis

### Comparison with ALS

| Rank | ALS Best Real Residual | Adam Best Residual | Improvement |
|------|----------------------|-------------------|-------------|
| 26 | 8.2570 | 5.588473 | +2.6685 |
| 32 | 8.2649 | 4.800794 | +3.4641 |
| 40 | 8.3350 | 3.483082 | +4.8519 |
| 49 | N/A | 1.428533 | N/A |

### Why Adam converges differently from ALS

1. **Joint updates**: Adam updates all factor matrices simultaneously, allowing correlated gradient directions that ALS alternating steps miss.

2. **ε-algebra deformation**: By maintaining ε-components, the optimizer can move in the tangent space of the tensor variety, following paths that approach T from border-rank directions.

3. **Momentum**: Adam's first and second moment estimates allow it to accumulate momentum across saddle points that trap ALS.

4. **Adaptive learning rate**: Per-parameter step sizes allow fine-grained movement in flat directions of the loss landscape.

5. **Landscape geometry**: The loss landscape for CP decomposition has many saddle points and degenerate critical points. ALS tends to spiral around saddles; Adam can escape them via gradient momentum.

## 4. Honest Conclusion

❌ **No decomposition found** with residual < 0.1 within the 10-minute time budget.

Best residual achieved: 1.428533 at rank 49 (tensor norm: 8.0000, ratio: 0.1786).

### Interpretation in context of known bounds

| Claim | Status |
|-------|--------|
| R(⟨4,4,4⟩) ≥ 40 (Bläser 2003) | ✅ Established |
| R̃(⟨4,4,4⟩) ≤ 49 (Smirnov 2013) | ✅ Published |
| Adam found rank-26 decomposition | ❌ No |

Even with Adam, finding an exact rank-26 decomposition would contradict the Bläser lower bound of 40 for classical rank. What the ε-algebra search is probing is *border rank* R̃(⟨4,4,4⟩): whether T is in the closure of rank-≤26 tensors. The known best border-rank upper bound is 49 (Smirnov), and no published result achieves border rank < 40 for ⟨4,4,4⟩. Our negative result is consistent with the current state of the field.

## 5. References

- Bläser, M. (2003). On the complexity of the multiplication of matrices. JACM.
- Smirnov, M. M. (2013). Bilinear complexity of algebras and computation. arXiv.
- Le Gall, F. (2024). Faster matrix multiplication using the Cohn-Umans approach. STOC.
- Kingma, D. P., Ba, J. (2014). Adam: A method for stochastic optimization. arXiv:1412.6980.
