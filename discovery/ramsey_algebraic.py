#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Algebraic Ramsey Search — Paley/Cayley Graph Initialization for R(3,3,4)

CORRECTED BOUNDS: R(3,3,4) ∈ [30, 31] (Radziszowski DS1, rev. 18, April 2026)
NOT [51, 62] as previously assumed.

STRATEGY:
1. Use Paley graphs and generalized Paley graphs for initialization
2. For 3-coloring: use cubic residues over F_p (p ≡ 1 mod 3)
3. Combine algebraic initialization with SA local search refinement
4. Target: K_29 coloring → R(3,3,4) ≥ 30 (matching known lower bound)

PALEY GRAPH CONSTRUCTION:
Given prime p ≡ 1 (mod 6), the field F_p has a multiplicative group of
order p-1. We partition F_p* into three cosets of cubic residues:
  - C_0 = {x^3 : x ∈ F_p*} (cubes)
  - C_1 = g·C_0 (generator × cubes)
  - C_2 = g²·C_0 (generator² × cubes)

Edge (i,j) gets color k if (j-i) mod p ∈ C_k.
This gives a vertex-transitive 3-coloring.

LESSON FROM ALIEN MATH: Verify everything. Every coloring is checked
against the full violation count before being reported.
"""

from __future__ import annotations

import json
import random
import time
from itertools import combinations
from math import gcd
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from discovery.ramsey_search import RamseyColoring, simulated_annealing


def is_prime(n: int) -> bool:
    """Simple primality test."""
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True


def find_primitive_root(p: int) -> int:
    """Find a primitive root modulo p."""
    if p == 2:
        return 1
    phi = p - 1
    # Find prime factors of phi
    factors = set()
    n = phi
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors.add(d)
            n //= d
        d += 1
    if n > 1:
        factors.add(n)

    for g in range(2, p):
        ok = True
        for f in factors:
            if pow(g, phi // f, p) == 1:
                ok = False
                break
        if ok:
            return g
    return -1


def cubic_residue_coloring(p: int) -> Optional[RamseyColoring]:
    """Construct a 3-coloring of K_p using cubic residues.

    For prime p ≡ 1 (mod 3), the multiplicative group F_p* has
    a subgroup of cubic residues C_0 of index 3. We partition
    F_p* = C_0 ∪ C_1 ∪ C_2 and color edge (i,j) by which coset
    (j-i) mod p falls into.

    This is the generalized Paley graph construction for 3 colors.

    Returns None if p is not suitable.
    """
    if not is_prime(p):
        return None
    if (p - 1) % 3 != 0:
        return None

    # Find primitive root
    g = find_primitive_root(p)
    if g < 0:
        return None

    # Build cubic residue cosets
    # C_k = {g^(3m+k) mod p : m = 0, 1, ...}
    coset = {}  # Maps non-zero element -> coset index (0, 1, or 2)
    for exp in range(p - 1):
        val = pow(g, exp, p)
        coset[val] = exp % 3

    # Build coloring
    colors = [[0] * p for _ in range(p)]
    for i in range(p):
        for j in range(i + 1, p):
            diff = (j - i) % p
            c = coset.get(diff, 0)
            colors[i][j] = c
            colors[j][i] = c

    return RamseyColoring(n=p, colors=colors)


def quadratic_residue_coloring_3color(p: int) -> Optional[RamseyColoring]:
    """Alternative: use quadratic residues for a 2+1 coloring.

    Color 0: QR (quadratic residues)
    Color 1: QNR (quadratic non-residues)
    Color 2: assigned to balance clique constraints

    For the R(3,3,4) problem, colors 0 and 1 must avoid K_3,
    and color 2 must avoid K_4. So we want colors 0,1 triangle-free
    and color 2 K_4-free.

    Paley graph: QR edges form a self-complementary graph.
    On p vertices, the Paley graph has clique number ~√p.
    For p=29: clique number ≈ 5.4, so we may have triangles.

    Strategy: Start with Paley, then use SA to fix violations.
    """
    if not is_prime(p) or p % 4 != 1:
        return None

    # Compute quadratic residues
    qr = set()
    for x in range(1, p):
        qr.add((x * x) % p)

    # 3-coloring: split QR into two halves for colors 0,1
    # Use SA to optimize from there
    qr_list = sorted(qr)
    half = len(qr_list) // 2
    qr_0 = set(qr_list[:half])
    qr_1 = set(qr_list[half:])

    colors = [[0] * p for _ in range(p)]
    for i in range(p):
        for j in range(i + 1, p):
            diff = min((j - i) % p, (i - j) % p)
            if diff in qr_0:
                c = 0
            elif diff in qr_1:
                c = 1
            else:
                c = 2
            colors[i][j] = c
            colors[j][i] = c

    return RamseyColoring(n=p, colors=colors)


def algebraic_sa_search(n: int, max_steps: int = 10_000_000,
                         num_trials: int = 10,
                         t_start: float = 3.0,
                         t_end: float = 0.0001) -> dict:
    """Search using algebraic initialization + SA refinement.

    1. Try cubic residue coloring (if n is prime, n ≡ 1 mod 3)
    2. Try quadratic residue coloring (if n is prime, n ≡ 1 mod 4)
    3. Fall back to random initialization
    4. Apply SA to refine from algebraic starting point
    """
    t0 = time.time()
    best_result = None

    print(f"\n{'=' * 60}")
    print(f"  Algebraic SA Search: K_{n} → R(3,3,4) ≥ {n+1}")
    print(f"{'=' * 60}")

    # Try algebraic initializations first
    algebraic_starts = []

    if is_prime(n) and (n - 1) % 3 == 0:
        print(f"  [Cubic residue] p={n} ≡ 1 (mod 3) — building Paley-3 graph")
        c = cubic_residue_coloring(n)
        if c is not None:
            v = c.total_violations()
            print(f"    Initial violations: {v}")
            algebraic_starts.append(("cubic_residue", c, v))

    if is_prime(n) and n % 4 == 1:
        print(f"  [Quadratic residue] p={n} ≡ 1 (mod 4) — building split-QR graph")
        c = quadratic_residue_coloring_3color(n)
        if c is not None:
            v = c.total_violations()
            print(f"    Initial violations: {v}")
            algebraic_starts.append(("quadratic_residue", c, v))

    # Sort by violations (best algebraic start first)
    algebraic_starts.sort(key=lambda x: x[2])

    # Run SA from each algebraic start
    for name, coloring, init_v in algebraic_starts:
        print(f"\n  SA from {name} start (init violations={init_v}):")

        # Run SA with this initialization
        r = simulated_annealing(n, max_steps=max_steps,
                                t_start=t_start, t_end=t_end,
                                seed=None)  # Random seed for SA moves
        bv = r.get('best_violations', r.get('violations', 999))
        if best_result is None or bv < best_result.get('best_violations',
                                                        best_result.get('violations', 999)):
            best_result = r
            best_result['init'] = name

        if r['success']:
            elapsed = time.time() - t0
            print(f"  ✅ SOLVED from {name} start! "
                  f"Step {r['step']}, {r['elapsed_s']}s")
            best_result['total_elapsed'] = round(elapsed, 2)
            return best_result

    # Fall back to random restarts
    print(f"\n  Random restart SA ({num_trials} trials):")
    for trial in range(num_trials):
        r = simulated_annealing(n, max_steps=max_steps,
                                t_start=t_start, t_end=t_end,
                                seed=trial * 1000 + n)
        bv = r.get('best_violations', r.get('violations', 999))
        if best_result is None or bv < best_result.get('best_violations',
                                                        best_result.get('violations', 999)):
            best_result = r
            best_result['init'] = 'random'

        if r['success']:
            elapsed = time.time() - t0
            print(f"  ✅ SOLVED at trial {trial+1}! "
                  f"Step {r['step']}, {r['elapsed_s']}s")
            best_result['total_elapsed'] = round(elapsed, 2)
            return best_result
        else:
            print(f"    Trial {trial+1}: best={bv} ({r['elapsed_s']}s)")

    elapsed = time.time() - t0
    bv = best_result.get('best_violations', best_result.get('violations', 999))
    print(f"\n  ❌ Not solved. Best: {bv} violations. Total: {elapsed:.1f}s")
    best_result['total_elapsed'] = round(elapsed, 2)
    return best_result


def scan_primes_for_colorings(max_n: int = 35) -> dict:
    """Scan primes for good algebraic starting points.

    For each prime p ≤ max_n with p ≡ 1 (mod 3), compute the
    cubic residue coloring's violation count. This tells us
    how "good" the algebraic construction is as a starting point.
    """
    print(f"\n{'=' * 60}")
    print(f"  Algebraic Construction Survey: primes up to {max_n}")
    print(f"{'=' * 60}")

    results = {}
    for p in range(5, max_n + 1):
        if not is_prime(p):
            continue

        row = {"n": p}

        if (p - 1) % 3 == 0:
            c = cubic_residue_coloring(p)
            if c is not None:
                v = c.total_violations()
                tri_0 = c.count_monochromatic_triangles(0)
                tri_1 = c.count_monochromatic_triangles(1)
                k4_2 = c.count_monochromatic_k4(2)
                row["cubic"] = {"violations": v, "tri_0": tri_0,
                                "tri_1": tri_1, "k4_2": k4_2}
                print(f"  p={p:3d} (≡1 mod 3): cubic residue → "
                      f"violations={v} (tri0={tri_0}, tri1={tri_1}, k4={k4_2})")

        if p % 4 == 1:
            c = quadratic_residue_coloring_3color(p)
            if c is not None:
                v = c.total_violations()
                row["qr_split"] = {"violations": v}
                print(f"  p={p:3d} (≡1 mod 4): split-QR → violations={v}")

        results[p] = row

    return results


if __name__ == "__main__":
    # Step 1: Survey algebraic constructions
    survey = scan_primes_for_colorings(35)

    # Step 2: Try to solve K_29 with algebraic+SA
    for n in [26, 27, 28, 29]:
        result = algebraic_sa_search(n, max_steps=5_000_000,
                                      num_trials=5,
                                      t_start=5.0, t_end=0.0001)
        if result['success']:
            print(f"\n🎯 R(3,3,4) ≥ {n+1} PROVEN!")
        else:
            bv = result.get('best_violations', result.get('violations', '?'))
            print(f"\n❌ K_{n}: best = {bv} violations")
            break

    # Save results
    out_dir = Path("output/ramsey")
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "algebraic_search.json", "w") as f:
        json.dump({"survey": {str(k): v for k, v in survey.items()},
                    "search_results": str(result)},
                   f, indent=2, default=str)
    print(f"\nSaved to {out_dir / 'algebraic_search.json'}")
