#!/usr/bin/env python3
"""
run_all_tests.py — Master test runner for S₂₀ verification suite.

Runs all 4 verification scripts and reports pass/fail status.
Designed to run inside a GCP Cloud Run Job container.
"""
import subprocess
import sys
import time
import os

TESTS = [
    ("compute_s20.py", "Sequence Values", ["20"]),
    ("verify_recurrence.py", "Order-5 Recurrence", ["20"]),
    ("verify_hypergeometric.py", "₅F₄ Identity", ["20"]),
    ("verify_mirror_map.py", "Mirror Map Integrality", ["16"]),
]

def main():
    print("=" * 70)
    print("  S₂₀ WEIGHT-5 APÉRY-LIKE VERIFICATION SUITE")
    print("  SocrateAI Scientific Agora — GCP Cloud Run")
    print("=" * 70)
    print(f"\n  Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print(f"  Python:    {sys.version}")
    print()
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    results = []
    
    for script, name, args in TESTS:
        print(f"\n{'─' * 70}")
        print(f"  RUNNING: {name} ({script})")
        print(f"{'─' * 70}\n")
        
        t0 = time.time()
        try:
            result = subprocess.run(
                [sys.executable, os.path.join(script_dir, script)] + args,
                capture_output=False,
                text=True,
                timeout=300,
            )
            elapsed = time.time() - t0
            passed = result.returncode == 0
            results.append((name, passed, elapsed))
        except subprocess.TimeoutExpired:
            elapsed = time.time() - t0
            results.append((name, False, elapsed))
            print(f"  ❌ TIMEOUT after {elapsed:.1f}s")
        except Exception as e:
            elapsed = time.time() - t0
            results.append((name, False, elapsed))
            print(f"  ❌ ERROR: {e}")
    
    # Final summary
    print(f"\n{'=' * 70}")
    print("  FINAL SUMMARY")
    print(f"{'=' * 70}\n")
    
    all_pass = True
    for name, passed, elapsed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {name:30s}  ({elapsed:.1f}s)")
        if not passed:
            all_pass = False
    
    print()
    if all_pass:
        print("  ✅✅✅ ALL TESTS PASSED ✅✅✅")
    else:
        print("  ❌❌❌ SOME TESTS FAILED ❌❌❌")
    
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
