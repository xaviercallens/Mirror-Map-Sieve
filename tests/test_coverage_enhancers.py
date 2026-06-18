# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Specialized unit tests designed to cover all outstanding code coverage gaps in Agora agents, tools, and vaults."""

from __future__ import annotations

import json
import math
import os
import pathlib
import subprocess
import pytest
from unittest.mock import MagicMock, patch

from agents.base import AgentConfig, AgentResult, AgentRole, AbstractAgent
from agents.common.budget_guard import BudgetGuard, BudgetExceededError, ServerlessPolicyViolation
from agents.common.telemetry import AgentTelemetry
from agents.euler.agent import EulerAgent
from agents.euler.tools.deepproblog_gate import evaluate_probabilistic_query, _parse_program, _type_check_program
from agents.euler.tools.lean4_compiler import compile_lean4_proof
from agents.euler.tools.leanabell_prover import leanabell_prove_theorem, _verifier_integrated_feedback_mutation
from agents.euler.tools.skeptical_auditor import audit_demonstration, _check_numeric_data
from agents.galileo.agent import GalileoAgent
from agents.galileo.tools.cost_estimator import estimate_cost
from agents.galileo.tools.data_integrity import validate_scientific_data_integrity
from agents.galileo.tools.nvidia_nim import query_nvidia_nim
from agents.galileo.tools.sundials_solver import sundials_cvode_solver, _solve_python_fallback, _SYSTEM_REGISTRY
from agents.galois.agent import GaloisAgent
from agents.galois.symbrain.cortex_v4 import GaloisComplexityClassifier, GaloisRoutingTensor, GaloisCortexConfig, HemisphereMode, ConjectureConfidence
from agents.galois.tools.conjecture_generator import generate_conjectures
from agents.galois.tools.proof_sketcher import sketch_proof, _detect_strategy, _build_lean4_sketch, ProofStrategy
from agents.galois.tools.self_improvement import plan_self_improvement, _analyze_performance
from agents.hypatie.agent import HypatieAgent
from agents.hypatie.tools.archive_vault import catalog_scientific_work
from agents.hypatie.tools.astrolabe_navigator import navigate_astrolabe
from agents.socrates.agent import SocratesAgent
from agents.socrates.dialectic_engine import DialecticEngine
from agents.turing.agent import TuringAgent
from agents.turing.tools.model_profiler import profile_execution_trace
from agents.turing.tools.runtime_optimizer import optimize_runtime_parameters
from agents.turing.tools.gcp_billing_monitor import monitor_gcp_billing_efficiency
from alexandrie.hub import AlexandrieHub
from alexandrie.metadata import ArtifactType, RoomType
from alexandrie.server import app, hub
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# 1. Base Framework & Guardrails (`agents/base.py`, `agents/common/*`)
# ---------------------------------------------------------------------------

def test_base_config_serverless_violation():
    """Verify that AgentConfig raises ValueError if min_replicas is non-zero."""
    with pytest.raises(ValueError, match="Serverless policy violation"):
        AgentConfig(name="test_agent", min_replicas=1)


def test_base_config_budget_limit_exceeded():
    """Verify that AgentConfig raises ValueError if experiment budget exceeds project budget."""
    with pytest.raises(ValueError, match="exceeds project budget"):
        AgentConfig(name="test_agent", budget_limit=600.0, project_budget=500.0)


def test_base_result_invalid_confidence():
    """Verify that AgentResult validates that confidence is in [0, 1]."""
    with pytest.raises(ValueError, match="Confidence must be in"):
        AgentResult(answer="ok", confidence=-0.5)

    with pytest.raises(ValueError, match="Confidence must be in"):
        AgentResult(answer="ok", confidence=1.5)


def test_base_agent_repr_and_iterations():
    """Test concrete agent representation and iteration safety guards."""
    agent = GalileoAgent()
    assert "GalileoAgent" in repr(agent)
    assert agent.config.role == AgentRole.EXPERIMENTER

    # Trigger iteration count safety guard
    agent.config = AgentConfig(name="galileo", max_iterations=2)
    agent._iteration = 0
    agent._guard_iterations()  # 1
    agent._guard_iterations()  # 2
    with pytest.raises(RuntimeError, match="exceeded max iterations"):
        agent._guard_iterations()  # 3


def test_base_agent_budget_check_failure():
    """Verify that the base agent's _check_budget raises BudgetExceededError."""
    agent = GalileoAgent()
    # Force experiment budget remaining to be very small, then call check_budget
    agent.budget_guard.experiment_limit = 10.0
    agent._check_budget(5.0)  # should pass
    with pytest.raises(BudgetExceededError, match="budget exceeded"):
        agent._check_budget(12.0)


def test_budget_guard_negative_cost():
    """Verify that record_cost raises ValueError for negative amounts."""
    guard = BudgetGuard()
    with pytest.raises(ValueError, match="cannot be negative"):
        guard.record_cost(-1.0)


def test_budget_guard_remaining_and_serverless():
    """Verify budget remaining edge cases and serverless policies."""
    guard = BudgetGuard(experiment_limit=10.0, project_limit=50.0)
    guard.record_cost(15.0)
    assert guard.experiment_remaining == 0.0
    assert guard.project_remaining == 35.0

    with pytest.raises(ServerlessPolicyViolation, match="requires min_replicas=0"):
        BudgetGuard.assert_serverless(1)


