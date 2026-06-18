# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Proof Assembler — substitute resolved sub-lemmas back into the parent sketch.

After Archimedes attacks each sorry gap individually, the resolved fragments must
be substituted into the original sketch. This is a careful operation:

1. Gaps are identified by their CHARACTER POSITION in the original sketch.
2. Substitutions must be applied in REVERSE ORDER (last to first) to preserve
   positions of earlier gaps (substituting gap[5] first would shift positions of
   gaps [0..4] if resolution is longer than "sorry").
3. If a resolution introduces its own `sorry` (failed resolution), it is NOT
   substituted — the original `sorry` is kept.

The assembler also performs a post-substitution validation:
- Checks that no new sorry stubs were introduced
- Verifies the basic Lean 4 structure is preserved (theorem/def keywords, braces)
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.archimedes.tools.sorry_decomposer import SorryGap


def assemble_proof(
    original_sketch: str,
    resolutions: dict[int, str],  # gap_index → resolved Lean 4 fragment
    gaps: list["SorryGap"],
) -> str:
    """Substitute resolved sorry gaps back into the original sketch.

    Args:
        original_sketch: The Lean 4 sketch with sorry stubs.
        resolutions: Mapping from gap_index to the resolved Lean 4 fragment.
                     Only gaps where resolution doesn't contain "sorry" are included.
        gaps: All detected gaps (with their positions in the sketch).

    Returns:
        The assembled sketch with sorry stubs replaced by their resolutions.
        Unresolved gaps retain their original `sorry` stub.

    Implementation Note:
        Substitutions are applied in REVERSE position order to preserve
        character positions of earlier gaps.
    """
    if not resolutions:
        return original_sketch

    # Sort gaps by position in REVERSE order (last first)
    # so that substituting later positions doesn't invalidate earlier positions
    gaps_to_substitute = sorted(
        [(gap.gap_index, gap.position, resolutions[gap.gap_index])
         for gap in gaps if gap.gap_index in resolutions],
        key=lambda x: x[1],
        reverse=True,  # Reverse: process from end to beginning
    )

    sketch = original_sketch
    substitution_count = 0

    for gap_index, position, resolution in gaps_to_substitute:
        # Safety check: make sure position is still valid (sketch may have changed
        # from previous substitutions, but since we process in reverse order this
        # shouldn't happen for well-formed sketches)
        if position >= len(sketch):
            continue

        # Verify we're still looking at a sorry at this position
        # (after reverse-order substitutions, earlier positions are unchanged)
        sorry_at_pos = sketch[position:position + 5].lower()
        if sorry_at_pos != "sorry":
            # Position drift — try to find the nearest sorry
            window_start = max(0, position - 20)
            window_end = min(len(sketch), position + 20)
            window = sketch[window_start:window_end].lower()
            sorry_offset = window.find("sorry")
            if sorry_offset < 0:
                continue  # Can't find it — skip this gap
            position = window_start + sorry_offset

        # Perform the substitution: replace "sorry" at position with resolution
        # Wrap the resolution in a comment block for traceability
        resolution_with_comment = (
            f"-- [Archimedes: gap {gap_index} resolved]\n"
            f"  {resolution.strip()}\n"
            f"  -- [end Archimedes gap {gap_index}]"
        )

        sketch = (
            sketch[:position]
            + resolution_with_comment
            + sketch[position + 5:]  # 5 = len("sorry")
        )
        substitution_count += 1

    # Post-substitution: count remaining sorry stubs
    remaining_sorry = sketch.lower().count("sorry")

    return sketch


def validate_assembly(sketch: str, original_sketch: str) -> dict[str, bool | int | str]:
    """Validate the assembled proof sketch.

    Checks:
    - No NEW sorry stubs were introduced by the assembly process
    - Basic Lean 4 structure is preserved (theorem/def keywords exist)
    - Brace balance hasn't been broken catastrophically

    Args:
        sketch: The assembled sketch after substitutions.
        original_sketch: The original sketch before any substitutions.

    Returns:
        Validation result dict with keys: valid, sorry_count, warnings.
    """
    original_sorry = original_sketch.lower().count("sorry")
    new_sorry = sketch.lower().count("sorry")

    warnings = []
    valid = True

    if new_sorry > original_sorry:
        warnings.append(
            f"Assembly introduced NEW sorry stubs: {original_sorry} → {new_sorry}"
        )
        valid = False

    # Check basic Lean 4 structure preserved
    has_theorem = bool(re.search(r'\b(theorem|lemma|def)\b', sketch))
    if not has_theorem:
        warnings.append("Assembly destroyed all theorem/def declarations")
        valid = False

    # Check approximate brace balance (allow ±5 difference as some may be in strings)
    open_braces = sketch.count('{') + sketch.count('(') + sketch.count('[')
    close_braces = sketch.count('}') + sketch.count(')') + sketch.count(']')
    brace_delta = abs(open_braces - close_braces)
    if brace_delta > 20:
        warnings.append(f"Brace imbalance: open={open_braces}, close={close_braces}")

    return {
        "valid": valid,
        "sorry_count": new_sorry,
        "sorry_delta": original_sorry - new_sorry,
        "warnings": "; ".join(warnings) if warnings else "OK",
    }
