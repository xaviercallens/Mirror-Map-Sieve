#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
"""
Diagonal Representation Discovery — Phase 3: Almkvist-Zudilin Match & Holonomic Analysis

KEY INSIGHT FROM PHASE 2:
  The minimal recurrence has order 5. For Apéry-like sequences, the order
  equals the dimension of the underlying Calabi-Yau manifold + 1.
  Order 5 → Calabi-Yau 4-fold → requires ≥ 5 variables for the diagonal.

THIS PHASE:
  1. Construct the HOLONOMIC ODE for f(t) = Σ S₂₀(n)tⁿ using sympy.holonomic
  2. Try to FACTOR the ODE — if it factors, the diagonal may decompose
  3. Search for diagonal representations by working backwards from the
     BIVARIATE generating function G(t,z) = Σ_{n,k} C(n,k)⁴C(n+k,k) t^n z^k
  4. Use the MULTIVARIATE RESIDUE formula to construct candidate diagonals

MATHEMATICAL KEY:
  We proved S₂₀(n) = CT_{z}[(1+z)ⁿ · P_n(z) ... ] but P_n has no product form.
  ALTERNATIVE: use C(n,k) = [u^k](1+u)^n = CT_u[(1+u)^n u^{-k}], 
  then C(n,k)^4 = CT_{u₁,...,u₄}[Π(1+uᵢ)ⁿ (u₁u₂u₃u₄)^{-k}]
  and C(n+k,k) = CT_v[(1+v)^n ((1+v)/v)^k]
  
  So S₂₀(n) = CT_{u,v}[Π(1+uᵢ)ⁿ (1+v)ⁿ · Σ_k ((1+v)/(u₁u₂u₃u₄v))^k]
  = CT_{u,v}[Π(1+uᵢ)ⁿ (1+v)ⁿ / (1 - (1+v)/(Pv))]   where P = u₁u₂u₃u₄
  = CT_{u,v}[Π(1+uᵢ)ⁿ (1+v)ⁿ · Pv/(Pv - 1 - v)]

  This is now a PROPER constant term. The diagonal extraction needs 
  a CHANGE OF VARIABLES to convert CT[Λⁿ · R] → Diag[G].

  The CRITICAL insight: Bostan-Lairez-Salvy (2015) Algorithm 1 gives
  a systematic method. Without SageMath, we can implement a simplified
  version for small cases.
"""

from __future__ import annotations
import sys
import json
import time
from math import comb, factorial
from fractions import Fraction
from pathlib import Path
from itertools import product as cartesian_product
from typing import List, Tuple, Dict, Optional, Any

import sympy as sp
from sympy import Rational, Integer, symbols, expand, factor, gcd, lcm


# ============================================================================
# KNOWN S₂₀ VALUES (exact)
# ============================================================================
def compute_s20(n: int) -> int:
    return sum(comb(n, k)**4 * comb(n+k, k) for k in range(n+1))

S20_VALUES = [compute_s20(n) for n in range(40)]


# ============================================================================
# PHASE 3A: HOLONOMIC ODE CONSTRUCTION
# ============================================================================

