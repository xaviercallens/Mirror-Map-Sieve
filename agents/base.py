# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Abstract base agent with shared configuration, result types, and lifecycle.

Every agent in the Agora (Galileo, Euler, Socrates, Galois) inherits from
:class:`AbstractAgent` and implements the *think → act → run* loop.
Budget enforcement is baked into the base class so no concrete agent
can accidentally overspend.

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import signal
import sys
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

import structlog

from agents.common.budget_guard import BudgetGuard, BudgetExceededError
from agents.common.telemetry import AgentTelemetry

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AgentRole(Enum):
    """Semantic role of an agent inside the Agora."""

    EXPERIMENTER = auto()
    VERIFIER = auto()
    ORCHESTRATOR = auto()
    MATHEMATICIAN = auto()
    OPTIMIZER = auto()
    COMPUTATIONAL_ORACLE = auto() # Galileo: Z3 / SAT Oracle for MCTS failures
    INGESTOR = auto()           # Bourbaki: code-to-Lean translator
    FILTER = auto()             # Aristotle: semantic guillotine
    EXPLOIT_SYNTHESIZER = auto() # Descartes: exploit synthesis
    REPORTER = auto()           # Champollion: certification reports
    EXPLAINER = auto()          # Feynman/TuringEdu: pedagogy and explanation

    # AlienMath specialist roles (v4.1+)
    THEOREM_PROVER = auto()          # Newton: formal theorem demonstration (Lean 4)
    HORIZON_SCOUT = auto()           # Darwin: cutting-edge discovery, literature survey
    QUORUM_JUDGE = auto()            # Poincaré: multi-agent consensus verification
    EDUCATOR = auto()                # TuringEdu: teaching and explanation (layered)
    KNOWLEDGE_SYNTHESIZER = auto()   # Gauss: exhaustive state-of-the-art survey
    NUMERIC_ORACLE = auto()          # Ramanujan: numerical witnesses + tensor search

    # Discovery Pipeline roles (v4.2+)
    HUMAN_GATEWAY = auto()           # Xavier: human final approval gate
    INTUITION_SCOUT = auto()         # Feynman: physical intuition + plausibility
    ALGO_TRANSLATOR = auto()         # Lovelace: cross-system proof translation
    AXIOMATIC_BUILDER = auto()       # Hilbert: sorry completion + axiom systems
    PROTOTYPER = auto()              # Tesla: formal specification & design prototypes


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class AgentConfig:
    """Immutable configuration for any Agora agent.

    Attributes:
        name: Human-readable agent name (e.g. ``"galileo"``).
        model: Foundation model identifier (e.g. ``"gemini-2.5-pro"``).
        role: Semantic role inside the Agora.
        budget_limit: Maximum spend for a single experiment in USD.
        project_budget: Maximum cumulative project spend in USD.
        timeout_ms: Per-tool call timeout in milliseconds.
        max_iterations: Safety cap on agentic loops.
        min_replicas: Serverless floor — **must** be ``0``.
        temperature: LLM sampling temperature.
        tools: List of tool function names to register.
    """

    name: str
    model: str = "gemini-2.5-pro"
    role: AgentRole = AgentRole.EXPERIMENTER
    budget_limit: float = 100.0
    project_budget: float = 500.0
    timeout_ms: int = 30_000
    max_iterations: int = 25
    min_replicas: int = 0
    temperature: float = 0.2
    tools: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.min_replicas != 0:
            raise ValueError(
                f"Serverless policy violation: min_replicas must be 0, "
                f"got {self.min_replicas}"
            )
        if self.budget_limit > self.project_budget:
            raise ValueError(
                f"Experiment budget ${self.budget_limit} exceeds "
                f"project budget ${self.project_budget}"
            )


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class AgentResult:
    """Structured output from any agent execution.

    Attributes:
        answer: The primary answer or artifact produced.
        confidence: Agent-reported confidence in ``[0, 1]``.
        cost_usd: Actual spend incurred during this run.
        proofs: List of formal proofs or verification certificates.
        telemetry: Raw telemetry dict (latency, tokens, solver stats).
        trace_id: Correlation ID for distributed tracing.
        warnings: Non-fatal issues encountered during execution.
    """

    answer: Any
    confidence: float = 0.0
    cost_usd: float = 0.0
    proofs: list[str] = field(default_factory=list)
    telemetry: dict[str, Any] = field(default_factory=dict)
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be in [0, 1], got {self.confidence}"
            )


