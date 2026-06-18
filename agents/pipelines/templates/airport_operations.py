# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Symposium template — Airport Operations Optimization.

Archived configuration for reproducible re-runs of the airport operations
symposium applying tensor networks, holographic entropy, and ω-limit sets
to airport flow optimisation under ICAO/ECAC regulatory frameworks.
"""

from __future__ import annotations

from pathlib import Path

from agents.pipelines.symposium import SymposiumConfig


def build_config() -> SymposiumConfig:
    """Build a frozen SymposiumConfig for Airport Operations Optimization.

    Returns:
        Configuration targeting tensor-network airport flow models with
        ICAO/ECAC constraints and M/G/k queueing baselines.
    """
    return SymposiumConfig(
        field="Airport Operations Optimization",
        research_question=(
            "Can tensor network decomposition and stochastic queueing theory "
            "improve airport passenger flow, gate assignment, and ground "
            "handling efficiency beyond classical M/G/k queueing and integer "
            "programming, while satisfying ICAO Doc 9854 and ECAC Doc 30 "
            "standards? Confidence threshold: ≥10% improvement in on-time "
            "performance (OTP) over EUROCONTROL CODA 2023 baseline."
        ),
        formalisms=[
            "M/G/k and G/G/1 queueing networks (Kleinrock 1975)",
            "tensor network decomposition for passenger flow (Oseledets 2011)",
            "integer programming for gate assignment (Bihr 1990)",
            "stochastic programming under demand uncertainty (Birge & Louveaux 2011)",
        ],
        constraints=[
            "ICAO Doc 9854 — Global ATM Operational Concept",
            "ECAC Doc 30 Part I — Air Traffic Management",
            "IATA Airport Handling Manual (AHM)",
            "EUROCONTROL CODA delay reporting standards",
            "EASA aerodrome certification requirements",
        ],
        comparison_baselines=[
            "M/G/k queueing models",
            "integer programming (gate assignment)",
            "discrete-event simulation (SIMMOD, CAST)",
            "stochastic optimization (SAA)",
        ],
        target_pages=80,
        template_name="airport_operations",
        output_dir=Path("output/symposium/airport_operations"),
    )
