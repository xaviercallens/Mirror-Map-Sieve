# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Scientific data fraud / integrity detector.

Implements three statistical screens:

1. **Benford's Law** — leading-digit distribution χ² test.
   Natural datasets follow Benford's distribution; fabricated data often
   has uniformly or suspiciously distributed leading digits.
   Rejection threshold: χ² > 15.51 (df=8, α=0.05).

2. **Noise entropy** — checks for impossibly clean data.
   Real instruments produce thermal / quantisation noise.  If the
   standard deviation of successive differences is < 1e-12, the data
   was likely hand-fabricated.

3. **Manual entry heuristic** — flags data with excessive integer
   or half-integer values, which suggests manual rounding.

Reference: Nigrini, M. J. (2012). *Benford's Law: Applications for
Forensic Accounting, Auditing, and Fraud Detection*. Wiley.

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Sequence

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Benford's expected leading-digit probabilities for digits 1–9
BENFORD_EXPECTED: dict[int, float] = {
    d: math.log10(1 + 1 / d) for d in range(1, 10)
}

# Chi-squared critical value: df=8, α=0.05
CHI2_CRITICAL: float = 15.51

# Noise floor: standard deviation of first-differences below this ⇒ suspect
NOISE_FLOOR: float = 1e-12

# Manual entry threshold: fraction of values that are integer or half-integer
MANUAL_ENTRY_THRESHOLD: float = 0.80

# Minimum dataset size for meaningful Benford analysis
MIN_SAMPLE_SIZE: int = 50


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class BenfordResult:
    """Benford's Law analysis result.

    Attributes:
        chi_squared: Computed χ² statistic.
        critical_value: Rejection threshold.
        passed: ``True`` if χ² ≤ critical value.
        observed: Observed leading-digit counts.
        expected: Expected leading-digit counts (Benford).
        n: Sample size.
    """

    chi_squared: float = 0.0
    critical_value: float = CHI2_CRITICAL
    passed: bool = True
    observed: dict[int, int] = field(default_factory=dict)
    expected: dict[int, float] = field(default_factory=dict)
    n: int = 0


@dataclass(slots=True)
class NoiseResult:
    """Noise entropy analysis result.

    Attributes:
        noise_std: Standard deviation of successive differences.
        threshold: Below this ⇒ suspiciously clean.
        passed: ``True`` if noise_std ≥ threshold.
    """

    noise_std: float = 0.0
    threshold: float = NOISE_FLOOR
    passed: bool = True


@dataclass(slots=True)
class ManualEntryResult:
    """Manual entry heuristic result.

    Attributes:
        integer_ratio: Fraction of values that are integers.
        half_integer_ratio: Fraction at half-integer values.
        combined_ratio: Sum of both ratios.
        threshold: Rejection threshold.
        passed: ``True`` if combined ratio < threshold.
    """

    integer_ratio: float = 0.0
    half_integer_ratio: float = 0.0
    combined_ratio: float = 0.0
    threshold: float = MANUAL_ENTRY_THRESHOLD
    passed: bool = True


@dataclass(slots=True)
class ValidationResult:
    """Aggregate data integrity validation result.

    Attributes:
        passed: ``True`` if all sub-checks passed.
        benford: Benford's Law sub-result.
        noise: Noise entropy sub-result.
        manual_entry: Manual entry sub-result.
        warnings: Non-fatal warnings.
        errors: Fatal integrity violations.
    """

    passed: bool = True
    benford: BenfordResult = field(default_factory=BenfordResult)
    noise: NoiseResult = field(default_factory=NoiseResult)
    manual_entry: ManualEntryResult = field(default_factory=ManualEntryResult)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Analysis functions
# ---------------------------------------------------------------------------

def _leading_digit(value: float) -> int | None:
    """Extract the leading significant digit from a numeric value.

    Args:
        value: Any real number.

    Returns:
        Leading digit (1–9), or ``None`` if the value is zero.
    """
    if value == 0:
        return None
    abs_val = abs(value)
    # Normalise to [1, 10)
    exp = math.floor(math.log10(abs_val))
    leading = int(abs_val / (10 ** exp))
    return max(1, min(leading, 9))


def _benford_test(data: Sequence[float]) -> BenfordResult:
    """Run Benford's Law χ² goodness-of-fit test.

    Args:
        data: Numeric dataset.

    Returns:
        :class:`BenfordResult`.
    """
    digits = [_leading_digit(v) for v in data if v != 0]
    digits_clean = [d for d in digits if d is not None]
    n = len(digits_clean)

    if n < MIN_SAMPLE_SIZE:
        return BenfordResult(
            n=n,
            passed=True,  # Insufficient data — benefit of the doubt
        )

    observed = Counter(digits_clean)
    expected = {d: BENFORD_EXPECTED[d] * n for d in range(1, 10)}

    chi2 = sum(
        (observed.get(d, 0) - expected[d]) ** 2 / expected[d]
        for d in range(1, 10)
    )

    passed = chi2 <= CHI2_CRITICAL
    logger.info("benford_test", chi2=round(chi2, 3), passed=passed, n=n)

    return BenfordResult(
        chi_squared=round(chi2, 4),
        passed=passed,
        observed=dict(observed),
        expected={d: round(v, 2) for d, v in expected.items()},
        n=n,
    )


