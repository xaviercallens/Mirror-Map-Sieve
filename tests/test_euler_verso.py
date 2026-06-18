# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Tests for the Euler Agent's Verso and certificate integration."""

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from agents.euler.agent import EulerAgent
from agents.euler.tools.verso_compiler import compile_verso_document
from agents.euler.tools.certificate_generator import generate_verification_certificate
from alexandrie.hub import AlexandrieHub


def test_certificate_generator() -> None:
    """Test generating a formal mathematical verification certificate and saving to Alexandrie."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        theorem_name = "addition_is_comm"
        proof_code = "theorem addition_is_comm (a b : Nat) : a + b = b + a := by omega"
        verdict = "VERIFIED"
        comments = "Euler skeptical audit: mathematical assertions formally checked. No sorry gaps found."
        confidence = 1.0

        # Generate certificate
        res = generate_verification_certificate(
            theorem_name=theorem_name,
            proof_code=proof_code,
            verdict=verdict,
            skeptical_audit_comments=comments,
            confidence=confidence,
            vault_root=tmp_dir,
        )

        assert res["certificate_id"].startswith("CERT-EULER-ADDITION_IS_COMM-")
        assert "VERIFICATION CERTIFICATE" in res["certificate_text"]
        assert "SIGNATURE BLOCK" in res["certificate_text"]
        assert res["sha256"] is not None

        # Verify catalog in the temp Alexandrie hub
        hub = AlexandrieHub(tmp_dir)
        catalog_results = hub.search_vault("addition_is_comm")
        assert len(catalog_results) == 1
        assert catalog_results[0].metrics["verification_confidence"] == 1.0
        assert catalog_results[0].metrics["verification_status"] == "VERIFIED"


@pytest.mark.asyncio
async def test_euler_agent_routing() -> None:
    """Test that the Euler agent correctly plans and routes Verso queries."""
    euler = EulerAgent()
    
    # Simple mathematical query mentioning verso
    query = "Compile a verso document checking the theorem gating_girdle_monotone."
    
    # Run think lifecycle
    plan = await euler.think({"query": query})
    
    assert "verso_compiler" in plan["tools"]
    assert "certificate_generator" in plan["tools"]
    assert "skeptical_auditor" in plan["tools"]
    assert plan["strategy"] == "verso_verification"


def test_verso_static_checks() -> None:
    """Test the static analysis regex inside verso_compiler.py."""
    doc = (
        "theorem addition_identity (n : Nat) : n + 0 = n := by\n"
        "  simp\n"
    )
    
    # We call compilation with dummy path to trigger error gracefully or run static analysis
    # (Checking that standard error outputs behave correctly without lean if it falls back)
    res = compile_verso_document(doc, project_dir="/nonexistent_path")
    assert "addition_identity" in res["theorems_found"]
    assert not res["has_sorry"]
    assert res["success"] is False  # nonexistent path should fail gracefully
    assert any(w in res["message"].lower() for w in ("not found", "timeout", "error", "failed", "read-only", "errno"))
