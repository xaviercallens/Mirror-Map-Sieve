# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Turing Model Profiler Tool.

Provides tools to analyze raw telemetry traces from the Agora, including
latencies, MCTS nodes visited, SUNDIALS solver evaluations, and bump-allocated
scratch zone memory usage to diagnose compute bottlenecks.
"""

from __future__ import annotations

from typing import Any
import structlog

logger = structlog.get_logger(__name__)


def profile_execution_trace(telemetry_data: dict[str, Any]) -> dict[str, Any]:
    """Analyze a computational execution trace to diagnose performance bottlenecks.

    Inspects MCTS tree growth, solver step frequency, memory allocations,
    and wall-clock latencies.

    Args:
        telemetry_data: Dictionary containing trace metrics:
            - mcts_nodes (int): Number of nodes expanded during search.
            - solver_evals (int): Number of SUNDIALS function evaluations.
            - latency_ms (float): Total elapsed time in milliseconds.
            - token_count (int): Number of generated tokens.
            - scratch_allocated_bytes (int): Dynamic memory bump allocations.

    Returns:
        A dictionary with bottleneck diagnosis, efficiency metrics, and alerts.
    """
    mcts_nodes = int(telemetry_data.get("mcts_nodes", 0))
    solver_evals = int(telemetry_data.get("solver_evals", 0))
    latency_ms = float(telemetry_data.get("latency_ms", 0.0))
    token_count = int(telemetry_data.get("token_count", 0))
    scratch_allocated = int(telemetry_data.get("scratch_allocated_bytes", 0))

    # Constants mapping to 8GB Arena
    SCRATCH_ZONE_CAPACITY = 2 * 1024 * 1024 * 1024  # 2 GB

    # Compute derived metrics
    scratch_efficiency = (scratch_allocated / SCRATCH_ZONE_CAPACITY) if scratch_allocated > 0 else 0.0
    tokens_per_sec = (token_count / (latency_ms / 1000.0)) if (latency_ms > 0 and token_count > 0) else 0.0
    evals_per_sec = (solver_evals / (latency_ms / 1000.0)) if (latency_ms > 0 and solver_evals > 0) else 0.0

    # Bottleneck classification
    bottleneck = "balanced"
    warnings: list[str] = []

    if latency_ms > 500.0:  # Speculative stopping ceiling
        warnings.append("Speculative early stopping threshold (500ms) exceeded or approached.")

    # Memory check (Scratch zone near-exhaustion)
    if scratch_efficiency > 0.85:
        bottleneck = "memory-bound"
        warnings.append(f"Arena scratch zone memory usage is critical ({scratch_efficiency * 100:.1f}%).")
    # Stiff solver evaluations check
    elif solver_evals > 1000:
        bottleneck = "solver-bound"
        warnings.append("High rusty-SUNDIALS evaluations trace. Stiff kinetics ODE system detected.")
    # Parallel MCTS search depth check
    elif mcts_nodes > 2000:
        bottleneck = "compute-bound"
        warnings.append(f"Deep MCTS parallel search active ({mcts_nodes} nodes expanded).")
    # IO / Network bounds check
    elif latency_ms > 2000.0 and token_count < 50:
        bottleneck = "network-bound"
        warnings.append("High latency with low token output indicates high remote NIM API or GCS mount latency.")

    result = {
        "diagnosed_bottleneck": bottleneck,
        "scratch_efficiency_ratio": round(scratch_efficiency, 4),
        "throughput": {
            "tokens_per_second": round(tokens_per_sec, 2),
            "solver_evals_per_second": round(evals_per_sec, 2),
        },
        "warnings": warnings,
        "telemetry_summary": {
            "mcts_nodes": mcts_nodes,
            "solver_evals": solver_evals,
            "latency_ms": round(latency_ms, 2),
            "token_count": token_count,
            "scratch_allocated_bytes": scratch_allocated,
        }
    }

    logger.info(
        "trace_profiled",
        bottleneck=bottleneck,
        scratch_efficiency=f"{scratch_efficiency * 100:.2f}%",
        warnings_count=len(warnings),
    )

    return result
