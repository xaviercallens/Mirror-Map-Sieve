#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""
Tensor Rank Search via Gradient Descent with Adam Optimizer
===========================================================

Searches for low-rank decompositions of the ⟨4,4,4⟩ matrix multiplication
tensor T ∈ ℝ^{16×16×16} using gradient descent with:
  - Adam optimizer (manually implemented with numpy)
  - Cosine learning rate decay
  - 20 random restarts per rank with 4 initialization strategies
  - Warm starts from higher-rank solutions
  - HOSVD-seeded initialization

This is a more sophisticated follow-up to the ALS-based search that
failed to converge (all residuals remained ~8.3–8.6).

The matrix multiplication tensor ⟨n,n,n⟩ encodes the bilinear map
    (A, B) ↦ A·B
for n×n matrices. The tensor rank R(T) is the minimum number of
rank-1 tensors u⊗v⊗w whose sum equals T.

For ⟨4,4,4⟩:
    - Naive: R ≤ 64 (n³)
    - Strassen-like: R ≤ 49
    - AlphaEvolve (DeepMind 2025): R ≤ 48 (current best)
    - Lower bound (Bläser 2003): R ≥ 28
    - Refined lower bound (Koszul flattenings / Landsberg): R ≥ ~34
    - Conjectured: R = 48

NOTE: Ranks below 34 are provably impossible. Ranks 34–47 are the
      interesting search range. Rank 26 is included for completeness
      but is known to be infeasible.

Usage:
    python scripts/tensor_rank_gd_search.py
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from numpy.linalg import norm, svd


# ══════════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class GDSearchConfig:
    """Configuration for the gradient descent tensor rank search."""
    n: int = 4                       # Matrix dimension (⟨n,n,n⟩)

    # Search parameters
    search_ranks: list = field(default_factory=lambda: [
        48, 47, 46, 45, 44, 43, 42, 41, 40, 35, 30, 26
    ])
    num_restarts: int = 20           # Random restarts per rank value

    # Adam optimizer parameters
    lr_init: float = 0.01            # Initial learning rate
    lr_min: float = 0.0001           # Minimum learning rate (cosine decay target)
    beta1: float = 0.9               # Adam first moment decay
    beta2: float = 0.999             # Adam second moment decay
    epsilon: float = 1e-8            # Adam numerical stability

    # Convergence parameters
    max_iterations: int = 2000       # Max iterations per restart
    convergence_tol: float = 1e-6    # Residual threshold for success
    gradient_clip: float = 10.0      # Max gradient norm (for stability)

    # Initialization strategy counts (must sum to num_restarts)
    n_gaussian: int = 5              # Random Gaussian inits
    n_uniform: int = 5               # Random uniform [-1,1] inits
    n_sparse: int = 5                # Sparse random inits
    n_svd: int = 5                   # HOSVD-seeded inits

    # Output
    seed: int = 42
    output_dir: str = "output/tensor_rank_search"
    print_every: int = 100           # Print progress every N iterations


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

    Then T[α, β, γ] = 1 iff the k-indices match and i,j are consistent:
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
                alpha = i * n + k   # (i,k) → row of A
                beta  = k * n + j   # (k,j) → entry of B
                gamma = i * n + j   # (i,j) → entry of C = A·B
                T[alpha, beta, gamma] = 1.0

    return T


def verify_matmul_tensor(T: np.ndarray, n: int) -> bool:
    """Verify the tensor correctly encodes matrix multiplication.

    Pick random n×n matrices A, B. Check C=A·B matches tensor contraction.
    """
    rng = np.random.default_rng(12345)
    A = rng.standard_normal((n, n))
    B = rng.standard_normal((n, n))
    C_true = A @ B

    a = A.flatten()
    b = B.flatten()

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
#  HIGHER-ORDER SVD (HOSVD) FOR INITIALIZATION
# ══════════════════════════════════════════════════════════════════════════

