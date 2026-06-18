# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""SymBrain v4 Cortex Configuration for Galois.

This module defines the innovation-biased Prefrontal Cortex (PFC) router
configuration that makes Galois unique among Agora agents. While Galileo
and Euler use balanced or deduction-heavy configurations, Galois's cortex
rewards creative mathematical exploration.

The cortex implements the SymBrain v4 3-stage PFC pipeline with modified
routing tensors:
  - σ_gen biased to 0.75 (vs. default 0.50)
  - σ_ded floor at 0.15 (vs. default 0.30)
  - σ_mcts multiplied by 1.5x for deeper creative search
  - Innovation reward: novelty bonus for semantically distant conjectures

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class HemisphereMode(Enum):
    """Active hemisphere dominance mode."""

    CREATIVE = auto()        # Right hemisphere dominant (Maieutic)
    FORMAL = auto()          # Left hemisphere dominant (Elenchus)
    BALANCED = auto()        # Equal allocation
    ESCALATED_FORMAL = auto()  # Emergency snap to formal (type error recovery)


class ConjectureConfidence(Enum):
    """Confidence classification for mathematical conjectures."""

    HIGH = "proof_sketch_passes"      # Lean 4 type-checks
    MEDIUM = "plausible_unverified"   # Heuristically consistent
    LOW = "speculative_intuition"     # Pure creative spark


# ---------------------------------------------------------------------------
# Routing Tensor
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class GaloisRoutingTensor:
    """Innovation-biased routing tensor for the Galois PFC.

    Compared to the standard SymBrain v4 routing tensor, Galois uses:
      - Higher σ_gen (generative/creative allocation)
      - Lower σ_ded floor (minimum deductive allocation)
      - Higher σ_mcts (deeper Monte-Carlo search)
      - Novelty bonus that rewards semantic distance from known theorems

    Invariants:
        σ_ded + σ_gen = 1.0
        σ_ded ≥ DEDUCTIVE_FLOOR (0.15)
        σ_mcts ≥ 1.0

    Attributes:
        sigma_ded: Deductive (formal) hemisphere allocation in [0.15, 0.85].
        sigma_gen: Generative (creative) hemisphere allocation.
        sigma_mcts: MCTS tree search multiplier.
        novelty_bonus: Reward signal for creative distance from known results.
        hemisphere: Current dominance mode.
    """

    sigma_ded: float = 0.25
    sigma_gen: float = 0.75
    sigma_mcts: float = 6.0
    novelty_bonus: float = 0.0
    hemisphere: HemisphereMode = HemisphereMode.CREATIVE

    # Galois-specific: lower floor allows more creative exploration
    DEDUCTIVE_FLOOR: float = field(default=0.15, init=False, repr=False)
    DEDUCTIVE_CEILING: float = field(default=0.85, init=False, repr=False)
    ESCALATION_DELTA: float = field(default=0.30, init=False, repr=False)

    def __post_init__(self) -> None:
        self._enforce_invariants()

    def _enforce_invariants(self) -> None:
        """Enforce routing tensor invariants."""
        self.sigma_ded = max(self.DEDUCTIVE_FLOOR,
                            min(self.DEDUCTIVE_CEILING, self.sigma_ded))
        self.sigma_gen = 1.0 - self.sigma_ded
        self.sigma_mcts = max(1.0, self.sigma_mcts)

        if self.sigma_gen > self.sigma_ded:
            self.hemisphere = HemisphereMode.CREATIVE
        elif self.sigma_ded > self.sigma_gen:
            self.hemisphere = HemisphereMode.FORMAL
        else:
            self.hemisphere = HemisphereMode.BALANCED

    def escalate_to_formal(self) -> None:
        """Emergency escalation: snap to formal mode on type error.

        Called when Lean 4 type-checking fails or DeepProbLog detects
        a contradiction. Increases σ_ded by ESCALATION_DELTA (0.30),
        capped at DEDUCTIVE_CEILING.
        """
        self.sigma_ded = min(
            self.DEDUCTIVE_CEILING,
            self.sigma_ded + self.ESCALATION_DELTA,
        )
        self.sigma_gen = 1.0 - self.sigma_ded
        self.hemisphere = HemisphereMode.ESCALATED_FORMAL
        logger.info(
            "cortex_escalated_to_formal",
            sigma_ded=self.sigma_ded,
            sigma_gen=self.sigma_gen,
        )

    def relax_to_creative(self, decay_rate: float = 0.10) -> None:
        """Gradually relax back toward creative mode after successful proof.

        Called when a conjecture passes formal verification. Reduces σ_ded
        by ``decay_rate`` to re-enable creative exploration.

        Args:
            decay_rate: Amount to reduce σ_ded (default 0.10).
        """
        self.sigma_ded = max(
            self.DEDUCTIVE_FLOOR,
            self.sigma_ded - decay_rate,
        )
        self.sigma_gen = 1.0 - self.sigma_ded
        self._enforce_invariants()
        logger.info(
            "cortex_relaxed_to_creative",
            sigma_ded=self.sigma_ded,
            sigma_gen=self.sigma_gen,
        )

    def compute_novelty_bonus(
        self,
        conjecture_embedding: list[float],
        known_theorem_embeddings: list[list[float]],
    ) -> float:
        """Compute innovation reward based on semantic distance.

        The novelty bonus is 1.5 × max cosine distance from known theorems.
        This biases the PFC to reward conjectures that are far from
        established results — encouraging creative leaps.

        Args:
            conjecture_embedding: Embedding vector of the conjecture.
            known_theorem_embeddings: List of known theorem embeddings.

        Returns:
            Novelty bonus in [0, 1.5].
        """
        if not known_theorem_embeddings or not conjecture_embedding:
            self.novelty_bonus = 0.75  # Default moderate novelty
            return self.novelty_bonus

        max_distance = 0.0
        conj_norm = math.sqrt(sum(x * x for x in conjecture_embedding))
        if conj_norm < 1e-12:
            self.novelty_bonus = 0.0
            return 0.0

        for known_emb in known_theorem_embeddings:
            known_norm = math.sqrt(sum(x * x for x in known_emb))
            if known_norm < 1e-12:
                continue

            dot_product = sum(a * b for a, b in zip(conjecture_embedding, known_emb))
            cosine_sim = dot_product / (conj_norm * known_norm)
            distance = 1.0 - cosine_sim
            max_distance = max(max_distance, distance)

        self.novelty_bonus = min(1.5, 1.5 * max(0.0, max_distance))
        return self.novelty_bonus


