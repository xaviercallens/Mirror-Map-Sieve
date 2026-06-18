# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Inference Transfer Bank — Persist RLFC learning across Olympiad rounds.

The InferenceTransferBank compresses learned RLFC updates into a transfer
vector that is saved to Alexandrie as a CHECKPOINT artifact. At the start
of each new round, Galois loads this checkpoint and injects the learned
sigma deltas into its active cortex.

This implements 'direct inference transfer': rather than full gradient-based
weight updates (which would require access to model weights), we encode the
improvements as cortex-level parameter shifts and mistake-avoidance strategies
embedded in the prompt/planning logic.

Patent: US-PAT-PEND-2026-0525
"""
from __future__ import annotations

import json
import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from agents.galois.olympiad.rlfc_engine import MistakeFingerprint, RLFCSigmaUpdate


@dataclass
class TransferVector:
    """A compressed representation of all RLFC learning up to a given round."""
    round_number: int
    cumulative_delta_ded:  float   # Total Δσ_ded accumulated
    cumulative_delta_gen:  float   # Total Δσ_gen accumulated
    cumulative_delta_mcts: float   # Total Δσ_mcts accumulated
    best_score_seen:       float   # Best round score achieved
    mean_improvement:      float   # Mean round-over-round improvement
    mistake_fingerprints:  list[dict[str, Any]] = field(default_factory=list)
    avoidance_strategies:  list[str] = field(default_factory=list)  # For prompt injection


class InferenceTransferBank:
    """Persists and loads RLFC learning state across Olympiad sessions.

    Storage: JSON checkpoint file under the Alexandrie vault.
    Loading: On apply_transfer(), injects learned delta into active cortex.
    """

    _CHECKPOINT_FILENAME = "galois_rlfc_transfer_checkpoint.json"

    def __init__(self, vault_root: str | None = None) -> None:
        if vault_root is None:
            vault_root = str(
                Path.home() / ".gemini" / "antigravity" / "alexandrie_vault"
            )
        self._vault_root = Path(vault_root)
        self._ckpt_path = self._vault_root / "private" / "checkpoint" / self._CHECKPOINT_FILENAME
        self._ckpt_path.parent.mkdir(parents=True, exist_ok=True)
        self._transfer: TransferVector | None = None

    # ------------------------------------------------------------------
    # Build and save a transfer vector from RLFC history
    # ------------------------------------------------------------------

    def record_transfer(
        self,
        updates: list[RLFCSigmaUpdate],
        fingerprints: list[MistakeFingerprint],
    ) -> TransferVector:
        """Compress RLFC history into a TransferVector and persist it."""
        if not updates:
            vec = TransferVector(
                round_number=0,
                cumulative_delta_ded=0.0,
                cumulative_delta_gen=0.0,
                cumulative_delta_mcts=0.0,
                best_score_seen=0.0,
                mean_improvement=0.0,
            )
            self._save(vec)
            self._transfer = vec
            return vec

        cum_ded  = sum(u.delta_sigma_ded  for u in updates)
        cum_gen  = sum(u.delta_sigma_gen  for u in updates)
        cum_mcts = sum(u.delta_sigma_mcts for u in updates)
        best     = max(u.batch_score for u in updates)
        mean_imp = sum(u.improvement for u in updates) / len(updates)

        # Build avoidance strategy prompts from fingerprints
        strategies = self._build_avoidance_strategies(fingerprints)

        vec = TransferVector(
            round_number       = len(updates),
            cumulative_delta_ded  = cum_ded,
            cumulative_delta_gen  = cum_gen,
            cumulative_delta_mcts = cum_mcts,
            best_score_seen    = best,
            mean_improvement   = mean_imp,
            mistake_fingerprints = [
                {
                    "problem_type": fp.problem_type,
                    "error_class": fp.error_class.value,
                    "correction_strategy": fp.correction_strategy,
                    "frequency": fp.frequency,
                }
                for fp in fingerprints[:10]  # Top 10 most frequent
            ],
            avoidance_strategies = strategies,
        )
        self._save(vec)
        self._transfer = vec
        return vec

    # ------------------------------------------------------------------
    # Load checkpoint and inject into cortex
    # ------------------------------------------------------------------

    def load(self) -> TransferVector | None:
        """Load the persisted transfer vector from disk."""
        if not self._ckpt_path.exists():
            return None
        try:
            data = json.loads(self._ckpt_path.read_text(encoding="utf-8"))
            vec = TransferVector(**data)
            self._transfer = vec
            return vec
        except Exception:
            return None

    def apply_transfer(self, cortex: Any) -> dict[str, Any]:
        """Inject the loaded transfer vector into the active Galois cortex.

        Returns a summary dict for logging.
        """
        vec = self._transfer or self.load()
        if vec is None:
            return {"status": "no_checkpoint_found", "applied": False}

        routing = getattr(cortex, "routing", None)
        if routing is None:
            return {"status": "cortex_no_routing", "applied": False}

        # Apply cumulative deltas (clamped)
        routing.sigma_ded  = max(0.10, min(0.90, routing.sigma_ded  + vec.cumulative_delta_ded))
        routing.sigma_gen  = max(0.10, min(0.90, routing.sigma_gen  + vec.cumulative_delta_gen))
        routing.sigma_mcts = max(1.5,  min(10.0, routing.sigma_mcts + vec.cumulative_delta_mcts))

        return {
            "status": "transfer_applied",
            "applied": True,
            "round_checkpoint": vec.round_number,
            "best_score_seen": vec.best_score_seen,
            "mean_improvement": vec.mean_improvement,
            "avoidance_strategies_injected": len(vec.avoidance_strategies),
            "new_sigma_ded":  routing.sigma_ded,
            "new_sigma_gen":  routing.sigma_gen,
            "new_sigma_mcts": routing.sigma_mcts,
        }

    def get_avoidance_prompt_block(self) -> str:
        """Return a formatted prompt block embedding all learned avoidance strategies."""
        vec = self._transfer or self.load()
        if vec is None or not vec.avoidance_strategies:
            return ""
        lines = [
            "## Learned Mistake Avoidance (RLFC Transfer)",
            f"(From {vec.round_number} prior Olympiad round(s))",
            "",
        ]
        for i, strategy in enumerate(vec.avoidance_strategies, 1):
            lines.append(f"{i}. {strategy}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _save(self, vec: TransferVector) -> None:
        """Persist TransferVector to disk as JSON."""
        data = {
            "round_number":           vec.round_number,
            "cumulative_delta_ded":   vec.cumulative_delta_ded,
            "cumulative_delta_gen":   vec.cumulative_delta_gen,
            "cumulative_delta_mcts":  vec.cumulative_delta_mcts,
            "best_score_seen":        vec.best_score_seen,
            "mean_improvement":       vec.mean_improvement,
            "mistake_fingerprints":   vec.mistake_fingerprints,
            "avoidance_strategies":   vec.avoidance_strategies,
        }
        self._ckpt_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @staticmethod
    def _build_avoidance_strategies(fingerprints: list[MistakeFingerprint]) -> list[str]:
        """Convert mistake fingerprints into human-readable avoidance strategies."""
        strategies: list[str] = []
        _EC_MAP = {
            "sign_error":           "Double-check every sign change in algebraic manipulations.",
            "arithmetic":           "Verify all arithmetic computations step by step before proceeding.",
            "domain_violation":     "Always state and verify domain constraints (e.g., x > 0, |r| < 1).",
            "missing_case":         "Enumerate ALL cases explicitly; never assume a case is obvious.",
            "logical_gap":          "Justify each deductive step; cite the theorem or axiom used.",
            "strategy_error":       "Step back and verify the chosen proof strategy before computing.",
            "formula_confusion":    "State the formula being applied and its exact preconditions.",
            "incomplete_solution":  "Always conclude with the final explicit answer/value.",
            "vagueness":            "Replace 'clearly', 'obviously', 'trivially' with full justification.",
        }
        seen: set[str] = set()
        for fp in fingerprints:
            ec = fp.error_class.value
            if ec not in seen and ec in _EC_MAP:
                strategies.append(f"[{ec.upper()}] (×{fp.frequency}) {_EC_MAP[ec]}")
                seen.add(ec)
        return strategies
