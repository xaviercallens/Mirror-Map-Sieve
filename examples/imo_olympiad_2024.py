#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""
🏛️ IMO 2024 SHORTLIST OLYMPIAD — Galois v8a → v8b with Heraclite & Euler
══════════════════════════════════════════════════════════════════════════════════

3-Agent IMO Challenge Pipeline:
  1. Heraclite  — ingests problems (solutions SEALED), compares proposals post-round
  2. Galois v8a — solves BLINDLY (no access to official solutions)
  3. Euler      — formally verifies Galois proposals
  4. RLFC loop  — upgrades Galois v8a → v8b from IMO feedback

Rounds × Problems:
  • 5 rounds × all 31 IMO 2024 SL problems
  • Rotating problem batches for domain diversity
  • Per-round: Galois solves → Euler verifies → Heraclite compares → RLFC update

Output:
  • Alexandrie: per-round reports, Heraclite comparisons, final monograph
  • cortex_v8b.py: upgraded Galois cortex from IMO RLFC
  • 300-page monograph PDF + EPUB → Kindle

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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ── Agents ────────────────────────────────────────────────────────────────────
from agents.socrates.agent import SocratesAgent
from agents.turing.agent   import TuringAgent
from agents.galois.agent   import GaloisAgent
from agents.euler.agent    import EulerAgent
from agents.hypatie.agent  import HypatieAgent
from agents.heraclite      import HeracliteAgent

# ── Alexandrie ────────────────────────────────────────────────────────────────
from alexandrie.hub      import AlexandrieHub
from alexandrie.metadata import ArtifactType, RoomType

# ── Problem bank ──────────────────────────────────────────────────────────────
from olympiad.imo_2024_sl_bank import (
    IMO_2024_SL_ALL,
    IMO_2024_SL_BLIND,
    IMOProblem,
    DOMAIN_COUNTS,
)

# ── Galois v8a cortex ─────────────────────────────────────────────────────────
from agents.galois.symbrain.cortex_v8a import (
    SymBrainV8aCortex,
    ADLER_RLFC_PRIORS,
    ADLER_AVOIDANCE_STRATEGIES,
)

# ── RLFC ──────────────────────────────────────────────────────────────────────
from agents.galois.olympiad.rlfc_engine       import RLFCEngine
from agents.galois.olympiad.inference_transfer import InferenceTransferBank
from agents.galois.olympiad.olympiad_session   import OlympiadSession

# ── Euler corrector ───────────────────────────────────────────────────────────
from agents.euler.tools.olympiad_corrector import (
    OlympiadCorrectionReport,
    correct_solution_batch,
)


# ──────────────────────────────────────────────────────────────────────────────
# Banner
# ──────────────────────────────────────────────────────────────────────────────

BANNER = """
╔════════════════════════════════════════════════════════════════════════════════╗
║  🏛️  SocrateAI Agora — IMO 2024 SHORTLIST OLYMPIAD                           ║
║  Galois v8a (Adler-Enhanced) × Euler (Skeptical Auditor) × Heraclite         ║
║  International Mathematical Olympiad 2024 — All Shortlisted Problems         ║
║  RLFC Learning Loop → Galois v8b Upgrade                                     ║
╚════════════════════════════════════════════════════════════════════════════════╝
"""

SECTION = "═" * 82
THIN    = "─" * 82


# ──────────────────────────────────────────────────────────────────────────────
# Phase implementations
# ──────────────────────────────────────────────────────────────────────────────

async def phase_turing_audit(turing: TuringAgent) -> float:
    """Phase 0: Turing budget audit for IMO olympiad."""
    print(f"\n[▶] Phase 0: Turing Infrastructure Audit")
    result = await turing.run(
        "Estimate GCP compute cost for IMO 2024 SL Olympiad (5 rounds × 31 problems)",
        pool_config={
            "gpu_type":      "dual-H100",
            "vram_gb":       160.0,
            "mcts_nodes":    1024.0,
            "vcpu_request":  96,
        },
        quota_limits={"h100_limit": 4, "l4_limit": 8, "vcpu_limit": 128},
    )
    pool    = result.answer.get("pool_report", {})
    hourly  = pool.get("estimated_hourly_rate_usd", 8.50)
    bill    = hourly * 4.0   # IMO harder → 4h estimate
    print(f"    ✓ GPU:          {pool.get('gpu_type', 'dual-H100')}")
    print(f"    ✓ Frugal-AI:   ${bill:.2f} / $50.00")
    if bill > 50.00:
        print(f"    ❌ Budget exceeded ${bill:.2f}. Exiting.")
        sys.exit(1)
    return bill