# ---------------------------------------------------------------------------
# Complexity Classifier (Galois variant)
# ---------------------------------------------------------------------------

# Galois uses extended STEM keywords focused on pure mathematics
GALOIS_MATH_KEYWORDS: set[str] = {
    "group", "ring", "field", "galois", "symmetry", "automorphism",
    "homomorphism", "isomorphism", "permutation", "polynomial",
    "algebraic", "topology", "manifold", "cohomology", "homotopy",
    "category", "functor", "monad", "sheaf", "scheme",
    "conjecture", "theorem", "lemma", "proof", "axiom",
    "prime", "ideal", "module", "vector space", "eigenvalue",
    "differential", "integral", "series", "convergence", "limit",
    "combinatorics", "graph", "lattice", "order", "partition",
    "probability", "measure", "random", "stochastic", "martingale",
    "number theory", "arithmetic", "modular", "residue", "quadratic",
    "lie", "algebra", "representation", "character", "weight",
}


@dataclass(slots=True)
class GaloisComplexityClassifier:
    """3-stage complexity classifier tuned for mathematical creativity.

    Stage 1: Lexical scan for mathematical domain keywords
    Stage 2: Semantic complexity estimation (LaTeX density, nesting, variables)
    Stage 3: Dynamic MCTS estimation with creativity-boosted sigmoid

    The Galois variant uses a shallower sigmoid midpoint (0.35 vs 0.45)
    to trigger deep creative search earlier on mathematical problems.
    """

    # Stage 3: Galois sigmoid parameters (earlier trigger for deep search)
    sigmoid_midpoint: float = 0.35  # vs. standard 0.45
    sigmoid_steepness: float = 6.0
    mcts_base: float = 1.0
    mcts_range: float = 7.0  # Mult ∈ [1.0, 8.0]

    def classify(self, query: str) -> tuple[float, float]:
        """Classify query complexity and compute MCTS multiplier.

        Args:
            query: The mathematical question or conjecture prompt.

        Returns:
            Tuple of (complexity_score ∈ [0,1], mcts_multiplier ∈ [1,8]).
        """
        # Stage 1: Lexical STEM scan
        query_lower = query.lower()
        keyword_hits = sum(1 for kw in GALOIS_MATH_KEYWORDS if kw in query_lower)
        lexical_score = min(1.0, keyword_hits / 8.0)

        # Stage 2: Semantic complexity features
        latex_density = query.count("$") / max(1, len(query)) * 50
        nesting_depth = max(query.count("("), query.count("{")) / max(1, len(query)) * 20
        variable_count = sum(1 for c in query if c.isalpha() and c.islower()) / max(1, len(query)) * 5
        proof_markers = sum(1 for marker in ("prove", "show", "demonstrate", "verify", "∀", "∃", "→", "⊢")
                           if marker in query_lower)

        semantic_score = min(1.0, (
            0.30 * latex_density +
            0.20 * nesting_depth +
            0.15 * variable_count +
            0.35 * min(1.0, proof_markers / 3.0)
        ))

        # Combined complexity
        complexity = 0.45 * lexical_score + 0.55 * semantic_score
        complexity = max(0.0, min(1.0, complexity))

        # Stage 3: Dynamic MCTS with creativity-boosted sigmoid
        exponent = -self.sigmoid_steepness * (complexity - self.sigmoid_midpoint)
        mcts_mult = self.mcts_base + self.mcts_range / (1.0 + math.exp(exponent))

        return complexity, mcts_mult


