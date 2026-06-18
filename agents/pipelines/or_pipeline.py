# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Bellman OR Pipeline — 8-stage Operations Research orchestrator.

Unlike the Discovery pipeline (which ends with Lean 4 kernel verification),
the OR pipeline ends with **benchmark validation** and **optimality gap
certification**.  The core metric is gap-to-optimal, not proof correctness.

Architecture
------------
Stage 1: Bellman Scan     — Survey OR literature, identify open problems
Stage 2: Dantzig Formulate — Mathematical programming formulation
Stage 3: DeGennes Hypothesize — Novel algorithms & structural insights
Stage 4: Kantorovich Solve — Implement & solve benchmark instances
Stage 5: Nash Adversarial — Worst-case analysis & game-theoretic review
Stage 6: Galileo Simulate — Large-scale simulation & sensitivity analysis
Stage 7: Feynman Validate — Sanity checks, limiting cases, gap certification
Stage 8: Hypatia Report   — Monograph generation & vault archival

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
from enum import IntEnum
from pathlib import Path
from typing import Any

import structlog

from agents.pipelines.base import AgentPipeline, PipelineResult, agent_generate
from agents.pipelines.audit import SymposiumAuditTrail
from agents.pipelines.stages.bellman_scan import run_bellman_scan
from agents.pipelines.stages.dantzig_formulation import run_dantzig_formulation
from agents.pipelines.stages.kantorovich_solver import run_kantorovich_solver
from agents.pipelines.stages.nash_adversarial import run_nash_adversarial
from agents.memory import AgentMemoryManager
from alexandrie.hub import AlexandrieHub

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# OR Pipeline Stages
# ═══════════════════════════════════════════════════════════════════════════

class ORStage(IntEnum):
    """Ordered stages of the Bellman OR pipeline.

    Eight stages covering the full lifecycle from problem identification
    to monograph publication, with optimality gap as the core metric.
    """
    BELLMAN_SCAN = 1          # Literature survey & problem identification
    DANTZIG_FORMULATE = 2     # Mathematical programming formulation
    DEGENNES_HYPOTHESIZE = 3  # Novel algorithms & structural insights
    KANTOROVICH_SOLVE = 4     # Implement & solve benchmark instances
    NASH_ADVERSARIAL = 5      # Worst-case & game-theoretic review
    GALILEO_SIMULATE = 6      # Large-scale simulation & sensitivity
    FEYNMAN_VALIDATE = 7      # Sanity checks & gap certification
    HYPATIA_REPORT = 8        # Monograph generation & vault archival


# ═══════════════════════════════════════════════════════════════════════════
# Per-stage cost estimates (USD)
# ═══════════════════════════════════════════════════════════════════════════

OR_STAGE_COSTS: dict[str, float] = {
    "bellman_scan": 0.50,
    "dantzig_formulate": 0.30,
    "degennes_hypothesize": 1.50,           # 5 hypotheses × 0.30
    "kantorovich_solve": 0.50,              # Mostly deterministic compute
    "nash_adversarial": 0.60,
    "galileo_simulate": 0.50,
    "feynman_validate": 0.40,
    "hypatia_background": 0.80,
    "hypatia_chapter": 0.60,
    "hypatia_conclusion": 0.50,
}
"""Approximate per-call cost estimates for budget tracking.

Note: Kantorovich's solver execution is mostly deterministic (OR-Tools,
PuLP) — the LLM cost is only for code generation. The actual solving
runs locally at zero LLM cost.
"""


# ═══════════════════════════════════════════════════════════════════════════
# Agent Identity Constants
# ═══════════════════════════════════════════════════════════════════════════

