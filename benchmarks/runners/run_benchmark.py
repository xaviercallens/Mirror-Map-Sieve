#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Benchmark runner for SocrateAI Scientific Agora.

Runs configurable benchmark suites and produces JSON result files.

Usage::

    python benchmarks/runners/run_benchmark.py --suite ode_solver
    python benchmarks/runners/run_benchmark.py --suite all --output results/

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Coroutine

import structlog

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents.galileo.tools.sundials_solver import sundials_cvode_solver
from agents.galileo.tools.data_integrity import validate_scientific_data_integrity
from agents.galileo.tools.cost_estimator import estimate_cost
from agents.galileo.agent import GalileoAgent
from agents.euler.agent import EulerAgent
from agents.socrates.agent import SocratesAgent

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Benchmark result types
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkCase:
    """A single benchmark test case."""

    name: str
    suite: str
    passed: bool = False
    elapsed_ms: float = 0.0
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass
class BenchmarkSuiteResult:
    """Aggregated results for a benchmark suite."""

    suite: str
    timestamp: str = ""
    total_cases: int = 0
    passed: int = 0
    failed: int = 0
    total_elapsed_ms: float = 0.0
    cases: list[BenchmarkCase] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Benchmark suites
# ---------------------------------------------------------------------------

def _bench_ode_solver() -> list[BenchmarkCase]:
    """Benchmark the ODE solver on pre-built systems."""
    cases: list[BenchmarkCase] = []

    systems = [
        ("robertson", (0.0, 1e5), [1.0, 0.0, 0.0], "BDF"),
        ("lorenz", (0.0, 50.0), [1.0, 1.0, 1.0], "Adams"),
        ("lotka_volterra", (0.0, 20.0), [10.0, 5.0], "BDF"),
    ]

    for system, t_span, y0, method in systems:
        start = time.monotonic()
        try:
            result = sundials_cvode_solver(
                system=system, t_span=t_span, y0=y0, method=method,
            )
            elapsed = (time.monotonic() - start) * 1000
            cases.append(BenchmarkCase(
                name=f"ode_{system}_{method}",
                suite="ode_solver",
                passed=result.get("success", False),
                elapsed_ms=round(elapsed, 2),
                result=result,
            ))
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            cases.append(BenchmarkCase(
                name=f"ode_{system}_{method}",
                suite="ode_solver",
                passed=False,
                elapsed_ms=round(elapsed, 2),
                error=str(exc),
            ))

    return cases


def _bench_data_integrity() -> list[BenchmarkCase]:
    """Benchmark data integrity checks."""
    import random
    cases: list[BenchmarkCase] = []

    # Good data — should pass
    random.seed(42)
    good_data = [random.gauss(100, 15) for _ in range(200)]
    start = time.monotonic()
    result = validate_scientific_data_integrity(good_data)
    elapsed = (time.monotonic() - start) * 1000
    cases.append(BenchmarkCase(
        name="integrity_good_data",
        suite="data_integrity",
        passed=result["passed"],
        elapsed_ms=round(elapsed, 2),
        result=result,
    ))

    # Fabricated data — uniform leading digits, should fail Benford
    fabricated = [float(i) for i in range(1, 201)]
    start = time.monotonic()
    result = validate_scientific_data_integrity(fabricated)
    elapsed = (time.monotonic() - start) * 1000
    cases.append(BenchmarkCase(
        name="integrity_fabricated_data",
        suite="data_integrity",
        passed=not result["passed"],  # We expect failure
        elapsed_ms=round(elapsed, 2),
        result=result,
    ))

    # Too-clean data — should fail noise check
    clean_data = [100.0 + 1e-15 * i for i in range(200)]
    start = time.monotonic()
    result = validate_scientific_data_integrity(clean_data)
    elapsed = (time.monotonic() - start) * 1000
    cases.append(BenchmarkCase(
        name="integrity_too_clean",
        suite="data_integrity",
        passed=not result["passed"],
        elapsed_ms=round(elapsed, 2),
        result=result,
    ))

    return cases


def _bench_cost_estimator() -> list[BenchmarkCase]:
    """Benchmark cost estimator accuracy and budget enforcement."""
    cases: list[BenchmarkCase] = []

    test_configs = [
        ("L4_1hr", "L4", 1.0, 1, True),
        ("A100_30hr", "A100-80GB", 30.0, 1, False),  # Over budget
        ("TPU_2hr", "TPU-v5e", 2.0, 1, True),
    ]

    for name, gpu, hours, replicas, expected_ok in test_configs:
        start = time.monotonic()
        try:
            result = estimate_cost(gpu_type=gpu, hours=hours, replicas=replicas)
            elapsed = (time.monotonic() - start) * 1000
            budget_ok = result["within_experiment_budget"]
            cases.append(BenchmarkCase(
                name=f"cost_{name}",
                suite="cost_estimator",
                passed=budget_ok == expected_ok,
                elapsed_ms=round(elapsed, 2),
                result=result,
            ))
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            cases.append(BenchmarkCase(
                name=f"cost_{name}",
                suite="cost_estimator",
                passed=False,
                elapsed_ms=round(elapsed, 2),
                error=str(exc),
            ))

    return cases


