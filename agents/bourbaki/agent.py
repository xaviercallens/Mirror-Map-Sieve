# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Bourbaki Agent — The Semantic Lifting Pipeline.

Three-stage deterministic pipeline that translates imperative code
into Lean 4 State Machines before the MCTS engine starts.

Stage 1: AST Parsing — Extract Abstract Syntax Tree via tree-sitter
Stage 2: Transition Mapping — Wrap state mutations into StateT monads
Stage 3: Invariant Generation — LLM-synthesize sorry-gapped theorems

Reference: 🏛️ SPECIFICATION: The Bourbaki Translation Layer v21.
Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

import structlog

from agents.base import AbstractAgent, AgentConfig, AgentResult, AgentRole
from agents.bourbaki.codegen.lean_codegen import LeanCodeGenerator
from agents.bourbaki.codegen.type_mapper import TypeMapper
from agents.bourbaki.parsers.base_parser import ParsedFunction, SourceParser

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Intermediate Representation
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class BourbakiIR:
    """Intermediate representation output from Stage 1 + 2.

    Attributes:
        source_language: The detected/specified source language.
        contract_name: Name of the contract/module being translated.
        state_fields: Mapping of state variable names to their Lean 4 types.
        functions: Parsed function signatures with their state transitions.
        raw_source: Original source code for traceability.
    """

    source_language: str
    contract_name: str
    state_fields: dict[str, str]  # {var_name: lean_type}
    functions: list[ParsedFunction]
    raw_source: str = ""


@dataclass(slots=True)
class BourbakiOutput:
    """Final output from the Bourbaki pipeline.

    Attributes:
        lean_code: Complete Lean 4 file content with sorry gaps.
        theorems: List of theorem names that have sorry gaps.
        ir: The intermediate representation for debugging.
        diagnostics: Warnings and notes from the translation.
    """

    lean_code: str
    theorems: list[str]
    ir: BourbakiIR
    diagnostics: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Bourbaki Agent
# ---------------------------------------------------------------------------

