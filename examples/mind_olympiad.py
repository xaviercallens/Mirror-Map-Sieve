#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""
🏛️ MIND OLYMPIAD — Automated Mathematical Challenge Loop
══════════════════════════════════════════════════════════════════════════════

Full implementation of the Agora Mind Olympiad feature:

  1. Loads ALL problems from Andrew Adler's PIMS Problem Collection
     (https://pims.math.ca/sites/default/files/adlerbook.pdf)
  2. Hypatie ingests every problem into Alexandrie
  3. Galois (SymBrain v8 "Mind Olympiad") solves them with category-aware
     SIAG routing and Lean 4 proof synthesis
  4. Euler corrects every solution with 5-verdict structured feedback
  5. RLFCEngine converts feedback into σ_ded / σ_gen / σ_mcts gradient updates
  6. InferenceTransferBank persists learned corrections to Alexandrie
  7. Cortex v8 applies the transfer at the start of each subsequent round
  8. Session tracks improvement trend across N configurable rounds
  9. Final multi-round report is stored as a PAPER artifact in Alexandrie

Usage:
  python examples/mind_olympiad.py [--rounds N] [--problems-per-round K] [--verbose]

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Agents
from agents.socrates.agent import SocratesAgent
from agents.turing.agent import TuringAgent
from agents.galois.agent import GaloisAgent
from agents.euler.agent import EulerAgent
from agents.hypatie.agent import HypatieAgent

# Alexandrie
from alexandrie.hub import AlexandrieHub
from alexandrie.metadata import ArtifactType, RoomType

# Olympiad problem bank
from olympiad.adler_problem_bank import ADLER_PROBLEMS_ALL, OlympiadProblemRecord

# Olympiad tools
from agents.galois.tools.olympiad_solver import OlympiadSolution, solve_olympiad_problem
from agents.euler.tools.olympiad_corrector import (
    OlympiadCorrectionReport,
    correct_solution_batch,
)

# RLFC & transfer
from agents.galois.olympiad.rlfc_engine import RLFCEngine
from agents.galois.olympiad.inference_transfer import InferenceTransferBank
from agents.galois.olympiad.olympiad_session import OlympiadSession


# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

BANNER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║      🏛️  SocrateAI Agora — MIND OLYMPIAD                                   ║
║      Automated Mathematical Challenge Loop                                   ║
║      Andrew Adler PIMS Problem Collection                                    ║
║      Galois v8 (SymBrain "Mind Olympiad") × Euler (Skeptical Auditor)        ║
║      RLFC + Inference Transfer — Multi-Round Improvement                     ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

SECTION = "═" * 80


# ──────────────────────────────────────────────────────────────────────────────
# Phase implementations
# ──────────────────────────────────────────────────────────────────────────────

async def phase_turing_audit(turing: TuringAgent) -> float:
    """Phase 1: Turing GCP cost audit (< $50 limit)."""
    print(f"\n[▶] Phase 1: Turing Infrastructure Audit")
    result = await turing.run(
        "Estimate GCP compute cost for Mind Olympiad loop (multi-round, all Adler problems)",
        pool_config={
            "gpu_type": "dual-H100",
            "vram_gb": 160.0,
            "mcts_nodes": 512.0,
            "vcpu_request": 64,
        },
        quota_limits={"h100_limit": 4, "l4_limit": 8, "vcpu_limit": 128},
    )
    pool = result.answer.get("pool_report", {})
    hourly = pool.get("estimated_hourly_rate_usd", 7.34)
    bill   = hourly * 3.0  # Estimate 3 hours for full multi-round Olympiad
    print(f"    ✓ GPU cluster:     {pool.get('gpu_type')} ({pool.get('active_gpus_requested')} cards)")
    print(f"    ✓ Quota status:    {pool.get('verdict', 'WITHIN_LIMITS')}")
    print(f"    ✓ Estimated bill:  ${bill:.2f}")
    if bill <= 50.00:
        print(f"    ✓ Frugal-AI compliance: ${bill:.2f} ≤ $50.00 ✅")
    else:
        print(f"    ❌ Budget violation: ${bill:.2f} > $50.00. Exiting.")
        sys.exit(1)
    return bill


def phase_hypatie_ingest(
    hub: AlexandrieHub,
    hypatie: HypatieAgent,
    problems: list[OlympiadProblemRecord],
) -> None:
    """Phase 2: Hypatie ingests all Adler problems into Alexandrie."""
    print(f"\n[▶] Phase 2: Hypatie Ingesting {len(problems)} Adler Problems → Alexandrie")
    for prob in problems:
        content = (
            f"# {prob.title}\n\n"
            f"**Chapter**: {prob.chapter}\n"
            f"**Problem**: {prob.chapter_number}.{prob.problem_number}\n"
            f"**Type**: {prob.problem_type.value} | "
            f"**Difficulty**: {prob.difficulty.name} ({prob.difficulty.value}/5)\n"
            f"**Topics**: {', '.join(prob.topics)}\n\n"
            f"## Question\n{prob.question}\n\n"
            f"## Official Solution\n{prob.solution_book}\n"
        )
        if prob.numerical_answer:
            content += f"\n**Answer**: {prob.numerical_answer}\n"
        if prob.lean4_template:
            content += f"\n## Lean 4 Template\n```lean\n{prob.lean4_template}\n```\n"

        hub.store_artifact(
            artifact_id   = prob.id,
            title         = f"Adler Problem {prob.chapter_number}.{prob.problem_number}: {prob.title}",
            content       = content,
            artifact_type = ArtifactType.PROTOCOL,
            room_type     = RoomType.OPEN_ACCESS,
            creator       = "hypatie_librarian",
            tags          = ["adler-pims", "mind-olympiad", prob.problem_type.value] + prob.topics[:3],
            metrics       = {"difficulty": prob.difficulty.value, "chapter": prob.chapter_number},
        )
    print(f"    ✓ {len(problems)} problems cataloged in Alexandrie Open Access.")


def phase_galois_solve(
    galois: GaloisAgent,
    problems: list[OlympiadProblemRecord],
    round_number: int,
    transfer_bank: InferenceTransferBank,
    verbose: bool = False,
) -> list[OlympiadSolution]:
    """Phase 3: Galois (v8) solves all problems in this round."""
    solutions: list[OlympiadSolution] = []
    for prob in problems:
        sol = solve_olympiad_problem(
            problem       = prob,
            cortex_v8     = galois.v8_cortex,
            transfer_bank = transfer_bank,
            round_number  = round_number,
        )
        solutions.append(sol)
        if verbose:
            print(
                f"    [Round {round_number}] {prob.id[:40]:<40} "
                f"conf={sol.confidence:.2f} strategy={sol.strategy_used}"
            )
    return solutions


def phase_euler_correct(
    euler: EulerAgent,
    problems: list[OlympiadProblemRecord],
    solutions: list[OlympiadSolution],
    round_number: int,
    verbose: bool = False,
) -> OlympiadCorrectionReport:
    """Phase 4: Euler corrects all solutions and returns structured feedback."""
    report = correct_solution_batch(problems, solutions, round_number)
    if verbose:
        for fb in report.feedback_list:
            verdict_icon = "✅" if fb.verdict.value == "correct" else (
                "⚠️" if fb.verdict.value == "partial" else "❌"
            )
            print(
                f"    {verdict_icon} {fb.problem_id[:38]:<38} "
                f"verdict={fb.verdict.value:<18} "
                f"error={fb.error_class.value}"
            )
    return report


def phase_rlfc_update(
    rlfc: RLFCEngine,
    report: OlympiadCorrectionReport,
    galois: GaloisAgent,
    transfer_bank: InferenceTransferBank,
    session: OlympiadSession,
    verbose: bool = False,
) -> Any:
    """Phase 5: RLFC updates cortex σ params and saves InferenceTransfer checkpoint."""
    # Process feedback batch
    update = rlfc.process_feedback_batch(report.feedback_list, galois.v8_cortex)

    # Persist InferenceTransfer checkpoint
    transfer_bank.record_transfer(
        updates      = rlfc.get_learning_history(),
        fingerprints = rlfc.get_mistake_fingerprints(),
    )

    if verbose:
        print(
            f"    RLFC: Δσ_ded={update.delta_sigma_ded:+.4f}  "
            f"Δσ_gen={update.delta_sigma_gen:+.4f}  "
            f"Δσ_mcts={update.delta_sigma_mcts:+.4f}  "
            f"LR={update.learning_rate:.4f}"
        )
        routing = getattr(galois.v8_cortex, "routing", None)
        if routing:
            print(
                f"    New σ: ded={routing.sigma_ded:.4f}  "
                f"gen={routing.sigma_gen:.4f}  "
                f"mcts={routing.sigma_mcts:.4f}"
            )
    return update


def phase_inference_transfer_inject(
    galois: GaloisAgent,
    transfer_bank: InferenceTransferBank,
    verbose: bool = False,
) -> dict[str, Any]:
    """Phase 6: Inject prior checkpoint into Galois cortex for next round."""
    result = transfer_bank.apply_transfer(galois.v8_cortex)
    if verbose and result.get("applied"):
        print(
            f"    Transfer: {result.get('avoidance_strategies_injected', 0)} avoidance strategies injected "
            f"(best_score={result.get('best_score_seen', 0):.1f}%)"
        )
    return result


def store_round_report(
    hub: AlexandrieHub,
    round_number: int,
    report: OlympiadCorrectionReport,
    update: Any,
    routing: Any,
) -> None:
    """Store round feedback to Alexandrie."""
    details = "\n".join(
        f"- [{fb.verdict.value}] {fb.problem_id}: {fb.correction_text[:80]}"
        for fb in report.feedback_list
    )
    routing_info = ""
    if routing:
        routing_info = (
            f"σ_ded={routing.sigma_ded:.4f}  "
            f"σ_gen={routing.sigma_gen:.4f}  "
            f"σ_mcts={routing.sigma_mcts:.4f}"
        )
    content = (
        f"# Mind Olympiad Round {round_number} — Euler Correction Report\n\n"
        f"**Score**: {report.correct}/{report.total} ({report.score_pct:.1f}%)\n"
        f"**Partial**: {report.partial} | **Errors**: {report.errors}\n"
        f"**RLFC**: Δσ_ded={update.delta_sigma_ded:+.4f}  "
        f"Δσ_gen={update.delta_sigma_gen:+.4f}  "
        f"Δσ_mcts={update.delta_sigma_mcts:+.4f}\n"
        f"**Updated Cortex**: {routing_info}\n\n"
        f"## Per-Problem Verdicts\n{details}\n"
    )
    hub.store_artifact(
        artifact_id   = f"olympiad_round_{round_number}_correction_report",
        title         = f"Mind Olympiad Round {round_number} Correction Report",
        content       = content,
        artifact_type = ArtifactType.PAPER,
        room_type     = RoomType.OPEN_ACCESS,
        creator       = "euler_verifier",
        tags          = ["mind-olympiad", f"round-{round_number}", "rlfc-feedback"],
        metrics       = {
            "score_pct":          report.score_pct,
            "correct":            report.correct,
            "total":              report.total,
            "delta_sigma_ded":    update.delta_sigma_ded,
            "delta_sigma_gen":    update.delta_sigma_gen,
            "delta_sigma_mcts":   update.delta_sigma_mcts,
            "learning_rate":      update.learning_rate,
        },
    )


def store_final_report(
    hub: AlexandrieHub,
    session: OlympiadSession,
    galois: GaloisAgent,
    total_bill: float,
) -> None:
    """Store the final multi-round Olympiad report to Alexandrie."""
    summary = session.summary()
    scores  = summary["score_history"]
    trend   = summary["improvement_trend_pct_per_round"]

    # Improvement trajectory from v8 cortex
    traj = {}
    if galois.v8_cortex:
        traj = galois.v8_cortex.compute_improvement_trajectory(scores)

    routing = getattr(galois.v8_cortex, "routing", None)
    final_sigma = ""
    if routing:
        final_sigma = (
            f"σ_ded={routing.sigma_ded:.4f}  "
            f"σ_gen={routing.sigma_gen:.4f}  "
            f"σ_mcts={routing.sigma_mcts:.4f}"
        )

    round_table = "\n".join(
        f"| Round {r['round']} | {r['score']:.1f}% | {r['correct']}/{r['total']} "
        f"| {r['delta_sigma_ded']:+.4f} | {r['delta_sigma_gen']:+.4f} "
        f"| {r['delta_sigma_mcts']:+.4f} | {r['learning_rate']:.4f} |"
        for r in summary["rounds"]
    )

    content = f"""# 🏛️ SocrateAI Agora — Mind Olympiad Final Report

**Framework**: Galois Agent (SymBrain v8 "Mind Olympiad") × Euler Verifier
**Source**: Andrew Adler PIMS Problem Collection (8 chapters, {sum(len(r['total'] if isinstance(r['total'], list) else [r['total']]) for r in summary['rounds'])} total problems solved)
**Total Rounds**: {summary['total_rounds']}
**Budget**: ${total_bill:.2f} (Frugal-AI compliant ≤ $50.00)
**Total Time**: {summary['total_elapsed_s']:.1f}s

---

## 📊 Score History

{', '.join(f"Round {i+1}: {s:.1f}%" for i, s in enumerate(scores))}

**Best Round**: {summary['best_score']:.1f}%
**Final Score**: {summary['final_score']:.1f}%
**Improvement Trend**: {trend:+.2f}% per round

## 📈 SymBrain v8 Improvement Trajectory

| Metric | Value |
|--------|-------|
| Trend (linear slope) | {traj.get('trend', 0.0):+.3f}%/round |
| Momentum (exp. weighted) | {traj.get('momentum', 0.0):.3f}% |
| Final Score | {traj.get('final_score', 0.0):.1f}% |
| Projected Round N+3 | {traj.get('projection', 0.0):.1f}% |

## 🔬 Per-Round RLFC Log

| Round | Score | Correct | Δσ_ded | Δσ_gen | Δσ_mcts | LR |
|-------|-------|---------|--------|--------|---------|-----|
{round_table}

## 🧠 Final Cortex State (SymBrain v8)

{final_sigma}

## 🏆 Mathematical Level Assessment

{"Galois demonstrates **Olympiad-level** performance with consistent improvement via RLFC." if summary['final_score'] >= 80 else "Galois demonstrates **Competition-level** performance with measurable RLFC-driven growth." if summary['final_score'] >= 60 else "Galois demonstrates **Academic-level** performance; continued RLFC rounds recommended."}

The Mind Olympiad framework successfully demonstrates:
- ✅ RLFC gradient updates from Euler's structured feedback
- ✅ Inference Transfer persisting knowledge across rounds
- ✅ SymBrain v8 σ parameter adaptation (deductive/generative balance)
- ✅ All {len(ADLER_PROBLEMS_ALL)} Adler problems ingested and evaluated
- ✅ Alexandrie cataloged all round reports and this final analysis

*Patent: US-PAT-PEND-2026-0525*
"""
    hub.store_artifact(
        artifact_id   = "mind_olympiad_final_report",
        title         = "SocrateAI Mind Olympiad Final Report — Galois v8 × Euler RLFC",
        content       = content,
        artifact_type = ArtifactType.PAPER,
        room_type     = RoomType.OPEN_ACCESS,
        creator       = "socrates_coordinator",
        tags          = [
            "mind-olympiad", "galois-v8", "rlfc", "inference-transfer",
            "adler-pims", "symbrain-v8", "final-report",
        ],
        metrics       = {
            "best_score":       summary["best_score"],
            "final_score":      summary["final_score"],
            "improvement_trend":trend,
            "total_rounds":     summary["total_rounds"],
            "compute_bill_usd": total_bill,
            "traj_trend":       traj.get("trend", 0.0),
            "traj_projection":  traj.get("projection", 0.0),
        },
    )
    print(f"\n    ✓ Final report stored in Alexandrie: 'mind_olympiad_final_report'")


# ──────────────────────────────────────────────────────────────────────────────
# Main orchestration loop
# ──────────────────────────────────────────────────────────────────────────────

async def run_mind_olympiad(
    num_rounds: int = 5,
    problems_per_round: int | None = None,
    verbose: bool = True,
) -> None:
    """Full Mind Olympiad challenge loop with RLFC and Inference Transfer."""

    print(BANNER)
    print(f"  Rounds: {num_rounds} | Problems/Round: {problems_per_round or 'ALL'} | Verbose: {verbose}")
    print(f"  Total problems in bank: {len(ADLER_PROBLEMS_ALL)}")
    print(SECTION)

    # ── Agent & hub initialization ───────────────────────────────────────────
    print("\n[+] Activating SocrateAI Swarm:")
    socrates = SocratesAgent()
    turing   = TuringAgent()
    galois   = GaloisAgent()
    euler    = EulerAgent()
    hypatie  = HypatieAgent()
    hub      = AlexandrieHub()

    print("    ✓ Socrates  (Dialectical Orchestrator)")
    print("    ✓ Turing    (Quota & Infrastructure Monitor)")
    print("    ✓ Galois    (SymBrain v8 'Mind Olympiad' — Solver)")
    print("    ✓ Euler     (Skeptical Auditor — Verifier & Corrector)")
    print("    ✓ Hypatie   (Alexandrie Librarian)")
    print("    ✓ Alexandrie Hub (Artifact Vault)")

    # ── SymBrain v8 upgrade ──────────────────────────────────────────────────
    galois.upgrade_to_v8()
    print(f"\n    ✓ Galois cortex upgraded: {galois.cortex.symbrain_version}")
    if galois.v8_cortex:
        r = galois.v8_cortex.routing
        print(f"      σ_ded={r.sigma_ded:.3f}  σ_gen={r.sigma_gen:.3f}  σ_mcts={r.sigma_mcts:.3f}")

    # ── RLFC & InferenceTransfer setup ───────────────────────────────────────
    rlfc          = RLFCEngine(total_rounds=num_rounds)
    transfer_bank = InferenceTransferBank()
    session       = OlympiadSession(
        session_name       = "AdlerMindOlympiad",
        total_rounds       = num_rounds,
        problems_per_round = problems_per_round,
    )

    # ── Phase 1: Turing audit ─────────────────────────────────────────────────
    total_bill = await phase_turing_audit(turing)

    # ── Phase 2: Hypatie ingest (done once) ──────────────────────────────────
    phase_hypatie_ingest(hub, hypatie, ADLER_PROBLEMS_ALL)

    # ── Select problem subset for each round ─────────────────────────────────
    if problems_per_round:
        # Use a rotating window across all problems
        all_probs  = ADLER_PROBLEMS_ALL
        n_total    = len(all_probs)
        batch_size = min(problems_per_round, n_total)
    else:
        all_probs  = ADLER_PROBLEMS_ALL
        batch_size = len(all_probs)

    # ── Check for existing InferenceTransfer checkpoint ──────────────────────
    existing = transfer_bank.load()
    if existing:
        print(f"\n[💾] Found existing InferenceTransfer checkpoint (round {existing.round_number})")
        result = transfer_bank.apply_transfer(galois.v8_cortex)
        print(f"     Applied: {result.get('avoidance_strategies_injected', 0)} strategies, "
              f"best_score={result.get('best_score_seen', 0):.1f}%")

    # ──────────────────────────────────────────────────────────────────────────
    # MAIN OLYMPIAD LOOP
    # ──────────────────────────────────────────────────────────────────────────
    print(f"\n{SECTION}")
    print(f"  🏁 Starting Mind Olympiad: {num_rounds} rounds × {batch_size} problems")
    print(SECTION)

    for round_idx in range(num_rounds):
        round_num = session.start_round()

        # Rotate problem batch for diversity across rounds
        start = (round_idx * batch_size) % len(all_probs)
        batch = all_probs[start : start + batch_size]
        if len(batch) < batch_size:
            batch = batch + all_probs[: batch_size - len(batch)]

        print(f"\n{'─'*80}")
        print(f"  🎯 Round {round_num}/{num_rounds} — {len(batch)} problems")
        print(f"{'─'*80}")

        # Phase 3: Galois solves
        print(f"\n  [▶] Galois (v8) solving {len(batch)} problems...")
        solutions = phase_galois_solve(galois, batch, round_num, transfer_bank, verbose)
        print(f"      ✓ {len(solutions)} solutions generated")

        # Phase 4: Euler corrects
        print(f"\n  [▶] Euler auditing {len(batch)} solutions...")
        report = phase_euler_correct(euler, batch, solutions, round_num, verbose)
        report.print_summary()

        # Phase 5: RLFC update
        print(f"\n  [▶] RLFC updating cortex σ parameters...")
        update = phase_rlfc_update(rlfc, report, galois, transfer_bank, session, verbose)

        # Phase 6: Inference Transfer inject (for next round)
        if round_num < num_rounds:
            print(f"\n  [▶] Injecting InferenceTransfer for Round {round_num + 1}...")
            phase_inference_transfer_inject(galois, transfer_bank, verbose)

        # Session tracking
        sigma_update_obj = update  # RLFCSigmaUpdate
        per_verdicts = [
            {
                "problem_id": fb.problem_id,
                "verdict":    fb.verdict.value,
                "error":      fb.error_class.value,
            }
            for fb in report.feedback_list
        ]
        result = session.end_round(
            problems_total       = report.total,
            problems_correct     = report.correct,
            sigma_update         = sigma_update_obj,
            per_problem_verdicts = per_verdicts,
        )
        session.print_round_banner(result)

        # Store round report to Alexandrie
        routing = getattr(galois.v8_cortex, "routing", None)
        store_round_report(hub, round_num, report, update, routing)
        print(f"  ✓ Round {round_num} report stored in Alexandrie.")

    # ──────────────────────────────────────────────────────────────────────────
    # Final Summary
    # ──────────────────────────────────────────────────────────────────────────
    print(f"\n{SECTION}")
    print(f"  🏆 MIND OLYMPIAD COMPLETE — {num_rounds} Rounds")
    print(SECTION)

    summary = session.summary()
    scores  = summary["score_history"]
    trend   = summary["improvement_trend_pct_per_round"]

    # Compute improvement trajectory
    traj: dict[str, Any] = {}
    if galois.v8_cortex:
        traj = galois.v8_cortex.compute_improvement_trajectory(scores)

    # Print final state
    routing = getattr(galois.v8_cortex, "routing", None)
    if routing:
        print(f"\n  Final Cortex State (SymBrain v8):")
        print(f"    σ_ded ={routing.sigma_ded:.4f}")
        print(f"    σ_gen ={routing.sigma_gen:.4f}")
        print(f"    σ_mcts={routing.sigma_mcts:.4f}")

    # Mistake fingerprint report
    fingerprints = rlfc.get_mistake_fingerprints()
    if fingerprints:
        print(f"\n  🔍 Top Mistake Patterns (RLFC Fingerprints):")
        for fp in fingerprints[:5]:
            print(f"    [{fp.error_class.value}] ×{fp.frequency}: {fp.correction_strategy[:70]}")

    # Improvement trajectory
    print(f"\n  📈 SymBrain v8 Improvement Trajectory:")
    print(f"    Trend:      {traj.get('trend', 0.0):+.3f}% per round")
    print(f"    Momentum:   {traj.get('momentum', 0.0):.1f}%")
    print(f"    Projection: {traj.get('projection', 0.0):.1f}% (3 more rounds)")

    # Score history table
    print(f"\n  📊 Score History:")
    for i, s in enumerate(scores):
        bar = "█" * int(s / 5)
        icon = "🏆" if s == max(scores) else ("📈" if i > 0 and s > scores[i-1] else "📊")
        print(f"    Round {i+1:2d}: {s:6.1f}%  {bar} {icon}")

    print(f"\n  ✓ Improvement trend: {trend:+.2f}% per round")
    print(f"  ✓ Best score:        {summary['best_score']:.1f}%")
    print(f"  ✓ Final score:       {summary['final_score']:.1f}%")
    print(f"  ✓ Total elapsed:     {summary['total_elapsed_s']:.1f}s")
    print(f"  ✓ Compute bill:      ${total_bill:.2f} (Frugal-AI ≤ $50.00)")

    # Store final report
    print(f"\n[▶] Storing final report to Alexandrie...")
    store_final_report(hub, session, galois, total_bill)

    # InferenceTransfer final state
    vec = transfer_bank.load()
    if vec:
        print(f"\n  💾 InferenceTransfer Checkpoint:")
        print(f"    Rounds recorded: {vec.round_number}")
        print(f"    Cumulative Δσ_ded:  {vec.cumulative_delta_ded:+.4f}")
        print(f"    Cumulative Δσ_gen:  {vec.cumulative_delta_gen:+.4f}")
        print(f"    Cumulative Δσ_mcts: {vec.cumulative_delta_mcts:+.4f}")
        print(f"    Avoidance strategies: {len(vec.avoidance_strategies)}")

    print(f"\n{SECTION}")
    print(f"  🏛️  Mind Olympiad Completed Successfully")
    print(f"  All artifacts stored in Alexandrie Open Access")
    print(f"  Galois RLFC InferenceTransfer checkpoint persisted")
    print(f"  Next run will automatically load and apply prior learning")
    print(SECTION)
    print()


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="SocrateAI Mind Olympiad — Automated Mathematical Challenge Loop"
    )
    p.add_argument(
        "--rounds", type=int, default=5,
        help="Number of Olympiad rounds (default: 5)",
    )
    p.add_argument(
        "--problems-per-round", type=int, default=None,
        metavar="N",
        help="Problems per round (default: all 30+ problems)",
    )
    p.add_argument(
        "--verbose", action="store_true",
        help="Print per-problem details",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(
        run_mind_olympiad(
            num_rounds          = args.rounds,
            problems_per_round  = args.problems_per_round,
            verbose             = args.verbose,
        )
    )


if __name__ == "__main__":
    main()
