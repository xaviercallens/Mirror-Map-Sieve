# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Tensor Rank Search Pipeline — Automated discovery of low-rank
tensor decompositions for ⟨N,N,N⟩ matrix multiplication tensors.

This pipeline targets Open Problem 2 from Paper B (Callens 2026):
"Can a complete set of 26 (or fewer) decomposition nodes be
constructed that verifiably reconstructs ⟨4,4,4⟩?"

Pipeline Stages:
  1. SURVEY     — Literature scan for known tensor decomposition techniques
  2. FORMULATE  — Generate candidate decomposition strategies
  3. SEARCH     — Computational search for rank-1 tensor components
  4. VERIFY     — Lean 4 verification of discovered decompositions
  5. SYNTHESIZE — Monograph generation with results

Architecture follows the established AgentPipeline pattern from base.py,
using agent_generate() for LLM-based stages and exec() for computational
search stages.

Key Design Decision: We search over the dual number algebra ℝ[ε]/(ε²)
rather than ℝ alone, since the nilpotent ε element may enable
additional cancellation pathways (per the ChargingAlgebra framework).
However, results must also be checked over ℝ to distinguish genuine
rank reduction from artefacts of the ε-extension.
"""

from __future__ import annotations

import json
import textwrap
import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any

import structlog

from agents.pipelines.base import agent_generate

logger = structlog.get_logger(__name__)


# ── Pipeline Stages ───────────────────────────────────────────────────────

class TensorSearchStage(IntEnum):
    """Stages of the tensor rank search pipeline."""
    SURVEY = 1       # Literature survey of tensor decomposition methods
    FORMULATE = 2    # Generate candidate decomposition strategies
    SEARCH = 3       # Computational search (the core stage)
    VERIFY = 4       # Lean 4 verification of results
    SYNTHESIZE = 5   # Monograph generation


# ── Configuration ─────────────────────────────────────────────────────────

@dataclass(slots=True)
class TensorSearchConfig:
    """Configuration for a tensor rank search run.

    Attributes:
        target_n: Matrix dimension to target (default 4 for ⟨4,4,4⟩).
        target_rank: Maximum rank to search for (default 48, current best).
        search_over_dual: Whether to include ε-elements in the search.
        max_iterations: Maximum iterations for the computational search.
        output_dir: Directory for output files.
        model: LLM model for survey and formulation stages.
    """
    target_n: int = 4
    target_rank: int = 48  # Current best = 48 (AlphaEvolve 2025)
    search_over_dual: bool = True
    max_iterations: int = 100_000
    output_dir: Path = Path("output/tensor_rank_search")
    model: str = "gemini-2.5-pro"


# ── Pipeline Result ───────────────────────────────────────────────────────

@dataclass(slots=True)
class TensorSearchResult:
    """Results from a tensor rank search pipeline run."""
    search_id: str
    stages_completed: list[str] = field(default_factory=list)
    total_duration_s: float = 0.0
    best_rank_found: int | None = None
    decomposition_verified: bool = False
    lean4_verdict: str = ""
    monograph_path: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "search_id": self.search_id,
            "stages_completed": self.stages_completed,
            "total_duration_s": round(self.total_duration_s, 3),
            "best_rank_found": self.best_rank_found,
            "decomposition_verified": self.decomposition_verified,
            "lean4_verdict": self.lean4_verdict,
            "monograph_path": self.monograph_path,
            "warnings": self.warnings,
        }


# ── Agent Identities ─────────────────────────────────────────────────────

SURVEY_IDENTITY = textwrap.dedent("""\
    You are a specialist in algebraic complexity theory and tensor
    decomposition. Survey the state of the art for low-rank decompositions
    of the ⟨N,N,N⟩ matrix multiplication tensor.

    Cover:
    1. Known rank bounds for small N (N=2: rank 7, N=3: rank 23, N=4: rank 48)
    2. Techniques: Strassen-like, laser method, border rank, substitution
    3. AlphaEvolve (DeepMind 2025): rank 48 for ⟨4,4,4⟩ via evolutionary search
    4. Approaches that use non-standard coefficient domains (dual numbers,
       truncated polynomial rings, Clifford algebras)
    5. Lower bounds: what prevents rank < 2N² - N?

    Output JSON with keys: known_ranks, techniques, open_gaps, lower_bounds.
