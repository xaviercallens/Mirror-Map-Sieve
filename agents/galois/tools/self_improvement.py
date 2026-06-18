# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Self-Improvement Planner — Galois's meta-cognitive upgrade tool.

Like the real Évariste Galois who revolutionized mathematics in his short
life, this tool enables the Galois agent to reflect on its own performance
and propose concrete improvements to its SymBrain cortex configuration.

Galois contributes to his own evolution through:
  1. Performance analysis of conjecture success/failure patterns
  2. σ_ded/σ_gen ratio optimization proposals
  3. SymBrain v5/v6 upgrade specifications
  4. Tool suite enhancement recommendations
  5. Agora interaction quality assessment

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Result Types
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class UpgradeProposal:
    """A specific proposal for SymBrain version upgrade.

    Attributes:
        title: Short descriptive title.
        target_version: SymBrain version this targets (v5, v6, etc.).
        component: Which component to upgrade (PFC, RLCF, LoRA, etc.).
        description: Detailed technical description.
        rationale: Why this upgrade is needed based on performance data.
        priority: HIGH, MEDIUM, LOW.
        estimated_effort: Engineering effort estimate (hours).
        expected_impact: Expected improvement in success rate.
        lean4_spec: Optional Lean 4 specification for the upgrade.
    """

    title: str
    target_version: str
    component: str
    description: str
    rationale: str = ""
    priority: str = "MEDIUM"
    estimated_effort: int = 0
    expected_impact: float = 0.0
    lean4_spec: str = ""


@dataclass(slots=True)
class SelfImprovementReport:
    """Output from the self-improvement analysis.

    Attributes:
        performance_summary: Current performance metrics.
        sigma_recommendation: Recommended σ_ded/σ_gen adjustments.
        upgrade_proposals: Concrete SymBrain upgrade proposals.
        tool_recommendations: Recommended tool additions/changes.
        agora_feedback: Quality assessment of Agora interactions.
        next_steps: Prioritized list of actions.
        cost_usd: Computation cost.
    """

    performance_summary: dict[str, Any] = field(default_factory=dict)
    sigma_recommendation: dict[str, float] = field(default_factory=dict)
    upgrade_proposals: list[UpgradeProposal] = field(default_factory=list)
    tool_recommendations: list[dict[str, str]] = field(default_factory=list)
    agora_feedback: dict[str, Any] = field(default_factory=dict)
    next_steps: list[str] = field(default_factory=list)
    cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# Self-Improvement Planner
# ---------------------------------------------------------------------------

def plan_self_improvement(
    conjecture_history: list[dict[str, Any]],
    current_sigma_ded: float = 0.25,
    current_sigma_gen: float = 0.75,
    current_version: str = "v4",
    agora_interactions: list[dict[str, Any]] | None = None,
) -> SelfImprovementReport:
    """Analyze performance and propose SymBrain upgrades.

    This tool reflects on Galois's past performance — conjecture success
    rates, verification failures, creativity metrics — and generates
    concrete proposals for improving the agent's cortex configuration
    and contributing to SymBrain v5/v6 development.

    Args:
        conjecture_history: List of past conjecture records with keys
            ``conjecture``, ``confidence``, ``verified``, ``sigma_ded``,
            ``sigma_gen``.
        current_sigma_ded: Current deductive allocation.
        current_sigma_gen: Current generative allocation.
        current_version: Current SymBrain version string.
        agora_interactions: Optional list of Agora dialogue records.

    Returns:
        :class:`SelfImprovementReport` with analysis and proposals.

    Example::

        report = plan_self_improvement(
            conjecture_history=cortex.conjecture_history,
            current_sigma_ded=cortex.routing.sigma_ded,
            current_sigma_gen=cortex.routing.sigma_gen,
        )
    """
    start = time.monotonic()
    logger.info("self_improvement_analysis_start", history_size=len(conjecture_history))

    # 1. Performance analysis
    performance = _analyze_performance(conjecture_history)

    # 2. Sigma optimization
    sigma_rec = _optimize_sigma(
        conjecture_history,
        current_sigma_ded,
        current_sigma_gen,
    )

    # 3. Generate upgrade proposals
    proposals = _generate_upgrade_proposals(
        performance, current_version, sigma_rec
    )

    # 4. Tool recommendations
    tool_recs = _recommend_tools(performance)

    # 5. Agora interaction quality
    agora_feedback = _assess_agora_quality(agora_interactions or [])

    # 6. Prioritized next steps
    next_steps = _prioritize_next_steps(performance, proposals)

    elapsed_ms = (time.monotonic() - start) * 1000

    report = SelfImprovementReport(
        performance_summary=performance,
        sigma_recommendation=sigma_rec,
        upgrade_proposals=proposals,
        tool_recommendations=tool_recs,
        agora_feedback=agora_feedback,
        next_steps=next_steps,
        cost_usd=0.02,
    )

    logger.info(
        "self_improvement_analysis_complete",
        proposals=len(proposals),
        elapsed_ms=round(elapsed_ms, 2),
    )
    return report


