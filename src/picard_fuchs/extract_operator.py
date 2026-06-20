#!/usr/bin/env python3
"""
extract_operator.py — Phase 1, Step 2: extract the EXACT minimal recurrence.

find_recurrence.py established (over two primes, with strong validation) that
the minimal holonomic recurrence for

    S_20(n) = sum_{k=0..n} C(n,k)^4 * C(n+k,k)

has order 4 and coefficient degree 13. This script reconstructs that recurrence
*exactly over Q* via an exact rational nullspace, normalizes it to primitive
integer polynomials, and verifies

    sum_{j=0}^{4} P_j(n) * S(n+j) = 0

for every n in the computed range (a strong consistency check; not yet a proof).

Requires: sympy. Run:
    python3 src/picard_fuchs/extract_operator.py

Author: SocrateAI Laboratory. License: MIT.
"""
from __future__ import annotations
from math import comb
import sympy as sp


def S(n: int) -> int:
    return sum(comb(n, k) ** 4 * comb(n + k, k) for k in range(n + 1))


ORDER = 4
DEGREE = 13


def main():
    print("=" * 78)
    print("  Phase 1 — exact extraction of the minimal order-4 recurrence")
    print("=" * 78)

    ncols = (ORDER + 1) * (DEGREE + 1)          # 5 * 14 = 70 unknowns
    n_eqs = ncols + 30                            # comfortable overdetermination
    maxn = n_eqs + ORDER
    print(f"\nComputing S_20(0..{maxn}) exactly ...")
    Svals = [S(n) for n in range(maxn + 1)]

    # Build the exact integer matrix: row n, column (j,i) = S(n+j) * n^i.
    print(f"Building {n_eqs} x {ncols} exact matrix and computing nullspace over Q ...")
    rows = []
    for n in range(n_eqs):
        row = []
        for j in range(ORDER + 1):
            s = Svals[n + j]
            for i in range(DEGREE + 1):
                row.append(s * (n ** i))
        rows.append(row)
    M = sp.Matrix(rows)
    ns = M.nullspace()
    print(f"  nullspace dimension over Q = {len(ns)}")
    if len(ns) != 1:
        print("  UNEXPECTED: nullspace is not 1-dimensional; aborting.")
        return

    vec = ns[0]
    # vec entries are already EXACT rationals. Clear denominators via the exact
    # lcm of denominators (do NOT use nsimplify — it can alter exact rationals),
    # then divide by the integer content.
    rats = [sp.Rational(x) for x in vec]
    dens = [r.q for r in rats]
    lcm = sp.ilcm(*dens) if dens else 1
    intvec = [int(r * lcm) for r in rats]
    g = sp.igcd(*[v for v in intvec if v != 0])
    intvec = [v // g for v in intvec]

    # Reassemble P_0..P_4 as polynomials in n.
    n = sp.symbols('n')
    P = []
    for j in range(ORDER + 1):
        coeffs = intvec[j * (DEGREE + 1):(j + 1) * (DEGREE + 1)]   # c_i for n^i
        poly = sum(c * n ** i for i, c in enumerate(coeffs))
        P.append(sp.expand(poly))

    print("\nMinimal recurrence  sum_{j=0}^4 P_j(n) * S(n+j) = 0,  with:")
    for j in range(ORDER + 1):
        deg = int(sp.degree(P[j], n)) if P[j] != 0 else -1
        lead = int(sp.LC(sp.Poly(P[j], n))) if P[j] != 0 else 0
        print(f"  deg P_{j} = {deg:2d},  leading coeff = {lead}")

    # ---- exact verification on ALL computed terms ----------------------
    print("\nVerifying the recurrence on all computed n ...")
    P_funcs = [sp.Poly(p, n) for p in P]
    ok = True
    checked = 0
    for nn in range(0, maxn - ORDER + 1):
        total = sum(int(P_funcs[j].eval(nn)) * Svals[nn + j] for j in range(ORDER + 1))
        if total != 0:
            ok = False
            print(f"  FAIL at n={nn}: residual = {total}")
            break
        checked += 1
    if ok:
        print(f"  PASS: recurrence holds exactly for all {checked} tested n "
              f"(n = 0..{maxn - ORDER}).")

    # ---- report the leading coefficient's roots (apparent singularities) -
    print("\nLeading coefficient P_4(n) factorization (over Z):")
    fac = sp.factor(P[ORDER])
    print(f"  P_4(n) = {fac}")
    print("\n(The singular points of the operator come from P_4; these feed Phase 2/3:")
    print(" apparent singularities, MUM/conifold structure, and rigid fibers.)")

    # ---- save the operator to JSON for downstream phases ---------------
    import json
    out = {
        "sequence": "S_20(n) = sum_k C(n,k)^4 C(n+k,k)",
        "order": ORDER,
        "degree": DEGREE,
        "convention": "sum_{j=0}^4 P_j(n) * S(n+j) = 0; P_j = sum_i coeffs[j][i] * n^i",
        "coefficients": [
            [int(c) for c in (intvec[j * (DEGREE + 1):(j + 1) * (DEGREE + 1)])]
            for j in range(ORDER + 1)
        ],
        "verified_upto_n": maxn - ORDER,
        "status": "computed and verified over the tested range; NOT yet a proof "
                  "(see certify_telescoper.sage)",
    }
    import os
    outpath = os.path.join(os.path.dirname(__file__), "minimal_operator.json")
    with open(outpath, "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"\nSaved exact operator coefficients to {outpath}")


if __name__ == "__main__":
    main()
