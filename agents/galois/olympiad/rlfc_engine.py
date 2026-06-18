# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""RLFC Engine — Reinforcement Learning from Feedback/Correction for Galois.

The RLFCEngine processes structured OlympiadFeedback from the Euler corrector
and converts it into gradient signals that update the Galois cortex parameters:
  - σ_ded (deductive hemisphere strength)
  - σ_gen (generative hemisphere strength)
  - σ_mcts (MCTS depth multiplier)

This implements a cosine-annealed adaptive learning rule that grows more
conservative as training progresses (standard curriculum learning schedule).

Patent: US-PAT-PEND-2026-0525
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FeedbackVerdict(str, Enum):
    """Euler's verdict on a Galois solution attempt."""
    CORRECT           = "correct"
    PARTIAL           = "partial"
    CONCEPTUAL_ERROR  = "conceptual_error"
    COMPUTATION_ERROR = "computation_error"
    INCOMPLETE        = "incomplete"


class ErrorClass(str, Enum):
    """Fine-grained classification of the type of mathematical error."""
    SIGN_ERROR          = "sign_error"           # Wrong sign in algebra
    ARITHMETIC          = "arithmetic"           # Simple computation mistake
    DOMAIN_VIOLATION    = "domain_violation"     # Ignored domain/range constraint
    MISSING_CASE        = "missing_case"         # Failed to consider all cases
    LOGICAL_GAP         = "logical_gap"          # Non-sequitur deductive step
    STRATEGY_ERROR      = "strategy_error"       # Fundamentally wrong approach
    FORMULA_CONFUSION   = "formula_confusion"    # Applied wrong formula/theorem
    INCOMPLETE_SOLUTION = "incomplete_solution"  # Correct start, unfinished
    VAGUENESS           = "vagueness"            # "Obviously", "clearly" without proof
    NO_ERROR            = "no_error"             # Correct solution


@dataclass(slots=True)
class OlympiadFeedback:
    """Structured feedback from Euler on one Galois solution attempt."""
    problem_id: str
    round_number: int
    verdict: FeedbackVerdict
    error_class: ErrorClass
    severity: float                    # 0.0 (trivial) – 1.0 (fundamental)
    affected_step: str                 # Description of the erroneous step
    correct_step: str                  # What the step should have been
    correction_text: str               # Full natural language correction
    galois_answer: str
    reference_answer: str
    confidence_before: float = 0.0     # Galois's stated confidence
    confidence_delta: float = 0.0      # How confidence should adjust


@dataclass
class RLFCSigmaUpdate:
    """The sigma parameter updates derived from one batch of feedback."""
    delta_sigma_ded: float  = 0.0    # Change to deductive hemisphere weight
    delta_sigma_gen: float  = 0.0    # Change to generative hemisphere weight
    delta_sigma_mcts: float = 0.0    # Change to MCTS depth multiplier
    learning_rate:    float = 0.05   # Effective LR after cosine annealing
    batch_score:      float = 0.0    # Fraction correct in this batch
    improvement:      float = 0.0    # Improvement vs previous batch


@dataclass
class MistakeFingerprint:
    """A persistent record of a mistake type and its learned correction."""
    problem_type: str
    error_class: ErrorClass
    correction_strategy: str
    frequency: int = 1
    last_round: int = 0


