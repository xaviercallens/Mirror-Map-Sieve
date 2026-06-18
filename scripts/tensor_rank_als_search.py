#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""
Tensor Rank Search via Alternating Least Squares (ALS)
======================================================

Searches for low-rank decompositions of the ⟨4,4,4⟩ matrix multiplication
tensor T ∈ ℝ^{16×16×16}.

The matrix multiplication tensor ⟨n,n,n⟩ encodes the bilinear map
    (A, B) ↦ A·B
for n×n matrices. Concretely, if we flatten A into a vector of length n²
and B into a vector of length n², the product C = A·B is also a vector
of length n², and T is the 3-way tensor such that:
    C_{ij} = Σ_{k} A_{ik} B_{kj} = Σ_{α,β} T_{αβγ} A_α B_β
where α = (i,k), β = (k,j), γ = (i,j) are multi-indices.

The tensor rank R(T) is the minimum number of rank-1 tensors u⊗v⊗w
whose sum equals T. For ⟨4,4,4⟩:
    - Naive: R ≤ 64 (n³)
    - Strassen-like: R ≤ 49
    - AlphaEvolve (DeepMind 2025): R ≤ 48 (current best)
    - Lower bound: R ≥ 48 (Bläser 2003 / Landsberg 2014)
    
This script attempts to find decompositions with R < 48 using ALS,
which is the standard workhorse algorithm for CP decomposition.

Algorithm: Alternating Least Squares (ALS)
------------------------------------------
Given T ∈ ℝ^{I×J×K}, find U ∈ ℝ^{I×R}, V ∈ ℝ^{J×R}, W ∈ ℝ^{K×R}
minimizing ‖T - [[U, V, W]]‖²_F where [[U,V,W]] = Σ_r u_r ⊗ v_r ⊗ w_r.

The ALS updates are:
    U ← T_(0) · (W ⊙ V) · ((V^T V) * (W^T W))^{-1}
    V ← T_(1) · (W ⊙ U) · ((U^T U) * (W^T W))^{-1}
    W ← T_(2) · (V ⊙ U) · ((U^T U) * (V^T V))^{-1}

where:
    T_(n) = mode-n unfolding (matricization) of T
    ⊙     = Khatri-Rao product (column-wise Kronecker)
    *     = Hadamard (element-wise) product

Dual Number Extension:
    We also search over ℝ[ε]/(ε²) where ε² = 0. Each factor entry
    becomes (a + bε). The larger search space may find decompositions
    that project to real decompositions via the ε→0 limit.

Usage:
    python scripts/tensor_rank_als_search.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.linalg import norm, pinv, solve


# ══════════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class SearchConfig:
    """Configuration for the ALS tensor rank search."""
    n: int = 4                    # Matrix dimension (⟨n,n,n⟩)
    max_rank: int = 48            # Start searching from this rank
    min_rank: int = 26            # Search down to this rank
    max_iterations: int = 200     # Max ALS iterations per restart
    num_restarts: int = 5         # Random restarts per rank
    convergence_tol: float = 1e-8 # Convergence tolerance for residual
    success_tol: float = 1e-6    # Tolerance to declare "success"
    seed: int = 42               # Base random seed
    search_dual: bool = True     # Also search over dual numbers
    output_dir: str = "output/tensor_rank_search"


# ══════════════════════════════════════════════════════════════════════════
#  TENSOR CONSTRUCTION
# ══════════════════════════════════════════════════════════════════════════

def build_matmul_tensor(n: int) -> np.ndarray:
    """Build the ⟨n,n,n⟩ matrix multiplication tensor.
    
    The tensor T ∈ ℝ^{n²×n²×n²} encodes the bilinear map (A,B) ↦ A·B
    for n×n matrices. We use the index convention:
        - First mode: α = (i,k) → A_{ik}, index = i*n + k
        - Second mode: β = (k,j) → B_{kj}, index = k*n + j  
        - Third mode:  γ = (i,j) → C_{ij}, index = i*n + j
    
    Then T[α, β, γ] = 1 if and only if the k-indices match and
    the i,j indices are consistent:
        T[i*n+k, k*n+j, i*n+j] = 1
    
    Args:
        n: Matrix dimension.
    
    Returns:
        T: np.ndarray of shape (n², n², n²) with entries in {0, 1}.
    """
    n2 = n * n
    T = np.zeros((n2, n2, n2), dtype=np.float64)
    
    for i in range(n):
        for j in range(n):
            for k in range(n):
                # α = (i,k), β = (k,j), γ = (i,j)
                alpha = i * n + k
                beta  = k * n + j
                gamma = i * n + j
                T[alpha, beta, gamma] = 1.0
    
    return T


