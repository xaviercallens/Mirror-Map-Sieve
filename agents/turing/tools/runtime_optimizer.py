# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Turing Runtime Optimizer Tool.

Generates mathematical and computational optimization directives for
SymBrain v5 and rusty-SUNDIALS solvers, allowing real-time, cost-effective
adaptation.
"""

from __future__ import annotations

from typing import Any
import structlog

logger = structlog.get_logger(__name__)


def optimize_runtime_parameters(
    bottleneck_diagnosis: dict[str, Any],
    budget_remaining_usd: float,
) -> dict[str, Any]:
    """Calculate optimized parameter configurations for SymBrain v5 and SUNDIALS.

    Dynamically tightens or relaxes search depths, tolerances, and model routing
    thresholds to maximize frugality and prevent timeouts.

    Args:
        bottleneck_diagnosis: Output from :meth:`profile_execution_trace`.
        budget_remaining_usd: Remaining experimental budget.

    Returns:
        A dictionary with optimized runtime parameters and explanations.
    """
    bottleneck = bottleneck_diagnosis.get("diagnosed_bottleneck", "balanced")
    scratch_eff = bottleneck_diagnosis.get("scratch_efficiency_ratio", 0.0)

    # Standard default configs
    opt_params = {
        "mcts_max_depth": 8,
        "mcts_exploration_c_ucb": 1.414,
        "dynamic_gating_threshold": 0.45,
        "early_stopping_ms": 500.0,
        "sundials_rtol": 1e-8,
        "sundials_atol": 1e-10,
        "quantization_tier": "BF16",
        "early_stopping_backtrack": True,
    }

    explanations: list[str] = []

    # 1. Budget-driven optimization (Austerity Mode)
    if budget_remaining_usd < 10.0:
        opt_params["mcts_max_depth"] = 2
        opt_params["dynamic_gating_threshold"] = 0.85  # Force routing to fast Edge-7B
        opt_params["early_stopping_ms"] = 150.0       # Tighten stopping bounds to 150ms
        opt_params["sundials_rtol"] = 1e-4
        opt_params["sundials_atol"] = 1e-5
        opt_params["quantization_tier"] = "INT4_AWQ"
        explanations.append("Severe budget constraints (<$10 remaining). Forced absolute austerity settings.")
    elif budget_remaining_usd < 50.0:
        opt_params["mcts_max_depth"] = 4
        opt_params["dynamic_gating_threshold"] = 0.60
        opt_params["early_stopping_ms"] = 300.0
        opt_params["sundials_rtol"] = 1e-6
        opt_params["sundials_atol"] = 1e-8
        opt_params["quantization_tier"] = "INT8_GPTQ"
        explanations.append("Moderate budget constraints (<$50 remaining). Relaxed tolerances and search depths.")

    # 2. Trace-driven optimizations
    if bottleneck == "solver-bound":
        # Relax stiff solver integration parameters to reduce evaluations
        opt_params["sundials_rtol"] = max(opt_params["sundials_rtol"], 1e-5)
        opt_params["sundials_atol"] = max(opt_params["sundials_atol"], 1e-6)
        explanations.append("Solver evaluations are high. Relaxed SUNDIALS integration tolerances to prevent solver freeze.")
    
    elif bottleneck == "compute-bound":
        # Dampen search depth and increase early stop backing
        opt_params["mcts_max_depth"] = min(opt_params["mcts_max_depth"], 4)
        opt_params["mcts_exploration_c_ucb"] = 1.0  # Favour exploitation to converge faster
        explanations.append("Search is compute-bound. Lowered MCTS max depth and narrowed exploration variance.")

    elif bottleneck == "memory-bound" or scratch_eff > 0.70:
        # Prune memory usage inside scratch bump-allocator
        opt_params["mcts_max_depth"] = min(opt_params["mcts_max_depth"], 3)
        explanations.append("Scratch arena is near memory limit. Capped MCTS depth to prevent memory overflow.")

    elif bottleneck == "network-bound":
        # Route away from remote models to reduce network latency
        opt_params["dynamic_gating_threshold"] = max(opt_params["dynamic_gating_threshold"], 0.75)
        explanations.append("High remote NIM latency detected. Adjusted gating to prefer local edge model routing.")

    result = {
        "optimized_parameters": opt_params,
        "rationale_explanations": explanations,
        "austerity_active": budget_remaining_usd < 10.0,
    }

    logger.info(
        "parameters_optimized",
        mcts_depth=opt_params["mcts_max_depth"],
        rtol=opt_params["sundials_rtol"],
        quantization=opt_params["quantization_tier"],
    )

    return result
