# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Unit and integration tests for Turing agent and Socrates optimization loops."""

from __future__ import annotations

import pytest

from agents.base import AgentConfig, AgentRole
from agents.turing.agent import TuringAgent
from agents.turing.tools.model_profiler import profile_execution_trace
from agents.turing.tools.runtime_optimizer import optimize_runtime_parameters
from agents.turing.tools.gcp_billing_monitor import monitor_gcp_billing_efficiency
from agents.socrates.agent import SocratesAgent
from agents.socrates.dialectic_engine import DialecticEngine


def test_turing_profiler_balanced():
    """Verify trace profiling on balanced traces."""
    trace = {
        "mcts_nodes": 400,
        "solver_evals": 80,
        "latency_ms": 150.0,
        "token_count": 120,
        "scratch_allocated_bytes": 1024 * 1024 * 50,  # 50 MB
    }
    result = profile_execution_trace(trace)
    assert result["diagnosed_bottleneck"] == "balanced"
    assert result["scratch_efficiency_ratio"] < 0.10
    assert not result["warnings"]


def test_turing_profiler_bottlenecks():
    """Verify trace profiling under different bottlenecks."""
    # Compute-bound search trace
    trace_compute = {
        "mcts_nodes": 3500,
        "solver_evals": 20,
        "latency_ms": 450.0,
        "token_count": 80,
        "scratch_allocated_bytes": 1024 * 1024 * 5,
    }
    result_comp = profile_execution_trace(trace_compute)
    assert result_comp["diagnosed_bottleneck"] == "compute-bound"
    assert any("MCTS" in w for w in result_comp["warnings"])

    # Solver stiff system trace
    trace_solver = {
        "mcts_nodes": 50,
        "solver_evals": 1500,
        "latency_ms": 380.0,
        "token_count": 10,
        "scratch_allocated_bytes": 1024 * 1024 * 200,
    }
    result_sol = profile_execution_trace(trace_solver)
    assert result_sol["diagnosed_bottleneck"] == "solver-bound"
    assert any("rusty-SUNDIALS" in w for w in result_sol["warnings"])


def test_turing_optimizer_austerity():
    """Verify runtime parameter tuning under low-budget restrictions."""
    diagnosis = {
        "diagnosed_bottleneck": "compute-bound",
        "scratch_efficiency_ratio": 0.05
    }
    
    # Severe budget (austerity)
    res_aust = optimize_runtime_parameters(diagnosis, budget_remaining_usd=4.50)
    assert res_aust["austerity_active"] is True
    assert res_aust["optimized_parameters"]["mcts_max_depth"] == 2
    assert res_aust["optimized_parameters"]["quantization_tier"] == "INT4_AWQ"

    # Comfortable budget
    res_comfortable = optimize_runtime_parameters(diagnosis, budget_remaining_usd=120.0)
    assert res_comfortable["austerity_active"] is False
    assert res_comfortable["optimized_parameters"]["mcts_max_depth"] == 4  # Compute bottleneck dampening


def test_gcp_billing_monitor():
    """Verify compliance alerts when scale-to-zero is violated."""
    # Compliant
    history_compliant = [
        {"service_name": "alexandrie_service", "gpu_type": "None", "min_replicas": 0, "duration_seconds": 15.4},
        {"service_name": "galois_service", "gpu_type": "L4", "min_replicas": 0, "duration_seconds": 30.5},
    ]
    res_comp = monitor_gcp_billing_efficiency(history_compliant)
    assert res_comp["verdict"] == "COMPLIANT"
    assert res_comp["estimated_accumulated_cost_usd"] > 0.0
    assert not res_comp["warnings"]

    # Non-compliant (min_replicas > 0)
    history_violating = [
        {"service_name": "alexandrie_service", "gpu_type": "None", "min_replicas": 1, "duration_seconds": 15.4},
    ]
    res_viol = monitor_gcp_billing_efficiency(history_violating)
    assert res_viol["verdict"] == "NON_COMPLIANT"
    assert len(res_viol["warnings"]) == 1
    assert "Frugal billing violation" in res_viol["warnings"][0]


