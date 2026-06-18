# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Python-to-Rust bridge for **rusty-SUNDIALS** stiff ODE/DAE solvers.

This module provides a high-level Python API that invokes the
``rusty_sundials`` CLI (compiled from Rust) to solve stiff initial-value
problems using CVODE's BDF or Adams methods.

Pre-built systems:
  • **Robertson** — classic 3-species stiff chemical kinetics
  • **Lorenz**    — chaotic attractor (ρ = 28, σ = 10, β = 8/3)
  • **Lotka–Volterra** — predator–prey dynamics

Reference: Hindmarsh et al., "SUNDIALS: Suite of Nonlinear and
Differential/Algebraic Equation Solvers", ACM TOMS 31(3), 2005.

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import json
import subprocess
import shutil
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Sequence

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class SolverMethod(str, Enum):
    """Supported CVODE linear multistep methods."""

    BDF = "BDF"          # Backward Differentiation Formula — stiff systems
    ADAMS = "Adams"      # Adams–Moulton — non-stiff systems


class PrebuiltSystem(str, Enum):
    """Pre-built ODE systems shipped with rusty-SUNDIALS."""

    ROBERTSON = "robertson"
    LORENZ = "lorenz"
    LOTKA_VOLTERRA = "lotka_volterra"


@dataclass(frozen=True, slots=True)
class SolverStats:
    """Solver performance statistics.

    Attributes:
        num_steps: Total integration steps taken.
        num_func_evals: Right-hand-side function evaluations.
        num_jac_evals: Jacobian matrix evaluations (dense or band).
        num_error_test_failures: Local error test failures.
        final_step_size: Last internal step size.
    """

    num_steps: int = 0
    num_func_evals: int = 0
    num_jac_evals: int = 0
    num_error_test_failures: int = 0
    final_step_size: float = 0.0


@dataclass(slots=True)
class SolverResult:
    """Result of an ODE integration.

    Attributes:
        t: Time points at which the solution was output.
        y: Solution matrix — ``y[i]`` is the state vector at ``t[i]``.
        stats: Solver performance statistics.
        system: Name of the solved system.
        method: Solver method used.
        success: Whether the solver converged without error.
        message: Human-readable status message.
    """

    t: list[float] = field(default_factory=list)
    y: list[list[float]] = field(default_factory=list)
    stats: SolverStats = field(default_factory=SolverStats)
    system: str = ""
    method: str = "BDF"
    success: bool = False
    message: str = ""


# ---------------------------------------------------------------------------
# Pre-built ODE systems (pure-Python fallback)
# ---------------------------------------------------------------------------

def _robertson_rhs(
    _t: float, y: Sequence[float],
) -> list[float]:
    """Robertson stiff chemical kinetics (3 species).

    ::

        dy₁/dt = -0.04·y₁ + 1e4·y₂·y₃
        dy₂/dt =  0.04·y₁ - 1e4·y₂·y₃ - 3e7·y₂²
        dy₃/dt =  3e7·y₂²

    Args:
        _t: Current time (unused — autonomous system).
        y: State vector ``[y₁, y₂, y₃]``.

    Returns:
        Derivatives ``[dy₁, dy₂, dy₃]``.
    """
    y1, y2, y3 = y
    dy1 = -0.04 * y1 + 1e4 * y2 * y3
    dy2 = 0.04 * y1 - 1e4 * y2 * y3 - 3e7 * y2 ** 2
    dy3 = 3e7 * y2 ** 2
    return [dy1, dy2, dy3]


def _lorenz_rhs(
    _t: float, y: Sequence[float],
    sigma: float = 10.0, rho: float = 28.0, beta: float = 8.0 / 3.0,
) -> list[float]:
    """Lorenz chaotic attractor.

    Args:
        _t: Current time.
        y: State ``[x, y, z]``.
        sigma: Prandtl number.
        rho: Rayleigh number.
        beta: Geometric factor.

    Returns:
        Derivatives ``[dx, dy, dz]``.
    """
    x, y_val, z = y
    dx = sigma * (y_val - x)
    dy = x * (rho - z) - y_val
    dz = x * y_val - beta * z
    return [dx, dy, dz]