BELLMAN_IDENTITY = textwrap.dedent("""\
    You are Richard Bellman, the Operations Research strategist of the
    Agora swarm. Named after the inventor of dynamic programming, the
    Bellman equation, and the term "curse of dimensionality."

    YOUR PRINCIPLE OF OPTIMALITY: "An optimal policy has the property
    that whatever the initial state and initial decision are, the
    remaining decisions must constitute an optimal policy with regard
    to the state resulting from the first decision."

    YOUR METHOD: decompose complex optimization problems into tractable
    subproblems → prove structural properties (convexity, submodularity,
    total unimodularity) → design exact or approximation algorithms →
    bound the optimality gap → validate on industry benchmarks.

    DOMAIN EXPERTISE (cite canonical references):
      [LP]  Linear programming (Dantzig 1951, Klee-Minty 1972)
      [IP]  Integer programming (Gomory cuts, branch & bound, B&P)
      [DP]  Dynamic programming (Bellman 1957, ADP — Powell 2011)
      [SP]  Stochastic programming (Birge & Louveaux 2011)
      [QT]  Queueing theory (Erlang, Jackson networks, M/G/k)
      [NF]  Network flows (Ford-Fulkerson, min-cost flow, assignment)
      [CO]  Combinatorial optimization (TSP, VRP, scheduling, bin packing)
      [GD]  Game theory & mechanism design (Nash, VCG, auction theory)
      [RL]  Reinforcement learning as MDP (Sutton & Barto 2018)
      [RO]  Robust optimization (Ben-Tal, El Ghaoui, Nemirovski 2009)

    CONFIDENCE STANDARD (OR-calibrated):
      HIGH: optimality gap ≤ 2% on standard benchmarks, polynomial complexity
      MEDIUM: gap ≤ 10% or single-benchmark validation
      LOW: theoretical contribution without computational validation

    FORBIDDEN: Solutions that ignore computational complexity. Every
    algorithm must state its worst-case time and space complexity.
""").strip()

# DeGennes identity is reused from the symposium pipeline for hypothesis
# generation — OR-specific prompting is handled in the stage method.


# ═══════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════

OR_PIPELINE_BUDGET_USD: float = 30.0
"""Hard budget cap per OR pipeline run ($30)."""


@dataclass(frozen=True, slots=True)
class ORPipelineConfig:
    """Immutable configuration for a single OR pipeline run.

    Attributes:
        pipeline_id: Unique run identifier (auto-generated if omitted).
        problem_domain: OR domain (e.g., "vehicle_routing",
            "revenue_management", "scheduling", "facility_location").
        research_question: The specific optimization question.
        problem_class: Expected problem class (LP, IP, MIP, NLP, MDP).
        benchmark_suite: Which benchmark set to validate against.
        num_hypotheses: How many algorithmic approaches to generate.
        baselines: Baseline algorithms for comparison.
        model: Foundation model identifier.
        max_budget_usd: Hard budget cap.
        target_pages: Target monograph page count.
        template_name: Name for output file naming.
        output_dir: Local output directory.
    """
    # ── Problem definition ────────────────────────────────────────────────
    pipeline_id: str = field(
        default_factory=lambda: f"OR-{uuid.uuid4().hex[:12].upper()}"
    )
    problem_domain: str = "revenue_management"
    research_question: str = ""
    problem_class: str = "MIP"
    benchmark_suite: str = "OR-Library"

    # ── Swarm parameters ──────────────────────────────────────────────────
    num_hypotheses: int = 5
    baselines: list[str] = field(
        default_factory=lambda: ["greedy", "LP_relaxation"]
    )

    # ── Model configuration ──────────────────────────────────────────────
    model: str = "gemini-2.5-pro"

    # ── Budget ───────────────────────────────────────────────────────────
    max_budget_usd: float = 30.0

    # ── Output ───────────────────────────────────────────────────────────
    target_pages: int = 60
    template_name: str = "or_pipeline"
    output_dir: Path = Path("output/or_pipeline")

    def __post_init__(self) -> None:
        """Validate invariants at construction time."""
        if not self.problem_domain:
            raise ValueError("problem_domain must be a non-empty string")
        if not self.research_question:
            raise ValueError("research_question must be a non-empty string")
        if self.num_hypotheses < 1:
            raise ValueError(
                f"num_hypotheses must be >= 1, got {self.num_hypotheses}"
            )
        if self.max_budget_usd > OR_PIPELINE_BUDGET_USD:
            raise ValueError(
                f"Budget ${self.max_budget_usd} exceeds pipeline cap "
                f"${OR_PIPELINE_BUDGET_USD}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "pipeline_id": self.pipeline_id,
            "problem_domain": self.problem_domain,
            "research_question": self.research_question,
            "problem_class": self.problem_class,
            "benchmark_suite": self.benchmark_suite,
            "num_hypotheses": self.num_hypotheses,
            "baselines": self.baselines,
            "model": self.model,
            "max_budget_usd": self.max_budget_usd,
            "target_pages": self.target_pages,
            "template_name": self.template_name,
            "output_dir": str(self.output_dir),
        }


