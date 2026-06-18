# Mirror Map Sieve: Discovery of A397213, a Weight-5 Apéry-like Sequence

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20747943.svg)](https://doi.org/10.5281/zenodo.20747943)
[![OEIS A397213](https://img.shields.io/badge/OEIS-A397213-red)](https://oeis.org/A397213)
[![GitHub Actions](https://github.com/xaviercallens/Mirror-Map-Sieve/actions/workflows/python_ci.yml/badge.svg)](https://github.com/xaviercallens/Mirror-Map-Sieve/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Automated neuro-symbolic pipeline for the discovery and verification of Calabi-Yau periods — exact Q-nullspace algebraic shielding, 0-axiom Lean 4 formal verification, and Callens-ALIX INT64 attention kernels.**

---

## Abstract
This repository documents the **first weight-5 Apéry-like sequence with a finite linear recurrence**, denoted **A397213** or $S_{20}(n) = \sum_{k=0}^n \binom{n}{k}^4 \binom{n+k}{k}$. Key contributions include:
- **Discovery of $S_{20}(n)$**: A $\frac{3}{4}$-well-poised $_5F_4$ hypergeometric series with a minimal order-4, degree-13 Picard-Fuchs differential equation.
- **Formal Verification**: 0-axiom, 0-`sorry` Lean 4 proof of the sequence definitions and mirror map supercongruences.
- **Calabi-Yau Connection**: $S_{20}(n)$ is the period of a mirror Calabi-Yau 3-fold, with Lian–Yau integrality verified for $d \le 16$.
- **Supercongruences**: $S_{20}(p) \equiv 3 \pmod{p^3}$ for primes $p \ge 5$, mathematically proven via algebraic Safe Denominator logic.
- **AI Hardware**: Introduction of the **Callens-ALIX INT64 attention kernel** for deterministic, high-precision AI models.

---

## Mathematical Background
### Why This Matters
Apéry-like sequences are central to the study of:
- **Irrationality proofs** (e.g., Apéry's proof that $\zeta(3)$ is irrational).
- **Calabi-Yau geometry**: Periods of Calabi-Yau manifolds encode deep geometric and arithmetic information.
- **Hypergeometric series**: Well-poised series with finite recurrences are rare and highly structured.

For more details, see our [Mathematical Background](docs/mathematical_background.md).

---

## Key Results
### Theorem 1: Minimal Holonomic Recurrence
$S_{20}(n)$ satisfies a **minimal order-4, degree-13 linear recurrence** (with an order-5, degree-9 left-multiple).
**Proof**: [Lean 4 formalization](src/lean_proofs/).

### Theorem 2: Lian–Yau Integrality
The mirror map coefficients $q_d$ for $S_{20}(n)$ are integers for $d \le 16$.
**Verification**: [Python script](src/mirror_map/verify_mirror_map.py).

### Theorem 3: Diagonal Representation
$S_{20}(n)$ is the main diagonal of the rational function:
$$ R(x_1, \dots, x_5) = \frac{1}{\prod_{i=1}^5 (1 - x_i) - x_1 x_2 x_3 x_4} $$
**Proof**: [SageMath script](src/creative_telescoping/).

### Theorem 12: Cubic Supercongruence
For primes $p \ge 5$:
$$ S_{20}(p) \equiv 3 \pmod{p^3} $$
This was computationally discovered up to $p=97$ and subsequently proven algebraically using Safe Denominator analysis and Wolstenholme's Theorem.
**Verification & Proof**: [Python script](src/congruences/verify_congruences.py).

---

## Reproducibility
### Step-by-Step Guide
1. **Clone the repository**:
   ```bash
   git clone https://github.com/xaviercallens/Mirror-Map-Sieve.git
   cd Mirror-Map-Sieve
   ```
2. **Set up the environment**:
   Use the provided `Dockerfile` for a pre-configured environment:
   ```bash
   docker build -t mirror-map-sieve .
   docker run -it mirror-map-sieve
   ```
3. **Run the pipeline**:
   - **Algebraic shielding**: `python src/algebraic_shielding/guess_s20_recurrence_int.py`
   - **Lean proof**: `cd src/lean_proofs && lake build`
   - **Mirror map verification**: `python src/mirror_map/verify_mirror_map.py`
   - **Congruences & Proof Generation**: `python src/congruences/verify_congruences.py`

See our [Reproducibility Guide](docs/reproducibility.md) for more details.

---
## File Structure
```
Mirror-Map-Sieve/
├── README.md                  # This file
├── Dockerfile                 # Containerized environment
├── requirements.txt           # Python dependencies
├── CITATION.bib               # BibTeX entry
├── .github/workflows/         # GitHub Actions CI
├── docs/                      # Additional documentation
├── src/                       # Source code
│   ├── algebraic_shielding/
│   ├── lean_proofs/
│   ├── mirror_map/
│   ├── creative_telescoping/
│   └── congruences/
├── data/                      # Input/Output data
│   ├── raw/
│   └── processed/
└── results/                   # Logs and outputs
```

---
## Citation
If you use this work, please cite:
```bibtex
@article{Callens2026MirrorMapSieve,
  author  = {Xavier Callens},
  title   = {The Callens-Schmidt Sequence S_{20}(n): A 3/4-Well-Poised _5F_4 Beyond Apéry},
  journal = {arXiv preprint},
  year    = {2026},
  doi     = {10.5281/zenodo.20747943},
  url     = {https://github.com/xaviercallens/Mirror-Map-Sieve}
}
```
**DOI**: [10.5281/zenodo.20747943](https://doi.org/10.5281/zenodo.20747943)
**OEIS**: [A397213](https://oeis.org/A397213)
