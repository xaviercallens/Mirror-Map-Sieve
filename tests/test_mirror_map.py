"""
test_mirror_map.py — Verify Lian-Yau mirror map integrality (Theorem 3).

Tests that the mirror map coefficients q_d lie in Z for d=1..16,
computed via exact rational arithmetic from the S(n) period sequence.

This verifies the main claim of Section 4 of the paper:
"the Lian-Yau integrality conjecture holds for S(n)".
"""
import sys
from fractions import Fraction
from math import comb
from pathlib import Path
import pytest

# Add geometry module to path
sys.path.insert(0, str(Path(__file__).parent.parent / "3_mirror_map_geometry"))


def compute_s20(n: int) -> int:
    return sum(comb(n, k) ** 4 * comb(n + k, k) for k in range(n + 1))


def harmonic(n: int) -> Fraction:
    """H_n = 1 + 1/2 + ... + 1/n (exact rational)."""
    return sum(Fraction(1, k) for k in range(1, n + 1))


def compute_mirror_map_qd(max_d: int) -> dict[int, Fraction]:
    """
    Compute mirror map q_d for d=1..max_d via exact rational arithmetic.

    The holomorphic period: f(z) = sum_{n>=0} S(n) * z^n
    The logarithmic period: g(z) = sum_{n>=1} B(n) * z^n
    where B(n) = S(n) * w(n), w(n) = 4*(H_n - H_{n-k averaged}) + H_{n+k} term

    Mirror map: q(z) = z * exp(g(z)/f(z))
    We extract q_d as the coefficient of z^d in q(z).
    """
    # Compute S(n) and the logarithmic derivative B(n)
    N = max_d + 2
    S = [compute_s20(n) for n in range(N)]
    
    # B(n) for the logarithmic period — weight-5 formula
    # H[n+k] can reach H[2n] for k=n, so precompute up to 2*N
    H_MAX = 2 * N + 2
    H = [harmonic(n) if n > 0 else Fraction(0) for n in range(H_MAX + 1)]

    B = [Fraction(0)]  # B(0) = 0
    for n in range(1, N):
        sn = Fraction(0)
        for k in range(n + 1):
            binom_n_k = comb(n, k)
            binom_nk_k = comb(n + k, k)
            # Weight factor: 4*(H_n - H_{n-k}) + (H_{n+k} - H_n)
            w = 4 * (H[n] - H[n - k]) + (H[n + k] - H[n])
            sn += Fraction(binom_n_k ** 4 * binom_nk_k) * w
        B.append(sn)

    # Power series: f(z) = sum S[n]*z^n, g(z) = sum B[n]*z^n
    # Compute h = g/f as power series to order max_d
    f = [Fraction(S[n]) for n in range(N)]
    g = list(B[:N])

    # Divide: h = g / f (h[0] = g[0]/f[0] = 0, so h[d] for d>=1)
    h = [Fraction(0)] * N
    for d in range(1, N):
        h[d] = (g[d] - sum(h[i] * f[d - i] for i in range(1, d))) / f[0]

    # q(z) = z * exp(h(z)) — extract coefficients via exp power series
    # exp(h)[d] = sum_{k=1}^{d} (k/d) * h[k] * exp(h)[d-k],  exp(h)[0]=1
    exp_h = [Fraction(0)] * N
    exp_h[0] = Fraction(1)
    for d in range(1, N):
        exp_h[d] = sum(
            Fraction(k, d) * h[k] * exp_h[d - k] for k in range(1, d + 1)
        )

    # q_d = coefficient of z^d in z*exp(h(z)) = exp_h[d-1]
    q = {d: exp_h[d - 1] for d in range(1, max_d + 1)}
    return q


EXPECTED_QD = {
    1:  Fraction(1),
    2:  Fraction(9),
    3:  Fraction(165),
    4:  Fraction(4110),
    5:  Fraction(111075),
    6:  Fraction(3316785),
}


@pytest.fixture(scope="module")
def mirror_map_coefficients():
    """Precompute q_d for d=1..16 once per test module."""
    return compute_mirror_map_qd(16)


def test_mirror_map_integrality(mirror_map_coefficients):
    """Primary theorem: q_d ∈ Z for all d = 1..16."""
    for d in range(1, 17):
        q = mirror_map_coefficients[d]
        assert q.denominator == 1, \
            f"q_{d} = {q} is NOT an integer! Lian-Yau fails at d={d}."


def test_mirror_map_positive(mirror_map_coefficients):
    """All q_d > 0 (instanton numbers must be positive)."""
    for d in range(1, 17):
        assert mirror_map_coefficients[d] > 0, f"q_{d} <= 0"


def test_mirror_map_q1_is_one(mirror_map_coefficients):
    """q_1 = 1 always (normalization of the mirror map)."""
    assert mirror_map_coefficients[1] == Fraction(1)


@pytest.mark.parametrize("d, expected", EXPECTED_QD.items())
def test_mirror_map_known_values(d, expected, mirror_map_coefficients):
    """q_d must match the values reported in Table 1 of the paper."""
    assert mirror_map_coefficients[d] == expected, \
        f"q_{d}: computed={mirror_map_coefficients[d]}, paper={expected}"


def test_mirror_map_strictly_increasing(mirror_map_coefficients):
    """q_d is strictly increasing (as expected for instanton counts)."""
    for d in range(1, 16):
        assert mirror_map_coefficients[d] < mirror_map_coefficients[d + 1], \
            f"q_{d} = {mirror_map_coefficients[d]} >= q_{d+1} = {mirror_map_coefficients[d+1]}"
