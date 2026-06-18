#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Example: Solving the Robertson stiff ODE system with rusty-SUNDIALS.

The Robertson chemical kinetics system is a classic test problem for
stiff ODE solvers. It models three chemical species with rate
constants spanning 7 orders of magnitude:

    dy₁/dt = -0.04·y₁ + 1e4·y₂·y₃
    dy₂/dt =  0.04·y₁ - 1e4·y₂·y₃ - 3e7·y₂²
    dy₃/dt =  3e7·y₂²

Initial conditions: y(0) = [1, 0, 0]
Integration interval: [0, 1e5]

The system requires an implicit solver (BDF) due to extreme stiffness.
Explicit methods (RK4, forward Euler) will fail catastrophically.

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.galileo.tools.sundials_solver import sundials_cvode_solver


def main() -> None:
    """Solve Robertson kinetics and display results."""
    print("=" * 60)
    print("SocrateAI Agora — Stiff ODE Solver Example")
    print("Robertson Chemical Kinetics (3 species, stiff)")
    print("=" * 60)

    # Solve using BDF (implicit, stiff-appropriate)
    print("\n▶ Solving with BDF method (stiff solver)...")
    result = sundials_cvode_solver(
        system="robertson",
        t_span=(0.0, 1e5),
        y0=[1.0, 0.0, 0.0],
        method="BDF",
        rtol=1e-6,
        atol=1e-10,
    )

    if result["success"]:
        print(f"✅ Success: {result['message']}")
        print(f"\nSolver statistics:")
        stats = result.get("stats", {})
        print(f"  Steps:            {stats.get('num_steps', 'N/A')}")
        print(f"  Function evals:   {stats.get('num_func_evals', 'N/A')}")
        print(f"  Jacobian evals:   {stats.get('num_jac_evals', 'N/A')}")

        # Display solution at select time points
        t_vals = result.get("t", [])
        y_vals = result.get("y", [])
        if t_vals and y_vals:
            print(f"\nSolution ({len(t_vals)} output points):")
            print(f"  {'t':>12s}  {'y₁':>12s}  {'y₂':>12s}  {'y₃':>12s}")
            print(f"  {'-'*12}  {'-'*12}  {'-'*12}  {'-'*12}")

            # Show first 5 and last 5 points
            indices = list(range(min(5, len(t_vals))))
            if len(t_vals) > 10:
                indices.extend(range(len(t_vals) - 5, len(t_vals)))

            for i in indices:
                t = t_vals[i]
                y = y_vals[i]
                if len(y) >= 3:
                    print(f"  {t:12.4e}  {y[0]:12.6e}  {y[1]:12.6e}  {y[2]:12.6e}")

            # Mass conservation check
            if y_vals[-1] and len(y_vals[-1]) >= 3:
                final_sum = sum(y_vals[-1])
                print(f"\n  Mass conservation: Σyᵢ = {final_sum:.10f} (should be 1.0)")
                print(f"  Relative error: {abs(final_sum - 1.0):.2e}")
    else:
        print(f"❌ Failed: {result['message']}")

    # Also solve Lorenz system
    print("\n" + "=" * 60)
    print("Lorenz Chaotic Attractor")
    print("=" * 60)

    print("\n▶ Solving with Adams method (non-stiff)...")
    lorenz = sundials_cvode_solver(
        system="lorenz",
        t_span=(0.0, 50.0),
        y0=[1.0, 1.0, 1.0],
        method="Adams",
    )

    if lorenz["success"]:
        print(f"✅ Success: {lorenz['message']}")
        t_vals = lorenz.get("t", [])
        print(f"  Output points: {len(t_vals)}")
    else:
        print(f"❌ Failed: {lorenz['message']}")

    print("\n" + "=" * 60)
    print("Done.")


if __name__ == "__main__":
    main()
