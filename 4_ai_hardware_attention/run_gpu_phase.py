#!/usr/bin/env python3
"""
run_gpu_phase.py — single entrypoint for the CY-Sieve GPU phase (tests.md §4/§5/§6).

Runs, in order, and collects everything into one JSON + a human summary:

  §4  Triton kernel <-> CPU-reference parity   (pytest test_cy_sieve_triton.py)
  §5  QUALITY GATE — from-scratch training per positional scheme, val perplexity
      + length extrapolation                    (cy_sieve_quality_gate.py, l4 preset)
  §6  Performance — Triton kernel vs dense SDPA vs materialized-bias table; bias
      HBM bytes O(L) vs O(L^2)                  (cy_sieve_perf.py)

T6.3 honesty guard: the §6 speed numbers are reported in the SAME artifact as the
§5 verdict; if §5 is KILL/MARGINAL the summary says so next to every speed row.

Usage (on the GPU box, after `pip install -r requirements-gpu.txt`):
    python run_gpu_phase.py --output gpu_phase_results.json
    python run_gpu_phase.py --quick          # smaller §5/§6 for a fast check
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))


def _gpu_info():
    try:
        import torch
        if not torch.cuda.is_available():
            return {"cuda": False}
        p = torch.cuda.get_device_properties(0)
        return {"cuda": True, "name": p.name,
                "vram_gb": round(p.total_memory / 1e9, 1),
                "torch": torch.__version__, "cuda_version": torch.version.cuda}
    except Exception as e:
        return {"cuda": False, "error": str(e)}


def run_section4():
    """§4 — Triton<->reference parity via pytest. Returns (passed, detail)."""
    print("\n" + "=" * 74 + "\n  §4 — Triton kernel <-> CPU reference parity\n" + "=" * 74)
    # pytest is not on the DLVM image by default; install it on demand so a
    # missing-module error can't masquerade as a parity FAIL.
    try:
        import pytest  # noqa: F401
    except ImportError:
        print("  pytest not found — installing…")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pytest"],
                       capture_output=True, text=True)
    cmd = [sys.executable, "-m", "pytest", "-v",
           os.path.join(HERE, "test_cy_sieve_triton.py")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if "No module named pytest" in (r.stderr + r.stdout):
        return {"returncode": r.returncode, "passed": False,
                "status": "ERROR (pytest unavailable — parity not run)",
                "summary": "pytest could not be installed"}
    print(r.stdout[-3000:])
    if r.returncode != 0:
        print(r.stderr[-2000:])
    last = [l for l in r.stdout.splitlines() if "passed" in l or "skipped" in l
            or "failed" in l or "error" in l]
    summary = last[-1] if last else "(no pytest summary)"
    # All-skipped (no CUDA) is NOT a pass — the parity test never ran.
    ran = "passed" in summary and "0 passed" not in summary
    skipped_only = "skipped" in summary and "passed" not in summary
    status = "PASS" if (r.returncode == 0 and ran) else \
             "SKIPPED (no CUDA — parity not exercised)" if skipped_only else "FAIL"
    return {"returncode": r.returncode, "passed": r.returncode == 0 and ran,
            "status": status, "summary": summary}


def run_section5(quick):
    """§5 — quality gate (from-scratch training)."""
    print("\n" + "=" * 74 + "\n  §5 — QUALITY GATE (from-scratch training)\n" + "=" * 74)
    out = os.path.join(HERE, "cy_sieve_quality_results.json")
    cmd = [sys.executable, os.path.join(HERE, "cy_sieve_quality_gate.py"),
           "--preset", "smoke" if quick else "l4",
           "--tau_sweep", "20", "128", "512", "--output", out]
    r = subprocess.run(cmd, text=True)
    data = json.load(open(out)) if os.path.exists(out) else {"error": "no output"}
    return data


def run_section6(quick):
    """§6 — performance of the Triton kernel."""
    print("\n" + "=" * 74 + "\n  §6 — Performance (Triton kernel)\n" + "=" * 74)
    out = os.path.join(HERE, "cy_sieve_perf_results.json")
    seq_lens = ["1024", "2048", "4096"] if quick else \
               ["1024", "2048", "4096", "8192", "16384", "32768"]
    cmd = [sys.executable, os.path.join(HERE, "cy_sieve_perf.py"),
           "--seq_lens", *seq_lens, "--output", out]
    subprocess.run(cmd, text=True)
    return json.load(open(out)) if os.path.exists(out) else {"error": "no output"}


def main():
    ap = argparse.ArgumentParser(description="CY-Sieve GPU phase orchestrator")
    ap.add_argument("--output", default="gpu_phase_results.json")
    ap.add_argument("--quick", action="store_true",
                    help="smaller §5/§6 for a fast functional check")
    ap.add_argument("--skip_quality", action="store_true")
    args = ap.parse_args()

    t0 = time.perf_counter()
    gpu = _gpu_info()
    print("=" * 74)
    print("  CY-Sieve GPU PHASE — tests.md §4 / §5 / §6")
    print(f"  GPU: {gpu}")
    print("=" * 74)

    s4 = run_section4()
    s5 = {} if args.skip_quality else run_section5(args.quick)
    s6 = run_section6(args.quick)

    verdict = s5.get("verdict", {}) if isinstance(s5, dict) else {}
    quality_status = verdict.get("status", "N/A")

    report = {
        "gpu": gpu,
        "elapsed_seconds": round(time.perf_counter() - t0, 1),
        "section4_parity": s4,
        "section5_quality": s5,
        "section6_perf": s6,
        "headline": {
            "section4_parity": s4["status"],
            "section5_quality": quality_status,
            "section6_speed_honesty_note": (
                "Speed numbers below are valid as a contribution ONLY if §5 is "
                f"PASS. Current §5 verdict: {quality_status}. (tests.md T6.3)"),
        },
    }
    json.dump(report, open(args.output, "w"), indent=2)

    print("\n" + "=" * 74)
    print("  GPU PHASE COMPLETE")
    print(f"    §4 parity : {report['headline']['section4_parity']} "
          f"({s4['summary']})")
    print(f"    §5 quality: {quality_status} — {verdict.get('summary','')}")
    if isinstance(s6, dict) and s6.get("rows"):
        r0 = s6["rows"][-1]
        print(f"    §6 perf   : L={r0['seq_len']} cy_sieve={r0['cy_sieve_ms']}ms "
              f"dense={r0['sdpa_dense_ms']}ms  bias-HBM reduction "
              f"{r0.get('bias_hbm_reduction_x')}x")
    print(f"    -> {args.output}  ({report['elapsed_seconds']}s)")
    print("=" * 74)
    return report


if __name__ == "__main__":
    main()