def verify_matmul_tensor(T: np.ndarray, n: int) -> bool:
    """Verify the tensor correctly encodes matrix multiplication.
    
    Test: pick random n×n matrices A, B, compute C = A·B.
    Then check that C_{ij} = Σ_{α,β} T[α,β,γ] · A_flat[α] · B_flat[β]
    where γ = i*n+j.
    """
    rng = np.random.default_rng(12345)
    A = rng.standard_normal((n, n))
    B = rng.standard_normal((n, n))
    C_true = A @ B
    
    a = A.flatten()  # length n²
    b = B.flatten()  # length n²
    
    # Compute C via tensor contraction
    # C_flat[γ] = Σ_{α,β} T[α,β,γ] * a[α] * b[β]
    C_tensor = np.einsum('abg,a,b->g', T, a, b)
    C_from_tensor = C_tensor.reshape(n, n)
    
    err = norm(C_true - C_from_tensor)
    if err > 1e-10:
        print(f"  ⚠ Tensor verification FAILED: error = {err:.2e}")
        return False
    else:
        print(f"  ✓ Tensor verification passed: error = {err:.2e}")
        return True


# ══════════════════════════════════════════════════════════════════════════
#  TENSOR OPERATIONS
# ══════════════════════════════════════════════════════════════════════════

def unfold(T: np.ndarray, mode: int) -> np.ndarray:
    """Mode-n unfolding (matricization) of a 3-way tensor.
    
    For a tensor T of shape (I, J, K):
        Mode-0 unfolding: T_(0) has shape (I, J*K), with T_(0)[i, j*K+k] = T[i,j,k]
        Mode-1 unfolding: T_(1) has shape (J, I*K), with T_(1)[j, i*K+k] = T[i,j,k]  
        Mode-2 unfolding: T_(2) has shape (K, I*J), with T_(2)[k, i*J+j] = T[i,j,k]
    
    Args:
        T: 3-way tensor of shape (I, J, K).
        mode: Which mode to unfold along (0, 1, or 2).
    
    Returns:
        Matrix of shape (dim_mode, product_of_other_dims).
    """
    if mode == 0:
        # T_(0)[i, j*K+k] = T[i,j,k]
        # Move axis 0 to front (already there), reshape
        return T.reshape(T.shape[0], -1)
    elif mode == 1:
        # T_(1)[j, i*K+k] = T[i,j,k]
        # Move axis 1 to front
        return np.moveaxis(T, 1, 0).reshape(T.shape[1], -1)
    elif mode == 2:
        # T_(2)[k, i*J+j] = T[i,j,k]
        # Move axis 2 to front
        return np.moveaxis(T, 2, 0).reshape(T.shape[2], -1)
    else:
        raise ValueError(f"mode must be 0, 1, or 2, got {mode}")


