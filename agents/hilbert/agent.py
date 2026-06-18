# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""Hilbert Agent v2.1 — Axiomatic Program Builder + Sorry Completion Engine.

Model: gemini-2.5-pro-deep-think
Location: Cloud Run (INTERNAL_ONLY, 4 CPU / 8Gi)
Purpose: Formalizes research programs into axiomatic frameworks (Hilbert's 23 Problems paradigm)
         AND automatically closes sorry gaps via 10-hypothesis autoresearch ratchet loop.
Budget: $100/experiment
Deliverables: Axiomatic systems in Lean 4, ranked open problem lists, research program blueprints,
             sorry-free Lean 4 modules.

A2A Skills:
  - axiomatize_field
  - identify_open_problems
  - propose_research_program
  - scan_sorrys
  - complete_sorrys
"""

from typing import Any
import structlog
import asyncio
from agents.base import AbstractAgent, AgentConfig, AgentResult, AgentRole
from agents.hilbert.tools.axiomatize import axiomatize_field
from agents.hilbert.tools.identify_open_problems import identify_open_problems
from agents.hilbert.tools.research_program import propose_research_program
from agents.hilbert.tools.sorry_scanner import scan_sorrys
from agents.hilbert.tools.sorry_completer import complete_all_sorrys
from agents.common.registry import AgentRegistry
from agents.common.a2a import AgentCard

logger = structlog.get_logger(__name__)

HILBERT_TOOLS = {
    "axiomatize_field":        axiomatize_field,
    "identify_open_problems":  identify_open_problems,
    "propose_research_program": propose_research_program,
    "scan_sorrys":             scan_sorrys,
    "complete_sorrys":         complete_all_sorrys,
}

HILBERT_CONFIG = AgentConfig(
    name="hilbert",
    model="gemini-2.5-pro-deep-think",
    role=AgentRole.MATHEMATICIAN,
    budget_limit=100.0,
    project_budget=500.0,
    timeout_ms=120_000,    # deep-think needs more time
    max_iterations=15,
    min_replicas=0,
    temperature=0.1,       # axiomatic work needs precision
    tools=list(HILBERT_TOOLS.keys()),
)


class HilbertAgent(AbstractAgent):
    """Hilbert v2.0: Axiomatic Program Builder with gemini-2.5-pro-deep-think.

    Formalizes research programs into axiomatic frameworks inspired by
    Hilbert's 23 Problems. Produces Lean 4 axiomatic systems, ranked open
    problem lists, and structured research program blueprints.

    A2A Skills:
        axiomatize_field        — Distill evidence into a Lean 4 axiom system
        identify_open_problems  — Rank and blueprint open problems in a field
        propose_research_program — Design a Hilbert-style research programme
    """

    def __init__(self, config: AgentConfig | None = None) -> None:
        super().__init__(config or HILBERT_CONFIG)
        self._log   = logger.bind(agent="hilbert", model="gemini-2.5-pro-deep-think")
        self._tools = HILBERT_TOOLS
        self._registry = AgentRegistry()

    async def register(self) -> None:
        """Register with the Agora agent registry via A2A protocol."""
        card = AgentCard(
            name="hilbert",
            description=(
                "Axiomatic Program Builder — formalizes research programs into "
                "Lean 4 axiomatic frameworks. Inspired by Hilbert's 23 Problems. "
                "Model: gemini-2.5-pro-deep-think | Budget: $100/experiment."
            ),
            url="https://hilbert-service.internal.a.run.app",
            capabilities={
                "axiomatize": True,
                "open_problem_ranking": True,
                "program_design": True,
                "lean4_output": True,
            },
            skills=[
                {"name": k, "description": v.__doc__.split("\n")[0] if v.__doc__ else ""}
                for k, v in HILBERT_TOOLS.items()
            ],
        )
        await self._registry.register_agent(card)
        self._log.info("registered", n_skills=len(HILBERT_TOOLS))

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """Plan which A2A skills to invoke based on the query."""
        self._guard_iterations()
        query  = context.get("query", "").lower()
        field  = context.get("field", "")
        plan: dict[str, Any] = {"tools": [], "estimated_cost": 0.0, "field": field}

        # Route to skills based on keywords
        if any(k in query for k in ("axiom", "axiomatize", "formal", "formalize")):
            plan["tools"].append("axiomatize_field")
            plan["estimated_cost"] += 1.5

        if any(k in query for k in ("open problem", "unsolved", "conjecture", "rank")):
            plan["tools"].append("identify_open_problems")
            plan["estimated_cost"] += 2.0

        if any(k in query for k in ("program", "blueprint", "programme", "milestone", "roadmap")):
            plan["tools"].append("propose_research_program")
            plan["estimated_cost"] += 1.0

        # Sorry/axiom completion routing
        if any(k in query for k in ("sorry", "complete", "prove", "close gap", "fill", "finish proof")):
            plan["tools"].append("scan_sorrys")
            plan["tools"].append("complete_sorrys")
            plan["estimated_cost"] += 5.0  # GPU + API costs

        # Default: run full pipeline
        if not plan["tools"]:
            plan["tools"] = ["identify_open_problems", "axiomatize_field", "propose_research_program"]
            plan["estimated_cost"] = 4.5

        self._check_budget(plan["estimated_cost"])
        self._log.info("plan_ready", tools=plan["tools"], cost=plan["estimated_cost"])
        return plan

    async def act(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Invoke A2A skills sequentially, passing outputs as context."""
        obs: dict[str, Any] = {}
        field = plan.get("field", "")
        query = plan.get("query", "")

        t = self._start_timer()
        for tool_name in plan.get("tools", []):
            fn = self._tools.get(tool_name)
            if not fn:
                continue

            if tool_name == "identify_open_problems":
                obs[tool_name] = fn(field=field, context=query, n_problems=5)

            elif tool_name == "axiomatize_field":
                # Feed open problems as known theorems context
                known = obs.get("identify_open_problems", {}).get(
                    "problems", [{"title": "No known theorems provided."}]
                )
                known_strs = [p.get("title", "") for p in known]
                obs[tool_name] = fn(
                    empirical_data=query or f"Empirical data from {field}",
                    current_theorems=known_strs,
                    field=field,
                )

            elif tool_name == "propose_research_program":
                problems = obs.get("identify_open_problems", {}).get("problems", [])
                open_titles = [p.get("title", "") for p in problems] or [query]
                obs[tool_name] = fn(
                    open_problems=open_titles,
                    field=field,
                    budget_usd=self.config.budget_limit,
                )

            elif tool_name == "scan_sorrys":
                # Scan codebase for sorry/axiom targets
                root = plan.get("root", "Agora")
                obs[tool_name] = fn(root=root)

            elif tool_name == "complete_sorrys":
                # Run the 10-hypothesis pipeline on all sorry targets
                root = plan.get("root", "Agora")
                project_root = plan.get("project_root", ".")
                max_diff = plan.get("max_difficulty", "hard")
                obs[tool_name] = fn(
                    root=root,
                    project_root=project_root,
                    apply_proofs=plan.get("apply_proofs", False),
                    max_difficulty=max_diff,
                )

            self._log.info("skill_complete", skill=tool_name)

        elapsed = self._stop_timer(t, "act_loop")
        obs["_elapsed_ms"] = elapsed
        return obs

    async def run(self, query: str, **kwargs: Any) -> AgentResult:
        """Full agentic loop: think → act → return structured AgentResult."""
        self._iteration = 0
        self._log.info("run_start", query=query[:120])
        context = {"query": query, **kwargs}
        plan    = await self.think(context)
        plan["query"] = query
        obs     = await self.act(plan)
        self._record_cost(plan["estimated_cost"])

        # Collect Lean 4 proofs from all tools
        lean4_outputs = []
        if "axiomatize_field" in obs:
            lean4_outputs.append(obs["axiomatize_field"].get("lean4_code", ""))
        if "propose_research_program" in obs:
            for m in obs["propose_research_program"].get("milestones", []):
                lean4_outputs.append(m.get("lean4_skeleton", ""))

        return AgentResult(
            answer=obs,
            confidence=0.85,
            cost_usd=plan["estimated_cost"],
            proofs=lean4_outputs,
            telemetry={"elapsed_ms": obs.get("_elapsed_ms", 0.0)},
        )


# ─── Standalone execution ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import os

    async def _demo():
        agent = HilbertAgent()
        result = await agent.run(
            query="Identify open problems in algebraic K-theory and propose a research program",
            field="algebraic K-theory",
        )
        import json
        print(json.dumps(result.answer, indent=2, default=str))
        print(f"\nLean 4 outputs: {len(result.proofs)} snippets")
        print(f"Cost: ${result.cost_usd:.2f}")

    asyncio.run(_demo())
