# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""SymBrain v16 'Agora-Exhaustion' Cortex — Galois neurocognitive reasoning cortex.

Extends SymBrain v12 (PSLQ-Discovery) with two winning hypotheses from
the v16 autoresearch cycle:

H1 — Lemma-Decomposition Engine:
    Pre-decomposes a theorem into 3-5 named sub-lemma slots BEFORE
    generating sorry stubs. Each slot is typed (algebraic / analytic /
    existence / decidable / number-theory) and paired with a top-3 candidate
    Mathlib4 tactic list, dramatically shrinking the search space for L4 GPUs.

H3 — Cross-Region Inference Sharding (via DopamineRegulatedThreshold):
    The dopamine_level from v11 now dynamically adjusts the minimum
    confidence required before escalating from an L4 (cheap) shard to a
    Spot-A10G (medium) shard or a Serverless A100 (expensive) shard.
    A chain of successes keeps us on L4; failures ratchet up the tier,
    effectively bypassing per-region A100/H100 quota limits by staying on
    smaller GPUs whenever possible.

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import structlog

from agents.galois.symbrain.cortex_v4 import GaloisCortexConfig
from agents.galois.symbrain.cortex_v12 import SymBrainV12Cortex

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# GPU Tier definitions (H3: Cross-Region Inference Sharding)
# ---------------------------------------------------------------------------

# The system automatically selects the cheapest tier that satisfies the
# DopamineRegulatedThreshold. Only escalates when dopamine_level falls below
# a tier boundary, meaning repeated failures force us up the tier ladder.

GPU_TIERS = {
    "L4_SPOT": {
        "regions": ["us-central1", "us-east4", "europe-west4", "asia-southeast1"],
        "cost_per_hour": 0.54,
        "dopamine_threshold": 0.6,   # Active when dopamine >= 0.6 (normal operation)
    },
    "A10G_SPOT": {
        "regions": ["us-east1", "us-east5", "us-west1"],
        "cost_per_hour": 1.20,
        "dopamine_threshold": 0.35,  # Active when dopamine < 0.6 but >= 0.35
    },
    "A100_SERVERLESS": {
        "regions": ["us-central1"],  # Serverless — no quota per-region limit
        "cost_per_hour": 3.67,
        "dopamine_threshold": 0.0,   # Last resort — always available as serverless
    },
}


# ---------------------------------------------------------------------------
# Lemma-Decomposition Engine (H1)
# ---------------------------------------------------------------------------

@dataclass
class LemmaSlot:
    """A single named sub-lemma slot extracted from a theorem.

    Attributes:
        name: Lean 4 identifier for the sub-lemma (e.g. ``aux_bound``).
        claim_type: One of ``algebraic | analytic | existence | decidable |
            number_theory | generic``.
        mathematical_claim: Human-readable description of what must be proved.
        candidate_tactics: Top-3 Mathlib4 tactics most likely to close this slot.
        context_hint: Short snippet of surrounding code for context.
    """
    name: str = ""
    claim_type: str = "generic"
    mathematical_claim: str = ""
    candidate_tactics: list[str] = field(default_factory=list)
    context_hint: str = ""


@dataclass
class LemmaDecompositionPlan:
    """Output of the LemmaDecompositionEngine.

    Attributes:
        slots: 3–5 LemmaSlot objects ready for individual proof attacks.
        theorem_header: The parent theorem statement.
        estimated_gpu_tier: Which GPU tier the engine recommends for this plan.
    """
    slots: list[LemmaSlot] = field(default_factory=list)
    theorem_header: str = ""
    estimated_gpu_tier: str = "L4_SPOT"


# Keyword → claim_type mapping for fast structural classification
_CLAIM_TYPE_KEYWORDS: dict[str, list[str]] = {
    "algebraic":    ["ring", "group", "field", "module", "algebra", "polynomial", "ideal",
                     "norm_num", "comm", "assoc", "distrib"],
    "analytic":     ["continuous", "differentiable", "integral", "series", "limit",
                     "converge", "tendsto", "measure", "holomorphic", "harmonic"],
    "existence":    ["exists", "∃", "nonempty", "fintype", "obtain", "classical",
                     "choice", "surjective", "injective"],
    "decidable":    ["decide", "omega", "norm_num", "nat.", "int.", "finset", "finite",
                     "computable", "bool"],
    "number_theory": ["prime", "mod", "congruence", "divisib", "zeta", "euler_phi",
                      "coprime", "dirichlet", "quadratic"],
}

