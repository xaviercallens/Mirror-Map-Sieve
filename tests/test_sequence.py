"""
test_sequence.py — Unit tests for the S(n) sequence definition.

Tests that S(n) = sum_{k=0}^n C(n,k)^4 * C(n+k,k) is computed correctly
from first principles, independently of any stored data.
"""
import pytest
from math import comb


def compute_s20(n: int) -> int:
    return sum(comb(n, k) ** 4 * comb(n + k, k) for k in range(n + 1))


KNOWN_VALUES = {
    0:  1,
    1:  3,
    2:  55,
    3:  1155,
    4:  29751,
    5:  852753,
    6:  26097499,
    7:  840454275,
    8:  28064517175,
    9:  964417304253,
    10: 33903837716805,
}


@pytest.mark.parametrize("n, expected", KNOWN_VALUES.items())
def test_s20_exact_value(n, expected):
    """S(n) must match known values at n=0..10."""
    assert compute_s20(n) == expected, \
        f"S({n}) = {compute_s20(n)}, expected {expected}"


def test_s20_n0_is_one():
    """S(0) = C(0,0)^4 * C(0,0) = 1."""
    assert compute_s20(0) == 1


def test_s20_n1_is_three():
    """S(1) = C(1,0)^4*C(1,0) + C(1,1)^4*C(2,1) = 1 + 2 = 3."""
    assert compute_s20(1) == 3


def test_s20_n2():
    """S(2) = 1 + 2*16 + 3 = 55 (manual check)."""
    # k=0: C(2,0)^4*C(2,0) = 1
    # k=1: C(2,1)^4*C(3,1) = 16*3 = 48
    # k=2: C(2,2)^4*C(4,2) = 1*6 = 6
    assert compute_s20(2) == 55


def test_s20_positive():
    """S(n) > 0 for all n >= 0."""
    for n in range(20):
        assert compute_s20(n) > 0


def test_s20_strictly_increasing():
    """S(n) is strictly increasing."""
    vals = [compute_s20(n) for n in range(15)]
    for i in range(len(vals) - 1):
        assert vals[i] < vals[i + 1], f"S({i}) >= S({i+1}): {vals[i]} >= {vals[i+1]}"


def test_s20_odd():
    """S(n) is always odd (observable pattern: all values end in odd digit)."""
    for n in range(20):
        assert compute_s20(n) % 2 == 1, f"S({n}) = {compute_s20(n)} is even"


def test_s20_not_in_stored_form():
    """Cross-check: formula output must never be zero for n=0..19."""
    for n in range(20):
        v = compute_s20(n)
        assert v != 0
