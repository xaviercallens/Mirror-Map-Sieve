#!/usr/bin/env python3
"""
find_recurrence.py — Phase 1, Step 1: settle the MINIMAL order of the
holonomic recurrence satisfied by

    S_20(n) = sum_{k=0..n} C(n,k)^4 * C(n+k,k).

This is the load-bearing question of the research plan (docs/RESEARCH_PLAN.md):
the Calabi-Yau dimension is dictated by the minimal Picard-Fuchs operator order
(order 4 => CY 3-fold; order 5 => CY 4-fold). The "weight-5" binomial-factor
count is NOT the classifier.

METHOD (this is exactly what ore_algebra's guesser does under the hood; we use
no external CAS, only Python big-integers and modular linear algebra so it is
fully reproducible):

  A recurrence of order r and coefficient-degree d is
      sum_{j=0}^{r} P_j(n) * S(n+j) = 0,    deg P_j <= d,
  i.e. a linear relation among the (r+1)*(d+1) unknowns {coefficient of n^i in
  P_j}. Each integer n gives one linear equation with entries S(n+j) * n^i.
  We build this matrix over a large prime field GF(p), compute the nullspace
  dimension, and find the (order, degree) "solvability frontier".

  The MINIMAL order is the smallest r for which a nontrivial, *validated*
  nullspace exists at some degree d. We validate a candidate by requiring the
  nullspace to persist when far more equations than unknowns are used (so the
  relation predicts many further terms), and by agreement across two primes.

OUTPUT: a frontier table + a verdict on the minimal order.

This is a rigorous *computation* but not yet a *proof*: a relation found over
GF(p) and validated on N extra terms could in principle fail later. The proof
step (a creative-telescoping certificate, machine-checked) is scaffolded
separately in certify_telescoper.sage. Run:

    python3 src/picard_fuchs/find_recurrence.py

Author: SocrateAI Laboratory. License: MIT.
"""
from __future__ import annotations
from math import comb

# Two large primes (31-bit and a different 31-bit) to guard against an unlucky
# modulus producing a spurious relation. Both are prime.
PRIMES = (2147483647, 2147483629)  # 2^31-1 (Mersenne) and the prime below it


def S(n: int) -> int:
    """Exact S_20(n) (Python arbitrary-precision integers)."""
    return sum(comb(n, k) ** 4 * comb(n + k, k) for k in range(n + 1))


def rref_nullity(rows: list[list[int]], ncols: int, p: int) -> tuple[int, list[list[int]]]:
    """Row-reduce `rows` (list of length-`ncols` int lists) over GF(p).
    Returns (rank, reduced_rows). Nullity = ncols - rank."""
    M = [r[:] for r in rows]
    nrows = len(M)
    pivot_row = 0
    pivot_cols = []
    for col in range(ncols):
        # find a pivot in this column at or below pivot_row
        sel = -1
        for r in range(pivot_row, nrows):
            if M[r][col] % p != 0:
                sel = r
                break
        if sel == -1:
            continue
        M[pivot_row], M[sel] = M[sel], M[pivot_row]
        inv = pow(M[pivot_row][col], p - 2, p)  # modular inverse (p prime)
        M[pivot_row] = [(x * inv) % p for x in M[pivot_row]]
        for r in range(nrows):
            if r != pivot_row and M[r][col] % p != 0:
                factor = M[r][col] % p
                M[r] = [(a - factor * b) % p for a, b in zip(M[r], M[pivot_row])]
        pivot_cols.append(col)
        pivot_row += 1
        if pivot_row == nrows:
            break
    return len(pivot_cols), M


def build_matrix(Svals: list[int], r: int, d: int, n_eqs: int, p: int) -> list[list[int]]:
    """Rows indexed by n = 0..n_eqs-1; columns by (j in 0..r, i in 0..d):
    entry = S(n+j) * n^i  (mod p). Needs Svals up to index n_eqs-1+r."""
    rows = []
    for n in range(n_eqs):
        npow = [pow(n, i, p) for i in range(d + 1)]
        row = []
        for j in range(r + 1):
            sval = Svals[n + j] % p
            for i in range(d + 1):
                row.append((sval * npow[i]) % p)
        rows.append(row)
    return rows


def nullity(Svals, r, d, n_eqs, p):
    ncols = (r + 1) * (d + 1)
    rows = build_matrix(Svals, r, d, n_eqs, p)
    rank, _ = rref_nullity(rows, ncols, p)
    return ncols - rank


