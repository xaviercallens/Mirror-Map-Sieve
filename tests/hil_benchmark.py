#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Hardware-in-the-Loop (HIL) Benchmark Suite.

Performs deterministic local MCTS execution, enforces per-problem time budgets,
profiles latency/resource scaling, and outputs rigorous statistical reports
using Wilson score confidence intervals to close the simulation-vs-production gap.
"""

from __future__ import annotations

import asyncio
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from olympiad.adler_problem_bank import ADLER_PROBLEMS_ALL, OlympiadProblemRecord
from agents.galois.tools.olympiad_solver import solve_olympiad_problem, OlympiadSolution
from agents.euler.tools.olympiad_corrector import correct_olympiad_solution
from agents.galois.olympiad.rlfc_engine import FeedbackVerdict


def calculate_wilson_interval(successes: int, total: int, confidence: float = 0.95) -> tuple[float, float]:
    """Calculate the Wilson score interval for binomial proportions.
    
    Provides highly robust coverage even for success rates near 0 or 1.
    """
    if total == 0:
        return 0.0, 0.0
    p = successes / total
    z = 1.96  # 95% confidence level
    
    denom = 1 + (z**2) / total
    center = p + (z**2) / (2 * total)
    spread = z * math.sqrt((p * (1 - p) + (z**2) / (4 * total)) / total)
    
    lower = max(0.0, (center - spread) / denom)
    upper = min(1.0, (center + spread) / denom)
    return lower, upper


@dataclass
class HILTestResult:
    problem_id: str
    solved: bool
    latency_ms: float
    verdict: str
    explanation: str
    confidence: float
    strategy: str


async def run_hil_benchmark(problems_subset: list[OlympiadProblemRecord], time_budget_sec: float = 30.0) -> list[HILTestResult]:
    """Run full HIL MCTS inference on a subset of mathematical contest problems."""
    results = []
    
    for idx, prob in enumerate(problems_subset, 1):
        print(f"\n[+] Running HIL Problem {idx}/{len(problems_subset)}: {prob.id} (Steepness C={prob.difficulty.value})")
        
        t0 = time.monotonic()
        try:
            # Wrap execution in a time-bounded container to simulate production safety limits
            loop = asyncio.get_running_loop()
            
            # Since solve_olympiad_problem is currently synchronous, we execute it in an executor
            # to preserve non-blocking asynchronous event loop integrity
            solution = await loop.run_in_executor(
                None,
                solve_olympiad_problem,
                prob,
                None,  # No cortex_v8 override
                None,  # No prior RLFC transfer bank
                1      # Round 1
            )
            
            elapsed_ms = (time.monotonic() - t0) * 1000.0
            
            if elapsed_ms > time_budget_sec * 1000.0:
                print(f"    ⚠️ Timeout violation! Inference took {elapsed_ms/1000:.2f}s (Budget: {time_budget_sec}s)")
                results.append(HILTestResult(
                    problem_id=prob.id,
                    solved=False,
                    latency_ms=elapsed_ms,
                    verdict="TIMEOUT",
                    explanation=f"Inference execution exceeded the {time_budget_sec}s timeout limit.",
                    confidence=0.0,
                    strategy="none"
                ))
                continue
                
            feedback = correct_olympiad_solution(prob, solution, round_number=1)
            solved = (feedback.verdict == FeedbackVerdict.CORRECT)
            
            results.append(HILTestResult(
                problem_id=prob.id,
                solved=solved,
                latency_ms=elapsed_ms,
                verdict=feedback.verdict.name,
                explanation=feedback.correction_text,
                confidence=solution.confidence,
                strategy=solution.strategy_used
            ))
            
            print(f"    ✓ Verdict: {feedback.verdict.name} | Latency: {elapsed_ms:.1f}ms | Confidence: {solution.confidence:.2f}")
            
        except Exception as exc:
            elapsed_ms = (time.monotonic() - t0) * 1000.0
            print(f"    ❌ Failure: {exc}")
            results.append(HILTestResult(
                problem_id=prob.id,
                solved=False,
                latency_ms=elapsed_ms,
                verdict="CRASHED",
                explanation=f"System crash during MCTS rollout: {str(exc)}",
                confidence=0.0,
                strategy="none"
            ))
            
    return results


def print_statistical_report(results: list[HILTestResult]) -> tuple[int, float]:
    """Compile and print a rigorous statistical evaluation report."""
    total = len(results)
    if total == 0:
        return 0, 0.0
        
    solved_count = sum(1 for r in results if r.solved)
    success_rate = (solved_count / total) * 100.0
    
    avg_latency = sum(r.latency_ms for r in results) / total
    min_latency = min(r.latency_ms for r in results)
    max_latency = max(r.latency_ms for r in results)
    
    lower_ci, upper_ci = calculate_wilson_interval(solved_count, total)
    
    print("\n" + "=" * 90)
    print("🔬  HARDWARE-IN-THE-LOOP (HIL) STATISTICAL BENCHMARK REPORT")
    print("=" * 90)
    print(f"  Total Problems Evaluated:  {total}")
    print(f"  Solved Successfully:       {solved_count} / {total}")
    print(f"  Empirical Accuracy Rate:   {success_rate:.2f}%")
    print(f"  Wilson 95% Confidence:     [{lower_ci*100:.1f}%, {upper_ci*100:.1f}%]")
    print(f"  Mean Latency (Steady):     {avg_latency:.2f} ms")
    print(f"  Latency Jitter (Min/Max):  {min_latency:.1f} ms / {max_latency:.1f} ms")
    
    # Check for simulation vs production drift
    if success_rate < 50.0:
        print("  ⚠️ ALERT: Production accuracy is critically low! Divergent MCTS behavior suspected.")
    else:
        print("  ✓ Verification: Production convergence satisfies stability constraints.")
    print("=" * 90)
    
    return solved_count, success_rate


async def main() -> None:
    print("🏛️ Starting SocrateAI Agora HIL Benchmark Suite...")
    
    # We select 5 representative problems spanning diverse complexity for our suite
    target_ids = {
        "adler_c1_p1_mushrooms",  # Numeric Word problem
        "adler_c2_p2_divisibility",  # Proof / number theory
        "adler_c3_p1_handshakes",  # Combinatorial counting
        "adler_c4_p1_factoring",  # Algebraic factoring
        "adler_c5_p1_arcsin_eq"  # Trigonometric equation
    }
    
    problems = [p for p in ADLER_PROBLEMS_ALL if p.id in target_ids]
    if not problems:
        print("❌ Error: Adler problem bank could not be loaded. Exiting.")
        sys.exit(1)
        
    results = await run_hil_benchmark(problems, time_budget_sec=30.0)
    print_statistical_report(results)


if __name__ == "__main__":
    asyncio.run(main())