@pytest.mark.anyio
async def test_turing_agent_run():
    """Verify turing agent lifecycle think -> act -> run."""
    agent = TuringAgent()
    
    # Perform general profiling run
    result = await agent.run(
        "Profile the computational trace",
        mcts_nodes=150,
        solver_evals=20,
        latency_ms=10.5,
        token_count=80,
        scratch_allocated_bytes=1024,
    )
    
    assert result.confidence == 0.95
    assert result.cost_usd > 0.0
    assert "diagnostics" in result.answer
    assert "optimized_parameters" in result.answer


@pytest.mark.anyio
async def test_socrates_dialectic_turing_integration():
    """Verify Socrates master orchestrates tri-agent and tetra-agent dialectic with Turing."""
    socrates = SocratesAgent()
    
    # We query Socrates for computational trace optimization specifically
    res = await socrates.run("Verify the billing replica scaling compliance of the Agora services on GCP")
    
    assert "complexity" in res.answer
    assert (
        "turing" in res.answer["observations"]
        or (
            "dialectic" in res.answer["observations"]
            and res.answer["observations"]["dialectic"]["turing_result"]
        )
    )
    assert res.cost_usd > 0.0


def test_gcp_quota_manager():
    """Verify that GCP Quota Manager correctly detects compliance and fallbacks."""
    from agents.turing.tools.gcp_quota_manager import check_quota_compliance, get_quota_database, draft_quota_increase_justification

    # Test database retrieval
    db = get_quota_database()
    assert len(db) >= 12
    assert any(q["id"] == "71885444" for q in db)

    # Compliant check: 3x L4 in us-central1 (limit is 3)
    res_compliant = check_quota_compliance({
        "gpu_type": "L4",
        "region": "us-central1",
        "nodes": 3,
    })
    assert res_compliant["verdict"] == "COMPLIANT"
    assert not res_compliant["violations"]

    # Non-compliant check: 4x L4 in us-central1 (limit is 3)
    res_l4_exceeded = check_quota_compliance({
        "gpu_type": "L4",
        "region": "us-central1",
        "nodes": 4,
    })
    assert res_l4_exceeded["verdict"] == "NON_COMPLIANT"
    assert any("limit is 3" in v or "active quota is 3" in v for v in res_l4_exceeded["violations"])
    assert any("Scale down" in r for r in res_l4_exceeded["recommendations"])

    # Non-compliant check: H100 in us-central1 (limit is 0)
    res_h100_exceeded = check_quota_compliance({
        "gpu_type": "H100",
        "region": "us-central1",
        "nodes": 1,
    })
    assert res_h100_exceeded["verdict"] == "NON_COMPLIANT"
    assert any("europe-west10" in r for r in res_h100_exceeded["recommendations"])

    # Justification drafting
    justification = draft_quota_increase_justification("L4", "us-central1", 4)
    assert "us-central1" in justification.lower()
    assert "l4" in justification.lower()
    assert "symbrain v11" in justification.lower()


@pytest.mark.anyio
async def test_turing_agent_quota_routing():
    """Verify that TuringAgent correctly routes quota requests and parses database/compliance."""
    agent = TuringAgent()
    
    # Query about Nvidia L4 quota limits
    result = await agent.run(
        "Check compliance for deploying 4 Nvidia L4 GPUs in us-central1 and write a justification for a quota increase to 4",
        gpu_type="L4",
        region="us-central1",
        nodes=4,
        requested_limit=4,
    )
    
    assert result.confidence == 0.80  # Non-compliant reduces confidence
    assert "quota_report" in result.answer
    assert result.answer["quota_report"]["compliance"]["verdict"] == "NON_COMPLIANT"
    assert "justification" in result.answer["quota_report"]
    assert "us-central1" in result.answer["quota_report"]["justification"].lower()


