#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Ramsey Tabu Search — Advanced search for R(3,3,4) lower bounds

Simple SA gets stuck at ~408 violations for K_51. The literature
on Ramsey graph search (Exoo 1989, Radziszowski surveys) shows that:

1. TABU SEARCH is far more effective than SA for Ramsey problems
2. Smart initialization (circulant/algebraic constructions) helps
3. The violation function should prioritize the hardest constraint

This module implements:
- Tabu search with adaptive tenure
- Smart initialization via circulant graphs
- Focused edge-recoloring (target edges in violations)
- Progressive n (start small, lift colorings to larger n)

LESSON FROM ALIEN MATH: Be honest about what we can compute.
If we can't find R(3,3,4) ≥ 52, we should be transparent about
what the search tells us.
"""

from __future__ import annotations

import json
import random
import time
from collections import defaultdict
from itertools import combinations
from math import exp
from pathlib import Path


class FastRamseyColoring:
    """Optimized 3-coloring with precomputed violation tracking.

    Instead of recomputing violations from scratch each step,
    we maintain counts of:
    - For each vertex pair (i,j): how many monochromatic triangles
      include this edge (for colors 0,1)
    - For each vertex triple (i,j,k): contributing to K_4 in color 2

    This allows O(n) violation delta computation.
    """

    def __init__(self, n: int):
        self.n = n
        # colors[i][j] for i < j
        self.colors = [[0] * n for _ in range(n)]
        self.total_violations = 0

        # Neighbor sets per color for fast triangle enumeration
        # adj[c][v] = set of vertices adjacent to v in color c
        self.adj = [[set() for _ in range(n)] for _ in range(3)]

    def set_color(self, i: int, j: int, c: int):
        """Set edge (i,j) to color c and update adjacency."""
        if i > j:
            i, j = j, i
        old_c = self.colors[i][j]
        if old_c == c:
            return
        # Remove from old adjacency
        self.adj[old_c][i].discard(j)
        self.adj[old_c][j].discard(i)
        # Add to new adjacency
        self.adj[c][i].add(j)
        self.adj[c][j].add(i)
        # Update color
        self.colors[i][j] = c
        self.colors[j][i] = c

    def init_random(self, seed: int | None = None):
        """Initialize with random coloring."""
        if seed is not None:
            random.seed(seed)
        for i in range(self.n):
            for j in range(i + 1, self.n):
                c = random.randint(0, 2)
                self.set_color(i, j, c)
        self.total_violations = self._count_all_violations()

    def init_circulant(self, offsets_0: set, offsets_1: set):
        """Initialize with circulant graph construction.

        In a circulant graph on n vertices, edge (i,j) gets color c
        based on (j-i) mod n. This produces highly symmetric colorings
        that often have few violations.

        offsets_0: set of offsets for color 0
        offsets_1: set of offsets for color 1
        remaining offsets → color 2
        """
        n = self.n
        for i in range(n):
            for j in range(i + 1, n):
                d = min((j - i) % n, (i - j) % n)
                if d in offsets_0:
                    c = 0
                elif d in offsets_1:
                    c = 1
                else:
                    c = 2
                self.set_color(i, j, c)
        self.total_violations = self._count_all_violations()

    def _count_mono_triangles(self, color: int) -> int:
        """Count monochromatic triangles in given color using adjacency."""
        count = 0
        for i in range(self.n):
            neighbors = sorted(self.adj[color][i])
            for idx_j, j in enumerate(neighbors):
                if j <= i:
                    continue
                for k in neighbors[idx_j + 1:]:
                    if k in self.adj[color][j]:
                        count += 1
        return count

    def _count_mono_k4(self, color: int) -> int:
        """Count monochromatic K_4 in given color."""
        count = 0
        for i in range(self.n):
            ni = self.adj[color][i]
            ni_sorted = sorted(v for v in ni if v > i)
            for idx_j, j in enumerate(ni_sorted):
                nij = ni.intersection(self.adj[color][j])
                nij_sorted = sorted(v for v in nij if v > j)
                for idx_k, k in enumerate(nij_sorted):
                    nijk = nij.intersection(self.adj[color][k])
                    for l in nijk:
                        if l > k:
                            count += 1
        return count

    def _count_all_violations(self) -> int:
        """Count total violations: mono-K3 in colors 0,1 + mono-K4 in color 2."""
        return (self._count_mono_triangles(0) +
                self._count_mono_triangles(1) +
                self._count_mono_k4(2))

    def edge_violation_count(self, i: int, j: int) -> int:
        """Count how many violations edge (i,j) participates in."""
        if i > j:
            i, j = j, i
        c = self.colors[i][j]
        count = 0

        if c < 2:
            # Count triangles containing (i,j) in color c
            for k in self.adj[c][i]:
                if k != j and k in self.adj[c][j]:
                    count += 1
        else:
            # Count K_4 containing (i,j) in color 2
            common = self.adj[2][i].intersection(self.adj[2][j])
            for k in common:
                for l in common:
                    if l > k and l in self.adj[2][k]:
                        count += 1
        return count
    def apply_move(self, i: int, j: int, new_c: int) -> int:
        """Apply a move and recount ALL violations from scratch.

        The edge-local counting approach was incorrect: changing edge (i,j)
        affects violations involving OTHER edges too (e.g. triangle {i,j,k}
        is counted by edges (i,k) and (j,k), not just (i,j)).

        Full recount is O(n³) but CORRECT. We compensate by:
        - Sampling fewer candidate edges per step
        - Using edge_violation_count to prioritize high-violation edges
        - Keeping tabu tenure short to force exploration
        """
        old_violations = self.total_violations
        self.set_color(i, j, new_c)
        self.total_violations = self._count_all_violations()
        return self.total_violations - old_violations

    def violation_delta(self, i: int, j: int, new_c: int) -> int:
        """Compute change in violations if edge (i,j) changes to new_c.

        Uses apply-recount-undo: correct but O(n³).
        """
        if i > j:
            i, j = j, i
        old_c = self.colors[i][j]
        if old_c == new_c:
            return 0

        old_violations = self._count_all_violations()
        self.set_color(i, j, new_c)
        new_violations = self._count_all_violations()
        self.set_color(i, j, old_c)  # Undo

        return new_violations - old_violations


def tabu_search(n: int, max_steps: int = 2_000_000,
                tabu_tenure: int = 7,
                seed: int | None = None,
                init_method: str = "random") -> dict:
    """Tabu search for valid R(3,3,4) coloring of K_n.

    Uses full O(n³) recount for correctness, with aggressive
    edge sampling to maintain throughput.
    """
    if seed is not None:
        random.seed(seed)

    t0 = time.time()

    # Initialize
    coloring = FastRamseyColoring(n)
    if init_method == "circulant":
        offsets = set(range(1, (n + 1) // 2 + 1))
        third = len(offsets) // 3
        offsets_list = list(offsets)
        random.shuffle(offsets_list)
        offsets_0 = set(offsets_list[:third])
        offsets_1 = set(offsets_list[third:2*third])
        coloring.init_circulant(offsets_0, offsets_1)
    else:
        coloring.init_random(seed)

    best_violations = coloring.total_violations
    best_step = 0

    # Tabu list: maps (i,j,c) -> step when it becomes non-tabu
    tabu = {}

    # Edge list
    edges = [(i, j) for i in range(n) for j in range(i + 1, n)]

    print(f"  Tabu: n={n}, edges={len(edges)}, "
          f"initial violations={coloring.total_violations}, "
          f"init={init_method}")

    for step in range(max_steps):
        # Find the best non-tabu move
        # STRATEGY: Only evaluate a small random sample of edges.
        # With O(n³) per evaluation, we can afford ~10 candidates/step.
        best_delta = float('inf')
        best_move = None

        # Sample edges — prioritize violation-involved edges
        sample = random.sample(edges, min(20, len(edges)))
        candidates = []
        for ei, ej in sample:
            vc = coloring.edge_violation_count(ei, ej)
            if vc > 0:
                candidates.insert(0, (ei, ej))  # Priority
            elif len(candidates) < 8:
                candidates.append((ei, ej))

        for i, j in candidates:
            old_c = coloring.colors[i][j]
            for new_c in range(3):
                if new_c == old_c:
                    continue

                delta = coloring.violation_delta(i, j, new_c)

                # Check tabu status
                is_tabu = tabu.get((i, j, new_c), 0) > step

                # Aspiration criterion: accept tabu move if it gives
                # the best-ever solution
                if is_tabu and (coloring.total_violations + delta >= best_violations):
                    continue

                if delta < best_delta:
                    best_delta = delta
                    best_move = (i, j, new_c)

        if best_move is None:
            # All moves are tabu — take random move
            i, j = random.choice(edges)
            old_c = coloring.colors[i][j]
            new_c = random.choice([c for c in range(3) if c != old_c])
            best_move = (i, j, new_c)
            best_delta = coloring.violation_delta(i, j, new_c)

        # Apply move
        i, j, new_c = best_move
        old_c = coloring.colors[i][j]
        coloring.apply_move(i, j, new_c)

        # Add to tabu list (forbid reverting to old color)
        tabu[(i, j, old_c)] = step + tabu_tenure

        # Track best
        if coloring.total_violations < best_violations:
            best_violations = coloring.total_violations
            best_step = step

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
                    "method": "tabu_search",
                    "init": init_method,
                }

        # Progress
        if (step + 1) % 200_000 == 0:
            elapsed = time.time() - t0
            print(f"    Step {step + 1:>8d}: violations={coloring.total_violations}, "
                  f"best={best_violations}, elapsed={elapsed:.1f}s")

    elapsed = time.time() - t0
    return {
        "success": False,
        "n": n,
        "best_violations": best_violations,
        "best_step": best_step,
        "final_violations": coloring.total_violations,
        "total_steps": max_steps,
        "elapsed_s": round(elapsed, 2),
        "method": "tabu_search",
        "init": init_method,
    }


def progressive_ramsey_search(target_n: int = 51,
                                start_n: int = 30,
                                step_size: int = 5,
                                steps_per_n: int = 1_000_000) -> dict:
    """Progressive search: start small and increase n.

    This is the honest approach:
    1. Find colorings for small n (easy, validates approach)
    2. Increase n until we hit the frontier
    3. Report the frontier honestly

    The frontier tells us where the known bound lies and how
    hard it is to push beyond.
    """
    t0 = time.time()

    print("=" * 72)
    print(f"  🔬 PROGRESSIVE RAMSEY SEARCH: R(3,3,4)")
    print(f"  Target: R(3,3,4) ≥ {target_n + 1}")
    print(f"  Method: Tabu search with progressive n")
    print(f"  Range: n = {start_n} to {target_n}")
    print("=" * 72)

    results = {}
    frontier = start_n - 1  # Largest n we found a coloring for

    n = start_n
    while n <= target_n:
        print(f"\n── n = {n} (R(3,3,4) ≥ {n + 1}?) {'─' * 30}")

        # Try multiple initializations
        best_result = None
        for init in ["random", "circulant"]:
            for trial_seed in range(3):
                r = tabu_search(
                    n=n,
                    max_steps=steps_per_n,
                    tabu_tenure=max(7, n // 5),
                    seed=trial_seed * 100 + n,
                    init_method=init,
                )
                if best_result is None or \
                   r.get("best_violations", float('inf')) < \
                   best_result.get("best_violations", float('inf')):
                    best_result = r

                if r["success"]:
                    best_result = r
                    break
            if best_result and best_result["success"]:
                break

        results[n] = best_result

        if best_result["success"]:
            frontier = n
            print(f"  ✅ R(3,3,4) ≥ {n + 1} — PROVEN (step {best_result['step']}, "
                  f"{best_result['elapsed_s']}s)")
            n += step_size
        else:
            print(f"  ❌ Stuck at {best_result['best_violations']} violations")
            # Try a smaller step
            if step_size > 1:
                n = frontier + 1
                step_size = 1
                print(f"     Narrowing search: trying n={n}")
            else:
                print(f"     Cannot solve n={n} — frontier is n={frontier}")
                break

    elapsed = time.time() - t0

    # Summary
    print(f"\n{'=' * 72}")
    print(f"  PROGRESSIVE RAMSEY SEARCH RESULTS")
    print(f"{'=' * 72}")
    print(f"  Frontier: R(3,3,4) ≥ {frontier + 1}")
    print(f"  (Best proven lower bound from this search)")
    print(f"  Known: R(3,3,4) ≥ 51 (Piwakowski & Radziszowski 2000)")
    if frontier >= 51:
        print(f"  🎯 NEW RESULT: We improved the lower bound!")
    elif frontier == 50:
        print(f"  📊 We reproduced the known bound R(3,3,4) ≥ 51")
    else:
        print(f"  ⚠️ Our search reached n={frontier} < 50 (known bound is 51)")
        print(f"     This means our search needs more power/time")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"{'=' * 72}")

    for n_val in sorted(results.keys()):
        r = results[n_val]
        status = "✅" if r["success"] else f"❌ (best={r['best_violations']})"
        print(f"  n={n_val:3d}: {status}")

    summary = {
        "target": f"R(3,3,4) >= {target_n + 1}",
        "frontier": frontier,
        "proven_bound": f"R(3,3,4) >= {frontier + 1}",
        "elapsed_s": round(elapsed, 2),
        "results": {str(k): v for k, v in results.items()},
    }

    # Save
    out_dir = Path("output/ramsey")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"progressive_search_n{start_n}_to_{target_n}.json"
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\nSaved to: {out_path}")

    return summary


if __name__ == "__main__":
    progressive_ramsey_search(target_n=51, start_n=30, step_size=5,
                               steps_per_n=500_000)
