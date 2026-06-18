# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file

import re
from typing import Any, Dict
import structlog

from agents.base import AbstractAgent, AgentConfig, AgentRole, AgentResult
from agents.galileo.z3_oracle import solve_difference_basis_sat

logger = structlog.get_logger(__name__)

class GalileoAgent(AbstractAgent):
    """
    Galileo: The Z3 / SAT Computational Oracle.
    
    When Galois hits a combinatorial wall or cannot prove a specific
    inequality (e.g., an integer overflow check), Galileo intercepts the
    failed invariant, negates it, and queries a Z3 pseudo-boolean SAT
    solver to extract an exact integer counter-model.
    """

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                name="galileo",
                model="z3-oracle",  # Galileo doesn't use an LLM, it uses Z3
                role=AgentRole.COMPUTATIONAL_ORACLE,
            )
        super().__init__(config)
        self._log = logger.bind(agent="galileo")

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Parse the failed Lean 4 invariant to determine the Z3 strategy.
        """
        goal = context.get("goal_state", "") or context.get("query", "")
        self._log.info("galileo_parsing_failed_invariant", goal=goal)
        
        if "diff_basis" in goal.lower() or "diff_basis" in context.get("theory", ""):
            return {
                "strategy": "difference_basis",
                "target_n": context.get("target_n", 10000),
                "target_k": context.get("target_k", 173),
            }
            
        if "bitvec" in goal.lower() or "MAX_UINT" in goal or "2^256" in goal or "deposit" in goal or "balance" in goal:
            return {
                "strategy": "bitvec_overflow",
                "invariant": goal
            }

        return {"strategy": "unknown"}

    async def act(self, plan: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the Z3 SAT solver against the planned strategy.
        """
        strategy = plan.get("strategy")
        
        if strategy == "difference_basis":
            n = plan.get("target_n", 10000)
            k = plan.get("target_k", 173)
            self._log.info("galileo_running_z3", target_n=n, target_k=k)
            
            tactic = solve_difference_basis_sat(target_n=n, target_k=k)
            
            if tactic == "UNSAT":
                return {
                    "status": "error",
                    "error": "Z3 returned UNSAT for the given parameters",
                    "logs": ["Z3 Oracle returned UNSAT."]
                }
                
            return {
                "status": "success",
                "tactic": tactic,
                "counter_model": None,
                "logs": [f"Galileo Z3 Oracle found optimal basis tactic."]
            }
            
        elif strategy == "bitvec_overflow":
            invariant = plan.get("invariant")
            self._log.info("galileo_running_bitvec_z3", invariant=invariant)
            
            from agents.galileo.z3_oracle import solve_bitvec_invariant_sat
            counter_model = solve_bitvec_invariant_sat(invariant)
            
            if not counter_model:
                return {
                    "status": "error",
                    "error": "Z3 failed to find an overflow counter-model",
                    "logs": ["Z3 Oracle returned UNSAT for overflow invariant."]
                }
                
            return {
                "status": "success",
                "counter_model": counter_model,
                "tactic": "bv_decide",
                "logs": [f"Galileo extracted overflow counter-model via Z3: {counter_model}"]
            }

        return {
            "status": "error",
            "error": f"Unknown Galileo strategy: {strategy}",
            "logs": ["Galileo could not parse the invariant."]
        }

    async def run(self, query: str, **kwargs: Any) -> AgentResult:
        """Full agent run loop."""
        self._guard_iterations()
        
        context = {
            "query": query,
            "goal_state": query,
            "theory": kwargs.get("theory", ""),
            "target_n": kwargs.get("target_n", 10000),
            "target_k": kwargs.get("target_k", 173),
        }
        
        plan = await self.think(context)
        result = await self.act(plan)
        
        if result.get("status") == "success":
            return AgentResult(
                answer=result,
                confidence=1.0,
                telemetry={"strategy": plan.get("strategy")},
                warnings=result.get("logs", [])
            )
        else:
            return AgentResult(
                answer=result,
                confidence=0.0,
                telemetry={"strategy": plan.get("strategy")},
                warnings=result.get("logs", [])
            )

    def _guard_iterations(self) -> None:
        self._iteration += 1
        if self._iteration > self.config.max_iterations:
            raise RuntimeError("Max iterations exceeded")
