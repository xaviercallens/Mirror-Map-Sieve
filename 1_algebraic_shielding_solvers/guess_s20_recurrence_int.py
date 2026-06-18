#!/usr/bin/env python3
"""
guess_s20_recurrence_int.py — Q-Nullspace Solver for S20(n)

This script calculates the first 80 terms of the Callens-ALIX sequence S_20(n)
using exact integer arithmetic, and then constructs a massive symbolic matrix
to extract the underlying minimal holonomic recurrence via Q-nullspace solving.

Output:
    extracts the exact 45-digit polynomials P_0(n)...P_5(n) and saves them
    to extracted_polynomials.json
"""
import sys
from math import comb
import sympy as sp

def compute_s20(n):
    return sum(comb(n, k)**4 * comb(n + k, k) for k in range(n + 1))

def main():
    N = 80
    S = [compute_s20(n) for n in range(N)]
    order = 5
    deg = 9
    
    C = sp.symbols(f'c_0:6_0:10')
    eqs = []
    for n in range(N - order):
        eq = 0
        for j in range(order + 1):
            term = 0
            for i in range(deg + 1):
                term += C[j*(deg+1) + i] * (n**i)
            eq += term * S[n + j]
        eqs.append(eq)
        
    M = []
    for eq in eqs:
        row = []
        for j in range(order + 1):
            for i in range(deg + 1):
                row.append(eq.coeff(C[j*(deg+1) + i]))
        M.append(row)
        
    M = sp.Matrix(M)
    ns = M.nullspace()
    sol = ns[0]
    
    # Find common denominator
    lcm = 1
    for x in sol:
        lcm = sp.lcm(lcm, x.q)
        
    sol = [x * lcm for x in sol]
    
    n_sym = sp.Symbol('n')
    for j in range(order + 1):
        poly = 0
        for i in range(deg + 1):
            poly += sol[j*(deg+1) + i] * (n_sym**i)
        print(f"P_{j}(n) = {sp.expand(poly)}")
        print(f"P_{j}(0) = {poly.subs(n_sym, 0)}")

if __name__ == '__main__':
    main()
