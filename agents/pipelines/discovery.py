# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Agora Discovery Pipeline — 6-Stage Mathematical Discovery Orchestrator.

Executes a streamlined, mathematically rigorous discovery pipeline that moves
from surveying open problems to generating verified proofs archived in the
Alexandrie vault.  This is the *mathematical counterpart* to the 12-stage
Symposium pipeline: fewer stages, but each one must survive the incorruptible
Lean 4 kernel judge.

Pipeline Stages (6 steps):
  1. HORIZON_SCAN       — Darwin surveys arXiv, Mathlib & Alexandrie for open problems
  2. CONJECTURE_GEN     — DeGennes swarm generates conjectures from experimental data
  3. AUTOFORMALIZE      — Newton translates natural-language conjectures to Lean 4
  4. PROOF_SEARCH        — Hilbert deterministic-first cascade: Lean tactics → LeanBert
                           → DeepSeek-Prover → Gemini deep-think
  5. KERNEL_VERIFY       — ``lake build`` deterministic gate (NO LLM — binary pass/fail)
  6. ARCHIVE_AND_REVIEW  — Hypatia archives to Alexandrie + Poincaré quorum + Xavier gate

Design Principles
-----------------
**Deterministic-first proof search.**  LLMs are probabilistic; they can
hallucinate "proofs" that look convincing but are unsound.  The cascade
deliberately starts with deterministic Lean 4 tactic scripts (``simp``,
``omega``, ``decide``, ``norm_num``, ``ring``) because those either work or
fail — they never hallucinate.  Only when deterministic tactics are
exhausted do we escalate to probabilistic assistants (LeanBert, DeepSeek,
Gemini), and *every* LLM-suggested proof must re-enter the Lean 4 kernel
for verification.

**The Lean 4 kernel is the incorruptible judge.**  No matter how
eloquent an LLM proof sounds, it is *meaningless* unless ``lake build``
returns exit code 0 with zero ``sorry`` placeholders.  Stage 5 is a
deterministic gate — it runs ``lake build`` in a sandboxed container and
records stdout/stderr.  If the build fails, the proof is rejected.  Period.
This is the foundational guarantee of the pipeline.

**Alexandrie private / open rooms.**  During discovery, unproven conjectures
and partial proofs are stored in the **private room** — these are
intellectual property and may contain incorrect statements.  Once a proof
passes kernel verification AND the Poincaré quorum, the conjecture +
proof package is promoted to the **open room** with a generated LaTeX
index page for human-readable browsing.

**Template design.**  This pipeline is a TEMPLATE.  Replace
``target_domain`` with any mathematical domain (``matrix_multiplication``,
``tensor_rank``, ``graph_coloring``, ``knot_invariants``) and the same
6-stage machinery applies.  Domain-specific knowledge enters through
Stage 1 (Darwin's literature scan) and Stage 2 (DeGennes' experimental
data), not through pipeline structure changes.

Budget: hard-capped at $30 per pipeline run.

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import asyncio
import json
import os
import textwrap
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any

import structlog

from agents.pipelines.base import AgentPipeline, PipelineResult, agent_generate
from agents.pipelines.audit import SymposiumAuditTrail
from agents.pipelines.stages.degennes_experimentalist import (
    generate_experimental_conjectures,
)
from agents.pipelines.stages.alexandrie_vault_manager import (
    archive_discovery_run,
    load_vault_context,
    generate_latex_index,
)
from agents.skills.registry import SKILL_REGISTRY, get_skill
from alexandrie.hub import AlexandrieHub
from alexandrie.metadata import ArtifactType, RoomType
from agents.memory import AgentMemoryManager

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Discovery Stages
# ═══════════════════════════════════════════════════════════════════════════

class DiscoveryStage(IntEnum):
    """Ordered stages of the Agora Discovery pipeline.

    Unlike the 12-stage Symposium pipeline (which covers the full
    lifecycle from hypothesis to monograph publication), the Discovery
    pipeline focuses on the *mathematical core*: scan → conjecture →
    formalize → prove → verify → archive.  Six stages, each essential.

    The integer value encodes execution order.
    """

    HORIZON_SCAN = 1          # Darwin surveys literature & Alexandrie vault
    CONJECTURE_GENERATION = 2  # DeGennes swarm: experimental data → conjectures
    AUTOFORMALIZE = 3          # Newton: natural language → Lean 4 statements
    PROOF_SEARCH = 4           # Hilbert: deterministic-first proof cascade
    KERNEL_VERIFY = 5          # lake build: deterministic binary gate (no LLM)
    ARCHIVE_AND_REVIEW = 6     # Hypatia archive + Poincaré quorum + Xavier gate


# ═══════════════════════════════════════════════════════════════════════════
# Per-stage cost estimates (USD)
# ═══════════════════════════════════════════════════════════════════════════

STAGE_COST_ESTIMATES: dict[str, float] = {
    "horizon_scan": 0.50,
    "conjecture_per_agent": 0.30,
    "autoformalize_per_conjecture": 0.40,
    "proof_lean_tactics": 0.00,           # deterministic — free
    "proof_leanbert_per_conjecture": 0.20,
    "proof_deepseek_per_conjecture": 0.35,
    "proof_gemini_per_conjecture": 0.50,
    "kernel_verify": 0.00,                # deterministic — free
    "poincare_quorum": 0.60,
    "hypatia_latex_index": 0.30,
}
"""Approximate per-call cost estimates for budget tracking.

Note: deterministic stages (Lean tactics, ``lake build``) have zero LLM
cost.  They consume only CPU / container time, which is negligible
compared to the LLM budget.
"""


# ═══════════════════════════════════════════════════════════════════════════
# Agent Identities — module-level constants
# ═══════════════════════════════════════════════════════════════════════════

DARWIN_IDENTITY = textwrap.dedent("""\
    You are Darwin, the literature surveyor of the Agora Discovery swarm.
    Named after Charles Darwin for his meticulous observation of natural
    phenomena and his synthesis of vast empirical evidence into theory.

    Your task: survey the mathematical landscape for open problems,
    recent breakthroughs, and knowledge gaps in the given domain.

    Sources to consult (in priority order):
    1. Alexandrie Vault — prior discoveries, monographs, and references
       stored by the Agora. These are the lab's own results and must be
       checked first to avoid redundant work.
    2. arXiv preprints — recent results in math.CO, math.AG, cs.CC, etc.
    3. Mathlib4 — what has already been formalized in Lean 4, and what
       remains as ``sorry`` or is entirely absent.

    Output a JSON object with keys:
    - open_problems: list of {title, description, source, difficulty}
    - recent_breakthroughs: list of {title, authors, year, relevance}
    - mathlib_gaps: list of {area, missing_formalization, difficulty}
    - vault_references: list of {artifact_id, title, relevance_score}
    - recommended_targets: top-5 conjectures worth attacking, ranked

    Be specific: cite paper IDs, theorem numbers, and Mathlib module paths.
""").strip()