def phase_heraclite_ingest(heraclite: HeracliteAgent) -> None:
    """Phase 1: Heraclite ingests all IMO 2024 SL problems (solutions SEALED)."""
    print(f"\n[▶] Phase 1: Heraclite — Ingesting IMO 2024 SL Problems (solutions sealed)")
    heraclite.ingest_problems_to_alexandrie(IMO_2024_SL_BLIND)
    print(f"    ✓ Domain breakdown: A={DOMAIN_COUNTS['A']} C={DOMAIN_COUNTS['C']} "
          f"G={DOMAIN_COUNTS['G']} N={DOMAIN_COUNTS['N']} TOTAL={DOMAIN_COUNTS['TOTAL']}")


def phase_galois_solve_imo(
    galois:       GaloisAgent,
    v8a_cortex:   SymBrainV8aCortex,
    problems:     list[IMOProblem],
    round_number: int,
    transfer_bank: InferenceTransferBank,
    verbose:      bool = False,
) -> list[Any]:
    """Phase 2: Galois v8a solves IMO problems in BLIND MODE."""
    proposals = []
    for prob in problems:
        proposal = v8a_cortex.solve_imo_blind(prob, round_number)
        proposals.append(proposal)
        if verbose:
            icon = "🔭" if proposal.confidence > 0.60 else "💡"
            print(
                f"    {icon} [{proposal.difficulty_code:3s}] "
                f"conf={proposal.confidence:.2f}  "
                f"domain={proposal.imo_domain.value}  "
                f"sig={proposal.verification_sig}"
            )
    return proposals


def phase_euler_verify_imo(
    euler:        EulerAgent,
    problems:     list[IMOProblem],
    proposals:    list[Any],
    round_number: int,
    verbose:      bool = False,
) -> OlympiadCorrectionReport:
    """Phase 3: Euler formally verifies Galois's blind proposals."""
    # Adapt IMO proposals to OlympiadSolution format
    class _ProposalAdapter:
        """Thin adapter: IMOProofProposal → OlympiadSolution interface."""
        def __init__(self, p: Any) -> None:
            self.problem_id    = p.problem_id
            self.solution_text = p.formal_argument
            self.strategy_used = p.proof_strategy[:60]
            self.lean4_proof   = p.lean4_skeleton
            self.confidence    = p.confidence
            self.proof_steps   = p.key_lemmas

    adapted = [_ProposalAdapter(p) for p in proposals]
    report  = correct_solution_batch(problems, adapted, round_number)

    if verbose:
        for fb in report.feedback_list:
            icon = (
                "✅" if fb.verdict.value == "correct" else
                "⚠️" if fb.verdict.value == "partial" else "❌"
            )
            print(
                f"    {icon} [{fb.problem_id[-3:]:3s}] "
                f"verdict={fb.verdict.value:<20} "
                f"error={fb.error_class.value}"
            )
    return report


def phase_heraclite_compare(
    heraclite:    HeracliteAgent,
    proposals:    list[Any],
    euler_report: OlympiadCorrectionReport,
    round_number: int,
) -> Any:
    """Phase 4: Heraclite opens the sealed vault and compares proposals vs official."""
    print(f"\n  [▶] Heraclite unsealing vault for round {round_number}...")
    comparison = heraclite.compare_proposals(
        proposals       = proposals,
        euler_verdicts  = euler_report.feedback_list,
        round_number    = round_number,
    )
    comparison.print_summary()
    heraclite.store_comparison_report(comparison)
    return comparison


def phase_rlfc_update_v8a(
    rlfc:          RLFCEngine,
    euler_report:  OlympiadCorrectionReport,
    v8a_cortex:    SymBrainV8aCortex,
    transfer_bank: InferenceTransferBank,
    verbose:       bool = False,
) -> Any:
    """Phase 5: RLFC updates v8a cortex → progress toward v8b."""
    update = rlfc.process_feedback_batch(euler_report.feedback_list, v8a_cortex)
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
        r = v8a_cortex.routing
        print(
            f"    v8a σ: ded={r.sigma_ded:.4f}  "
            f"gen={r.sigma_gen:.4f}  "
            f"mcts={r.sigma_mcts:.4f}"
        )
    return update


