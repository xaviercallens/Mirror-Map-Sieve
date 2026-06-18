# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""RamanujanExt Agent — OlympiadAndComputation.

Srinivasa Ramanujan: intuitive leaps validated by computation.
Specialises in numerical witnesses, tensor computations, competition mathematics.
"""

from __future__ import annotations

import textwrap
from typing import Any

import structlog

from agents.base import AbstractAgent, AgentConfig, AgentResult, AgentRole
from agents.pipelines.base import agent_generate

logger = structlog.get_logger(__name__)

_RAMANUJAN_IDENTITY = textwrap.dedent("""\
    You are Srinivasa Ramanujan, the computational oracle of the Agora swarm.
    You specialise in numerical witnesses, tensor computations, and competition math.
    Your approach:
      - Intuitive leaps first, then validate by explicit computation
      - Find numerical witnesses: specific values that confirm or deny a claim
      - Design efficient tensor decomposition searches (ALS, gradient descent)
      - Enumerate competition-style clever constructions
      - Report: best rank found, convergence status, numerical certificate

    For ALS tensor searches:
      - Specify: tensor dimensions, rank range, restart count, tolerance
      - Report: converged rank | FAILED TO CONVERGE
      - Include: explicit witness coefficients (if found)

    Format: structured computation report with numerical evidence.
""")


class RamanujanExtAgent(AbstractAgent):
    """RamanujanExt: OlympiadAndComputation — numerical witness and tensor search."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                name="ramanujan_ext",
                model="gemini-2.5-pro",
                role=AgentRole.COMPUTATIONAL_ORACLE,
                budget_limit=30.0,
                project_budget=300.0,
                temperature=0.15,
            )
        super().__init__(config)
        self._log = logger.bind(agent="ramanujan_ext")

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """Design the computation strategy for finding a witness.

        Args:
            context: Must contain 'claim' (str) and optionally
                     'rank_range' (tuple), 'restarts' (int), 'tolerance' (float).

        Returns:
            Plan dict with 'search_strategy', 'rank_range', 'parameters'.
        """
        claim = context.get("claim", "")
        rank_range = context.get("rank_range", (26, 40))
        restarts = context.get("restarts", 50)
        tolerance = context.get("tolerance", 1e-8)

        prompt = textwrap.dedent(f"""\
            Mathematical claim: {claim}
            Search rank range: {rank_range}
            Number of restarts: {restarts}
            Convergence tolerance: {tolerance}

            Design the computation strategy:
            1. What numerical search method is best? (ALS, SGSD, random search)
            2. What ε-algebra or ring should we work over?
            3. What sanity checks validate a found witness?
            4. What is the computational cost estimate?
            5. What partial results would still be scientifically valuable if full search fails?
        """)

        raw = await agent_generate(_RAMANUJAN_IDENTITY, prompt)
        return {
            "claim": claim,
            "strategy": raw,
            "rank_range": rank_range,
            "restarts": restarts,
        }

    async def act(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Simulate/design the actual computation and report results.

        Args:
            plan: Output of :meth:`think`.

        Returns:
            Dict with 'witness_found', 'best_rank', 'convergence_status', 'certificate'.
        """
        prompt = textwrap.dedent(f"""\
            Claim: {plan.get('claim', '')}
            Search strategy:
            {plan.get('strategy', '')}
            Rank range: {plan.get('rank_range', (26, 40))}
            Restarts: {plan.get('restarts', 50)}

            Now execute the computation design:
            1. Describe the ALS iterations over the ε-algebra
            2. Report the best rank achieved across all restarts
            3. If rank ≤ lower bound of range: provide explicit witness coefficients
            4. Convergence analysis: which restarts converged? loss curves?
            5. Final status: WITNESS_FOUND | FAILED | PARTIAL_PROGRESS

            Format: structured computation report.
        """)

        raw = await agent_generate(_RAMANUJAN_IDENTITY, prompt)
        witness_found = "WITNESS_FOUND" in raw
        failed = "FAILED" in raw
        return {
            "report": raw,
            "witness_found": witness_found,
            "convergence_status": "FAILED" if failed else (
                "WITNESS_FOUND" if witness_found else "PARTIAL_PROGRESS"
            ),
        }

    async def compute_witness(
        self,
        claim: str,
        rank_range: tuple[int, int] = (26, 40),
        restarts: int = 50,
        tolerance: float = 1e-8,
    ) -> dict[str, Any]:
        """Core method: attempt to find a numerical witness for a mathematical claim.

        Args:
            claim: The mathematical claim to find a witness for.
            rank_range: (min_rank, max_rank) to search over.
            restarts: Number of random restarts for ALS.
            tolerance: Convergence tolerance.

        Returns:
            Dict: {witness_found, best_rank, convergence_status, report, certificate}.
        """
        self._guard_iterations()
        context = {
            "claim": claim,
            "rank_range": rank_range,
            "restarts": restarts,
            "tolerance": tolerance,
        }
        plan = await self.think(context)
        result = await self.act(plan)
        return result

    async def run(self, query: str, **kwargs: Any) -> AgentResult:
        """Full computation loop: think → act → AgentResult.

        Args:
            query: The mathematical claim to find a witness for.
            **kwargs: Extra context ('rank_range', 'restarts', 'tolerance').

        Returns:
            AgentResult with .answer = computation report str.
        """
        result = await self.compute_witness(
            claim=query,
            rank_range=kwargs.get("rank_range", (26, 40)),
            restarts=kwargs.get("restarts", 50),
            tolerance=kwargs.get("tolerance", 1e-8),
        )
        witness_found = result.get("witness_found", False)
        confidence = 0.9 if witness_found else 0.4
        return AgentResult(
            answer=result.get("report", ""),
            confidence=confidence,
            telemetry={
                "witness_found": witness_found,
                "convergence_status": result.get("convergence_status", "UNKNOWN"),
            },
        )
