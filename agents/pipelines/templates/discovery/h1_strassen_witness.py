# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Discovery template — H1: Strassen ⟨2,2,2⟩ Witness.

H1 is the VALIDATION hypothesis for the Discovery Pipeline.
It is chosen deliberately because:

  1. The answer is KNOWN: R(⟨2,2,2⟩) = 7 (Strassen 1969).
  2. It is already formalized in Mathlib4 via DecideBorderRank.
  3. The Lean 4 proof uses `decide` — fully deterministic, no LLM needed.

This means we can verify the ENTIRE pipeline end-to-end (all 6 stages)
with a known-correct expected output, before running harder open problems.
If H1 fails, it's a pipeline bug, not a mathematical difficulty.

Target Lean 4 theorem (expected output of Stage 5):
  theorem strassen_witness : MatrixMultiplication.rank 2 2 2 = 7 := by decide

Expected pipeline outcome:
  - Stage 1 (Darwin)    : finds Strassen 1969, Mathlib DecideBorderRank
  - Stage 2 (DeGennes)  : generates ≥1 conjecture near this target
  - Stage 3 (Newton)    : autoformalize to Lean 4 with sorry
  - Stage 4 (Hilbert)   : `decide` tactic completes the proof (deterministic)
  - Stage 5 (kernel)    : `lake build` exits 0, zero sorry — VERIFIED ✅
  - Stage 6 (Hypatia)   : stores in OPEN room (sorry-free, kernel-verified)
"""

from __future__ import annotations

from pathlib import Path

from agents.pipelines.discovery import DiscoveryConfig


def build_config() -> DiscoveryConfig:
    """Build DiscoveryConfig for H1: Strassen ⟨2,2,2⟩ witness validation.

    Tuned for SPEED and DEBUGGABILITY:
    - 3 conjectures only (fast, predictable)
    - 1 DeGennes agent (no parallelism overhead)
    - LeanBert / DeepSeek disabled (validate deterministic path first)
    - $10 budget cap (far below $30 — this should cost < $1 in practice)
    - human_approval = False (fully automated for CI)

    Returns:
        Minimal DiscoveryConfig targeting matrix multiplication rank.
    """
    return DiscoveryConfig(
        # ── Identity ──────────────────────────────────────────────────────
        discovery_id="H1-STRASSEN-VALIDATION",

        # ── Target domain ─────────────────────────────────────────────────
        # The domain description feeds Darwin's literature scan (Stage 1)
        # and seeds DeGennes' experimental lenses (Stage 2).
        target_domain=(
            "Matrix multiplication tensor rank: specifically R(⟨2,2,2⟩) = 7 "
            "(Strassen 1969). The question: can the Lean 4 kernel independently "
            "verify the Strassen 7-multiplication witness via `decide` or "
            "explicit decomposition proof?"
        ),

        # ── Validation scale: minimal for fast feedback ───────────────────
        # 3 conjectures × 1 agent = 3 total. Enough to exercise the swarm
        # machinery without wasting tokens.
        num_conjectures=3,
        num_degennes_agents=1,

        # ── Proof cascade: deterministic only (validate pipeline first) ───
        # H1 should close with `decide` or `native_decide` — pure Lean 4.
        # LeanBert / DeepSeek disabled for this validation run.
        enable_leanbert=False,  # Re-enable for H2+ (harder problems)
        enable_deepseek=False,  # Re-enable for H2+ (harder problems)

        # ── Model: gemini-2.5-pro with deep think ─────────────────────────
        # Used only for Darwin (horizon scan) and Newton (autoformalization).
        # Stages 4 & 5 are purely deterministic.
        model="gemini-2.5-pro",

        # ── Budget: tight cap for validation ─────────────────────────────
        max_budget_usd=10.0,

        # ── Alexandrie: use the production vault ──────────────────────────
        alexandrie_bucket="socrateai-alexandrie-vault",

        # ── Human gate: disabled for CI / automated validation ────────────
        require_human_approval=False,

        # ── Output ────────────────────────────────────────────────────────
        output_dir=Path("output/discovery/h1_strassen_witness"),
    )