def test_budget_guard_summary_and_reset():
    """Verify budget guard summary and reset_experiment functions."""
    guard = BudgetGuard(experiment_limit=10.0, project_limit=50.0)
    guard.record_cost(5.0)
    guard.reset_experiment()
    assert guard.experiment_cost == 0.0
    assert guard.cumulative_cost == 5.0
    sum_data = guard.summary()
    assert sum_data["experiment_cost"] == 0.0
    assert sum_data["project_cost"] == 5.0


def test_telemetry_custom_metrics_and_reset():
    """Test the telemetry counters, tokens recording, and reset logic."""
    telemetry = AgentTelemetry(agent_name="test_telemetry")
    telemetry.record_tokens(100, 200)
    telemetry.record_solver_stats(func_evals=10, jacobian_evals=2, mcts_nodes=5)
    
    summary = telemetry.summary()
    assert summary["total_tokens"] == 300
    assert summary["solver_evals"] == 10
    assert summary["jacobian_evals"] == 2
    assert summary["mcts_nodes"] == 5

    telemetry.reset()
    assert telemetry.total_tokens == 0
    assert telemetry.solver_evals == 0
    assert telemetry.mcts_nodes == 0


# ---------------------------------------------------------------------------
# 2. Euler Agent & Tools (`agents/euler/*`)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_euler_dialectic_runs_incomplete_or_failed():
    """Verify Euler agent run-loop coverage for failing tool results."""
    agent = EulerAgent()

    # Case 1: Lean 4 compilation failure
    mock_obs_fail = {
        "lean4_compiler": {
            "success": False,
            "message": "Syntax error at line 5",
            "has_sorry": False,
        }
    }
    with patch.object(EulerAgent, "act", return_value=mock_obs_fail):
        res = await agent.run("Verify this failing proof")
        assert res.answer["status"] == "REFUTED"
        assert any("compilation failed" in o for o in res.answer["objections"])

    # Case 2: Proof contains sorry gaps
    mock_obs_sorry = {
        "lean4_compiler": {
            "success": True,
            "has_sorry": True,
            "message": "Contains sorry stubs",
        }
    }
    with patch.object(EulerAgent, "act", return_value=mock_obs_sorry):
        res = await agent.run("Verify this incomplete proof")
        assert res.answer["status"] == "INCOMPLETE"
        assert any("sorry" in o.lower() for o in res.answer["objections"])

    # Case 3: DeepProbLog type violation (P=0)
    mock_obs_dpl = {
        "deepproblog_gate": {
            "probability": 0.0,
        }
    }
    with patch.object(EulerAgent, "act", return_value=mock_obs_dpl):
        res = await agent.run("Verify this probabilistically refuted query")
        assert res.answer["status"] == "REFUTED"

    # Case 4: Skeptical auditor severity error
    mock_obs_audit = {
        "skeptical_auditor": {
            "issues": [
                {"severity": "error", "message": "Catastrophic logic loop"}
            ]
        }
    }
    with patch.object(EulerAgent, "act", return_value=mock_obs_audit):
        res = await agent.run("Verify this logically faulty claim")
        assert res.answer["status"] == "REFUTED"
        assert "[ERROR] Catastrophic logic" in res.answer["objections"][0]


def test_euler_confidence_edge_cases():
    """Test confidence scoring for all possible tool return values in Euler."""
    # Empty scores - skeptical auditor default of 0.9 is appended
    assert EulerAgent._compute_verification_confidence({}) == 0.9

    # Leanabell outcomes
    obs_lb1 = {"leanabell_prover": MagicMock(success=True, sorry_remaining=False)}
    assert EulerAgent._compute_verification_confidence(obs_lb1) == 0.95  # (1.0 + 0.9) / 2

    obs_lb2 = {"leanabell_prover": MagicMock(success=True, sorry_remaining=True)}
    assert EulerAgent._compute_verification_confidence(obs_lb2) == 0.6  # (0.3 + 0.9) / 2

    obs_lb3 = {"leanabell_prover": MagicMock(success=False, sorry_remaining=False)}
    assert EulerAgent._compute_verification_confidence(obs_lb3) == 0.45  # (0.0 + 0.9) / 2

    # Dictionary representation for leanabell
    obs_lb_dict = {"leanabell_prover": {"success": True, "sorry_remaining": True}}
    assert EulerAgent._compute_verification_confidence(obs_lb_dict) == 0.6

    # Lean 4 compiler outcomes
    obs_lean1 = {"lean4_compiler": {"success": True, "has_sorry": False}}
    assert EulerAgent._compute_verification_confidence(obs_lean1) == 0.95

    obs_lean2 = {"lean4_compiler": {"success": True, "has_sorry": True}}
    assert EulerAgent._compute_verification_confidence(obs_lean2) == 0.6

    obs_lean3 = {"lean4_compiler": {"success": False}}
    assert EulerAgent._compute_verification_confidence(obs_lean3) == 0.45


