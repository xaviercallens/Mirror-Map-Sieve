# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Sorry Gap Decomposer — parse and classify sorry stubs in Lean 4 sketches.

Each `sorry` stub in a Lean 4 proof represents a specific mathematical gap.
This module:
  1. Locates every `sorry` occurrence in the sketch
  2. Extracts surrounding context (theorem signature, goal type)
  3. Classifies the gap type (definition, lemma, convergence, existence, etc.)
  4. Generates a targeted sub-proof description for Galois to attack

Gap classification is crucial: a "missing definition" gap needs a different
prompt than a "convergence argument" gap.

Reference: Lean 4 sorry semantics:
  https://leanprover.github.io/lean4/doc/sorry.html
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


# ── Gap Classification ────────────────────────────────────────────────────────

class SorryGapType(str, Enum):
    """Classification of sorry gap types, ordered from easiest to hardest to resolve."""

    # Likely resolvable with `decide`, `norm_num`, or `simp`
    DECIDABLE = "decidable"

    # Missing type or structure definition — often a `noncomputable def ... := sorry`
    DEFINITION = "definition"

    # A standard lemma step — often `theorem X := sorry` inside a proof
    LEMMA = "lemma"

    # Convergence of a sequence, limit argument, ε-δ reasoning
    CONVERGENCE = "convergence"

    # Inequality or bound claim — `f(x) ≤ g(x) := sorry`
    INEQUALITY = "inequality"

    # Existence or uniqueness claim — `∃ x, P x := sorry`
    EXISTENCE = "existence"

    # Analytic continuation, contour integration, special function identity
    ANALYTIC = "analytic"

    # Algebraic identity or ring/field manipulation
    ALGEBRAIC = "algebraic"

    # Topological or set-theoretic argument
    TOPOLOGICAL = "topological"

    # Genuinely intractable: Mathlib4 coverage gap or open problem
    INTRACTABLE = "intractable"

    # Unclassified
    UNKNOWN = "unknown"


# ── Heuristic Classification Rules ───────────────────────────────────────────

# Each rule: (regex pattern on context, gap_type, confidence)
# Patterns are checked against the 120-char window around the sorry
_CLASSIFICATION_RULES: list[tuple[re.Pattern[str], SorryGapType, float]] = [
    # ── High-priority domain-specific patterns (checked first) ─────────────────
    # Convergence / limit / tendsto (conf=0.92 — beats definition at 0.85)
    (re.compile(r'\b(Tendsto|Filter\.Tendsto|atTop|nhds|lim|Cauchy|converge|summable)\b', re.I), SorryGapType.CONVERGENCE, 0.92),
    (re.compile(r'\bε\b|\bepsilon\b|\bdelta\b.*bound', re.I), SorryGapType.CONVERGENCE, 0.78),

    # Analytic: special functions, integrals, zeta, Bessel, Gamma (conf=0.90)
    (re.compile(r'\b(integral|integral\'|Complex\.integral|contour|residue|zeta|Gamma|Beta|Bessel|MZV|mzv|CuspForm)\b', re.I), SorryGapType.ANALYTIC, 0.90),
    (re.compile(r'\b(holomorphic|meromorphic|modular|L-function|EllipticCurve)\b', re.I), SorryGapType.ANALYTIC, 0.88),

    # Existence / ∃ claim (conf=0.88)
    (re.compile(r'(∃|Exists\.intro|Finset\.mem|Set\.mem_range)\b.*sorry', re.I | re.S), SorryGapType.EXISTENCE, 0.88),
    (re.compile(r'\buniqueness\b|\bunique\b.*exists', re.I), SorryGapType.EXISTENCE, 0.78),

    # Inequality / bound (conf=0.85)
    (re.compile(r'[≤≥].*sorry|sorry.*[≤≥]|\b(le_|lt_|ge_|gt_)\b.*sorry', re.I | re.S), SorryGapType.INEQUALITY, 0.87),
    (re.compile(r'\b(bound|positivity|linarith|nlinarith|upperBound|lowerBound)\b', re.I), SorryGapType.INEQUALITY, 0.73),

    # ── Mid-priority structural patterns ────────────────────────────────────────
    # Definition-level sorry — noncomputable def / structure field
    (re.compile(r'\bnoncomputable\s+def\b', re.I), SorryGapType.DEFINITION, 0.86),
    (re.compile(r'\bdef\b[^:=\n]{0,80}:=\s*sorry', re.I | re.S), SorryGapType.DEFINITION, 0.82),
    (re.compile(r'\binstance\b.*:=\s*sorry', re.I | re.S), SorryGapType.DEFINITION, 0.80),

    # Algebraic: ring, field, group, Galois (conf=0.80)
    (re.compile(r'\b(GaloisGroup|CharP|Polynomial\.|Matrix\.|LinearMap\.|AlgHom)\b', re.I), SorryGapType.ALGEBRAIC, 0.82),
    (re.compile(r'\b(ring|field_simp|group|module|ideal|homomorphism|isomorphism)\b', re.I), SorryGapType.ALGEBRAIC, 0.78),

    # Topological: topology, manifold, homotopy, compactness (conf=0.80)
    (re.compile(r'\b(IsOpen|IsClosed|Compact|Continuous|Manifold|homotopy|TopologicalSpace)\b', re.I), SorryGapType.TOPOLOGICAL, 0.82),

    # Decidable / computable (conf=0.80)
    (re.compile(r'\b(decide|norm_num|omega|rfl|native_decide)\b', re.I), SorryGapType.DECIDABLE, 0.80),

    # ── Low-priority fallback ─────────────────────────────────────────────────
    # Generic lemma/theorem stub — lowest priority
    (re.compile(r'\b(theorem|lemma)\s+\w+', re.I), SorryGapType.LEMMA, 0.60),
]


