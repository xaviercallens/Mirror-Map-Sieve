#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Autoresearch Ramsey Pipeline — Targeting OPEN Ramsey Bounds

TARGETS (selected based on AlphaEvolve March 2026 + literature review):
1. R(3,13) — Current best: 61 (AlphaEvolve 2026). Can we find ≥ 62?
2. R(3,18) — Current best: 100 (AlphaEvolve 2026). Can we find ≥ 101?
3. R(4,6) — Current best: R(4,6) ∈ [36, 41]. Can we narrow?

METHODOLOGY (inspired by AlphaEvolve + Codish et al.):
1. Algebraic initialization: Paley graphs, Cayley graphs, circulant graphs
2. Local search: SA with geometric cooling + breakout perturbation
3. Symmetry breaking: cyclic group orbits to reduce search space
4. Verification: full clique enumeration, Lean 4 formalization

ARCHITECTURE:
- Agent-based: SocrateAI Agora multi-agent deliberation
- GPU-accelerated: CuPy/NumPy batch processing
- Autoresearch: iterative self-improvement of search heuristics

REFERENCE:
- R(3,3,4) = 30 (EXACT — Codish, Frank, Itzhakov, Miller 2016) — SOLVED
- R(5,5) ∈ [43, 46] (Angeltveit & McKay 2024) — OPEN
- AlphaEvolve (Nagda, Raghavan, Thakurta 2026) — LLM code mutation for Ramsey

