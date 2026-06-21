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


# --- The HARDWARE path: generate S20 mod p from the order-4 recurrence --------
# This is the "generate on the fly in SRAM" claim made concrete. It uses ONLY
# the proved order-4 recurrence  sum_{j=0}^4 P_j(n) S(n+j) = 0  (coefficients in
# src/picard_fuchs/minimal_operator.json), seeded by the first 4 values:
#   S(n+4) = -(P_0(n)S(n)+P_1(n)S(n+1)+P_2(n)S(n+2)+P_3(n)S(n+3)) / P_4(n)  in GF(p)
# HONEST OBSTACLE (found on CPU): the leading coefficient P_4(n) VANISHES mod p
# at ~p/80 points (e.g. n=176 for p=251). At those n the forward step divides by
# zero and the recurrence cannot self-continue; a hardware generator must carry a
# tiny "reseed" table of the true values at the vanishing points. This is a real
# design constraint for the SRAM generator, documented rather than hidden.

import json as _json, os as _os

def _load_operator():
    path = _os.path.join(_os.path.dirname(__file__), "..", "src",
                         "picard_fuchs", "minimal_operator.json")
    path = _os.path.normpath(path)
    with open(path) as fh:
        return _json.load(fh)["coefficients"]      # P_0..P_4, ascending coeffs

_OP_COEFFS = None  # lazy

def _poly_mod(coeffs_asc, n, p):
    val = 0
    for i, c in enumerate(coeffs_asc):
        val = (val + (c % p) * pow(n, i, p)) % p
    return val

def recurrence_vanishing_points(p: int, N: int) -> list[int]:
    """n in [0,N) where the order-4 leading coefficient P_4(n) == 0 (mod p):
    the points where the forward recurrence cannot self-continue and a reseed
    is required. Documents the SRAM-generator obstacle."""
    global _OP_COEFFS
    if _OP_COEFFS is None:
        _OP_COEFFS = _load_operator()
    return [n for n in range(N) if _poly_mod(_OP_COEFFS[4], n, p) == 0]

def s20_mod_p_recurrence(N: int, p: int):
    """Generate [S20(0..N-1) mod p] via the order-4 recurrence in GF(p), the
    hardware-faithful path. Returns (values, reseed_points). At each n where
    P_4(n)==0 the generator reseeds from the true S20 value (the tiny table a
    real SRAM generator would carry); everywhere else it uses ONLY the recurrence.
    """
    global _OP_COEFFS
    if _OP_COEFFS is None:
        _OP_COEFFS = _load_operator()
    P = _OP_COEFFS
    seq = [S20(i) % p for i in range(min(4, N))]   # 4 seed values
    reseed = []
    for n in range(0, N - 4):
        p4 = _poly_mod(P[4], n, p)
        if p4 == 0:
            seq.append(S20(n + 4) % p)              # reseed (table lookup)
            reseed.append(n)
            continue
        acc = sum(_poly_mod(P[j], n, p) * seq[n + j] for j in range(4)) % p
        seq.append((-acc * pow(p4, p - 2, p)) % p)  # GF(p) division
    return seq[:N], reseed


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
                  log_lambda: float = S20_LOG_LAMBDA, beta: float = S20_BETA,
                  tau: float = 1.0) -> float:
    """Asymptotic positional penalty for d beyond the exact window, with an
    optional temperature scalar tau.

        penalty(d) = (1/tau) * ( -d*logλ + β*log d - logC ).

    With tau=1 this is exactly -log S(d) (the raw Calabi-Yau geometry).
    Mathematically the tau form is the bias of S(d)^(1/tau): it preserves the
    shape (the linear slope and the β=2 log-curvature) but rescales steepness.

    WHY tau MATTERS (see tests.md §3T / the τ-attenuation analysis): the raw
    slope logλ = 3.762 is so steep that exp(penalty) underflows FP16 to 0 by
    d≈6, collapsing the model into a ~6-token sliding window and ANNIHILATING
    long-range retrieval (Needle-in-a-Haystack). tau in roughly [8, 1000],
    assigned PER HEAD (à la ALiBi), compresses the decay into a survivable,
    long-range logit range while keeping the topological curvature.
    """
    if logC is None:
        logC = tier3_logC(seq, log_lambda=log_lambda, beta=beta)
    return (-d * log_lambda + beta * log(d) - logC) / tau


