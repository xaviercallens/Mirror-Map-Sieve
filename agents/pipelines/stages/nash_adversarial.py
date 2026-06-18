# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Stage: Nash — Game-Theoretic Adversarial Review.

Named after John Forbes Nash Jr. (1928–2015), Nobel laureate (1994),
whose equilibrium concept is the foundation of modern game theory.
Nash reviews proposed OR solutions with adversarial thinking: worst-case
analysis, scalability probes, and game-theoretic considerations.

Patent: US-PAT-PEND-2026-0525
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

NASH_IDENTITY = textwrap.dedent("""\
    You are John Nash, Nobel laureate, master of game-theoretic analysis
    and equilibrium concepts. You are the adversarial reviewer for Operations
    Research solutions in the Bellman OR Pipeline.

    Your role: subject every proposed algorithm and formulation to rigorous
    adversarial scrutiny. You think like an opponent constructing worst-case
    inputs, like a referee spotting hidden assumptions, and like a practitioner
    demanding scalability.

    For each proposed optimization approach, analyze:
    1. FORMULATION COMPLETENESS — Is the mathematical program complete?
       Missing constraints? Relaxed integrality that shouldn't be? Are
       there hidden assumptions about the input data?
    2. ALGORITHM CORRECTNESS — Does the algorithm actually guarantee the
       claimed approximation ratio? What are the pathological instances?
       Is the complexity analysis tight or loose?
    3. WORST-CASE ANALYSIS — Construct adversarial instances. What inputs
       would cause the algorithm to perform poorly? What is the true
       competitive ratio or approximation ratio?
    4. GAME-THEORETIC CONSIDERATIONS — Are there strategic interactions?
       (pricing → Stackelberg games, auctions → incentive compatibility,
       scheduling → fairness/envy-freeness, routing → Braess's paradox)
    5. SCALABILITY — Will this solve industrial-size instances?
       (10^5+ variables, 10^6+ constraints) What is the practical
       bottleneck? Memory? Time? Numerical stability?

    Output ONLY valid JSON with these keys:
    {
        "formulation_completeness": <integer 1-10>,
        "missing_constraints": [...],
        "algorithm_correctness": "verified|flawed|unproven",
        "correctness_issues": [...],
        "worst_case_analysis": "...",
        "adversarial_instances": [...],
        "scalability_assessment": "...",
        "practical_bottleneck": "...",
        "game_theoretic_issues": [...],
        "nash_score": <integer 1-10>,
        "verdict": "ACCEPT|REVISE|REJECT",
        "recommendations": [...]
    }
""").strip()


# ── Main stage function ──────────────────────────────────────────────────────


async def run_nash_adversarial(
    formulation: dict[str, Any],
    solutions: list[dict[str, Any]],
    algorithms: list[dict[str, Any]],
    model: str = "gemini-2.5-pro",
) -> dict[str, Any]:
    """Conduct game-theoretic adversarial review of OR solutions.

    Nash reviews the proposed formulation, solutions, and algorithms
    with adversarial thinking: constructing worst-case instances,
    probing scalability limits, and identifying game-theoretic issues
    that could undermine the solution's practical value.

    Args:
        formulation: Mathematical formulation from Dantzig.
        solutions: Solution results from Kantorovich (objective, gap, etc.).
        algorithms: Algorithmic hypotheses from DeGennes with complexity
            claims and approximation ratios.
        model: Foundation model identifier.

    Returns:
        Dict with keys: ``formulation_completeness``, ``algorithm_correctness``,
        ``worst_case_analysis``, ``scalability_assessment``,
        ``game_theoretic_issues``, ``nash_score``, ``verdict``,
        ``elapsed_s``, ``agent``.
    """
    log = logger.bind(stage="nash_adversarial")
    t0 = time.monotonic()

    # ── Build the adversarial review prompt ───────────────────────────────
    # Inject the full context so Nash can critique with precision.
    formulation_str = json.dumps(formulation, indent=2, default=str)[:3000]
    solutions_str = json.dumps(solutions[:5], indent=2, default=str)[:2000]
    algorithms_str = json.dumps(algorithms[:5], indent=2, default=str)[:2000]

    prompt = textwrap.dedent(f"""\
        Conduct a rigorous adversarial review of the following OR solution:

        Mathematical Formulation:
        {formulation_str}

        Solution Results (from Kantorovich solver):
        {solutions_str}

        Proposed Algorithms:
        {algorithms_str}

        Analyse each aspect with game-theoretic rigour:
        1. Is the formulation complete? Are there missing constraints?
        2. Do the algorithms achieve their claimed approximation ratios?
        3. Construct adversarial instances that would defeat the approach.
        4. Assess scalability to industrial-size problems (10^5+ vars).
        5. Identify any game-theoretic issues (incentive compatibility,
           fairness, strategic behaviour).

        Be merciless. A Nash score of 8+ means the solution is
        publication-ready. Below 5 means reject.

        Output ONLY valid JSON.
    """).strip()

    log.info("nash_adversarial_start")
    raw = await agent_generate(NASH_IDENTITY, prompt, model=model)

    # ── Parse JSON from model response ────────────────────────────────────
    result: dict[str, Any] = {}
    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            result = json.loads(match.group())
    except (json.JSONDecodeError, ValueError) as exc:
        log.warning("nash_adversarial_json_parse_error", error=str(exc)[:120])

    # ── Structured fallback ───────────────────────────────────────────────
    if not result or "nash_score" not in result:
        log.info("nash_adversarial_using_fallback")
        result = {
            "formulation_completeness": 5,
            "missing_constraints": ["Unable to fully analyse — review manually"],
            "algorithm_correctness": "unproven",
            "correctness_issues": [],
            "worst_case_analysis": "Adversarial analysis pending manual review",
            "adversarial_instances": [],
            "scalability_assessment": "Unknown — requires benchmark testing",
            "practical_bottleneck": "To be determined",
            "game_theoretic_issues": [],
            "nash_score": 5,
            "verdict": "REVISE",
            "recommendations": [
                "Run on larger benchmark instances to validate scalability",
                "Verify approximation ratio claims with formal proof",
            ],
        }

    elapsed = time.monotonic() - t0

    # Enrich with metadata
    result["elapsed_s"] = round(elapsed, 2)
    result["agent"] = "Nash"

    log.info(
        "nash_adversarial_complete",
        elapsed_s=round(elapsed, 1),
        nash_score=result.get("nash_score", 0),
        verdict=result.get("verdict", "UNKNOWN"),
    )
    return result
