# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Discovery template — H3: Callens-Schmidt Sequence.

H3 targets the Callens-Schmidt sequence S20(n) = Sum_{k=0..n} choose(n, k)^4 * choose(n+k, k).
Proves modular super-congruences, Calabi-Yau period diagonal representations, and compiles
its minimal order-5, degree-9 recurrence in the Lean 4 proof assistant kernel.
"""

from __future__ import annotations

from pathlib import Path

from agents.pipelines.discovery import DiscoveryConfig


def build_config() -> DiscoveryConfig:
    """Build DiscoveryConfig for H3: Callens-Schmidt Sequence."""
    return DiscoveryConfig(
        discovery_id="H3-CALLENS-SCHMIDT",
        target_domain=(
            "Callens-Schmidt sequence S_20(n) = Sum_{k=0..n} choose(n, k)^4 * choose(n+k, k). "
            "Verification of minimal order-5 degree-9 recurrence and Calabi-Yau period diagonal "
            "rational generators."
        ),
        num_conjectures=1,
        num_degennes_agents=2,
        enable_leanbert=True,
        enable_deepseek=True,
        model="gemini-2.5-pro",
        max_budget_usd=30.0,
        alexandrie_bucket="socrateai-alexandrie-vault",
        require_human_approval=True,
        output_dir=Path("output/discovery/h3_callens_schmidt"),
    )