def test_deepproblog_type_violations_and_bounds():
    """Verify DeepProbLog's probability bounds, missing neural preds, and rounding."""
    # Probability bounds check in type-checking
    ill_typed_prog = "1.5 :: fact()."
    res = evaluate_probabilistic_query(ill_typed_prog, "fact()")
    assert res["probability"] == 0.0
    assert res["type_check"] is False
    assert any("Invalid probability" in w for w in res["warnings"])

    # Neural predicate availability
    missing_net_prog = "nn(mnist, [img], digit)."
    res_missing = evaluate_probabilistic_query(missing_net_prog, "digit(img, 1)", neural_preds={})
    assert res_missing["probability"] == 0.0
    assert res_missing["type_check"] is False
    assert "referenced but not provided" in res_missing["warnings"][0]

    # Continuous grounding values outside [0,1]
    prog_value = "nn(net, [input], output)."
    res_value = evaluate_probabilistic_query(
        prog_value,
        "output(true)",
        neural_preds={"net": {"value": 1.8}}
    )
    assert res_value["probability"] == 1.0  # min(1.0, value)

    res_value_neg = evaluate_probabilistic_query(
        prog_value,
        "output(true)",
        neural_preds={"net": {"value": -0.5}}
    )
    assert res_value_neg["probability"] == 0.0  # max(0.0, value)

    # Simple program with no neural preds (evaluates correctly)
    simple_prog = "0.9 :: rain()."
    res_simple = evaluate_probabilistic_query(simple_prog, "rain()", neural_preds=None)
    assert res_simple["probability"] == 0.9


def test_lean4_compiler_timeout_and_errors():
    """Verify Lean 4 compiler error parsing, missing binary fallback, and timeout paths."""
    # Case 1: Sorry warning detection
    code_with_sorry = "theorem my_proof : True := by sorry"
    # Mock shutil.which to find the compiler
    with patch("shutil.which", return_value="/usr/bin/lean"):
        # Mock subprocess to fail
        mock_proc = MagicMock(returncode=1, stdout="", stderr="Type checking error at line 1")
        with patch("subprocess.run", return_value=mock_proc):
            res = compile_lean4_proof(code_with_sorry)
            assert res["success"] is False
            assert res["has_sorry"] is True
            assert "Type-checking FAILED" in res["message"]

    # Case 2: Timeout trigger
    with patch("shutil.which", return_value="/usr/bin/lean"):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=[], timeout=120)):
            res_timeout = compile_lean4_proof("theorem test : 1=1 := rfl")
            assert res_timeout["success"] is False
            assert "timed out" in res_timeout["message"]

    # Case 3: Missing compiler binary
    with patch("shutil.which", return_value=None):
        res_missing = compile_lean4_proof("theorem test : 1=1 := rfl")
        assert res_missing["success"] is False
        assert "not found" in res_missing["message"]


def test_leanabell_prover_mutation_and_timeouts():
    """Verify Leanabell Prover feedback mutations and compiler execution exceptions."""
    # Test tactic selection heuristics
    assert _verifier_integrated_feedback_mutation("", [], ["multiplication in Nat"], 1) == "by ring"
    assert _verifier_integrated_feedback_mutation("", [], ["Goal has ≤ and nat"], 1) == "by omega"
    assert _verifier_integrated_feedback_mutation("", ["equality error"], [], 1) == "by rfl"
    assert _verifier_integrated_feedback_mutation("", [], ["∀ x, P x → Q x"], 1) == "by\n  intro x\n  aesop"
    # Fallback to TACTIC_LIBRARY
    assert _verifier_integrated_feedback_mutation("", [], ["some random goal"], 3) == "by ring"

    # Mock Leanabell compiler timeout exception
    with patch("shutil.which", return_value="/usr/bin/lean"):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=[], timeout=30)):
            res = leanabell_prove_theorem("theorem test (n : Nat) : n + 0 = n", max_backtracks=1)
            assert res.success is False
            assert "Compiler timed out" in res.trajectory[0].errors


def test_skeptical_auditor_numerical_anomalies():
    """Verify auditor checks on denominators, IEEE754 patterns, and numeric data arrays."""
    # Test division patterns triggering denominator risk
    res_denom = audit_demonstration("We can divide both sides by x.", numeric_data=[])
    assert res_denom["passed"] is False  # Division by x is an error!
    assert any("denominator_risk" in i["code"] for i in res_denom["issues"])

    # Test IEEE 754 float patterns
    res_ieee = audit_demonstration("Let the tolerance be 1e-305 and value equal to inf.")
    assert len(res_ieee["issues"]) >= 2

    # Test numeric data checks (NaN, Infinity, Denormalized)
    res_numeric = audit_demonstration("Checking raw data array", numeric_data=[float("nan"), float("inf"), 1e-310, 5.0])
    assert res_numeric["passed"] is False
    assert any("nan_in_data" in i["code"] for i in res_numeric["issues"])
    assert any("inf_in_data" in i["code"] for i in res_numeric["issues"])
    assert any("denormalised_value" in i["code"] for i in res_numeric["issues"])