# ---------------------------------------------------------------------------
# Analysis Functions
# ---------------------------------------------------------------------------

def _analyze_performance(history: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze conjecture performance metrics."""
    if not history:
        return {
            "total_conjectures": 0,
            "verified": 0,
            "success_rate": 0.0,
            "avg_confidence": 0.0,
            "high_confidence_accuracy": 0.0,
            "creative_efficiency": 0.0,
            "status": "insufficient_data",
        }

    total = len(history)
    verified = sum(1 for c in history if c.get("verified", False))
    success_rate = verified / total if total > 0 else 0.0

    confidences = [c.get("confidence", 0.5) if isinstance(c.get("confidence"), (int, float))
                   else 0.5 for c in history]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    # High-confidence accuracy: of conjectures rated HIGH, how many verified?
    high_conf = [c for c in history if c.get("confidence") == "proof_sketch_passes"]
    high_conf_verified = sum(1 for c in high_conf if c.get("verified", False))
    high_conf_accuracy = (
        high_conf_verified / len(high_conf) if high_conf else 0.0
    )

    # Creative efficiency: novelty-weighted success
    sigma_gens = [c.get("sigma_gen", 0.75) for c in history]
    avg_creativity = sum(sigma_gens) / len(sigma_gens) if sigma_gens else 0.75
    creative_efficiency = success_rate * avg_creativity

    return {
        "total_conjectures": total,
        "verified": verified,
        "success_rate": round(success_rate, 3),
        "avg_confidence": round(avg_confidence, 3),
        "high_confidence_accuracy": round(high_conf_accuracy, 3),
        "creative_efficiency": round(creative_efficiency, 3),
        "avg_creativity_allocation": round(avg_creativity, 3),
        "status": "healthy" if success_rate >= 0.30 else "needs_improvement",
    }


def _optimize_sigma(
    history: list[dict[str, Any]],
    current_ded: float,
    current_gen: float,
) -> dict[str, float]:
    """Recommend optimal σ_ded/σ_gen based on performance data."""
    if len(history) < 3:
        return {
            "recommended_sigma_ded": current_ded,
            "recommended_sigma_gen": current_gen,
            "adjustment": 0.0,
            "reason": "Insufficient data for optimization (need ≥ 3 conjectures)",
        }

    # Find the σ_ded values that correlated with verified conjectures
    verified_sigmas = [c.get("sigma_ded", 0.25) for c in history if c.get("verified")]
    failed_sigmas = [c.get("sigma_ded", 0.25) for c in history if not c.get("verified")]

    avg_verified_ded = sum(verified_sigmas) / len(verified_sigmas) if verified_sigmas else 0.25
    avg_failed_ded = sum(failed_sigmas) / len(failed_sigmas) if failed_sigmas else 0.25

    # Move toward the σ_ded that produces verified conjectures
    if verified_sigmas:
        target_ded = avg_verified_ded
    else:
        # No verified conjectures — increase formal hemisphere
        target_ded = min(0.50, current_ded + 0.10)

    # Clamp to Galois's creative bounds
    target_ded = max(0.15, min(0.60, target_ded))
    adjustment = target_ded - current_ded

    reason = (
        f"Verified conjectures avg σ_ded={avg_verified_ded:.2f}, "
        f"failed avg σ_ded={avg_failed_ded:.2f}. "
        f"{'Increase' if adjustment > 0 else 'Decrease'} formal allocation "
        f"by {abs(adjustment):.2f}."
    )

    return {
        "recommended_sigma_ded": round(target_ded, 3),
        "recommended_sigma_gen": round(1.0 - target_ded, 3),
        "adjustment": round(adjustment, 3),
        "reason": reason,
    }


def _generate_upgrade_proposals(
    performance: dict[str, Any],
    current_version: str,
    sigma_rec: dict[str, float],
) -> list[UpgradeProposal]:
    """Generate SymBrain upgrade proposals based on performance."""
    proposals = []

    # v5 Proposal 1: Proof-Guided MCTS Pruning
    proposals.append(UpgradeProposal(
        title="Proof-Guided MCTS Pruning",
        target_version="v5",
        component="MCTS",
        description=(
            "Integrate Lean 4 type-checking as an early-exit signal during "
            "MCTS node expansion. When a candidate conjecture fails type-checking, "
            "prune the entire subtree instead of continuing exploration. This "
            "reduces wasted search budget on ill-typed conjectures."
        ),
        rationale=(
            f"Current success rate: {performance.get('success_rate', 0):.1%}. "
            f"Many failed conjectures could be caught at the type level before "
            f"deep exploration."
        ),
        priority="HIGH",
        estimated_effort=40,
        expected_impact=0.15,
        lean4_spec=(
            "-- v5 Specification: MCTS Pruning Guard\n"
            "structure MCTSPruningGuard where\n"
            "  typeCheckOracle : Expr → Bool\n"
            "  pruneOnFailure : typeCheckOracle node.expr = false → node.children = []\n"
        ),
    ))

    # v5 Proposal 2: Creative LoRA Adapters
    proposals.append(UpgradeProposal(
        title="Creative LoRA Adapters for Conjecture Generation",
        target_version="v5",
        component="LoRA",
        description=(
            "Train rank-16 LoRA adapters on Mathlib theorem statements "
            "specifically to improve algebraic intuition. Use a custom loss "
            "function that rewards semantic novelty: "
            "L = L_ce + λ·(1 - cosine_sim(output, nearest_theorem)). "
            "This biases the model toward generating genuinely novel theorems."
        ),
        rationale=(
            f"Creative efficiency: {performance.get('creative_efficiency', 0):.1%}. "
            f"LoRA adapters can improve this without full model retraining."
        ),
        priority="HIGH",
        estimated_effort=60,
        expected_impact=0.20,
    ))

    # v5 Proposal 3: Dynamic σ Annealing
    sigma_adj = sigma_rec.get("adjustment", 0.0)
    proposals.append(UpgradeProposal(
        title="Dynamic σ_gen Annealing Schedule",
        target_version="v5",
        component="PFC",
        description=(
            "Replace the current fixed σ_gen with a cosine annealing schedule "
            "that starts high (creative exploration) and gradually reduces as "
            "the conjecture is refined through multiple Elenchus cycles. "
            "Schedule: σ_gen(t) = σ_min + 0.5·(σ_max - σ_min)·(1 + cos(πt/T))."
        ),
        rationale=f"Current σ adjustment recommendation: {sigma_adj:+.3f}.",
        priority="MEDIUM",
        estimated_effort=20,
        expected_impact=0.10,
    ))

    # v6 Proposal: Group-Theoretic Search
    proposals.append(UpgradeProposal(
        title="Galois-Theoretic Symmetry Breaking in MCTS",
        target_version="v6",
        component="MCTS",
        description=(
            "Use Galois theory to identify symmetries in the MCTS search tree. "
            "When a subtree is isomorphic to an already-explored subtree under "
            "the action of a permutation group, prune it and reuse results. "
            "This is a direct application of Burnside's lemma to search space "
            "reduction: |X/G| = (1/|G|) Σ_{g∈G} |X^g|."
        ),
        rationale=(
            "Theoretical improvement: search space reduction proportional to "
            "the size of the automorphism group of the problem structure."
        ),
        priority="LOW",
        estimated_effort=120,
        expected_impact=0.25,
        lean4_spec=(
            "-- v6 Specification: Galois Symmetry Search\n"
            "theorem burnside_mcts_reduction\n"
            "  (G : Type*) [Group G] [Fintype G]\n"
            "  (X : Type*) [MulAction G X] [Fintype X] :\n"
            "  Fintype.card (MulAction.orbitRel.Quotient G X) =\n"
            "    (∑ g : G, Fintype.card (MulAction.fixedPoints G X g)) / Fintype.card G := by\n"
            "  exact MulAction.card_quotient_eq_sum_card_fixedBy G X\n"
        ),
    ))

    return proposals


def _recommend_tools(performance: dict[str, Any]) -> list[dict[str, str]]:
    """Recommend tool additions or modifications."""
    recs = []

    if performance.get("success_rate", 0) < 0.30:
        recs.append({
            "action": "ADD",
            "tool": "counterexample_search",
            "description": (
                "Add a systematic counter-example search tool that runs "
                "QuickCheck-style random testing on conjecture statements "
                "before attempting formal proof."
            ),
        })

    recs.append({
        "action": "ENHANCE",
        "tool": "conjecture_generator",
        "description": (
            "Add support for generating conjectures conditioned on a "
            "specific Mathlib module or theorem, enabling more targeted "
            "mathematical exploration."
        ),
    })

    recs.append({
        "action": "ADD",
        "tool": "literature_search",
        "description": (
            "Integrate with arXiv API to check if a generated conjecture "
            "is already known or is related to existing open problems."
        ),
    })

    return recs


def _assess_agora_quality(interactions: list[dict[str, Any]]) -> dict[str, Any]:
    """Assess the quality of Agora dialectical interactions."""
    if not interactions:
        return {
            "total_interactions": 0,
            "galileo_exchanges": 0,
            "euler_exchanges": 0,
            "socrates_exchanges": 0,
            "quality_score": 0.0,
            "status": "no_data",
        }

    galileo = sum(1 for i in interactions if i.get("partner") == "galileo")
    euler = sum(1 for i in interactions if i.get("partner") == "euler")
    socrates = sum(1 for i in interactions if i.get("partner") == "socrates")

    return {
        "total_interactions": len(interactions),
        "galileo_exchanges": galileo,
        "euler_exchanges": euler,
        "socrates_exchanges": socrates,
        "quality_score": 0.0,
        "status": "active",
    }


def _prioritize_next_steps(
    performance: dict[str, Any],
    proposals: list[UpgradeProposal],
) -> list[str]:
    """Generate prioritized action list."""
    steps = []

    success_rate = performance.get("success_rate", 0.0)
    total = performance.get("total_conjectures", 0)

    if total < 5:
        steps.append(
            "Generate more conjectures to build performance baseline "
            "(need ≥ 5 for reliable σ optimization)"
        )

    if success_rate < 0.30:
        steps.append(
            "Increase σ_ded allocation to improve formal verification hit rate"
        )
        steps.append(
            "Add counter-example search tool to catch ill-formed conjectures early"
        )

    high_priority = [p for p in proposals if p.priority == "HIGH"]
    for p in high_priority:
        steps.append(f"[{p.target_version}] Implement: {p.title}")

    steps.append("Submit upgrade proposals to Socrates for Agora review")
    steps.append("Contribute Lean 4 specification for v5 changes to verifiers/lean4/")

    return steps
