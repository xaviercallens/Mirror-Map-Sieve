# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
"""Tests for s15_kernel.sequence — S₂₀ / S₁₅ values and decay tables."""

from __future__ import annotations

import pytest
import torch

from s15_kernel.sequence import compute_decay_table, compute_s15, compute_s20


# ------------------------------------------------------------------
# Known values for S₂₀ (Callens-Schmidt sequence, NOT in OEIS)
# ------------------------------------------------------------------

# First 10 values of S₂₀(n) = Σ_{k=0}^n C(n,k)⁴ · C(n+k,k)
# Computed via exact integer arithmetic. NOT A005259 (which is Σ C(n,k)² C(n+k,k)²).
S20_KNOWN: list[int] = [
    1,               # n=0
    3,               # n=1
    55,              # n=2
    1155,            # n=3
    29751,           # n=4
    852753,          # n=5
    26097499,        # n=6
    840454275,       # n=7
    28064517175,     # n=8
    964417304253,    # n=9
]


class TestComputeS20:
    """Verify S₂₀(n) = Σ C(n,k)⁴ C(n+k,k) against exact values."""

    @pytest.mark.parametrize("n, expected", enumerate(S20_KNOWN))
    def test_known_values(self, n: int, expected: int) -> None:
        assert compute_s20(n) == expected, f"S₂₀({n}) should be {expected}"

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            compute_s20(-1)

    def test_monotonically_increasing(self) -> None:
        """S₂₀ is strictly increasing for n ≥ 0."""
        vals = [compute_s20(n) for n in range(8)]
        for i in range(1, len(vals)):
            assert vals[i] > vals[i - 1]


# ------------------------------------------------------------------
# S₁₅ known values
# ------------------------------------------------------------------

S15_KNOWN: list[int] = [
    1,
    33,
    8263,
    3503073,
    1895356251,
    1180593064563,
]


class TestComputeS15:
    """Verify S₁₅(n) basic properties."""

    @pytest.mark.parametrize("n, expected", enumerate(S15_KNOWN))
    def test_known_values(self, n: int, expected: int) -> None:
        assert compute_s15(n) == expected, f"S₁₅({n}) should be {expected}"

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            compute_s15(-1)

    def test_monotonically_increasing(self) -> None:
        vals = [compute_s15(n) for n in range(6)]
        for i in range(1, len(vals)):
            assert vals[i] > vals[i - 1]


# ------------------------------------------------------------------
# Decay table tests
# ------------------------------------------------------------------

class TestDecayTable:
    """Test compute_decay_table properties."""

    def test_d0_is_one(self) -> None:
        """D_0 = 1/S(0) = 1 for both S₂₀ and S₁₅."""
        table = compute_decay_table(compute_s20, max_d=5)
        assert table[0].item() == pytest.approx(1.0)

    def test_monotonically_decreasing(self) -> None:
        """Decay values must be strictly decreasing."""
        table = compute_decay_table(compute_s20, max_d=10)
        for i in range(1, len(table)):
            assert table[i].item() < table[i - 1].item(), (
                f"D_{i} should be < D_{i-1}"
            )

    def test_all_positive(self) -> None:
        """All decay values must be positive."""
        table = compute_decay_table(compute_s20, max_d=10)
        assert (table > 0).all()

    def test_shape(self) -> None:
        """Length should be max_d + 1."""
        table = compute_decay_table(compute_s20, max_d=7)
        assert table.shape == (8,)

    @pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
    def test_dtype_matches(self, dtype: torch.dtype) -> None:
        """Output dtype must match the requested dtype."""
        table = compute_decay_table(compute_s20, max_d=3, dtype=dtype)
        assert table.dtype == dtype

    def test_known_d1_value(self) -> None:
        """D_1 = 1/3 ≈ 0.33333 for S₂₀."""
        table = compute_decay_table(compute_s20, max_d=1)
        assert table[1].item() == pytest.approx(1.0 / 3.0, rel=1e-5)

    def test_known_d2_value(self) -> None:
        """D_2 = 1/55 ≈ 0.01818 for S₂₀."""
        table = compute_decay_table(compute_s20, max_d=2)
        assert table[2].item() == pytest.approx(1.0 / 55.0, rel=1e-5)

    def test_super_exponential_decay(self) -> None:
        """Verify the ratio S(d+1)/S(d) is growing (super-exponential)."""
        table = compute_decay_table(compute_s20, max_d=6)
        ratios = []
        for i in range(1, len(table)):
            ratios.append(table[i - 1].item() / table[i].item())
        # Ratios should be strictly increasing (super-exponential growth)
        for i in range(1, len(ratios)):
            assert ratios[i] > ratios[i - 1], (
                f"Decay ratio at step {i} should exceed step {i-1}"
            )

    def test_negative_max_d_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            compute_decay_table(compute_s20, max_d=-1)

    def test_s15_decay_table(self) -> None:
        """S₁₅ decay table should also be monotonically decreasing."""
        table = compute_decay_table(compute_s15, max_d=5)
        assert table[0].item() == pytest.approx(1.0)
        for i in range(1, len(table)):
            assert table[i].item() < table[i - 1].item()
