# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Z3 SMT Solver Bridge for Galois.

Offloads heavy bit-vector arithmetic and integer reasoning to Z3 so
the LLM focuses purely on structural logic. This implements the v21
spec requirement: "Galois is upgraded to natively call external SMT
solvers (like Z3) for heavy bit-vector arithmetic via Lean plugins."

The bridge translates Lean 4 proof obligations into SMT-LIB2 queries
and returns proof witnesses that Galois can inject as tactic hints.

Usage:
    from agents.galois.tools.z3_bridge import Z3Bridge

    z3 = Z3Bridge()
    result = z3.check_bitvector_overflow(
        width=256,
        a="balance",
        b="amount",
        operation="sub",
    )
    # result.is_safe → True if no overflow possible under constraints

Reference: THE AGORA SENTINEL CODEX, Chapter 6.
"""

from __future__ import annotations

import subprocess
import tempfile
import os
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class SMTResult(Enum):
    """Result of an SMT query."""
    SAT = auto()       # Satisfiable — counterexample exists (overflow possible)
    UNSAT = auto()     # Unsatisfiable — property holds (no overflow)
    UNKNOWN = auto()   # Solver timed out or hit complexity limit
    ERROR = auto()     # Z3 returned an error


@dataclass(slots=True)
class Z3QueryResult:
    """Structured result of a Z3 SMT query."""
    status: SMTResult
    counterexample: dict[str, Any] = field(default_factory=dict)
    proof_witness: str = ""
    raw_output: str = ""
    query_time_ms: float = 0.0

    @property
    def is_safe(self) -> bool:
        """True if the property holds (UNSAT = no counterexample)."""
        return self.status == SMTResult.UNSAT

    @property
    def is_exploitable(self) -> bool:
        """True if a counterexample was found (SAT)."""
        return self.status == SMTResult.SAT

    def to_tactic_hint(self) -> str:
        """Convert the Z3 result into a Lean 4 tactic hint.

        If UNSAT, suggests omega or norm_num.
        If SAT, provides counterexample values.
        """
        if self.status == SMTResult.UNSAT:
            return "-- Z3: UNSAT (property holds). Try: omega"
        elif self.status == SMTResult.SAT:
            vals = ", ".join(f"{k}={v}" for k, v in self.counterexample.items())
            return f"-- Z3: SAT (counterexample: {vals}). This obligation cannot be proven."
        return f"-- Z3: {self.status.name}"


class Z3Bridge:
    """Bridge to the Z3 SMT solver for bit-vector arithmetic.

    Translates proof obligations into SMT-LIB2 format, invokes Z3,
    and returns structured results with proof witnesses.
    """

    def __init__(
        self,
        z3_path: str = "z3",
        timeout_ms: int = 5000,
    ) -> None:
        self.z3_path = z3_path
        self.timeout_ms = timeout_ms
        self._log = logger.bind(component="z3_bridge")
        self._available: bool | None = None

    @property
    def is_available(self) -> bool:
        """Check if Z3 is installed and accessible."""
        if self._available is None:
            try:
                result = subprocess.run(
                    [self.z3_path, "--version"],
                    capture_output=True, text=True, timeout=5,
                )
                self._available = result.returncode == 0
                if self._available:
                    version = result.stdout.strip()
                    self._log.info("z3_available", version=version)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                self._available = False
                self._log.warning("z3_not_available")
        return self._available

    def _invoke_z3(self, smt_lib2: str) -> Z3QueryResult:
        """Execute an SMT-LIB2 query against Z3."""
        import time

        if not self.is_available:
            return Z3QueryResult(
                status=SMTResult.ERROR,
                raw_output="Z3 is not installed or not in PATH",
            )

        t_start = time.perf_counter()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".smt2", delete=False
        ) as f:
            f.write(smt_lib2)
            tmp_path = f.name

        try:
            result = subprocess.run(
                [self.z3_path, f"-T:{self.timeout_ms // 1000}", tmp_path],
                capture_output=True, text=True,
                timeout=self.timeout_ms / 1000 + 5,
            )
            elapsed = (time.perf_counter() - t_start) * 1000
            raw = result.stdout.strip()

            # Parse result
            if "unsat" in raw.lower().split("\n")[0]:
                return Z3QueryResult(
                    status=SMTResult.UNSAT,
                    raw_output=raw,
                    query_time_ms=elapsed,
                )
            elif "sat" in raw.lower().split("\n")[0]:
                # Parse counterexample from model
                model = self._parse_model(raw)
                return Z3QueryResult(
                    status=SMTResult.SAT,
                    counterexample=model,
                    raw_output=raw,
                    query_time_ms=elapsed,
                )
            elif "unknown" in raw.lower():
                return Z3QueryResult(
                    status=SMTResult.UNKNOWN,
                    raw_output=raw,
                    query_time_ms=elapsed,
                )
            else:
                return Z3QueryResult(
                    status=SMTResult.ERROR,
                    raw_output=raw,
                    query_time_ms=elapsed,
                )

        except subprocess.TimeoutExpired:
            return Z3QueryResult(
                status=SMTResult.UNKNOWN,
                raw_output="Z3 timed out",
            )
        finally:
            os.unlink(tmp_path)

    def _parse_model(self, raw: str) -> dict[str, Any]:
        """Parse a Z3 model output into a dictionary."""
        model = {}
        # Match hex bitvector values directly: (define-fun name () TYPE #xHEX)
        hex_pattern = r"\(define-fun\s+(\w+)\s+\(\)\s+.*?\s+(#x[0-9a-fA-F]+)\)"
        for match in re.finditer(hex_pattern, raw):
            name = match.group(1)
            value = match.group(2)
            model[name] = int(value[2:], 16)

        # Match binary bitvector values: (define-fun name () TYPE #bBINARY)
        bin_pattern = r"\(define-fun\s+(\w+)\s+\(\)\s+.*?\s+(#b[01]+)\)"
        for match in re.finditer(bin_pattern, raw):
            name = match.group(1)
            if name not in model:  # Don't overwrite hex matches
                model[name] = int(match.group(2)[2:], 2)

        # Match integer values: (define-fun name () Int VALUE)
        int_pattern = r"\(define-fun\s+(\w+)\s+\(\)\s+Int\s+(-?\d+)\)"
        for match in re.finditer(int_pattern, raw):
            name = match.group(1)
            if name not in model:
                model[name] = int(match.group(2))

        return model

    # ──────────────────────────────────────────────────────────
    # High-Level Queries
    # ──────────────────────────────────────────────────────────

    def check_bitvector_overflow(
        self,
        width: int = 256,
        a: str = "a",
        b: str = "b",
        operation: str = "sub",
        constraints: list[str] | None = None,
    ) -> Z3QueryResult:
        """Check if a bit-vector operation can overflow/underflow.

        Generates an SMT-LIB2 query that asks:
          "Does there exist values of a, b such that a `op` b wraps?"

        For subtraction: checks if a - b can underflow (a < b).
        For addition: checks if a + b can overflow (result < a).

        Args:
            width: Bit-vector width (e.g., 256 for uint256).
            a: Name of the first operand.
            b: Name of the second operand.
            operation: One of 'sub', 'add', 'mul'.
            constraints: Additional SMT-LIB2 constraints.

        Returns:
            Z3QueryResult. is_safe=True if no overflow possible.
        """
        bv_type = f"(_ BitVec {width})"

        smt = f"""; Agora Sentinel — Z3 bit-vector overflow check
