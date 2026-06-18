# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""BioNeMo protein science integrations."""

from nvidia.bionemo.protein_folding import predict_protein_structure
from nvidia.bionemo.sequence_validator import validate_sequence

__all__ = ["predict_protein_structure", "validate_sequence"]
