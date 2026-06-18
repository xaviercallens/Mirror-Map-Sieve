# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""GCP compute cost estimator with budget enforcement.

GPU pricing (us-central1, on-demand, per-GPU-hour):
  • NVIDIA L4        — $0.70/hr
  • NVIDIA A100 80GB — $3.67/hr
  • TPU v5e          — $1.20/hr

Hard limits:
  • $100 per experiment
  • $500 project total
  • ``min_replicas = 0`` (serverless — mandatory)

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# GPU Pricing (USD per GPU-hour, us-central1 on-demand)
# ---------------------------------------------------------------------------

GPU_RATES: dict[str, float] = {
    "L4": 0.70,
    "A100-40GB": 2.21,
    "A100-80GB": 3.67,
    "H100-80GB": 8.68,
    "T4": 0.35,
    "TPU-v5e": 1.20,
    "TPU-v5p": 4.20,
    "CPU": 0.03,
}

# Budget ceilings
EXPERIMENT_BUDGET: float = 100.0
PROJECT_BUDGET: float = 500.0

# Serverless policy
REQUIRED_MIN_REPLICAS: int = 0


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CostEstimate:
    """Cost estimation result.

    Attributes:
        gpu_type: Accelerator type.
        hourly_rate: Per-GPU-hour rate in USD.
        hours: Estimated wall-clock hours.
        replicas: Number of GPU replicas.
        total_cost: ``hourly_rate × hours × replicas``.
        within_experiment_budget: ``True`` if ≤ $100.
        within_project_budget: ``True`` if ≤ $500.
        min_replicas_compliant: ``True`` if ``min_replicas == 0``.
        recommendation: Human-readable advice.
    """

    gpu_type: str
    hourly_rate: float
    hours: float
    replicas: int
    total_cost: float
    within_experiment_budget: bool
    within_project_budget: bool
    min_replicas_compliant: bool
    recommendation: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def estimate_cost(
    gpu_type: str = "L4",
    hours: float = 1.0,
    replicas: int = 1,
    min_replicas: int = 0,
) -> dict[str, Any]:
    """Estimate GCP compute cost and enforce budget limits.

    Args:
        gpu_type: Accelerator type — one of :data:`GPU_RATES` keys.
        hours: Estimated wall-clock hours of GPU time.
        replicas: Number of concurrent GPU instances.
        min_replicas: Minimum replica count (must be ``0``).

    Returns:
        Dict with cost breakdown and compliance flags.

    Raises:
        ValueError: If ``gpu_type`` is unknown.

    Example::

        result = estimate_cost(gpu_type="L4", hours=2.0, replicas=1)
        assert result["within_experiment_budget"]
        assert result["min_replicas_compliant"]
    """
    logger.info(
        "cost_estimate_request",
        gpu_type=gpu_type,
        hours=hours,
        replicas=replicas,
        min_replicas=min_replicas,
    )

    # Validate GPU type
    if gpu_type not in GPU_RATES:
        raise ValueError(
            f"Unknown GPU type '{gpu_type}'. "
            f"Available: {sorted(GPU_RATES.keys())}"
        )

    hourly_rate = GPU_RATES[gpu_type]
    total = hourly_rate * hours * replicas

    within_exp = total <= EXPERIMENT_BUDGET
    within_proj = total <= PROJECT_BUDGET
    min_rep_ok = min_replicas == REQUIRED_MIN_REPLICAS

    # Build recommendation
    recommendations: list[str] = []

    if not within_exp:
        recommendations.append(
            f"⚠️ Exceeds $100 experiment budget by ${total - EXPERIMENT_BUDGET:.2f}. "
            f"Consider fewer hours or switching to a cheaper GPU."
        )

    if not within_proj:
        recommendations.append(
            f"⚠️ Exceeds $500 project budget by ${total - PROJECT_BUDGET:.2f}."
        )

    if not min_rep_ok:
        recommendations.append(
            f"🚫 min_replicas={min_replicas} violates serverless policy. "
            f"Set min_replicas=0 for cold-start savings."
        )

    if within_exp and within_proj and min_rep_ok:
        budget_pct = (total / EXPERIMENT_BUDGET) * 100
        recommendations.append(
            f"✅ Budget OK — ${total:.2f} is {budget_pct:.0f}% of "
            f"experiment limit."
        )

    # Suggest cheaper alternatives if over budget
    if not within_exp:
        cheaper = [
            (name, rate * hours * replicas)
            for name, rate in sorted(GPU_RATES.items(), key=lambda x: x[1])
            if rate * hours * replicas <= EXPERIMENT_BUDGET
        ]
        if cheaper:
            alt_name, alt_cost = cheaper[0]
            recommendations.append(
                f"💡 Alternative: {alt_name} at ${alt_cost:.2f} "
                f"(${GPU_RATES[alt_name]:.2f}/hr)"
            )

    recommendation = " | ".join(recommendations)

    estimate = CostEstimate(
        gpu_type=gpu_type,
        hourly_rate=hourly_rate,
        hours=hours,
        replicas=replicas,
        total_cost=round(total, 2),
        within_experiment_budget=within_exp,
        within_project_budget=within_proj,
        min_replicas_compliant=min_rep_ok,
        recommendation=recommendation,
    )

    logger.info(
        "cost_estimate_result",
        total=estimate.total_cost,
        ok=within_exp and within_proj and min_rep_ok,
    )

    return {
        "gpu_type": estimate.gpu_type,
        "hourly_rate": estimate.hourly_rate,
        "hours": estimate.hours,
        "replicas": estimate.replicas,
        "total_cost": estimate.total_cost,
        "within_experiment_budget": estimate.within_experiment_budget,
        "within_project_budget": estimate.within_project_budget,
        "min_replicas_compliant": estimate.min_replicas_compliant,
        "recommendation": estimate.recommendation,
    }