def construct_holonomic_ode():
    """
    Construct the linear ODE for f(t) = Σ S₂₀(n) tⁿ using the recurrence.
    
    From the recurrence: Σ_{i=0}^5 P_i(n) S(n+i) = 0
    
    The ODE is obtained by:
      n → θ = t d/dt  (Euler operator)
      S(n+i) → f_i(t) = (f(t) - Σ_{j=0}^{i-1} S(j)t^j) / t^i
    
    For small orders, it's easier to work with the NORMALIZED recurrence
    (divide through by the leading coefficient) and compute the ODE
    from the asymptotic growth.
    """
    print("=" * 70)
    print("  HOLONOMIC ODE CONSTRUCTION")
    print("=" * 70)
    
    # Instead of converting the huge degree-9 recurrence, let's search for
    # a SMALLER recurrence directly and then convert that.
    
    # The key insight: maybe the degree-9 recurrence is NOT minimal in degree.
    # The discovery pipeline may have found a multiple of the true minimal
    # recurrence. Let's search harder with more data points.
    
    n = sp.Symbol('n')
    
    # For order 5, search degrees 1 through 5 with MORE data
    max_n = len(S20_VALUES) - 6  # can test n=0..max_n-1
    
    for deg in range(1, 6):
        num_unknowns = 6 * (deg + 1)  # 6 polys (P₀..P₅) of degree deg
        num_equations = num_unknowns + 10  # overdetermined
        
        if num_equations > max_n:
            print(f"  Order 5, degree {deg}: need {num_equations} eqns, have {max_n} — skip")
            continue
        
        # Build the linear system
        rows = []
        for n_val in range(num_equations):
            row = []
            for i in range(6):  # P₀..P₅
                for j in range(deg + 1):  # coefficients n⁰,...,nᵈ
                    row.append(n_val**j * S20_VALUES[n_val + i])
            rows.append(row)
        
        M = sp.Matrix(rows)
        ns = M.nullspace()
        
        if ns:
            for sol in ns:
                # Validate
                valid = True
                for n_val in range(num_equations, min(max_n, num_equations + 5)):
                    val = 0
                    idx = 0
                    for i in range(6):
                        for j in range(deg + 1):
                            val += int(sol[idx]) * n_val**j * S20_VALUES[n_val + i]
                            idx += 1
                    if val != 0:
                        valid = False
                        break
                
                if valid:
                    polys = []
                    idx = 0
                    for i in range(6):
                        poly = 0
                        for j in range(deg + 1):
                            poly += sol[idx] * n**j
                            idx += 1
                        polys.append(sp.simplify(poly))
                    
                    if polys[0] == 0 or polys[5] == 0:
                        continue
                    
                    print(f"\n  🎯 FOUND order-5 recurrence with degree {deg}!")
                    for i, p in enumerate(polys):
                        print(f"    P_{i}(n) = {p}")
                    return polys
        else:
            print(f"  Order 5, degree {deg}: no nullspace — degree too low")
    
    # Also try orders 2, 3, 4
    for order in range(2, 5):
        for deg in range(1, 8):
            num_unknowns = (order + 1) * (deg + 1)
            num_equations = num_unknowns + 10
            
            if num_equations + order >= len(S20_VALUES):
                continue
            
            rows = []
            for n_val in range(num_equations):
                row = []
                for i in range(order + 1):
                    for j in range(deg + 1):
                        row.append(n_val**j * S20_VALUES[n_val + i])
                rows.append(row)
            
            M = sp.Matrix(rows)
            ns = M.nullspace()
            
            if ns:
                for sol in ns:
                    valid = True
                    for n_val in range(num_equations, min(len(S20_VALUES) - order, num_equations + 5)):
                        val = 0
                        idx = 0
                        for i in range(order + 1):
                            for j in range(deg + 1):
                                val += int(sol[idx]) * n_val**j * S20_VALUES[n_val + i]
                                idx += 1
                        if val != 0:
                            valid = False
                            break
                    
                    if valid:
                        polys = []
                        idx = 0
                        for i in range(order + 1):
                            poly = 0
                            for j in range(deg + 1):
                                poly += sol[idx] * n**j
                                idx += 1
                            polys.append(sp.simplify(poly))
                        
                        if polys[0] == 0 or polys[order] == 0:
                            continue
                        
                        print(f"\n  🎯 FOUND order-{order} recurrence with degree {deg}!")
                        for i, p in enumerate(polys):
                            print(f"    P_{i}(n) = {p}")
                        
                        # Convert to ODE
                        print("\n  Converting to Picard-Fuchs ODE...")
                        convert_recurrence_to_ode(polys, order)
                        return polys
    
    print("\n  ❌ No simpler recurrence found (orders 2-5, degrees 1-7)")
    print("  The order-5 degree-9 recurrence appears to be minimal (or close to it).")
    return None


