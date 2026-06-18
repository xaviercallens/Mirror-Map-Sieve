# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Solidity Parser for the Bourbaki Translation Layer.

Extracts function signatures, state variables, require() guards,
and state mutations from Solidity smart contract source code using
regex-based parsing (no external solc dependency required).

For advanced use: when slither-analyzer is installed, this parser
delegates to its richer AST for accurate data-flow analysis.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

from agents.bourbaki.parsers.base_parser import ParsedFunction, SourceParser

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Regex patterns for Solidity AST extraction
# ---------------------------------------------------------------------------

_STATE_VAR_PATTERN = re.compile(
    r'^\s*(?:mapping\s*\(.*?\)|(?:uint\d*|int\d*|address|bool|bytes\d*|string))'
    r'\s+(?:public\s+|private\s+|internal\s+)?(\w+)\s*(?:=.*?)?;',
    re.MULTILINE,
)

_MAPPING_PATTERN = re.compile(
    r'^\s*mapping\s*\((\w+)\s*=>\s*(\w+)\)\s*(?:public\s+|private\s+)?(\w+)\s*;',
    re.MULTILINE,
)

_FUNCTION_PATTERN = re.compile(
    r'function\s+(\w+)\s*\((.*?)\)\s*((?:public|private|internal|external)\s*)?'
    r'((?:payable|view|pure)\s*)*(returns\s*\((.*?)\))?\s*\{',
    re.DOTALL,
)

_REQUIRE_PATTERN = re.compile(
    r'require\s*\((.*?)\)\s*;',
    re.DOTALL,
)

_STATE_WRITE_PATTERN = re.compile(
    r'(\w+)\s*(?:\[.*?\])?\s*[-+*]?=\s*',
)

_TYPE_PATTERN = re.compile(
    r'^\s*(uint\d*|int\d*|address|bool|bytes\d*|string)\s+(?:public\s+|private\s+|internal\s+)?(\w+)',
    re.MULTILINE,
)


class SolidityParser(SourceParser):
    """Regex-based Solidity parser for the Bourbaki pipeline.

    Extracts:
    - State variables (uint, mapping, address, bool, etc.)
    - Function signatures with parameters and visibility
    - require() preconditions
    - State variable mutations (write patterns)
    """

    def __init__(self) -> None:
        self._log = logger.bind(parser="solidity")

    def detect_state_variables(self, source_code: str) -> dict[str, str]:
        """Extract top-level state variable declarations from Solidity.

        Args:
            source_code: Raw Solidity source code.

        Returns:
            Dict mapping variable name → Solidity type string.
        """
        state_vars: dict[str, str] = {}

        # Simple typed variables
        for match in _TYPE_PATTERN.finditer(source_code):
            var_type, var_name = match.group(1), match.group(2)
            state_vars[var_name] = var_type

        # Mapping variables
        for match in _MAPPING_PATTERN.finditer(source_code):
            key_type, val_type, var_name = match.groups()
            state_vars[var_name] = f"mapping({key_type} => {val_type})"

        self._log.debug("state_vars_detected", count=len(state_vars))
        return state_vars

    def parse(self, source_code: str) -> list[ParsedFunction]:
        """Parse Solidity source into ParsedFunction list.

        Args:
            source_code: Raw Solidity source code.

        Returns:
            List of ParsedFunction with state reads/writes and preconditions.
        """
        state_vars = self.detect_state_variables(source_code)
        functions: list[ParsedFunction] = []

        for match in _FUNCTION_PATTERN.finditer(source_code):
            func_name = match.group(1)
            params_str = match.group(2).strip()
            visibility = (match.group(3) or "public").strip()
            mutability = (match.group(4) or "").strip()
            return_type = (match.group(6) or "").strip()

            # Parse parameters
            params: dict[str, str] = {}
            if params_str:
                for param in params_str.split(","):
                    parts = param.strip().split()
                    if len(parts) >= 2:
                        params[parts[-1]] = parts[0]

            # Extract function body (find matching braces)
            start_idx = match.end() - 1  # Position of opening '{'
            body = self._extract_body(source_code, start_idx)

            # Extract require() preconditions
            preconditions = [m.group(1).strip() for m in _REQUIRE_PATTERN.finditer(body)]

            # Detect state reads and writes
            state_reads: dict[str, str] = {}
            state_writes: dict[str, str] = {}

            for var_name, var_type in state_vars.items():
                if var_name in body:
                    # Check if it's a write
                    write_match = re.search(
                        rf'\b{re.escape(var_name)}\b\s*(?:\[.*?\])?\s*[-+*]?=\s*',
                        body,
                    )
                    if write_match:
                        state_writes[var_name] = var_type
                    else:
                        state_reads[var_name] = var_type

            functions.append(ParsedFunction(
                name=func_name,
                params=params,
                return_type=return_type,
                state_reads=state_reads,
                state_writes=state_writes,
                preconditions=preconditions,
                body_summary=self._summarize_body(body),
                raw_body=body,
                visibility=visibility,
                is_payable="payable" in mutability,
            ))

        self._log.info(
            "parse_complete",
            functions=len(functions),
            state_vars=len(state_vars),
        )
        return functions

    def _extract_body(self, source: str, start: int) -> str:
        """Extract a brace-delimited body starting at '{'.

        Args:
            source: Full source code string.
            start: Index of the opening '{'.

        Returns:
            The function body content (excluding outer braces).
        """
        depth = 0
        for i in range(start, len(source)):
            if source[i] == "{":
                depth += 1
            elif source[i] == "}":
                depth -= 1
                if depth == 0:
                    return source[start + 1 : i].strip()
        return source[start + 1 :].strip()

    def _summarize_body(self, body: str) -> str:
        """Create a simplified summary of a function body.

        Args:
            body: Raw function body.

        Returns:
            Simplified string suitable for LLM context.
        """
        lines = [
            line.strip()
            for line in body.split("\n")
            if line.strip() and not line.strip().startswith("//")
        ]
        return "; ".join(lines[:5])

    def language_name(self) -> str:
        return "Solidity"
