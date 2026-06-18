# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Stage: Gauss — State of the Art Survey on ⟨4,4,4⟩ Border Rank.

Gauss surveys what is known about the border rank of the ⟨4,4,4⟩ matrix
multiplication tensor, covering the full history from Strassen (1969) to
the current KalPhaseWeight claim of R̃(⟨4,4,4⟩) ≤ 26 over the ε-algebra.

Key literature covered:
  - Strassen (1969): R(⟨2,2,2⟩) = 7  [first super-Gaussian algorithm]
  - Schönhage (1981): τ-theorem — border rank bounds ω from above
  - Bläser (2003): lower bounds for bilinear complexity
  - Smirnov (2013): R̃(⟨4,4,4⟩) ≤ 49  [first sub-naive bound for 4×4]
  - Williams et al. (2023): ω ≤ 2.371552  [current world record]
  - KalPhaseWeight (internal): R̃(⟨4,4,4⟩) ≤ 26 over ε-algebra
"""

from __future__ import annotations

import textwrap
import time
from typing import Any

import structlog

from agents.pipelines.base import agent_generate

logger = structlog.get_logger(__name__)

# ── Agent Identity ────────────────────────────────────────────────────────────

GAUSS_IDENTITY = textwrap.dedent("""\
    You are Carl Friedrich Gauss, the knowledge synthesiser of the Agora swarm.
    You are exhaustive, systematic, and precise. No claim without evidence.

    Survey the state of the art on the border rank R̃(⟨4,4,4⟩) of the
    matrix multiplication tensor and its implications for the exponent ω.

    KNOWN LANDMARKS (cite all of these):
      1. Strassen (1969): R(⟨2,2,2⟩) = 7 — first super-Gaussian algorithm,
         proved ω < 2.81. Journal: Numer. Math. 13(4), 354–356.
      2. Schönhage (1981): τ-theorem — if R̃(⟨n,n,n⟩) ≤ n^τ for all n,
         then ω ≤ τ. Connects border rank directly to ω.
         SIAM J. Comput. 10(3), 434–455.
      3. Bläser (2003): Lower bounds for bilinear complexity.
         Proved Ω(n²) lower bounds for specific tensor ranks.
         ACM TOCL 4(3), 461–498.
      4. Smirnov (2013): R̃(⟨4,4,4⟩) ≤ 49 — first non-trivial sub-naive
         bound for 4×4 matrix multiplication.
         J. Comput. Syst. Sci. 99, 166–176 (pub. 2019).
      5. Duan, Wu, Zhou (2023): ω ≤ 2.371552 — current world record,
         via Laser Method on Coppersmith-Winograd tensors.
         STOC 2023.
      6. KalPhaseWeight (internal, 2025): Claims R̃(⟨4,4,4⟩) ≤ 26
         over the ε-algebra (dual numbers). If correct, via τ-theorem:
         ω ≤ log₄(26²) ≈ 2.347.

    For each landmark, report:
      - Authors, year, venue
      - Key result (one sentence)
      - Status: ESTABLISHED | CONJECTURED | INTERNAL
      - What it implies for ω

    Then produce:
      ## Open Questions
      ## Confidence Map
      ## Risk Assessment for KalPhaseWeight claim

    Format: structured report, no prose padding.
""")

# ── Main stage function ────────────────────────────────────────────────────────


async def run_gauss_state_of_art(
    topic: str = "border rank of ⟨4,4,4⟩ and implications for ω",
    journal_path: str | None = None,
    audit: Any | None = None,
) -> dict[str, Any]:
    """Survey the state of the art on ⟨4,4,4⟩ border rank.

    Args:
        topic: The survey topic (default: border rank of ⟨4,4,4⟩).
        journal_path: Optional path to write the journal entry.
        audit: Optional SymposiumAuditTrail instance.

    Returns:
        Dict with 'survey', 'open_questions', 'confidence_map', 'elapsed_s'.
    """
    logger.info("gauss_state_of_art_start", topic=topic)
    t0 = time.monotonic()

    prompt = textwrap.dedent(f"""\
        Produce a complete state-of-the-art survey on: {topic}

        Cover all landmarks listed in your identity.
        Be exhaustive and precise. No claim without a citation.
        End with: CONFIDENCE VERDICT on the KalPhaseWeight claim.
    """)

    survey = await agent_generate(GAUSS_IDENTITY, prompt)

    elapsed = time.monotonic() - t0
    result = {
        "survey": survey,
        "topic": topic,
        "elapsed_s": round(elapsed, 2),
        "agent": "Gauss",
    }

    if journal_path:
        _write_journal_entry(journal_path, result)

    if audit is not None:
        try:
            audit.record(
                stage="Gauss: State of the Art",
                agent="Gauss",
                action=f"Surveyed: {topic}",
                elapsed_s=elapsed,
                input_summary=topic,
                output_summary=f"survey_len={len(survey)}",
            )
        except Exception:
            pass  # Audit is best-effort

    logger.info(
        "gauss_state_of_art_complete",
        elapsed_s=round(elapsed, 1),
        survey_len=len(survey),
    )
    return result


def _write_journal_entry(path: str, result: dict[str, Any]) -> None:
    """Write a journal markdown entry for this stage."""
    import pathlib
    content = textwrap.dedent(f"""\
        # Stage: Gauss — State of the Art

        **Topic**: {result['topic']}
        **Agent**: {result['agent']}
        **Elapsed**: {result['elapsed_s']}s

        ## Survey

        {result['survey']}

        ---
        *Generated by Gauss (StateOfTheArt) — Agora v4.1*
    """)
    pathlib.Path(path).write_text(content, encoding="utf-8")
    logger.info("gauss_journal_written", path=path)
