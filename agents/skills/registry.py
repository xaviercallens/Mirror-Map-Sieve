# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Agora Skill Registry — Central catalog of all available skills.

The registry is the single source of truth for which skills exist,
which agents can use them, and how they are configured.

Usage:
    from agents.skills.registry import SKILL_REGISTRY, get_skill
    
    # Get a skill by ID
    lit_survey = get_skill("SK-001")
    
    # List all skills for an agent
    newton_skills = SKILL_REGISTRY.skills_for_agent("newton")

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from agents.skills.schema import (
    AgoraSkill,
    AuditLevel,
    BackendType,
    SkillBackend,
    SkillGuardrails,
)


# ---------------------------------------------------------------------------
# Skill Definitions (v4.2.0)
# ---------------------------------------------------------------------------

SKILLS: dict[str, AgoraSkill] = {

    # ── SK-001: Literature Survey ────────────────────────────────────────
    "SK-001": AgoraSkill(
        skill_id="SK-001",
        name="literature_survey",
        description="Exhaustive survey of known results, lower/upper bounds, "
                    "impossibility theorems, and computational evidence for a "
                    "mathematical claim or research question.",
        required_tools=("web_search", "arxiv_api", "mathlib_search"),
        guardrails=SkillGuardrails(
            max_budget_usd=2.0,
            max_duration_s=300,
            max_retries=2,
            audit_level=AuditLevel.FULL,
        ),
        backends=(
            SkillBackend(BackendType.LLM_API, "gemini", "api", priority=0,
                         cost_per_call_usd=0.15),
        ),
    ),

    # ── SK-002: Hypothesis Generation ────────────────────────────────────
    "SK-002": AgoraSkill(
        skill_id="SK-002",
        name="hypothesis_generation",
        description="Generate N candidate conjectures with informal proofs. "
                    "Filter by LeanBert novelty score (cosine distance > 0.3).",
        required_tools=("leanbert_embeddings",),
        guardrails=SkillGuardrails(
            max_budget_usd=3.0,
            max_duration_s=600,
            max_retries=2,
            forbidden_actions=("create_axiom",),
            audit_level=AuditLevel.FULL,
        ),
        backends=(
            SkillBackend(BackendType.LLM_API, "gemini", "api", priority=0,
                         cost_per_call_usd=0.25),
            SkillBackend(BackendType.LEARNED, "leanbert", "local", priority=1,
                         cost_per_call_usd=0.01),
        ),
    ),

    # ── SK-003: Autoformalization ────────────────────────────────────────
    "SK-003": AgoraSkill(
        skill_id="SK-003",
        name="autoformalize",
        description="Translate natural language mathematical statement to "
                    "Lean 4 code. Statement MUST type-check (no proof needed).",
        required_tools=("lean4_typecheck",),
        guardrails=SkillGuardrails(
            max_budget_usd=1.0,
            max_duration_s=120,
            max_retries=5,
            forbidden_actions=("create_axiom",),
            audit_level=AuditLevel.FULL,
        ),
        backends=(
            SkillBackend(BackendType.LLM_API, "gemini", "api", priority=0,
                         cost_per_call_usd=0.10),
            SkillBackend(BackendType.LLM_SELFHOSTED, "deepseek_7b",
                         "https://deepseek-prover-v2.internal.a.run.app/prove",
                         priority=1, cost_per_call_usd=0.05, gpu_required=True),
        ),
    ),

    # ── SK-004: Tactic Search ────────────────────────────────────────────
    "SK-004": AgoraSkill(
        skill_id="SK-004",
        name="tactic_search",
        description="Search for Lean 4 tactics to close a sorry gap. "
                    "Uses deterministic-first cascade.",
        required_tools=("lean4_compiler", "leanbert_critic"),
        guardrails=SkillGuardrails(
            max_budget_usd=2.0,
            max_duration_s=300,
            max_retries=3,
            audit_level=AuditLevel.FULL,
        ),
        backends=(
            # Priority 1: deterministic Lean tactics (FREE)
            SkillBackend(BackendType.DETERMINISTIC, "lean_tactics", "local",
                         priority=0, cost_per_call_usd=0.0),
            # Priority 2: LeanBert GAN critic (near-free)
            SkillBackend(BackendType.LEARNED, "leanbert", "local",
                         priority=1, cost_per_call_usd=0.01),
            # Priority 3: DeepSeek-Prover-V2-7B (self-hosted)
            SkillBackend(BackendType.LLM_SELFHOSTED, "deepseek_7b",
                         "https://deepseek-prover-v2.internal.a.run.app/prove",
                         priority=2, cost_per_call_usd=0.05, gpu_required=True),
            # Priority 4: Gemini creative fallback
            SkillBackend(BackendType.LLM_API, "gemini", "api",
                         priority=3, cost_per_call_usd=0.10),
            # Priority 5: DeepSeek-671B premium escalation
            SkillBackend(BackendType.LLM_API, "deepseek_671b",
                         "https://api.deepseek.com/chat/completions",
                         priority=4, cost_per_call_usd=0.50),
        ),
    ),

    # ── SK-005: Kernel Verification ──────────────────────────────────────
    "SK-005": AgoraSkill(
        skill_id="SK-005",
        name="kernel_verify",
        description="Run `lake build` on Lean 4 files. DETERMINISTIC — no LLM. "
                    "The Lean 4 kernel is the incorruptible judge.",
        required_tools=("lean4_compiler",),
        guardrails=SkillGuardrails(
            max_budget_usd=0.50,
            max_duration_s=600,
            max_retries=1,  # No retry — it either compiles or not
            audit_level=AuditLevel.FULL,
        ),
        backends=(
            SkillBackend(BackendType.DETERMINISTIC, "lake_build",
                         "https://lean-compiler.internal.a.run.app/build",
                         priority=0, cost_per_call_usd=0.01),
        ),
    ),

    # ── SK-006: Quorum Deliberation ──────────────────────────────────────
    "SK-006": AgoraSkill(
        skill_id="SK-006",
        name="quorum_deliberate",
        description="3-perspective deliberation (skeptic/advocate/judge) "
                    "to reach consensus on a mathematical claim.",
        guardrails=SkillGuardrails(
            max_budget_usd=1.50,
            max_duration_s=300,
            max_retries=1,
            audit_level=AuditLevel.FULL,
        ),
        backends=(
            SkillBackend(BackendType.LLM_API, "gemini", "api",
                         priority=0, cost_per_call_usd=0.45),
        ),
    ),

    # ── SK-007: Human Explanation ────────────────────────────────────────
    "SK-007": AgoraSkill(
        skill_id="SK-007",
        name="explain_for_humans",
        description="Generate layered explanations (expert/student/public) "
                    "of a mathematical result.",
        guardrails=SkillGuardrails(
            max_budget_usd=0.50,
            max_duration_s=120,
            audit_level=AuditLevel.SUMMARY,
        ),
        backends=(
            SkillBackend(BackendType.LLM_API, "gemini", "api",
                         priority=0, cost_per_call_usd=0.10),
        ),
    ),

    # ── SK-008: Numeric Witness Search ───────────────────────────────────
    "SK-008": AgoraSkill(
        skill_id="SK-008",
        name="numeric_witness",
        description="Search for constructive numerical witnesses using "
                    "gradient descent (Adam), ALS, or SAT/SMT solvers.",
        required_tools=("gpu_compute",),
        guardrails=SkillGuardrails(
            max_budget_usd=5.0,
            max_duration_s=600,
            max_retries=3,
            audit_level=AuditLevel.FULL,
        ),
        backends=(
            SkillBackend(BackendType.DETERMINISTIC, "numpy_jax", "local",
                         priority=0, cost_per_call_usd=0.0),
            SkillBackend(BackendType.DETERMINISTIC, "gpu_search",
                         "https://solver-service.internal.a.run.app/search",
                         priority=1, cost_per_call_usd=0.35, gpu_required=True),
        ),
    ),

    # ── SK-009: GCP Deployment ───────────────────────────────────────────
    "SK-009": AgoraSkill(
        skill_id="SK-009",
        name="deploy_experiment",
        description="Deploy an experiment container to GCP Cloud Run.",
        required_tools=("gcloud_cli",),
        guardrails=SkillGuardrails(
            max_budget_usd=10.0,
            max_duration_s=600,
            requires_approval=True,  # Human must approve deployments
            audit_level=AuditLevel.FULL,
            allowed_agents=("lovelace", "hilbert"),
        ),
        backends=(
            SkillBackend(BackendType.DETERMINISTIC, "gcloud", "local",
                         priority=0, cost_per_call_usd=0.0),
        ),
    ),

    # ── SK-010: Sorry Completion ─────────────────────────────────────────
    "SK-010": AgoraSkill(
        skill_id="SK-010",
        name="sorry_completion",
        description="Close a sorry gap using 10-hypothesis ratchet: "
                    "LeanBert(3) + DeepSeek-7B(4) + Gemini(3). "
                    "3 retry iterations = 30 total attempts per sorry.",
        required_tools=("lean4_compiler", "leanbert_critic",
                        "deepseek_prover"),
        guardrails=SkillGuardrails(
            max_budget_usd=5.0,
            max_duration_s=900,
            max_retries=3,
            audit_level=AuditLevel.FULL,
            allowed_agents=("hilbert",),
        ),
        backends=(
            SkillBackend(BackendType.DETERMINISTIC, "lean_tactics", "local",
                         priority=0, cost_per_call_usd=0.0),
            SkillBackend(BackendType.LEARNED, "leanbert", "local",
                         priority=1, cost_per_call_usd=0.01),
            SkillBackend(BackendType.LLM_SELFHOSTED, "deepseek_7b",
                         "https://deepseek-prover-v2.internal.a.run.app/prove",
                         priority=2, cost_per_call_usd=0.05, gpu_required=True),
            SkillBackend(BackendType.LLM_API, "gemini", "api",
                         priority=3, cost_per_call_usd=0.10),
            SkillBackend(BackendType.LLM_API, "deepseek_671b",
                         "https://api.deepseek.com/chat/completions",
                         priority=4, cost_per_call_usd=0.50),
        ),
    ),

    # ══════════════════════════════════════════════════════════════════════
    # Bellman OR Pipeline Skills (SK-011 → SK-016)
    # ══════════════════════════════════════════════════════════════════════

    # ── SK-011: LP/MIP Solver ────────────────────────────────────────────
    "SK-011": AgoraSkill(
        skill_id="SK-011",
        name="lp_solve",
        description="Solve linear and mixed-integer programs via OR-Tools, "
                    "HiGHS, or CPLEX. Returns optimal objective, gap, solve time.",
        required_tools=("ortools", "highs"),
        guardrails=SkillGuardrails(
            max_budget_usd=0.50,
            max_duration_s=600,
            max_retries=2,
            audit_level=AuditLevel.FULL,
            allowed_agents=("bellman", "kantorovich", "galileo"),
        ),
        backends=(
            SkillBackend(BackendType.DETERMINISTIC, "ortools_cp_sat", "local",
                         priority=0, cost_per_call_usd=0.0),
            SkillBackend(BackendType.DETERMINISTIC, "highs_solver", "local",
                         priority=1, cost_per_call_usd=0.0),
        ),
    ),

    # ── SK-012: Stochastic Programming ──────────────────────────────────
    "SK-012": AgoraSkill(
        skill_id="SK-012",
        name="stochastic_program",
        description="Two-stage stochastic programming with Benders decomposition "
                    "or sample-average approximation (SAA). Solves under uncertainty.",
        required_tools=("ortools", "numpy"),
        guardrails=SkillGuardrails(
            max_budget_usd=2.00,
            max_duration_s=900,
            max_retries=2,
            audit_level=AuditLevel.FULL,
            allowed_agents=("bellman",),
        ),
        backends=(
            SkillBackend(BackendType.DETERMINISTIC, "pysp_benders", "local",
                         priority=0, cost_per_call_usd=0.0),
            SkillBackend(BackendType.DETERMINISTIC, "saa_solver", "local",
                         priority=1, cost_per_call_usd=0.0),
        ),
    ),

    # ── SK-013: Discrete-Event Simulation ───────────────────────────────
    "SK-013": AgoraSkill(
        skill_id="SK-013",
        name="discrete_event_sim",
        description="Discrete-event simulation using SimPy for queueing systems, "
                    "scheduling, and resource allocation. Reports utilization, "
                    "wait times, throughput.",
        required_tools=("simpy",),
        guardrails=SkillGuardrails(
            max_budget_usd=1.00,
            max_duration_s=300,
            max_retries=2,
            audit_level=AuditLevel.FULL,
            allowed_agents=("bellman", "galileo"),
        ),
        backends=(
            SkillBackend(BackendType.DETERMINISTIC, "simpy_engine", "local",
                         priority=0, cost_per_call_usd=0.0),
        ),
    ),

    # ── SK-014: OR Benchmark Validation ─────────────────────────────────
    "SK-014": AgoraSkill(
        skill_id="SK-014",
        name="benchmark_validate",
        description="Validate optimization solutions against standard OR benchmarks: "
                    "OR-Library, MIPLIB 2017, TSPlib, Solomon (VRP), Taillard (scheduling).",
        required_tools=("benchmark_loader",),
        guardrails=SkillGuardrails(
            max_budget_usd=0.50,
            max_duration_s=300,
            max_retries=1,
            audit_level=AuditLevel.FULL,
        ),
        backends=(
            SkillBackend(BackendType.DETERMINISTIC, "or_benchmark_suite", "local",
                         priority=0, cost_per_call_usd=0.0),
        ),
    ),

    # ── SK-015: Complexity Proof ────────────────────────────────────────
    "SK-015": AgoraSkill(
        skill_id="SK-015",
        name="complexity_prove",
        description="Prove or bound computational complexity: NP-hardness reductions, "
                    "approximation ratios (e.g., 3/2 - epsilon for metric TSP), "
                    "inapproximability results, FPT analysis.",
        guardrails=SkillGuardrails(
            max_budget_usd=1.50,
            max_duration_s=300,
            max_retries=2,
            audit_level=AuditLevel.FULL,
            allowed_agents=("bellman",),
        ),
        backends=(
            SkillBackend(BackendType.LLM_API, "gemini", "api",
                         priority=0, cost_per_call_usd=0.30),
        ),
    ),

    # ── SK-016: OR Problem Formulation ──────────────────────────────────
    "SK-016": AgoraSkill(
        skill_id="SK-016",
        name="or_formulate",
        description="Translate natural-language optimization problems into "
                    "mathematical programs (LP, IP, MIP, QP, NLP). Identify "
                    "decision variables, objective, constraints, and special structure.",
        guardrails=SkillGuardrails(
            max_budget_usd=1.00,
            max_duration_s=180,
            max_retries=3,
            audit_level=AuditLevel.FULL,
        ),
        backends=(
            SkillBackend(BackendType.LLM_API, "gemini", "api",
                         priority=0, cost_per_call_usd=0.15),
        ),
    ),

    # ── SK-017: Socrates Taste Sieve ──────────────────────────────────────
    "SK-017": AgoraSkill(
        skill_id="SK-017",
        name="socrates_taste_sieve",
        description="Applies Socratic elenchus, structural constraints, and the "
                    "OEIS live novelty sieve to filter out trivial mathematical "
                    "conjectures and ensure high mathematical taste.",
        required_tools=("oeis_live_api", "rational_ansatz_fitter"),
        guardrails=SkillGuardrails(
            max_budget_usd=2.50,
            max_duration_s=400,
            max_retries=3,
            audit_level=AuditLevel.FULL,
            allowed_agents=("socrates",),
        ),
        backends=(
            SkillBackend(BackendType.LLM_API, "gemini", "api",
                         priority=0, cost_per_call_usd=0.20),
        ),
    ),
}


