#!/usr/bin/env python3
"""
SAT-based Ramsey R(3,3,4) search with subprocess-based timeout.

Uses subprocess.run() to invoke the SAT worker with a hard timeout.
This actually works (unlike SIGALRM) because the OS kills the subprocess.
"""

import sys
import os
import time
import json
import subprocess
from itertools import combinations

sys.path.insert(0, "/Users/xcallens/xdev/SocrateAI-Scientific-Agora")

from discovery.ramsey_sat import generate_ramsey_cnf, edge_var, write_dimacs

WORKER = "/Users/xcallens/xdev/SocrateAI-Scientific-Agora/sat_worker.py"
PYTHON = sys.executable


def decode_and_verify(model, n):
    """Decode SAT model and verify the coloring."""
    pos_vars = set(v for v in model if v > 0)

    colors = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            for c in range(3):
                var = edge_var(i, j, c, n)
                if var in pos_vars:
                    colors[i][j] = c
                    colors[j][i] = c
                    break

    # Verify: no mono-K3 in colors 0, 1
    violations = 0
    for i, j, k in combinations(range(n), 3):
        for c in [0, 1]:
            if colors[i][j] == c and colors[i][k] == c and colors[j][k] == c:
                violations += 1

    # Verify: no mono-K4 in color 2
    for i, j, k, l in combinations(range(n), 4):
        if (colors[i][j] == 2 and colors[i][k] == 2 and colors[i][l] == 2 and
            colors[j][k] == 2 and colors[j][l] == 2 and colors[k][l] == 2):
            violations += 1

    return colors, violations


def run_sat_search(n, timeout_s=300):
    """Run SAT search using subprocess with hard timeout."""
    print(f"\n{'=' * 60}")
    print(f"  SAT ENCODING: K_{n} → R(3,3,4) ≥ {n+1}?")
    print(f"{'=' * 60}", flush=True)

    t0 = time.time()

    # Generate CNF
    clauses, num_vars = generate_ramsey_cnf(n, symmetry_breaking=True)
    num_edges = n * (n - 1) // 2

    # Write DIMACS
    cnf_path = f"/tmp/ramsey_{n}.cnf"
    write_dimacs(clauses, num_vars, cnf_path)
    cnf_size = os.path.getsize(cnf_path)

    gen_time = time.time() - t0

    print(f"  Variables: {num_vars} ({num_edges} edges × 3 colors)")
    print(f"  Clauses:   {len(clauses):,}")
    print(f"  DIMACS:    {cnf_path} ({cnf_size / 1024:.0f} KB)")
    print(f"  Generation: {gen_time:.2f}s")
    print(f"  Timeout: {timeout_s}s")
    print(f"  Solving with CaDiCaL 153 (subprocess)...", flush=True)

    # Solve via subprocess
    output_path = f"/tmp/ramsey_{n}_result.json"
    solve_start = time.time()

    try:
        result = subprocess.run(
            [PYTHON, WORKER, cnf_path, output_path],
            timeout=timeout_s,
            capture_output=True, text=True
        )
        solve_time = time.time() - solve_start

        if result.returncode == 10:  # SAT
            with open(output_path) as f:
                data = json.load(f)
            model = data["model"]
            colors, violations = decode_and_verify(model, n)

            total_time = time.time() - t0
            print(f"  ✅ SATISFIABLE — R(3,3,4) ≥ {n+1} PROVEN!")
            print(f"     Solve time: {solve_time:.2f}s")
            print(f"     Verification: {violations} violations")

            if colors:
                color_counts = [0, 0, 0]
                for i in range(n):
                    for j in range(i + 1, n):
                        color_counts[colors[i][j]] += 1
                print(f"     Color distribution: c0={color_counts[0]}, c1={color_counts[1]}, c2={color_counts[2]}")

            return {
                "n": n, "target": f"R(3,3,4) >= {n+1}",
                "satisfiable": True, "verified": violations == 0,
                "violations": violations,
                "num_vars": num_vars, "num_clauses": len(clauses),
                "solve_time_s": round(solve_time, 2),
                "total_time_s": round(total_time, 2),
            }

        elif result.returncode == 20:  # UNSAT
            total_time = time.time() - t0
            print(f"  ❌ UNSATISFIABLE — R(3,3,4) ≤ {n}")
            print(f"     Solve time: {solve_time:.2f}s")

            return {
                "n": n, "target": f"R(3,3,4) >= {n+1}",
                "satisfiable": False,
                "num_vars": num_vars, "num_clauses": len(clauses),
                "solve_time_s": round(solve_time, 2),
                "total_time_s": round(total_time, 2),
            }
        else:
            print(f"  ⚠️ Solver error (exit code {result.returncode})")
            if result.stderr:
                print(f"     stderr: {result.stderr[:200]}")
            return {
                "n": n, "target": f"R(3,3,4) >= {n+1}",
                "satisfiable": None, "error": True,
                "num_vars": num_vars, "num_clauses": len(clauses),
                "solve_time_s": round(solve_time, 2),
            }

    except subprocess.TimeoutExpired:
        solve_time = time.time() - solve_start
        total_time = time.time() - t0
        print(f"  ⏱️ TIMEOUT after {timeout_s}s")

        return {
            "n": n, "target": f"R(3,3,4) >= {n+1}",
            "satisfiable": None, "timeout": True,
            "num_vars": num_vars, "num_clauses": len(clauses),
            "solve_time_s": round(solve_time, 2),
            "total_time_s": round(total_time, 2),
        }


# ──── Main execution ────

results = []
overall_start = time.time()

# Phase 1: Quick validation
print("=" * 60)
print("  PHASE 1: Solver validation (small n)")
print("=" * 60, flush=True)

for n in [10, 15, 20, 25]:
    result = run_sat_search(n, timeout_s=60)
    results.append(result)
    sys.stdout.flush()

# Phase 2: Target instances
print("\n" + "=" * 60)
print("  PHASE 2: Target instances (n=27, 28, 29, 30)")
print("=" * 60, flush=True)

for n in [27, 28, 29, 30]:
    timeout = {27: 300, 28: 300, 29: 600, 30: 600}[n]
    result = run_sat_search(n, timeout_s=timeout)
    results.append(result)
    sys.stdout.flush()

    if result.get("satisfiable") is False:
        print(f"\n  ❌ n={n} UNSAT => R(3,3,4) ≤ {n}")
        print("  Stopping — no point trying larger n.")
        break

# ──── Summary ────
print(f"\n\n{'=' * 70}")
print(f"  SUMMARY — SAT-based R(3,3,4) Search")
print(f"{'=' * 70}")
for r in results:
    sat_str = {True: "✅ SAT", False: "❌ UNSAT", None: "⏱️ TIMEOUT"}.get(r.get("satisfiable"), "❓")
    verified = ""
    if 'verified' in r:
        verified = f" | Verified: {r['verified']}"
    timeout_str = ""
    if r.get("timeout"):
        timeout_str = " (timeout)"
    print(f"  n={r['n']:2d}: {sat_str:12s} => {r['target']} | "
          f"{r.get('solve_time_s', 0):7.2f}s | {r['num_clauses']:>10,} clauses{verified}{timeout_str}")

total_time = time.time() - overall_start
print(f"\n  Total wall time: {total_time:.1f}s")
print(f"{'=' * 70}")

# Save
output_path = "/tmp/ramsey_sat_results.json"
with open(output_path, 'w') as f:
    json.dump(results, f, indent=2)
print(f"\n  Results saved to {output_path}")
sys.stdout.flush()