# ---------------------------------------------------------------------------
# 3. Galileo Agent & Tools (`agents/galileo/*`)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_galileo_early_exits():
    """Verify Galileo's execution fallback and early timeout handling."""
    agent = GalileoAgent()
    # Mock the tool inside _tools to raise an exception, which act catches locally
    agent._tools = {
        **agent._tools,
        "sundials_solver": MagicMock(side_effect=Exception("Solver exploded"))
    }
    res = await agent.run("Perform simulation for Robertson kinetics")
    assert res.confidence == 0.5
    assert "error" in res.answer["sundials_solver"]


def test_cost_estimator_unknown_gpu():
    """Verify cost estimator handles unknown GPU types by raising a ValueError."""
    # Case: Unknown GPU
    with pytest.raises(ValueError, match="Unknown GPU type"):
        estimate_cost(gpu_type="QuantumGPU", hours=2.0)


def test_data_integrity_noise_entropy():
    """Verify data integrity checks trigger on flat noise distributions and extreme counts."""
    # Zero-noise data
    flat_data = [5.0] * 20
    res = validate_scientific_data_integrity(flat_data)
    assert res["passed"] is False
    assert any("noise entropy failed" in e.lower() for e in res["errors"])


def test_nvidia_nim_bounds_and_mock_api(monkeypatch):
    """Test Earth2 latitude range boundaries, invalid BioNeMo sequences, and NIM API mocks."""
    # Case 1: Unknown model ValueError
    with pytest.raises(ValueError, match="Unknown NIM model"):
        query_nvidia_nim("Unknown-NIM-Model", {})

    # Case 2: ESM2 Invalid sequence amino acids & length
    res_invalid = query_nvidia_nim("BioNeMo-ESM2", {"sequence": "MKTXXIL"})
    assert res_invalid["success"] is False
    assert "Invalid amino acids" in res_invalid["message"]

    res_short = query_nvidia_nim("BioNeMo-ESM2", {"sequence": "MKT"})
    assert res_short["success"] is False
    assert "Sequence too short" in res_short["message"]

    monkeypatch.setenv("NIM_API_KEY", "mock_key")
    with patch("httpx.Client.post") as mock_post:
        # Mock responses
        mock_resp_earth2 = MagicMock()
        mock_resp_earth2.json.return_value = {
            "temperatures": [290.0, 295.0]
        }
        mock_resp_esm = MagicMock()
        mock_resp_esm.json.return_value = {
            "total_mass": 1100.0,
            "predicted_structure": "alpha_helix",
            "embeddings": [0.1] * 10
        }
        
        # We make mock_post return earth2 response by default
        mock_post.return_value = mock_resp_earth2

        # Case 3: Earth2 geographic out-of-bounds
        res_bounds = query_nvidia_nim("Earth2-FourCastNet", {"latitudes": [-95.0, 45.0]})
        assert res_bounds["success"] is False
        assert "lat_bounds" in res_bounds["invariant_checks"]
        assert res_bounds["invariant_checks"]["lat_bounds"] is False

        # Case 4: Earth2 empty latitudes (pre-flight passes)
        res_empty_lats = query_nvidia_nim("Earth2-FourCastNet", {"latitudes": []})
        assert res_empty_lats["success"] is True

        # Case 5: Execute with NIM API key enabled
        mock_post.return_value = mock_resp_esm
        res_api = query_nvidia_nim("BioNeMo-ESM2", {"sequence": "MKTLLILAVV"})
        assert res_api["success"] is True



def test_sundials_solver_fallbacks_and_exceptions():
    """Verify solver parameter validation, python integration convergence retry, and rust mocks."""
    # Case 1: Unknown ODE system
    res = sundials_cvode_solver("non_existent_ode", (0.0, 1.0), [1.0])
    assert res["success"] is False
    assert "Unknown system" in res["message"]

    # Case 2: Method validation ValueError
    res_meth = sundials_cvode_solver("lorenz", (0.0, 1.0), [1.0, 1.0, 1.0], method="Euler")
    assert res_meth["success"] is False
    assert "Adams" in res_meth["message"]

    # Case 3: Stiff blow-up overflow retry in Python fallback solver
    # We monkeypatch the lorenz RHS function to raise OverflowError
    original_rhs = _SYSTEM_REGISTRY["lorenz"]["rhs"]
    _SYSTEM_REGISTRY["lorenz"]["rhs"] = MagicMock(side_effect=OverflowError)
    try:
        res_python = _solve_python_fallback("lorenz", (0.0, 1.0), [1.0, 1.0, 1.0])
        assert res_python.success is True  # Solver returns partial trajectory safely
    finally:
        _SYSTEM_REGISTRY["lorenz"]["rhs"] = original_rhs

    # Case 4: Infinity check retry loop
    # We monkeypatch lorenz RHS to return infinity derivatives
    _SYSTEM_REGISTRY["lorenz"]["rhs"] = MagicMock(return_value=[float("inf"), float("inf"), float("inf")])
    try:
        res_retry = _solve_python_fallback("lorenz", (0.0, 1.0), [1.0, 1.0, 1.0])
        assert len(res_retry.t) == 2  # Fails to recover and stops with [0.0, 0.0]
    finally:
        _SYSTEM_REGISTRY["lorenz"]["rhs"] = original_rhs

    # Case 5: Rust solver subprocess execution mock
    with patch("shutil.which", return_value="/usr/bin/rusty_sundials"):
        # Mock successful Rust JSON output
        mock_output = {
            "success": True,
            "t": [0.0, 1.0],
            "y": [[1.0, 1.0], [2.0, 2.0]],
            "stats": {"num_steps": 12, "num_func_evals": 15, "num_jac_evals": 1, "num_error_test_failures": 0, "final_step_size": 0.1},
            "system": "lotka_volterra",
            "method": "BDF"
        }
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=json.dumps(mock_output), stderr="")):
            res_rust = sundials_cvode_solver("lotka_volterra", (0.0, 1.0), [1.0, 1.0])
            assert res_rust["success"] is True
            assert res_rust["stats"]["num_steps"] == 12

        # Mock Rust Solver exit failure
        with patch("subprocess.run", return_value=MagicMock(returncode=1, stderr="Segment fault in SUNDIALS BDF")):
            res_fail = sundials_cvode_solver("lotka_volterra", (0.0, 1.0), [1.0, 1.0])
            assert res_fail["success"] is False
            assert "exited with code 1" in res_fail["message"]

        # Mock Rust Solver Timeout
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=[], timeout=120)):
            res_timeout = sundials_cvode_solver("lotka_volterra", (0.0, 1.0), [1.0, 1.0])
            assert res_timeout["success"] is False
            assert "timed out" in res_timeout["message"]

        # Mock Rust solver bad JSON
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="bad_json", stderr="")):
            res_json = sundials_cvode_solver("lotka_volterra", (0.0, 1.0), [1.0, 1.0])
            assert res_json["success"] is False
            assert "JSONDecodeError" in res_json["message"] or "parse solver output" in res_json["message"].lower()