# Gap type → recommended Mathlib4 tactics (H5 Euclid Index, upgraded for v16)
_TACTIC_RECOMMENDATIONS: dict[str, list[str]] = {
    "algebraic":    ["ring", "field_simp; ring", "norm_cast; ring", "simp [mul_comm]",
                     "GroupHom.ext (fun x => _)"],
    "analytic":     ["exact tendsto_const_nhds", "filter_upwards", "continuity",
                     "apply MeasureTheory.integral_add (by measurability)",
                     "exact Real.HasDerivAt.integral_comp_sub_right"],
    "existence":    ["exact ⟨_, rfl⟩", "refine ⟨?_, ?_⟩", "exact ⟨Classical.choice h, rfl⟩",
                     "simp [Set.mem_range]", "exact Finset.mem_image.mpr ⟨_, _, rfl⟩"],
    "decidable":    ["decide", "omega", "norm_num", "simp [Nat.dvd_iff_mod_eq_zero]",
                     "exact Nat.decEq _ _"],
    "number_theory": ["exact Nat.Coprime.pow_dvd_of_pow_dvd", "simp [ZMod.val_natCast]",
                      "exact Nat.Prime.eq_one_or_self_of_dvd", "norm_num",
                      "exact Int.emod_emod_of_dvd"],
    "generic":      ["simp", "exact?", "apply?", "tauto", "aesop"],
}


