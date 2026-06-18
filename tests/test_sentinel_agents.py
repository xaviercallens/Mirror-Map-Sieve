# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Unit tests for the Sentinel Codex agents: Aristotle, Descartes, Champollion."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.aristotle.agent import AristotleAgent
from agents.descartes.agent import DescartesAgent, ExploitVector
from agents.champollion.agent import (
    ChampollionAgent,
    CertificateOfAssurance,
    ZeroDayAdvisory,
)


class TestAristotleAgent:
    """Tests for the Aristotle Semantic Guillotine."""

    def test_instantiation(self):
        agent = AristotleAgent()
        assert agent.config.name == "aristotle"
        assert agent.config.model == "gemini-2.5-flash"

    def test_stats_initial(self):
        agent = AristotleAgent()
        stats = agent.stats
        assert stats["approvals"] == 0
        assert stats["rejections"] == 0
        assert stats["total_reviews"] == 0

    def test_config_override(self):
        from agents.base import AgentConfig, AgentRole
        config = AgentConfig(
            name="aristotle_custom",
            model="gemini-2.5-pro",
            role=AgentRole.FILTER,
            budget_limit=20.0,
            project_budget=200.0,
            temperature=0.2,
        )
        agent = AristotleAgent(config=config)
        assert agent.config.name == "aristotle_custom"
        assert agent.config.temperature == 0.2


class TestDescartesAgent:
    """Tests for the Descartes Exploit Synthesizer."""

    def test_instantiation(self):
        agent = DescartesAgent()
        assert agent.config.name == "descartes"

    def test_classify_overflow(self):
        agent = DescartesAgent()
        vuln, cwe, sev = agent._classify_vulnerability(
            "h : amount > balance ⊢ False"
        )
        assert vuln == "integer_overflow"
        assert cwe == "CWE-190"
        assert sev == "CRITICAL"

    def test_classify_reentrancy(self):
        agent = DescartesAgent()
        vuln, cwe, sev = agent._classify_vulnerability(
            "call.value{...} external state"
        )
        assert vuln == "reentrancy"
        assert cwe == "CWE-841"

    def test_classify_access_control(self):
        agent = DescartesAgent()
        vuln, cwe, sev = agent._classify_vulnerability(
            "h : msg.sender ≠ owner ⊢ False"
        )
        assert vuln == "access_control_bypass"
        assert cwe == "CWE-284"

    def test_classify_unknown(self):
        agent = DescartesAgent()
        vuln, cwe, sev = agent._classify_vulnerability(
            "h : some_unknown_state ⊢ False"
        )
        assert vuln == "logic_violation"
        assert cwe == "CWE-682"

    def test_exploit_vector_to_dict(self):
        ev = ExploitVector(
            vulnerability_type="integer_overflow",
            lean_contradiction="h : amount > balance",
            english_description="Balance underflow",
            exploit_payload="# exploit code",
            affected_function="transfer",
            severity="CRITICAL",
            cwe_id="CWE-190",
        )
        d = ev.to_dict()
        assert d["vulnerability_type"] == "integer_overflow"
        assert d["severity"] == "CRITICAL"
        assert d["cwe_id"] == "CWE-190"


class TestChampollionAgent:
    """Tests for the Champollion Executive Decoder."""

    def test_instantiation(self):
        agent = ChampollionAgent()
        assert agent.config.name == "champollion"

    def test_generate_certificate(self):
        agent = ChampollionAgent()
        cert = agent.generate_certificate(
            contract_name="TestToken",
            theorems_proven=["transfer_safe", "mint_safe"],
            proof_summary="Proved by ring tactic",
            compute_cost_usd=0.30,
        )
        assert "TestToken" in cert
        assert "PROVEN SECURE" in cert
        assert "transfer_safe" in cert
        assert "mint_safe" in cert
        assert "$0.30" in cert

    def test_generate_advisory(self):
        agent = ChampollionAgent()
        advisory = agent.generate_advisory(
            contract_name="VulnToken",
            vulnerability_type="integer_overflow",
            severity="CRITICAL",
            exploit_description="Balance underflow allows infinite minting",
            exploit_payload="# attack payload here",
            affected_function="transfer",
            remediation="Add SafeMath or use Solidity 0.8+ checked arithmetic",
            cwe_id="CWE-190",
            lean_contradiction="h : amount > balance ⊢ False",
        )
        assert "VulnToken" in advisory
        assert "VULNERABILITY DETECTED" in advisory
        assert "CRITICAL" in advisory
        assert "integer_overflow" in advisory
        assert "CWE-190" in advisory
        assert "attack payload" in advisory

    def test_certificate_has_signature_hash(self):
        agent = ChampollionAgent()
        cert = agent.generate_certificate(
            contract_name="HashTest",
            theorems_proven=["test_theorem"],
            proof_summary="Test",
        )
        assert "SHA-256 Signature:" in cert

    def test_reports_counter_increments(self):
        agent = ChampollionAgent()
        assert agent._reports_generated == 0
        agent.generate_certificate("A", ["t1"], "s")
        assert agent._reports_generated == 1
        agent.generate_advisory("B", "t", "H", "d", "p", "f", "r")
        assert agent._reports_generated == 2


class TestCertificateOfAssurance:
    """Tests for the certificate data structure."""

    def test_signature_hash_deterministic(self):
        c1 = CertificateOfAssurance(
            contract_name="Token",
            certificate_id="ABC123",
            timestamp=1000.0,
            theorems_proven=["transfer_safe"],
            proof_summary="Test",
            compute_cost_usd=0.0,
            dag_stats={},
        )
        c2 = CertificateOfAssurance(
            contract_name="Token",
            certificate_id="ABC123",
            timestamp=1000.0,
            theorems_proven=["transfer_safe"],
            proof_summary="Test",
            compute_cost_usd=0.0,
            dag_stats={},
        )
        assert c1.signature_hash == c2.signature_hash

    def test_different_inputs_different_hash(self):
        c1 = CertificateOfAssurance(
            contract_name="Token1",
            certificate_id="A",
            timestamp=1000.0,
            theorems_proven=["t1"],
            proof_summary="Test",
            compute_cost_usd=0.0,
            dag_stats={},
        )
        c2 = CertificateOfAssurance(
            contract_name="Token2",
            certificate_id="B",
            timestamp=2000.0,
            theorems_proven=["t2"],
            proof_summary="Test",
            compute_cost_usd=0.0,
            dag_stats={},
        )
        assert c1.signature_hash != c2.signature_hash
