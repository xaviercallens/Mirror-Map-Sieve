# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Gowers Agent — The Auto-informalization Specialist.

Named after Sir Timothy Gowers, a pioneer in the polymath projects and 
advocate for making formal mathematics accessible to humans.

This agent specializes in "Deformalization": transforming rigorous, machine-checked
Lean 4 code into highly readable, pedagogically sound, and peer-reviewable
human mathematics (informal prose and LaTeX).
"""

import os
from pathlib import Path
from typing import Any

import structlog

from agents.base import AbstractAgent, AgentConfig, AgentResult, AgentRole
from agents.pipelines.base import agent_generate

logger = structlog.get_logger(__name__)

class GowersAgent(AbstractAgent):
    """The Auto-informalization and Deformalization Agent."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                name="gowers",
                role=AgentRole.MATHEMATICIAN, # Acting as translator/mathematician
                model="gemini-2.5-pro",
            )
        super().__init__(config)
        self.system_prompt = self._load_prompt("system_prompt.md")

    def _load_prompt(self, filename: str) -> str:
        prompt_path = Path(__file__).parent / "prompts" / filename
        if prompt_path.exists():
            return prompt_path.read_text()
        return (
            "You are Gowers, the Auto-informalization Specialist. "
            "Your task is to transform Lean 4 formal code into natural, human-readable "
            "mathematics suitable for peer review, ensuring mathematical fidelity."
        )

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """Gowers decides how to deformalize the input."""
        return {"action": "deformalize"}

    async def act(self, plan: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Gowers translates Lean 4 to human math."""
        if context is None:
            context = {}
            
        lean_code = context.get("lean_code", "")
        query = context.get("query", "Translate this Lean 4 code into a human-readable proof.")
        
        prompt = (
            f"{self.system_prompt}\n\n"
            f"User Request: {query}\n\n"
            f"Lean 4 Code:\n```lean\n{lean_code}\n```\n\n"
            "Produce the natural language mathematical text (using LaTeX for formulas)."
        )
            
        result_text = await agent_generate(
            identity=self.system_prompt,
            prompt=prompt,
            model=self.config.model
        )
        return {"output": result_text}

    async def run(self, query: str, **kwargs: Any) -> AgentResult:
        """Entry point for the agent."""
        t_start = self._start_timer()
        log = logger.bind(agent=self.config.name, role=self.config.role.name)
        log.info("gowers_run_start")
        
        context = kwargs.copy()
        context["query"] = query
        
        plan = await self.think(context)
        action_result = await self.act(plan, context)
        
        self._stop_timer(t_start, "gowers_run")
        log.info("gowers_run_complete")
        
        return AgentResult(
            answer=action_result,
            confidence=0.95,
            cost_usd=self.budget_guard.cumulative_cost,
            proofs=[],
            telemetry=self.telemetry.summary(),
        )