class LemmaDecompositionEngine:
    """H1 core engine — decomposes a theorem into named sub-lemma slots.

    This engine operates purely on the textual structure of the Lean 4
    sketch without LLM calls, making it fast and deterministic. The LLM
    is invoked separately for each slot during the Archimedes exhaustion loop.
    """

    def decompose(
        self,
        theorem_header: str,
        lean4_sketch: str,
        domain: str,
        max_slots: int = 5,
    ) -> LemmaDecompositionPlan:
        """Decompose a theorem into named sub-lemma slots.

        Args:
            theorem_header: The Lean 4 ``theorem <name> : <type>`` line.
            lean4_sketch: Full sketch potentially containing ``sorry`` stubs.
            domain: Mathematical domain for tactic bias.
            max_slots: Maximum sub-lemma slots to produce (3–5).

        Returns:
            A :class:`LemmaDecompositionPlan` with typed, tactic-annotated slots.
        """
        slots: list[LemmaSlot] = []

        # Step 1: Find every `sorry` occurrence with context
        sorry_positions = [m.start() for m in re.finditer(r'\bsorry\b', lean4_sketch, re.IGNORECASE)]
        if not sorry_positions:
            return LemmaDecompositionPlan(
                slots=[],
                theorem_header=theorem_header,
                estimated_gpu_tier="L4_SPOT",
            )

        # Step 2: For each sorry (up to max_slots), create a named slot
        for idx, pos in enumerate(sorry_positions[:max_slots]):
            # Extract surrounding context (120 chars on each side)
            ctx_before = lean4_sketch[max(0, pos - 120): pos]
            ctx_after = lean4_sketch[pos + 5: pos + 125]
            context_hint = ctx_before.split("\n")[-1] + " sorry " + ctx_after.split("\n")[0]

            # Classify claim type from context keywords
            claim_type = self._classify_claim_type(ctx_before + ctx_after, domain)

            # Build a readable claim description from the `have` or `show` line
            mathematical_claim = self._extract_claim(ctx_before)

            slot = LemmaSlot(
                name=f"aux_lemma_{idx + 1}_{claim_type[:4]}",
                claim_type=claim_type,
                mathematical_claim=mathematical_claim or f"Sub-goal {idx + 1} ({claim_type})",
                candidate_tactics=_TACTIC_RECOMMENDATIONS.get(claim_type, _TACTIC_RECOMMENDATIONS["generic"])[:3],
                context_hint=context_hint[:200],
            )
            slots.append(slot)

        # Step 3: Estimate required GPU tier based on slot count and complexity
        gpu_tier = self._estimate_gpu_tier(slots, domain)

        plan = LemmaDecompositionPlan(
            slots=slots,
            theorem_header=theorem_header,
            estimated_gpu_tier=gpu_tier,
        )
        logger.info(
            "lemma_decomposition_plan_built",
            slot_count=len(slots),
            gpu_tier=gpu_tier,
            domain=domain,
        )
        return plan

    def _classify_claim_type(self, context: str, domain: str) -> str:
        """Classify a sorry gap by the mathematical type of its claim."""
        context_lower = context.lower()

        # Domain bias: give number_theory and analytic keywords domain priority
        if domain in ("number_theory", "coding_theory"):
            for kw in _CLAIM_TYPE_KEYWORDS["number_theory"]:
                if kw in context_lower:
                    return "number_theory"
        if domain in ("special_functions", "stat_mechanics", "mathematical_physics"):
            for kw in _CLAIM_TYPE_KEYWORDS["analytic"]:
                if kw in context_lower:
                    return "analytic"

        # Generic keyword scan
        for claim_type, keywords in _CLAIM_TYPE_KEYWORDS.items():
            for kw in keywords:
                if kw in context_lower:
                    return claim_type

        return "generic"

    def _extract_claim(self, context_before: str) -> str:
        """Extract the claim description from a `have`, `show`, or `calc` line."""
        for line in reversed(context_before.strip().splitlines()):
            line = line.strip()
            if any(line.startswith(kw) for kw in ("have ", "show ", "calc ", "suffices ")):
                return line[:120]
        return ""

    def _estimate_gpu_tier(self, slots: list[LemmaSlot], domain: str) -> str:
        """Recommend the cheapest GPU tier sufficient for this decomposition plan."""
        # Many slots or hard domains → need more compute
        hard_domains = {"number_theory", "mathematical_physics", "spectral_theory"}
        if len(slots) >= 4 or domain in hard_domains:
            return "A10G_SPOT"
        return "L4_SPOT"

    def format_for_prompt(self, plan: LemmaDecompositionPlan) -> str:
        """Format the decomposition plan as a prompt injection for Galois."""
        if not plan.slots:
            return ""
        lines = [
            "## Lemma Decomposition Plan (SymBrain v16 — H1)",
            f"Theorem: {plan.theorem_header[:120]}",
            f"Sub-lemma slots ({len(plan.slots)} identified, GPU tier: {plan.estimated_gpu_tier}):",
        ]
        for slot in plan.slots:
            lines.append(
                f"  [{slot.name}] Type: {slot.claim_type} | "
                f"Claim: {slot.mathematical_claim[:80]} | "
                f"Tactics: {', '.join(slot.candidate_tactics)}"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dopamine-Regulated GPU Tier Selector (H3)
# ---------------------------------------------------------------------------

class DopamineRegulatedThreshold:
    """H3 — Dynamically selects the cheapest viable GPU tier.

    The ``dopamine_level`` (inherited from SymBrainV11Cortex) tracks recent
    success rate. High dopamine = recent successes → stay on cheap L4.
    Low dopamine = repeated failures → escalate to A10G then A100.

    This mechanism bypasses per-region H100/A100 quota limits by exhausting
    cheap tiers first and only escalating on genuine difficulty signals.
    """

    def __init__(self, initial_dopamine: float = 1.0) -> None:
        self.dopamine_level = initial_dopamine
        self.total_escalations = 0

    def select_gpu_tier(self) -> tuple[str, dict[str, Any]]:
        """Select the cheapest GPU tier matching current dopamine level.

        Returns:
            Tuple of (tier_name, tier_config_dict).
        """
        for tier_name, config in GPU_TIERS.items():
            if self.dopamine_level >= config["dopamine_threshold"]:
                logger.info(
                    "gpu_tier_selected",
                    tier=tier_name,
                    dopamine=round(self.dopamine_level, 3),
                )
                return tier_name, config
        # Fallback — should never reach here given A100_SERVERLESS threshold=0.0
        return "A100_SERVERLESS", GPU_TIERS["A100_SERVERLESS"]

    def on_success(self, reward: float = 0.1) -> None:
        """Update dopamine on successful proof step (gap closed)."""
        self.dopamine_level = min(1.0, self.dopamine_level + reward)
        logger.debug("dopamine_increased", new_level=round(self.dopamine_level, 3))

    def on_failure(self, penalty: float = 0.15) -> None:
        """Update dopamine on failed proof step (gap not closed)."""
        prev = self.dopamine_level
        self.dopamine_level = max(0.0, self.dopamine_level - penalty)
        # Detect tier change
        old_tier, _ = self.select_gpu_tier()
        if old_tier != self._tier_at(prev):
            self.total_escalations += 1
            logger.info(
                "gpu_tier_escalation",
                from_tier=self._tier_at(prev),
                to_tier=old_tier,
                escalations=self.total_escalations,
            )
        logger.debug("dopamine_decreased", new_level=round(self.dopamine_level, 3))

    def _tier_at(self, dopamine: float) -> str:
        """Compute tier name for a given dopamine level."""
        for tier_name, config in GPU_TIERS.items():
            if dopamine >= config["dopamine_threshold"]:
                return tier_name
        return "A100_SERVERLESS"

    def summary(self) -> dict[str, Any]:
        """Return a summary dict for telemetry."""
        tier_name, tier_cfg = self.select_gpu_tier()
        return {
            "dopamine_level": round(self.dopamine_level, 4),
            "selected_tier": tier_name,
            "regions": tier_cfg["regions"],
            "cost_per_hour": tier_cfg["cost_per_hour"],
            "total_escalations": self.total_escalations,
        }


# ---------------------------------------------------------------------------
# SymBrain v16 Cortex
# ---------------------------------------------------------------------------

class SymBrainV16Cortex(SymBrainV12Cortex):
    """Agora-Exhaustion cortex — SymBrain v16.

    Adds to v12 (PSLQ-Discovery):
    - :class:`LemmaDecompositionEngine` (H1) for theorem pre-decomposition.
    - :class:`DopamineRegulatedThreshold` (H3) for GPU tier management.
    - Region list exposed as ``active_regions`` for the ShardRouter.
    """

    def __init__(self, base_config: GaloisCortexConfig) -> None:
        super().__init__(base_config)
        self.symbrain_version = "v16-AgoraExhaustion"

        # H1: Lemma decomposition engine
        self.lemma_engine = LemmaDecompositionEngine()

        # H3: Dopamine-regulated GPU tier selector
        # Seeds from v11 dopamine_level if already tuned
        self.gpu_selector = DopamineRegulatedThreshold(
            initial_dopamine=getattr(self, "dopamine_level", 1.0)
        )

        # Expose active regions from the selected tier
        self._refresh_active_regions()

    def _refresh_active_regions(self) -> None:
        """Sync active_regions from the current GPU tier selection."""
        _, tier_cfg = self.gpu_selector.select_gpu_tier()
        self.active_regions: list[str] = tier_cfg["regions"]

    def decompose_theorem(
        self,
        theorem_header: str,
        lean4_sketch: str,
        domain: str,
    ) -> LemmaDecompositionPlan:
        """H1: Decompose a theorem into sub-lemma slots."""
        plan = self.lemma_engine.decompose(
            theorem_header=theorem_header,
            lean4_sketch=lean4_sketch,
            domain=domain,
        )
        return plan

    def record_gap_resolved(self) -> None:
        """Signal H3 that a sorry gap was closed → dopamine up → stay on L4."""
        # v11 hippocampal replay
        self.record_to_hippocampal_replay("gap_resolved")
        # v11 RPE (reward = 1.0 per closed gap)
        self.calculate_reward_prediction_error(actual_reward=1.0, predicted_reward=0.7)
        # v16 GPU selector
        self.gpu_selector.on_success(reward=0.1)
        self._refresh_active_regions()

    def record_gap_intractable(self) -> None:
        """Signal H3 that a gap was not resolved → dopamine down → possible escalation."""
        self.record_to_hippocampal_replay("gap_intractable")
        self.calculate_reward_prediction_error(actual_reward=0.0, predicted_reward=0.7)
        self.gpu_selector.on_failure(penalty=0.15)
        self._refresh_active_regions()

    def get_gpu_tier_summary(self) -> dict[str, Any]:
        """Return current GPU tier summary for Turing's FinOps reporting."""
        return self.gpu_selector.summary()
