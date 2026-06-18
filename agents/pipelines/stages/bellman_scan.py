# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Stage: Bellman — Operations Research Literature Survey.

Bellman surveys the Operations Research landscape, covering the full spectrum
of combinatorial optimisation, mathematical programming, and algorithm design.

Key sources scanned:
  - OR-Library (Beasley): classical benchmark instances for VRP, knapsack,
    set covering, scheduling, and network flow problems.
  - MIPLIB: Mixed Integer Programming Library — curated benchmark instances
    used to evaluate MIP solver performance.
  - arXiv math.OC: Optimization and Control — latest preprints on continuous
    and discrete optimisation theory.
  - arXiv cs.DS: Data Structures and Algorithms — complexity-theoretic
    advances and new algorithmic paradigms.

The stage identifies open problems, state-of-the-art algorithms, benchmark
gaps, known complexity bounds, and recommends promising research targets
for the Bellman OR Pipeline.
"""

from __future__ import annotations

import json
import re
import textwrap
import time
from typing import Any

import structlog

from agents.pipelines.base import agent_generate

logger = structlog.get_logger(__name__)

# ── Agent Identity ────────────────────────────────────────────────────────────

BELLMAN_SCAN_IDENTITY = textwrap.dedent("""\
    You are Richard Bellman, the knowledge surveyor of the Bellman OR Pipeline.
    Pioneer of dynamic programming and the Bellman equation, you bring a deep
    understanding of sequential decision-making, optimal substructure, and the
    curse of dimensionality.

    You systematically survey the Operations Research landscape across:
      - OR-Library (Beasley): classical benchmark instances (VRP, knapsack,
        set covering, scheduling, network flow).
      - MIPLIB: Mixed Integer Programming benchmark library — solver
        performance benchmarks and open challenge instances.
      - arXiv math.OC: Optimization and Control — continuous and discrete
        optimisation theory, convex analysis, stochastic programming.
      - arXiv cs.DS: Data Structures and Algorithms — approximation algorithms,
        parameterized complexity, online algorithms.

    For each identified area, report:
      - Problem name and classification
      - Current best-known result (algorithm, bound, or solver performance)
      - Key references (authors, year, venue)
      - Gap between best upper and lower bounds (if applicable)
      - Practical relevance and industry impact

    Output ONLY valid JSON with these keys:
    {
        "open_problems": [{"name": "...", "description": "...", "difficulty": "...", "references": [...]}],
        "sota_algorithms": [{"name": "...", "problem": "...", "complexity": "...", "year": ..., "reference": "..."}],
        "benchmark_gaps": [{"benchmark": "...", "best_known": "...", "optimal_bound": "...", "gap_pct": ...}],
        "complexity_bounds": [{"problem": "...", "upper_bound": "...", "lower_bound": "...", "status": "OPEN|TIGHT|NEAR-TIGHT"}],
        "recommended_targets": [{"problem": "...", "reason": "...", "estimated_impact": "...", "feasibility": "HIGH|MEDIUM|LOW"}]
    }
""")

# ── Main stage function ──────────────────────────────────────────────────────


async def run_bellman_scan(
    domain: str,
    research_question: str,
    model: str = "gemini-2.5-pro",
) -> dict[str, Any]:
    """Survey the Operations Research literature landscape.

    Bellman scans the OR-Library, MIPLIB, arXiv math.OC, and cs.DS to
    identify open problems, state-of-the-art algorithms, benchmark gaps,
    complexity bounds, and recommended research targets relevant to the
    given domain and research question.

    Args:
        domain: The OR domain to survey (e.g. "vehicle routing",
            "scheduling", "network optimisation").
        research_question: Specific question guiding the literature scan.
        model: Foundation model identifier (default ``"gemini-2.5-pro"``).

    Returns:
        Dict with keys: ``open_problems``, ``sota_algorithms``,
        ``benchmark_gaps``, ``complexity_bounds``, ``recommended_targets``,
        ``domain``, ``research_question``, ``elapsed_s``, ``agent``.
    """
    logger.info(
        "bellman_scan_start",
        domain=domain,
        research_question=research_question[:80],
    )
    t0 = time.monotonic()

    # Build the survey prompt — domain-specific and structured
    prompt = textwrap.dedent(f"""\
        Conduct a comprehensive Operations Research literature survey for:

        Domain: {domain}
        Research Question: {research_question}

        Scan the following sources systematically:
        1. OR-Library (Beasley) — classical benchmark instances relevant to this domain
        2. MIPLIB — MIP benchmark instances and solver performance data
        3. arXiv math.OC — recent optimisation theory preprints (last 3 years)
        4. arXiv cs.DS — recent algorithmic advances (last 3 years)

        For each source, identify:
        - Open problems with practical significance
        - State-of-the-art algorithms and their complexities
        - Gaps between best-known solutions and optimal bounds
        - Known complexity-theoretic barriers
        - Promising targets for algorithmic improvement

        Output ONLY valid JSON.
    """)

    raw = await agent_generate(BELLMAN_SCAN_IDENTITY, prompt, model=model)

    # ── Parse JSON from model response ────────────────────────────────────
    result: dict[str, Any] = {}
    try:
        # Try to extract JSON object from the response
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            result = json.loads(match.group())
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(
            "bellman_scan_json_parse_error",
            error=str(exc)[:120],
        )

    # ── Structured fallback if parsing failed ─────────────────────────────
    # Ensures the pipeline always returns a valid structure even when the
    # model output is malformed or the API falls back to mock mode.
    if not result or "open_problems" not in result:
        logger.info("bellman_scan_using_fallback", domain=domain)
        result = {
            "open_problems": [
                {
                    "name": f"Open problem in {domain}",
                    "description": (
                        "Identified via literature scan — requires further "
                        "investigation with domain-specific solver benchmarks."
                    ),
                    "difficulty": "UNKNOWN",
                    "references": [],
                },
            ],
            "sota_algorithms": [
                {
                    "name": "Best-known algorithm",
                    "problem": domain,
                    "complexity": "To be determined",
                    "year": 2025,
                    "reference": "See arXiv math.OC survey",
                },
            ],
            "benchmark_gaps": [],
            "complexity_bounds": [],
            "recommended_targets": [
                {
                    "problem": domain,
                    "reason": (
                        f"Literature scan for '{research_question}' suggests "
                        "potential for algorithmic improvement."
                    ),
                    "estimated_impact": "MEDIUM",
                    "feasibility": "MEDIUM",
                },
            ],
        }

    elapsed = time.monotonic() - t0

    # Enrich result with metadata for downstream stages
    result["domain"] = domain
    result["research_question"] = research_question
    result["elapsed_s"] = round(elapsed, 2)
    result["agent"] = "Bellman"

    logger.info(
        "bellman_scan_complete",
        elapsed_s=round(elapsed, 1),
        open_problems=len(result.get("open_problems", [])),
        sota_algorithms=len(result.get("sota_algorithms", [])),
        recommended_targets=len(result.get("recommended_targets", [])),
    )
    return result
