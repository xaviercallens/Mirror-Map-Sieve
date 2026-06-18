# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Agent Memory — Persistent memory and self-improvement for pipeline agents.

Provides a thin API for pipeline orchestrators to:
1. Load an agent's accumulated memory before a run.
2. Generate a structured LessonLearned at run completion.
3. Inject past experience into agent prompts.

Usage::

    from agents.memory.agent_memory import AgentMemoryManager

    mgr = AgentMemoryManager(science_library)

    # At pipeline start — load past experience
    lessons_prompt = mgr.get_experience_prompt("Hypatia", domain="Airport Operations")

    # At pipeline end — record what happened
    mgr.record_run_outcome(
        run_id="abc123",
        agent_name="Hypatia",
        domain="Airport Operations",
        pipeline="symposium",
        success=True,
        what_worked=["LaTeX sanitizer prevented hbox crashes"],
        what_failed=[],
        improvements=["Add citation cross-reference validation"],
        metrics={"cost_usd": 23.0, "duration_s": 106, "pages": 19},
    )
"""

from __future__ import annotations

from typing import Any

import structlog

from alexandrie.science_library import LessonLearned, ScienceLibrary

logger = structlog.get_logger(__name__)


class AgentMemoryManager:
    """High-level interface for agent memory and lessons learned.

    Wraps :class:`ScienceLibrary` with convenience methods tailored for
    pipeline orchestrators (Symposium, Discovery, OR/Opt).
    """

    def __init__(self, library: ScienceLibrary) -> None:
        self._lib = library
        self._log = logger.bind(component="agent_memory_manager")

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------

    def load_agent_memory(self, agent_name: str) -> dict[str, Any]:
        """Load persistent memory for an agent."""
        return self._lib.load_memory(agent_name)

    def save_agent_memory(
        self, agent_name: str, memory: dict[str, Any]
    ) -> str:
        """Save or update an agent's persistent memory."""
        return self._lib.save_memory(agent_name, memory)

    # ------------------------------------------------------------------
    # Experience Injection
    # ------------------------------------------------------------------

    def get_experience_prompt(
        self,
        agent_name: str,
        domain: str | None = None,
        limit: int = 5,
    ) -> str:
        """Generate a prompt fragment with past lessons for an agent.

        This should be prepended to the agent's system prompt so it
        benefits from accumulated experience across runs.

        Args:
            agent_name: The agent whose experience to retrieve.
            domain: Optional domain filter (e.g., "Airport Operations").
            limit: Maximum number of past lessons to include.

        Returns:
            Formatted markdown string, or empty string if no lessons exist.
        """
        return self._lib.format_lessons_for_prompt(agent_name, domain, limit)

    # ------------------------------------------------------------------
    # Run Outcome Recording
    # ------------------------------------------------------------------

    def record_run_outcome(
        self,
        run_id: str,
        agent_name: str,
        domain: str,
        pipeline: str,
        success: bool,
        what_worked: list[str] | None = None,
        what_failed: list[str] | None = None,
        improvements: list[str] | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> str:
        """Record a lesson learned after a pipeline run completes.

        Args:
            run_id: Pipeline run identifier.
            agent_name: Primary agent name (or "pipeline" for orchestrator-level).
            domain: Research domain (e.g., "Airline Revenue Management").
            pipeline: Pipeline type ("symposium", "discovery", "or_optimization").
            success: Whether the run completed successfully.
            what_worked: List of things that worked well.
            what_failed: List of things that failed or caused issues.
            improvements: Actionable improvements for the next run.
            metrics: Quantitative metrics (cost, duration, pages, etc.).

        Returns:
            GCS URI of the stored lesson.
        """
        lesson = LessonLearned(
            run_id=run_id,
            agent_name=agent_name,
            domain=domain,
            pipeline=pipeline,
            success=success,
            what_worked=what_worked or [],
            what_failed=what_failed or [],
            improvements=improvements or [],
            metrics=metrics or {},
        )

        uri = self._lib.store_lesson_learned(lesson)
        self._log.info(
            "run_outcome_recorded",
            run_id=run_id,
            agent=agent_name,
            domain=domain,
            success=success,
            uri=uri,
        )
        return uri

    # ------------------------------------------------------------------
    # Checkpoint Helpers (delegates to ScienceLibrary)
    # ------------------------------------------------------------------

    def checkpoint_stage(
        self,
        run_id: str,
        stage_name: str,
        data: dict[str, Any],
    ) -> str:
        """Save a pipeline stage checkpoint."""
        return self._lib.checkpoint_stage(run_id, stage_name, data)

    def load_checkpoint(
        self,
        run_id: str,
        stage_name: str,
    ) -> dict[str, Any] | None:
        """Load a previously-saved stage checkpoint."""
        return self._lib.load_checkpoint(run_id, stage_name)

    def list_checkpoints(self, run_id: str) -> list[str]:
        """List all available checkpoint stages for a run."""
        return self._lib.list_checkpoints(run_id)

    def find_resume_point(self, run_id: str) -> str | None:
        """Find the last successful checkpoint stage for resuming a failed run.

        Returns:
            The name of the last completed stage, or *None* if no checkpoints exist.
        """
        stages = self.list_checkpoints(run_id)
        return stages[-1] if stages else None
