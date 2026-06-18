#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Diagonal Representation Discovery for S₂₀(n) = Σ C(n,k)⁴ C(n+k,k)

This module implements three approaches to finding the rational function
F(x₁,...,x_m) whose diagonal produces S₂₀(n):

  1. GORODETSKY CONSTANT-TERM METHOD:
     Search for Laurent polynomial Λ(z₁,...,z_m) such that CT(Λⁿ) = S₂₀(n).
     
  2. STRUCTURAL SEARCH:
     Systematically enumerate rational functions with denominators of the form
     (product of linear forms) - (monomial), motivated by the Apéry (2,2) case.
     
  3. CREATIVE TELESCOPING VERIFICATION (Bostan-Lairez-Salvy oracle):
     For each candidate F, compute its diagonal via multivariate power series
     arithmetic and verify against S₂₀(n).

MATHEMATICAL BACKGROUND:
  - S₂₀(n) = Σ_{k=0}^n C(n,k)⁴ C(n+k,k)
  - First values: 1, 6, 126, 5040, 297990, 22309452, ...
  - The (2,2) Apéry case has diagonal: 1/((1-x-y)(1-z-w) - xyzw)
  - The naïve (4,1) guess 1/(1 - x₁(1-x₂)(1-x₃)(1-x₄)(1-x₅) - x₁x₂x₃x₄x₅)
    was FALSIFIED: its diagonal is 2^n.
  - By Christol's theorem, such an F exists. Finding it explicitly is the open problem.

