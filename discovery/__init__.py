# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0

"""
Discovery Pipeline — Combinatorial Identity Discovery Engine

This package implements the Agora's mathematical discovery pipeline,
which uses Lean 4's type checker as a ground-truth oracle to find
genuinely new, kernel-verified mathematical results.

Architecture:
    Conjecture Generator → Computational Falsifier → Lean 4 Formalizer
    → Non-Triviality Checker → Novelty Checker → Paper Writer

Design principles (from Alien Mathematics lessons learned):
    1. Zero sorry, zero axiom — non-negotiable
    2. Computational falsification BEFORE formalization
    3. Non-triviality checking — no definitional tautologies
    4. Search from known ground truth, improve incrementally
    5. Negative results are results — log everything
"""

__version__ = "0.1.0"
__author__ = "Xavier Callens / Socrate AI Lab"
