# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Turing Computer Science & Mathematical Optimization Agent.

Turing is in charge of monitoring the Agora execution bounds, optimizing
parameters, and verifying GCP serverless cost constraints.
"""

from __future__ import annotations

import pathlib
from typing import Any

import structlog

from agents.base import AbstractAgent, AgentConfig, AgentResult, AgentRole
from agents.turing.tools.model_profiler import profile_execution_trace
from agents.turing.tools.runtime_optimizer import optimize_runtime_parameters
from agents.turing.tools.gcp_billing_monitor import monitor_gcp_billing_efficiency, estimate_pool_and_quota_costs
from agents.turing.tools.deployment_manager import (
    warm_up_deployment, scale_deployment, tear_down_deployment,
    deploy_symbrain_model, deploy_for_solvability_class, fast_deploy_v12,
)
from agents.turing.tools.image_cache_manager import (
    build_and_cache_image, warm_image_in_region, select_image_for_class,
    list_cached_images, purge_old_cache, get_deployment_status, create_build_cache_bucket,
)
from agents.turing.tools.gcp_quota_manager import check_quota_compliance, get_quota_database, draft_quota_increase_justification

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT_PATH = pathlib.Path(__file__).parent / "prompts" / "system_prompt.md"

TURING_TOOLS = {
    # Profiling & optimization
    "model_profiler": profile_execution_trace,
    "runtime_optimizer": optimize_runtime_parameters,
    "gcp_billing_monitor": monitor_gcp_billing_efficiency,
    "gcp_pool_estimator": estimate_pool_and_quota_costs,
    # Deployment lifecycle
    "warm_up_deployment": warm_up_deployment,
    "scale_deployment": scale_deployment,
    "tear_down_deployment": tear_down_deployment,
    "deploy_symbrain_model": deploy_symbrain_model,
    # Complexity-aware routing (v12)
    "deploy_for_solvability_class": deploy_for_solvability_class,
    "fast_deploy_v12": fast_deploy_v12,
    # Image cache management (v12)
    "build_and_cache_image": build_and_cache_image,
    "warm_image_in_region": warm_image_in_region,
    "select_image_for_class": select_image_for_class,
    "list_cached_images": list_cached_images,
    "purge_old_cache": purge_old_cache,
    "get_deployment_status": get_deployment_status,
    "create_build_cache_bucket": create_build_cache_bucket,
    # Quota management
    "gcp_quota_checker": check_quota_compliance,
    "gcp_quota_database": get_quota_database,
    "gcp_quota_justifier": draft_quota_increase_justification,
}




class TuringAgent(AbstractAgent):
    """Computer Science & Optimization agent — manages resource and complexity limits.

    Turing performs the following tasks:
    1. **Profile** — inspects wall-clock latency, token output, solver step count.
    2. **Optimize** — computes dynamic gating girdles and SUNDIALS tolerances.
    3. **Enforce** — audits serverless scaling policies to guarantee scale-to-zero.
    """

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                name="turing",
                model="gemini-2.5-pro",
                role=AgentRole.OPTIMIZER,
                budget_limit=100.0,
                project_budget=500.0,
                timeout_ms=60_000,
                tools=list(TURING_TOOLS.keys()),
            )
        super().__init__(config)
        self._tools = TURING_TOOLS
        self._system_prompt = self._load_system_prompt()

    @staticmethod
    def _load_system_prompt() -> str:
        """Load the Turing system prompt from disk.

        Returns:
            System prompt text.
        """
        if _SYSTEM_PROMPT_PATH.exists():
            return _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        return (
            "You are Turing, the computational optimizer of the Agora. "
            "Profile performance traces, optimize SymBrain v5 and solver bounds, and audit GCP billing."
        )

    # ------ Lifecycle implementation --------------------------------------

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """Analyze the query and context to select appropriate profiling or billing tools.

        Args:
            context: Context containing query, execution traces, or billing history.

        Returns:
            A plan dictionary with selected tools and rationale.
        """
        self._guard_iterations()
        start = self._start_timer()

        query: str = context.get("query", "")
        plan: dict[str, Any] = {
            "tools": [],
            "estimated_cost": 0.0,
            "rationale": "",
        }

        query_lower = query.lower()
        rationales: list[str] = []

        def add_tools(names: list[str]) -> None:
            for name in names:
                if name not in plan["tools"]:
                    plan["tools"].append(name)

        # Deployment management routing
        if any(kw in query_lower for kw in ("deploy", "warm", "scale", "tear", "swarm", "symbrain", "tpu", "gpu")):
            add_tools(["deploy_symbrain_model", "warm_up_deployment", "scale_deployment", "tear_down_deployment"])
            plan["estimated_cost"] += 0.05
            
            # Dynamic deployment tier routing based on Solvability Class (only if not explicitly overridden)
            if "gpu_type" not in context and "accelerator_type" not in context:
                solv_class = context.get("solvability_class", "class_2")
                region = context.get("region", "us-central1")
                
                # Query active quota limits to determine best hardware fallback
                from agents.turing.tools.gcp_quota_manager import get_active_limit
                h100_limit = get_active_limit("h100", region)
                l4_limit = get_active_limit("l4", region)
                
                if solv_class == "class_3":
                    if h100_limit >= 4:
                        plan["gpu_type"] = "H100"
                        plan["deployment_nodes"] = 4
                        plan["symbrain_version"] = "v12_large"
                        rationales.append("Large Tier deployment selected (Class 3 / 4x H100).")
                    elif l4_limit >= 3:
                        plan["gpu_type"] = "L4"
                        plan["deployment_nodes"] = 3
                        plan["symbrain_version"] = "v12_large"
                        rationales.append("Large Tier deployment selected (Class 3 / 3x L4 fallback due to H100 quota constraint).")
                    else:
                        # Lowest cost/capacity fallback
                        nodes_l4 = int(max(1.0, l4_limit))
                        plan["gpu_type"] = "L4"
                        plan["deployment_nodes"] = nodes_l4
                        plan["symbrain_version"] = "v12_large"
                        rationales.append(f"Large Tier deployment selected (Class 3 / {nodes_l4}x L4 fallback due to severe quota limits).")
                else:
                    if h100_limit >= 1:
                        plan["gpu_type"] = "H100"
                        plan["deployment_nodes"] = 1
                        plan["symbrain_version"] = "v11_small"
                        rationales.append(f"Small Tier deployment selected ({solv_class} / 1x H100).")
                    elif l4_limit >= 1:
                        plan["gpu_type"] = "L4"
                        plan["deployment_nodes"] = 1
                        plan["symbrain_version"] = "v12_small"
                        rationales.append(f"Small Tier deployment selected ({solv_class} / 1x L4 fallback due to H100 quota constraint).")
                    else:
                        plan["gpu_type"] = "CPU"
                        plan["deployment_nodes"] = 1
                        plan["symbrain_version"] = "v6"
                        rationales.append(f"CPU Tier deployment selected ({solv_class} / CPU fallback due to severe GPU quota constraints).")


        # Pool & Quota billing/estimator routing
        if any(kw in query_lower for kw in ("quota", "pool", "vram", "l4", "limit", "compliance", "approved", "denied", "pending", "justification", "tpu", "h100")):
            add_tools(["gcp_quota_checker", "gcp_quota_database", "gcp_quota_justifier", "gcp_pool_estimator"])
            plan["estimated_cost"] += 0.05
            rationales.append("GCP GPU/vCPU quota manager, database, and pool estimator selected.")

        # Billing monitor routing
        if any(kw in query_lower for kw in ("bill", "cost", "billing", "replica", "gcp", "minimise", "governance")):
            add_tools(["gcp_billing_monitor"])
            plan["estimated_cost"] += 0.02
            rationales.append("Billing path selected (auditing scale-to-zero).")

        # Profile routing
        if any(kw in query_lower for kw in ("profile", "bottleneck", "trace", "latency", "eval", "nodes", "headroom", "time")):
            add_tools(["model_profiler", "runtime_optimizer"])
            plan["estimated_cost"] += 0.05
            rationales.append("Profiling path selected (analyzing telemetry).")

        # Fallback to general profiling and optimization if no tools matched
        if not plan["tools"]:
            add_tools(["model_profiler", "runtime_optimizer"])
            plan["estimated_cost"] += 0.05
            rationales.append("Dynamic optimization path selected. Profiling performance limits.")

        plan["rationale"] = " | ".join(rationales)

        self._check_budget(plan["estimated_cost"])
        self._stop_timer(start, "turing_think")
        return plan

    async def act(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Execute selected profiling or billing tools.

        Args:
            plan: The plan dict generated in think().

        Returns:
            Observations from execution.
        """
        start = self._start_timer()
        observations: dict[str, Any] = {}

        for tool_name in plan.get("tools", []):
            tool_fn = self._tools.get(tool_name)
            if tool_fn is None:
                continue

            try:
                if tool_name == "model_profiler":
                    # Fallback default trace
                    trace = plan.get("telemetry_data", {
                        "mcts_nodes": plan.get("mcts_nodes", 450),
                        "solver_evals": plan.get("solver_evals", 120),
                        "latency_ms": plan.get("latency_ms", 320.0),
                        "token_count": plan.get("token_count", 250),
                        "scratch_allocated_bytes": plan.get("scratch_allocated_bytes", 1024 * 1024 * 10),
                    })
                    result = tool_fn(telemetry_data=trace)
                    observations["model_profiler"] = result

                elif tool_name == "runtime_optimizer":
                    # Check if model_profiler observation is already populated, or compile default diagnosis
                    profiler_res = observations.get("model_profiler", {
                        "diagnosed_bottleneck": "balanced",
                        "scratch_efficiency_ratio": 0.05
                    })
                    result = tool_fn(
                        bottleneck_diagnosis=profiler_res,
                        budget_remaining_usd=self.budget_guard.experiment_remaining,
                    )
                    observations["runtime_optimizer"] = result

                elif tool_name == "gcp_billing_monitor":
                    history = plan.get("execution_history", [
                        {"service_name": "alexandrie_service", "gpu_type": "None", "min_replicas": 0, "duration_seconds": 15.4},
                        {"service_name": "socrates_service", "gpu_type": "L4", "min_replicas": 0, "duration_seconds": 45.2},
                    ])
                    result = tool_fn(execution_history=history)
                    observations["gcp_billing_monitor"] = result

                elif tool_name == "gcp_pool_estimator":
                    pool_cfg = plan.get("pool_config", {
                        "gpu_type": plan.get("gpu_type", "dual-H100"),
                        "vram_gb": plan.get("vram_gb", 160.0),
                        "mcts_nodes": plan.get("mcts_nodes", 250.0),
                        "base_duration_seconds": plan.get("base_duration_seconds", 0.12),
                        "vcpu_request": plan.get("vcpu_request", 32),
                    })
                    quota = plan.get("quota_limits", None)
                    result = tool_fn(pool_config=pool_cfg, quota_limits=quota)
                    observations["gcp_pool_estimator"] = result

                elif tool_name == "gcp_quota_checker":
                    req_res = plan.get("requested_resources", {
                        "gpu_type": plan.get("gpu_type", "L4"),
                        "region": plan.get("region", "us-central1"),
                        "nodes": plan.get("nodes", plan.get("deployment_nodes", 4)),
                        "ssd_gb": plan.get("ssd_gb", None),
                        "build_cpus": plan.get("build_cpus", None),
                    })
                    result = tool_fn(requested_resources=req_res)
                    observations["gcp_quota_checker"] = result

                elif tool_name == "gcp_quota_database":
                    result = tool_fn()
                    observations["gcp_quota_database"] = result

                elif tool_name == "gcp_quota_justifier":
                    res_name = plan.get("resource", plan.get("gpu_type", "L4"))
                    reg_name = plan.get("region", "us-central1")
                    req_limit = plan.get("requested_limit", 4)
                    result = tool_fn(resource=res_name, region=reg_name, requested_limit=req_limit)
                    observations["gcp_quota_justifier"] = result


                elif tool_name == "warm_up_deployment":
                    result = tool_fn(gpu_type=plan.get("gpu_type", "H100"), nodes=plan.get("deployment_nodes", 4))
                    observations["warm_up_deployment"] = result

                elif tool_name == "deploy_symbrain_model":
                    ver = plan.get("symbrain_version", "v9")
                    accel = plan.get("gpu_type", plan.get("accelerator_type", "L4"))
                    nodes_count = plan.get("nodes", plan.get("deployment_nodes", 4))
                    reg = plan.get("region", "us-central1")
                    result = tool_fn(
                        symbrain_version=ver,
                        accelerator_type=accel,
                        nodes=nodes_count,
                        region=reg,
                    )
                    observations["deploy_symbrain_model"] = result

                elif tool_name == "scale_deployment":
                    result = tool_fn(gpu_type=plan.get("gpu_type", "H100"), nodes=plan.get("deployment_nodes", 4))
                    observations["scale_deployment"] = result

                elif tool_name == "tear_down_deployment":
                    result = tool_fn(service_name=plan.get("service_name", "symbrain_swarm"))
                    observations["tear_down_deployment"] = result

            except Exception as exc:
                self._log.error("tool_failed", tool=tool_name, error=str(exc))
                observations[tool_name] = {"error": str(exc)}

        self._stop_timer(start, "turing_act")
        return observations

    async def run(self, query: str, **kwargs: Any) -> AgentResult:
        """Full Turing optimization run.

        Args:
            query: Problem, optimization prompt, or audit request.
            **kwargs: Telemetry trace or billing histories.

        Returns:
            Structured AgentResult containing parameters, bills, and diagnostics.
        """
        self._log.info("turing_run_start", query=query[:120])
        start = self._start_timer()
        self._iteration = 0

        context: dict[str, Any] = {"query": query, **kwargs}
        plan = await self.think(context)

        # Forward inputs
        plan["query"] = query
        for key in ("telemetry_data", "execution_history", "mcts_nodes", "solver_evals",
                     "latency_ms", "token_count", "scratch_allocated_bytes", "pool_config",
                     "quota_limits", "gpu_type", "vram_gb", "vcpu_request", "base_duration_seconds",
                     "requested_resources", "region", "nodes", "ssd_gb", "build_cpus", "resource", "requested_limit",
                     "symbrain_version", "accelerator_type", "solvability_class"):
            if key in kwargs:
                plan[key] = kwargs[key]

        observations = await self.act(plan)

        actual_cost = plan.get("estimated_cost", 0.0)
        self._record_cost(actual_cost)

        # Calculate final confidence based on compliance or profiling metrics
        confidence = 0.95
        if "gcp_billing_monitor" in observations:
            verdict = observations["gcp_billing_monitor"].get("verdict")
            if verdict == "NON_COMPLIANT":
                confidence = 0.80  # Flag lower optimization confidence due to compliance violation
        if "gcp_pool_estimator" in observations:
            verdict = observations["gcp_pool_estimator"].get("verdict")
            if verdict == "NON_COMPLIANT":
                confidence = 0.80
        if "gcp_quota_checker" in observations:
            verdict = observations["gcp_quota_checker"].get("verdict")
            if verdict == "NON_COMPLIANT":
                confidence = 0.80
        if "deploy_symbrain_model" in observations:
            deploy_status = observations["deploy_symbrain_model"].get("status")
            if deploy_status in ("QUOTA_EXCEEDED", "ERROR"):
                confidence = 0.80

        elapsed = self._stop_timer(start, "turing_run_total")

        result = AgentResult(
            answer={
                "diagnostics": observations,
                "optimized_parameters": observations.get("runtime_optimizer", {}).get("optimized_parameters", {}),
                "billing_report": observations.get("gcp_billing_monitor", {}),
                "pool_report": observations.get("gcp_pool_estimator", {}),
                "quota_report": {
                    "compliance": observations.get("gcp_quota_checker", {}),
                    "database": observations.get("gcp_quota_database", []),
                    "justification": observations.get("gcp_quota_justifier", ""),
                },
                "deployment_report": {
                    "deploy": observations.get("deploy_symbrain_model", {}),
                    "warm_up": observations.get("warm_up_deployment", {}),
                    "scale": observations.get("scale_deployment", {}),
                    "tear_down": observations.get("tear_down_deployment", {}),
                },
                "summary": self._summarise_findings(observations),
            },


            confidence=confidence,
            cost_usd=actual_cost,
            telemetry={**self.telemetry.summary(), "total_elapsed_ms": round(elapsed, 2)},
        )

        self._log.info("turing_run_complete", confidence=result.confidence, cost=result.cost_usd)
        return result

    @staticmethod
    def _summarise_findings(observations: dict[str, Any]) -> str:
        """Generate a text summary of Turing's observations and audits."""
        parts: list[str] = []

        if "model_profiler" in observations:
            prof = observations["model_profiler"]
            parts.append(f"Diagnosed Bottleneck: {prof.get('diagnosed_bottleneck', 'balanced')}")
            if prof.get("warnings"):
                parts.append(f"Profiling warnings: {'; '.join(prof['warnings'])}")

        if "runtime_optimizer" in observations:
            opt = observations["runtime_optimizer"]
            if opt.get("optimized_parameters"):
                mcts = opt["optimized_parameters"].get("mcts_max_depth")
                rtol = opt["optimized_parameters"].get("sundials_rtol")
                parts.append(f"Directives: MCTS depth={mcts}, SUNDIALS rtol={rtol}")

        if "gcp_billing_monitor" in observations:
            bill = observations["gcp_billing_monitor"]
            parts.append(f"Billing Audit: {bill.get('verdict', 'unknown')} (Estimated cumulative cost: ${bill.get('estimated_accumulated_cost_usd', 0.0):.4f})")

        if "gcp_pool_estimator" in observations:
            pool = observations["gcp_pool_estimator"]
            parts.append(f"GCP Pool Quota: {pool.get('quota_status', 'unknown')} (Hourly cost: ${pool.get('estimated_hourly_rate_usd', 0.0):.2f}/hr)")

        if "gcp_quota_checker" in observations:
            q_chk = observations["gcp_quota_checker"]
            parts.append(f"GCP Quota Compliance: {q_chk.get('verdict', 'unknown')}")
            if q_chk.get("violations"):
                parts.append(f"Violations: {'; '.join(q_chk['violations'])}")
            if q_chk.get("recommendations"):
                parts.append(f"Recommendations: {'; '.join(q_chk['recommendations'])}")

        if "gcp_quota_justifier" in observations:
            parts.append("Quota increase justification drafted.")


        if "deploy_symbrain_model" in observations:
            dep = observations["deploy_symbrain_model"]
            parts.append(f"SymBrain Deploy: {dep.get('status', 'unknown')} ({dep.get('details', dep.get('message', ''))})")


        if "scale_deployment" in observations:
            scale = observations["scale_deployment"]

            parts.append(f"Deployment Scaled: {scale.get('nodes')}x {scale.get('gpu_type')} (${scale.get('hourly_rate_usd', 0.0)}/hr)")

        if "tear_down_deployment" in observations:
            tear = observations["tear_down_deployment"]
            parts.append(f"Deployment Torn Down: {tear.get('service_name')} active_nodes={tear.get('active_nodes')}")

        return " | ".join(parts)
