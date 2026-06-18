# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Creative Telescoping Engine — Sister Celine's Algorithm

This module implements Sister Celine's technique to find recurrence relations
and telescoping certificates for hypergeometric terms F(n, k1, k2, ...).
It also provides support for q-hypergeometric terms.
"""

from __future__ import annotations

import sympy as sp
from typing import Callable, Optional, Union, Dict, Any, List

# Define common symbols
n = sp.symbols('n', integer=True)
k = sp.symbols('k', integer=True)
q = sp.symbols('q')

class HypergeometricTerm:
    """
    Represents a multivariate hypergeometric term F(n, k1, k2, ...) via its shift ratios:
       R_n(n, k1...) = F(n+1, k1...) / F(n, k1...)
       R_ki(n, k1...) = F(n, ..., ki+1, ...) / F(n, k1...)
    """
    def __init__(self, name: str,
                 vars_syms: List[sp.Symbol],
                 ratios: Dict[sp.Symbol, Union[sp.Expr, Callable[..., sp.Expr]]]):
        self.name = name
        self.vars = vars_syms
        self.ratios_expr = {}
        
        for sym, ratio in ratios.items():
            if callable(ratio):
                self.ratios_expr[sym] = ratio(*self.vars)
            else:
                self.ratios_expr[sym] = sp.sympify(ratio)
                
    def get_ratio(self, var_sym: sp.Symbol, eval_point: Dict[sp.Symbol, sp.Expr]) -> sp.Expr:
        """Get F(..., var_sym+1, ...) / F(...) evaluated at the given point."""
        return self.ratios_expr[var_sym].subs(eval_point)

    def get_shift_ratio(self, shifts: Dict[sp.Symbol, int]) -> sp.Expr:
        """
        Compute the shift ratio F(n+shifts[n], k+shifts[k], ...) / F(n, k, ...)
        """
        ratio = sp.Integer(1)
        current_point = {sym: sym for sym in self.vars}
        
        for sym, shift in shifts.items():
            if shift > 0:
                for s in range(shift):
                    ratio *= self.get_ratio(sym, current_point)
                    current_point[sym] += 1
            elif shift < 0:
                for s in range(-shift):
                    current_point[sym] -= 1
                    ratio /= self.get_ratio(sym, current_point)
                    
        return sp.simplify(ratio)

class QHypergeometricTerm(HypergeometricTerm):
    """
    Represents a q-hypergeometric term where shifts in k mean F(n, q*k).
    """
    def get_shift_ratio(self, shifts: Dict[sp.Symbol, int]) -> sp.Expr:
        """
        Compute the q-shift ratio. 
        For n, it's n+shifts[n]. For k, it's q^shifts[k] * k.
        """
        ratio = sp.Integer(1)
        current_point = {sym: sym for sym in self.vars}
        
        # We only support n as additive shift, and other vars as q-shifts (multiplicative)
        # Assuming n is the first variable in self.vars for standard recurrence
        n_sym = self.vars[0]
        
        # Additive shifts for n
        n_shift = shifts.get(n_sym, 0)
        if n_shift > 0:
            for s in range(n_shift):
                ratio *= self.get_ratio(n_sym, current_point)
                current_point[n_sym] += 1
                
        # q-shifts for other variables
        for sym in self.vars[1:]:
            sym_shift = shifts.get(sym, 0)
            if sym_shift > 0:
                for s in range(sym_shift):
                    ratio *= self.get_ratio(sym, current_point)
                    current_point[sym] *= q
                    
        return sp.simplify(ratio)

# --- Pre-defined Hypergeometric Terms ---

def binomial_term() -> HypergeometricTerm:
    """F(n, k) = C(n, k)"""
    return HypergeometricTerm(
        "binomial",
        [n, k],
        {
            n: (n + 1) / (n + 1 - k),
            k: (n - k) / (k + 1)
        }
    )

def weighted_binomial_term(p: int) -> HypergeometricTerm:
    """F(n, k) = k^p * C(n, k)"""
    if p == 0:
        return binomial_term()
    return HypergeometricTerm(
        f"weighted_binomial_p{p}",
        [n, k],
        {
            n: (n + 1) / (n + 1 - k),
            k: sp.simplify(((k + 1)**p * (n - k)) / (k**p * (k + 1)))
        }
    )

def alternating_binomial_term() -> HypergeometricTerm:
    """F(n, k) = (-1)^k * C(n, k)"""
    return HypergeometricTerm(
        "alternating_binomial",
        [n, k],
        {
            n: (n + 1) / (n + 1 - k),
            k: sp.simplify(- (n - k) / (k + 1))
        }
    )

def q_binomial_term() -> QHypergeometricTerm:
    """F(n, k) = q-binomial coefficient."""
    # R_n = (1 - q^(n+1)) / (1 - q^(n+1-k))
    # R_k = (1 - q^(n-k)) / (1 - q^(k+1))
    return QHypergeometricTerm(
        "q_binomial",
        [n, k],
        {
            n: (1 - q**(n+1)) / (1 - q**(n+1-k)),
            k: (1 - q**(n-k)) / (1 - q**(k+1))
        }
    )

# --- Sister Celine's Algorithm Implementation ---

def find_sister_celine_recurrence(term: HypergeometricTerm, shifts_max: Dict[sp.Symbol, int]) -> Optional[Dict[str, Any]]:
    """
    Finds a recurrence relation of the form:
       sum_{shifts} a_{shifts}(n) F(n+i, k+j, ...) = 0
    """
    print(f"🔬 Running multivariate Sister Celine's algorithm for '{term.name}' (Shifts={shifts_max})...")
    
    n_sym = term.vars[0]
    k_syms = term.vars[1:]
    
    import itertools
    # Generate all shift combinations
    ranges = [range(shifts_max.get(sym, 0) + 1) for sym in term.vars]
    shift_tuples = list(itertools.product(*ranges))
    
    ratios = {}
    denominators = []
    
    for shift_tuple in shift_tuples:
        shifts = {sym: s for sym, s in zip(term.vars, shift_tuple)}
        ratio = term.get_shift_ratio(shifts)
        ratios[shift_tuple] = ratio
        num, den = sp.fraction(ratio)
        denominators.append(den)
            
    # Find common denominator
    common_den = sp.Integer(1)
    for den in denominators:
        common_den = sp.lcm(common_den, den)
        
    a_symbols = {}
    numerator_terms = []
    for shift_tuple in shift_tuples:
        a_sym_name = "a_" + "_".join(str(s) for s in shift_tuple)
        a_sym = sp.Symbol(a_sym_name)
        a_symbols[shift_tuple] = a_sym
        
        contrib = a_sym * ratios[shift_tuple] * common_den
        numerator_terms.append(sp.cancel(contrib))
        
    num_equation = sum(numerator_terms)
    
    # We need to extract coefficients with respect to all k variables
    poly = sp.poly(num_equation, *k_syms)
    if poly is None:
        print("  ❌ Failed to convert numerator equation to polynomial in summation variables.")
        return None
        
    coeffs = poly.coeffs()
    
    system_vars = list(a_symbols.values())
    solution = sp.solve(coeffs, system_vars)
    
    if not solution:
        print("  ❌ No solution found for the coefficient system.")
        return None
        
    solved_vars = {}
    for var in system_vars:
        if var in solution:
            solved_vars[var] = sp.simplify(solution[var])
        else:
            solved_vars[var] = var
            
    if all(val == 0 for val in solved_vars.values()):
        print("  ❌ Found only the trivial (all zero) solution.")
        return None
        
    free_vars = [var for var, val in solved_vars.items() if val == var]
    
    final_coeffs = {}
    if free_vars:
        substitutions = {var: sp.Integer(1) for var in free_vars}
        for shift_tuple, var in a_symbols.items():
            val = solved_vars[var].subs(substitutions)
            final_coeffs[shift_tuple] = sp.simplify(val)
    else:
        if any(val != 0 for val in solution.values()):
            for shift_tuple, var in a_symbols.items():
                final_coeffs[shift_tuple] = sp.simplify(solution[var])
        else:
            print("  ❌ Found only the trivial solution.")
            return None
            
    all_vals = list(final_coeffs.values())
    denoms = [sp.fraction(sp.together(val))[1] for val in all_vals if val != 0]
    lcm_denom = sp.Integer(1)
    for den in denoms:
        lcm_denom = sp.lcm(lcm_denom, den)
        
    for key in final_coeffs:
        final_coeffs[key] = sp.simplify(final_coeffs[key] * lcm_denom)
        
    print(f"  ✅ Sister Celine recurrence found! Max Shifts={shifts_max}")
    for shift_tuple, val in final_coeffs.items():
        if val != 0:
            a_sym_name = "a_" + "_".join(str(s) for s in shift_tuple)
            print(f"     {a_sym_name}(n) = {val}")
            
    return {
        "a_coeffs": final_coeffs,
        "shifts_max": shifts_max,
        "vars": term.vars
    }

def get_telescoping_relation(celine_res: dict[str, Any], term: HypergeometricTerm) -> dict[str, sp.Expr]:
    """
    (Adapted for standard 1D summation currently. Requires further generalization for multi-sum)
    Converts a Sister Celine recurrence to a telescoping relation.
    """
    # Fallback to original 1D logic if possible
    if len(celine_res["vars"]) != 2:
        return {"error": "Telescoping certificate extraction currently only supports 1D summation."}
        
    a_coeffs_multi = celine_res["a_coeffs"]
    shifts_max = celine_res["shifts_max"]
    vars_syms = celine_res["vars"]
    n_sym, k_sym = vars_syms[0], vars_syms[1]
    
    I = shifts_max.get(n_sym, 0)
    J = shifts_max.get(k_sym, 0)
    
    # Map back to (i, j) tuple format for 1D logic
    a_coeffs = {(shift[0], shift[1]): val for shift, val in a_coeffs_multi.items()}
    
    t_coeffs = {}
    for i in range(I + 1):
        t_coeffs[i] = sp.simplify(sum(a_coeffs.get((i, j), sp.Integer(0)) for j in range(J + 1)))
        
    c_coeffs = {}
    for i in range(I + 1):
        for j in range(1, J + 1):
            c_coeffs[(i, j)] = sp.simplify(- sum(a_coeffs.get((i, r), sp.Integer(0)) for r in range(j, J + 1)))
            
    g_terms = []
    for (i, j), coeff in c_coeffs.items():
        if coeff != 0:
            g_terms.append(f"({coeff}) * F(n+{i}, k+{j-1})")
            
    g_expr_str = " + ".join(g_terms).replace("+ -", "- ")
    
    sum_recurrence_terms = []
    for i, coeff in t_coeffs.items():
        if coeff != 0:
            sum_recurrence_terms.append(f"({coeff}) * S(n+{i})")
    sum_recurrence_str = " + ".join(sum_recurrence_terms).replace("+ -", "- ")
    
    print("\n  🎯 Creative Telescoping Relation:")
    print(f"     LHS Sum Recurrence: {sum_recurrence_str} = 0")
    print(f"     Certificate G(n, k): {g_expr_str}")
    
    return {
        "t_coeffs": t_coeffs,
        "c_coeffs": c_coeffs,
        "sum_recurrence_str": sum_recurrence_str,
        "g_expr_str": g_expr_str
    }