; Operation: {a} {operation} {b} ({width}-bit)
(set-logic QF_BV)

(declare-const {a} {bv_type})
(declare-const {b} {bv_type})
"""
        # Add user constraints
        if constraints:
            for c in constraints:
                smt += f"(assert {c})\n"

        # Add overflow condition
        if operation == "sub":
            smt += f"""
; Underflow: a < b (unsigned)
(assert (bvult {a} {b}))
"""
        elif operation == "add":
            smt += f"""
; Overflow: a + b wraps around (result < a)
(declare-const result {bv_type})
(assert (= result (bvadd {a} {b})))
(assert (bvult result {a}))
"""
        elif operation == "mul":
            smt += f"""
; Overflow: a * b truncated ≠ full product
(declare-const result {bv_type})
(assert (= result (bvmul {a} {b})))
; Check if truncation lost bits (simplified: result/a ≠ b when a ≠ 0)
(assert (not (= {a} (_ bv0 {width}))))
(assert (not (= (bvudiv result {a}) {b})))
"""

        smt += """
(check-sat)
(get-model)
"""

        self._log.info(
            "z3_bitvector_check",
            operation=operation,
            width=width,
            has_constraints=bool(constraints),
        )

        return self._invoke_z3(smt)

    def check_nat_inequality(
        self,
        lhs: str,
        rhs: str,
        relation: str = ">=",
        constraints: list[str] | None = None,
    ) -> Z3QueryResult:
        """Check if a natural number inequality always holds.

        Asks Z3: "Is there a counterexample where ¬(lhs >= rhs)?"
        If UNSAT → the inequality always holds.

        Args:
            lhs: Left-hand side expression (SMT-LIB2 syntax).
            rhs: Right-hand side expression.
            relation: Comparison operator (>=, >, <=, <, =).
            constraints: Additional constraints.

        Returns:
            Z3QueryResult. is_safe=True means inequality always holds.
        """
        # Map relation to SMT negation
        neg_map = {
            ">=": "<", ">": "<=", "<=": ">",
            "<": ">=", "=": "distinct",
        }
        neg_rel = neg_map.get(relation, "distinct")

        smt = f"""; Agora Sentinel — Natural number inequality check