def convert_recurrence_to_ode(polys, order):
    """
    Convert a recurrence Σ P_i(n) S(n+i) = 0 to a differential equation.
    
    Using: n → θ = t·d/dt and the shift identity 
    Σ_n a(n+k) t^n = (f(t) - Σ_{j<k} a(j) t^j) / t^k
    """
    t, n = symbols('t n')
    
    # For a recurrence of order r with degree d polynomials:
    # The resulting ODE has order r and its coefficients are polynomials in t
    # of degree ≤ r + d.
    
    # Simple case: if P_i(n) = c_i (constants), then the ODE is
    # Σ c_i t^{-i} (t d/dt)^0 f = ... which simplifies to an algebraic equation.
    
    # For polynomial P_i(n), use n^j → θ^j where θ = t d/dt.
    # Note: θ^j f = t^j (d/dt)^j f + lower order terms (Stirling numbers).
    
    print(f"    Order: {order}")
    print(f"    Polynomial coefficients:")
    for i, p in enumerate(polys):
        print(f"      P_{i}(n) = {p}")
    
    # The leading coefficient of the ODE (highest derivative) determines
    # the singular points.
    # For the shift: S(n+k) ~ f(t)/t^k, so the ODE has denominators t^order.
    # After clearing denominators, the leading coefficient is a polynomial in t.
    
    # Instead of full conversion, extract the INDICIAL EQUATION at t=0
    # and the SINGULAR POINTS from the leading coefficients.
    
    # At large n: P_i(n) ~ leading_i * n^d
    # The characteristic equation is: Σ leading_i * s^i = 0
    # Roots give s = S(n+1)/S(n) as n → ∞, hence 1/t at singularities.
    
    s = sp.Symbol('s')
    char_poly = sum(sp.Poly(p, n).LC() * s**i for i, p in enumerate(polys))
    print(f"\n    Characteristic polynomial: {char_poly}")
    
    roots = sp.solve(char_poly, s)
    print(f"    Roots (= growth rates):")
    for r in roots:
        r_float = complex(r.evalf())
        print(f"      s = {r}  ≈ {r_float}")
        if r != 0:
            print(f"      → singularity at t = 1/s ≈ {1/r_float}")


# ============================================================================
# PHASE 3B: ALMKVIST-ZUDILIN CATALOG MATCH
# ============================================================================

def almkvist_zudilin_match():
    """
    Check if S₂₀ matches any known Apéry-like sequence in the literature.
    
    Known families:
    - A(n) = Σ C(n,k)² C(n+k,k)²  → Apéry (ζ(3)), order 2
    - B(n) = Σ C(n,k)² C(2k,k) C(2(n-k),n-k) → Franel-like, order 3
    - C(n) = Σ C(n,k)³ C(n+k,k) → related to modular forms, order 3
    - D(n) = Σ C(2n,2k) C(2k,k)² → Domb numbers
    - E(n) = Σ C(n,k) C(2k,n) C(2(n-k),n-k) → order 3
    
    Our sequence: S₂₀(n) = Σ C(n,k)⁴ C(n+k,k)
    This has the form Σ C(n,k)^a C(n+k,k)^b with (a,b) = (4,1).
    
    Known (a,b) pairs:
    - (2,2): Apéry for ζ(3), A005259, order 2
    - (3,1): Apéry-like for ζ(2), A006077 variant, order 3  
    - (4,1): OUR SEQUENCE — not previously studied!
    - (2,1): A001700 variant
    - (1,1): C(2n,n) = Catalan related
    """
    print("\n" + "=" * 70)
    print("  ALMKVIST-ZUDILIN CATALOG MATCH")
    print("=" * 70)
    
    # Compute related sequences for comparison
    families = {
        "(2,2) Apéry": lambda n: sum(comb(n,k)**2 * comb(n+k,k)**2 for k in range(n+1)),
        "(3,1) ζ(2)-like": lambda n: sum(comb(n,k)**3 * comb(n+k,k) for k in range(n+1)),
        "(4,1) S₂₀ OURS": lambda n: sum(comb(n,k)**4 * comb(n+k,k) for k in range(n+1)),
        "(5,1)": lambda n: sum(comb(n,k)**5 * comb(n+k,k) for k in range(n+1)),
        "(2,3)": lambda n: sum(comb(n,k)**2 * comb(n+k,k)**3 for k in range(n+1)),
        "(3,2)": lambda n: sum(comb(n,k)**3 * comb(n+k,k)**2 for k in range(n+1)),
        "(1,4)": lambda n: sum(comb(n,k) * comb(n+k,k)**4 for k in range(n+1)),
    }
    
    print("\n  Comparison of Σ C(n,k)^a C(n+k,k)^b families:")
    print(f"  {'Family':<20} {'n=0':>5} {'n=1':>5} {'n=2':>8} {'n=3':>10} {'n=4':>14} {'Ratio':>10}")
    print("  " + "-" * 72)
    
    for name, fn in families.items():
        vals = [fn(n) for n in range(5)]
        ratio = vals[4] / vals[3] if vals[3] != 0 else 0
        print(f"  {name:<20} {vals[0]:>5} {vals[1]:>5} {vals[2]:>8} {vals[3]:>10} {vals[4]:>14} {ratio:>10.2f}")
    
    print("\n  Growth ratios (asymptotic):")
    for name, fn in families.items():
        vals = [fn(n) for n in range(8)]
        ratios = [vals[i+1]/vals[i] for i in range(len(vals)-1) if vals[i] > 0]
        last_ratio = ratios[-1] if ratios else 0
        print(f"  {name:<20} → {last_ratio:.4f}")
    
    # Check recurrence orders for each family
    print("\n  Conjectured minimal recurrence orders:")
    for name, fn in families.items():
        vals = [fn(n) for n in range(30)]
        order = find_recurrence_order(vals)
        print(f"  {name:<20} order = {order}")


