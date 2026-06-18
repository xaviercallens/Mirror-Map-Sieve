# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Alexandrie Science Library — GCS-backed checkpoint workspace for agents.

Provides temporary storage for pipeline intermediary results so that
orchestrators can resume from the last successful stage after a failure.
Also stores per-agent lessons learned and memory for self-improvement
across runs.

GCS Layout::

    gs://{bucket}/science_library/
        checkpoints/{run_id}/
            stage_01_socrate_rules.json
            stage_02_degennes_hypotheses.json
            ...
            stage_09_hypatia_monograph.tex
        lessons_learned/{agent_name}/{domain}/{timestamp}.json
        memory/{agent_name}/memory.json
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from google.api_core.exceptions import GoogleAPIError

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Lesson Learned Data Model
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class LessonLearned:
    """A single lesson extracted after a pipeline run completion or failure.

    Captures what worked, what failed, and actionable improvements so that
    agents can bootstrap subsequent runs with accumulated experience.
    """

    run_id: str
    agent_name: str
    domain: str
    pipeline: str  # "symposium" | "discovery" | "or_optimization"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    success: bool = False
    what_worked: list[str] = field(default_factory=list)
    what_failed: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    # e.g. {"error_rate": 0.001, "latex_compile_success": True,
    #        "cost_usd": 23.0, "duration_s": 106.0, "hypotheses_generated": 25}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LessonLearned:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Science Library
# ---------------------------------------------------------------------------

