# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Metadata schemas for the Alexandrie scientific storage hub."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class RoomType(Enum):
    """Access level for Alexandrie storage rooms."""

    OPEN_ACCESS = auto()  # Publicly available scientific artifacts
    PRIVATE = auto()      # Encrypted/restricted intellectual property (Frugal IP protection)


class ArtifactType(Enum):
    """Types of scientific artifacts stored in Alexandrie."""

    MODEL = auto()          # GGUF, SafeTensors, ONNX, G_Socratique weights
    CHECKPOINT = auto()     # RLCF training checkpoints, LoRA adapters
    DATASET = auto()        # Empirical data, ODE trajectories, CSVs
    PAPER = auto()          # LaTeX PDFs, markdown drafts, academic papers
    PROOF = auto()          # Lean 4 proof source code, DeepProbLog files
    PROTOCOL = auto()       # Scientific experiment reproduction guides
    EXPLANATION = auto()    # Blog posts, courses, conceptual documentation
    SYMPOSIUM = auto()      # Complete Symposium run package
    AUDIT_TRAIL = auto()    # Scientific audit trail JSONL
    MONOGRAPH = auto()      # Multi-chapter formal monograph
    SIMULATION = auto()     # Numerical simulation results + figures

    # Discovery Pipeline types (v4.2+)
    DISCOVERY = auto()      # Complete discovery run package (conjectures + proofs)
    CONJECTURE = auto()     # Unproven mathematical conjecture (private until proven)
    LATEX_INDEX = auto()    # LaTeX index page for open room visualization


@dataclass(slots=True)
class ArtifactMetadata:
    """Rigorous metadata structure for an Alexandrie scientific artifact.

    Patent: US-PAT-PEND-2026-0525
    """

    id: str
    title: str
    artifact_type: ArtifactType
    room_type: RoomType
    creator: str
    timestamp: float
    sha256_hash: str
    tags: list[str] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)  # e.g., accuracy, conservation ratio
    dependencies: list[str] = field(default_factory=list)  # IDs of dependent artifacts
    extra_attributes: dict[str, Any] = field(default_factory=dict)