def main():
    print("=" * 78)
    print("  Phase 1 — minimal holonomic recurrence order for S_20(n)")
    print("=" * 78)

    MAXN = 200
    print(f"\nComputing S_20(0..{MAXN}) exactly ...")
    Svals = [S(n) for n in range(MAXN + 1)]
    print(f"  S_20(0..9) = {Svals[:10]}")

    # ---- Solvability frontier: for each order r, smallest degree d with a
    #      nontrivial, validated nullspace. --------------------------------
    print("\nSolvability frontier (smallest degree d giving a validated relation):")
    print("  order r |  min degree d  |  unknowns  |  validated?")
    print("  --------+----------------+------------+------------")

    frontier = {}
    for r in range(2, 7):
        found_d = None
        for d in range(0, 20):
            ncols = (r + 1) * (d + 1)
            # Use generously many more equations than unknowns so any relation
            # must predict many further terms (margin = +60).
            n_eqs = ncols + 60
            if n_eqs + r > MAXN:
                break  # not enough precomputed terms
            null_p0 = nullity(Svals, r, d, n_eqs, PRIMES[0])
            if null_p0 >= 1:
                # cross-check on a second prime
                null_p1 = nullity(Svals, r, d, n_eqs, PRIMES[1])
                if null_p1 >= 1:
                    found_d = d
                    frontier[r] = (d, ncols, n_eqs, null_p0, null_p1)
                    break
        if found_d is not None:
            d, ncols, n_eqs, n0, n1 = frontier[r]
            ok = "YES (2 primes agree)" if n0 == n1 else f"DIM MISMATCH {n0} vs {n1}"
            print(f"     {r}    |       {d:2d}       |    {ncols:4d}    |  {ok}")
        else:
            print(f"     {r}    |     (none <=19) |     --     |  no relation found")

    # ---- Verdict on minimal order --------------------------------------
    print("\n" + "-" * 78)
    orders_found = sorted(frontier.keys())
    if orders_found:
        m = orders_found[0]
        d_m = frontier[m][0]
        print(f"MINIMAL ORDER (empirical): r = {m}, achievable at degree d = {d_m}.")
        # explicitly report the failure of all lower orders
        for r in range(2, m):
            print(f"  - order {r}: NO validated relation at any degree <= 19 "
                  f"(over both primes) => minimal order > {r}.")
        print(f"\nInterpretation (per docs/RESEARCH_PLAN.md):")
        if m == 4:
            print("  Minimal order 4  =>  Calabi-Yau 3-fold motive (the Apery-zeta(3)")
            print("  situation). This CONTRADICTS 'CY 4-fold' and SUPPORTS the proposed")
            print("  narrative: ambient 4-torus period, but order-4 => 3-fold motive.")
        elif m == 5:
            print("  Minimal order 5  =>  Calabi-Yau 4-fold motive. This would REHABILITATE")
            print("  the 'weight-5 / 4-fold' language. Revise the narrative accordingly.")
        else:
            print(f"  Minimal order {m} => CY {m-1}-fold motive (per the order/dimension")
            print("  dictionary). Revise the narrative to match.")
    else:
        print("No recurrence found in the tested (order<=6, degree<=19) range.")

    # ---- Strong validation of the minimal-order relation ----------------
    if orders_found:
        m = orders_found[0]
        d_m = frontier[m][0]
        print("\n" + "-" * 78)
        print(f"Extra validation of the order-{m}, degree-{d_m} relation:")
        ncols = (m + 1) * (d_m + 1)
        # Fit using the minimum needed, then check the nullspace stays 1-dim as
        # we add many more equations (a spurious relation would be killed).
        for extra in (0, 20, 40, 80, MAXN - (ncols + m) - 1):
            n_eqs = ncols + extra
            if n_eqs + m > MAXN or n_eqs < ncols:
                continue
            nd = nullity(Svals, m, d_m, n_eqs, PRIMES[0])
            print(f"  equations = unknowns({ncols}) + {extra:4d}  ->  nullspace dim = {nd}")
        print("  (A stable nullspace dim >= 1 as equations grow = the relation")
        print("   genuinely predicts all further computed terms, not a fluke.)")

    print("\nNOTE: this is a rigorous computation, not yet a proof. The certified")
    print("proof requires a creative-telescoping certificate; see")
    print("src/picard_fuchs/certify_telescoper.sage and docs/RESEARCH_PLAN.md.")


if __name__ == "__main__":
    main()