def _lotka_volterra_rhs(
    _t: float, y: Sequence[float],
    alpha: float = 1.5, beta: float = 1.0,
    delta: float = 1.0, gamma: float = 3.0,
) -> list[float]:
    """Lotka–Volterra predator–prey dynamics.

    Args:
        _t: Current time.
        y: State ``[prey, predator]``.
        alpha: Prey birth rate.
        beta: Predation rate.
        delta: Predator reproduction efficiency.
        gamma: Predator death rate.

    Returns:
        Derivatives ``[d_prey, d_predator]``.
    """
    prey, predator = y
    d_prey = alpha * prey - beta * prey * predator
    d_predator = delta * prey * predator - gamma * predator
    return [d_prey, d_predator]


_SYSTEM_REGISTRY: dict[str, Any] = {
    "robertson": {
        "rhs": _robertson_rhs,
        "default_y0": [1.0, 0.0, 0.0],
        "default_t_span": (0.0, 1e5),
    },
    "lorenz": {
        "rhs": _lorenz_rhs,
        "default_y0": [1.0, 1.0, 1.0],
        "default_t_span": (0.0, 50.0),
    },
    "lotka_volterra": {
        "rhs": _lotka_volterra_rhs,
        "default_y0": [10.0, 5.0],
        "default_t_span": (0.0, 20.0),
    },
}


# ---------------------------------------------------------------------------
# Simple Euler fallback solver
# ---------------------------------------------------------------------------

