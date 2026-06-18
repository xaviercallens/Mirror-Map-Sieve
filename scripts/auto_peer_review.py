#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Automated 5-iteration peer review loop.

Runs a multi-agent peer review where:
  1. Galileo submits a scientific claim with evidence
  2. Euler reviews the claim (formal verification + skeptical audit)
  3. Galileo addresses objections with refined evidence
  4. Repeat for 5 iterations or until convergence
  5. Socrates produces a final synthesis

This simulates the scientific peer review process using the
Agora's dialectic framework, ensuring claims are rigorously tested.

Usage::

    python scripts/auto_peer_review.py \
        --claim "Robertson kinetics conserves mass" \
        --iterations 5 \
        --output review_report.json

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.galileo.agent import GalileoAgent
from agents.euler.agent import EulerAgent
from agents.common.budget_guard import BudgetGuard

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Review data types
# ---------------------------------------------------------------------------

@dataclass
class ReviewRound:
    """A single round of peer review.

    Attributes:
        round_number: 1-indexed review round.
        submission: Galileo's claim/evidence.
        review: Euler's critique.
        galileo_confidence: Galileo's confidence after this round.
        euler_confidence: Euler's confidence after this round.
        objections: List of specific objections raised.
        resolved_objections: Objections addressed from previous round.
        cost_usd: Cost of this round.
        elapsed_ms: Time taken for this round.
    """

    round_number: int = 0
    submission: dict[str, Any] = field(default_factory=dict)
    review: dict[str, Any] = field(default_factory=dict)
    galileo_confidence: float = 0.0
    euler_confidence: float = 0.0
    objections: list[str] = field(default_factory=list)
    resolved_objections: list[str] = field(default_factory=list)
    cost_usd: float = 0.0
    elapsed_ms: float = 0.0


@dataclass
class PeerReviewReport:
    """Complete peer review report.

    Attributes:
        claim: The original scientific claim.
        timestamp: ISO-format timestamp.
        total_rounds: Number of review rounds completed.
        converged: Whether the review converged.
        final_verdict: ACCEPTED / REJECTED / REVISE.
        final_confidence: Aggregated confidence.
        total_cost_usd: Cumulative cost of the review process.
        rounds: Per-round details.
        synthesis: Final narrative synthesis.
    """

    claim: str = ""
    timestamp: str = ""
    total_rounds: int = 0
    converged: bool = False
    final_verdict: str = "PENDING"
    final_confidence: float = 0.0
    total_cost_usd: float = 0.0
    rounds: list[ReviewRound] = field(default_factory=list)
    synthesis: str = ""


# ---------------------------------------------------------------------------
# Review engine
# ---------------------------------------------------------------------------