def generate_cortex_v8b(
    v8a_cortex:    SymBrainV8aCortex,
    rlfc:          RLFCEngine,
    transfer_bank: InferenceTransferBank,
    session_summary: dict[str, Any],
) -> dict[str, Any]:
    """Generate SymBrain v8b parameters from completed IMO RLFC run."""
    r = v8a_cortex.routing
    vec = transfer_bank.load()
    fingerprints = rlfc.get_mistake_fingerprints()

    v8b_params = {
        # Final IMO-tuned sigma values
        "sigma_ded":   round(r.sigma_ded,  4),
        "sigma_gen":   round(r.sigma_gen,  4),
        "sigma_mcts":  round(r.sigma_mcts, 4),
        # RLFC history
        "imo_rounds":          session_summary.get("total_rounds", 5),
        "imo_final_score":     session_summary.get("final_score", 0.0),
        "imo_best_score":      session_summary.get("best_score",  0.0),
        "improvement_trend":   session_summary.get("improvement_trend_pct_per_round", 0.0),
        # Source priors
        "adler_sigma_ded_prior":  ADLER_RLFC_PRIORS["sigma_ded_final"],
        "adler_sigma_gen_prior":  ADLER_RLFC_PRIORS["sigma_gen_final"],
        "adler_sigma_mcts_prior": ADLER_RLFC_PRIORS["sigma_mcts_final"],
        # Net delta from IMO
        "imo_delta_ded":  round(r.sigma_ded  - ADLER_RLFC_PRIORS["sigma_ded_final"],  4),
        "imo_delta_gen":  round(r.sigma_gen  - ADLER_RLFC_PRIORS["sigma_gen_final"],  4),
        "imo_delta_mcts": round(r.sigma_mcts - ADLER_RLFC_PRIORS["sigma_mcts_final"], 4),
        # Mistake fingerprints count
        "fingerprints_count": len(fingerprints),
        "top_errors": [
            {"error": fp.error_class.value, "freq": fp.frequency,
             "strategy": fp.correction_strategy[:80]}
            for fp in fingerprints[:5]
        ],
        # Cumulative deltas
        "cumulative_delta_ded":   round(vec.cumulative_delta_ded,  4) if vec else 0.0,
        "cumulative_delta_gen":   round(vec.cumulative_delta_gen,  4) if vec else 0.0,
        "cumulative_delta_mcts":  round(vec.cumulative_delta_mcts, 4) if vec else 0.0,
        "avoidance_strategies_total": len(ADLER_AVOIDANCE_STRATEGIES) + len(fingerprints),
        "symbrain_version": "v8b-IMO2024SL-RLFC",
        "predecessor": "v8a-IMO-AdlerPrior",
        "olympiad_source": "IMO 2024 Shortlist (31 problems, 4 domains: A/C/G/N)",
    }
    return v8b_params


