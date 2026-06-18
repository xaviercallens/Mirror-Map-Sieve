import os
import sys
from mpmath import mp
import mpmath

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.galois.pslq_reduction import PSLQReductionWorker

def main():
    print("==================================================")
    print(" Galois Experimental Math: Lattice Reduction (PSLQ)")
    print(" Target: Bessel Moment c_5,1")
    print("==================================================\n")

    # Set up worker
    dps = 150
    worker = PSLQReductionWorker(dps=dps)
    mp.dps = dps

    # 1. Target T
    # Loading 115 digit target from HorizonMath dataset
    target_str = "2.4965992507497653561840017811514997432406114327981162232729101382421014141270463045039463065513848490719149810"
    T = mp.mpf(target_str)

    # 2. Candidate C
    # C = Gamma(1/4)^4 / (16 * pi * sqrt(2))
    gamma_1_4 = mpmath.gamma(mp.mpf('0.25'))
    C = (gamma_1_4 ** 4) / (16 * mp.pi * mp.sqrt(2))

    print(f"[Target T]    {T}")
    print(f"[Candidate C] {C}")
    
    # Calculate relative error
    rel_error = mp.fabs(T - C) / T * 100
    print(f"[Rel. Error]  {float(rel_error):.4f}%\n")

    # 3. Pass A: Linear Hunt
    print("--- Pass A: Additive (Linear) Hunt ---")
    print("Basis: [T, C, pi, pi^2, sqrt(2), 1]")
    res_linear = worker.hunt_linear(T, C, tol=1e-100)
    if res_linear["found"]:
        print(f"Relation Found! {res_linear['relation']}")
        print(f"Residual Error: {res_linear['residual']:.2e}")
        if res_linear["confidence_drop"]:
            print(">>> CONFIDENCE DROP DETECTED! Exact identity likely.")
        else:
            print(">>> Residual error too high. Likely a false relation due to insufficient precision.")
    else:
        print("No relation found at current precision.\n")

    # 4. Pass B: Logarithmic Hunt
    print("--- Pass B: Multiplicative (Logarithmic) Hunt ---")
    print("Basis: [ln(T), ln(C), ln(pi), ln(2), ln(3), ln(5)]")
    res_log = worker.hunt_logarithmic(T, C, tol=1e-100)
    if res_log["found"]:
        print(f"Relation Found! {res_log['relation']}")
        print(f"Residual Error: {res_log['residual']:.2e}")
        if res_log["confidence_drop"]:
            print(">>> CONFIDENCE DROP DETECTED! Exact identity likely.")
        else:
            print(">>> Residual error too high. Likely a false relation due to insufficient precision.")
    else:
        print("No relation found at current precision.\n")

if __name__ == "__main__":
    main()
