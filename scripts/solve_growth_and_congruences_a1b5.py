#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Growth and Congruence Solver for Callens-Socrates Sequence S15(n)
------------------------------------------------------------------
Finds the peak root x0 and calculates the growth constant G.
Verifies modular super-congruences modulo p^2 and p^3 for small primes.
"""

from math import comb
import scipy.optimize as opt

def compute_apery_like(n: int, a: int, b: int) -> int:
    total = 0
    for k in range(n + 1):
        term = (comb(n, k) ** a) * (comb(n+k, k) ** b)
        total += term
    return total

def main():
    a, b = 1, 5
    
    # 1. Growth Constant Calculation
    # Peak root equation: (1-x)^a * (1+x)^b = x^(a+b)
    # For a=1, b=5: (1-x)(1+x)^5 = x^6
    # 2x^6 + 4x^5 + 5x^4 - 5x^2 - 4x - 1 = 0
    def f(x):
        return 2*x**6 + 4*x**5 + 5*x**4 - 5*x**2 - 4*x - 1
        
    x0 = opt.brentq(f, 0.0, 1.0)
    # G = [x0 * (1-x0)]^(-a) * [(1+x0)/x0]^(b)
    G = (1.0 / (x0 * (1.0 - x0)))**1 * ((1.0 + x0) / x0)**5
    
    print("=============================================")
    print(" 🔬 S15 ANALYTICAL INVARIANTS & CONGRUENCES ")
    print("=============================================")
    print(f"Peak root x0: {x0:.12f}")
    print(f"Growth constant G: {G:.12f}")
    
    # 2. Verify Modular Congruences
    # Check if S15(p*n) == S15(n) (mod p^k) for p in {2, 3, 5}
    # S15 terms
    print("\nVerifying super-congruences...")
    primes = [2, 3, 5]
    results = {}
    
    for p in primes:
        results[p] = {}
        for k in [2, 3]:
            pk = p ** k
            is_congruent = True
            for n in range(1, 4):
                lhs = compute_apery_like(p * n, a, b)
                rhs = compute_apery_like(n, a, b)
                if (lhs - rhs) % pk != 0:
                    is_congruent = False
                    break
            results[p][k] = is_congruent
            print(f"  S15({p}*n) ≡ S15(n) (mod {p}^{k}) [n=1..3]: {'✅ TRUE' if is_congruent else '❌ FALSE'}")
            
    # Export results to json
    out_data = {
        "x0": x0,
        "growth_constant": G,
        "congruences": {f"mod_p_{k}": [p for p in primes if results[p][k]] for k in [2, 3]}
    }
    
    import json
    with open("alexandrie_data/s15_invariants.json", "w") as f_out:
        json.dump(out_data, f_out, indent=2)
    print("\n🎉 Invariants saved to alexandrie_data/s15_invariants.json")

if __name__ == "__main__":
    main()