# ---------------------------------------------------------------------------
# 4. Galois & Cortex Tests (`agents/galois/*`)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_galois_agent_act_timeout():
    """Verify Galois route resolution fallbacks."""
    agent = GaloisAgent()
    agent._tools = {
        **agent._tools,
        "conjecture_generator": MagicMock(side_effect=Exception("Conjecture model dead"))
    }
    res = await agent.run("Construct a new theory of arithmetic")
    assert "error" in res.answer["conjecture_generator"]


def test_cortex_hemispheres_and_decays():
    """Verify formal and creative gating thresholds, decays, and proposals."""
    # Formal Mode routing
    tensor_formal = GaloisRoutingTensor(sigma_ded=0.6, sigma_gen=0.4)
    assert tensor_formal.hemisphere == HemisphereMode.FORMAL

    # Balanced Mode routing
    tensor_bal = GaloisRoutingTensor(sigma_ded=0.5, sigma_gen=0.5)
    assert tensor_bal.hemisphere == HemisphereMode.BALANCED

    # Cortex decays and escalations
    cortex = GaloisCortexConfig()
    cortex.routing.sigma_ded = 0.20
    cortex.routing.escalate_to_formal()
    assert cortex.routing.sigma_ded == 0.50
    assert cortex.routing.hemisphere == HemisphereMode.ESCALATED_FORMAL

    cortex.routing.relax_to_creative(decay_rate=0.20)
    assert cortex.routing.sigma_ded == 0.30

    # Self-improvement adaptive tuning rates
    cortex.total_conjectures = 4
    cortex.verified_conjectures = 4
    cortex.record_conjecture("theorem test : 1=1", ConjectureConfidence.HIGH, verified=True)
    # Success rate = 5 / 5 = 100% -> should reduce sigma_ded to afford more creativity!
    assert cortex.routing.sigma_ded == 0.25  # 0.30 - 0.05

    cortex.routing.sigma_ded = 0.25
    cortex.total_conjectures = 4
    cortex.verified_conjectures = 0
    cortex.record_conjecture("failed theorem", ConjectureConfidence.LOW, verified=False)
    # Success rate = 0 / 5 = 0% -> should increase sigma_ded
    assert cortex.routing.sigma_ded == 0.30  # 0.25 + 0.05

    # Propose SymBrain V5 proposals
    proposal = cortex.propose_v5_upgrade()
    assert proposal["agent"] == "galois"
    assert proposal["metrics"]["success_rate"] == 0.0


def test_cortex_novelty_distance_checks():
    """Verify semantic distance bounds, empty vector checks, and zero-norms in Cortex."""
    cortex = GaloisCortexConfig()

    # Empty listings
    assert cortex.routing.compute_novelty_bonus([], [[0.1, 0.2]]) == 0.75
    assert cortex.routing.compute_novelty_bonus([0.1], []) == 0.75

    # Zero norms
    assert cortex.routing.compute_novelty_bonus([0.0, 0.0], [[0.1, 0.2]]) == 0.0
    assert cortex.routing.compute_novelty_bonus([0.1, 0.2], [[0.0, 0.0]]) == 0.0


