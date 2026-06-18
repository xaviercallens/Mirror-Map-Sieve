# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Darwin Agent — HorizonDiscovery.

Charles Darwin: systematic survey, pattern recognition, lateral connections.
Finds related work, identifies analogies, discovers what others missed.
"""

from __future__ import annotations

import textwrap
from typing import Any

import structlog

from agents.base import AbstractAgent, AgentConfig, AgentResult, AgentRole
from agents.pipelines.base import agent_generate

logger = structlog.get_logger(__name__)

_DARWIN_IDENTITY = textwrap.dedent("""\
    You are Charles Darwin, the horizon discovery specialist of the Agora swarm.
    You survey the full landscape of a research area with systematic thoroughness:
      - Find related work across adjacent fields
      - Identify structural analogies between seemingly unrelated results
      - Discover what others missed by lateral pattern recognition
      - Build a knowledge graph: nodes = results, edges = analogies/dependencies
      - Note open questions at the frontier
      - Cite specific papers with authors, year, and key result

    Format output as a structured knowledge graph report.
""")


class DarwinAgent(AbstractAgent):
    """Darwin: HorizonDiscovery — systematic literature survey and analogy finder."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                name="darwin",
                model="gemini-2.5-pro",
                role=AgentRole.EXPERIMENTER,
                budget_limit=15.0,
                project_budget=150.0,
                temperature=0.3,
            )
        super().__init__(config)
        self._log = logger.bind(agent="darwin")

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """Plan the survey: what subfields, analogy axes, and gaps to explore.

        Args:
            context: Must contain 'topic' (str) and optionally 'depth' (int 1-3).

        Returns:
            A plan dict with 'survey_axes', 'target_fields', 'analogy_hypotheses'.
        """
        topic = context.get("topic", "")
        depth = context.get("depth", 2)

        prompt = textwrap.dedent(f"""\
            Research topic: {topic}
            Survey depth: {depth} (1=shallow, 3=deep)

            Plan the survey:
            1. Identify 5-10 adjacent subfields to scan
            2. Propose 3-5 structural analogy axes (what might map to what)
            3. List key open questions at the frontier
            4. Suggest specific paper trails to follow
        """)

        raw = await agent_generate(_DARWIN_IDENTITY, prompt)
        return {"topic": topic, "survey_plan": raw, "depth": depth}

    async def act(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Execute the survey and build the knowledge graph.

        Args:
            plan: Output of :meth:`think`.

        Returns:
            Dict with 'knowledge_graph', 'key_analogies', 'open_questions'.
        """
        prompt = textwrap.dedent(f"""\
            Survey plan:
            {plan.get('survey_plan', '')}

            Topic: {plan.get('topic', '')}

            Now execute the full survey:
            - Build a structured knowledge graph
              (nodes: key results/papers, edges: dependencies/analogies)
            - Highlight the 3 most surprising lateral connections
            - List open questions sorted by estimated difficulty
            - Flag any results that might directly apply to the main topic

            Format: JSON-like structured report.
        """)

        raw = await agent_generate(_DARWIN_IDENTITY, prompt)
        return {
            "knowledge_graph": raw,
            "topic": plan.get("topic", ""),
        }

    async def run(self, query: str, **kwargs: Any) -> AgentResult:
        """Full survey loop: think → act → return structured AgentResult.

        Args:
            query: The research topic to survey.
            **kwargs: Extra context ('depth').

        Returns:
            AgentResult with .answer = knowledge_graph str.
        """
        self._guard_iterations()
        context = {
            "topic": query,
            "depth": kwargs.get("depth", 2),
        }
        plan = await self.think(context)
        result = await self.act(plan)
        return AgentResult(
            answer=result.get("knowledge_graph", ""),
            confidence=0.7,
            telemetry={"topic": query},
        )