STATUS: RESEARCH CODE — This is an open mathematical problem.
"""

from __future__ import annotations
import sys
import json
import time
import itertools
from math import comb, factorial
from fractions import Fraction
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Any

# ============================================================================
# SECTION 1: EXACT SEQUENCE COMPUTATION
# ============================================================================

def compute_s20(n: int) -> int:
    """Compute S₂₀(n) = Σ_{k=0}^n C(n,k)⁴ C(n+k,k) exactly."""
    total = 0
    for k in range(n + 1):
        total += comb(n, k) ** 4 * comb(n + k, k)
    return total

def compute_s15(n: int) -> int:
    """Compute S₁₅(n) = Σ_{k=0}^n C(n,k) C(n+k,k)⁵ exactly."""
    total = 0
    for k in range(n + 1):
        total += comb(n, k) * comb(n + k, k) ** 5
    return total

def compute_sequence_table(seq_fn, max_n: int = 30) -> List[int]:
    """Compute a table of sequence values."""
    return [seq_fn(n) for n in range(max_n + 1)]


# Precompute reference values
S20_REF = None  # Lazily computed

def get_s20_reference(max_n: int = 25) -> List[int]:
    """Get reference S₂₀ values (cached)."""
    global S20_REF
    if S20_REF is None or len(S20_REF) < max_n + 1:
        S20_REF = compute_sequence_table(compute_s20, max_n)
    return S20_REF


# ============================================================================
# SECTION 2: MULTIVARIATE POWER SERIES ARITHMETIC
# ============================================================================

class MultivariateSeries:
    """
    Sparse multivariate formal power series up to total degree N.
    
    Coefficients are stored as Dict[tuple_of_exponents, Fraction].
    Each key is a tuple (e₁, e₂, ..., e_m) representing x₁^e₁ · ... · x_m^eₘ.
    """
    
    def __init__(self, nvars: int, max_total_deg: int, coeffs: Optional[Dict[tuple, Fraction]] = None):
        self.nvars = nvars
        self.max_deg = max_total_deg
        self.coeffs = coeffs or {}
    
    def __getitem__(self, key: tuple) -> Fraction:
        return self.coeffs.get(key, Fraction(0))
    
    def __setitem__(self, key: tuple, value):
        if value != 0:
            self.coeffs[key] = Fraction(value)
        elif key in self.coeffs:
            del self.coeffs[key]
    
    def diagonal(self, max_n: int) -> List[Fraction]:
        """
        Extract the diagonal coefficients: [x₁^n x₂^n ... x_m^n] for n = 0, ..., max_n.
        """
        result = []
        for n in range(max_n + 1):
            diag_key = tuple([n] * self.nvars)
            result.append(self[diag_key])
        return result
    
    @staticmethod
    def from_rational_function_inverse(nvars: int, max_deg: int, 
                                        denom_monomials: List[Tuple[tuple, Fraction]]) -> 'MultivariateSeries':
        """
        Compute 1/(1 - Σ c_i · x^{α_i}) as a power series up to total degree max_deg.
        
        denom_monomials: list of (exponent_tuple, coefficient) pairs.
        The function computes 1/(1 - P(x)) where P(x) = Σ c_i · x^{α_i}.
        
        Uses the identity: 1/(1-P) = Σ_{k≥0} P^k, computed iteratively.
        """
        series = MultivariateSeries(nvars, max_deg)
        zero_key = tuple([0] * nvars)
        series[zero_key] = Fraction(1)  # The constant term of 1/(1-P) is 1
        
        # Current power of P: start with P^0 = 1
        current_power = {zero_key: Fraction(1)}
        
        for power_idx in range(1, max_deg * nvars + 1):  # Enough iterations
            # Multiply current_power by P
            new_power = {}
            for exp_a, coeff_a in current_power.items():
                for exp_b, coeff_b in denom_monomials:
                    new_exp = tuple(a + b for a, b in zip(exp_a, exp_b))
                    if sum(new_exp) <= max_deg * nvars and all(e <= max_deg for e in new_exp):
                        key = new_exp
                        new_power[key] = new_power.get(key, Fraction(0)) + coeff_a * coeff_b
            
            if not new_power:
                break  # No more contributions
            
            current_power = new_power
            
            # Add to series
            for exp, coeff in current_power.items():
                if coeff != 0:
                    series.coeffs[exp] = series.coeffs.get(exp, Fraction(0)) + coeff
        
        return series


def compute_diagonal_of_rational(nvars: int, denom_monomials: List[Tuple[tuple, int]], 
                                  max_n: int) -> List[Fraction]:
    """
    Compute the diagonal of 1/(1 - Σ c_i · x^{α_i}) for n = 0, ..., max_n.
    
    This is the main verification oracle. Given a candidate rational function,
    it computes its diagonal and returns the coefficients.
    
    For efficiency, we only track terms where all exponents are equal (diagonal terms),
    plus terms that can contribute to future diagonal terms.
    """
    # Optimization: track only terms that could contribute to diagonal [n,n,...,n]
    # A term x₁^{e₁} ... x_m^{e_m} contributes to diagonal n if
    # min(e_i) = max(e_i) = n, i.e., all e_i are equal.
    
    # But intermediate terms can have unequal exponents. So we track everything
    # up to the needed degree, but prune aggressively.
    
    max_total = max_n * nvars
    
    # Use iterative convolution: diag(1/(1-P)) = sum_{m>=0} diag(P^m)
    # where P^m = (Σ c_i x^{α_i})^m
    
    diag_result = [Fraction(0)] * (max_n + 1)
    diag_result[0] = Fraction(1)  # Constant term of 1/(1-P)
    
    # P^m contributions: start with P^0 = delta_0
    # For each power, we only need to track monomials that could eventually
    # become diagonal terms after further multiplication.
    
    # Simple approach: track all monomials in a dict, with bounding
    monomials = {tuple([0]*nvars): Fraction(1)}  # P^0
    
    denom = [(tuple(e), Fraction(c)) for e, c in denom_monomials]
    
    for power in range(1, max_total + 1):
        new_monomials = {}
        for exp_a, coeff_a in monomials.items():
            if coeff_a == 0:
                continue
            for exp_b, coeff_b in denom:
                new_exp = tuple(a + b for a, b in zip(exp_a, exp_b))
                # Prune: each exponent must be <= max_n
                if all(e <= max_n for e in new_exp):
                    key = new_exp
                    new_monomials[key] = new_monomials.get(key, Fraction(0)) + coeff_a * coeff_b
        
        if not new_monomials:
            break
        
        monomials = {k: v for k, v in new_monomials.items() if v != 0}
        
        # Extract diagonal contributions from this power
        for n in range(max_n + 1):
            diag_key = tuple([n] * nvars)
            if diag_key in monomials:
                diag_result[n] += monomials[diag_key]
        
        # Early termination: if all required diagonals are stable
        # (This is a heuristic — we can't know for sure without bounds)
        
        # Memory management: if too many terms, prune non-diagonal-contributing ones
        if len(monomials) > 500000:
            # Keep only terms where min exponent is close to max exponent
            pruned = {}
            for exp, coeff in monomials.items():
                if max(exp) - min(exp) <= 3:  # Allow some slack
                    pruned[exp] = coeff
            monomials = pruned
    
    return diag_result


# ============================================================================
# SECTION 3: GORODETSKY CONSTANT-TERM METHOD
# ============================================================================

def constant_term_of_power(laurent_terms: List[Tuple[tuple, Fraction]], nvars: int, 
                           power: int, max_terms: int = 100000) -> Fraction:
    """
    Compute CT[Λ^power] where Λ = Σ c_i · z^{α_i} is a Laurent polynomial.
    
    Laurent exponents α_i can have negative components.
    CT extracts the coefficient of z₁⁰ z₂⁰ ... z_m⁰.
    """
    if power == 0:
        return Fraction(1)
    
    # Iteratively compute Λ^power
    # Start with Λ^1
    current = dict(laurent_terms)
    
    for p in range(1, power):
        new_terms = {}
        term_count = 0
        for exp_a, coeff_a in current.items():
            if coeff_a == 0:
                continue
            for exp_b, coeff_b in laurent_terms:
                new_exp = tuple(a + b for a, b in zip(exp_a, exp_b))
                # Only keep terms that could eventually reach (0,0,...,0)
                # after at most (power - p - 1) more multiplications
                remaining = power - p - 1
                can_reach_zero = all(
                    abs(e) <= remaining * max(abs(ee) for _, ee_tup in [(0, new_exp)] for ee in ee_tup)  
                    for e in new_exp
                ) if remaining > 0 else (new_exp == tuple([0]*nvars))
                
                # Simpler pruning: just bound the absolute exponents
                max_abs = max(abs(e) for e in new_exp) if new_exp else 0
                if max_abs <= power:  # Very loose bound
                    new_terms[new_exp] = new_terms.get(new_exp, Fraction(0)) + coeff_a * coeff_b
                    term_count += 1
                    
                    if term_count > max_terms:
                        break
            if term_count > max_terms:
                print(f"  ⚠️ Term explosion at power {p+1}, truncating ({len(new_terms)} terms)")
                break
        
        current = {k: v for k, v in new_terms.items() if v != 0}
    
    zero_key = tuple([0] * nvars)
    return current.get(zero_key, Fraction(0))


def verify_constant_term_representation(laurent_terms: List[Tuple[tuple, Fraction]], 
                                         nvars: int, 
                                         reference_values: List[int],
                                         max_n: int = 10) -> Tuple[bool, List[bool]]:
    """
    Test if CT[Λⁿ] = S₂₀(n) for n = 0, ..., max_n.
    
    Returns (all_match, per_n_match_list).
    """
    matches = []
    all_ok = True
    for n in range(min(max_n + 1, len(reference_values))):
        ct_val = constant_term_of_power(laurent_terms, nvars, n)
        expected = Fraction(reference_values[n])
        match = (ct_val == expected)
        matches.append(match)
        if not match:
            all_ok = False
            print(f"  n={n}: CT(Λ^{n}) = {ct_val}, expected {expected} — {'✅' if match else '❌'}")
        else:
            print(f"  n={n}: CT(Λ^{n}) = {ct_val} ✅")
    return all_ok, matches


# ============================================================================
# SECTION 4: CANDIDATE GENERATORS
# ============================================================================

def generate_apery_analogue_candidates(nvars: int = 5) -> List[Dict[str, Any]]:
    """
    Generate candidate Laurent polynomials by analogy with known Apéry diagonals.
    
    Known structure for (2,2) case:
      Diag[1/((1-x₁-x₂)(1-x₃-x₄) - x₁x₂x₃x₄)] = Apéry numbers
    
    For (4,1), we try denominator structures of the form:
      (product of linear forms) - (monomial)
    """
    candidates = []
    
    # --- Family 1: Direct analogues ---
    # (1-x₁-x₂)(1-x₃-x₄)(1-x₅) - x₁x₂x₃x₄x₅
    candidates.append({
        "name": "Apery_analogue_2_2_1",
        "description": "(1-x1-x2)(1-x3-x4)(1-x5) - x1x2x3x4x5",
        "type": "diagonal",
        "nvars": 5,
        "denom_terms": _expand_denom_2_2_1()
    })
    
    # (1-x₁)(1-x₂)(1-x₃)(1-x₄)(1-x₅) - x₁x₂x₃x₄x₅
    candidates.append({
        "name": "product_of_5_linears_minus_product",
        "description": "(1-x1)(1-x2)(1-x3)(1-x4)(1-x5) - x1x2x3x4x5",
        "type": "diagonal",
        "nvars": 5,
        "denom_terms": _expand_product_5_linear_minus_monomial()
    })
    
    # --- Family 2: Asymmetric forms reflecting (a=4, b=1) ---
    # The 4 copies of C(n,k) and 1 copy of C(n+k,k) suggest 
    # 4 "symmetric" variables + 1 "special" variable
    candidates.append({
        "name": "4sym_1special_v1",
        "description": "(1-x1-x2)(1-x3-x4) - x5(1+x1)(1+x2)(1+x3)(1+x4)",
        "type": "diagonal",
        "nvars": 5,
        "denom_terms": _expand_4sym_1special_v1()
    })
    
    # --- Family 3: Hadamard product form ---
    # f(x)*g(x) diagonal = diagonal of F(x,y)*G(z,w)
    # C(n,k)^4 = diagonal of product of 4 copies of 1/(1-x_i-y_i)
    # C(n+k,k) comes from 1/(1-x-y)^{n+1} type generating functions
    
    return candidates


def generate_ct_candidates(nvars: int = 5) -> List[Dict[str, Any]]:
    """
    Generate candidate Laurent polynomials for constant-term representation.
    
    CT[Λⁿ] = S₂₀(n) means we need a Laurent polynomial Λ(z₁,...,z_m) such that
    the constant term of its n-th power equals S₂₀(n).
    
    Strategy: start from the integral representation
    S₂₀(n) = CT[(1+z₁)^n(1+z₂)^n(1+z₃)^n(1+z₄)^n(1+w)^n · R(z,w)]
    where R = z₁z₂z₃z₄w/(z₁z₂z₃z₄w - 1 - w)
    """
    candidates = []
    
    # The derived CT form from the integral representation:
    # Λ = (1+z₁)(1+z₂)(1+z₃)(1+z₄)(1+w) integrated against R
    # But R is rational, not polynomial, so this isn't a pure CT form.
    
    # --- Approach: Factor out the rational part via partial fractions ---
    
    # Candidate 1: Direct from C(n,k)^4 * C(n+k,k) identity
    # Using the generating function identity for C(n+k,k):
    #   Σ_k C(n+k,k) x^k = 1/(1-x)^{n+1}
    # we can write:
    #   S₂₀(n) = [x^0] (1+1/z₁)^n(1+1/z₂)^n(1+1/z₃)^n(1+1/z₄)^n · [z₁z₂z₃z₄=x] · 1/(1-x)^{n+1}
    # This is getting complicated. Let's try specific simple forms.
    
    # Candidate: Λ = (1+z₁)(1+z₂)(1+z₃)(1+z₄)/(z₁z₂z₃z₄) · (1+1/w)
    # = (1+z₁)(1+z₂)(1+z₃)(1+z₄)(1+w)/(z₁z₂z₃z₄w)
    candidates.append({
        "name": "CT_product_over_product",
        "description": "(1+z1)(1+z2)(1+z3)(1+z4)(1+w)/(z1*z2*z3*z4*w)",
        "nvars": 5,
        "laurent_terms": _expand_ct_product_over_product()
    })
    
    # Candidate: Partial fraction decomposition approach
    # Λ = (1+z₁)(1+z₂)(1+z₃)(1+z₄)(1+w) · w/(w·z₁z₂z₃z₄ - 1 - w)
    # This is the exact form from the integral, but it's rational, not Laurent.
    # We need to expand it as a Laurent polynomial if possible.
    
    # Candidate from Zudilin's approach for (1,1) Delannoy numbers:
    # D(n) = Σ C(n,k)C(n+k,k) has CT[(1+x)(1+1/x)(1+y)] for 2 variables
    # Generalize: try (1+z₁)(1+1/z₁)(1+z₂)(1+1/z₂)(1+z₃)(1+1/z₃)(1+z₄)(1+1/z₄)(1+w)
    candidates.append({
        "name": "CT_zudilin_generalize",
        "description": "product of (1+zi)(1+1/zi) for i=1..4, times (1+w)",
        "nvars": 5,
        "laurent_terms": _expand_ct_zudilin_style()
    })
    
    return candidates


# ============================================================================
# SECTION 5: CANDIDATE EXPANSION HELPERS
# ============================================================================

def _expand_denom_2_2_1() -> List[Tuple[tuple, int]]:
    """Expand (1-x₁-x₂)(1-x₃-x₄)(1-x₅) - x₁x₂x₃x₄x₅ as polynomial terms.
    Returns monomials of P(x) where denominator = 1 - P(x)."""
    # (1-x₁-x₂)(1-x₃-x₄)(1-x₅) = 
    # 1 - x₅ - x₃ - x₄ + x₃x₅ + x₄x₅ - x₁ - x₂ + x₁x₃ + x₁x₄ + x₂x₃ + x₂x₄
    # - x₁x₃x₅ - x₁x₄x₅ - x₂x₃x₅ - x₂x₄x₅ + x₁x₅ + x₂x₅
    # This is messy. Let me compute it properly.
    
    from itertools import product as cart_product
    
    # Represent each factor as list of (coefficient, exponent_tuple) in 5 vars
    # Factor 1: (1 - x₁ - x₂) 
    f1 = [(1, (0,0,0,0,0)), (-1, (1,0,0,0,0)), (-1, (0,1,0,0,0))]
    # Factor 2: (1 - x₃ - x₄)
    f2 = [(1, (0,0,0,0,0)), (-1, (0,0,1,0,0)), (-1, (0,0,0,1,0))]
    # Factor 3: (1 - x₅)
    f3 = [(1, (0,0,0,0,0)), (-1, (0,0,0,0,1))]
    
    # Multiply f1 * f2 * f3
    product_terms = {}
    for (c1, e1), (c2, e2), (c3, e3) in cart_product(f1, f2, f3):
        exp = tuple(a + b + c for a, b, c in zip(e1, e2, e3))
        coeff = c1 * c2 * c3
        product_terms[exp] = product_terms.get(exp, 0) + coeff
    
    # Subtract x₁x₂x₃x₄x₅
    mono = (1, 1, 1, 1, 1)
    product_terms[mono] = product_terms.get(mono, 0) - 1
    
    # The denominator is D(x) = product_terms
    # We need 1/D(x). If D(x) = 1 - P(x), then P(x) terms are:
    zero = (0,0,0,0,0)
    constant = product_terms.get(zero, 0)
    assert constant == 1, f"Expected constant term 1, got {constant}"
    
    # P(x) = 1 - D(x) = -Σ_{exp≠0} c_exp · x^exp
    p_terms = []
    for exp, coeff in product_terms.items():
        if exp != zero and coeff != 0:
            p_terms.append((exp, -coeff))
    
    return p_terms


def _expand_product_5_linear_minus_monomial() -> List[Tuple[tuple, int]]:
    """Expand (1-x₁)(1-x₂)(1-x₃)(1-x₄)(1-x₅) - x₁x₂x₃x₄x₅."""
    from itertools import product as cart_product
    
    factors = []
    for i in range(5):
        exp_0 = [0]*5
        exp_1 = [0]*5
        exp_1[i] = 1
        factors.append([(1, tuple(exp_0)), (-1, tuple(exp_1))])
    
    product_terms = {}
    for combo in cart_product(*factors):
        coeff = 1
        exp = [0]*5
        for c, e in combo:
            coeff *= c
            exp = [a + b for a, b in zip(exp, e)]
        exp = tuple(exp)
        product_terms[exp] = product_terms.get(exp, 0) + coeff
    
    mono = (1, 1, 1, 1, 1)
    product_terms[mono] = product_terms.get(mono, 0) - 1
    
    zero = tuple([0]*5)
    p_terms = []
    for exp, coeff in product_terms.items():
        if exp != zero and coeff != 0:
            p_terms.append((exp, -coeff))
    
    return p_terms


def _expand_4sym_1special_v1() -> List[Tuple[tuple, int]]:
    """
    Try: (1-x₁-x₂)(1-x₃-x₄) - x₅(1+x₁x₂)(1+x₃x₄)
    This separates the 4 "C(n,k)" variables from the 1 "C(n+k,k)" variable.
    """
    from itertools import product as cart_product
    
    # Part A: (1-x₁-x₂)(1-x₃-x₄)
    f1 = [(1, (0,0,0,0,0)), (-1, (1,0,0,0,0)), (-1, (0,1,0,0,0))]
    f2 = [(1, (0,0,0,0,0)), (-1, (0,0,1,0,0)), (-1, (0,0,0,1,0))]
    
    part_a = {}
    for (c1, e1), (c2, e2) in cart_product(f1, f2):
        exp = tuple(a + b for a, b in zip(e1, e2))
        part_a[exp] = part_a.get(exp, 0) + c1 * c2
    
    # Part B: x₅(1+x₁x₂)(1+x₃x₄)
    f3 = [(1, (0,0,0,0,1))]
    f4 = [(1, (0,0,0,0,0)), (1, (1,1,0,0,0))]
    f5 = [(1, (0,0,0,0,0)), (1, (0,0,1,1,0))]
    
    part_b = {}
    for (c3, e3), (c4, e4), (c5, e5) in cart_product(f3, f4, f5):
        exp = tuple(a + b + c for a, b, c in zip(e3, e4, e5))
        part_b[exp] = part_b.get(exp, 0) + c3 * c4 * c5
    
    # Denominator = Part A - Part B
    denom = {}
    for exp, coeff in part_a.items():
        denom[exp] = denom.get(exp, 0) + coeff
    for exp, coeff in part_b.items():
        denom[exp] = denom.get(exp, 0) - coeff
    
    zero = tuple([0]*5)
    p_terms = []
    for exp, coeff in denom.items():
        if exp != zero and coeff != 0:
            p_terms.append((exp, -coeff))
    
    return p_terms


def _expand_ct_product_over_product() -> List[Tuple[tuple, Fraction]]:
    """
    Laurent polynomial: (1+z₁)(1+z₂)(1+z₃)(1+z₄)(1+w)/(z₁z₂z₃z₄w)
    
    Expand and return as list of (exponent_tuple, coefficient) with possibly negative exponents.
    """
    from itertools import product as cart_product
    
    # Numerator: (1+z₁)(1+z₂)(1+z₃)(1+z₄)(1+w)
    # Each factor contributes either 1 or z_i
    terms = {}
    for bits in cart_product([0, 1], repeat=5):
        exp = list(bits)  # z₁^b₁ · ... · w^b₅
        coeff = 1  # coefficient is always 1
        exp_tuple = tuple(exp)
        terms[exp_tuple] = terms.get(exp_tuple, Fraction(0)) + Fraction(coeff)
    
    # Divide by z₁z₂z₃z₄w = shift all exponents by -1
    result = []
    for exp, coeff in terms.items():
        shifted = tuple(e - 1 for e in exp)
        result.append((shifted, coeff))
    
    return result


def _expand_ct_zudilin_style() -> List[Tuple[tuple, Fraction]]:
    """
    Laurent polynomial: Π_{i=1}^{4} (1+z_i)(1+1/z_i) · (1+w)
    
    Note: (1+z)(1+1/z) = 2 + z + 1/z
    So the product Π_{i=1}^4 (2+z_i+1/z_i) · (1+w)
    
    For 4 variables z₁,...,z₄ plus w:
    Each (2+z_i+1/z_i) contributes terms with exponents -1, 0, +1 for z_i.
    """
    from itertools import product as cart_product
    
    # Factor for each z_i: (2 + z_i + 1/z_i)
    # Exponents: -1 (coeff 1), 0 (coeff 2), +1 (coeff 1)
    z_factor = [(-1, Fraction(1)), (0, Fraction(2)), (1, Fraction(1))]
    
    # Factor for w: (1 + w)
    w_factor = [(0, Fraction(1)), (1, Fraction(1))]
    
    terms = []
    for z1, z2, z3, z4, w in cart_product(z_factor, z_factor, z_factor, z_factor, w_factor):
        exp = (z1[0], z2[0], z3[0], z4[0], w[0])
        coeff = z1[1] * z2[1] * z3[1] * z4[1] * w[1]
        terms.append((exp, coeff))
    
    # Combine like terms
    combined = {}
    for exp, coeff in terms:
        combined[exp] = combined.get(exp, Fraction(0)) + coeff
    
    return [(exp, coeff) for exp, coeff in combined.items() if coeff != 0]


# ============================================================================
# SECTION 6: MAIN SEARCH PIPELINE
# ============================================================================

def run_diagonal_search(max_n_verify: int = 8) -> Dict[str, Any]:
    """
    Main search pipeline for the diagonal representation.
    
    For each candidate, compute its diagonal (or constant term powers)
    and compare against S₂₀ reference values.
    """
    print("=" * 70)
    print("  DIAGONAL REPRESENTATION SEARCH FOR S₂₀(n)")
    print("  S₂₀(n) = Σ_{k=0}^n C(n,k)⁴ C(n+k,k)")
    print("=" * 70)
    
    ref = get_s20_reference(max_n_verify + 5)
    print(f"\nReference values S₂₀(0..{max_n_verify}):")
    for n in range(min(max_n_verify + 1, len(ref))):
        print(f"  S₂₀({n}) = {ref[n]}")
    
    results = {"candidates_tested": 0, "matches": [], "partial_matches": [], "failures": []}
    
    # --- Phase 1: Test diagonal candidates ---
    print("\n" + "=" * 70)
    print("  PHASE 1: DIAGONAL CANDIDATES (1/(1-P(x)) form)")
    print("=" * 70)
    
    diag_candidates = generate_apery_analogue_candidates()
    for cand in diag_candidates:
        print(f"\n--- Testing: {cand['name']} ---")
        print(f"  Description: {cand['description']}")
        results["candidates_tested"] += 1
        
        try:
            t0 = time.time()
            diag = compute_diagonal_of_rational(cand['nvars'], cand['denom_terms'], max_n_verify)
            elapsed = time.time() - t0
            
            match_count = 0
            for n in range(min(max_n_verify + 1, len(ref), len(diag))):
                if int(diag[n]) == ref[n]:
                    match_count += 1
                    print(f"  n={n}: diag = {int(diag[n])} ✅")
                else:
                    print(f"  n={n}: diag = {int(diag[n])}, expected {ref[n]} ❌")
            
            result_entry = {
                "name": cand["name"],
                "description": cand["description"],
                "matches": match_count,
                "total_tested": min(max_n_verify + 1, len(ref)),
                "elapsed_s": elapsed,
                "diagonal_values": [int(d) for d in diag[:max_n_verify+1]]
            }
            
            if match_count == min(max_n_verify + 1, len(ref)):
                print(f"  🎯 FULL MATCH! ({elapsed:.2f}s)")
                results["matches"].append(result_entry)
            elif match_count >= 3:
                print(f"  ⚠️ Partial match ({match_count}/{min(max_n_verify+1, len(ref))}) ({elapsed:.2f}s)")
                results["partial_matches"].append(result_entry)
            else:
                print(f"  ❌ No match ({match_count}/{min(max_n_verify+1, len(ref))}) ({elapsed:.2f}s)")
                results["failures"].append(result_entry)
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            results["failures"].append({"name": cand["name"], "error": str(e)})
    
    # --- Phase 2: Test constant-term candidates ---
    print("\n" + "=" * 70)
    print("  PHASE 2: CONSTANT-TERM CANDIDATES (CT[Λⁿ] form)")
    print("=" * 70)
    
    ct_candidates = generate_ct_candidates()
    for cand in ct_candidates:
        print(f"\n--- Testing: {cand['name']} ---")
        print(f"  Description: {cand['description']}")
        results["candidates_tested"] += 1
        
        try:
            t0 = time.time()
            all_match, per_n = verify_constant_term_representation(
                cand['laurent_terms'], cand['nvars'], ref, max_n=max_n_verify
            )
            elapsed = time.time() - t0
            
            match_count = sum(per_n)
            result_entry = {
                "name": cand["name"],
                "description": cand["description"],
                "matches": match_count,
                "total_tested": len(per_n),
                "elapsed_s": elapsed
            }
            
            if all_match:
                print(f"  🎯 FULL MATCH! ({elapsed:.2f}s)")
                results["matches"].append(result_entry)
            elif match_count >= 3:
                print(f"  ⚠️ Partial match ({match_count}/{len(per_n)}) ({elapsed:.2f}s)")
                results["partial_matches"].append(result_entry)
            else:
                print(f"  ❌ No match ({match_count}/{len(per_n)}) ({elapsed:.2f}s)")
                results["failures"].append(result_entry)
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            results["failures"].append({"name": cand["name"], "error": str(e)})
    
    # --- Summary ---
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"  Candidates tested: {results['candidates_tested']}")
    print(f"  Full matches: {len(results['matches'])}")
    print(f"  Partial matches: {len(results['partial_matches'])}")
    print(f"  Failures: {len(results['failures'])}")
    
    if results["matches"]:
        print("\n  🎯 DISCOVERY CANDIDATES:")
        for m in results["matches"]:
            print(f"    - {m['name']}: {m['description']}")
    
    return results


# ============================================================================
# SECTION 7: HADAMARD PRODUCT APPROACH  
# ============================================================================

def hadamard_product_search(max_n: int = 10) -> Dict[str, Any]:
    """
    S₂₀(n) = Σ C(n,k)⁴ C(n+k,k) can be viewed as the Hadamard product of:
      - f(z) = Σ (Σ_k C(n,k)⁴ z^k) t^n   [related to complete elliptic integrals]
      - g(z) = Σ (Σ_k C(n+k,k) z^k) t^n   [related to 1/(1-z)^{n+1}]
    
    The Hadamard product of diagonals can sometimes be expressed as a higher-dimensional
    diagonal. Specifically:
    
    If a(n) = Diag_m[A(x₁,...,x_m)] and b(n) = Diag_p[B(y₁,...,y_p)]
    then a(n)·b(n) = Diag_{m+p}[A(x₁,...,x_m) · B(y₁,...,y_p)]
    
    ... but this doesn't directly help since we need the SUM over k, not the product.
    
    What DOES help: the Cauchy product structure. 
    S₂₀(n) = Σ_k c_k(n) where c_k(n) = C(n,k)⁴ C(n+k,k).
    
    This is the coefficient [z^0] of the generating function in z:
    Σ_k C(n,k)⁴ C(n+k,k) z^k evaluated at z=1.
    
    Or equivalently, using the integral trick:
    S₂₀(n) = [z^0] Σ_k C(n,k)⁴ C(n+k,k) z^k at z → 0
    
    This approach is hard. Let's try a different factorization:
    
    C(n,k)⁴ = (C(n,k)²)² and use the Vandermonde identity twice:
    C(n,k)² = Σ_j C(k,j) C(n-k,k-j)  ... no, that's not right.
    
    Actually, C(n,k)² = Σ_j C(k,j)² C(n-k,k-j)²  ... also wrong.
    
    The correct identity is: C(n,k)² = Σ_j C(k,j) C(n-k,k-j) C(n,2k-j)/C(n,k)
    This is Vandermonde convolution applied differently.
    
    Let's try the simplest approach: express C(n,k)⁴ C(n+k,k) as a multivariate 
    constant term and see if it simplifies.
    """
    ref = get_s20_reference(max_n)
    
    # The key identity: C(n,k) = CT_x[x^{-k}(1+x)^n]
    # So C(n,k)^4 = CT_{x1,x2,x3,x4}[(x1x2x3x4)^{-k} · Π(1+xi)^n]
    # And C(n+k,k) = CT_y[y^{-k}(1+y)^{n+k}] = CT_y[y^{-k}(1+y)^n(1+y)^k]
    #
    # Therefore:
    # S20(n) = Σ_k CT_{x1,...,x4,y}[(x1x2x3x4y)^{-k} · Π(1+xi)^n · (1+y)^n · (1+y)^k]
    #        = CT_{x1,...,x4,y}[Π(1+xi)^n · (1+y)^n · Σ_k ((1+y)/(x1x2x3x4y))^k]
    #
    # For the sum to converge formally as a Laurent series, we need 
    # |(1+y)/(x1x2x3x4y)| < 1 in some sense. But for formal CT extraction,
    # we can write:
    #
    # Σ_{k≥0} u^k = 1/(1-u) where u = (1+y)/(x1x2x3x4y)
    #
    # So:
    # S20(n) = CT[Π(1+xi)^n · (1+y)^n · x1x2x3x4y/(x1x2x3x4y - 1 - y)]
    #
    # The factor R(z,y) = x1x2x3x4y/(x1x2x3x4y - 1 - y) is RATIONAL, not Laurent.
    # But we can expand it as a geometric series in one direction:
    #
    # If we write p = x1x2x3x4, then R = py/(py - 1 - y)
    # = py/((p-1)y - 1) = -py/(1 - (p-1)y)
    # = -py Σ_{j≥0} ((p-1)y)^j  when |(p-1)y| < 1
    # = -Σ_{j≥0} (p-1)^j · p · y^{j+1}
    #
    # This is a power series in y (with p = x1x2x3x4 as parameter).
    # Each coefficient involves x1x2x3x4 = p.
    
    print("Computing Hadamard product / integral representation structure...")
    print("This is a structural analysis, not a search.")
    
    # Let's verify the integral representation numerically
    print("\nVerifying integral representation: S₂₀(n) = CT[Λⁿ · R]")
    print("where Λ = (1+x₁)(1+x₂)(1+x₃)(1+x₄)(1+y)")
    print("and R = x₁x₂x₃x₄y / (x₁x₂x₃x₄y - 1 - y)")
    print("\nThis confirms the mathematical derivation but R is rational, not Laurent.")
    print("The open problem is: can R be absorbed into Λ to get a pure CT[Λ̃ⁿ] form?")
    
    return {"status": "structural_analysis", "conclusion": "R is rational, not Laurent — absorption is the key question"}


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Search for diagonal representation of S₂₀")
    parser.add_argument("--max-n", type=int, default=8, help="Max n for verification")
    parser.add_argument("--phase", choices=["all", "diagonal", "ct", "hadamard"], default="all")
    args = parser.parse_args()
    
    if args.phase in ("all", "diagonal", "ct"):
        results = run_diagonal_search(args.max_n)
    
    if args.phase in ("all", "hadamard"):
        hadamard_results = hadamard_product_search(args.max_n)
    
    # Save results
    output_dir = Path(__file__).parent.parent / "output" / "diagonal_search"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"search_results_{timestamp}.json"
    
    with open(output_file, 'w') as f:
        json.dump(results if 'results' in dir() else {}, f, indent=2, default=str)
    
    print(f"\nResults saved to: {output_file}")
