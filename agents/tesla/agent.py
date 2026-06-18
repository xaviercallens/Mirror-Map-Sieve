# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Tesla Agent — Prototyping and Applied Engineering.

The Tesla Agent takes theoretical patents and mathematical constructs
and prototypes them by writing formal specifications, designs, and numeric
validation loops, emulating a skill/goal-oriented loop.
"""

import os
from pathlib import Path
from typing import Any

import structlog

from agents.base import AbstractAgent, AgentConfig, AgentResult, AgentRole
from agents.pipelines.base import agent_generate

logger = structlog.get_logger(__name__)

class TeslaAgent(AbstractAgent):
    """The Director of Prototyping and Applied Engineering."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                name="tesla",
                role=AgentRole.PROTOTYPER,
                model="gemini-2.5-pro",
            )
        super().__init__(config)
        self.system_prompt = self._load_prompt("system_prompt.md")

    def _load_prompt(self, filename: str) -> str:
        prompt_path = Path(__file__).parent / "prompts" / filename
        if prompt_path.exists():
            return prompt_path.read_text()
        return "You are Tesla, the Director of Prototyping and Applied Engineering."

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """Tesla decides what skill/goal to execute based on the phase."""
        phase = context.get("phase", "init")
        return {"action": phase}

    async def act(self, plan: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Tesla executes the action."""
        if context is None:
            context = {}
            
        action = plan.get("action")
        query = context.get("query", "")
        prompt = f"{self.system_prompt}\n\nTask: {query}\nPhase: {action}"
        prompt += "\n\nIMPORTANT: You do NOT have access to external search tools (e.g., literature-search-arxiv, literature-search-openalex). Do not attempt to use or invoke any tool calls. Rely entirely on your extensive internal knowledge to synthesize the requested output."
        
        if action == "literature_review":
            prompt += "\nPerform a technical literature review and state of the art analysis."
        elif action == "specs_and_design":
            prompt += "\nProduce formal SPECS.md and DESIGN.md content. Focus on test-driven and specification-driven concepts."
        elif action == "prototype_loop":
            iteration = context.get("iteration", 1)
            prompt += f"\nIteration {iteration}. Run numeric validation, refine the design, and extract LESSONS_LEARNT."
        else:
            prompt += "\nExecute the required prototyping tasks."
            
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
        log.info("tesla_run_start")
        
        context = kwargs.copy()
        context["query"] = query
        
        plan = await self.think(context)
        action_result = await self.act(plan, context)
        
        self._stop_timer(t_start, "tesla_run")
        log.info("tesla_run_complete")
        
        return AgentResult(
            answer=action_result,
            confidence=0.9,
            cost_usd=self.budget_guard.cumulative_cost,
            proofs=[],
            telemetry=self.telemetry.summary(),
        )