def khatri_rao(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """Khatri-Rao product (column-wise Kronecker product).
    
    For A of shape (I, R) and B of shape (J, R), the Khatri-Rao product
    A ⊙ B is a matrix of shape (I*J, R) where column r is:
        (A ⊙ B)[:, r] = kron(A[:, r], B[:, r])
    
    Efficient implementation using broadcasting:
        A[:, np.newaxis, :] has shape (I, 1, R)
        B[np.newaxis, :, :] has shape (1, J, R)
        product has shape (I, J, R)
        reshape to (I*J, R)
    
    Args:
        A: Matrix of shape (I, R).
        B: Matrix of shape (J, R).
    
    Returns:
        Matrix of shape (I*J, R).
    """
    I, R = A.shape
    J, _ = B.shape
    # Broadcasting: (I,1,R) * (1,J,R) -> (I,J,R) -> (I*J, R)
    return (A[:, np.newaxis, :] * B[np.newaxis, :, :]).reshape(I * J, R)


def reconstruct_tensor(U: np.ndarray, V: np.ndarray, W: np.ndarray) -> np.ndarray:
    """Reconstruct a tensor from its CP decomposition.
    
    T_approx = Σ_r u_r ⊗ v_r ⊗ w_r = [[U, V, W]]
    
    This is equivalent to:
        T_approx[i,j,k] = Σ_r U[i,r] * V[j,r] * W[k,r]
    
    Args:
        U: Factor matrix of shape (I, R).
        V: Factor matrix of shape (J, R).
        W: Factor matrix of shape (K, R).
    
    Returns:
        Tensor of shape (I, J, K).
    """
    return np.einsum('ir,jr,kr->ijk', U, V, W)


def compute_residual(T: np.ndarray, U: np.ndarray, V: np.ndarray, W: np.ndarray) -> float:
    """Compute ‖T - [[U,V,W]]‖_F."""
    T_approx = reconstruct_tensor(U, V, W)
    return norm(T - T_approx)


# ══════════════════════════════════════════════════════════════════════════
#  ALS ALGORITHM
# ══════════════════════════════════════════════════════════════════════════

def als_step(T_unf: list[np.ndarray], U: np.ndarray, V: np.ndarray, W: np.ndarray,
             reg: float = 1e-12) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Perform one full ALS sweep (update U, V, W in sequence).
    
    The ALS update for each factor uses the normal equations:
        U ← T_(0) · (W ⊙ V) · ((V^T V) * (W^T W))^{-1}
    where * is the Hadamard product.
    
    We add a small Tikhonov regularization (reg * I) to the Gram matrix
    for numerical stability.
    
    Args:
        T_unf: List of 3 mode unfoldings [T_(0), T_(1), T_(2)].
        U, V, W: Current factor matrices.
        reg: Tikhonov regularization parameter.
    
    Returns:
        Updated (U, V, W).
    """
    R = U.shape[1]
    eye_R = reg * np.eye(R)
    
    # ── Update U ──────────────────────────────────────────────────────
    # Gram matrix: (V^T V) * (W^T W) — Hadamard product of Gram matrices
    VtV = V.T @ V  # (R, R)
    WtW = W.T @ W  # (R, R)
    gram_U = VtV * WtW + eye_R  # (R, R) — Hadamard product
    
    # Right-hand side: T_(0) @ (W ⊙ V)
    kr_WV = khatri_rao(W, V)  # (K*J, R)
    rhs_U = T_unf[0] @ kr_WV  # (I, R)
    
    # Solve: U = rhs_U @ gram_U^{-1}  <==>  gram_U^T @ U^T = rhs_U^T
    # Since gram is symmetric: gram @ U^T = rhs_U^T
    U_new = solve(gram_U.T, rhs_U.T).T
    
    # ── Update V ──────────────────────────────────────────────────────
    UtU = U_new.T @ U_new
    gram_V = UtU * WtW + eye_R
    kr_WU = khatri_rao(W, U_new)  # (K*I, R)
    rhs_V = T_unf[1] @ kr_WU     # (J, R)
    V_new = solve(gram_V.T, rhs_V.T).T
    
    # ── Update W ──────────────────────────────────────────────────────
    VtV_new = V_new.T @ V_new
    gram_W = UtU * VtV_new + eye_R
    kr_VU = khatri_rao(V_new, U_new)  # (J*I, R)
    rhs_W = T_unf[2] @ kr_VU          # (K, R)
    W_new = solve(gram_W.T, rhs_W.T).T
    
    return U_new, V_new, W_new


def als_decompose(T: np.ndarray, R: int, max_iter: int = 200,
                  tol: float = 1e-8, reg: float = 1e-12,
                  rng: np.random.Generator | None = None,
                  verbose: bool = False) -> dict[str, Any]:
    """Run ALS to find a rank-R CP decomposition of T.
    
    Args:
        T: Target tensor of shape (I, J, K).
        R: Target rank (number of rank-1 components).
        max_iter: Maximum number of ALS iterations.
        tol: Convergence tolerance on the residual norm.
        reg: Tikhonov regularization.
        rng: Random number generator.
        verbose: Print progress.
    
    Returns:
        Dict with keys: U, V, W, residual, converged, iterations.
    """
    if rng is None:
        rng = np.random.default_rng()
    
    I, J, K = T.shape
    T_norm = norm(T)
    
    # Precompute mode unfoldings
    T_unf = [unfold(T, mode) for mode in range(3)]
    
    # Initialize factors randomly (Gaussian, scaled)
    # Scale by (T_norm / R)^{1/3} for a reasonable starting point
    scale = (T_norm / R) ** (1.0 / 3.0)
    U = rng.standard_normal((I, R)) * scale
    V = rng.standard_normal((J, R)) * scale
    W = rng.standard_normal((K, R)) * scale
    
    residual_history = []
    converged = False
    best_residual = float('inf')
    best_factors = (U.copy(), V.copy(), W.copy())
    
    for it in range(max_iter):
        try:
            U, V, W = als_step(T_unf, U, V, W, reg=reg)
        except np.linalg.LinAlgError:
            # Singular matrix — increase regularization and retry
            if verbose:
                print(f"    LinAlgError at iter {it}, increasing reg")
            reg *= 10
            continue
        
        residual = compute_residual(T, U, V, W)
        rel_residual = residual / T_norm
        residual_history.append(float(residual))
        
        if residual < best_residual:
            best_residual = residual
            best_factors = (U.copy(), V.copy(), W.copy())
        
        if verbose and (it % 50 == 0 or it == max_iter - 1):
            print(f"    Iter {it:4d}: residual = {residual:.6e} "
                  f"(relative = {rel_residual:.6e})")
        
        # Check convergence
        if residual < tol:
            converged = True
            if verbose:
                print(f"    ✓ Converged at iter {it}: residual = {residual:.6e}")
            break
        
        # Check for stagnation (no improvement in last 20 iters)
        if len(residual_history) > 20:
            recent_min = min(residual_history[-20:])
            older_min = min(residual_history[-40:-20]) if len(residual_history) > 40 else residual_history[0]
            if abs(recent_min - older_min) / (older_min + 1e-30) < 1e-10:
                if verbose:
                    print(f"    ⊘ Stagnated at iter {it}: residual = {residual:.6e}")
                break
        
        # Check for divergence
        if not np.isfinite(residual):
            if verbose:
                print(f"    ✗ Diverged at iter {it}")
            break
    
    U_best, V_best, W_best = best_factors
    return {
        "U": U_best,
        "V": V_best,
        "W": W_best,
        "residual": float(best_residual),
        "converged": converged,
        "iterations": it + 1 if 'it' in dir() else 0,
        "residual_history": residual_history,
    }


# ══════════════════════════════════════════════════════════════════════════
#  DUAL NUMBER ALS
# ══════════════════════════════════════════════════════════════════════════
# 
# Dual numbers ℝ[ε]/(ε²): each element is a + bε where ε² = 0.
# Arithmetic:
#   (a + bε)(c + dε) = ac + (ad + bc)ε
#   (a + bε) + (c + dε) = (a+c) + (b+d)ε
#
# We represent dual matrices as pairs (real_part, eps_part).
# The key insight: if we find a decomposition T = Σ u_r⊗v_r⊗w_r
# over the dual numbers, the real parts alone give:
#   T_real = Σ u_r_real ⊗ v_r_real ⊗ w_r_real + (cross terms involving ε)
# Since ε²=0, some cancellations may allow a lower-rank decomposition.
#
# However, a valid real decomposition requires the real parts alone
# to reconstruct T. The dual search is an exploration of the
# optimization landscape that may find better local minima.

def dual_multiply(A_real: np.ndarray, A_eps: np.ndarray,
                  B_real: np.ndarray, B_eps: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Matrix multiplication in ℝ[ε]/(ε²).
    
    (A_r + A_e·ε)(B_r + B_e·ε) = A_r·B_r + (A_r·B_e + A_e·B_r)·ε
    """
    real = A_real @ B_real
    eps = A_real @ B_eps + A_eps @ B_real
    return real, eps


def dual_khatri_rao(A_real: np.ndarray, A_eps: np.ndarray,
                    B_real: np.ndarray, B_eps: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Khatri-Rao product over ℝ[ε]/(ε²).
    
    (A_r + A_e·ε) ⊙ (B_r + B_e·ε) = A_r⊙B_r + (A_r⊙B_e + A_e⊙B_r)·ε
    """
    real = khatri_rao(A_real, B_real)
    eps = khatri_rao(A_real, B_eps) + khatri_rao(A_eps, B_real)
    return real, eps


def dual_hadamard(A_real: np.ndarray, A_eps: np.ndarray,
                  B_real: np.ndarray, B_eps: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Hadamard product over ℝ[ε]/(ε²)."""
    real = A_real * B_real
    eps = A_real * B_eps + A_eps * B_real
    return real, eps


def dual_als_decompose(T: np.ndarray, R: int, max_iter: int = 200,
                       tol: float = 1e-8, reg: float = 1e-12,
                       rng: np.random.Generator | None = None,
                       verbose: bool = False) -> dict[str, Any]:
    """Run ALS over ℝ[ε]/(ε²) to find a rank-R CP decomposition.
    
    The key idea: we embed T into the dual number algebra by setting
    T_dual = T + 0·ε (the real tensor, with zero epsilon part).
    Then we search for U, V, W over ℝ[ε]/(ε²) such that
    [[U, V, W]] = T_dual.
    
    For the decomposition to be valid over ℝ, we need:
    1. Real part: Σ u_r_real ⊗ v_r_real ⊗ w_r_real = T  (this is the real constraint)
    2. Epsilon part: the ε-component of the sum should be zero.
    
    Strategy: We do standard ALS but in the dual algebra, then extract
    the real parts and check if they alone form a valid decomposition.
    
    Simplified approach: We use the dual number extension primarily
    as a regularization / landscape-shaping technique. After convergence,
    we extract the real parts and re-run a few standard ALS steps.
    
    Args:
        T: Target tensor (real).
        R: Target rank.
        max_iter: Max ALS iterations.
        tol: Convergence tolerance.
        reg: Regularization.
        rng: RNG.
        verbose: Print progress.
    
    Returns:
        Dict with keys: U, V, W, residual, converged, iterations, method.
    """
    if rng is None:
        rng = np.random.default_rng()
    
    I, J, K = T.shape
    T_norm = norm(T)
    T_unf = [unfold(T, mode) for mode in range(3)]
    
    scale = (T_norm / R) ** (1.0 / 3.0)
    eps_scale = scale * 0.1  # epsilon parts are small perturbations
    
    # Initialize dual factors: U = U_r + U_e·ε, etc.
    U_r = rng.standard_normal((I, R)) * scale
    U_e = rng.standard_normal((I, R)) * eps_scale
    V_r = rng.standard_normal((J, R)) * scale
    V_e = rng.standard_normal((J, R)) * eps_scale
    W_r = rng.standard_normal((K, R)) * scale
    W_e = rng.standard_normal((K, R)) * eps_scale
    
    best_residual = float('inf')
    best_factors = (U_r.copy(), V_r.copy(), W_r.copy())
    converged = False
    
    for it in range(max_iter):
        try:
            # ── Update U (dual) ───────────────────────────────────────
            # Gram: (V^T V) * (W^T W) in dual numbers
            VtV_r, VtV_e = V_r.T @ V_r, V_r.T @ V_e + V_e.T @ V_r
            WtW_r, WtW_e = W_r.T @ W_r, W_r.T @ W_e + W_e.T @ W_r
            gram_r, gram_e = dual_hadamard(VtV_r, VtV_e, WtW_r, WtW_e)
            gram_r += reg * np.eye(R)
            
            # RHS: T_(0) @ (W ⊙ V) — but T has no epsilon part
            kr_WV_r, kr_WV_e = dual_khatri_rao(W_r, W_e, V_r, V_e)
            rhs_r = T_unf[0] @ kr_WV_r
            rhs_e = T_unf[0] @ kr_WV_e  # T_eps = 0, so only real T @ eps KR
            
            # Solve dual system: (gram_r + gram_e ε)(U_r + U_e ε)^T = (rhs_r + rhs_e ε)^T
            # Real part: gram_r @ U_r^T = rhs_r^T
            # Eps part:  gram_r @ U_e^T + gram_e @ U_r^T = rhs_e^T
            #         => U_e^T = gram_r^{-1} @ (rhs_e^T - gram_e @ U_r^T)
            U_r = solve(gram_r.T, rhs_r.T).T
            U_e = solve(gram_r.T, (rhs_e - U_r @ gram_e).T).T
            
            # ── Update V (dual) ───────────────────────────────────────
            UtU_r, UtU_e = U_r.T @ U_r, U_r.T @ U_e + U_e.T @ U_r
            gram_r_v, gram_e_v = dual_hadamard(UtU_r, UtU_e, WtW_r, WtW_e)
            gram_r_v += reg * np.eye(R)
            
            kr_WU_r, kr_WU_e = dual_khatri_rao(W_r, W_e, U_r, U_e)
            rhs_r_v = T_unf[1] @ kr_WU_r
            rhs_e_v = T_unf[1] @ kr_WU_e
            
            V_r = solve(gram_r_v.T, rhs_r_v.T).T
            V_e = solve(gram_r_v.T, (rhs_e_v - V_r @ gram_e_v).T).T
            
            # ── Update W (dual) ───────────────────────────────────────
            VtV_r_new, VtV_e_new = V_r.T @ V_r, V_r.T @ V_e + V_e.T @ V_r
            gram_r_w, gram_e_w = dual_hadamard(UtU_r, UtU_e, VtV_r_new, VtV_e_new)
            gram_r_w += reg * np.eye(R)
            
            kr_VU_r, kr_VU_e = dual_khatri_rao(V_r, V_e, U_r, U_e)
            rhs_r_w = T_unf[2] @ kr_VU_r
            rhs_e_w = T_unf[2] @ kr_VU_e
            
            W_r = solve(gram_r_w.T, rhs_r_w.T).T
            W_e = solve(gram_r_w.T, (rhs_e_w - W_r @ gram_e_w).T).T
            
        except np.linalg.LinAlgError:
            reg *= 10
            continue
        
        # Evaluate residual using REAL parts only (the decomposition we care about)
        residual = compute_residual(T, U_r, V_r, W_r)
        
        if residual < best_residual:
            best_residual = residual
            best_factors = (U_r.copy(), V_r.copy(), W_r.copy())
        
        if verbose and (it % 50 == 0):
            print(f"    [dual] Iter {it:4d}: residual = {residual:.6e}")
        
        if residual < tol:
            converged = True
            if verbose:
                print(f"    [dual] ✓ Converged at iter {it}: residual = {residual:.6e}")
            break
        
        if not np.isfinite(residual):
            break
    
    # Phase 2: Polish the real parts with standard ALS
    U_best, V_best, W_best = best_factors
    if best_residual < T_norm * 0.5:  # Only polish if we're in a reasonable basin
        polish_result = als_decompose(T, R, max_iter=50, tol=tol, reg=reg,
                                       rng=rng, verbose=False)
        # Use initial point from dual search
        T_unf_polish = [unfold(T, mode) for mode in range(3)]
        U_p, V_p, W_p = U_best, V_best, W_best
        for _ in range(50):
            try:
                U_p, V_p, W_p = als_step(T_unf_polish, U_p, V_p, W_p, reg=reg)
            except np.linalg.LinAlgError:
                break
            res = compute_residual(T, U_p, V_p, W_p)
            if res < best_residual:
                best_residual = res
                U_best, V_best, W_best = U_p.copy(), V_p.copy(), W_p.copy()
            if res < tol:
                converged = True
                break
    
    return {
        "U": U_best,
        "V": V_best,
        "W": W_best,
        "residual": float(best_residual),
        "converged": converged,
        "iterations": it + 1 if 'it' in dir() else 0,
        "method": "dual_als",
    }


# ══════════════════════════════════════════════════════════════════════════
#  MAIN SEARCH LOOP
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class RankResult:
    """Results for a single rank value."""
    rank: int
    best_residual: float
    converged: bool
    best_restart: int
    method: str  # "standard_als" or "dual_als"
    total_iterations: int
    wall_time_s: float
    all_residuals: list[float] = field(default_factory=list)


def run_search(config: SearchConfig) -> dict[str, Any]:
    """Run the full tensor rank search.
    
    For each rank R from max_rank down to min_rank:
      1. Run num_restarts random restarts of standard ALS
      2. If search_dual, also run num_restarts of dual-ALS
      3. Record the best result
    
    Returns:
        Complete results dictionary.
    """
    print("=" * 70)
    print("  Tensor Rank Search via ALS")
    print(f"  Target: ⟨{config.n},{config.n},{config.n}⟩ matrix multiplication tensor")
    print(f"  Tensor shape: {config.n**2}×{config.n**2}×{config.n**2}")
    print(f"  Rank range: [{config.min_rank}, {config.max_rank}]")
    print(f"  Restarts per rank: {config.num_restarts}")
    print(f"  Max iterations: {config.max_iterations}")
    print(f"  Dual number search: {config.search_dual}")
    print("=" * 70)
    
    # Build the tensor
    print("\n▸ Building ⟨4,4,4⟩ matrix multiplication tensor...")
    T = build_matmul_tensor(config.n)
    n2 = config.n ** 2
    print(f"  Shape: {T.shape}, nnz: {np.count_nonzero(T)}, "
          f"Frobenius norm: {norm(T):.6f}")
    verify_matmul_tensor(T, config.n)
    
    # Results storage
    results_by_rank: dict[int, RankResult] = {}
    best_overall_rank = config.max_rank
    best_overall_residual = float('inf')
    search_start = time.time()
    
    # ── Search loop ───────────────────────────────────────────────────
    for R in range(config.max_rank, config.min_rank - 1, -1):
        rank_start = time.time()
        print(f"\n{'─' * 60}")
        print(f"  Searching rank R = {R}")
        print(f"{'─' * 60}")
        
        best_res_for_rank = float('inf')
        best_restart_for_rank = -1
        best_method_for_rank = "standard_als"
        all_residuals = []
        total_iters = 0
        
        # ── Standard ALS restarts ─────────────────────────────────────
        for restart in range(config.num_restarts):
            rng = np.random.default_rng(config.seed + R * 1000 + restart)
            
            result = als_decompose(
                T, R,
                max_iter=config.max_iterations,
                tol=config.convergence_tol,
                reg=1e-12,
                rng=rng,
                verbose=(restart == 0),  # verbose only for first restart
            )
            
            res = result["residual"]
            all_residuals.append(res)
            total_iters += result["iterations"]
            
            print(f"  [ALS] Restart {restart}: residual = {res:.6e} "
                  f"({'✓ CONVERGED' if result['converged'] else '✗'})")
            
            if res < best_res_for_rank:
                best_res_for_rank = res
                best_restart_for_rank = restart
                best_method_for_rank = "standard_als"
            
            # Early exit if converged
            if result["converged"]:
                break
        
        # ── Dual-ALS restarts ─────────────────────────────────────────
        if config.search_dual:
            for restart in range(config.num_restarts):
                rng = np.random.default_rng(config.seed + R * 1000 + restart + 500)
                
                result = dual_als_decompose(
                    T, R,
                    max_iter=config.max_iterations,
                    tol=config.convergence_tol,
                    reg=1e-12,
                    rng=rng,
                    verbose=(restart == 0),
                )
                
                res = result["residual"]
                all_residuals.append(res)
                total_iters += result["iterations"]
                
                print(f"  [Dual] Restart {restart}: residual = {res:.6e} "
                      f"({'✓ CONVERGED' if result['converged'] else '✗'})")
                
                if res < best_res_for_rank:
                    best_res_for_rank = res
                    best_restart_for_rank = restart
                    best_method_for_rank = "dual_als"
                
                if result["converged"]:
                    break
        
        rank_time = time.time() - rank_start
        rank_result = RankResult(
            rank=R,
            best_residual=best_res_for_rank,
            converged=best_res_for_rank < config.convergence_tol,
            best_restart=best_restart_for_rank,
            method=best_method_for_rank,
            total_iterations=total_iters,
            wall_time_s=rank_time,
            all_residuals=all_residuals,
        )
        results_by_rank[R] = rank_result
        
        print(f"\n  ► Rank {R}: best residual = {best_res_for_rank:.6e} "
              f"via {best_method_for_rank} "
              f"({'CONVERGED' if rank_result.converged else 'NOT CONVERGED'}) "
              f"[{rank_time:.1f}s]")
        
        # Track overall best
        if rank_result.converged and R < best_overall_rank:
            best_overall_rank = R
            best_overall_residual = best_res_for_rank
            print(f"  ★ NEW BEST RANK: {R} (residual = {best_res_for_rank:.6e})")
        
        # If we can't converge at this rank, skip lower ranks
        # (ALS won't find lower rank if it can't find this one)
        # But we continue for a bit to explore the landscape
        if not rank_result.converged and R < config.max_rank - 5:
            # Check if we're making progress
            if best_res_for_rank > norm(T) * 0.5:
                print(f"\n  ⊘ Residual too large at rank {R}, "
                      f"stopping search.")
                break
    
    total_time = time.time() - search_start
    
    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  SEARCH COMPLETE")
    print("=" * 70)
    print(f"  Total time: {total_time:.1f}s")
    print(f"  Best converged rank: {best_overall_rank}")
    print(f"  Best residual: {best_overall_residual:.6e}")
    print(f"  AlphaEvolve comparison: R=48 (current best)")
    
    if best_overall_rank < 48:
        print(f"  🎉 IMPROVEMENT FOUND: rank {best_overall_rank} < 48!")
    elif best_overall_rank == 48:
        print(f"  ≡ Matched AlphaEvolve: rank {best_overall_rank} = 48")
    else:
        print(f"  ▽ Could not match AlphaEvolve: best rank {best_overall_rank} > 48")
    
    # Build output dict
    output = {
        "search_config": {
            "n": config.n,
            "tensor_shape": [config.n**2] * 3,
            "max_rank": config.max_rank,
            "min_rank": config.min_rank,
            "max_iterations": config.max_iterations,
            "num_restarts": config.num_restarts,
            "convergence_tol": config.convergence_tol,
            "search_dual": config.search_dual,
            "seed": config.seed,
        },
        "tensor_info": {
            "name": f"⟨{config.n},{config.n},{config.n}⟩ matrix multiplication",
            "shape": list(T.shape),
            "frobenius_norm": float(norm(T)),
            "nnz": int(np.count_nonzero(T)),
            "known_rank": 48,
            "known_rank_source": "AlphaEvolve (DeepMind 2025)",
        },
        "results_by_rank": {
            str(R): {
                "rank": r.rank,
                "best_residual": r.best_residual,
                "converged": r.converged,
                "best_restart": r.best_restart,
                "method": r.method,
                "total_iterations": r.total_iterations,
                "wall_time_s": round(r.wall_time_s, 3),
                "all_residuals": r.all_residuals,
            }
            for R, r in sorted(results_by_rank.items(), reverse=True)
        },
        "summary": {
            "best_converged_rank": best_overall_rank,
            "best_residual": best_overall_residual,
            "total_time_s": round(total_time, 3),
            "ranks_tested": len(results_by_rank),
            "improvement_over_alpha_evolve": best_overall_rank < 48,
            "matched_alpha_evolve": best_overall_rank == 48,
        },
        "comparison": {
            "alpha_evolve_rank": 48,
            "our_best_rank": best_overall_rank,
            "delta": 48 - best_overall_rank,
            "note": (
                "ALS is a local optimization method and typically cannot "
                "find globally optimal decompositions for large tensors. "
                "The AlphaEvolve result uses evolutionary search with "
                "neural network guidance, which explores a much larger "
                "search space."
            ),
        },
    }
    
    return output


# ══════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════

def main():
    """Main entry point."""
    # Determine output directory
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    output_dir = project_root / "output" / "tensor_rank_search"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    config = SearchConfig(
        n=4,
        max_rank=48,
        min_rank=26,
        max_iterations=200,
        num_restarts=5,
        convergence_tol=1e-8,
        success_tol=1e-6,
        seed=42,
        search_dual=True,
        output_dir=str(output_dir),
    )
    
    results = run_search(config)
    
    # Save results
    output_path = output_dir / "als_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n  Results saved to: {output_path}")
    print(f"\n  Done.")


if __name__ == "__main__":
    main()
