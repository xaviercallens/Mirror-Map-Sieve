# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Galois Mathematical Agent — The creative mathematician of the Agora.

Galois leverages the SymBrain v4 architecture, utilizing dual-hemisphere
reasoning biased towards innovation. He generates bold mathematical
conjectures, sketches formal Lean 4 proofs, and reflects on his own
performance to propose cortex upgrades.

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import pathlib
from typing import Any

import structlog

from agents.base import AbstractAgent, AgentConfig, AgentResult, AgentRole
from agents.galois.symbrain.cortex_v4 import GaloisCortexConfig, HemisphereMode, ConjectureConfidence
from agents.galois.tools.conjecture_generator import generate_conjectures
from agents.galois.tools.proof_sketcher import sketch_proof
from agents.galois.tools.self_improvement import plan_self_improvement

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT_PATH = pathlib.Path(__file__).parent / "prompts" / "system_prompt.md"

from agents.galois.tools.olympiad_solver import solve_olympiad_problem

GALOIS_TOOLS = {
    "conjecture_generator": generate_conjectures,
    "proof_sketcher": sketch_proof,
    "self_improvement": plan_self_improvement,
    "olympiad_solver": solve_olympiad_problem,
}


class GaloisAgent(AbstractAgent):
    """Creative mathematician agent using SymBrain v4 cortex."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                name="galois",
                model="gemini-2.5-pro", # Emulating Cloud-32B tier
                role=AgentRole.MATHEMATICIAN,
                budget_limit=100.0,
                project_budget=500.0,
                timeout_ms=30_000,
                tools=list(GALOIS_TOOLS.keys()),
            )
        super().__init__(config)
        self._tools = GALOIS_TOOLS
        self._system_prompt = self._load_system_prompt()
        self.cortex = GaloisCortexConfig()
        self.v6_cortex = None
        self.v7_cortex = None
        self.v8_cortex = None
        self.v9_cortex = None
        self.v11_cortex = None
        self.v16_cortex = None

    def checkpoint_state(self) -> None:
        """Save cortex state and any running MCTS trees to Alexandrie on preemption."""
        self._log.info("galois_checkpointing_state", 
                       symbrain_version=self.cortex.symbrain_version,
                       history_size=len(self.cortex.conjecture_history))
        # Write to Alexandrie vault
        try:
            from agents.common.alexandrie import AlexandrieVault
            vault = AlexandrieVault()
            vault.store_json(
                "galois_checkpoint.json", 
                {
                    "symbrain_version": self.cortex.symbrain_version,
                    "conjectures": [c.statement for c in self.cortex.conjecture_history]
                }
            )
        except Exception as e:
            self._log.error("galois_checkpoint_failed", error=str(e))

    def upgrade_to_v6(self) -> None:
        """Upgrade the agent's cortex to SymBrain v6 'Prometheus'."""
        from agents.galois.symbrain.cortex_v6 import SymBrainV6Cortex
        self.v6_cortex = SymBrainV6Cortex(base_config=self.cortex)
        self.cortex.symbrain_version = "v6-Prometheus"

    def upgrade_to_v7(self) -> None:
        """Upgrade the agent's cortex to SymBrain v7 'Galois-Einstein'."""
        from agents.galois.symbrain.cortex_v7 import SymBrainV7Cortex
        self.v7_cortex = SymBrainV7Cortex(base_config=self.cortex)
        self.cortex.symbrain_version = "v7-Galois-Einstein"

    def upgrade_to_v8(self) -> None:
        """Upgrade the agent's cortex to SymBrain v8 'Mind Olympiad' (RLFC-enhanced)."""
        from agents.galois.symbrain.cortex_v8 import SymBrainV8Cortex
        self.v8_cortex = SymBrainV8Cortex(base_config=self.cortex)
        self.cortex.symbrain_version = "v8-MindOlympiad"

    def upgrade_to_v9(self) -> None:
        """Upgrade the agent's cortex to SymBrain v9 'Archimedes'."""
        from agents.galois.symbrain.cortex_v9 import SymBrainV9Cortex
        self.v9_cortex = SymBrainV9Cortex(base_config=self.cortex)
        self.cortex.symbrain_version = "v9-Archimedes"

    def upgrade_to_v11(self) -> None:
        """Upgrade the agent's cortex to SymBrain v11 'Dieudonné'."""
        from agents.galois.symbrain.cortex_v11 import SymBrainV11Cortex
        self.v11_cortex = SymBrainV11Cortex(base_config=self.cortex)
        self.cortex.symbrain_version = "v11-Dieudonne"

    def upgrade_to_v16(self) -> None:
        """Upgrade the agent's cortex to SymBrain v16 'Agora Exhaustion'."""
        from agents.galois.symbrain.cortex_v16 import SymBrainV16Cortex
        self.v16_cortex = SymBrainV16Cortex(base_config=self.cortex)
        self.cortex.symbrain_version = "v16-Agora-Exhaustion"

    @staticmethod
    def _load_system_prompt() -> str:
        if _SYSTEM_PROMPT_PATH.exists():
            return _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        return "You are Galois, a creative mathematician."

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """Deliberate using SymBrain v4 cortex."""
        self._guard_iterations()
        start = self._start_timer()

        query: str = context.get("query", "")
        plan: dict[str, Any] = {
            "query": query,
            "tools": [],
            "estimated_cost": 0.0,
            "rationale": "",
        }

        # Route query through PFC
        complexity, mcts_mult = self.cortex.classifier.classify(query)
        logger.info("cortex_classification", complexity=complexity, mcts_mult=mcts_mult)

        # Plan tools based on context and hemisphere mode
        if "propose" in query.lower() or "conjecture" in query.lower() or "imagine" in query.lower() or self.cortex.routing.hemisphere == HemisphereMode.CREATIVE:
            plan["tools"].append("conjecture_generator")
            plan["estimated_cost"] += 0.10

            # Usually sketch proofs for generated conjectures
            plan["tools"].append("proof_sketcher")
            plan["estimated_cost"] += 0.05
            
        elif "verify" in query.lower() or "sketch" in query.lower() or self.cortex.routing.hemisphere == HemisphereMode.FORMAL:
            plan["tools"].append("proof_sketcher")
            plan["estimated_cost"] += 0.05

        if "reflect" in query.lower() or "improve" in query.lower() or "upgrade" in query.lower():
            plan["tools"].append("self_improvement")
            plan["estimated_cost"] += 0.02

        plan["rationale"] = f"PFC routing: {self.cortex.routing.hemisphere.name}. Selected {plan['tools']}."
        self._check_budget(plan["estimated_cost"])
        
        self._stop_timer(start, "galois_think")
        return plan

    async def act(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute the planned tools."""
        start = self._start_timer()
        observations: dict[str, Any] = {}

        # Pass data between tools
        conjectures = []

        for tool_name in context.get("tools", []):
            tool_fn = self._tools.get(tool_name)
            if tool_fn is None:
                continue

            try:
                if tool_name == "conjecture_generator":
                    user_query = context.get("query", context.get("problem", "Generate innovative mathematics"))
                    res = tool_fn(problem=user_query)
                    observations[tool_name] = res
                    conjectures = res.conjectures
                elif tool_name == "proof_sketcher":
                    sketches = []
                    for conj in conjectures:
                        res = tool_fn(conjecture_statement=conj.statement, conjecture_natural_language=conj.natural_language)
                        sketches.append(res)
                    observations[tool_name] = sketches if sketches else tool_fn(conjecture_statement="Example conjecture")
                elif tool_name == "self_improvement":
                    res = tool_fn(
                        conjecture_history=self.cortex.conjecture_history,
                        current_sigma_ded=self.cortex.routing.sigma_ded,
                        current_sigma_gen=self.cortex.routing.sigma_gen,
                    )
                    observations[tool_name] = res
            except Exception as exc:
                self._log.error("tool_failed", tool=tool_name, error=str(exc))
                observations[tool_name] = {"error": str(exc)}

        self._stop_timer(start, "galois_act")
        return observations

    async def run(self, query: str, **kwargs: Any) -> AgentResult:
        """Run the Galois agent."""
        self._log.info("galois_run_start", query=query[:120])
        start = self._start_timer()
        self._iteration = 0

        context: dict[str, Any] = {"query": query, **kwargs}
        plan = await self.think(context)
        observations = await self.act(plan)

        actual_cost = plan.get("estimated_cost", 0.0)
        self._record_cost(actual_cost)

        # Record conjectures in cortex for self-improvement
        if "conjecture_generator" in observations:
            res = observations["conjecture_generator"]
            if not isinstance(res, dict) and hasattr(res, "conjectures"):
                for conj in res.conjectures:
                    self.cortex.record_conjecture(conj.statement, ConjectureConfidence.MEDIUM, False)

        elapsed = self._stop_timer(start, "galois_run_total")
        result = AgentResult(
            answer=observations,
            confidence=0.8,
            cost_usd=actual_cost,
            telemetry={**self.telemetry.summary(), "total_elapsed_ms": round(elapsed, 2)},
        )
        return result