def write_cortex_v8b_module(
    v8b_params: dict[str, Any],
    output_path: Path,
) -> None:
    """Write the cortex_v8b.py module with learned sigma parameters."""
    code = f'''# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
# AUTO-GENERATED by imo_olympiad_2024.py — DO NOT EDIT MANUALLY
"""SymBrain v8b — IMO 2024 SL RLFC-upgraded cortex.

Generated after completion of the IMO 2024 Shortlist Olympiad:
  • 5 rounds × 31 problems (A={DOMAIN_COUNTS["A"]}, C={DOMAIN_COUNTS["C"]}, G={DOMAIN_COUNTS["G"]}, N={DOMAIN_COUNTS["N"]})
  • RLFC learning from Euler formal verification + Heraclite comparison
  • Cross-olympiad InferenceTransfer: Adler PIMS → IMO 2024

v8b sigma values represent the fully converged post-IMO state:
  σ_ded  = {v8b_params["sigma_ded"]}   (Adler prior: {v8b_params["adler_sigma_ded_prior"]}, IMO Δ: {v8b_params["imo_delta_ded"]:+.4f})
  σ_gen  = {v8b_params["sigma_gen"]}   (Adler prior: {v8b_params["adler_sigma_gen_prior"]}, IMO Δ: {v8b_params["imo_delta_gen"]:+.4f})
  σ_mcts = {v8b_params["sigma_mcts"]}  (Adler prior: {v8b_params["adler_sigma_mcts_prior"]}, IMO Δ: {v8b_params["imo_delta_mcts"]:+.4f})

IMO 2024 SL Performance:
  Final score:       {v8b_params["imo_final_score"]:.1f}%
  Best score:        {v8b_params["imo_best_score"]:.1f}%
  Improvement trend: {v8b_params["improvement_trend"]:+.2f}%/round

Patent: US-PAT-PEND-2026-0525
"""
from __future__ import annotations
from agents.galois.symbrain.cortex_v8a import SymBrainV8aCortex, ADLER_RLFC_PRIORS
from agents.galois.symbrain.cortex_v4 import GaloisCortexConfig


# ── v8b learned parameters ────────────────────────────────────────────────────
V8B_PARAMS: dict = {json.dumps(v8b_params, indent=4)[1:-1]}

# IMO 2024 SL mistake avoidance strategies (from RLFC fingerprints)
IMO_AVOIDANCE_STRATEGIES: list[str] = [
{chr(10).join(f'    "{fp["strategy"]}",' for fp in v8b_params["top_errors"])}
    # -- Adler priors carried forward --
    "NT: verify p-adic valuation before applying LTE lemma",
    "GEOM: state which circle theorem (Power/Radical/Ptolemy) is applied",
    "ALG: decompose as SOS before claiming non-negativity",
    "COMB: double-count in bipartite graphs — both sides",
    "PROOF: all boundary/degenerate cases must be explicitly verified",
]


class SymBrainV8bCortex(SymBrainV8aCortex):
    """SymBrain v8b — fully IMO-trained cortex.

    Inherits from v8a (Adler-enhanced) and overrides sigma parameters
    with values learned from 5 rounds of IMO 2024 SL RLFC.

    Key improvements over v8a:
    - Deeper MCTS search (σ_mcts = {v8b_params["sigma_mcts"]})
    - More balanced deductive/generative routing
    - {len(v8b_params["top_errors"])} IMO-specific avoidance strategies
    - Cross-olympiad knowledge: Adler + IMO 2024 SL
    """

    symbrain_version = "v8b-IMO2024SL-RLFC"

    def __init__(self, base_config: GaloisCortexConfig) -> None:
        super().__init__(base_config)
        self.symbrain_version = "v8b-IMO2024SL-RLFC"
        # Override with v8b learned sigma
        self.routing.sigma_ded  = {v8b_params["sigma_ded"]}
        self.routing.sigma_gen  = {v8b_params["sigma_gen"]}
        self.routing.sigma_mcts = {v8b_params["sigma_mcts"]}
        # Extend avoidance strategies with IMO-learned patterns
        self._imo_avoidance = IMO_AVOIDANCE_STRATEGIES + self._imo_avoidance

    @property
    def v8b_improvement_summary(self) -> dict[str, float]:
        """Return a summary of v8b improvements over v8a."""
        return {{
            "sigma_ded_delta":  {v8b_params["imo_delta_ded"]},
            "sigma_gen_delta":  {v8b_params["imo_delta_gen"]},
            "sigma_mcts_delta": {v8b_params["imo_delta_mcts"]},
            "imo_final_score":  {v8b_params["imo_final_score"]},
            "imo_best_score":   {v8b_params["imo_best_score"]},
            "trend_pct_round":  {v8b_params["improvement_trend"]},
            "avoidance_count":  {v8b_params["avoidance_strategies_total"]},
        }}
'''
    output_path.write_text(code, encoding="utf-8")
    print(f"\n    ✓ cortex_v8b.py written to {output_path}")


def store_imo_round_report(
    hub:          AlexandrieHub,
    round_number: int,
    euler_report: OlympiadCorrectionReport,
    comparison:   Any,
    update:       Any,
    v8a_cortex:   SymBrainV8aCortex,
) -> None:
    """Store per-round combined Euler+Heraclite report to Alexandrie."""
    r = v8a_cortex.routing
    content = (
        f"# IMO 2024 SL Olympiad — Round {round_number} Combined Report\n\n"
        f"## Euler Verification\n"
        f"Score: {euler_report.correct}/{euler_report.total} "
        f"({euler_report.score_pct:.1f}%)\n"
        f"Partial: {euler_report.partial} | Errors: {euler_report.errors}\n\n"
        f"## Heraclite Comparison\n"
        f"Approach matches: {comparison.approach_matches}/{comparison.total_problems}\n"
        f"Correct solutions: {comparison.correct_solutions}\n"
        f"Mean alignment: {comparison.mean_alignment:.3f}\n"
        f"Mean completeness: {comparison.mean_completeness:.3f}\n\n"
        f"## RLFC Update\n"
        f"Δσ_ded={update.delta_sigma_ded:+.4f}  "
        f"Δσ_gen={update.delta_sigma_gen:+.4f}  "
        f"Δσ_mcts={update.delta_sigma_mcts:+.4f}\n"
        f"LR={update.learning_rate:.4f}\n\n"
        f"## v8a Cortex State\n"
        f"σ_ded={r.sigma_ded:.4f}  σ_gen={r.sigma_gen:.4f}  σ_mcts={r.sigma_mcts:.4f}\n"
    )
    hub.store_artifact(
        artifact_id   = f"imo2024sl_round_{round_number}_report",
        title         = f"IMO 2024 SL Olympiad Round {round_number} Combined Report",
        content       = content,
        artifact_type = ArtifactType.PAPER,
        room_type     = RoomType.OPEN_ACCESS,
        creator       = "agora_orchestrator",
        tags          = ["imo-2024", f"round-{round_number}", "euler", "heraclite", "rlfc"],
        metrics       = {
            "score_pct":        euler_report.score_pct,
            "correct":          euler_report.correct,
            "total":            euler_report.total,
            "mean_alignment":   comparison.mean_alignment,
            "delta_sigma_ded":  update.delta_sigma_ded,
            "delta_sigma_mcts": update.delta_sigma_mcts,
        },
    )