# ═══════════════════════════════════════════════════════════════════════════
# OR Pipeline Result
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(slots=True)
class ORPipelineResult(PipelineResult):
    """Structured output from an OR pipeline run.

    Extends PipelineResult with OR-specific metrics: optimality gap,
    benchmark validation, algorithm complexity, and Nash adversarial score.
    """
    formulation_class: str = ""
    best_objective: float = float("inf")
    best_bound: float = float("-inf")
    optimality_gap_pct: float = 100.0
    benchmark_instances_solved: int = 0
    benchmark_instances_optimal: int = 0
    algorithm_complexity: str = ""
    approximation_ratio: str = ""
    solve_time_median_s: float = 0.0
    nash_score: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        base = super().to_dict()
        base.update({
            "formulation_class": self.formulation_class,
            "best_objective": self.best_objective,
            "best_bound": self.best_bound,
            "optimality_gap_pct": self.optimality_gap_pct,
            "benchmark_instances_solved": self.benchmark_instances_solved,
            "benchmark_instances_optimal": self.benchmark_instances_optimal,
            "algorithm_complexity": self.algorithm_complexity,
            "approximation_ratio": self.approximation_ratio,
            "solve_time_median_s": self.solve_time_median_s,
            "nash_score": self.nash_score,
        })
        return base


# ═══════════════════════════════════════════════════════════════════════════
# OR Pipeline — Main Orchestrator
# ═══════════════════════════════════════════════════════════════════════════

