# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
"""
S20 Spectral Attention — softmax-free banded attention via combinatorial decay.

Replaces standard softmax attention with a precomputed, super-exponentially
decaying banded mask derived from the S₂₀ (or S₁₅) combinatorial sequence.

Standard:  Attn = softmax(QK^T / √d) · V
S20:       Attn = normalize(decay_mask ⊙ (Q̂ K̂^T)) · V

where:
  • Q̂, K̂  are L2-normalised query / key vectors (per head)
  • decay_mask[i,j] = D_{|i-j|}  for |i-j| ≤ W, else 0
  • D_d = 1 / S₂₀(d) is the precomputed decay table
  • normalize = ReLU → row-wise L1 normalisation

Key properties:
  ✓ No exp() computation (softmax-free)
  ✓ O(L·W·d) FLOPs vs O(L²·d) for full softmax
  ✓ Precomputed decay weights (no extra learned parameters)
  ✓ Causal masking supported via zeroing the upper triangle
"""

from __future__ import annotations

from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

from .sequence import compute_decay_table, compute_s15, compute_s20


class S20SpectralAttention(nn.Module):
    """Banded spectral-decay multi-head attention.

    This module is a **drop-in replacement** for ``nn.MultiheadAttention``
    in the common ``(batch, seq_len, d_model)`` layout.

    Parameters
    ----------
    d_model : int
        Total model dimension (must be divisible by ``n_heads``).
    n_heads : int
        Number of parallel attention heads.
    window_size : int, optional
        Maximum attention distance *W*.  Positions with ``|i-j| > W`` receive
        zero weight.  Default ``32``.
    sequence_fn : str, optional
        Which combinatorial sequence to use: ``"s20"`` (default) or ``"s15"``.
    causal : bool, optional
        If ``True`` (default), mask out future positions (upper triangle).

    Attributes
    ----------
    decay_table : torch.Tensor
        Registered buffer of shape ``(window_size + 1,)`` holding D_d values.
    """

    def __init__(
        self,
        d_model: int,
        n_heads: int,
        window_size: int = 32,
        sequence_fn: str = "s20",
        causal: bool = True,
    ) -> None:
        super().__init__()

        if d_model % n_heads != 0:
            raise ValueError(
                f"d_model ({d_model}) must be divisible by n_heads ({n_heads})"
            )

        self.d_model: int = d_model
        self.n_heads: int = n_heads
        self.head_dim: int = d_model // n_heads
        self.window_size: int = window_size
        self.causal: bool = causal

        # --- Projections ---
        self.q_proj = nn.Linear(d_model, d_model)
        self.k_proj = nn.Linear(d_model, d_model)
        self.v_proj = nn.Linear(d_model, d_model)
        self.out_proj = nn.Linear(d_model, d_model)

        # --- Precomputed decay ---
        seq_fn_map = {"s20": compute_s20, "s15": compute_s15}
        if sequence_fn not in seq_fn_map:
            raise ValueError(
                f"sequence_fn must be one of {list(seq_fn_map)}, got {sequence_fn!r}"
            )
        decay_table = compute_decay_table(
            seq_fn_map[sequence_fn], max_d=window_size, dtype=torch.float32
        )
        self.register_buffer("decay_table", decay_table, persistent=False)

        # Cache for the full (L×L) decay mask — rebuilt when L changes.
        self._cached_mask: Optional[torch.Tensor] = None
        self._cached_L: int = -1

    # ------------------------------------------------------------------
    # Mask construction
    # ------------------------------------------------------------------

    def _build_decay_mask(self, L: int, device: torch.device) -> torch.Tensor:
        """Build the (L, L) banded decay mask.

        ``mask[i, j] = D_{|i-j|}`` when ``|i-j| ≤ W``, else ``0``.
        If causal, the upper triangle (j > i) is additionally zeroed.

        Parameters
        ----------
        L : int
            Sequence length.
        device : torch.device
            Target device.

        Returns
        -------
        torch.Tensor
            Shape ``(L, L)`` float mask.
        """
        # Distance matrix  dist[i,j] = |i - j|
        idx = torch.arange(L, device=device)
        dist = (idx.unsqueeze(0) - idx.unsqueeze(1)).abs()  # (L, L)

        # Build mask from decay table — positions beyond window get 0
        W = self.window_size
        in_window = dist <= W  # bool (L, L)

        # Clamp distances to valid table range for safe indexing, then zero
        # out-of-window entries.
        clamped_dist = dist.clamp(max=W)
        decay_table = self.decay_table.to(device=device, dtype=torch.float32)
        mask = decay_table[clamped_dist] * in_window.float()  # (L, L)

        if self.causal:
            causal_mask = torch.tril(torch.ones(L, L, device=device))
            mask = mask * causal_mask

        return mask

    def _get_decay_mask(self, L: int, device: torch.device) -> torch.Tensor:
        """Return a cached or freshly built decay mask."""
        if self._cached_L != L or self._cached_mask is None or self._cached_mask.device != device:
            self._cached_mask = self._build_decay_mask(L, device)
            self._cached_L = L
        return self._cached_mask

    # ------------------------------------------------------------------
    # Forward
    # ------------------------------------------------------------------

    def forward(
        self,
        x: torch.Tensor,
        key: Optional[torch.Tensor] = None,
        value: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Run S20 spectral attention.

        Parameters
        ----------
        x : torch.Tensor
            Query input of shape ``(B, L, D)`` where B = batch, L = length,
            D = d_model.
        key : torch.Tensor, optional
            Key input.  Defaults to ``x`` (self-attention).
        value : torch.Tensor, optional
            Value input.  Defaults to ``x`` (self-attention).

        Returns
        -------
        torch.Tensor
            Output of shape ``(B, L, D)``.
        """
        if key is None:
            key = x
        if value is None:
            value = x

        B, L, D = x.shape
        H = self.n_heads
        Dh = self.head_dim

        # --- Project ---
        Q = self.q_proj(x).view(B, L, H, Dh).transpose(1, 2)   # (B, H, L, Dh)
        K = self.k_proj(key).view(B, L, H, Dh).transpose(1, 2)  # (B, H, L, Dh)
        V = self.v_proj(value).view(B, L, H, Dh).transpose(1, 2)  # (B, H, L, Dh)

        # --- L2-normalise Q, K ---
        Q = F.normalize(Q, p=2, dim=-1)
        K = F.normalize(K, p=2, dim=-1)

        # --- Dot-product scores ---
        scores = torch.matmul(Q, K.transpose(-2, -1))  # (B, H, L, L)

        # --- Apply banded decay mask ---
        decay_mask = self._get_decay_mask(L, x.device)  # (L, L)
        scores = scores * decay_mask.unsqueeze(0).unsqueeze(0)  # broadcast over B, H

        # --- ReLU + L1 row normalisation ---
        scores = F.relu(scores)
        row_sums = scores.sum(dim=-1, keepdim=True).clamp(min=1e-8)
        attn_weights = scores / row_sums  # (B, H, L, L)

        # --- Weighted sum of values ---
        out = torch.matmul(attn_weights, V)  # (B, H, L, Dh)
        out = out.transpose(1, 2).contiguous().view(B, L, D)

        # --- Output projection ---
        out = self.out_proj(out)
        return out

    def extra_repr(self) -> str:
        return (
            f"d_model={self.d_model}, n_heads={self.n_heads}, "
            f"head_dim={self.head_dim}, window_size={self.window_size}, "
            f"causal={self.causal}"
        )
