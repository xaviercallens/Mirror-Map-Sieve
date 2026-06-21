#!/usr/bin/env python3
"""
cy_sieve_attention.py — NumPy attention reference using the CY-Sieve positional
bias (vision.md / tests.md §4). CPU-only; no GPU, no Triton.

This is the algorithm a future Triton/GPU kernel must reproduce. It provides:

  * cy_sieve_bias_vector(L, seq, tau)         — additive log-space bias by distance
  * sdpa_with_bias(...)                       — dense, naive softmax (ground truth)
  * flash_sdpa_with_bias(...)                 — FlashAttention-style ONLINE/blocked
                                                 softmax (numerically what the GPU
                                                 kernel does); must match the dense
                                                 reference (tests.md §4).
  * multihead_cy_sieve(...)                   — per-head tau ladder (ALiBi-style)

The bias enters as a standard additive term on the pre-softmax logits:
    scores[i,j] = (q_i . k_j)/sqrt(D) + bias(|i-j|)          (causal: j<=i)
where bias(d) = cy_sieve_reference.cy_sieve_bias(d, seq, tau).

Design rule (tests.md): correctness/parity here is necessary but NOT sufficient;
the decisive quality gate (§5: perplexity + Needle-in-a-Haystack on a real model)
requires a GPU and is out of scope for this CPU reference.
"""
from __future__ import annotations
import numpy as np

import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import cy_sieve_reference as cy


# ----------------------------------------------------------------------------
# Bias vector (distance -> additive log-space bias)
# ----------------------------------------------------------------------------

def cy_sieve_bias_vector(max_distance: int, seq: str = "S20",
                         tau: float = 1.0) -> np.ndarray:
    """bias[d] = cy_sieve_bias(d, seq, tau) for d = 0..max_distance.
    bias[0] = 0 by construction (-log S(0) = -log 1 = 0)."""
    return np.array([cy.cy_sieve_bias(d, seq, tau) for d in range(max_distance + 1)],
                    dtype=np.float64)


def bias_matrix(L: int, seq: str = "S20", tau: float = 1.0,
                causal: bool = True) -> np.ndarray:
    """[L,L] additive bias matrix B[i,j] = bias(|i-j|), with -inf above the
    diagonal when causal."""
    bv = cy_sieve_bias_vector(L, seq, tau)
    idx = np.abs(np.subtract.outer(np.arange(L), np.arange(L)))   # |i-j|
    B = bv[idx]
    if causal:
        iu = np.triu_indices(L, k=1)
        B[iu] = -np.inf
    return B


# ----------------------------------------------------------------------------
# Dense reference (naive softmax) — ground truth
# ----------------------------------------------------------------------------

def _softmax_rows(x: np.ndarray) -> np.ndarray:
    m = np.max(x, axis=-1, keepdims=True)
    m = np.where(np.isfinite(m), m, 0.0)          # all-(-inf) row guard
    e = np.exp(x - m)
    s = np.sum(e, axis=-1, keepdims=True)
    s = np.where(s == 0, 1.0, s)
    return e / s


def sdpa_with_bias(Q, K, V, seq="S20", tau=1.0, causal=True):
    """Dense scaled-dot-product attention with the CY-Sieve additive bias.
    Q,K,V: [L,D]. Returns (out [L,D], attn [L,L])."""
    L, D = Q.shape
    scores = (Q @ K.T) / np.sqrt(D) + bias_matrix(L, seq, tau, causal)
    attn = _softmax_rows(scores)
    return attn @ V, attn


# ----------------------------------------------------------------------------
# FlashAttention-style online/blocked softmax — what the GPU kernel computes
# ----------------------------------------------------------------------------

def flash_sdpa_with_bias(Q, K, V, seq="S20", tau=1.0, causal=True,
                         block: int = 16):
    """Blocked, running-max/running-sum online softmax (the FlashAttention
    recurrence) with the CY-Sieve bias folded into the scores. Numerically
    identical (up to fp error) to sdpa_with_bias, but never materializes the
    full [L,L] score matrix — this is the kernel-faithful path for §4 parity.
    """
    L, D = Q.shape
    scale = 1.0 / np.sqrt(D)
    bv = cy_sieve_bias_vector(L, seq, tau)
    out = np.zeros((L, D), dtype=np.float64)
    for i0 in range(0, L, block):
        i1 = min(i0 + block, L)
        qi = Q[i0:i1]                                    # [bi, D]
        bi = i1 - i0
        m = np.full((bi, 1), -np.inf)                    # running max
        l = np.zeros((bi, 1))                            # running denom
        acc = np.zeros((bi, D))                          # running numerator
        for j0 in range(0, L, block):
            j1 = min(j0 + block, L)
            if causal and j0 > i1 - 1:
                break                                    # whole block is future
            kj = K[j0:j1]; vj = V[j0:j1]
            s = (qi @ kj.T) * scale                      # [bi, bj]
            # add bias(|i-j|) and causal mask
            ii = np.arange(i0, i1)[:, None]
            jj = np.arange(j0, j1)[None, :]
            d = np.abs(ii - jj)
            s = s + bv[d]
            if causal:
                s = np.where(jj <= ii, s, -np.inf)
            # online softmax update
            m_new = np.maximum(m, np.max(s, axis=1, keepdims=True))
            m_new = np.where(np.isfinite(m_new), m_new, 0.0)
            p = np.exp(s - m_new)
            p = np.where(np.isfinite(s), p, 0.0)
            alpha = np.exp(m - m_new)
            alpha = np.where(np.isfinite(m), alpha, 0.0)
            l = alpha * l + np.sum(p, axis=1, keepdims=True)
            acc = alpha * acc + p @ vj
            m = m_new
        l = np.where(l == 0, 1.0, l)
        out[i0:i1] = acc / l
    return out


# ----------------------------------------------------------------------------
# Multi-head with the ALiBi-style per-head tau ladder
# ----------------------------------------------------------------------------

def multihead_cy_sieve(Q, K, V, seq="S20", causal=True, taus=None):
    """Q,K,V: [H,L,D]. Each head h uses temperature taus[h] (default: the
    ALiBi-style ladder). Returns out [H,L,D]."""
    H = Q.shape[0]
    if taus is None:
        taus = cy.alibi_style_tau_ladder(H)
    assert len(taus) == H
    return np.stack([sdpa_with_bias(Q[h], K[h], V[h], seq, taus[h], causal)[0]
                     for h in range(H)], axis=0)


def main():
    rng = np.random.default_rng(0)
    L, D = 48, 16
    Q, K, V = (rng.standard_normal((L, D)) for _ in range(3))
    print("CY-Sieve attention reference — quick check")
    o1, a = sdpa_with_bias(Q, K, V, tau=20.0)
    o2 = flash_sdpa_with_bias(Q, K, V, tau=20.0)
    print(f"  dense vs flash max abs diff: {np.max(np.abs(o1 - o2)):.2e}")
    print(f"  attention rows sum to 1: {np.allclose(a.sum(1), 1.0)}")
    print(f"  causal (no upper-tri weight): {np.allclose(np.triu(a, 1), 0.0)}")


if __name__ == "__main__":
    main()
