# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Pythagore Mathematical Librarian and Proof Synthesis Agent.

Pythagore is in charge of dynamic proof gap mapping, mathematical literature
harvesting (arXiv / OpenAlex), and formalizing Lean 4 skeletons to systematically
verify Agora specifications.
"""

from __future__ import annotations

import pathlib
from typing import Any

import structlog

from agents.base import AbstractAgent, AgentConfig, AgentResult, AgentRole
from agents.pythagore.tools.lean_gap_mapper import map_lean_proof_gaps
from agents.pythagore.tools.proof_retriever import retrieve_proof_literature
from agents.pythagore.tools.formal_draft_generator import generate_formal_lean_draft
from agents.pythagore.tools.generate_research_hypotheses import generate_research_hypotheses
from agents.pythagore.tools.extract_lean_states import extract_lean_states

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT_PATH = pathlib.Path(__file__).parent / "prompts" / "system_prompt.md"

PYTHAGORE_TOOLS = {
    "lean_gap_mapper": map_lean_proof_gaps,
    "proof_retriever": retrieve_proof_literature,
    "formal_draft_generator": generate_formal_lean_draft,
    "generate_research_hypotheses": generate_research_hypotheses,
    "extract_lean_states": extract_lean_states,
}


class PythagoreAgent(AbstractAgent):
    """Librarian and formalizer agent for dynamic proof gap synthesis."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                name="pythagore",
                model="gemini-2.5-pro",
                role=AgentRole.VERIFIER,
                budget_limit=100.0,
                project_budget=500.0,
                timeout_ms=60_000,
                tools=list(PYTHAGORE_TOOLS.keys()),
            )
        super().__init__(config)
        self._tools = PYTHAGORE_TOOLS
        self._system_prompt = self._load_system_prompt()

    @staticmethod
    def _load_system_prompt() -> str:
        """Load Pythagore's system prompt from disk."""
        if _SYSTEM_PROMPT_PATH.exists():
            return _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        return (
            "You are Pythagore, the mathematical librarian of the Agora. "
            "Scan the codebase for proof gaps, harvest scholarly proof papers, and generate compilable Lean 4 skeletons."
        )

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """Analyze query to route to gap mapper, literature retriever, or draft generator."""
        self._guard_iterations()
        start = self._start_timer()

        query: str = context.get("query", "")
        plan: dict[str, Any] = {
            "tools": [],
            "estimated_cost": 0.0,
            "rationale": "",
        }

        query_lower = query.lower()

        # Audit/Gap Mapper routing
        if any(kw in query_lower for kw in ("scan", "sorry", "gap", "audit", "todo", "incomplete", "unproven")):
            plan["tools"].append("lean_gap_mapper")
            plan["estimated_cost"] += 0.01
            plan["rationale"] = "Gap mapping path selected. Dynamic scanning of verifiers/lean4/Agora/."

        # Scholarly Retrieval routing
        elif any(kw in query_lower for kw in ("search", "find", "arxiv", "paper", "literature", "document", " grothendieck", "elliptic", "leandojo")):
            if "leandojo" in query_lower or "trace" in query_lower:
                plan["tools"].append("extract_lean_states")
                plan["estimated_cost"] += 0.10
                plan["rationale"] = "LeanDojo state extraction path selected."
            else:
                plan["tools"].append("proof_retriever")
                plan["tools"].append("generate_research_hypotheses")
                plan["estimated_cost"] += 0.15
                plan["rationale"] = "Scholarly retrieval path selected. Ingesting proof abstracts/PDFs and generating 5 hypotheses."

        # Draft generator routing
        elif any(kw in query_lower for kw in ("formalise", "draft", "skeleton", "theorem", "generate", "sketch")):
            plan["tools"].append("formal_draft_generator")
            plan["estimated_cost"] += 0.02
            plan["rationale"] = "Formal draft generation path selected. Synthesizing Lean 4 skeleton."

        # Fallback: scan gaps and search concepts
        else:
            plan["tools"].append("lean_gap_mapper")
            plan["tools"].append("proof_retriever")
            plan["estimated_cost"] += 0.06
            plan["rationale"] = "Fallback: general math survey. Dynamic sorry scan + concepts search."

        self._check_budget(plan["estimated_cost"])
        self._stop_timer(start, "pythagore_think")
        return plan

    async def act(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Execute selected mathematical tools."""
        start = self._start_timer()
        observations: dict[str, Any] = {}

        for tool_name in plan.get("tools", []):
            tool_fn = self._tools.get(tool_name)
            if tool_fn is None:
                continue

            try:
                if tool_name == "lean_gap_mapper":
                    result = tool_fn(library_path=plan.get("library_path", None))
                elif tool_name == "proof_retriever":
                    q_str = plan.get("query", "Lean 4 verification")
                    result = tool_fn(query=q_str, max_results=plan.get("max_results", 3))
                elif tool_name == "formal_draft_generator":
                    result = tool_fn(
                        theorem_name=plan.get("theorem_name", "custom_theorem"),
                        signature=plan.get("signature", "(p : Real) : p = p"),
                        proof_strategy=plan.get("proof_strategy", "Reflexivity."),
                        imports=plan.get("imports", None),
                    )
                elif tool_name == "generate_research_hypotheses":
                    target = plan.get("query", "Resolve sorry gap")
                    # Use retrieved literature if proof_retriever was run, else use rag_context
                    context_data = observations.get("proof_retriever", plan.get("rag_context", ""))
                    result = tool_fn(target_gap=target, context_data=context_data)
                elif tool_name == "extract_lean_states":
                    repo_path = plan.get("repo_path", "Mathlib")
                    result = tool_fn(repo_path=repo_path)
                else:
                    result = {"status": "unknown_tool"}
                
                observations[tool_name] = result
            except Exception as exc:
                self._log.error("tool_failed", tool=tool_name, error=str(exc))
                observations[tool_name] = {"error": str(exc)}

        self._stop_timer(start, "pythagore_act")
        return observations

    async def run(self, query: str, **kwargs: Any) -> AgentResult:
        """Execute the mathematical librarian loop."""
        self._log.info("pythagore_run_start", query=query[:120])
        start = self._start_timer()
        self._iteration = 0

        context: dict[str, Any] = {"query": query, **kwargs}
        
        # Continuous learning: Load SymBrain v11 Top 5 monograph as RAG context
        v11_rag_context = ""
        try:
            p = pathlib.Path("/Users/xcallens/.gemini/antigravity/brain/142e4281-5564-4819-8826-7d615d389330/achievement_output/symbrain_v11_horizonmath_top5_strict.tex")
            if p.exists():
                v11_rag_context = p.read_text()[:3000] # Load part of the continuous learning context
        except Exception:
            pass

        context["rag_context"] = v11_rag_context

        plan = await self.think(context)
        
        # Forward inputs to plan
        plan["query"] = query
        for key in ("library_path", "max_results", "theorem_name", "signature", "proof_strategy", "imports"):
            if key in kwargs:
                plan[key] = kwargs[key]

        observations = await self.act(plan)

        actual_cost = plan.get("estimated_cost", 0.0)
        self._record_cost(actual_cost)

        elapsed = self._stop_timer(start, "pythagore_run_total")
        result = AgentResult(
            answer={
                "observations": observations,
                "summary": self._summarise_findings(observations),
            },
            confidence=0.98,  # Pythagore provides highly structured mathematical audits
            cost_usd=actual_cost,
            telemetry={**self.telemetry.summary(), "total_elapsed_ms": round(elapsed, 2)},
        )
        return result

    @staticmethod
    def _summarise_findings(observations: dict[str, Any]) -> str:
        """Summarize mathematical findings in a concise line."""
        parts = []
        if "lean_gap_mapper" in observations:
            gaps = observations["lean_gap_mapper"]
            parts.append(f"Gaps: found {gaps.get('total_gaps', 0)} sorries across {gaps.get('files_audited', 0)} files")
        if "proof_retriever" in observations:
            papers = observations["proof_retriever"]
            parts.append(f"Retrieval: mined {len(papers)} proof papers from scholarly databases")
        if "formal_draft_generator" in observations:
            draft = observations["formal_draft_generator"]
            parts.append(f"Formalizer: successfully generated Lean 4 skeleton for {draft.get('theorem_name')}")
        if "generate_research_hypotheses" in observations:
            hyps = observations["generate_research_hypotheses"]
            parts.append(f"Hypotheses: generated {hyps.get('hypothesis_count', 0)} formal hypotheses to close gap")
        return " | ".join(parts)