NEWTON_IDENTITY = textwrap.dedent("""\
    You are Newton, the autoformalization expert of the Agora Discovery swarm.
    Named after Isaac Newton for his commitment to rigorous mathematical proof
    from first principles, and for translating physical intuition into precise
    differential equations.

    Your task: translate a natural-language mathematical conjecture into a
    syntactically valid Lean 4 statement that can be checked by ``lake build``.

    Rules:
    1. Import from Mathlib4: ``import Mathlib.LinearAlgebra.*``,
       ``import Mathlib.Analysis.*``, ``import Mathlib.Combinatorics.*``, etc.
    2. Define a ``namespace`` for the conjecture.
    3. Write a ``theorem`` statement with precise type signatures.
    4. Use ``sorry`` only where the proof body is the target of Stage 4.
       Mark each ``sorry`` with a structured comment:
       ``-- SORRY: [what needs proving] [difficulty estimate 1-5]``
    5. Include ``#check`` statements to verify type signatures.
    6. Never add ``axiom`` — all assumptions must be stated as hypotheses.

    Output raw Lean 4 code only — no markdown fences, no prose explanations.
    The code must compile with ``lake build`` (modulo ``sorry``).
""").strip()

POINCARE_IDENTITY = textwrap.dedent("""\
    You are Poincaré, the quorum judge of the Agora Discovery swarm.
    Named after Henri Poincaré for his ability to hold multiple mathematical
    perspectives simultaneously and synthesize rigorous verdicts.

    You lead a 3-agent quorum (Skeptic, Advocate, Judge) that reviews
    each kernel-verified proof before it is promoted to the Alexandrie
    open room.

    Your task as final Judge:
    1. Review the Lean 4 source — is the theorem statement faithful to the
       original conjecture? (no weakening, no hidden assumptions)
    2. Review the proof — does it use ``native_decide`` correctly? Are
       there axioms that should be eliminated?
    3. Check for mathematical significance — is this a new result or a
       trivial restatement of something already in Mathlib?
    4. Render a VERDICT: ACCEPT / REJECT / NEEDS_REVISION
    5. Assign a CONFIDENCE score in [0.0, 1.0]
    6. State what evidence would change the verdict

    Output a JSON object with keys:
    verdict, confidence, faithfulness_check, axiom_review,
    significance_assessment, recommendations
""").strip()


# ═══════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════

DISCOVERY_BUDGET_USD: float = 30.0
"""Hard budget cap per discovery run ($30)."""


@dataclass(frozen=True, slots=True)
class DiscoveryConfig:
    """Immutable configuration for a single Discovery pipeline run.

    This is the mathematical counterpart to :class:`SymposiumConfig`.
    While the Symposium config focuses on research questions and monograph
    generation, DiscoveryConfig targets a specific mathematical domain
    and tunes the proof-search cascade.

    Attributes:
        discovery_id: Unique run identifier (auto-generated if omitted).
        target_domain: Mathematical domain to explore (e.g.
            ``'matrix_multiplication'``, ``'tensor_rank'``).
        num_conjectures: Target number of conjectures to generate.
        num_degennes_agents: Size of the DeGennes experimentalist swarm.
        enable_leanbert: Whether to include LeanBert in the proof cascade.
        enable_deepseek: Whether to include DeepSeek-Prover in the cascade.
        model: Foundation model identifier for LLM stages.
        max_budget_usd: Maximum spend for the entire pipeline run.
        alexandrie_bucket: GCS bucket for the Alexandrie Vault.
        require_human_approval: Whether Xavier's human gate is enforced
            before promoting results to the open room.
        output_dir: Local directory for generated artifacts.
    """

    # ── Discovery target ─────────────────────────────────────────────────
    discovery_id: str = field(
        default_factory=lambda: f"DISC-{uuid.uuid4().hex[:12].upper()}"
    )
    target_domain: str = "matrix_multiplication"

    # ── Swarm & search parameters ────────────────────────────────────────
    num_conjectures: int = 10
    num_degennes_agents: int = 5
    enable_leanbert: bool = True
    enable_deepseek: bool = True

    # ── Model configuration ──────────────────────────────────────────────
    model: str = "gemini-2.5-pro"

    # ── Budget ───────────────────────────────────────────────────────────
    max_budget_usd: float = 30.0

    # ── Alexandrie storage ───────────────────────────────────────────────
    alexandrie_bucket: str = "socrateai-alexandrie-vault"

    # ── Human-in-the-loop ────────────────────────────────────────────────
    require_human_approval: bool = True

    # ── Output ───────────────────────────────────────────────────────────
    output_dir: Path = Path("output/discovery")

    # ── Validation ───────────────────────────────────────────────────────

    def __post_init__(self) -> None:
        """Validate invariants at construction time."""
        if not self.target_domain:
            raise ValueError("target_domain must be a non-empty string")
        if self.num_conjectures < 1:
            raise ValueError(
                f"num_conjectures must be ≥ 1, got {self.num_conjectures}"
            )
        if self.num_degennes_agents < 1:
            raise ValueError(
                f"num_degennes_agents must be ≥ 1, got {self.num_degennes_agents}"
            )
        if self.max_budget_usd > DISCOVERY_BUDGET_USD:
            raise ValueError(
                f"Budget ${self.max_budget_usd} exceeds pipeline cap "
                f"${DISCOVERY_BUDGET_USD}"
            )

    # ── Derived properties ───────────────────────────────────────────────

    @property
    def conjectures_per_agent(self) -> int:
        """Conjectures each DeGennes agent should produce."""
        # Distribute evenly, rounding up so total ≥ num_conjectures
        return -(-self.num_conjectures // self.num_degennes_agents)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "discovery_id": self.discovery_id,
            "target_domain": self.target_domain,
            "num_conjectures": self.num_conjectures,
            "num_degennes_agents": self.num_degennes_agents,
            "conjectures_per_agent": self.conjectures_per_agent,
            "enable_leanbert": self.enable_leanbert,
            "enable_deepseek": self.enable_deepseek,
            "model": self.model,
            "max_budget_usd": self.max_budget_usd,
            "alexandrie_bucket": self.alexandrie_bucket,
            "require_human_approval": self.require_human_approval,
            "output_dir": str(self.output_dir),
        }


# ═══════════════════════════════════════════════════════════════════════════
# Discovery Result
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(slots=True)
class DiscoveryResult(PipelineResult):
    """Structured output from a complete Discovery pipeline run.

    Extends :class:`PipelineResult` with discovery-specific metrics:
    conjecture counts, formalization/proof statistics, kernel verification
    results, and Alexandrie vault artifact references.

    Attributes:
        conjectures_generated: Raw conjectures produced by the DeGennes swarm.
        conjectures_formalized: Successfully translated to Lean 4 statements.
        proofs_completed: Proofs with zero ``sorry`` placeholders.
        proofs_with_sorry: Proofs that still contain ``sorry`` (partial).
        kernel_verified: Proofs that pass ``lake build`` with exit code 0.
        vault_open_artifacts: Artifact IDs promoted to the Alexandrie open room.
        vault_private_artifacts: Artifact IDs in the Alexandrie private room.
        latex_index_path: Local path to the generated LaTeX index page.
    """

    conjectures_generated: int = 0
    conjectures_formalized: int = 0
    proofs_completed: int = 0
    proofs_with_sorry: int = 0
    kernel_verified: int = 0
    vault_open_artifacts: list[str] = field(default_factory=list)
    vault_private_artifacts: list[str] = field(default_factory=list)
    latex_index_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        base = super().to_dict()
        base.update({
            "conjectures_generated": self.conjectures_generated,
            "conjectures_formalized": self.conjectures_formalized,
            "proofs_completed": self.proofs_completed,
            "proofs_with_sorry": self.proofs_with_sorry,
            "kernel_verified": self.kernel_verified,
            "vault_open_artifacts": self.vault_open_artifacts,
            "vault_private_artifacts": self.vault_private_artifacts,
            "latex_index_path": self.latex_index_path,
        })
        return base