def test_proof_sketcher_strategies_and_compilers():
    """Test topological strategies, check with Lean options, and compiler exit error mocks."""
    # Tactic strategy detections
    assert _detect_strategy("For all induction models") == ProofStrategy.INDUCTION
    assert _detect_strategy("Symmetry homeomorphic to space") == ProofStrategy.TOPOLOGICAL
    assert _detect_strategy("Impossible logic contradiction") == ProofStrategy.CONTRADICTION

    # Math syntax stubs
    conjectures = [
        "x ≤ y bound",
        "there exists an element",
        "A isomorphic to B",
    ]
    for c in conjectures:
        code = _build_lean4_sketch("my_test_thm", c, "nl desc", ProofStrategy.ALGEBRAIC)
        assert "sorry" in code

    # Compiler errors and file not found in sketcher
    with patch("subprocess.run", side_effect=FileNotFoundError):
        res_fnf = sketch_proof("1 = 1", check_with_lean=True, lean4_binary="/invalid/lean")
        assert "not found" in res_fnf.sketches[0].diagnostics[0]

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=[], timeout=30)):
        res_to = sketch_proof("1 = 1", check_with_lean=True, lean4_binary="/usr/bin/lean")
        assert "timed out" in res_to.sketches[0].diagnostics[0]


def test_self_improvement_insufficient_data():
    """Verify Galois self improvement rules for low historical records."""
    report = plan_self_improvement(conjecture_history=[])
    assert report.performance_summary["status"] == "insufficient_data"

    # History size < 3 for sigma optimization
    report_low = plan_self_improvement(
        conjecture_history=[{"conjecture": "1=1", "confidence": "high", "verified": True}],
        current_sigma_ded=0.25
    )
    assert "Insufficient data" in report_low.sigma_recommendation["reason"]


# ---------------------------------------------------------------------------
# 5. Hypatie & Socrates Agents (`agents/hypatie/*`, `agents/socrates/*`)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_hypatie_vault_failure_handling():
    """Verify Hypatie handles remote REST cataloging network errors gracefully."""
    agent = HypatieAgent()
    # Mock archive vault tool directly in the local instantiated agent
    agent._tools = {
        **agent._tools,
        "archive_vault": MagicMock(side_effect=Exception("Alexandrie down"))
    }
    res = await agent.run("Catalog this theory")
    assert "error" in res.answer["archive_vault"]
    assert "down" in res.answer["archive_vault"]["error"].lower()


def test_astrolabe_navigator_empty_alignments():
    """Verify astrolabe alignment navigator logic handles zero matches."""
    # Point server's hub to an empty catalog
    original_catalog = hub._catalog
    hub._catalog = {}
    try:
        with patch.object(AlexandrieHub, "search_vault", return_value=[]):
            res = navigate_astrolabe("quantum cosmology", required_alignment=0.85)
            assert len(res.alignments) == 0
    finally:
        hub._catalog = original_catalog


@pytest.mark.anyio
async def test_socrates_dialectic_non_convergence():
    """Verify Socrates dialectic orchestration terminates gracefully on non-convergence."""
    engine = DialecticEngine(max_iterations=1)
    
    # Mock Galileo and Euler runs to return non-convergent arguments
    galileo_res = AgentResult(answer={"observations": {"sundials_solver": {"success": True}}}, confidence=0.8)
    euler_res = AgentResult(answer={"status": "REFUTED", "objections": ["contradiction in mass"]}, confidence=0.9)

    galileo_agent = GalileoAgent()
    euler_agent = EulerAgent()

    with patch.object(GalileoAgent, "run", return_value=galileo_res), \
         patch.object(EulerAgent, "run", return_value=euler_res):
        
        res = await engine.run("Test hypothesis", galileo_agent, euler_agent)
        assert res.converged is False
        assert "Dialectic did not converge" in res.synthesis


# ---------------------------------------------------------------------------
# 6. Turing Optimizer Tool (`agents/turing/tools/*`)
# ---------------------------------------------------------------------------

def test_turing_optimizer_various_bottlenecks():
    """Verify that turing parameter tuning handles memory, solver, and network boundaries."""
    diag_solver = {"diagnosed_bottleneck": "solver-bound", "scratch_efficiency_ratio": 0.10}
    res_solver = optimize_runtime_parameters(diag_solver, budget_remaining_usd=80.0)
    assert res_solver["optimized_parameters"]["sundials_rtol"] >= 1e-5

    diag_mem = {"diagnosed_bottleneck": "memory-bound", "scratch_efficiency_ratio": 0.85}
    res_mem = optimize_runtime_parameters(diag_mem, budget_remaining_usd=60.0)
    assert res_mem["optimized_parameters"]["mcts_max_depth"] <= 3

    diag_net = {"diagnosed_bottleneck": "network-bound", "scratch_efficiency_ratio": 0.05}
    res_net = optimize_runtime_parameters(diag_net, budget_remaining_usd=30.0)
    assert res_net["optimized_parameters"]["dynamic_gating_threshold"] >= 0.60


# ---------------------------------------------------------------------------
# 7. Alexandrie Backend Server (`alexandrie/*`)
# ---------------------------------------------------------------------------

