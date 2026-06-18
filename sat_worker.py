#!/usr/bin/env python3
"""
SAT Solver Worker — solves a DIMACS CNF file with pysat CaDiCaL.
Called as a subprocess so the parent can kill it on timeout.

Usage: python3 sat_worker.py <dimacs_file> <output_file>
Exit codes: 10 = SAT, 20 = UNSAT, 1 = error
"""
import sys
import json
from pysat.solvers import Cadical153

def main():
    cnf_path = sys.argv[1]
    output_path = sys.argv[2]

    # Parse DIMACS
    clauses = []
    num_vars = 0
    with open(cnf_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith('c') or line == '':
                continue
            if line.startswith('p cnf'):
                parts = line.split()
                num_vars = int(parts[2])
                continue
            lits = [int(x) for x in line.split()]
            if lits and lits[-1] == 0:
                lits = lits[:-1]
            if lits:
                clauses.append(lits)

    # Solve
    solver = Cadical153()
    for clause in clauses:
        solver.add_clause(clause)

    if solver.solve():
        model = solver.get_model()
        with open(output_path, 'w') as f:
            json.dump({"sat": True, "model": model}, f)
        sys.exit(10)  # SAT
    else:
        with open(output_path, 'w') as f:
            json.dump({"sat": False, "model": None}, f)
        sys.exit(20)  # UNSAT

if __name__ == "__main__":
    main()
