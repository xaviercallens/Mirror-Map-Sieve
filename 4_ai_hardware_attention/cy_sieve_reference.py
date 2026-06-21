#!/usr/bin/env python3
"""
cy_sieve_reference.py — CPU reference implementation of the CY-Sieve attention
positional-bias scheme (the falsifiable engineering bet in `vision.md`).

This is the **reference** (pure standard library, exact where possible) that a
Triton/GPU kernel must match bit-for-bit within tolerance. It implements the
three tiers, and is deliberately honest about Tier 2 (which fails as proposed).

  Tier 1 — exact INT64 local table   (d <= 13 for S20, d <= 16 for S15):
      reciprocal decay  table[d] = floor(2^32 * S(0) / S(d))  in exact integers.
      Zero floating-point drift; in hardware this lives in L1/registers.

  Tier 2 — recurrence-mod-p generator  (RESEARCH; DISABLED as a keep-rule):
      S(d) mod p computed in a finite field (never overflows). The originally
      proposed keep-rule "keep iff S(d) == 0 (mod 251)" is measured here to be
      unusable (~0.78% kept, nearest kept distance 226). We expose the generator
      (correct) and the density diagnostic (documents the failure), but the
      shipped bias does NOT route on it.

  Tier 3 — asymptotic log-space penalty  (d beyond the exact window):
      penalty(d) = -d*log(lambda) + beta*log(d) - logC,  approximating
      -log S(d). The constants are fixed BY THEORY, not fitted:
        lambda = 43.044328670928671   (dominant singularity reciprocal)
        beta   = 2                    (rank-4 MUM / Calabi-Yau 3-fold n^-2 tail)
      logC is fixed by continuity at the window edge d0 (so Tier1<->Tier3 match).

Design rule (see tests.md): a fast kernel that degrades model quality is a
FAILED kernel. This file only provides the bias; quality is judged separately.

Author: SocrateAI Laboratory (X. Callens) + Claude (Opus 4.8). License: MIT.
"""
from __future__ import annotations
from math import comb, log
from fractions import Fraction

# ----------------------------------------------------------------------------
# The sequences (exact integers)
# ----------------------------------------------------------------------------

def S20(n: int) -> int:
    """S_20(n) = sum_k C(n,k)^4 C(n+k,k)  (weight-(4,1))."""
    return sum(comb(n, k) ** 4 * comb(n + k, k) for k in range(n + 1))


def S15(n: int) -> int:
    """S_15(n) = sum_k C(n,k)^3 C(n+k,k)  (slower-growing weight-(3,1) sibling)."""
    return sum(comb(n, k) ** 3 * comb(n + k, k) for k in range(n + 1))


SEQUENCES = {"S20": S20, "S15": S15}

INT64_MAX = 2 ** 63 - 1
# Fixed-point shift for the reciprocal-decay table. It must be large enough that
# floor(2^SHIFT / S(d)) stays >= 1 across the window (S(13)~1.6e18 ~ 2^61), and
# small enough that the numerator 2^SHIFT itself fits a signed INT64 (SHIFT<=62).
# SHIFT=32 (the original naive choice) underflows to 0 by d~8 — caught by the
# monotonicity test. SHIFT=62 keeps the table strictly positive and decreasing.
FIXED_POINT_SHIFT = 62

# Theory-fixed asymptotic constants for S20 (NOT fitted; see docs/PHASE2_FINDINGS).
S20_LOG_LAMBDA = log(43.044328670928671)   # = 3.7622...   (NOT the proposal's 2.456)
S20_BETA = 2.0                              # rank-4 MUM / CY-3-fold n^-2 tail


def int64_safe_window(seq: str = "S20") -> int:
    """Largest d with S(d) <= INT64_MAX (the raw INT64-value window).
    Returns 13 for S20, 16 for S15."""
    f = SEQUENCES[seq]
    d = 0
    while f(d + 1) <= INT64_MAX:
        d += 1
    return d


def tier1_window(seq: str = "S20") -> int:
    """Largest d for which the fixed-point reciprocal table[d] = 2^SHIFT // S(d)
    is still >= 1 (i.e. the table can represent the decay at d). This is the
    usable Tier-1 window and may be one shorter than int64_safe_window when the
    sequence's value exceeds 2^SHIFT inside the value-window.
    Returns 13 for S20, 15 for S15 (with SHIFT=62)."""
    f = SEQUENCES[seq]
    d = 0
    while (1 << FIXED_POINT_SHIFT) // f(d + 1) >= 1:
        d += 1
    return d


# ----------------------------------------------------------------------------
# Tier 1 — exact INT64 reciprocal-decay table
# ----------------------------------------------------------------------------

