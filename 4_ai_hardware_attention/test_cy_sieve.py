#!/usr/bin/env python3
"""
test_cy_sieve.py — CY-Sieve reference validation, tests.md sections §1–§3.

CPU-only (no GPU); pure standard library + pytest. Run:
    pytest 4_ai_hardware_attention/test_cy_sieve.py -v

These cover the three tiers of cy_sieve_reference.py:
  §1  Tier-1 exact INT64 local table (overflow boundary, values, monotonicity)
  §2  Tier-2 recurrence-mod-p generator (correctness) + documented keep-rule failure
  §3  Tier-3 asymptotic penalty (theory-correct constants, error bound, handoff)

Quality-gate tests (§5) and kernel-parity (§4) are GPU/model-level and live
elsewhere; this file is the part runnable on a laptop.
"""
from __future__ import annotations
from math import comb, log
import pytest

import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import cy_sieve_reference as cy


# ==========================================================================
# §1 — Tier 1: exact INT64 local table
# ==========================================================================

def test_s1_1_overflow_boundary_S20():
    """T1.1: S20 safe through d=13, overflows at d=14."""
    assert cy.S20(13) <= cy.INT64_MAX
    assert cy.S20(14) > cy.INT64_MAX
    assert cy.int64_safe_window("S20") == 13


def test_s1_1_overflow_boundary_S15():
    """T1.1: S15 safe through d=16, overflows at d=17."""
    assert cy.S15(16) <= cy.INT64_MAX
    assert cy.S15(17) > cy.INT64_MAX
    assert cy.int64_safe_window("S15") == 16


def test_s1_1_known_first_terms():
    """Sanity: published first terms of both sequences."""
    assert [cy.S20(n) for n in range(6)] == [1, 3, 55, 1155, 29751, 852753]
    # S15 = sum C(n,k)^3 C(n+k,k): 1,3,...,  cross-check against direct comb
    assert cy.S15(0) == 1 and cy.S15(1) == 3
    assert cy.S15(2) == sum(comb(2, k) ** 3 * comb(2 + k, k) for k in range(3))


@pytest.mark.parametrize("seq", ["S20", "S15"])
def test_s1_2_table_values_exact(seq):
    """T1.2: table[d] == floor(2^32 * S(0) / S(d)), bit-exact vs reference."""
    tbl = cy.tier1_table(seq)
    f = cy.SEQUENCES[seq]
    s0 = f(0)
    for d, val in enumerate(tbl):
        assert val == (s0 << cy.FIXED_POINT_SHIFT) // f(d)


@pytest.mark.parametrize("seq", ["S20", "S15"])
def test_s1_2_table_fits_int64(seq):
    """Table entries fit in unsigned/again signed INT64 within the window."""
    for val in cy.tier1_table(seq):
        assert 0 <= val <= cy.INT64_MAX


def test_s1_2_table_zeroth_is_max():
    """table[0] == 2^SHIFT (S(0)=1) and is the maximum; table stays >= 1 and
    fits INT64 across the (reciprocal) window."""
    tbl = cy.tier1_table("S20")
    assert tbl[0] == (1 << cy.FIXED_POINT_SHIFT)
    assert tbl[0] == max(tbl)
    assert min(tbl) >= 1                      # no underflow to 0 inside the window
    assert tbl[0] <= cy.INT64_MAX             # numerator fits signed INT64


@pytest.mark.parametrize("seq", ["S20", "S15"])
def test_s1_3_strictly_decreasing(seq):
    """T1.3: reciprocal-decay table is strictly decreasing (a positional decay).
    This test originally FAILED with the naive 2^32 shift (table underflowed to
    0 by d~8); it forced FIXED_POINT_SHIFT=62 so the table spans the window."""
    tbl = cy.tier1_table(seq)
    assert all(tbl[d] > tbl[d + 1] for d in range(len(tbl) - 1))


@pytest.mark.parametrize("seq,expected", [("S20", 13), ("S15", 15)])
def test_s1_3_reciprocal_window(seq, expected):
    """The usable reciprocal window (table stays >= 1). For S15 it is 15, one
    shorter than the INT64-value window (16) because S15(16) > 2^SHIFT — an
    honest fixed-point limitation, documented rather than hidden."""
    assert cy.tier1_window(seq) == expected


def test_s1_3_fixedpoint_tail_quantization_is_documented():
    """The fixed-point reciprocal loses resolution at the window tail (e.g.
    S20: table[13]=2, ~50% quantization). The mathematically faithful bias
    therefore uses the exact integer in-window, NOT the quantized table. This
    test records the effect so it is never mistaken for a bug."""
    tbl = cy.tier1_table("S20")
    assert tbl[-1] <= 4   # only a couple of bits of resolution remain at the tail
    # and the unified bias avoids that quantization (uses exact -log S):
    d = cy.tier1_window("S20")
    from math import log
    assert abs(cy.cy_sieve_bias(d, "S20") - (-log(cy.S20(d)))) < 1e-9


