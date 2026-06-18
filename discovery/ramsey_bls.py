#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Breakout Local Search (BLS) for Ramsey R(3,3,4)

Based on: Benlic & Hao (2013) — Breakout Local Search for the
Maximum Clique Problem.

BLS is specifically designed to escape local minima in combinatorial
optimization, which is exactly what SA fails at for Ramsey numbers.

KEY IDEA:
1. Steepest descent until local minimum
2. At local minimum, apply "breakout" perturbation
3. Perturbation strength adapts: weak first, stronger if stuck
4. Reset if completely stuck

This is much more effective than SA for Ramsey-type problems because:
- SA wastes moves on random uphill moves with low acceptance
- BLS deterministically descends, then deliberately perturbs
- Adaptive perturbation strength avoids cycling

CORRECTED: R(3,3,4) ∈ [30, 31]

Uses the verified O(n²) delta from ramsey_search.py.
"""

from __future__ import annotations

import json
import random
import time
from itertools import combinations
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from discovery.ramsey_search import RamseyColoring


def breakout_local_search(n: int,
                           max_steps: int = 10_000_000,
                           perturbation_base: int = 3,
                           perturbation_max: int = 20,
                           seed: int | None = None) -> dict:
    """Breakout Local Search for R(3,3,4) coloring of K_n.

    Algorithm:
    1. Initialize random 3-coloring
    2. DESCEND: Find the best improving move (steepest descent)
       - Evaluate all edges involved in violations
       - Pick the move that reduces violations most
    3. If no improving move exists → LOCAL MINIMUM
       - Apply perturbation: randomly recolor `strength` edges
       - If violations didn't improve recently, increase strength
       - If violations improved, reset strength to base
    4. Repeat until violations = 0 or max_steps reached

    The perturbation strength adapts:
    - Start at `perturbation_base` (3 edges)
    - Increase by 1 each time we hit a local minimum without improvement
    - Cap at `perturbation_max`
    - Reset to base when we find a new best
    """
    if seed is not None:
        random.seed(seed)

    t0 = time.time()

    # Initialize
    coloring = RamseyColoring.random(n)
    violations = coloring.total_violations()
    best_violations = violations
    best_step = 0

    edges = [(i, j) for i in range(n) for j in range(i + 1, n)]
    strength = perturbation_base
    plateau_count = 0

    print(f"  BLS: n={n}, edges={len(edges)}, "
          f"initial violations={violations}")

    step = 0
    while step < max_steps:
        # ─── Phase 1: Steepest Descent ───
        improved = True
        while improved and step < max_steps:
            improved = False
            best_delta = 0
            best_move = None

            # Evaluate all possible moves on violation-involved edges
            for i, j in edges:
                old_c = coloring.get_color(i, j)
                for new_c in range(3):
                    if new_c == old_c:
                        continue
                    delta = coloring.violation_delta(i, j, old_c, new_c)
                    if delta < best_delta:
                        best_delta = delta
                        best_move = (i, j, old_c, new_c)

            step += 1

            if best_move is not None and best_delta < 0:
                # Apply the best improving move
                i, j, old_c, new_c = best_move
                coloring.set_color(i, j, new_c)
                violations += best_delta
                improved = True

                if violations < best_violations:
                    best_violations = violations
                    best_step = step
                    strength = perturbation_base  # Reset strength
                    plateau_count = 0

                if violations == 0:
                    elapsed = time.time() - t0
                    # Ground-truth verify!
                    actual = coloring.total_violations()
                    if actual == 0:
                        print(f"  ✅ SOLUTION at step {step}! ({elapsed:.1f}s)")
                        return {
                            "success": True,
                            "n": n,
                            "violations": 0,
                            "step": step,
                            "elapsed_s": round(elapsed, 2),
                            "method": "BLS",
                        }
                    else:
                        # Delta tracking error — fix tracked count
                        violations = actual

        # ─── Phase 2: Breakout Perturbation ───
        plateau_count += 1

        # Perturb: randomly recolor `strength` edges
        perturb_edges = random.sample(edges, min(strength, len(edges)))
        for i, j in perturb_edges:
            old_c = coloring.get_color(i, j)
            new_c = random.choice([c for c in range(3) if c != old_c])
            coloring.set_color(i, j, new_c)

        # Recount after perturbation (ground truth)
        violations = coloring.total_violations()

        if violations < best_violations:
            best_violations = violations
            best_step = step
            strength = perturbation_base
            plateau_count = 0
        else:
            # Increase perturbation strength
            strength = min(strength + 1, perturbation_max)

        # Major restart if very stuck
        if plateau_count > 100:
            coloring = RamseyColoring.random(n)
            violations = coloring.total_violations()
            strength = perturbation_base
            plateau_count = 0

        step += 1

        # Progress
        if step % 100 == 0:
            elapsed = time.time() - t0
            print(f"    Step {step:>8d}: violations={violations}, "
                  f"best={best_violations}, strength={strength}, "
                  f"elapsed={elapsed:.1f}s")

    elapsed = time.time() - t0
    return {
        "success": False,
        "n": n,
        "best_violations": best_violations,
        "best_step": best_step,
        "final_violations": violations,
        "total_steps": step,
        "elapsed_s": round(elapsed, 2),
        "method": "BLS",
    }


def bls_campaign(target_n: int = 29, num_trials: int = 10,
                  max_steps: int = 5_000_000) -> dict:
    """Run BLS campaign for R(3,3,4).

    CORRECTED: R(3,3,4) ∈ [30, 31]. Target is K_29.
    """
    t0 = time.time()

    print("=" * 72)
    print(f"  🔬 BREAKOUT LOCAL SEARCH CAMPAIGN — R(3,3,4)")
    print(f"  Known bounds: R(3,3,4) ∈ [30, 31]")
    print(f"  Target: K_{target_n} → R(3,3,4) ≥ {target_n + 1}")
    print("=" * 72)

    results = {}
    for n in range(25, target_n + 1):
        print(f"\n── K_{n} (R(3,3,4) ≥ {n+1}) ──")
        best = None
        for trial in range(num_trials):
            r = breakout_local_search(n, max_steps=max_steps,
                                       perturbation_base=max(3, n // 8),
                                       perturbation_max=max(10, n // 3),
                                       seed=trial * 1000 + n)
            bv = r.get('best_violations', r.get('violations', 999))
            if best is None or bv < best.get('best_violations',
                                              best.get('violations', 999)):
                best = r
            if r['success']:
                best = r
                break

        results[n] = best
        if best['success']:
            print(f"  ✅ R(3,3,4) ≥ {n+1}")
        else:
            bv = best.get('best_violations', best.get('violations', '?'))
            print(f"  ❌ Best: {bv} violations")

    elapsed = time.time() - t0
    print(f"\n{'=' * 72}")
    print(f"  BLS CAMPAIGN RESULTS ({elapsed:.1f}s total)")
    print(f"{'=' * 72}")
    for n in sorted(results.keys()):
        r = results[n]
        if r['success']:
            print(f"  K_{n}: ✅ R(3,3,4) ≥ {n+1}")
        else:
            bv = r.get('best_violations', r.get('violations', '?'))
            print(f"  K_{n}: ❌ (best={bv})")

    # Save
    out_dir = Path("output/ramsey")
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "bls_campaign.json", "w") as f:
        json.dump({str(k): v for k, v in results.items()},
                   f, indent=2, default=str)

    return results


if __name__ == "__main__":
    bls_campaign(target_n=29, num_trials=5, max_steps=2_000_000)
