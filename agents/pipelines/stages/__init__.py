# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Agora Symposium pipeline stages — re-exports all 12 stage functions (V2+).

Usage::

    from agents.pipelines.stages import (
        generate_scientific_rules,  # Stage 1
        generate_hypotheses,        # Stage 2
        adversarial_review,         # Stage 3
        formalize_lean4,            # Stage 4
        compile_kernels,            # Stage 5
        run_simulations,            # Stage 6
        assess_impact,              # Stage 7
        generate_monograph,         # Stage 8
        peer_review_loop,           # Stage 9
        publish,                    # Stage 10
        run_eiffel_quorum,          # Stage 11
    )
"""

from agents.pipelines.stages.socrate_rules import generate_scientific_rules
from agents.pipelines.stages.hypothesis_swarm import generate_hypotheses
from agents.pipelines.stages.adversarial_review import adversarial_review
from agents.pipelines.stages.euler_formalization import formalize_lean4
from agents.pipelines.stages.pythagore_kernel import compile_kernels
from agents.pipelines.stages.galileo_simulation import run_simulations
from agents.pipelines.stages.impact_assessment import assess_impact
from agents.pipelines.stages.hypatia_monograph import generate_monograph
from agents.pipelines.stages.peer_review_loop import peer_review_loop
from agents.pipelines.stages.publication import publish
from agents.pipelines.stages.eiffel_conclusion import run_eiffel_quorum

__all__ = [
    "generate_scientific_rules",
    "generate_hypotheses",
    "adversarial_review",
    "formalize_lean4",
    "compile_kernels",
    "run_simulations",
    "assess_impact",
    "generate_monograph",
    "peer_review_loop",
    "publish",
    "run_eiffel_quorum",
]
