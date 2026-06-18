# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Abstract Source Parser for the Bourbaki Translation Layer.

All language-specific parsers must inherit from SourceParser and return
a list of ParsedFunction objects.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ParsedFunction:
    """A parsed function extracted from source code.

    Attributes:
        name: Function name in the source language.
        params: Parameter names and their source types.
        return_type: Return type in the source language (if any).
        state_reads: State variables read by this function.
        state_writes: State variables written/mutated by this function.
        preconditions: Guard conditions (e.g., require() in Solidity).
        body_summary: A simplified representation of the function body.
        raw_body: The raw source code of the function body.
        visibility: Access modifier (public, private, internal, external).
        is_payable: Whether this function accepts funds (Solidity-specific).
        modifiers: Applied modifiers (Solidity-specific).
    """

    name: str
    params: dict[str, str]           # {param_name: source_type}
    return_type: str = ""
    state_reads: dict[str, str] = field(default_factory=dict)   # {var: type}
    state_writes: dict[str, str] = field(default_factory=dict)  # {var: type}
    preconditions: list[str] = field(default_factory=list)
    body_summary: str = ""
    raw_body: str = ""
    visibility: str = "public"
    is_payable: bool = False
    modifiers: list[str] = field(default_factory=list)


class SourceParser(ABC):
    """Abstract base class for language-specific source code parsers.

    Implementations must extract function signatures, state reads/writes,
    and preconditions from the source AST.
    """

    @abstractmethod
    def parse(self, source_code: str) -> list[ParsedFunction]:
        """Parse source code into structured function representations.

        Args:
            source_code: Raw source code string.

        Returns:
            List of ParsedFunction objects, one per function/method.
        """

    @abstractmethod
    def detect_state_variables(self, source_code: str) -> dict[str, str]:
        """Extract top-level state variable declarations.

        Args:
            source_code: Raw source code string.

        Returns:
            Dict mapping variable name → source type.
        """

    def language_name(self) -> str:
        """Return the human-readable name of this parser's language."""
        return self.__class__.__name__.replace("Parser", "")