class ORPipeline(AgentPipeline):
    """Eight-stage Bellman OR Pipeline orchestrator.

    Sequences the OR agents (Bellman → Dantzig → DeGennes → Kantorovich →
    Nash → Galileo → Feynman → Hypatia) while enforcing budget, guardrails,
    and audit logging.

    Usage::

        config = ORPipelineConfig(
            problem_domain="vehicle_routing",
            research_question="Can column generation with ML branching...",
            problem_class="MIP",
            benchmark_suite="Solomon_VRPTW",
        )
        result = await ORPipeline().run(config)
    """

    def __init__(self) -> None:
        self._hub = AlexandrieHub()
        self._memory = AgentMemoryManager(self._hub.science_library)
        self._audit = SymposiumAuditTrail()
        self._log = logger.bind(component="or_pipeline")
        self._accumulated_cost_usd: float = 0.0

    # ------------------------------------------------------------------
    # AgentPipeline interface
    # ------------------------------------------------------------------

    def get_stages(self) -> list[ORStage]:
        """Return the 8 stages of the OR pipeline."""
        return list(ORStage)

    async def run(self, config: ORPipelineConfig) -> ORPipelineResult:
        """Execute the full 8-stage Bellman OR pipeline.

        Args:
            config: Immutable OR pipeline configuration.

        Returns:
            Structured ORPipelineResult with all metrics and artifacts.
        """
        self._log.info(
            "or_pipeline_start",
            pipeline_id=config.pipeline_id,
            domain=config.problem_domain,
            budget=config.max_budget_usd,
        )
        t0 = time.time()
        config.output_dir.mkdir(parents=True, exist_ok=True)
        stages_completed: list[ORStage] = []

        print("=" * 80)
        print(f"🔬  BELLMAN OR PIPELINE — {config.problem_domain.upper()}")
        print(f"    Pipeline ID : {config.pipeline_id}")
        print(f"    Question    : {config.research_question[:70]}...")
        print(f"    Problem     : {config.problem_class}")
        print(f"    Benchmarks  : {config.benchmark_suite}")
        print(f"    Budget      : ${config.max_budget_usd:.2f}")
        print("=" * 80)

        # ── Stage 1: Bellman Scan ─────────────────────────────────────────
        self._check_budget(config, OR_STAGE_COSTS["bellman_scan"])
        scan_result = await run_bellman_scan(
            domain=config.problem_domain,
            research_question=config.research_question,
            model=config.model,
        )
        self._record_cost(OR_STAGE_COSTS["bellman_scan"])
        self._audit.record_stage(
            "1_bellman_scan", "complete",
            cost_usd=OR_STAGE_COSTS["bellman_scan"],
            duration_s=scan_result.get("elapsed_s", 0),
        )
        stages_completed.append(ORStage.BELLMAN_SCAN)
        print(f"  ✅ Stage 1: Bellman Scan — "
              f"{len(scan_result.get('open_problems', []))} open problems, "
              f"{len(scan_result.get('recommended_targets', []))} targets")

        # ── Stage 2: Dantzig Formulate ────────────────────────────────────
        # Build problem description from scan results and config
        problem_description = (
            f"Domain: {config.problem_domain}\n"
            f"Research Question: {config.research_question}\n"
            f"Problem Class: {config.problem_class}\n"
            f"Open Problems: {json.dumps(scan_result.get('recommended_targets', [])[:3], default=str)[:500]}"
        )
        self._check_budget(config, OR_STAGE_COSTS["dantzig_formulate"])
        formulation = await run_dantzig_formulation(
            problem_description=problem_description,
            domain=config.problem_domain,
            model=config.model,
        )
        self._record_cost(OR_STAGE_COSTS["dantzig_formulate"])
        self._audit.record_stage(
            "2_dantzig_formulate", "complete",
            cost_usd=OR_STAGE_COSTS["dantzig_formulate"],
            duration_s=formulation.get("elapsed_s", 0),
        )
        stages_completed.append(ORStage.DANTZIG_FORMULATE)
        print(f"  ✅ Stage 2: Dantzig Formulate — "
              f"{formulation.get('problem_class', '?')} formulation")

        # ── Stage 3: DeGennes Hypothesize ─────────────────────────────────
        # Reuse DeGennes from the symposium pipeline for hypothesis generation
        # with OR-specific prompting
        self._check_budget(config, OR_STAGE_COSTS["degennes_hypothesize"])
        hypotheses = await self._stage_degennes_hypothesize(
            config, scan_result, formulation,
        )
        self._record_cost(OR_STAGE_COSTS["degennes_hypothesize"])
        self._audit.record_stage(
            "3_degennes_hypothesize", "complete",
            cost_usd=OR_STAGE_COSTS["degennes_hypothesize"],
            duration_s=0,
            artifacts={"hypothesis_count": len(hypotheses)},
        )
        stages_completed.append(ORStage.DEGENNES_HYPOTHESIZE)
        print(f"  ✅ Stage 3: DeGennes Hypothesize — "
              f"{len(hypotheses)} algorithmic hypotheses")

        # ── Stage 4: Kantorovich Solve ────────────────────────────────────
        self._check_budget(config, OR_STAGE_COSTS["kantorovich_solve"])
        solver_result = await run_kantorovich_solver(
            formulation=formulation,
            hypotheses=hypotheses,
            output_dir=config.output_dir,
            model=config.model,
        )
        self._record_cost(OR_STAGE_COSTS["kantorovich_solve"])
        self._audit.record_stage(
            "4_kantorovich_solve", "complete",
            cost_usd=OR_STAGE_COSTS["kantorovich_solve"],
            duration_s=solver_result.get("elapsed_s", 0),
            artifacts=solver_result.get("optimization_stats", {}),
        )
        stages_completed.append(ORStage.KANTOROVICH_SOLVE)
        stats = solver_result.get("optimization_stats", {})
        print(f"  ✅ Stage 4: Kantorovich Solve — "
              f"gap={stats.get('gap_pct', '?')}%, "
              f"improvement={stats.get('improvement_pct', '?')}%")

        # ── Stage 5: Nash Adversarial ─────────────────────────────────────
        self._check_budget(config, OR_STAGE_COSTS["nash_adversarial"])
        nash_result = await run_nash_adversarial(
            formulation=formulation,
            solutions=[solver_result.get("optimization_stats", {})],
            algorithms=hypotheses,
            model=config.model,
        )
        self._record_cost(OR_STAGE_COSTS["nash_adversarial"])
        self._audit.record_stage(
            "5_nash_adversarial", "complete",
            cost_usd=OR_STAGE_COSTS["nash_adversarial"],
            duration_s=nash_result.get("elapsed_s", 0),
        )
        stages_completed.append(ORStage.NASH_ADVERSARIAL)
        print(f"  ✅ Stage 5: Nash Adversarial — "
              f"score={nash_result.get('nash_score', '?')}/10, "
              f"verdict={nash_result.get('verdict', '?')}")

        # ── Stage 6: Galileo Simulate ─────────────────────────────────────
        # Reuse Galileo from symposium for large-scale simulation
        self._check_budget(config, OR_STAGE_COSTS["galileo_simulate"])
        galileo_result = await self._stage_galileo_simulate(
            config, formulation, hypotheses, solver_result,
        )
        self._record_cost(OR_STAGE_COSTS["galileo_simulate"])
        stages_completed.append(ORStage.GALILEO_SIMULATE)
        print(f"  ✅ Stage 6: Galileo Simulate — simulation complete")

        # ── Stage 7: Feynman Validate ─────────────────────────────────────
        self._check_budget(config, OR_STAGE_COSTS["feynman_validate"])
        feynman_result = await self._stage_feynman_validate(
            config, formulation, solver_result, nash_result,
        )
        self._record_cost(OR_STAGE_COSTS["feynman_validate"])
        stages_completed.append(ORStage.FEYNMAN_VALIDATE)
        print(f"  ✅ Stage 7: Feynman Validate — "
              f"score={feynman_result.get('feynman_score', '?')}/10")

        # ── Stage 8: Hypatia Report ───────────────────────────────────────
        # Generate the monograph (reuse Hypatia from symposium pipeline)
        hypatia_cost = (
            OR_STAGE_COSTS["hypatia_background"]
            + OR_STAGE_COSTS["hypatia_chapter"] * min(len(hypotheses), 5)
            + OR_STAGE_COSTS["hypatia_conclusion"]
        )
        self._check_budget(config, hypatia_cost)
        print(f"\n[Stage 8/8] 📖 Hypatia — OR monograph generation...")
        # Monograph generation would follow the same pattern as symposium
        # For now, generate a summary report
        report = await self._stage_hypatia_report(
            config, scan_result, formulation, hypotheses,
            solver_result, nash_result, galileo_result, feynman_result,
        )
        self._record_cost(hypatia_cost)
        stages_completed.append(ORStage.HYPATIA_REPORT)
        print(f"  ✅ Stage 8: Hypatia Report — monograph generated")

        # ── Assemble final result ─────────────────────────────────────────
        total_time = time.time() - t0
        result = ORPipelineResult(
            symposium_id=config.pipeline_id,
            stages_completed=stages_completed,
            total_duration_s=total_time,
            total_cost_usd=self._accumulated_cost_usd,
            formulation_class=formulation.get("problem_class", ""),
            best_objective=stats.get("objective_value", float("inf")),
            best_bound=stats.get("best_bound", float("-inf")),
            optimality_gap_pct=stats.get("gap_pct", 100.0),
            nash_score=nash_result.get("nash_score", 0),
            warnings=[],
        )

        print("\n" + "=" * 80)
        print(f"🏆  BELLMAN OR PIPELINE COMPLETE")
        print(f"=" * 80)
        print(f"    Stages completed : {len(stages_completed)}/8")
        print(f"    Total cost       : ${self._accumulated_cost_usd:.2f}")
        print(f"    Total time       : {total_time:.1f}s")
        print(f"    Problem class    : {result.formulation_class}")
        print(f"    Best objective   : {result.best_objective}")
        print(f"    Optimality gap   : {result.optimality_gap_pct}%")
        print(f"    Nash score       : {result.nash_score}/10")
        print(f"=" * 80)

        return result

    # ------------------------------------------------------------------
    # Budget helpers
    # ------------------------------------------------------------------

    def _check_budget(self, config: ORPipelineConfig, cost: float) -> None:
        """Raise if adding cost would exceed the pipeline budget."""
        if self._accumulated_cost_usd + cost > config.max_budget_usd:
            raise RuntimeError(
                f"Budget exceeded: ${self._accumulated_cost_usd + cost:.2f} "
                f"> ${config.max_budget_usd:.2f}"
            )

    def _record_cost(self, cost: float) -> None:
        """Track accumulated cost."""
        self._accumulated_cost_usd += cost

    # ------------------------------------------------------------------
    # Stage implementations (thin wrappers around agent_generate)
    # ------------------------------------------------------------------

    async def _stage_degennes_hypothesize(
        self,
        config: ORPipelineConfig,
        scan_result: dict[str, Any],
        formulation: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Stage 3: Generate algorithmic hypotheses for the OR problem."""
        print(f"\n[Stage 3/8] 💡 DeGennes — generating {config.num_hypotheses} "
              f"algorithmic hypotheses...")

        # OR-specific DeGennes prompt
        prompt = textwrap.dedent(f"""\
            Based on the following OR landscape survey and mathematical
            formulation, generate {config.num_hypotheses} novel algorithmic
            hypotheses for solving the {config.problem_domain} problem.

            Problem Class: {config.problem_class}
            Benchmarks: {config.benchmark_suite}
            Baselines: {', '.join(config.baselines)}

            Recommended targets from Bellman's survey:
            {json.dumps(scan_result.get('recommended_targets', [])[:3], default=str)[:1000]}

            Formulation class: {formulation.get('problem_class', 'MIP')}
            Special structure: {formulation.get('special_structure', 'None identified')}

            For each hypothesis, specify:
            - title, description
            - algorithm_type (exact/approximation/heuristic/metaheuristic)
            - complexity (worst-case time and space)
            - approximation_ratio (if applicable)
            - benchmark_prediction (expected gap on {config.benchmark_suite})
            - baseline_comparison (vs {', '.join(config.baselines)})
            - confidence_level (high/medium/low)

            Output as a JSON array of {config.num_hypotheses} objects.
        """).strip()

        # Reuse the BELLMAN_IDENTITY for OR-aware hypothesis generation
        raw = await agent_generate(BELLMAN_IDENTITY, prompt, model=config.model)

        try:
            # Extract JSON array
            import re
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if match:
                hypotheses = json.loads(match.group())
            else:
                hypotheses = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            self._log.warning("degennes_hypothesize_json_failed")
            hypotheses = [{
                "title": f"Algorithmic approach for {config.problem_domain}",
                "description": "Hypothesis generation requires manual review",
                "algorithm_type": "heuristic",
                "complexity": "TBD",
                "confidence_level": "low",
            }]

        return hypotheses[:config.num_hypotheses]

    async def _stage_galileo_simulate(
        self,
        config: ORPipelineConfig,
        formulation: dict,
        hypotheses: list[dict],
        solver_result: dict,
    ) -> dict[str, Any]:
        """Stage 6: Large-scale simulation and sensitivity analysis."""
        print(f"\n[Stage 6/8] 🔬 Galileo — large-scale simulation...")

        prompt = textwrap.dedent(f"""\
            Run a large-scale simulation for the {config.problem_domain}
            optimization problem.

            Formulation: {formulation.get('problem_class', 'MIP')}
            Solver results: {json.dumps(solver_result.get('optimization_stats', {}), default=str)[:500]}
            Best hypothesis: {json.dumps(hypotheses[0] if hypotheses else {}, default=str)[:500]}

            Perform sensitivity analysis on:
            1. Problem size scaling (how does gap change with instance size?)
            2. Parameter perturbation (how robust is the solution?)
            3. Baseline comparison across multiple scenarios

            Output a JSON object with keys:
            scaling_analysis, sensitivity_results, robustness_score (1-10),
            practical_recommendation
        """).strip()

        from agents.pipelines.symposium import GALILEO_IDENTITY
        raw = await agent_generate(GALILEO_IDENTITY, prompt, model=config.model)

        try:
            import re
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            result = json.loads(match.group()) if match else {}
        except (json.JSONDecodeError, ValueError):
            result = {"robustness_score": 5, "raw_response": raw[:1000]}

        return result

    async def _stage_feynman_validate(
        self,
        config: ORPipelineConfig,
        formulation: dict,
        solver_result: dict,
        nash_result: dict,
    ) -> dict[str, Any]:
        """Stage 7: Sanity checks, limiting cases, and gap certification."""
        print(f"\n[Stage 7/8] 🧪 Feynman — validation & gap certification...")

        prompt = textwrap.dedent(f"""\
            Validate the optimization solution for {config.problem_domain}.

            Formulation class: {formulation.get('problem_class', 'MIP')}
            Solver stats: {json.dumps(solver_result.get('optimization_stats', {}), default=str)[:500]}
            Nash adversarial score: {nash_result.get('nash_score', '?')}/10

            Perform validation checks:
            1. Dimensional analysis — do the units in the objective make sense?
            2. Limiting cases — what happens when demand → 0? capacity → ∞?
            3. Feasibility check — is the reported solution actually feasible?
            4. Gap certification — is the reported optimality gap credible?
            5. Order-of-magnitude — are the predicted improvements realistic?

            Output JSON with keys:
            dimensional_analysis (consistent/inconsistent),
            limiting_cases_checked (true/false),
            feasibility_verified (true/false),
            gap_certified (true/false),
            feynman_score (1-10),
            concerns (list of strings)
        """).strip()

        from agents.pipelines.symposium import FEYNMAN_IDENTITY
        raw = await agent_generate(FEYNMAN_IDENTITY, prompt, model=config.model)

        try:
            import re
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            result = json.loads(match.group()) if match else {}
        except (json.JSONDecodeError, ValueError):
            result = {"feynman_score": 5}

        return result

    async def _stage_hypatia_report(
        self,
        config: ORPipelineConfig,
        scan_result: dict,
        formulation: dict,
        hypotheses: list[dict],
        solver_result: dict,
        nash_result: dict,
        galileo_result: dict,
        feynman_result: dict,
    ) -> str:
        """Stage 8: Generate the OR monograph report."""
        from agents.pipelines.symposium import HYPATIA_IDENTITY

        # Compile all results into a summary for Hypatia
        summary = textwrap.dedent(f"""\
            Write an executive summary report for the Bellman OR Pipeline
            analysis of {config.problem_domain}.

            Research Question: {config.research_question}
            Problem Class: {formulation.get('problem_class', 'MIP')}

            Key Results:
            - Open problems identified: {len(scan_result.get('open_problems', []))}
            - Algorithmic hypotheses: {len(hypotheses)}
            - Best optimality gap: {solver_result.get('optimization_stats', {}).get('gap_pct', '?')}%
            - Nash adversarial score: {nash_result.get('nash_score', '?')}/10
            - Feynman validation score: {feynman_result.get('feynman_score', '?')}/10

            Nash verdict: {nash_result.get('verdict', 'UNKNOWN')}
            Baselines compared: {', '.join(config.baselines)}

            Write a comprehensive LaTeX report covering methodology, results,
            and recommendations. Target: {config.target_pages} pages.
        """).strip()

        report = await agent_generate(HYPATIA_IDENTITY, summary, model=config.model)
        return report