def find_recurrence_order(vals: List[int], max_order: int = 8) -> Optional[int]:
    """Find the minimal recurrence order for a sequence."""
    n = sp.Symbol('n')
    
    for order in range(1, max_order + 1):
        for deg in range(0, 6):
            num_unknowns = (order + 1) * (deg + 1)
            num_equations = num_unknowns + 5
            
            if num_equations + order >= len(vals):
                break
            
            rows = []
            for n_val in range(num_equations):
                row = []
                for i in range(order + 1):
                    for j in range(deg + 1):
                        row.append(n_val**j * vals[n_val + i])
                rows.append(row)
            
            M = sp.Matrix(rows)
            ns = M.nullspace()
            
            if ns:
                # Validate
                sol = ns[0]
                valid = True
                for n_val in range(num_equations, min(len(vals) - order, num_equations + 5)):
                    val = 0
                    idx = 0
                    for i in range(order + 1):
                        for j in range(deg + 1):
                            val += int(sol[idx]) * n_val**j * vals[n_val + i]
                            idx += 1
                    if val != 0:
                        valid = False
                        break
                
                if valid:
                    # Check non-trivial
                    polys = []
                    idx = 0
                    for i in range(order + 1):
                        poly = 0
                        for j in range(deg + 1):
                            poly += sol[idx] * n**j
                            idx += 1
                        polys.append(poly)
                    if polys[0] != 0 and polys[order] != 0:
                        return order
    
    return None


# ============================================================================
# PHASE 3C: SYSTEMATIC DIAGONAL TEST (IMPROVED)
# ============================================================================

