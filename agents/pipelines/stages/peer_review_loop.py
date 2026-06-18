# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Stage 9 — Peer Review Loop: Iterative LaTeX Refinement.

Runs ``config.review_loops`` (default 5) iterative review-revise cycles.
Each loop:
  1. A reviewer agent analyses the LaTeX using Lean 4 kernel results,
     Galileo numerical results, and Euler/Pythagore verdicts.
  2. Identifies issues (mathematical errors, inconsistencies, missing refs).
  3. Hypatia revises the flagged sections in-place.

Returns the improved LaTeX document.
"""

from __future__ import annotations

import re
import textwrap
import time

import structlog

from agents.pipelines.audit import SymposiumAuditTrail
from agents.pipelines.base import agent_generate
from agents.pipelines.config import SymposiumConfig

logger = structlog.get_logger(__name__)

# ── Agent Identities ───────────────────────────────────────────────────────────

REVIEWER_IDENTITY = textwrap.dedent("""\
    You are a senior scientific peer reviewer auditing a LaTeX monograph
    on {domain} optimization using Alien Mathematics.

    You have access to the following verification data:
    - Lean 4 kernel compilation results for each hypothesis
    - Galileo numerical simulation statistics
    - Euler formalization and Pythagore verification reports

    Identify SPECIFIC issues in the document:
    1. Mathematical errors or inconsistencies
    2. Claims not supported by the Lean 4 or simulation data
    3. Missing or incorrect references
    4. Logical gaps in theoretical derivations
    5. Statistical claims that contradict the simulation results

    For each issue, specify:
    - SECTION: the LaTeX section/subsection containing the issue
    - ISSUE: precise description of the problem
    - SEVERITY: HIGH / MEDIUM / LOW
    - FIX: specific correction to apply

    Output as a numbered list of issues. If no issues remain, output
    "NO_ISSUES_FOUND".
""")

HYPATIA_REVISE_IDENTITY = textwrap.dedent(r"""
    You are Hypatia, scientific author. You are revising a LaTeX monograph
    based on peer review feedback.

    Apply the specified corrections to the relevant sections.
    Output the COMPLETE revised LaTeX document — do not abbreviate or
    truncate any sections. Preserve all existing content that was not
    flagged for revision.
""").strip()


async def peer_review_loop(
    config: SymposiumConfig,
    latex_doc: str,
    top_k: list[dict],
    audit: SymposiumAuditTrail,
) -> str:
    """Iteratively review and revise the LaTeX monograph.

    Runs ``config.review_loops`` cycles of review → revise.  Each cycle
    uses verification data from all pipeline stages to ground the review.

    Args:
        config: Symposium configuration.
        latex_doc: LaTeX document from Stage 8.
        top_k: Top-K hypotheses (for verification data context).
        audit: Audit trail.

    Returns:
        Improved LaTeX document string.
    """
    n_loops = config.review_loops
    logger.info("stage9_peer_review_start", loops=n_loops)
    t0 = time.monotonic()

    # ── Build verification context ─────────────────────────────────────
    verification_context_parts: list[str] = []
    for idx, hyp in enumerate(top_k):
        kernel = hyp.get("lean_kernel_result", {})
        stats = hyp.get("numerical_stats", {})
        verification_context_parts.append(
            f"Hypothesis {idx + 1}: {hyp.get('title', 'Untitled')}\n"
            f"  Lean 4 Verdict: {kernel.get('kernel_verdict', 'N/A')}\n"
            f"  Sorry Count: {kernel.get('sorry_count', '?')}\n"
            f"  Axiom Count: {kernel.get('axiom_count', '?')}\n"
            f"  Simulation Improvement: {stats.get('improvement_pct', '?')}%\n"
            f"  Baseline Mean: {stats.get('baseline_mean', '?')}\n"
            f"  Alien Mean: {stats.get('alien_mean', '?')}\n"
        )
    verification_context = "\n".join(verification_context_parts)

    current_doc = latex_doc
    total_issues_fixed = 0

    for loop_num in range(1, n_loops + 1):
        log = logger.bind(loop=loop_num, total_loops=n_loops)
        log.info("peer_review_loop_start")

        # ── Step 1: Review ─────────────────────────────────────────────
        review_identity = REVIEWER_IDENTITY.format(domain=config.domain)
        # Send a manageable excerpt (first 8000 chars + last 4000 chars)
        doc_excerpt = current_doc[:8000]
        if len(current_doc) > 12000:
            doc_excerpt += "\n[... MIDDLE SECTIONS OMITTED FOR REVIEW ...]\n"
            doc_excerpt += current_doc[-4000:]

        review_prompt = textwrap.dedent(f"""\
            Review the following LaTeX monograph excerpt.

            VERIFICATION DATA:
            {verification_context}

            DOCUMENT (excerpt):
            {doc_excerpt}

            Identify all issues. If none remain, output "NO_ISSUES_FOUND".
        """)

        review_result = await agent_generate(review_identity, review_prompt)

        # ── Check for convergence ──────────────────────────────────────
        if "NO_ISSUES_FOUND" in review_result:
            log.info("peer_review_converged", loop=loop_num)
            break

        # Count issues found
        issue_count = len(re.findall(r"(?:ISSUE|SECTION|SEVERITY):", review_result))
        if issue_count == 0:
            issue_count = len(re.findall(r"\d+\.", review_result))

        log.info("peer_review_issues_found", count=issue_count)

        # ── Step 2: Revise ─────────────────────────────────────────────
        revise_prompt = textwrap.dedent(f"""\
            PEER REVIEW FEEDBACK (Loop {loop_num}/{n_loops}):
            {review_result[:3000]}

            CURRENT DOCUMENT:
            {current_doc}

            Apply all corrections. Output the COMPLETE revised document.
        """)

        revised = await agent_generate(HYPATIA_REVISE_IDENTITY, revise_prompt)

        # ── Validate revision ──────────────────────────────────────────
        if "[MOCK_FALLBACK" not in revised and len(revised) > len(current_doc) * 0.5:
            # Clean markdown fences if present
            revised = revised.replace("```latex", "").replace("```", "")
            current_doc = revised
            total_issues_fixed += issue_count
            log.info("peer_review_revision_applied", issues_fixed=issue_count)
        else:
            log.warning(
                "peer_review_revision_skipped",
                reason="revision too short or mock fallback",
            )

        audit.record(
            stage=f"Stage 9: Peer Review Loop {loop_num}/{n_loops}",
            agent="Reviewer + Hypatia",
            action=f"Loop {loop_num}: {issue_count} issues identified and addressed",
            elapsed_s=time.monotonic() - t0,
            input_summary=f"doc_len={len(current_doc)}",
            output_summary=f"issues={issue_count}",
        )

    elapsed = time.monotonic() - t0
    audit.record(
        stage="Stage 9: Peer Review Loop (Summary)",
        agent="Reviewer + Hypatia",
        action=f"Completed {n_loops} review loops, {total_issues_fixed} total issues fixed",
        elapsed_s=elapsed,
        input_summary=f"initial_doc_len={len(latex_doc)}",
        output_summary=f"final_doc_len={len(current_doc)}, issues_fixed={total_issues_fixed}",
        total_issues_fixed=total_issues_fixed,
    )

    logger.info(
        "stage9_peer_review_complete",
        loops=n_loops,
        issues_fixed=total_issues_fixed,
        elapsed_s=round(elapsed, 1),
    )
    return current_doc
