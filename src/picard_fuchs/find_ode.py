#!/usr/bin/env python3
"""
find_ode.py — Phase 2 GATE: the minimal-order linear ODE for the generating
function f(z) = sum_{n>=0} S_20(n) z^n.

The Calabi-Yau dimension is read off the order of the minimal Picard-Fuchs
DIFFERENTIAL operator (order 4 => CY 3-fold). The recurrence in n is order 4,
but ore_algebra's series-`guess` returned an ODE of order 6 — almost certainly
because the naive operator carries APPARENT singularities. This script finds the
true minimal ODE

    sum_{i=0}^{r} Q_i(z) f^{(i)}(z) = 0,   deg Q_i <= d,

by exact linear algebra on the Taylor coefficients of f, scanning (r, d) for the
smallest order r that admits a validated relation. This is the same rigorous,
no-CAS method used in find_recurrence.py.

Coefficient bookkeeping:
    [z^a] f^{(i)}(z) = (a+i)!/a! * S_20(a+i).
    [z^m] ( z^j f^{(i)}(z) ) = [z^{m-j}] f^{(i)}  (0 if m-j < 0).

Run:  python3 src/picard_fuchs/find_ode.py

Author: SocrateAI Laboratory. License: MIT.
"""
from __future__ import annotations
from math import comb
import json, os

PRIMES = (2147483647, 2147483629)


def S(n: int) -> int:
    return sum(comb(n, k) ** 4 * comb(n + k, k) for k in range(n + 1))


def coeff_fi(a: int, i: int, Svals, p: int) -> int:
    """[z^a] f^{(i)}(z) mod p  =  (a+i)!/a! * S(a+i)  =  falling product * S(a+i)."""
    if a < 0:
        return 0
    fac = 1
    for t in range(1, i + 1):
        fac = (fac * (a + t)) % p          # (a+1)(a+2)...(a+i) = (a+i)!/a!
    return (fac % p) * (Svals[a + i] % p) % p


def rref_rank(rows, ncols, p):
    M = [r[:] for r in rows]
    nrows = len(M); pr = 0; pivots = 0
    for col in range(ncols):
        sel = -1
        for r in range(pr, nrows):
            if M[r][col] % p:
                sel = r; break
        if sel < 0:
            continue
        M[pr], M[sel] = M[sel], M[pr]
        inv = pow(M[pr][col], p - 2, p)
        M[pr] = [(x * inv) % p for x in M[pr]]
        for r in range(nrows):
            if r != pr and M[r][col] % p:
                f = M[r][col] % p
                M[r] = [(a - f * b) % p for a, b in zip(M[r], M[pr])]
        pivots += 1; pr += 1
        if pr == nrows:
            break
    return pivots


def nullity(Svals, r, d, n_eqs, p):
    # unknowns c_{i,j}: i in 0..r (order), j in 0..d (deg). column index = i*(d+1)+j
    ncols = (r + 1) * (d + 1)
    rows = []
    for m in range(n_eqs):
        row = [0] * ncols
        for i in range(r + 1):
            for j in range(d + 1):
                row[i * (d + 1) + j] = coeff_fi(m - j, i, Svals, p)
        rows.append(row)
    return ncols - rref_rank(rows, ncols, p)


def main():
    print("=" * 74)
    print("  Phase 2 gate — minimal linear ODE order for f(z) = sum S_20(n) z^n")
    print("=" * 74)

    MAXN = 240
    Svals = [S(n) for n in range(MAXN + 1)]
    print(f"\nUsing S_20(0..{MAXN}); S_20(0..5) = {Svals[:6]}")

    print("\nSolvability frontier for the ODE (smallest deg d per order r):")
    print("  order r | min deg d | unknowns | validated?")
    print("  --------+-----------+----------+-----------")
    frontier = {}
    for r in range(1, 7):
        for d in range(0, 30):
            ncols = (r + 1) * (d + 1)
            n_eqs = ncols + 40                # heavy over-determination
            if n_eqs + r > MAXN:
                break
            if nullity(Svals, r, d, n_eqs, PRIMES[0]) >= 1 and \
               nullity(Svals, r, d, n_eqs, PRIMES[1]) >= 1:
                frontier[r] = (d, ncols, n_eqs)
                print(f"     {r}    |    {d:2d}     |   {ncols:4d}   |  YES (2 primes)")
                break
        else:
            continue
        # printed
    for r in range(1, 7):
        if r not in frontier:
            print(f"     {r}    |    --     |    --    |  none (deg<=29)")

    print("\n" + "-" * 74)
    if frontier:
        m = min(frontier)
        d_m = frontier[m][0]
        print(f"MINIMAL ODE ORDER (empirical) = {m}, at degree {d_m}.")
        for r in range(1, m):
            print(f"  - order {r}: no validated ODE at any degree <= 29 => order > {r}.")
        dim = m - 1
        print(f"\nInterpretation: minimal differential order {m} <=> Calabi-Yau {dim}-fold")
        print(f"  period (order/dimension dictionary). ", end="")
        if m == 4:
            print("CONFIRMS the CY 3-fold narrative;")
            print("  the order-6 series-guess was inflated by apparent singularities.")
        elif m == 6:
            print("order 6 is unusual; if irreducible it is NOT a")
            print("  standard CY 3-fold operator — investigate factorization.")
        else:
            print("revise the narrative to match.")
        # extra validation
        print(f"\nStability of the order-{m}, degree-{d_m} nullspace as equations grow:")
        ncols = (m + 1) * (d_m + 1)
        for extra in (40, 80, 120, MAXN - ncols - m - 1):
            ne = ncols + extra
            if ne + m <= MAXN and ne >= ncols:
                print(f"  eqs = unknowns({ncols}) + {extra:4d} -> nullity "
                      f"{nullity(Svals, m, d_m, ne, PRIMES[0])}")
        out = {"min_ode_order": m, "min_ode_degree": d_m,
               "cy_dimension_if_irreducible": m - 1,
               "note": "empirical (exact GF(p) nullspace, 2 primes); apparent "
                       "singularities may still allow a lower irreducible core"}
        with open(os.path.join(os.path.dirname(__file__), "min_ode.json"), "w") as fh:
            json.dump(out, fh, indent=2)
        print("\nSaved min_ode.json")
    else:
        print("No ODE found in tested range.")


if __name__ == "__main__":
    main()