class BourbakiAgent(AbstractAgent):
    """The Bourbaki Translation Layer — Code-to-Lean 4 translator.

    Operates strictly BEFORE the MCTS engine starts. It is a deterministic
    pipeline that prevents the LLM from hallucinating variables by grounding
    the translation in the parsed AST.

    Supports: Solidity, Python, Rust, C++ (via tree-sitter parsers).
    """

    # Mapping of language names to parser classes
    _PARSER_REGISTRY: dict[str, type[SourceParser]] = {}

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                name="bourbaki",
                model="gemini-2.5-pro",
                role=AgentRole.EXPERIMENTER,  # Will be INGESTOR after registry update
                budget_limit=50.0,
                project_budget=200.0,
                temperature=0.1,
                tools=["parse_ast", "generate_lean", "synthesize_invariant"],
            )
        super().__init__(config)
        self._type_mapper = TypeMapper()
        self._codegen = LeanCodeGenerator(self._type_mapper)
        self._log = logger.bind(agent="bourbaki")

    @classmethod
    def register_parser(cls, language: str, parser_class: type[SourceParser]) -> None:
        """Register a source parser for a given language.

        Args:
            language: Language identifier (e.g., 'solidity', 'python').
            parser_class: Parser class implementing SourceParser.
        """
        cls._PARSER_REGISTRY[language.lower()] = parser_class

    def _get_parser(self, language: str) -> SourceParser:
        """Get the appropriate parser for the source language.

        Args:
            language: Language identifier.

        Returns:
            Instantiated SourceParser.

        Raises:
            ValueError: If no parser is registered for this language.
        """
        lang = language.lower()
        if lang not in self._PARSER_REGISTRY:
            # Try the generic tree-sitter parser
            try:
                from agents.bourbaki.parsers.tree_sitter_parser import TreeSitterParser
                return TreeSitterParser(language=lang)
            except ImportError:
                raise ValueError(
                    f"No parser registered for language '{language}'. "
                    f"Available: {list(self._PARSER_REGISTRY.keys())}"
                )
        return self._PARSER_REGISTRY[lang]()

    # ------ Stage 1: AST Parsing -------------------------------------------

    def parse_source(self, source_code: str, language: str) -> list[ParsedFunction]:
        """Stage 1: Parse source code into structured function representations.

        Uses deterministic AST parsers (tree-sitter, slither) to extract
        function signatures, state reads/writes, and control flow.

        Args:
            source_code: The raw source code to parse.
            language: Programming language identifier.

        Returns:
            List of ParsedFunction objects.
        """
        timer = self._start_timer()
        parser = self._get_parser(language)
        functions = parser.parse(source_code)
        elapsed = self._stop_timer(timer, "stage1_ast_parse")

        self._log.info(
            "stage1_complete",
            language=language,
            functions_found=len(functions),
            elapsed_ms=elapsed,
        )
        return functions

    # ------ Stage 2: Transition Mapping ------------------------------------

    def map_transitions(
        self,
        functions: list[ParsedFunction],
        contract_name: str,
        language: str,
        source_code: str = "",
    ) -> BourbakiIR:
        """Stage 2: Map imperative functions into Lean 4 StateT monads.

        Extracts state variables, identifies state mutations, and builds
        the intermediate representation for Lean code generation.

        Args:
            functions: Parsed functions from Stage 1.
            contract_name: Name for the Lean 4 structure.
            language: Source language identifier.
            source_code: Original source code for traceability.

        Returns:
            BourbakiIR intermediate representation.
        """
        timer = self._start_timer()

        # Collect all state variables across functions
        state_fields: dict[str, str] = {}
        for func in functions:
            for var_name, var_type in func.state_reads.items():
                lean_type = self._type_mapper.map_type(var_type, language)
                state_fields[var_name] = lean_type
            for var_name, var_type in func.state_writes.items():
                lean_type = self._type_mapper.map_type(var_type, language)
                state_fields[var_name] = lean_type

        ir = BourbakiIR(
            source_language=language,
            contract_name=contract_name,
            state_fields=state_fields,
            functions=functions,
            raw_source=source_code,
        )

        elapsed = self._stop_timer(timer, "stage2_transition_map")
        self._log.info(
            "stage2_complete",
            contract=contract_name,
            state_fields=len(state_fields),
            functions=len(functions),
            elapsed_ms=elapsed,
        )
        return ir

    # ------ Stage 3: Invariant Generation ----------------------------------

    def generate_lean(self, ir: BourbakiIR) -> BourbakiOutput:
        """Stage 3: Generate Lean 4 code with sorry-gapped theorems.

        Produces:
        - A Lean 4 structure for the contract state
        - StateT monad functions for each transition
        - Security theorems with sorry gaps for Galois

        Args:
            ir: Intermediate representation from Stage 2.

        Returns:
            BourbakiOutput with complete Lean 4 file content.
        """
        timer = self._start_timer()

        lean_code, theorems, diagnostics = self._codegen.generate(ir)

        output = BourbakiOutput(
            lean_code=lean_code,
            theorems=theorems,
            ir=ir,
            diagnostics=diagnostics,
        )

        elapsed = self._stop_timer(timer, "stage3_lean_generation")
        self._log.info(
            "stage3_complete",
            lean_lines=lean_code.count("\n"),
            theorems=len(theorems),
            diagnostics=len(diagnostics),
            elapsed_ms=elapsed,
        )
        return output

    # ------ Full Pipeline --------------------------------------------------

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """Deliberation: parse the source code and plan the translation."""
        source_code = context.get("source_code", "")
        language = context.get("language", "solidity")
        contract_name = context.get("contract_name", "Contract")

        functions = self.parse_source(source_code, language)

        return {
            "functions": functions,
            "language": language,
            "contract_name": contract_name,
            "source_code": source_code,
        }

    async def act(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Execution: generate the Lean 4 output."""
        ir = self.map_transitions(
            functions=plan["functions"],
            contract_name=plan["contract_name"],
            language=plan["language"],
            source_code=plan["source_code"],
        )
        output = self.generate_lean(ir)

        return {
            "lean_code": output.lean_code,
            "theorems": output.theorems,
            "diagnostics": output.diagnostics,
        }

    async def run(self, query: str, **kwargs: Any) -> AgentResult:
        """Full Bourbaki pipeline: parse → map → generate.

        Args:
            query: The source code to translate.
            **kwargs: Must include 'language' and optionally 'contract_name'.

        Returns:
            AgentResult with the Lean 4 translation.
            `.answer` is a dict with keys: ir, lean_code, theorems, diagnostics.
        """
        self._guard_iterations()
        timer = self._start_timer()

        language = kwargs.get("language", "solidity")
        contract_name = kwargs.get("contract_name", "Contract")

        context = {
            "source_code": query,
            "language": language,
            "contract_name": contract_name,
        }

        plan = await self.think(context)

        # Build IR
        ir = self.map_transitions(
            functions=plan["functions"],
            contract_name=plan["contract_name"],
            language=plan["language"],
            source_code=plan["source_code"],
        )

        # Generate Lean 4
        output = self.generate_lean(ir)

        elapsed = self._stop_timer(timer, "bourbaki_full_pipeline")

        return AgentResult(
            answer={
                "ir": ir,
                "lean_code": output.lean_code,
                "theorems": output.theorems,
                "diagnostics": output.diagnostics,
            },
            confidence=0.8 if not output.diagnostics else 0.5,
            proofs=[],
            telemetry={
                "theorems_generated": output.theorems,
                "diagnostics": output.diagnostics,
                "elapsed_ms": elapsed,
                "language": language,
            },
            warnings=output.diagnostics,
        )

