# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""
Rank26Discovery Pipeline — Dual-Track Search for ⟨4,4,4⟩ Border Rank ≤ 26

This pipeline runs two parallel scientific tracks:

Track A (Constructive): Numerical ALS search for explicit 26-matrix witness
  Stage 1. Gauss     — State of art: what's known about R(⟨4,4,4⟩)?
  Stage 2. Ramanujan — Compute: ALS over ε-algebra, ranks 26..40, 50 restarts
  Stage 3. Poincaré  — Verify: if witness found, multi-agent sanity check
  Stage 4. Newton    — Formalize: if verified, write native_decide Lean 4 proof

Track B (Lower Bound): Theoretical analysis
  Stage 5. Gauss     — Collect: Bläser lower bound arguments
  Stage 6. Poincaré  — Synthesize: what do Track A + Track B together conclude?

Learning output: detailed journal of what worked, what failed, and why.
Each stage writes a stage_N_journal.md entry.
Final output: rank26_discovery_report.md with the complete learning journal.

Architecture follows the neuro-symbolic, frugal-AI paradigm with strict
budget guards ($30/pipeline) and serverless-first deployment.

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import pathlib
import textwrap
import time
import uuid
from dataclasses import dataclass
from typing import Any

import structlog

from agents.pipelines.base import AgentPipeline, PipelineResult, PipelineStage
from agents.pipelines.stages.gauss_state_of_art import run_gauss_state_of_art
from agents.pipelines.stages.ramanujan_rank_search import run_ramanujan_rank_search
from agents.pipelines.stages.poincare_quorum import run_poincare_quorum
from agents.pipelines.stages.newton_lean4_formalization import run_newton_lean4_formalization

logger = structlog.get_logger(__name__)

# ── Pipeline stages for Rank26Discovery ──────────────────────────────────────

TRACK_A_STAGES = [
    PipelineStage.HYPOTHESIS_GENERATION,    # Stage 1 (Gauss — State of Art)
    PipelineStage.NUMERICAL_SIMULATION,     # Stage 2 (Ramanujan — ALS search)
    PipelineStage.ADVERSARIAL_REVIEW,       # Stage 3 (Poincaré — verification)
    PipelineStage.LEAN4_FORMALIZATION,      # Stage 4 (Newton — formalization)
]

TRACK_B_STAGES = [
    PipelineStage.IMPACT_ASSESSMENT,        # Stage 5 (Gauss — lower bounds)
    PipelineStage.PEER_REVIEW_LOOP,         # Stage 6 (Poincaré — synthesis)
]


@dataclass
class Rank26Config:
    """Configuration for the Rank26Discovery pipeline.

    Attributes:
        output_dir: Directory for journal entries and final report.
        rank_range: (min, max) rank to search via ALS.
        als_restarts: Number of random restarts per rank.
        als_tolerance: ALS convergence tolerance.
        model: Foundation model for all agent calls.
        run_track_b: Whether to also run the lower bound track.
    """
    output_dir: str = "rank26_discovery_output"
    rank_range: tuple = (26, 40)
    als_restarts: int = 50
    als_tolerance: float = 1e-8
    model: str = "gemini-2.5-pro"
    run_track_b: bool = True


