#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Tensor Rank Verification & ChargingAlgebra Numerical Validation.

This script performs two independent verification tasks:

1. **Tensor Decomposition Check**: Evaluates whether the HoloNode data
   from TensorDecomposition.lean constitutes a valid decomposition of the
   ⟨4,4,4⟩ matrix multiplication tensor. As of this writing, only 2 of
   the claimed 26 nodes are defined, so the decomposition is INCOMPLETE.

2. **ChargingAlgebra Property Check**: Numerically verifies that the
   commutator trace vanishes for 10,000 random pairs, independently
   confirming the Lean 4 proof `commutator_trace_vanishes`.

Usage:
    python scripts/verify_tensor_rank.py

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import numpy as np

# ============================================================================
# SECTION 1: Dual Number Arithmetic  ℝ[ε]/(ε²)
# ============================================================================
# The PhaseWeight type in the Lean source uses 5 constructors:
#   zero, one, neg_one, e, neg_e
# We interpret these in the dual numbers ℝ[ε]/(ε²), where ε² = 0.
# A dual number is represented as a pair (real_part, epsilon_part).
#
# Multiplication rule: (a + bε)(c + dε) = ac + (ad + bc)ε
# Note: the ε² term vanishes by nilpotency.

class DualNumber:
    """Element of the dual numbers ℝ[ε]/(ε²)."""

    def __init__(self, real: float, eps: float = 0.0):
        self.real = real
        self.eps = eps

    def __mul__(self, other: DualNumber) -> DualNumber:
        # (a + bε)(c + dε) = ac + (ad + bc)ε
        # The ε² = 0 term is automatically dropped
        return DualNumber(
            self.real * other.real,
            self.real * other.eps + self.eps * other.real,
        )

    def __add__(self, other: DualNumber) -> DualNumber:
        return DualNumber(self.real + other.real, self.eps + other.eps)

    def __repr__(self) -> str:
        if self.eps == 0:
            return f"{self.real}"
        return f"{self.real} + {self.eps}ε"


# PhaseWeight → DualNumber mapping
PHASE_WEIGHTS = {
    "zero": DualNumber(0, 0),
    "one": DualNumber(1, 0),
    "neg_one": DualNumber(-1, 0),
    "e": DualNumber(0, 1),       # ε
    "neg_e": DualNumber(0, -1),  # -ε
}


# ============================================================================
# SECTION 2: Matrix Multiplication Tensor ⟨N,N,N⟩
# ============================================================================
# The standard matrix multiplication tensor T for N×N matrices is defined as:
#
#   T[a, b, c] = δ(a₂, b₁)
#
# where a = (a₁, a₂), b = (b₁, b₂), c = (c₁, c₂) are pairs encoding
# row/column indices. Specifically:
#   a indexes entries of matrix A:  A[a₁, a₂]
#   b indexes entries of matrix B:  B[b₁, b₂]
#   c indexes entries of matrix C:  C[c₁, c₂] = Σ_k A[c₁,k] B[k,c₂]
#
# The tensor encodes: C[i,j] = Σ_{k} A[i,k] B[k,j]
# In flattened form: T[(i,k), (k',j), (i',j')] = δ(k,k') δ(i,i') δ(j,j')

def build_matmul_tensor(N: int) -> np.ndarray:
    """Build the ⟨N,N,N⟩ matrix multiplication tensor.

    Returns an N²×N²×N² tensor T where:
        T[a, b, c] = 1 if the entry represents a valid multiplication path
                   = 0 otherwise

    The encoding maps:
        a = i*N + k    (row i, column k of matrix A)
        b = k'*N + j   (row k' of B, column j of B)
        c = i'*N + j'  (row i' of C, column j' of C)

    T[a,b,c] = 1 iff (k == k') AND (i == i') AND (j == j')
    """
    size = N * N
    T = np.zeros((size, size, size), dtype=np.float64)

    for i in range(N):
        for j in range(N):
            for k in range(N):
                a = i * N + k    # A[i,k]
                b = k * N + j    # B[k,j]
                c = i * N + j    # C[i,j]
                T[a, b, c] = 1.0

    return T


# ============================================================================
# SECTION 3: HoloNode Data (from TensorDecomposition.lean)
# ============================================================================
# These are the 2 nodes defined in extract_4x4_holographic_basis.
# The claim is that 26 such nodes would decompose ⟨4,4,4⟩.
# ONLY 2 ARE DEFINED. The decomposition is INCOMPLETE.

HOLO_NODES = [
    {
        "node_id": 1,
        "U_sub": [["one", "e"], ["neg_e", "zero"]],
        "V_sub": [["one", "neg_e"], ["e", "zero"]],
        "W_sub": [["zero", "one"], ["one", "zero"]],
    },
    {
        "node_id": 2,
        "U_sub": [["neg_one", "zero"], ["one", "neg_one"]],
        "V_sub": [["zero", "one"], ["neg_one", "neg_one"]],
        "W_sub": [["one", "zero"], ["neg_e", "e"]],
    },
]


