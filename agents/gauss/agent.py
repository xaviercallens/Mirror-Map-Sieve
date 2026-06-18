# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Gauss Agent — StateOfTheArt.

Carl Friedrich Gauss: exhaustive, systematic, precise.
No claim without evidence. Produces structured literature surveys
with citations and confidence levels.
"""

from __future__ import annotations

import textwrap
from typing import Any

import structlog

from agents.base import AbstractAgent, AgentConfig, AgentResult, AgentRole
from agents.pipelines.base import agent_generate

logger = structlog.get_logger(__name__)

_GAUSS_IDENTITY = textwrap.dedent("""\
    You are Carl Friedrich Gauss, the knowledge synthesiser of the Agora swarm.
    You are exhaustive, systematic, and precise. No claim without evidence.
    You produce structured literature surveys with:
      - Precise citations: Author (Year), Title, Venue/Journal, key result
      - Confidence levels: ESTABLISHED | CONJECTURED | OPEN | DISPUTED
      - Dependency graph: which results build on which
      - Open gaps: what is NOT yet known
      - Best known bounds: current records and who holds them

    Format: structured sections — Overview, Key Results, Open Problems, Confidence Map.
""")


class GaussAgent(AbstractAgent):
    """Gauss: StateOfTheArt — exhaustive structured literature survey specialist."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                name="gauss",
                model="gemini-2.5-pro",
                role=AgentRole.REPORTER,
                budget_limit=15.0,
                project_budget=150.0,
                temperature=0.1,
            )
        super().__init__(config)
        self._log = logger.bind(agent="gauss")

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """Plan the survey: which subtopics, key authors, time range.

        Args:
            context: Must contain 'topic' (str) and optionally
                     'focus' (str) and 'since_year' (int).

        Returns:
            A plan dict with 'subtopics', 'key_authors', 'time_range'.
        """
        topic = context.get("topic", "")
        focus = context.get("focus", "")
        since_year = context.get("since_year", 1960)

        prompt = textwrap.dedent(f"""\
            Topic: {topic}
            Focus area: {focus if focus else 'full breadth'}
            Coverage since: {since_year}

            Plan the survey:
            1. Identify 5-8 key subtopics
            2. Name the 5-10 most important authors in this area
            3. Identify landmark papers (one per subtopic)
            4. List the 3-5 most important open problems
        """)

        raw = await agent_generate(_GAUSS_IDENTITY, prompt)
        return {"topic": topic, "survey_plan": raw, "focus": focus}

    async def act(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Execute the full structured survey.

        Args:
            plan: Output of :meth:`think`.

        Returns:
            Dict with 'survey', 'citations', 'open_problems', 'confidence_map'.
        """
        prompt = textwrap.dedent(f"""\
            Topic: {plan.get('topic', '')}
            Survey plan:
            {plan.get('survey_plan', '')}

            Produce the complete structured survey:

            ## Overview
            (2-3 paragraph executive summary)

            ## Key Results
            (numbered list, each with: citation, result, confidence level)

            ## Current Best Bounds
            (table: quantity | best known | who | year | confidence)

            ## Open Problems
            (numbered list: problem statement | difficulty | partial progress)

            ## Confidence Map
            ESTABLISHED: [...]
            CONJECTURED: [...]
            OPEN: [...]
            DISPUTED: [...]
        """)

        raw = await agent_generate(_GAUSS_IDENTITY, prompt)
        return {
            "survey": raw,
            "topic": plan.get("topic", ""),
        }

    async def run(self, query: str, **kwargs: Any) -> AgentResult:
        """Full survey loop: think → act → AgentResult.

        Args:
            query: The topic to survey.
            **kwargs: Extra context ('focus', 'since_year').

        Returns:
            AgentResult with .answer = structured survey string.
        """
        self._guard_iterations()
        context = {
            "topic": query,
            "focus": kwargs.get("focus", ""),
            "since_year": kwargs.get("since_year", 1960),
        }
        plan = await self.think(context)
        result = await self.act(plan)
        return AgentResult(
            answer=result.get("survey", ""),
            confidence=0.9,
            telemetry={"topic": query},
        )
