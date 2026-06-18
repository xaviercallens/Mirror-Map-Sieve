# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Olympiad Session Manager — track round state and performance trends.

Patent: US-PAT-PEND-2026-0525
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from agents.galois.olympiad.rlfc_engine import RLFCSigmaUpdate


@dataclass
class OlympiadRoundResult:
    """Outcome of a single Olympiad round."""
    round_number:     int
    problems_total:   int
    problems_correct: int
    score_pct:        float
    sigma_update:     RLFCSigmaUpdate
    elapsed_seconds:  float
    per_problem_verdicts: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_improvement(self) -> bool:
        return self.sigma_update.improvement > 0.0


class OlympiadSession:
    """Manages state for a full Mind Olympiad run across multiple rounds.

    Tracks:
    - Per-round results (score, RLFC update, problem verdicts)
    - Cumulative improvement trend
    - Best/worst round
    - Time spent per round

    Also acts as the canonical reference for the current round number,
    shared between GaloisAgent, EulerAgent, and the RLFC engine.
    """

    def __init__(
        self,
        session_name: str = "AdlerOlympiad",
        total_rounds: int = 5,
        problems_per_round: int | None = None,
    ) -> None:
        self.session_name       = session_name
        self.total_rounds       = total_rounds
        self.problems_per_round = problems_per_round  # None = all problems
        self._rounds: list[OlympiadRoundResult] = []
        self._start_time        = time.monotonic()
        self._round_start: float | None = None

    # ------------------------------------------------------------------
    # Round lifecycle
    # ------------------------------------------------------------------

    def start_round(self) -> int:
        """Mark the start of a new round. Returns the 1-indexed round number."""
        self._round_start = time.monotonic()
        return len(self._rounds) + 1

    def end_round(
        self,
        problems_total: int,
        problems_correct: int,
        sigma_update: RLFCSigmaUpdate,
        per_problem_verdicts: list[dict[str, Any]] | None = None,
    ) -> OlympiadRoundResult:
        """Mark the end of a round and record results."""
        elapsed = time.monotonic() - (self._round_start or self._start_time)
        score = (problems_correct / max(problems_total, 1)) * 100.0
        result = OlympiadRoundResult(
            round_number         = len(self._rounds) + 1,
            problems_total       = problems_total,
            problems_correct     = problems_correct,
            score_pct            = score,
            sigma_update         = sigma_update,
            elapsed_seconds      = elapsed,
            per_problem_verdicts = per_problem_verdicts or [],
        )
        self._rounds.append(result)
        return result

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    @property
    def current_round(self) -> int:
        return len(self._rounds)

    @property
    def rounds(self) -> list[OlympiadRoundResult]:
        return list(self._rounds)

    @property
    def best_round(self) -> OlympiadRoundResult | None:
        if not self._rounds:
            return None
        return max(self._rounds, key=lambda r: r.score_pct)

    @property
    def worst_round(self) -> OlympiadRoundResult | None:
        if not self._rounds:
            return None
        return min(self._rounds, key=lambda r: r.score_pct)

    def improvement_trend(self) -> float:
        """Return the average score gain per round (positive = improving)."""
        if len(self._rounds) < 2:
            return 0.0
        deltas = [
            self._rounds[i].score_pct - self._rounds[i - 1].score_pct
            for i in range(1, len(self._rounds))
        ]
        return sum(deltas) / len(deltas)

    def score_history(self) -> list[float]:
        return [r.score_pct for r in self._rounds]

    def total_elapsed_seconds(self) -> float:
        return time.monotonic() - self._start_time

    def summary(self) -> dict[str, Any]:
        """Return a full session summary dict for Alexandrie ingestion."""
        scores = self.score_history()
        return {
            "session_name":     self.session_name,
            "total_rounds":     self.current_round,
            "score_history":    scores,
            "best_score":       max(scores) if scores else 0.0,
            "final_score":      scores[-1] if scores else 0.0,
            "improvement_trend_pct_per_round": self.improvement_trend(),
            "total_elapsed_s":  self.total_elapsed_seconds(),
            "rounds": [
                {
                    "round": r.round_number,
                    "score": r.score_pct,
                    "correct": r.problems_correct,
                    "total": r.problems_total,
                    "delta_sigma_ded":  r.sigma_update.delta_sigma_ded,
                    "delta_sigma_gen":  r.sigma_update.delta_sigma_gen,
                    "delta_sigma_mcts": r.sigma_update.delta_sigma_mcts,
                    "learning_rate":    r.sigma_update.learning_rate,
                    "elapsed_s":        r.elapsed_seconds,
                }
                for r in self._rounds
            ],
        }

    def print_round_banner(self, result: OlympiadRoundResult) -> None:
        """Print a formatted round summary to stdout."""
        trend_icon = "📈" if result.is_improvement else "📊"
        print(f"\n  {'─' * 70}")
        print(
            f"  {trend_icon}  Round {result.round_number}/{self.total_rounds} Complete: "
            f"{result.problems_correct}/{result.problems_total} correct "
            f"({result.score_pct:.1f}%)"
        )
        print(f"     Δσ_ded={result.sigma_update.delta_sigma_ded:+.4f}  "
              f"Δσ_gen={result.sigma_update.delta_sigma_gen:+.4f}  "
              f"Δσ_mcts={result.sigma_update.delta_sigma_mcts:+.4f}  "
              f"LR={result.sigma_update.learning_rate:.4f}")
        if result.round_number > 1:
            trend = result.sigma_update.improvement
            print(f"     Improvement vs prior round: {trend:+.1f}%")
        print(f"     Elapsed: {result.elapsed_seconds:.1f}s")
        print(f"  {'─' * 70}")
