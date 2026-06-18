#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Conjecture Generator — Combinatorial Identity Discovery

Generates candidate combinatorial identities by:
1. Systematic enumeration of binomial coefficient sums
2. Pattern matching against known identity families
3. Randomized coefficient exploration with rational arithmetic

Each candidate is expressed as:
    LHS(n) = RHS(n) for all n ≥ n₀

where LHS and RHS are closed-form expressions involving:
    - Nat.choose (binomial coefficients)
    - Powers of 2, 3, etc.
    - Factorials
    - Products and sums

LESSON FROM ALIEN MATH: Every candidate must be computationally
testable BEFORE formalization. No "assume and derive" patterns.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from fractions import Fraction
from itertools import product
from math import comb, factorial
from pathlib import Path
from typing import Callable, Optional


class IdentityFamily(Enum):
    """Classification of combinatorial identity families."""
    BINOMIAL_SUM = "binomial_sum"           # Σ f(k)·C(n,k)
    WEIGHTED_BINOMIAL = "weighted_binomial"  # Σ k^p·C(n,k)
    CONVOLUTION = "convolution"             # Σ C(n,k)·C(m,n-k)
    ALTERNATING = "alternating"             # Σ (-1)^k·f(k)·C(n,k)
    DOUBLE_SUM = "double_sum"               # ΣΣ f(j,k)·C(n,j)·C(j,k)
    PRODUCT = "product"                     # Π f(k)
    SQUARED = "squared"                     # Σ C(n,k)²
    HARMONIC = "harmonic"                   # Involves H_n = Σ 1/k
    CUSTOM = "custom"                       # Freeform


