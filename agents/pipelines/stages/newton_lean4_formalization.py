# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Stage: Newton — Lean 4 Formalization of Pipeline Results.

Newton takes the output from all previous stages and produces a formal
Lean 4 statement. Unlike Euler (hypothesis formalization), Newton focuses
on formalizing RESULTS — whether positive (a witness) or negative (a bound).

Key principle: even a negative result deserves formal mathematical language.
A precise statement of "we searched and did not find" is more valuable than
informal prose, because it is reproducible and precisely scoped.

Named after Isaac Newton for his commitment to rigorous mathematical proof
from first principles, and for his systematic approach to celestial mechanics
via formal differential equations rather than informal reasoning.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

import structlog

from agents.pipelines.base import agent_generate

logger = structlog.get_logger(__name__)

# ── Agent Identity ────────────────────────────────────────────────────────────

NEWTON_IDENTITY = textwrap.dedent("""\
    You are Newton, the formal mathematician of the Agora.
    Your task: write rigorous Lean 4 code that formally states the result
    of a mathematical search or computation.

    Rules:
    1. If a witness was found: write a `theorem` using `native_decide`
    2. If no witness was found: write a formally-scoped `theorem` stating what
       was SEARCHED and NOT FOUND, using `sorry` with an honest comment
    3. Every `sorry` must have: (a) what was tried, (b) best result, (c) next approach
    4. Include `#print axioms` comments to document dependencies
    5. Never claim more than the computation showed

    Output raw Lean 4 code only — no markdown fences, no explanations outside comments.
""")


async def run_newton_formalization(
    witness: Any,
    best_residual: float,
    quorum_verdict: dict[str, Any],
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Newton writes the Lean 4 formalization of the search result.

    Args:
        witness:        The found decomposition witness, or None if not found.
        best_residual:  Best ALS residual achieved (0.0 = exact decomposition).
        quorum_verdict: Poincaré quorum verdict dict.
        output_path:    File path to write the Lean 4 code.

    Returns:
        A dict with `status`, `lean4_code`, and `output_path`.
    """
    log = logger.bind(stage="newton_lean4_formalization")
    log.info("newton_start", witness_found=witness is not None, residual=best_residual)

    verdict = quorum_verdict.get("verdict", "NEEDS_WORK")
    judge_synthesis = quorum_verdict.get("judge_synthesis", "No synthesis available.")

    if witness is not None:
        # ── Positive case: witness found ──────────────────────────────────
        prompt = textwrap.dedent(f"""\
            A rank-26 decomposition of the 4×4 matrix multiplication tensor has been found
            over the KalPhaseWeight ε-algebra (TrivSqZeroExt ℚ ℚ) with residual < 1e-6.

            Quorum verdict: {verdict} (confidence: {quorum_verdict.get('confidence', 0):.0%})
            Judge synthesis: {judge_synthesis[:300]}

            Write Lean 4 code in `namespace AlienMath.Rank26Result` that:
            1. States the theorem: `theorem kal_rank26_verified : ...`
            2. Provides a `native_decide` proof referencing the numeric witness
            3. Includes `#print axioms` to show dependencies

            The witness matrices are available at experiments/rank26_witness.json.
            Use `native_decide` for the verification step.
        """)
        status = "WITNESS_FORMALIZED"
    else:
        # ── Negative case: no witness found ──────────────────────────────
        prompt = textwrap.dedent(f"""\
            An ALS search for a rank-26 decomposition of the 4×4 matrix multiplication
            tensor over KalPhaseWeight ε-algebra found NO witness.
            Best ALS residual: {best_residual:.6f} (tensor Frobenius norm: 8.0)
            Ranks searched: 26 through 40, with 50 restarts each.

            Quorum verdict: {verdict} (confidence: {quorum_verdict.get('confidence', 0):.0%})
            Judge synthesis: {judge_synthesis[:300]}

            Write Lean 4 code in `namespace AlienMath.Rank26Result` that formally states:
            1. What was searched: rank range, algebra, method
            2. What was NOT found (scope the negative result precisely)
            3. What open questions remain
            4. A formally-stated open problem: "Is R_{{TrivSqZeroExt ℚ ℚ}}(⟨4,4,4⟩) < 40?"

            Use `sorry` for unproved claims, with honest comments about what's missing.
            Include the Bläser 2003 lower bound as an `axiom` or cited reference.

            The output should demonstrate that NEGATIVE results deserve formal language too.
        """)
        status = "SEARCH_INCONCLUSIVE_FORMALIZED"

    lean4_code = await agent_generate(NEWTON_IDENTITY, prompt)

    # Write to file if path provided
    result = {
        "status": status,
        "lean4_code": lean4_code,
        "output_path": str(output_path) if output_path else None,
    }

    if output_path:
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            header = textwrap.dedent(f"""\
                /-
                Auto-generated by Newton (Lean4 Formalization Agent)
                Pipeline: rank26_discovery
                Witness found: {witness is not None}
                Best ALS residual: {best_residual:.6f}
                Quorum verdict: {verdict}

                Patent: US-PAT-PEND-2026-0525
                -/
            """)
            with open(output_path, "w") as f:
                f.write(header + "\n" + lean4_code)
            log.info("lean4_written", path=str(output_path))
            result["output_path"] = str(output_path)
        except Exception as e:
            log.warning("lean4_write_failed", error=str(e))

    log.info("newton_complete", status=status)
    return result
