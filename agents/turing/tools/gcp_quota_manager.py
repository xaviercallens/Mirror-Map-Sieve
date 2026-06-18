# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Turing GCP Quota Manager Tool.

Tracks the actual GCP quotas, checks compliance for deployment requests,
proposes optimizations (e.g. region fallbacks), and drafts justifications.
"""

from __future__ import annotations

from typing import Any
import structlog

logger = structlog.get_logger(__name__)

# Quota database compiled from user-reported Google Cloud Console quota approvals/denials
QUOTA_REQUESTS = [
    {
        "id": "60cabebc7e1c4c71b6",
        "requester": "User",
        "service": "Compute Engine API",
        "name": "Committed NVIDIA H100 GPUs",
        "region": "europe-west10",
        "limit_before": 1,
        "limit_requested": 2,
        "limit_approved": 1,
        "status": "Denied",
        "created_at": "2026-06-03T16:51:00",
        "resolved_at": "2026-06-03T16:51:00",
    },
    {
        "id": "17af30862b31449c97",
        "requester": "User",
        "service": "Agent Platform API",
        "name": "Custom model serving preemptible Nvidia A100 80GB GPUs per region",
        "region": "europe-west4",
        "limit_before": 0,
        "limit_requested": 4,
        "limit_approved": 0,
        "status": "Pending",
        "created_at": "2026-06-03T16:50:00",
        "resolved_at": None,
    },
    {
        "id": "71923934",
        "requester": "User",
        "service": "Agent Platform API",
        "name": "Custom model serving preemptible Nvidia A100 80GB GPUs per region",
        "region": "us-central1",
        "limit_before": 0,
        "limit_requested": 4,
        "limit_approved": 0,
        "status": "Pending",
        "created_at": "2026-06-03T16:48:00",
        "resolved_at": None,
    },
    {
        "id": "71885444",
        "requester": "User",
        "service": "Agent Platform API",
        "name": "Custom model serving preemptible Nvidia H100 80GB GPUs per region",
        "region": "us-central1",
        "limit_before": 0,
        "limit_requested": 2,
        "limit_approved": 0,
        "status": "Denied",
        "created_at": "2026-06-02T14:14:00",
        "resolved_at": "2026-06-02T17:00:00",
    },
    {
        "id": "d9b538cd66e34418ac",
        "requester": "User",
        "service": "Compute Engine API",
        "name": "Committed NVIDIA H100 GPUs",
        "region": "europe-west10",
        "limit_before": 0,
        "limit_requested": 1,
        "limit_approved": 1,
        "status": "Approved",
        "created_at": "2026-06-02T14:12:00",
        "resolved_at": "2026-06-02T14:12:00",
    },
    {
        "id": "d9656c337b5f43b495",
        "requester": "Auto",
        "service": "Cloud Build API",
        "name": "Concurrent Build CPUs (Regional Default Pool)",
        "region": "europe-west1",
        "limit_before": 14,
        "limit_requested": 15,
        "limit_approved": 15,
        "status": "Approved",
        "created_at": "2026-06-02T08:41:00",
        "resolved_at": "2026-06-02T08:41:00",
    },
    {
        "id": "9ac72de4ff3c4344a6",
        "requester": "Auto",
        "service": "Cloud Build API",
        "name": "Concurrent Build CPUs (Regional Default Pool)",
        "region": "europe-west1",
        "limit_before": 12,
        "limit_requested": 14,
        "limit_approved": 14,
        "status": "Approved",
        "created_at": "2026-06-01T10:02:00",
        "resolved_at": "2026-06-01T10:02:00",
    },
    {
        "id": "68dc70a2fafc4333b1",
        "requester": "Auto",
        "service": "Cloud Build API",
        "name": "Concurrent Build CPUs (Regional Default Pool)",
        "region": "europe-west1",
        "limit_before": 10,
        "limit_requested": 12,
        "limit_approved": 12,
        "status": "Approved",
        "created_at": "2026-05-31T06:50:00",
        "resolved_at": "2026-05-31T06:50:00",
    },
    {
        "id": "4615ca6047214ad089",
        "requester": "Auto",
        "service": "Cloud Build API",
        "name": "Concurrent Build CPUs (Regional Default Pool)",
        "region": "us-central1",
        "limit_before": 10,
        "limit_requested": 12,
        "limit_approved": 12,
        "status": "Approved",
        "created_at": "2026-05-29T12:09:00",
        "resolved_at": "2026-05-29T12:09:00",
    },
    {
        "id": "dd8c9921609448a983",
        "requester": "Auto",
        "service": "Compute Engine API",
        "name": "Persistent Disk SSD (GB)",
        "region": "us-central1",
        "limit_before": 500,
        "limit_requested": 572,
        "limit_approved": 572,
        "status": "Approved",
        "created_at": "2026-05-29T00:16:00",
        "resolved_at": "2026-05-29T00:16:00",
    },
    {
        "id": "aa9827bbd82f48a485",
        "requester": "User",
        "service": "Compute Engine API",
        "name": "GPUs (all regions)",
        "region": "global",
        "limit_before": 1,
        "limit_requested": 3,
        "limit_approved": 1,
        "status": "Denied",
        "created_at": "2026-05-27T10:11:00",
        "resolved_at": "2026-05-27T10:11:00",
    },
    {
        "id": "71697863",
        "requester": "User",
        "service": "Compute Engine API",
        "name": "Preemptible TPU slices tpu7x",
        "region": "us-central1",
        "limit_before": 0,
        "limit_requested": 2,
        "limit_approved": 0,
        "status": "Pending",
        "created_at": "2026-05-27T10:02:00",
        "resolved_at": None,
    },
    {
        "id": "55d9a92338c140249a",
        "requester": "User",
        "service": "Compute Engine API",
        "name": "Preemptible NVIDIA L4 GPUs",
        "region": "us-central1",
        "limit_before": 1,
        "limit_requested": 4,
        "limit_approved": 3,
        "status": "Partially approved",
        "created_at": "2026-05-27T09:46:00",
        "resolved_at": "2026-05-27T09:46:00",
    },
    {
        "id": "55f9a0c48cc441b09d",
        "requester": "User",
        "service": "Compute Engine API",
        "name": "GPUs (all regions)",
        "region": "global",
        "limit_before": 0,
        "limit_requested": 1,
        "limit_approved": 1,
        "status": "Approved",
        "created_at": "2026-05-27T09:39:00",
        "resolved_at": "2026-05-27T09:39:00",
    },
    {
        "id": "d4f14eb82827469ba7",
        "requester": "User",
        "service": "Compute Engine API",
        "name": "GPUs (all regions)",
        "region": "global",
        "limit_before": 0,
        "limit_requested": 4,
        "limit_approved": 0,
        "status": "Denied",
        "created_at": "2026-05-27T09:36:00",
        "resolved_at": "2026-05-27T09:37:00",
    }
]


def get_quota_database() -> list[dict[str, Any]]:
    """Retrieve the full historical GCP Quota Request database."""
    return QUOTA_REQUESTS


def get_active_limit(resource: str, region: str | None = None) -> float:
    """Calculate the active limit for a resource/region from approval history.

    Args:
        resource: Resource type ('h100', 'l4', 'tpu', 'gpu_global', 'build_cpu', 'ssd')
        region: Targeted GCP region (e.g. 'us-central1', 'europe-west10')

    Returns:
        The current active numeric limit.
    """
    res_lower = resource.lower()
    reg_lower = (region or "").lower()

    if res_lower == "h100":
        if reg_lower == "europe-west10":
            # Approved committed H100
            return 1.0
        elif reg_lower == "us-central1":
            # Denied custom model serving H100
            return 0.0
        # Default global GPU pool constraint applies
        return get_active_limit("gpu_global")

    elif res_lower == "l4":
        if reg_lower == "us-central1":
            # Partially approved L4 GPUs
            return 3.0
        return 0.0

    elif res_lower == "tpu":
        if reg_lower == "us-central1":
            # Pending TPU slices tpu7x
            return 0.0
        return 0.0

    elif res_lower == "a100":
        if reg_lower in ("europe-west4", "us-central1"):
            # Pending A100 80GB custom model serving
            return 0.0
        return 0.0

    elif res_lower == "gpu_global":
        # GPUs (all regions) - latest approval is 1
        return 1.0

    elif res_lower == "build_cpu":
        if reg_lower == "europe-west1":
            return 15.0
        elif reg_lower == "us-central1":
            return 12.0
        return 10.0  # default fall-back

    elif res_lower == "ssd":
        if reg_lower == "us-central1":
            return 572.0
        return 500.0  # default fall-back

    return 0.0


def check_quota_compliance(
    requested_resources: dict[str, Any]
) -> dict[str, Any]:
    """Verify if requested GCE/GKE resources fit inside current active quotas.

    Args:
        requested_resources: Dictionary containing:
            - gpu_type (str): 'H100', 'L4', 'TPU', or 'None'.
            - region (str): Targeted region (e.g., 'us-central1').
            - nodes (int): Number of nodes/GPUs requested.
            - ssd_gb (int, optional): Disk space requested.
            - build_cpus (int, optional): Build concurrency cpus needed.

    Returns:
        Compliance check results dict (verdict, violations, suggestions).
    """
    gpu_type = str(requested_resources.get("gpu_type", "None")).upper()
    region = str(requested_resources.get("region", "us-central1")).lower()
    nodes = int(requested_resources.get("nodes", 0))
    ssd_gb = requested_resources.get("ssd_gb")
    build_cpus = requested_resources.get("build_cpus")

    verdict = "COMPLIANT"
    violations: list[str] = []
    recommendations: list[str] = []

    # Check GPU limits
    if gpu_type in ("H100", "L4", "TPU", "A100"):
        # Map to specific resource keys
        res_key = gpu_type.lower()
        limit = get_active_limit(res_key, region)

        if nodes > limit:
            verdict = "NON_COMPLIANT"
            violations.append(
                f"Requested {nodes}x {gpu_type} in {region}, but active quota is {int(limit)}."
            )

            # Check if pending status is the bottleneck
            pending_reqs = [
                q for q in QUOTA_REQUESTS
                if q["status"] == "Pending" and region in q["region"] and res_key in q["name"].lower()
            ]
            if pending_reqs:
                violations.append(
                    f"A request for this resource is currently pending approval since "
                    f"{pending_reqs[0]['created_at']} (Request ID: {pending_reqs[0]['id']})."
                )

            # Suggest fallbacks
            if gpu_type == "H100" and region == "us-central1":
                # User H100 was denied in us-central1, but approved in europe-west10
                h100_ew10_limit = get_active_limit("h100", "europe-west10")
                if h100_ew10_limit > 0:
                    recommendations.append(
                        f"Redirect deployment to europe-west10 where 1x Committed NVIDIA H100 GPU is active."
                    )
            elif gpu_type == "L4" and region == "us-central1":
                # Limit is 3. Suggest scaling down to 3.
                recommendations.append(
                    f"Scale down Swarm deployment configuration from {nodes} to 3 preemptible NVIDIA L4 GPUs."
                )
            elif gpu_type == "A100" and region in ("europe-west4", "us-central1"):
                # Limit is 0. Suggest using the approved H100 in europe-west10
                h100_ew10_limit = get_active_limit("h100", "europe-west10")
                if h100_ew10_limit > 0:
                    recommendations.append(
                        f"Redirect deployment to europe-west10 where 1x Committed NVIDIA H100 GPU is active."
                    )
            
            recommendations.append(
                f"Submit a GCP quota increase request for {gpu_type} in {region}."
            )

        # Check global GPU count rule
        global_gpu_limit = get_active_limit("gpu_global")
        if nodes > global_gpu_limit and gpu_type != "None":
            # Some resources (like committed H100) might bypass global limits depending on billing,
            # but we alert for safety.
            logger.warning("global_gpu_limit_warning", limit=global_gpu_limit, requested=nodes)

    # Check SSD limits
    if ssd_gb is not None:
        limit = get_active_limit("ssd", region)
        if ssd_gb > limit:
            verdict = "NON_COMPLIANT"
            violations.append(
                f"Requested {ssd_gb} GB SSD in {region}, but active quota is {int(limit)} GB."
            )
            recommendations.append(
                f"Reduce persistent disk allocation to {int(limit)} GB or cleanup orphaned disks in {region}."
            )

    # Check Build cpus limits
    if build_cpus is not None:
        limit = get_active_limit("build_cpu", region)
        if build_cpus > limit:
            verdict = "NON_COMPLIANT"
            violations.append(
                f"Requested {build_cpus} Concurrent Build CPUs in {region}, but active quota is {int(limit)}."
            )
            recommendations.append(
                f"Wait for parallel builds to clear, or run builds in another region with higher limits."
            )

    return {
        "verdict": verdict,
        "violations": violations,
        "recommendations": recommendations,
        "requested": {
            "gpu_type": gpu_type,
            "region": region,
            "nodes": nodes,
            "ssd_gb": ssd_gb,
            "build_cpus": build_cpus
        }
    }


def draft_quota_increase_justification(
    resource: str, region: str, requested_limit: int
) -> str:
    """Draft a professional justification text to request a quota increase in GCP Console.

    Args:
        resource: Resource identifier (e.g. 'L4', 'H100', 'TPU').
        region: GCP region name.
        requested_limit: The new target limit.

    Returns:
        Justification text string.
    """
    res_upper = resource.upper()
    reg_upper = region.upper()

    return (
        f"Requesting a quota increase for {res_upper} GPUs in the {reg_upper} region "
        f"(Target limit: {requested_limit}). This quota is required to support the "
        f"SocrateAI Scientific Agora framework's mathematical reasoner (SymBrain v11). "
        f"The nodes run Monte Carlo Tree Search (MCTS) lemma exploration, which is "
        f"stochastically driven by Dopaminergic Reward-Prediction Error (RPE) logic. "
        f"These workloads are non-graphical, compute-bound theorem-proving cycles that "
        f"utilize preemptible instances. Our project is governed by a strict cost-monitoring "
        f"framework to ensure high efficiency and minimal resource wastage."
    )
