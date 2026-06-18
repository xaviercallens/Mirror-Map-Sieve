# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Mathlib Submission Pipeline — Preparing AlienMath Results for Mathlib4 PR.

This pipeline orchestrates the preparation of three key AlienMath results
for submission to the Mathlib4 library:

  1. IsMatMulExponent — The predicate "ω is the matrix multiplication exponent"
  2. IsSAW — The predicate for Self-Avoiding Walks
  3. TensorDecomp — Tensor rank decomposition infrastructure

Pipeline stages (4):
  Stage 1. Gauss     — Audit: what currently exists in Mathlib4 that overlaps?
  Stage 2. Newton    — Polish: generate Mathlib-style Lean 4 code
  Stage 3. TuringEdu — Explain: write the Mathlib PR description and docstrings
  Stage 4. Poincaré  — Review: does this meet Mathlib quality standards?

Journal: each stage writes stage_N_journal.md.
Final output: mathlib_submission_report.md with PR-ready artifacts.

Target Mathlib4 modules:
  - Mathlib.Algebra.TensorProduct.Rank
  - Mathlib.Analysis.SpecialFunctions.MatMulExponent
  - Mathlib.Combinatorics.SelfAvoidingWalks

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import pathlib
import textwrap
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog

from agents.pipelines.base import AgentPipeline, PipelineResult, PipelineStage, agent_generate
from agents.pipelines.stages.gauss_state_of_art import run_gauss_state_of_art
from agents.pipelines.stages.poincare_quorum import run_poincare_quorum

logger = structlog.get_logger(__name__)

# ── Identities ────────────────────────────────────────────────────────────────

_NEWTON_MATHLIB_IDENTITY = textwrap.dedent("""\
    You are Isaac Newton, the formal theorem demonstrator of the Agora swarm.
    You are writing Lean 4 code for submission to Mathlib4.

    Mathlib code quality standards:
      - Full docstrings with /-- ... -/ for every definition and theorem
      - Precise type signatures using Mathlib's existing type hierarchy
      - No sorry (Mathlib does not accept sorry in PRs)
      - Follow Mathlib naming conventions: camelCase for defs, snake_case for lemmas
      - Import only what is needed (no wildcard imports)
      - Add @[simp] attributes where appropriate
      - Proofs use `by` blocks with standard Mathlib tactics

    If a step genuinely requires a lemma not yet in Mathlib:
      - State it as a separate `lemma` with sorry and mark:
        -- [MATHLIB_MISSING] description — suggest which Mathlib module this belongs to

    Output raw Lean 4 code only. No markdown fences.
""")

_TURING_EDU_IDENTITY = textwrap.dedent("""\
    You are Alan Turing, the educator of the Agora swarm.
    Write documentation for a Mathlib4 Pull Request submission.

    The PR description must include:
      ## Summary
      (1-3 sentences: what is being added, why it matters)

      ## Main Definitions
      (list: name, type, informal description)

      ## Main Theorems
      (list: name, statement in English, relationship to existing Mathlib)

      ## Implementation Notes
      (design decisions, alternatives considered, performance)

      ## References
      (APA-style citations)

      ## Tags
      (Mathlib PR tags, e.g., `matrix`, `tensor`, `algebra`)

    Also write Lean 4 /-- module docstring --/ for the top of each file.
    Format: markdown for the PR description, Lean 4 for the docstring.
""")


@dataclass
class MathLibConfig:
    """Configuration for the Mathlib submission pipeline.

    Attributes:
        output_dir: Directory for stage artifacts.
        targets: Which items to prepare (IsMatMulExponent, IsSAW, TensorDecomp).
        lean_source_dir: Base directory for Lean 4 sources.
        model: Foundation model for all agent calls.
    """
    output_dir: str = "mathlib_submission_output"
    targets: list[str] = field(default_factory=lambda: [
        "IsMatMulExponent",
        "IsSAW",
        "TensorDecomp",
    ])
    lean_source_dir: str = (
        "/Users/xcallens/xdev/SocrateAI-Lean-Verification/Agora/AlienMath"
    )
    model: str = "gemini-2.5-pro"


