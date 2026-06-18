# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Galois Monte Carlo Tree Search (MCTS) Reasoner.

Provides Tier-4 o1-style "Test-Time Compute" for the Galois agent.
Rather than zero-shot ("Blind") heuristics, Galois spans a thought tree,
evaluates logical branches via an inner-monologue critique (simulated Euler),
and selects the most rigorous path.

Integrates with Turing's budget allocator to limit depth/width based on token constraints.
"""

from __future__ import annotations

import math
import structlog
from dataclasses import dataclass, field
from typing import Any
from google import genai

logger = structlog.get_logger(__name__)

_REPLAY_BUFFER: list[str] = []


@dataclass
class ThoughtNode:
    """A single logical step in a mathematical proof search tree."""
    problem_statement: str
    thought_step: str
    parent: ThoughtNode | None = None
    children: list[ThoughtNode] = field(default_factory=list)
    visits: int = 0
    total_value: float = 0.0
    predicted_value: float = 0.0
    rpe_delta: float = 0.0
    is_terminal: bool = False
    candidate_value: str | None = None
    pslq_relation: list[int] | None = None
    
    @property
    def uct_score(self) -> float:
        """Upper Confidence Bound applied to Trees (UCT)."""
        if self.visits == 0:
            return float('inf')
        
        exploitation = self.total_value / self.visits
        # If no parent or parent has no visits, exploration term is 0
        parent_visits = self.parent.visits if self.parent else 1
        exploration = math.sqrt(2.0 * math.log(max(1, parent_visits)) / self.visits)
        
        return exploitation + exploration

    def get_full_path(self) -> str:
        """Trace the logic from the root to this node."""
        path = []
        curr = self
        while curr:
            if curr.thought_step:
                path.append(curr.thought_step)
            curr = curr.parent
        return " -> ".join(reversed(path))


def expand_node(client: genai.Client, node: ThoughtNode, expansion_width: int = 3) -> None:
    """Generate multiple possible next logical steps using an LLM."""
    if node.is_terminal:
        return

    context = node.get_full_path()
    prompt = f"""
You are the Galois agent (SymBrain v10). You are solving the following problem:
{node.problem_statement}

Current logical progression:
{context if context else 'Starting state.'}

Propose {expansion_width} distinct logical next steps to continue this proof.
Format each step clearly on a new line prefixed with 'STEP:'.
Do not skip to the end; propose the immediate next rigorous mathematical deduction.
"""
    try:
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=prompt,
        )
        
        # Parse the 'STEP:' proposals
        proposals = [
            line.replace("STEP:", "").strip() 
            for line in response.text.split("\n") 
            if line.strip().startswith("STEP:")
        ]
        
        for p in proposals[:expansion_width]:
            child = ThoughtNode(
                problem_statement=node.problem_statement,
                thought_step=p,
                parent=node
            )
            
            # Lightweight syntactic Lean 4 check for pruning
            is_valid = True
            lean_tactics = ["by ", "simp", "rw", "omega", "ring", "exact", "apply"]
            if any(t in p for t in lean_tactics):
                try:
                    from agents.euler.tools.lean4_compiler import compile_lean4_proof
                    # Check if it has immediate compilation errors
                    dummy_code = f"theorem dummy : True := {p}"
                    res = compile_lean4_proof(dummy_code, timeout=5)
                    
                    # Zero-Sorry Guillotine: Check AST/Code for sorry tokens
                    if "sorry" in p or "sorryAx" in p or res.get("has_sorry", False):
                        child.is_terminal = True
                        child.total_value = -1.0
                        child.predicted_value = -1.0
                        child.candidate_value = "FAILED_OPEN_GAPS"
                        logger.warning("mcts_zero_sorry_guillotine_triggered", proposal=p)
                        node.children.append(child)
                        continue

                    # If type-checking fails with a clear type error, mark as invalid
                    if not res.get("success", False) and any(err in res.get("stderr", "") for err in ["type mismatch", "failed to synthesize", "application type mismatch"]):
                        is_valid = False
                        
                        # Trigger Alexandrie on Tactic Category Mismatches
                        # If a basic arithmetic tactic fails in a high-level domain, inject GraphRAG context
                        if any(t in p for t in ["omega", "ring", "linarith"]):
                            try:
                                from alexandrie.hub import AlexandrieHub
                                hub = AlexandrieHub()
                                docs = hub.search_vault("Mathlib.FieldTheory.Galois")
                                if docs:
                                    doc_content = hub.retrieve_artifact(docs[0].id)[1]
                                    # Inject GraphRAG Context directly into the problem statement for the next LLM prompt loop
                                    child.problem_statement += f"\n\n[GraphRAG Context Injected from Alexandrie]:\nYou attempted an arithmetic tactic ({p}) which caused a category mismatch. Here is the domain documentation:\n{doc_content[:1500]}\nSearch for explicit polynomials instead of guessing."
                                    logger.info("alexandrie_graphrag_injected", tactic=p)
                            except Exception as rag_err:
                                logger.error("graphrag_injection_failed", error=str(rag_err))
                except Exception:
                    pass
            
            if not is_valid:
                child.is_terminal = True
                child.total_value = -10.0
                child.predicted_value = -10.0
                logger.info("mcts_lean4_pruned_node", proposal=p)
            elif "QED" in p or "□" in p or "proved" in p.lower():
                child.is_terminal = True
                
            node.children.append(child)
            
    except Exception as e:
        logger.error("mcts_expansion_failed", error=str(e))


def process_reward_model_eval(client: genai.Client, node: ThoughtNode) -> float:
    """Process Reward Model (PRM) evaluation of a specific logical step.
    
    Critiques the *individual logical step* in the CoT and assigns a reward value in [0.0, 1.0].
    Heavily penalizes deductive leaps, logical fallacies, or unhandled edge cases.
    """
    context = node.get_full_path()
    prompt = f"""