def systematic_diagonal_test():
    """
    Test diagonal representations using MULTIVARIATE generating functions.
    
    KEY INSIGHT: C(n,k) = [x^n y^k] 1/(1-x-xy)
    
    So the BIVARIATE GF of C(n,k) is:
      F(x,y) = 1/(1-x-xy) = 1/(1 - x(1+y))
    
    And C(n,k)^4 = [x₁^n...x₄^n y₁^k...y₄^k] Π 1/(1-xᵢ(1+yᵢ))
    C(n+k,k) = [u^n v^k] 1/(1-u-v)  (where u↔n, v↔k)
    
    S₂₀(n) = Σ_k C(n,k)^4 C(n+k,k)
    = [x₁^n...x₄^n u^n] Σ_k [y₁^k...y₄^k v^k] · Π 1/(1-xᵢ(1+yᵢ)) · 1/(1-u-v)
    
    The k-sum is a DIAGONAL extraction in the (y₁,...,y₄,v) variables:
    Set y₁=...=y₄=v=z, extract [z^0]:
    
    S₂₀(n) = [x₁^n...x₄^n u^n] [z^0] Π 1/(1-xᵢ(1+z)) · 1/(1-u-z) · z^{-5k}...
    
    WAIT — this isn't a diagonal extraction because k appears as a free sum.
    
    The correct approach: use the CAUCHY PRODUCT formula.
    Σ_k a(k) b(k) = (1/2πi) ∮ A(z) B(1/z) dz/z = [z^0] A(z) B(1/z)
    
    where A(z) = Σ a(k) z^k and B(z) = Σ b(k) z^k.
    
    With a(k) = C(n,k)^4 and b(k) = C(n+k,k):
    A(z) = Σ C(n,k)^4 z^k = P_n(z)  (polynomial of degree n)
    B(z) = Σ C(n+k,k) z^k = 1/(1-z)^{n+1}
    B(1/z) = z^{n+1}/(z-1)^{n+1}
    
    S₂₀(n) = [z^0] P_n(z) · z^{n+1}/(z-1)^{n+1}
    
    Now P_n(z) = [x₁^n...x₄^n] Π 1/(1-xᵢ(1+z))  (reading off the 4-variate GF at y₁=...=y₄=z)
    
    No wait: Π 1/(1-xᵢ(1+z)) = Σ_{n₁,...,n₄,k₁,...,k₄} (stuff) xᵢ^{nᵢ}
    But C(n,k)^4 = Π C(n,k), which requires n₁=...=n₄=n and k₁=...=k₄=k.
    The GF of C(n,k) in (x,y) is 1/(1-x(1+y)).
    [x^n y^k] 1/(1-x(1+y)) = C(n,k). ✓
    
    So P_n(z) = Σ_k C(n,k)^4 z^k 
    = Σ_k [Π_{i=1}^4 [x_i^n] 1/(1-x_i(1+y_i))] |_{y_i=z} · z^k
    
    Hmm this is getting circular. Let's try a COMPLETELY DIFFERENT approach.
    
    APPROACH: Candidate diagonal from the BIVARIATE GF of S₂₀.
    
    If S₂₀(n) = Diag_m[G], then Σ S₂₀(n) t^n = Diag_m[G(t^{1/m},...,t^{1/m})].
    
    The GF radius of convergence is R ≈ 1/43.04 (from Phase 2).
    
    For a 5-variable diagonal of 1/Q(x₁,...,x₅):
    - G(x,...,x) = 1/Q(x,...,x) must have smallest root at x⁵ = R
    - So Q(x,...,x) must have a root at x = R^{1/5} ≈ 0.471
    
    Let's search over SIMPLE denominator forms.
    """
    print("\n" + "=" * 70)
    print("  SYSTEMATIC DIAGONAL TEST (PHASE 3)")
    print("=" * 70)
    
    # Target: R ≈ 1/43.04 ≈ 0.02323
    # For 5-variable diagonal: root at x ≈ 0.02323^(1/5) ≈ 0.471
    
    R_target = 1.0 / 43.04
    x_target = R_target ** 0.2
    print(f"\n  Target: R = {R_target:.6f}, x₅ = R^(1/5) = {x_target:.6f}")
    
    # For a denominator Q(x₁,...,x₅) = 1 - a·Λ(x₁,...,x₅),
    # the diagonal of 1/Q is Σ [x^n] 1/(1-a·Λ) · ... 
    
    # Known pattern: for Apéry (2,2), the diagonal of 
    # 1/(1 - x₁ - x₂ - x₃ - x₄ + x₁x₂x₃x₄) ... no, let me look this up.
    
    # Actually, for the Apéry numbers A(n) = Σ C(n,k)² C(n+k,k)²:
    # A(n) = Diag[1/((1-x-y)(1-z-w) - xyzw)]  (4 variables)
    # This was proven by Straub (2014).
    
    # The denominator is (1-x-y)(1-z-w) - xyzw
    # = 1 - x - y - z - w + xz + xw + yz + yw - xyzw - xyzw
    # Hmm, let me just expand it.
    
    x1, x2, x3, x4 = symbols('x1 x2 x3 x4')
    apery_denom = (1 - x1 - x2) * (1 - x3 - x4) - x1*x2*x3*x4
    apery_expanded = expand(apery_denom)
    print(f"\n  Reference: Apéry (2,2) diagonal denominator:")
    print(f"    Q = {apery_expanded}")
    print(f"    Q(x,...,x) = {expand(apery_expanded.subs([(x1,x1),(x2,x1),(x3,x1),(x4,x1)]))}")
    
    x = sp.Symbol('x')
    q_apery = expand(apery_denom.subs([(x1,x),(x2,x),(x3,x),(x4,x)]))
    print(f"    Q(x,x,x,x) = {q_apery}")
    roots = sp.solve(q_apery, x)
    print(f"    Roots: {[r.evalf() for r in roots]}")
    
    # For S₂₀ (4,1), try a 5-variable generalization:
    # Q = (1 - x₁ - x₂)(1 - x₃ - x₄)(1 - x₅) - α · x₁x₂x₃x₄x₅
    # for some parameter α.
    
    x5 = sp.Symbol('x5')
    alpha = sp.Symbol('alpha')
    
    candidate_Q = (1 - x1 - x2) * (1 - x3 - x4) * (1 - x5) - alpha * x1*x2*x3*x4*x5
    
    # Set all xᵢ = x and find α such that the smallest positive root matches
    q_diag = expand(candidate_Q.subs([(x1,x),(x2,x),(x3,x),(x4,x),(x5,x)]))
    print(f"\n  Candidate: Q = (1-x₁-x₂)(1-x₃-x₄)(1-x₅) - α·x₁x₂x₃x₄x₅")
    print(f"    Q(x,...,x) = {q_diag}")
    
    # For each α, find the smallest positive root and test the diagonal
    print("\n  Sweeping α to match growth rate ≈ 43:")
    
    target_growth = S20_VALUES[7] / S20_VALUES[6]  # ≈ 32.2 for n=6→7
    # Actually, asymptotic growth
    target_growth_asymp = S20_VALUES[30] / S20_VALUES[29]
    print(f"  Target growth rate: S₂₀(30)/S₂₀(29) = {target_growth_asymp:.4f}")
    
    for alpha_val in [1, 2, 4, 8, 16, 32, 64, 128]:
        q_at_alpha = q_diag.subs(alpha, alpha_val)
        roots_at_alpha = sp.solve(q_at_alpha, x)
        real_pos_roots = [float(r.evalf()) for r in roots_at_alpha if r.is_real and r > 0]
        if real_pos_roots:
            smallest = min(real_pos_roots)
            growth = 1 / (smallest ** 5)
            print(f"    α = {alpha_val:>3}: smallest root x = {smallest:.6f}, "
                  f"growth ≈ 1/x⁵ = {growth:.2f}")
    
    # Now actually TEST the diagonal for the best-matching α values
    print("\n  Testing diagonal extraction for promising α values...")
    test_diagonal_of_rational(5)