# ==========================================================================
# §2 — Tier 2: recurrence-mod-p generator + documented keep-rule failure
# ==========================================================================

@pytest.mark.parametrize("p", [251, 67, 17])
@pytest.mark.parametrize("seq", ["S20", "S15"])
def test_s2_1_generator_matches_exact(p, seq):
    """T2.1: the fast finite-field generator equals S(d) mod p exactly."""
    f = cy.SEQUENCES[seq]
    for d in range(0, 64):
        assert cy.s_mod_p(d, p, seq) == f(d) % p


def test_s2_1_no_overflow_large_d():
    """Generator stays in [0,p) for large d (never overflows)."""
    for d in (100, 250, 400):
        r = cy.s_mod_p(d, 251, "S20")
        assert 0 <= r < 251


def test_s2_2_keep_rule_is_too_sparse():
    """T2.2 (diagnostic): the proposed 'keep iff S(d)==0 mod 251' rule is
    unusable — density ~0.78% and the nearest kept distance is far (>= 100),
    which would starve a token of local/mid-range context. This test asserts
    the FAILURE, documenting why Tier 2 is disabled in the shipped bias."""
    kept, density, nearest = cy.tier2_keep_rule_density(p=251, N=512, seq="S20")
    assert density < 0.02, "keep-rule unexpectedly dense (rule may have changed)"
    assert nearest is not None and nearest >= 100, (
        "the proposed rule keeps no near tokens — confirms it cannot be a "
        "stand-alone router")


def test_s2_3_tier2_disabled_in_bias():
    """T2.3: the unified bias must NOT route on the failing keep-rule; i.e. the
    bias is finite (never -inf) for every distance in a mid-range band where the
    keep-rule would otherwise have dropped almost everything."""
    for d in range(14, 120):
        b = cy.cy_sieve_bias(d, "S20")
        assert b != float("-inf") and b == b  # finite, not NaN


# ==========================================================================
# §3 — Tier 3: asymptotic log-space penalty
# ==========================================================================

def test_s3_1_constants_are_theory_values():
    """T3.1: constants match the geometry (NOT the proposal's wrong 2.456/1.5)."""
    assert abs(cy.S20_LOG_LAMBDA - log(43.044328670928671)) < 1e-9
    assert abs(cy.S20_LOG_LAMBDA - 3.7622) < 1e-3
    assert cy.S20_BETA == 2.0
    # explicitly reject the proposal's incorrect constants
    assert abs(cy.S20_LOG_LAMBDA - 2.456) > 1.0


@pytest.mark.parametrize("d,max_rel", [(20, 0.001), (50, 0.001), (100, 0.0005),
                                       (200, 0.0005)])
def test_s3_2_penalty_tracks_exact(d, max_rel):
    """T3.2: penalty(d) approximates -log S20(d) to tight relative error
    (theory constants give <0.03% by d=20, improving with d)."""
    exact = -log(cy.S20(d))
    pen = cy.tier3_penalty(d, "S20")
    rel = abs(pen - exact) / abs(exact)
    assert rel < max_rel, f"d={d}: rel.err {rel:.5f} exceeds {max_rel}"


def test_s3_2_error_monotone_improves():
    """T3.2: relative error decreases as d grows (asymptotic regime)."""
    def rel(d):
        exact = -log(cy.S20(d))
        return abs(cy.tier3_penalty(d, "S20") - exact) / abs(exact)
    errs = [rel(d) for d in (30, 60, 120, 200)]
    assert all(errs[i] > errs[i + 1] for i in range(len(errs) - 1))


def test_s3_3_handoff_continuity():
    """T3.3: at the window edge the asymptotic penalty matches the exact decay
    (continuity), and the jump just past the edge is small (no hard cliff)."""
    w = cy.int64_safe_window("S20")  # 13
    # by construction penalty(w) == -log S20(w)
    assert abs(cy.tier3_penalty(w, "S20") - (-log(cy.S20(w)))) < 1e-9
    # one step past the edge: small discrepancy vs exact
    jump = abs(cy.tier3_penalty(w + 1, "S20") - (-log(cy.S20(w + 1))))
    assert jump < 0.01


def test_s3_unified_bias_matches_exact_in_window():
    """The unified bias inside the window equals -log S20(d) (the exact path)."""
    for d in range(0, cy.int64_safe_window("S20") + 1):
        assert abs(cy.cy_sieve_bias(d, "S20") - (-log(cy.S20(d)))) < 1e-6


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call(["pytest", "-v", __file__]))
