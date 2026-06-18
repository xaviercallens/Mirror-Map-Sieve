# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
SageMath Script to extract the exact degree-9 polynomials and Zeilberger certificate
for the S20 sequence: sum_{k=0}^n binomial(n, k)^4 * binomial(n+k, k)

This computes the order-5 creative telescoping relation:
sum_{j=0}^5 P_j(n) F(n+j, k) = G(n, k+1) - G(n, k)
where G(n, k) = R(n, k) F(n, k)
"""

from sage.all import *

def compute_s20_zeilberger():
    print("Loading Maxima zeilberger package...")
    maxima.load("zeilberger")
    
    var('n k')
    
    # Define the summand
    # F(n, k) = binomial(n, k)^4 * binomial(n+k, k)
    F = binomial(n, k)^4 * binomial(n+k, k)
    print(f"Summand F(n, k) = {F}")
    
    print("Executing Zeilberger algorithm (this will take significant time for order 5)...")
    # For a high order recurrence like order 5, we specify MAX_ORD
    maxima.eval('MAX_ORD: 5')
    
    # Zeilberger(F, k, n) returns a list of solutions.
    # The result contains the polynomials P_j(n) and the rational certificate R(n,k).
    try:
        res = maxima(f"Zeilberger({F}, k, n)")
        print("Zeilberger algorithm completed.")
        print(f"Result: {res}")
        return res
    except Exception as e:
        print(f"Error executing Zeilberger: {e}")
        return None

if __name__ == '__main__':
    compute_s20_zeilberger()