def test_diagonal_of_rational(n_max: int = 5):
    """
    Test: Diag[1/Q] where Q = (1-Σ₁)(1-Σ₂)(1-x₅) - α·Π xᵢ
    
    For the diagonal of 1/Q(x₁,...,x₅), the coefficient of x₁ⁿ...x₅ⁿ
    is computed by expanding 1/Q as a multivariate power series.
    
    For small n this is feasible.
    """
    from functools import lru_cache
    
    # We need to compute [x₁ⁿ...x₅ⁿ] 1/Q for various Q
    # Using the recurrence: 1/(1-A) = Σ Aⁿ where A = sum of monomial terms
    
    # For Q = 1 - L + M where L is the "linear" part and M is the "monomial" part:
    # 1/Q = 1/(1 - (L - M)) = Σ (L - M)^k
    
    # This gets unwieldy for 5 variables. Let's use sympy's series expansion
    # but with integer arithmetic.
    
    # Actually, for small n (up to 5), we can use the MULTINOMIAL COEFFICIENT
    # approach: expand 1/Q as Σ c_{n₁,...,n₅} x₁^{n₁}...x₅^{n₅}
    # and extract c_{n,n,n,n,n}.
    
    # For Q = (1-x₁-x₂)(1-x₃-x₄)(1-x₅) - α·x₁x₂x₃x₄x₅:
    # 1/Q = 1/((1-x₁-x₂)(1-x₃-x₄)(1-x₅)) · 1/(1 - α·x₁x₂x₃x₄x₅/((1-x₁-x₂)(1-x₃-x₄)(1-x₅)))
    
    # The first factor: 1/((1-x₁-x₂)(1-x₃-x₄)(1-x₅))
    # = [Σ C(a+b,a) x₁^a x₂^b] · [Σ C(c+d,c) x₃^c x₄^d] · [Σ x₅^e]
    
    # [x₁ⁿx₂ⁿx₃ⁿx₄ⁿx₅ⁿ] of the first factor = C(2n,n)² · 1 = C(2n,n)²
    
    # The second factor: 1/(1 - α·B) where B = x₁x₂x₃x₄x₅/((1-x₁-x₂)(1-x₃-x₄)(1-x₅))
    # = Σ_{m≥0} α^m B^m
    
    # So the full diagonal = Σ_m α^m · [x₁ⁿ...x₅ⁿ] B^m / ((1-x₁-x₂)(1-x₃-x₄)(1-x₅))^{m+1}
    
    # [x₁ⁿ...x₅ⁿ] of the (m+1)-th power of the base:
    # Need [x₁ⁿx₂ⁿ] 1/(1-x₁-x₂)^{m+1} = C(2n+m, n+m)? No...
    # Actually [x₁^a x₂^b] 1/(1-x₁-x₂)^{m+1} = C(a+b+m, m) C(a+b, a)
    # Wait, that's not right either.
    
    # 1/(1-u)^{m+1} = Σ C(j+m, m) u^j. With u = x₁+x₂:
    # = Σ_j C(j+m, m) (x₁+x₂)^j = Σ_j C(j+m,m) Σ_a C(j,a) x₁^a x₂^{j-a}
    # [x₁^n x₂^n] = Σ_j C(j+m,m) C(j,n) δ_{j,2n} = C(2n+m, m) C(2n, n)
    
    # So: [x₁ⁿx₂ⁿ] 1/(1-x₁-x₂)^{m+1} = C(2n+m, m) C(2n, n) ✓
    # Similarly: [x₃ⁿx₄ⁿ] 1/(1-x₃-x₄)^{m+1} = C(2n+m, m) C(2n, n)
    # And: [x₅ⁿ] 1/(1-x₅)^{m+1} = C(n+m, m)
    
    # But we also need to account for the B^m factor.
    # B^m = (x₁x₂x₃x₄x₅)^m contributes x_i^m for each variable.
    # So we need [x₁^{n-m}x₂^{n-m}] 1/(1-x₁-x₂)^{m+1} if n ≥ m.
    
    # = C(2(n-m)+m, m) C(2(n-m), n-m) = C(2n-m, m) C(2n-2m, n-m)
    
    # Full diagonal coefficient:
    # D(n) = Σ_{m=0}^n α^m · C(2n-m, m)² · C(2n-2m, n-m)² · C(n-m+m, m)
    #       Wait, I need to be more careful.
    
    # Let's redo: 
    # 1/Q = Σ_{m≥0} α^m (x₁x₂x₃x₄x₅)^m / [(1-x₁-x₂)(1-x₃-x₄)(1-x₅)]^{m+1}
    
    # [x₁ⁿ...x₅ⁿ] = Σ_m α^m · A(n,m) · B(n,m) · C_val(n,m)
    # where:
    # A(n,m) = [x₁^{n-m} x₂^{n-m}] 1/(1-x₁-x₂)^{m+1} = C(2(n-m)+m, m) C(2(n-m), n-m)
    # B(n,m) = [x₃^{n-m} x₄^{n-m}] 1/(1-x₃-x₄)^{m+1} = same as A
    # C_val(n,m) = [x₅^{n-m}] 1/(1-x₅)^{m+1} = C(n-m+m, m) = C(n, m)
    
    # Check A(n,m):
    # [x₁^a x₂^b] 1/(1-x₁-x₂)^{p} = C(a+b+p-1, p-1) C(a+b, a) ... 
    # Actually, let me re-derive:
    # 1/(1-u)^p = Σ_j C(j+p-1, p-1) u^j  where u = x₁+x₂
    # [x₁^a x₂^b] = C(a+b+p-1, p-1) C(a+b, a) when j = a+b? 
    # No: [x₁^a x₂^b] u^j = [x₁^a x₂^b](x₁+x₂)^j = C(j,a) if b=j-a.
    # So [x₁^a x₂^b] 1/(1-u)^p = C(a+b+p-1, p-1) C(a+b, a)
    
    # Wait, that's wrong too. Let me be very precise:
    # 1/(1-x₁-x₂)^p = Σ_{j≥0} C(j+p-1, j) (x₁+x₂)^j
    # (x₁+x₂)^j = Σ_{a=0}^j C(j,a) x₁^a x₂^{j-a}
    # [x₁^a x₂^b] requires j=a+b, giving C(a+b+p-1, a+b) C(a+b, a)
    
    # So for a=b=n-m, p=m+1:
    # A(n,m) = C(2(n-m)+m, 2(n-m)) · C(2(n-m), n-m)
    #        = C(2n-m, 2n-2m) · C(2n-2m, n-m)
    
    # And C_val(n,m) = [x₅^{n-m}] 1/(1-x₅)^{m+1} = C(n-m+m, n-m) = C(n, n-m) = C(n, m)
    
    print(f"\n  Testing Q = (1-x₁-x₂)(1-x₃-x₄)(1-x₅) - α·x₁x₂x₃x₄x₅")
    print(f"  Diagonal formula: D(n) = Σ_m α^m C(2n-m,2n-2m)² C(2n-2m,n-m)² C(n,m)")
    
    for alpha_val in [1, 2, 4, 8, 16, 32, 64]:
        diag_vals = []
        for n in range(n_max + 1):
            d_n = 0
            for m in range(n + 1):
                a = 2*n - 2*m
                b = n - m
                if a < 0 or b < 0:
                    continue
                term = (alpha_val**m 
                       * comb(2*n-m, a)  # C(2n-m, 2n-2m)
                       * comb(2*n-m, a)  # same for (x₃,x₄) pair 
                       * comb(a, b)      # C(2n-2m, n-m) 
                       * comb(a, b)      # same
                       * comb(n, m))     # C(n, m)
                d_n += term
            diag_vals.append(d_n)
        
        match_count = sum(1 for i in range(len(diag_vals)) if diag_vals[i] == S20_VALUES[i])
        marker = "🎯" if match_count == n_max + 1 else "  "
        
        if match_count >= 2 or alpha_val in [1, 16]:
            print(f"  {marker} α={alpha_val:>3}: {diag_vals[:n_max+1]}")
            print(f"         S₂₀: {S20_VALUES[:n_max+1]}")
            print(f"         Match: {match_count}/{n_max+1}")
    
    # Also try the ASYMMETRIC decomposition: 
    # Q = (1-x₁-x₂-x₃-x₄)(1-x₅) - β·x₁x₂x₃x₄x₅
    print(f"\n  Testing Q = (1-x₁-x₂-x₃-x₄)(1-x₅) - β·x₁x₂x₃x₄x₅")
    
    # [x₁^a x₂^b x₃^c x₄^d] 1/(1-x₁-x₂-x₃-x₄)^p
    # = C(a+b+c+d+p-1, a+b+c+d) · MULTINOMIAL(a+b+c+d; a,b,c,d)
    # For a=b=c=d=n-m, p=m+1:
    # = C(4(n-m)+m, 4(n-m)) · (4(n-m))! / ((n-m)!)^4
    
    for beta_val in [1, 2, 4, 8]:
        diag_vals = []
        for n in range(n_max + 1):
            d_n = 0
            for m in range(n + 1):
                q = n - m  # each of x₁,...,x₄ has exponent q
                if q < 0:
                    continue
                J = 4*q  # total degree of the (x₁+...+x₄)^J part
                
                # C(J + m, J) = C(4q+m, 4q)
                coeff_1 = comb(J + m, J)
                # multinomial: J! / (q!)^4
                multi = factorial(J) // (factorial(q)**4)
                # x₅ part: C(n, m)
                coeff_5 = comb(n, m)
                
                term = beta_val**m * coeff_1 * multi * coeff_5
                d_n += term
            diag_vals.append(d_n)
        
        match_count = sum(1 for i in range(len(diag_vals)) if diag_vals[i] == S20_VALUES[i])
        marker = "🎯" if match_count == n_max + 1 else "  "
        
        print(f"  {marker} β={beta_val}: {diag_vals[:n_max+1]}")
        print(f"       S₂₀: {S20_VALUES[:n_max+1]}")
        print(f"       Match: {match_count}/{n_max+1}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 70)
    print("  S₂₀ DIAGONAL DISCOVERY — PHASE 3")
    print("  Holonomic Analysis / Catalog Match / Systematic Diagonal Test")
    print("=" * 70)
    t0 = time.time()
    
    # Phase 3A: Holonomic ODE / Minimal Recurrence
    print("\n\n" + "▓" * 70)
    print("  PHASE 3A: HOLONOMIC ODE / MINIMAL RECURRENCE")
    print("▓" * 70)
    polys = construct_holonomic_ode()
    
    # Phase 3B: Almkvist-Zudilin catalog match
    print("\n\n" + "▓" * 70)
    print("  PHASE 3B: ALMKVIST-ZUDILIN CATALOG MATCH")
    print("▓" * 70)
    almkvist_zudilin_match()
    
    # Phase 3C: Systematic diagonal test
    print("\n\n" + "▓" * 70)
    print("  PHASE 3C: SYSTEMATIC DIAGONAL TEST")
    print("▓" * 70)
    systematic_diagonal_test()
    
    elapsed = time.time() - t0
    print(f"\n\nTotal elapsed: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
