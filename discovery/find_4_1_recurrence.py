#!/usr/bin/env python3
import sys
import sympy as sp
from math import comb

def compute_seq(n, a, b):
    total = 0
    for k in range(n + 1):
        total += (comb(n, k) ** a) * (comb(n + k, k) ** b)
    return total

def fit_recurrence(S, max_d=5, max_m=8):
    n = sp.Symbol('n')
    # Loop order and degree
    for d in range(1, max_d + 1):
        for m in range(1, max_m + 1):
            num_vars = (d + 1) * (m + 1)
            num_eqs = num_vars + 10
            
            if len(S) < num_eqs + d + 15:
                continue
                
            print(f"Trying order d={d}, degree m={m} (vars={num_vars}, eqs={num_eqs})...")
            eqs = []
            for n_val in range(num_eqs):
                row = []
                for i in range(d + 1):
                    for j in range(m + 1):
                        row.append((n_val ** j) * S[n_val + i])
                eqs.append(row)
                
            M = sp.Matrix(eqs)
            ns = M.nullspace()
            
            if ns:
                print(f"  Found nullspace size {len(ns)}! Validating...")
                for sol in ns:
                    is_valid = True
                    val_start = num_eqs
                    val_end = val_start + 10
                    for n_val in range(val_start, val_end):
                        val = 0
                        var_idx = 0
                        for i in range(d + 1):
                            poly_val = 0
                            for j in range(m + 1):
                                poly_val += sol[var_idx] * (n_val ** j)
                                var_idx += 1
                            val += poly_val * S[n_val + i]
                        if sp.simplify(val) != 0:
                            is_valid = False
                            break
                    if is_valid:
                        # Reconstruct
                        terms = []
                        var_idx = 0
                        for i in range(d + 1):
                            poly_expr = 0
                            for j in range(m + 1):
                                poly_expr += sol[var_idx] * (n ** j)
                                var_idx += 1
                            poly_expr = sp.simplify(poly_expr)
                            terms.append(poly_expr)
                        
                        all_coeffs = []
                        for term in terms:
                            if term != 0:
                                p = sp.Poly(term, n)
                                all_coeffs.extend(p.all_coeffs())
                        dens = [sp.fraction(c)[1] for c in all_coeffs if c != 0]
                        lcm = 1
                        for den in dens:
                            lcm = sp.lcm(lcm, den)
                        scaled = [sp.simplify(t * lcm) for t in terms]
                        return {"order": d, "degree": m, "polys": scaled}
    return None

def main():
    print("Computing sequence for C(n,k)^4 * C(n+k,k)^1...")
    S = [compute_seq(n, 4, 1) for n in range(95)]
    print(f"First 10 terms: {S[:10]}")
    res = fit_recurrence(S)
    if res:
        print("🎯 Found recurrence!")
        print(f"Order: {res['order']}, Degree: {res['degree']}")
        polys = res['polys']
        rec_str = " + ".join(f"({polys[i]}) * S(n+{i})" for i in range(res['order'] + 1)) + " = 0"
        print(f"Recurrence: {rec_str}")
    else:
        print("❌ Failed to find recurrence relation.")

if __name__ == "__main__":
    main()
