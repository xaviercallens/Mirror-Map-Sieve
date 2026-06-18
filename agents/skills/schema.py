# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Agora Skills — Guardrailed, reusable capabilities for Agora agents.

An Agora Skill is a bounded, auditable unit of work that any agent can invoke.
Skills separate WHAT an agent can do from WHO the agent is, making pipelines
composable and reusable as templates.

Key design principles:
  1. **Determinism first** — prefer deterministic backends over LLMs
  2. **Budget guarded** — every skill has a hard spend cap
  3. **Audit trail** — every invocation is logged
  4. **Fallback chain** — if primary backend fails, try next in priority order
  5. **Human gate** — certain actions require human approval

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Backend Types
# ---------------------------------------------------------------------------

class BackendType(Enum):
    """Type of execution backend for a skill."""
    DETERMINISTIC = auto()   # Lean tactics, lake build, native_decide
    LEARNED = auto()         # LeanBert latent space, GAN critic
    LLM_SELFHOSTED = auto()  # DeepSeek-Prover-V2-7B on GCP
    LLM_API = auto()         # DeepSeek-671B API, Gemini API
    HUMAN = auto()           # Requires human input


class AuditLevel(Enum):
    """How much to log for each skill invocation."""
    FULL = auto()     # Every input/output/intermediate step
    SUMMARY = auto()  # Input, output, duration, cost
    NONE = auto()     # Nothing (for trivial skills)


# ---------------------------------------------------------------------------
# Skill Backend
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SkillBackend:
    """A single execution backend for a skill.

    Backends are tried in priority order (lower = first). If a backend
    fails, the skill falls through to the next one.

    Attributes:
        backend_type: Deterministic, learned, LLM, or human
        engine: Identifier (e.g. "lake_build", "leanbert", "deepseek_7b")
        endpoint: GCP URL, "local", or "api"
        priority: Lower = tried first
        cost_per_call_usd: Estimated cost per invocation
        fallback_to: Engine name of the next backend to try
        gpu_required: Whether this backend needs GPU
    """
    backend_type: BackendType
    engine: str
    endpoint: str = "local"
    priority: int = 0
    cost_per_call_usd: float = 0.0
    fallback_to: Optional[str] = None
    gpu_required: bool = False


# ---------------------------------------------------------------------------
# Skill Guardrails
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SkillGuardrails:
    """Hard limits that cannot be overridden by agents.

    Guardrails are enforced at the skill framework level, not by the
    agent itself. This prevents agents from bypassing budget or safety limits.

    Attributes:
        max_budget_usd: Maximum spend per invocation
        max_duration_s: Wall-clock timeout
        max_retries: How many times to retry on failure
        requires_approval: Whether human must approve before execution
        forbidden_actions: Actions the skill is NOT allowed to perform
        audit_level: How much to log
        allowed_agents: Which agents can invoke this skill (empty = all)
    """
    max_budget_usd: float = 1.0
    max_duration_s: int = 300
    max_retries: int = 3
    requires_approval: bool = False
    forbidden_actions: tuple[str, ...] = ()
    audit_level: AuditLevel = AuditLevel.SUMMARY
    allowed_agents: tuple[str, ...] = ()  # Empty = all agents


# ---------------------------------------------------------------------------
# Agora Skill
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AgoraSkill:
    """A guardrailed, reusable capability for Agora agents.

    Skills are registered in the SkillRegistry and can be invoked by
    any agent that has permission (per guardrails.allowed_agents).

    Attributes:
        skill_id: Unique identifier (e.g. "SK-001")
        name: Human-readable name (e.g. "literature_survey")
        description: What this skill does
        version: Semantic version
        required_tools: External tools needed (e.g. ["web_search"])
        guardrails: Hard limits on the skill
        backends: Ordered list of execution backends
        input_schema: JSON schema for input validation (optional)
        output_schema: JSON schema for output validation (optional)
    """
    skill_id: str
    name: str
    description: str
    version: str = "1.0.0"
    required_tools: tuple[str, ...] = ()
    guardrails: SkillGuardrails = field(default_factory=SkillGuardrails)
    backends: tuple[SkillBackend, ...] = ()
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)

    @property
    def primary_backend(self) -> Optional[SkillBackend]:
        """Return the highest-priority (lowest number) backend."""
        if not self.backends:
            return None
        return min(self.backends, key=lambda b: b.priority)

    @property
    def is_deterministic(self) -> bool:
        """True if the primary backend is deterministic."""
        primary = self.primary_backend
        return primary is not None and primary.backend_type == BackendType.DETERMINISTIC

    @property
    def estimated_cost(self) -> float:
        """Estimated cost of one invocation using primary backend."""
        primary = self.primary_backend
        return primary.cost_per_call_usd if primary else 0.0
