# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Stage: Ramanujan — Rank Search via ALS over ε-algebra.

Ramanujan designs and reports on the numerical search for a rank-26
decomposition of the ⟨4,4,4⟩ matrix multiplication tensor over the
ε-algebra (dual numbers: ε² = 0).

This stage:
  1. Loads results from experiments/rank26_report.md if available
  2. Otherwise calls agent_generate with Ramanujan identity to design the search
  3. Reports best rank found and convergence status

The ALS (Alternating Least Squares) search:
  - Tensor: ⟨4,4,4⟩ ∈ ℝ^{16×16×16} flattened
  - Ring: ε-algebra (Z/2Z[ε], ε² = 0) for border rank computation
  - Rank range: 26..40 (target is 26, naive is 64)
  - Restarts: 50 random initializations
  - Convergence: ‖T - Σᵢ aᵢ ⊗ bᵢ ⊗ cᵢ‖_F < 1e-8
"""

from __future__ import annotations

import pathlib
import textwrap
import time
from typing import Any

import structlog

from agents.pipelines.base import agent_generate

logger = structlog.get_logger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────

_EXPERIMENT_REPORT = pathlib.Path("experiments/rank26_report.md")

# ── Agent Identity ────────────────────────────────────────────────────────────

RAMANUJAN_IDENTITY = textwrap.dedent("""\
    You are Srinivasa Ramanujan, the computational oracle of the Agora swarm.
    You specialise in finding numerical witnesses for deep mathematical conjectures.

    Your task: design and analyse an ALS (Alternating Least Squares) search
    for a rank-26 decomposition of the ⟨4,4,4⟩ matrix multiplication tensor
    over the ε-algebra (dual numbers: ε² = 0).

    TENSOR SETUP:
      - ⟨4,4,4⟩ = matrix multiplication tensor for 4×4 matrices
      - Dimensions: 16 × 16 × 16 (4² = 16 for each mode)
      - Naive rank: 64 (=4³), Smirnov bound: ≤ 49, TARGET: ≤ 26
      - Working over: ε-algebra Z[ε]/(ε²) — dual numbers

    ALS ALGORITHM:
      1. Random initialization: A₀ ∈ ℝ^{16×r}, B₀ ∈ ℝ^{16×r}, C₀ ∈ ℝ^{16×r}
      2. Iterate: fix B,C → solve for A by least squares; fix A,C → B; fix A,B → C
      3. Convergence: ‖T - [A,B,C]‖_F < τ (τ = 1e-8)
      4. Repeat for r = 26, 27, ..., 40 with 50 random restarts each

    REPORT FORMAT:
      ## Search Parameters
      ## Results by Rank (r=26: N_converged/50, best_loss, ...)
      ## Best Witness Found (if any): explicit coefficients
      ## Convergence Analysis: loss curves, failure modes
      ## Status: WITNESS_FOUND | FAILED_TO_CONVERGE | PARTIAL_PROGRESS
      ## Scientific Value of Partial Results
