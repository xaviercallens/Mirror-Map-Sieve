#!/usr/bin/env python3
"""
verify_mirror_map.py — Verify mirror map integrality for S₂₀.

Computes the mirror map q(z) = z · exp(g(z)/f(z)) associated with S₂₀
using exact rational arithmetic (Python's fractions.Fraction).

Verifies: q_d ∈ ℤ for d = 2, ..., D.

Reference: Lian–Yau integrality conjecture; verified computationally
through d=16 in the paper.
"""
from math import comb
from fractions import Fraction
import sys

def S20(n: int) -> int:
    """Compute S₂₀(n) = Σ_{k=0}^{n} C(n,k)⁴ · C(n+k,k)."""
    return sum(comb(n, k)**4 * comb(n + k, k) for k in range(n + 1))

def harmonic_sum(n: int) -> Fraction:
    """H(n) = Σ_{j=1}^{n} 1/j (exact rational)."""
    return sum(Fraction(1, j) for j in range(1, n + 1))

def compute_mirror_map(D: int) -> list[Fraction]:
    """
    Compute mirror map coefficients q_d for d = 0, ..., D.
    
    The holomorphic period: f(z) = Σ S₂₀(n) z^n
    The logarithmic period: g(z) = Σ S₂₀(n) · H_n · z^n
      where H_n = 4·H(n) - H(n) = 3·H(n) for the (4,1) case.
      
    Actually, for the weight-(a,b)=(4,1) case:
      H_n = a·Σ_{j=1}^{n} 1/j + b·Σ_{j=1}^{n} 1/j = (a+b)·H(n) = 5·H(n)
      
    But the standard Calabi-Yau convention uses:
      B(n) = Σ_{k=0}^{n} C(n,k)^4 · C(n+k,k) · (5·H(n) - 4·H(k) - H(n+k) + H(n-k))
      ≈ simplified harmonic weight
      
    We use the standard definition:
      h_n = Σ_{k=0}^{n} C(n,k)^4 · C(n+k,k) · Σ_{j=1}^{k} (5/(j) - 4*(-1)^{j+1}·...)
      
    For computational correctness we use the simpler approach:
      B(n) = Σ_{k=0}^{n} C(n,k)^4 · C(n+k,k) · [4·Σ_{j=n-k+1}^{n} 1/j + Σ_{j=n+1}^{n+k} 1/j]
    """
    # Compute f-coefficients (holomorphic period)
    f = [Fraction(S20(n)) for n in range(D + 1)]
    
    # Compute B-coefficients (logarithmic period numerator)
    # B(n) = Σ_{k=0}^{n} C(n,k)^4 · C(n+k,k) · [4·(H_n - H_{n-k}) + (H_{n+k} - H_n)]
    B = []
    for n in range(D + 1):
        Hn = harmonic_sum(n)
        val = Fraction(0)
        for k in range(n + 1):
            Hnk = harmonic_sum(n - k)
            Hnpk = harmonic_sum(n + k)
            weight = 4 * (Hn - Hnk) + (Hnpk - Hn)
            val += Fraction(comb(n, k)**4 * comb(n + k, k)) * weight
        B.append(val)
    
    # h_n = B(n) / S20(n) for the ratio, but we work with power series:
    # g(z) = Σ B(n) z^n
    # q(z) = z · exp(g(z) / f(z))
    
    # First compute ratio r(z) = g(z)/f(z) as power series
    # r_0 = B(0)/f(0) = 0/1 = 0
    # Then r_n = (B(n) - Σ_{j=1}^{n-1} r_j · f(n-j)) / f(0)
    r = [Fraction(0)] * (D + 1)
    for n in range(1, D + 1):
        r[n] = B[n]
        for j in range(1, n):
            r[n] -= r[j] * f[n - j]
        r[n] /= f[0]
    
    # Now compute exp(r(z)) as power series e_n
    # e_0 = 1, e_n = (1/n) Σ_{k=1}^{n} k · r_k · e_{n-k}
    e = [Fraction(0)] * (D + 1)
    e[0] = Fraction(1)
    for n in range(1, D + 1):
        for k in range(1, n + 1):
            e[n] += Fraction(k) * r[k] * e[n - k]
        e[n] /= Fraction(n)
    
    # q(z) = z · exp(r(z)), so q_d = e_{d-1} for d >= 1
    # q_0 = 0, q_1 = 1, q_d = e_{d-1} for d >= 2
    q = [Fraction(0)] * (D + 1)
    for d in range(1, D + 1):
        q[d] = e[d - 1]
    
    return q

# Expected values from the paper (Table 6.1)
EXPECTED_Q = {
    2: 9,
    3: 165,
    4: 4110,
    5: 111075,
    6: 3316785,
    7: 104271733,
    8: 3421974692,
    9: 115918914756,
    10: 4027088171898,
    11: 142793489195634,
    12: 5149415166799466,
    13: 188353171046524999,
    14: 6973330284143733181,
    15: 260877511906858891334,
    16: 9848682801654949278015,
}

def main():
    D = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    print("=" * 70)
    print("  MIRROR MAP INTEGRALITY VERIFICATION (EXACT RATIONAL ARITHMETIC)")
    print("=" * 70)
    
    print(f"\nComputing mirror map coefficients q_d for d = 1, ..., {D}...")
    q = compute_mirror_map(D)
    
    all_integer = True
    all_match = True
    
    print(f"\nResults:")
    for d in range(1, D + 1):
        is_int = q[d].denominator == 1
        int_status = "✅ ∈ ℤ" if is_int else "❌ ∉ ℤ"
        
        match_status = ""
        if d in EXPECTED_Q:
            if is_int and int(q[d]) == EXPECTED_Q[d]:
                match_status = " (matches paper)"
            elif is_int:
                match_status = f" ❌ MISMATCH (expected {EXPECTED_Q[d]})"
                all_match = False
        
        if is_int:
            print(f"  q_{d:2d} = {int(q[d]):>30d}  {int_status}{match_status}")
        else:
            print(f"  q_{d:2d} = {q[d]}  {int_status}")
            all_integer = False
    
    print()
    if all_integer:
        print(f"✅ ALL q_d ∈ ℤ FOR d = 1, ..., {D}")
    else:
        print(f"❌ SOME q_d ∉ ℤ — INTEGRALITY FAILS")
    
    if all_match:
        print("✅ ALL VALUES MATCH PAPER TABLE")
    else:
        print("❌ SOME VALUES DO NOT MATCH PAPER")
    
    return 0 if (all_integer and all_match) else 1

if __name__ == "__main__":
    sys.exit(main())
