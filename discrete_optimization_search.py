#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Discrete Optimization Search Loop - Parallel Extremal Graphs & Hypergeometric Sums

This script runs massively parallel discrete optimization loops:
1. Extremal Graph Theory: Parallel Simulated Annealing to search for R(3,5) graph colorings.
2. Hypergeometric Summation: Parallel fitting of exact closed forms for weighted binomial sums.
"""

import os
import sys
import time
import json
import random
import math
from pathlib import Path
from fractions import Fraction
from itertools import combinations
from concurrent.futures import ProcessPoolExecutor, as_completed

# Make sure we can import local modules if needed
sys.path.insert(0, str(Path(__file__).parent))

# ============================================================================
# EXTREMAL GRAPH THEORY: RAMSEY R(3,5) LOWER BOUND SEARCH
# ============================================================================

def count_r35_violations(colors, n):
    """
    Count violations of R(3,5) coloring constraints.
    - Color 0: No monochromatic K_3 (triangles)
    - Color 1: No monochromatic K_5 (5-cliques)
    """
    violations = 0
    
    # Check monochromatic K_3 in color 0
    for i, j, k in combinations(range(n), 3):
        if colors[i][j] == 0 and colors[i][k] == 0 and colors[j][k] == 0:
            violations += 1
            
    # Check monochromatic K_5 in color 1
    for clique in combinations(range(n), 5):
        all_one = True
        for u, v in combinations(clique, 2):
            if colors[u][v] != 1:
                all_one = False
                break
        if all_one:
            violations += 1
            
    return violations

def sa_ramsey_r35_trial(trial_id, n=13, max_steps=100000, t_start=3.0, t_end=0.01):
    """
    Simulated Annealing trial to find R(3,5) coloring for K_n (usually n=13).
    Since R(3,5)=14, a valid 2-coloring exists for K_13.
    """
    random.seed(trial_id + int(time.time() * 1000) % 10000)
    
    # Initialize random coloring
    colors = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            c = random.randint(0, 1)
            colors[i][j] = c
            colors[j][i] = c
            
    v = count_r35_violations(colors, n)
    best_v = v
    best_colors = [row[:] for row in colors]
    
    t0 = time.time()
    
    for step in range(max_steps):
        if best_v == 0:
            break
            
        progress = step / max_steps
        T = t_start * (t_end / t_start) ** progress
        
        # Select random edge to flip
        i = random.randint(0, n - 2)
        j = random.randint(i + 1, n - 1)
        
        # Flip edge color
        old_color = colors[i][j]
        new_color = 1 - old_color
        colors[i][j] = new_color
        colors[j][i] = new_color
        
        # Evaluate
        new_v = count_r35_violations(colors, n)
        delta = new_v - v
        
        # Accept/Reject
        if delta <= 0 or random.random() < math.exp(-delta / T):
            v = new_v
            if v < best_v:
                best_v = v
                best_colors = [row[:] for row in colors]
        else:
            # Revert
            colors[i][j] = old_color
            colors[j][i] = old_color
            
    elapsed = time.time() - t0
    return {
        "trial_id": trial_id,
        "n": n,
        "success": best_v == 0,
        "violations": best_v,
        "steps_run": step + 1,
        "elapsed_s": round(elapsed, 3),
        "coloring": best_colors if best_v == 0 else None
    }


# ============================================================================
# HYPERGEOMETRIC SUMMATION: RATIONAL POLYNOMIAL FITTING
# ============================================================================

def solve_rational_system(A, b):
    """Solve linear system A x = b exactly using Gaussian elimination over Fraction."""
    n = len(A)
    # Augment matrix
    M = [[Fraction(A[i][j]) for j in range(n)] + [Fraction(b[i])] for i in range(n)]
    
    for i in range(n):
        # Pivot selection
        pivot_row = i
        while pivot_row < n and M[pivot_row][i] == 0:
            pivot_row += 1
        if pivot_row == n:
            raise ValueError("System of equations is singular (no unique solution).")
            
        if pivot_row != i:
            M[i], M[pivot_row] = M[pivot_row], M[i]
            
        pivot = M[i][i]
        for j in range(i, n + 1):
            M[i][j] /= pivot
            
        for k in range(n):
            if k != i:
                factor = M[k][i]
                for j in range(i, n + 1):
                    M[k][j] -= factor * M[i][j]
                    
    return [M[i][n] for i in range(n)]

def comb_nat(n, k):
    """Compute binomial coefficient."""
    if k < 0 or k > n:
        return 0
    res = 1
    for i in range(1, min(k, n - k) + 1):
        res = res * (n - i + 1) // i
    return res

def evaluate_weighted_sum(n, p):
    """Evaluate sum_{k=0}^n k^p * C(n,k) exactly as Fraction."""
    val = sum(k**p * comb_nat(n, k) for k in range(n + 1))
    return Fraction(val)

def fit_weighted_binomial_closed_form(p):
    """
    Discover the closed form for:
       S_p(n) = sum_{k=0}^n k^p * C(n,k)
    Since we know S_p(n) = Q_p(n) * 2^(n - p) where Q_p(n) is a polynomial of degree p,
    we can evaluate S_p(n) for n = p, p+1, ..., 2p and solve for Q_p(n) = sum_{i=0}^p a_i * n^i.
    """
    t0 = time.time()
    
    # We need p+1 equations to fit a polynomial of degree p
    points = []
    for n in range(p, 2 * p + 1):
        s_val = evaluate_weighted_sum(n, p)
        # Q_p(n) = s_val * 2^(p-n)
        q_val = s_val * Fraction(2**(p - n))
        points.append((n, q_val))
        
    # Set up linear system A * a = b where a = [a_0, a_1, ..., a_p]
    A = []
    b = []
    for n_val, q_val in points:
        row = [Fraction(n_val**i) for i in range(p + 1)]
        A.append(row)
        b.append(q_val)
        
    try:
        coefficients = solve_rational_system(A, b)
        
        # Build latex representation of the polynomial Q_p(n)
        poly_terms = []
        for i, coef in enumerate(coefficients):
            if coef == 0:
                continue
            sign = " + " if coef > 0 and poly_terms else ""
            if coef < 0:
                sign = " - " if poly_terms else "-"
            abs_coef = abs(coef)
            
            coef_str = f"{abs_coef}" if abs_coef.denominator != 1 else f"{abs_coef.numerator}"
            if coef_str == "1" and i > 0:
                coef_str = ""
                
            if i == 0:
                poly_terms.append(f"{sign}{coef_str if coef_str else '1'}")
            elif i == 1:
                poly_terms.append(f"{sign}{coef_str}n")
            else:
                poly_terms.append(f"{sign}{coef_str}n^{i}")
                
        poly_str = "".join(poly_terms)
        closed_form = f"({poly_str}) * 2^(n - {p})"
        
        # Validate the fitted closed form on n = 2p + 1 to 2p + 5
        validation_ok = True
        for n in range(2 * p + 1, 2 * p + 6):
            s_val = evaluate_weighted_sum(n, p)
            # Evaluate fitted polynomial
            q_val_fitted = sum(coefficients[i] * Fraction(n**i) for i in range(p + 1))
            s_val_fitted = q_val_fitted * Fraction(2**(n - p))
            if s_val != s_val_fitted:
                validation_ok = False
                break
                
        elapsed = time.time() - t0
        return {
            "p": p,
            "success": validation_ok,
            "coefficients": [str(c) for c in coefficients],
            "closed_form": closed_form,
            "elapsed_s": round(elapsed, 4)
        }
    except Exception as e:
        return {
            "p": p,
            "success": False,
            "error": str(e),
            "elapsed_s": round(time.time() - t0, 4)
        }


# ============================================================================
# PARALLEL ORCHESTRATION
# ============================================================================

def main():
    print("=" * 80)
    print(" 🚀 MASSIVELY PARALLEL DISCRETE OPTIMIZATION SWARM")
    print("=" * 80)
    print(f" CPU Cores Detected: {os.cpu_count()}")
    print(" Running parallel processes across Extremal Graph Theory and Hypergeometric Sums...")
    
    t_start = time.time()
    
    # ── Part 1: Parallel Hypergeometric Sum Fitting ──────────────────
    print("\n[PART 1] Parallel Hypergeometric Polynomial Fitting (Fraction Arithmetic)")
    print(" Target: Discover closed forms for sum_{k=0}^n k^p * C(n,k) in parallel")
    
    sum_results = []
    with ProcessPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fit_weighted_binomial_closed_form, p): p for p in range(1, 6)}
        for fut in as_completed(futures):
            p = futures[fut]
            try:
                res = fut.result()
                sum_results.append(res)
                if res["success"]:
                    print(f"  ✅ p={p} Fit Successful: {res['closed_form']} ({res['elapsed_s']:.4f}s)")
                else:
                    print(f"  ❌ p={p} Fit Failed! Error: {res.get('error', 'unknown error')}")
            except Exception as e:
                print(f"  ⚠️ Worker exception for p={p}: {e}")
                
    # ── Part 2: Parallel Ramsey Simulated Annealing Search ───────────
    print("\n[PART 2] Parallel Ramsey R(3,5) Lower Bound Search (SA on K_13)")
    print(" Target: Find a 2-coloring of K_13 with 0 violations (no red K_3, no blue K_5)")
    print(" Running 4 parallel simulated annealing trials...")
    
    ramsey_results = []
    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(sa_ramsey_r35_trial, i, n=13, max_steps=200000): i for i in range(4)}
        for fut in as_completed(futures):
            i = futures[fut]
            try:
                res = fut.result()
                ramsey_results.append(res)
                if res["success"]:
                    print(f"  🎯 Trial {i} SUCCEEDED! Verified R(3,5) >= 14 witness found. ({res['elapsed_s']:.3f}s)")
                else:
                    print(f"  ❌ Trial {i} Finished: stuck at {res['violations']} violations. ({res['elapsed_s']:.3f}s)")
            except Exception as e:
                print(f"  ⚠️ Worker exception for Trial {i}: {e}")
                
    total_elapsed = time.time() - t_start
    print("\n" + "=" * 80)
    print(" 📊 OPTIMIZATION SWARM COMPLETE")
    print("=" * 80)
    print(f" Total Wall Time: {total_elapsed:.2f}s")
    
    # Save the results to the Alexandrie discrete memory vault
    vault_path = Path("alexandrie_data/discrete_memory.json")
    if vault_path.exists():
        try:
            with open(vault_path, "r") as f:
                vault_data = json.load(f)
        except Exception:
            vault_data = {"domains": ["Extremal Graph Theory", "Hypergeometric Summation"], "memory_nodes": [], "theorems": []}
    else:
        vault_data = {"domains": ["Extremal Graph Theory", "Hypergeometric Summation"], "memory_nodes": [], "theorems": []}
        
    # Add new memory nodes
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Add Ramsey search results
    success_ramsey = any(r["success"] for r in ramsey_results)
    vault_data["memory_nodes"].append({
        "id": int(time.time() * 1000) % 1000000,
        "domain": "Extremal Graph Theory",
        "name": "Ramsey R(3,5) Lower Bound Verification",
        "description": f"Parallel Simulated Annealing search on K_13. Valid coloring found: {success_ramsey}",
        "confidence_score": 1.0 if success_ramsey else 0.5,
        "computational_verification": "Passed exact clique checks" if success_ramsey else "Unsuccessful",
        "timestamp": timestamp
    })
    
    # Add hypergeometric sum results
    for res in sum_results:
        if res["success"]:
            vault_data["memory_nodes"].append({
                "id": int(time.time() * 1000) % 1000000 + res["p"],
                "domain": "Hypergeometric Summation",
                "name": f"Weighted Binomial Sum closed form p={res['p']}",
                "description": f"sum_{{k=0}}^n k^{res['p']} * C(n,k) = {res['closed_form']}",
                "confidence_score": 1.0,
                "computational_verification": "Verified exact rational match on n=[p..2p+5]",
                "timestamp": timestamp
            })
            
    vault_path.parent.mkdir(parents=True, exist_ok=True)
    with open(vault_path, "w") as f:
        json.dump(vault_data, f, indent=4)
        
    print(f" Results successfully archived in Alexandrie Vault: {vault_path}")

if __name__ == "__main__":
    main()
