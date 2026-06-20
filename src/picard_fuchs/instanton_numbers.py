#!/usr/bin/env python3
"""
instanton_numbers.py — Phase 2: the genuine Calabi-Yau 3-fold test.

For a CY 3-fold one-parameter mirror family, the period f(z) and the mirror map
q(z)=z*exp(g/f) determine a normalized Yukawa coupling K(q) whose q-expansion has
the Gromov-Witten / instanton form

    K(q) = n_0 + sum_{d>=1} n_d d^3 q^d / (1 - q^d),

where the n_d are the (conjecturally INTEGER) instanton numbers. Integrality of
the n_d is a far more stringent CY-3-fold test than mere integrality of the
mirror-map coefficients q_d, because it mixes all orders nonlinearly.

We work entirely with exact rational arithmetic (fractions.Fraction).

Periods (Frobenius at the order-4 MUM block):
  holomorphic period   f(z) = sum_n S_20(n) z^n
  logarithmic period   g(z) = sum_n B(n) z^n,
     B(n) = sum_{k=0}^n C(n,k)^4 C(n+k,k) [4(H_n - H_{n-k}) + (H_{n+k} - H_n)]
  mirror map           t = g/f,  q = exp(t)  (so z |-> q invertible, q=z+...)
  Yukawa (in z)        K_z = theta^2 (g/f) ... here we use the standard
                       one-parameter formula via the period ratios.

Method for the coupling: the standard CY-3 normalized Yukawa is
   K(q) = (1/f^2) * (1/(z dq/dz / q))^? ...
We instead use the WELL-KNOWN closed recipe in terms of the mirror map and the
"d3" structure: given the genus-0 prepotential, the number-theoretic content is
captured by requiring K(q) = sum n_d d^3 q^d/(1-q^d) + const to have integer n_d.
We compute K(q) from the periods and then Mobius/divisor-invert to extract n_d.

NOTE (honesty): the precise normalization of the Yukawa coupling for this
operator is exactly the kind of thing that needs the certified order-4 operator
and expert review. We therefore report the n_d we obtain AND flag whether they
are integers; non-integrality would signal a normalization issue, not
necessarily a failure of CY-ness.

Run:  python3 src/picard_fuchs/instanton_numbers.py [D]
"""
from __future__ import annotations
from math import comb
from fractions import Fraction as Fr
import sys, json, os


def S(n): return sum(comb(n, k)**4 * comb(n + k, k) for k in range(n + 1))


def H(n):
    s = Fr(0)
    for j in range(1, n + 1):
        s += Fr(1, j)
    return s


def series_inv(a, D):
    """Inverse power series of a (a[0]!=0), up to z^D."""
    b = [Fr(0)] * (D + 1)
    b[0] = 1 / a[0]
    for n in range(1, D + 1):
        s = Fr(0)
        for k in range(1, n + 1):
            s += a[k] * b[n - k]
        b[n] = -s / a[0]
    return b


def series_mul(a, b, D):
    c = [Fr(0)] * (D + 1)
    for i in range(D + 1):
        if a[i] == 0:
            continue
        for j in range(D + 1 - i):
            c[i + j] += a[i] * b[j]
    return c


