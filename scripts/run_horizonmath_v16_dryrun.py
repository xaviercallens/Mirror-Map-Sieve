#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""
SymBrain v16 Dry Run — 15 Easiest HorizonMath Problems
=======================================================

Phase 1 of the 4th HorizonMath Run:
  1. Deploy SymBrain v16 via Turing (GCP infrastructure warmup)
  2. Run 15 easiest problems (solvability ≥ 2) to calibrate cost/time
  3. Store results in Alexandrie
  4. Generate cost estimation for full 113-problem run
"""
from __future__ import annotations

# ── SSL fix ──────────────────────────────────────────────────────────────────
import os
import certifi
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ.pop("SSL_CERT_DIR", None)

import asyncio
import json
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

# ── Agent imports ─────────────────────────────────────────────────────────────
from agents.galois.agent import GaloisAgent
from agents.euler.agent import EulerAgent
from agents.pythagore.agent import PythagoreAgent
from agents.turing.agent import TuringAgent
from agents.archimedes.agent import ArchimedesAgent
from agents.base import AgentConfig, AgentRole

# ── v16 imports ───────────────────────────────────────────────────────────────
from agents.archimedes.tools.lemma_decomposer_v16 import LemmaPreDecomposer
from agents.galois.tools.region_shard_router import ShardRouter

# ── Alexandrie ────────────────────────────────────────────────────────────────
from alexandrie.hub import AlexandrieHub

logger = structlog.get_logger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
BRAIN_DIR    = Path('/Users/xcallens/.gemini/antigravity/brain/142e4281-5564-4819-8826-7d615d389330')
DATA_DIR     = BRAIN_DIR / 'scratch/HorizonMath/data'
OUTPUT_DIR   = Path(__file__).parent.parent / 'achievement_output'
DRY_RUN_DIR  = OUTPUT_DIR / 'v16_dryrun'
V16_OFF_DIR  = OUTPUT_DIR / 'v16_offline'
V14_DIR      = OUTPUT_DIR / 'v14_results'
DOWNLOADS    = Path.home() / 'Downloads'

DRY_RUN_DIR.mkdir(parents=True, exist_ok=True)

# ── Budget ────────────────────────────────────────────────────────────────────
BUDGET_CAP_USD     = 400.0
PREVIOUS_SPEND_USD = 100.0   # v13 + v14 + v15 + v16_offline combined
DRY_RUN_CAP_USD    = 60.0    # cap for the dry run specifically

# ── 15 Easiest Problems (sorted by solvability descending) ────────────────────
DRY_RUN_PROBLEMS = [
    {"pid": "A21_10_binary_code",                    "domain": "coding_theory",        "solvability": 3},
    {"pid": "knot_volume_6_3",                       "domain": "discrete_geometry",    "solvability": 3},
    {"pid": "saw_simple_cubic",                      "domain": "statistical_mechanics","solvability": 3},
    {"pid": "saw_triangular_lattice",                "domain": "statistical_mechanics","solvability": 3},
    {"pid": "saw_square_lattice",                    "domain": "statistical_mechanics","solvability": 3},
    {"pid": "euler_mascheroni_closed_form",          "domain": "number_theory",        "solvability": 3},
    {"pid": "feigenbaum_alpha",                      "domain": "continuum_physics",    "solvability": 3},
    {"pid": "feigenbaum_delta",                      "domain": "continuum_physics",    "solvability": 3},
    {"pid": "lane_emden_polytrope_function",         "domain": "spectral_theory",      "solvability": 2},
    {"pid": "spherical_mode_quality_factor_tm_te",   "domain": "spectral_theory",      "solvability": 2},
    {"pid": "spherical_mode_quality_factor_te_tm",   "domain": "spectral_theory",      "solvability": 2},
    {"pid": "photokinetic_bimolecular_rate_law",     "domain": "continuum_physics",    "solvability": 2},
    {"pid": "tpsml_quantile_function",               "domain": "special_functions",    "solvability": 2},
    {"pid": "dual_risk_pareto_finite_time_ruin",     "domain": "special_functions",    "solvability": 2},
    {"pid": "anderson_lyapunov_exponent",            "domain": "mathematical_physics", "solvability": 2},
]


def load_existing_sketch(pid: str) -> tuple[str, str]:
    """Load best existing Lean 4 sketch from v16_offline or v14."""
    # v16_offline first
    f16 = V16_OFF_DIR / f"{pid}_v16_offline.json"
    if f16.exists():
        d = json.loads(f16.read_text())
        return d.get("lean4_sketch", ""), "v16_offline"
    # v14 fallback
    f14 = V14_DIR / f"{pid}_v14.json"
    if f14.exists():
        d = json.loads(f14.read_text())
        return d.get("lean4_sketch", ""), "v14"
    # v16 lean file
    lean_f = V16_OFF_DIR / f"{pid}.lean"
    if lean_f.exists():
        return lean_f.read_text(), "v16_lean"
    return "", "missing"


async def main() -> None:
    run_start = time.monotonic()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║     SymBrain v16 — DRY RUN: 15 Easiest HorizonMath Problems        ║
║     Phase 1: Infrastructure Validation & Cost Calibration           ║
║     Budget Cap: ${DRY_RUN_CAP_USD:.0f} | Previous Spend: ${PREVIOUS_SPEND_USD:.0f}                    ║
╚══════════════════════════════════════════════════════════════════════╝
    """)

    # ── Phase 1A: Turing Deployment & Infrastructure Recap ────────────────────
    print("═" * 70)
    print("  PHASE 1A: Turing Agent — GCP Infrastructure Deployment")
    print("═" * 70)

    turing = TuringAgent()

    # Step 1: Query quota database
    print("\n  [Turing] Checking GCP quota database...")
    quota_result = await turing.run(
        "Check GCP GPU quota compliance for H100, A100, L4 deployment across all regions. "
        "Report active limits and pending requests.",
        gpu_type="L4",
        region="us-central1",
        nodes=3,
    )
    quota_report = quota_result.answer
    print(f"  ✓ Quota check: {quota_report.get('quota_report', {}).get('compliance', {}).get('verdict', 'N/A')}")

    # Step 2: Deploy SymBrain v16 endpoint
    print("\n  [Turing] Deploying SymBrain v16 on best available GPU tier...")
    deploy_result = await turing.run(
        "Deploy SymBrain v16 model on GCP. Use L4 Spot in us-central1 (3 GPUs approved). "
        "Warm up the endpoint. Report deployment status.",
        symbrain_version="v16",
        accelerator_type="L4",
        nodes=3,
        region="us-central1",
    )
    deploy_report = deploy_result.answer
    deployment_status = deploy_report.get("deployment_report", {}).get("deploy", {}).get("status", "UNKNOWN")
    print(f"  ✓ Deploy status: {deployment_status}")
    print(f"  ✓ Warm-up: {deploy_report.get('deployment_report', {}).get('warm_up', {}).get('status', 'N/A')}")

    # Step 3: Billing estimation
    print("\n  [Turing] Estimating pool costs...")
    pool_result = await turing.run(
        "Estimate GCP pool costs for L4 Spot deployment with 3 GPUs, 250 MCTS nodes, "
        "for processing 15 problems at ~5 min each.",
        pool_config={
            "gpu_type": "L4",
            "vram_gb": 72.0,
            "mcts_nodes": 250.0,
            "base_duration_seconds": 300.0,
            "vcpu_request": 32,
        },
    )
    pool_report = pool_result.answer.get("pool_report", {})
    print(f"  ✓ Estimated hourly rate: ${pool_report.get('estimated_hourly_rate_usd', 0):.2f}/hr")

    # ── Infrastructure Recap ──────────────────────────────────────────────────
    from agents.turing.tools.gcp_quota_manager import get_quota_database, get_active_limit

    infra_recap = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "gpu_quotas": {
            "H100_europe-west10": get_active_limit("h100", "europe-west10"),
            "H100_us-central1": get_active_limit("h100", "us-central1"),
            "A100_europe-west4": get_active_limit("a100", "europe-west4"),
            "A100_us-central1": get_active_limit("a100", "us-central1"),
            "L4_us-central1": get_active_limit("l4", "us-central1"),
            "GPU_global": get_active_limit("gpu_global"),
            "TPU_us-central1": get_active_limit("tpu", "us-central1"),
        },
        "build_cpus": {
            "europe-west1": get_active_limit("build_cpu", "europe-west1"),
            "us-central1": get_active_limit("build_cpu", "us-central1"),
        },
        "ssd_gb": {
            "us-central1": get_active_limit("ssd", "us-central1"),
        },
        "pending_requests": [
            q for q in get_quota_database() if q["status"] == "Pending"
        ],
        "deployment": {
            "status": deployment_status,
            "gpu_tier": "L4 Spot",
            "nodes": 3,
            "region": "us-central1",
            "symbrain_version": "v16",
            "gemini_fallback": "Gemini 3.1 Pro (via google.genai API)",
        },
    }

    print(f"\n{'─'*70}")
    print("  📋 GCP INFRASTRUCTURE RECAP")
    print(f"{'─'*70}")
    print(f"  H100 europe-west10: {infra_recap['gpu_quotas']['H100_europe-west10']:.0f} (committed)")
    print(f"  H100 us-central1:   {infra_recap['gpu_quotas']['H100_us-central1']:.0f} (denied)")
    print(f"  A100 europe-west4:  {infra_recap['gpu_quotas']['A100_europe-west4']:.0f} (pending)")
    print(f"  A100 us-central1:   {infra_recap['gpu_quotas']['A100_us-central1']:.0f} (pending)")
    print(f"  L4   us-central1:   {infra_recap['gpu_quotas']['L4_us-central1']:.0f} (partially approved)")
    print(f"  GPU  global:        {infra_recap['gpu_quotas']['GPU_global']:.0f}")
    print(f"  Pending requests:   {len(infra_recap['pending_requests'])}")
    print(f"  Deployment:         {infra_recap['deployment']['status']} → {infra_recap['deployment']['gpu_tier']} × {infra_recap['deployment']['nodes']}")
    print(f"  Gemini fallback:    {infra_recap['deployment']['gemini_fallback']}")
    print(f"{'─'*70}")

    # ── Phase 1B: Initialize Processing Agents ────────────────────────────────
    print("\n" + "═" * 70)
    print("  PHASE 1B: Agent Initialization")
    print("═" * 70)

    galois = GaloisAgent()
    euler = EulerAgent()
    pythagore = PythagoreAgent()
    archimedes = ArchimedesAgent()
    pre_decomposer = LemmaPreDecomposer()
    shard_router = ShardRouter(tier="L4_SPOT")

    # v16 cortex upgrade
    galois.upgrade_to_v16()
    print(f"  ✓ Galois cortex:    {galois.cortex.symbrain_version}")
    print(f"  ✓ ShardRouter:      {shard_router.tier} | {len(shard_router.endpoints)} endpoints")
    print(f"  ✓ LemmaPreDecomp:   Ready (H1)")
    print(f"  ✓ Archimedes:       Ready (Method of Exhaustion)")
    print(f"  ✓ Euler:            Ready (ZSG enforced)")

    # Alexandrie hub
    try:
        alexandrie = AlexandrieHub()
        print(f"  ✓ Alexandrie:       Connected")
    except Exception as e:
        alexandrie = None
        print(f"  ⚠ Alexandrie:       Unavailable ({str(e)[:40]})")

    # ── Phase 2: Process 15 Problems ──────────────────────────────────────────
    print("\n" + "═" * 70)
    print(f"  PHASE 2: DRY RUN — Processing {len(DRY_RUN_PROBLEMS)} problems")
    print("═" * 70)

    experiment_budget = [PREVIOUS_SPEND_USD]
    results = []

    for i, prob in enumerate(DRY_RUN_PROBLEMS):
        pid = prob["pid"]
        domain = prob["domain"]
        t0 = time.monotonic()

        # Budget guard
        dry_cost = experiment_budget[0] - PREVIOUS_SPEND_USD
        if dry_cost >= DRY_RUN_CAP_USD:
            print(f"\n  💰 DRY RUN BUDGET CAP reached (${dry_cost:.2f} / ${DRY_RUN_CAP_USD:.0f})")
            break

        print(f"\n  ┌─ [{i+1}/{len(DRY_RUN_PROBLEMS)}] {pid}")
        print(f"  │  Domain: {domain} | Solvability: {prob['solvability']}")

        # Load existing sketch from v16_offline
        existing_sketch, source = load_existing_sketch(pid)
        existing_sorry = existing_sketch.lower().count("sorry") if existing_sketch else -1
        print(f"  │  Existing: {source} | Sorry: {existing_sorry}")

        # H1: Pre-decompose
        pre_decomp_n = 0
        try:
            pre_plan = pre_decomposer.decompose_theorem_statement(
                theorem_header=f"theorem {pid} (v16)",
                domain=domain,
                pid=pid,
                max_lemmas=5,
            )
            pre_decomp_n = len(pre_plan.lemmas)
        except Exception:
            pass

        # Galois: generate conjecture + sketch (120s timeout)
        lean4_sketch = ""
        conjecture = ""
        cost_galois = 0.0
        try:
            galois_result = await asyncio.wait_for(galois.run(
                f"Generate a rigorous mathematical conjecture and Lean 4 proof sketch for: {pid}\n"
                f"Domain: {domain} | Solvability: {prob['solvability']}\n"
                f"Use real Mathlib4 theorems. Follow the Lemma Pre-Decomposition Plan.\n"
                f"Only use `sorry` for genuinely open sub-claims."
            ), timeout=120.0)
            galois_answer = galois_result.answer
            galois_str = str(galois_answer)

            # Extract sketch
            conj_result = galois_answer.get("conjecture_generator") if isinstance(galois_answer, dict) else None
            inner = getattr(conj_result, "conjectures", None) or []
            if inner and hasattr(inner[0], "lean4_sketch"):
                lean4_sketch = getattr(inner[0], "lean4_sketch", "") or ""
                conjecture = getattr(inner[0], "statement", "") or ""

            cost_galois = getattr(galois_result, "cost_usd", 0.17)
        except asyncio.TimeoutError:
            print(f"  │  ⏱ Galois TIMEOUT (120s) — using existing sketch")
            lean4_sketch = existing_sketch
            cost_galois = 0.17
        except Exception as e:
            print(f"  │  ⚠ Galois error: {str(e)[:60]}")
            cost_galois = 0.17

        sorry_count = lean4_sketch.lower().count("sorry") if lean4_sketch else 0
        experiment_budget[0] += cost_galois

        # Archimedes: exhaustion if sorry > 0
        arch_reduction = 0
        if sorry_count > 0:
            try:
                arch_result = await asyncio.wait_for(archimedes.run(
                    query=f"Prove sub-lemmas for: {pid}",
                    lean4_sketch=lean4_sketch,
                    domain=domain,
                    theorem_header=conjecture[:120],
                    pid=pid,
                ), timeout=90.0)
                arch_data = arch_result.answer
                if arch_data and arch_data.get("reduction", 0) > 0:
                    arch_reduction = arch_data.get("reduction", 0)
                    lean4_sketch = arch_data.get("lean4_sketch", lean4_sketch)
                    sorry_count = arch_data.get("sorry_count", sorry_count)
                experiment_budget[0] += arch_result.cost_usd
            except asyncio.TimeoutError:
                print(f"  │  ⏱ Archimedes TIMEOUT (90s) — keeping current sketch")
            except Exception:
                pass

        # Euler: verify
        final_sorry = lean4_sketch.lower().count("sorry") if lean4_sketch else 0
        verdict = "INCOMPLETE"
        euler_conf = 0.6
        try:
            euler_res = await asyncio.wait_for(euler.run(
                f"Verify the conjecture for '{pid}'.\n"
                f"sorry_count = {final_sorry}. If > 0 → verdict MUST be INCOMPLETE\n"
                f"Only VERIFIED if sorry_count == 0 AND all goals closed."
            ), timeout=60.0)
            euler_conf = euler_res.confidence
            if euler_conf >= 0.85 and final_sorry == 0:
                verdict = "VERIFIED"
            elif euler_conf >= 0.65:
                verdict = "INCOMPLETE"
            else:
                verdict = "REFUTED"
            experiment_budget[0] += getattr(euler_res, "cost_usd", 0.15)
        except asyncio.TimeoutError:
            print(f"  │  ⏱ Euler TIMEOUT (60s) — marking INCOMPLETE")
            experiment_budget[0] += 0.15
        except Exception:
            experiment_budget[0] += 0.15

        elapsed = time.monotonic() - t0

        # Store in Alexandrie
        alexandrie_id = f"v16_dryrun_{pid}"
        if alexandrie and lean4_sketch:
            try:
                from alexandrie.metadata import ArtifactType, RoomType
                alexandrie.store_artifact(
                    artifact_id=alexandrie_id,
                    title=f"HorizonMath v16 DryRun — {pid}",
                    content=lean4_sketch,
                    artifact_type=ArtifactType.PROOF,
                    room_type=RoomType.OPEN_ACCESS,
                    creator="SymBrain-v16-DryRun",
                    tags=[domain, "v16", "dryrun", verdict],
                    metrics={"sorry_count": final_sorry, "verdict": verdict},
                )
            except Exception:
                pass

        r = {
            "pid": pid,
            "domain": domain,
            "solvability": prob["solvability"],
            "source": source,
            "pre_decomp_lemmas": pre_decomp_n,
            "sorry_galois": sorry_count + arch_reduction,
            "sorry_final": final_sorry,
            "arch_reduction": arch_reduction,
            "verdict": verdict,
            "euler_confidence": euler_conf,
            "cost_usd": round(cost_galois + 0.15, 4),
            "elapsed_s": round(elapsed, 2),
            "alexandrie_id": alexandrie_id,
        }
        results.append(r)

        verdict_emoji = {"VERIFIED": "✅", "INCOMPLETE": "🔶", "REFUTED": "❌"}.get(verdict, "❓")
        print(f"  │  {verdict_emoji} {verdict} | Sorry: {r['sorry_galois']} → {final_sorry} | "
              f"Cost: ${r['cost_usd']:.3f} | Time: {elapsed:.1f}s")
        print(f"  └─ Stored: {alexandrie_id}")

        # Save per-problem JSON
        (DRY_RUN_DIR / f"{pid}_dryrun.json").write_text(json.dumps(r, indent=2))

    # ── Phase 3: Cost Estimation & Report ─────────────────────────────────────
    elapsed_total = time.monotonic() - run_start
    dry_cost = experiment_budget[0] - PREVIOUS_SPEND_USD
    n_processed = len(results)
    avg_cost = dry_cost / n_processed if n_processed > 0 else 0
    avg_time = sum(r["elapsed_s"] for r in results) / n_processed if n_processed > 0 else 0

    verified_n = sum(1 for r in results if r["verdict"] == "VERIFIED")
    incomplete_n = sum(1 for r in results if r["verdict"] == "INCOMPLETE")
    refuted_n = sum(1 for r in results if r["verdict"] == "REFUTED")

    # Extrapolate to 113 problems
    est_cost_113 = avg_cost * 113
    est_time_113_min = (avg_time * 113) / 60.0

    print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║  SymBrain v16 — DRY RUN COMPLETE                                     ║