# ── SorryGap Dataclass ────────────────────────────────────────────────────────

@dataclass
class SorryGap:
    """One sorry stub identified in a Lean 4 sketch.

    Attributes:
        gap_index: 0-based index of this sorry in the sketch.
        position: Character position of `sorry` in the full sketch string.
        context_before: Up to CONTEXT_WINDOW chars immediately before sorry.
        context_after: Up to CONTEXT_WINDOW chars immediately after sorry.
        gap_type: Classified type of the gap.
        classification_confidence: Heuristic confidence [0, 1].
        claim_description: Human-readable description of what needs to be proven.
        lean4_goal_type: Extracted Lean 4 goal type (if parseable).
        suggested_tactics: List of Lean 4 tactics likely to work.
    """
    gap_index: int = 0
    position: int = 0
    context_before: str = ""
    context_after: str = ""
    gap_type: SorryGapType = SorryGapType.UNKNOWN
    classification_confidence: float = 0.0
    claim_description: str = ""
    lean4_goal_type: str = ""
    suggested_tactics: list[str] = field(default_factory=list)


# ── Core Decomposition Function ───────────────────────────────────────────────

def decompose_sorry_gaps(
    lean4_sketch: str,
    problem_context: str = "",
    domain: str = "unknown",
    context_window: int = 120,
) -> list[SorryGap]:
    """Locate and classify all sorry stubs in a Lean 4 sketch.

    Args:
        lean4_sketch: The Lean 4 proof sketch containing sorry stubs.
        problem_context: Original problem description (for claim generation).
        domain: Mathematical domain (informs classification confidence).
        context_window: Characters of context to capture around each sorry.

    Returns:
        List of :class:`SorryGap` objects, one per sorry occurrence,
        sorted by position (first occurrence first).
    """
    gaps: list[SorryGap] = []

    # ── Step 1: Locate every sorry ────────────────────────────────────────────
    # Use word-boundary matching to avoid matching 'sorry_state' etc.
    sorry_pattern = re.compile(r'\bsorry\b', re.IGNORECASE)
    for gap_idx, match in enumerate(sorry_pattern.finditer(lean4_sketch)):
        pos = match.start()

        # Extract surrounding context
        before_start = max(0, pos - context_window)
        after_end = min(len(lean4_sketch), pos + 5 + context_window)

        context_before = lean4_sketch[before_start:pos]
        context_after = lean4_sketch[pos + 5:after_end]

        # ── Step 2: Classify the gap ──────────────────────────────────────────
        local_context = context_before + " sorry " + context_after

        gap_type = SorryGapType.UNKNOWN
        best_confidence = 0.0
        for pattern, candidate_type, confidence in _CLASSIFICATION_RULES:
            if pattern.search(local_context):
                if confidence > best_confidence:
                    gap_type = candidate_type
                    best_confidence = confidence

        # ── Step 3: Extract Lean 4 goal type ─────────────────────────────────
        lean4_goal_type = _extract_goal_type(context_before)

        # ── Step 4: Build claim description ──────────────────────────────────
        claim_description = _build_claim_description(
            gap_type=gap_type,
            context_before=context_before,
            context_after=context_after,
            lean4_goal_type=lean4_goal_type,
            domain=domain,
        )

        # ── Step 5: Suggest tactics ───────────────────────────────────────────
        suggested_tactics = _suggest_tactics(gap_type, domain)

        gaps.append(SorryGap(
            gap_index=gap_idx,
            position=pos,
            context_before=context_before,
            context_after=context_after,
            gap_type=gap_type,
            classification_confidence=best_confidence,
            claim_description=claim_description,
            lean4_goal_type=lean4_goal_type,
            suggested_tactics=suggested_tactics,
        ))

    return gaps


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_goal_type(context_before: str) -> str:
    """Try to extract the Lean 4 goal type from the theorem/lemma signature.

    Looks for patterns like `theorem name (args) : TYPE :=` or `have h : TYPE :=`.
    Returns the TYPE string if found, otherwise empty string.
    """
    # Pattern: theorem/lemma/have ... : TYPE :=
    # We look backwards from the sorry for the most recent `:` that introduces a type
    patterns = [
        r'(?:theorem|lemma|def)\s+\w+[^:]*:\s*([^:=]+)\s*:=\s*(?:by\s*)?$',
        r'\bhave\s+\w+\s*:\s*([^:=]+)\s*:=\s*(?:by\s*)?$',
        r':\s*([^:=\n]+)\s*:=\s*sorry\s*$',
    ]
    for pattern in patterns:
        m = re.search(pattern, context_before.strip(), re.DOTALL)
        if m:
            return m.group(1).strip()[:200]  # Cap at 200 chars
    return ""