def test_alexandrie_catalog_parsing_exceptions(tmp_path: pathlib.Path):
    """Verify Hub recovers safely from invalid catalog files and missing vault records."""
    # Case 1: Corrupted JSON catalog file
    catalog_file = tmp_path / "catalog.json"
    catalog_file.write_text("invalid_json_content", encoding="utf-8")
    
    corrupt_hub = AlexandrieHub(vault_root=str(tmp_path))
    assert corrupt_hub._catalog == {}

    # Case 2: File missing from vault on retrieve_artifact
    corrupt_hub.store_artifact("dummy_01", "Dummy work", "payload", ArtifactType.PROOF, RoomType.OPEN_ACCESS, "test_scientist")
    # Delete the written text file
    txt_file = tmp_path / "open_access" / "proof" / "dummy_01.txt"
    txt_file.unlink()
    
    assert corrupt_hub.retrieve_artifact("dummy_01") is None


def test_fastapi_server_validation_and_database_errors(tmp_path: pathlib.Path):
    """Test REST validation failures, bad room requests, and mock storage crashes on server."""
    original_root = hub.root
    hub.__init__(vault_root=str(tmp_path))

    try:
        with TestClient(app) as client:
            # Case 1: Invalid artifact type
            body_bad_type = {
                "id": "invalid_art",
                "title": "Bad Type Artifact",
                "payload": "code",
                "artifact_type": "invalid_category",
                "room_type": "open_access"
            }
            res_bad_type = client.post("/vault/artifact", json=body_bad_type)
            assert res_bad_type.status_code == 400
            assert "Invalid artifact type" in res_bad_type.json()["detail"]

            # Case 2: Invalid room type in post
            body_bad_room = {
                "id": "invalid_art",
                "title": "Bad Room Artifact",
                "payload": "code",
                "artifact_type": "proof",
                "room_type": "invalid_room"
            }
            res_bad_room = client.post("/vault/artifact", json=body_bad_room)
            assert res_bad_room.status_code == 400
            assert "Invalid room type" in res_bad_room.json()["detail"]

            # Case 3: Invalid room type in retrieve
            res_get_bad = client.get("/vault/artifact/nim_adapter_v1?room=invalid_room")
            assert res_get_bad.status_code == 400
            assert "Invalid room type" in res_get_bad.json()["detail"]

            # Case 4: Storage failure (Internal Server Error)
            with patch.object(AlexandrieHub, "store_artifact", side_effect=Exception("Disk full")):
                body_ok = {
                    "id": "failed_art",
                    "title": "Failing Storage Ingestion",
                    "payload": "code",
                    "artifact_type": "proof",
                    "room_type": "open_access"
                }
                res_crash = client.post("/vault/artifact", json=body_ok)
                assert res_crash.status_code == 500
                assert "Inward storage failure" in res_crash.json()["detail"]

    finally:
        hub.__init__(vault_root=str(original_root))


# ---------------------------------------------------------------------------
# 8. Extra Coverage Enhancers
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_socrates_dialectic_elenchus_and_maieutic():
    """Verify elenchus and maieutic cycles in DialecticEngine directly."""
    engine = DialecticEngine()
    
    mock_euler = MagicMock()
    # Mocking euler.run to return a result
    mock_result_euler = AgentResult(answer={"status": "REFUTED", "objections": ["contradiction"]}, confidence=0.85)
    async def mock_run_euler(*args, **kwargs):
        return mock_result_euler
    mock_euler.run = mock_run_euler
    
    res_elenchus = await engine.run_elenchus("Hypothesis", {"data": 123}, mock_euler)
    assert res_elenchus["refuted"] is True
    assert res_elenchus["objections"] == ["contradiction"]
    assert res_elenchus["confidence"] == 0.85
    
    mock_galileo = MagicMock()
    mock_result_galileo = AgentResult(answer="Maieutic discovery", confidence=0.9, cost_usd=0.05)
    async def mock_run_galileo(*args, **kwargs):
        return mock_result_galileo
    mock_galileo.run = mock_run_galileo
    
    res_maieutic = await engine.run_maieutic("Question?", {"context": 456}, mock_galileo)
    assert res_maieutic["discovery"] == "Maieutic discovery"
    assert res_maieutic["confidence"] == 0.9
    assert res_maieutic["cost_usd"] == 0.05


@pytest.mark.anyio
async def test_socrates_agent_complexity_research_and_prompt_stub():
    """Verify Socrates agent handles RESEARCH complexity and default prompt loading."""
    # 1. RESEARCH complexity check
    agent = SocratesAgent()
    res_research = await agent.run("Characterise and prove this novel philosophical hypothesis")
    assert res_research.answer["complexity"] == "research"
    assert "dialectic" in res_research.answer["observations"]
    
    # 2. Fallback prompt stub loading
    with patch("agents.socrates.agent._SYSTEM_PROMPT_PATH") as mock_path:
        mock_path.exists.return_value = False
        fallback_prompt = agent._load_system_prompt()
        assert "You are Socrates" in fallback_prompt


