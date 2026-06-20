# Reproducibility Guide

To reproduce the discovery and verification of the weight-5 Apéry-like sequence S₂₀(n) (proposed OEIS A397213, pending review):

## 1. Environment Setup
You can use the provided Docker container to ensure all dependencies (Python, Lean 4, SageMath) are properly installed.

**Option A: Pull from GitHub Container Registry (Recommended)**
```bash
docker pull ghcr.io/xaviercallens/mirror-map-sieve:latest
docker run -it ghcr.io/xaviercallens/mirror-map-sieve:latest /bin/bash
```

**Option B: Build Locally**
```bash
docker build -t mirror-map-sieve .
docker run -it mirror-map-sieve /bin/bash
```

## 2. Algebraic Shielding
To extract the exact rational recurrence for S_20(n):
```bash
python3 src/algebraic_shielding/guess_s20_recurrence_int.py
```
This script computes the terms and solves the exact Q-nullspace to extract the polynomials.

## 3. Lean 4 Formal Proofs
To formally verify the sequence properties:
```bash
cd src/lean_proofs
lake build
```

## 4. Mirror Map and Congruences
To verify the Lian-Yau integrality and the supercongruences:
```bash
python3 src/mirror_map/verify_mirror_map.py
python3 src/congruences/verify_congruences.py
```