def _build_claim_description(
    gap_type: SorryGapType,
    context_before: str,
    context_after: str,
    lean4_goal_type: str,
    domain: str,
) -> str:
    """Build a human-readable description of what needs to be proven at this gap."""
    if lean4_goal_type:
        base = f"Prove: {lean4_goal_type}"
    else:
        # Fall back to the last meaningful line before sorry
        lines = [l.strip() for l in context_before.split('\n') if l.strip()]
        last_line = lines[-1] if lines else context_before[-80:].strip()
        base = f"Prove the claim implied by: {last_line}"

    type_descriptions = {
        SorryGapType.DECIDABLE: f"{base} (likely decidable by norm_num/ring/omega)",
        SorryGapType.DEFINITION: f"Provide a concrete Lean 4 definition (replacing `sorry` body): {base}",
        SorryGapType.LEMMA: f"Prove auxiliary lemma: {base}",
        SorryGapType.CONVERGENCE: f"Prove convergence/limit argument: {base}",
        SorryGapType.EXISTENCE: f"Prove existence (and construct witness): {base}",
        SorryGapType.INEQUALITY: f"Prove inequality/bound: {base}",
        SorryGapType.ANALYTIC: f"Prove analytic identity (domain={domain}): {base}",
        SorryGapType.ALGEBRAIC: f"Prove algebraic identity: {base}",
        SorryGapType.TOPOLOGICAL: f"Prove topological claim: {base}",
        SorryGapType.INTRACTABLE: f"[LIKELY INTRACTABLE] {base}",
        SorryGapType.UNKNOWN: base,
    }
    return type_descriptions.get(gap_type, base)


def _suggest_tactics(gap_type: SorryGapType, domain: str) -> list[str]:
    """Suggest Lean 4 tactics most likely to work for this gap type."""
    base_tactics = {
        SorryGapType.DECIDABLE: ["decide", "norm_num", "ring", "omega", "simp [Nat.succ_pos]"],
        SorryGapType.DEFINITION: ["exact ⟨⟩", "refine ⟨_, _, _⟩", "constructor"],
        SorryGapType.LEMMA: ["apply?", "exact?", "simp [*]", "tauto", "aesop"],
        SorryGapType.CONVERGENCE: [
            "apply Filter.Tendsto.comp", "exact tendsto_const_nhds",
            "apply Real.tendsto_pow_atTop_nhds_zero_of_lt_one",
        ],
        SorryGapType.EXISTENCE: ["exact ⟨_, rfl⟩", "refine ⟨?_, ?_⟩", "use _; ring"],
        SorryGapType.INEQUALITY: ["linarith", "nlinarith", "positivity", "bound_tac"],
        SorryGapType.ANALYTIC: [
            "simp [Real.integral_comp_mul_right]",
            "apply MeasureTheory.integral_congr_ae",
            "exact Complex.ext_iff.mpr",
        ],
        SorryGapType.ALGEBRAIC: ["ring", "field_simp", "group", "norm_cast"],
        SorryGapType.TOPOLOGICAL: [
            "exact isOpen_univ", "apply IsOpen.inter",
            "exact IsClosed.closure_eq rfl",
        ],
        SorryGapType.INTRACTABLE: [],
        SorryGapType.UNKNOWN: ["simp", "aesop", "tauto", "decide"],
    }
    return base_tactics.get(gap_type, ["simp", "aesop"])