""")


async def run_ramanujan_rank_search(
    rank_range: tuple[int, int] = (26, 40),
    restarts: int = 50,
    tolerance: float = 1e-8,
    journal_path: str | None = None,
    audit: Any | None = None,
) -> dict[str, Any]:
    """Run the Ramanujan ALS rank search stage.

    Checks for existing experiment results first; if found, parses them.
    Otherwise, calls Ramanujan to design and analyse the search.

    Args:
        rank_range: (min_rank, max_rank) to search over.
        restarts: Number of random restarts per rank.
        tolerance: ALS convergence tolerance.
        journal_path: Optional path to write the journal entry.
        audit: Optional audit trail instance.

    Returns:
        Dict: {report, witness_found, best_rank, convergence_status, elapsed_s}.
    """
    logger.info("ramanujan_rank_search_start", rank_range=rank_range, restarts=restarts)
    t0 = time.monotonic()

    # ── Check for existing experiment results ─────────────────────────────────
    existing_report = ""
    if _EXPERIMENT_REPORT.exists():
        try:
            existing_report = _EXPERIMENT_REPORT.read_text(encoding="utf-8")
            logger.info(
                "ramanujan_loaded_existing",
                path=str(_EXPERIMENT_REPORT),
                size=len(existing_report),
            )
        except Exception as e:
            logger.warning("ramanujan_load_failed", error=str(e))

    # ── Build prompt ──────────────────────────────────────────────────────────
    if existing_report:
        prompt = textwrap.dedent(f"""\
            Existing experiment results loaded from {_EXPERIMENT_REPORT}:

            {existing_report[:8000]}

            Analyse these results:
            1. What is the best rank found? Did it converge?
            2. Is this a valid witness for R̃(⟨4,4,4⟩) ≤ that rank?
            3. What does this imply for ω via the τ-theorem?
            4. What further experiments would narrow the gap?
            5. Status: WITNESS_FOUND | FAILED_TO_CONVERGE | PARTIAL_PROGRESS

            Produce a full computation report.
        """)
    else:
        prompt = textwrap.dedent(f"""\
            No existing experiment results found. Design the ALS search:

            Parameters:
            - Rank range: {rank_range[0]}..{rank_range[1]}
            - Restarts per rank: {restarts}
            - Convergence tolerance: {tolerance}

            Design the full search:
            1. Tensor parameterisation over ε-algebra
            2. ALS iteration details (step size, regularisation)
            3. Expected compute cost and wall-clock estimate
            4. How to validate a found witness (independent check)
            5. What partial results (e.g., rank 32) are already scientifically valuable

            Produce a computation design report + predicted outcomes.
        """)

    report = await agent_generate(RAMANUJAN_IDENTITY, prompt)

    # ── Parse convergence status ──────────────────────────────────────────────
    witness_found = "WITNESS_FOUND" in report
    failed = "FAILED_TO_CONVERGE" in report
    convergence_status = (
        "WITNESS_FOUND" if witness_found
        else "FAILED_TO_CONVERGE" if failed
        else "PARTIAL_PROGRESS"
    )

    # Heuristic: extract best rank mentioned
    best_rank: int | None = None
    import re
    rank_match = re.search(r"best rank[:\s]+(\d+)", report, re.IGNORECASE)
    if rank_match:
        best_rank = int(rank_match.group(1))

    elapsed = time.monotonic() - t0
    result = {
        "report": report,
        "witness_found": witness_found,
        "best_rank": best_rank,
        "convergence_status": convergence_status,
        "existing_report_loaded": bool(existing_report),
        "elapsed_s": round(elapsed, 2),
        "agent": "Ramanujan",
    }

    if journal_path:
        _write_journal_entry(journal_path, result)

    if audit is not None:
        try:
            audit.record(
                stage="Ramanujan: Rank Search",
                agent="Ramanujan",
                action=(
                    f"ALS search rank {rank_range}, {restarts} restarts. "
                    f"Status: {convergence_status}"
                ),
                elapsed_s=elapsed,
                input_summary=f"rank_range={rank_range}, restarts={restarts}",
                output_summary=f"status={convergence_status}, best_rank={best_rank}",
            )
        except Exception:
            pass

    logger.info(
        "ramanujan_rank_search_complete",
        convergence_status=convergence_status,
        best_rank=best_rank,
        elapsed_s=round(elapsed, 1),
    )
    return result


def _write_journal_entry(path: str, result: dict[str, Any]) -> None:
    """Write a journal markdown entry for this stage."""
    status_emoji = {
        "WITNESS_FOUND": "✅",
        "FAILED_TO_CONVERGE": "❌",
        "PARTIAL_PROGRESS": "🔄",
    }.get(result.get("convergence_status", ""), "❓")

    content = textwrap.dedent(f"""\
        # Stage: Ramanujan — ALS Rank Search

        **Status**: {status_emoji} {result.get('convergence_status', 'UNKNOWN')}
        **Best rank**: {result.get('best_rank', 'N/A')}
        **Witness found**: {result.get('witness_found', False)}
        **Existing data loaded**: {result.get('existing_report_loaded', False)}
        **Elapsed**: {result.get('elapsed_s', 0)}s

        ## Computation Report

        {result.get('report', '')}

        ---
        *Generated by Ramanujan (OlympiadAndComputation) — Agora v4.1*
    """)
    pathlib.Path(path).write_text(content, encoding="utf-8")
    logger.info("ramanujan_journal_written", path=path)
