# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""L2 residual convergence checker for PDE solvers.

Validates that physics-informed neural network (PINN) solutions have
achieved adequate convergence by checking:
  - L2 norm of PDE residual ≤ threshold
  - Continuity equation residual (mass conservation)
  - Residual decay rate (stagnation detection)

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import math
from typing import Any, Sequence

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_THRESHOLD = 1e-4
CONTINUITY_THRESHOLD = 1e-5
STAGNATION_WINDOW = 100
STAGNATION_MIN_IMPROVEMENT = 0.01  # 1% improvement required


def check_convergence(
    residual: float,
    threshold: float = DEFAULT_THRESHOLD,
    continuity_residual: float | None = None,
    residual_history: Sequence[float] | None = None,
) -> dict[str, Any]:
    """Check whether a PDE solver has converged.

    Evaluates three criteria:
      1. **Residual threshold** — L2 residual ≤ threshold
      2. **Mass conservation** — continuity residual ≤ 1e-5
      3. **Stagnation** — residual is still decreasing

    Args:
        residual: Current L2 norm of the PDE residual.
        threshold: Convergence threshold.
        continuity_residual: L2 norm of the continuity equation (∇·u = 0).
        residual_history: Time series of residual values for stagnation check.

    Returns:
        Dict with ``converged``, ``checks``, ``recommendation``.

    Example::

        result = check_convergence(residual=5e-5, threshold=1e-4)
        assert result["converged"]

        result = check_convergence(residual=1e-2, threshold=1e-4)
        assert not result["converged"]
    """
    checks: dict[str, dict[str, Any]] = {}

    # 1. Residual threshold
    residual_ok = residual <= threshold
    checks["residual"] = {
        "value": residual,
        "threshold": threshold,
        "passed": residual_ok,
        "message": (
            f"L2 residual: {residual:.2e} "
            f"{'≤' if residual_ok else '>'} {threshold:.2e}"
        ),
    }

    # 2. Continuity (mass conservation)
    continuity_ok = True
    if continuity_residual is not None:
        continuity_ok = continuity_residual <= CONTINUITY_THRESHOLD
        checks["continuity"] = {
            "value": continuity_residual,
            "threshold": CONTINUITY_THRESHOLD,
            "passed": continuity_ok,
            "message": (
                f"Continuity: {continuity_residual:.2e} "
                f"{'≤' if continuity_ok else '>'} {CONTINUITY_THRESHOLD:.2e}"
            ),
        }

    # 3. Stagnation detection
    stagnation_ok = True
    if residual_history and len(residual_history) >= STAGNATION_WINDOW:
        recent = residual_history[-STAGNATION_WINDOW:]
        older = residual_history[-2 * STAGNATION_WINDOW:-STAGNATION_WINDOW]
        if older:
            old_mean = sum(older) / len(older)
            new_mean = sum(recent) / len(recent)
            if old_mean > 0:
                improvement = (old_mean - new_mean) / old_mean
                stagnation_ok = improvement >= STAGNATION_MIN_IMPROVEMENT
                checks["stagnation"] = {
                    "improvement": round(improvement, 4),
                    "threshold": STAGNATION_MIN_IMPROVEMENT,
                    "passed": stagnation_ok,
                    "message": (
                        f"Residual improvement: {improvement:.2%} "
                        f"{'≥' if stagnation_ok else '<'} "
                        f"{STAGNATION_MIN_IMPROVEMENT:.2%}"
                    ),
                }

    # Overall
    converged = residual_ok and continuity_ok
    all_passed = converged and stagnation_ok

    # Recommendation
    recommendations: list[str] = []
    if not residual_ok:
        orders_away = math.log10(residual / threshold) if residual > 0 else 0
        recommendations.append(
            f"Residual is {orders_away:.1f} orders above threshold. "
            f"Consider increasing training iterations or learning rate."
        )
    if not continuity_ok:
        recommendations.append(
            "Mass conservation violated. Increase continuity loss weight "
            "or refine the mesh near high-gradient regions."
        )
    if not stagnation_ok:
        recommendations.append(
            "Training has stagnated. Try learning rate scheduling, "
            "curriculum training, or increasing network capacity."
        )
    if all_passed:
        recommendations.append("All convergence criteria satisfied ✓")

    logger.info(
        "convergence_check",
        converged=converged,
        residual=residual,
        num_checks=len(checks),
    )

    return {
        "converged": converged,
        "all_checks_passed": all_passed,
        "checks": checks,
        "recommendation": " | ".join(recommendations),
    }