class Rank26DiscoveryPipeline(AgentPipeline):
    """Dual-track pipeline for discovering the border rank of ⟨4,4,4⟩.

    Track A (Constructive): ALS numerical witness search + formal verification.
    Track B (Lower Bound): Theoretical lower bound analysis.
    """

    def get_stages(self) -> list[PipelineStage]:
        """Return all 6 pipeline stages."""
        return TRACK_A_STAGES + TRACK_B_STAGES

    async def run(self, config: Any = None) -> PipelineResult:
        """Execute the full Rank26Discovery pipeline.

        Args:
            config: Rank26Config instance (or None for defaults).

        Returns:
            PipelineResult with all stage outputs and the journal path.
        """
        if config is None:
            config = Rank26Config()
        if isinstance(config, dict):
            config = Rank26Config(**config)

        symposium_id = f"rank26_{uuid.uuid4().hex[:8]}"
        logger.info("rank26_pipeline_start", symposium_id=symposium_id)
        t_pipeline_start = time.monotonic()

        # ── Setup output directory ────────────────────────────────────────────
        output_dir = pathlib.Path(config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        journal_entries: list[str] = []
        stages_completed: list[PipelineStage] = []
        warnings: list[str] = []

        def journal_path(stage_n: int) -> str:
            return str(output_dir / f"stage_{stage_n}_journal.md")

        # ── TRACK A ───────────────────────────────────────────────────────────

        # Stage 1: Gauss — State of the Art
        logger.info("rank26_stage1_gauss_start")
        gauss_result: dict[str, Any] = {}
        try:
            gauss_result = await run_gauss_state_of_art(
                topic="border rank of ⟨4,4,4⟩ matrix multiplication tensor and ω",
                journal_path=journal_path(1),
            )
            stages_completed.append(PipelineStage.HYPOTHESIS_GENERATION)
            journal_entries.append(
                f"## Stage 1 — Gauss (State of Art)\n\n"
                f"{gauss_result.get('survey', '')[:3000]}"
            )
            logger.info("rank26_stage1_complete", elapsed_s=gauss_result.get("elapsed_s", 0))
        except Exception as e:
            warnings.append(f"Stage 1 (Gauss) failed: {e}")
            logger.error("rank26_stage1_failed", error=str(e))

        # Stage 2: Ramanujan — ALS Rank Search
        logger.info("rank26_stage2_ramanujan_start")
        ramanujan_result: dict[str, Any] = {}
        try:
            ramanujan_result = await run_ramanujan_rank_search(
                rank_range=config.rank_range,
                restarts=config.als_restarts,
                tolerance=config.als_tolerance,
                journal_path=journal_path(2),
            )
            stages_completed.append(PipelineStage.NUMERICAL_SIMULATION)
            journal_entries.append(
                f"## Stage 2 — Ramanujan (ALS Search)\n\n"
                f"Status: **{ramanujan_result.get('convergence_status', 'UNKNOWN')}**\n"
                f"Best rank: {ramanujan_result.get('best_rank', 'N/A')}\n\n"
                f"{ramanujan_result.get('report', '')[:3000]}"
            )
            logger.info(
                "rank26_stage2_complete",
                convergence=ramanujan_result.get("convergence_status"),
                best_rank=ramanujan_result.get("best_rank"),
            )
        except Exception as e:
            warnings.append(f"Stage 2 (Ramanujan) failed: {e}")
            logger.error("rank26_stage2_failed", error=str(e))

        # Stage 3: Poincaré — Quorum Verification of witness
        logger.info("rank26_stage3_poincare_start")
        poincare_a_result: dict[str, Any] = {}
        if ramanujan_result.get("witness_found"):
            try:
                claim = (
                    f"Ramanujan found a numerical witness showing R̃(⟨4,4,4⟩) ≤ "
                    f"{ramanujan_result.get('best_rank', '?')} over the ε-algebra."
                )
                evidence = ramanujan_result.get("report", "")[:4000]
                poincare_a_result = await run_poincare_quorum(
                    claim=claim,
                    evidence=evidence,
                    context="Track A: constructive witness verification",
                    journal_path=journal_path(3),
                )
                stages_completed.append(PipelineStage.ADVERSARIAL_REVIEW)
                journal_entries.append(
                    f"## Stage 3 — Poincaré (Witness Verification)\n\n"
                    f"Verdict: **{poincare_a_result.get('verdict', 'N/A')}** "
                    f"(confidence: {poincare_a_result.get('confidence', 0):.0%})\n\n"
                    f"Reasoning: {poincare_a_result.get('reasoning', '')[:1500]}"
                )
                logger.info(
                    "rank26_stage3_complete",
                    verdict=poincare_a_result.get("verdict"),
                    confidence=poincare_a_result.get("confidence"),
                )
            except Exception as e:
                warnings.append(f"Stage 3 (Poincaré) failed: {e}")
                logger.error("rank26_stage3_failed", error=str(e))
        else:
            logger.info("rank26_stage3_skipped", reason="no witness found")
            journal_entries.append(
                "## Stage 3 — Poincaré (Witness Verification)\n\n"
                "⏭ **SKIPPED**: No witness found by Ramanujan. "
                "Poincaré quorum not applicable.\n\n"
                f"Ramanujan status: {ramanujan_result.get('convergence_status', 'UNKNOWN')}"
            )

        # Stage 4: Newton — Lean 4 Formalization
        logger.info("rank26_stage4_newton_start")
        newton_result: dict[str, Any] = {}
        try:
            newton_result = await run_newton_lean4_formalization(
                witness_result=ramanujan_result if ramanujan_result else None,
                quorum_result=poincare_a_result if poincare_a_result else None,
                gauss_survey=gauss_result.get("survey", ""),
                journal_path=journal_path(4),
            )
            stages_completed.append(PipelineStage.LEAN4_FORMALIZATION)
            lean_snippet = newton_result.get("lean_code", "")[:2000]
            journal_entries.append(
                f"## Stage 4 — Newton (Lean 4 Formalization)\n\n"
                f"Mode: **{newton_result.get('mode', 'N/A')}**\n"
                f"Sorry count: {newton_result.get('sorry_count', 0)}\n"
                f"Output: `{newton_result.get('output_path', 'N/A')}`\n\n"
                f"```lean4\n{lean_snippet}\n```"
            )
            logger.info(
                "rank26_stage4_complete",
                mode=newton_result.get("mode"),
                sorry=newton_result.get("sorry_count"),
            )
        except Exception as e:
            warnings.append(f"Stage 4 (Newton) failed: {e}")
            logger.error("rank26_stage4_failed", error=str(e))

        # ── TRACK B ───────────────────────────────────────────────────────────

        if config.run_track_b:
            # Stage 5: Gauss — Lower Bound Analysis
            logger.info("rank26_stage5_gauss_lb_start")
            gauss_lb_result: dict[str, Any] = {}
            try:
                gauss_lb_result = await run_gauss_state_of_art(
                    topic=(
                        "lower bounds for bilinear complexity and tensor rank: "
                        "Bläser (2003), Shpilka-Wigderson (2001), "
                        "and implications for R(⟨4,4,4⟩)"
                    ),
                    journal_path=journal_path(5),
                )
                stages_completed.append(PipelineStage.IMPACT_ASSESSMENT)
                journal_entries.append(
                    f"## Stage 5 — Gauss (Lower Bound Analysis)\n\n"
                    f"{gauss_lb_result.get('survey', '')[:3000]}"
                )
                logger.info(
                    "rank26_stage5_complete",
                    elapsed_s=gauss_lb_result.get("elapsed_s"),
                )
            except Exception as e:
                warnings.append(f"Stage 5 (Gauss LB) failed: {e}")
                logger.error("rank26_stage5_failed", error=str(e))

            # Stage 6: Poincaré — Synthesize Track A + Track B
            logger.info("rank26_stage6_poincare_synthesis_start")
            track_a_summary = _build_track_a_summary(
                ramanujan_result, poincare_a_result, newton_result
            )
            track_b_summary = gauss_lb_result.get(
                "survey", "No lower bound survey available."
            )
            try:
                final_claim = textwrap.dedent(f"""\
                    COMBINED ANALYSIS: What do Track A and Track B together tell us
                    about R̃(⟨4,4,4⟩) and the matrix multiplication exponent ω?

                    Track A (Constructive): {track_a_summary}
                    Track B (Lower Bounds): {track_b_summary[:2000]}
                """)
                poincare_final = await run_poincare_quorum(
                    claim=final_claim,
                    evidence=gauss_result.get("survey", "")[:2000],
                    context="Final synthesis: Track A + Track B combined conclusion",
                    journal_path=journal_path(6),
                )
                stages_completed.append(PipelineStage.PEER_REVIEW_LOOP)
                journal_entries.append(
                    f"## Stage 6 — Poincaré (Final Synthesis)\n\n"
                    f"Verdict: **{poincare_final.get('verdict', 'N/A')}** "
                    f"(confidence: {poincare_final.get('confidence', 0):.0%})\n\n"
                    f"{poincare_final.get('reasoning', '')[:2000]}"
                )
                logger.info(
                    "rank26_stage6_complete",
                    verdict=poincare_final.get("verdict"),
                    confidence=poincare_final.get("confidence"),
                )
            except Exception as e:
                warnings.append(f"Stage 6 (Poincaré synthesis) failed: {e}")
                logger.error("rank26_stage6_failed", error=str(e))

        # ── Final Report ──────────────────────────────────────────────────────
        total_duration = time.monotonic() - t_pipeline_start
        report_path = _write_final_report(
            output_dir=output_dir,
            symposium_id=symposium_id,
            journal_entries=journal_entries,
            stages_completed=stages_completed,
            warnings=warnings,
            duration_s=total_duration,
            ramanujan_result=ramanujan_result,
            poincare_a_result=poincare_a_result,
            newton_result=newton_result,
        )

        logger.info(
            "rank26_pipeline_complete",
            symposium_id=symposium_id,
            stages=len(stages_completed),
            warnings=len(warnings),
            duration_s=round(total_duration, 1),
            report=report_path,
        )

        return PipelineResult(
            symposium_id=symposium_id,
            stages_completed=stages_completed,
            total_duration_s=total_duration,
            pdf_path="",
            tex_path="",
            audit_trail_path=report_path,
            hypotheses_count=1,
            warnings=warnings,
        )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _build_track_a_summary(
    ramanujan: dict[str, Any],
    poincare: dict[str, Any],
    newton: dict[str, Any],
) -> str:
    """Build a text summary of Track A results."""
    status = ramanujan.get("convergence_status", "NOT_RUN")
    best_rank = ramanujan.get("best_rank", "N/A")
    verdict = poincare.get("verdict", "N/A") if poincare else "NOT_VERIFIED"
    lean_mode = newton.get("mode", "N/A") if newton else "NOT_FORMALIZED"
    return (
        f"ALS search status={status}, best_rank={best_rank}. "
        f"Quorum verdict={verdict}. Lean 4 mode={lean_mode}."
    )


def _write_final_report(
    output_dir: pathlib.Path,
    symposium_id: str,
    journal_entries: list[str],
    stages_completed: list[PipelineStage],
    warnings: list[str],
    duration_s: float,
    ramanujan_result: dict[str, Any],
    poincare_a_result: dict[str, Any],
    newton_result: dict[str, Any],
) -> str:
    """Write the final rank26_discovery_report.md."""
    from datetime import datetime, timezone
    report_path = output_dir / "rank26_discovery_report.md"

    witness_status = ramanujan_result.get("convergence_status", "NOT_RUN")
    best_rank = ramanujan_result.get("best_rank", "N/A")
    quorum_verdict = poincare_a_result.get("verdict", "N/A") if poincare_a_result else "N/A"
    lean_mode = newton_result.get("mode", "N/A") if newton_result else "N/A"
    lean_path = newton_result.get("output_path", "N/A") if newton_result else "N/A"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    successes = _summarise_successes(ramanujan_result, poincare_a_result, newton_result)
    failures = _summarise_failures(warnings, ramanujan_result)
    next_steps = _propose_next_steps(witness_status, best_rank, quorum_verdict)
    warning_block = "\n".join(f"- {w}" for w in warnings) if warnings else "(none)"
    journal_block = "\n\n---\n\n".join(journal_entries)

    content = textwrap.dedent(f"""\
        # Rank26Discovery Pipeline — Final Report

        **Symposium ID**: `{symposium_id}`
        **Stages completed**: {len(stages_completed)}/6
        **Duration**: {duration_s:.1f}s
        **Date**: {timestamp}

        ---

        ## Executive Summary

        | Metric | Value |
        |--------|-------|
        | ALS Search Status | {witness_status} |
        | Best Rank Found | {best_rank} |
        | Quorum Verdict | {quorum_verdict} |
        | Lean 4 Mode | {lean_mode} |
        | Lean 4 Output | `{lean_path}` |

        ---

        ## Learning Journal

        {journal_block}

        ---

        ## What Worked

        {successes}

        ## What Failed

        {failures}

        ## Why and Next Steps

        {next_steps}

        ---

        ## Warnings / Errors

        {warning_block}

        ---

        *Generated by Rank26Discovery Pipeline — Agora v4.1*
        *Patent: US-PAT-PEND-2026-0525*
    """)

    report_path.write_text(content, encoding="utf-8")
    logger.info("rank26_final_report_written", path=str(report_path))
    return str(report_path)


def _summarise_successes(
    ramanujan: dict[str, Any],
    poincare: dict[str, Any],
    newton: dict[str, Any],
) -> str:
    items = []
    if ramanujan.get("convergence_status") == "WITNESS_FOUND":
        items.append(f"✅ Ramanujan found witness at rank {ramanujan.get('best_rank')}")
    elif ramanujan.get("convergence_status") == "PARTIAL_PROGRESS":
        items.append(f"🔄 Ramanujan partial progress: best rank {ramanujan.get('best_rank', 'N/A')}")
    if poincare.get("verdict") == "ACCEPT":
        items.append("✅ Poincaré quorum accepted the witness")
    if newton.get("lean_code"):
        items.append(f"✅ Newton produced Lean 4 code ({newton.get('mode')})")
    return "\n".join(items) if items else "(No clear successes — see warnings)"


def _summarise_failures(warnings: list[str], ramanujan: dict[str, Any]) -> str:
    items = []
    if ramanujan.get("convergence_status") == "FAILED_TO_CONVERGE":
        items.append("❌ ALS search failed to converge — no witness found")
    items.extend(f"❌ {w}" for w in warnings)
    return "\n".join(items) if items else "(No failures recorded)"


def _propose_next_steps(
    convergence_status: str,
    best_rank: Any,
    quorum_verdict: str,
) -> str:
    if convergence_status == "WITNESS_FOUND" and quorum_verdict == "ACCEPT":
        return textwrap.dedent("""\
            1. Submit Lean 4 proof to Mathlib4 PR review
            2. Run independent numerical verification (SageMath/Python)
            3. Write up result as preprint (arXiv)
            4. Compute improved ω bound via τ-theorem
        """)
    elif convergence_status == "PARTIAL_PROGRESS":
        return textwrap.dedent(f"""\
            1. Increase ALS restarts (current: 50 → try 200)
            2. Try SGSD as alternative to ALS
            3. Explore structured initialisations (Smirnov's 49-term decomposition)
            4. Best rank so far: {best_rank} — document as partial result
            5. Investigate lower bounds: is rank {best_rank} tight?
        """)
    else:
        return textwrap.dedent("""\
            1. Check tensor parameterisation over ε-algebra
            2. Try exact arithmetic (ℚ) instead of floating point
            3. Consult Bläser lower bounds: is rank 26 geometrically impossible?
            4. Revisit KalPhaseWeight claim — may need deeper algebraic analysis
            5. Consider approaching via border rank complexity theory (Bürgisser et al.)
        """)