class RLFCEngine:
    """Reinforcement Learning from Feedback/Correction engine for Galois.

    After each Olympiad round, the engine:
    1. Computes aggregate gradient signals from all Euler feedback items
    2. Applies cosine-annealed learning rate schedule
    3. Updates σ_ded, σ_gen, σ_mcts in the active Galois cortex
    4. Maintains a mistake fingerprint database for InferenceTransfer

    The learning rule is inspired by DPO (Direct Preference Optimisation) but
    adapted for symbolic reasoning: incorrect deductive steps increase σ_ded,
    while over-rigid deduction decreases σ_gen to re-enable creative search.
    """

    # Learning rate hyperparameters
    _LR_INITIAL:  float = 0.10   # Starting learning rate
    _LR_MIN:      float = 0.005  # Minimum (fully annealed) learning rate
    _SIGMA_DED_MAX: float = 0.90
    _SIGMA_DED_MIN: float = 0.10
    _SIGMA_GEN_MAX: float = 0.90
    _SIGMA_GEN_MIN: float = 0.10
    _SIGMA_MCTS_MAX: float = 10.0
    _SIGMA_MCTS_MIN: float = 1.5

    def __init__(self, total_rounds: int = 10) -> None:
        self._total_rounds = total_rounds
        self._current_round = 0
        self._previous_batch_score: float | None = None
        self._fingerprints: dict[str, MistakeFingerprint] = {}
        self._history: list[RLFCSigmaUpdate] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_feedback_batch(
        self,
        feedback_list: list[OlympiadFeedback],
        cortex: Any,   # GaloisCortexConfig or SymBrainV8Cortex
    ) -> RLFCSigmaUpdate:
        """Process a batch of Euler feedback and update the cortex σ params.

        Returns the sigma update record for logging.
        """
        self._current_round += 1
        lr = self._cosine_lr(self._current_round)

        # Aggregate metrics
        n = len(feedback_list)
        if n == 0:
            return RLFCSigmaUpdate(learning_rate=lr)

        correct   = sum(1 for f in feedback_list if f.verdict == FeedbackVerdict.CORRECT)
        batch_score = correct / n
        improvement = (
            (batch_score - self._previous_batch_score)
            if self._previous_batch_score is not None
            else 0.0
        )
        self._previous_batch_score = batch_score

        # Compute sigma gradient signals
        delta_ded  = 0.0
        delta_gen  = 0.0
        delta_mcts = 0.0

        for fb in feedback_list:
            grad = self._feedback_to_gradient(fb)
            delta_ded  += grad["d_ded"]
            delta_gen  += grad["d_gen"]
            delta_mcts += grad["d_mcts"]
            self._register_fingerprint(fb)

        # Normalise by batch size and apply learning rate
        delta_ded  = lr * delta_ded  / n
        delta_gen  = lr * delta_gen  / n
        delta_mcts = lr * delta_mcts / n

        # Apply to cortex (clamped to valid ranges)
        self._apply_to_cortex(cortex, delta_ded, delta_gen, delta_mcts)

        update = RLFCSigmaUpdate(
            delta_sigma_ded  = delta_ded,
            delta_sigma_gen  = delta_gen,
            delta_sigma_mcts = delta_mcts,
            learning_rate    = lr,
            batch_score      = batch_score,
            improvement      = improvement,
        )
        self._history.append(update)
        return update

    def get_mistake_fingerprints(self) -> list[MistakeFingerprint]:
        """Return sorted list of known mistake fingerprints (most frequent first)."""
        return sorted(self._fingerprints.values(), key=lambda f: -f.frequency)

    def get_learning_history(self) -> list[RLFCSigmaUpdate]:
        """Return the full history of sigma updates."""
        return list(self._history)

    def improvement_trend(self) -> float:
        """Return the mean improvement rate over the last 3 rounds."""
        recent = self._history[-3:]
        if not recent:
            return 0.0
        return sum(u.improvement for u in recent) / len(recent)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cosine_lr(self, round_idx: int) -> float:
        """Cosine annealing learning rate schedule."""
        progress = min(round_idx / max(self._total_rounds, 1), 1.0)
        return self._LR_MIN + 0.5 * (self._LR_INITIAL - self._LR_MIN) * (
            1 + math.cos(math.pi * progress)
        )

    def _feedback_to_gradient(self, fb: OlympiadFeedback) -> dict[str, float]:
        """Map a single feedback item to (d_ded, d_gen, d_mcts) gradient signals."""
        v = fb.verdict
        ec = fb.error_class
        sev = fb.severity

        if v == FeedbackVerdict.CORRECT:
            # Correct: lightly reinforce current balance
            return {"d_ded": 0.0, "d_gen": 0.0, "d_mcts": 0.0}

        if ec in (ErrorClass.LOGICAL_GAP, ErrorClass.MISSING_CASE, ErrorClass.STRATEGY_ERROR):
            # Deductive weakness → increase formal reasoning
            return {"d_ded": +sev * 0.5, "d_gen": -sev * 0.1, "d_mcts": +sev * 1.0}

        if ec in (ErrorClass.SIGN_ERROR, ErrorClass.ARITHMETIC, ErrorClass.FORMULA_CONFUSION):
            # Computation slip → slow creative leap, increase verification
            return {"d_ded": +sev * 0.3, "d_gen": -sev * 0.05, "d_mcts": +sev * 0.5}

        if ec == ErrorClass.DOMAIN_VIOLATION:
            # Domain: requires formal constraint checking
            return {"d_ded": +sev * 0.4, "d_gen": 0.0, "d_mcts": +sev * 0.8}

        if ec == ErrorClass.VAGUENESS:
            # Vagueness: needs more rigorous deduction
            return {"d_ded": +sev * 0.6, "d_gen": -sev * 0.2, "d_mcts": 0.0}

        if ec == ErrorClass.INCOMPLETE_SOLUTION:
            # Incomplete: needs more MCTS search depth
            return {"d_ded": 0.0, "d_gen": 0.0, "d_mcts": +sev * 1.5}

        return {"d_ded": 0.0, "d_gen": 0.0, "d_mcts": 0.0}

    def _apply_to_cortex(
        self,
        cortex: Any,
        delta_ded: float,
        delta_gen: float,
        delta_mcts: float,
    ) -> None:
        """Apply the gradient updates to cortex parameters with safety clamping."""
        routing = getattr(cortex, "routing", None)
        if routing is None:
            return  # Cortex doesn't have routing tensor — no-op

        routing.sigma_ded = max(
            self._SIGMA_DED_MIN,
            min(self._SIGMA_DED_MAX, routing.sigma_ded + delta_ded),
        )
        routing.sigma_gen = max(
            self._SIGMA_GEN_MIN,
            min(self._SIGMA_GEN_MAX, routing.sigma_gen + delta_gen),
        )
        routing.sigma_mcts = max(
            self._SIGMA_MCTS_MIN,
            min(self._SIGMA_MCTS_MAX, routing.sigma_mcts + delta_mcts),
        )

    def _register_fingerprint(self, fb: OlympiadFeedback) -> None:
        """Record or update a mistake fingerprint in the database."""
        if fb.verdict == FeedbackVerdict.CORRECT:
            return
        key = f"{fb.problem_id}::{fb.error_class.value}"
        if key in self._fingerprints:
            fp = self._fingerprints[key]
            fp.frequency += 1
            fp.last_round = self._current_round
        else:
            self._fingerprints[key] = MistakeFingerprint(
                problem_type=fb.problem_id.split("_c")[0],
                error_class=fb.error_class,
                correction_strategy=fb.correction_text[:120],
                frequency=1,
                last_round=self._current_round,
            )
