<!-- Copyright (c) 2026 Xavier Callens / Socrate AI Lab, Paris, France -->
<!-- SPDX-License-Identifier: Apache-2.0 AND CC-BY-NC-ND-4.0 -->
<!-- Patent: US-PAT-PEND-2026-0525 -->

# API Reference — Agents

> Agent base class and the three Agora agents: Galileo, Euler, Socrates.

| Field | Value |
|---|---|
| **Module** | `agora.agents` |
| **SDK** | Google Antigravity (AGY) SDK |
| **Version** | 1.0.0 |

---

## Table of Contents

1. [Base Agent Class](#1-base-agent-class)
2. [AgentRole Enum](#2-agentrole-enum)
3. [AgoraMessage Dataclass](#3-agoramessage-dataclass)
4. [Galileo Agent](#4-galileo-agent)
5. [Euler Agent](#5-euler-agent)
6. [Socrates Agent](#6-socrates-agent)
7. [BudgetGuard](#7-budgetguard)
8. [Configuration](#8-configuration)

---

## 1. Base Agent Class

```python
# agora/agents/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
import uuid


class BaseAgent(ABC):
    """Abstract base class for all Agora agents.

    All agents in the Scientific Agora inherit from this class,
    which provides:
    - Identity and role management
    - Budget tracking via BudgetGuard
    - Message send/receive with typed envelopes
    - Lifecycle hooks (init, step, shutdown)

    Agents are instantiated by the AGY SDK runtime and communicate
    via the Elenchus-Maieutic dialectical protocol.

    Args:
        agent_id: Unique identifier for this agent instance.
        role: The agent's role in the Agora (SOCRATES, GALILEO, EULER).
        budget: BudgetGuard instance for cost enforcement.
        config: Agent-specific configuration dictionary.

    Example:
        >>> class MyAgent(BaseAgent):
        ...     async def step(self, message: AgoraMessage) -> AgoraMessage:
        ...         return self.reply(message, payload={"answer": 42})
    """

    def __init__(
        self,
        agent_id: str,
        role: "AgentRole",
        budget: "BudgetGuard",
        config: dict[str, Any] | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.role = role
        self.budget = budget
        self.config = config or {}
        self._message_log: list[AgoraMessage] = []

    @abstractmethod
    async def init(self) -> None:
        """Initialise agent resources (models, connections, etc.).

        Called once when the agent is first instantiated by the AGY runtime.
        Use this to load models, establish connections, and warm caches.

        Raises:
            AgentInitError: If initialisation fails.
        """
        ...

    @abstractmethod
    async def step(self, message: "AgoraMessage") -> "AgoraMessage":
        """Process an incoming message and produce a response.

        This is the core agent loop. Each call to step() represents one
        turn in the dialectical exchange. The agent should:
        1. Parse the incoming message
        2. Perform computation (inference, proof search, etc.)
        3. Return a typed response message

        Args:
            message: The incoming AgoraMessage from another agent.

        Returns:
            An AgoraMessage response to be routed by Socrates.

        Raises:
            BudgetExhaustedError: If the operation would exceed budget.
            AgentTimeoutError: If processing exceeds the configured timeout.
        """
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Clean up agent resources.

        Called when the Agora session ends or the agent is being
        replaced. Release models, close connections, flush logs.
        """
        ...

    def send(
        self,
        receiver: "AgentRole",
        msg_type: "MessageType",
        payload: dict[str, Any],
        parent_id: str | None = None,
        cycle_id: str | None = None,
    ) -> "AgoraMessage":
        """Construct and log an outgoing message.

        Args:
            receiver: Target agent role.
            msg_type: Type of dialectical message.
            payload: Message-specific payload dictionary.
            parent_id: Optional parent message ID for threading.
            cycle_id: Optional cycle ID for grouping messages.

        Returns:
            The constructed AgoraMessage (also logged internally).
        """
        msg = AgoraMessage(
            msg_id=str(uuid.uuid7()),
            sender=self.role,
            receiver=receiver,
            msg_type=msg_type,
            payload=payload,
            budget_remaining_usd=self.budget.remaining,
            timestamp=datetime.utcnow(),
            parent_id=parent_id,
            cycle_id=cycle_id or str(uuid.uuid4()),
        )
        self._message_log.append(msg)
        return msg

    def reply(
        self,
        original: "AgoraMessage",
        msg_type: "MessageType | None" = None,
        payload: dict[str, Any] | None = None,
    ) -> "AgoraMessage":
        """Construct a reply to an incoming message.

        Automatically sets parent_id and cycle_id from the original.

        Args:
            original: The message being replied to.
            msg_type: Override message type (default: same as original).
            payload: Response payload.

        Returns:
            The constructed reply AgoraMessage.
        """
        return self.send(
            receiver=original.sender,
            msg_type=msg_type or original.msg_type,
            payload=payload or {},
            parent_id=original.msg_id,
            cycle_id=original.cycle_id,
        )
```

---

## 2. AgentRole Enum

```python
class AgentRole(Enum):
    """Roles available in the Scientific Agora.

    Each role corresponds to a distinct intellectual tradition:
    - SOCRATES: Dialectical orchestration (Elenchus/Maieutics)
    - GALILEO: Empirical experimentation and simulation
    - EULER: Formal mathematical verification

    Attributes:
        SOCRATES: The dialectical orchestrator agent.
        GALILEO: The scientific experimenter agent.
        EULER: The mathematical verifier agent.
    """
    SOCRATES = "socrates"
    GALILEO = "galileo"
    EULER = "euler"
```

---

## 3. AgoraMessage Dataclass

```python
class MessageType(Enum):
    """Types of dialectical messages in the Elenchus-Maieutic protocol.

    Attributes:
        ELENCHUS: Cross-examination query from Socrates.
        MAIEUTIC: Knowledge-extraction response.
        SYNTHESIS: Dialectical synthesis of multiple responses.
        APORIA: Declaration of irresolvable contradiction.
        BUDGET_ALERT: Budget warning or austerity notification.
    """
    ELENCHUS = "elenchus"
    MAIEUTIC = "maieutic"
    SYNTHESIS = "synthesis"
    APORIA = "aporia"
    BUDGET_ALERT = "budget_alert"


@dataclass
class AgoraMessage:
    """Typed envelope for inter-agent communication.

    Every message in the Agora is wrapped in this envelope, ensuring
    type safety, budget tracking, and auditability.

    Attributes:
        msg_id: UUID v7 (time-ordered) unique identifier.
        sender: The role of the sending agent.
        receiver: The role of the target agent.
        msg_type: The dialectical message type.
        payload: Type-specific payload dictionary.
        budget_remaining_usd: Sender's remaining experiment budget.
        timestamp: ISO 8601 timestamp of message creation.
        parent_id: Optional parent message ID for threading.
        cycle_id: Groups messages within a dialectical cycle.

    Example:
        >>> msg = AgoraMessage(
        ...     msg_id="01902a3b-...",
        ...     sender=AgentRole.SOCRATES,
        ...     receiver=AgentRole.GALILEO,
        ...     msg_type=MessageType.ELENCHUS,
        ...     payload={"query": "Solve dy/dt = -2y"},
        ...     budget_remaining_usd=Decimal("98.50"),
        ...     timestamp=datetime.utcnow(),
        ...     cycle_id="cycle-001",
        ... )
    """
    msg_id: str
    sender: AgentRole
    receiver: AgentRole
    msg_type: MessageType
    payload: dict[str, Any]
    budget_remaining_usd: Decimal
    timestamp: datetime
    parent_id: str | None = None
    cycle_id: str = field(default_factory=lambda: str(uuid.uuid4()))
```

---

## 4. Galileo Agent

```python
# agora/agents/galileo/agent.py

class GalileoAgent(BaseAgent):
    """Scientific Experimenter Agent.

    Galileo generates hypotheses, runs numerical simulations via
    rusty-SUNDIALS, and calls NVIDIA NIM APIs for domain-specific
    computations (BioNeMo, Earth-2, Modulus).

    Galileo operates in two modes:
    1. **Hypothesis mode**: Generates N candidate hypotheses using
       MCTS-guided search (System 2) or direct generation (System 1).
    2. **Simulation mode**: Validates hypotheses through numerical
       integration (ODE/DAE solvers) or NIM API calls.

    Args:
        agent_id: Unique agent identifier.
        budget: BudgetGuard for cost enforcement.
        solver_config: Configuration for rusty-SUNDIALS solvers.
        nim_config: Configuration for NVIDIA NIM API clients.

    Attributes:
        solver: rusty-SUNDIALS solver instance.
        nim_client: NVIDIA NIM API client.
        max_hypotheses: Maximum hypotheses per cycle (default: 8).

    Example:
        >>> galileo = GalileoAgent(
        ...     agent_id="galileo-001",
        ...     budget=BudgetGuard(Decimal("100.00")),
        ...     solver_config={"method": "bdf", "rtol": 1e-8},
        ...     nim_config={"endpoint": "https://nim.example.com"},
        ... )
        >>> await galileo.init()
    """

    def __init__(
        self,
        agent_id: str,
        budget: BudgetGuard,
        solver_config: dict[str, Any] | None = None,
        nim_config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(agent_id, AgentRole.GALILEO, budget)
        self.solver_config = solver_config or {}
        self.nim_config = nim_config or {}
        self.max_hypotheses: int = 8

    async def init(self) -> None:
        """Initialise solver bindings and NIM client."""
        ...

    async def step(self, message: AgoraMessage) -> AgoraMessage:
        """Process an Elenchus query and return hypotheses.

        Flow:
        1. Parse the query from Socrates
        2. Generate candidate hypotheses via MCTS or direct generation
        3. Validate top candidates through simulation
        4. Return ranked hypothesis set with confidence scores

        Args:
            message: Incoming ElencticalQuery from Socrates.

        Returns:
            AgoraMessage with payload:
            {
                "hypotheses": [
                    {"statement": str, "confidence": float, "evidence": dict},
                    ...
                ],
                "simulations_run": int,
                "cost_incurred_usd": str,
            }
        """
        ...

    async def shutdown(self) -> None:
        """Release solver resources and close NIM connections."""
        ...

    # --- Galileo-specific methods ---

    async def generate_hypotheses(
        self,
        query: str,
        n: int = 8,
        use_mcts: bool = True,
    ) -> list[dict[str, Any]]:
        """Generate candidate hypotheses for a scientific query.

        Args:
            query: The scientific question or problem statement.
            n: Number of hypotheses to generate (default: 8).
            use_mcts: Whether to use MCTS search (default: True).

        Returns:
            List of hypothesis dictionaries with keys:
            - statement (str): The hypothesis text.
            - confidence (float): Estimated confidence [0, 1].
            - reasoning (str): Chain-of-thought reasoning.

        Raises:
            BudgetExhaustedError: If generation would exceed budget.
        """
        ...

    async def run_simulation(
        self,
        ode_system: callable,
        t_span: tuple[float, float],
        y0: list[float],
        method: str = "bdf",
        rtol: float = 1e-8,
        atol: float = 1e-10,
    ) -> dict[str, Any]:
        """Run a numerical simulation via rusty-SUNDIALS.

        Args:
            ode_system: Right-hand side function f(t, y) -> dy/dt.
            t_span: Integration interval (t_start, t_end).
            y0: Initial conditions vector.
            method: Solver method ("bdf", "adams", "erk", "dirk").
            rtol: Relative tolerance.
            atol: Absolute tolerance.

        Returns:
            Dictionary with keys:
            - t (list[float]): Time points.
            - y (list[list[float]]): Solution vectors.
            - stats (dict): Solver statistics (steps, evals, etc.).

        Raises:
            SolverError: If the solver fails to converge.
            BudgetExhaustedError: If compute would exceed budget.
        """
        ...

    async def call_nim(
        self,
        service: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Make a call to an NVIDIA NIM microservice.

        Pre-estimates cost and checks budget before executing.

        Args:
            service: NIM service name ("bionemo", "earth2", "modulus").
            payload: Service-specific request payload.

        Returns:
            Service response dictionary.

        Raises:
            BudgetExhaustedError: If call would exceed budget.
            NIMServiceError: If the NIM API returns an error.
            NIMTimeoutError: If the call exceeds 30s timeout.
        """
        ...
```

---

## 5. Euler Agent

```python
# agora/agents/euler/agent.py

class EulerAgent(BaseAgent):
    """Mathematical Verifier Agent.

    Euler verifies hypotheses through formal proof in Lean 4 and
    probabilistic reasoning in DeepProbLog. It also performs
    statistical analysis (Wilson CIs, McNemar's tests).

    Euler operates in three modes:
    1. **Proof mode**: Attempts to prove/refute claims in Lean 4.
    2. **Probabilistic mode**: Uses DeepProbLog for uncertain reasoning.
    3. **Statistical mode**: Computes confidence intervals and tests.

    Args:
        agent_id: Unique agent identifier.
        budget: BudgetGuard for cost enforcement.
        lean4_config: Configuration for Lean 4 prover.
        deepproblog_config: Configuration for DeepProbLog engine.

    Attributes:
        lean4: Lean 4 proof assistant interface.
        deepproblog: DeepProbLog inference engine.
        min_proof_confidence: Minimum confidence threshold (default: 0.95).
    """

    def __init__(
        self,
        agent_id: str,
        budget: BudgetGuard,
        lean4_config: dict[str, Any] | None = None,
        deepproblog_config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(agent_id, AgentRole.EULER, budget)
        self.lean4_config = lean4_config or {}
        self.deepproblog_config = deepproblog_config or {}
        self.min_proof_confidence: float = 0.95

    async def init(self) -> None:
        """Initialise Lean 4 environment and DeepProbLog engine."""
        ...

    async def step(self, message: AgoraMessage) -> AgoraMessage:
        """Process a verification request and return proof results.

        Flow:
        1. Parse hypotheses from Socrates' VerificationRequest
        2. Attempt formal proof in Lean 4
        3. If proof fails, try DeepProbLog probabilistic verification
        4. Compute statistical measures (CIs, p-values)
        5. Return verification results with proofs and/or refutations

        Args:
            message: Incoming VerificationRequest from Socrates.

        Returns:
            AgoraMessage with payload:
            {
                "proofs": [{"theorem": str, "proof": str, "status": str}],
                "refutations": [{"claim": str, "counterexample": dict}],
                "statistics": {"wilson_ci": list, "mcnemar_p": float},
                "confidence": float,
            }
        """
        ...

    async def shutdown(self) -> None:
        """Shut down Lean 4 server and DeepProbLog engine."""
        ...

    # --- Euler-specific methods ---

    async def prove(
        self,
        theorem: str,
        timeout_s: float = 60.0,
    ) -> dict[str, Any]:
        """Attempt to prove a theorem in Lean 4.

        Args:
            theorem: Lean 4 theorem statement.
            timeout_s: Maximum time for proof search (default: 60s).

        Returns:
            Dictionary with keys:
            - status (str): "proven" | "refuted" | "timeout" | "error".
            - proof (str | None): The proof term if successful.
            - tactics (list[str]): Sequence of tactics applied.
            - time_s (float): Wall time consumed.

        Raises:
            Lean4ServerError: If the Lean 4 server is unavailable.
        """
        ...

    async def probabilistic_verify(
        self,
        program: str,
        query: str,
    ) -> dict[str, Any]:
        """Run probabilistic verification via DeepProbLog.

        Args:
            program: DeepProbLog program (Prolog + neural predicates).
            query: The query to evaluate.

        Returns:
            Dictionary with keys:
            - probability (float): Estimated probability [0, 1].
            - explanation (str): Human-readable explanation.
            - neural_outputs (dict): Raw neural predicate outputs.
        """
        ...

    def wilson_ci(
        self,
        n_success: int,
        n_total: int,
        confidence: float = 0.95,
    ) -> tuple[float, float]:
        """Compute Wilson score confidence interval.

        Args:
            n_success: Number of successes.
            n_total: Total number of trials.
            confidence: Confidence level (default: 0.95).

        Returns:
            Tuple of (lower_bound, upper_bound).
        """
        ...

    def mcnemar_test(
        self,
        table: tuple[int, int, int, int],
    ) -> dict[str, float]:
        """Perform McNemar's test for paired proportions.

        Args:
            table: (a, b, c, d) contingency table values where:
                a = both correct, b = only system A correct,
                c = only system B correct, d = both incorrect.

        Returns:
            Dictionary with keys:
            - chi2 (float): McNemar's chi-squared statistic.
            - p_value (float): Two-tailed p-value.
            - significant (bool): Whether p < 0.05.
        """
        ...
```

---

## 6. Socrates Agent

```python
# agora/agents/socrates/agent.py

class SocratesAgent(BaseAgent):
    """Dialectical Orchestrator Agent.

    Socrates manages the Elenchus-Maieutic dialectical protocol,
    coordinating Galileo and Euler through structured cycles of
    questioning, verification, and synthesis.

    Socrates does not generate scientific content directly. Instead,
    it poses probing questions (Elenchus), extracts knowledge
    (Maieutics), and synthesises verified results.

    Args:
        agent_id: Unique agent identifier.
        budget: BudgetGuard for the experiment.
        max_cycles: Maximum Elenchus cycles per query (default: 5).
        agents: Registry of available agents.

    Attributes:
        max_cycles: Maximum dialectical cycles.
        aporia_threshold: Cycles before declaring aporia (default: 3).
        cycle_history: Log of all completed cycles.
    """

    def __init__(
        self,
        agent_id: str,
        budget: BudgetGuard,
        max_cycles: int = 5,
        agents: dict[AgentRole, BaseAgent] | None = None,
    ) -> None:
        super().__init__(agent_id, AgentRole.SOCRATES, budget)
        self.max_cycles = max_cycles
        self.aporia_threshold = 3
        self.agents = agents or {}
        self.cycle_history: list[dict[str, Any]] = []

    async def init(self) -> None:
        """Initialise the orchestration runtime."""
        ...

    async def step(self, message: AgoraMessage) -> AgoraMessage:
        """Execute a full dialectical session.

        This is the main entry point for scientific queries. Socrates
        orchestrates the following sequence:

        1. Parse and classify the user query
        2. Enter Elenchus cycle:
           a. Send ElencticalQuery to Galileo
           b. Receive hypotheses
           c. Send VerificationRequest to Euler
           d. Receive proofs/refutations
           e. Synthesise results
        3. Repeat until consensus or aporia

        Args:
            message: The initial query (from user or external system).

        Returns:
            AgoraMessage with final result or aporia declaration.
        """
        ...

    async def shutdown(self) -> None:
        """Shut down orchestration and flush logs."""
        ...

    # --- Socrates-specific methods ---

    async def run_elenchus_cycle(
        self,
        query: str,
        cycle_number: int,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute one Elenchus-Maieutic cycle.

        Args:
            query: The scientific question.
            cycle_number: Current cycle number (1-indexed).
            context: Previous cycle context for refinement.

        Returns:
            Cycle result dictionary with keys:
            - hypotheses (list): Galileo's hypothesis set.
            - verifications (list): Euler's verification results.
            - synthesis (str): Socrates' synthesis.
            - consensus (bool): Whether consensus was reached.
            - cost_usd (str): Total cost of this cycle.
        """
        ...

    async def synthesise(
        self,
        hypotheses: list[dict[str, Any]],
        verifications: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Perform dialectical synthesis of hypotheses and proofs.

        Combines Galileo's empirical findings with Euler's formal
        verifications to produce a unified, verified result.

        Args:
            hypotheses: List of hypothesis dictionaries from Galileo.
            verifications: List of verification results from Euler.

        Returns:
            Synthesis dictionary with keys:
            - conclusion (str): The synthesised conclusion.
            - confidence (float): Overall confidence [0, 1].
            - proven_claims (list[str]): Formally proven statements.
            - open_questions (list[str]): Unresolved questions.
        """
        ...

    def declare_aporia(
        self,
        reason: str,
        open_questions: list[str],
    ) -> AgoraMessage:
        """Declare aporia (irresolvable contradiction).

        Called when the maximum number of cycles is exhausted without
        reaching consensus. This is a valid scientific outcome.

        Args:
            reason: Explanation of why consensus could not be reached.
            open_questions: List of questions that remain unresolved.

        Returns:
            AgoraMessage of type APORIA.
        """
        ...
```

---

## 7. BudgetGuard

See [BUDGET_POLICY.md](../BUDGET_POLICY.md) for full policy documentation.

```python
# agora/core/budget.py

class BudgetGuard:
    """Thread-safe budget enforcement for experiments.

    Raises BudgetExhaustedError if any operation would exceed
    the remaining budget. All amounts are in USD.

    Args:
        experiment_budget: Maximum budget for this experiment.

    Attributes:
        remaining: Current remaining budget (read-only property).
        in_austerity: True when budget < $1.00.

    Example:
        >>> guard = BudgetGuard(Decimal("100.00"))
        >>> guard.pre_approve(Decimal("0.05"))
        True
        >>> guard.deduct(Decimal("0.05"))
        Decimal('99.95')
        >>> guard.remaining
        Decimal('99.95')
    """
    ...


class BudgetExhaustedError(Exception):
    """Raised when an operation would exceed the experiment budget."""
    ...


class CostEstimator:
    """Pre-estimates cost before executing cloud operations.

    Class methods estimate costs for GPU compute and NIM API calls
    based on published rates with a 15% overhead factor.

    Example:
        >>> CostEstimator.estimate_gpu("L4", wall_time_s=3600)
        Decimal('0.805')
        >>> CostEstimator.estimate_nim("bionemo", num_calls=5)
        Decimal('0.25')
    """
    ...
```

---

## 8. Configuration

Agent configuration is loaded from `agora.toml`. See [SPECS.md](../SPECS.md)
§10 for the full schema.

```python
# agora/config.py

from dataclasses import dataclass

@dataclass
class AgoraConfig:
    """Root configuration for the Scientific Agora.

    Loaded from agora.toml at startup.

    Attributes:
        version: Agora framework version.
        budget_usd: Experiment budget ceiling.
        max_cycles: Maximum Elenchus cycles.
        symbrain: SymBrain v5 configuration.
        galileo: Galileo agent configuration.
        euler: Euler agent configuration.
        socrates: Socrates agent configuration.
        turing: Turing agent configuration.
    """
    version: str
    budget_usd: float
    max_cycles: int
    symbrain: "SymBrainConfig"
    galileo: "GalileoConfig"
    euler: "EulerConfig"
    socrates: "SocratesConfig"
    turing: "TuringConfig"

    @classmethod
    def from_toml(cls, path: str = "agora.toml") -> "AgoraConfig":
        """Load configuration from a TOML file.

        Args:
            path: Path to the TOML configuration file.

        Returns:
            Populated AgoraConfig instance.

        Raises:
            FileNotFoundError: If the config file doesn't exist.
            ConfigValidationError: If required fields are missing.
        """
        ...
```

---

## 9. Turing Agent

```python
# agora/agents/turing/agent.py

class TuringAgent(BaseAgent):
    """Computer Science & Optimization Agent.

    Turing monitors Agora reasoning traces, evaluates memory bump utilization
    in the 8GB scratch arena, profiles solver evaluations, and optimizes SymBrain
    configurations. He also audits billing lines to enforce serverless zero-replicas.

    Registered tools:
      1. ``model_profiler``          — Profile wall-clock latency and compute bottlenecks.
      2. ``runtime_optimizer``        — Propose optimized exploration constants and solver tolerances.
      3. ``gcp_billing_monitor``      — Audit Cloud Run deployments for scale-to-zero compliance.

    Args:
        agent_id: Unique agent identifier.
        budget: BudgetGuard instance for cost tracking.

    Example:
        >>> turing = TuringAgent(
        ...     agent_id="turing-001",
        ...     budget=BudgetGuard(Decimal("100.00")),
        ... )
        >>> await turing.init()
    """

    def __init__(self, agent_id: str, budget: BudgetGuard) -> None:
        super().__init__(agent_id, AgentRole.OPTIMIZER, budget)

    async def init(self) -> None:
        """Initialise optimization registries."""
        ...

    async def step(self, message: AgoraMessage) -> AgoraMessage:
        """Process an optimization audit request and return optimized parameters.

        Args:
            message: Incoming request containing execution trace context.

        Returns:
            AgoraMessage containing profiling diagnostics and optimized configurations.
        """
        ...


# --- Specialized Turing Optimization Tools ---

def profile_execution_trace(telemetry_data: dict[str, Any]) -> dict[str, Any]:
    """Diagnose execution trace anomalies and bottlenecks.

    Checks scratch bump allocator capacity and ODE/DAE evaluations trace.

    Args:
        telemetry_data: Latency, MCTS nodes expanded, and allocated bytes.

    Returns:
        Diagnosis dict with bottleneck alerts.
    """
    ...


def optimize_runtime_parameters(
    bottleneck_diagnosis: dict[str, Any],
    budget_remaining_usd: float,
) -> dict[str, Any]:
    """Calculate dynamic optimization values for SymBrain v5 and rusty-SUNDIALS.

    Args:
        bottleneck_diagnosis: Diagnosis results.
        budget_remaining_usd: Remaining session cash limits.

    Returns:
        Optimized param values (MCTS depth, rtol, early stopping time window).
    """
    ...


def monitor_gcp_billing_efficiency(execution_history: list[dict[str, Any]]) -> dict[str, Any]:
    """Enforce serverless zero-replica constraints.

    Args:
        execution_history: List of service metrics.

    Returns:
        Billing audit verdict.
    """
    ...
```

---

## Cross-References

- [ARCHITECTURE.md](../ARCHITECTURE.md) — Agent communication topology
- [SPECS.md](../SPECS.md) — Agent specifications and parameters
- [solvers.md](solvers.md) — Solver API (used by Galileo)
- [verifiers.md](verifiers.md) — Verifier API (used by Euler)
- [../tutorials/quickstart.md](../tutorials/quickstart.md) — Getting started

---

*Copyright © 2026 Xavier Callens / Socrate AI Lab, Paris, France.*
*Licensed under Apache 2.0 (framework) and CC-BY-NC-ND 4.0 (proprietary content).*
*Patent Pending: US-PAT-PEND-2026-0525*
