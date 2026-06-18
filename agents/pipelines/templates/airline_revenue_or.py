# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""OR Pipeline template — Airline Revenue Management (OR formulation).

Archived configuration for reproducible runs of the airline network RM
pipeline using approximate dynamic programming vs EMSR-b baselines.
"""

from __future__ import annotations

from pathlib import Path

from agents.pipelines.or_pipeline import ORPipelineConfig


def build_config() -> ORPipelineConfig:
    """Build a frozen ORPipelineConfig for Airline Revenue Management.

    Returns:
        Configuration targeting ADP with basis function approximation,
        validated on Talluri-vanRyzin benchmark scenarios, compared
        against EMSR-b, DLP, and bid-price control.
    """
    return ORPipelineConfig(
        problem_domain="revenue_management",
        research_question=(
            "Can approximate dynamic programming with basis function "
            "approximation outperform EMSR-b and DLP on multi-leg O&D "
            "network revenue management with 500+ legs and 10,000+ ODFs?"
        ),
        problem_class="MDP",
        benchmark_suite="Talluri-vanRyzin",
        baselines=["EMSR-b", "DLP", "bid_price_control"],
        target_pages=70,
        template_name="airline_revenue_or",
        output_dir=Path("output/or_pipeline/airline_revenue_or"),
    )
