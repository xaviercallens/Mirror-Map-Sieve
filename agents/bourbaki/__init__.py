# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Bourbaki Translation Layer — Code-to-Lean 4 Translator.

Autonomously translates imperative industrial code (Solidity, Rust, Python)
and natural-language constraints into typed Lean 4 State Machines with
sorry-gapped theorems for the Galois MCTS engine.
"""

from agents.bourbaki.agent import BourbakiAgent
from agents.bourbaki.parsers.solidity_parser import SolidityParser

# Auto-register built-in parsers
BourbakiAgent.register_parser("solidity", SolidityParser)

__all__ = ["BourbakiAgent"]