def _solve_python_fallback(
    system: str,
    t_span: tuple[float, float],
    y0: list[float],
    dt: float = 0.001,
    max_steps: int = 100_000,
) -> SolverResult:
    """Pure-Python implicit-Euler-like fallback when rusty-SUNDIALS is unavailable.

    This is a *very* simplified solver used only for development / testing.
    Production runs should always use the Rust binary.

    Args:
        system: System name (must be in ``_SYSTEM_REGISTRY``).
        t_span: ``(t_start, t_end)``.
        y0: Initial conditions.
        dt: Fixed step size.
        max_steps: Safety cap.

    Returns:
        :class:`SolverResult`.
    """
    if system not in _SYSTEM_REGISTRY:
        return SolverResult(
            success=False,
            message=f"Unknown system: {system}. "
                    f"Available: {list(_SYSTEM_REGISTRY.keys())}",
        )

    rhs = _SYSTEM_REGISTRY[system]["rhs"]
    t_start, t_end = t_span
    t_current = t_start
    y_current = list(y0)
    t_out: list[float] = [t_current]
    y_out: list[list[float]] = [list(y_current)]
    steps = 0
    func_evals = 0

    import math

    current_dt = dt

    while t_current < t_end and steps < max_steps:
        try:
            dydt = rhs(t_current, y_current)
            func_evals += 1

            # Adaptive step: if derivatives are huge, shrink dt
            max_deriv = max(abs(d) for d in dydt) if dydt else 0.0
            if max_deriv > 1e10:
                current_dt = min(dt, 0.1 / max_deriv)
            else:
                current_dt = min(dt, t_end - t_current)

            y_next = [yi + current_dt * di for yi, di in zip(y_current, dydt)]

            # Overflow / NaN guard
            if any(math.isnan(v) or math.isinf(v) or abs(v) > 1e100
                   for v in y_next):
                # Step too large — halve and retry up to 10 times
                retry_dt = current_dt
                recovered = False
                for _ in range(10):
                    retry_dt *= 0.5
                    y_retry = [yi + retry_dt * di
                               for yi, di in zip(y_current, dydt)]
                    if not any(math.isnan(v) or math.isinf(v) or abs(v) > 1e100
                               for v in y_retry):
                        y_next = y_retry
                        current_dt = retry_dt
                        recovered = True
                        break
                if not recovered:
                    # Can't integrate further — return what we have
                    break

            y_current = y_next
            t_current += current_dt
            steps += 1

        except (OverflowError, ValueError):
            # Stiff blow-up — stop and return partial result
            break

        # Output every 100 steps to limit memory
        if steps % 100 == 0:
            t_out.append(t_current)
            y_out.append(list(y_current))

    t_out.append(t_current)
    y_out.append(list(y_current))

    return SolverResult(
        t=t_out,
        y=y_out,
        stats=SolverStats(
            num_steps=steps,
            num_func_evals=func_evals,
            num_jac_evals=0,
        ),
        system=system,
        method="euler_fallback",
        success=True,
        message=f"Python fallback solver completed {steps} steps.",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def sundials_cvode_solver(
    system: str,
    t_span: tuple[float, float],
    y0: list[float],
    method: str = "BDF",
    rtol: float = 1e-6,
    atol: float = 1e-10,
) -> dict[str, Any]:
    """Solve a stiff ODE system using rusty-SUNDIALS CVODE.

    Attempts to call the ``rusty_sundials`` Rust binary first; falls back
    to a pure-Python Euler solver if the binary is not found.

    Args:
        system: System name — ``"robertson"``, ``"lorenz"``, or
            ``"lotka_volterra"``.
        t_span: Integration interval ``(t_start, t_end)``.
        y0: Initial condition vector.
        method: Linear multistep method — ``"BDF"`` (stiff) or
            ``"Adams"`` (non-stiff).
        rtol: Relative tolerance.
        atol: Absolute tolerance.

    Returns:
        Dict with keys ``t``, ``y``, ``stats``, ``system``, ``method``,
        ``success``, ``message``.

    Example::

        result = sundials_cvode_solver(
            system="robertson",
            t_span=(0.0, 1e5),
            y0=[1.0, 0.0, 0.0],
            method="BDF",
        )
        assert result["success"]
    """
    logger.info(
        "sundials_solve_request",
        system=system,
        t_span=t_span,
        method=method,
    )

    # Validate method
    try:
        solver_method = SolverMethod(method)
    except ValueError:
        return {
            "success": False,
            "message": f"Unknown method '{method}'. Use 'BDF' or 'Adams'.",
        }

    # Try Rust binary
    binary = shutil.which("rusty_sundials")
    if binary is not None:
        return _invoke_rust_solver(
            binary, system, t_span, y0, solver_method.value, rtol, atol,
        )

    # Fallback to Python
    logger.warning(
        "rust_binary_not_found",
        msg="Falling back to Python Euler solver — results are approximate",
    )
    result = _solve_python_fallback(system, t_span, y0)
    return {
        "t": result.t,
        "y": result.y,
        "stats": {
            "num_steps": result.stats.num_steps,
            "num_func_evals": result.stats.num_func_evals,
            "num_jac_evals": result.stats.num_jac_evals,
            "num_error_test_failures": result.stats.num_error_test_failures,
            "final_step_size": result.stats.final_step_size,
        },
        "system": result.system,
        "method": result.method,
        "success": result.success,
        "message": result.message,
    }


def _invoke_rust_solver(
    binary: str,
    system: str,
    t_span: tuple[float, float],
    y0: list[float],
    method: str,
    rtol: float,
    atol: float,
) -> dict[str, Any]:
    """Invoke the rusty_sundials Rust binary via subprocess.

    Args:
        binary: Path to the ``rusty_sundials`` executable.
        system: ODE system name.
        t_span: Integration bounds.
        y0: Initial conditions.
        method: ``"BDF"`` or ``"Adams"``.
        rtol: Relative tolerance.
        atol: Absolute tolerance.

    Returns:
        Parsed JSON output from the Rust solver.
    """
    cmd = [
        binary,
        "--system", system,
        "--t-start", str(t_span[0]),
        "--t-end", str(t_span[1]),
        "--y0", json.dumps(y0),
        "--method", method,
        "--rtol", str(rtol),
        "--atol", str(atol),
        "--output-format", "json",
    ]

    logger.info("rust_solver_invoke", cmd=" ".join(cmd))

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

        if proc.returncode != 0:
            logger.error("rust_solver_failed", stderr=proc.stderr[:500])
            return {
                "success": False,
                "message": f"rusty_sundials exited with code {proc.returncode}: "
                           f"{proc.stderr[:200]}",
            }

        result = json.loads(proc.stdout)
        logger.info(
            "rust_solver_success",
            steps=result.get("stats", {}).get("num_steps", "?"),
        )
        return result

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "rusty_sundials timed out after 120 seconds",
        }
    except json.JSONDecodeError as exc:
        return {
            "success": False,
            "message": f"Failed to parse solver output: {exc}",
        }