# ---------------------------------------------------------------------------
# Abstract Agent
# ---------------------------------------------------------------------------

class AbstractAgent(ABC):
    """Base class for all Agora agents.

    Subclasses must implement:
      - :meth:`think` — deliberation / planning step
      - :meth:`act`   — tool execution step
      - :meth:`run`   — full agentic loop

    The base class provides budget guard integration, structured logging,
    telemetry collection, and a uniform lifecycle.
    """

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.budget_guard = BudgetGuard(
            experiment_limit=config.budget_limit,
            project_limit=config.project_budget,
        )
        self.telemetry = AgentTelemetry(agent_name=config.name)
        self._log = logger.bind(agent=config.name, role=config.role.name)
        self._iteration = 0
        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        """Register signal handlers for Spot Instance preemption (SIGTERM)."""
        try:
            signal.signal(signal.SIGTERM, self._handle_sigterm)
        except ValueError:
            # signal only works in main thread
            pass

    def _handle_sigterm(self, signum: int, frame: Any) -> None:
        """Handle Cloud Run Spot preemption signal."""
        self._log.warning("spot_preemption_sigterm_received", action="checkpointing")
        try:
            self.checkpoint_state()
        except Exception as e:
            self._log.error("checkpoint_failed", error=str(e))
        sys.exit(143) # standard exit code for SIGTERM

    def checkpoint_state(self) -> None:
        """Override to implement preemption checkpointing to Alexandrie/GCS."""
        pass

    # ------ Abstract lifecycle methods ------------------------------------

    @abstractmethod
    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """Deliberation step: analyse the context and plan next actions.

        Args:
            context: Current conversational / experimental state.

        Returns:
            A plan dict describing intended actions and rationale.
        """

    @abstractmethod
    async def act(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Execution step: invoke tools according to the plan.

        Args:
            plan: Output of :meth:`think`.

        Returns:
            Observations from tool executions.
        """

    @abstractmethod
    async def run(self, query: str, **kwargs: Any) -> AgentResult:
        """Full agentic loop: think → act → converge.

        Args:
            query: The user/orchestrator question.
            **kwargs: Extra context forwarded to ``think``.

        Returns:
            Structured :class:`AgentResult`.
        """

    # ------ Shared helpers ------------------------------------------------

    def _check_budget(self, estimated_cost: float) -> None:
        """Raise :class:`BudgetExceededError` if over budget.

        Args:
            estimated_cost: Projected cost in USD for the next action.

        Raises:
            BudgetExceededError: If cumulative spend would exceed limits.
        """
        if not self.budget_guard.check_budget(estimated_cost):
            raise BudgetExceededError(
                f"Agent '{self.config.name}': estimated cost "
                f"${estimated_cost:.2f} would exceed budget "
                f"(used ${self.budget_guard.cumulative_cost:.2f} / "
                f"${self.config.budget_limit:.2f} experiment, "
                f"${self.config.project_budget:.2f} project)"
            )

    def _record_cost(self, actual_cost: float) -> None:
        """Record spend and emit telemetry.

        Args:
            actual_cost: Realised cost in USD.
        """
        self.budget_guard.record_cost(actual_cost)
        self.telemetry.record_cost(actual_cost)
        self._log.info(
            "cost_recorded",
            cost_usd=actual_cost,
            cumulative=self.budget_guard.cumulative_cost,
        )

    def _start_timer(self) -> float:
        """Start a high-resolution timer for latency tracking.

        Returns:
            Monotonic timestamp in seconds.
        """
        return time.monotonic()

    def _stop_timer(self, start: float, label: str) -> float:
        """Stop the timer, record latency, and return elapsed milliseconds.

        Args:
            start: Value returned by :meth:`_start_timer`.
            label: Human-readable name for the timed span.

        Returns:
            Elapsed time in milliseconds.
        """
        elapsed_ms = (time.monotonic() - start) * 1000
        self.telemetry.record_latency(label, elapsed_ms)
        return elapsed_ms

    def _guard_iterations(self) -> None:
        """Increment and check the iteration counter.

        Raises:
            RuntimeError: If ``max_iterations`` is exceeded.
        """
        self._iteration += 1
        if self._iteration > self.config.max_iterations:
            raise RuntimeError(
                f"Agent '{self.config.name}' exceeded max iterations "
                f"({self.config.max_iterations})"
            )

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} name={self.config.name!r} "
            f"role={self.config.role.name}>"
        )
