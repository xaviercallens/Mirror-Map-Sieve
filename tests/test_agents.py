# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Unit and integration tests for the Socratic Agora cognitive agents and tools."""

from __future__ import annotations

import os
import pathlib
import pytest

from agents.base import AgentConfig, AgentRole
from agents.galileo.agent import GalileoAgent
from agents.galileo.tools.data_integrity import validate_scientific_data_integrity
from agents.galileo.tools.cost_estimator import estimate_cost
from agents.galileo.tools.nvidia_nim import query_nvidia_nim
from agents.galileo.tools.sundials_solver import sundials_cvode_solver
from agents.euler.agent import EulerAgent
from agents.euler.tools.skeptical_auditor import audit_demonstration
from agents.euler.tools.leanabell_prover import leanabell_prove_theorem
from agents.euler.tools.lean4_compiler import compile_lean4_proof
from agents.euler.tools.deepproblog_gate import evaluate_probabilistic_query
from agents.galois.agent import GaloisAgent
from agents.galois.symbrain.cortex_v4 import GaloisComplexityClassifier, GaloisRoutingTensor
from agents.galois.tools.conjecture_generator import generate_conjectures
from agents.galois.tools.proof_sketcher import sketch_proof
from agents.galois.tools.self_improvement import plan_self_improvement
from agents.hypatie.agent import HypatieAgent
from agents.hypatie.tools.archive_vault import catalog_scientific_work
from agents.socrates.agent import SocratesAgent


# ---------------------------------------------------------------------------
# Galileo Tools Tests
# ---------------------------------------------------------------------------

def test_data_integrity_validation():
    """Verify Galileo's Benford's Law and noise integrity checks."""
    # Compliant data (Benford-like distribution)
    compliant_data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 1.1, 1.2, 2.1, 3.1]
    res_comp = validate_scientific_data_integrity(compliant_data)
    assert res_comp["passed"] is True
    assert not res_comp["errors"]

    # Non-compliant / manual / integer-heavy data
    manual_data = [5.0, 5.0, 5.0, 5.0, 5.0, 5.0]
    res_manual = validate_scientific_data_integrity(manual_data)
    assert res_manual["passed"] is False
    assert any("manual entry" in i.lower() for i in res_manual["warnings"])


def test_cost_estimator():
    """Verify GCP serverless billing checks and min_replicas compliance."""
    # Compliant L4 GPU
    res_l4 = estimate_cost(gpu_type="L4", hours=10.0, min_replicas=0, replicas=1)
    assert res_l4["total_cost"] == 7.0
    assert res_l4["within_experiment_budget"] is True
    assert res_l4["min_replicas_compliant"] is True

    # Budget violation (> $100)
    res_violation = estimate_cost(gpu_type="A100-80GB", hours=50.0, min_replicas=0, replicas=1)
    assert res_violation["within_experiment_budget"] is False

    # Serverless violation (min_replicas > 0)
    res_serverless = estimate_cost(gpu_type="L4", hours=1.0, min_replicas=1, replicas=1)
    assert res_serverless["min_replicas_compliant"] is False
    assert "violates serverless policy" in res_serverless["recommendation"]


def test_nvidia_nim_connector(monkeypatch):
    """Verify Modulus and BioNeMo connectors return physical invariant telemetry."""
    from unittest.mock import patch, MagicMock
    
    monkeypatch.setenv("NIM_API_KEY", "dummy_key")
    
    with patch("httpx.Client.post") as mock_post:
        # Mock BioNeMo-ESM2 response
        mock_resp_esm = MagicMock()
        mock_resp_esm.json.return_value = {
            "total_mass": 1100.0,
            "predicted_structure": "alpha_helix",
            "embeddings": [0.1] * 10
        }
        mock_post.return_value = mock_resp_esm
        
        res_esm = query_nvidia_nim("BioNeMo-ESM2", {"sequence": "MKTLLILAVV"})
        assert res_esm["success"] is True
        assert "sequence_validity" in res_esm["invariant_checks"]

        # Mock Modulus-NavierStokes response
        mock_resp_modulus = MagicMock()
        mock_resp_modulus.json.return_value = {
            "velocity_field": [[1.0, 0.5]],
            "pressure_field": [[101325.0]],
            "l2_residual": 1e-5,
            "iterations": 100
        }
        mock_post.return_value = mock_resp_modulus

        res_modulus = query_nvidia_nim("Modulus-NavierStokes", {"reynolds": 100})
        assert res_modulus["success"] is True
        assert "residual_convergence" in res_modulus["invariant_checks"]