class MathLibSubmissionPipeline(AgentPipeline):
    """4-stage pipeline for preparing AlienMath results for Mathlib4 PR."""

    def get_stages(self) -> list[PipelineStage]:
        return [
            PipelineStage.HYPOTHESIS_GENERATION,    # Stage 1: Gauss — audit
            PipelineStage.LEAN4_FORMALIZATION,       # Stage 2: Newton — polish
            PipelineStage.MONOGRAPH_GENERATION,      # Stage 3: TuringEdu — docs
            PipelineStage.PEER_REVIEW_LOOP,          # Stage 4: Poincaré — review
        ]

    async def run(self, config: Any = None) -> PipelineResult:
        """Execute the Mathlib submission preparation pipeline.

        Args:
            config: MathLibConfig instance (or None for defaults).

        Returns:
            PipelineResult with PR artifacts.
        """
        if config is None:
            config = MathLibConfig()
        if isinstance(config, dict):
            config = MathLibConfig(**config)

        symposium_id = f"mathlib_{uuid.uuid4().hex[:8]}"
        logger.info("mathlib_pipeline_start", symposium_id=symposium_id,
                    targets=config.targets)
        t0 = time.monotonic()

        output_dir = pathlib.Path(config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        journal_entries: list[str] = []
        stages_completed: list[PipelineStage] = []
        warnings: list[str] = []
        pr_artifacts: dict[str, str] = {}

        def jpath(n: int) -> str:
            return str(output_dir / f"stage_{n}_journal.md")

        # ── Stage 1: Gauss — Mathlib Audit ───────────────────────────────────
        logger.info("mathlib_stage1_gauss")
        gauss_result: dict[str, Any] = {}
        try:
            targets_str = ", ".join(config.targets)
            gauss_result = await run_gauss_state_of_art(
                topic=(
                    f"What does Mathlib4 currently have for: {targets_str}? "
                    "Survey: matrix multiplication complexity, self-avoiding walks, "
                    "tensor rank / decomposition in Mathlib4. "
                    "What is missing? What would a PR need to provide?"
                ),
                journal_path=jpath(1),
            )
            stages_completed.append(PipelineStage.HYPOTHESIS_GENERATION)
            journal_entries.append(
                f"## Stage 1 — Gauss (Mathlib Audit)\n\n"
                f"{gauss_result.get('survey', '')[:3000]}"
            )
            logger.info("mathlib_stage1_complete")
        except Exception as e:
            warnings.append(f"Stage 1 (Gauss) failed: {e}")

        # ── Stage 2: Newton — Mathlib-Quality Lean 4 Code ────────────────────
        logger.info("mathlib_stage2_newton")
        lean_artifacts: dict[str, str] = {}
        for target in config.targets:
            try:
                prompt = textwrap.dedent(f"""\
                    Mathlib audit context:
                    {gauss_result.get('survey', 'No audit available')[:2000]}

                    Write Mathlib4-quality Lean 4 code for: {target}

                    Requirements:
                    - Full docstrings for every definition and theorem
                    - No sorry (or mark [MATHLIB_MISSING] if unavoidable)
                    - Follow Mathlib4 naming conventions
                    - Use Mathlib.Data.Matrix.Basic and related imports
                    - Include @[simp] lemmas where appropriate
                    - The code must compile with Mathlib4 v4.14.0

                    For {target}:
                    {"- Define the predicate IsMatMulExponent : ℝ → Prop" if target == "IsMatMulExponent" else ""}
                    {"  (ω is the inf of exponents τ s.t. matrix mult can be done in O(n^τ) ops)" if target == "IsMatMulExponent" else ""}
                    {"- Define IsSAW : List (ℤ × ℤ) → Prop for self-avoiding walks on ℤ²" if target == "IsSAW" else ""}
                    {"  (a walk that does not revisit any vertex)" if target == "IsSAW" else ""}
                    {"- Define TensorRankDecomp : TensorRank ≤ r for explicit witness" if target == "TensorDecomp" else ""}
                    {"  (and prove basic properties: sub-multiplicativity, border rank ≤ rank)" if target == "TensorDecomp" else ""}
                """)
                code = await agent_generate(_NEWTON_MATHLIB_IDENTITY, prompt)
                lean_artifacts[target] = code
                sorry_count = code.count("sorry")
                journal_entries.append(
                    f"## Stage 2 — Newton (Lean 4 — {target})\n\n"
                    f"Sorry count: {sorry_count}\n\n"
                    f"```lean4\n{code[:2000]}\n```"
                )
                _write_file(
                    output_dir / f"{target}.lean",
                    code,
                    f"-- Mathlib4 submission: {target}\n"
                )
                logger.info("mathlib_stage2_target_done", target=target, sorry=sorry_count)
            except Exception as e:
                warnings.append(f"Stage 2 (Newton/{target}) failed: {e}")

        if lean_artifacts:
            stages_completed.append(PipelineStage.LEAN4_FORMALIZATION)

        # ── Stage 3: TuringEdu — PR Description and Docstrings ───────────────
        logger.info("mathlib_stage3_turing_edu")
        pr_description = ""
        try:
            lean_summary = "\n\n".join(
                f"=== {t} ===\n{code[:1500]}"
                for t, code in lean_artifacts.items()
            )
            prompt = textwrap.dedent(f"""\
                Mathlib4 PR content to document:
                {lean_summary[:5000]}

                Mathlib audit (what exists):
                {gauss_result.get('survey', '')[:2000]}

                Write:
                1. A complete Mathlib4 PR description (markdown format)
                2. A /-- module docstring --/ for each target file
                3. Reviewer guide: what to check, what proofs to spot-verify

                Targets: {', '.join(config.targets)}
            """)
            pr_description = await agent_generate(_TURING_EDU_IDENTITY, prompt)
            pr_artifacts["pr_description"] = pr_description
            stages_completed.append(PipelineStage.MONOGRAPH_GENERATION)
            journal_entries.append(
                f"## Stage 3 — TuringEdu (PR Description)\n\n{pr_description[:3000]}"
            )
            _write_file(
                output_dir / "PR_DESCRIPTION.md",
                pr_description,
                "",
            )
            logger.info("mathlib_stage3_complete", desc_len=len(pr_description))
        except Exception as e:
            warnings.append(f"Stage 3 (TuringEdu) failed: {e}")

        # ── Stage 4: Poincaré — Mathlib Quality Review ───────────────────────
        logger.info("mathlib_stage4_poincare")
        try:
            lean_evidence = "\n\n".join(
                f"{t}:\n{code[:1000]}" for t, code in lean_artifacts.items()
            )
            poincare_result = await run_poincare_quorum(
                claim=(
                    "The Lean 4 code for IsMatMulExponent, IsSAW, and TensorDecomp "
                    "meets Mathlib4 quality standards and is ready for PR submission."
                ),
                evidence=lean_evidence[:4000],
                context=(
                    "Mathlib4 PR review: checking code quality, naming conventions, "
                    "docstring completeness, and mathematical correctness."
                ),
                journal_path=jpath(4),
            )
            stages_completed.append(PipelineStage.PEER_REVIEW_LOOP)
            journal_entries.append(
                f"## Stage 4 — Poincaré (Quality Review)\n\n"
                f"Verdict: **{poincare_result.get('verdict', 'N/A')}** "
                f"(confidence: {poincare_result.get('confidence', 0):.0%})\n\n"
                f"Reasoning: {poincare_result.get('reasoning', '')[:2000]}\n\n"
                f"Conditions for acceptance:\n"
                + "\n".join(
                    f"- {c}" for c in poincare_result.get("conditions", [])
                )
            )
            logger.info(
                "mathlib_stage4_complete",
                verdict=poincare_result.get("verdict"),
                confidence=poincare_result.get("confidence"),
            )
        except Exception as e:
            warnings.append(f"Stage 4 (Poincaré) failed: {e}")
            poincare_result = {}

        # ── Final Report ──────────────────────────────────────────────────────
        duration = time.monotonic() - t0
        report_path = _write_mathlib_report(
            output_dir, symposium_id, journal_entries, stages_completed,
            warnings, duration, lean_artifacts, pr_description,
            poincare_result if "poincare_result" in dir() else {},
        )

        logger.info(
            "mathlib_pipeline_complete",
            symposium_id=symposium_id,
            stages=len(stages_completed),
            targets_done=len(lean_artifacts),
            duration_s=round(duration, 1),
        )

        vault_ids = list(lean_artifacts.keys())
        return PipelineResult(
            symposium_id=symposium_id,
            stages_completed=stages_completed,
            total_duration_s=duration,
            vault_artifact_ids=vault_ids,
            warnings=warnings,
            audit_trail_path=report_path,
        )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _write_file(path: pathlib.Path, content: str, header: str) -> None:
    """Write content to file with optional header."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + content, encoding="utf-8")
    logger.info("mathlib_file_written", path=str(path))


def _write_mathlib_report(
    output_dir: pathlib.Path,
    symposium_id: str,
    journal_entries: list[str],
    stages_completed: list[PipelineStage],
    warnings: list[str],
    duration_s: float,
    lean_artifacts: dict[str, str],
    pr_description: str,
    poincare_result: dict[str, Any],
) -> str:
    """Write the mathlib_submission_report.md."""
    from datetime import datetime, timezone
    report_path = output_dir / "mathlib_submission_report.md"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    warning_block = "\n".join(f"- {w}" for w in warnings) if warnings else "(none)"
    journal_block = "\n\n---\n\n".join(journal_entries)

    target_table = "\n".join(
        f"| {t} | {code.count('sorry')} | "
        f"{'✅ Ready' if code.count('sorry') == 0 else '🔄 Has sorry'} |"
        for t, code in lean_artifacts.items()
    )

    verdict = poincare_result.get("verdict", "N/A") if poincare_result else "N/A"
    confidence = poincare_result.get("confidence", 0.0) if poincare_result else 0.0

    content = textwrap.dedent(f"""\
        # Mathlib Submission Pipeline — Final Report

        **Symposium ID**: `{symposium_id}`
        **Stages completed**: {len(stages_completed)}/4
        **Duration**: {duration_s:.1f}s
        **Date**: {ts}

        ---

        ## PR Readiness Status

        | Target | Sorry Count | Status |
        |--------|-------------|--------|
        {target_table}

        **Quality Review Verdict**: {verdict} ({confidence:.0%} confidence)

        ---

        ## PR Description Preview

        {pr_description[:2000]}

        ---

        ## Learning Journal

        {journal_block}

        ---

        ## Warnings / Errors

        {warning_block}

        ---

        ## Next Steps

        1. Address any remaining sorry's (marked [MATHLIB_MISSING])
        2. Run `lake build` to verify compilation
        3. Submit PR to leanprover-community/mathlib4
        4. Respond to reviewer feedback (Poincaré conditions: {poincare_result.get('conditions', [])})
        5. Update CONTRIBUTING.md with PR link

        ---

        *Generated by Mathlib Submission Pipeline — Agora v4.1*
        *Patent: US-PAT-PEND-2026-0525*
    """)

    report_path.write_text(content, encoding="utf-8")
    logger.info("mathlib_report_written", path=str(report_path))
    return str(report_path)