# ---------------------------------------------------------------------------
# Cortex Configuration
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class GaloisCortexConfig:
    """Complete SymBrain v4 cortex configuration for Galois.

    Bundles the routing tensor, complexity classifier, and operational
    parameters specific to the creative mathematician agent.

    Attributes:
        routing: The innovation-biased routing tensor.
        classifier: Complexity classifier with Galois-tuned sigmoid.
        symbrain_version: Current SymBrain version (upgradeable).
        cloud_tier: GCP deployment tier.
        model_quant: Quantization strategy.
        vram_gb: VRAM budget in gigabytes.
        context_length: Maximum context length.
        temperature: LLM sampling temperature (high for creativity).
        warmup_enabled: Whether serverless warm-up is active.
        conjecture_history: Track of conjectures for self-improvement.
    """

    routing: GaloisRoutingTensor = field(default_factory=GaloisRoutingTensor)
    classifier: GaloisComplexityClassifier = field(default_factory=GaloisComplexityClassifier)

    # SymBrain version management
    symbrain_version: str = "v4"
    upgrade_path: list[str] = field(default_factory=lambda: ["v5", "v6"])

    # Cloud deployment
    cloud_tier: str = "Cloud-32B"
    model_quant: str = "INT8"
    vram_gb: int = 40
    context_length: int = 65_536
    temperature: float = 0.9  # High for creative exploration
    warmup_enabled: bool = True

    # Self-improvement tracking
    conjecture_history: list[dict[str, Any]] = field(default_factory=list)
    success_rate: float = 0.0
    total_conjectures: int = 0
    verified_conjectures: int = 0

    def record_conjecture(
        self,
        conjecture: str,
        confidence: ConjectureConfidence,
        verified: bool = False,
    ) -> None:
        """Record a conjecture for self-improvement tracking.

        Args:
            conjecture: The mathematical conjecture text.
            confidence: Confidence classification.
            verified: Whether formal verification succeeded.
        """
        self.total_conjectures += 1
        if verified:
            self.verified_conjectures += 1

        self.conjecture_history.append({
            "conjecture": conjecture[:200],
            "confidence": confidence.value,
            "verified": verified,
            "sigma_ded": self.routing.sigma_ded,
            "sigma_gen": self.routing.sigma_gen,
        })

        # Update success rate
        if self.total_conjectures > 0:
            self.success_rate = self.verified_conjectures / self.total_conjectures

        # Adaptive σ tuning based on success rate
        if self.total_conjectures >= 5:
            if self.success_rate < 0.30:
                # Too many failures — increase formal verification
                self.routing.sigma_ded = min(0.50, self.routing.sigma_ded + 0.05)
                self.routing.sigma_gen = 1.0 - self.routing.sigma_ded
                logger.info("cortex_adapted_more_formal", success_rate=self.success_rate)
            elif self.success_rate > 0.80:
                # Very high success — can afford more creativity
                self.routing.sigma_ded = max(0.15, self.routing.sigma_ded - 0.05)
                self.routing.sigma_gen = 1.0 - self.routing.sigma_ded
                logger.info("cortex_adapted_more_creative", success_rate=self.success_rate)

    def propose_v5_upgrade(self) -> dict[str, Any]:
        """Generate a SymBrain v5 upgrade proposal based on operational data.

        Returns:
            Dict describing proposed v5 improvements for Galois.
        """
        return {
            "agent": "galois",
            "current_version": self.symbrain_version,
            "target_version": "v5",
            "proposals": [
                {
                    "name": "Creative LoRA Adapters",
                    "description": (
                        "Low-rank fine-tuning biased toward conjecture generation. "
                        "Rank r=16 adapters trained on Mathlib theorem statements "
                        "to improve algebraic intuition."
                    ),
                    "priority": "HIGH",
                },
                {
                    "name": "Proof-Guided MCTS Pruning",
                    "description": (
                        "Use Lean 4 type-checking as early MCTS pruning signal. "
                        f"Current success rate: {self.success_rate:.1%}. "
                        f"Total conjectures: {self.total_conjectures}."
                    ),
                    "priority": "HIGH",
                },
                {
                    "name": "Dynamic σ_gen Annealing",
                    "description": (
                        "Gradually reduce creative exploration as confidence "
                        "in a conjecture grows. Anneal σ_gen from 0.75 → 0.40 "
                        "over verification iterations."
                    ),
                    "priority": "MEDIUM",
                },
                {
                    "name": "Edge LoRA for Proof Sketching",
                    "description": (
                        "Deploy lightweight proof-sketch LoRA on Edge-7B tier "
                        "for rapid type-checking feedback (< 100ms latency). "
                        "Use Cloud-32B only for deep creative search."
                    ),
                    "priority": "MEDIUM",
                },
            ],
            "metrics": {
                "total_conjectures": self.total_conjectures,
                "verified_conjectures": self.verified_conjectures,
                "success_rate": self.success_rate,
                "avg_sigma_ded": (
                    sum(c["sigma_ded"] for c in self.conjecture_history) /
                    max(1, len(self.conjecture_history))
                ),
            },
        }