class ScienceLibrary:
    """Temporary GCS-backed workspace for ongoing agent work and checkpointing.

    Each pipeline run gets a namespace under ``science_library/checkpoints/{run_id}/``
    where intermediary stage results are stored as JSON. On failure, the
    orchestrator can call :meth:`load_checkpoint` to resume from the last
    successful stage instead of re-running the entire (expensive) pipeline.

    Lessons learned are stored per-agent and per-domain so that future runs
    can load relevant experience from past attempts.
    """

    PREFIX = "science_library"

    def __init__(self, bucket: Any | None = None) -> None:
        """Initialize the Science Library.

        Args:
            bucket: A ``google.cloud.storage.Bucket`` instance. If *None*,
                    checkpoints are stored only in the local cache.
        """
        self._bucket = bucket
        self._log = logger.bind(component="science_library")

    # ------------------------------------------------------------------
    # Checkpointing
    # ------------------------------------------------------------------

    def checkpoint_stage(
        self,
        run_id: str,
        stage_name: str,
        data: dict[str, Any],
    ) -> str:
        """Persist intermediary results for a pipeline stage.

        Args:
            run_id: Unique pipeline run identifier.
            stage_name: Human-readable stage name (e.g., ``"stage_02_degennes"``).
            data: Serializable stage output to checkpoint.

        Returns:
            GCS URI of the checkpoint, or empty string on failure.
        """
        object_name = (
            f"{self.PREFIX}/checkpoints/{run_id}/{stage_name}.json"
        )
        payload = json.dumps(data, indent=2, default=str, ensure_ascii=False)

        if self._bucket:
            try:
                blob = self._bucket.blob(object_name)
                blob.upload_from_string(payload, content_type="application/json")
                uri = f"gs://{self._bucket.name}/{object_name}"
                self._log.info(
                    "checkpoint_saved",
                    run_id=run_id,
                    stage=stage_name,
                    uri=uri,
                    size_bytes=len(payload),
                )
                return uri
            except (GoogleAPIError, OSError, json.JSONDecodeError, ValueError) as exc:
                self._log.error(
                    "checkpoint_save_failed",
                    run_id=run_id,
                    stage=stage_name,
                    error=str(exc),
                )
        return ""

    def checkpoint_tex(
        self,
        run_id: str,
        stage_name: str,
        tex_content: str,
    ) -> str:
        """Persist raw LaTeX content for a stage (e.g. Hypatia monograph).

        Args:
            run_id: Unique pipeline run identifier.
            stage_name: Stage name (e.g., ``"stage_09_hypatia_monograph"``).
            tex_content: Raw LaTeX document string.

        Returns:
            GCS URI of the checkpoint, or empty string on failure.
        """
        object_name = (
            f"{self.PREFIX}/checkpoints/{run_id}/{stage_name}.tex"
        )

        if self._bucket:
            try:
                blob = self._bucket.blob(object_name)
                blob.upload_from_string(
                    tex_content, content_type="application/x-latex"
                )
                uri = f"gs://{self._bucket.name}/{object_name}"
                self._log.info(
                    "tex_checkpoint_saved",
                    run_id=run_id,
                    stage=stage_name,
                    uri=uri,
                    size_kb=len(tex_content) // 1024,
                )
                return uri
            except (GoogleAPIError, OSError, json.JSONDecodeError, ValueError) as exc:
                self._log.error(
                    "tex_checkpoint_save_failed",
                    run_id=run_id,
                    stage=stage_name,
                    error=str(exc),
                )
        return ""

    def load_checkpoint(
        self,
        run_id: str,
        stage_name: str,
    ) -> dict[str, Any] | None:
        """Load a previously-saved checkpoint for a stage.

        Args:
            run_id: Pipeline run identifier.
            stage_name: Stage name to load.

        Returns:
            The checkpoint data dict, or *None* if no checkpoint exists.
        """
        object_name = (
            f"{self.PREFIX}/checkpoints/{run_id}/{stage_name}.json"
        )

        if self._bucket:
            try:
                blob = self._bucket.blob(object_name)
                if blob.exists():
                    content = blob.download_as_text()
                    self._log.info(
                        "checkpoint_loaded",
                        run_id=run_id,
                        stage=stage_name,
                    )
                    return json.loads(content)
            except (GoogleAPIError, OSError, json.JSONDecodeError, ValueError) as exc:
                self._log.warning(
                    "checkpoint_load_failed",
                    run_id=run_id,
                    stage=stage_name,
                    error=str(exc),
                )
        return None

    def list_checkpoints(self, run_id: str) -> list[str]:
        """List all checkpoint stage names for a given run.

        Returns:
            Sorted list of stage names (e.g., ``["stage_01_socrate_rules",
            "stage_02_degennes_hypotheses"]``).
        """
        prefix = f"{self.PREFIX}/checkpoints/{run_id}/"
        stages: list[str] = []

        if self._bucket:
            try:
                blobs = self._bucket.list_blobs(prefix=prefix)
                for blob in blobs:
                    # Extract stage name from path
                    name = blob.name.replace(prefix, "")
                    # Remove extension (.json or .tex)
                    stage = name.rsplit(".", 1)[0] if "." in name else name
                    if stage:
                        stages.append(stage)
            except (GoogleAPIError, OSError, json.JSONDecodeError, ValueError) as exc:
                self._log.warning(
                    "checkpoint_list_failed",
                    run_id=run_id,
                    error=str(exc),
                )

        return sorted(stages)

    # ------------------------------------------------------------------
    # Lessons Learned
    # ------------------------------------------------------------------

    def store_lesson_learned(self, lesson: LessonLearned) -> str:
        """Persist a lesson learned after a pipeline run.

        Args:
            lesson: The lesson to store.

        Returns:
            GCS URI of the stored lesson, or empty string on failure.
        """
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        domain_slug = lesson.domain.lower().replace(" ", "_")[:50]
        object_name = (
            f"{self.PREFIX}/lessons_learned/"
            f"{lesson.agent_name}/{domain_slug}/{ts}_{lesson.run_id[:8]}.json"
        )
        payload = json.dumps(lesson.to_dict(), indent=2, default=str)

        if self._bucket:
            try:
                blob = self._bucket.blob(object_name)
                blob.upload_from_string(payload, content_type="application/json")
                uri = f"gs://{self._bucket.name}/{object_name}"
                self._log.info(
                    "lesson_learned_stored",
                    agent=lesson.agent_name,
                    domain=domain_slug,
                    success=lesson.success,
                    uri=uri,
                )
                return uri
            except (GoogleAPIError, OSError, json.JSONDecodeError, ValueError) as exc:
                self._log.error(
                    "lesson_learned_store_failed",
                    agent=lesson.agent_name,
                    error=str(exc),
                )
        return ""

    def load_lessons(
        self,
        agent_name: str,
        domain: str | None = None,
        limit: int = 10,
    ) -> list[LessonLearned]:
        """Load past lessons for an agent, optionally filtered by domain.

        Args:
            agent_name: Agent whose lessons to load.
            domain: If provided, filter to this domain only.
            limit: Maximum number of lessons to return (most recent first).

        Returns:
            List of :class:`LessonLearned` objects, newest first.
        """
        if domain:
            domain_slug = domain.lower().replace(" ", "_")[:50]
            prefix = (
                f"{self.PREFIX}/lessons_learned/{agent_name}/{domain_slug}/"
            )
        else:
            prefix = f"{self.PREFIX}/lessons_learned/{agent_name}/"

        lessons: list[LessonLearned] = []

        if self._bucket:
            try:
                blobs = list(self._bucket.list_blobs(prefix=prefix))
                # Sort by name descending (timestamp prefix ensures recency)
                blobs.sort(key=lambda b: b.name, reverse=True)
                for blob in blobs[:limit]:
                    try:
                        content = blob.download_as_text()
                        data = json.loads(content)
                        lessons.append(LessonLearned.from_dict(data))
                    except Exception:
                        continue
            except (GoogleAPIError, OSError, json.JSONDecodeError, ValueError) as exc:
                self._log.warning(
                    "lessons_load_failed",
                    agent=agent_name,
                    error=str(exc),
                )

        return lessons

    # ------------------------------------------------------------------
    # Agent Memory
    # ------------------------------------------------------------------

    def save_memory(self, agent_name: str, memory: dict[str, Any]) -> str:
        """Save or update an agent's persistent memory.

        Args:
            agent_name: Agent identifier.
            memory: Arbitrary memory dict (the agent decides its schema).

        Returns:
            GCS URI of the memory file, or empty string on failure.
        """
        object_name = f"{self.PREFIX}/memory/{agent_name}/memory.json"
        memory["_last_updated"] = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(memory, indent=2, default=str, ensure_ascii=False)

        if self._bucket:
            try:
                blob = self._bucket.blob(object_name)
                blob.upload_from_string(payload, content_type="application/json")
                uri = f"gs://{self._bucket.name}/{object_name}"
                self._log.info("agent_memory_saved", agent=agent_name, uri=uri)
                return uri
            except (GoogleAPIError, OSError, json.JSONDecodeError, ValueError) as exc:
                self._log.error(
                    "agent_memory_save_failed",
                    agent=agent_name,
                    error=str(exc),
                )
        return ""

    def load_memory(self, agent_name: str) -> dict[str, Any]:
        """Load an agent's persistent memory.

        Args:
            agent_name: Agent identifier.

        Returns:
            The memory dict, or an empty dict if none exists.
        """
        object_name = f"{self.PREFIX}/memory/{agent_name}/memory.json"

        if self._bucket:
            try:
                blob = self._bucket.blob(object_name)
                if blob.exists():
                    content = blob.download_as_text()
                    self._log.info("agent_memory_loaded", agent=agent_name)
                    return json.loads(content)
            except (GoogleAPIError, OSError, json.JSONDecodeError, ValueError) as exc:
                self._log.warning(
                    "agent_memory_load_failed",
                    agent=agent_name,
                    error=str(exc),
                )
        return {}

    def format_lessons_for_prompt(
        self,
        agent_name: str,
        domain: str | None = None,
        limit: int = 5,
    ) -> str:
        """Format lessons learned as a prompt injection for an agent.

        Produces a structured text block that can be prepended to an agent's
        system prompt so it benefits from past experience.

        Args:
            agent_name: Agent to retrieve lessons for.
            domain: Optional domain filter.
            limit: Max number of lessons.

        Returns:
            Formatted multi-line string, or empty string if no lessons.
        """
        lessons = self.load_lessons(agent_name, domain, limit)
        if not lessons:
            return ""

        lines = [
            f"## Lessons from {len(lessons)} Previous Runs",
            "",
        ]
        for i, lesson in enumerate(lessons, 1):
            status = "✅ SUCCESS" if lesson.success else "❌ FAILURE"
            lines.append(f"### Run {i} ({status} — {lesson.timestamp[:10]})")
            if lesson.what_worked:
                lines.append("**What worked:**")
                for item in lesson.what_worked:
                    lines.append(f"  - {item}")
            if lesson.what_failed:
                lines.append("**What failed:**")
                for item in lesson.what_failed:
                    lines.append(f"  - {item}")
            if lesson.improvements:
                lines.append("**Improvements for next run:**")
                for item in lesson.improvements:
                    lines.append(f"  - {item}")
            if lesson.metrics:
                lines.append(f"**Metrics:** {lesson.metrics}")
            lines.append("")

        return "\n".join(lines)
