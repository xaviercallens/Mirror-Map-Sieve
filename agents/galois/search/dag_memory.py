# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""LEAP AND-OR DAG Memory — Global Lemma Cache.

Implements the DeepMind LEAP architecture: an AND-OR Directed Acyclic Graph
with content-hashed global lemma caching.

Key concepts:
    - OR-Nodes (Goals): A theorem to prove. Succeeds if ANY child path succeeds.
    - AND-Nodes (Sketches): A blueprint decomposition with sorry gaps.
      Succeeds only if ALL child sorry gaps are proven.

When a lemma is proven on Branch A, it is cached globally. When Branch B
needs the same lemma, the DAG resolves it instantly in O(1) with zero
LLM inference cost.

Reference: THE AGORA SENTINEL CODEX, Chapter 8.
Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class NodeType(Enum):
    """Type of node in the AND-OR DAG."""

    OR_NODE = auto()    # Goal: succeeds if ANY child succeeds
    AND_NODE = auto()   # Sketch: succeeds if ALL children succeed


class NodeStatus(Enum):
    """Resolution status of a DAG node."""

    OPEN = auto()       # Not yet attempted
    EXPLORING = auto()  # Currently being worked on by MCTS
    PROVEN = auto()     # Successfully closed
    FAILED = auto()     # Exhausted compute budget, no proof found
    CACHED = auto()     # Resolved via global lemma cache hit


# ---------------------------------------------------------------------------
# Alpha-Normalization
# ---------------------------------------------------------------------------

_VAR_PATTERN = re.compile(r'\b([a-z])\d*(?:✝\d+)?\b')


def alpha_normalize(lean_state: str) -> str:
    """Normalize a Lean 4 tactic state for content-hash deduplication.

    Replaces all single-letter variable names (including auto-generated
    suffixes like h✝, h✝1) with canonical names (v0, v1, ...) to detect
    semantically identical goals that differ only in variable naming.

    Args:
        lean_state: Raw Lean 4 tactic state string.

    Returns:
        Alpha-normalized state with canonical variable names.
    """
    seen: dict[str, str] = {}
    counter = 0

    def replace_var(match: re.Match) -> str:
        nonlocal counter
        var = match.group(0)
        if var not in seen:
            seen[var] = f"v{counter}"
            counter += 1
        return seen[var]

    # Strip whitespace variations
    normalized = " ".join(lean_state.split())
    # Replace variable names
    normalized = _VAR_PATTERN.sub(replace_var, normalized)
    return normalized


def state_hash(lean_state: str) -> str:
    """Compute a content hash for a Lean 4 state after alpha-normalization.

    Args:
        lean_state: Raw Lean 4 tactic state string.

    Returns:
        MD5 hex digest of the alpha-normalized state.
    """
    normalized = alpha_normalize(lean_state)
    return hashlib.md5(normalized.encode()).hexdigest()


# ---------------------------------------------------------------------------
# DAG Node
# ---------------------------------------------------------------------------

@dataclass
class DAGNode:
    """A node in the LEAP AND-OR DAG.

    Attributes:
        node_type: OR_NODE (goal) or AND_NODE (sketch).
        statement: The Lean 4 goal or sketch content.
        state_hash: Content hash for deduplication.
        status: Current resolution status.
        parents: Nodes that depend on this one.
        children: Child nodes (sub-goals or sub-sketches).
        proof_trace: The tactic sequence that closed this node (if proven).
        blueprint: Informal English strategy description.
        visits: MCTS visit count.
        value: MCTS cumulative value.
        depth: Depth in the DAG (root = 0).
        created_at: Timestamp of node creation.
        metadata: Extra context for debugging and reporting.
    """

    node_type: NodeType
    statement: str
    state_hash: str = ""
    status: NodeStatus = NodeStatus.OPEN
    parents: list[DAGNode] = field(default_factory=list, repr=False)
    children: list[DAGNode] = field(default_factory=list, repr=False)
    proof_trace: list[str] = field(default_factory=list)
    blueprint: str = ""
    visits: int = 0
    value: float = 0.0
    depth: int = 0
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.state_hash:
            self.state_hash = state_hash(self.statement)

    @property
    def is_proven(self) -> bool:
        return self.status in (NodeStatus.PROVEN, NodeStatus.CACHED)

    @property
    def is_terminal(self) -> bool:
        return self.status in (NodeStatus.PROVEN, NodeStatus.CACHED, NodeStatus.FAILED)

    def mark_proven(self, proof_trace: list[str] | None = None) -> None:
        """Mark this node as proven and trigger upward propagation."""
        self.status = NodeStatus.PROVEN
        if proof_trace:
            self.proof_trace = proof_trace

    def mark_failed(self) -> None:
        """Mark this node as failed (compute budget exhausted)."""
        self.status = NodeStatus.FAILED

    def add_child(self, child: DAGNode) -> None:
        """Add a child node and set the parent back-reference."""
        if child not in self.children:
            self.children.append(child)
        if self not in child.parents:
            child.parents.append(self)
        child.depth = self.depth + 1

    def uct_score(self, c_param: float = 1.414) -> float:
        """Upper Confidence Bound for tree search.

        Args:
            c_param: Exploration constant.

        Returns:
            UCT score (exploitation + exploration).
        """
        import math

        if self.is_terminal:
            return float("-inf") if self.status == NodeStatus.FAILED else float("inf")
        if self.visits == 0:
            return float("inf")
        exploitation = self.value / self.visits
        parent_visits = max(sum(p.visits for p in self.parents), 1)
        exploration = c_param * math.sqrt(math.log(parent_visits) / self.visits)
        return exploitation + exploration

    def __repr__(self) -> str:
        return (
            f"<DAGNode type={self.node_type.name} "
            f"status={self.status.name} "
            f"depth={self.depth} "
            f"hash={self.state_hash[:8]}>"
        )


