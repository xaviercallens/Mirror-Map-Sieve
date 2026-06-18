# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Archimedes Lemma Decomposition Agent.

Core innovation of SymBrain v15. Archimedes receives a Galois proof sketch
containing sorry stubs and decomposes it into a TREE of targeted sub-lemmas.
Each sub-lemma is attacked independently by a focused Galois call. Resolved
sub-lemmas are assembled back into the parent theorem.

Architecture:
    1. sorry_decomposer  — Parse every sorry context, classify gap type
    2. Galois (focused)  — Targeted single-lemma generation per gap
    3. proof_assembler   — Substitute resolutions into the parent sketch
    4. Euler (ZSG)       — Re-verify the assembled proof

The 'Method of Exhaustion' loop:
    - Round 1: All sorry gaps targeted simultaneously (parallel Galois calls)
    - Round 2: Remaining sorry gaps (those not resolved in Round 1)
    - Round 3: Final sweep — if gap survives 3 rounds it is classified INTRACTABLE

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from agents.base import AbstractAgent, AgentConfig, AgentResult, AgentRole
from agents.archimedes.tools.sorry_decomposer import decompose_sorry_gaps, SorryGap
from agents.archimedes.tools.proof_assembler import assemble_proof

logger = structlog.get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

# Maximum number of exhaustion rounds (increasing temperatures each round)
MAX_EXHAUSTION_ROUNDS = 3
MIN_EXHAUSTION_ROUNDS = MAX_EXHAUSTION_ROUNDS  # alias used in think() to cap rounds

# Temperature escalation per round: Round 1=precise, Round 2=creative, Round 3=bold
ROUND_TEMPERATURES = [0.70, 0.85, 0.95]

# Context window for each sorry gap (chars before and after the sorry keyword)
SORRY_CONTEXT_WINDOW = 120

# We only retry a gap if it was at least partially resolved in the previous round
# (i.e., sorry count dropped). Stagnant gaps after 1 round are classified INTRACTABLE.
STAGNATION_THRESHOLD = 0  # 0 = stop if no improvement in this round


# ── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class ExhaustionRound:
    """One round of the Archimedes sorry-exhaustion loop.

    Attributes:
        round_number: 1-indexed round counter.
        gaps_targeted: Number of sorry gaps targeted in this round.
        gaps_resolved: Number of gaps successfully closed.
        gaps_intractable: Gaps that could not be resolved (all 3 rounds failed).
        cost_usd: Cumulative Galois API cost for this round.
        lean4_sketch_after: The assembled proof after this round's substitutions.
        sorry_count_after: Number of remaining sorry stubs after this round.
    """
    round_number: int = 0
    gaps_targeted: int = 0
    gaps_resolved: int = 0
    gaps_intractable: int = 0
    cost_usd: float = 0.0
    lean4_sketch_after: str = ""
    sorry_count_after: int = 0


@dataclass
class ArchimedesResult:
    """Complete output from the Archimedes exhaustion process.

    Attributes:
        original_sorry_count: Stubs in the input sketch.
        final_sorry_count: Stubs remaining after all rounds.
        reduction: original - final (number of gaps closed).
        rounds: Detailed log of each exhaustion round.
        final_sketch: The best assembled Lean 4 sketch.
        intractable_gaps: List of gap descriptions that could not be resolved.
        total_cost_usd: Total Galois API cost for all rounds.
        elapsed_s: Wall-clock time for the full exhaustion process.
    """
    original_sorry_count: int = 0
    final_sorry_count: int = 0
    reduction: int = 0
    rounds: list[ExhaustionRound] = field(default_factory=list)
    final_sketch: str = ""
    intractable_gaps: list[str] = field(default_factory=list)
    total_cost_usd: float = 0.0
    elapsed_s: float = 0.0

    @property
    def improvement_pct(self) -> float:
        """Percentage of sorry gaps resolved."""
        if self.original_sorry_count == 0:
            return 100.0
        return self.reduction / self.original_sorry_count * 100.0


# ── Archimedes Agent ─────────────────────────────────────────────────────────

