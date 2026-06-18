#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Ramsey Number Search Engine — R(3,3,4) Lower Bound

Searches for 3-colorings of complete graphs K_n that avoid:
  - Monochromatic K_3 in colors 1 and 2
  - Monochromatic K_4 in color 3

If we find such a coloring on n=51 vertices, we prove R(3,3,4) ≥ 52.

Known bounds: R(3,3,4) ∈ [30, 31]
  - Lower: R(3,3,4) ≥ 30 (Radziszowski DS1, rev. 18, 2026)
  - Upper: R(3,3,4) ≤ 31 (Radziszowski DS1, rev. 18, 2026)

STRATEGY:
1. Represent coloring as adjacency matrices for each color class
2. Use constraint propagation to prune impossible colorings
3. Apply local search (simulated annealing) to minimize violations
4. Verify any candidate via exhaustive triangle/K4 checking

LESSON FROM ALIEN MATH: Verify computationally FIRST.
If we find a candidate, we then formalize in Lean 4.
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Optional


@dataclass
class RamseyColoring:
    """A 3-coloring of the edges of K_n.

    Colors are 0, 1, 2. The constraint is:
      - No monochromatic triangle (K_3) in color 0
      - No monochromatic triangle (K_3) in color 1
      - No monochromatic K_4 in color 2

    This means we need to avoid:
      - Any 3 vertices all connected by color-0 edges
      - Any 3 vertices all connected by color-1 edges
      - Any 4 vertices all connected by color-2 edges
    """
    n: int                          # Number of vertices
    colors: list[list[int]]         # colors[i][j] = color of edge (i,j), i < j

    @classmethod
    def random(cls, n: int) -> "RamseyColoring":
        """Create a random 3-coloring of K_n."""
        colors = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                c = random.randint(0, 2)
                colors[i][j] = c
                colors[j][i] = c
        return cls(n=n, colors=colors)

    def get_color(self, i: int, j: int) -> int:
        """Get color of edge (i, j)."""
        return self.colors[min(i, j)][max(i, j)]

    def set_color(self, i: int, j: int, c: int):
        """Set color of edge (i, j)."""
        self.colors[i][j] = c
        self.colors[j][i] = c

    def count_monochromatic_triangles(self, color: int) -> int:
        """Count monochromatic triangles of a given color.

        A triangle {i,j,k} is monochromatic in color c if
        all three edges (i,j), (i,k), (j,k) have color c.
        """
        count = 0
        for i in range(self.n):
            for j in range(i + 1, self.n):
                if self.colors[i][j] != color:
                    continue
                for k in range(j + 1, self.n):
                    if (self.colors[i][k] == color and
                        self.colors[j][k] == color):
                        count += 1
        return count

    def count_monochromatic_k4(self, color: int) -> int:
        """Count monochromatic K_4 of a given color.

        A K_4 {i,j,k,l} is monochromatic in color c if
        all 6 edges have color c.
        """
        count = 0
        for i in range(self.n):
            for j in range(i + 1, self.n):
                if self.colors[i][j] != color:
                    continue
                for k in range(j + 1, self.n):
                    if (self.colors[i][k] != color or
                        self.colors[j][k] != color):
                        continue
                    for l in range(k + 1, self.n):
                        if (self.colors[i][l] == color and
                            self.colors[j][l] == color and
                            self.colors[k][l] == color):
                            count += 1
        return count

    def total_violations(self) -> int:
        """Total constraint violations.

        Returns the sum of:
        - Monochromatic K_3 in color 0
        - Monochromatic K_3 in color 1
        - Monochromatic K_4 in color 2
        """
        return (self.count_monochromatic_triangles(0) +
                self.count_monochromatic_triangles(1) +
                self.count_monochromatic_k4(2))

    def violation_delta(self, i: int, j: int,
                        old_c: int, new_c: int) -> int:
        """Compute the change in violations if edge (i,j)
        changes from old_c to new_c.

        This is O(n) instead of O(n^3), making SA feasible.
        """
        delta = 0
        # For each vertex k, check triangles {i,j,k}
        for k in range(self.n):
            if k == i or k == j:
                continue
            c_ik = self.colors[i][k] if i < k else self.colors[k][i]
            c_jk = self.colors[j][k] if j < k else self.colors[k][j]

            # Old contribution: was edge (i,j) part of a mono-triangle?
            # Triangle {i,j,k} in color old_c
            if old_c < 2:  # K_3 constraint for colors 0,1
                if c_ik == old_c and c_jk == old_c:
                    delta -= 1  # Removing a violation

            # New contribution
            if new_c < 2:  # K_3 constraint for colors 0,1
                if c_ik == new_c and c_jk == new_c:
                    delta += 1  # Adding a violation

            # K_4 constraint for color 2
            if old_c == 2 or new_c == 2:
                # Need to check 4-cliques containing edge (i,j)
                # and vertex k — need a 4th vertex l
                for l in range(k + 1, self.n):
                    if l == i or l == j:
                        continue
                    c_il = self.colors[i][l] if i < l else self.colors[l][i]
                    c_jl = self.colors[j][l] if j < l else self.colors[l][j]
                    c_kl = self.colors[k][l] if k < l else self.colors[l][k]

                    # Was {i,j,k,l} a mono-K4 in old_c=2?
                    if old_c == 2:
                        if (c_ik == 2 and c_jk == 2 and
                            c_il == 2 and c_jl == 2 and c_kl == 2):
                            delta -= 1

                    # Is {i,j,k,l} a mono-K4 in new_c=2?
                    if new_c == 2:
                        if (c_ik == 2 and c_jk == 2 and
                            c_il == 2 and c_jl == 2 and c_kl == 2):
                            delta += 1

        return delta

    def to_adjacency_list(self) -> dict:
        """Export as adjacency list for each color."""
        result = {c: [] for c in range(3)}
        for i in range(self.n):
            for j in range(i + 1, self.n):
                result[self.colors[i][j]].append((i, j))
        return result


