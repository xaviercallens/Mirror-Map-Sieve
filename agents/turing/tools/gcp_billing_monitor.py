# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Turing GCP Billing Monitor Tool.

Monitors active and simulated GCP billing metrics, asserts serverless scale-to-zero
governance (min_replicas=0), and computes optimal GPU tier mappings.
"""

from __future__ import annotations

import math
from typing import Any
import structlog

logger = structlog.get_logger(__name__)


def monitor_gcp_billing_efficiency(
    execution_history: list[dict[str, Any]],
) -> dict[str, Any]:
    """Audit GCP billing history to verify cost efficiency policies.

    Enforces serverless zero-replicas restrictions and recommends compute models.

    Args:
        execution_history: A list of runtime invocation dictionaries containing:
            - service_name (str): Cloud Run service or function.
            - gpu_type (str): L4, A100, TPU-v5e, or None (CPU).
            - min_replicas (int): Configured minimum replica floor.
            - duration_seconds (float): Execution wall-time.
            - replicas_active (int): Current active count.

    Returns:
        A dictionary with policy compliance verdicts, cost metrics, and optimization proposals.
    """
    total_cost_usd = 0.0
    non_compliant_services: list[str] = []
    compliance_verdict = "COMPLIANT"
    
    # GCP pricing tables (cost per hour)
    RATES = {
        "A100": 3.67,
        "L4": 0.70,
        "TPU-V5E": 1.20,
        "CPU": 0.08,  # Cloud Run standard CPU allocation
    }

    for idx, exec_entry in enumerate(execution_history):
        service = exec_entry.get("service_name", f"service_{idx}")
        gpu = str(exec_entry.get("gpu_type", "None")).upper()
        min_reps = int(exec_entry.get("min_replicas", 0))
        duration = float(exec_entry.get("duration_seconds", 0.0))

        # Check compliance: Frugal policy mandates serverless scale-to-zero (min_replicas = 0)
        if min_reps != 0:
            compliance_verdict = "NON_COMPLIANT"
            if service not in non_compliant_services:
                non_compliant_services.append(service)

        # Calculate estimated cost
        gpu_key = gpu if gpu in RATES else "CPU"
        hourly_rate = RATES[gpu_key]
        item_cost = (duration / 3600.0) * hourly_rate
        total_cost_usd += item_cost

    warnings: list[str] = []
    recommendations: list[str] = []

    if compliance_verdict == "NON_COMPLIANT":
        warnings.append(
            f"Frugal billing violation: Services {non_compliant_services} "
            f"configured with min_replicas > 0! Enforce scale-to-zero immediately."
        )
        recommendations.append("Set min_replicas = 0 in Terraform deployment modules for all Cloud Run services.")
    else:
        recommendations.append("All services respect serverless scale-to-zero. Idle cost overhead is $0.00.")

    # GPU mapping suggestions
    average_duration = (
        sum(e.get("duration_seconds", 0.0) for e in execution_history) / len(execution_history)
        if execution_history else 0.0
    )

    if average_duration > 120.0:
        recommendations.append(
            "Long-duration tasks detected. Recommend utilizing spot GCP instances or batch A100 scheduling "
            "to reduce billing rates."
        )
    elif average_duration < 2.0:
        recommendations.append(
            "Ultra-short execution loops detected. Recommend CPU fallback over GPU cold-start pipelines "
            "to maximize warm-cache hits."
        )

    result = {
        "verdict": compliance_verdict,
        "estimated_accumulated_cost_usd": round(total_cost_usd, 4),
        "non_compliant_services": non_compliant_services,
        "warnings": warnings,
        "recommendations": recommendations,
    }

    logger.info(
        "billing_audited",
        verdict=compliance_verdict,
        cost=f"${total_cost_usd:.4f}",
        warnings=len(warnings),
    )

    return result


def estimate_pool_and_quota_costs(
    pool_config: dict[str, Any],
    quota_limits: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Estimate operational costs for GPU pools & assess GCP service quota compliance.

    Args:
        pool_config: Configuration dict with keys:
            - gpu_type (str): 'dual-H100', 'L4-Pool', 'A100', 'L4', 'TPU-v5e', or 'None'.
            - vram_gb (float): Target VRAM layout (e.g. 160.0).
            - mcts_nodes (float): Tree search node expansion depth (e.g. 250.0).
            - base_duration_seconds (float): Base inference execution time (default 0.12).
            - vcpu_request (int): Number of vCPUs requested (default 32).
        quota_limits: Optional dictionary of active GCP service quotas:
            - h100_limit (int): Default 4.
            - l4_limit (int): Default 8.
            - vcpu_limit (int): Default 64.

    Returns:
        A dictionary with quota verdicts, cost estimations, and recommendations.
    """
    if quota_limits is None:
        quota_limits = {
            "h100_limit": 4,
            "l4_limit": 8,
            "vcpu_limit": 64,
        }

    gpu_type = str(pool_config.get("gpu_type", "None")).lower()
    vram_gb = float(pool_config.get("vram_gb", 24.0))
    mcts_nodes = float(pool_config.get("mcts_nodes", 250.0))
    base_duration = float(pool_config.get("base_duration_seconds", 0.12))
    vcpu_request = int(pool_config.get("vcpu_request", 32))

    # Base GPU specs & pricing
    RATES = {
        "a100": 3.67,
        "h100": 4.76,
        "l4": 0.70,
        "tpu-v5e": 1.20,
        "cpu": 0.08,
    }

    hourly_rate = 0.0
    active_gpus = 0
    quota_needed_key = ""

    if gpu_type == "dual-h100":
        hourly_rate = RATES["a100"] * 2.0  # Emulating H100 with A100 baseline: 2 * 3.67 = $7.34/hr
        active_gpus = 2
        quota_needed_key = "h100_limit"
    elif gpu_type in ("l4-pool", "l4"):
        # L4 Serverless Pool: each L4 GPU provides 24GB VRAM
        active_gpus = int(math.ceil(vram_gb / 24.0))
        hourly_rate = active_gpus * RATES["l4"]
        quota_needed_key = "l4_limit"
    else:
        # Check standard GPU type
        gpu_key = gpu_type.split("-")[0]
        if gpu_key in RATES:
            hourly_rate = RATES[gpu_key]
            active_gpus = 1
            quota_needed_key = f"{gpu_key}_limit"
        else:
            hourly_rate = RATES["cpu"]
            active_gpus = 0
            quota_needed_key = ""

    # Latency scaling under Hypothesis 1 / Hypothesis 3
    # 250-node MCTS depth multiplier (scales base duration linearly)
    duration_multiplier = 1.0 + (mcts_nodes / 100.0)
    execution_time = base_duration * duration_multiplier
    
    # Query Throughput & Cost per Query
    throughput_per_hour = 3600.0 / execution_time if execution_time > 0 else 0.0
    cost_per_query = hourly_rate / throughput_per_hour if throughput_per_hour > 0 else 0.0
    cost_per_million = cost_per_query * 1_000_000.0

    # Quota verification
    warnings = []
    quota_status = "QUOTA_AVAILABLE"

    # GPU quota verification
    if quota_needed_key:
        allowed_gpu = int(quota_limits.get(quota_needed_key, 0))
        if active_gpus > allowed_gpu:
            quota_status = "QUOTA_EXCEEDED"
            warnings.append(
                f"GCP Quota Exceeded: Requested {active_gpus} of type {gpu_type.upper()}, "
                f"but active GCP limit '{quota_needed_key}' is only {allowed_gpu}."
            )

    # CPU quota verification
    allowed_vcpu = int(quota_limits.get("vcpu_limit", 0))
    if vcpu_request > allowed_vcpu:
        quota_status = "QUOTA_EXCEEDED"
        warnings.append(
            f"GCP Quota Exceeded: Requested {vcpu_request} vCPUs, "
            f"but active GCP limit 'vcpu_limit' is only {allowed_vcpu}."
        )

    recommendations = []
    if quota_status == "QUOTA_EXCEEDED":
        recommendations.append(
            "Raise a GCP Quota Increase request in the Google Cloud Console "
            "for the exhausted service boundaries before executing deployment."
        )
    else:
        recommendations.append(
            f"Quota is fully verified. Dual-H100/L4 serverless pool deployment compliant."
        )

    result = {
        "gpu_type": gpu_type.upper(),
        "vram_allocated_gb": vram_gb,
        "mcts_nodes": mcts_nodes,
        "active_gpus_requested": active_gpus,
        "vcpu_requested": vcpu_request,
        "quota_status": quota_status,
        "estimated_hourly_rate_usd": round(hourly_rate, 4),
        "estimated_query_latency_ms": round(execution_time * 1000.0, 2),
        "estimated_query_throughput_per_hour": round(throughput_per_hour, 2),
        "estimated_cost_per_million_queries_usd": round(cost_per_million, 4),
        "warnings": warnings,
        "recommendations": recommendations,
        "verdict": "COMPLIANT" if quota_status == "QUOTA_AVAILABLE" else "NON_COMPLIANT",
    }

    logger.info(
        "pool_billing_audited",
        gpu_type=result["gpu_type"],
        quota_status=quota_status,
        hourly_rate=f"${hourly_rate:.4f}",
        latency_ms=result["estimated_query_latency_ms"],
        warnings=len(warnings),
    )

    return result

