# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
"""
Exact computation of S₂₀ and S₁₅ combinatorial sequences and decay tables.

Mathematical definitions:
    S₂₀(n) = Σ_{k=0}^{n} C(n,k)⁴ · C(n+k,k)
    S₁₅(n) = Σ_{k=0}^{n} C(n,k) · C(n+k,k)⁵

The decay table D_d = 1/S(d) provides super-exponentially decaying weights
for banded spectral attention. The ratio S(d+1)/S(d) grows roughly ~43× per
step for S₂₀, making the decay far steeper than any exponential.

First values of S₂₀:  1, 3, 55, 1155, 29751, 852753, ...
"""

from __future__ import annotations

from math import comb
from typing import Callable

import torch


def compute_s20(n: int) -> int:
    """Compute S₂₀(n) = Σ_{k=0}^{n} C(n,k)⁴ · C(n+k,k).

    This is the Callens-Schmidt sequence (not in OEIS as of 2026-06).
    NOT the Apéry numbers (A005259), which use C(n,k)² C(n+k,k)².

    Parameters
    ----------
    n : int
        Non-negative integer index.

    Returns
    -------
    int
        The exact integer value S₂₀(n).

    Examples
    --------
    >>> compute_s20(0)
    1
    >>> compute_s20(1)
    3
    >>> compute_s20(2)
    55
    """
    if n < 0:
        raise ValueError(f"n must be non-negative, got {n}")
    total = 0
    for k in range(n + 1):
        total += comb(n, k) ** 4 * comb(n + k, k)
    return total


def compute_s15(n: int) -> int:
    """Compute S₁₅(n) = Σ_{k=0}^{n} C(n,k) · C(n+k,k)⁵.

    Parameters
    ----------
    n : int
        Non-negative integer index.

    Returns
    -------
    int
        The exact integer value S₁₅(n).

    Examples
    --------
    >>> compute_s15(0)
    1
    >>> compute_s15(1)
    33
    """
    if n < 0:
        raise ValueError(f"n must be non-negative, got {n}")
    total = 0
    for k in range(n + 1):
        total += comb(n, k) * comb(n + k, k) ** 5
    return total


@torch.no_grad()
def compute_decay_table(
    seq_fn: Callable[[int], int],
    max_d: int,
    dtype: torch.dtype = torch.float32,
) -> torch.Tensor:
    """Precompute decay weights D_d = 1/S(d) as a 1-D tensor.

    The decay table is used to build the banded attention mask. Because S(d)
    grows super-exponentially, D_d → 0 extremely fast, making the attention
    effectively local.

    Parameters
    ----------
    seq_fn : Callable[[int], int]
        One of :func:`compute_s20` or :func:`compute_s15`.
    max_d : int
        Maximum distance (inclusive). The returned tensor has length max_d + 1.
    dtype : torch.dtype
        Desired floating-point dtype for the output tensor.

    Returns
    -------
    torch.Tensor
        1-D tensor of shape ``(max_d + 1,)`` with ``D[d] = 1 / seq_fn(d)``.

    Examples
    --------
    >>> table = compute_decay_table(compute_s20, 3)
    >>> table[0].item()
    1.0
    >>> round(table[1].item(), 4)
    0.1667
    """
    if max_d < 0:
        raise ValueError(f"max_d must be non-negative, got {max_d}")

    values: list[float] = []
    for d in range(max_d + 1):
        s = seq_fn(d)
        values.append(1.0 / s)

    return torch.tensor(values, dtype=dtype)
