# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""DAG-Aware MCTS Search Controller — The Galois LEAP Engine.

Bridges the existing MCTS search engine with:
  1. The LEAP AND-OR DAG (GlobalLemmaCache)
  2. Alexandrie RAG memory
  3. Aristotle semantic pre-screening (The Guillotine)
  4. Descartes exploit synthesis on failure
  5. Champollion proof trace extraction on success

This is the v21 'integration glue' that wires ALL Sentinel agents
into a single coherent proof search orchestration.

Reference: THE AGORA SENTINEL CODEX, Chapters 6-9.
Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable

import structlog

from agents.galois.search.dag_memory import (
    DAGNode,
    GlobalLemmaCache,
    NodeStatus,
    NodeType,
)
from agents.galois.mcts_node import ProofNode
from agents.galois.mcts_policy import MCTSPolicy

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Search Outcome
# ---------------------------------------------------------------------------

class SearchOutcome(Enum):
    """Outcome of a DAG-aware MCTS search."""
    PROVEN = auto()          # All sorry gaps closed — goals: []
    BUDGET_EXHAUSTED = auto()  # Hit iteration/cost limit
    CONTRADICTION = auto()    # Found unprovable state → exploit opportunity
    FILTERED = auto()         # Aristotle rejected all decompositions


@dataclass(slots=True)
class SearchResult:
    """Result of a DAG-aware MCTS proof search."""
    outcome: SearchOutcome
    proof_trace: list[str] = field(default_factory=list)
    dead_end_states: list[str] = field(default_factory=list)
    total_nodes_explored: int = 0
    cache_hits: int = 0
    aristotle_rejections: int = 0
    elapsed_ms: float = 0.0
    compute_cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.name,
            "proof_trace": self.proof_trace,
            "dead_end_states": self.dead_end_states,
            "total_nodes_explored": self.total_nodes_explored,
            "cache_hits": self.cache_hits,
            "aristotle_rejections": self.aristotle_rejections,
            "elapsed_ms": self.elapsed_ms,
            "compute_cost_usd": self.compute_cost_usd,
        }


# ---------------------------------------------------------------------------
# DAG Search Controller
# ---------------------------------------------------------------------------