def alibi_style_tau_ladder(n_heads: int, log_lambda: float = S20_LOG_LAMBDA):
    """Per-head temperature ladder, chosen so each head's effective CY slope
    logλ/τ_h equals an ALiBi head slope m_h = 2^(-8 h / n_heads).  Hence
    τ_h = logλ / m_h.  Steep heads (small τ) handle local syntax; shallow heads
    (large τ) preserve long-range retrieval. Returns a list of τ per head."""
    return [log_lambda / (2.0 ** (-8.0 * h / n_heads)) for h in range(1, n_heads + 1)]


# ----------------------------------------------------------------------------
# Unified CY-Sieve bias (Tier 1 exact, Tier 3 asymptotic; Tier 2 disabled)
# ----------------------------------------------------------------------------

def cy_sieve_bias(d: int, seq: str = "S20", tau: float = 1.0) -> float:
    """The additive log-space attention bias at token distance d >= 0, with an
    optional temperature scalar tau (see tier3_penalty / alibi_style_tau_ladder).

    The whole bias scales by 1/tau (the S(d)^(1/tau) interpretation applied at
    every distance), so Tier 1 and Tier 3 stay mutually continuous:
      - d within the exact window: bias = (-log S(d)) / tau   (exact integer S(d))
      - d beyond the window:       bias = tier3_penalty(d, tau=tau)

    tau=1 reproduces the raw geometry (which UNDERFLOWS FP16 by d≈6 — do not ship
    it; use a per-head tau ladder instead). Tier 2 is intentionally not applied.
    """
    window = tier1_window(seq)
    if d <= window:
        return (-log(SEQUENCES[seq](d))) / tau
    return tier3_penalty(d, seq, tau=tau)


def attention_weight(d: int, seq: str = "S20", tau: float = 1.0,
                     dtype_min: float = 2.0 ** -24) -> float:
    """exp(bias) — the (unnormalized) relative attention weight at distance d.
    `dtype_min` is the smallest representable positive value (FP16 subnormal by
    default); a weight below it is functionally zero on that hardware."""
    from math import exp
    return exp(cy_sieve_bias(d, seq, tau))


def effective_context(seq: str = "S20", tau: float = 1.0,
                      threshold: float = 0.01, max_d: int = 200000) -> int:
    """Largest distance d at which the attention weight (relative to d=0) still
    exceeds `threshold` — a proxy for usable context length at temperature tau."""
    last = 0
    for d in range(1, max_d):
        if attention_weight(d, seq, tau) >= threshold:
            last = d
        elif d > 16:               # past the window, weight is monotone decreasing
            break
    return last


def build_bias_vector(max_distance: int, seq: str = "S20",
                      tau: float = 1.0) -> list[float]:
    """Convenience: the full additive-bias vector for d = 0..max_distance."""
    return [cy_sieve_bias(d, seq, tau) for d in range(max_distance + 1)]


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
    for d in (14, 30, 100, 200):
        exact = -log(S20(d)); p = tier3_penalty(d)
        print(f"  d={d:3d}: exact={exact:11.4f}  penalty={p:11.4f}  "
              f"rel.err={abs(p-exact)/abs(exact)*100:.4f}%")
    print("\n[S20] Temperature tau — native geometry collapses; tau rescues range:")
    print(f"  tau=1 (native): effective >1% context = {effective_context('S20', 1.0)} tokens"
          f"  (FP16 collapse -> NIAH would fail)")
    for tau in (10, 20, 40, 128, 512):
        print(f"  tau={tau:4d}: effective context = {effective_context('S20', tau):5d} tokens")
    ladder = alibi_style_tau_ladder(8)
    print(f"  per-head ALiBi-style tau ladder (H=8): {[round(t,1) for t in ladder]}")
    print(f"    per-head reach: {[effective_context('S20', t) for t in ladder]} tokens")


if __name__ == "__main__":
    main()
