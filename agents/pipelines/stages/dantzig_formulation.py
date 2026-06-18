# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Stage: Dantzig — Mathematical Formulation.

George Dantzig, inventor of the simplex method (1947), translates natural-
language problem descriptions into rigorous mathematical programming
formulations in standard form.

The stage produces:
  - Complete formulation: sets, parameters, decision variables, objective
    function, and constraints in standard mathematical notation.
  - Problem classification: LP, IP, MIP, QP, NLP, SOCP, SDP.
  - Structural properties: total unimodularity (TU), balanced matrices,
    network structure, and other exploitable special structures.
  - Solver recommendations: matched to problem class and size.
  - Complexity analysis: worst-case and practical complexity estimates.
  - Reformulation suggestions: tighter formulations, valid inequalities,
    decomposition opportunities (Benders, Dantzig-Wolfe, Lagrangian).
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

DANTZIG_IDENTITY = textwrap.dedent("""\
    You are George Dantzig, the mathematical formulator of the Bellman OR Pipeline.
    Inventor of the simplex method (1947), you bring unparalleled expertise in
    translating real-world problems into precise mathematical programming
    formulations.

    Your role: take a natural-language problem description and produce a
    rigorous mathematical formulation in standard form, suitable for
    computational solving.

    For every formulation you must provide:
      1. **Sets**: Index sets with clear definitions and cardinalities.
      2. **Parameters**: Input data with units and typical ranges.
      3. **Decision Variables**: Type (continuous, binary, integer), bounds,
         and semantic meaning.
      4. **Objective Function**: Minimise or maximise, with each term explained.
      5. **Constraints**: Classified as equality, inequality, bound, logical,
         or linking constraints. Each with a brief justification.

    Then analyse the formulation:
      - Problem class: LP | IP | MIP | QP | NLP | SOCP | SDP
      - Structural properties: total unimodularity (TU), balanced matrix,
        network matrix, interval matrix, conservation-of-flow structure
      - Recommended solver(s) with justification
      - Worst-case complexity and practical tractability estimate
      - Special structure that can be exploited (e.g. block-angular,
        staircase, set-packing polytope)
      - Reformulation suggestions: tighter LP relaxations, valid
        inequalities, decomposition opportunities (Benders, Dantzig-Wolfe,
        Lagrangian relaxation, column generation)

    Output ONLY valid JSON with these keys:
    {
        "formulation": {
            "sets": [...],
            "parameters": [...],
            "decision_variables": [...],
            "objective": "...",
            "constraints": [...]
        },
        "problem_class": "LP|IP|MIP|QP|NLP|SOCP|SDP",
        "structural_properties": [...],
        "recommended_solver": "...",
        "complexity": "...",
        "special_structure": "...",
        "reformulation_suggestions": [...]
    }
""")

# ── Main stage function ──────────────────────────────────────────────────────


async def run_dantzig_formulation(
    problem_description: str,
    domain: str,
    model: str = "gemini-2.5-pro",
) -> dict[str, Any]:
    """Translate a problem description into a mathematical formulation.

    Dantzig produces a complete mathematical programming formulation in
    standard form, classifies the problem type, identifies exploitable
    structural properties, and recommends appropriate solvers and
    reformulation strategies.

    Args:
        problem_description: Natural-language description of the OR problem
            to formulate. Should include objective, constraints, and any
            domain-specific requirements.
        domain: The OR domain (e.g. "vehicle routing", "scheduling",
            "supply chain optimisation").
        model: Foundation model identifier (default ``"gemini-2.5-pro"``).

    Returns:
        Dict with keys: ``formulation``, ``problem_class``,
        ``structural_properties``, ``recommended_solver``, ``complexity``,
        ``special_structure``, ``reformulation_suggestions``,
        ``domain``, ``problem_description``, ``elapsed_s``, ``agent``.
    """
    logger.info(
        "dantzig_formulation_start",
        domain=domain,
        problem_len=len(problem_description),
    )
    t0 = time.monotonic()

    # Build the formulation prompt — precise and structured
    prompt = textwrap.dedent(f"""\
        Translate the following Operations Research problem into a rigorous
        mathematical programming formulation in standard form.

        Domain: {domain}
        Problem Description:
        {problem_description}

        Provide the complete formulation with:
        1. All sets, parameters, and decision variables clearly defined
        2. Objective function (min or max) with each term explained
        3. All constraints classified and justified
        4. Problem class identification (LP/IP/MIP/QP/NLP/SOCP/SDP)
        5. Structural properties analysis (TU, balanced, network, etc.)
        6. Solver recommendation with justification
        7. Complexity analysis (worst-case and practical)
        8. Reformulation suggestions for tighter bounds or decomposition

        Output ONLY valid JSON.
    """)

    raw = await agent_generate(DANTZIG_IDENTITY, prompt, model=model)

    # ── Parse JSON from model response ────────────────────────────────────
    result: dict[str, Any] = {}
    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            result = json.loads(match.group())
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(
            "dantzig_formulation_json_parse_error",
            error=str(exc)[:120],
        )

    # ── Structured fallback if parsing failed ─────────────────────────────
    # Guarantees downstream stages always receive a valid formulation
    # skeleton, even when the model output is malformed or unavailable.
    if not result or "formulation" not in result:
        logger.info("dantzig_formulation_using_fallback", domain=domain)
        result = {
            "formulation": {
                "sets": [
                    "I: set of items/entities (to be refined)",
                ],
                "parameters": [
                    "c_i: cost coefficient for item i",
                    "a_ij: constraint matrix coefficient",
                    "b_j: right-hand side of constraint j",
                ],
                "decision_variables": [
                    "x_i >= 0: allocation for item i (continuous or integer)",
                ],
                "objective": (
                    "Minimise sum_{i in I} c_i * x_i "
                    "(placeholder — refine with domain-specific costs)"
                ),
                "constraints": [
                    "sum_{i in I} a_ij * x_i <= b_j for all j "
                    "(resource/capacity constraints)",
                    "x_i >= 0 for all i (non-negativity)",
                ],
            },
            "problem_class": "MIP",
            "structural_properties": [
                "To be analysed — check for TU, network structure",
            ],
            "recommended_solver": (
                "Gurobi or CPLEX for MIP; HiGHS for open-source LP/MIP"
            ),
            "complexity": (
                "NP-hard in general for MIP; polynomial if LP relaxation "
                "is integral (e.g., TU constraint matrix)"
            ),
            "special_structure": (
                "Pending analysis — check for block-angular, staircase, "
                "or set-packing structure"
            ),
            "reformulation_suggestions": [
                "Investigate LP relaxation integrality gap",
                "Consider Dantzig-Wolfe decomposition if block structure exists",
                "Add valid inequalities (cover, clique, or flow-cover cuts)",
            ],
        }

    elapsed = time.monotonic() - t0

    # Enrich result with metadata for downstream stages
    result["domain"] = domain
    result["problem_description"] = problem_description
    result["elapsed_s"] = round(elapsed, 2)
    result["agent"] = "Dantzig"

    logger.info(
        "dantzig_formulation_complete",
        elapsed_s=round(elapsed, 1),
        problem_class=result.get("problem_class", "UNKNOWN"),
        recommended_solver=result.get("recommended_solver", "N/A"),
    )
    return result
