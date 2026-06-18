# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Integration test for the Sentinel Cybersecurity pipeline.

Traces Bourbaki mapping Solidity to BitVec, Galois MCTS failing, Galileo SAT solving
the failed invariant, Descartes synthesizing the exploit, and Champollion creating
the markdown advisory.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base import AgentConfig, AgentRole
from agents.bourbaki.agent import BourbakiAgent
from agents.bourbaki.codegen.type_mapper import TypeMapper
from agents.galileo.agent import GalileoAgent
from agents.descartes.agent import DescartesAgent
from agents.champollion.agent import ChampollionAgent
from agents.aristotle.agent import AristotleAgent

def test_type_mapper_bitvec():
    """Verify that Solidity uint256 is mapped to BitVec 256 for machine arithmetic."""
    mapper = TypeMapper()
    assert mapper.map_type("uint256", "solidity") == "Std.Data.BitVec 256"
    assert mapper.map_type("uint8", "solidity") == "Std.Data.BitVec 8"

def test_aristotle_epistemic_guillotine():
    """Verify that Aristotle blocks proofs containing axioms/sorry/opaque."""
    agent = AristotleAgent()
    
    clean_proof = "theorem add_comm (a b : Nat) : a + b = b + a := Nat.add_comm a b"
    assert agent.audit_epistemic_integrity(clean_proof) is True
    
    smuggled_axiom = "axiom saw_asymptotic_form_Z3 : some_unproven_axiom"
    assert agent.audit_epistemic_integrity(smuggled_axiom) is False
    
    sorry_proof = "theorem fermat : x^n + y^n = z^n := sorry"
    assert agent.audit_epistemic_integrity(sorry_proof) is False

@pytest.mark.asyncio
async def test_galileo_z3_difference_basis():
    """Verify Galileo's Z3 solver resolves difference basis parameters."""
    agent = GalileoAgent()
    
    # Run the Z3 solver on the difference basis goal
    result = await agent.run(
        query="diff_basis N=6 K=4",
        theory="diff_basis",
        target_n=6,
        target_k=4
    )
    
    assert result.answer["status"] == "success"
    assert "tactic" in result.answer
    assert "use {" in result.answer["tactic"]

@pytest.mark.asyncio
async def test_cybersecurity_pipeline_flow():
    """Simulates the full Bourbaki -> Galois -> Galileo -> Descartes -> Champollion pipeline."""
    # 1. Bourbaki type mapping
    mapper = TypeMapper()
    mapped_type = mapper.map_type("uint256", "solidity")
    assert mapped_type == "Std.Data.BitVec 256"

    # 2. Galois fails to prove invariant (e.g., addition overflow check)
    failed_invariant = "h : amount > balance ⊢ False"

    # 3. Galileo intercepts the failed invariant and runs Z3 to find the overflow condition
    galileo = GalileoAgent()
    galileo_result = await galileo.run(query=failed_invariant)
    assert galileo_result.answer["status"] == "success"
    counter_model = galileo_result.answer["counter_model"]
    assert counter_model is not None
    assert "deposit" in counter_model

    # 4. Descartes synthesizes the exploit payload
    descartes = DescartesAgent()
    
    # Mock LLM call to return deterministic JSON exploit vector
    from unittest.mock import AsyncMock
    descartes._call_llm = AsyncMock(return_value='{"exploit_code": "deposit(255)", "description": "Integer overflow in deposit function allows balance manipulation.", "remediation": "Ensure checked arithmetic is enforced or use OpenZeppelin SafeMath."}')
    
    exploit_vector = await descartes.synthesize_exploit(
        dead_end_state=failed_invariant,
        source_function="deposit"
    )
    assert exploit_vector.vulnerability_type == "integer_overflow"
    assert exploit_vector.cwe_id == "CWE-190"
    
    # 5. Champollion produces the markdown zero-day advisory
    champollion = ChampollionAgent()
    advisory = champollion.generate_advisory(
        contract_name="VulnerableVault",
        vulnerability_type=exploit_vector.vulnerability_type,
        severity=exploit_vector.severity,
        exploit_description="Integer overflow in deposit function allows balance manipulation.",
        exploit_payload=exploit_vector.exploit_payload,
        affected_function="deposit",
        remediation="Ensure checked arithmetic is enforced or use OpenZeppelin SafeMath.",
        cwe_id=exploit_vector.cwe_id,
        lean_contradiction=failed_invariant,
    )
    
    assert "VulnerableVault" in advisory
    assert "VULNERABILITY DETECTED" in advisory
    assert "CWE-190" in advisory
    assert "deposit" in advisory
