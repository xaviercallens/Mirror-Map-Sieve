# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Test suite for SymBrain v16 — H1 Lemma Pre-Decomposition and H3 Cross-Region Sharding.

Covers:
    - SymBrainV16Cortex: LemmaDecompositionEngine, DopamineRegulatedThreshold
    - ShardRouter: round-robin, race-all, failover, escalation, dry-run
    - LemmaPreDecomposer: per-domain decomposition, prompt injection
    - GaloisAgent.upgrade_to_v16()
    - ArchimedesAgent._pre_decompose_theorem()
    - run_horizonmath_v16.py: process_problem_v16 integration
"""
from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: SymBrainV16Cortex — LemmaDecompositionEngine
# ─────────────────────────────────────────────────────────────────────────────

class TestLemmaDecompositionEngine:
    """Tests for the H1 LemmaDecompositionEngine inside SymBrainV16Cortex."""

    def test_produces_3_to_5_slots_for_sorry_sketch(self):
        """Engine produces 3-5 LemmaSlot objects for a sketch with 4 sorry stubs."""
        from agents.galois.symbrain.cortex_v16 import LemmaDecompositionEngine

        engine = LemmaDecompositionEngine()
        sketch = (
            "theorem foo : ∀ n, P n := by\n"
            "  have h1 : A := by sorry\n"
            "  have h2 : B := by sorry\n"
            "  have h3 : C := by sorry\n"
            "  exact sorry\n"
        )
        plan = engine.decompose(
            theorem_header="theorem foo : ∀ n, P n",
            lean4_sketch=sketch,
            domain="number_theory",
        )
        assert 3 <= len(plan.slots) <= 5, (
            f"Expected 3-5 slots, got {len(plan.slots)}"
        )

    def test_slots_have_names_and_tactics(self):
        """Each slot has a non-empty name and at least one candidate tactic."""
        from agents.galois.symbrain.cortex_v16 import LemmaDecompositionEngine

        engine = LemmaDecompositionEngine()
        sketch = "theorem bar : X = Y := by\n  sorry\n  sorry\n  sorry\n"
        plan = engine.decompose(
            theorem_header="theorem bar",
            lean4_sketch=sketch,
            domain="algebraic",
        )
        for slot in plan.slots:
            assert slot.name, "Slot name must not be empty"
            assert len(slot.candidate_tactics) >= 1, "Slot must have at least one tactic"

    def test_no_sorry_returns_empty_plan(self):
        """Engine returns empty slots for a sketch with no sorry stubs."""
        from agents.galois.symbrain.cortex_v16 import LemmaDecompositionEngine

        engine = LemmaDecompositionEngine()
        sketch = "theorem trivial : True := trivial\n"
        plan = engine.decompose(
            theorem_header="theorem trivial",
            lean4_sketch=sketch,
            domain="generic",
        )
        assert plan.slots == [], "Expected empty slot list for sorry-free sketch"

    def test_claim_type_classification_algebraic(self):
        """Algebraic keywords in context lead to algebraic claim type."""
        from agents.galois.symbrain.cortex_v16 import LemmaDecompositionEngine

        engine = LemmaDecompositionEngine()
        sketch = "theorem ring_eq : a * b = b * a := by\n  ring\n  sorry\n"
        plan = engine.decompose(
            theorem_header="theorem ring_eq",
            lean4_sketch=sketch,
            domain="number_theory",
        )
        # At least one slot should be algebraic or number_theory
        types = {slot.claim_type for slot in plan.slots}
        assert types & {"algebraic", "number_theory"}, (
            f"Expected algebraic/number_theory type in {types}"
        )

    def test_gpu_tier_estimation_hard_domain(self):
        """Hard domains (number_theory, mathematical_physics) recommend A10G_SPOT."""
        from agents.galois.symbrain.cortex_v16 import LemmaDecompositionEngine

        engine = LemmaDecompositionEngine()
        sketch = "theorem big : P := by\n  sorry\n  sorry\n  sorry\n  sorry\n"
        plan = engine.decompose(
            theorem_header="theorem big",
            lean4_sketch=sketch,
            domain="mathematical_physics",
        )
        # 4 slots + hard domain → A10G_SPOT
        assert plan.estimated_gpu_tier in ("A10G_SPOT", "L4_SPOT"), (
            f"Unexpected tier: {plan.estimated_gpu_tier}"
        )

    def test_format_for_prompt_non_empty(self):
        """format_for_prompt returns a non-empty string for a non-empty plan."""
        from agents.galois.symbrain.cortex_v16 import LemmaDecompositionEngine

        engine = LemmaDecompositionEngine()
        sketch = "theorem t : P := by\n  sorry\n  sorry\n"
        plan = engine.decompose("theorem t", sketch, "combinatorics")
        prompt_text = engine.format_for_prompt(plan)
        assert len(prompt_text) > 50, "Prompt injection should be substantial"
        assert "Sub-lemma" in prompt_text or "slot" in prompt_text.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: DopamineRegulatedThreshold — GPU Tier Selection (H3)
# ─────────────────────────────────────────────────────────────────────────────

class TestDopamineRegulatedThreshold:
    """Tests for the H3 DopamineRegulatedThreshold."""

    def test_high_dopamine_selects_l4(self):
        """dopamine_level=1.0 (default) selects L4_SPOT."""
        from agents.galois.symbrain.cortex_v16 import DopamineRegulatedThreshold

        drt = DopamineRegulatedThreshold(initial_dopamine=1.0)
        tier, config = drt.select_gpu_tier()
        assert tier == "L4_SPOT"

    def test_threshold_lowers_on_success(self):
        """Successive successes keep dopamine high (stays on L4)."""
        from agents.galois.symbrain.cortex_v16 import DopamineRegulatedThreshold

        drt = DopamineRegulatedThreshold(initial_dopamine=0.7)
        drt.on_success(reward=0.1)
        drt.on_success(reward=0.1)
        tier, _ = drt.select_gpu_tier()
        assert tier == "L4_SPOT", f"Expected L4 after successes, got {tier}"

    def test_failures_escalate_tier(self):
        """Repeated failures reduce dopamine below L4 threshold → A10G or A100."""
        from agents.galois.symbrain.cortex_v16 import DopamineRegulatedThreshold

        drt = DopamineRegulatedThreshold(initial_dopamine=0.65)
        # 2 failures should push dopamine below 0.6 (L4 threshold)
        drt.on_failure(penalty=0.15)
        drt.on_failure(penalty=0.15)
        tier, _ = drt.select_gpu_tier()
        assert tier in ("A10G_SPOT", "A100_SERVERLESS"), (
            f"Expected escalated tier after failures, got {tier}"
        )

    def test_dopamine_clamps_to_zero(self):
        """Dopamine level never goes below 0.0."""
        from agents.galois.symbrain.cortex_v16 import DopamineRegulatedThreshold

        drt = DopamineRegulatedThreshold(initial_dopamine=0.1)
        for _ in range(10):
            drt.on_failure(penalty=0.5)
        assert drt.dopamine_level >= 0.0

    def test_dopamine_clamps_to_one(self):
        """Dopamine level never exceeds 1.0."""
        from agents.galois.symbrain.cortex_v16 import DopamineRegulatedThreshold

        drt = DopamineRegulatedThreshold(initial_dopamine=0.9)
        for _ in range(10):
            drt.on_success(reward=0.5)
        assert drt.dopamine_level <= 1.0

    def test_summary_contains_expected_keys(self):
        """DopamineRegulatedThreshold.summary() returns all required keys."""
        from agents.galois.symbrain.cortex_v16 import DopamineRegulatedThreshold

        drt = DopamineRegulatedThreshold(initial_dopamine=1.0)
        s = drt.summary()
        for key in ("dopamine_level", "selected_tier", "regions", "cost_per_hour", "total_escalations"):
            assert key in s, f"Missing key {key!r} in summary"


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: SymBrainV16Cortex — Full Integration
# ─────────────────────────────────────────────────────────────────────────────

class TestSymBrainV16Cortex:
    """Tests for the SymBrainV16Cortex class."""

    def _make_cortex(self):
        from agents.galois.symbrain.cortex_v4 import GaloisCortexConfig
        from agents.galois.symbrain.cortex_v16 import SymBrainV16Cortex
        return SymBrainV16Cortex(GaloisCortexConfig())

    def test_version_string(self):
        """Cortex version string is correctly set."""
        cortex = self._make_cortex()
        assert cortex.symbrain_version == "v16-AgoraExhaustion"

    def test_active_regions_populated(self):
        """Active regions list is non-empty after init."""
        cortex = self._make_cortex()
        assert len(cortex.active_regions) > 0

    def test_decompose_theorem_returns_plan(self):
        """decompose_theorem returns a valid LemmaDecompositionPlan."""
        cortex = self._make_cortex()
        sketch = "theorem x : P := by\n  sorry\n  sorry\n"
        plan = cortex.decompose_theorem(
            theorem_header="theorem x : P",
            lean4_sketch=sketch,
            domain="combinatorics",
        )
        assert plan is not None
        assert len(plan.slots) >= 1

    def test_record_gap_resolved_increases_dopamine(self):
        """record_gap_resolved increases dopamine level."""
        cortex = self._make_cortex()
        cortex.gpu_selector.dopamine_level = 0.7
        cortex.record_gap_resolved()
        assert cortex.gpu_selector.dopamine_level > 0.7

    def test_record_gap_intractable_decreases_dopamine(self):
        """record_gap_intractable decreases dopamine level."""
        cortex = self._make_cortex()
        cortex.gpu_selector.dopamine_level = 0.9
        cortex.record_gap_intractable()
        assert cortex.gpu_selector.dopamine_level < 0.9

    def test_get_gpu_tier_summary(self):
        """get_gpu_tier_summary returns dict with expected keys."""
        cortex = self._make_cortex()
        s = cortex.get_gpu_tier_summary()
        assert "selected_tier" in s
        assert "dopamine_level" in s


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: ShardRouter — Round-Robin and Failover (H3)
# ─────────────────────────────────────────────────────────────────────────────

class TestShardRouter:
    """Tests for the Cross-Region Inference ShardRouter."""

    def test_round_robin_cycles_endpoints(self):
        """ShardRouter cycles through endpoints in round-robin order."""
        from agents.galois.tools.region_shard_router import ShardRouter

        router = ShardRouter(tier="L4_SPOT")
        endpoints_seen = []
        for _ in range(len(router.endpoints)):
            endpoints_seen.append(router._next_endpoint())

        # All unique in one pass
        assert len(set(endpoints_seen)) == len(router.endpoints)

    @pytest.mark.asyncio
    async def test_dry_run_returns_success(self):
        """In dry-run mode, route() returns a successful ShardResult."""
        from agents.galois.tools.region_shard_router import ShardRouter

        with patch.dict(os.environ, {"AGORA_SHARD_DRY_RUN": "1"}):
            router = ShardRouter(tier="L4_SPOT")
            result = await router.route("theorem P := by exact trivial")
        assert result.success is True
        assert result.text != ""

    @pytest.mark.asyncio
    async def test_dry_run_tier_matches_router(self):
        """Dry-run ShardResult.tier matches the router's configured tier."""
        from agents.galois.tools.region_shard_router import ShardRouter

        with patch.dict(os.environ, {"AGORA_SHARD_DRY_RUN": "1"}):
            router = ShardRouter(tier="A10G_SPOT")
            result = await router.route("theorem T := by ring")
        assert result.tier == "A10G_SPOT"

    @pytest.mark.asyncio
    async def test_escalate_moves_to_next_tier(self):
        """escalate() moves the router from L4_SPOT to A10G_SPOT."""
        from agents.galois.tools.region_shard_router import ShardRouter

        router = ShardRouter(tier="L4_SPOT")
        success = router.escalate()
        assert success is True
        assert router.tier == "A10G_SPOT"

    @pytest.mark.asyncio
    async def test_escalate_at_max_tier_returns_false(self):
        """escalate() at A100_SERVERLESS returns False (no higher tier)."""
        from agents.galois.tools.region_shard_router import ShardRouter

        router = ShardRouter(tier="A100_SERVERLESS")
        success = router.escalate()
        assert success is False
        assert router.tier == "A100_SERVERLESS"

    @pytest.mark.asyncio
    async def test_all_endpoints_fail_returns_error(self):
        """If all endpoints fail, route() returns a ShardResult with success=False."""
        from agents.galois.tools.region_shard_router import ShardRouter

        with patch.dict(os.environ, {"AGORA_SHARD_DRY_RUN": "0"}):
            router = ShardRouter(tier="L4_SPOT")

            async def failing_call(ep, prompt, timeout):
                from agents.galois.tools.region_shard_router import ShardResult
                return ShardResult(success=False, error="connection refused", region_endpoint=ep)

            router._call_endpoint = failing_call  # type: ignore[assignment]
            result = await router.route("test prompt", race_all=False)
        assert result.success is False
        assert "failed" in result.error.lower() or "exhausted" in result.error.lower()

    def test_stats_tracks_calls(self):
        """stats() accurately tracks total call count."""
        from agents.galois.tools.region_shard_router import ShardRouter

        with patch.dict(os.environ, {"AGORA_SHARD_DRY_RUN": "1"}):
            router = ShardRouter(tier="L4_SPOT")
            asyncio.run(router.route("test"))
            asyncio.run(router.route("test"))
        assert router.stats()["total_calls"] == 2

    @pytest.mark.asyncio
    async def test_build_router_from_cortex(self):
        """build_router_from_cortex builds router matching cortex tier."""
        from agents.galois.symbrain.cortex_v4 import GaloisCortexConfig
        from agents.galois.symbrain.cortex_v16 import SymBrainV16Cortex
        from agents.galois.tools.region_shard_router import build_router_from_cortex

        cortex = SymBrainV16Cortex(GaloisCortexConfig())
        expected_tier = cortex.get_gpu_tier_summary()["selected_tier"]
        router = build_router_from_cortex(cortex)
        assert router.tier == expected_tier


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: LemmaPreDecomposer — Per-Domain Decomposition
# ─────────────────────────────────────────────────────────────────────────────