async def _bench_agents() -> list[BenchmarkCase]:
    """Benchmark agent execution."""
    cases: list[BenchmarkCase] = []

    # Galileo
    start = time.monotonic()
    try:
        galileo = GalileoAgent()
        result = await galileo.run("Solve the Robertson stiff ODE system")
        elapsed = (time.monotonic() - start) * 1000
        cases.append(BenchmarkCase(
            name="galileo_robertson",
            suite="agents",
            passed=result.confidence > 0,
            elapsed_ms=round(elapsed, 2),
            result={"confidence": result.confidence, "cost": result.cost_usd},
        ))
    except Exception as exc:
        elapsed = (time.monotonic() - start) * 1000
        cases.append(BenchmarkCase(
            name="galileo_robertson",
            suite="agents",
            passed=False,
            elapsed_ms=round(elapsed, 2),
            error=str(exc),
        ))

    # Euler
    start = time.monotonic()
    try:
        euler = EulerAgent()
        result = await euler.run("Verify: for all n, n + 0 = n")
        elapsed = (time.monotonic() - start) * 1000
        cases.append(BenchmarkCase(
            name="euler_verify",
            suite="agents",
            passed=result.confidence > 0,
            elapsed_ms=round(elapsed, 2),
            result={"confidence": result.confidence, "cost": result.cost_usd},
        ))
    except Exception as exc:
        elapsed = (time.monotonic() - start) * 1000
        cases.append(BenchmarkCase(
            name="euler_verify",
            suite="agents",
            passed=False,
            elapsed_ms=round(elapsed, 2),
            error=str(exc),
        ))

    return cases


SUITE_REGISTRY: dict[str, Callable[..., Any]] = {
    "ode_solver": _bench_ode_solver,
    "data_integrity": _bench_data_integrity,
    "cost_estimator": _bench_cost_estimator,
    "agents": _bench_agents,
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def run_suite(suite_name: str) -> BenchmarkSuiteResult:
    """Run a single benchmark suite.

    Args:
        suite_name: Name of the suite to run.

    Returns:
        :class:`BenchmarkSuiteResult`.
    """
    logger.info("benchmark_suite_start", suite=suite_name)
    start = time.monotonic()

    runner = SUITE_REGISTRY.get(suite_name)
    if runner is None:
        raise ValueError(f"Unknown suite: {suite_name}. Available: {list(SUITE_REGISTRY.keys())}")

    if asyncio.iscoroutinefunction(runner):
        cases = await runner()
    else:
        cases = runner()

    elapsed = (time.monotonic() - start) * 1000
    passed = sum(1 for c in cases if c.passed)
    failed = len(cases) - passed

    result = BenchmarkSuiteResult(
        suite=suite_name,
        timestamp=datetime.now(timezone.utc).isoformat(),
        total_cases=len(cases),
        passed=passed,
        failed=failed,
        total_elapsed_ms=round(elapsed, 2),
        cases=cases,
    )

    logger.info(
        "benchmark_suite_done",
        suite=suite_name,
        passed=passed,
        failed=failed,
        elapsed_ms=round(elapsed, 2),
    )
    return result


async def run_all_suites(output_dir: Path) -> None:
    """Run all benchmark suites and save results.

    Args:
        output_dir: Directory to write JSON result files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M")

    for suite_name in SUITE_REGISTRY:
        result = await run_suite(suite_name)
        output_file = output_dir / f"{timestamp}_{suite_name}_results.json"
        output_file.write_text(
            json.dumps(asdict(result), indent=2, default=str),
            encoding="utf-8",
        )
        logger.info("results_saved", file=str(output_file))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="SocrateAI Benchmark Runner")
    parser.add_argument(
        "--suite",
        choices=list(SUITE_REGISTRY.keys()) + ["all"],
        default="all",
        help="Benchmark suite to run",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/results"),
        help="Output directory for results",
    )
    args = parser.parse_args()

    if args.suite == "all":
        asyncio.run(run_all_suites(args.output))
    else:
        result = asyncio.run(run_suite(args.suite))
        args.output.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M")
        output_file = args.output / f"{timestamp}_{args.suite}_results.json"
        output_file.write_text(
            json.dumps(asdict(result), indent=2, default=str),
            encoding="utf-8",
        )
        print(f"Results: {output_file}")
        print(f"Passed: {result.passed}/{result.total_cases}")


if __name__ == "__main__":
    main()
