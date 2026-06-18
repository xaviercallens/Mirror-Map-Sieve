#!/usr/bin/env python3
"""
verify_hypergeometric.py — Verify the ₅F₄ hypergeometric identity for S₂₀.

Theorem: S₂₀(n) = ₅F₄(-n, -n, -n, -n, n+1; 1, 1, 1, 1; 1)

This verifies the identity by computing both sides independently using
exact integer arithmetic for n = 0, ..., N.

The proof is algebraic (Pochhammer symbol manipulation), but this script
provides independent numerical verification.
"""
from math import comb, factorial
import sys

def S20(n: int) -> int:
    """Compute S₂₀(n) via the binomial sum definition."""
    return sum(comb(n, k)**4 * comb(n + k, k) for k in range(n + 1))

def pochhammer(a: int, k: int) -> int:
    """Compute the Pochhammer symbol (a)_k = a(a+1)...(a+k-1)."""
    result = 1
    for i in range(k):
        result *= (a + i)
    return result

def hypergeometric_5F4(n: int) -> int:
    """
    Compute ₅F₄(-n, -n, -n, -n, n+1; 1, 1, 1, 1; 1).
    
    = Σ_{k=0}^{n} [(-n)_k]⁴ · (n+1)_k / [(1)_k]⁴ · 1/k!
    
    Since (1)_k = k!, this simplifies to:
    = Σ_{k=0}^{n} [(-n)_k]⁴ · (n+1)_k / (k!)⁵
    """
    total = 0
    for k in range(n + 1):
        neg_n_k = pochhammer(-n, k)       # (-n)_k
        n_plus_1_k = pochhammer(n + 1, k) # (n+1)_k
        k_fact = factorial(k)              # k!
        
        numerator = neg_n_k**4 * n_plus_1_k
        denominator = k_fact**5
        
        # This must be an exact integer
        assert numerator % denominator == 0, \
            f"Non-integer term at n={n}, k={k}: {numerator}/{denominator}"
        
        total += numerator // denominator
    
    return total

def main():
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    print("=" * 70)
    print("  ₅F₄ HYPERGEOMETRIC IDENTITY VERIFICATION")
    print("=" * 70)
    print(f"\n  S₂₀(n) = ₅F₄(-n, -n, -n, -n, n+1; 1, 1, 1, 1; 1)")
    print(f"\n  Verifying for n = 0, ..., {N}:")
    
    all_pass = True
    for n in range(N + 1):
        binomial_val = S20(n)
        hyper_val = hypergeometric_5F4(n)
        
        if binomial_val == hyper_val:
            print(f"  n = {n:2d}: S₂₀ = {binomial_val:>20d}  ₅F₄ = {hyper_val:>20d}  ✅")
        else:
            print(f"  n = {n:2d}: S₂₀ = {binomial_val}  ₅F₄ = {hyper_val}  ❌ MISMATCH")
            all_pass = False
    
    print()
    # Also verify the ¾-well-poised classification
    print("  Well-poised analysis for ₅F₄(-n,-n,-n,-n,n+1; 1,1,1,1; 1):")
    print("    a₀ = -n, so 1 + a₀ = 1 - n")
    print(f"    a₁ + b₁ = -n + 1 = 1-n  ✅")
    print(f"    a₂ + b₂ = -n + 1 = 1-n  ✅")
    print(f"    a₃ + b₃ = -n + 1 = 1-n  ✅")
    print(f"    a₄ + b₄ = (n+1) + 1 = n+2 ≠ 1-n  ❌")
    print(f"    → ¾-well-poised (3 of 4 conditions hold)")
    
    print()
    if all_pass:
        print(f"✅ HYPERGEOMETRIC IDENTITY VERIFIED FOR ALL n = 0, ..., {N}")
    else:
        print("❌ HYPERGEOMETRIC IDENTITY FAILED")
    
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