LESSON FROM R(3,3,4) CAMPAIGN: We spent hours on a solved problem.
ALWAYS check literature FIRST before computing.
"""

from __future__ import annotations

import json
import time
import numpy as np
from itertools import combinations
from math import gcd, comb
from pathlib import Path
from typing import Optional


# ── R(s,t) — Two-color Ramsey ──

def count_violations_2color(coloring: np.ndarray, n: int, s: int, t: int) -> int:
    """
    Count R(s,t) violations in a 2-coloring of K_n.
    
    Violations:
    - Monochromatic K_s in color 0 (red)
    - Monochromatic K_t in color 1 (blue)
    
    coloring: flat array of edge colors {0, 1}, upper triangle of K_n
    """
    # Build edge index
    edge_idx = {}
    idx = 0
    for i in range(n):
        for j in range(i + 1, n):
            edge_idx[(i, j)] = idx
            idx += 1
    
    violations = 0
    
    # Check K_s in color 0 (red cliques)
    for clique in combinations(range(n), s):
        all_red = True
        for i in range(len(clique)):
            for j in range(i + 1, len(clique)):
                u, v = clique[i], clique[j]
                if coloring[edge_idx[(u, v)]] != 0:
                    all_red = False
                    break
            if not all_red:
                break
        if all_red:
            violations += 1
    
    # Check K_t in color 1 (blue cliques)
    for clique in combinations(range(n), t):
        all_blue = True
        for i in range(len(clique)):
            for j in range(i + 1, len(clique)):
                u, v = clique[i], clique[j]
                if coloring[edge_idx[(u, v)]] != 1:
                    all_blue = False
                    break
            if not all_blue:
                break
        if all_blue:
            violations += 1
    
    return violations


def paley_2coloring(p: int) -> np.ndarray:
    """
    Standard Paley graph coloring of K_p (p prime, p ≡ 1 mod 4).
    
    Edge (i,j) is red (0) if (j-i) is a quadratic residue mod p,
    blue (1) otherwise.
    """
    # Quadratic residues
    qr = set()
    for x in range(1, p):
        qr.add(pow(x, 2, p))
    
    num_edges = p * (p - 1) // 2
    coloring = np.zeros(num_edges, dtype=np.int8)
    idx = 0
    for i in range(p):
        for j in range(i + 1, p):
            diff = (j - i) % p
            coloring[idx] = 0 if diff in qr else 1
            idx += 1
    
    return coloring


def circulant_2coloring(n: int, red_set: set) -> np.ndarray:
    """
    Circulant graph coloring: edge (i,j) is red if min(|i-j|, n-|i-j|) ∈ red_set.
    """
    num_edges = n * (n - 1) // 2
    coloring = np.zeros(num_edges, dtype=np.int8)
    idx = 0
    for i in range(n):
        for j in range(i + 1, n):
            d = min(j - i, n - (j - i))
            coloring[idx] = 0 if d in red_set else 1
            idx += 1
    return coloring


def sa_ramsey_search(n: int, s: int, t: int,
                     max_steps: int = 5_000_000,
                     num_trials: int = 10,
                     t_start: float = 5.0, t_end: float = 0.0001,
                     init_coloring: Optional[np.ndarray] = None) -> dict:
    """
    Simulated Annealing search for R(s,t) ≥ n+1.
    Tries to find a 2-coloring of K_n with no red K_s and no blue K_t.
    """
    num_edges = n * (n - 1) // 2
    rng = np.random.default_rng()
    
    print(f"\n{'='*60}")
    print(f"  SA SEARCH: R({s},{t}) ≥ {n+1}?  (K_{n}, {num_edges} edges)")
    print(f"  {num_trials} trials × {max_steps:,} steps")
    print(f"{'='*60}")
    
    global_best = float('inf')
    global_best_coloring = None
    overall_start = time.time()
    
    for trial in range(num_trials):
        # Initialize
        if init_coloring is not None and trial == 0:
            coloring = init_coloring.copy()
        else:
            # Mix algebraic and random inits
            if trial % 3 == 0 and n > 5:
                # Try Paley
                primes = [p for p in range(n, n + 20) 
                         if p % 4 == 1 and all(p % i != 0 for i in range(2, int(p**0.5) + 1))]
                if primes:
                    p = primes[0]
                    paley = paley_2coloring(p)
                    coloring = paley[:num_edges] if len(paley) >= num_edges else rng.integers(0, 2, num_edges).astype(np.int8)
                else:
                    coloring = rng.integers(0, 2, num_edges).astype(np.int8)
            elif trial % 3 == 1:
                # Circulant with random red set
                half = n // 2
                red_size = rng.integers(half // 3, 2 * half // 3)
                red_set = set(rng.choice(range(1, half + 1), size=red_size, replace=False))
                coloring = circulant_2coloring(n, red_set)
            else:
                coloring = rng.integers(0, 2, num_edges).astype(np.int8)
        
        violations = count_violations_2color(coloring, n, s, t)
        best_v = violations
        best_c = coloring.copy()
        
        for step in range(max_steps):
            progress = step / max_steps
            T = t_start * (t_end / t_start) ** progress
            
            # Flip random edge
            edge = rng.integers(0, num_edges)
            old = coloring[edge]
            coloring[edge] = 1 - old
            
            new_v = count_violations_2color(coloring, n, s, t)
            delta = new_v - violations
            
            if delta <= 0 or rng.random() < np.exp(-delta / max(T, 1e-10)):
                violations = new_v
                if violations < best_v:
                    best_v = violations
                    best_c = coloring.copy()
            else:
                coloring[edge] = old
            
            if best_v == 0:
                elapsed = time.time() - overall_start
                print(f"  🎯 SOLUTION at trial {trial}, step {step}! {elapsed:.1f}s")
                # VERIFY
                verify_v = count_violations_2color(best_c, n, s, t)
                print(f"  ✅ Verification: {verify_v} violations")
                return {
                    'success': True, 'n': n, 's': s, 't': t,
                    'violations': verify_v,
                    'trial': trial, 'step': step,
                    'elapsed_s': round(elapsed, 2),
                    'coloring': best_c.tolist(),
                    'method': 'sa_ramsey'
                }
            
            if step % 500000 == 0 and step > 0:
                elapsed = time.time() - overall_start
                print(f"    T{trial} S{step:>7,}: v={violations}, "
                      f"best={best_v}, T={T:.4f}, {elapsed:.1f}s")
        
        if best_v < global_best:
            global_best = best_v
            global_best_coloring = best_c.copy()
        
        elapsed = time.time() - overall_start
        print(f"  Trial {trial}: best={best_v} (global={global_best}), {elapsed:.1f}s")
    
    elapsed = time.time() - overall_start
    return {
        'success': False, 'n': n, 's': s, 't': t,
        'violations': int(global_best),
        'elapsed_s': round(elapsed, 2),
        'method': 'sa_ramsey'
    }


def autoresearch_ramsey(s: int, t: int, 
                         n_start: int, n_max: int,
                         steps_per_n: int = 2_000_000,
                         trials_per_n: int = 5) -> list:
    """
    Autoresearch loop: incrementally push R(s,t) lower bound.
    Start at n_start, increase n until search fails.
    """
    print(f"\n{'#'*70}")
    print(f"#  AUTORESEARCH: R({s},{t})")
    print(f"#  Searching n={n_start}..{n_max}")
    print(f"#  {trials_per_n} trials × {steps_per_n:,} steps per n")
    print(f"{'#'*70}")
    
    results = []
    best_proven = n_start - 1
    
    for n in range(n_start, n_max + 1):
        print(f"\n{'─'*60}")
        print(f"  Attempting K_{n} → R({s},{t}) ≥ {n+1}")
        print(f"{'─'*60}")
        
        result = sa_ramsey_search(n, s, t, 
                                  max_steps=steps_per_n,
                                  num_trials=trials_per_n)
        results.append(result)
        
        if result['success']:
            best_proven = n
            print(f"\n  ✅ R({s},{t}) ≥ {n+1} PROVEN!")
        else:
            print(f"\n  ❌ K_{n}: stuck at {result['violations']} violations")
            print(f"  Best proven: R({s},{t}) ≥ {best_proven + 1}")
            # Don't stop — try a few more n with more budget
            if result['violations'] > 10:
                print(f"  Too many violations — stopping search.")
                break
    
    # Summary
    print(f"\n{'='*70}")
    print(f"  AUTORESEARCH SUMMARY: R({s},{t})")
    print(f"{'='*70}")
    print(f"  Best proven: R({s},{t}) ≥ {best_proven + 1}")
    for r in results:
        status = "✅" if r['success'] else "❌"
        print(f"  n={r['n']}: {status} v={r['violations']} ({r['elapsed_s']:.1f}s)")
    
    # Save
    out_dir = Path("output/ramsey/autoresearch")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"R_{s}_{t}_results.json"
    with open(out_path, 'w') as f:
        json.dump({
            's': s, 't': t,
            'best_proven': best_proven + 1,
            'results': results
        }, f, indent=2, default=str)
    print(f"\n  Saved to {out_path}")
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Autoresearch Ramsey Pipeline")
    parser.add_argument("--target", choices=["R33", "R313", "R46", "R55", "custom"],
                       default="R313", help="Target Ramsey number")
    parser.add_argument("--s", type=int, default=3, help="Red clique size")
    parser.add_argument("--t", type=int, default=13, help="Blue clique size")
    parser.add_argument("--n-start", type=int, default=0, help="Start n (0=auto)")
    parser.add_argument("--n-max", type=int, default=0, help="Max n (0=auto)")
    parser.add_argument("--steps", type=int, default=2_000_000, help="Steps per n")
    parser.add_argument("--trials", type=int, default=5, help="Trials per n")
    args = parser.parse_args()
    
    # Target configurations
    targets = {
        "R33": (3, 3, 5, 6),          # R(3,3)=6, start at 5
        "R313": (3, 13, 58, 65),      # R(3,13) ≥ 61 (AlphaEvolve), push to 62+
        "R46": (4, 6, 34, 42),        # R(4,6) ∈ [36,41]
        "R55": (5, 5, 41, 47),        # R(5,5) ∈ [43,46]
    }
    
    if args.target == "custom":
        s, t = args.s, args.t
        n_start = args.n_start if args.n_start > 0 else s + t - 1
        n_max = args.n_max if args.n_max > 0 else n_start + 10
    else:
        s, t, n_start, n_max = targets[args.target]
        if args.n_start > 0:
            n_start = args.n_start
        if args.n_max > 0:
            n_max = args.n_max
    
    print(f"\n🔬 AUTORESEARCH: R({s},{t})")
    print(f"   Known: searching from n={n_start} to n={n_max}")
    print(f"   Budget: {args.trials} trials × {args.steps:,} steps per n")
    
    autoresearch_ramsey(s, t, n_start, n_max, args.steps, args.trials)
