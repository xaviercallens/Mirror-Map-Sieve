# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Unit tests for the LEAP AND-OR DAG and Global Lemma Cache."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.galois.search.dag_memory import (
    DAGNode,
    GlobalLemmaCache,
    NodeStatus,
    NodeType,
    alpha_normalize,
    state_hash,
)


class TestAlphaNormalization:
    """Tests for alpha-normalization of Lean 4 states."""

    def test_identical_states_same_hash(self):
        s1 = "h : x > 0 ⊢ x^2 > 0"
        s2 = "h : x > 0 ⊢ x^2 > 0"
        assert state_hash(s1) == state_hash(s2)

    def test_whitespace_normalization(self):
        s1 = "h : x > 0  ⊢  x^2 > 0"
        s2 = "h : x > 0 ⊢ x^2 > 0"
        assert state_hash(s1) == state_hash(s2)

    def test_different_states_different_hash(self):
        s1 = "h : x > 0 ⊢ x^2 > 0"
        s2 = "h : x > 0 ⊢ x^3 > 0"
        assert state_hash(s1) != state_hash(s2)

    def test_normalize_strips_extra_spaces(self):
        result = alpha_normalize("  h  :  x > 0  ⊢  x^2 > 0  ")
        assert "  " not in result


class TestDAGNode:
    """Tests for DAG node properties."""

    def test_new_node_is_open(self):
        node = DAGNode(node_type=NodeType.OR_NODE, statement="⊢ True")
        assert node.status == NodeStatus.OPEN
        assert not node.is_proven
        assert not node.is_terminal

    def test_mark_proven(self):
        node = DAGNode(node_type=NodeType.OR_NODE, statement="⊢ True")
        node.mark_proven(proof_trace=["trivial"])
        assert node.is_proven
        assert node.is_terminal
        assert node.proof_trace == ["trivial"]

    def test_mark_failed(self):
        node = DAGNode(node_type=NodeType.OR_NODE, statement="⊢ False")
        node.mark_failed()
        assert node.status == NodeStatus.FAILED
        assert node.is_terminal
        assert not node.is_proven

    def test_add_child_sets_parent(self):
        parent = DAGNode(node_type=NodeType.AND_NODE, statement="parent")
        child = DAGNode(node_type=NodeType.OR_NODE, statement="child")
        parent.add_child(child)
        assert child in parent.children
        assert parent in child.parents
        assert child.depth == 1

    def test_auto_hash(self):
        node = DAGNode(node_type=NodeType.OR_NODE, statement="⊢ True")
        assert len(node.state_hash) == 32  # MD5 hex

    def test_uct_unvisited_is_infinity(self):
        node = DAGNode(node_type=NodeType.OR_NODE, statement="⊢ True")
        assert node.uct_score() == float("inf")

    def test_uct_failed_is_neg_infinity(self):
        node = DAGNode(node_type=NodeType.OR_NODE, statement="⊢ False")
        node.mark_failed()
        assert node.uct_score() == float("-inf")


