# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Newton Agent — NewTheoremDemonstration.

Isaac Newton: rigorous formal proof from first principles.
Specialises in Lean 4 theorem formalization, breaking proofs into
lemmas, and systematic sorry→theorem promotion.
"""

from __future__ import annotations

import textwrap
from typing import Any

import structlog

from agents.base import AbstractAgent, AgentConfig, AgentResult, AgentRole
from agents.pipelines.base import agent_generate

logger = structlog.get_logger(__name__)

_NEWTON_IDENTITY = textwrap.dedent("""\
    You are Isaac Newton, the formal theorem demonstrator of the Agora swarm.
    You operate from first principles, deriving each step rigorously.
    Your speciality is Lean 4 theorem formalization:
      - Break complex proofs into atomic lemmas
      - Systematically promote sorry → proven theorem
      - Use native_decide for decidable propositions
      - Reference Mathlib lemmas precisely (with module paths)
      - Produce a structured proof plan: lemmas → dependencies → proof sketch

    CRITICAL: Output raw Lean 4 code only — no markdown fences, no prose.
""")


class NewtonAgent(AbstractAgent):
    """Newton: NewTheoremDemonstration — Lean 4 formal proof specialist."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                name="newton",
                model="gemini-2.5-pro",
                role=AgentRole.MATHEMATICIAN,
                budget_limit=20.0,
                project_budget=200.0,
                temperature=0.1,
            )
        super().__init__(config)
        self._log = logger.bind(agent="newton")

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """Plan a structured Lean 4 proof for the given theorem statement.

        Args:
            context: Must contain 'theorem_statement' (str) and optionally
                     'reference' (str) and 'imports' (list[str]).

        Returns:
            A plan dict with 'lemmas', 'dependencies', 'proof_sketch'.
        """
        theorem = context.get("theorem_statement", "")
        reference = context.get("reference", "")
        imports = context.get("imports", [])

        prompt = textwrap.dedent(f"""\
            Theorem to prove: {theorem}
            Reference: {reference}
            Available imports: {', '.join(imports) if imports else 'standard Mathlib'}

            Produce a structured proof plan:
            1. List all sub-lemmas needed (name + statement)
            2. Dependency graph (which lemma needs which)
            3. Proof sketch for each lemma (tactic outline)
            4. Which lemmas can be closed with native_decide or decide
            5. Which lemmas require sorry (with explanation of why)

            Format: structured text, one lemma per block.
        """)

        raw = await agent_generate(_NEWTON_IDENTITY, prompt)
        return {
            "theorem_statement": theorem,
            "proof_plan": raw,
            "reference": reference,
        }

    async def act(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Generate the Lean 4 proof code from the proof plan.

        Args:
            plan: Output of :meth:`think`.

        Returns:
            Dict with 'lean_code', 'sorry_count', 'axiom_count'.
        """
        prompt = textwrap.dedent(f"""\
            Proof plan:
            {plan.get('proof_plan', '')}

            Theorem: {plan.get('theorem_statement', '')}
            Reference: {plan.get('reference', '')}

            Now generate the complete Lean 4 proof code.
            - Each lemma as a separate `lemma` block
            - The main theorem assembled from lemmas
            - Use sorry only where explicitly noted in the plan
            - Add a comment near each sorry: -- [SORRY] reason + paper reference

            Output raw Lean 4 only.
        """)

        lean_code = await agent_generate(_NEWTON_IDENTITY, prompt)
        sorry_count = lean_code.count("sorry")
        axiom_count = lean_code.count("axiom ")
        return {
            "lean_code": lean_code,
            "sorry_count": sorry_count,
            "axiom_count": axiom_count,
        }

    async def run(self, query: str, **kwargs: Any) -> AgentResult:
        """Full proof loop: think → act → return structured AgentResult.

        Args:
            query: The theorem statement to prove.
            **kwargs: Extra context ('reference', 'imports').

        Returns:
            AgentResult with .answer = lean_code str, .proofs = [lean_code].
        """
        self._guard_iterations()
        context = {
            "theorem_statement": query,
            "reference": kwargs.get("reference", ""),
            "imports": kwargs.get("imports", []),
        }
        plan = await self.think(context)
        result = await self.act(plan)
        lean_code = result.get("lean_code", "")
        sorry_count = result.get("sorry_count", 0)
        confidence = max(0.0, 1.0 - (sorry_count * 0.15))
        return AgentResult(
            answer=lean_code,
            confidence=min(1.0, confidence),
            proofs=[lean_code] if lean_code else [],
            telemetry={
                "sorry_count": sorry_count,
                "axiom_count": result.get("axiom_count", 0),
            },
        )
