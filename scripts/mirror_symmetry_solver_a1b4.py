#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Mirror Symmetry Solver for Callens-Agora Sequence S14(n)
-----------------------------------------------------------
Computes the exact terms of S14(n) and its canonical logarithmic period
sequence B14(n), recursively computes the mirror map q(z) coefficients,
verifies their integrality, and exports results to JSON.
"""

import os
import json
from math import comb
from fractions import Fraction
from pathlib import Path

def main():
    N = 16 # compute up to z^15 (q_16)
    
    # Harmonic numbers helper
    def H(m):
        return sum(Fraction(1, i) for i in range(1, m + 1)) if m > 0 else Fraction(0)

    # Holomorphic period coefficients S(n)
    def S14(n):
        return sum(comb(n, k) * comb(n+k, k)**4 for k in range(n + 1))
        
    # Logarithmic period coefficients B(n)
    def B14(n):
        total = Fraction(0)
        for k in range(n + 1):
            term = comb(n, k) * comb(n+k, k)**4
            h_factor = 4*H(n+k) - H(n-k)
            total += term * h_factor
        return total

    print("Computing S14 and B14 terms...")
    S = [Fraction(S14(i)) for i in range(N)]
    B = [B14(i) for i in range(N)]
    
    # 1. Compute h_n coefficients: h(z) = g(z)/f(z)
    # h_n = B(n) - sum_{k=1}^{n-1} S(n-k) h_k
    h = [Fraction(0)] * N
    for n_idx in range(1, N):
        val = B[n_idx]
        for k in range(1, n_idx):
            val -= S[n_idx - k] * h[k]
        h[n_idx] = val

    # 2. Compute e_n coefficients: E(z) = exp(h(z))
    # e_n = h_n + (1/n) * sum_{k=1}^{n-1} k h_k e_{n-k}
    e = [Fraction(0)] * N
    e[0] = Fraction(1)
    for n_idx in range(1, N):
        val = h[n_idx]
        sum_val = Fraction(0)
        for k in range(1, n_idx):
            sum_val += k * h[k] * e[n_idx - k]
        val += sum_val / n_idx
        e[n_idx] = val

    # q(z) = z E(z) = z + q_2 z^2 + q_3 z^3 + ...
    # q_d = e_{d-1} for d >= 2
    mirror_map_coeffs = []
    all_integral = True
    
    for m in range(2, N + 1):
        coeff = e[m - 1]
        is_integer = (coeff.denominator == 1)
        if not is_integer:
            all_integral = False
        mirror_map_coeffs.append({
            "m": m,
            "coefficient": str(coeff),
            "is_integer": is_integer,
            "value": int(coeff) if is_integer else float(coeff)
        })

    # Prepare export dictionary
    results = {
        "sequence_name": "Callens-Agora Sequence",
        "symbol": "S_14",
        "formula": "S_{14}(n) = \\sum_{k=0}^n \\binom{n}{k} \\binom{n+k}{k}^4",
        "logarithmic_formula": "B_{14}(n) = \\sum_{k=0}^n \\binom{n}{k} \\binom{n+k}{k}^4 (4 H_{n+k} - H_{n-k})",
        "mirror_map_integrality": all_integral,
        "mirror_map_coefficients": mirror_map_coeffs,
        "first_few_terms": [int(S[i]) for i in range(10)]
    }

    # Save to alexandrie_data
    out_dir = Path("/Users/xcallens/xdev/SocrateAI-Scientific-Agora/alexandrie_data")
    os.makedirs(out_dir, exist_ok=True)
    out_file = out_dir / "mirror_symmetry_results_a1b4.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"🎉 Mirror Symmetry results successfully written to {out_file}")
    for c in mirror_map_coeffs[:8]:
        print(f"  q_{c['m']} = {c['coefficient']} (integer: {c['is_integer']})")
    if all_integral:
        print("✅ Success: The mirror map coefficients are confirmed to be integers!")
    else:
        print("⚠️ Warning: Non-integer coefficients found in the mirror map.")

if __name__ == "__main__":
    main()