class TestGlobalLemmaCache:
    """Tests for the content-addressed global lemma cache."""

    def test_get_or_create_new(self):
        cache = GlobalLemmaCache()
        node, was_cached = cache.get_or_create(NodeType.OR_NODE, "⊢ 1 + 1 = 2")
        assert not was_cached
        assert node.node_type == NodeType.OR_NODE
        assert node.status == NodeStatus.OPEN

    def test_get_or_create_dedup(self):
        cache = GlobalLemmaCache()
        node1, c1 = cache.get_or_create(NodeType.OR_NODE, "⊢ 1 + 1 = 2")
        node2, c2 = cache.get_or_create(NodeType.OR_NODE, "⊢ 1 + 1 = 2")
        assert not c1 and c2
        assert node1 is node2

    def test_different_statements_different_nodes(self):
        cache = GlobalLemmaCache()
        n1, _ = cache.get_or_create(NodeType.OR_NODE, "⊢ 1 + 1 = 2")
        n2, _ = cache.get_or_create(NodeType.OR_NODE, "⊢ 2 + 2 = 4")
        assert n1 is not n2

    def test_stats(self):
        cache = GlobalLemmaCache()
        cache.get_or_create(NodeType.OR_NODE, "stmt1")
        cache.get_or_create(NodeType.OR_NODE, "stmt2")
        cache.get_or_create(NodeType.OR_NODE, "stmt1")  # hit
        stats = cache.stats
        assert stats["total_nodes"] == 2
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 2

    def test_get_open_goals(self):
        cache = GlobalLemmaCache()
        n1, _ = cache.get_or_create(NodeType.OR_NODE, "goal_a")
        n2, _ = cache.get_or_create(NodeType.OR_NODE, "goal_b")
        n3, _ = cache.get_or_create(NodeType.AND_NODE, "sketch_c")
        open_goals = cache.get_open_goals()
        assert n1 in open_goals
        assert n2 in open_goals
        assert n3 not in open_goals  # AND nodes are not goals

    def test_propagate_or_node(self):
        """OR-node parent resolves when ANY child is proven."""
        cache = GlobalLemmaCache()
        parent, _ = cache.get_or_create(NodeType.OR_NODE, "parent_goal")
        child1, _ = cache.get_or_create(NodeType.OR_NODE, "child1")
        child2, _ = cache.get_or_create(NodeType.OR_NODE, "child2")
        parent.add_child(child1)
        parent.add_child(child2)

        child1.mark_proven(proof_trace=["ring"])
        cache.propagate_success(child1)
        assert parent.is_proven

    def test_propagate_and_node_needs_all(self):
        """AND-node parent resolves only when ALL children are proven."""
        cache = GlobalLemmaCache()
        parent, _ = cache.get_or_create(NodeType.AND_NODE, "and_parent")
        child1, _ = cache.get_or_create(NodeType.OR_NODE, "sub1")
        child2, _ = cache.get_or_create(NodeType.OR_NODE, "sub2")
        parent.add_child(child1)
        parent.add_child(child2)

        child1.mark_proven(proof_trace=["tactic1"])
        cache.propagate_success(child1)
        assert not parent.is_proven  # Needs child2 too

        child2.mark_proven(proof_trace=["tactic2"])
        cache.propagate_success(child2)
        assert parent.is_proven
        assert parent.proof_trace == ["tactic1", "tactic2"]

    def test_on_proven_callback(self):
        """Callbacks fire when nodes are proven."""
        cache = GlobalLemmaCache()
        proven_nodes = []
        cache.on_proven(lambda n: proven_nodes.append(n))

        parent, _ = cache.get_or_create(NodeType.OR_NODE, "callback_parent")
        child, _ = cache.get_or_create(NodeType.OR_NODE, "callback_child")
        parent.add_child(child)

        child.mark_proven(proof_trace=["omega"])
        cache.propagate_success(child)

        # Both child propagation triggers parent proven → callback
        assert parent in proven_nodes

    def test_cross_branch_resolution(self):
        """A lemma proven on Branch A instantly resolves Branch B."""
        cache = GlobalLemmaCache()

        # Branch A uses lemma L
        branch_a, _ = cache.get_or_create(NodeType.AND_NODE, "branch_a")
        lemma_l, _ = cache.get_or_create(NodeType.OR_NODE, "lemma_l: ⊢ 2 > 1")
        branch_a.add_child(lemma_l)

        # Branch B also uses lemma L
        branch_b, _ = cache.get_or_create(NodeType.AND_NODE, "branch_b")
        lemma_l_again, cached = cache.get_or_create(NodeType.OR_NODE, "lemma_l: ⊢ 2 > 1")
        assert cached  # Same lemma!
        assert lemma_l_again is lemma_l
        branch_b.add_child(lemma_l_again)

        # Prove lemma on Branch A
        lemma_l.mark_proven(proof_trace=["omega"])
        cache.propagate_success(lemma_l)

        # Branch B's copy is also resolved (same node)
        assert lemma_l_again.is_proven
