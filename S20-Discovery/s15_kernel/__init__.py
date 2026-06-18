# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
"""
s15_kernel — S20/S15 Spectral Attention for PyTorch.

A softmax-free, banded attention mechanism that replaces the exponential
softmax with precomputed super-exponential decay weights derived from
the S₂₀ and S₁₅ combinatorial sequences.
"""

from .attention import S20SpectralAttention
from .sequence import compute_decay_table, compute_s15, compute_s20

__all__ = [
    "S20SpectralAttention",
    "compute_s20",
    "compute_s15",
    "compute_decay_table",
]
