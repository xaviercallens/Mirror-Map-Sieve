#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Production Smoke Test Gate.

Validates the Galois solver on 10 random math problems of moderate complexity,
requiring a 7/10 success rate to verify solver integrity and prevent regressive drift.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from olympiad.adler_problem_bank import ADLER_PROBLEMS_ALL
from agents.galois.tools.olympiad_solver import solve_olympiad_problem
from agents.euler.tools.olympiad_corrector import correct_olympiad_solution
from agents.galois.olympiad.rlfc_engine import FeedbackVerdict


def run_smoke_test() -> bool:
    print("🚀 Running Agora Production Smoke Test Gate (10-Problem Check)...")
    
    # We select 10 diverse moderate problems across all chapters
    smoke_ids = [
        "adler_c1_p1_mushrooms",
        "adler_c1_p2_age",
        "adler_c1_p3_work",
        "adler_c2_p2_divisibility",
        "adler_c3_p1_handshakes",
        "adler_c3_p2_inclusion_exclusion",
        "adler_c4_p1_factoring",
        "adler_c4_p3_quadratic_ineq",
        "adler_c5_p1_arcsin_eq",
        "adler_c5_p2_trig_identity"
    ]
    
    problems = [p for p in ADLER_PROBLEMS_ALL if p.id in smoke_ids]
    if len(problems) < 10:
        print(f"❌ Error: Found only {len(problems)}/10 target smoke problems in bank!")
        return False
        
    correct_count = 0
    
    for idx, prob in enumerate(problems, 1):
        print(f"  [{idx:02d}/10] Testing: {prob.id} ... ", end="")
        try:
            solution = solve_olympiad_problem(prob)
            feedback = correct_olympiad_solution(prob, solution)
            if feedback.verdict == FeedbackVerdict.CORRECT:
                correct_count += 1
                print("✓ PASS")
            else:
                print(f"✗ FAIL ({feedback.verdict.name}: {feedback.correction_text[:60]}...)")
        except Exception as exc:
            print(f"💥 CRASH ({exc})")
            
    success_rate = (correct_count / 10.0) * 100.0
    print("\n" + "=" * 60)
    print(f"  SMOKE TEST VERDICT: {correct_count} / 10 Correct ({success_rate:.1f}%)")
    print("=" * 60)
    
    if correct_count >= 7:
        print("  ✓ SUCCESS: Core solver and corrector are functionally stable!")
        return True
    else:
        print("  ❌ FAILURE: Accuracy fell below the 70% (7/10) deployment gate limit!")
        return False


if __name__ == "__main__":
    success = run_smoke_test()
    sys.exit(0 if success else 1)
