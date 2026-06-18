# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Feynman Agent — Quantum path integrals and pedagogy (empty at the moment).

Note: Scaffolded for v4.0 architecture. empty at the moment
"""

from typing import Any
import structlog

import warnings
warnings.warn(
    "This agent is a STUB and has been DEPRECATED in v4.4.0. "
    "Do not use in production pipelines.",
    DeprecationWarning,
    stacklevel=2
)

from agents.base import AbstractAgent, AgentConfig, AgentResult, AgentRole

logger = structlog.get_logger(__name__)

class FeynmanAgent(AbstractAgent):
    """Feynman: Quantum path integrals and pedagogy (empty at the moment)."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                name="feynman",
                model="gemini-2.5-pro",
                role=AgentRole.EXPLAINER,
                budget_limit=10.0,
                project_budget=100.0,
            )
        super().__init__(config)
        self._log = logger.bind(agent="feynman")

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        return {}

    async def act(self, plan: dict[str, Any]) -> dict[str, Any]:
        return {"status": "not_implemented_yet"}

    async def run(self, query: str, **kwargs: Any) -> AgentResult:
        self._guard_iterations()
        return AgentResult(answer=False, confidence=0.0)