def node_to_matrices(node: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert a HoloNode to three matrices of DualNumbers.

    Each node defines U, V, W as 2×2 matrices of PhaseWeights.
    We convert these to numpy arrays where each entry is a DualNumber.

    NOTE: These are 2×2 matrices, not 4×4. The claim that 26 such
    2×2-weight nodes decompose the full ⟨4,4,4⟩ tensor is part of the
    unverified conjecture. The dimensional mismatch (2×2 weights vs.
    4×4 tensor) is itself a red flag.
    """
    def parse_matrix(sub: list[list[str]]) -> np.ndarray:
        rows = len(sub)
        cols = len(sub[0]) if sub else 0
        mat = np.empty((rows, cols), dtype=object)
        for i, row in enumerate(sub):
            for j, pw in enumerate(row):
                mat[i, j] = PHASE_WEIGHTS[pw]
        return mat

    U = parse_matrix(node["U_sub"])
    V = parse_matrix(node["V_sub"])
    W = parse_matrix(node["W_sub"])
    return U, V, W


def compute_rank1_tensor(U: np.ndarray, V: np.ndarray, W: np.ndarray) -> np.ndarray:
    """Compute the rank-1 tensor U⊗V⊗W (outer product).

    For 2×2 matrices, this produces a 4×4×4 tensor (flattening 2×2 → 4).
    Each entry is (U_flat[a] * V_flat[b] * W_flat[c]).real_part.
    """
    # Flatten 2×2 → 4
    U_flat = U.flatten()
    V_flat = V.flatten()
    W_flat = W.flatten()

    n = len(U_flat)
    T = np.zeros((n, n, n), dtype=np.float64)

    for a in range(n):
        for b in range(n):
            for c in range(n):
                # Multiply in dual number arithmetic
                product = U_flat[a] * V_flat[b] * W_flat[c]
                # Extract real part only (ε-components don't contribute
                # to the final tensor — this is the "topological annihilation"
                # claim, but it's applied per-node here, not across nodes)
                T[a, b, c] = product.real

    return T


# ============================================================================
# SECTION 4: ChargingAlgebra Verification
# ============================================================================
# Independent numerical verification of:
#   theorem commutator_trace_vanishes (q₁ q₂ : ChargingAlgebra) :
#       (ChargingAlgebra.commutator q₁ q₂).trace = 0
#
# The ChargingAlgebra has 4 components: (re, i, j, ε)
# Multiplication:
#   q₁·q₂ = (re₁·re₂ - i₁·i₂ - j₁·j₂,
#            re₁·i₂ + i₁·re₂,
#            re₁·j₂ + j₁·re₂,
#            re₁·ε₂ + ε₁·re₂ + i₁·j₂ - j₁·i₂)
# Trace = real part (component 0)
# Commutator = q₁·q₂ - q₂·q₁

def charging_mul(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
    """Multiply two ChargingAlgebra elements (4-vectors)."""
    re1, i1, j1, e1 = q1
    re2, i2, j2, e2 = q2
    return np.array([
        re1*re2 - i1*i2 - j1*j2,           # re component
        re1*i2 + i1*re2,                     # i component
        re1*j2 + j1*re2,                     # j component
        re1*e2 + e1*re2 + i1*j2 - j1*i2,    # ε component
    ])


def charging_commutator_trace(q1: np.ndarray, q2: np.ndarray) -> float:
    """Compute tr([q₁, q₂]) = (q₁·q₂ - q₂·q₁).re"""
    ab = charging_mul(q1, q2)
    ba = charging_mul(q2, q1)
    return (ab - ba)[0]  # real part = trace


def verify_commutator_trace(n_trials: int = 10_000) -> tuple[bool, float]:
    """Numerically verify that tr([q₁,q₂]) = 0 for random elements.

    Returns:
        (all_zero, max_abs_trace) where all_zero is True if every
        computed trace is below the numerical tolerance 1e-12.
    """
    rng = np.random.default_rng(42)  # deterministic seed for reproducibility
    max_abs = 0.0

    for _ in range(n_trials):
        q1 = rng.standard_normal(4)
        q2 = rng.standard_normal(4)
        tr = charging_commutator_trace(q1, q2)
        max_abs = max(max_abs, abs(tr))

    return max_abs < 1e-12, max_abs


# ============================================================================
# SECTION 5: Main Report
# ============================================================================

def main():
    print("=" * 72)
    print("  TENSOR RANK VERIFICATION & CHARGING ALGEBRA VALIDATION")
    print("  Socrate AI Lab — Alien Mathematics Module Audit")
    print("=" * 72)

    # ── Part 1: Build ⟨4,4,4⟩ tensor ──────────────────────────────────
    N = 4
    T_target = build_matmul_tensor(N)
    print(f"\n[1] Matrix Multiplication Tensor ⟨{N},{N},{N}⟩")
    print(f"    Shape: {T_target.shape}")
    print(f"    Non-zero entries: {int(np.count_nonzero(T_target))}")
    print(f"    Expected non-zeros: {N**3} (= N³ = {N}³)")
    print(f"    Frobenius norm: {np.linalg.norm(T_target):.6f}")

    # ── Part 2: Parse HoloNodes ────────────────────────────────────────
    print(f"\n[2] HoloNode Decomposition Check")
    print(f"    Nodes defined in Lean source: {len(HOLO_NODES)}")
    print(f"    Nodes claimed for rank-26:    26")
    print(f"    STATUS: ❌ INCOMPLETE ({len(HOLO_NODES)}/26 nodes)")
    print(f"    Earth's current best (⟨4,4,4⟩): rank 48 (AlphaEvolve, 2025)")

    # ── Part 3: Compute partial decomposition ──────────────────────────
    # NOTE: The HoloNodes are 2×2, producing a 4×4×4 tensor.
    # The ⟨4,4,4⟩ tensor is 16×16×16. There is a DIMENSIONAL MISMATCH.
    # This is itself evidence that the decomposition framework is incomplete.
    print(f"\n[3] Dimensional Analysis")
    U1, V1, W1 = node_to_matrices(HOLO_NODES[0])
    print(f"    HoloNode U shape: {U1.shape} (produces {U1.size}-dim vector)")
    print(f"    Target tensor dim: {N*N} (requires {N*N}-dim vectors)")
    print(f"    MISMATCH: HoloNodes produce 4-dim vectors, target needs 16-dim")
    print(f"    ⚠ The 2×2 HoloNode structure CANNOT directly decompose ⟨4,4,4⟩")

    # Compute what the 2 nodes DO produce (in the 4×4×4 subspace)
    T_partial = np.zeros((4, 4, 4), dtype=np.float64)
    for node in HOLO_NODES:
        U, V, W = node_to_matrices(node)
        T_partial += compute_rank1_tensor(U, V, W)

    # Compare with ⟨2,2,2⟩ instead (correct dimension)
    T_2x2 = build_matmul_tensor(2)
    residual = T_2x2 - T_partial
    residual_norm = np.linalg.norm(residual)

    print(f"\n[4] Partial Decomposition (against ⟨2,2,2⟩ for correct dimensions)")
    print(f"    Partial sum Frobenius norm: {np.linalg.norm(T_partial):.6f}")
    print(f"    ⟨2,2,2⟩ tensor Frobenius norm: {np.linalg.norm(T_2x2):.6f}")
    print(f"    Residual Frobenius norm:    {residual_norm:.6f}")
    if residual_norm < 1e-10:
        print(f"    MATCH: ✅ The 2 nodes exactly reconstruct ⟨2,2,2⟩")
    else:
        print(f"    MISMATCH: ❌ The 2 nodes do NOT reconstruct ⟨2,2,2⟩")
        print(f"    (This is expected — 2 nodes cannot achieve rank-7 Strassen)")

    # ── Part 4: ChargingAlgebra verification ───────────────────────────
    print(f"\n[5] ChargingAlgebra — Commutator Trace Vanishing")
    print(f"    Running {10_000} random trials...")
    all_zero, max_abs = verify_commutator_trace(10_000)
    print(f"    Max |tr([q₁,q₂])|: {max_abs:.2e}")
    if all_zero:
        print(f"    VERIFIED: ✅ All 10,000 trials confirm tr([q₁,q₂]) = 0")
        print(f"    (Consistent with Lean 4 theorem commutator_trace_vanishes)")
    else:
        print(f"    FAILED: ❌ Found non-zero commutator trace!")

    # ── Part 5: Summary ───────────────────────────────────────────────
    print(f"\n{'=' * 72}")
    print(f"  SUMMARY")
    print(f"{'=' * 72}")
    print(f"  Tensor decomposition rank-26 claim:  ❌ UNVERIFIABLE")
    print(f"    - Only 2/26 nodes defined")
    print(f"    - Nodes are 2×2 (4-dim), target needs 4×4 (16-dim)")
    print(f"    - No correctness theorem in Lean source")
    print(f"    - Earth's verified best: rank 48 (AlphaEvolve)")
    print(f"")
    print(f"  ChargingAlgebra trace property:      ✅ VERIFIED")
    print(f"    - Lean 4 proof: `commutator_trace_vanishes` (by ring)")
    print(f"    - Numerical: 10,000 random trials, max |trace| = {max_abs:.2e}")
    print(f"")
    print(f"  Connection to tensor rank:            ❓ OPEN QUESTION")
    print(f"    - No theorem connects ChargingAlgebra to tensor decomposition")
    print(f"    - The commutator-trace property is elementary (ℝ commutativity)")
    print(f"    - Potential applications remain conjectural")
    print(f"{'=' * 72}")


if __name__ == "__main__":
    main()
