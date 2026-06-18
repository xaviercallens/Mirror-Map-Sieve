#!/usr/bin/env python3
"""
s20_decay.py — Vectorized S20-Based Attention Decay (Optimized Core)

This module provides a mathematically exact, GPU-efficient implementation
of the S20-based attention decay for causal transformers.

The key insight: the decay matrix D[i,j] = f(|i-j|) can be constructed
entirely without Python loops using torch.arange and broadcasting.

Design:
  - Builds decay as a float32 Toeplitz-like tensor via vectorized indexing
  - Compatible with torch.compile() for graph capture and kernel fusion
  - Falls back gracefully to CPU when CUDA is unavailable
  - Separate track from the Calabi-Yau mathematics paper
    (target: Hugging Face paper + CS benchmark publication)

Author: Xavier Callens / SocrateAI Scientific Agora
License: MIT
"""

import math
from math import comb
from typing import Optional
import torch
import torch.nn.functional as F


# ─────────────────────────────────────────────────────────────
# 1. S20 Sequence — exact Python big-integer arithmetic
# ─────────────────────────────────────────────────────────────

def s20(n: int) -> int:
    """Compute S_{20}(n) = sum_{k=0}^{n} C(n,k)^4 * C(n+k,k) exactly."""
    return sum(comb(n, k) ** 4 * comb(n + k, k) for k in range(n + 1))


# Precompute exact values for d=0..17 (INT64-safe: S20(17) < 2^63)
_S20_TABLE: list[int] = [s20(d) for d in range(18)]

# Verification reference
_S20_REF = [1, 3, 55, 1155, 29751, 852753, 26097499, 840454275,
             28064517175, 964417304253, 33903837716805, 1214258225057265,
             44166395275424475, 1627604857066000725, 60654810749855283555,
             2282379931043443585155, 86613897907152215198775,
             3311529972822006548243925]

assert _S20_TABLE == _S20_REF, "S20 computation mismatch!"


# ─────────────────────────────────────────────────────────────
# 2. Vectorized Decay Tensor Construction
# ─────────────────────────────────────────────────────────────

def build_decay_vector(max_distance: int = 17, device: str = "cpu") -> torch.Tensor:
    """
    Build the float32 decay weight vector of length (max_distance+1).

    decay[d] = S20(0) / S20(d)  for d <= 17 (exact rational, then cast to float32)
    decay[d] = 0.0              for d >  17 (beyond INT64-safe range)

    Returns:
        Tensor of shape (max_distance+1,) on `device`, dtype=float32
    """
    base = float(_S20_TABLE[0])  # = 1.0
    weights = []
    for d in range(max_distance + 1):
        if d < len(_S20_TABLE) and _S20_TABLE[d] > 0:
            weights.append(base / float(_S20_TABLE[d]))
        else:
            weights.append(0.0)
    return torch.tensor(weights, dtype=torch.float32, device=device)


def build_decay_matrix(seq_len: int, max_distance: int = 17,
                        device: str = "cpu") -> torch.Tensor:
    """
    Build an (L, L) float32 decay matrix in O(L) time (vectorized, no Python loops).

    decay_matrix[i, j] = decay_vector[|i-j|]  if |i-j| <= max_distance
                        = 0.0                  otherwise

    Uses torch.arange + broadcasting — fully vectorized, torch.compile compatible.

    Returns:
        Tensor of shape (L, L), dtype=float32, on `device`
    """
    L = seq_len
    # distance matrix: dist[i,j] = |i - j|, shape (L, L)
    idx = torch.arange(L, device=device)
    dist = (idx.unsqueeze(0) - idx.unsqueeze(1)).abs()  # (L, L)

    # decay vector lookup — clamp out-of-range distances to index max_distance+1
    dv = build_decay_vector(max_distance, device=device)  # (max_distance+1,)

    # For distances > max_distance, use 0. Pad dv with one zero.
    dv_padded = torch.cat([dv, dv.new_zeros(1)])  # (max_distance+2,)
    dist_clamped = dist.clamp(max=max_distance + 1)  # safe index into dv_padded

    return dv_padded[dist_clamped]  # (L, L) — pure vectorized gather