; Question: Does {lhs} {relation} {rhs} always hold?
(set-logic QF_LIA)

"""
        # Auto-declare variables found in expressions
        variables = set(re.findall(r'\b([a-zA-Z_]\w*)\b', f"{lhs} {rhs}"))
        keywords = {"ite", "and", "or", "not", "true", "false", "let", "forall", "exists"}
        for var in sorted(variables - keywords):
            smt += f"(declare-const {var} Int)\n"
            smt += f"(assert (>= {var} 0))  ; Natural numbers\n"

        if constraints:
            for c in constraints:
                smt += f"(assert {c})\n"

        # Assert negation of the property
        if neg_rel == "distinct":
            smt += f"(assert (not (= {lhs} {rhs})))\n"
        else:
            smt += f"(assert ({neg_rel} {lhs} {rhs}))\n"

        smt += """
(check-sat)
(get-model)
"""

        return self._invoke_z3(smt)

    def check_solidity_transfer_safety(
        self,
        balance_var: str = "balance",
        amount_var: str = "amount",
        has_require_guard: bool = True,
    ) -> Z3QueryResult:
        """Check if a Solidity transfer function is safe from underflow.

        Models the exact Bourbaki semantics:
          require(balance >= amount)
          balance' = balance - amount

        Args:
            balance_var: Name of the balance variable.
            amount_var: Name of the amount variable.
            has_require_guard: Whether there's a require(balance >= amount).

        Returns:
            Z3QueryResult. is_safe=True if transfer can't underflow.
        """
        smt = f"""; Agora Sentinel — Solidity transfer safety check
; Contract semantics: require({balance_var} >= {amount_var}); {balance_var} -= {amount_var}
(set-logic QF_BV)

(declare-const {balance_var} (_ BitVec 256))
(declare-const {amount_var} (_ BitVec 256))
"""

        if has_require_guard:
            smt += f"""
; require guard: balance >= amount
(assert (bvuge {balance_var} {amount_var}))
"""

        smt += f"""
; Can the subtraction underflow?
(assert (bvult {balance_var} {amount_var}))

(check-sat)
(get-model)
"""

        result = self._invoke_z3(smt)

        if has_require_guard and result.status == SMTResult.UNSAT:
            result.proof_witness = (
                f"Z3 verified: with require({balance_var} >= {amount_var}), "
                f"the subtraction {balance_var} - {amount_var} cannot underflow. "
                f"Lean 4 tactic: omega"
            )

        return result

    # ──────────────────────────────────────────────────────────
    # Generic SMT-LIB2 Interface
    # ──────────────────────────────────────────────────────────

    def raw_query(self, smt_lib2: str) -> Z3QueryResult:
        """Execute a raw SMT-LIB2 query.

        For advanced users who need direct Z3 access.
        """
        return self._invoke_z3(smt_lib2)