async def run_peer_review(
    claim: str,
    max_iterations: int = 5,
    convergence_threshold: float = 0.85,
) -> PeerReviewReport:
    """Run an automated peer review loop.

    Args:
        claim: Scientific claim to review.
        max_iterations: Maximum number of review rounds.
        convergence_threshold: Confidence threshold for acceptance.

    Returns:
        :class:`PeerReviewReport`.
    """
    logger.info("peer_review_start", claim=claim[:100], iterations=max_iterations)

    galileo = GalileoAgent()
    euler = EulerAgent()
    budget = BudgetGuard(experiment_limit=100.0, project_limit=500.0)

    report = PeerReviewReport(
        claim=claim,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    prev_objections: list[str] = []

    for i in range(1, max_iterations + 1):
        round_start = time.monotonic()
        logger.info("review_round_start", round=i)

        # ---- Galileo: Submit / Revise ----
        if i == 1:
            submission_query = f"Present evidence for: {claim}"
        else:
            objection_text = "; ".join(prev_objections) if prev_objections else "none"
            submission_query = (
                f"Address these objections to your claim '{claim}': "
                f"{objection_text}. Provide stronger evidence."
            )

        galileo_result = await galileo.run(submission_query)

        # ---- Euler: Review ----
        review_query = (
            f"Critically review this scientific claim: '{claim}'. "
            f"Evidence provided (round {i}): {galileo_result.answer}. "
            f"Find flaws, logical gaps, and numerical issues."
        )
        euler_result = await euler.run(review_query)

        # Extract objections
        current_objections: list[str] = []
        if isinstance(euler_result.answer, dict):
            current_objections = euler_result.answer.get("objections", [])

        # Determine which previous objections were resolved
        resolved = [
            obj for obj in prev_objections
            if obj not in current_objections
        ]

        round_elapsed = (time.monotonic() - round_start) * 1000
        round_cost = galileo_result.cost_usd + euler_result.cost_usd
        budget.record_cost(round_cost)

        review_round = ReviewRound(
            round_number=i,
            submission={
                "answer": str(galileo_result.answer)[:500],
                "confidence": galileo_result.confidence,
            },
            review={
                "answer": str(euler_result.answer)[:500],
                "confidence": euler_result.confidence,
            },
            galileo_confidence=galileo_result.confidence,
            euler_confidence=euler_result.confidence,
            objections=current_objections,
            resolved_objections=resolved,
            cost_usd=round(round_cost, 4),
            elapsed_ms=round(round_elapsed, 2),
        )
        report.rounds.append(review_round)

        logger.info(
            "review_round_complete",
            round=i,
            galileo_conf=galileo_result.confidence,
            euler_conf=euler_result.confidence,
            objections=len(current_objections),
            cost=round_cost,
        )

        # Print progress
        print(
            f"  Round {i}: Galileo={galileo_result.confidence:.2f} "
            f"Euler={euler_result.confidence:.2f} "
            f"Objections={len(current_objections)} "
            f"Cost=${round_cost:.2f}"
        )

        # ---- Convergence check ----
        avg_confidence = (galileo_result.confidence + euler_result.confidence) / 2
        if avg_confidence >= convergence_threshold and not current_objections:
            report.converged = True
            report.final_verdict = "ACCEPTED"
            break

        if euler_result.confidence < 0.1:
            report.final_verdict = "REJECTED"
            break

        prev_objections = current_objections

    # ---- Final synthesis ----
    report.total_rounds = len(report.rounds)
    report.total_cost_usd = round(budget.cumulative_cost, 4)

    if report.rounds:
        last = report.rounds[-1]
        report.final_confidence = round(
            (last.galileo_confidence + last.euler_confidence) / 2, 2,
        )

    if not report.converged and report.final_verdict == "PENDING":
        report.final_verdict = "REVISE"

    report.synthesis = (
        f"Peer review of '{claim}' completed after {report.total_rounds} "
        f"round(s). Verdict: {report.final_verdict}. "
        f"Final confidence: {report.final_confidence:.2f}. "
        f"Total cost: ${report.total_cost_usd:.2f}."
    )

    logger.info(
        "peer_review_complete",
        verdict=report.final_verdict,
        rounds=report.total_rounds,
        confidence=report.final_confidence,
        cost=report.total_cost_usd,
    )

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

async def async_main(args: argparse.Namespace) -> None:
    """Async main entry point.

    Args:
        args: Parsed CLI arguments.
    """
    print("=" * 60)
    print("SocrateAI Agora — Automated Peer Review")
    print("=" * 60)
    print(f"\n  Claim: {args.claim}")
    print(f"  Max iterations: {args.iterations}")
    print()

    report = await run_peer_review(
        claim=args.claim,
        max_iterations=args.iterations,
    )

    print(f"\n{'=' * 60}")
    print(f"VERDICT: {report.final_verdict}")
    print(f"Confidence: {report.final_confidence}")
    print(f"Rounds: {report.total_rounds}")
    print(f"Cost: ${report.total_cost_usd:.2f}")
    print(f"{'=' * 60}")

    # Save report
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(
            json.dumps(asdict(report), indent=2, default=str),
            encoding="utf-8",
        )
        print(f"\nReport saved: {output_path}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="SocrateAI Automated Peer Review",
    )
    parser.add_argument(
        "--claim",
        type=str,
        default="The Robertson chemical kinetics ODE system conserves total mass",
        help="Scientific claim to review",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="Maximum review iterations",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="peer_review_report.json",
        help="Output file for the review report",
    )
    args = parser.parse_args()

    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
