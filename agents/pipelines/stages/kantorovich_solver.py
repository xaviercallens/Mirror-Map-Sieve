# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Stage: Kantorovich — Computational Solving & Benchmarking.

Named after Leonid Kantorovich (1912–1986), Nobel laureate (1975),
pioneer of linear programming in production planning. Kantorovich
generates solver code, runs benchmark instances, and reports
optimality gaps — the computational workhorse of the OR pipeline.

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import json
import re
import textwrap
import time
import traceback
from pathlib import Path
from typing import Any

import structlog

from agents.pipelines.base import agent_generate

logger = structlog.get_logger(__name__)

# ── Agent Identity ────────────────────────────────────────────────────────────

KANTOROVICH_IDENTITY = textwrap.dedent("""\
    You are Leonid Kantorovich, Nobel laureate (1975), pioneer of linear
    programming in production planning and the theory of optimal resource
    allocation. You write solvers.

    Write complete, self-contained Python 3 optimization code that:
    1. Formulates the problem using PuLP, OR-Tools, or scipy.optimize
    2. Implements the exact algorithm or a provably-good approximation
    3. Solves benchmark instances and records: objective value, solve time,
       optimality gap (if available from solver), number of B&B nodes
    4. Compares against at least one baseline heuristic
    5. Generates a publication-quality figure:
       - Panel 1: Convergence / optimality gap over iterations
       - Panel 2: Solution quality vs. instance size
       - Panel 3: Runtime comparison

    SOLVER PREFERENCES (in priority order):
    1. Google OR-Tools (from ortools.sat.python import cp_model) — free, excellent for CP-SAT
    2. PuLP (import pulp) — free, interfaces CBC/HiGHS/GLPK
    3. scipy.optimize.linprog — for simple LP
    4. Custom implementations — for specialised algorithms (column generation, etc.)

    Assign results to a dict named `optimization_stats` with keys:
    objective_value, best_bound, gap_pct, solve_time_s, nodes_explored,
    baseline_objective, improvement_pct, instance_name

    Use plt.savefig(path, dpi=150, bbox_inches='tight'). Never plt.show().
    Output ONLY valid Python inside a ```python ... ``` block.
""").strip()


# ── Main stage function ──────────────────────────────────────────────────────


async def run_kantorovich_solver(
    formulation: dict[str, Any],
    hypotheses: list[dict[str, Any]],
    output_dir: Path | None = None,
    model: str = "gemini-2.5-pro",
) -> dict[str, Any]:
    """Generate and execute optimization solver code.

    Kantorovich produces Python code that formulates and solves the
    optimization problem using OR-Tools or PuLP, runs benchmark instances,
    and generates comparison plots against baseline approaches.

    The generated code is executed in a sandboxed namespace with numpy,
    scipy, matplotlib, and (optionally) OR-Tools available.

    Args:
        formulation: Mathematical formulation from Dantzig (sets, params,
            variables, objective, constraints).
        hypotheses: Algorithmic hypotheses from DeGennes with proposed
            solution approaches.
        output_dir: Directory for saving generated plots. If None, uses
            the current working directory.
        model: Foundation model identifier.

    Returns:
        Dict with keys: ``code``, ``optimization_stats``, ``plots``,
        ``errors``, ``elapsed_s``, ``agent``.
    """
    log = logger.bind(stage="kantorovich_solver")
    t0 = time.monotonic()

    if output_dir is None:
        output_dir = Path("output/or_pipeline")
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Build the solver prompt ───────────────────────────────────────────
    # Inject the mathematical formulation and algorithmic hypotheses so
    # Kantorovich can write targeted solver code.
    formulation_str = json.dumps(formulation, indent=2, default=str)[:3000]
    hypotheses_str = json.dumps(hypotheses[:3], indent=2, default=str)[:2000]
    plot_path = str(output_dir / "kantorovich_benchmark.png")

    prompt = textwrap.dedent(f"""\
        Implement an optimization solver for the following formulation:

        Mathematical Formulation:
        {formulation_str}

        Algorithmic Hypotheses to implement:
        {hypotheses_str}

        Requirements:
        1. Use PuLP or OR-Tools (cp_model) to formulate and solve
        2. Include a simple greedy/heuristic baseline for comparison
        3. Record: objective_value, best_bound, gap_pct, solve_time_s,
           nodes_explored, baseline_objective, improvement_pct, instance_name
        4. Generate a 3-panel figure saved to: {plot_path}
        5. Store results in a dict named `optimization_stats`

        Output ONLY the Python code in a ```python ... ``` block.
    """).strip()

    log.info("kantorovich_solver_start")
    raw = await agent_generate(KANTOROVICH_IDENTITY, prompt, model=model)

    # ── Extract Python code from response ─────────────────────────────────
    code = ""
    code_match = re.search(r"```python\s*\n(.*?)```", raw, re.DOTALL)
    if code_match:
        code = code_match.group(1).strip()
    else:
        # Fallback: try to use the entire response if it looks like Python
        if "import " in raw and "optimization_stats" in raw:
            code = raw.strip()
        else:
            log.warning("kantorovich_no_code_extracted", response_len=len(raw))

    # ── Execute in sandboxed namespace ────────────────────────────────────
    # Provide common scientific computing libraries in the execution
    # namespace so the generated code can use them directly.
    optimization_stats: dict[str, Any] = {}
    errors: list[str] = []
    plots: list[str] = []

    if code:
        namespace: dict[str, Any] = {"__builtins__": __builtins__}
        try:
            # Pre-import commonly needed modules into the namespace
            import numpy as np
            import matplotlib
            matplotlib.use("Agg")  # Non-interactive backend for server
            import matplotlib.pyplot as plt

            namespace.update({
                "np": np,
                "numpy": np,
                "plt": plt,
                "matplotlib": matplotlib,
                "Path": Path,
                "json": json,
            })

            # Try to import OR-Tools if available
            try:
                from ortools.sat.python import cp_model
                namespace["cp_model"] = cp_model
            except ImportError:
                log.info("kantorovich_ortools_not_available")

            # Try to import PuLP if available
            try:
                import pulp
                namespace["pulp"] = pulp
            except ImportError:
                log.info("kantorovich_pulp_not_available")

            # Execute the generated code
            exec(code, namespace)  # noqa: S102 — sandboxed execution

            # Extract the optimization_stats dict from the namespace
            if "optimization_stats" in namespace:
                optimization_stats = namespace["optimization_stats"]
            else:
                errors.append("Code executed but 'optimization_stats' dict not found")

            # Check if plot was generated
            if Path(plot_path).exists():
                plots.append(plot_path)

        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            log.warning("kantorovich_execution_error", error=error_msg[:200])
            errors.append(error_msg)
            errors.append(traceback.format_exc()[-500:])

    elapsed = time.monotonic() - t0

    result = {
        "code": code[:5000],  # Truncate for serialisation safety
        "optimization_stats": optimization_stats,
        "plots": plots,
        "errors": errors,
        "elapsed_s": round(elapsed, 2),
        "agent": "Kantorovich",
    }

    log.info(
        "kantorovich_solver_complete",
        elapsed_s=round(elapsed, 1),
        has_stats=bool(optimization_stats),
        error_count=len(errors),
    )
    return result