def store_final_imo_report(
    hub:          AlexandrieHub,
    session:      OlympiadSession,
    v8a_cortex:   SymBrainV8aCortex,
    v8b_params:   dict[str, Any],
    comparisons:  list[Any],
    total_bill:   float,
) -> None:
    """Store the final IMO Olympiad report to Alexandrie."""
    summary = session.summary()
    scores  = summary["score_history"]
    trend   = summary["improvement_trend_pct_per_round"]
    traj    = v8a_cortex.compute_improvement_trajectory(scores)

    # Aggregate comparison stats across all rounds
    total_correct   = sum(c.correct_solutions   for c in comparisons)
    total_matches   = sum(c.approach_matches     for c in comparisons)
    total_novel     = sum(c.novel_approaches     for c in comparisons)
    total_problems  = sum(c.total_problems       for c in comparisons)
    mean_align      = sum(c.mean_alignment       for c in comparisons) / max(len(comparisons), 1)

    score_table = "\n".join(
        f"| Round {r['round']} | {r['score']:.1f}% | {r['correct']}/{r['total']} "
        f"| {r['delta_sigma_ded']:+.4f} | {r['delta_sigma_gen']:+.4f} "
        f"| {r['delta_sigma_mcts']:+.4f} |"
        for r in summary.get("rounds", [])
    )

    content = f"""# 🏛️ SocrateAI Agora — IMO 2024 Shortlist Olympiad Final Report

**Framework**: Galois v8a (Adler-Enhanced) × Euler (Formal Verifier) × Heraclite (Comparator)
**Source**: IMO 2024 Official Shortlist — {DOMAIN_COUNTS['TOTAL']} problems across A/C/G/N
**Total Rounds**: {summary['total_rounds']}
**Budget**: ${total_bill:.2f} (Frugal-AI compliant ≤ $50.00)

---

## 📊 Euler Verification Score History

{', '.join(f"Round {i+1}: {s:.1f}%" for i, s in enumerate(scores))}

**Best Round**: {summary['best_score']:.1f}%
**Final Score**: {summary['final_score']:.1f}%
**Improvement Trend**: {trend:+.2f}% per round

## 🏺 Heraclite Comparison Summary (All Rounds)

| Metric | Value |
|--------|-------|
| Total problems attempted | {total_problems} |
| Correct solutions (Galois) | {total_correct} ({100*total_correct/max(total_problems,1):.1f}%) |
| Approach matches | {total_matches} ({100*total_matches/max(total_problems,1):.1f}%) |
| Novel approaches | {total_novel} |
| Mean approach alignment | {mean_align:.3f} |

## 📈 SymBrain v8a → v8b RLFC Upgrade

| Parameter | v8a (Adler prior) | v8b (Post-IMO) | Δ |
|-----------|-------------------|-----------------|---|
| σ_ded  | {v8b_params['adler_sigma_ded_prior']} | {v8b_params['sigma_ded']} | {v8b_params['imo_delta_ded']:+.4f} |
| σ_gen  | {v8b_params['adler_sigma_gen_prior']} | {v8b_params['sigma_gen']} | {v8b_params['imo_delta_gen']:+.4f} |
| σ_mcts | {v8b_params['adler_sigma_mcts_prior']} | {v8b_params['sigma_mcts']} | {v8b_params['imo_delta_mcts']:+.4f} |

## 🔬 Per-Round RLFC Log

| Round | Score | Correct | Δσ_ded | Δσ_gen | Δσ_mcts |
|-------|-------|---------|--------|--------|---------|
{score_table}

## 🏆 Domain Performance Analysis

| Domain | Problems | Focus | Key Gaps |
|--------|----------|-------|----------|
| Algebra (A) | {DOMAIN_COUNTS['A']} | Functional equations, inequalities | SOS decomposition, substitution |
| Combinatorics (C) | {DOMAIN_COUNTS['C']} | Graphs, extremal | Double counting, monovariant |
| Geometry (G) | {DOMAIN_COUNTS['G']} | Circles, projective | Power of point, inversion |
| Number Theory (N) | {DOMAIN_COUNTS['N']} | Primes, Diophantine | LTE lemma, Vieta jumping |

## 🧠 SymBrain v8b — Learned Knowledge Summary

- ✅ **{v8b_params['avoidance_strategies_total']} avoidance strategies** (Adler + IMO combined)
- ✅ **Cross-olympiad transfer**: Adler PIMS (33 problems) → IMO 2024 SL (31 problems)
- ✅ **v8b cortex file**: `agents/galois/symbrain/cortex_v8b.py`
- ✅ **Trend**: {traj.get('trend', 0.0):+.3f}%/round | Projection: {traj.get('projection', 0.0):.1f}% (3 more rounds)

*Patent: US-PAT-PEND-2026-0525*
*Copyright © 2026 Xavier Callens / Socrate AI Lab*
"""
    hub.store_artifact(
        artifact_id   = "imo2024sl_final_report",
        title         = "IMO 2024 SL Olympiad Final Report — Galois v8b RLFC",
        content       = content,
        artifact_type = ArtifactType.PAPER,
        room_type     = RoomType.OPEN_ACCESS,
        creator       = "agora_orchestrator",
        tags          = [
            "imo-2024", "shortlist", "galois-v8b", "rlfc", "heraclite",
            "euler", "inference-transfer", "final-report",
        ],
        metrics       = {
            "best_score":      summary["best_score"],
            "final_score":     summary["final_score"],
            "improvement_pct": trend,
            "total_rounds":    summary["total_rounds"],
            "mean_alignment":  mean_align,
            "v8b_sigma_ded":   v8b_params["sigma_ded"],
            "v8b_sigma_gen":   v8b_params["sigma_gen"],
            "v8b_sigma_mcts":  v8b_params["sigma_mcts"],
        },
    )
    print(f"\n    ✓ Final IMO report stored: 'imo2024sl_final_report'")