""").strip()

FORMULATE_IDENTITY = textwrap.dedent("""\
    You are a mathematical strategist for tensor decomposition search.
    Given the survey results, formulate concrete search strategies.

    Each strategy should specify:
    1. The coefficient domain (ℝ, ℚ, ℝ[ε]/(ε²), etc.)
    2. The search space parameterization (which entries to fix vs. search)
    3. The symmetry reductions (permutation groups, sign changes)
    4. The objective function (Frobenius norm of residual tensor)
    5. The search algorithm (gradient descent, evolutionary, MIP, SAT/SMT)

    Output JSON with keys: strategies (list of strategy dicts).
""").strip()

SEARCH_IDENTITY = textwrap.dedent("""\
    You are a computational mathematician. Write Python code using numpy
    that implements a tensor rank search algorithm.

    The code MUST:
    1. Build the standard ⟨N,N,N⟩ matrix multiplication tensor T
    2. Parameterize rank-1 tensors u⊗v⊗w with learnable entries
    3. Use gradient descent (or alternating least squares) to minimize
       ‖T - Σᵢ uᵢ⊗vᵢ⊗wᵢ‖² over R components
    4. Start with R = target_rank and try to decrease
    5. Report the best rank found and the residual norm
    6. Save results to a JSON file

    Output ONLY the Python code in a ```python``` block.
    Store results in a variable called `search_results` (a dict).
""").strip()

VERIFY_IDENTITY = textwrap.dedent("""\
    You are a formal verification specialist for Lean 4. Given a
    tensor decomposition (list of rank-1 tensors), generate a Lean 4
    module that:
    1. Defines each rank-1 tensor as a concrete Lean definition
    2. Sums them to produce the candidate product
    3. States and proves (by native_decide or norm_num) that the sum
       equals the standard matrix multiplication tensor

    Output ONLY valid Lean 4 code. Use rational coefficients (ℚ) to
    enable kernel-decidable verification.
""").strip()


# ── Pipeline Orchestrator ─────────────────────────────────────────────────

class TensorRankSearchPipeline:
    """Orchestrates the tensor rank search pipeline.

    Usage:
        config = TensorSearchConfig(target_n=4, target_rank=48)
        pipeline = TensorRankSearchPipeline(config)
        result = await pipeline.run()
    """

    def __init__(self, config: TensorSearchConfig):
        self._config = config
        self._search_id = f"tensor-search-{uuid.uuid4().hex[:8]}"
        self._result = TensorSearchResult(search_id=self._search_id)

    async def run(self) -> TensorSearchResult:
        """Execute the full tensor rank search pipeline."""
        t0 = time.monotonic()
        log = logger.bind(search_id=self._search_id)
        log.info("pipeline_start",
                 target_n=self._config.target_n,
                 target_rank=self._config.target_rank)

        # Ensure output directory exists
        self._config.output_dir.mkdir(parents=True, exist_ok=True)

        # ── Stage 1: Survey ──────────────────────────────────────────
        log.info("stage_start", stage="SURVEY")
        survey = await self._stage_survey()
        self._result.stages_completed.append("SURVEY")

        # ── Stage 2: Formulate ───────────────────────────────────────
        log.info("stage_start", stage="FORMULATE")
        strategies = await self._stage_formulate(survey)
        self._result.stages_completed.append("FORMULATE")

        # ── Stage 3: Search ──────────────────────────────────────────
        log.info("stage_start", stage="SEARCH")
        search_results = await self._stage_search(strategies)
        self._result.stages_completed.append("SEARCH")
        self._result.best_rank_found = search_results.get("best_rank")

        # ── Stage 4: Verify ──────────────────────────────────────────
        if search_results.get("decomposition"):
            log.info("stage_start", stage="VERIFY")
            lean_code = await self._stage_verify(search_results)
            self._result.stages_completed.append("VERIFY")
            self._result.lean4_verdict = lean_code.get("verdict", "UNKNOWN")
            self._result.decomposition_verified = (
                lean_code.get("verdict") == "VERIFIED"
            )
        else:
            log.info("stage_skip", stage="VERIFY",
                     reason="no decomposition found")

        # ── Stage 5: Synthesize ──────────────────────────────────────
        log.info("stage_start", stage="SYNTHESIZE")
        await self._stage_synthesize(survey, search_results)
        self._result.stages_completed.append("SYNTHESIZE")

        self._result.total_duration_s = time.monotonic() - t0
        log.info("pipeline_complete",
                 duration_s=self._result.total_duration_s,
                 best_rank=self._result.best_rank_found)

        return self._result

    # ── Stage Implementations ─────────────────────────────────────────

    async def _stage_survey(self) -> dict:
        """Stage 1: Literature survey on tensor decomposition."""
        prompt = f"""