class DAGSearchController:
    """Orchestrates LEAP AND-OR DAG search with Sentinel agent hooks.

    The search loop:
      1. Select an open OR-node (sorry gap) from the DAG
      2. Query Alexandrie for RAG-augmented tactic hints
      3. Ask LLM (MCTSPolicy) for candidate decompositions
      4. Pass each decomposition through Aristotle (The Guillotine)
      5. Submit survivors to Lean REPL (Euler bridge)
      6. Update DAG with results; propagate proofs
      7. On success: extract proof trace for Champollion
      8. On failure: collect dead-end states for Descartes

    Attributes:
        cache: The Global Lemma Cache (content-addressed DAG).
        policy: The MCTSPolicy that generates tactics.
        aristotle: Optional Aristotle agent for decomposition QA.
        alexandrie_hub: Optional Alexandrie hub for RAG.
        max_iterations: Maximum MCTS iterations.
        cost_per_iteration_usd: Estimated cost per LLM call.
    """

    def __init__(
        self,
        cache: GlobalLemmaCache | None = None,
        policy: MCTSPolicy | None = None,
        aristotle: Any = None,  # AristotleAgent — lazy import to avoid cycles
        alexandrie_hub: Any = None,
        max_iterations: int = 1000,
        cost_per_iteration_usd: float = 0.001,
        lean_repl: Any = None,  # LeanREPL instance
    ) -> None:
        self.cache = cache or GlobalLemmaCache()
        self.policy = policy
        self.aristotle = aristotle
        self.alexandrie_hub = alexandrie_hub
        self.max_iterations = max_iterations
        self.cost_per_iteration_usd = cost_per_iteration_usd
        self.lean_repl = lean_repl

        # Metrics
        self._nodes_explored = 0
        self._cache_hits = 0
        self._aristotle_rejections = 0
        self._dead_end_states: list[str] = []

        # Callbacks
        self._on_proof_found: list[Callable[[DAGNode], None]] = []
        self._on_dead_end: list[Callable[[DAGNode], None]] = []

        self._log = logger.bind(component="dag_search_controller")

    # ──────────────────────────────────────────────────────────
    # Callback Registration
    # ──────────────────────────────────────────────────────────

    def on_proof_found(self, callback: Callable[[DAGNode], None]) -> None:
        """Register a callback for when a proof is discovered."""
        self._on_proof_found.append(callback)

    def on_dead_end(self, callback: Callable[[DAGNode], None]) -> None:
        """Register a callback for when an unprovable state is found."""
        self._on_dead_end.append(callback)

    # ──────────────────────────────────────────────────────────
    # Core Search Loop
    # ──────────────────────────────────────────────────────────

    def search(self, root_goal: str) -> SearchResult:
        """Run the DAG-aware MCTS search.

        Args:
            root_goal: The initial Lean 4 goal state (e.g., "⊢ transfer_safe ...").

        Returns:
            SearchResult with outcome, proof trace, and diagnostics.
        """
        t_start = time.perf_counter()

        # Initialize root OR-node
        root, was_cached = self.cache.get_or_create(NodeType.OR_NODE, root_goal)
        if was_cached and root.is_proven:
            self._log.info("instant_cache_hit", goal=root_goal[:80])
            return SearchResult(
                outcome=SearchOutcome.PROVEN,
                proof_trace=root.proof_trace or [],
                cache_hits=1,
                elapsed_ms=(time.perf_counter() - t_start) * 1000,
            )

        # Main search loop
        for iteration in range(self.max_iterations):
            # Check termination
            if root.is_proven:
                break

            # 1. Select: pick the most promising open OR-node
            target_node = self._select_open_goal()
            if target_node is None:
                break  # No open goals left

            self._nodes_explored += 1

            # 2. Expand: generate candidate tactics/decompositions
            candidates = self._generate_candidates(target_node)

            # 3. Filter: Aristotle reviews each candidate
            survivors = self._aristotle_filter(target_node, candidates)

            if not survivors:
                # All candidates rejected — mark as dead end
                target_node.mark_failed()
                self._dead_end_states.append(target_node.statement)
                for cb in self._on_dead_end:
                    cb(target_node)
                continue

            # 4. Evaluate: submit to Lean REPL
            for tactic_sequence in survivors:
                result = self._evaluate_tactic(target_node, tactic_sequence)
                if result == "proven":
                    target_node.mark_proven(proof_trace=tactic_sequence)
                    self.cache.propagate_success(target_node)

                    # Memorize in Alexandrie
                    if self.alexandrie_hub and self.policy:
                        self.policy.memorize_success(
                            lean_state=target_node.statement,
                            winning_tactic="; ".join(tactic_sequence),
                        )

                    for cb in self._on_proof_found:
                        cb(target_node)
                    break

                elif result == "subgoals":
                    # Created AND-node with sub-goals — already in DAG
                    pass

                elif result == "error":
                    # Tactic failed compilation
                    continue

            # Periodic logging
            if (iteration + 1) % 100 == 0:
                open_goals = self.cache.get_open_goals()
                self._log.info(
                    "search_progress",
                    iteration=iteration + 1,
                    open_goals=len(open_goals),
                    nodes_explored=self._nodes_explored,
                    cache_hits=self._cache_hits,
                )

        # Determine outcome
        elapsed_ms = (time.perf_counter() - t_start) * 1000
        cost = self._nodes_explored * self.cost_per_iteration_usd

        if root.is_proven:
            outcome = SearchOutcome.PROVEN
        elif self._dead_end_states:
            outcome = SearchOutcome.CONTRADICTION
        elif self._aristotle_rejections > self._nodes_explored * 0.8:
            outcome = SearchOutcome.FILTERED
        else:
            outcome = SearchOutcome.BUDGET_EXHAUSTED

        self._log.info(
            "search_complete",
            outcome=outcome.name,
            nodes=self._nodes_explored,
            cache_hits=self._cache_hits,
            dead_ends=len(self._dead_end_states),
            elapsed_ms=elapsed_ms,
        )

        return SearchResult(
            outcome=outcome,
            proof_trace=root.proof_trace or [],
            dead_end_states=self._dead_end_states,
            total_nodes_explored=self._nodes_explored,
            cache_hits=self._cache_hits,
            aristotle_rejections=self._aristotle_rejections,
            elapsed_ms=elapsed_ms,
            compute_cost_usd=cost,
        )

    # ──────────────────────────────────────────────────────────
    # Selection Strategy
    # ──────────────────────────────────────────────────────────

    def _select_open_goal(self) -> DAGNode | None:
        """Select the most promising open OR-node using UCT."""
        open_goals = self.cache.get_open_goals()
        if not open_goals:
            return None

        # Sort by UCT score (exploration-exploitation balance)
        scored = [(node, node.uct_score()) for node in open_goals]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]

    # ──────────────────────────────────────────────────────────
    # Tactic Generation (MCTSPolicy + Alexandrie RAG)
    # ──────────────────────────────────────────────────────────

    def _generate_candidates(self, node: DAGNode) -> list[list[str]]:
        """Generate candidate tactic sequences using MCTSPolicy.

        If Alexandrie is available, the prompt is RAG-augmented with
        historical tactics from semantically similar proof states.
        """
        if self.policy is None:
            # Fallback: return basic tactics
            return [
                ["simp"],
                ["ring"],
                ["omega"],
                ["linarith"],
                ["norm_num"],
                ["decide"],
            ]

        # Generate tactics via LLM policy (RAG-augmented if hub is set)
        try:
            tactics = self.policy.generate_tactics(
                lean_state=node.statement,
                num_candidates=8,
            )
            # Each tactic string becomes a single-step sequence
            return [[t] for t in tactics]
        except Exception as exc:
            self._log.warning("tactic_generation_failed", error=str(exc))
            return [["simp"], ["ring"], ["omega"]]

    # ──────────────────────────────────────────────────────────
    # Aristotle Filter (The Semantic Guillotine)
    # ──────────────────────────────────────────────────────────

    def _aristotle_filter(
        self,
        parent_node: DAGNode,
        candidates: list[list[str]],
    ) -> list[list[str]]:
        """Filter candidate decompositions through Aristotle.

        Aristotle rejects circular tautologies, trivial restatements,
        and complexity-increasing decompositions before any Lean
        compilation cost is incurred.

        Args:
            parent_node: The OR-node being decomposed.
            candidates: List of candidate tactic sequences.

        Returns:
            Filtered list of approved tactic sequences.
        """
        if self.aristotle is None:
            return candidates  # No filter — pass all through

        survivors = []
        for candidate in candidates:
            # Build the review context
            tactic_str = "; ".join(candidate)
            try:
                approved = self.aristotle.review_decomposition(
                    parent_goal=parent_node.statement,
                    blueprint=tactic_str,
                    lemmas=candidate,
                )
                if approved:
                    survivors.append(candidate)
                else:
                    self._aristotle_rejections += 1
                    self._log.debug(
                        "aristotle_rejected",
                        parent=parent_node.statement[:60],
                        tactic=tactic_str,
                    )
            except Exception as exc:
                # If Aristotle fails, pass the candidate through
                self._log.warning("aristotle_error", error=str(exc))
                survivors.append(candidate)

        return survivors

    # ──────────────────────────────────────────────────────────
    # Lean REPL Evaluation (Euler Bridge)
    # ──────────────────────────────────────────────────────────

    def _evaluate_tactic(
        self,
        node: DAGNode,
        tactic_sequence: list[str],
    ) -> str:
        """Submit a tactic sequence to the Lean REPL.

        Returns:
            "proven" if goals: []
            "subgoals" if new subgoals were created
            "error" if the tactic failed
        """
        if self.lean_repl is None:
            # Simulation mode: check DAG cache
            cache_node, was_cached = self.cache.get_or_create(
                NodeType.OR_NODE,
                f"{node.statement} → {'; '.join(tactic_sequence)}",
            )
            if was_cached:
                self._cache_hits += 1
                if cache_node.is_proven:
                    return "proven"
            return "error"  # No REPL available

        # Live REPL evaluation
        try:
            combined_tactic = "\n".join(tactic_sequence)
            result = self.lean_repl.execute_tactic(
                state=node.state_id if hasattr(node, 'state_id') else 0,
                tactic_string=combined_tactic,
            )

            if not result:
                return "error"

            # Check for proof completion
            if result.get("goals") == [] or "goals accomplished" in str(result).lower():
                return "proven"

            # Check for new subgoals
            new_goals = result.get("goals", [])
            if new_goals:
                # Create AND-node for the decomposition
                and_node, _ = self.cache.get_or_create(
                    NodeType.AND_NODE,
                    f"sketch({'; '.join(tactic_sequence)})",
                )
                node.add_child(and_node)

                # Create OR-nodes for each subgoal
                for goal in new_goals:
                    goal_str = goal if isinstance(goal, str) else str(goal)
                    subgoal, was_cached = self.cache.get_or_create(
                        NodeType.OR_NODE, goal_str
                    )
                    if was_cached:
                        self._cache_hits += 1
                    and_node.add_child(subgoal)

                return "subgoals"

            # Check for errors
            if result.get("message") or result.get("error"):
                return "error"

            return "error"

        except Exception as exc:
            self._log.warning("repl_error", error=str(exc))
            return "error"

    # ──────────────────────────────────────────────────────────
    # Proof Trace Extraction (for Champollion)
    # ──────────────────────────────────────────────────────────

    def extract_proof_trace(self, root_goal: str) -> list[dict[str, str]]:
        """Extract the complete proof trace from a proven DAG.

        Walks the proven DAG and extracts each step with its
        tactic and goal state, formatted for Champollion's
        report generation.

        Returns:
            List of {goal, tactic, status} dicts.
        """
        from agents.galois.search.dag_memory import state_hash as _state_hash
        root_hash = _state_hash(root_goal)
        root = self.cache.nodes.get(root_hash)
        if root is None or not root.is_proven:
            return []

        trace: list[dict[str, str]] = []
        visited: set[str] = set()

        def _walk(node: DAGNode, depth: int = 0) -> None:
            if node.state_hash in visited:
                return
            visited.add(node.state_hash)

            if node.node_type == NodeType.OR_NODE:
                trace.append({
                    "depth": depth,
                    "goal": node.statement,
                    "tactics": node.proof_trace or [],
                    "status": node.status.name,
                })

            for child in node.children:
                _walk(child, depth + 1)

        _walk(root)
        return trace

    # ──────────────────────────────────────────────────────────
    # Dead-End Extraction (for Descartes)
    # ──────────────────────────────────────────────────────────

    def extract_dead_ends(self) -> list[dict[str, str]]:
        """Extract all dead-end states for Descartes exploit synthesis.

        Returns:
            List of {goal_state, parent_tactic, depth} dicts for
            each failed node in the DAG.
        """
        dead_ends = []
        for sh, node in self.cache.nodes.items():
            if node.status == NodeStatus.FAILED and node.node_type == NodeType.OR_NODE:
                parent_tactics = []
                for parent in node.parents:
                    if parent.proof_trace:
                        parent_tactics.extend(parent.proof_trace)

                dead_ends.append({
                    "goal_state": node.statement,
                    "parent_tactics": parent_tactics,
                    "depth": node.depth,
                    "visits": node.visits,
                })

        return dead_ends
