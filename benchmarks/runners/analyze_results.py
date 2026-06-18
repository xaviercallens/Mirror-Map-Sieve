#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Benchmark results analyser with Wilson confidence intervals.

Reads JSON benchmark result files and produces a Markdown report
with pass/fail rates, latency statistics, and Wilson score CIs.

Usage::

    python benchmarks/runners/analyze_results.py \
        --input benchmarks/results/ \
        --report benchmarks/results/report.md

Reference: Wilson, E. B. (1927). "Probable inference, the law of
succession, and statistical inference." JASA 22(158).

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Wilson CI
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class WilsonCI:
    """Wilson score confidence interval for a proportion.

    Attributes:
        proportion: Point estimate p̂ = successes / n.
        lower: Lower bound of the CI.
        upper: Upper bound of the CI.
        n: Total trials.
        successes: Number of successes.
        z: Z-score for the confidence level.
    """

    proportion: float
    lower: float
    upper: float
    n: int
    successes: int
    z: float


def wilson_score_interval(
    successes: int,
    n: int,
    confidence: float = 0.95,
) -> WilsonCI:
    """Compute the Wilson score confidence interval for a proportion.

    The Wilson interval is preferred over the Wald (normal) interval
    because it is accurate even for small sample sizes and extreme
    proportions.

    Args:
        successes: Number of successes.
        n: Total number of trials.
        confidence: Confidence level (default 0.95 for 95% CI).

    Returns:
        :class:`WilsonCI` with point estimate and bounds.

    Example::

        ci = wilson_score_interval(successes=8, n=10)
        assert 0.4 < ci.lower < ci.proportion < ci.upper < 1.0
    """
    if n == 0:
        return WilsonCI(0.0, 0.0, 0.0, 0, 0, 0.0)

    # Z-score for the confidence level
    # For 95%: z ≈ 1.96; for 99%: z ≈ 2.576
    z = _z_score(confidence)
    p_hat = successes / n
    z2 = z * z

    denominator = 1 + z2 / n
    center = (p_hat + z2 / (2 * n)) / denominator
    margin = (z / denominator) * math.sqrt(
        p_hat * (1 - p_hat) / n + z2 / (4 * n * n)
    )

    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)

    return WilsonCI(
        proportion=round(p_hat, 4),
        lower=round(lower, 4),
        upper=round(upper, 4),
        n=n,
        successes=successes,
        z=round(z, 4),
    )


def _z_score(confidence: float) -> float:
    """Approximate z-score for a given confidence level.

    Uses the rational approximation for the inverse normal CDF.

    Args:
        confidence: Confidence level in (0, 1).

    Returns:
        Z-score.
    """
    # Common values
    z_table = {
        0.90: 1.645,
        0.95: 1.960,
        0.99: 2.576,
    }
    if confidence in z_table:
        return z_table[confidence]

    # Abramowitz & Stegun approximation for Φ⁻¹
    alpha = 1 - confidence
    p = alpha / 2
    t = math.sqrt(-2 * math.log(p))
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    return t - (c0 + c1 * t + c2 * t * t) / (1 + d1 * t + d2 * t * t + d3 * t ** 3)


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze_results(input_dir: Path) -> dict[str, Any]:
    """Analyse all benchmark result files in a directory.

    Args:
        input_dir: Directory containing JSON result files.

    Returns:
        Analysis dict with per-suite statistics.
    """
    result_files = sorted(input_dir.glob("*_results.json"))
    if not result_files:
        logger.warning("no_results_found", dir=str(input_dir))
        return {"error": "No result files found"}

    suites: dict[str, Any] = {}

    for file in result_files:
        data = json.loads(file.read_text(encoding="utf-8"))
        suite_name = data.get("suite", "unknown")

        cases = data.get("cases", [])
        n = len(cases)
        passed = sum(1 for c in cases if c.get("passed", False))
        latencies = [c.get("elapsed_ms", 0.0) for c in cases if c.get("elapsed_ms", 0)]

        ci = wilson_score_interval(passed, n)

        stats: dict[str, Any] = {
            "file": file.name,
            "timestamp": data.get("timestamp", ""),
            "total": n,
            "passed": passed,
            "failed": n - passed,
            "pass_rate": ci.proportion,
            "wilson_ci_lower": ci.lower,
            "wilson_ci_upper": ci.upper,
        }

        if latencies:
            sorted_lat = sorted(latencies)
            stats["latency_p50_ms"] = round(sorted_lat[len(sorted_lat) // 2], 2)
            stats["latency_p95_ms"] = round(
                sorted_lat[int(len(sorted_lat) * 0.95)], 2,
            )
            stats["latency_mean_ms"] = round(
                sum(latencies) / len(latencies), 2,
            )

        suites[suite_name] = stats

    return suites


def generate_report(analysis: dict[str, Any], output_file: Path) -> None:
    """Generate a Markdown report from analysis results.

    Args:
        analysis: Output of :func:`analyze_results`.
        output_file: Path to write the report.
    """
    lines: list[str] = [
        "# SocrateAI Benchmark Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Summary",
        "",
        "| Suite | Total | Passed | Failed | Rate | Wilson 95% CI |",
        "|-------|-------|--------|--------|------|---------------|",
    ]

    for suite_name, stats in sorted(analysis.items()):
        if isinstance(stats, str):
            continue
        lines.append(
            f"| {suite_name} | {stats['total']} | {stats['passed']} | "
            f"{stats['failed']} | {stats['pass_rate']:.0%} | "
            f"[{stats['wilson_ci_lower']:.2%}, {stats['wilson_ci_upper']:.2%}] |"
        )

    lines.extend(["", "## Latency", ""])
    lines.append("| Suite | p50 (ms) | p95 (ms) | Mean (ms) |")
    lines.append("|-------|----------|----------|-----------|")

    for suite_name, stats in sorted(analysis.items()):
        if isinstance(stats, str):
            continue
        p50 = stats.get("latency_p50_ms", "N/A")
        p95 = stats.get("latency_p95_ms", "N/A")
        mean = stats.get("latency_mean_ms", "N/A")
        lines.append(f"| {suite_name} | {p50} | {p95} | {mean} |")

    lines.extend([
        "",
        "---",
        "",
        "Patent: US-PAT-PEND-2026-0525",
    ])

    output_file.write_text("\n".join(lines), encoding="utf-8")
    logger.info("report_generated", file=str(output_file))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="SocrateAI Benchmark Analyser")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("benchmarks/results"),
        help="Directory containing result JSON files",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("benchmarks/results/report.md"),
        help="Output Markdown report path",
    )
    args = parser.parse_args()

    analysis = analyze_results(args.input)
    if "error" in analysis:
        print(f"Error: {analysis['error']}", file=sys.stderr)
        sys.exit(1)

    generate_report(analysis, args.report)
    print(f"Report written to {args.report}")

    for suite, stats in analysis.items():
        if isinstance(stats, dict):
            print(
                f"  {suite}: {stats['passed']}/{stats['total']} "
                f"({stats['pass_rate']:.0%}) "
                f"CI=[{stats['wilson_ci_lower']:.2%}, "
                f"{stats['wilson_ci_upper']:.2%}]"
            )


if __name__ == "__main__":
    main()