# ──────────────────────────────────────────────────────────────────────────────
# Main orchestration loop
# ──────────────────────────────────────────────────────────────────────────────

async def run_imo_olympiad(
    num_rounds:         int  = 5,
    problems_per_round: int | None = None,
    verbose:            bool = True,
) -> None:
    """Full IMO 2024 SL Olympiad with 3-agent pipeline and v8a→v8b RLFC upgrade."""
    print(BANNER)
    print(f"  Rounds: {num_rounds} | Problems/Round: {problems_per_round or 'ALL'} | Verbose: {verbose}")
    print(f"  IMO 2024 SL: {DOMAIN_COUNTS['TOTAL']} problems "
          f"(A={DOMAIN_COUNTS['A']} C={DOMAIN_COUNTS['C']} "
          f"G={DOMAIN_COUNTS['G']} N={DOMAIN_COUNTS['N']})")
    print(SECTION)

    # ── Agent & hub initialization ─────────────────────────────────────────
    print("\n[+] Activating SocrateAI IMO Swarm:")
    socrates  = SocratesAgent()
    turing    = TuringAgent()
    galois    = GaloisAgent()
    euler     = EulerAgent()
    hypatie   = HypatieAgent()
    heraclite = HeracliteAgent()
    hub       = AlexandrieHub()

    print("    ✓ Socrates   (Dialectical Orchestrator)")
    print("    ✓ Turing     (Infrastructure Monitor)")
    print("    ✓ Galois     (SymBrain v8a — Blind IMO Solver)")
    print("    ✓ Euler      (Skeptical Auditor — Formal Verifier)")
    print("    ✓ Heraclite  (IMO Problem Curator & Solution Comparator) ← NEW")
    print("    ✓ Hypatie    (Alexandrie Librarian)")
    print("    ✓ Alexandrie Hub")

    # ── SymBrain v8a upgrade ───────────────────────────────────────────────
    galois.upgrade_to_v8()
    from agents.galois.symbrain.cortex_v4 import GaloisCortexConfig
    v8a_cortex = SymBrainV8aCortex(galois.cortex)
    print(f"\n    ✓ Galois upgraded to {v8a_cortex.symbrain_version}")
    r = v8a_cortex.routing
    print(f"      Adler priors: σ_ded={r.sigma_ded:.4f}  "
          f"σ_gen={r.sigma_gen:.4f}  σ_mcts={r.sigma_mcts:.4f}")
    transfer = v8a_cortex.get_adler_transfer_summary()
    print(f"      Cross-olympiad transfer: {transfer['source']}")

    # ── RLFC & InferenceTransfer ───────────────────────────────────────────
    rlfc          = RLFCEngine(total_rounds=num_rounds)
    transfer_bank = InferenceTransferBank()
    session       = OlympiadSession(
        session_name       = "IMO2024SLOlympiad",
        total_rounds       = num_rounds,
        problems_per_round = problems_per_round,
    )

    # ── Phase 0: Turing audit ──────────────────────────────────────────────
    total_bill = await phase_turing_audit(turing)

    # ── Phase 1: Heraclite ingests all problems ────────────────────────────
    phase_heraclite_ingest(heraclite)

    # ── Problem batch selection ────────────────────────────────────────────
    all_probs   = IMO_2024_SL_BLIND
    n_total     = len(all_probs)
    batch_size  = min(problems_per_round, n_total) if problems_per_round else n_total

    # ── Load existing InferenceTransfer checkpoint ─────────────────────────
    existing = transfer_bank.load()
    if existing:
        print(f"\n[💾] Loaded InferenceTransfer checkpoint (round {existing.round_number})")
        transfer_bank.apply_transfer(v8a_cortex)

    # ──────────────────────────────────────────────────────────────────────
    # MAIN IMO OLYMPIAD LOOP
    # ──────────────────────────────────────────────────────────────────────
    print(f"\n{SECTION}")
    print(f"  🏁 Starting IMO 2024 SL Olympiad: {num_rounds} rounds × {batch_size} problems")
    print(f"  Pipeline: Galois(blind) → Euler(verify) → Heraclite(compare) → RLFC(update)")
    print(SECTION)

    all_comparisons: list[Any] = []

    for round_idx in range(num_rounds):
        round_num = session.start_round()

        # Rotate batch across rounds
        start = (round_idx * batch_size) % n_total
        batch = all_probs[start : start + batch_size]
        if len(batch) < batch_size:
            batch = batch + all_probs[: batch_size - len(batch)]

        print(f"\n{THIN}")
        domain_dist = {}
        for p in batch:
            domain_dist[p.imo_domain] = domain_dist.get(p.imo_domain, 0) + 1
        dist_str = " ".join(f"{d}:{n}" for d, n in sorted(domain_dist.items()))
        print(f"  🎯 Round {round_num}/{num_rounds} — {len(batch)} problems [{dist_str}]")
        print(THIN)

        # Phase 2: Galois blind solving
        print(f"\n  [▶] Galois v8a solving {len(batch)} problems (BLIND MODE)...")
        proposals = phase_galois_solve_imo(
            galois, v8a_cortex, batch, round_num, transfer_bank, verbose
        )
        print(f"      ✓ {len(proposals)} blind proposals generated")

        # Phase 3: Euler formal verification
        print(f"\n  [▶] Euler formally verifying {len(batch)} proposals...")
        euler_report = phase_euler_verify_imo(
            euler, batch, proposals, round_num, verbose
        )
        euler_report.print_summary()

        # Phase 4: Heraclite opens vault and compares
        print(f"\n  [▶] Heraclite comparing proposals vs official solutions...")
        comparison = phase_heraclite_compare(
            heraclite, proposals, euler_report, round_num
        )
        all_comparisons.append(comparison)

        # Phase 5: RLFC update v8a → toward v8b
        print(f"\n  [▶] RLFC updating SymBrain v8a cortex...")
        update = phase_rlfc_update_v8a(
            rlfc, euler_report, v8a_cortex, transfer_bank, verbose
        )

        # Inject transfer for next round
        if round_num < num_rounds:
            print(f"\n  [▶] Injecting InferenceTransfer for Round {round_num + 1}...")
            transfer_bank.apply_transfer(v8a_cortex)

        # Session tracking
        per_verdicts = [
            {"problem_id": fb.problem_id, "verdict": fb.verdict.value,
             "error": fb.error_class.value}
            for fb in euler_report.feedback_list
        ]
        result = session.end_round(
            problems_total       = euler_report.total,
            problems_correct     = euler_report.correct,
            sigma_update         = update,
            per_problem_verdicts = per_verdicts,
        )
        session.print_round_banner(result)

        # Store round report
        store_imo_round_report(
            hub, round_num, euler_report, comparison, update, v8a_cortex
        )
        print(f"  ✓ Round {round_num} report → Alexandrie")

    # ──────────────────────────────────────────────────────────────────────
    # Post-Olympiad: Generate v8b cortex
    # ──────────────────────────────────────────────────────────────────────
    print(f"\n{SECTION}")
    print(f"  🧠 Generating SymBrain v8b from IMO RLFC...")
    print(SECTION)

    summary    = session.summary()
    v8b_params = generate_cortex_v8b(v8a_cortex, rlfc, transfer_bank, summary)

    # Write cortex_v8b.py
    v8b_path = Path(__file__).resolve().parents[1] / "agents" / "galois" / "symbrain" / "cortex_v8b.py"
    write_cortex_v8b_module(v8b_params, v8b_path)

    # Store v8b params to Alexandrie
    hub.store_artifact(
        artifact_id   = "galois_v8b_params",
        title         = "Galois SymBrain v8b Learned Parameters (Post-IMO RLFC)",
        content       = json.dumps(v8b_params, indent=2),
        artifact_type = ArtifactType.CHECKPOINT,
        room_type     = RoomType.PRIVATE,
        creator       = "rlfc_engine",
        tags          = ["galois-v8b", "rlfc", "imo-2024", "symbrain", "checkpoint"],
        metrics       = {
            "sigma_ded":  v8b_params["sigma_ded"],
            "sigma_gen":  v8b_params["sigma_gen"],
            "sigma_mcts": v8b_params["sigma_mcts"],
            "imo_final_score": v8b_params["imo_final_score"],
        },
    )
    print(f"    ✓ v8b params stored to Alexandrie (private vault)")

    # ── Final summary ──────────────────────────────────────────────────────
    scores = summary["score_history"]
    trend  = summary["improvement_trend_pct_per_round"]

    print(f"\n{SECTION}")
    print(f"  🏆 IMO 2024 SL OLYMPIAD COMPLETE — {num_rounds} Rounds")
    print(SECTION)

    r_final = v8a_cortex.routing
    print(f"\n  Final SymBrain v8b Cortex:")
    print(f"    σ_ded  = {r_final.sigma_ded:.4f}  "
          f"(Adler: {ADLER_RLFC_PRIORS['sigma_ded_final']}  "
          f"Δ_IMO: {v8b_params['imo_delta_ded']:+.4f})")
    print(f"    σ_gen  = {r_final.sigma_gen:.4f}  "
          f"(Adler: {ADLER_RLFC_PRIORS['sigma_gen_final']}  "
          f"Δ_IMO: {v8b_params['imo_delta_gen']:+.4f})")
    print(f"    σ_mcts = {r_final.sigma_mcts:.4f}  "
          f"(Adler: {ADLER_RLFC_PRIORS['sigma_mcts_final']}  "
          f"Δ_IMO: {v8b_params['imo_delta_mcts']:+.4f})")

    print(f"\n  📊 Score History:")
    for i, s in enumerate(scores):
        bar  = "█" * int(s / 5)
        icon = "🏆" if s == max(scores) else ("📈" if i > 0 and s > scores[i-1] else "📊")
        print(f"    Round {i+1:2d}: {s:6.1f}%  {bar} {icon}")

    print(f"\n  📈 Trajectory: {trend:+.2f}%/round | "
          f"Best: {summary['best_score']:.1f}% | "
          f"Final: {summary['final_score']:.1f}%")

    # Heraclite aggregate
    total_correct = sum(c.correct_solutions for c in all_comparisons)
    total_probs   = sum(c.total_problems    for c in all_comparisons)
    print(f"\n  🏺 Heraclite: {total_correct}/{total_probs} correct "
          f"({100*total_correct/max(total_probs,1):.1f}%) vs official solutions")

    # RLFC fingerprints
    fps = rlfc.get_mistake_fingerprints()
    if fps:
        print(f"\n  🔍 Top RLFC Error Fingerprints:")
        for fp in fps[:4]:
            print(f"    [{fp.error_class.value}] ×{fp.frequency}: "
                  f"{fp.correction_strategy[:65]}")

    # Store final report
    print(f"\n[▶] Storing final IMO report to Alexandrie...")
    store_final_imo_report(
        hub, session, v8a_cortex, v8b_params, all_comparisons, total_bill
    )

    print(f"\n  ✓ Budget: ${total_bill:.2f}")
    print(f"  ✓ v8b cortex: {v8b_path}")
    print(f"  ✓ Alexandrie artifacts: {3 + 2*num_rounds} stored")
    print(f"\n  Next: run generate_imo_monograph_300.py to produce the 300-page PDF\n")

    print(SECTION)
    print(f"  🏛️  IMO 2024 SL Olympiad Complete — Galois v8b ready for next olympiad")
    print(SECTION)


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="SocrateAI IMO 2024 SL Olympiad — Galois v8a→v8b RLFC upgrade"
    )
    p.add_argument("--rounds", type=int, default=5, help="Olympiad rounds (default: 5)")
    p.add_argument("--problems-per-round", type=int, default=None, metavar="N",
                   help="Problems per round (default: all 31)")
    p.add_argument("--verbose", action="store_true", help="Per-problem detail")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(run_imo_olympiad(
        num_rounds          = args.rounds,
        problems_per_round  = args.problems_per_round,
        verbose             = args.verbose,
    ))


if __name__ == "__main__":
    main()