def test_sundials_solver_bridge():
    """Verify CVODE integration solver bridge solves Lotka-Volterra dynamics."""
    # Solve standard Lotka-Volterra predator prey model
    res = sundials_cvode_solver("lotka_volterra", (0.0, 1.0), [1.0, 1.0])
    assert res["success"] is True
    assert len(res["y"]) > 0
    assert "num_steps" in res["stats"]


# ---------------------------------------------------------------------------
# Euler Tools Tests
# ---------------------------------------------------------------------------

def test_skeptical_auditor():
    """Verify Euler's skepticism triggers on vague terms and precision anomalies."""
    # Vague proof text
    res_vague = audit_demonstration("This is obviously true and trivially verified.")
    assert res_vague["passed"] is True  # Only warnings, no errors
    assert len(res_vague["issues"]) >= 2
    assert any("obviously" in i["message"] for i in res_vague["issues"])

    # Precise audit
    res_precise = audit_demonstration("The sequence x_n = 1/n converges to 0 as n -> infinity.")
    assert res_precise["passed"] is True
    assert not res_precise["issues"]


def test_leanabell_prover_trace():
    """Verify Leanabell Prover step evaluation trajectory."""
    result = leanabell_prove_theorem("theorem add_zero (n : Nat) : n + 0 = n")
    assert result.success is False  # Search depth reached
    assert result.total_steps == 5
    assert len(result.trajectory) == 5


def test_lean4_compiler_mock():
    """Verify Lean 4 compiler compilation diagnostics."""
    res = compile_lean4_proof("theorem my_proof : 1 = 1 := rfl")
    # By default, compiles via local lake environment stub
    assert "success" in res


def test_deepproblog_probabilistic_grounding():
    """Verify DeepProbLog continuous-to-discrete query gating."""
    res = evaluate_probabilistic_query(
        program="addition(X, Y, Z) :- digit(X, DX), digit(Y, DY), Z is DX + DY.",
        query="addition(img1, img2, 8)",
        neural_preds={"img1": {3: 0.9, 5: 0.1}, "img2": {5: 0.8, 3: 0.2}}
    )
    assert res["success"] is True
    assert res["probability"] > 0.0


# ---------------------------------------------------------------------------
# Galois & Cortex Tests
# ---------------------------------------------------------------------------

def test_cortex_classification():
    """Verify SymBrain Cortex v4 classification and gating."""
    classifier = GaloisComplexityClassifier()
    
    # Mathematical query
    complexity, mcts_mult = classifier.classify("Prove the RLCF convergence boundaries")
    assert 0.0 <= complexity <= 1.0
    assert mcts_mult >= 1.0
    
    # Simple query
    comp_simple, _ = classifier.classify("what is 5+5?")
    assert comp_simple < 0.40

    # Tensor invariants
    tensor = GaloisRoutingTensor(sigma_ded=0.10)
    assert tensor.sigma_ded >= 0.15  # Deductive floor enforced