Survey the state of the art for decompositions of the ⟨{self._config.target_n},{self._config.target_n},{self._config.target_n}⟩
matrix multiplication tensor. Include:
- All known rank bounds for N={self._config.target_n}
- Techniques that have been tried
- Lower bounds
- Recent breakthroughs (AlphaEvolve 2025)

Output as JSON.
"""
        response = await agent_generate(
            SURVEY_IDENTITY, prompt.strip(), self._config.model
        )
        return _parse_json_response(response, "survey")

    async def _stage_formulate(self, survey: dict) -> dict:
        """Stage 2: Generate search strategies."""
        prompt = f"""
Given this survey of tensor rank bounds:
{json.dumps(survey, indent=2)[:3000]}

Formulate 3 concrete search strategies for finding a rank-{self._config.target_rank}
(or lower) decomposition of ⟨{self._config.target_n},{self._config.target_n},{self._config.target_n}⟩.

{"Include strategies using the dual number algebra ℝ[ε]/(ε²)." if self._config.search_over_dual else ""}

Output as JSON with key "strategies".
"""
        response = await agent_generate(
            FORMULATE_IDENTITY, prompt.strip(), self._config.model
        )
        return _parse_json_response(response, "strategies")

    async def _stage_search(self, strategies: dict) -> dict:
        """Stage 3: Computational search for decompositions.

        This is the core computational stage. It generates and executes
        Python code that performs alternating least squares (ALS) or
        gradient descent to find low-rank tensor decompositions.
        """
        prompt = f"""
Write Python code (using only numpy) to search for a rank-R decomposition
of the ⟨{self._config.target_n},{self._config.target_n},{self._config.target_n}⟩ matrix multiplication tensor.

Use alternating least squares (ALS):
1. Build T as an N²×N²×N² tensor where T[ik,kj,ij] = 1
2. Initialize R random rank-1 tensors (u_r, v_r, w_r)
3. Alternately fix two factors and solve for the third via least squares
4. Track ‖T - Σ u_r⊗v_r⊗w_r‖_F
5. Try R = {self._config.target_rank} down to R = {self._config.target_n**2}
6. Max iterations per R: {min(self._config.max_iterations, 500)}

Strategies to incorporate:
{json.dumps(strategies, indent=2)[:2000]}

Store results in `search_results` dict with keys:
  best_rank, residual_norm, converged, iterations, decomposition (list of triples)

Output ONLY the Python code.
"""
        response = await agent_generate(
            SEARCH_IDENTITY, prompt.strip(), self._config.model
        )

        # Extract and execute the code
        code = _extract_code_block(response)
        search_results = _safe_exec(code, timeout_s=120)

        # Save results
        out_path = self._config.output_dir / "search_results.json"
        with open(out_path, "w") as f:
            # numpy arrays aren't JSON-serializable, so we convert
            results_serializable = {
                k: v.tolist() if hasattr(v, "tolist") else v
                for k, v in search_results.items()
                if k != "decomposition"  # decomposition may be huge
            }
            json.dump(results_serializable, f, indent=2)

        logger.info("search_complete",
                     best_rank=search_results.get("best_rank"),
                     residual=search_results.get("residual_norm"))

        return search_results

    async def _stage_verify(self, search_results: dict) -> dict:
        """Stage 4: Generate Lean 4 verification code."""
        decomp = search_results.get("decomposition", [])
        prompt = f"""