def tier1_table(seq: str = "S20", window: int | None = None) -> list[int]:
    """Exact fixed-point reciprocal-decay table for d = 0..window.

    table[d] = floor(2^32 * S(0) / S(d))  (S(0)=1, so = floor(2^32 / S(d))).
    table[0] = 2^32 (the maximum), strictly decreasing in d. All entries are
    computed in exact Python integers and fit in INT64 within the window.
    """
    f = SEQUENCES[seq]
    if window is None:
        window = tier1_window(seq)
    s0 = f(0)
    table = []
    for d in range(window + 1):
        sd = f(d)
        table.append((s0 << FIXED_POINT_SHIFT) // sd)
    return table


# ----------------------------------------------------------------------------
# Tier 2 — recurrence-mod-p generator (research; not used as a keep-rule)
# ----------------------------------------------------------------------------

def s_mod_p(d: int, p: int, seq: str = "S20") -> int:
    """S(d) mod p, computed in the finite field without ever forming the huge
    integer (so it is fast for large d, as the hardware path would be).

    S(d) = sum_k C(d,k)^a * C(d+k,k) (mod p), with a=4 (S20) or a=3 (S15).
    We build C(d,k) incrementally; C(d+k,k) is taken mod p via `comb` then
    reduced. The result is identical to `SEQUENCES[seq](d) % p`, which the test
    suite cross-checks on a small range.
    """
    a = 4 if seq == "S20" else 3
    s = 0
    cdk = 1  # C(d,0)
    for k in range(d + 1):
        if k > 0:
            cdk = cdk * (d - k + 1) // k          # exact small integer
        s = (s + pow(cdk % p, a, p) * (comb(d + k, k) % p)) % p
    return s


def tier2_keep_rule_density(p: int = 251, N: int = 2048, seq: str = "S20"):
    """Diagnostic for the PROPOSED keep-rule 'keep iff S(d) == 0 (mod p)'.

    Returns (kept_distances, density, nearest_nonzero_kept). Documents WHY the
    proposed rule is unusable as a sparse-attention router.
    """
    kept = [d for d in range(N) if s_mod_p(d, p, seq) == 0]
    density = len(kept) / N
    nearest = next((d for d in kept if d > 0), None)
    return kept, density, nearest


# ----------------------------------------------------------------------------
# Tier 3 — asymptotic log-space penalty
# ----------------------------------------------------------------------------

def tier3_logC(seq: str = "S20", d0: int | None = None,
               log_lambda: float = S20_LOG_LAMBDA, beta: float = S20_BETA) -> float:
    """Offset logC fixing continuity at the window edge d0:
    penalty(d0) = -log S(d0).  => logC = -d0*logλ + β*log d0 + log S(d0)."""
    if d0 is None:
        d0 = tier1_window(seq)
    f = SEQUENCES[seq]
    return -d0 * log_lambda + beta * log(d0) + log(f(d0))


def tier3_penalty(d: int, seq: str = "S20", logC: float | None = None,
                  log_lambda: float = S20_LOG_LAMBDA, beta: float = S20_BETA) -> float:
    """Asymptotic positional penalty ≈ -log S(d), for d beyond the exact window.

    penalty(d) = -d*logλ + β*log d - logC.   Lower (more negative) = stronger
    decay (less attention) at larger distance.
    """
    if logC is None:
        logC = tier3_logC(seq, log_lambda=log_lambda, beta=beta)
    return -d * log_lambda + beta * log(d) - logC


# ----------------------------------------------------------------------------
# Unified CY-Sieve bias (Tier 1 exact, Tier 3 asymptotic; Tier 2 disabled)
# ----------------------------------------------------------------------------

def cy_sieve_bias(d: int, seq: str = "S20") -> float:
    """The additive log-space attention bias at token distance d >= 0.

    For d within the exact window: bias = -log S(d) computed from the exact
    INT64 table (so it agrees with the integer hardware path).
    For d beyond the window: bias = tier3_penalty(d) (continuous at the edge).

    Tier 2 is intentionally NOT applied (the proposed keep-rule fails; see
    tier2_keep_rule_density and tests.md §2).
    """
    window = tier1_window(seq)
    if d <= window:
        # Inside the exact window the bias is -log S(d) computed from the exact
        # integer S(d) (no quantization). The fixed-point reciprocal `tier1_table`
        # is the *integer-hardware* artifact (tested for exactness in §1); on a
        # GPU one would use it directly, accepting its tail quantization, but the
        # mathematically faithful reference bias uses the exact integer.
        return -log(SEQUENCES[seq](d))
    return tier3_penalty(d, seq)


def build_bias_vector(max_distance: int, seq: str = "S20") -> list[float]:
    """Convenience: the full additive-bias vector for d = 0..max_distance."""
    return [cy_sieve_bias(d, seq) for d in range(max_distance + 1)]


# ----------------------------------------------------------------------------
# Self-report
# ----------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("  CY-Sieve CPU reference — self report")
    print("=" * 70)
    for seq in ("S20", "S15"):
        w = int64_safe_window(seq)
        print(f"\n[{seq}] INT64-safe window: d <= {w} "
              f"(S({w})={SEQUENCES[seq](w)}, S({w+1}) overflows INT64)")
        tbl = tier1_table(seq)
        print(f"  Tier-1 table (fixed-point /2^{FIXED_POINT_SHIFT}), "
              f"d=0..{min(w,6)}: {tbl[:7]}")
    print("\n[S20] Tier-2 proposed keep-rule (p=251, N=512):")
    kept, dens, nearest = tier2_keep_rule_density(p=251, N=512)
    print(f"  kept {len(kept)} distances ({dens*100:.2f}%), nearest nonzero kept = {nearest}")
    print(f"  -> UNUSABLE as a router; Tier 2 disabled in cy_sieve_bias().")
    print("\n[S20] Tier-3 asymptotic penalty vs exact -log S20(d):")
    logC = tier3_logC("S20")
    for d in (14, 30, 100, 200):
        exact = -log(S20(d)); p = tier3_penalty(d)
        print(f"  d={d:3d}: exact={exact:11.4f}  penalty={p:11.4f}  "
              f"rel.err={abs(p-exact)/abs(exact)*100:.4f}%")


if __name__ == "__main__":
    main()