def test_galois_tools():
    """Verify Galois conjecture generator and proof sketcher."""
    conj = generate_conjectures("quantum mechanics", creativity_level=0.8)
    assert len(conj.conjectures) > 0
    assert conj.conjectures[0].primary_domain is not None

    sketch = sketch_proof("1 = 1", strategy="constructive")
    assert len(sketch.sketches) > 0
    assert sketch.sketches[0].confidence > 0.0

    # Test self-improvement
    history = [
        {"conjecture": "1=1", "confidence": 0.9, "verified": True, "sigma_ded": 0.25, "sigma_gen": 0.75},
        {"conjecture": "2=2", "confidence": 0.8, "verified": False, "sigma_ded": 0.25, "sigma_gen": 0.75},
        {"conjecture": "3=3", "confidence": 0.8, "verified": True, "sigma_ded": 0.25, "sigma_gen": 0.75},
    ]
    report = plan_self_improvement(history)
    assert report.performance_summary["total_conjectures"] == 3
    assert "recommended_sigma_ded" in report.sigma_recommendation


# ---------------------------------------------------------------------------
# Hypatie & Library Tests
# ---------------------------------------------------------------------------

def test_hypatie_vault_archive(tmp_path: pathlib.Path):
    """Verify Hypatie's archival and serialization pipeline."""
    original_env = os.environ.get("ALEXANDRIE_VAULT_ROOT")
    os.environ["ALEXANDRIE_VAULT_ROOT"] = str(tmp_path)
    
    try:
        res = catalog_scientific_work(
            artifact_id="vault_test_01",
            title="Archived Proof",
            payload="theorem my_proof : True := trivial",
            artifact_type="proof",
            tags=["hypatie", "test"]
        )
        assert res.artifact_id == "vault_test_01"
        assert res.metadata.sha256_hash is not None

    finally:
        if original_env is not None:
            os.environ["ALEXANDRIE_VAULT_ROOT"] = original_env
        else:
            os.environ.pop("ALEXANDRIE_VAULT_ROOT", None)


# ---------------------------------------------------------------------------
# Agent Integration Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_galileo_agent_run():
    """Verify Galileo scientific agent execution."""
    agent = GalileoAgent()
    res = await agent.run("Perform simulation for Robertson kinetics")
    assert res.confidence > 0.0
    assert "sundials_solver" in res.answer


@pytest.mark.anyio
async def test_euler_agent_run():
    """Verify Euler skeptical agent execution."""
    agent = EulerAgent()
    res = await agent.run("Verify the mathematical proof of add_zero")
    assert res.confidence > 0.0
    assert "objections" in res.answer


@pytest.mark.anyio
async def test_galois_agent_run():
    """Verify Galois creative agent execution."""
    agent = GaloisAgent()
    res = await agent.run("Formulate a symmetry framework for RLCF")
    assert res.confidence == 0.8
    assert "conjecture_generator" in res.answer
    assert len(res.answer["conjecture_generator"].conjectures) > 0


@pytest.mark.anyio
async def test_hypatie_agent_run(tmp_path: pathlib.Path):
    """Verify Hypatie librarian agent execution."""
    original_env = os.environ.get("ALEXANDRIE_VAULT_ROOT")
    os.environ["ALEXANDRIE_VAULT_ROOT"] = str(tmp_path)
    
    try:
        agent = HypatieAgent()
        res = await agent.run("Catalog and archive the Socratic proof of conics")
        assert res.confidence == 0.95
        assert "archive_vault" in res.answer
    finally:
        if original_env is not None:
            os.environ["ALEXANDRIE_VAULT_ROOT"] = original_env
        else:
            os.environ.pop("ALEXANDRIE_VAULT_ROOT", None)


@pytest.mark.anyio
async def test_socrates_orchestrator_runs():
    """Verify Socrates orchestrates both direct and dialectic cycles."""
    socrates = SocratesAgent()

    # Simple/moderate direct query routing
    res_direct = await socrates.run("Estimate the GCP L4 GPU hosting cost for 12 hours")
    assert res_direct.answer["complexity"] == "moderate"
    assert "galileo" in res_direct.answer["observations"]

    # Full dialectic query routing (Verify/Validate)
    res_dial = await socrates.run("Verify the RLCF convergence parameters")
    assert res_dial.answer["complexity"] == "complex"
    assert "dialectic" in res_dial.answer["observations"]
