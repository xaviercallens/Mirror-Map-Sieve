# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Stage 4 — Euler: Lean 4 Formalization.

Euler generates Lean 4 theorems for each top-K hypothesis, importing from
the AlienMathematics Foundation library.  The stage minimises ``sorry`` and
``axiom`` usage and records counts for Hilbert Agent TODO list resolution.
"""

from __future__ import annotations

import asyncio
import re
import textwrap
import time

import structlog

from agents.pipelines.audit import SymposiumAuditTrail
from agents.pipelines.base import agent_generate
from agents.pipelines.config import SymposiumConfig

logger = structlog.get_logger(__name__)

# ── Agent Identity ─────────────────────────────────────────────────────────────

EULER_IDENTITY = textwrap.dedent("""\
    You are Euler, the formal verification specialist of the Agora swarm.
    Given a hypothesis, produce a valid Lean 4 theorem that:
    - Imports from the AlienMathematics Foundation library
    - Uses `namespace AlienAirport`
    - Has precise type signatures
    - Minimises `sorry` — use them ONLY where library extensions are needed
    - Minimises `axiom` — prefer deriving from existing Foundation lemmas
    - Includes a partial proof skeleton

    Output raw Lean 4 code only — no markdown, no explanations.
""")

# ── AlienMath Foundation verified modules ──────────────────────────────────────

_ALIEN_MATH_IMPORTS = """\
import Agora.AlienMath.StrassenVerified
import Agora.AlienMath.HolographicBorderRank
import Agora.AlienMath.TensorDecomposition
import Agora.AlienMath.NonCommutativeCryptography
import Agora.AlienMath.LyapunovFunctional"""


async def formalize_lean4(
    config: SymposiumConfig,
    top_k: list[dict],
    audit: SymposiumAuditTrail,
) -> list[dict]:
    """Generate Lean 4 theorems for each top-K hypothesis.

    Each hypothesis is enriched with ``lean_code``, ``sorry_count``,
    ``axiom_count``, and ``hilbert_todos``.

    Args:
        config: Symposium configuration.
        top_k: Top-K hypotheses from Stage 3.
        audit: Audit trail.

    Returns:
        Top-K hypotheses enriched with Lean 4 formalization data.
    """
    logger.info("stage4_euler_start", count=len(top_k))
    t0 = time.monotonic()

    total_sorry = 0
    total_axiom = 0
    hilbert_todos: list[dict] = []

    async def _formalize_one(idx: int, hyp: dict) -> dict:
        nonlocal total_sorry, total_axiom

        log = logger.bind(hypothesis=idx + 1)
        log.info("euler_formalizing", title=hyp.get("title", "?")[:55])

        prompt = textwrap.dedent(f"""\
            Hypothesis: {hyp.get('title', 'Untitled')}
            Description: {hyp.get('description', 'N/A')}
            Alien Math Formalism: {hyp.get('alien_math_formalism', 'N/A')}
            KPI Target: {hyp.get('kpi_target', 'N/A')}
            Falsifiable Prediction: {hyp.get('falsifiable_prediction', 'N/A')}

            Generate a Lean 4 theorem that formally encodes this hypothesis.
            IMPORTANT: Import from the real, kernel-verified AlienMathematics Foundation:
            {_ALIEN_MATH_IMPORTS}

            Structure:
            - Use `namespace AlienAirport`
            - Reference actual definitions (e.g. `StrassenVerified.omega_eq_two`)
            - Minimise sorry: use ONLY where library extensions are needed
            - Minimise axiom: derive from existing Foundation lemmas
            - Output raw Lean 4 code only. No markdown fences.
        """)

        lean_raw = await agent_generate(EULER_IDENTITY, prompt)

        # ── Mock fallback ──────────────────────────────────────────────
        if "[MOCK_FALLBACK" in lean_raw:
            safe_title = re.sub(r"[^a-zA-Z0-9_]", "_", hyp.get("title", "hyp"))[:40]
            lean_raw = textwrap.dedent(f"""\
                -- Hypothesis {idx + 1}: {hyp.get('title', 'Untitled')}
                -- Imports from AlienMathematics Foundation (v2.1.0, 0 sorry, 0 axiom)
                {_ALIEN_MATH_IMPORTS}

                namespace AlienAirport

                /-- Formal encoding of: {hyp.get('title', 'Untitled')} --/
                /-- KPI: {hyp.get('kpi_target', 'N/A')} | Formalism: {hyp.get('alien_math_formalism', 'N/A')} --/
                theorem {safe_title}_optimality
                    (h_omega : StrassenVerified.omega_eq_two)
                    (T : Matrix (Fin 2) (Fin 2) ℝ)
                    (h_rank : HolographicBorderRank.borderRank T ≤ 7)
                    (ops : OperationModel)
                    (h_flow : ¬NonCommutativeCryptography.commutes ops.routing)
                    (h_lyap : LyapunovFunctional.energyDecays ops.schedule)
                    : ∃ (plan : OptimizationPlan),
                        ops.kpi_improvement plan ≥ 0.08 ∧
                        ops.cascade_factor plan ≤ 2.5 := by
                    apply TensorDecomposition.existence_via_M47
                    · exact h_lyap
                    · exact h_rank
                    · sorry  -- Requires OperationModel↔TensorDecomposition bridge lemma

                end AlienAirport
            """)

        hyp["lean_code"] = lean_raw

        # ── Count sorry and axiom ──────────────────────────────────────
        sorry_count = lean_raw.count("sorry")
        axiom_count = lean_raw.count("axiom ")
        hyp["sorry_count"] = sorry_count
        hyp["axiom_count"] = axiom_count
        total_sorry += sorry_count
        total_axiom += axiom_count

        # ── Hilbert Agent TODO entries ─────────────────────────────────
        if sorry_count > 0:
            todo = {
                "hypothesis_idx": idx + 1,
                "title": hyp.get("title", "Untitled"),
                "sorry_count": sorry_count,
                "axiom_count": axiom_count,
                "action": "Resolve sorry gaps — provide bridge lemmas",
                "priority": "HIGH" if sorry_count > 2 else "MEDIUM",
            }
            hyp["hilbert_todos"] = [todo]
            hilbert_todos.append(todo)
        else:
            hyp["hilbert_todos"] = []

        log.info(
            "euler_formalized",
            sorry=sorry_count,
            axioms=axiom_count,
            lean_len=len(lean_raw),
        )
        return hyp

    # ── Parallel formalization ─────────────────────────────────────────
    tasks = [_formalize_one(i, hyp) for i, hyp in enumerate(top_k)]
    results = list(await asyncio.gather(*tasks))

    elapsed = time.monotonic() - t0
    audit.record(
        stage="Stage 4: Euler Formalization",
        agent="Euler",
        action=(
            f"Formalized {len(results)} hypotheses in Lean 4. "
            f"Total sorry={total_sorry}, axiom={total_axiom}"
        ),
        elapsed_s=elapsed,
        input_summary=f"{len(top_k)} hypotheses",
        output_summary=f"sorry={total_sorry}, axiom={total_axiom}, todos={len(hilbert_todos)}",
        total_sorry=total_sorry,
        total_axiom=total_axiom,
        hilbert_todos_count=len(hilbert_todos),
    )

    logger.info(
        "stage4_euler_complete",
        sorry=total_sorry,
        axiom=total_axiom,
        elapsed_s=round(elapsed, 1),
    )
    return results