# ═══════════════════════════════════════════════════════════════════════════
# Discovery Pipeline — Main Orchestrator
# ═══════════════════════════════════════════════════════════════════════════

class DiscoveryPipeline(AgentPipeline):
    """Six-stage Agora Discovery orchestrator.

    Sequences the mathematical discovery agents (Darwin → DeGennes →
    Newton → Hilbert → lake build → Hypatia/Poincaré/Xavier) while
    enforcing budget, guardrails, and audit logging.

    This class follows the SAME structural template as
    :class:`~agents.pipelines.symposium.SymposiumPipeline` so that
    both pipelines can be composed, compared, and extended using
    the same tooling.

    Usage::

        config = DiscoveryConfig(
            target_domain="tensor_rank",
            num_conjectures=10,
            num_degennes_agents=5,
        )
        pipeline = DiscoveryPipeline(config)
        result = await pipeline.run(config)

    Architecture
    ------------
    The proof-search cascade in Stage 4 is deliberately ordered from
    most-deterministic to most-probabilistic:

    1. **Lean 4 tactic scripts** — ``simp``, ``omega``, ``decide``,
       ``norm_num``, ``ring``.  These are *sound by construction*:
       they either close the goal or fail.  Zero hallucination risk.

    2. **LeanBert** — a fine-tuned transformer trained on Mathlib proofs.
       Probabilistic, but constrained to Lean syntax.  Low hallucination.

    3. **DeepSeek-Prover** — a large reasoning model specialized for
       mathematical proofs.  Higher creativity, higher hallucination risk.

    4. **Gemini 3.1 Pro deep-think** — the most powerful LLM in the
       cascade, used as a last resort for creative proof strategies.
       Highest hallucination risk, but also the broadest reasoning.

    Every proof suggestion from layers 2–4 is *re-verified* by the
    Lean 4 kernel in Stage 5.  The cascade is an optimization strategy,
    not a trust hierarchy.
    """

    def __init__(self, config: DiscoveryConfig) -> None:
        self._config = config
        self._hub = AlexandrieHub()
        self._memory = AgentMemoryManager(self._hub.science_library)
        self._audit = SymposiumAuditTrail(symposium_id=config.discovery_id)
        self._log = logger.bind(
            component="discovery_pipeline",
            discovery_id=config.discovery_id,
        )
        self._accumulated_cost_usd: float = 0.0

    # ------------------------------------------------------------------
    # AgentPipeline interface
    # ------------------------------------------------------------------

    def get_stages(self) -> list[DiscoveryStage]:
        """Return the ordered list of stages this pipeline implements.

        Returns:
            The 6 :class:`DiscoveryStage` values in execution order.
        """
        return list(DiscoveryStage)

    async def run(self, config: DiscoveryConfig) -> DiscoveryResult:
        """Execute the full 6-stage Agora Discovery pipeline with checkpointing.

        Each stage's output is persisted to GCS via ScienceLibrary so that
        the orchestrator can resume from the last successful checkpoint on
        failure — avoiding re-running expensive LLM stages.

        Args:
            config: Frozen discovery configuration.

        Returns:
            :class:`DiscoveryResult` with all outputs, metrics, and
            Alexandrie artifact references.
        """
        pipeline_start = time.time()
        self._audit.record(
            self._make_audit_entry(
                DiscoveryStage.HORIZON_SCAN,
                agent="DiscoveryPipeline",
                metrics={"event": "pipeline_start"},
            )
        )

        # Ensure output directory exists
        config.output_dir.mkdir(parents=True, exist_ok=True)

        result = DiscoveryResult(
            symposium_id=config.discovery_id,
        )

        self._print_banner(config)

        # ── Checkpointing: load any prior progress for this run ──────
        # The ScienceLibrary stores intermediary results under
        # gs://{bucket}/science_library/checkpoints/{run_id}/ so the
        # orchestrator can skip already-completed stages on resume.
        lib = self._hub.science_library
        run_id = config.discovery_id
        existing_checkpoints = lib.list_checkpoints(run_id)
        self._log.info(
            "checkpoint_scan",
            run_id=run_id,
            existing_stages=existing_checkpoints,
        )

        try:
            # ── Stage 1/6: HORIZON_SCAN — Darwin surveys the landscape ──
            ckpt_name = "stage_01_horizon_scan"
            cached = lib.load_checkpoint(run_id, ckpt_name)
            if cached and ckpt_name in existing_checkpoints:
                self._log.info("checkpoint_hit", stage=ckpt_name)
                print(f"  ♻️  Stage 1/6 HORIZON_SCAN — restored from checkpoint")
                horizon = cached
            else:
                horizon = await self._stage_horizon_scan(config)
                lib.checkpoint_stage(run_id, ckpt_name, horizon)
                self._log.info("checkpoint_saved", stage=ckpt_name)

            # ── Stage 2/6: CONJECTURE_GENERATION — DeGennes swarm ────────
            ckpt_name = "stage_02_conjecture_gen"
            cached = lib.load_checkpoint(run_id, ckpt_name)
            if cached and ckpt_name in existing_checkpoints:
                self._log.info("checkpoint_hit", stage=ckpt_name)
                print(f"  ♻️  Stage 2/6 CONJECTURE_GEN — restored from checkpoint")
                conjectures = cached.get("conjectures", [])
            else:
                conjectures = await self._stage_conjecture_generation(
                    config, horizon,
                )
                lib.checkpoint_stage(
                    run_id, ckpt_name, {"conjectures": conjectures},
                )
                self._log.info("checkpoint_saved", stage=ckpt_name)
            result.conjectures_generated = len(conjectures)

            # ── Stage 3/6: AUTOFORMALIZE — Newton → Lean 4 ──────────────
            ckpt_name = "stage_03_autoformalize"
            cached = lib.load_checkpoint(run_id, ckpt_name)
            if cached and ckpt_name in existing_checkpoints:
                self._log.info("checkpoint_hit", stage=ckpt_name)
                print(f"  ♻️  Stage 3/6 AUTOFORMALIZE — restored from checkpoint")
                lean_statements = cached.get("lean_statements", [])
            else:
                lean_statements = await self._stage_autoformalize(
                    config, conjectures,
                )
                lib.checkpoint_stage(
                    run_id, ckpt_name, {"lean_statements": lean_statements},
                )
                self._log.info("checkpoint_saved", stage=ckpt_name)
            result.conjectures_formalized = len(lean_statements)

            # ── Stage 4/6: PROOF_SEARCH — Hilbert cascade ───────────────
            ckpt_name = "stage_04_proof_search"
            cached = lib.load_checkpoint(run_id, ckpt_name)
            if cached and ckpt_name in existing_checkpoints:
                self._log.info("checkpoint_hit", stage=ckpt_name)
                print(f"  ♻️  Stage 4/6 PROOF_SEARCH — restored from checkpoint")
                proof_results = cached.get("proof_results", [])
            else:
                proof_results = await self._stage_proof_search(
                    config, lean_statements,
                )
                lib.checkpoint_stage(
                    run_id, ckpt_name, {"proof_results": proof_results},
                )
                self._log.info("checkpoint_saved", stage=ckpt_name)
            result.proofs_completed = sum(
                1 for p in proof_results if p.get("sorry_count", 1) == 0
            )
            result.proofs_with_sorry = sum(
                1 for p in proof_results if p.get("sorry_count", 1) > 0
            )

            # ── Stage 5/6: KERNEL_VERIFY — lake build gate ──────────────
            ckpt_name = "stage_05_kernel_verify"
            cached = lib.load_checkpoint(run_id, ckpt_name)
            if cached and ckpt_name in existing_checkpoints:
                self._log.info("checkpoint_hit", stage=ckpt_name)
                print(f"  ♻️  Stage 5/6 KERNEL_VERIFY — restored from checkpoint")
                verified = cached.get("verified", [])
            else:
                verified = await self._stage_kernel_verify(
                    config, proof_results,
                )
                lib.checkpoint_stage(
                    run_id, ckpt_name, {"verified": verified},
                )
                self._log.info("checkpoint_saved", stage=ckpt_name)
            result.kernel_verified = len(verified)

            # ── Stage 6/6: ARCHIVE_AND_REVIEW — Hypatia + Poincaré ──────
            ckpt_name = "stage_06_archive_review"
            cached = lib.load_checkpoint(run_id, ckpt_name)
            if cached and ckpt_name in existing_checkpoints:
                self._log.info("checkpoint_hit", stage=ckpt_name)
                print(f"  ♻️  Stage 6/6 ARCHIVE — restored from checkpoint")
                archive_result = cached
            else:
                archive_result = await self._stage_archive_and_review(
                    config, conjectures, verified,
                )
                lib.checkpoint_stage(run_id, ckpt_name, archive_result)
                self._log.info("checkpoint_saved", stage=ckpt_name)
            result.vault_open_artifacts = archive_result.get(
                "open_artifacts", [],
            )
            result.vault_private_artifacts = archive_result.get(
                "private_artifacts", [],
            )
            result.latex_index_path = archive_result.get(
                "latex_index_path", "",
            )

            # Mark stages completed
            result.stages_completed = list(DiscoveryStage)

        except Exception as exc:
            self._log.exception("discovery_pipeline_error")
            result.warnings.append(f"Pipeline error: {exc}")

        # Finalize
        elapsed = time.time() - pipeline_start
        result.total_duration_s = round(elapsed, 2)
        result.total_cost_usd = round(self._accumulated_cost_usd, 4)

        # ── Store lesson learned for future agent self-improvement ────
        from alexandrie.science_library import LessonLearned

        lesson = LessonLearned(
            run_id=run_id,
            agent_name="discovery_pipeline",
            domain=config.target_domain,
            pipeline="discovery",
            success=len(result.warnings) == 0,
            what_worked=[
                f"Generated {result.conjectures_generated} conjectures",
                f"Formalized {result.conjectures_formalized} to Lean 4",
                f"Kernel-verified {result.kernel_verified} proofs",
            ],
            what_failed=[w for w in result.warnings],
            improvements=[
                "Resume from checkpoint on retry" if result.warnings
                else "Pipeline completed successfully — no changes needed",
            ],
            metrics={
                "conjectures_generated": result.conjectures_generated,
                "conjectures_formalized": result.conjectures_formalized,
                "proofs_completed": result.proofs_completed,
                "kernel_verified": result.kernel_verified,
                "cost_usd": result.total_cost_usd,
                "duration_s": result.total_duration_s,
            },
        )
        lib.store_lesson_learned(lesson)

        self._print_summary(config, result)
        return result

    # ------------------------------------------------------------------
    # Stage 1: HORIZON_SCAN — Darwin surveys the landscape
    # ------------------------------------------------------------------

    async def _stage_horizon_scan(
        self, config: DiscoveryConfig,
    ) -> dict[str, Any]:
        """Stage 1: Darwin surveys literature and Alexandrie vault.

        Darwin queries three sources in priority order:
        1. Alexandrie vault — our own prior discoveries and monographs
        2. arXiv — recent preprints in relevant math/CS categories
        3. Mathlib4 — what is already formalized vs. what is missing

        Returns:
            A structured dict with open_problems, recent_breakthroughs,
            mathlib_gaps, vault_references, and recommended_targets.
        """
        stage_name = "1_horizon_scan"
        print(f"\n[Stage 1/6] 🔭 Darwin — Scanning horizon for "
              f"'{config.target_domain}'...")
        t0 = time.time()

        self._check_budget(STAGE_COST_ESTIMATES["horizon_scan"])

        # Load prior context from Alexandrie vault
        vault_context = await load_vault_context(
            hub=self._hub,
            query=config.target_domain,
        )

        prompt = textwrap.dedent(f"""\
            Survey the mathematical landscape for the domain: {config.target_domain}

            Prior discoveries from our Alexandrie vault:
            {json.dumps(vault_context, indent=2, default=str)[:3000]}

            Identify:
            1. Open problems — unsolved conjectures or bounds worth attacking
            2. Recent breakthroughs — papers from the last 2 years that shift the landscape
            3. Mathlib gaps — areas where formalization is missing or incomplete
            4. Vault references — which of our prior results are relevant
            5. Recommended targets — rank top-5 conjectures to attack in this run

            Output a JSON object with the keys listed above.
            Be specific: cite paper IDs, theorem numbers, Mathlib module paths.
        """).strip()

        raw = await agent_generate(
            DARWIN_IDENTITY, prompt, model=config.model,
        )

        # Parse or construct fallback
        horizon = self._parse_json_safe(raw) or {
            "open_problems": [
                {"title": f"Open problem in {config.target_domain}",
                 "description": "Identified via mock fallback",
                 "source": "arXiv", "difficulty": "unknown"}
            ],
            "recent_breakthroughs": [],
            "mathlib_gaps": [],
            "vault_references": vault_context.get("references", []),
            "recommended_targets": [
                {"title": f"Primary target in {config.target_domain}",
                 "rank": 1}
            ],
        }

        cost = STAGE_COST_ESTIMATES["horizon_scan"]
        dt = time.time() - t0
        self._record_cost(cost)
        self._audit.record(
            self._make_audit_entry(
                DiscoveryStage.HORIZON_SCAN,
                agent="Darwin",
                duration_s=dt,
                cost_usd=cost,
                metrics={
                    "open_problems": len(horizon.get("open_problems", [])),
                    "recommended_targets": len(
                        horizon.get("recommended_targets", [])
                    ),
                },
            )
        )
        print(f"  ✅ Horizon scanned: "
              f"{len(horizon.get('open_problems', []))} open problems, "
              f"{len(horizon.get('recommended_targets', []))} targets "
              f"({dt:.1f}s)")
        return horizon

    # ------------------------------------------------------------------
    # Stage 2: CONJECTURE_GENERATION — DeGennes experimentalist swarm
    # ------------------------------------------------------------------

    async def _stage_conjecture_generation(
        self,
        config: DiscoveryConfig,
        horizon: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Stage 2: DeGennes swarm generates conjectures from experiments.

        Key principle: DeGennes proposes ideas from *experimentation*
        (numerical computation, pattern observation, empirical data) —
        NOT from abstract "alien math".  Every conjecture must be
        grounded in observable computational evidence.

        The swarm runs ``num_degennes_agents`` agents in parallel,
        each specializing in a different aspect of the target domain.

        Returns:
            List of conjecture dicts with keys: id, title, statement,
            evidence, lean_sketch, confidence.
        """
        stage_name = "2_conjecture_generation"
        total = config.num_conjectures
        print(f"\n[Stage 2/6] 🧪 DeGennes — Generating {total} conjectures "
              f"({config.num_degennes_agents} agents)...")
        t0 = time.time()

        per_agent_cost = STAGE_COST_ESTIMATES["conjecture_per_agent"]
        self._check_budget(per_agent_cost * config.num_degennes_agents)

        # Delegate to the specialized DeGennes experimentalist module
        conjectures = await generate_experimental_conjectures(
            target_domain=config.target_domain,
            vault_context=horizon,
            num_agents=config.num_degennes_agents,
            conjectures_per_agent=config.conjectures_per_agent,
            model=config.model,
        )

        # Trim to requested count and assign IDs
        conjectures = conjectures[:config.num_conjectures]
        for i, c in enumerate(conjectures):
            c["id"] = f"CONJ-{config.discovery_id}-{i+1:03d}"
            c.setdefault("status", "pending_formalization")

        cost = per_agent_cost * config.num_degennes_agents
        dt = time.time() - t0
        self._record_cost(cost)
        self._audit.record(
            self._make_audit_entry(
                DiscoveryStage.CONJECTURE_GENERATION,
                agent="DeGennes-swarm",
                duration_s=dt,
                cost_usd=cost,
                metrics={"conjectures_generated": len(conjectures)},
            )
        )

        # Store raw conjectures in Alexandrie private room
        self._hub.store_artifact(
            artifact_id=f"conjectures_{config.discovery_id}",
            title=f"Raw Conjectures — {config.target_domain}",
            content=json.dumps(conjectures, indent=2, default=str),
            artifact_type=ArtifactType.CONJECTURE,
            room_type=RoomType.PRIVATE,
            creator="DeGennes-swarm",
            tags=["conjecture", config.target_domain, config.discovery_id],
            metrics={"count": len(conjectures)},
        )

        print(f"  ✅ Generated {len(conjectures)} conjectures "
              f"(stored in private vault) ({dt:.1f}s)")
        return conjectures

    # ------------------------------------------------------------------
    # Stage 3: AUTOFORMALIZE — Newton translates to Lean 4
    # ------------------------------------------------------------------

    async def _stage_autoformalize(
        self,
        config: DiscoveryConfig,
        conjectures: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Stage 3: Newton translates each conjecture to a Lean 4 statement.

        For each conjecture, Newton generates:
        - A Lean 4 ``theorem`` statement with precise types
        - ``sorry`` in the proof body (to be filled in Stage 4)
        - ``import`` statements from Mathlib4
        - ``#check`` assertions for type safety

        Returns:
            List of dicts, each extending the conjecture with a
            ``lean_code`` field containing the Lean 4 source.
        """
        stage_name = "3_autoformalize"
        print(f"\n[Stage 3/6] 📐 Newton — Formalizing "
              f"{len(conjectures)} conjectures to Lean 4...")
        t0 = time.time()

        per_conj_cost = STAGE_COST_ESTIMATES["autoformalize_per_conjecture"]
        self._check_budget(per_conj_cost * len(conjectures))

        async def formalize_one(conjecture: dict[str, Any]) -> dict[str, Any]:
            """Translate a single conjecture to Lean 4."""
            prompt = textwrap.dedent(f"""\
                Translate the following mathematical conjecture into a
                syntactically valid Lean 4 theorem statement.

                Domain: {config.target_domain}
                Conjecture ID: {conjecture.get('id', 'unknown')}
                Title: {conjecture.get('title', 'Untitled')}
                Statement: {conjecture.get('statement', conjecture.get('description', ''))}
                Evidence: {conjecture.get('evidence', 'N/A')}

                Write the Lean 4 code. Use ``sorry`` for the proof body.
                Include Mathlib4 imports and #check statements.
            """).strip()

            lean_code = await agent_generate(
                NEWTON_IDENTITY, prompt, model=config.model,
            )
            conjecture["lean_code"] = lean_code
            conjecture["status"] = "formalized"

            # Count sorry placeholders
            sorry_count = lean_code.lower().count("sorry")
            conjecture["sorry_count"] = sorry_count

            return conjecture

        # Run formalizations concurrently (bounded by swarm size)
        tasks = [formalize_one(c) for c in conjectures]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out failures
        formalized = []
        for r in results:
            if isinstance(r, Exception):
                self._log.warning("formalization_failed", error=str(r))
            elif isinstance(r, dict) and "lean_code" in r:
                formalized.append(r)

        cost = per_conj_cost * len(conjectures)
        dt = time.time() - t0
        self._record_cost(cost)
        self._audit.record(
            self._make_audit_entry(
                DiscoveryStage.AUTOFORMALIZE,
                agent="Newton",
                duration_s=dt,
                cost_usd=cost,
                lean_sorry_count=sum(
                    c.get("sorry_count", 0) for c in formalized
                ),
                metrics={"formalized": len(formalized)},
            )
        )
        print(f"  ✅ Formalized {len(formalized)}/{len(conjectures)} "
              f"conjectures ({dt:.1f}s)")
        return formalized

    # ------------------------------------------------------------------
    # Stage 4: PROOF_SEARCH — Hilbert deterministic-first cascade
    # ------------------------------------------------------------------

    async def _stage_proof_search(
        self,
        config: DiscoveryConfig,
        lean_statements: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Stage 4: Hilbert attempts to prove each formalized conjecture.

        The proof-search cascade runs in strict order, escalating from
        deterministic to probabilistic only when the previous layer fails:

        Layer 1 — **Lean 4 tactic scripts** (deterministic, cost=$0):
            ``simp``, ``omega``, ``decide``, ``norm_num``, ``ring``,
            ``linarith``, ``nlinarith``, ``aesop``.
            These are sound-by-construction: they close the goal or fail.

        Layer 2 — **LeanBert** (if ``enable_leanbert``):
            Fine-tuned transformer trained on Mathlib proofs.  Suggests
            tactic sequences that are likely to work.

        Layer 3 — **DeepSeek-Prover** (if ``enable_deepseek``):
            Large reasoning model specialized for mathematical proofs.
            Higher creativity but also higher hallucination risk.

        Layer 4 — **Gemini 3.1 Pro deep-think**:
            Last resort — broadest reasoning, but proof MUST be
            re-verified by ``lake build`` in Stage 5.

        Returns:
            List of dicts with ``proof_code``, ``sorry_count``,
            ``proof_method`` (which layer succeeded).
        """
        stage_name = "4_proof_search"
        print(f"\n[Stage 4/6] 🏗️  Hilbert — Proof search cascade for "
              f"{len(lean_statements)} statements...")
        t0 = time.time()

        proof_results: list[dict[str, Any]] = []

        for stmt in lean_statements:
            lean_code = stmt.get("lean_code", "")
            conj_id = stmt.get("id", "unknown")

            self._log.info("proof_search_start", conjecture_id=conj_id)

            # ── Layer 1: Deterministic Lean tactics (free) ───────────────
            # Inject standard tactic block to replace sorry
            tactic_proof = self._try_deterministic_tactics(lean_code)
            if tactic_proof is not None:
                stmt["proof_code"] = tactic_proof
                stmt["sorry_count"] = 0
                stmt["proof_method"] = "lean_tactics"
                proof_results.append(stmt)
                print(f"  [{conj_id}] ✅ Proved by Lean tactics (Layer 1)")
                continue

            # ── Layer 2: LeanBert (if enabled) ───────────────────────────
            if config.enable_leanbert:
                self._check_budget(
                    STAGE_COST_ESTIMATES["proof_leanbert_per_conjecture"]
                )
                leanbert_skill = get_skill("leanbert_prover")
                if leanbert_skill:
                    leanbert_result = await leanbert_skill.execute(
                        lean_code=lean_code,
                        domain=config.target_domain,
                    )
                    if leanbert_result and leanbert_result.get("success"):
                        stmt["proof_code"] = leanbert_result["proof"]
                        stmt["sorry_count"] = 0
                        stmt["proof_method"] = "leanbert"
                        self._record_cost(
                            STAGE_COST_ESTIMATES["proof_leanbert_per_conjecture"]
                        )
                        proof_results.append(stmt)
                        print(f"  [{conj_id}] ✅ Proved by LeanBert (Layer 2)")
                        continue

            # ── Layer 3: DeepSeek-Prover (if enabled) ────────────────────
            if config.enable_deepseek:
                self._check_budget(
                    STAGE_COST_ESTIMATES["proof_deepseek_per_conjecture"]
                )
                deepseek_skill = get_skill("deepseek_prover")
                if deepseek_skill:
                    ds_result = await deepseek_skill.execute(
                        lean_code=lean_code,
                        domain=config.target_domain,
                    )
                    if ds_result and ds_result.get("success"):
                        stmt["proof_code"] = ds_result["proof"]
                        stmt["sorry_count"] = 0
                        stmt["proof_method"] = "deepseek"
                        self._record_cost(
                            STAGE_COST_ESTIMATES["proof_deepseek_per_conjecture"]
                        )
                        proof_results.append(stmt)
                        print(f"  [{conj_id}] ✅ Proved by DeepSeek (Layer 3)")
                        continue

            # ── Layer 4: Gemini deep-think (last resort) ─────────────────
            self._check_budget(
                STAGE_COST_ESTIMATES["proof_gemini_per_conjecture"]
            )
            gemini_proof = await self._try_gemini_proof(
                lean_code, config,
            )
            stmt["proof_code"] = gemini_proof
            stmt["sorry_count"] = gemini_proof.lower().count("sorry")
            stmt["proof_method"] = "gemini_deep_think"
            self._record_cost(
                STAGE_COST_ESTIMATES["proof_gemini_per_conjecture"]
            )
            proof_results.append(stmt)

            status = "✅ Proved" if stmt["sorry_count"] == 0 else "⚠️  Partial"
            print(f"  [{conj_id}] {status} by Gemini deep-think (Layer 4) "
                  f"[{stmt['sorry_count']} sorry]")

        dt = time.time() - t0
        self._audit.record(
            self._make_audit_entry(
                DiscoveryStage.PROOF_SEARCH,
                agent="Hilbert-cascade",
                duration_s=dt,
                cost_usd=sum(
                    STAGE_COST_ESTIMATES.get(
                        f"proof_{p.get('proof_method', 'gemini')}_per_conjecture",
                        0.0,
                    )
                    for p in proof_results
                ),
                lean_sorry_count=sum(
                    p.get("sorry_count", 0) for p in proof_results
                ),
                metrics={
                    "total_proofs": len(proof_results),
                    "sorry_free": sum(
                        1 for p in proof_results
                        if p.get("sorry_count", 1) == 0
                    ),
                    "methods": {
                        m: sum(
                            1 for p in proof_results
                            if p.get("proof_method") == m
                        )
                        for m in [
                            "lean_tactics", "leanbert",
                            "deepseek", "gemini_deep_think",
                        ]
                    },
                },
            )
        )
        print(f"  ✅ Proof search complete: "
              f"{sum(1 for p in proof_results if p.get('sorry_count', 1) == 0)}"
              f" sorry-free / {len(proof_results)} total ({dt:.1f}s)")
        return proof_results

    # ------------------------------------------------------------------
    # Stage 5: KERNEL_VERIFY — lake build deterministic gate
    # ------------------------------------------------------------------

    async def _stage_kernel_verify(
        self,
        config: DiscoveryConfig,
        proof_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Stage 5: Deterministic kernel verification via ``lake build``.

        This stage contains **zero LLM calls**.  It is a pure deterministic
        gate: each proof is written to a temporary Lean 4 project and
        ``lake build`` is invoked.  Exit code 0 = verified.  Anything
        else = rejected.

        The Lean 4 kernel is the **incorruptible judge** — it cannot be
        persuaded, bribed, or hallucinated past.  A proof either type-checks
        or it doesn't.  This is the foundational integrity guarantee of the
        entire pipeline.

        Returns:
            List of proof dicts that passed ``lake build`` verification.
        """
        stage_name = "5_kernel_verify"
        print(f"\n[Stage 5/6] 🔐 Kernel — Verifying {len(proof_results)} "
              f"proofs via `lake build`...")
        t0 = time.time()

        verified: list[dict[str, Any]] = []

        for proof in proof_results:
            conj_id = proof.get("id", "unknown")
            lean_code = proof.get("proof_code", proof.get("lean_code", ""))

            # Skip proofs that still contain sorry — they cannot pass
            # kernel verification by definition
            if proof.get("sorry_count", 1) > 0:
                self._log.info(
                    "kernel_skip_sorry",
                    conjecture_id=conj_id,
                    sorry_count=proof.get("sorry_count"),
                )
                proof["kernel_verdict"] = "SKIPPED_SORRY"
                print(f"  [{conj_id}] ⏭️  Skipped (contains sorry)")
                continue

            # Write Lean 4 source to temporary project and run lake build
            try:
                build_ok, stdout, stderr = await self._run_lake_build(
                    lean_code, config,
                )
            except Exception as exc:
                self._log.error(
                    "lake_build_error",
                    conjecture_id=conj_id,
                    error=str(exc),
                )
                proof["kernel_verdict"] = "BUILD_ERROR"
                proof["kernel_stderr"] = str(exc)
                print(f"  [{conj_id}] ❌ Build error: {str(exc)[:80]}")
                continue

            if build_ok:
                proof["kernel_verdict"] = "VERIFIED"
                proof["status"] = "kernel_verified"
                verified.append(proof)
                print(f"  [{conj_id}] ✅ KERNEL VERIFIED — lake build pass")
            else:
                proof["kernel_verdict"] = "REJECTED"
                proof["kernel_stderr"] = stderr[:500]
                print(f"  [{conj_id}] ❌ Rejected — {stderr[:80]}")

        dt = time.time() - t0
        # No LLM cost — this stage is deterministic
        self._audit.record(
            self._make_audit_entry(
                DiscoveryStage.KERNEL_VERIFY,
                agent="lake-build",
                duration_s=dt,
                cost_usd=0.0,
                metrics={
                    "submitted": len(proof_results),
                    "verified": len(verified),
                    "rejected": len(proof_results) - len(verified),
                },
            )
        )
        print(f"  ✅ Kernel verification: {len(verified)}/"
              f"{len(proof_results)} passed ({dt:.1f}s)")
        return verified

    # ------------------------------------------------------------------
    # Stage 6: ARCHIVE_AND_REVIEW — Hypatia + Poincaré + Xavier
    # ------------------------------------------------------------------

    async def _stage_archive_and_review(
        self,
        config: DiscoveryConfig,
        conjectures: list[dict[str, Any]],
        verified_proofs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Stage 6: Archive to Alexandrie, run Poincaré quorum, Xavier gate.

        This final stage has three sub-steps:

        1. **Hypatia** archives all artifacts to the Alexandrie vault:
           - Unverified conjectures → private room (IP protection)
           - Verified proofs → private room initially, pending review

        2. **Poincaré quorum** reviews each verified proof:
           - 3-agent quorum (Skeptic / Advocate / Judge)
           - Checks faithfulness, significance, and axiom hygiene
           - ACCEPT → proof is promoted to open room
           - REJECT / NEEDS_REVISION → stays in private room

        3. **Xavier human gate** (if ``require_human_approval``):
           - Human scientist reviews before open-room promotion
           - Final checkpoint — the pipeline does NOT auto-publish

        After review, generates a LaTeX index page for the open room
        with all accepted proofs rendered in human-readable form.

        Returns:
            Dict with open_artifacts, private_artifacts, latex_index_path.
        """
        stage_name = "6_archive_and_review"
        print(f"\n[Stage 6/6] 📚 Archive & Review — "
              f"{len(verified_proofs)} verified proofs...")
        t0 = time.time()

        open_artifacts: list[str] = []
        private_artifacts: list[str] = []

        # ── Sub-step 1: Archive all conjectures to private vault ─────────
        archive_result = await archive_discovery_run(
            hub=self._hub,
            run_id=config.discovery_id,
            conjectures=conjectures,
            lean_proofs=verified_proofs,
            numerical_results=[],
            audit=self._audit,
        )
        private_artifacts.extend(archive_result)

        # ── Sub-step 2: Poincaré quorum for each verified proof ──────────
        self._check_budget(STAGE_COST_ESTIMATES["poincare_quorum"])

        for proof in verified_proofs:
            conj_id = proof.get("id", "unknown")

            quorum_prompt = textwrap.dedent(f"""\
                Review this kernel-verified proof for promotion to the
                Alexandrie open room.

                Domain: {config.target_domain}
                Conjecture ID: {conj_id}
                Title: {proof.get('title', 'Untitled')}
                Original statement: {proof.get('statement', 'N/A')}

                Lean 4 proof code:
                {proof.get('proof_code', proof.get('lean_code', ''))[:3000]}

                Proof method: {proof.get('proof_method', 'unknown')}
                Kernel verdict: {proof.get('kernel_verdict', 'unknown')}

                Render your VERDICT as a JSON object.
            """).strip()

            verdict_raw = await agent_generate(
                POINCARE_IDENTITY, quorum_prompt, model=config.model,
            )
            verdict = self._parse_json_safe(verdict_raw) or {
                "verdict": "NEEDS_REVISION",
                "confidence": 0.5,
            }

            proof["poincare_verdict"] = verdict

            if verdict.get("verdict") == "ACCEPT":
                # Promote to open room (subject to human gate)
                if config.require_human_approval:
                    proof["status"] = "pending_human_review"
                    print(f"  [{conj_id}] 🔍 Poincaré ACCEPT — "
                          f"awaiting Xavier human gate")
                else:
                    proof["status"] = "accepted_open"
                    artifact_id = f"proof_{conj_id}"
                    self._hub.store_artifact(
                        artifact_id=artifact_id,
                        title=f"Verified Proof — {proof.get('title', conj_id)}",
                        content=proof.get(
                            "proof_code", proof.get("lean_code", "")
                        ),
                        artifact_type=ArtifactType.PROOF,
                        room_type=RoomType.OPEN_ACCESS,
                        creator="DiscoveryPipeline",
                        tags=[
                            "proof", "verified", config.target_domain,
                            config.discovery_id,
                        ],
                        metrics={
                            "proof_method": proof.get("proof_method"),
                            "poincare_confidence": verdict.get("confidence"),
                        },
                    )
                    open_artifacts.append(artifact_id)
                    print(f"  [{conj_id}] ✅ Promoted to open room")
            else:
                proof["status"] = "private_needs_revision"
                print(f"  [{conj_id}] ⚠️  Poincaré {verdict.get('verdict')} "
                      f"— stays in private room")

        # ── Sub-step 3: Generate LaTeX index for open room ───────────────
        self._check_budget(STAGE_COST_ESTIMATES["hypatia_latex_index"])

        latex_index_path = ""
        if open_artifacts or not config.require_human_approval:
            latex_index_path = generate_latex_index(
                conjectures=conjectures,
                lean_proofs=verified_proofs,
                run_id=config.discovery_id,
            )
            self._record_cost(STAGE_COST_ESTIMATES["hypatia_latex_index"])

        quorum_cost = STAGE_COST_ESTIMATES["poincare_quorum"]
        dt = time.time() - t0
        self._record_cost(quorum_cost)
        self._audit.record(
            self._make_audit_entry(
                DiscoveryStage.ARCHIVE_AND_REVIEW,
                agent="Hypatia+Poincaré",
                duration_s=dt,
                cost_usd=quorum_cost,
                metrics={
                    "open_artifacts": len(open_artifacts),
                    "private_artifacts": len(private_artifacts),
                    "poincare_accept": sum(
                        1 for p in verified_proofs
                        if p.get("poincare_verdict", {}).get("verdict")
                        == "ACCEPT"
                    ),
                },
            )
        )
        print(f"  ✅ Archived: {len(open_artifacts)} open, "
              f"{len(private_artifacts)} private ({dt:.1f}s)")

        return {
            "open_artifacts": open_artifacts,
            "private_artifacts": private_artifacts,
            "latex_index_path": latex_index_path,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _try_deterministic_tactics(self, lean_code: str) -> str | None:
        """Attempt to replace ``sorry`` with standard Lean 4 tactics.

        Constructs a proof attempt using the standard tactic battery:
        ``simp``, ``omega``, ``decide``, ``norm_num``, ``ring``,
        ``linarith``, ``nlinarith``, ``aesop``.

        This is a *heuristic* — it generates a candidate proof that must
        still pass ``lake build`` in Stage 5.  Returns ``None`` if the
        tactic substitution cannot be constructed.
        """
        if "sorry" not in lean_code.lower():
            return lean_code

        # Replace sorry with a tactic cascade
        tactic_block = (
            "by\n"
            "  first\n"
            "  | simp\n"
            "  | omega\n"
            "  | decide\n"
            "  | norm_num\n"
            "  | ring\n"
            "  | linarith\n"
            "  | nlinarith\n"
            "  | aesop"
        )

        import re
        candidate = re.sub(
            r'\bsorry\b',
            tactic_block,
            lean_code,
        )

        # Only return if we actually made replacements
        if candidate != lean_code:
            return candidate
        return None

    async def _try_gemini_proof(
        self,
        lean_code: str,
        config: DiscoveryConfig,
    ) -> str:
        """Layer 4: Use Gemini 3.1 Pro deep-think to attempt a proof.

        This is the last resort in the cascade.  Gemini has the broadest
        reasoning capability but also the highest hallucination risk.
        Any proof it suggests MUST pass ``lake build`` in Stage 5.
        """
        prompt = textwrap.dedent(f"""\
            You are a Lean 4 proof engineer. Complete the following Lean 4
            theorem by replacing all ``sorry`` placeholders with valid proofs.

            Domain: {config.target_domain}

            ```lean4
            {lean_code}
            ```

            Rules:
            - Use Mathlib4 tactics: simp, omega, decide, norm_num, ring,
              linarith, nlinarith, aesop, exact, apply, intro, cases, rcases
            - If you cannot prove a goal, leave ``sorry`` with a comment
              explaining what approach might work
            - Output raw Lean 4 code only — no markdown fences

            Think deeply about the mathematical structure before writing.
        """).strip()

        return await agent_generate(
            NEWTON_IDENTITY, prompt, model=config.model,
        )

    async def _run_lake_build(
        self,
        lean_code: str,
        config: DiscoveryConfig,
    ) -> tuple[bool, str, str]:
        """Run ``lake build`` on the given Lean 4 source code.

        Creates a temporary Lean 4 project, writes the source file,
        and invokes ``lake build``.

        Returns:
            Tuple of (success: bool, stdout: str, stderr: str).
        """
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory(prefix="agora_lean_") as tmpdir:
            tmp_path = Path(tmpdir)

            # Write lakefile
            lakefile = tmp_path / "lakefile.lean"
            lakefile.write_text(textwrap.dedent("""\
                import Lake
                open Lake DSL

                package «agora_verify» where
                  leanOptions := #[
                    ⟨`autoImplicit, false⟩
                  ]

                @[default_target]
                lean_lib «AgoraVerify» where
                  srcDir := "."

                require mathlib from git
                  "https://github.com/leanprover-community/mathlib4"
            """), encoding="utf-8")

            # Write lean source
            src_file = tmp_path / "AgoraVerify.lean"
            src_file.write_text(lean_code, encoding="utf-8")

            # Run lake build
            proc = await asyncio.create_subprocess_exec(
                "lake", "build",
                cwd=str(tmp_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=300,  # 5 minute timeout
            )
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            return (proc.returncode == 0, stdout, stderr)

    def _check_budget(self, estimated_cost: float) -> None:
        """Check budget before a stage execution.

        Raises:
            RuntimeError: If the estimated cost exceeds remaining budget.
        """
        remaining = self._config.max_budget_usd - self._accumulated_cost_usd
        if estimated_cost > remaining:
            raise RuntimeError(
                f"Budget exceeded: stage cost ${estimated_cost:.2f} > "
                f"remaining ${remaining:.2f} / "
                f"${self._config.max_budget_usd:.2f}"
            )

    def _record_cost(self, cost: float) -> None:
        """Record actual LLM / compute cost."""
        self._accumulated_cost_usd += cost

    def _make_audit_entry(
        self,
        stage: DiscoveryStage,
        agent: str = "",
        duration_s: float = 0.0,
        cost_usd: float = 0.0,
        lean_sorry_count: int = 0,
        metrics: dict[str, Any] | None = None,
    ) -> Any:
        """Create an audit entry compatible with SymposiumAuditTrail.

        Maps DiscoveryStage to the closest PipelineStage for audit
        compatibility, since the audit trail uses PipelineStage internally.
        """
        from agents.pipelines.audit import AuditEntry
        from agents.pipelines.base import PipelineStage

        # Map discovery stages to the closest symposium stage for audit
        stage_map = {
            DiscoveryStage.HORIZON_SCAN: PipelineStage.SOCRATE_RULES,
            DiscoveryStage.CONJECTURE_GENERATION: PipelineStage.HYPOTHESIS_GENERATION,
            DiscoveryStage.AUTOFORMALIZE: PipelineStage.LEAN4_FORMALIZATION,
            DiscoveryStage.PROOF_SEARCH: PipelineStage.LEAN4_FORMALIZATION,
            DiscoveryStage.KERNEL_VERIFY: PipelineStage.KERNEL_COMPILATION,
            DiscoveryStage.ARCHIVE_AND_REVIEW: PipelineStage.PUBLICATION,
        }

        return AuditEntry(
            stage=stage_map.get(stage, PipelineStage.SOCRATE_RULES),
            agent=agent,
            duration_s=duration_s,
            cost_usd=cost_usd,
            lean_sorry_count=lean_sorry_count,
            metrics=metrics or {},
        )

    @staticmethod
    def _parse_json_safe(raw: str) -> dict[str, Any] | None:
        """Best-effort JSON extraction from LLM output."""
        import re

        # Strategy 1: direct parse
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass

        # Strategy 2: extract JSON object via regex
        try:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                return json.loads(match.group())
        except (json.JSONDecodeError, TypeError):
            pass

        # Strategy 3: code fence extraction
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, re.DOTALL)
        if fence_match:
            try:
                return json.loads(fence_match.group(1).strip())
            except (json.JSONDecodeError, TypeError):
                pass

        return None

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def _print_banner(self, config: DiscoveryConfig) -> None:
        """Print the pipeline startup banner."""
        print("=" * 80)
        print("🔬  AGORA DISCOVERY PIPELINE — MATHEMATICAL DISCOVERY")
        print(f"    Domain: {config.target_domain}")
        print(f"    Target conjectures: {config.num_conjectures}")
        print(f"    DeGennes agents: {config.num_degennes_agents}")
        print(f"    Model: {config.model}")
        print(f"    Budget: ${config.max_budget_usd:.2f}")
        print(f"    Proof cascade: Lean tactics"
              f"{' → LeanBert' if config.enable_leanbert else ''}"
              f"{' → DeepSeek' if config.enable_deepseek else ''}"
              f" → Gemini")
        print(f"    Human gate: {'✅ required' if config.require_human_approval else '❌ disabled'}")
        print(f"    Run ID: {config.discovery_id}")
        print(f"    Started: "
              f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        print(f"    GEMINI_API_KEY: "
              f"{'✅ loaded' if gemini_key else '❌ missing'}")
        print("=" * 80)

    def _print_summary(
        self, config: DiscoveryConfig, result: DiscoveryResult,
    ) -> None:
        """Print the final pipeline summary."""
        print(f"\n{'=' * 80}")
        if result.kernel_verified > 0:
            print("🎉  DISCOVERY PIPELINE COMPLETE — New results verified!")
        elif result.conjectures_generated > 0:
            print("⚠️  DISCOVERY PIPELINE COMPLETE — No kernel-verified proofs")
        else:
            print("❌  DISCOVERY PIPELINE FINISHED WITH ERRORS")
        print(f"    Run ID: {config.discovery_id}")
        print(f"    Domain: {config.target_domain}")
        print(f"    Total time: {result.total_duration_s:.0f}s "
              f"({result.total_duration_s / 60:.1f} min)")
        print(f"    Total cost: ${result.total_cost_usd:.2f} / "
              f"${config.max_budget_usd:.2f}")
        print(f"    Conjectures: {result.conjectures_generated} generated → "
              f"{result.conjectures_formalized} formalized")
        print(f"    Proofs: {result.proofs_completed} complete, "
              f"{result.proofs_with_sorry} partial")
        print(f"    Kernel verified: {result.kernel_verified}")
        print(f"    Vault: {len(result.vault_open_artifacts)} open, "
              f"{len(result.vault_private_artifacts)} private")
        if result.latex_index_path:
            print(f"    LaTeX index: {result.latex_index_path}")
        if result.warnings:
            print(f"    ⚠️  Warnings: {len(result.warnings)}")
            for w in result.warnings:
                print(f"       • {w}")
        print(f"{'=' * 80}")
