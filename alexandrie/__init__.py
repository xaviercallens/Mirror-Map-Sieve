# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Alexandrie — The Scientific Storage and Artifact Hub.

storing serialized models, pretrained checkpoints, scientific papers,
datasets, Lean 4 proofs, and educational content for the Scientific Agora.
Inspired by Hugging Face but built for neuro-symbolic, frugal AI.
"""

from alexandrie.hub import AlexandrieHub
from alexandrie.metadata import ArtifactMetadata, ArtifactType, RoomType
from alexandrie.science_library import LessonLearned, ScienceLibrary

__all__ = [
    "AlexandrieHub",
    "ArtifactMetadata",
    "ArtifactType",
    "LessonLearned",
    "RoomType",
    "ScienceLibrary",
]