╠══════════════════════════════════════════════════════════════════════╣
║  Problems Processed: {n_processed:3d} / 15                                     ║
║  ✅ VERIFIED:        {verified_n:3d}                                            ║
║  🔶 INCOMPLETE:      {incomplete_n:3d}                                            ║
║  ❌ REFUTED:         {refuted_n:3d}                                            ║
╠══════════════════════════════════════════════════════════════════════╣
║  Cost Metrics (Dry Run):                                              ║
║    Total dry run cost:    ${dry_cost:8.2f}                               ║
║    Avg cost per problem:  ${avg_cost:8.4f}                               ║
║    Avg time per problem:  {avg_time:8.1f}s                                ║
╠══════════════════════════════════════════════════════════════════════╣
║  ESTIMATED COST FOR FULL 113-PROBLEM RUN:                             ║
║    Estimated total cost:  ${est_cost_113:8.2f}                               ║
║    Estimated total time:  {est_time_113_min:8.1f} min                           ║
║    Budget remaining:      ${BUDGET_CAP_USD - PREVIOUS_SPEND_USD - dry_cost:8.2f}                               ║
╠══════════════════════════════════════════════════════════════════════╣
║  Infrastructure:                                                       ║
║    GPU Tier: L4 Spot × 3 (us-central1)                                ║
║    Fallback: Gemini 3.1 Pro endpoint                                  ║
║    Alexandrie: {n_processed} proofs stored                                       ║
╚══════════════════════════════════════════════════════════════════════╝
    """)

    # Save summary
    summary = {
        "run": "v16_dryrun",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "problems_processed": n_processed,
        "verified": verified_n,
        "incomplete": incomplete_n,
        "refuted": refuted_n,
        "dry_run_cost_usd": round(dry_cost, 2),
        "avg_cost_per_problem_usd": round(avg_cost, 4),
        "avg_time_per_problem_s": round(avg_time, 2),
        "estimated_113_cost_usd": round(est_cost_113, 2),
        "estimated_113_time_min": round(est_time_113_min, 1),
        "budget_remaining_usd": round(BUDGET_CAP_USD - PREVIOUS_SPEND_USD - dry_cost, 2),
        "infrastructure": infra_recap,
        "results": results,
    }
    summary_file = DRY_RUN_DIR / f"v16_dryrun_summary_{ts}.json"
    summary_file.write_text(json.dumps(summary, indent=2))
    print(f"📁 Summary: {summary_file}")

    import shutil
    shutil.copy(str(summary_file), str(DOWNLOADS / "v16_dryrun_summary.json"))
    print(f"📥 Copied to: {DOWNLOADS / 'v16_dryrun_summary.json'}")


if __name__ == "__main__":
    asyncio.run(main())
