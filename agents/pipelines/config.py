# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Symposium pipeline configuration.

:class:`SymposiumConfig` is a frozen (immutable) dataclass that captures
every tuneable parameter for a full Agora Symposium research run — from
the research question and agent swarm size to model selection, thinking
depth, and budget caps.

Validation is enforced in ``__post_init__`` so that invalid configs
fail fast before any LLM calls are made.

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from google.antigravity.types import ThinkingLevel
from alexandrie.metadata import RoomType


# ---------------------------------------------------------------------------
# Default Alien Mathematics Formalisms
# ---------------------------------------------------------------------------

_DEFAULT_ALIEN_MATH_FORMALISMS: list[str] = [
    "Asymptotic tensor limits (ω=2)",
    "Ryu-Takayanagi holographic entropy bounds",
    "Non-commutative operator algebras",
    "Tensor network renormalization (MERA/TTN)",
    "Spectral gap analysis on Cayley graphs",
]

_DEFAULT_COMPARISON_METHODS: list[str] = [
    "Classical linear regression / OLS",
    "Monte Carlo simulation",
    "Finite element methods (FEM)",
    "Traditional queue theory (Erlang-C, M/G/k)",
    "Integer programming / constraint satisfaction",
]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SymposiumConfig:
    """Immutable configuration for a full Agora Symposium pipeline run.

    All parameters have sensible defaults so that a minimal config only
    requires ``scientific_field`` and ``research_question``.

    Attributes:
        symposium_id: Unique identifier for this run (auto-generated if omitted).
        scientific_field: The broad scientific domain (e.g. ``"Airport Operations"``).
        research_question: The specific question driving the symposium.
        target_pages: Target monograph page count (50–150).
        num_swarm_agents: Number of DeGennes swarm agents for hypothesis generation.
        hypotheses_per_agent: Hypotheses each swarm agent produces.
        top_k_hypotheses: Number of top hypotheses selected after adversarial review.
        peer_review_loops: Number of Socratic peer-review iterations.
        thinking_level: Default chain-of-thought depth for all agents.
        model_name: Foundation model identifier.
        alien_math_formalisms: Alien Mathematics formalisms to explore.
        domain_constraints: Domain-specific constraints (e.g. ICAO regulations).
        comparison_methods: Classical methods to compare against.
        vault_room_type: Alexandrie Vault room for artifact storage.
        gcs_output_bucket: GCS bucket for pipeline outputs (PDFs, TeX).
        alexandrie_bucket: GCS bucket for the Alexandrie Vault.
        budget_limit_usd: Maximum spend for the entire pipeline run.
        owner_email: Contact email for the pipeline owner.
    """

    # ── Research definition ──────────────────────────────────────────────
    symposium_id: str = field(
        default_factory=lambda: f"SYM-{uuid.uuid4().hex[:12].upper()}"
    )
    scientific_field: str = ""
    research_question: str = ""

    # ── Pipeline parameters ──────────────────────────────────────────────
    target_pages: int = 100
    num_swarm_agents: int = 5
    hypotheses_per_agent: int = 5
    top_k_hypotheses: int = 5
    peer_review_loops: int = 5
    eiffel_correction_rounds: int = 3

    # ── Model configuration ──────────────────────────────────────────────
    thinking_level: ThinkingLevel = ThinkingLevel.HIGH
    model_name: str = "gemini-2.5-pro"

    # ── Alien Mathematics ────────────────────────────────────────────────
    alien_math_formalisms: tuple[str, ...] = field(
        default_factory=lambda: tuple(_DEFAULT_ALIEN_MATH_FORMALISMS)
    )
    domain_constraints: tuple[str, ...] = field(default_factory=tuple)
    comparison_methods: tuple[str, ...] = field(
        default_factory=lambda: tuple(_DEFAULT_COMPARISON_METHODS)
    )

    # ── Storage / infrastructure ─────────────────────────────────────────
    vault_room_type: RoomType = RoomType.PRIVATE
    gcs_output_bucket: str = "agora-autoresearch-001-outputs"
    alexandrie_bucket: str = "socrateai-alexandrie-vault"

    # ── Budget ───────────────────────────────────────────────────────────
    budget_limit_usd: float = 50.0

    # ── Ownership ────────────────────────────────────────────────────────
    owner_email: str = "callensxavier@gmail.com"

    # ── Validation ───────────────────────────────────────────────────────

    def __post_init__(self) -> None:
        """Validate invariants at construction time."""
        if not self.scientific_field:
            raise ValueError("scientific_field must be a non-empty string")
        if not self.research_question:
            raise ValueError("research_question must be a non-empty string")

        if not (50 <= self.target_pages <= 150):
            raise ValueError(
                f"target_pages must be in [50, 150], got {self.target_pages}"
            )

        if self.num_swarm_agents < 1:
            raise ValueError(
                f"num_swarm_agents must be ≥ 1, got {self.num_swarm_agents}"
            )
        if self.hypotheses_per_agent < 1:
            raise ValueError(
                f"hypotheses_per_agent must be ≥ 1, got {self.hypotheses_per_agent}"
            )
        if self.top_k_hypotheses < 1:
            raise ValueError(
                f"top_k_hypotheses must be ≥ 1, got {self.top_k_hypotheses}"
            )
        if self.peer_review_loops < 1:
            raise ValueError(
                f"peer_review_loops must be ≥ 1, got {self.peer_review_loops}"
            )
        if self.budget_limit_usd <= 0:
            raise ValueError(
                f"budget_limit_usd must be > 0, got {self.budget_limit_usd}"
            )
        if not (1 <= self.eiffel_correction_rounds <= 5):
            raise ValueError(
                f"eiffel_correction_rounds must be in [1, 5], got {self.eiffel_correction_rounds}"
            )

    # ── Derived properties ───────────────────────────────────────────────

    @property
    def total_raw_hypotheses(self) -> int:
        """Total hypotheses generated before adversarial filtering."""
        return self.num_swarm_agents * self.hypotheses_per_agent

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "symposium_id": self.symposium_id,
            "scientific_field": self.scientific_field,
            "research_question": self.research_question,
            "target_pages": self.target_pages,
            "num_swarm_agents": self.num_swarm_agents,
            "hypotheses_per_agent": self.hypotheses_per_agent,
            "top_k_hypotheses": self.top_k_hypotheses,
            "peer_review_loops": self.peer_review_loops,
            "thinking_level": self.thinking_level.name,
            "model_name": self.model_name,
            "alien_math_formalisms": list(self.alien_math_formalisms),
            "domain_constraints": list(self.domain_constraints),
            "comparison_methods": list(self.comparison_methods),
            "vault_room_type": self.vault_room_type.name,
            "gcs_output_bucket": self.gcs_output_bucket,
            "alexandrie_bucket": self.alexandrie_bucket,
            "budget_limit_usd": self.budget_limit_usd,
            "eiffel_correction_rounds": self.eiffel_correction_rounds,
            "owner_email": self.owner_email,
            "total_raw_hypotheses": self.total_raw_hypotheses,
        }
