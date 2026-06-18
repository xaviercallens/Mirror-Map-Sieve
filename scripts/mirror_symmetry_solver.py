#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Mirror Symmetry Solver for Callens-Schmidt Sequence S20(n)
-----------------------------------------------------------
Computes the exact terms of S20(n) and its canonical logarithmic period
sequence B(n), recursively computes the mirror map q(z) coefficients,
verifies their integrality, and exports results to JSON.
"""

import os
import json
from math import comb
from fractions import Fraction
from pathlib import Path

def series_power(e, p, N):
    f = [Fraction(0)] * N
    f[0] = Fraction(1)
    for j in range(1, N):
        val = Fraction(0)
        for l in range(1, j + 1):
            val += (l * (p + 1) - j) * e[l] * f[j - l]
        f[j] = val / j
    return f

def main():
    N = 16 # compute up to z^15 (q_16)
    
    # Harmonic numbers helper
    def H(m):
        return sum(Fraction(1, i) for i in range(1, m + 1)) if m > 0 else Fraction(0)

    # Holomorphic period coefficients S(n)
    def S20(n):
        return sum(comb(n, k)**4 * comb(n+k, k) for k in range(n + 1))
        
    # Logarithmic period coefficients B(n)
    def B20(n):
        total = Fraction(0)
        for k in range(n + 1):
            term = comb(n, k)**4 * comb(n+k, k)
            h_factor = 3*H(n) + H(n+k) - 4*H(n-k)
            total += term * h_factor
        return total

    print("Computing S20 and B20 terms...")
    S = [Fraction(S20(i)) for i in range(N)]
    B = [B20(i) for i in range(N)]
    
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
        "sequence_name": "Callens-Schmidt Sequence",
        "symbol": "S_20",
        "formula": "S_{20}(n) = \\sum_{k=0}^n \\binom{n}{k}^4 \\binom{n+k}{k}",
        "logarithmic_formula": "B_{20}(n) = \\sum_{k=0}^n \\binom{n}{k}^4 \\binom{n+k}{k} (3 H_n + H_{n+k} - 4 H_{n-k})",
        "mirror_map_integrality": all_integral,
        "mirror_map_coefficients": mirror_map_coeffs,
        "first_few_terms": [int(S[i]) for i in range(10)]
    }

    # Save to alexandrie_data
    out_dir = Path("/Users/xcallens/xdev/SocrateAI-Scientific-Agora/alexandrie_data")
    os.makedirs(out_dir, exist_ok=True)
    out_file = out_dir / "mirror_symmetry_results.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"🎉 Mirror Symmetry results successfully written to {out_file}")
    if all_integral:
        print("✅ Success: The mirror map coefficients are confirmed to be integers!")
    else:
        print("⚠️ Warning: Non-integer coefficients found in the mirror map.")

if __name__ == "__main__":
    main()
