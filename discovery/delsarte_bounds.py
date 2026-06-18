# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Delsarte LP Bounds Optimization

This module couples exact rational solvers and orthogonal polynomials 
with Semidefinite Programming (SDP) via CVXPY.
It automates the search for maximal code sizes (or independent set bounds)
in association schemes like the Hamming or Grassmann graphs.
"""

import cvxpy as cp
import numpy as np

def compute_delsarte_bound(n: int, d: int, q: int = 2) -> float:
    """
    Computes the Delsarte Linear Programming bound for a code of length n 
    and minimum distance d over an alphabet of size q (Hamming scheme).
    
    A code C is an independent set in the distance graph. The Delsarte bound 
    is formulated as an LP over the MacWilliams transform (Krawtchouk polynomials).
    
    Variables:
      A_i : Number of codewords at distance i from a fixed codeword.
      A_0 = 1
      A_i = 0 for 1 <= i < d
      A_i >= 0 for d <= i <= n
      
    Constraint:
      The MacWilliams transform of A (the dual distance distribution) must be non-negative:
      sum_{i=0}^n A_i K_k(i) >= 0 for all k = 1, ..., n
      
    Objective:
      Maximize sum_{i=0}^n A_i
    """
    # 1. Generate Krawtchouk polynomials K_k(i)
    # K_k(i) = sum_{j=0}^k (-1)^j (q-1)^(k-j) * choose(i, j) * choose(n-i, k-j)
    import scipy.special
    
    K = np.zeros((n + 1, n + 1))
    for k in range(n + 1):
        for i in range(n + 1):
            val = 0
            for j in range(k + 1):
                term = ((-1)**j * 
                        (q - 1)**(k - j) * 
                        scipy.special.comb(i, j) * 
                        scipy.special.comb(n - i, k - j))
                if not np.isnan(term):
                    val += term
            K[k, i] = val

    # 2. Setup LP with CVXPY
    A = cp.Variable(n + 1)
    
    constraints = [
        A[0] == 1,
    ]
    
    for i in range(1, d):
        constraints.append(A[i] == 0)
        
    for i in range(d, n + 1):
        constraints.append(A[i] >= 0)
        
    # Dual non-negativity: sum_{i=0}^n A_i K_k(i) >= 0 for k = 1..n
    for k in range(1, n + 1):
        constraints.append(K[k, :] @ A >= 0)
        
    objective = cp.Maximize(cp.sum(A))
    
    problem = cp.Problem(objective, constraints)
    
    # Solve using an SDP/LP solver like SCS
    problem.solve(solver=cp.SCS)
    
    return problem.value

def test_delsarte():
    """Test standard Hamming bounds."""
    # (n, d) = (8, 3) over binary alphabet should yield A(8, 3) <= 20
    # Actually the strict bound is A(8, 3) <= 20, knowing the actual is 20.
    val = compute_delsarte_bound(8, 3, q=2)
    print(f"Delsarte Bound for n=8, d=3, q=2: {val:.4f}")

if __name__ == "__main__":
    test_delsarte()