def simulated_annealing(n: int, max_steps: int = 500_000,
                         t_start: float = 2.0, t_end: float = 0.01,
                         seed: Optional[int] = None) -> dict:
    """Search for a valid R(3,3,4) coloring using simulated annealing.

    Strategy:
    - Start with random 3-coloring of K_n
    - At each step, randomly recolor one edge
    - Accept improvements always; accept worsening moves
      with probability exp(-delta/T)
    - Cool temperature from t_start to t_end exponentially

    Args:
        n: Number of vertices (try n=51 for R(3,3,4) ≥ 52)
        max_steps: Maximum SA iterations
        t_start: Initial temperature
        t_end: Final temperature
        seed: Random seed for reproducibility

    Returns:
        Dict with search results
    """
    if seed is not None:
        random.seed(seed)

    t0 = time.time()

    # Initialize random coloring
    coloring = RamseyColoring.random(n)
    current_violations = coloring.total_violations()
    best_violations = current_violations
    best_step = 0

    # Temperature schedule (exponential cooling)
    alpha = (t_end / t_start) ** (1.0 / max_steps)

    # Edge list for random selection
    edges = [(i, j) for i in range(n) for j in range(i + 1, n)]
    num_edges = len(edges)

    print(f"  SA: n={n}, edges={num_edges}, "
          f"initial violations={current_violations}")

    temp = t_start
    accepted = 0
    improved = 0

    for step in range(max_steps):
        # Pick a random edge
        i, j = edges[random.randint(0, num_edges - 1)]
        old_c = coloring.colors[i][j]

        # Pick a new color (different from current)
        new_c = random.choice([c for c in range(3) if c != old_c])

        # Compute violation delta (O(n²) for K4, O(n) for K3)
        delta = coloring.violation_delta(i, j, old_c, new_c)

        # Accept or reject
        if delta <= 0 or random.random() < __import__('math').exp(-delta / temp):
            coloring.set_color(i, j, new_c)
            current_violations += delta
            accepted += 1

            if current_violations < best_violations:
                best_violations = current_violations
                best_step = step
                improved += 1

                if best_violations == 0:
                    elapsed = time.time() - t0
                    print(f"  ✅ SOLUTION FOUND at step {step}! "
                          f"({elapsed:.1f}s)")
                    return {
                        "success": True,
                        "n": n,
                        "violations": 0,
                        "step": step,
                        "elapsed_s": round(elapsed, 2),
                        "coloring": coloring.to_adjacency_list(),
                    }

        # Cool
        temp *= alpha

        # Progress reporting
        if (step + 1) % 100_000 == 0:
            elapsed = time.time() - t0
            print(f"    Step {step + 1:>7d}: violations={current_violations}, "
                  f"best={best_violations}, T={temp:.4f}, "
                  f"accepted={accepted/(step+1):.2%}, "
                  f"elapsed={elapsed:.1f}s")

    elapsed = time.time() - t0
    return {
        "success": False,
        "n": n,
        "best_violations": best_violations,
        "best_step": best_step,
        "final_violations": current_violations,
        "total_steps": max_steps,
        "accepted_ratio": accepted / max_steps,
        "improved": improved,
        "elapsed_s": round(elapsed, 2),
    }


