#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Difference Operator Minimizer
-----------------------------
Factors shift operators in Ore Algebras to extract minimal-order recurrences.
Prevents Complexity Bias by checking if a second-order recurrence can be reduced
to a first-order difference relation using the general falling factorial moments.
"""

import sympy as sp
from typing import Dict, Any, Tuple, Optional

def polynomial_to_falling_factorial_coeffs(poly: sp.Expr, var: sp.Symbol) -> list:
    """
    Converts a polynomial to falling factorial coefficients.
    Returns a list of coefficients [a_0, a_1, ..., a_d] such that
    poly = sum a_i * var_falling_i.
    """
    poly_obj = sp.Poly(poly, var)
    deg = poly_obj.degree()
    coeffs = [0] * (deg + 1)
    current_poly = poly_obj.as_expr()
    for d in range(deg, -1, -1):
        ff = 1
        for j in range(d):
            ff *= (var - j)
        ff = sp.expand(ff)
        coeff = sp.Poly(current_poly, var).coeff_monomial(var**d)
        coeffs[d] = coeff
        current_poly = sp.simplify(current_poly - coeff * ff)
    return coeffs

def minimize_recurrence(A_str: str, B_str: str, C_str: str, W_str: str) -> Optional[Tuple[str, str]]:
    """
    Checks if a second-order recurrence:
        A(n) S(n) + B(n) S(n+1) + C(n) S(n+2) = 0
    with weight polynomial W(k) can be reduced to a minimal first-order recurrence:
        D(n) S(n) + E(n) S(n+1) = 0
        
    Returns (D_str, E_str) if reducible, otherwise None.
    """
    n = sp.Symbol('n')
    k = sp.Symbol('k')
    
    try:
        W = sp.sympify(W_str)
        # Verify W is a polynomial in k
        if not W.is_polynomial(k):
            return None # Alternating signs or rational weights are skipped
            
        deg = sp.degree(W, k)
        coeffs = polynomial_to_falling_factorial_coeffs(W, k)
        
        # S(n) = 2^(n-d) * P(n) where P(n) = sum a_r * n^(r)_falling * 2^(d-r)
        P_n = 0
        for r, a_r in enumerate(coeffs):
            falling = 1
            for j in range(r):
                falling *= (n - j)
            P_n += a_r * falling * (2**(deg - r))
        
        P_n = sp.simplify(P_n)
        P_n1 = P_n.subs(n, n+1)
        
        # The first-order recurrence is:
        # -2 * P(n+1) * S(n) + P(n) * S(n+1) = 0
        D_expr = sp.simplify(-2 * P_n1)
        E_expr = sp.simplify(P_n)
        
        # Verify that the original second-order coefficients actually annihilate S(n)
        # i.e., A(n)*P(n) + 2*B(n)*P(n+1) + 4*C(n)*P(n+2) == 0
        P_n2 = P_n.subs(n, n+2)
        A = sp.sympify(A_str)
        B = sp.sympify(B_str)
        C = sp.sympify(C_str)
        
        check = sp.simplify(A * P_n + 2 * B * P_n1 + 4 * C * P_n2)
        if check != 0:
            print(f"  [Minimizer] Warning: Recurrence relation does not annihilate the sum (residue: {check})")
            return None
            
        return str(D_expr), str(E_expr)
    except Exception as e:
        print(f"Error in minimization: {e}")
        return None

if __name__ == "__main__":
    res = minimize_recurrence(
        "28*n**3 + 136*n**2 + 164*n + 56",
        "-34*n**3 - 188*n**2 - 142*n - 36",
        "10*n**3 + 54*n**2 - 8",
        "-k**2 - 3*k + 6"
    )
    print("Case 1 Reduction:", res)