@dataclass
class CandidateIdentity:
    """A candidate combinatorial identity to verify.

    Attributes:
        name: Human-readable name for the identity
        family: Which family it belongs to
        lhs_expr: String representation of the LHS (for display)
        rhs_expr: String representation of the RHS (for display)
        lhs_func: Callable that computes LHS(n) as a Fraction
        rhs_func: Callable that computes RHS(n) as a Fraction
        min_n: Minimum n for which the identity should hold
        max_test_n: Maximum n tested so far
        status: Current verification status
        lean_statement: Optional Lean 4 statement
        source: Where this identity came from
    """
    name: str
    family: IdentityFamily
    lhs_expr: str
    rhs_expr: str
    lhs_func: Callable[[int], Fraction]
    rhs_func: Callable[[int], Fraction]
    min_n: int = 0
    max_test_n: int = 0
    status: str = "UNTESTED"  # UNTESTED, VERIFIED, FALSIFIED, KNOWN, NEW
    lean_statement: Optional[str] = None
    source: str = "generator"
    test_results: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to JSON-safe dict (excluding callables)."""
        return {
            "name": self.name,
            "family": self.family.value,
            "lhs_expr": self.lhs_expr,
            "rhs_expr": self.rhs_expr,
            "min_n": self.min_n,
            "max_test_n": self.max_test_n,
            "status": self.status,
            "lean_statement": self.lean_statement,
            "source": self.source,
        }


def generate_weighted_binomial_sums() -> list[CandidateIdentity]:
    """Generate identities of the form Σ_{k=0}^{n} k^p · C(n,k) = f(n).

    Known results:
        p=0: Σ C(n,k) = 2^n
        p=1: Σ k·C(n,k) = n·2^(n-1)
        p=2: Σ k²·C(n,k) = n·(n+1)·2^(n-2)
        p=3: Σ k³·C(n,k) = n²·(n+3)·2^(n-3)

    We'll generate and test p=0..6, derive the closed forms,
    and check which ones match known results vs. new.
    """
    candidates = []

    # ── p=0: Σ C(n,k) = 2^n (KNOWN) ──────────────────────────────
    candidates.append(CandidateIdentity(
        name="binomial_sum_p0",
        family=IdentityFamily.BINOMIAL_SUM,
        lhs_expr="Σ_{k=0}^{n} C(n,k)",
        rhs_expr="2^n",
        lhs_func=lambda n: Fraction(sum(comb(n, k) for k in range(n + 1))),
        rhs_func=lambda n: Fraction(2 ** n),
        source="known (Newton's binomial theorem)",
    ))

    # ── p=1: Σ k·C(n,k) = n·2^(n-1) (KNOWN) ────────────────────
    candidates.append(CandidateIdentity(
        name="weighted_binomial_p1",
        family=IdentityFamily.WEIGHTED_BINOMIAL,
        lhs_expr="Σ_{k=0}^{n} k·C(n,k)",
        rhs_expr="n·2^(n-1)",
        lhs_func=lambda n: Fraction(sum(k * comb(n, k) for k in range(n + 1))),
        rhs_func=lambda n: Fraction(n * 2 ** (n - 1)) if n >= 1 else Fraction(0),
        min_n=1,
        source="known (differentiation of (1+x)^n)",
    ))

    # ── p=2: Σ k²·C(n,k) = n·(n+1)·2^(n-2) (KNOWN) ─────────────
    candidates.append(CandidateIdentity(
        name="weighted_binomial_p2",
        family=IdentityFamily.WEIGHTED_BINOMIAL,
        lhs_expr="Σ_{k=0}^{n} k²·C(n,k)",
        rhs_expr="n·(n+1)·2^(n-2)",
        lhs_func=lambda n: Fraction(
            sum(k * k * comb(n, k) for k in range(n + 1))
        ),
        rhs_func=lambda n: Fraction(n * (n + 1) * 2 ** (n - 2)) if n >= 2
                           else Fraction(sum(k * k * comb(n, k) for k in range(n + 1))),
        min_n=2,
        source="known (second derivative)",
    ))

    # ── p=3: Σ k³·C(n,k) = n²·(n+3)·2^(n-3) (KNOWN) ────────────
    candidates.append(CandidateIdentity(
        name="weighted_binomial_p3",
        family=IdentityFamily.WEIGHTED_BINOMIAL,
        lhs_expr="Σ_{k=0}^{n} k³·C(n,k)",
        rhs_expr="n²·(n+3)·2^(n-3)",
        lhs_func=lambda n: Fraction(
            sum(k ** 3 * comb(n, k) for k in range(n + 1))
        ),
        rhs_func=lambda n: Fraction(n * n * (n + 3) * 2 ** (n - 3)) if n >= 3
                           else Fraction(sum(k ** 3 * comb(n, k) for k in range(n + 1))),
        min_n=3,
        source="known (third derivative)",
    ))

    # ── p=4: Σ k⁴·C(n,k) = ? ────────────────────────────────────
    # This is where discovery starts! We compute the LHS and try to
    # find a closed form. The pattern should be:
    # n·(n³ + 6n² + 7n + 1)·2^(n-4) ? Let's test.
    candidates.append(CandidateIdentity(
        name="weighted_binomial_p4",
        family=IdentityFamily.WEIGHTED_BINOMIAL,
        lhs_expr="Σ_{k=0}^{n} k⁴·C(n,k)",
        rhs_expr="n·(n³+6n²+7n+1)·2^(n-4)  [CANDIDATE]",
        lhs_func=lambda n: Fraction(
            sum(k ** 4 * comb(n, k) for k in range(n + 1))
        ),
        rhs_func=lambda n: Fraction(
            n * (n ** 3 + 6 * n ** 2 + 7 * n + 1) * 2 ** (n - 4)
        ) if n >= 4 else Fraction(
            sum(k ** 4 * comb(n, k) for k in range(n + 1))
        ),
        min_n=4,
        source="candidate (polynomial fitting of derivatives)",
    ))

    # ── p=5: Σ k⁵·C(n,k) = ? ────────────────────────────────────
    # Discovery: compute values and attempt closed-form fitting
    candidates.append(CandidateIdentity(
        name="weighted_binomial_p5",
        family=IdentityFamily.WEIGHTED_BINOMIAL,
        lhs_expr="Σ_{k=0}^{n} k⁵·C(n,k)",
        rhs_expr="[TO BE DISCOVERED]",
        lhs_func=lambda n: Fraction(
            sum(k ** 5 * comb(n, k) for k in range(n + 1))
        ),
        rhs_func=lambda n: Fraction(0),  # Placeholder — will be fitted
        min_n=5,
        source="discovery target",
    ))

    # ── p=6: Σ k⁶·C(n,k) = ? ────────────────────────────────────
    candidates.append(CandidateIdentity(
        name="weighted_binomial_p6",
        family=IdentityFamily.WEIGHTED_BINOMIAL,
        lhs_expr="Σ_{k=0}^{n} k⁶·C(n,k)",
        rhs_expr="[TO BE DISCOVERED]",
        lhs_func=lambda n: Fraction(
            sum(k ** 6 * comb(n, k) for k in range(n + 1))
        ),
        rhs_func=lambda n: Fraction(0),  # Placeholder
        min_n=6,
        source="discovery target",
    ))

    return candidates


def generate_squared_binomial_sums() -> list[CandidateIdentity]:
    """Generate identities involving Σ C(n,k)^p for various p.

    Known: Σ C(n,k)² = C(2n, n)  (Vandermonde self-convolution)
    Target: Σ C(n,k)³, Σ C(n,k)⁴, and mixed products.
    """
    candidates = []

    # ── Σ C(n,k)² = C(2n,n) (KNOWN — Vandermonde) ────────────────
    candidates.append(CandidateIdentity(
        name="squared_binomial_vandermonde",
        family=IdentityFamily.SQUARED,
        lhs_expr="Σ_{k=0}^{n} C(n,k)²",
        rhs_expr="C(2n, n)",
        lhs_func=lambda n: Fraction(
            sum(comb(n, k) ** 2 for k in range(n + 1))
        ),
        rhs_func=lambda n: Fraction(comb(2 * n, n)),
        source="known (Vandermonde self-convolution)",
    ))

    # ── Σ C(n,k)³ = ? (KNOWN — Dixon's theorem for special cases) ─
    # Dixon's identity: Σ (-1)^k C(2n,n+k)³ = (3n)!/(n!)³
    # But the unsigned version Σ C(n,k)³ has a known form too:
    # Σ_{k=0}^{n} C(n,k)³ = Σ_{k=0}^{n} C(n,k)²·C(n,k)
    # This equals the Franel number f_n. No simple closed form exists,
    # but it satisfies the recurrence (n+1)²·f_{n+1} = (7n²+7n+2)·f_n + 8n²·f_{n-1}
    candidates.append(CandidateIdentity(
        name="cubed_binomial_franel",
        family=IdentityFamily.SQUARED,
        lhs_expr="Σ_{k=0}^{n} C(n,k)³",
        rhs_expr="Franel number f_n (no simple closed form)",
        lhs_func=lambda n: Fraction(
            sum(comb(n, k) ** 3 for k in range(n + 1))
        ),
        rhs_func=lambda n: Fraction(
            sum(comb(n, k) ** 3 for k in range(n + 1))
        ),  # Self-referential — we're computing it to study it
        source="known (Franel numbers, OEIS A000172)",
    ))

    # ── Σ k·C(n,k)² = n·C(2n-1, n-1) (CANDIDATE) ───────────────
    candidates.append(CandidateIdentity(
        name="weighted_squared_binomial",
        family=IdentityFamily.SQUARED,
        lhs_expr="Σ_{k=0}^{n} k·C(n,k)²",
        rhs_expr="n·C(2n-1, n-1)  [CANDIDATE]",
        lhs_func=lambda n: Fraction(
            sum(k * comb(n, k) ** 2 for k in range(n + 1))
        ),
        rhs_func=lambda n: Fraction(n * comb(2 * n - 1, n - 1)) if n >= 1
                           else Fraction(0),
        min_n=1,
        source="candidate (weighted Vandermonde variant)",
    ))

    # ── Σ k²·C(n,k)² = ? (DISCOVERY TARGET) ─────────────────────
    candidates.append(CandidateIdentity(
        name="weighted_squared_binomial_p2",
        family=IdentityFamily.SQUARED,
        lhs_expr="Σ_{k=0}^{n} k²·C(n,k)²",
        rhs_expr="[TO BE DISCOVERED]",
        lhs_func=lambda n: Fraction(
            sum(k * k * comb(n, k) ** 2 for k in range(n + 1))
        ),
        rhs_func=lambda n: Fraction(0),  # Placeholder
        min_n=1,
        source="discovery target",
    ))

    return candidates


def generate_alternating_sums() -> list[CandidateIdentity]:
    """Generate alternating-sign identities.

    These are often richer because the cancellation reveals
    deeper structure. Many are connected to polynomial evaluation.
    """
    candidates = []

    # ── Σ (-1)^k·C(n,k) = 0 for n≥1 (KNOWN) ─────────────────────
    candidates.append(CandidateIdentity(
        name="alternating_binomial_sum",
        family=IdentityFamily.ALTERNATING,
        lhs_expr="Σ_{k=0}^{n} (-1)^k·C(n,k)",
        rhs_expr="0",
        lhs_func=lambda n: Fraction(
            sum((-1) ** k * comb(n, k) for k in range(n + 1))
        ),
        rhs_func=lambda n: Fraction(0),
        min_n=1,
        source="known ((1-1)^n = 0)",
    ))

    # ── Σ (-1)^k·k·C(n,k) = 0 for n≥2 (KNOWN) ──────────────────
    candidates.append(CandidateIdentity(
        name="alternating_weighted_p1",
        family=IdentityFamily.ALTERNATING,
        lhs_expr="Σ_{k=0}^{n} (-1)^k·k·C(n,k)",
        rhs_expr="0",
        lhs_func=lambda n: Fraction(
            sum((-1) ** k * k * comb(n, k) for k in range(n + 1))
        ),
        rhs_func=lambda n: Fraction(0),
        min_n=2,
        source="known (derivative of (1-x)^n at x=1)",
    ))

    # ── Σ (-1)^k·C(n,k)² = (-1)^{n/2}·C(n, n/2) if n even, 0 if n odd
    # This is known but interesting to verify
    candidates.append(CandidateIdentity(
        name="alternating_squared_binomial",
        family=IdentityFamily.ALTERNATING,
        lhs_expr="Σ_{k=0}^{n} (-1)^k·C(n,k)²",
        rhs_expr="(-1)^(n/2)·C(n, n/2) if n even, 0 if n odd",
        lhs_func=lambda n: Fraction(
            sum((-1) ** k * comb(n, k) ** 2 for k in range(n + 1))
        ),
        rhs_func=lambda n: (
            Fraction((-1) ** (n // 2) * comb(n, n // 2)) if n % 2 == 0
            else Fraction(0)
        ),
        source="known (evaluation of Legendre polynomial at 0)",
    ))

    # ── Σ (-1)^k·C(n,k)·C(n+k, k) = ? (DISCOVERY TARGET) ───────
    # This involves upper and lower binomial coefficients combined
    candidates.append(CandidateIdentity(
        name="alternating_mixed_binomial",
        family=IdentityFamily.ALTERNATING,
        lhs_expr="Σ_{k=0}^{n} (-1)^k·C(n,k)·C(n+k, k)",
        rhs_expr="[TO BE DISCOVERED]",
        lhs_func=lambda n: Fraction(
            sum((-1) ** k * comb(n, k) * comb(n + k, k)
                for k in range(n + 1))
        ),
        rhs_func=lambda n: Fraction(0),  # Placeholder
        min_n=0,
        source="discovery target (mixed upper-lower binomials)",
    ))

    return candidates


def generate_convolution_identities() -> list[CandidateIdentity]:
    """Generate convolution-type identities: Σ C(a,k)·C(b,c-k).

    These generalize Vandermonde's identity and often arise
    in combinatorial proofs.
    """
    candidates = []

    # ── Σ C(n,k)·C(n, n-k) = C(2n, n) (Vandermonde) ─────────────
    candidates.append(CandidateIdentity(
        name="vandermonde_self",
        family=IdentityFamily.CONVOLUTION,
        lhs_expr="Σ_{k=0}^{n} C(n,k)·C(n, n-k)",
        rhs_expr="C(2n, n)",
        lhs_func=lambda n: Fraction(
            sum(comb(n, k) * comb(n, n - k) for k in range(n + 1))
        ),
        rhs_func=lambda n: Fraction(comb(2 * n, n)),
        source="known (Vandermonde's identity, m=n, r=n)",
    ))

    # ── Σ C(2k, k)·C(2(n-k), n-k)·4^(-n) = C(2n,n)·4^(-n) ─────
    # Actually: Σ C(2k,k)·C(2(n-k),n-k) = 4^n
    # This is the central binomial coefficient convolution
    candidates.append(CandidateIdentity(
        name="central_binomial_convolution",
        family=IdentityFamily.CONVOLUTION,
        lhs_expr="Σ_{k=0}^{n} C(2k,k)·C(2(n-k), n-k)",
        rhs_expr="4^n",
        lhs_func=lambda n: Fraction(
            sum(comb(2 * k, k) * comb(2 * (n - k), n - k)
                for k in range(n + 1))
        ),
        rhs_func=lambda n: Fraction(4 ** n),
        source="known (central binomial convolution)",
    ))

    # ── Σ C(n,k)²·C(2n-2k, n-k) = ? (DISCOVERY TARGET) ─────────
    candidates.append(CandidateIdentity(
        name="mixed_convolution_discovery",
        family=IdentityFamily.CONVOLUTION,
        lhs_expr="Σ_{k=0}^{n} C(n,k)²·C(2n-2k, n-k)",
        rhs_expr="[TO BE DISCOVERED]",
        lhs_func=lambda n: Fraction(
            sum(comb(n, k) ** 2 * comb(2 * (n - k), n - k)
                for k in range(n + 1))
        ),
        rhs_func=lambda n: Fraction(0),  # Placeholder
        min_n=0,
        source="discovery target (mixed squared-central convolution)",
    ))

    return candidates


def generate_all_candidates() -> list[CandidateIdentity]:
    """Generate all candidate identities from all families.

    Returns a list of CandidateIdentity objects ready for
    computational falsification.
    """
    all_candidates = []
    all_candidates.extend(generate_weighted_binomial_sums())
    all_candidates.extend(generate_squared_binomial_sums())
    all_candidates.extend(generate_alternating_sums())
    all_candidates.extend(generate_convolution_identities())
    return all_candidates


if __name__ == "__main__":
    # Quick test: generate and print all candidates
    candidates = generate_all_candidates()
    print(f"Generated {len(candidates)} candidate identities:\n")
    for i, c in enumerate(candidates, 1):
        print(f"  [{i:2d}] {c.name}")
        print(f"       LHS: {c.lhs_expr}")
        print(f"       RHS: {c.rhs_expr}")
        print(f"       Family: {c.family.value}, Source: {c.source}")
        print()