class ArchimedesAgent(AbstractAgent):
    """Lemma decomposition agent using the Method of Exhaustion.

    Archimedes bridges GaloisAgent (proof generation) and EulerAgent
    (verification) by adding an iterative refinement loop that progressively
    closes sorry gaps through targeted sub-lemma generation.
    """

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                name="archimedes",
                model="gemini-2.5-pro",
                role=AgentRole.MATHEMATICIAN,
                # Archimedes has higher budget: up to 3 Galois calls per sorry gap
                budget_limit=3.0,
                project_budget=400.0,
                timeout_ms=60_000,
                tools=["sorry_decomposer", "proof_assembler"],
            )
        super().__init__(config)

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """Plan the exhaustion rounds based on sorry gap analysis."""
        self._guard_iterations()
        start = self._start_timer()

        lean4_sketch: str = context.get("lean4_sketch", "")
        sorry_count = lean4_sketch.lower().count("sorry")

        plan = {
            "lean4_sketch": lean4_sketch,
            "sorry_count": sorry_count,
            "problem": context.get("problem", ""),
            "domain": context.get("domain", "unknown"),
            "max_rounds": min(MAX_EXHAUSTION_ROUNDS, sorry_count),  # Don't waste rounds on 0-sorry sketches
            "estimated_cost": 0.10 * sorry_count * MAX_EXHAUSTION_ROUNDS,
            "rationale": (
                f"Method of Exhaustion: {sorry_count} sorry gaps identified. "
                f"Planning {min(MAX_EXHAUSTION_ROUNDS, sorry_count)} rounds at "
                f"temperatures {ROUND_TEMPERATURES[:MIN_EXHAUSTION_ROUNDS]}."
            ),
        }

        self._check_budget(plan["estimated_cost"])
        self._stop_timer(start, "archimedes_think")
        return plan

    async def act(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Execute the Method of Exhaustion loop."""
        start = self._start_timer()
        result = await self._exhaustion_loop(
            lean4_sketch=plan["lean4_sketch"],
            problem=plan["problem"],
            domain=plan["domain"],
            max_rounds=plan["max_rounds"],
        )
        self._stop_timer(start, "archimedes_act")
        return {"exhaustion_result": result}

    async def run(self, query: str, **kwargs: Any) -> AgentResult:
        """Full Archimedes run: decompose → exhaust → assemble.

        Args:
            query: Problem description (used for Galois sub-prompts).
            **kwargs:
                lean4_sketch (str): The initial Galois sketch with sorry stubs.
                domain (str): Mathematical domain for context.

        Returns:
            AgentResult with assembled proof in answer dict.
        """
        self._log.info("archimedes_run_start", query=query[:80])
        start = self._start_timer()
        self._iteration = 0

        lean4_sketch = kwargs.get("lean4_sketch", "")
        domain = kwargs.get("domain", "unknown")

        if not lean4_sketch:
            # No sketch to refine — pass through unchanged
            return AgentResult(
                answer={"lean4_sketch": "", "archimedes_result": None, "sorry_count": 0},
                confidence=0.0,
                cost_usd=0.0,
            )

        context = {"lean4_sketch": lean4_sketch, "problem": query, "domain": domain}
        plan = await self.think(context)
        observations = await self.act(plan)

        result: ArchimedesResult = observations["exhaustion_result"]
        actual_cost = result.total_cost_usd
        self._record_cost(actual_cost)

        elapsed = self._stop_timer(start, "archimedes_run_total")
        logger.info(
            "archimedes_run_complete",
            original_sorry=result.original_sorry_count,
            final_sorry=result.final_sorry_count,
            reduction=result.reduction,
            improvement_pct=f"{result.improvement_pct:.1f}%",
            rounds=len(result.rounds),
            cost_usd=round(actual_cost, 3),
        )

        return AgentResult(
            answer={
                "lean4_sketch": result.final_sketch,
                "archimedes_result": result,
                "sorry_count": result.final_sorry_count,
                "original_sorry_count": result.original_sorry_count,
                "reduction": result.reduction,
                "improvement_pct": result.improvement_pct,
                "intractable_gaps": result.intractable_gaps,
            },
            confidence=max(0.0, min(1.0, 1.0 - (result.final_sorry_count / max(1, result.original_sorry_count)) * 0.5)),
            cost_usd=actual_cost,
            telemetry={**self.telemetry.summary(), "total_elapsed_ms": round(elapsed, 2)},
        )

    # ── Private: Method of Exhaustion ────────────────────────────────────────


    def _split_lean_declarations(self, content: str) -> list[str]:
        # Split Lean 4 into declarations heuristically
        pattern = r'^(import |def |theorem |lemma |instance |class |structure |open |namespace |end |section |variable |abbrev |example |noncomputable def |noncomputable theorem )'
        parts = re.split(pattern, content, flags=re.MULTILINE)
        
        decls = []
        if parts:
            if parts[0].strip():
                decls.append(parts[0])
            for i in range(1, len(parts), 2):
                decls.append(parts[i] + parts[i+1])
                
        return decls

    async def _exhaustion_loop(
        self,
        lean4_sketch: str,
        problem: str,
        domain: str,
        max_rounds: int,
    ) -> ArchimedesResult:
        """Core exhaustion loop: attack sorry gaps using MCTS and LeanREPL."""
        import time
        from agents.galois.lean_repl import LeanREPL
        from agents.galois.mcts_node import ProofNode
        from agents.galois.mcts_policy import MCTSPolicy

        start = time.monotonic()
        original_sorry_count = lean4_sketch.count("sorry")
        current_sketch = lean4_sketch
        total_cost = 0.0
        rounds = []
        all_intractable = []

        policy = MCTSPolicy()
        
        # Instantiate REPL once per exhaustion loop
        import pathlib
        workspace_dir = str(pathlib.Path(__file__).resolve().parent.parent.parent / "verifiers" / "lean4")
        repl = LeanREPL(workspace_dir=workspace_dir)
        
        for round_num in range(1, max_rounds + 1):
            sorry_count_before = current_sketch.count("sorry")
            if sorry_count_before == 0:
                logger.info("archimedes_early_exit", reason="all_gaps_resolved", round=round_num)
                break
                
            logger.info(
                "archimedes_round_start",
                round=round_num,
                sorry_count=sorry_count_before
            )
            
            # Clean up mid-file imports which break the Lean 4 REPL
            lines = current_sketch.split('\n')
            imports = []
            rest = []
            for line in lines:
                if line.strip().startswith('import '):
                    imports.append(line)
                else:
                    rest.append(line)
            
            # Deduplicate imports and preserve order
            seen_imports = set()
            unique_imports = []
            for imp in imports:
                if imp not in seen_imports:
                    unique_imports.append(imp)
                    seen_imports.add(imp)
                    
            current_sketch = '\n'.join(unique_imports + rest)
            
            init_res = repl.init_proof(current_sketch)
            
            if "sorries" not in init_res or len(init_res["sorries"]) == 0:
                logger.warning("archimedes_no_gaps_found", round=round_num)
                if "messages" in init_res:
                    for msg in init_res["messages"]:
                        if msg.get("severity") == "error":
                            all_intractable.append(f"Compiler Error: {msg.get('data')}")
                break
                
            target_sorry = init_res["sorries"][0]
            root_state_id = target_sorry["proofState"]
            root_goal = target_sorry["goal"]
            
            root_node = ProofNode(state_id=root_state_id, goal_state=root_goal)
            
            max_mcts_iterations = 10
            solution_tactics = None
            round_cost = 0.0
            
            for i in range(max_mcts_iterations):
                curr = root_node
                while curr.children:
                    best_child = None
                    best_score = float('-inf')
                    for child in curr.children:
                        score = child.uct_score()
                        if score > best_score:
                            best_score = score
                            best_child = child
                    if best_child is None or best_score == float('-inf'):
                        break
                    curr = best_child
                    
                if curr.is_terminal:
                    tactics = []
                    temp = curr
                    while temp.parent is not None:
                        tactics.append(temp.tactic_applied)
                        temp = temp.parent
                    solution_tactics = list(reversed(tactics))
                    break
                    
                if curr.is_dead_end or (curr.parent and curr.children and all(c.is_dead_end for c in curr.children)):
                    curr.is_dead_end = True
                    temp = curr
                    while temp:
                        temp.visits += 1
                        temp = temp.parent
                    continue
                    
                tactics = policy.generate_tactics(curr.goal_state)
                round_cost += 0.02
                
                if not tactics:
                    curr.is_dead_end = True
                    continue
                    
                for tactic in tactics:
                    res = repl.execute_tactic(curr.state_id, tactic)
                    is_error = False
                    if "messages" in res:
                        for msg in res["messages"]:
                            if msg.get("severity") == "error":
                                is_error = True
                                break
                    if is_error or "proofState" not in res:
                        child_node = ProofNode(state_id=-1, goal_state="", parent=curr, tactic_applied=tactic)
                        child_node.is_dead_end = True
                        curr.children.append(child_node)
                    else:
                        new_state_id = res["proofState"]
                        new_goal = res["goals"][0] if res.get("goals") else ""
                        child_node = ProofNode(state_id=new_state_id, goal_state=new_goal, parent=curr, tactic_applied=tactic)
                        curr.children.append(child_node)
                        
                        if child_node.is_terminal:
                            tactics_list = []
                            temp_n = child_node
                            while temp_n.parent is not None:
                                tactics_list.append(temp_n.tactic_applied)
                                temp_n = temp_n.parent
                            solution_tactics = list(reversed(tactics_list))
                            break
                            
                if solution_tactics:
                    break
                    
                temp = curr
                while temp:
                    temp.visits += 1
                    temp = temp.parent
                    
            total_cost += round_cost
            
            sorry_count_after = sorry_count_before
            intractable_this_round = 0
            
            if solution_tactics:
                tactic_str = "\n  ".join(solution_tactics)
                replacement = f"by {{\n  {tactic_str}\n}}"
                current_sketch = current_sketch.replace("sorry", replacement, 1)
                sorry_count_after -= 1
                logger.info("archimedes_gap_resolved", round=round_num)
            else:
                intractable_this_round = 1
                all_intractable.append(f"MCTS failed for goal: {root_goal[:80]}")
                logger.warning("archimedes_gap_not_resolved", round=round_num)
                current_sketch = current_sketch.replace("sorry", "sorry -- INTRACTABLE", 1)
                
            round_result = ExhaustionRound(
                round_number=round_num,
                gaps_targeted=1,
                gaps_resolved=1 if solution_tactics else 0,
                gaps_intractable=intractable_this_round,
                cost_usd=round_cost,
                lean4_sketch_after=current_sketch,
                sorry_count_after=sorry_count_after,
            )
            rounds.append(round_result)
            
            logger.info(
                "archimedes_round_complete",
                round=round_num,
                sorry_before=sorry_count_before,
                sorry_after=sorry_count_after,
                cost_usd=round(round_cost, 3),
            )
            
            if not solution_tactics:
                break
                
        current_sketch = current_sketch.replace("sorry -- INTRACTABLE", "sorry")
        final_sorry = current_sketch.count("sorry")
        elapsed = time.monotonic() - start

        return ArchimedesResult(
            original_sorry_count=original_sorry_count,
            final_sorry_count=final_sorry,
            reduction=original_sorry_count - final_sorry,
            rounds=rounds,
            final_sketch=current_sketch,
            intractable_gaps=all_intractable[:20],
            total_cost_usd=total_cost,
            elapsed_s=elapsed,
        )

    async def _attack_single_gap(
        self,
        gap: SorryGap,
        problem: str,
        domain: str,
        temperature: float,
        round_num: int,
        compiler_feedback: str = "",
    ) -> tuple[str, float]:
        """Attack a single sorry gap with a targeted Galois call.

        Returns:
            Tuple of (resolved Lean 4 fragment, cost in USD).
            If resolution fails or still contains sorry, returns ("", cost).
        """
        import os, json as _json, re as _re, httpx

        # Build a FOCUSED prompt for this specific gap
        # This is much more effective than the global conjecture prompt
        feedback_section = f"\n\n## Compiler Feedback from Previous Attempt\n{compiler_feedback}\nReflect on why this error occurred and provide a valid proof fragment." if compiler_feedback else ""

        gap_prompt = f"""You are Galois, a SKEPTICAL MATHEMATICIAN filling in a single `sorry` stub in a Lean 4 proof.

## Mathematical Context
Domain: {domain}
Problem: {problem[:300]}

## The Sorry Gap (Round {round_num} — Temperature: creative)
Gap Type: {gap.gap_type}
Mathematical Claim: {gap.claim_description}

## Surrounding Lean 4 Context
```lean4
...{gap.context_before}
sorry  ← THIS IS THE GAP TO FILL
{gap.context_after}...
```
{feedback_section}
## Your Task
Replace the `sorry` with a valid Lean 4 proof fragment.
- Use real Mathlib4 tactics: `simp`, `ring`, `omega`, `norm_num`, `exact?`, `apply?`
- If the claim requires a lemma, provide the lemma first (as `have lemma_name : ... := by ...`)
- If the claim is GENUINELY unprovable with current Mathlib4, respond with exactly: INTRACTABLE
- Do NOT use `sorry` in your response
- Respond ONLY with the Lean 4 proof fragment (no markdown fences, no explanation)

Lean 4 proof fragment:"""

        # Try Gemini first (primary), Mistral second (diversity)
        api_key = os.getenv("GALOIS_GEMINI_KEY") or os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            return "", 0.0

        try:
            # Import Gemini client
            from agents.galois.auth import GaloisAuthManager
            auth = GaloisAuthManager()
            if auth.gemini_client is None:
                return "", 0.0

            response = auth.gemini_client.generate_content(gap_prompt)
            raw = response.text.strip()

            # Check if the model says it's intractable
            if "INTRACTABLE" in raw[:20]:
                return "", 0.02  # Small cost for the API call

            # Strip any markdown fences the model might have added
            raw = _re.sub(r"```(?:lean4?|lean)?\n?", "", raw).strip().rstrip("`").strip()

            # Validate: no sorry stubs
            if "sorry" in raw.lower():
                # Model still produced sorry — not resolved
                return "", 0.02

            return raw, 0.05  # $0.05 per successful gap attack

        except Exception as e:
            logger.warning("archimedes_gap_attack_failed", exc_info=True, error=str(e)[:100], gap_type=gap.gap_type)
            return "", 0.01


# MIN_EXHAUSTION_ROUNDS is defined at module top (line 45) to be available in think().