def test_turing_profiler_and_optimizer_edge_cases():
    """Verify Turing profiler network-bound, memory-bound bottleneck classifications and optimizations."""
    # 1. Profile execution trace: network-bound
    trace_network = {
        "mcts_nodes": 10,
        "solver_evals": 10,
        "latency_ms": 2500.0,
        "token_count": 20,
        "scratch_allocated_bytes": 1000,
    }
    res_network = profile_execution_trace(trace_network)
    assert res_network["diagnosed_bottleneck"] == "network-bound"
    assert any("remote NIM API" in w for w in res_network["warnings"])
    
    # 2. Profile execution trace: memory-bound (scratch zone efficiency > 0.85)
    trace_memory = {
        "mcts_nodes": 10,
        "solver_evals": 10,
        "latency_ms": 100.0,
        "token_count": 10,
        "scratch_allocated_bytes": int(2 * 1024 * 1024 * 1024 * 0.9),  # 90% capacity
    }
    res_memory = profile_execution_trace(trace_memory)
    assert res_memory["diagnosed_bottleneck"] == "memory-bound"
    assert any("scratch zone memory usage is critical" in w for w in res_memory["warnings"])
    
    # 3. Optimize parameters: network-bound bottleneck
    diag_network = {"diagnosed_bottleneck": "network-bound", "scratch_efficiency_ratio": 0.01}
    res_opt_network = optimize_runtime_parameters(diag_network, budget_remaining_usd=80.0)
    assert res_opt_network["optimized_parameters"]["dynamic_gating_threshold"] == 0.75
    
    # 4. Optimize parameters: memory-bound bottleneck / scratch eff > 0.70
    diag_memory = {"diagnosed_bottleneck": "balanced", "scratch_efficiency_ratio": 0.75}
    res_opt_memory = optimize_runtime_parameters(diag_memory, budget_remaining_usd=80.0)
    assert res_opt_memory["optimized_parameters"]["mcts_max_depth"] == 3
    
    # 5. Optimize parameters: moderate budget [10.0, 50.0]
    diag_bal = {"diagnosed_bottleneck": "balanced", "scratch_efficiency_ratio": 0.05}
    res_opt_budget = optimize_runtime_parameters(diag_bal, budget_remaining_usd=25.0)
    assert res_opt_budget["optimized_parameters"]["mcts_max_depth"] == 4
    assert res_opt_budget["optimized_parameters"]["quantization_tier"] == "INT8_GPTQ"


def test_hypatie_catalog_scientific_work_exception():
    """Verify Hypatie handles remote REST cataloging network errors gracefully on exception."""
    import httpx
    # Enable API URL
    with patch.dict(os.environ, {"ALEXANDRIE_API_URL": "http://localhost:8080"}):
        # Mock httpx.post to raise an exception
        with patch("httpx.post", side_effect=httpx.RequestError("Connection refused")):
            res = catalog_scientific_work(
                artifact_id="vault_test_exc",
                title="Exception Proof",
                payload="theorem my_proof : True := trivial",
                artifact_type="proof",
                tags=["hypatie", "exception"]
            )
            assert res.artifact_id == "vault_test_exc"
            assert res.metadata.sha256_hash is not None


def test_alexandrie_catalog_silent_keyerror():
    """Verify search_vault handles invalid room and type parameter strings silently."""
    with TestClient(app) as client:
        response = client.get("/vault/search?query=test&room=invalid_room&type=invalid_type")
        assert response.status_code == 200
        # Results should be returned normally, filtering is ignored due to KeyError catch
        assert isinstance(response.json(), list)


def test_alexandrie_hub_binary_artifact(tmp_path: pathlib.Path):
    """Verify store and retrieve of binary files in AlexandrieHub."""
    import hashlib
    hub_local = AlexandrieHub(vault_root=str(tmp_path))
    binary_payload = b"\x00\x01\x02\x03\xff"
    
    metadata = hub_local.store_artifact(
        artifact_id="bin_artifact_test",
        title="Binary Weights",
        content=binary_payload,
        artifact_type=ArtifactType.MODEL,
        room_type=RoomType.OPEN_ACCESS,
        creator="turing_optimizer",
    )
    
    assert metadata.id == "bin_artifact_test"
    assert metadata.sha256_hash == hashlib.sha256(binary_payload).hexdigest()
    
    # Retrieve and verify content is exactly bytes
    retrieved = hub_local.retrieve_artifact("bin_artifact_test", RoomType.OPEN_ACCESS)
    assert retrieved is not None
    ret_metadata, ret_content = retrieved
    assert ret_metadata.id == "bin_artifact_test"
    assert isinstance(ret_content, bytes)
    assert ret_content == binary_payload


@pytest.mark.anyio
async def test_socrates_agent_autoresearch_loop():
    """Verify Socrates agent closed-loop Karpathy-style autoresearch iteration and self-correction."""
    agent = SocratesAgent()
    
    # Define two sequential mock return values for agent.run
    mock_run_1 = AgentResult(answer={"synthesis": "objection path", "observations": {}}, confidence=0.60)
    mock_run_2 = AgentResult(answer={"synthesis": "perfect converged path", "observations": {}}, confidence=0.90)
    
    with patch.object(SocratesAgent, "run", side_effect=[mock_run_1, mock_run_2]) as mock_run:
        res = await agent.run_autoresearch(
            research_goal="Synthesize stable BDF solvers",
            max_refinement_cycles=2
        )
        assert res["status"] == "CONVERGED"
        assert res["cycles_run"] == 2
        assert res["final_confidence"] == 0.90
        assert res["synthesis"] == "perfect converged path"
        assert mock_run.call_count == 2


