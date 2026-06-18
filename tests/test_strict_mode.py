# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Unit tests for Agora strict mode, FinOps circuit breakers, GPU energy tracking, and MCTS Lean 4 pruning."""

import os
import pytest
from unittest.mock import patch, MagicMock
from agents.euler.tools.lean4_compiler import compile_lean4_proof
from agents.galileo.tools.nvidia_nim import query_nvidia_nim
from agents.common.budget_guard import BudgetGuard, BudgetExceededError
from agents.common.telemetry import AgentTelemetry
from agents.galois.tools.mcts_reasoner import ThoughtNode, expand_node, MCTSReasoner

def test_strict_mode_lean4_compilation(monkeypatch):
    """Verify compile_lean4_proof raises RuntimeError under AGORA_STRICT_MODE=1 on compilation failure."""
    monkeypatch.setenv("AGORA_STRICT_MODE", "1")
    # Patch subprocess to return non-zero exit code
    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = "Type error in theorem comm"
        mock_run.returnvalue = mock_proc
        
        with patch("shutil.which", return_value="/usr/bin/lean"):
            with pytest.raises(RuntimeError, match="Lean 4 compilation failed under AGORA_STRICT_MODE"):
                compile_lean4_proof("theorem dummy : True := sorry")

def test_strict_mode_nim_api_failure(monkeypatch):
    """Verify NIM API caller raises RuntimeError under AGORA_STRICT_MODE=1 on failure."""
    monkeypatch.setenv("AGORA_STRICT_MODE", "1")
    monkeypatch.setenv("NIM_API_KEY", "dummy_key")
    
    with patch("httpx.Client.post") as mock_post:
        mock_post.side_effect = RuntimeError("Connection timed out")
        
        with pytest.raises(RuntimeError, match="Real NIM API Failure"):
            query_nvidia_nim("BioNeMo-ESM2", {"sequence": "MVLSPADKT"})

def test_unconditional_nim_key_error(monkeypatch):
    """Verify query_nvidia_nim raises ValueError unconditionally if key is missing."""
    monkeypatch.delenv("NIM_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_NIM_API_KEY", raising=False)
    with patch("agents.galileo.tools.nvidia_nim.NIM_API_KEY", ""):
        with pytest.raises(ValueError, match="NIM_API_KEY missing"):
            query_nvidia_nim("BioNeMo-ESM2", {"sequence": "MVLSPADKT"})

def test_budget_guard_finops_strict_mode(monkeypatch):
    """Verify BudgetGuard raises BudgetExceededError and triggers teardown in strict mode when limits exceeded."""
    monkeypatch.setenv("AGORA_STRICT_MODE", "1")
    
    guard = BudgetGuard(cumulative_cost=15.0) # threshold is 10.0
    
    with patch("agents.turing.tools.deployment_manager.tear_down_deployment") as mock_teardown:
        with pytest.raises(BudgetExceededError, match="FinOps billing limit exceeded"):
            guard.check_budget(1.0)
        mock_teardown.assert_called_with(service_name="symbrain_swarm")

def test_agent_telemetry_gpu_energy():
    """Verify AgentTelemetry tracks GPU energy in Joules."""
    telemetry = AgentTelemetry(agent_name="test_agent")
    telemetry.record_gpu_energy(120.5)
    assert telemetry.gpu_energy_joules == 120.5
    summary = telemetry.summary()
    assert summary["gpu_energy_joules"] == 120.5
    
    telemetry.reset()
    assert telemetry.gpu_energy_joules == 0.0

def test_mcts_lean_pruning(monkeypatch):
    """Verify MCTS expand_node prunes invalid Lean proposals."""
    node = ThoughtNode(problem_statement="Prove Commutativity", thought_step="Root")
    
    # We patch compile_lean4_proof to return success=False with type mismatch
    with patch("agents.euler.tools.lean4_compiler.compile_lean4_proof") as mock_compile:
        mock_compile.return_value = {
            "success": False,
            "stderr": "type mismatch in application"
        }
        
        # Propose a step that contains Lean tactics
        class MockResponse:
            text = "STEP: by rw [add_comm]"
            
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = MockResponse()
        
        expand_node(mock_client, node, expansion_width=1)
        
        assert len(node.children) == 1
        child = node.children[0]
        assert child.is_terminal is True
        assert child.total_value == -10.0
        assert child.predicted_value == -10.0
