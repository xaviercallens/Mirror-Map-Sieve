# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Agent observability: structured telemetry for latency, cost, and metrics.

Every agent interaction emits telemetry that is collected here and can be
exported to Cloud Monitoring, OpenTelemetry, or a local JSON log.

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class TelemetrySpan:
    """A single measured span (tool call, solver invocation, etc.).

    Attributes:
        label: Human-readable name of the span.
        start_epoch: Wall-clock start time (``time.time()``).
        duration_ms: Elapsed milliseconds.
        metadata: Arbitrary key-value pairs.
    """

    label: str
    start_epoch: float = field(default_factory=time.time)
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentTelemetry:
    """Telemetry collector for a single agent.

    Tracks latency distributions, token counts, cost accumulation,
    MCTS node expansions, and solver evaluations.

    Attributes:
        agent_name: Name of the owning agent.
        trace_id: Distributed trace correlation ID.
        spans: Ordered list of recorded spans.
        total_tokens: Cumulative token count (prompt + completion).
        total_cost_usd: Cumulative cost in USD.
        mcts_nodes: Number of MCTS nodes expanded (SymBrain routing).
        solver_evals: Number of ODE right-hand-side evaluations.
        jacobian_evals: Number of Jacobian evaluations (implicit solvers).
    """

    agent_name: str
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    spans: list[TelemetrySpan] = field(default_factory=list)
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    mcts_nodes: int = 0
    solver_evals: int = 0
    jacobian_evals: int = 0
    gpu_energy_joules: float = 0.0

    # ---- Recording -------------------------------------------------------

    def record_latency(self, label: str, duration_ms: float, **meta: Any) -> None:
        """Record a latency span.

        Args:
            label: Span name (e.g. ``"lean4_compile"``).
            duration_ms: Elapsed time in milliseconds.
            **meta: Extra metadata to attach.
        """
        span = TelemetrySpan(
            label=label,
            duration_ms=duration_ms,
            metadata=meta,
        )
        self.spans.append(span)
        logger.debug(
            "telemetry_span",
            agent=self.agent_name,
            label=label,
            duration_ms=round(duration_ms, 2),
        )

    def record_tokens(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Record token usage from an LLM call.

        Args:
            prompt_tokens: Number of tokens in the prompt.
            completion_tokens: Number of tokens in the completion.
        """
        total = prompt_tokens + completion_tokens
        self.total_tokens += total
        logger.debug(
            "token_usage",
            agent=self.agent_name,
            prompt=prompt_tokens,
            completion=completion_tokens,
            total=total,
            cumulative=self.total_tokens,
        )

    def record_cost(self, cost_usd: float) -> None:
        """Record dollar cost.

        Args:
            cost_usd: Spend in USD.
        """
        self.total_cost_usd += cost_usd
        logger.debug(
            "cost_recorded",
            agent=self.agent_name,
            cost_usd=cost_usd,
            cumulative=self.total_cost_usd,
        )

    def record_solver_stats(
        self,
        func_evals: int = 0,
        jacobian_evals: int = 0,
        mcts_nodes: int = 0,
    ) -> None:
        """Record numerical solver and MCTS statistics.

        Args:
            func_evals: ODE right-hand-side evaluations.
            jacobian_evals: Jacobian matrix evaluations.
            mcts_nodes: MCTS tree nodes expanded.
        """
        self.solver_evals += func_evals
        self.jacobian_evals += jacobian_evals
        self.mcts_nodes += mcts_nodes
        logger.debug(
            "solver_stats",
            agent=self.agent_name,
            func_evals=func_evals,
            jacobian_evals=jacobian_evals,
            mcts_nodes=mcts_nodes,
        )

    def record_gpu_energy(self, joules: float) -> None:
        """Record GPU energy consumption in Joules.

        Args:
            joules: Energy in Joules.
        """
        self.gpu_energy_joules += joules
        logger.debug(
            "gpu_energy_recorded",
            agent=self.agent_name,
            joules=joules,
            cumulative=self.gpu_energy_joules,
        )

    # ---- Summarisation ---------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Return a serialisable telemetry summary.

        Returns:
            Dict containing all accumulated metrics and span data.
        """
        latencies = {s.label: s.duration_ms for s in self.spans}
        return {
            "agent_name": self.agent_name,
            "trace_id": self.trace_id,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "solver_evals": self.solver_evals,
            "jacobian_evals": self.jacobian_evals,
            "mcts_nodes": self.mcts_nodes,
            "gpu_energy_joules": round(self.gpu_energy_joules, 2),
            "num_spans": len(self.spans),
            "latencies_ms": latencies,
        }

    def reset(self) -> None:
        """Reset all counters (preserves ``trace_id``)."""
        self.spans.clear()
        self.total_tokens = 0
        self.total_cost_usd = 0.0
        self.mcts_nodes = 0
        self.solver_evals = 0
        self.jacobian_evals = 0
        self.gpu_energy_joules = 0.0
        logger.info("telemetry_reset", agent=self.agent_name)