# ---------------------------------------------------------------------------
# Skill Registry
# ---------------------------------------------------------------------------

@dataclass
class SkillRegistry:
    """Central catalog of all Agora skills.

    Provides lookup by ID, filtering by agent, and validation.
    """
    _skills: dict[str, AgoraSkill] = field(default_factory=lambda: dict(SKILLS))

    def get(self, skill_id: str) -> Optional[AgoraSkill]:
        """Get a skill by ID, or None if not found."""
        return self._skills.get(skill_id)

    def skills_for_agent(self, agent_name: str) -> list[AgoraSkill]:
        """Return all skills this agent is allowed to invoke."""
        return [
            s for s in self._skills.values()
            if not s.guardrails.allowed_agents  # Empty = all agents
            or agent_name in s.guardrails.allowed_agents
        ]

    def deterministic_skills(self) -> list[AgoraSkill]:
        """Return all skills whose primary backend is deterministic."""
        return [s for s in self._skills.values() if s.is_deterministic]

    def total_budget(self) -> float:
        """Sum of all skill max budgets (theoretical maximum)."""
        return sum(s.guardrails.max_budget_usd for s in self._skills.values())

    def register(self, skill: AgoraSkill) -> None:
        """Register a new skill."""
        self._skills[skill.skill_id] = skill

    def list_all(self) -> list[AgoraSkill]:
        """Return all registered skills."""
        return list(self._skills.values())


# Module-level singleton
SKILL_REGISTRY = SkillRegistry()


def get_skill(skill_id: str) -> Optional[AgoraSkill]:
    """Convenience function to get a skill from the global registry."""
    return SKILL_REGISTRY.get(skill_id)