# ---------------------------------------------------------------------------
# Global Lemma Cache
# ---------------------------------------------------------------------------

class GlobalLemmaCache:
    """Content-addressed cache for the LEAP AND-OR DAG.

    Provides O(1) deduplication of proof obligations. If a lemma
    has been proven on any branch of the search, all other branches
    that need the same lemma resolve instantly.

    Attributes:
        nodes: Hash-map from state_hash → DAGNode.
    """

    def __init__(self) -> None:
        self.nodes: dict[str, DAGNode] = {}
        self._on_proven_callbacks: list[Callable[[DAGNode], None]] = []
        self._log = logger.bind(component="global_lemma_cache")
        self._cache_hits = 0
        self._cache_misses = 0

    def get_or_create(
        self,
        node_type: NodeType,
        statement: str,
        blueprint: str = "",
    ) -> tuple[DAGNode, bool]:
        """Get existing node or create a new one.

        Args:
            node_type: OR_NODE or AND_NODE.
            statement: Lean 4 goal/sketch statement.
            blueprint: Optional informal strategy description.

        Returns:
            Tuple of (node, was_cached). If was_cached is True, the node
            already existed in the cache (possible instant resolution).
        """
        h = state_hash(statement)

        if h in self.nodes:
            existing = self.nodes[h]
            self._cache_hits += 1
            self._log.debug(
                "cache_hit",
                hash=h[:8],
                status=existing.status.name,
            )
            return existing, True

        # Create new node
        node = DAGNode(
            node_type=node_type,
            statement=statement,
            state_hash=h,
            blueprint=blueprint,
        )
        self.nodes[h] = node
        self._cache_misses += 1
        return node, False

    def propagate_success(self, node: DAGNode) -> None:
        """Recursively propagate proof success upward through the DAG.

        For OR-nodes: parent succeeds if THIS child succeeds.
        For AND-nodes: parent succeeds only if ALL children succeed.

        Args:
            node: The node that was just proven.
        """
        if not node.is_proven:
            return

        for parent in node.parents:
            if parent.is_proven:
                continue

            if parent.node_type == NodeType.OR_NODE:
                # OR: any child success proves the parent
                parent.mark_proven(proof_trace=node.proof_trace)
                self._log.info(
                    "or_node_resolved",
                    hash=parent.state_hash[:8],
                )
                # Notify callbacks
                for cb in self._on_proven_callbacks:
                    cb(parent)
                # Continue propagation
                self.propagate_success(parent)

            elif parent.node_type == NodeType.AND_NODE:
                # AND: all children must be proven
                if all(child.is_proven for child in parent.children):
                    # Merge proof traces from all children
                    combined_trace = []
                    for child in parent.children:
                        combined_trace.extend(child.proof_trace)
                    parent.mark_proven(proof_trace=combined_trace)
                    self._log.info(
                        "and_node_resolved",
                        hash=parent.state_hash[:8],
                        children=len(parent.children),
                    )
                    for cb in self._on_proven_callbacks:
                        cb(parent)
                    self.propagate_success(parent)

    def on_proven(self, callback: Callable[[DAGNode], None]) -> None:
        """Register a callback fired when any node is proven.

        Useful for triggering Alexandrie memorization on proof success.

        Args:
            callback: Function taking a DAGNode.
        """
        self._on_proven_callbacks.append(callback)

    def get_open_goals(self) -> list[DAGNode]:
        """Get all OR-nodes that are still open (not proven, not failed).

        Returns:
            List of open goal nodes, sorted by depth (deepest first).
        """
        return sorted(
            [
                n for n in self.nodes.values()
                if n.node_type == NodeType.OR_NODE
                and n.status in (NodeStatus.OPEN, NodeStatus.EXPLORING)
            ],
            key=lambda n: n.depth,
            reverse=True,
        )

    @property
    def stats(self) -> dict[str, int]:
        """Cache statistics."""
        proven = sum(1 for n in self.nodes.values() if n.is_proven)
        failed = sum(1 for n in self.nodes.values() if n.status == NodeStatus.FAILED)
        exploring = sum(1 for n in self.nodes.values() if n.status == NodeStatus.EXPLORING)
        open_count = sum(1 for n in self.nodes.values() if n.status == NodeStatus.OPEN)
        return {
            "total_nodes": len(self.nodes),
            "proven": proven,
            "failed": failed,
            "exploring": exploring,
            "open": open_count,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": (
                self._cache_hits / (self._cache_hits + self._cache_misses)
                if (self._cache_hits + self._cache_misses) > 0
                else 0.0
            ),
        }

    def __repr__(self) -> str:
        s = self.stats
        return (
            f"<GlobalLemmaCache nodes={s['total_nodes']} "
            f"proven={s['proven']} "
            f"hit_rate={s['hit_rate']:.1%}>"
        )