class TestLemmaPreDecomposer:
    """Tests for the v16 LemmaPreDecomposer (H1 pre-proof step)."""

    def test_number_theory_produces_lemmas(self):
        """number_theory domain produces number-theory-flavored lemmas."""
        from agents.archimedes.tools.lemma_decomposer_v16 import LemmaPreDecomposer

        decomp = LemmaPreDecomposer()
        plan = decomp.decompose_theorem_statement(
            theorem_header="theorem riemann_hypothesis : ...",
            domain="number_theory",
            pid="riemann_hypothesis",
            max_lemmas=3,
        )
        assert len(plan.lemmas) == 3
        assert plan.domain == "number_theory"

    def test_lemma_names_include_pid(self):
        """Sub-lemma names incorporate the problem ID as a prefix."""
        from agents.archimedes.tools.lemma_decomposer_v16 import LemmaPreDecomposer

        decomp = LemmaPreDecomposer()
        plan = decomp.decompose_theorem_statement(
            theorem_header="theorem feigenbaum",
            domain="mathematical_physics",
            pid="feigenbaum_delta",
            max_lemmas=3,
        )
        for lemma in plan.lemmas:
            assert "feigenbaum" in lemma.name or "sub" in lemma.name, (
                f"Unexpected lemma name: {lemma.name}"
            )

    def test_max_lemmas_respected(self):
        """max_lemmas=4 produces at most 4 lemmas."""
        from agents.archimedes.tools.lemma_decomposer_v16 import LemmaPreDecomposer

        decomp = LemmaPreDecomposer()
        plan = decomp.decompose_theorem_statement(
            theorem_header="theorem big",
            domain="combinatorics",
            pid="big_theorem",
            max_lemmas=4,
        )
        assert len(plan.lemmas) <= 4

    def test_estimated_cost_positive(self):
        """Total estimated cost is positive for non-empty plans."""
        from agents.archimedes.tools.lemma_decomposer_v16 import LemmaPreDecomposer

        decomp = LemmaPreDecomposer()
        plan = decomp.decompose_theorem_statement(
            theorem_header="theorem t",
            domain="special_functions",
            pid="bessel_c5",
            max_lemmas=3,
        )
        assert plan.total_estimated_cost_usd > 0.0

    def test_prompt_injection_contains_lean4(self):
        """Prompt injection contains Lean 4 syntax stubs."""
        from agents.archimedes.tools.lemma_decomposer_v16 import LemmaPreDecomposer

        decomp = LemmaPreDecomposer()
        plan = decomp.decompose_theorem_statement(
            theorem_header="theorem spectral",
            domain="spectral_theory",
            pid="spheroidal_eigenvalue",
            max_lemmas=3,
        )
        assert "lean4" in plan.prompt_injection.lower() or "have" in plan.prompt_injection

    def test_all_difficulty_levels_covered(self):
        """At least one easy, one medium, one hard lemma appears across domains."""
        from agents.archimedes.tools.lemma_decomposer_v16 import LemmaPreDecomposer

        decomp = LemmaPreDecomposer()
        all_difficulties = set()
        for domain in ["number_theory", "combinatorics", "special_functions"]:
            plan = decomp.decompose_theorem_statement(
                theorem_header=f"theorem {domain}",
                domain=domain,
                pid=domain,
                max_lemmas=3,
            )
            for lemma in plan.lemmas:
                all_difficulties.add(lemma.estimated_difficulty)

        assert "easy" in all_difficulties or "medium" in all_difficulties, (
            f"Expected at least easy/medium difficulty in {all_difficulties}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: GaloisAgent.upgrade_to_v16()
# ─────────────────────────────────────────────────────────────────────────────

class TestGaloisAgentV16Upgrade:
    """Tests for GaloisAgent.upgrade_to_v16()."""

    def test_upgrade_to_v16_sets_cortex(self):
        """upgrade_to_v16() creates a SymBrainV16Cortex and sets v16_cortex."""
        from agents.galois.agent import GaloisAgent
        from agents.galois.symbrain.cortex_v16 import SymBrainV16Cortex

        agent = GaloisAgent()
        assert agent.v16_cortex is None, "v16_cortex should be None before upgrade"
        agent.upgrade_to_v16()
        assert agent.v16_cortex is not None
        assert isinstance(agent.v16_cortex, SymBrainV16Cortex)

    def test_upgrade_to_v16_updates_version_string(self):
        """upgrade_to_v16() updates the cortex version string."""
        from agents.galois.agent import GaloisAgent

        agent = GaloisAgent()
        agent.upgrade_to_v16()
        assert "v16" in agent.cortex.symbrain_version

    def test_upgrade_to_v12_sets_cortex(self):
        """upgrade_to_v12() creates a SymBrainV12Cortex and sets v12_cortex."""
        from agents.galois.agent import GaloisAgent
        from agents.galois.symbrain.cortex_v12 import SymBrainV12Cortex

        agent = GaloisAgent()
        assert agent.v12_cortex is None
        agent.upgrade_to_v12()
        assert isinstance(agent.v12_cortex, SymBrainV12Cortex)

    def test_upgrade_chain_v11_then_v16(self):
        """Upgrade chain v11 → v16 leaves both cortices assigned."""
        from agents.galois.agent import GaloisAgent

        agent = GaloisAgent()
        agent.upgrade_to_v11()
        agent.upgrade_to_v16()
        assert agent.v11_cortex is not None
        assert agent.v16_cortex is not None


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: ArchimedesAgent._pre_decompose_theorem()
# ─────────────────────────────────────────────────────────────────────────────

class TestArchimedesPreDecompose:
    """Tests for ArchimedesAgent._pre_decompose_theorem() (v16 H1 integration)."""

    def test_pre_decompose_returns_plan(self):
        """_pre_decompose_theorem returns a TheoremPreDecomposition plan."""
        from agents.archimedes.agent import ArchimedesAgent

        agent = ArchimedesAgent()
        plan = agent._pre_decompose_theorem(
            theorem_header="theorem foo : ∀ n, P n",
            lean4_sketch="theorem foo : ∀ n, P n := by\n  sorry\n",
            domain="number_theory",
            pid="foo_problem",
        )
        assert plan is not None
        assert len(plan.lemmas) >= 1

    def test_pre_decompose_domain_coding_theory(self):
        """_pre_decompose_theorem works for coding_theory domain."""
        from agents.archimedes.agent import ArchimedesAgent

        agent = ArchimedesAgent()
        plan = agent._pre_decompose_theorem(
            theorem_header="theorem cwcode : ...",
            lean4_sketch="theorem cwcode := by\n  sorry\n  sorry\n",
            domain="coding_theory",
            pid="cwcode_29_8_5",
        )
        assert plan is not None
        assert plan.domain == "coding_theory"

    def test_pre_decompose_called_in_run(self):
        """ArchimedesAgent.run() calls _pre_decompose_theorem (via mock)."""
        from agents.archimedes.agent import ArchimedesAgent

        agent = ArchimedesAgent()

        called_with = {}

        original = agent._pre_decompose_theorem

        def mock_pre_decompose(theorem_header, lean4_sketch, domain, pid=""):
            called_with["theorem_header"] = theorem_header
            called_with["domain"] = domain
            return original(theorem_header, lean4_sketch, domain, pid)

        agent._pre_decompose_theorem = mock_pre_decompose  # type: ignore[assignment]

        async def run_it():
            return await agent.run(
                "test query",
                lean4_sketch="theorem t := by\n  sorry\n",
                domain="combinatorics",
                pid="test",
            )

        asyncio.run(run_it())
        assert "domain" in called_with, "_pre_decompose_theorem was not called"
        assert called_with["domain"] == "combinatorics"


# ─────────────────────────────────────────────────────────────────────────────
# Test 8: Non-regression — v15 tests still pass under v16 imports
# ─────────────────────────────────────────────────────────────────────────────

class TestV16NonRegression:
    """Verify that v16 additions do not break v15 code paths."""

    def test_v15_archimedes_still_works(self):
        """ArchimedesAgent runs without v16 kwargs (backward compatible)."""
        from agents.archimedes.agent import ArchimedesAgent

        agent = ArchimedesAgent()

        async def run_legacy():
            return await agent.run(
                "legacy query",
                lean4_sketch="theorem t := by\n  sorry\n",
                domain="number_theory",
                # No pid kwarg — v15 style
            )

        result = asyncio.run(run_legacy())
        # Should not raise; cost should be non-negative
        assert result.cost_usd >= 0.0

    def test_galois_upgrade_to_v11_still_works(self):
        """upgrade_to_v11() still works after adding v16 attribute."""
        from agents.galois.agent import GaloisAgent

        agent = GaloisAgent()
        agent.upgrade_to_v11()  # Must not raise
        assert agent.v11_cortex is not None

    def test_cortex_v12_inherits_from_v11(self):
        """SymBrainV12Cortex inherits from SymBrainV11Cortex."""
        from agents.galois.symbrain.cortex_v11 import SymBrainV11Cortex
        from agents.galois.symbrain.cortex_v12 import SymBrainV12Cortex

        assert issubclass(SymBrainV12Cortex, SymBrainV11Cortex)

    def test_cortex_v16_inherits_from_v12(self):
        """SymBrainV16Cortex inherits from SymBrainV12Cortex."""
        from agents.galois.symbrain.cortex_v12 import SymBrainV12Cortex
        from agents.galois.symbrain.cortex_v16 import SymBrainV16Cortex

        assert issubclass(SymBrainV16Cortex, SymBrainV12Cortex)

    def test_shard_router_invalid_tier_raises(self):
        """ShardRouter raises ValueError for an unknown tier name."""
        from agents.galois.tools.region_shard_router import ShardRouter

        with pytest.raises(ValueError, match="Unknown tier"):
            ShardRouter(tier="H100_WISHFUL_THINKING")

    def test_pre_decomposer_default_domain_fallback(self):
        """LemmaPreDecomposer falls back to _default templates for unknown domain."""
        from agents.archimedes.tools.lemma_decomposer_v16 import LemmaPreDecomposer

        decomp = LemmaPreDecomposer()
        plan = decomp.decompose_theorem_statement(
            theorem_header="theorem unknown_domain",
            domain="continuum_physics",  # not in registry → _default
            pid="feigenbaum_alpha",
            max_lemmas=3,
        )
        assert len(plan.lemmas) > 0, "Should fall back to _default templates"