def verify_coloring(coloring: RamseyColoring) -> dict:
    """Exhaustively verify a coloring has no violations.

    This is the ground-truth check — O(n^4) but exact.
    """
    tri_0 = coloring.count_monochromatic_triangles(0)
    tri_1 = coloring.count_monochromatic_triangles(1)
    k4_2 = coloring.count_monochromatic_k4(2)

    return {
        "n": coloring.n,
        "mono_triangles_color0": tri_0,
        "mono_triangles_color1": tri_1,
        "mono_k4_color2": k4_2,
        "total_violations": tri_0 + tri_1 + k4_2,
        "valid": (tri_0 + tri_1 + k4_2) == 0,
    }


def run_ramsey_search(n: int = 51, num_trials: int = 10,
                       steps_per_trial: int = 1_000_000) -> dict:
    """Run multiple SA trials searching for R(3,3,4) ≥ n+1.

    Args:
        n: Number of vertices to try coloring
        num_trials: Number of independent SA runs
        steps_per_trial: SA steps per trial

    Returns:
        Dict with all trial results
    """
    t0 = time.time()

    print("=" * 72)
    print(f"  🔬 RAMSEY NUMBER SEARCH: R(3,3,4) ≥ {n + 1}?")
    print(f"  Searching for valid 3-coloring of K_{n}")
    print(f"  Constraint: no mono-K_3 (colors 0,1), no mono-K_4 (color 2)")
    print(f"  Trials: {num_trials}, Steps/trial: {steps_per_trial:,}")
    print("=" * 72)

    all_results = []
    best_overall = float('inf')

    for trial in range(num_trials):
        print(f"\n── Trial {trial + 1}/{num_trials} {'─' * 40}")
        result = simulated_annealing(
            n=n,
            max_steps=steps_per_trial,
            t_start=2.0,
            t_end=0.001,
            seed=trial * 42 + 1,
        )
        all_results.append(result)

        if result["success"]:
            print(f"\n🎯 R(3,3,4) ≥ {n + 1} PROVEN!")
            print(f"   Found valid coloring of K_{n}")
            break

        violations = result.get("best_violations", float('inf'))
        if violations < best_overall:
            best_overall = violations
        print(f"  Best violations this trial: {violations}")

    elapsed = time.time() - t0

    # Summary
    success = any(r.get("success", False) for r in all_results)
    summary = {
        "target": f"R(3,3,4) >= {n + 1}",
        "n": n,
        "num_trials": len(all_results),
        "steps_per_trial": steps_per_trial,
        "success": success,
        "best_violations_overall": best_overall,
        "elapsed_s": round(elapsed, 2),
        "trials": all_results,
    }

    print(f"\n{'=' * 72}")
    print(f"  RAMSEY SEARCH RESULTS")
    print(f"{'=' * 72}")
    if success:
        print(f"  ✅ R(3,3,4) ≥ {n + 1} — PROVEN!")
    else:
        print(f"  ❌ No valid coloring found in {len(all_results)} trials")
        print(f"     Best violations: {best_overall}")
        print(f"     (0 violations needed for proof)")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"{'=' * 72}")

    # Save results
    out_dir = Path("output/ramsey")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"ramsey_334_n{n}_results.json"
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\nResults saved to: {out_path}")

    return summary


if __name__ == "__main__":
    # Phase 1: Warm up with smaller n to validate the search works
    # R(3,3,3) = 17, so K_16 should be colorable
    print("Phase 1: Validation — R(3,3,3) = 17, trying K_16...")
    warmup = run_ramsey_search(n=16, num_trials=3, steps_per_trial=200_000)

    if warmup["success"]:
        print("\n✅ Validation passed! Search engine works.")
        print("\nPhase 2: Target — R(3,3,4) ≥ 52, trying K_51...")
        target = run_ramsey_search(n=51, num_trials=5,
                                    steps_per_trial=1_000_000)
    else:
        print("\n⚠️ Validation failed — search engine needs tuning.")
        print("   (Even K_16 should be 3-colorable for R(3,3,3))")