def test_deploy_symbrain_model():
    """Verify that deploying SymBrain versions on compatible/incompatible hardware and quota restrictions works."""
    from agents.turing.tools.deployment_manager import deploy_symbrain_model

    # Incompatible hardware test: v4 on TPU
    res_incompat = deploy_symbrain_model(symbrain_version="v4", accelerator_type="TPU", nodes=1)
    assert res_incompat["success"] is False
    assert "Incompatible Hardware" in res_incompat["message"]

    # Unknown version test
    res_unknown = deploy_symbrain_model(symbrain_version="v100", accelerator_type="GPU", nodes=1)
    assert res_unknown["success"] is False
    assert "Unknown SymBrain" in res_unknown["message"]

    # Quota exceeded test: 4x L4 in us-central1 (limit is 3)
    res_quota = deploy_symbrain_model(symbrain_version="v9", accelerator_type="L4", nodes=4, region="us-central1")
    assert res_quota["success"] is False
    assert res_quota["status"] == "QUOTA_EXCEEDED"
    assert any("limit is 3" in v or "active quota is 3" in v for v in res_quota["violations"])

    # Successful deployment: 1x Committed H100 in europe-west10
    res_success = deploy_symbrain_model(symbrain_version="v9", accelerator_type="H100", nodes=1, region="europe-west10")
    assert res_success["success"] is True
    assert res_success["status"] == "DEPLOYED"
    assert "SymBrain-V9" in res_success["symbrain_version"]
    assert res_success["nodes"] == 1
    assert res_success["hourly_rate_usd"] == 4.76


@pytest.mark.anyio
async def test_turing_agent_symbrain_deploy_routing():
    """Verify that TuringAgent correctly routes queries for SymBrain GPU/TPU deployments."""
    agent = TuringAgent()
    
    # Query to deploy cortex_v9 on 3x L4 GPUs
    result = await agent.run(
        "Deploy cortex_v9 on 3x L4 GPUs in us-central1",
        symbrain_version="v9",
        accelerator_type="L4",
        nodes=3,
        region="us-central1",
    )
    
    assert result.confidence == 0.95  # Compliant deployment
    assert "deployment_report" in result.answer
    assert result.answer["deployment_report"]["deploy"]["success"] is True
    assert result.answer["deployment_report"]["deploy"]["status"] == "DEPLOYED"
    assert result.answer["deployment_report"]["deploy"]["hourly_rate_usd"] == pytest.approx(2.10)  # 3 * 0.70 = 2.10


def test_deploy_symbrain_v11():
    """Verify that deploying SymBrain v11 on compatible hardware and quota restrictions works."""
    from agents.turing.tools.deployment_manager import deploy_symbrain_model

    # Incompatible hardware test: v11 on CPU/T4
    res_incompat = deploy_symbrain_model(symbrain_version="v11", accelerator_type="T4", nodes=1)
    assert res_incompat["success"] is False
    assert "Incompatible Hardware" in res_incompat["message"]

    # Successful deployment: 3x L4 in us-central1 (limit is 3, so compliant)
    res_success_l4 = deploy_symbrain_model(symbrain_version="v11", accelerator_type="L4", nodes=3, region="us-central1")
    assert res_success_l4["success"] is True
    assert res_success_l4["status"] == "DEPLOYED"
    assert "SymBrain-V11" in res_success_l4["symbrain_version"]
    assert res_success_l4["nodes"] == 3
    assert res_success_l4["hourly_rate_usd"] == pytest.approx(2.10)

    # Quota exceeded test: 4x L4 in us-central1 (limit is 3)
    res_quota_l4 = deploy_symbrain_model(symbrain_version="v11", accelerator_type="L4", nodes=4, region="us-central1")
    assert res_quota_l4["success"] is False
    assert res_quota_l4["status"] == "QUOTA_EXCEEDED"

    # Successful deployment: 1x Committed H100 in europe-west10 (limit is 1, so compliant)
    res_success_h100 = deploy_symbrain_model(symbrain_version="v11", accelerator_type="H100", nodes=1, region="europe-west10")
    assert res_success_h100["success"] is True
    assert res_success_h100["status"] == "DEPLOYED"
    assert "SymBrain-V11" in res_success_h100["symbrain_version"]
    assert res_success_h100["nodes"] == 1
    assert res_success_h100["hourly_rate_usd"] == 4.76