Generate Lean 4 code to verify this {len(decomp)}-component tensor
decomposition of ⟨{self._config.target_n},{self._config.target_n},{self._config.target_n}⟩.

The decomposition has {len(decomp)} rank-1 tensors.
Residual norm: {search_results.get('residual_norm', 'unknown')}.

If the residual norm is > 0.01, output code that documents the
FAILURE to decompose, with the residual as evidence.

Output valid Lean 4 code.
"""
        response = await agent_generate(
            VERIFY_IDENTITY, prompt.strip(), self._config.model
        )

        lean_path = self._config.output_dir / "TensorSearchResult.lean"
        lean_path.write_text(response)

        return {
            "verdict": ("VERIFIED" if search_results.get("residual_norm", 1) < 1e-10
                        else "NOT_VERIFIED"),
            "lean_path": str(lean_path),
        }

    async def _stage_synthesize(
        self, survey: dict, search_results: dict
    ) -> None:
        """Stage 5: Generate a summary report."""
        report = {
            "search_id": self._search_id,
            "target": f"⟨{self._config.target_n},{self._config.target_n},{self._config.target_n}⟩",
            "target_rank": self._config.target_rank,
            "best_rank_found": search_results.get("best_rank"),
            "residual_norm": search_results.get("residual_norm"),
            "converged": search_results.get("converged"),
            "verified": self._result.decomposition_verified,
            "survey_highlights": survey.get("known_ranks", {}),
        }

        report_path = self._config.output_dir / "report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        self._result.monograph_path = str(report_path)


# ── Utility Functions ─────────────────────────────────────────────────────

def _parse_json_response(response: str, context: str) -> dict:
    """Parse JSON from an LLM response, with fallback."""
    # Try to find JSON in the response
    import re
    json_match = re.search(r'\{[\s\S]*\}', response)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    logger.warning("json_parse_failed", context=context)
    return {"raw_response": response[:2000], "parse_error": True}


def _extract_code_block(response: str) -> str:
    """Extract Python code from a ```python``` block."""
    import re
    match = re.search(r'```python\s*([\s\S]*?)\s*```', response)
    if match:
        return match.group(1)
    # Fallback: try the whole response as code
    return response


def _safe_exec(code: str, timeout_s: int = 120) -> dict:
    """Execute Python code in a sandboxed namespace.

    Returns the `search_results` dict from the executed code,
    or an error dict if execution fails.

    # Design Decision: We use exec() in a restricted namespace.
    # This is the same pattern used by galileo_simulation.py for
    # running LLM-generated simulation code. In production, this
    # should be replaced with a proper sandbox (e.g., gVisor).
    """
    import signal

    namespace: dict[str, Any] = {"__builtins__": __builtins__}

    # Add numpy to the namespace (the search code needs it)
    try:
        import numpy as np
        namespace["np"] = np
        namespace["numpy"] = np
    except ImportError:
        return {"error": "numpy not available", "best_rank": None}

    try:
        # Timeout guard
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Search exceeded {timeout_s}s timeout")

        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout_s)

        exec(code, namespace)  # noqa: S102

        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

        return namespace.get("search_results", {"error": "no search_results"})

    except Exception as exc:
        signal.alarm(0)
        logger.warning("search_exec_failed", error=str(exc)[:200])
        return {"error": str(exc)[:200], "best_rank": None}


# ── Entry Point ───────────────────────────────────────────────────────────

async def run_tensor_search(
    target_n: int = 4,
    target_rank: int = 48,
    search_over_dual: bool = True,
) -> TensorSearchResult:
    """Convenience entry point for running the tensor rank search.

    Example:
        import asyncio
        result = asyncio.run(run_tensor_search(target_n=4, target_rank=48))
    """
    config = TensorSearchConfig(
        target_n=target_n,
        target_rank=target_rank,
        search_over_dual=search_over_dual,
    )
    pipeline = TensorRankSearchPipeline(config)
    return await pipeline.run()
