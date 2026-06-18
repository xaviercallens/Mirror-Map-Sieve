# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Unit tests for the DAG Search Controller and Euler Bridge."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.galois.search.dag_search_controller import (
    DAGSearchController,
    SearchOutcome,
    SearchResult,
)
from agents.galois.search.dag_memory import GlobalLemmaCache, NodeType
from agents.galois.euler_bridge import EulerBridge, EulerPool, REPLState


# ---------------------------------------------------------------------------
# DAG Search Controller Tests
# ---------------------------------------------------------------------------

class TestDAGSearchController:
    """Tests for the DAG-aware MCTS search controller."""

    def test_instantiation_defaults(self):
        controller = DAGSearchController()
        assert controller.cache is not None
        assert controller.policy is None
        assert controller.aristotle is None
        assert controller.max_iterations == 1000

    def test_instantiation_with_cache(self):
        cache = GlobalLemmaCache()
        controller = DAGSearchController(cache=cache)
        assert controller.cache is cache

    def test_search_no_repl_returns_budget_exhausted(self):
        """Without a REPL, search should exhaust budget quickly."""
        controller = DAGSearchController(max_iterations=5)
        result = controller.search("⊢ 1 + 1 = 2")
        assert result.outcome in (
            SearchOutcome.BUDGET_EXHAUSTED,
            SearchOutcome.CONTRADICTION,
        )
        assert result.total_nodes_explored <= 5

    def test_search_cached_proven_returns_instantly(self):
        """If the root goal is already proven in cache, return immediately."""
        cache = GlobalLemmaCache()
        node, _ = cache.get_or_create(NodeType.OR_NODE, "⊢ trivial")
        node.mark_proven(proof_trace=["trivial"])

        controller = DAGSearchController(cache=cache)
        result = controller.search("⊢ trivial")
        assert result.outcome == SearchOutcome.PROVEN
        assert result.cache_hits == 1

    def test_search_result_serialization(self):
        result = SearchResult(
            outcome=SearchOutcome.PROVEN,
            proof_trace=["ring", "simp"],
            total_nodes_explored=42,
            elapsed_ms=123.4,
        )
        d = result.to_dict()
        assert d["outcome"] == "PROVEN"
        assert d["proof_trace"] == ["ring", "simp"]
        assert d["total_nodes_explored"] == 42

    def test_callback_registration(self):
        controller = DAGSearchController()
        proofs = []
        dead_ends = []
        controller.on_proof_found(lambda n: proofs.append(n))
        controller.on_dead_end(lambda n: dead_ends.append(n))
        assert len(controller._on_proof_found) == 1
        assert len(controller._on_dead_end) == 1

    def test_generate_candidates_fallback(self):
        """Without MCTSPolicy, should return basic tactic list."""
        controller = DAGSearchController()
        from agents.galois.search.dag_memory import DAGNode
        node = DAGNode(node_type=NodeType.OR_NODE, statement="⊢ True")
        candidates = controller._generate_candidates(node)
        assert len(candidates) >= 3
        assert ["simp"] in candidates

    def test_aristotle_filter_passthrough(self):
        """Without Aristotle, all candidates pass through."""
        controller = DAGSearchController()
        from agents.galois.search.dag_memory import DAGNode
        node = DAGNode(node_type=NodeType.OR_NODE, statement="⊢ True")
        candidates = [["simp"], ["ring"]]
        survivors = controller._aristotle_filter(node, candidates)
        assert survivors == candidates

    def test_aristotle_filter_with_mock(self):
        """Mock Aristotle that rejects 'ring'."""
        class MockAristotle:
            def review_decomposition(self, parent_goal, blueprint, lemmas):
                return "ring" not in blueprint

        controller = DAGSearchController(aristotle=MockAristotle())
        from agents.galois.search.dag_memory import DAGNode
        node = DAGNode(node_type=NodeType.OR_NODE, statement="⊢ test")
        candidates = [["simp"], ["ring"], ["omega"]]
        survivors = controller._aristotle_filter(node, candidates)
        assert ["simp"] in survivors
        assert ["ring"] not in survivors
        assert ["omega"] in survivors
        assert controller._aristotle_rejections == 1

    def test_extract_dead_ends(self):
        controller = DAGSearchController()
        from agents.galois.search.dag_memory import DAGNode
        node, _ = controller.cache.get_or_create(NodeType.OR_NODE, "⊢ False")
        node.mark_failed()
        dead_ends = controller.extract_dead_ends()
        assert len(dead_ends) == 1
        assert dead_ends[0]["goal_state"] == "⊢ False"