You are a strict Process Reward Model (PRM). Evaluate the rigorousness of this specific mathematical step.
Problem:
{node.problem_statement}

Current Step Chain:
{context}

Does this chain contain logical fallacies (like backward induction)? Is it rigorous?
Respond with ONLY a float score between 0.0 (completely flawed/hallucinated) and 1.0 (rigorous and correct).
"""
    try:
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=prompt,
        )
        # Attempt to parse float
        import re
        match = re.search(r"0\.\d+|1\.0|0|1", response.text)
        if match:
            return float(match.group())
    except Exception as e:
        logger.error("mcts_evaluation_failed", error=str(e))
    
    # Fallback score if evaluation fails
    return 0.1


class MCTSReasoner:
    """Monte Carlo Tree Search Reasoner."""
    
    def __init__(self, max_iterations: int = 5, expansion_width: int = 3, cortex: Any = None, telemetry: Any = None, pslq_evaluator: Any = None):
        self.max_iterations = max_iterations
        self.expansion_width = expansion_width
        self.cortex = cortex
        self.telemetry = telemetry
        self.pslq_evaluator = pslq_evaluator
        self.client = genai.Client()

    def run(self, problem_statement: str, target_constant: Any = None, pslq_domain: str | None = None) -> str:
        """Execute the full Monte Carlo Tree Search thought engine."""
        import time
        start_time = time.monotonic()
        
        # Measure GPU power before MCTS loop
        power_before = 0.0
        nvml_enabled = False
        nvml_handle = None
        try:
            import pynvml
            pynvml.nvmlInit()
            nvml_enabled = True
            nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            power_before = pynvml.nvmlDeviceGetPowerUsage(nvml_handle) / 1000.0
        except Exception:
            pass

        root = ThoughtNode(problem_statement=problem_statement, thought_step="")
        
        for i in range(self.max_iterations):
            logger.info("mcts_iteration", iteration=i, max=self.max_iterations)
            
            # 1. Selection
            curr = root
            while curr.children and not curr.is_terminal:
                curr = max(curr.children, key=lambda c: c.uct_score)
                
            # 2. Expansion
            if not curr.is_terminal and curr.visits > 0 or curr == root:
                expand_node(self.client, curr, self.expansion_width)
                if curr.children:
                    curr = curr.children[0]
                    
            # 3. Simulation / PRM Evaluation
            reward = process_reward_model_eval(self.client, curr)
            
            # PSLQ Leaf Evaluation Override
            if self.pslq_evaluator and target_constant is not None:
                import re
                candidate_expr = curr.thought_step
                match = re.search(r"Candidate:\s*(.*)", curr.thought_step)
                if match:
                    candidate_expr = match.group(1).strip()
                
                pslq_result = self.pslq_evaluator.evaluate_candidate(target_constant, candidate_expr, domain=pslq_domain)
                if pslq_result.found and pslq_result.confidence == "EXACT":
                    reward = 1.0  # Override PRM with PSLQ certainty
                    curr.pslq_relation = pslq_result.relation
                    curr.candidate_value = candidate_expr
            
            # 4. Backpropagation
            back = curr
            while back:
                back.visits += 1
                v_s = back.predicted_value
                back.total_value += reward
                back.predicted_value = back.total_value / back.visits
                
                # Dopaminergic RPE delta: delta = target - V(s)
                gamma = 0.95
                target = reward if back == curr else reward + gamma * curr.predicted_value
                
                if self.cortex and hasattr(self.cortex, "calculate_reward_prediction_error"):
                    back.rpe_delta = self.cortex.calculate_reward_prediction_error(target, v_s)
                else:
                    back.rpe_delta = target - v_s
                
                # Hippocampal Replay: save high-RPE trajectories
                if abs(back.rpe_delta) > 0.5:
                    if self.cortex and hasattr(self.cortex, "record_to_hippocampal_replay"):
                        self.cortex.record_to_hippocampal_replay(back.get_full_path())
                    else:
                        _REPLAY_BUFFER.append(back.get_full_path())
                        if len(_REPLAY_BUFFER) > 50:
                            _REPLAY_BUFFER.pop(0)
                
                back = back.parent
                
        # Select best path
        best = root
        while best.children:
            best = max(best.children, key=lambda c: c.visits)
            
        # Measure GPU power after MCTS loop
        duration_seconds = time.monotonic() - start_time
        power_after = 0.0
        if nvml_enabled and nvml_handle:
            try:
                import pynvml
                power_after = pynvml.nvmlDeviceGetPowerUsage(nvml_handle) / 1000.0
                joules = ((power_before + power_after) / 2.0) * duration_seconds
                if self.telemetry and hasattr(self.telemetry, "record_gpu_energy"):
                    self.telemetry.record_gpu_energy(joules)
                logger.info("mcts_gpu_energy_consumption", duration_seconds=duration_seconds, joules=joules)
            except Exception as e:
                logger.error("mcts_gpu_energy_tracking_failed", error=str(e))

        return best.get_full_path()


def run_mcts(problem_statement: str, max_iterations: int = 5, expansion_width: int = 3) -> str:
    """Runs Monte Carlo Tree Search for proof generation and conjecture expansion.

    Args:
        problem_statement: The mathematical problem or conjecture to solve.
        max_iterations: The maximum number of MCTS iterations.
        expansion_width: The expansion width for generating child nodes.

    Returns:
        The best reasoning path found by MCTS.
    """
    reasoner = MCTSReasoner(max_iterations=max_iterations, expansion_width=expansion_width)
    return reasoner.run(problem_statement)
