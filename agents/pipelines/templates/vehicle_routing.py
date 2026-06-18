# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""OR Pipeline template — Vehicle Routing Problem.

Archived configuration for reproducible runs of the VRP optimization
pipeline using column generation with ML-guided branching against
Solomon and Gehring-Homberger benchmarks.
"""

from __future__ import annotations

from pathlib import Path

from agents.pipelines.or_pipeline import ORPipelineConfig


def build_config() -> ORPipelineConfig:
    """Build a frozen ORPipelineConfig for the Vehicle Routing Problem.

    Returns:
        Configuration targeting column generation with ML branching,
        validated on Solomon VRPTW and Gehring-Homberger benchmarks,
        compared against LKH-3, OR-Tools routing, and Clarke-Wright.
    """
    return ORPipelineConfig(
        problem_domain="vehicle_routing",
        research_question=(
            "Can column generation with machine-learning-guided branching "
            "solve large-scale heterogeneous VRP instances to within 2% "
            "optimality gap, outperforming LKH-3 and Google OR-Tools on "
            "Solomon and Gehring-Homberger benchmarks?"
        ),
        problem_class="MIP",
        benchmark_suite="Solomon_VRPTW",
        baselines=["LKH-3", "OR-Tools_routing", "Clarke-Wright"],
        target_pages=60,
        template_name="vehicle_routing",
        output_dir=Path("output/or_pipeline/vehicle_routing"),
    )
