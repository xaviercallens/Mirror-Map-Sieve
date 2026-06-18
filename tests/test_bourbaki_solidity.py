# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Unit tests for the Bourbaki Translation Layer — Solidity pipeline.

Tests the full Stage 1 → Stage 2 → Stage 3 pipeline on ERC-20 contracts.
"""

import os
import pytest
import sys

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.bourbaki.parsers.base_parser import ParsedFunction
from agents.bourbaki.parsers.solidity_parser import SolidityParser
from agents.bourbaki.codegen.type_mapper import TypeMapper
from agents.bourbaki.codegen.lean_codegen import LeanCodeGenerator
from agents.bourbaki.agent import BourbakiIR


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SIMPLE_CONTRACT = """
pragma solidity ^0.8.20;
contract Token {
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;

    function transfer(address to, uint256 amount) public returns (bool) {
        require(balanceOf[msg.sender] >= amount, "Insufficient balance");
        require(to != address(0), "Zero address");
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        return true;
    }

    function mint(uint256 amount) public {
        totalSupply += amount;
        balanceOf[msg.sender] += amount;
    }
}
"""

MINIMAL_CONTRACT = """
pragma solidity ^0.8.20;
contract Minimal {
    uint256 public counter;
    function increment() public {
        counter += 1;
    }
}
"""


# ---------------------------------------------------------------------------
# Stage 1: Solidity Parser Tests
# ---------------------------------------------------------------------------

class TestSolidityParser:
    """Tests for the Solidity AST parser."""

    def test_detects_state_variables(self):
        parser = SolidityParser()
        state_vars = parser.detect_state_variables(SIMPLE_CONTRACT)
        assert "totalSupply" in state_vars
        assert state_vars["totalSupply"] == "uint256"

    def test_parses_functions(self):
        parser = SolidityParser()
        functions = parser.parse(SIMPLE_CONTRACT)
        names = [f.name for f in functions]
        assert "transfer" in names
        assert "mint" in names

    def test_extracts_preconditions(self):
        parser = SolidityParser()
        functions = parser.parse(SIMPLE_CONTRACT)
        transfer = next(f for f in functions if f.name == "transfer")
        # Should find at least the balance check
        assert len(transfer.preconditions) >= 1
        assert any("balance" in p.lower() for p in transfer.preconditions)

    def test_extracts_state_writes(self):
        parser = SolidityParser()
        functions = parser.parse(SIMPLE_CONTRACT)
        transfer = next(f for f in functions if f.name == "transfer")
        assert "balanceOf" in transfer.state_writes

    def test_extracts_parameters(self):
        parser = SolidityParser()
        functions = parser.parse(SIMPLE_CONTRACT)
        transfer = next(f for f in functions if f.name == "transfer")
        assert "to" in transfer.params
        assert "amount" in transfer.params

    def test_parses_minimal_contract(self):
        parser = SolidityParser()
        functions = parser.parse(MINIMAL_CONTRACT)
        assert len(functions) == 1
        assert functions[0].name == "increment"
        assert "counter" in functions[0].state_writes

    def test_empty_input_returns_empty(self):
        parser = SolidityParser()
        assert parser.parse("") == []
        assert parser.detect_state_variables("") == {}


# ---------------------------------------------------------------------------
# Stage 2: Type Mapper Tests
# ---------------------------------------------------------------------------

class TestTypeMapper:
    """Tests for Solidity → Lean 4 type mappings."""

    def test_basic_types(self):
        mapper = TypeMapper()
        assert mapper.map_type("uint256", "solidity") == "Nat"
        assert mapper.map_type("address", "solidity") == "Nat"
        assert mapper.map_type("bool", "solidity") == "Bool"
        assert mapper.map_type("string", "solidity") == "String"

    def test_fixed_width_integers(self):
        mapper = TypeMapper()
        assert mapper.map_type("uint8", "solidity") == "Fin (2 ^ 8)"
        assert mapper.map_type("uint32", "solidity") == "Fin (2 ^ 32)"
        assert mapper.map_type("uint64", "solidity") == "Fin (2 ^ 64)"

    def test_signed_integers(self):
        mapper = TypeMapper()
        assert mapper.map_type("int", "solidity") == "Int"
        assert mapper.map_type("int256", "solidity") == "Int"

    def test_mapping_type(self):
        mapper = TypeMapper()
        result = mapper.map_type("mapping(address => uint)", "solidity")
        assert "Std.HashMap" in result
        assert "Nat" in result

    def test_python_types(self):
        mapper = TypeMapper()
        assert mapper.map_type("int", "python") == "Int"
        assert mapper.map_type("str", "python") == "String"
        assert mapper.map_type("bool", "python") == "Bool"
        assert mapper.map_type("list", "python") == "List"

    def test_rust_types(self):
        mapper = TypeMapper()
        assert mapper.map_type("u64", "rust") == "Fin (2 ^ 64)"
        assert mapper.map_type("bool", "rust") == "Bool"
        assert mapper.map_type("Vec", "rust") == "Array"

    def test_unknown_type_passthrough(self):
        mapper = TypeMapper()
        assert mapper.map_type("MyCustomStruct", "solidity") == "MyCustomStruct"

    def test_map_params(self):
        mapper = TypeMapper()
        params = {"to": "address", "amount": "uint256"}
        result = mapper.map_params(params, "solidity")
        assert result["to"] == "Nat"
        assert result["amount"] == "Nat"


# ---------------------------------------------------------------------------
# Stage 3: Lean Code Generator Tests
# ---------------------------------------------------------------------------

class TestLeanCodeGenerator:
    """Tests for the Lean 4 code generation from IR."""

    def _build_ir(self, source=SIMPLE_CONTRACT):
        parser = SolidityParser()
        mapper = TypeMapper()
        functions = parser.parse(source)

        state_fields = {}
        for func in functions:
            for var, stype in func.state_reads.items():
                state_fields[var] = mapper.map_type(stype, "solidity")
            for var, stype in func.state_writes.items():
                state_fields[var] = mapper.map_type(stype, "solidity")

        return BourbakiIR(
            source_language="solidity",
            contract_name="Token",
            state_fields=state_fields,
            functions=functions,
            raw_source=source,
        ), mapper

    def test_generates_structure(self):
        ir, mapper = self._build_ir()
        codegen = LeanCodeGenerator(mapper)
        lean_code, _, _ = codegen.generate(ir)
        assert "structure TokenState" in lean_code

    def test_generates_sorry_theorems(self):
        ir, mapper = self._build_ir()
        codegen = LeanCodeGenerator(mapper)
        lean_code, theorems, _ = codegen.generate(ir)
        assert len(theorems) >= 1
        assert "sorry" in lean_code
        assert all("_safe" in t for t in theorems)

    def test_generates_imports(self):
        ir, mapper = self._build_ir()
        codegen = LeanCodeGenerator(mapper)
        lean_code, _, _ = codegen.generate(ir)
        assert "import Mathlib" in lean_code
        assert "namespace Bourbaki.Token" in lean_code

    def test_generates_transition_functions(self):
        ir, mapper = self._build_ir()
        codegen = LeanCodeGenerator(mapper)
        lean_code, _, _ = codegen.generate(ir)
        assert "def transfer" in lean_code
        assert "def mint" in lean_code
        assert "StateT" in lean_code

    def test_generates_guard_clauses(self):
        ir, mapper = self._build_ir()
        codegen = LeanCodeGenerator(mapper)
        lean_code, _, _ = codegen.generate(ir)
        # Preconditions should generate guard clauses
        assert "throw" in lean_code or "if" in lean_code

    def test_empty_contract_warns(self):
        ir = BourbakiIR(
            source_language="solidity",
            contract_name="Empty",
            state_fields={},
            functions=[],
        )
        mapper = TypeMapper()
        codegen = LeanCodeGenerator(mapper)
        _, _, diagnostics = codegen.generate(ir)
        assert len(diagnostics) >= 1  # Should warn about no state/functions

    def test_minimal_contract(self):
        ir, mapper = self._build_ir(MINIMAL_CONTRACT)
        codegen = LeanCodeGenerator(mapper)
        lean_code, theorems, _ = codegen.generate(ir)
        assert "def increment" in lean_code
        assert len(theorems) == 1


# ---------------------------------------------------------------------------
# End-to-End Pipeline Test
# ---------------------------------------------------------------------------

class TestBourbakiE2E:
    """End-to-end test: Solidity → Lean 4."""

    def test_erc20_full_pipeline(self):
        """Test that a full ERC-20 contract produces valid Lean output."""
        erc20_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples", "erc20_token.sol"
        )
        if not os.path.exists(erc20_path):
            pytest.skip("ERC-20 example not found")

        with open(erc20_path) as f:
            source = f.read()

        parser = SolidityParser()
        mapper = TypeMapper()
        functions = parser.parse(source)

        state_fields = {}
        for func in functions:
            for var, stype in {**func.state_reads, **func.state_writes}.items():
                state_fields[var] = mapper.map_type(stype, "solidity")

        ir = BourbakiIR(
            source_language="solidity",
            contract_name="SimpleERC20",
            state_fields=state_fields,
            functions=functions,
        )

        codegen = LeanCodeGenerator(mapper)
        lean_code, theorems, diagnostics = codegen.generate(ir)

        # Assertions
        assert "structure SimpleERC20State" in lean_code
        assert "sorry" in lean_code
        assert len(theorems) >= 3  # transfer, approve, transferFrom
        assert len(functions) >= 3
