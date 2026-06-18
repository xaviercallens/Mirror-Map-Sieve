#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Computational Falsifier — Tests candidate identities over ℚ

LESSON FROM ALIEN MATH: The rank-26 debunking took 0.06 seconds
with Bläser's formula. Computational falsification should ALWAYS
precede formalization.

This module:
1. Tests each candidate identity for n = min_n .. max_n
2. Uses exact Fraction arithmetic (no floating point!)
3. Attempts to discover closed forms for unknown RHS
4. Classifies results as VERIFIED, FALSIFIED, or NEEDS_FITTING

The key insight from ExactRationalWitness: ℚ-arithmetic is
decidable. If an identity holds over ℚ for all tested values,
it's a strong candidate for Lean 4 formalization.
"""

from __future__ import annotations

import json
import time
from fractions import Fraction
from math import comb
from pathlib import Path

from discovery.conjecture_generator import (
    CandidateIdentity,
    generate_all_candidates,
)


def test_identity(candidate: CandidateIdentity, max_n: int = 20) -> dict:
    """Test a candidate identity for n = min_n .. max_n.

    Uses EXACT rational arithmetic (Fraction) to avoid
    floating-point errors. This is the computational analog
    of ExactRationalWitness's ℚ-decidability.

    Returns a dict with test results and status.
    """
    results = {
        "name": candidate.name,
        "family": candidate.family.value,
        "lhs_expr": candidate.lhs_expr,
        "rhs_expr": candidate.rhs_expr,
        "min_n": candidate.min_n,
        "max_n": max_n,
        "tests": [],
        "status": "VERIFIED",
        "source": candidate.source,
    }

    for n in range(candidate.min_n, max_n + 1):
        try:
            lhs = candidate.lhs_func(n)
            rhs = candidate.rhs_func(n)
            match = (lhs == rhs)

            results["tests"].append({
                "n": n,
                "lhs": str(lhs),
                "rhs": str(rhs),
                "match": match,
            })

            if not match:
                results["status"] = "FALSIFIED"
                # For discovery targets (RHS=0 placeholder), this is expected
                if candidate.source == "discovery target":
                    results["status"] = "NEEDS_FITTING"
                break

        except Exception as e:
            results["tests"].append({
                "n": n,
                "error": str(e),
                "match": False,
            })
            results["status"] = "ERROR"
            break

    candidate.max_test_n = max_n
    candidate.status = results["status"]
    return results


def discover_closed_form(candidate: CandidateIdentity,
                          max_n: int = 30) -> dict:
    """Attempt to discover a closed form for the LHS.

    Strategy:
    1. Compute LHS(n) for n = min_n .. max_n
    2. Compute ratios LHS(n+1)/LHS(n) — if polynomial, this is rational
    3. Fit polynomial coefficients to ratio sequence
    4. Check if LHS(n) = P(n) · 2^(n-d) for some polynomial P and shift d

    This is the "polynomial fitting" approach: for Σ k^p · C(n,k),
    the result is always P_p(n) · 2^(n-p) where P_p is a polynomial
    of degree p with integer coefficients (Stirling numbers of 2nd kind).
    """
    values = {}
    for n in range(max(candidate.min_n, 1), max_n + 1):
        values[n] = candidate.lhs_func(n)

    if not values:
        return {"status": "NO_DATA"}

    # Strategy 1: Check if LHS(n) / 2^n is a polynomial in n
    # Compute q(n) = LHS(n) / 2^n for each n
    q_values = {}
    for n, v in values.items():
        q_values[n] = v / Fraction(2 ** n)

    # Check if q(n) is a polynomial by computing finite differences
    # Δ^0 q(n) = q(n)
    # Δ^1 q(n) = q(n+1) - q(n)
    # Δ^d q(n) = 0 for all n implies q is polynomial of degree < d
    ns = sorted(q_values.keys())

    # Compute finite differences
    diffs = [q_values[n] for n in ns]
    degree = -1
    for d in range(len(ns)):
        # Check if all differences at this level are (approximately) zero
        if all(x == Fraction(0) for x in diffs):
            degree = d - 1
            break
        # Compute next level of differences
        diffs = [diffs[i + 1] - diffs[i] for i in range(len(diffs) - 1)]
        if not diffs:
            break

    result = {
        "strategy": "polynomial_times_2n",
        "q_values": {n: str(q) for n, q in list(q_values.items())[:10]},
    }

    if degree >= 0:
        result["polynomial_degree"] = degree
        result["status"] = "FITTED"

        # Reconstruct polynomial using Newton's forward differences
        # q(n) = Σ_{k=0}^{d} C(n-n₀, k) · Δ^k q(n₀)
        n0 = ns[0]
        coeffs = []
        diffs_from_start = [q_values[n] for n in ns]
        for d in range(degree + 1):
            coeffs.append(diffs_from_start[0])
            diffs_from_start = [diffs_from_start[i + 1] - diffs_from_start[i]
                                 for i in range(len(diffs_from_start) - 1)]

        result["newton_coefficients"] = [str(c) for c in coeffs]
        result["base_n"] = n0

        # Try to express as standard polynomial P(n)
        # For the weighted binomial sums, P(n) involves Stirling numbers
        # Let's just output the values and let the user/Lean verify
        result["closed_form_hint"] = (
            f"LHS(n) = Q(n) · 2^n where Q is degree-{degree} polynomial"
        )

        # Verify the fit
        verified = True
        for n in ns[:20]:
            # Reconstruct q(n) from Newton coefficients
            q_reconstructed = Fraction(0)
            for k, c in enumerate(coeffs):
                # Newton basis: C(n - n0, k)
                binom = Fraction(1)
                for j in range(k):
                    binom *= Fraction(n - n0 - j, j + 1)
                q_reconstructed += c * binom
            if q_reconstructed != q_values[n]:
                verified = False
                break
        result["fit_verified"] = verified

    else:
        result["status"] = "NO_POLYNOMIAL_FIT"

    # Strategy 2: Check ratio LHS(n+1) / LHS(n)
    ratios = {}
    for n in ns[:-1]:
        if values[n] != 0:
            ratios[n] = values[n + 1] / values[n]
    result["ratios"] = {n: str(r) for n, r in list(ratios.items())[:10]}

    return result


def run_full_pipeline(max_test_n: int = 25, max_fit_n: int = 30) -> dict:
    """Run the complete falsification + discovery pipeline.

    Steps:
    1. Generate all candidate identities
    2. Test each one computationally (exact ℚ arithmetic)
    3. For discovery targets, attempt closed-form fitting
    4. Report results
    """
    t0 = time.time()
    candidates = generate_all_candidates()

    print("=" * 72)
    print("  COMBINATORIAL IDENTITY DISCOVERY PIPELINE")
    print("  Socrate AI Lab — Computational Falsification Phase")
    print("=" * 72)
    print(f"\nGenerated {len(candidates)} candidates")

    all_results = {
        "pipeline": "combinatorial_identity_discovery",
        "version": "0.1.0",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "num_candidates": len(candidates),
        "results": [],
    }

    verified = []
    falsified = []
    needs_fitting = []
    errors = []

    for i, candidate in enumerate(candidates, 1):
        print(f"\n[{i:2d}/{len(candidates)}] {candidate.name}")
        print(f"     LHS: {candidate.lhs_expr}")
        print(f"     RHS: {candidate.rhs_expr}")

        # Step 1: Test the identity
        test = test_identity(candidate, max_n=max_test_n)
        marker = {"VERIFIED": "✅", "FALSIFIED": "❌",
                   "NEEDS_FITTING": "🔍", "ERROR": "⚠️"}
        print(f"     Status: {marker.get(test['status'], '?')} {test['status']}")

        result_entry = {
            "test": test,
        }

        if test["status"] == "VERIFIED":
            verified.append(candidate.name)
            print(f"     Verified for n = {candidate.min_n}..{max_test_n}")

        elif test["status"] == "NEEDS_FITTING":
            needs_fitting.append(candidate.name)
            # Step 2: Try to discover closed form
            print(f"     Attempting closed-form discovery...")
            fit = discover_closed_form(candidate, max_n=max_fit_n)
            result_entry["closed_form"] = fit
            if fit.get("status") == "FITTED":
                print(f"     🎯 Found: {fit.get('closed_form_hint', '?')}")
                print(f"     Degree: {fit.get('polynomial_degree', '?')}")
                print(f"     Fit verified: {fit.get('fit_verified', '?')}")
            else:
                print(f"     No polynomial fit found")

            # Print the actual values for manual inspection
            lhs_values = []
            for n in range(candidate.min_n, min(candidate.min_n + 12, max_fit_n)):
                val = candidate.lhs_func(n)
                lhs_values.append(f"f({n})={val}")
            print(f"     Values: {', '.join(lhs_values[:8])}")

        elif test["status"] == "FALSIFIED":
            falsified.append(candidate.name)
            # Find the first failing n
            for t in test["tests"]:
                if not t.get("match", True):
                    print(f"     Failed at n={t['n']}: "
                          f"LHS={t.get('lhs','?')} ≠ RHS={t.get('rhs','?')}")
                    break

        else:
            errors.append(candidate.name)

        all_results["results"].append(result_entry)

    elapsed = time.time() - t0

    # Summary
    print(f"\n{'=' * 72}")
    print(f"  PIPELINE SUMMARY")
    print(f"{'=' * 72}")
    print(f"  ✅ Verified:     {len(verified):3d} — {verified}")
    print(f"  ❌ Falsified:    {len(falsified):3d} — {falsified}")
    print(f"  🔍 Needs fitting: {len(needs_fitting):3d} — {needs_fitting}")
    print(f"  ⚠️  Errors:       {len(errors):3d}")
    print(f"  Total:           {len(candidates):3d}")
    print(f"  Elapsed:         {elapsed:.2f}s")
    print(f"{'=' * 72}")

    all_results["summary"] = {
        "verified": verified,
        "falsified": falsified,
        "needs_fitting": needs_fitting,
        "errors": errors,
        "elapsed_s": round(elapsed, 2),
    }

    # Save results
    out_dir = Path("output/discovery")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "falsification_results.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults saved to: {out_path}")

    return all_results


if __name__ == "__main__":
    run_full_pipeline()
