# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Archimedes Agent — Lemma Decomposition & Sorry Gap Resolution.

Named after Archimedes' 'Method of Exhaustion', which progressively approximates
a result through ever-finer subdivisions. Similarly, Archimedes decomposes a
monolithic proof with sorry stubs into smaller, targeted sub-lemmas,
then iteratively attacks each gap until either resolved or genuinely intractable.

This is the H1 hypothesis from the v15 improvement plan.
"""

from agents.archimedes.agent import ArchimedesAgent

__all__ = ["ArchimedesAgent"]
