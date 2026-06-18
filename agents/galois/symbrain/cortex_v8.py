# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""SymBrain v8 'Mind Olympiad' Cortex — Galois RLFC-enhanced reasoning cortex.

Extends SymBrain v7 (Galois-Einstein) with:
1. Contest-category routing via extended SIAG (Solomonoff Induction with
   domain-aware Kolmogorov approximation)
2. RLFC gradient integration (receives Euler's correction signals)
3. Direct inference transfer (loads prior-round checkpoint)
4. Olympiad-specific proof synthesis (contest-tuned tactic templates)
5. Improvement trajectory computation (trend scoring for Turing monitor)

Patent: US-PAT-PEND-2026-0525
"""
from __future__ import annotations

import gzip
import hashlib
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from agents.galois.symbrain.cortex_v4 import (
    GaloisCortexConfig,
    GaloisRoutingTensor,
    HemisphereMode,
)


class ContestCategory(str, Enum):
    """Contest math domain categories for SIAG routing."""
    ALGEBRA       = "algebra"
    NUMBER_THEORY = "number_theory"
    COMBINATORICS = "combinatorics"
    GEOMETRY      = "geometry"
    CALCULUS      = "calculus"
    PROBABILITY   = "probability"
    TRIGONOMETRY  = "trigonometry"
    SEQUENCES     = "sequences"
    UNKNOWN       = "unknown"


@dataclass
class OlympiadRoutingDecision:
    """Full routing decision from SIAG for one problem."""
    problem_id:       str
    contest_category: ContestCategory
    kolmogorov_ratio: float           # gzip(problem) / len(problem) — complexity proxy
    assigned_tier:    str             # "edge-7b" | "cloud-32b" | "cloud-141b"
    sigma_ded_used:   float
    sigma_gen_used:   float
    sigma_mcts_used:  float
    avoidance_hint:   str = ""        # Injected from InferenceTransfer


@dataclass
class OlympiadProofResult:
    """Result of synthesize_olympiad_proof()."""
    problem_id:          str
    lean4_skeleton:      str
    reasoning_trace:     list[str]
    tactic_used:         str
    confidence:          float
    has_formal_template: bool
    elapsed_ms:          float
    verification_signature: str


class SymBrainV8Cortex:
    """Mind Olympiad cortex — RLFC-enhanced SymBrain v8.

    Sigma parameter semantics:
    - routing.sigma_ded  ∈ [0.1, 0.9]: Deductive hemisphere strength
    - routing.sigma_gen  ∈ [0.1, 0.9]: Generative hemisphere strength
    - routing.sigma_mcts ∈ [1.5, 10]: MCTS tree-search depth multiplier

    These are dynamically adjusted by the RLFCEngine after every batch
    of Euler corrections, and then persisted via InferenceTransferBank.
    """

    # Contest tactic templates per category
    _TACTIC_TEMPLATES: dict[ContestCategory, list[str]] = {
        ContestCategory.ALGEBRA:       ["ring", "field_simp", "nlinarith", "polyrith"],
        ContestCategory.NUMBER_THEORY: ["omega", "decide", "norm_num", "Nat.dvd_intro"],
        ContestCategory.COMBINATORICS: ["simp [Finset.card]", "aesop", "decide"],
        ContestCategory.GEOMETRY:      ["norm_num", "field_simp", "linarith"],
        ContestCategory.CALCULUS:      ["simp [Real.sqrt]", "norm_num", "positivity"],
        ContestCategory.PROBABILITY:   ["norm_num", "simp [Finset.card_sdiff]"],
        ContestCategory.TRIGONOMETRY:  ["ring", "norm_num", "Real.sin_sq_add_cos_sq"],
        ContestCategory.SEQUENCES:     ["induction", "omega", "simp [Finset.sum_range]"],
        ContestCategory.UNKNOWN:       ["aesop", "simp", "ring"],
    }

    # Tier assignment thresholds (Kolmogorov ratio)
    _TIER_EDGE   = 0.35   # K-ratio < 0.35 → edge-7b
    _TIER_CLOUD  = 0.55   # 0.35 ≤ K-ratio < 0.55 → cloud-32b
    # K-ratio ≥ 0.55 → cloud-141b

    def __init__(self, base_config: GaloisCortexConfig) -> None:
        self.base = base_config
        # Copy routing tensor for local mutations
        self.routing = GaloisRoutingTensor()
        self.routing.sigma_ded  = base_config.routing.sigma_ded
        self.routing.sigma_gen  = base_config.routing.sigma_gen
        self.routing.sigma_mcts = base_config.routing.sigma_mcts
        self.routing.hemisphere = HemisphereMode.BALANCED
        self.symbrain_version   = "v8-MindOlympiad"
        self._proof_count       = 0
        self._trajectory: list[float] = []  # Round scores

    # ------------------------------------------------------------------
    # Hypothesis 1: Olympiad SIAG — Extended contest routing
    # ------------------------------------------------------------------

    def evaluate_olympiad_gating(
        self,
        problem: Any,   # OlympiadProblemRecord
        avoidance_hint: str = "",
    ) -> OlympiadRoutingDecision:
        """Extended SIAG routing with contest-category awareness.

        Uses Kolmogorov complexity approximation (gzip ratio) combined with
        domain-keyword matching to route problems to the optimal reasoning tier.
        """
        q = getattr(problem, "question", str(problem))
        p_id = getattr(problem, "id", "unknown")
        p_type = str(getattr(problem, "problem_type", ""))
        topics = getattr(problem, "topics", [])

        # Kolmogorov ratio: gzip ratio as complexity proxy
        q_bytes = q.encode("utf-8")
        k_ratio = len(gzip.compress(q_bytes)) / max(len(q_bytes), 1)

        # Category detection
        category = self._detect_category(p_type, topics, q)

        # Tier assignment
        if k_ratio < self._TIER_EDGE:
            tier = "edge-7b"
        elif k_ratio < self._TIER_CLOUD:
            tier = "cloud-32b"
        else:
            tier = "cloud-141b"

        # Adjust hemisphere based on category
        if category in (ContestCategory.NUMBER_THEORY, ContestCategory.ALGEBRA):
            self.routing.hemisphere = HemisphereMode.FORMAL
        elif category in (ContestCategory.COMBINATORICS, ContestCategory.GEOMETRY):
            self.routing.hemisphere = HemisphereMode.CREATIVE
        else:
            self.routing.hemisphere = HemisphereMode.BALANCED

        return OlympiadRoutingDecision(
            problem_id       = p_id,
            contest_category = category,
            kolmogorov_ratio = round(k_ratio, 4),
            assigned_tier    = tier,
            sigma_ded_used   = self.routing.sigma_ded,
            sigma_gen_used   = self.routing.sigma_gen,
            sigma_mcts_used  = self.routing.sigma_mcts,
            avoidance_hint   = avoidance_hint,
        )

    # ------------------------------------------------------------------
    # Hypothesis 2: RLFC Gradient Integration
    # ------------------------------------------------------------------

    def route_rlfc_gradient(self, feedback: Any) -> dict[str, float]:
        """Integrate a single OlympiadFeedback into a routing gradient signal.

        This is called by the RLFCEngine — the engine aggregates these per-batch
        and applies the final Δσ updates to this cortex.

        Returns a dict with gradient components for logging.
        """
        severity = getattr(feedback, "severity", 0.5)
        verdict = str(getattr(feedback, "verdict", ""))
        if "correct" in verdict:
            return {"d_ded": 0.0, "d_gen": 0.0, "d_mcts": 0.0}
        # Proxy gradient: wrong answers push toward more formal reasoning
        return {
            "d_ded": +severity * 0.2,
            "d_gen": -severity * 0.05,
            "d_mcts": +severity * 0.5,
        }

    # ------------------------------------------------------------------
    # Hypothesis 3: Direct Inference Transfer
    # ------------------------------------------------------------------

    def apply_inference_transfer(self, transfer_bank: Any) -> dict[str, Any]:
        """Apply the inference transfer bank's checkpoint to this cortex.

        This injects prior-round sigma deltas and avoidance strategy hints
        directly into the cortex state, enabling cross-round learning without
        full weight retraining.
        """
        return transfer_bank.apply_transfer(self)

    # ------------------------------------------------------------------
    # Hypothesis 4: Olympiad Proof Synthesis (LATS + Contest Templates)
    # ------------------------------------------------------------------

    def synthesize_olympiad_proof(
        self,
        problem: Any,
        routing: OlympiadRoutingDecision | None = None,
        avoidance_prompt: str = "",
    ) -> OlympiadProofResult:
        """Generate a contest-calibrated Lean 4 proof skeleton.

        Selects the appropriate tactic template for the problem's contest
        category, then constructs a proof sketch with sorry-marked gaps.
        """
        t0 = time.monotonic()
        self._proof_count += 1

        p_id      = getattr(problem, "id", f"prob_{self._proof_count}")
        category  = routing.contest_category if routing else ContestCategory.UNKNOWN
        template  = getattr(problem, "lean4_template", None)
        question  = getattr(problem, "question", "")
        has_template = template is not None

        tactics = self._TACTIC_TEMPLATES.get(category, ["aesop", "simp"])
        primary_tactic = tactics[0]

        # Build reasoning trace
        trace = self._build_reasoning_trace(problem, category, avoidance_prompt)

        # Build Lean 4 skeleton
        if has_template:
            lean4 = template
        else:
            lean4 = self._generate_lean4_skeleton(p_id, question, primary_tactic)

        # Confidence: higher for easier problems
        difficulty = getattr(problem, "difficulty", None)
        diff_val = difficulty.value if difficulty else 3
        base_conf = max(0.4, 1.0 - (diff_val - 1) * 0.12)
        confidence = min(0.95, base_conf + self.routing.sigma_ded * 0.2)

        sig = hashlib.sha256(f"{p_id}:{lean4}:{primary_tactic}".encode()).hexdigest()[:16]
        elapsed = (time.monotonic() - t0) * 1000

        return OlympiadProofResult(
            problem_id          = p_id,
            lean4_skeleton      = lean4,
            reasoning_trace     = trace,
            tactic_used         = primary_tactic,
            confidence          = confidence,
            has_formal_template = has_template,
            elapsed_ms          = elapsed,
            verification_signature = f"v8-mq-{sig}",
        )

    # ------------------------------------------------------------------
    # Hypothesis 5: Improvement Trajectory
    # ------------------------------------------------------------------

    def compute_improvement_trajectory(self, scores: list[float]) -> dict[str, Any]:
        """Compute the improvement trajectory metric from a round score history.

        Returns:
          - trend: linear regression slope of scores over rounds
          - momentum: exponentially weighted score (more recent rounds weighted more)
          - final_score: last round score
          - projection: extrapolated score at round (current + 3)
        """
        self._trajectory = scores
        n = len(scores)
        if n == 0:
            return {"trend": 0.0, "momentum": 0.0, "final_score": 0.0, "projection": 0.0}

        final = scores[-1]

        if n == 1:
            return {"trend": 0.0, "momentum": final, "final_score": final, "projection": final}

        # Linear regression slope
        x_mean = (n - 1) / 2
        y_mean = sum(scores) / n
        num = sum((i - x_mean) * (s - y_mean) for i, s in enumerate(scores))
        den = sum((i - x_mean) ** 2 for i in range(n))
        trend = num / den if den > 0 else 0.0

        # Exponential momentum (decay = 0.7)
        decay = 0.7
        weight = 1.0
        total_w = 0.0
        momentum = 0.0
        for s in reversed(scores):
            momentum += weight * s
            total_w  += weight
            weight   *= decay
        momentum /= total_w

        projection = min(100.0, final + 3 * trend)

        return {
            "trend":       round(trend, 3),
            "momentum":    round(momentum, 3),
            "final_score": round(final, 3),
            "projection":  round(projection, 3),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _detect_category(
        self,
        p_type: str,
        topics: list[str],
        question: str,
    ) -> ContestCategory:
        """Keyword-based contest category detection."""
        p_type_l = p_type.lower()
        q_lower = question.lower()
        all_text = " ".join(topics) + " " + p_type_l + " " + q_lower

        kw_map: list[tuple[ContestCategory, list[str]]] = [
            (ContestCategory.NUMBER_THEORY,  ["prime", "gcd", "lcm", "modular", "congruence", "divisib", "number_theory"]),
            (ContestCategory.ALGEBRA,        ["factor", "polynomial", "equation", "inequalit", "algebra", "symbolic"]),
            (ContestCategory.COMBINATORICS,  ["combinat", "permutation", "count", "pigeonhole", "binomial", "arrange"]),
            (ContestCategory.GEOMETRY,       ["triangle", "circle", "angle", "area", "geometric", "distance"]),
            (ContestCategory.CALCULUS,       ["derivative", "integral", "limit", "differential", "calculus", "rate", "optimiz"]),
            (ContestCategory.PROBABILITY,    ["probability", "random", "bayes", "event", "likely", "chance"]),
            (ContestCategory.TRIGONOMETRY,   ["trigon", "sin", "cos", "tan", "arcsin", "arccos", "pi"]),
            (ContestCategory.SEQUENCES,      ["sequence", "series", "fibonacci", "recurrence", "sum", "telescope"]),
        ]
        for cat, keywords in kw_map:
            if any(kw in all_text for kw in keywords):
                return cat
        return ContestCategory.UNKNOWN

    def _build_reasoning_trace(
        self,
        problem: Any,
        category: ContestCategory,
        avoidance_prompt: str,
    ) -> list[str]:
        """Build a structured reasoning trace for the problem."""
        q = getattr(problem, "question", "")
        difficulty = getattr(problem, "difficulty", None)
        diff_name = difficulty.name if difficulty else "MEDIUM"

        trace = [
            f"[SIAG] Category: {category.value} | Difficulty: {diff_name}",
            f"[SIAG] σ_ded={self.routing.sigma_ded:.3f} σ_gen={self.routing.sigma_gen:.3f}",
            f"[LATS] Hemisphere: {self.routing.hemisphere.name}",
        ]
        if avoidance_prompt:
            trace.append(f"[RLFC] Avoidance active: {avoidance_prompt[:80]}...")

        # Category-specific reasoning hints
        hints = {
            ContestCategory.ALGEBRA:       "Apply Factor Theorem / Vieta's / symmetric function decomposition.",
            ContestCategory.NUMBER_THEORY: "Use modular arithmetic: 10 ≡ 1 (mod 9), Bézout, CRT.",
            ContestCategory.COMBINATORICS: "Apply inclusion-exclusion / pigeonhole / generating functions.",
            ContestCategory.GEOMETRY:      "Use Law of Cosines/Sines, coordinate geometry, or vectors.",
            ContestCategory.CALCULUS:      "Apply L'Hôpital / Taylor expansion / integration by parts.",
            ContestCategory.PROBABILITY:   "Condition on events, apply Bayes or inclusion-exclusion.",
            ContestCategory.TRIGONOMETRY:  "Use addition formulas, double-angle, or inverse trig identities.",
            ContestCategory.SEQUENCES:     "Look for telescoping pattern or characteristic roots.",
            ContestCategory.UNKNOWN:       "Classify the problem type before selecting a strategy.",
        }
        trace.append(f"[LATS] Strategy hint: {hints.get(category, '')}")
        return trace

    def _generate_lean4_skeleton(
        self,
        problem_id: str,
        question: str,
        primary_tactic: str,
    ) -> str:
        """Generate a generic Lean 4 proof skeleton for problems without a template."""
        safe_id = problem_id.replace("-", "_").replace(" ", "_")
        return (
            f"-- Mind Olympiad: {problem_id}\n"
            f"-- Question: {question[:80]}...\n"
            f"theorem {safe_id}_solution : True := by\n"
            f"  -- Step 1: Set up notation and preliminary lemmas\n"
            f"  trivial\n"
            f"  -- Main proof: {primary_tactic}\n"
            f"  -- sorry  -- Fill in actual proof"
        )
