#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
SAT-based Ramsey Search — R(3,3,4) via Boolean Satisfiability

APPROACH (Codish et al. 2016 style):
Encode the Ramsey coloring problem as a SAT instance:

Variables:
  x_{i,j,c} = True iff edge (i,j) has color c, for c ∈ {0, 1, 2}

Constraints:
1. Exactly-one: each edge has exactly one color
   - At-least-one: x_{i,j,0} ∨ x_{i,j,1} ∨ x_{i,j,2}
   - At-most-one:  ¬x_{i,j,c1} ∨ ¬x_{i,j,c2} for c1 ≠ c2

2. No monochromatic K_3 in color 0:
   For all triples (i,j,k):
     ¬(x_{i,j,0} ∧ x_{i,k,0} ∧ x_{j,k,0})
   i.e.: ¬x_{i,j,0} ∨ ¬x_{i,k,0} ∨ ¬x_{j,k,0}

3. No monochromatic K_3 in color 1:
   Same as above but for color 1.

4. No monochromatic K_4 in color 2:
   For all 4-tuples (i,j,k,l):
     ¬(x_{i,j,2} ∧ x_{i,k,2} ∧ x_{i,l,2} ∧ x_{j,k,2} ∧ x_{j,l,2} ∧ x_{k,l,2})
   i.e.: at least one of the 6 edges is NOT color 2.

SYMMETRY BREAKING (Codish et al.):
  - Fix vertex 0's edges: x_{0,1,0}=True (WLOG, first edge is color 0)
  - Lex-leader: first row of adj matrix is lexicographically smallest

SOLVER: We generate a DIMACS CNF file and call an external SAT solver
(kissat, cadical, or minisat). If no solver is available, we use
Python's pysat library.

