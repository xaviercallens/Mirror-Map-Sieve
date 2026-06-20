#!/usr/bin/env python3
"""
compute_s20.py — Compute and verify the first N values of the weight-5 Apéry-like sequence S_20.

S₂₀(n) = Σ_{k=0}^{n} C(n,k)⁴ · C(n+k,k)

This script computes values using exact integer arithmetic (Python's arbitrary
precision integers) and cross-checks against the published table.
"""
from math import comb
import sys

def S20(n: int) -> int:
    """Compute S₂₀(n) = Σ_{k=0}^{n} C(n,k)⁴ · C(n+k,k)."""
    return sum(comb(n, k)**4 * comb(n + k, k) for k in range(n + 1))

# Published table values from the paper (Table 2.1)
EXPECTED = {
    0: 1,
    1: 3,
    2: 55,
    3: 1155,
    4: 29751,
    5: 852753,
    6: 26097499,
    7: 840454275,
    8: 28064517175,
    9: 964417304253,
}

def main():
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    print("=" * 70)
    print("  WEIGHT-5 APÉRY-LIKE SEQUENCE S₂₀(n) — VALUE COMPUTATION")
    print("=" * 70)
    
    all_pass = True
    values = []
    
    for n in range(N):
        val = S20(n)
        values.append(val)
        status = ""
        if n in EXPECTED:
            if val == EXPECTED[n]:
                status = " ✅ matches paper"
            else:
                status = f" ❌ MISMATCH (expected {EXPECTED[n]})"
                all_pass = False
        print(f"  S₂₀({n:2d}) = {val}{status}")
    
    print()
    if all_pass:
        print("✅ ALL VALUES MATCH PUBLISHED TABLE")
    else:
        print("❌ SOME VALUES DO NOT MATCH — INVESTIGATE")
    
    # Output OEIS-format sequence
    print(f"\nOEIS format: {','.join(str(v) for v in values)}")
    
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