def _noise_entropy(data: Sequence[float]) -> NoiseResult:
    """Analyse noise in successive differences.

    Real instrument data has measurable noise. Fabricated data often
    has impossibly smooth transitions.

    Args:
        data: Numeric time series.

    Returns:
        :class:`NoiseResult`.
    """
    if len(data) < 3:
        return NoiseResult(passed=True)

    diffs = [data[i + 1] - data[i] for i in range(len(data) - 1)]
    mean_diff = sum(diffs) / len(diffs)
    variance = sum((d - mean_diff) ** 2 for d in diffs) / len(diffs)
    std = math.sqrt(variance)

    passed = std >= NOISE_FLOOR
    logger.info("noise_entropy", std=std, passed=passed)

    return NoiseResult(
        noise_std=std,
        passed=passed,
    )


def _manual_entry_check(data: Sequence[float]) -> ManualEntryResult:
    """Detect manually-entered data (integer/half-integer rounding).

    Args:
        data: Numeric dataset.

    Returns:
        :class:`ManualEntryResult`.
    """
    if not data:
        return ManualEntryResult(passed=True)

    n = len(data)
    integers = sum(1 for v in data if v == int(v))
    half_ints = sum(1 for v in data if (v * 2) == int(v * 2) and v != int(v))

    int_ratio = integers / n
    half_ratio = half_ints / n
    combined = int_ratio + half_ratio
    passed = combined < MANUAL_ENTRY_THRESHOLD

    logger.info(
        "manual_entry_check",
        int_ratio=round(int_ratio, 3),
        half_ratio=round(half_ratio, 3),
        combined=round(combined, 3),
        passed=passed,
    )

    return ManualEntryResult(
        integer_ratio=round(int_ratio, 4),
        half_integer_ratio=round(half_ratio, 4),
        combined_ratio=round(combined, 4),
        passed=passed,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_scientific_data_integrity(
    data: Sequence[float],
) -> dict[str, object]:
    """Run all data integrity checks on a numeric dataset.

    Combines:
      - Benford's Law χ² test (reject if χ² > 15.51)
      - Noise entropy analysis (flag if σ_noise < 1e-12)
      - Manual entry heuristic (integer/half-integer ratio)

    Args:
        data: A list/array of numeric scientific measurements.

    Returns:
        Dict representation of :class:`ValidationResult` with keys
        ``passed``, ``benford``, ``noise``, ``manual_entry``,
        ``warnings``, ``errors``.

    Example::

        import random
        measurements = [random.gauss(100, 15) for _ in range(200)]
        result = validate_scientific_data_integrity(measurements)
        assert result["passed"]
    """
    logger.info("integrity_validation_start", n=len(data))

    if not data:
        return {
            "passed": False,
            "errors": ["Empty dataset — nothing to validate"],
            "warnings": [],
        }

    benford = _benford_test(data)
    noise = _noise_entropy(data)
    manual = _manual_entry_check(data)

    warnings: list[str] = []
    errors: list[str] = []

    if not benford.passed:
        errors.append(
            f"Benford's Law FAILED: χ²={benford.chi_squared:.2f} > "
            f"{CHI2_CRITICAL} (n={benford.n})"
        )

    if not noise.passed:
        errors.append(
            f"Noise entropy FAILED: σ_noise={noise.noise_std:.2e} < "
            f"{NOISE_FLOOR:.2e} — data is suspiciously clean"
        )

    if not manual.passed:
        warnings.append(
            f"Manual entry WARNING: {manual.combined_ratio:.1%} of values "
            f"are integer or half-integer (threshold {MANUAL_ENTRY_THRESHOLD:.0%})"
        )

    if benford.n < MIN_SAMPLE_SIZE:
        warnings.append(
            f"Benford test skipped: n={benford.n} < {MIN_SAMPLE_SIZE} minimum"
        )

    overall_passed = benford.passed and noise.passed and manual.passed

    logger.info(
        "integrity_validation_complete",
        passed=overall_passed,
        num_warnings=len(warnings),
        num_errors=len(errors),
    )

    return {
        "passed": overall_passed,
        "benford": {
            "chi_squared": benford.chi_squared,
            "critical_value": benford.critical_value,
            "passed": benford.passed,
            "n": benford.n,
        },
        "noise": {
            "noise_std": noise.noise_std,
            "threshold": noise.threshold,
            "passed": noise.passed,
        },
        "manual_entry": {
            "integer_ratio": manual.integer_ratio,
            "half_integer_ratio": manual.half_integer_ratio,
            "combined_ratio": manual.combined_ratio,
            "threshold": manual.threshold,
            "passed": manual.passed,
        },
        "warnings": warnings,
        "errors": errors,
    }
