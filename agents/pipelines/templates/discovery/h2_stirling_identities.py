# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Discovery template — H2: Stirling Number (Second Kind) Identities.

H2 is the validation and proof benchmark targeting the Stirling Number (Second Kind)
recurrences and weighted binomial sum decompositions. 

These identities are mathematically classical but represent a major benchmark
for automated theorem proving due to the complexity of index shifting, finite
summations over Ico/range, and coercions between Nat and Int in Lean 4.

Target Lean 4 theorems (expected output of Stage 5):
  - theorem stirlingS2_vertical_recurrence
  - theorem stirlingS2_horizontal_recurrence
  - theorem stirlingS2_explicit_formula
  - theorem weighted_binomial_sum_stirling_decomposition

Expected pipeline outcome:
  - Stage 1 (Darwin)    : surveys Mathlib for Stirling numbers definition.
  - Stage 2 (DeGennes)  : proposes horizontal and vertical recurrences.
  - Stage 3 (Newton)    : autoformalizes to Lean 4.
  - Stage 4 (Hilbert)   : proves theorems using a combination of induction, 
                          Finset.sum extraction, and the aesop tactic engine.
  - Stage 5 (kernel)    : kernel verification via `lake build`.
  - Stage 6 (Hypatia)   : monograph generation and open-room archiving.
"""

from __future__ import annotations

from pathlib import Path

from agents.pipelines.discovery import DiscoveryConfig


def build_config() -> DiscoveryConfig:
    """Build DiscoveryConfig for H2: Stirling Number (Second Kind) Identities.

    Configured for rigorous mathlib-compatible verification:
    - 4 targets corresponding to the vertical, horizontal, explicit, and decomposition properties.
    - Enable advanced tactic engines (deep-think and solver helpers) to handle the complex index shifts.
    - Budget cap of $25.
    """
    return DiscoveryConfig(
        # ── Identity ──────────────────────────────────────────────────────
        discovery_id="H2-STIRLING-IDENTITIES",

        # ── Target domain ─────────────────────────────────────────────────
        target_domain=(
            "Stirling Numbers of the Second Kind S(n,k). Proving vertical and "
            "horizontal recurrences, the explicit alternating sum formula via "
            "inclusion-exclusion, and the weighted binomial sum decomposition "
            "using falling factorials. Requires handling of Finset.sum_Ico, "
            "Nat.choose, and Nat.descFactorial under Nat/Int coercions."
        ),

        # ── Configuration parameters ──────────────────────────────────────
        num_conjectures=4,
        num_degennes_agents=2,

        # ── Proof cascade: Enable proof engines for complex proofs ────────
        enable_leanbert=True,
        enable_deepseek=True,

        # ── Model configuration ───────────────────────────────────────────
        model="gemini-2.5-pro",

        # ── Budget cap ────────────────────────────────────────────────────
        max_budget_usd=25.0,

        # ── Alexandrie GCS storage ────────────────────────────────────────
        alexandrie_bucket="socrateai-alexandrie-vault",

        # ── Human-in-the-loop: True for production promotion ─────────────
        require_human_approval=True,

        # ── Output ────────────────────────────────────────────────────────
        output_dir=Path("output/discovery/h2_stirling_identities"),
    )
