"""
conftest.py — Shared fixtures for the Mirror Map Sieve test suite.
"""
import json
from math import comb
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent


def _compute_s20(n: int) -> int:
    """Exact S(n) = sum_{k=0}^n C(n,k)^4 * C(n+k,k), from first principles."""
    return sum(comb(n, k) ** 4 * comb(n + k, k) for k in range(n + 1))


@pytest.fixture(scope="session")
def s20_reference():
    """First 80 terms of S(n) computed independently from the formula."""
    return [_compute_s20(n) for n in range(80)]


@pytest.fixture(scope="session")
def polynomials():
    """Load P_0..P_5 coefficient lists from extracted_polynomials.json."""
    path = ROOT / "1_algebraic_shielding_solvers" / "extracted_polynomials.json"
    with open(path) as f:
        data = json.load(f)
    return {
        j: data["polynomials"][f"P_{j}"]["coefficients_ascending"]
        for j in range(6)
    }


@pytest.fixture(scope="session")
def poly_data():
    """Full extracted_polynomials.json data."""
    path = ROOT / "1_algebraic_shielding_solvers" / "extracted_polynomials.json"
    with open(path) as f:
        return json.load(f)
