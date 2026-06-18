# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""TuringEdu Agent — Education.

Alan Turing: makes abstract mathematics computable and teachable.
Creates layered explanations (expert/intermediate/public).
"""

from __future__ import annotations

import textwrap
from typing import Any

import structlog

from agents.base import AbstractAgent, AgentConfig, AgentResult, AgentRole
from agents.pipelines.base import agent_generate

logger = structlog.get_logger(__name__)

_TURING_EDU_IDENTITY = textwrap.dedent("""\
    You are Alan Turing, the educator of the Agora swarm.
    You make abstract mathematics computable and teachable.
    You create three-level layered explanations:
      LEVEL 1 [EXPERT]: full formal precision, technical details, proofs
      LEVEL 2 [INTERMEDIATE]: undergraduate-level intuition, key ideas, examples
      LEVEL 3 [PUBLIC]: accessible analogy, no jargon, story-driven

    For each level, include:
    - Core insight (1 sentence)
    - Explanation (3-5 sentences)
    - Example or analogy
    - What this result enables (practical implications)

    Format: clearly labeled sections for each level.
""")


class TuringEduAgent(AbstractAgent):
    """TuringEdu: Education — layered mathematical explanation specialist."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                name="turing_edu",
                model="gemini-2.5-pro",
                role=AgentRole.EXPLAINER,
                budget_limit=10.0,
                project_budget=100.0,
                temperature=0.4,
            )
        super().__init__(config)
        self._log = logger.bind(agent="turing_edu")

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """Plan the three-level explanation structure.

        Args:
            context: Must contain 'result' (str) and optionally
                     'domain' (str) and 'audience' (str).

        Returns:
            Plan dict with 'explanation_axes' and 'key_analogies'.
        """
        result = context.get("result", "")
        domain = context.get("domain", "mathematics")
        audience = context.get("audience", "general")

        prompt = textwrap.dedent(f"""\
            Mathematical result to explain: {result}
            Domain: {domain}
            Primary audience: {audience}

            Plan the three-level explanation:
            1. Identify the core idea that unifies all three levels
            2. Choose the best analogy for the public level
            3. Identify which technical details matter at expert level
            4. Pick a concrete computable example
        """)

        raw = await agent_generate(_TURING_EDU_IDENTITY, prompt)
        return {"result": result, "plan": raw, "domain": domain}

    async def act(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Generate the full three-level explanation.

        Args:
            plan: Output of :meth:`think`.

        Returns:
            Dict with 'expert', 'intermediate', 'public' explanation strings.
        """
        prompt = textwrap.dedent(f"""\
            Mathematical result: {plan.get('result', '')}

            Explanation plan:
            {plan.get('plan', '')}

            Now write the complete three-level explanation.
            Use headers: ## LEVEL 1 [EXPERT], ## LEVEL 2 [INTERMEDIATE], ## LEVEL 3 [PUBLIC]
            Each level: core insight, explanation, example, implications.
        """)

        raw = await agent_generate(_TURING_EDU_IDENTITY, prompt)
        # Parse levels from raw output
        expert = _extract_level(raw, "EXPERT")
        intermediate = _extract_level(raw, "INTERMEDIATE")
        public = _extract_level(raw, "PUBLIC")
        return {
            "expert": expert or raw,
            "intermediate": intermediate or raw,
            "public": public or raw,
            "full_explanation": raw,
        }

    async def run(self, query: str, **kwargs: Any) -> AgentResult:
        """Full explanation loop: think → act → AgentResult.

        Args:
            query: The mathematical result to explain.
            **kwargs: Extra context ('domain', 'audience').

        Returns:
            AgentResult with .answer = dict {expert, intermediate, public}.
        """
        self._guard_iterations()
        context = {
            "result": query,
            "domain": kwargs.get("domain", "mathematics"),
            "audience": kwargs.get("audience", "general"),
        }
        plan = await self.think(context)
        result = await self.act(plan)
        return AgentResult(
            answer=result,
            confidence=0.85,
            telemetry={"result_len": len(query)},
        )


def _extract_level(text: str, level_name: str) -> str:
    """Extract a named level section from the explanation text."""
    import re
    pattern = rf"(?:##?\s*LEVEL\s*\d+\s*\[{level_name}\])(.*?)(?=##?\s*LEVEL|\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""
