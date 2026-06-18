#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Lean 4 Compiler Stress-Testing Benchmark
----------------------------------------
Compares compilation times and resources of:
1. Raw kernel evaluation of combinatorial sums (using rfl/decide)
2. Algebraically shielded general proofs (using ring)
"""

import os
import sys
import time
import subprocess
import json
from pathlib import Path

# Ensure paths are correct
LEAN_WORKSPACE = Path("/Users/xcallens/xdev/SocrateAI-Scientific-Agora/SocrateAI-Scientific-AlienMathematics-Foundation")
DATA_DIR = Path("/Users/xcallens/xdev/SocrateAI-Scientific-Agora/alexandrie_data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

def measure_compilation(lean_code: str, filename: str) -> dict:
    filepath = LEAN_WORKSPACE / filename
    with open(filepath, "w") as f:
        f.write(lean_code)
        
    start_time = time.time()
    # Run Lean compiler on the file
    proc = subprocess.run(
        ["/Users/xcallens/.elan/bin/lake", "env", "lean", filename],
        capture_output=True, text=True, cwd=str(LEAN_WORKSPACE)
    )
    elapsed = time.time() - start_time
    
    # Clean up
    if filepath.exists():
        filepath.unlink()
        
    return {
        "success": proc.returncode == 0,
        "elapsed_s": elapsed,
        "stdout": proc.stdout,
        "stderr": proc.stderr
    }

def run_stress_test():
    print("==========================================================")
    print(" 🪐 RUNNING LEAN 4 COMPILER STRESS-TEST BENCHMARK ")
    print("==========================================================\n")
    
    # 1. Raw Evaluation (N = 10, 15, 20)
    raw_code = """import Mathlib.Data.Nat.Choose.Basic
import Mathlib.Tactic

open Nat Finset BigOperators

-- We evaluate the sum: sum_{k=0}^n (k^4 - 2k^2 + 1) * choose n k
-- at concrete n values using kernel evaluation (decide).

theorem raw_inst_n5 :
  (∑ k ∈ range 6, ((k : ℤ)^4 - 2*(k : ℤ)^2 + 1) * (choose 5 k : ℤ)) = 2432 := by decide

theorem raw_inst_n10 :
  (∑ k ∈ range 11, ((k : ℤ)^4 - 2*(k : ℤ)^2 + 1) * (choose 10 k : ℤ)) = 986624 := by decide

theorem raw_inst_n15 :
  (∑ k ∈ range 16, ((k : ℤ)^4 - 2*(k : ℤ)^2 + 1) * (choose 15 k : ℤ)) = 142573568 := by decide
"""

    print("⚡ Compiling Raw Kernel Evaluations (decide)...")
    res_raw = measure_compilation(raw_code, "RawStressTest.lean")
    print(f"  Raw compilation: {res_raw['elapsed_s']:.2f} seconds (Success: {res_raw['success']})")
    if not res_raw['success']:
        print(f"  Error: {res_raw['stderr']}")

    # 2. Algebraically Shielded Proof (General n)
    shielded_code = """import Mathlib.Data.Real.Basic
import Mathlib.Tactic

namespace Agora.AlienMath

def S_shielded (n : ℚ) (y : ℚ) : ℚ := y * (n^4 + 6*n^3 - 5*n^2 - 10*n + 16)

theorem shielded_general (n : ℚ) (y : ℚ) :
    (-2*n^4 - 20*n^3 - 38*n^2 - 4*n - 16) * S_shielded n y +
    (n^4 + 6*n^3 - 5*n^2 - 10*n + 16) * S_shielded (n + 1) (y * 2) = 0 := by
  dsimp [S_shielded]
  ring

end Agora.AlienMath
"""

    print("⚡ Compiling Algebraically Shielded General Proof (ring)...")
    res_shielded = measure_compilation(shielded_code, "ShieldedStressTest.lean")
    print(f"  Shielded compilation: {res_shielded['elapsed_s']:.2f} seconds (Success: {res_shielded['success']})")
    if not res_shielded['success']:
        print(f"  Error: {res_shielded['stderr']}")

    # Save results to alexandrie_data
    results = {
        "timestamp": time.time(),
        "raw_eval": {
            "success": res_raw["success"],
            "time_s": res_raw["elapsed_s"],
            "theorems": ["n=5", "n=10", "n=15"]
        },
        "shielded_proof": {
            "success": res_shielded["success"],
            "time_s": res_shielded["elapsed_s"],
            "theorems": ["general_n"]
        },
        "ratio": res_raw["elapsed_s"] / res_shielded["elapsed_s"] if res_shielded["elapsed_s"] > 0 else 0
    }
    
    output_path = DATA_DIR / "lean_stress_test_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"\n🎉 Benchmark complete! Results saved to {output_path}")

if __name__ == "__main__":
    run_stress_test()
