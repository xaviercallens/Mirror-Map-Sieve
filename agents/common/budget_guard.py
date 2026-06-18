# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Budget enforcement for frugal-AI experiments.

Hard constraints:
  • $100 per experiment
  • $500 cumulative project spend
  • ``min_replicas == 0`` for serverless cold-start savings

These limits are non-negotiable and enforced at the framework level.
Any tool call that would breach a limit raises :class:`BudgetExceededError`.

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_EXPERIMENT_LIMIT: float = 100.0
DEFAULT_PROJECT_LIMIT: float = 500.0

# Serverless policy — every deployment **must** set min_replicas = 0.
REQUIRED_MIN_REPLICAS: int = 0


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class BudgetExceededError(RuntimeError):
    """Raised when a proposed action would exceed budget limits."""


class ServerlessPolicyViolation(ValueError):
    """Raised when min_replicas ≠ 0."""


# ---------------------------------------------------------------------------
# Budget Guard
# ---------------------------------------------------------------------------

@dataclass
class BudgetGuard:
    """Thread-safe budget tracker enforcing per-experiment and project limits.

    Attributes:
        experiment_limit: Maximum spend for the current experiment (USD).
        project_limit: Maximum cumulative project spend (USD).
        cumulative_cost: Total spend recorded so far (USD).
        experiment_cost: Spend in the current experiment (USD).
    """

    experiment_limit: float = DEFAULT_EXPERIMENT_LIMIT
    project_limit: float = DEFAULT_PROJECT_LIMIT
    cumulative_cost: float = 0.0
    experiment_cost: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # ---- Core API --------------------------------------------------------

    def query_gcp_billing_api(self, project_id: str = "gen-lang-client-0625573011") -> float:
        """Query the GCP Cloud Billing API and compute estimated resource costs.
        
        Uses gcloud to verify billing configuration and list active resources
        to estimate current hourly expenditure.
        """
        import subprocess
        import json
        
        # Verify billing is enabled
        try:
            cmd = ["gcloud", "beta", "billing", "projects", "describe", project_id, "--format=json"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode == 0:
                info = json.loads(res.stdout)
                if not info.get("billingEnabled", False):
                    logger.warning("billing_disabled_on_gcp", project_id=project_id)
                    return 0.0
            else:
                logger.warning("gcp_billing_api_inaccessible", error=res.stderr)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
            logger.error("gcp_billing_api_query_failed", error=str(e))
            return 0.0

        # Enforce daily threshold (estimate costs from active resources to maintain strict scale-to-zero)
        estimated_hourly_cost = 0.0
        try:
            # Cloud Run active services check
            cmd_run = ["gcloud", "run", "services", "list", "--format=json"]
            res_run = subprocess.run(cmd_run, capture_output=True, text=True, timeout=10)
            if res_run.returncode == 0:
                services = json.loads(res_run.stdout)
                for svc in services:
                    meta = svc.get("metadata", {})
                    annotations = meta.get("annotations", {})
                    min_scale = int(annotations.get("autoscaling.knative.dev/minScale", 0))
                    if min_scale > 0:
                        estimated_hourly_cost += min_scale * 0.10
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
            pass

        return estimated_hourly_cost

    def enforce_finops_billing_limits(self, project_id: str = "gen-lang-client-0625573011", daily_threshold: float = 10.0) -> None:
        """Query billing/resource state and trigger a global teardown if limits are exceeded."""
        if os.getenv("AGORA_STRICT_MODE") == "1":
            hourly_rate = self.query_gcp_billing_api(project_id)
            if hourly_rate > 0.0 or self.cumulative_cost > daily_threshold:
                logger.error("finops_billing_limit_exceeded", hourly_rate=hourly_rate, cumulative=self.cumulative_cost)
                try:
                    from agents.turing.tools.deployment_manager import tear_down_deployment
                    # Trigger teardown for scale-to-zero enforcement
                    tear_down_deployment(service_name="symbrain_swarm")
                except (ImportError, RuntimeError, OSError) as te:
                    logger.critical("global_teardown_failed", error=str(te))
                raise BudgetExceededError(
                    f"FinOps billing limit exceeded! Hourly rate: ${hourly_rate:.2f}/hr, "
                    f"Cumulative: ${self.cumulative_cost:.2f}. Forced global GCP teardown."
                )

    def check_budget(self, estimated_cost: float) -> bool:
        """Check whether an action with *estimated_cost* is affordable.

        Args:
            estimated_cost: Projected cost in USD.

        Returns:
            ``True`` if the action is within budget.

        Raises:
            BudgetExceededError: If the action would breach either limit.
        """
        # Run FinOps billing limit enforcement check
        self.enforce_finops_billing_limits()

        with self._lock:
            new_experiment = self.experiment_cost + estimated_cost
            new_cumulative = self.cumulative_cost + estimated_cost

            if new_experiment > self.experiment_limit:
                raise BudgetExceededError(
                    f"Experiment budget exceeded: "
                    f"${new_experiment:.2f} > ${self.experiment_limit:.2f} "
                    f"(proposed +${estimated_cost:.2f})"
                )

            if new_cumulative > self.project_limit:
                raise BudgetExceededError(
                    f"Project budget exceeded: "
                    f"${new_cumulative:.2f} > ${self.project_limit:.2f} "
                    f"(proposed +${estimated_cost:.2f})"
                )

            logger.debug(
                "budget_check_passed",
                estimated=estimated_cost,
                experiment_used=self.experiment_cost,
                project_used=self.cumulative_cost,
            )
            return True

    def record_cost(self, actual_cost: float) -> None:
        """Record realised spend.

        Args:
            actual_cost: Actual spend in USD (must be ≥ 0).

        Raises:
            ValueError: If *actual_cost* is negative.
        """
        if actual_cost < 0:
            raise ValueError(f"Cost cannot be negative: {actual_cost}")

        with self._lock:
            self.experiment_cost += actual_cost
            self.cumulative_cost += actual_cost
            logger.info(
                "cost_recorded",
                actual=actual_cost,
                experiment_total=self.experiment_cost,
                project_total=self.cumulative_cost,
            )

    def reset_experiment(self) -> None:
        """Reset experiment-level spend (project total is preserved)."""
        with self._lock:
            logger.info(
                "experiment_budget_reset",
                experiment_cost=self.experiment_cost,
            )
            self.experiment_cost = 0.0

    @property
    def experiment_remaining(self) -> float:
        """Remaining experiment budget in USD."""
        return max(0.0, self.experiment_limit - self.experiment_cost)

    @property
    def project_remaining(self) -> float:
        """Remaining project budget in USD."""
        return max(0.0, self.project_limit - self.cumulative_cost)

    # ---- Serverless policy -----------------------------------------------

    @staticmethod
    def assert_serverless(min_replicas: int) -> None:
        """Assert that ``min_replicas == 0`` per serverless policy.

        Args:
            min_replicas: The replica floor for the deployment.

        Raises:
            ServerlessPolicyViolation: If ``min_replicas != 0``.
        """
        if min_replicas != REQUIRED_MIN_REPLICAS:
            raise ServerlessPolicyViolation(
                f"Serverless policy requires min_replicas=0, "
                f"got min_replicas={min_replicas}"
            )

    # ---- Summary ---------------------------------------------------------

    def summary(self) -> dict[str, float]:
        """Return a snapshot of budget utilisation.

        Returns:
            Dict with experiment/project spend and remaining amounts.
        """
        return {
            "experiment_cost": self.experiment_cost,
            "experiment_limit": self.experiment_limit,
            "experiment_remaining": self.experiment_remaining,
            "project_cost": self.cumulative_cost,
            "project_limit": self.project_limit,
            "project_remaining": self.project_remaining,
        }
