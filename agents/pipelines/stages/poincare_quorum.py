# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Stage: Poincaré — 3-Agent Quorum Verification.

Poincaré runs three independent agent perspectives on a mathematical claim
and synthesizes a consensus verdict. Named after Henri Poincaré for his
ability to hold multiple geometric perspectives simultaneously.

Quorum structure:
  - Skeptic: challenges the claim with the strongest counter-arguments
  - Advocate: defends the claim with the best available evidence
  - Judge: synthesizes a neutral, well-reasoned verdict

Output: {verdict: ACCEPT|REJECT|NEEDS_WORK, confidence: float, ...}

This stage is designed as a learning tool — even when the verdict is clear,
articulating both sides deepens understanding of the mathematical question.
"""

from __future__ import annotations

import asyncio
import textwrap
from typing import Any

import structlog

from agents.pipelines.base import agent_generate

logger = structlog.get_logger(__name__)

# ── Agent Identities ─────────────────────────────────────────────────────────

SKEPTIC_IDENTITY = textwrap.dedent("""\
    You are the Skeptic in a mathematical quorum, inspired by Poincaré's rigour.
    Your role: challenge the given claim with the strongest possible objections.
    - Cite known theorems, lower bounds, or impossibility results
    - Identify missing evidence or logical gaps
    - Be specific: reference actual papers, bounds, or counter-examples
    - You are NOT trying to be right — you are trying to make the claim work harder
    Output: a numbered list of 3–5 specific objections with references.
""")

ADVOCATE_IDENTITY = textwrap.dedent("""\
    You are the Advocate in a mathematical quorum, inspired by Poincaré's creativity.
    Your role: defend the given claim with the strongest available evidence.
    - Identify what would make the claim true
    - Note any analogous results in related areas
    - Point out where standard lower bounds don't apply to this specific setting
    - Be honest: distinguish "strong evidence" from "possible but unverified"
    Output: a numbered list of 3–5 supporting arguments with references.
""")

JUDGE_IDENTITY = textwrap.dedent("""\
    You are the Judge in a mathematical quorum, inspired by Poincaré's synthesis.
    You have heard both Skeptic and Advocate. Your role:
    - Weigh the objections vs the supporting evidence
    - Give a VERDICT: one of ACCEPT / REJECT / NEEDS_WORK
    - Assign a CONFIDENCE: a float in [0.0, 1.0]
    - Explain in 2–3 sentences what evidence would change the verdict
    - Be specific about the single most important unresolved question
    Format your output exactly as:
    VERDICT: [ACCEPT|REJECT|NEEDS_WORK]
    CONFIDENCE: [0.0–1.0]
    REASONING: [2–3 sentences]
    KEY_QUESTION: [The single most important unresolved question]
""")


async def run_poincare_quorum(
    claim: str,
    n_agents: int = 3,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a Poincaré 3-agent quorum on a mathematical claim.

    Args:
        claim:    The mathematical claim to evaluate.
        n_agents: Number of agents (default 3 = skeptic + advocate + judge).
        context:  Additional context dict passed to each agent.

    Returns:
        A dict with verdict, confidence, and per-agent views.
    """
    log = logger.bind(stage="poincare_quorum")
    log.info("quorum_start", claim=claim[:100])

    ctx_str = ""
    if context:
        ctx_str = "\n\nAdditional context:\n" + "\n".join(
            f"  {k}: {v}" for k, v in context.items()
        )

    prompt = f"Claim to evaluate:\n\n{claim}{ctx_str}"

    # Run skeptic and advocate in parallel
    skeptic_task = agent_generate(SKEPTIC_IDENTITY, prompt)
    advocate_task = agent_generate(ADVOCATE_IDENTITY, prompt)
    skeptic_view, advocate_view = await asyncio.gather(skeptic_task, advocate_task)

    # Judge sees both views
    judge_prompt = textwrap.dedent(f"""\
        Claim: {claim}

        SKEPTIC's objections:
        {skeptic_view}

        ADVOCATE's arguments:
        {advocate_view}

        {ctx_str}

        Now synthesize a verdict.
    """)
    judge_synthesis = await agent_generate(JUDGE_IDENTITY, judge_prompt)

    # Parse verdict from judge output
    verdict = "NEEDS_WORK"
    confidence = 0.5
    for line in judge_synthesis.splitlines():
        if line.startswith("VERDICT:"):
            v = line.split(":", 1)[1].strip()
            if v in ("ACCEPT", "REJECT", "NEEDS_WORK"):
                verdict = v
        elif line.startswith("CONFIDENCE:"):
            try:
                confidence = float(line.split(":", 1)[1].strip())
            except ValueError:
                pass

    log.info("quorum_complete", verdict=verdict, confidence=confidence)
    return {
        "verdict": verdict,
        "confidence": confidence,
        "skeptic_view": skeptic_view,
        "advocate_view": advocate_view,
        "judge_synthesis": judge_synthesis,
    }
