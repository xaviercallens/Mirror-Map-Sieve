# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Hypatie Librarian Agent — The conceptual astronomical navigator of the Agora.

Hypatie manages the Alexandrie Storage Hub, cataloging scientific outcomes
(serialized weights, Lean 4 proofs, numerical datasets, and LaTeX papers),
authoring Socratic explainers/reproduction checklists, generating conceptual
suggestions via astrolabe-guided structural alignment, and editing/reviewing/compiling
LaTeX documents dynamically integrated with the octree-agora editor.

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import pathlib
from typing import Any

import structlog

from agents.base import AbstractAgent, AgentConfig, AgentResult, AgentRole
from agents.hypatie.tools.archive_vault import catalog_scientific_work
from agents.hypatie.tools.astrolabe_navigator import navigate_astrolabe
from agents.hypatie.tools.latex_synthesizer import generate_latex_source
from agents.hypatie.tools.latex_reviewer import review_and_repair_latex
from agents.hypatie.tools.latex_compiler import compile_latex_to_pdf
from agents.hypatie.tools.octree_db_sync import OctreeSyncClient

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT_PATH = pathlib.Path(__file__).parent / "prompts" / "system_prompt.md"


def pull_octree_project(project_id: str, auth_token: str | None = None) -> dict[str, str]:
    """Pull all files in an octree project from Supabase."""
    client = OctreeSyncClient(auth_token=auth_token)
    return client.pull_project_workspace(project_id)


def push_octree_project(project_id: str, workspace: dict[str, str], auth_token: str | None = None) -> int:
    """Push modified workspace files back to Supabase."""
    client = OctreeSyncClient(auth_token=auth_token)
    return client.push_project_workspace(project_id, workspace)


HYPATIE_TOOLS = {
    "archive_vault": catalog_scientific_work,
    "astrolabe_navigator": navigate_astrolabe,
    "latex_synthesizer": generate_latex_source,
    "latex_reviewer": review_and_repair_latex,
    "latex_compiler": compile_latex_to_pdf,
    "pull_octree_project": pull_octree_project,
    "push_octree_project": push_octree_project,
}


