# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""IUPAC amino acid sequence validator.

Validates protein sequences against the standard 20-letter IUPAC
amino acid alphabet, with optional support for ambiguity codes
(B, J, X, Z) and selenocysteine (U) / pyrrolysine (O).

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)

# Standard 20 amino acids
STANDARD_AA = set("ACDEFGHIKLMNPQRSTVWY")

# Extended alphabet (ambiguity + rare)
EXTENDED_AA = STANDARD_AA | {"B", "J", "O", "U", "X", "Z"}

# Minimum sequence length for meaningful analysis
MIN_LENGTH = 5

# Maximum sequence length for ESM2
MAX_LENGTH = 1024


@dataclass(slots=True)
class SequenceValidation:
    """Sequence validation result.

    Attributes:
        valid: Whether the sequence passed all checks.
        sequence: The cleaned (uppercase, whitespace-stripped) sequence.
        length: Sequence length.
        composition: Amino acid frequency dict.
        errors: List of validation errors.
        warnings: List of non-fatal warnings.
    """

    valid: bool = True
    sequence: str = ""
    length: int = 0
    composition: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_sequence(
    sequence: str,
    allow_extended: bool = False,
    min_length: int = MIN_LENGTH,
    max_length: int = MAX_LENGTH,
) -> SequenceValidation:
    """Validate an amino acid sequence.

    Checks:
      - Non-empty after stripping whitespace
      - Length within ``[min_length, max_length]``
      - All characters in the valid alphabet
      - No unusual composition (e.g., 100% of one amino acid)

    Args:
        sequence: Raw sequence string.
        allow_extended: If ``True``, allow ambiguity codes (B, J, X, Z)
            and rare amino acids (U, O).
        min_length: Minimum acceptable length.
        max_length: Maximum acceptable length.

    Returns:
        :class:`SequenceValidation` result.

    Example::

        result = validate_sequence("MVLSPADKTNVKAAWGKVGA")
        assert result.valid
        assert result.length == 20
    """
    result = SequenceValidation()

    # Clean
    cleaned = sequence.upper().replace(" ", "").replace("\n", "").replace("\r", "")
    result.sequence = cleaned
    result.length = len(cleaned)

    # Empty check
    if not cleaned:
        result.valid = False
        result.errors.append("Sequence is empty")
        return result

    # Length checks
    if len(cleaned) < min_length:
        result.valid = False
        result.errors.append(
            f"Sequence too short: {len(cleaned)} < {min_length} residues"
        )

    if len(cleaned) > max_length:
        result.valid = False
        result.errors.append(
            f"Sequence too long: {len(cleaned)} > {max_length} residues"
        )

    # Alphabet check
    alphabet = EXTENDED_AA if allow_extended else STANDARD_AA
    invalid_chars = set(cleaned) - alphabet
    if invalid_chars:
        result.valid = False
        result.errors.append(
            f"Invalid characters: {sorted(invalid_chars)}. "
            f"Expected: {sorted(alphabet)}"
        )

    # Composition
    composition: dict[str, int] = {}
    for char in cleaned:
        composition[char] = composition.get(char, 0) + 1
    result.composition = composition

    # Composition warnings
    if len(cleaned) > 0:
        max_freq = max(composition.values()) / len(cleaned)
        if max_freq > 0.5:
            dominant = max(composition, key=composition.get)  # type: ignore[arg-type]
            result.warnings.append(
                f"Unusual composition: {dominant} accounts for "
                f"{max_freq:.0%} of residues"
            )

    # Extended alphabet warnings
    if allow_extended:
        extended_only = set(cleaned) & (EXTENDED_AA - STANDARD_AA)
        if extended_only:
            result.warnings.append(
                f"Extended alphabet characters present: {sorted(extended_only)}"
            )

    logger.debug(
        "sequence_validated",
        valid=result.valid,
        length=result.length,
        errors=result.errors,
    )

    return result
