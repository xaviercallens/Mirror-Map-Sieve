# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Poincaré Agent — QuorumVerification.

Henri Poincaré: multi-perspective consensus, topological thinking.
Runs N independent reviews and synthesizes a verdict.
"""

from __future__ import annotations

import asyncio
import textwrap
from typing import Any

import structlog

from agents.base import AbstractAgent, AgentConfig, AgentResult, AgentRole
from agents.pipelines.base import agent_generate

logger = structlog.get_logger(__name__)

_POINCARE_SKEPTIC_IDENTITY = textwrap.dedent("""\
    You are Henri Poincaré playing the role of SKEPTIC in a quorum review.
    Challenge every assumption. Find edge cases, counter-examples, and gaps.
    Your job is to stress-test the claim ruthlessly.
    Produce: [CHALLENGES] list + [FATAL_FLAWS] list (if any).
""")

_POINCARE_ADVOCATE_IDENTITY = textwrap.dedent("""\
    You are Henri Poincaré playing the role of ADVOCATE in a quorum review.
    Defend the claim. Find supporting evidence, analogies, and corroborating results.
    Your job is to build the strongest possible case for the claim.
    Produce: [SUPPORTING_EVIDENCE] list + [ANALOGIES] list.
""")

_POINCARE_JUDGE_IDENTITY = textwrap.dedent("""\
    You are Henri Poincaré playing the role of JUDGE in a quorum review.
    Synthesise the skeptic's challenges and the advocate's defense.
    Render a final verdict: ACCEPT | REJECT | NEEDS_WORK
    Produce a JSON-like dict:
      {"verdict": "ACCEPT|REJECT|NEEDS_WORK",
       "confidence": 0.0-1.0,
       "reasoning": "...",
       "dissents": ["..."],
       "conditions": ["..."]}
""")


class PoincareAgent(AbstractAgent):
    """Poincaré: QuorumVerification — multi-agent consensus review."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                name="poincare",
                model="gemini-2.5-pro",
                role=AgentRole.VERIFIER,
                budget_limit=20.0,
                project_budget=200.0,
                temperature=0.2,
            )
        super().__init__(config)
        self._log = logger.bind(agent="poincare")

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """Run the skeptic and advocate in parallel.

        Args:
            context: Must contain 'claim' (str) and optionally 'evidence' (str).

        Returns:
            A plan dict with 'skeptic_report' and 'advocate_report'.
        """
        claim = context.get("claim", "")
        evidence = context.get("evidence", "")

        prompt = textwrap.dedent(f"""\
            Claim under review: {claim}
            Supporting evidence: {evidence if evidence else 'None provided'}

            Analyse this claim from your assigned perspective.
        """)

        skeptic_task = agent_generate(_POINCARE_SKEPTIC_IDENTITY, prompt)
        advocate_task = agent_generate(_POINCARE_ADVOCATE_IDENTITY, prompt)
        skeptic_report, advocate_report = await asyncio.gather(
            skeptic_task, advocate_task
        )

        return {
            "claim": claim,
            "skeptic_report": skeptic_report,
            "advocate_report": advocate_report,
        }

    async def act(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Run the judge to synthesise a final verdict.

        Args:
            plan: Output of :meth:`think`.

        Returns:
            Dict with 'verdict', 'confidence', 'reasoning', 'dissents'.
        """
        prompt = textwrap.dedent(f"""\
            Claim: {plan.get('claim', '')}

            SKEPTIC REPORT:
            {plan.get('skeptic_report', '')}

            ADVOCATE REPORT:
            {plan.get('advocate_report', '')}

            Synthesise and render a final verdict.
            Output a JSON dict: verdict, confidence, reasoning, dissents, conditions.
        """)

        verdict_raw = await agent_generate(_POINCARE_JUDGE_IDENTITY, prompt)
        return {
            "verdict_raw": verdict_raw,
            "claim": plan.get("claim", ""),
            "skeptic_report": plan.get("skeptic_report", ""),
            "advocate_report": plan.get("advocate_report", ""),
        }

    async def run(self, query: str, **kwargs: Any) -> AgentResult:
        """Full quorum loop: think (skeptic+advocate) → act (judge) → AgentResult.

        Args:
            query: The claim to verify.
            **kwargs: Extra context ('evidence').

        Returns:
            AgentResult with .answer = dict {verdict, confidence, reasoning, dissents}.
        """
        self._guard_iterations()
        context = {
            "claim": query,
            "evidence": kwargs.get("evidence", ""),
        }
        plan = await self.think(context)
        result = await self.act(plan)
        verdict_raw = result.get("verdict_raw", "")
        # Parse confidence heuristically
        confidence = 0.5
        if "ACCEPT" in verdict_raw:
            confidence = 0.85
        elif "REJECT" in verdict_raw:
            confidence = 0.9
        elif "NEEDS_WORK" in verdict_raw:
            confidence = 0.6
        return AgentResult(
            answer={
                "verdict_raw": verdict_raw,
                "skeptic_report": plan.get("skeptic_report", ""),
                "advocate_report": plan.get("advocate_report", ""),
            },
            confidence=confidence,
            telemetry={"claim_len": len(query)},
        )