class HypatieAgent(AbstractAgent):
    """Librarian and Astronomical Navigator agent of Alexandrie."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                name="hypatie",
                model="gemini-2.5-pro",
                role=AgentRole.ORCHESTRATOR,  # Acts as an orchestrator of scientific memory
                budget_limit=100.0,
                project_budget=500.0,
                timeout_ms=60_000,
                tools=list(HYPATIE_TOOLS.keys()),
            )
        super().__init__(config)
        self._tools = HYPATIE_TOOLS
        self._system_prompt = self._load_system_prompt()

    @staticmethod
    def _load_system_prompt() -> str:
        """Load Hypatie's neoplatonist librarian prompt from disk."""
        if _SYSTEM_PROMPT_PATH.exists():
            return _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        return "You are Hypatie, the astrolabe-guided neoplatonist librarian of Alexandrie."

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """Align the request with Diophantine precision to plan action."""
        self._guard_iterations()
        start = self._start_timer()

        query: str = context.get("query", "")
        plan: dict[str, Any] = {
            "tools": [],
            "estimated_cost": 0.0,
            "rationale": "",
        }

        query_lower = query.lower()

        # Decide between Ingestion, Navigation, LaTeX Processing, or Workspace Sync
        if any(kw in query_lower for kw in ("pull", "fetch project", "download project", "import")):
            plan["tools"].append("pull_octree_project")
            plan["estimated_cost"] += 0.02
            plan["rationale"] = "Workspace Pull selected. Retrieving project files from Supabase."
        elif any(kw in query_lower for kw in ("push", "upload project", "save project", "export")):
            plan["tools"].append("push_octree_project")
            plan["estimated_cost"] += 0.05
            plan["rationale"] = "Workspace Push selected. Uploading modified files to Supabase."
        elif any(kw in query_lower for kw in ("store", "save", "catalog", "archive", "ingest", "vault", "room")):
            plan["tools"].append("archive_vault")
            plan["estimated_cost"] += 0.05
            plan["rationale"] = "Ingestion path selected. Cataloging scientific work in Alexandrie."
        elif any(kw in query_lower for kw in ("search", "find", "align", "correlate", "astrolabe", "conic", "idea", "zenith")):
            plan["tools"].append("astrolabe_navigator")
            plan["estimated_cost"] += 0.02
            plan["rationale"] = "Navigation path selected. Aligning conceptual conics using the astrolabe navigator."
        elif any(kw in query_lower for kw in ("synthesize", "draft", "latex", "document", "tex", "write")):
            plan["tools"].append("latex_synthesizer")
            plan["estimated_cost"] += 0.10
            plan["rationale"] = "LaTeX synthesis path selected. Drafting formal mathematical document."
        elif any(kw in query_lower for kw in ("review", "repair", "fix", "syntax", "error", "broken")):
            plan["tools"].append("latex_reviewer")
            plan["estimated_cost"] += 0.05
            plan["rationale"] = "LaTeX repair path selected. AI-fixing broken LaTeX syntax."
        elif any(kw in query_lower for kw in ("compile", "pdf", "build", "render")):
            plan["tools"].append("latex_compiler")
            plan["estimated_cost"] += 0.05
            plan["rationale"] = "LaTeX compile path selected. Rendering document to PDF."
        else:
            # Default to conceptual astrolabe navigation
            plan["tools"].append("astrolabe_navigator")
            plan["estimated_cost"] += 0.02
            plan["rationale"] = "Fallback: astronomical concept search in Alexandrie."

        self._check_budget(plan["estimated_cost"])
        self._stop_timer(start, "hypatie_think")
        return plan

    async def act(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Execute the planned astrolabe or vault tools."""
        start = self._start_timer()
        observations: dict[str, Any] = {}

        for tool_name in plan.get("tools", []):
            tool_fn = self._tools.get(tool_name)
            if tool_fn is None:
                continue

            try:
                if tool_name == "pull_octree_project":
                    result = tool_fn(
                        project_id=plan.get("project_id", ""),
                        auth_token=plan.get("auth_token"),
                    )
                elif tool_name == "push_octree_project":
                    result = tool_fn(
                        project_id=plan.get("project_id", ""),
                        workspace=plan.get("workspace", {}),
                        auth_token=plan.get("auth_token"),
                    )
                elif tool_name == "archive_vault":
                    result = tool_fn(
                        artifact_id=plan.get("artifact_id", "artifact_1"),
                        title=plan.get("title", "Agora scientific payload"),
                        payload=plan.get("payload", "Raw payload data"),
                        artifact_type=plan.get("artifact_type", "paper"),
                        room_type=plan.get("room_type", "open_access"),
                        tags=plan.get("tags", []),
                        metrics=plan.get("metrics", {}),
                        dependencies=plan.get("dependencies", []),
                    )
                elif tool_name == "astrolabe_navigator":
                    result = tool_fn(
                        focus_topic=plan.get("query", "conic alignments"),
                        required_alignment=plan.get("required_alignment", 0.30),
                    )
                elif tool_name == "latex_synthesizer":
                    result = tool_fn(
                        title=plan.get("title", "Agora Scientific Document"),
                        raw_content=plan.get("raw_content", plan.get("query", "")),
                        document_type=plan.get("document_type", "general"),
                        document_class=plan.get("document_class", "article"),
                        include_preamble=plan.get("include_preamble", True),
                    )
                elif tool_name == "latex_reviewer":
                    result = tool_fn(
                        latex_code=plan.get("latex_code", plan.get("query", "")),
                        focus_errors=plan.get("focus_errors", "Syntax, unclosed environments, math mode boundary violations"),
                        max_iterations=plan.get("max_iterations", 3),
                    )
                elif tool_name == "latex_compiler":
                    result = tool_fn(
                        latex_code=plan.get("latex_code", ""),
                        timeout=plan.get("timeout", 60),
                    )
                else:
                    result = {"status": "unknown_tool"}
                
                observations[tool_name] = result
            except Exception as exc:
                self._log.error("tool_failed", tool=tool_name, error=str(exc))
                observations[tool_name] = {"error": str(exc)}

        self._stop_timer(start, "hypatie_act")
        return observations

    async def run(self, query: str, **kwargs: Any) -> AgentResult:
        """Execute the librarian agent loop."""
        self._log.info("hypatie_run_start", query=query[:120])
        start = self._start_timer()
        self._iteration = 0

        context: dict[str, Any] = {"query": query, **kwargs}
        plan = await self.think(context)
        
        # Forward inputs to plan
        plan["query"] = query
        for key in ("project_id", "workspace", "auth_token", "artifact_id", "title",
                     "payload", "artifact_type", "room_type", "tags", "metrics",
                     "dependencies", "required_alignment", "document_type",
                     "document_class", "include_preamble", "latex_code", "focus_errors",
                     "max_iterations", "timeout"):
            if key in kwargs:
                plan[key] = kwargs[key]

        observations = await self.act(plan)

        actual_cost = plan.get("estimated_cost", 0.0)
        self._record_cost(actual_cost)

        elapsed = self._stop_timer(start, "hypatie_run_total")
        result = AgentResult(
            answer=observations,
            confidence=0.95,  # Hypatie offers highly structured and reliable conceptual guidance
            cost_usd=actual_cost,
            telemetry={**self.telemetry.summary(), "total_elapsed_ms": round(elapsed, 2)},
        )
        return result
