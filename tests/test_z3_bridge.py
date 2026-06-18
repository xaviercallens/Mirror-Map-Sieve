# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Tests for the Z3 SMT Solver Bridge."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.galois.tools.z3_bridge import (
    Z3Bridge,
    Z3QueryResult,
    SMTResult,
)


class TestZ3QueryResult:
    """Tests for Z3QueryResult data class."""

    def test_safe_when_unsat(self):
        r = Z3QueryResult(status=SMTResult.UNSAT)
        assert r.is_safe is True
        assert r.is_exploitable is False

    def test_exploitable_when_sat(self):
        r = Z3QueryResult(status=SMTResult.SAT, counterexample={"a": 0, "b": 1})
        assert r.is_safe is False
        assert r.is_exploitable is True

    def test_tactic_hint_unsat(self):
        r = Z3QueryResult(status=SMTResult.UNSAT)
        hint = r.to_tactic_hint()
        assert "omega" in hint
        assert "UNSAT" in hint

    def test_tactic_hint_sat(self):
        r = Z3QueryResult(
            status=SMTResult.SAT,
            counterexample={"balance": 0, "amount": 42},
        )
        hint = r.to_tactic_hint()
        assert "SAT" in hint
        assert "balance=0" in hint
        assert "amount=42" in hint

    def test_tactic_hint_unknown(self):
        r = Z3QueryResult(status=SMTResult.UNKNOWN)
        assert "UNKNOWN" in r.to_tactic_hint()


class TestZ3Bridge:
    """Tests for Z3Bridge (may skip if Z3 not installed)."""

    @pytest.fixture
    def z3(self):
        return Z3Bridge()

    def test_instantiation(self, z3):
        assert z3.z3_path == "z3"
        assert z3.timeout_ms == 5000

    def test_custom_timeout(self):
        z3 = Z3Bridge(timeout_ms=10000)
        assert z3.timeout_ms == 10000

    @pytest.mark.skipif(
        not Z3Bridge().is_available,
        reason="Z3 not installed",
    )
    def test_bitvector_underflow_no_guard(self, z3):
        """Without require guard, subtraction CAN underflow."""
        result = z3.check_bitvector_overflow(
            width=256,
            a="balance",
            b="amount",
            operation="sub",
        )
        # SAT = counterexample exists (overflow possible)
        assert result.status == SMTResult.SAT
        assert result.is_exploitable

    @pytest.mark.skipif(
        not Z3Bridge().is_available,
        reason="Z3 not installed",
    )
    def test_bitvector_underflow_with_guard(self, z3):
        """With require(balance >= amount), subtraction CANNOT underflow."""
        result = z3.check_bitvector_overflow(
            width=256,
            a="balance",
            b="amount",
            operation="sub",
            constraints=["(bvuge balance amount)"],
        )
        # UNSAT = no counterexample (safe)
        assert result.status == SMTResult.UNSAT
        assert result.is_safe

    @pytest.mark.skipif(
        not Z3Bridge().is_available,
        reason="Z3 not installed",
    )
    def test_transfer_safety_with_guard(self, z3):
        """Solidity transfer with require guard should be safe."""
        result = z3.check_solidity_transfer_safety(has_require_guard=True)
        assert result.status == SMTResult.UNSAT
        assert result.is_safe
        assert "omega" in result.proof_witness

    @pytest.mark.skipif(
        not Z3Bridge().is_available,
        reason="Z3 not installed",
    )
    def test_transfer_safety_without_guard(self, z3):
        """Solidity transfer WITHOUT require guard should be exploitable."""
        result = z3.check_solidity_transfer_safety(has_require_guard=False)
        assert result.status == SMTResult.SAT
        assert result.is_exploitable
        assert "balance" in result.counterexample or "amount" in result.counterexample

    @pytest.mark.skipif(
        not Z3Bridge().is_available,
        reason="Z3 not installed",
    )
    def test_raw_query(self, z3):
        """Test a raw SMT-LIB2 query."""
        smt = """
(set-logic QF_LIA)
(declare-const x Int)
(assert (> x 0))
(assert (< x 0))
(check-sat)
"""
        result = z3.raw_query(smt)
        assert result.status == SMTResult.UNSAT  # x > 0 AND x < 0 is unsatisfiable

    def test_not_available_returns_error(self):
        """Z3Bridge with wrong path should report ERROR."""
        z3 = Z3Bridge(z3_path="/nonexistent/z3")
        result = z3.check_bitvector_overflow()
        assert result.status == SMTResult.ERROR

    def test_model_parsing(self, z3):
        """Test the model parser."""
        raw = """sat
(model
  (define-fun balance () (_ BitVec 256) #x0000000000000000000000000000000000000000000000000000000000000005)
  (define-fun amount () (_ BitVec 256) #x000000000000000000000000000000000000000000000000000000000000000a)
)"""
        model = z3._parse_model(raw)
        assert model["balance"] == 5
        assert model["amount"] == 10