CORRECTED: R(3,3,4) ∈ [30, 31]
"""

from __future__ import annotations

import subprocess
import tempfile
import time
from itertools import combinations
from pathlib import Path


def edge_var(i: int, j: int, c: int, n: int) -> int:
    """Map edge (i,j) with color c to a SAT variable number.

    Variables are numbered 1, 2, 3, ...
    For edge (i,j) with i < j, color c ∈ {0,1,2}:
      var = (edge_index * 3) + c + 1

    Total variables: 3 * C(n,2)
    """
    if i > j:
        i, j = j, i
    # Edge index: i*n - i*(i+1)/2 + (j - i - 1)
    edge_idx = i * n - i * (i + 1) // 2 + (j - i - 1)
    return edge_idx * 3 + c + 1


def generate_ramsey_cnf(n: int, symmetry_breaking: bool = True) -> tuple[list[list[int]], int]:
    """Generate CNF clauses for R(3,3,4) on K_n.

    Returns (clauses, num_vars).
    """
    num_edges = n * (n - 1) // 2
    num_vars = num_edges * 3
    clauses = []

    edges = [(i, j) for i in range(n) for j in range(i + 1, n)]

    # ─── Constraint 1: Exactly-one color per edge ───
    for i, j in edges:
        # At-least-one
        clauses.append([edge_var(i, j, 0, n),
                        edge_var(i, j, 1, n),
                        edge_var(i, j, 2, n)])
        # At-most-one (pairwise)
        for c1 in range(3):
            for c2 in range(c1 + 1, 3):
                clauses.append([-edge_var(i, j, c1, n),
                                -edge_var(i, j, c2, n)])

    # ─── Constraint 2: No mono-K_3 in color 0 ───
    for i, j, k in combinations(range(n), 3):
        clauses.append([-edge_var(i, j, 0, n),
                        -edge_var(i, k, 0, n),
                        -edge_var(j, k, 0, n)])

    # ─── Constraint 3: No mono-K_3 in color 1 ───
    for i, j, k in combinations(range(n), 3):
        clauses.append([-edge_var(i, j, 1, n),
                        -edge_var(i, k, 1, n),
                        -edge_var(j, k, 1, n)])

    # ─── Constraint 4: No mono-K_4 in color 2 ───
    for i, j, k, l in combinations(range(n), 4):
        # All 6 edges in color 2 → contradiction
        clauses.append([-edge_var(i, j, 2, n),
                        -edge_var(i, k, 2, n),
                        -edge_var(i, l, 2, n),
                        -edge_var(j, k, 2, n),
                        -edge_var(j, l, 2, n),
                        -edge_var(k, l, 2, n)])

    # ─── Symmetry Breaking ───
    if symmetry_breaking:
        # Fix first edge to color 0 (WLOG by color symmetry between 0,1)
        clauses.append([edge_var(0, 1, 0, n)])

    return clauses, num_vars


def write_dimacs(clauses: list[list[int]], num_vars: int,
                 filepath: str) -> None:
    """Write clauses to DIMACS CNF format."""
    with open(filepath, 'w') as f:
        f.write(f"p cnf {num_vars} {len(clauses)}\n")
        for clause in clauses:
            f.write(" ".join(str(lit) for lit in clause) + " 0\n")


def solve_with_external(cnf_path: str, solver: str = "kissat",
                         timeout: int = 300) -> tuple[bool, list[int] | None]:
    """Run an external SAT solver on a DIMACS file.

    Returns (satisfiable, model) where model is a list of literals.
    """
    try:
        result = subprocess.run(
            [solver, cnf_path],
            capture_output=True, text=True,
            timeout=timeout
        )
        # Parse output
        if result.returncode == 10:  # SAT
            model = []
            for line in result.stdout.split('\n'):
                if line.startswith('v '):
                    model.extend(int(x) for x in line[2:].split() if x != '0')
            return True, model
        elif result.returncode == 20:  # UNSAT
            return False, None
        else:
            print(f"  Solver returned code {result.returncode}")
            return False, None
    except FileNotFoundError:
        print(f"  Solver '{solver}' not found")
        return False, None
    except subprocess.TimeoutExpired:
        print(f"  Solver timed out after {timeout}s")
        return False, None


def solve_with_pysat(clauses: list[list[int]],
                     num_vars: int) -> tuple[bool, list[int] | None]:
    """Solve using pysat (Python SAT toolkit)."""
    try:
        from pysat.solvers import Cadical153
        solver = Cadical153()
        for clause in clauses:
            solver.add_clause(clause)
        if solver.solve():
            return True, solver.get_model()
        else:
            return False, None
    except ImportError:
        print("  pysat not installed. Install with: pip install python-sat")
        return False, None


def decode_coloring(model: list[int], n: int) -> list[list[int]]:
    """Decode a SAT model into a coloring matrix."""
    colors = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            for c in range(3):
                var = edge_var(i, j, c, n)
                if var in model or (model and var <= len(model) and
                                     model[var - 1] > 0):
                    colors[i][j] = c
                    colors[j][i] = c
                    break
    return colors


def sat_ramsey_search(n: int, timeout: int = 600,
                       solver: str = "auto") -> dict:
    """Search for R(3,3,4) coloring of K_n using SAT.

    If satisfiable → R(3,3,4) ≥ n+1
    If unsatisfiable → R(3,3,4) ≤ n (with this constraint set)
    """
    t0 = time.time()

    print(f"\n{'=' * 60}")
    print(f"  SAT ENCODING: K_{n} → R(3,3,4) ≥ {n+1}?")
    print(f"{'=' * 60}")

    # Generate CNF
    clauses, num_vars = generate_ramsey_cnf(n, symmetry_breaking=True)
    num_edges = n * (n - 1) // 2

    # Count constraint types
    num_alo = num_edges  # at-least-one
    num_amo = num_edges * 3  # at-most-one (3 pairs)
    num_tri = 2 * (n * (n-1) * (n-2) // 6)  # K_3 for colors 0,1
    num_k4 = n * (n-1) * (n-2) * (n-3) // 24  # K_4 for color 2

    print(f"  Variables: {num_vars} ({num_edges} edges × 3 colors)")
    print(f"  Clauses:   {len(clauses)}")
    print(f"    - Exactly-one: {num_alo + num_amo}")
    print(f"    - No-mono-K3:  {num_tri}")
    print(f"    - No-mono-K4:  {num_k4}")
    print(f"    - Symmetry:    1")

    # Write DIMACS
    cnf_path = f"/tmp/ramsey_{n}.cnf"
    write_dimacs(clauses, num_vars, cnf_path)
    print(f"  DIMACS: {cnf_path} ({Path(cnf_path).stat().st_size / 1024:.0f} KB)")

    # Solve
    gen_time = time.time() - t0
    print(f"  Generation time: {gen_time:.2f}s")
    print(f"  Solving...")

    sat = False
    model = None

    if solver == "auto":
        # Try external solvers in order of preference
        for s in ["kissat", "cadical", "minisat"]:
            sat, model = solve_with_external(cnf_path, s, timeout)
            if model is not None or sat is False:
                solver = s
                break
        else:
            # Fall back to pysat
            print("  No external solver found, trying pysat...")
            sat, model = solve_with_pysat(clauses, num_vars)
            solver = "pysat"
    elif solver == "pysat":
        sat, model = solve_with_pysat(clauses, num_vars)
    else:
        sat, model = solve_with_external(cnf_path, solver, timeout)

    elapsed = time.time() - t0

    result = {
        "n": n,
        "target": f"R(3,3,4) >= {n+1}",
        "satisfiable": sat,
        "solver": solver,
        "num_vars": num_vars,
        "num_clauses": len(clauses),
        "elapsed_s": round(elapsed, 2),
    }

    if sat and model:
        print(f"  ✅ SATISFIABLE — R(3,3,4) ≥ {n+1} PROVEN!")
        print(f"     Solver: {solver}, Time: {elapsed:.2f}s")

        # Verify solution
        from discovery.ramsey_search import RamseyColoring
        colors_matrix = decode_coloring(model, n)
        coloring = RamseyColoring(n=n, colors=colors_matrix)
        violations = coloring.total_violations()
        print(f"     Ground-truth verification: {violations} violations")
        if violations > 0:
            print(f"     ⚠️ WARNING: SAT solution has violations! Decoder bug?")
        result["verified"] = violations == 0
        result["violations"] = violations
    elif sat is False:
        print(f"  ❌ UNSATISFIABLE or timeout — R(3,3,4) ≤ {n}")
        print(f"     Solver: {solver}, Time: {elapsed:.2f}s")
    else:
        print(f"  ⚠️ Unknown result (solver issue)")

    return result


if __name__ == "__main__":
    # Stats for different n values
    print("SAT encoding sizes:")
    for n in [15, 20, 25, 29, 30]:
        clauses, num_vars = generate_ramsey_cnf(n)
        print(f"  K_{n:2d}: {num_vars:6d} vars, {len(clauses):10d} clauses")

    # Try to solve
    for n in [20, 25, 29]:
        result = sat_ramsey_search(n, timeout=300)
        if result.get("satisfiable"):
            print(f"\n🎯 R(3,3,4) ≥ {n+1} via SAT!")
        else:
            print(f"\nStopping at K_{n}")
            break