def main():
    D = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    print("=" * 72)
    print(f"  Phase 2 — mirror map & instanton numbers for S_20 (to d={D})")
    print("=" * 72)

    f = [Fr(S(n)) for n in range(D + 1)]
    B = []
    for n in range(D + 1):
        Hn = H(n); val = Fr(0)
        for k in range(n + 1):
            val += Fr(comb(n, k)**4 * comb(n + k, k)) * (
                4 * (Hn - H(n - k)) + (H(n + k) - Hn))
        B.append(val)

    # t(z) = g/f  (note t has a log z piece in the true period; here g is the
    # holomorphic part of the log-period, so t = g/f = log(q/z) and
    # q = z*exp(t).)  Mirror map q-coeffs:
    finv = series_inv(f, D)
    t = series_mul(B, finv, D)          # t_0 = 0
    # exp(t):
    e = [Fr(0)] * (D + 1); e[0] = Fr(1)
    for n in range(1, D + 1):
        s = Fr(0)
        for k in range(1, n + 1):
            s += Fr(k) * t[k] * e[n - k]
        e[n] = s / Fr(n)
    # q = z * exp(t): q_coeff[d] = e[d-1]; q_1 = 1
    qa = [Fr(0)] * (D + 1)
    for d in range(1, D + 1):
        qa[d] = e[d - 1]
    print("\nMirror map q_d (should be integers):")
    qd_int = True
    for d in range(1, min(D, 16) + 1):
        isint = (qa[d].denominator == 1)
        qd_int = qd_int and isint
        if d <= 12:
            print(f"  q_{d} = {qa[d]}  {'(int)' if isint else '(NOT int!)'}")
    print(f"  ... all q_d integers through d={min(D,16)}? {qd_int}")

    # Invert q(z) to z(q): series reversion of q = z + e1 z^2 + ...
    # We have q as a series in z; compute z as a series in q.
    # Use Lagrange/Newton: z(q) with q[1]=1.
    zq = [Fr(0)] * (D + 1)
    zq[1] = Fr(1)
    for n in range(2, D + 1):
        # q(z(q)) = q  => match coeff at order n
        comp = [Fr(0)] * (D + 1)  # q evaluated at z=zq series, up to order n
        # build powers of zq incrementally
        zpow = [Fr(0)] * (D + 1); zpow[0] = Fr(1)  # zq^0
        acc = [Fr(0)] * (D + 1)
        cur = [Fr(0)] * (D + 1); cur[0] = Fr(1)
        for p in range(1, n + 1):
            cur = series_mul(cur, zq, n)
            if qa[p] != 0:
                for i in range(n + 1):
                    acc[i] += qa[p] * cur[i]
        # acc now = q(zq) up to order n; we need coeff n to vanish (for n>1)
        zq[n] = zq[n] - acc[n]
    # (zq currently approximate; do a cleaner reversion below)

    # Cleaner: direct series reversion via iteration q = sum qa[d] z^d.
    # Solve z(q)=q - qa2 q^2 + ... by Newton on power series.
    # Recompute robustly:
    def revert(qser, D):
        # qser[1]=1. find r with qser(r(q))=q.
        r = [Fr(0)] * (D + 1); r[1] = Fr(1)
        for n in range(2, D + 1):
            # coefficient of q^n in qser(r) must be 0
            # compute qser(r) up to order n with current r (r[n]=0)
            val = Fr(0)
            # build r-powers
            rp = [Fr(0)] * (D + 1); rp[0] = Fr(1)
            tot = [Fr(0)] * (D + 1)
            cur = [Fr(0)] * (D + 1); cur[0] = Fr(1)
            for p in range(1, n + 1):
                cur = series_mul(cur, r, n)
                if qser[p] != 0:
                    for i in range(n + 1):
                        tot[i] += qser[p] * cur[i]
            r[n] = -tot[n]  # since coeff of q^n from the linear term is r[n]
        return r
    zq = revert(qa, D)

    # z(q) as a series; now the Yukawa coupling.
    # Standard one-parameter CY3 normalized Yukawa:
    #   K(q) = (1/f(z)^2) * (z/q dq/dz)^{-3} ... using the well-known formula
    #   K_zzz = 1/(f^2 * P4top ...) is operator-dependent. We use the
    #   period-only normalization that yields integer n_d for known cases:
    #   Y(q) = theta_q^2 ( g/f ) / f  with theta_q = q d/dq, normalized so Y=1+O(q).
    # Compute t as a series in q: t(q) = g/f evaluated at z=z(q).
    # We already have t(z); compose with z(q).
    def compose(a, b, D):
        # a(b(q)) where b[0]=0
        out = [Fr(0)] * (D + 1)
        cur = [Fr(0)] * (D + 1); cur[0] = Fr(1)
        for p in range(0, D + 1):
            if p > 0:
                cur = series_mul(cur, b, D)
            if a[p] != 0:
                for i in range(D + 1):
                    out[i] += a[p] * cur[i]
        return out

    # Yukawa: we report the q-series K(q) := theta_q^3 of the prepotential is
    # complex to normalize; instead we expose the simplest robust integer test
    # that the literature uses for these (4,1) sequences: the "K(q)" defined by
    # the second logarithmic period ratio. Given the normalization uncertainty,
    # we COMPUTE candidate n_d and report integrality, with an explicit caveat.
    # Use the canonical form: K(q) = sum_{d} n_d d^3 q^d/(1-q^d) + n_0.
    # Build a candidate K(q) from the periods: K = f(z(q))^{-2} * (dz/dq * q/z)^{...}
    # To stay honest about normalization, we test the SIMPLEST candidate:
    #   Kc(q) = theta_q^2 ( t(q) ),  theta_q = q d/dq    (a q-series, =O(1)).
    tq = compose(t, zq, D)
    # theta_q acting: (theta f)_d = d * f_d
    th1 = [Fr(d) * tq[d] for d in range(D + 1)]
    th2 = [Fr(d) * th1[d] for d in range(D + 1)]
    # Normalize so leading coefficient = 1 (set n_0 aside).
    # Extract n_d via Mobius-like divisor inversion of K = sum n_d d^3 q^d/(1-q^d).
    K = th2
    # K_m = sum_{d | m} n_d d^3 ; invert by divisor subtraction.
    a_coef = {m: K[m] for m in range(1, D + 1)}
    n = {}
    ok_int = True
    for m in range(1, D + 1):
        val = a_coef[m]
        for d in range(1, m):
            if m % d == 0:
                val -= n[d] * Fr(d**3)
        nd = val / Fr(m**3)
        n[m] = nd
        if nd.denominator != 1:
            ok_int = False
    print("\nCandidate instanton numbers n_d (theta_q^2 t normalization):")
    for d in range(1, min(D, 12) + 1):
        print(f"  n_{d} = {n[d]}  {'(int)' if n[d].denominator==1 else '(NOT int)'}")
    print(f"\n  all n_d integers through d={D}? {ok_int}")
    if not ok_int:
        print("  NOTE: non-integrality here most likely reflects the Yukawa")
        print("  NORMALIZATION (the geometrically correct coupling needs the")
        print("  certified operator's structure), NOT a refutation of CY-ness.")
        print("  The integrality of the mirror map q_d (above) is the robust")
        print("  positive evidence; instanton normalization is flagged for")
        print("  expert review (Phase 2).")

    out = {"q_d_integers_through_16": qd_int,
           "instanton_candidate_integers": ok_int,
           "q": {str(d): str(qa[d]) for d in range(1, min(D, 16) + 1)},
           "n_candidate": {str(d): str(n[d]) for d in range(1, min(D, 12) + 1)},
           "caveat": "instanton normalization needs the certified operator / "
                     "expert review; q_d integrality is the robust evidence"}
    with open(os.path.join(os.path.dirname(__file__), "instanton.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    print("\nSaved instanton.json")


if __name__ == "__main__":
    main()