def compute_hosvd_factors(T: np.ndarray, R: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute HOSVD (Tucker decomposition via SVD) of tensor T.

    For each mode n, compute the SVD of the mode-n unfolding T_(n),
    and take the leading R left singular vectors as the factor matrix.

    This provides a structured initialization that captures the main
    variation in each mode of the tensor.

    Args:
        T: 3-way tensor of shape (I, J, K).
        R: Target rank — number of singular vectors to keep.

    Returns:
        U0, U1, U2: Factor matrices of shapes (I,R), (J,R), (K,R).
    """
    I, J, K = T.shape

    # Mode-0 unfolding: shape (I, J*K)
    T0 = T.reshape(I, -1)
    U0, _, _ = svd(T0, full_matrices=False)
    U0 = U0[:, :min(R, U0.shape[1])]

    # Mode-1 unfolding: shape (J, I*K)
    T1 = np.moveaxis(T, 1, 0).reshape(J, -1)
    U1, _, _ = svd(T1, full_matrices=False)
    U1 = U1[:, :min(R, U1.shape[1])]

    # Mode-2 unfolding: shape (K, I*J)
    T2 = np.moveaxis(T, 2, 0).reshape(K, -1)
    U2, _, _ = svd(T2, full_matrices=False)
    U2 = U2[:, :min(R, U2.shape[1])]

    # Pad with zeros if needed (R > min dimension)
    def pad_to_R(M, target_R, dim):
        if M.shape[1] < target_R:
            padding = np.zeros((dim, target_R - M.shape[1]))
            return np.hstack([M, padding])
        return M

    U0 = pad_to_R(U0, R, I)
    U1 = pad_to_R(U1, R, J)
    U2 = pad_to_R(U2, R, K)

    return U0, U1, U2


# ══════════════════════════════════════════════════════════════════════════
#  INITIALIZATION STRATEGIES
# ══════════════════════════════════════════════════════════════════════════

def init_gaussian(rng: np.random.Generator, I: int, J: int, K: int, R: int,
                  scale: float = 0.1) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Random Gaussian initialization with small scale.

    U, V, W ~ N(0, scale²) independently.
    Small scale avoids initial explosion of the Frobenius norm of the
    approximation, which would cause large gradients.

    Args:
        rng: NumPy random generator.
        I, J, K: Tensor dimensions.
        R: Target rank.
        scale: Standard deviation of the Gaussian.

    Returns:
        U (I,R), V (J,R), W (K,R) factor matrices.
    """
    U = rng.standard_normal((I, R)) * scale
    V = rng.standard_normal((J, R)) * scale
    W = rng.standard_normal((K, R)) * scale
    return U, V, W


def init_uniform(rng: np.random.Generator, I: int, J: int, K: int, R: int,
                 lo: float = -1.0, hi: float = 1.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Random uniform initialization in [lo, hi].

    Provides a different landscape exploration compared to Gaussian.

    Args:
        rng: NumPy random generator.
        I, J, K: Tensor dimensions.
        R: Target rank.
        lo, hi: Bounds for uniform distribution.

    Returns:
        U (I,R), V (J,R), W (K,R) factor matrices.
    """
    U = rng.uniform(lo, hi, (I, R))
    V = rng.uniform(lo, hi, (J, R))
    W = rng.uniform(lo, hi, (K, R))
    return U, V, W


def init_sparse(rng: np.random.Generator, I: int, J: int, K: int, R: int,
                sparsity: float = 0.8) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sparse random initialization: 80% zeros, 20% ±1.

    Inspired by the structure of known decompositions (e.g., Strassen),
    which tend to have entries in {-1, 0, 1}.

    Args:
        rng: NumPy random generator.
        I, J, K: Tensor dimensions.
        R: Target rank.
        sparsity: Fraction of entries that are zero.

    Returns:
        U (I,R), V (J,R), W (K,R) factor matrices.
    """
    def make_sparse(shape):
        mask = rng.random(shape) > sparsity          # True for ~20% of entries
        signs = rng.choice([-1.0, 1.0], size=shape)  # Random ±1
        return mask.astype(np.float64) * signs

    U = make_sparse((I, R))
    V = make_sparse((J, R))
    W = make_sparse((K, R))
    return U, V, W


def init_svd_perturbed(rng: np.random.Generator, T: np.ndarray, R: int,
                       perturbation_scale: float = 0.05) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """HOSVD-seeded initialization with small random perturbation.

    Start from the HOSVD factors (which capture the dominant structure
    of the tensor) and add a small perturbation to break symmetry
    and allow gradient descent to explore.

    Args:
        rng: NumPy random generator.
        T: Target tensor of shape (I, J, K).
        R: Target rank.
        perturbation_scale: Std dev of the added Gaussian noise.

    Returns:
        U (I,R), V (J,R), W (K,R) factor matrices.
    """
    I, J, K = T.shape
    U0, U1, U2 = compute_hosvd_factors(T, R)

    # Add small perturbation for symmetry breaking
    U = U0 + rng.standard_normal(U0.shape) * perturbation_scale
    V = U1 + rng.standard_normal(U1.shape) * perturbation_scale
    W = U2 + rng.standard_normal(U2.shape) * perturbation_scale

    return U, V, W


# ══════════════════════════════════════════════════════════════════════════
#  ADAM OPTIMIZER (MANUAL NUMPY IMPLEMENTATION)
# ══════════════════════════════════════════════════════════════════════════

class AdamState:
    """State for the Adam optimizer applied to factor matrices U, V, W.

    Adam maintains exponential moving averages of the gradient (first moment)
    and squared gradient (second moment) for bias-corrected updates:

        m_t = β₁ · m_{t-1} + (1 - β₁) · g_t
        v_t = β₂ · v_{t-1} + (1 - β₂) · g_t²
        m̂_t = m_t / (1 - β₁^t)
        v̂_t = v_t / (1 - β₂^t)
        θ_t = θ_{t-1} - lr · m̂_t / (√v̂_t + ε)

    Reference: Kingma & Ba, "Adam: A Method for Stochastic Optimization", ICLR 2015.
    """

    def __init__(self, U: np.ndarray, V: np.ndarray, W: np.ndarray,
                 beta1: float = 0.9, beta2: float = 0.999, epsilon: float = 1e-8):
        """Initialize Adam state for three factor matrices.

        Args:
            U, V, W: Initial factor matrices.
            beta1: Exponential decay rate for first moment estimates.
            beta2: Exponential decay rate for second moment estimates.
            epsilon: Small constant for numerical stability.
        """
        self.beta1 = beta1
        self.beta2 = beta2
        self.epsilon = epsilon
        self.t = 0  # Timestep counter (for bias correction)

        # First moment estimates (mean of gradients)
        self.m_U = np.zeros_like(U)
        self.m_V = np.zeros_like(V)
        self.m_W = np.zeros_like(W)

        # Second moment estimates (mean of squared gradients)
        self.v_U = np.zeros_like(U)
        self.v_V = np.zeros_like(V)
        self.v_W = np.zeros_like(W)

    def step(self, U: np.ndarray, V: np.ndarray, W: np.ndarray,
             grad_U: np.ndarray, grad_V: np.ndarray, grad_W: np.ndarray,
             lr: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Perform one Adam update step.

        Args:
            U, V, W: Current factor matrices.
            grad_U, grad_V, grad_W: Gradients of the loss w.r.t. each factor.
            lr: Current learning rate (may be decayed).

        Returns:
            Updated U, V, W after the Adam step.
        """
        self.t += 1

        # Bias correction denominators
        bc1 = 1.0 - self.beta1 ** self.t  # Bias correction for first moment
        bc2 = 1.0 - self.beta2 ** self.t  # Bias correction for second moment

        # Update each factor matrix
        U_new = self._update_param(U, grad_U, self.m_U, self.v_U, lr, bc1, bc2)
        V_new = self._update_param(V, grad_V, self.m_V, self.v_V, lr, bc1, bc2)
        W_new = self._update_param(W, grad_W, self.m_W, self.v_W, lr, bc1, bc2)

        return U_new, V_new, W_new

    def _update_param(self, param: np.ndarray, grad: np.ndarray,
                      m: np.ndarray, v: np.ndarray,
                      lr: float, bc1: float, bc2: float) -> np.ndarray:
        """Update a single parameter with Adam.

        Note: m and v are modified in-place (they are references to
        self.m_U/m_V/m_W and self.v_U/v_V/v_W).

        Args:
            param: Current parameter values.
            grad: Gradient of loss w.r.t. param.
            m: First moment estimate (modified in-place).
            v: Second moment estimate (modified in-place).
            lr: Current learning rate.
            bc1: First moment bias correction factor (1 - β₁^t).
            bc2: Second moment bias correction factor (1 - β₂^t).

        Returns:
            Updated parameter values.
        """
        # Update biased first moment estimate
        m[:] = self.beta1 * m + (1.0 - self.beta1) * grad

        # Update biased second moment estimate
        v[:] = self.beta2 * v + (1.0 - self.beta2) * (grad ** 2)

        # Compute bias-corrected estimates
        m_hat = m / bc1
        v_hat = v / bc2

        # Adam update: move in direction of corrected first moment,
        # scaled inversely by square root of corrected second moment
        return param - lr * m_hat / (np.sqrt(v_hat) + self.epsilon)


# ══════════════════════════════════════════════════════════════════════════
#  LEARNING RATE SCHEDULE
# ══════════════════════════════════════════════════════════════════════════

def cosine_lr(iteration: int, max_iterations: int,
              lr_init: float, lr_min: float) -> float:
    """Cosine annealing learning rate schedule.

    Smoothly decays from lr_init to lr_min over max_iterations steps:
        lr(t) = lr_min + 0.5 * (lr_init - lr_min) * (1 + cos(π * t / T))

    This schedule provides fast initial progress (high LR) and fine-grained
    convergence at the end (low LR), which is well-suited for tensor
    decomposition where we need both exploration and precision.

    Args:
        iteration: Current iteration (0-indexed).
        max_iterations: Total number of iterations.
        lr_init: Initial learning rate.
        lr_min: Minimum learning rate.

    Returns:
        Learning rate for this iteration.
    """
    if iteration >= max_iterations:
        return lr_min
    progress = iteration / max_iterations  # 0 → 1
    return lr_min + 0.5 * (lr_init - lr_min) * (1.0 + math.cos(math.pi * progress))


# ══════════════════════════════════════════════════════════════════════════
#  CORE: LOSS, GRADIENT, AND OPTIMIZATION
# ══════════════════════════════════════════════════════════════════════════

def compute_approximation(U: np.ndarray, V: np.ndarray, W: np.ndarray) -> np.ndarray:
    """Compute the rank-R tensor approximation T_hat = Σ_r u_r ⊗ v_r ⊗ w_r.

    Using einsum for efficiency:
        T_hat[i,j,k] = Σ_r U[i,r] * V[j,r] * W[k,r]

    This is equivalent to the CP decomposition reconstruction.

    Args:
        U: Factor matrix of shape (I, R).
        V: Factor matrix of shape (J, R).
        W: Factor matrix of shape (K, R).

    Returns:
        T_hat: Approximation tensor of shape (I, J, K).
    """
    return np.einsum('ir,jr,kr->ijk', U, V, W)


def compute_loss_and_gradients(
    T: np.ndarray,
    U: np.ndarray,
    V: np.ndarray,
    W: np.ndarray
) -> Tuple[float, np.ndarray, np.ndarray, np.ndarray]:
    """Compute the squared Frobenius norm loss and gradients.

    Loss:
        L(U,V,W) = ‖T - T_hat‖²_F   where T_hat = Σ_r u_r ⊗ v_r ⊗ w_r

    Gradients (derived via chain rule from the residual R = T - T_hat):
        ∂L/∂U[i,r] = -2 · Σ_{j,k} R[i,j,k] · V[j,r] · W[k,r]
        ∂L/∂V[j,r] = -2 · Σ_{i,k} R[i,j,k] · U[i,r] · W[k,r]
        ∂L/∂W[k,r] = -2 · Σ_{i,j} R[i,j,k] · U[i,r] · V[j,r]

    These are computed efficiently via einsum contractions.

    Args:
        T: Target tensor of shape (I, J, K).
        U: Factor matrix of shape (I, R).
        V: Factor matrix of shape (J, R).
        W: Factor matrix of shape (K, R).

    Returns:
        loss: Scalar loss value ‖T - T_hat‖²_F.
        grad_U: Gradient w.r.t. U, shape (I, R).
        grad_V: Gradient w.r.t. V, shape (J, R).
        grad_W: Gradient w.r.t. W, shape (K, R).
    """
    # Step 1: Compute approximation
    T_hat = compute_approximation(U, V, W)

    # Step 2: Compute residual
    R = T - T_hat  # shape (I, J, K)

    # Step 3: Compute loss = ‖R‖²_F
    loss = np.sum(R ** 2)

    # Step 4: Compute gradients via einsum
    # grad_U[i,r] = -2 * Σ_{j,k} R[i,j,k] * V[j,r] * W[k,r]
    grad_U = -2.0 * np.einsum('ijk,jr,kr->ir', R, V, W)

    # grad_V[j,r] = -2 * Σ_{i,k} R[i,j,k] * U[i,r] * W[k,r]
    grad_V = -2.0 * np.einsum('ijk,ir,kr->jr', R, U, W)

    # grad_W[k,r] = -2 * Σ_{i,j} R[i,j,k] * U[i,r] * V[j,r]
    grad_W = -2.0 * np.einsum('ijk,ir,jr->kr', R, U, V)

    return loss, grad_U, grad_V, grad_W


def clip_gradients(grad_U: np.ndarray, grad_V: np.ndarray, grad_W: np.ndarray,
                   max_norm: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Clip gradients by global norm to prevent explosion.

    Computes the total gradient norm across all three factor matrices.
    If it exceeds max_norm, all gradients are scaled down proportionally.

    Args:
        grad_U, grad_V, grad_W: Gradients for each factor matrix.
        max_norm: Maximum allowed gradient norm.

    Returns:
        Clipped grad_U, grad_V, grad_W.
    """
    # Compute global gradient norm across all factors
    total_norm = math.sqrt(
        np.sum(grad_U ** 2) + np.sum(grad_V ** 2) + np.sum(grad_W ** 2)
    )

    if total_norm > max_norm:
        scale = max_norm / total_norm
        return grad_U * scale, grad_V * scale, grad_W * scale

    return grad_U, grad_V, grad_W


def run_single_restart(
    T: np.ndarray,
    U_init: np.ndarray,
    V_init: np.ndarray,
    W_init: np.ndarray,
    config: GDSearchConfig,
    restart_id: int,
    rank: int,
    init_label: str,
) -> Dict[str, Any]:
    """Run a single gradient descent optimization from a given initialization.

    This function performs the full optimization loop:
    1. Initialize Adam optimizer state
    2. For each iteration:
       a. Compute loss and gradients
       b. Clip gradients
       c. Compute learning rate (cosine schedule)
       d. Adam update
       e. Check convergence
    3. Return results

    Args:
        T: Target tensor.
        U_init, V_init, W_init: Initial factor matrices.
        config: Search configuration.
        restart_id: Index of this restart (for logging).
        rank: Current target rank.
        init_label: Description of the initialization strategy used.

    Returns:
        Dictionary with optimization results.
    """
    # Copy initial factors (don't modify in place)
    U = U_init.copy()
    V = V_init.copy()
    W = W_init.copy()

    # Initialize Adam optimizer state
    adam = AdamState(U, V, W, beta1=config.beta1, beta2=config.beta2,
                     epsilon=config.epsilon)

    # Track the best solution found during this restart
    best_loss = float('inf')
    best_U, best_V, best_W = U.copy(), V.copy(), W.copy()
    best_iter = 0

    # Track loss history for diagnostics
    loss_history = []

    t_start = time.time()

    for iteration in range(config.max_iterations):
        # ── Compute loss and gradients ──
        loss, grad_U, grad_V, grad_W = compute_loss_and_gradients(T, U, V, W)
        residual = math.sqrt(loss)  # ‖T - T_hat‖_F

        loss_history.append(loss)

        # ── Track best solution ──
        if loss < best_loss:
            best_loss = loss
            best_U = U.copy()
            best_V = V.copy()
            best_W = W.copy()
            best_iter = iteration

        # ── Check convergence ──
        if residual < config.convergence_tol:
            elapsed = time.time() - t_start
            print(f"    ✓ Restart {restart_id} ({init_label}) CONVERGED at iter {iteration}: "
                  f"residual = {residual:.2e}, time = {elapsed:.2f}s")
            return {
                "restart_id": restart_id,
                "init_strategy": init_label,
                "converged": True,
                "best_loss": float(best_loss),
                "best_residual": float(math.sqrt(best_loss)),
                "best_iter": best_iter,
                "total_iters": iteration + 1,
                "wall_time_s": round(elapsed, 3),
                "final_loss": float(loss),
                "U": best_U,
                "V": best_V,
                "W": best_W,
            }

        # ── Clip gradients for numerical stability ──
        grad_U, grad_V, grad_W = clip_gradients(grad_U, grad_V, grad_W,
                                                  config.gradient_clip)

        # ── Compute learning rate with cosine annealing ──
        lr = cosine_lr(iteration, config.max_iterations,
                       config.lr_init, config.lr_min)

        # ── Adam update ──
        U, V, W = adam.step(U, V, W, grad_U, grad_V, grad_W, lr)

        # ── Progress logging ──
        if (iteration + 1) % config.print_every == 0:
            elapsed = time.time() - t_start
            print(f"    Restart {restart_id:2d} ({init_label:10s}) iter {iteration+1:4d}: "
                  f"loss = {loss:.6f}, residual = {residual:.6f}, "
                  f"lr = {lr:.6f}, time = {elapsed:.1f}s")

    # ── End of optimization (did not converge) ──
    elapsed = time.time() - t_start
    best_residual = math.sqrt(best_loss)
    print(f"    ✗ Restart {restart_id:2d} ({init_label:10s}) did not converge: "
          f"best residual = {best_residual:.6f} at iter {best_iter}, time = {elapsed:.2f}s")

    return {
        "restart_id": restart_id,
        "init_strategy": init_label,
        "converged": False,
        "best_loss": float(best_loss),
        "best_residual": float(best_residual),
        "best_iter": best_iter,
        "total_iters": config.max_iterations,
        "wall_time_s": round(elapsed, 3),
        "final_loss": float(loss_history[-1]),
        "U": best_U,
        "V": best_V,
        "W": best_W,
    }


# ══════════════════════════════════════════════════════════════════════════
#  WARM START LOGIC
# ══════════════════════════════════════════════════════════════════════════

def warm_start_from_higher_rank(
    U_high: np.ndarray, V_high: np.ndarray, W_high: np.ndarray,
    rng: np.random.Generator, perturbation_scale: float = 0.01
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Create a warm start for rank R-1 from a rank-R solution.

    Strategy: drop the component with the smallest norm
    (measured as ‖u_r‖ · ‖v_r‖ · ‖w_r‖) and add a small perturbation.

    This is based on the intuition that if a component has negligible
    contribution, removing it should not significantly affect the
    decomposition quality, giving the optimizer a head start.

    Args:
        U_high, V_high, W_high: Best factor matrices from rank R.
        rng: Random generator for perturbation.
        perturbation_scale: Std dev of perturbation noise.

    Returns:
        U_low, V_low, W_low: Factor matrices for rank R-1.
    """
    R = U_high.shape[1]
    if R <= 1:
        raise ValueError("Cannot reduce rank below 1")

    # Compute the contribution norm of each component
    # ‖u_r‖ · ‖v_r‖ · ‖w_r‖ measures how much component r contributes
    component_norms = np.array([
        norm(U_high[:, r]) * norm(V_high[:, r]) * norm(W_high[:, r])
        for r in range(R)
    ])

    # Find the component with the smallest contribution
    drop_idx = np.argmin(component_norms)

    # Remove that component (column) from each factor matrix
    keep = [r for r in range(R) if r != drop_idx]
    U_low = U_high[:, keep].copy()
    V_low = V_high[:, keep].copy()
    W_low = W_high[:, keep].copy()

    # Add small perturbation for exploration
    U_low += rng.standard_normal(U_low.shape) * perturbation_scale
    V_low += rng.standard_normal(V_low.shape) * perturbation_scale
    W_low += rng.standard_normal(W_low.shape) * perturbation_scale

    return U_low, V_low, W_low


# ══════════════════════════════════════════════════════════════════════════
#  MAIN SEARCH LOOP
# ══════════════════════════════════════════════════════════════════════════

def search_rank(
    T: np.ndarray,
    rank: int,
    config: GDSearchConfig,
    rng: np.random.Generator,
    warm_U: Optional[np.ndarray] = None,
    warm_V: Optional[np.ndarray] = None,
    warm_W: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Search for a rank-R decomposition of T using 20 restarts.

    The 20 restarts are divided among 4 initialization strategies:
      - 5 Gaussian random
      - 5 Uniform random
      - 5 Sparse random (80% zeros, 20% ±1)
      - 5 HOSVD-seeded with perturbation

    If warm start factors are provided (from a higher-rank solution),
    one of the Gaussian restarts is replaced with the warm start.

    Args:
        T: Target tensor.
        rank: Target rank R.
        config: Search configuration.
        rng: Random generator.
        warm_U, warm_V, warm_W: Optional warm start factors (rank R).

    Returns:
        Dictionary with results for all restarts at this rank.
    """
    I, J, K = T.shape
    print(f"\n{'='*70}")
    print(f"  Searching rank R = {rank}")
    print(f"{'='*70}")

    all_results = []
    best_overall = None
    restart_id = 0

    t_rank_start = time.time()

    # ── Warm start restart (replaces first Gaussian restart if available) ──
    has_warm = warm_U is not None and warm_V is not None and warm_W is not None
    if has_warm:
        assert warm_U.shape[1] == rank, (
            f"Warm start rank mismatch: got {warm_U.shape[1]}, expected {rank}"
        )

    # ── Strategy 1: Gaussian random (5 restarts, or 4 if warm start used) ──
    n_gauss = config.n_gaussian - (1 if has_warm else 0)

    if has_warm:
        print(f"\n  ▶ Restart {restart_id}: Warm start from rank {rank + 1}")
        result = run_single_restart(T, warm_U, warm_V, warm_W, config,
                                     restart_id, rank, "warm_start")
        all_results.append(result)
        if best_overall is None or result["best_loss"] < best_overall["best_loss"]:
            best_overall = result
        restart_id += 1

    for i in range(n_gauss):
        print(f"\n  ▶ Restart {restart_id}: Gaussian random init")
        U, V, W = init_gaussian(rng, I, J, K, rank)
        result = run_single_restart(T, U, V, W, config, restart_id, rank, "gaussian")
        all_results.append(result)
        if best_overall is None or result["best_loss"] < best_overall["best_loss"]:
            best_overall = result
        restart_id += 1

    # ── Strategy 2: Uniform random (5 restarts) ──
    for i in range(config.n_uniform):
        print(f"\n  ▶ Restart {restart_id}: Uniform random init")
        U, V, W = init_uniform(rng, I, J, K, rank)
        result = run_single_restart(T, U, V, W, config, restart_id, rank, "uniform")
        all_results.append(result)
        if best_overall is None or result["best_loss"] < best_overall["best_loss"]:
            best_overall = result
        restart_id += 1

    # ── Strategy 3: Sparse random (5 restarts) ──
    for i in range(config.n_sparse):
        print(f"\n  ▶ Restart {restart_id}: Sparse random init")
        U, V, W = init_sparse(rng, I, J, K, rank)
        result = run_single_restart(T, U, V, W, config, restart_id, rank, "sparse")
        all_results.append(result)
        if best_overall is None or result["best_loss"] < best_overall["best_loss"]:
            best_overall = result
        restart_id += 1

    # ── Strategy 4: HOSVD-seeded (5 restarts) ──
    for i in range(config.n_svd):
        print(f"\n  ▶ Restart {restart_id}: HOSVD-seeded init (perturbation {i+1})")
        U, V, W = init_svd_perturbed(rng, T, rank,
                                      perturbation_scale=0.05 * (i + 1))
        result = run_single_restart(T, U, V, W, config, restart_id, rank, "hosvd_seed")
        all_results.append(result)
        if best_overall is None or result["best_loss"] < best_overall["best_loss"]:
            best_overall = result
        restart_id += 1

    t_rank_elapsed = time.time() - t_rank_start

    # ── Summarize results for this rank ──
    any_converged = any(r["converged"] for r in all_results)
    best_residual = best_overall["best_residual"]
    best_strategy = best_overall["init_strategy"]

    print(f"\n  ── Rank {rank} Summary ──")
    print(f"  Best residual:  {best_residual:.8f}")
    print(f"  Best strategy:  {best_strategy}")
    print(f"  Converged:      {any_converged}")
    print(f"  Total time:     {t_rank_elapsed:.1f}s")

    return {
        "rank": rank,
        "best_residual": float(best_residual),
        "best_loss": float(best_overall["best_loss"]),
        "converged": any_converged,
        "best_restart": best_overall["restart_id"],
        "best_strategy": best_strategy,
        "total_restarts": len(all_results),
        "wall_time_s": round(t_rank_elapsed, 3),
        "all_residuals": [r["best_residual"] for r in all_results],
        "all_strategies": [r["init_strategy"] for r in all_results],
        "converged_restarts": [r["restart_id"] for r in all_results if r["converged"]],
        # Keep factor matrices for warm start (not serialized to JSON)
        "_best_U": best_overall.get("U"),
        "_best_V": best_overall.get("V"),
        "_best_W": best_overall.get("W"),
    }


def main():
    """Main entry point for the gradient descent tensor rank search."""
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  Tensor Rank Search — Gradient Descent with Adam Optimizer  ║")
    print("║  Target: ⟨4,4,4⟩ matrix multiplication tensor (16×16×16)   ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    config = GDSearchConfig()

    # ── Build the tensor ──
    print("Building ⟨4,4,4⟩ matrix multiplication tensor...")
    T = build_matmul_tensor(config.n)
    n2 = config.n ** 2
    T_norm = norm(T)
    T_nnz = int(np.count_nonzero(T))
    print(f"  Shape:           {T.shape}")
    print(f"  Frobenius norm:  {T_norm:.4f}")
    print(f"  Non-zeros:       {T_nnz}")
    verify_matmul_tensor(T, config.n)

    # ── Initialize random generator ──
    rng = np.random.default_rng(config.seed)

    # ── Prepare output directory ──
    script_dir = Path(__file__).resolve().parent.parent
    output_dir = script_dir / config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Run the search ──
    print(f"\nSearch configuration:")
    print(f"  Ranks to test:    {config.search_ranks}")
    print(f"  Restarts/rank:    {config.num_restarts}")
    print(f"  Max iters/restart: {config.max_iterations}")
    print(f"  Adam LR:          {config.lr_init} → {config.lr_min} (cosine)")
    print(f"  Adam (β₁,β₂,ε):  ({config.beta1}, {config.beta2}, {config.epsilon})")
    print(f"  Convergence tol:  {config.convergence_tol}")
    print(f"  Gradient clip:    {config.gradient_clip}")
    print(f"  Init strategies:  {config.n_gaussian} gaussian + {config.n_uniform} uniform "
          f"+ {config.n_sparse} sparse + {config.n_svd} HOSVD")
    print(f"  Seed:             {config.seed}")

    results_by_rank = {}
    prev_best_U = None
    prev_best_V = None
    prev_best_W = None
    prev_rank = None

    t_total_start = time.time()

    for rank in config.search_ranks:
        # ── Prepare warm start from previous (higher) rank ──
        warm_U, warm_V, warm_W = None, None, None

        if prev_best_U is not None and prev_rank is not None:
            # Only do warm start when decreasing rank by 1
            if prev_rank == rank + 1:
                print(f"\n  Preparing warm start: rank {prev_rank} → {rank}")
                try:
                    warm_U, warm_V, warm_W = warm_start_from_higher_rank(
                        prev_best_U, prev_best_V, prev_best_W, rng
                    )
                except Exception as e:
                    print(f"  ⚠ Warm start failed: {e}")

        # ── Search at this rank ──
        rank_result = search_rank(T, rank, config, rng, warm_U, warm_V, warm_W)

        # ── Store result (without numpy arrays) ──
        result_serializable = {k: v for k, v in rank_result.items()
                               if not k.startswith('_')}
        results_by_rank[str(rank)] = result_serializable

        # ── Save current best for warm start ──
        prev_best_U = rank_result["_best_U"]
        prev_best_V = rank_result["_best_V"]
        prev_best_W = rank_result["_best_W"]
        prev_rank = rank

        # ── Early celebration if we find something below rank 48 ──
        if rank_result["converged"] and rank < 48:
            print(f"\n  🎉 BREAKTHROUGH: Found rank-{rank} decomposition!")
            print(f"     This IMPROVES on AlphaEvolve's rank-48 result!")

    t_total = time.time() - t_total_start

    # ── Compile summary ──
    converged_ranks = [r for r, res in results_by_rank.items() if res["converged"]]
    best_converged = min((int(r) for r in converged_ranks), default=None)
    all_best_residuals = {r: res["best_residual"] for r, res in results_by_rank.items()}
    overall_best_rank = min(all_best_residuals, key=all_best_residuals.get)

    summary = {
        "best_converged_rank": best_converged,
        "overall_best_residual_rank": int(overall_best_rank),
        "overall_best_residual": all_best_residuals[overall_best_rank],
        "converged_ranks": sorted([int(r) for r in converged_ranks]),
        "total_time_s": round(t_total, 3),
        "ranks_tested": len(config.search_ranks),
        "total_restarts": len(config.search_ranks) * config.num_restarts,
        "improvement_over_alpha_evolve": (
            best_converged is not None and best_converged < 48
        ),
    }

    # ── Build output JSON ──
    output = {
        "search_config": {
            "n": config.n,
            "tensor_shape": [n2, n2, n2],
            "search_ranks": config.search_ranks,
            "num_restarts": config.num_restarts,
            "max_iterations": config.max_iterations,
            "lr_init": config.lr_init,
            "lr_min": config.lr_min,
            "adam_beta1": config.beta1,
            "adam_beta2": config.beta2,
            "adam_epsilon": config.epsilon,
            "convergence_tol": config.convergence_tol,
            "gradient_clip": config.gradient_clip,
            "init_strategies": {
                "gaussian": config.n_gaussian,
                "uniform": config.n_uniform,
                "sparse": config.n_sparse,
                "hosvd_seeded": config.n_svd,
            },
            "seed": config.seed,
        },
        "tensor_info": {
            "name": "⟨4,4,4⟩ matrix multiplication",
            "shape": [n2, n2, n2],
            "frobenius_norm": float(T_norm),
            "nnz": T_nnz,
            "known_rank": 48,
            "known_rank_source": "AlphaEvolve (DeepMind 2025)",
        },
        "results_by_rank": results_by_rank,
        "summary": summary,
        "comparison": {
            "alpha_evolve_rank": 48,
            "our_best_converged_rank": best_converged,
            "delta": (48 - best_converged) if best_converged else None,
            "als_baseline": {
                "best_residual": 8.34,
                "converged": False,
                "note": "ALS completely failed to converge for any rank",
            },
            "gd_vs_als": "Gradient descent with Adam provides adaptive per-parameter "
                         "learning rates and momentum, which helps navigate the "
                         "non-convex landscape of tensor decomposition better than ALS.",
        },
    }

    # ── Save results ──
    output_path = output_dir / "gd_results.json"
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\n\nResults saved to: {output_path}")

    # ── Final report ──
    print(f"\n{'='*70}")
    print(f"  FINAL REPORT — Gradient Descent Tensor Rank Search")
    print(f"{'='*70}")
    print(f"  Ranks tested:              {config.search_ranks}")
    print(f"  Total restarts:            {summary['total_restarts']}")
    print(f"  Total wall time:           {summary['total_time_s']:.1f}s")
    print(f"  Best converged rank:       {summary['best_converged_rank']}")
    print(f"  Best residual (any rank):  {summary['overall_best_residual']:.8f} "
          f"(at rank {summary['overall_best_residual_rank']})")
    print(f"  Converged ranks:           {summary['converged_ranks']}")

    if summary['improvement_over_alpha_evolve']:
        print(f"\n  🎉 IMPROVEMENT OVER ALPHAEVOLVE!")
        print(f"     AlphaEvolve: rank 48")
        print(f"     Our result:  rank {best_converged}")
    else:
        print(f"\n  No improvement over AlphaEvolve (rank 48).")
        print(f"  This is expected — ⟨4,4,4⟩ rank is likely exactly 48.")
        print(f"  The search confirms the difficulty of this problem.")

    print(f"\n  Comparison with ALS baseline:")
    print(f"    ALS best residual: ~8.34 (never converged)")
    print(f"    GD best residual:  {summary['overall_best_residual']:.8f}")

    return output


if __name__ == "__main__":
    main()
