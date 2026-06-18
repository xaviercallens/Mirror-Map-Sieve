# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Turing Specialized Computational Tools.

Exports tools for profiling execution traces, dynamically optimizing runtime
parameters, and auditing GCP billing policies.
"""

from agents.turing.tools.model_profiler import profile_execution_trace
from agents.turing.tools.runtime_optimizer import optimize_runtime_parameters
from agents.turing.tools.gcp_billing_monitor import monitor_gcp_billing_efficiency
from agents.turing.tools.gcp_quota_manager import check_quota_compliance, get_quota_database, draft_quota_increase_justification
from agents.turing.tools.image_cache_manager import (
    build_and_cache_image,
    warm_image_in_region,
    select_image_for_class,
    list_cached_images,
    purge_old_cache,
    get_deployment_status,
    create_build_cache_bucket,
)

__all__ = [
    "profile_execution_trace",
    "optimize_runtime_parameters",
    "monitor_gcp_billing_efficiency",
    "check_quota_compliance",
    "get_quota_database",
    "draft_quota_increase_justification",
    # Image cache & deployment (v12)
    "build_and_cache_image",
    "warm_image_in_region",
    "select_image_for_class",
    "list_cached_images",
    "purge_old_cache",
    "get_deployment_status",
    "create_build_cache_bucket",
    # Deployment manager (v12)
    "deploy_for_solvability_class",
    "fast_deploy_v12",
]


