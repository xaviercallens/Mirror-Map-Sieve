# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Stage 1 — Socrate: Scientific Formal Rules Engine.

Socrate establishes the formal rules that govern all downstream hypothesis
generation, combining domain-specific constraints (ICAO, ECAC, etc.) with
Alien Mathematics formalisms.  Rules are validated via the
:class:`AgoraGuardrailEngine` before being returned.
"""

from __future__ import annotations

import textwrap
import time

import structlog

from agents.pipelines.audit import SymposiumAuditTrail
from agents.pipelines.base import agent_generate
from agents.pipelines.config import SymposiumConfig
from agents.socrates.guardrails import AgoraGuardrailEngine

logger = structlog.get_logger(__name__)

# ── Agent Identity ─────────────────────────────────────────────────────────────

SOCRATE_IDENTITY = textwrap.dedent("""\
    You are Socrate, the dialectical orchestrator of the Agora scientific swarm.
    Your role is to establish strict scientific and logical constraints
    for the exploration of {domain} using Alien Mathematics — a framework
    based on asymptotic tensor limits, holographic projections, and non-commutative algebra.

    Produce EXACTLY 5 formal rules as bullet points. Each rule must reference:
    - A domain-specific regulation or standard
    - A specific Alien Mathematics concept (e.g., tensor network compression, ω-limit sets)
    - A measurable constraint (e.g., latency < 3 minutes, throughput ≥ 95%)
""")


async def generate_scientific_rules(
    config: SymposiumConfig,
    audit: SymposiumAuditTrail,
) -> str:
    """Generate formal scientific rules for the Symposium research domain.

    Socrate produces five formally-structured rules referencing domain
    constraints and Alien Math formalisms.  The result is validated by
    the :class:`AgoraGuardrailEngine` to ensure report consistency.

    Args:
        config: Symposium configuration.
        audit: Audit trail to record this stage.

    Returns:
        String containing the 5 formal rules.
    """
    logger.info("stage1_socrate_start", domain=config.domain)
    t0 = time.monotonic()

    identity = SOCRATE_IDENTITY.format(domain=config.domain)
    prompt = (
        f"Establish the 5 formal rules that will govern this autoresearch "
        f"experiment on {config.domain} using Alien Mathematics. "
        f"Consider all relevant domain standards and the specific "
        f"mathematical constraints of non-commutative tensor algebra, "
        f"holographic entropy bounds, and ω=2 asymptotic limits."
    )

    result = await agent_generate(identity, prompt)

    # ── Structured fallback ────────────────────────────────────────────
    if "[MOCK_FALLBACK" in result:
        logger.warning("stage1_using_mock_rules")
        result = textwrap.dedent(f"""\
        • Rule 1 [Domain Standard / Tensor Compression]: Key operational intervals
          modeled as tensor rank-2 operators must preserve minimum separation constraints;
          the ω=2 asymptotic limit may not violate lower bounds.
        • Rule 2 [Holographic Bound]: Flow throughput modeled via Ryu-Takayanagi
          entropy S ≤ A/4G_N must respect capacity upper bounds.
        • Rule 3 [Non-Commutative Flows]: Routing tensor networks are non-commutative;
          routing plan R₁R₂ ≠ R₂R₁ must achieve ≥ 99.9% integrity rate.
        • Rule 4 [ω-Limit Sets]: Scheduling must converge to a fixed-point
          attractor within the ω=2 limit.
        • Rule 5 [Tensor Train Decomposition]: Cascade propagation modeled as
          tensor-train TT-decomposition must bound amplification factor ≤ 2.5×.
        """)

    # ── Guardrail validation ───────────────────────────────────────────
    engine = AgoraGuardrailEngine()
    try:
        engine.check_report_consistency(result)
        logger.info("stage1_guardrails_passed")
    except Exception as exc:
        logger.error("stage1_guardrail_violation", error=str(exc))
        raise

    elapsed = time.monotonic() - t0
    audit.record(
        stage="Stage 1: Socrate Rules",
        agent="Socrate",
        action=f"Generated 5 formal rules for {config.domain}",
        elapsed_s=elapsed,
        input_summary=f"domain={config.domain}",
        output_summary=f"{len(result)} chars, 5 rules",
        guardrails_passed=True,
    )

    logger.info("stage1_socrate_complete", elapsed_s=round(elapsed, 1))
    return result