# ---------------------------------------------------------------------------
# Euler Bridge Tests (without live REPL)
# ---------------------------------------------------------------------------

class TestEulerBridge:
    """Tests for Euler Bridge properties (no live Lean REPL needed)."""

    def test_instantiation(self):
        bridge = EulerBridge(workspace_dir="/tmp/test")
        assert bridge.workspace_dir == "/tmp/test"
        assert bridge.timeout_seconds == 30.0
        assert not bridge.is_alive

    def test_initial_stats(self):
        bridge = EulerBridge(workspace_dir="/tmp/test")
        stats = bridge.stats
        assert stats["is_alive"] is False
        assert stats["total_commands"] == 0
        assert stats["avg_latency_ms"] == 0.0

    def test_avg_latency_zero_commands(self):
        bridge = EulerBridge(workspace_dir="/tmp/test")
        assert bridge.avg_latency_ms == 0.0

    def test_send_command_not_alive(self):
        bridge = EulerBridge(workspace_dir="/tmp/test")
        result = bridge._send_command({"cmd": "test"})
        assert result is None


class TestREPLState:
    """Tests for REPLState data class."""

    def test_default_state(self):
        state = REPLState()
        assert state.env_id == 0
        assert state.proof_states == {}
        assert state.sorry_count == 0
        assert not state.is_initialized


class TestEulerPool:
    """Tests for EulerPool (no live connections)."""

    def test_instantiation(self):
        pool = EulerPool(workspace_dir="/tmp/test", pool_size=4)
        assert pool.pool_size == 4
        assert len(pool._bridges) == 0

    def test_acquire_empty_pool(self):
        pool = EulerPool(workspace_dir="/tmp/test")
        result = pool.acquire()
        assert result is None

    def test_stats_empty(self):
        pool = EulerPool(workspace_dir="/tmp/test")
        stats = pool.stats
        assert stats["pool_size"] == 4
        assert stats["active_connections"] == 0


# ---------------------------------------------------------------------------
# Alexandrie Seeder Tests
# ---------------------------------------------------------------------------

class TestAlexandrieSeeder:
    """Tests for the day-zero memory seeder."""

    def test_extract_proven_theorems(self):
        from scripts.seed_alexandrie import extract_proven_theorems

        lean_code = """
theorem test_add : 1 + 1 = 2 := by
  norm_num

theorem test_sorry : 1 + 2 = 3 := by
  sorry
"""
        theorems = extract_proven_theorems(lean_code)
        assert len(theorems) == 1  # Only the proven one
        assert theorems[0]["name"] == "test_add"
        assert "norm_num" in theorems[0]["tactics"]

    def test_extract_all_theorems(self):
        from scripts.seed_alexandrie import extract_all_lean_theorems

        lean_code = """
theorem proven1 : True := by
  trivial

theorem sorry1 : False := by
  sorry

lemma helper : 1 = 1 := by
  rfl
"""
        all_theorems = extract_all_lean_theorems(lean_code)
        assert len(all_theorems) == 3
        names = [t["name"] for t in all_theorems]
        assert "proven1" in names
        assert "sorry1" in names
        assert "helper" in names

        sorry_count = sum(1 for t in all_theorems if t["has_sorry"])
        assert sorry_count == 1

    def test_extract_empty_source(self):
        from scripts.seed_alexandrie import extract_proven_theorems
        assert extract_proven_theorems("") == []

    def test_extract_no_by_block(self):
        from scripts.seed_alexandrie import extract_proven_theorems
        lean_code = "def foo : Nat := 42"
        assert extract_proven_theorems(lean_code) == []
