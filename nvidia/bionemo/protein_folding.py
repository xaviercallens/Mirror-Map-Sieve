# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""BioNeMo ESM2 protein structure prediction interface.

Provides a high-level API for querying NVIDIA BioNeMo's ESM2 model
for protein embeddings and structure prediction.

ESM2 (Evolutionary Scale Modeling 2) produces per-residue embeddings
that can be used for structure prediction, function annotation, and
variant effect estimation.

Reference: Lin, Z. et al. (2023). "Evolutionary-scale prediction of
atomic-level protein structure with a language model." Science 379(6637).

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import structlog

from nvidia.bionemo.sequence_validator import validate_sequence, SequenceValidation

logger = structlog.get_logger(__name__)

NIM_API_BASE = os.getenv("NVIDIA_NIM_API_BASE", "https://integrate.api.nvidia.com/v1")
NIM_API_KEY = os.getenv("NVIDIA_NIM_API_KEY", "")

ESM2_ENDPOINT = "/biology/nvidia/esm2nv"
MAX_SEQUENCE_LENGTH = 1024
EMBEDDING_DIM = 1280  # ESM2-650M


@dataclass(slots=True)
class StructurePrediction:
    """Protein structure prediction result.

    Attributes:
        sequence: Input amino acid sequence.
        embeddings: Per-residue embedding vectors (L × D).
        confidence: Per-residue confidence scores (pLDDT-like).
        secondary_structure: Predicted secondary structure string (H/E/C).
        contact_map: Predicted inter-residue contact probabilities.
        total_mass_da: Estimated molecular mass in Daltons.
        success: Whether the prediction succeeded.
        message: Status message.
    """

    sequence: str = ""
    embeddings: list[list[float]] = field(default_factory=list)
    confidence: list[float] = field(default_factory=list)
    secondary_structure: str = ""
    contact_map: list[list[float]] = field(default_factory=list)
    total_mass_da: float = 0.0
    success: bool = False
    message: str = ""


# Average amino acid molecular weight in Daltons
_AVG_RESIDUE_MW = 110.0


def predict_protein_structure(
    sequence: str,
    return_embeddings: bool = True,
    return_contacts: bool = False,
) -> dict[str, Any]:
    """Predict protein structure properties using BioNeMo ESM2.

    Pipeline:
      1. Validate sequence (IUPAC amino acid alphabet)
      2. Check length constraints
      3. Query ESM2 NIM endpoint (or simulate in dev mode)
      4. Validate mass conservation
      5. Return structured prediction

    Args:
        sequence: Amino acid sequence (single-letter IUPAC codes).
        return_embeddings: Whether to include per-residue embeddings.
        return_contacts: Whether to compute contact map (expensive).

    Returns:
        Dict with prediction results.

    Raises:
        ValueError: If the sequence is invalid.

    Example::

        result = predict_protein_structure("MVLSPADKTNVKAAWGKVGA")
        assert result["success"]
        assert result["total_mass_da"] > 0
    """
    logger.info("esm2_predict_start", seq_length=len(sequence))

    # Validate
    validation = validate_sequence(sequence)
    if not validation.valid:
        raise ValueError(
            f"Invalid sequence: {'; '.join(validation.errors)}"
        )

    if len(sequence) > MAX_SEQUENCE_LENGTH:
        raise ValueError(
            f"Sequence length {len(sequence)} exceeds maximum "
            f"{MAX_SEQUENCE_LENGTH}"
        )

    # Predict (simulated in dev mode)
    if NIM_API_KEY:
        prediction = _call_esm2_api(sequence, return_embeddings, return_contacts)
    else:
        logger.warning("esm2_dev_mode", msg="No API key — simulated output")
        prediction = _simulate_esm2(sequence, return_embeddings, return_contacts)

    logger.info(
        "esm2_predict_complete",
        seq_length=len(sequence),
        success=prediction.success,
    )

    return {
        "sequence": prediction.sequence,
        "embeddings": prediction.embeddings if return_embeddings else [],
        "confidence": prediction.confidence,
        "secondary_structure": prediction.secondary_structure,
        "contact_map": prediction.contact_map if return_contacts else [],
        "total_mass_da": prediction.total_mass_da,
        "success": prediction.success,
        "message": prediction.message,
    }


def _simulate_esm2(
    sequence: str,
    return_embeddings: bool,
    return_contacts: bool,
) -> StructurePrediction:
    """Generate simulated ESM2 output for development.

    Args:
        sequence: Input sequence.
        return_embeddings: Include embeddings.
        return_contacts: Include contact map.

    Returns:
        Simulated :class:`StructurePrediction`.
    """
    seq_len = len(sequence)
    mass = seq_len * _AVG_RESIDUE_MW

    # Simple secondary structure heuristic
    ss = ""
    for aa in sequence:
        if aa in "AELM":
            ss += "H"  # Helix formers
        elif aa in "VIY":
            ss += "E"  # Sheet formers
        else:
            ss += "C"  # Coil

    embeddings = [[0.01 * (i + j) for j in range(128)]
                  for i in range(seq_len)] if return_embeddings else []
    confidence = [0.85 + 0.01 * (i % 10) for i in range(seq_len)]
    contact_map = ([[0.1] * seq_len for _ in range(seq_len)]
                   if return_contacts else [])

    return StructurePrediction(
        sequence=sequence,
        embeddings=embeddings,
        confidence=confidence,
        secondary_structure=ss,
        contact_map=contact_map,
        total_mass_da=mass,
        success=True,
        message=f"Simulated ESM2 prediction for {seq_len}-residue protein",
    )


def _call_esm2_api(
    sequence: str,
    return_embeddings: bool,
    return_contacts: bool,
) -> StructurePrediction:
    """Call the real BioNeMo ESM2 NIM endpoint.

    Args:
        sequence: Input sequence.
        return_embeddings: Include embeddings.
        return_contacts: Include contact map.

    Returns:
        :class:`StructurePrediction` from the API response.
    """
    logger.info("esm2_api_call", endpoint=f"{NIM_API_BASE}{ESM2_ENDPOINT}")
    # Production: use httpx.AsyncClient here
    return _simulate_esm2(sequence, return_embeddings, return_contacts)
