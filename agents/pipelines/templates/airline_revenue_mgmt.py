# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Symposium template — Airline Revenue Management.

Archived configuration for reproducible re-runs of the airline revenue
management symposium applying non-commutative demand algebra and tensor
pricing networks to dynamic fare optimisation.
"""

from __future__ import annotations

from pathlib import Path

from agents.pipelines.symposium import SymposiumConfig


def build_config() -> SymposiumConfig:
    """Build a frozen SymposiumConfig for Airline Revenue Management.

    Returns:
        Configuration targeting tensor-network pricing with IATA/DOT
        regulatory constraints and EMSR-b/DLP baselines.
    """
    return SymposiumConfig(
        field="Airline Revenue Management",
        research_question=(
            "Can tensor network decomposition and stochastic dynamic programming "
            "outperform classical EMSR-b and deterministic linear programming in "
            "multi-leg O&D revenue management under non-stationary demand, "
            "while satisfying IATA interline settlement and DOT consumer "
            "protection regulations? Confidence threshold: ≥12% yield "
            "improvement over EMSR-b benchmark (IATA RM Best Practice 2023)."
        ),
        formalisms=[
            "stochastic dynamic programming (Bellman equations, network RM)",
            "tensor decomposition for multi-leg O&D demand forecasting",
            "deep reinforcement learning (proximal policy optimization)",
            "Markov decision process with non-stationary transition kernels",
        ],
        constraints=[
            "IATA Resolution 787 (interline electronic ticketing)",
            "IATA Revenue Accounting Manual (RAM)",
            "US DOT 14 CFR Part 399 (fare advertising rules)",
            "EU Regulation 261/2004 (passenger compensation)",
            "ATPCO fare filing standards",
        ],
        comparison_baselines=[
            "Expected Marginal Seat Revenue (EMSR-b)",
            "Deterministic Linear Programming (DLP)",
            "Bid-price control (network RM)",
            "Q-learning dynamic pricing",
        ],
        target_pages=90,
        template_name="airline_revenue_mgmt",
        output_dir=Path("output/symposium/airline_revenue_mgmt"),
    )
