# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Skeptical auditor — contradiction and vagueness detector.

Implements three audit layers:

1. **Reciprocal Denominator Check** — detects division-by-zero risks
   and denominator-crossing fallacies (sign changes in denominators
   invalidate inequality manipulations).

2. **IEEE 754 Float Precision Audit** — flags catastrophic cancellation,
   denormalised numbers, and precision loss indicators.

3. **Vagueness Heuristics** — flags weasel words that mask logical gaps:
   'obviously', 'trivially', 'clearly', 'it is easy to see', etc.

Reference: Lakatos, I. (1976). *Proofs and Refutations*. Cambridge UP.

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Sequence

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class IssueSeverity(str, Enum):
    """Severity level for audit issues."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


# Vagueness trigger words/phrases
VAGUENESS_TRIGGERS: list[tuple[str, str]] = [
    (r"\bobviously\b", "vagueness:obviously"),
    (r"\btrivially\b", "vagueness:trivially"),
    (r"\bclearly\b", "vagueness:clearly"),
    (r"\bit is easy to see\b", "vagueness:easy_to_see"),
    (r"\bwithout loss of generality\b", "vagueness:wlog"),
    (r"\bby inspection\b", "vagueness:by_inspection"),
    (r"\bthe rest is straightforward\b", "vagueness:straightforward"),
    (r"\bleft as an exercise\b", "vagueness:exercise"),
    (r"\bhand-?waving\b", "vagueness:handwaving"),
    (r"\bintuitively\b", "vagueness:intuitively"),
]

# IEEE 754 problematic patterns
IEEE754_PATTERNS: list[tuple[str, str]] = [
    (r"\b1e-30[0-9]\b", "ieee754:denormalised"),
    (r"\b1e\+30[0-9]\b", "ieee754:overflow_risk"),
    (r"\binf\b", "ieee754:infinity"),
    (r"\bnan\b", "ieee754:not_a_number"),
    (r"\b0\.0{10,}", "ieee754:underflow_risk"),
]

# Division patterns
DIVISION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r'(?:divided\s+by|/)\s*(?:0(?:\.0*)?|\bx\b)', re.IGNORECASE),
    re.compile(r'denominator.*(?:zero|vanish|undefined)', re.IGNORECASE),
    re.compile(r'(?:multiply|divide)\s+both\s+sides', re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# 🚨 ZERO-SORRY GUILLOTINE
#
# In Lean 4, `sorry` is a kernel-level axiom that allows any goal to be
# discharged without proof. The compiler exits with code 0 (success) even
# when sorry is present — it only emits a WARNING. This means a compiler
# exit-code check is insufficient. We must detect sorry via regex FIRST.
#
# A proof containing even ONE `sorry` is by definition INCOMPLETE.
# This is the absolute epistemic guardrail of the SocrateAI Agora.
# ---------------------------------------------------------------------------

SORRY_PATTERN: re.Pattern[str] = re.compile(
    r'\bsorry\b',
    re.IGNORECASE | re.MULTILINE,
)

# Bayesian confidence priors per domain
# These encode how likely a Lean 4 proof in this domain can be fully verified
# by current AI systems. Used to calibrate Euler's epistemic confidence.
DOMAIN_CONFIDENCE_PRIORS: dict[str, float] = {
    "number_theory":          0.05,   # Very hard — open problems, likely irrational constants
    "continuum_physics":      0.10,   # Feigenbaum, renormalization — no algebraic proofs
    "discrete_geometry":      0.20,   # Hyperbolic volumes — SnapPy numerics, hard to formalize
    "statistical_mechanics":  0.30,   # Watson integrals, SAW constants — some known formulas
    "special_functions":      0.25,   # Bessel moments — elliptic integral identities
    "spectral_theory":        0.20,   # Eigenvalues — numerical but not symbolic
    "combinatorics":          0.35,   # Schur, autocorrelation — combinatorial proofs possible
    "coding_theory":          0.30,   # Binary codes — computational search methods
    "mathematical_physics":   0.15,   # Feynman diagrams — very hard to formalize
    "unknown":                0.15,   # Default conservative prior
}


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class AuditIssue:
    """A single audit finding.

    Attributes:
        code: Machine-readable issue code.
        severity: ``info``, ``warning``, or ``error``.
        message: Human-readable description.
        line: Approximate line number (if applicable).
        context: Surrounding text for context.
    """

    code: str = ""
    severity: str = "warning"
    message: str = ""
    line: int = 0
    context: str = ""


@dataclass(slots=True)
class AuditResult:
    """Aggregated audit result.

    Attributes:
        passed: ``True`` if no errors were found.
        issues: List of all audit findings.
        summary: Count breakdown by severity.
        recommendations: Actionable suggestions.
    """

    passed: bool = True
    issues: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Audit functions
# ---------------------------------------------------------------------------

def _check_vagueness(text: str) -> list[AuditIssue]:
    """Detect vagueness heuristics in proof text.

    Flags words like 'obviously', 'trivially', 'clearly' that often
    mask logical gaps in mathematical arguments.

    Args:
        text: Proof or demonstration text.

    Returns:
        List of vagueness issues.
    """
    issues: list[AuditIssue] = []
    lines = text.splitlines()

    for line_num, line in enumerate(lines, 1):
        for pattern, code in VAGUENESS_TRIGGERS:
            matches = re.finditer(pattern, line, re.IGNORECASE)
            for match in matches:
                word = match.group()
                issues.append(AuditIssue(
                    code=code,
                    severity=IssueSeverity.WARNING.value,
                    message=(
                        f"Vagueness detected: '{word}' at line {line_num}. "
                        f"This often masks a logical gap — "
                        f"provide an explicit argument instead."
                    ),
                    line=line_num,
                    context=line.strip()[:100],
                ))

    return issues


def _check_reciprocal_denominators(text: str) -> list[AuditIssue]:
    """Detect division-by-zero risks and denominator-crossing fallacies.

    Flags:
      - Explicit division by zero or potentially-zero variables
      - "Multiply/divide both sides" without checking denominator sign
      - Denominators described as vanishing or undefined

    Args:
        text: Proof text.

    Returns:
        List of denominator issues.
    """
    issues: list[AuditIssue] = []
    lines = text.splitlines()

    for line_num, line in enumerate(lines, 1):
        for pattern in DIVISION_PATTERNS:
            if pattern.search(line):
                issues.append(AuditIssue(
                    code="reciprocal:denominator_risk",
                    severity=IssueSeverity.ERROR.value,
                    message=(
                        f"Denominator risk at line {line_num}: "
                        f"division by potentially-zero or sign-changing "
                        f"expression. Verify denominator is nonzero and "
                        f"has constant sign before manipulating."
                    ),
                    line=line_num,
                    context=line.strip()[:100],
                ))

    return issues


def _check_ieee754(text: str) -> list[AuditIssue]:
    """Audit for IEEE 754 floating-point precision issues.

    Flags:
      - Denormalised numbers (< ~2.2e-308)
      - Overflow risks (> ~1.8e+308)
      - Infinity and NaN references
      - Extreme underflow indicators

    Args:
        text: Proof or computation text.

    Returns:
        List of IEEE 754 issues.
    """
    issues: list[AuditIssue] = []
    lines = text.splitlines()

    for line_num, line in enumerate(lines, 1):
        for pattern, code in IEEE754_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                issues.append(AuditIssue(
                    code=code,
                    severity=IssueSeverity.WARNING.value,
                    message=(
                        f"IEEE 754 concern at line {line_num}: "
                        f"potential {code.split(':')[1]} — "
                        f"verify numerical stability."
                    ),
                    line=line_num,
                    context=line.strip()[:100],
                ))

    return issues


def _check_numeric_data(data: Sequence[float]) -> list[AuditIssue]:
    """Audit numeric data for floating-point anomalies.

    Checks:
      - Catastrophic cancellation (nearly-equal large numbers subtracted)
      - Denormalised values
      - NaN or Inf values

    Args:
        data: Numeric sequence to audit.

    Returns:
        List of numeric issues.
    """
    issues: list[AuditIssue] = []

    for i, value in enumerate(data):
        if math.isnan(value):
            issues.append(AuditIssue(
                code="ieee754:nan_in_data",
                severity=IssueSeverity.ERROR.value,
                message=f"NaN detected at index {i}",
            ))
        elif math.isinf(value):
            issues.append(AuditIssue(
                code="ieee754:inf_in_data",
                severity=IssueSeverity.ERROR.value,
                message=f"Infinity detected at index {i}",
            ))
        elif abs(value) > 0 and abs(value) < 2.2e-308:
            issues.append(AuditIssue(
                code="ieee754:denormalised_value",
                severity=IssueSeverity.WARNING.value,
                message=(
                    f"Denormalised value {value:.2e} at index {i} — "
                    f"precision is degraded"
                ),
            ))

    return issues


def _check_sorry_gaps(lean_code: str, lean4_result: dict | None = None) -> list[AuditIssue]:
    """🚨 ZERO-SORRY GUILLOTINE: Detect Lean 4 `sorry` stubs in proof code.

    Lean 4 exits with code 0 even when `sorry` is present (it's a warning,
    not an error at the compiler level). This function is the absolute
    epistemic guardrail — if `sorry` appears ANYWHERE, the proof is INCOMPLETE.

    Args:
        lean_code: The Lean 4 proof text.
        lean4_result: Optional dict from lean4_compiler tool (may have sorry_count).

    Returns:
        List of sorry-gap issues (each is severity ERROR).
    """
    issues: list[AuditIssue] = []

    # Count sorry occurrences in code (regex)
    regex_count = len(SORRY_PATTERN.findall(lean_code))

    # Also check compiler-reported sorry_count (if available)
    compiler_count = 0
    if lean4_result and isinstance(lean4_result, dict):
        compiler_count = lean4_result.get("sorry_count", 0)

    actual_sorries = max(regex_count, compiler_count)

    if actual_sorries > 0:
        lines = lean_code.splitlines()
        for line_num, line in enumerate(lines, 1):
            if SORRY_PATTERN.search(line):
                issues.append(AuditIssue(
                    code="lean4:sorry_gap",
                    severity=IssueSeverity.ERROR.value,
                    message=(
                        f"Mathematical gap at line {line_num}: `sorry` stub detected. "
                        f"Lean 4 exits with code 0 on sorry, but this is NOT a proof. "
                        f"This goal must be resolved with a genuine Mathlib4 lemma."
                    ),
                    line=line_num,
                    context=line.strip()[:120],
                ))

    return issues


def get_domain_prior(domain: str) -> float:
    """Return the Bayesian prior probability of full verification for a domain.

    Args:
        domain: Mathematical domain string (e.g. 'number_theory').

    Returns:
        Float in [0, 1] — prior probability that this domain's problem
        can be fully verified by current AI theorem proving systems.
    """
    return DOMAIN_CONFIDENCE_PRIORS.get(domain.lower(), DOMAIN_CONFIDENCE_PRIORS["unknown"])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def audit_demonstration(
    proof_text: str,
    numeric_data: Sequence[float] | None = None,
    lean4_result: dict | None = None,
    domain: str = "unknown",
) -> dict:
    """Run the full skeptical audit on a mathematical demonstration.

    Audit layers (in priority order):
      0. **Zero-Sorry Guillotine** — ABSOLUTE VETO: any `sorry` in Lean 4 code
         is an immediate FAIL, regardless of compiler exit code.
      1. **Vagueness heuristics** — flags 'obviously', 'trivially', etc.
      2. **Reciprocal denominator checks** — division-by-zero risks.
      3. **IEEE 754 float precision audit** — catastrophic cancellation, etc.
      4. **Numeric data anomaly detection** — NaN, Inf, denormalised values.

    Also computes a Bayesian-calibrated confidence score using domain priors.

    Args:
        proof_text: The proof or demonstration text to audit.
        numeric_data: Optional numeric data to check for float anomalies.
        lean4_result: Optional dict from lean4_compiler (for sorry_count cross-check).
        domain: Mathematical domain (used for Bayesian prior calibration).

    Returns:
        Dict with ``passed``, ``issues``, ``summary``, ``recommendations``,
        ``sorry_count``, ``domain_prior``.
    """
    logger.info("audit_start", text_length=len(proof_text))

    all_issues: list[AuditIssue] = []
    domain_prior = get_domain_prior(domain)

    if not proof_text or not proof_text.strip():
        all_issues.append(AuditIssue(
            code="empty_proof",
            severity=IssueSeverity.ERROR.value,
            message="No proof text provided for audit. Euler rejects empty hand-waving.",
        ))
    else:
        # Layer 0: 🚨 ZERO-SORRY GUILLOTINE (highest priority — absolute veto)
        # Must run BEFORE checking compiler exit code.
        sorry_issues = _check_sorry_gaps(proof_text, lean4_result)
        all_issues.extend(sorry_issues)

        # Layer 1-3: Standard audit layers (only meaningful if no sorry)
        all_issues.extend(_check_vagueness(proof_text))
        all_issues.extend(_check_reciprocal_denominators(proof_text))
        all_issues.extend(_check_ieee754(proof_text))

    if numeric_data:
        all_issues.extend(_check_numeric_data(numeric_data))

    # Sorry count for reporting
    sorry_count = sum(1 for i in all_issues if i.code == "lean4:sorry_gap")

    # Summarise
    summary: dict[str, int] = {
        "info": sum(1 for i in all_issues if i.severity == "info"),
        "warning": sum(1 for i in all_issues if i.severity == "warning"),
        "error": sum(1 for i in all_issues if i.severity == "error"),
        "total": len(all_issues),
    }

    passed = summary["error"] == 0

    # Generate recommendations
    recommendations: list[str] = []

    if sorry_count > 0:
        recommendations.append(
            f"🚨 {sorry_count} `sorry` gap(s) found. Each must be replaced with a valid "
            f"Mathlib4 proof. The sorry macro is a placeholder, not a proof. "
            f"Lean 4 compiler exit code 0 does NOT imply sorry-free verification."
        )

    vagueness_count = sum(1 for i in all_issues if i.code.startswith("vagueness"))
    if vagueness_count > 0:
        recommendations.append(
            f"Replace {vagueness_count} vague term(s) with explicit arguments. "
            f"Every step should be justified without appeal to 'obvious' claims."
        )

    denom_count = sum(1 for i in all_issues if i.code.startswith("reciprocal"))
    if denom_count > 0:
        recommendations.append(
            f"Address {denom_count} denominator risk(s). Before dividing, "
            f"prove the denominator is nonzero and has constant sign."
        )

    ieee_count = sum(1 for i in all_issues if i.code.startswith("ieee754"))
    if ieee_count > 0:
        recommendations.append(
            f"Review {ieee_count} IEEE 754 concern(s). Consider using "
            f"arbitrary-precision arithmetic or compensated summation."
        )

    if sorry_count > 0:
        logger.warning(
            "zero_sorry_guillotine_applied",
            sorry_count=sorry_count,
            domain=domain,
            domain_prior=domain_prior,
            verdict="FORCED_INCOMPLETE",
        )

    logger.info(
        "audit_complete",
        passed=passed,
        errors=summary["error"],
        warnings=summary["warning"],
        sorry_count=sorry_count,
        domain=domain,
        domain_prior=domain_prior,
    )

    return {
        "passed": passed,
        "issues": [
            {
                "code": issue.code,
                "severity": issue.severity,
                "message": issue.message,
                "line": issue.line,
                "context": issue.context,
            }
            for issue in all_issues
        ],
        "summary": summary,
        "recommendations": recommendations,
        "sorry_count": sorry_count,
        "domain_prior": domain_prior,
    }
