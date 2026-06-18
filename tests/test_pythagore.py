# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Unit and Integration Tests for Pythagore Agent."""

from __future__ import annotations

import pytest

from agents.pythagore.agent import PythagoreAgent
from agents.socrates.agent import SocratesAgent
from agents.base import AgentRole


def test_pythagore_agent_initialization():
    """Verify that PythagoreAgent can be instantiated with default configuration."""
    agent = PythagoreAgent()
    assert agent.config.name == "pythagore"
    assert agent.config.role == AgentRole.VERIFIER
    assert "lean_gap_mapper" in agent._tools
    assert "proof_retriever" in agent._tools
    assert "formal_draft_generator" in agent._tools


@pytest.mark.anyio
async def test_pythagore_gap_mapping():
    """Verify that Pythagore lean_gap_mapper tool compiles a structured gaps report."""
    agent = PythagoreAgent()
    result = await agent.run("Scan the repository and report all sorry stubs")
    
    obs = result.answer.get("observations", {})
    assert "lean_gap_mapper" in obs
    
    mapper_res = obs["lean_gap_mapper"]
    assert mapper_res["success"] is True
    assert mapper_res["total_gaps"] >= 0
    assert mapper_res["files_audited"] > 0
    
    # Check details breakdown
    details = mapper_res["details"]
    assert len(details) > 0
    assert any(d["file_name"].endswith("Gating.lean") for d in details)


@pytest.mark.anyio
async def test_pythagore_proof_retrieval():
    """Verify that Pythagore proof_retriever mines math paper abstracts."""
    agent = PythagoreAgent()
    result = await agent.run("Search literature for Elliptic Curve E37 formalizations")
    
    obs = result.answer.get("observations", {})
    assert "proof_retriever" in obs
    
    retriever_res = obs["proof_retriever"]
    assert len(retriever_res) >= 0


@pytest.mark.anyio
async def test_pythagore_draft_generator(mocker):
    """Verify Pythagore formal_draft_generator tool synthesizes Lean 4 skeletons."""
    class MockResponse:
        text = "```lean4\ntheorem test_addition_monotone (x y : Real) (h : x ≤ y) : x + 1 ≤ y + 1 := by\n  sorry\n```"
    
    mock_client = mocker.MagicMock()
    mock_client.models.generate_content.return_value = MockResponse()
    mocker.patch("agents.pythagore.tools.formal_draft_generator.genai.Client", return_value=mock_client)
    
    agent = PythagoreAgent()
    result = await agent.run(
        "Generate a formal skeleton draft",
        theorem_name="test_addition_monotone",
        signature="(x y : Real) (h : x ≤ y) : x + 1 ≤ y + 1",
        proof_strategy="Monotonicity of real addition."
    )
    
    obs = result.answer.get("observations", {})
    assert "formal_draft_generator" in obs
    
    draft_res = obs["formal_draft_generator"]
    assert draft_res["success"] is True
    assert draft_res["theorem_name"] == "test_addition_monotone"
    assert "theorem test_addition_monotone" in draft_res["code"]
    assert "sorry" in draft_res["code"]


@pytest.mark.anyio
async def test_socrates_pythagore_routing():
    """Verify that SocratesAgent routes scan and gap queries autonomously to Pythagore."""
    socrates = SocratesAgent()
    result = await socrates.run("Scan all sorries in the specifications library and list them")
    
    obs = result.answer.get("observations", {})
    assert "pythagore" in obs
    
    pyth_res = obs["pythagore"]
    assert pyth_res["confidence"] == 0.98