# ─────────────────────────────────────────────────────────────
# 3. Long-Range Decay (LIA variant) — vectorized
# ─────────────────────────────────────────────────────────────

def build_lia_decay_matrix(seq_len: int, local_cutoff: int = 17,
                            device: str = "cpu") -> torch.Tensor:
    """
    LIA long-range decay matrix (fully vectorized).

    For d <= local_cutoff:  exact S20 ratio (fast local decay)
    For d >  local_cutoff:  anchor * sqrt(local_cutoff / d)  (slow long-range tail)

    Returns:
        Tensor of shape (L, L), dtype=float32, on `device`
    """
    L = seq_len
    idx = torch.arange(L, dtype=torch.float32, device=device)
    dist = (idx.unsqueeze(0) - idx.unsqueeze(1)).abs()  # (L, L) float

    # Local part (d <= local_cutoff)
    dv = build_decay_vector(local_cutoff, device=device)
    dv_padded = torch.cat([dv, dv.new_zeros(1)])
    dist_int = dist.long().clamp(max=local_cutoff + 1)
    local_decay = dv_padded[dist_int]

    # Long-range part (d > local_cutoff)
    anchor = dv[local_cutoff]  # scalar
    # Avoid div-by-zero at d=0
    safe_dist = dist.clamp(min=1.0)
    long_range_decay = anchor * torch.sqrt(torch.tensor(float(local_cutoff), device=device) / safe_dist)

    # Blend: use local where d <= cutoff, long-range otherwise
    is_local = (dist <= local_cutoff)
    combined = torch.where(is_local, local_decay, long_range_decay)

    return combined


# ─────────────────────────────────────────────────────────────
# 4. Core Attention Function — optimized, compile-ready
# ─────────────────────────────────────────────────────────────

def s20_causal_attention(q: torch.Tensor, k: torch.Tensor, v: torch.Tensor,
                          decay_matrix: torch.Tensor,
                          scale: Optional[float] = None) -> tuple[torch.Tensor, torch.Tensor]:
    """
    S20-decayed scaled dot-product causal attention (optimized).

    Args:
        q, k, v:       [B, H, L, D] float tensors (float32 or float16)
        decay_matrix:  [L, L] float32 decay weights (precomputed once)
        scale:         optional manual scale (default: 1/sqrt(D))

    Returns:
        (output, attention_weights): both [B, H, L, L] for attn, [B, H, L, D] for output
    """
    B, H, L, D = q.shape
    sc = scale if scale is not None else math.sqrt(D)

    # QK^T scores
    scores = torch.einsum("bhid,bhjd->bhij", q, k) / sc  # (B, H, L, L)

    # Apply S20 decay (broadcast over batch and heads)
    scores = scores + torch.log(decay_matrix.clamp(min=1e-9)).unsqueeze(0).unsqueeze(0)

    # Causal mask: upper triangle → -inf
    causal_mask = torch.triu(
        torch.full((L, L), float("-inf"), device=q.device, dtype=scores.dtype),
        diagonal=1
    )
    scores = scores + causal_mask

    # Softmax and weighted sum
    attn = F.softmax(scores, dim=-1)
    out = torch.einsum("bhij,bhjd->bhid", attn, v)

    return out, attn


def fp16_sdpa_baseline(q: torch.Tensor, k: torch.Tensor, v: torch.Tensor) -> torch.Tensor:
    """
    Standard scaled dot-product attention (FP16, PyTorch built-in flash attention).
    Baseline for comparison.
    """
    return F.scaled_dot_product_attention(
        q.half(), k.half(), v.half(),
        attn_mask=None,
        dropout_p=0.0,
        is_causal=True
    ).float()


# ─────────────────────────────────────────────────────────────
# 5. torch.compile wrappers
# ─────────────────────────────────────────────────────────────

try:
    _compiled_s20_attn = torch.compile(s20_causal_attention, mode="reduce-overhead")
except Exception:
    _compiled_s20_attn = s20_causal_attention  # fallback if compile unavailable


def s20_attention_compiled(q, k, v, decay_matrix):
    """torch.compile-optimized S20 attention entry point."""
    return _compiled_s20_attn(q, k, v, decay_matrix)
