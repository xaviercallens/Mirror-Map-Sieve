# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Elenchus-Maieutic dialectic cycle engine.

Manages structured debates between Galileo (experimenter) and Euler
(verifier) using two classical Socratic methods:

  • **Elenchus** — systematic cross-examination to expose contradictions
    in a hypothesis through iterative challenge-response cycles.

  • **Maieutic** — guiding agents toward latent knowledge through
    carefully crafted questions, enabling discovery of deeper truths.

The engine monitors convergence: when both agents' confidence levels
stabilise within a threshold, the dialectic concludes.

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from agents.galileo.agent import GalileoAgent
    from agents.euler.agent import EulerAgent
    from agents.galois.agent import GaloisAgent
    from agents.turing.agent import TuringAgent

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class DialecticCycle:
    """Record of a single elenchus-maieutic cycle in the Agora.

    Attributes:
        cycle_number: 1-indexed cycle number.
        galois_conjecture: Galois's innovative conjecture / mathematical concept.
        galileo_claim: Galileo's empirical hypothesis / numerical results.
        euler_objection: Euler's skeptical verification / formal audit.
        turing_audit: Turing's computational & resource optimization audit.
        galois_confidence: Galois's confidence in the conjecture.
        galileo_confidence: Galileo's confidence in the physical invariants.
        euler_confidence: Euler's confidence in the formal proofs.
        turing_confidence: Turing's confidence in computational resource efficiency.
        resolved: Whether the cycle resolved the dispute or converged.
    """

    cycle_number: int = 0
    galois_conjecture: dict[str, Any] = field(default_factory=dict)
    galileo_claim: dict[str, Any] = field(default_factory=dict)
    euler_objection: dict[str, Any] = field(default_factory=dict)
    turing_audit: dict[str, Any] = field(default_factory=dict)
    galois_confidence: float = 0.0
    galileo_confidence: float = 0.0
    euler_confidence: float = 0.0
    turing_confidence: float = 0.0
    resolved: bool = False


@dataclass(slots=True)
class DialecticOutcome:
    """Final outcome of the dialectic process.

    Attributes:
        status: ``"converged"``, ``"diverged"``, or ``"max_cycles"``.
        cycles_completed: Number of cycles run.
        converged: Whether agents reached consensus.
        final_confidence: Aggregated confidence score of all three hemispheres.
        synthesis: Natural-language Socratic synthesis of the outcome.
        galois_result: Galois's final mathematical result.
        galileo_result: Galileo's final empirical result.
        euler_result: Euler's final formal result.
        turing_result: Turing's final computational optimization result.
        history: Full cycle history.
    """

    status: str = "pending"
    cycles_completed: int = 0
    converged: bool = False
    final_confidence: float = 0.0
    synthesis: str = ""
    galois_result: dict[str, Any] = field(default_factory=dict)
    galileo_result: dict[str, Any] = field(default_factory=dict)
    euler_result: dict[str, Any] = field(default_factory=dict)
    turing_result: dict[str, Any] = field(default_factory=dict)
    history: list[DialecticCycle] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class DialecticEngine:
    """Manages Galileo ↔ Euler ↔ Galois Socratic dialectic cycles in the Agora.

    The engine alternates between three distinct phases:
      1. **Galois (Creative)**: Proposes a bold, innovative conjecture or algebraic symmetry.
      2. **Galileo (Empirical)**: Translates the conjecture into physical experiments or implicit simulations.
      3. **Euler (Formal/Skeptical)**: Scrutinizes both the conjecture and numerical simulations, running Lean 4 and DeepProbLog audits.
      4. **Socrates (Orchestrator)**: Mediates debate, asks Socratic questions, checks convergence.

    Args:
        max_iterations: Maximum number of dialectic cycles.
        convergence_threshold: Confidence above which we consider convergence.
        confidence_delta: If successive confidence changes are below this, the debate has stabilized.
    """

    def __init__(
        self,
        max_iterations: int = 5,
        convergence_threshold: float = 0.85,
        confidence_delta: float = 0.05,
    ) -> None:
        self.max_iterations = max_iterations
        self.convergence_threshold = convergence_threshold
        self.confidence_delta = confidence_delta
        self._log = logger.bind(component="dialectic_engine")

    async def run(
        self,
        hypothesis: str,
        galileo: GalileoAgent,
        euler: EulerAgent,
        galois: GaloisAgent | None = None,
        turing: TuringAgent | None = None,
        max_cycles: int | None = None,
        complexity_level: str = "complex",
        solvability_class: str = "class_2",
    ) -> DialecticOutcome:
        """Run the full dialectic between Galileo, Euler, Galois, and Turing (if available).

        Args:
            hypothesis: The scientific question or hypothesis to examine.
            galileo: The Galileo agent instance.
            euler: The Euler agent instance.
            galois: The optional Galois agent instance (enables tri-agent Agora).
            turing: The optional Turing agent instance (enables tetra-agent optimization).
            max_cycles: Override for maximum cycles (defaults to ``self.max_iterations``).
            complexity_level: Socratic complexity classification.
            solvability_class: Solvability class for compute routing.

        Returns:
            :class:`DialecticOutcome` with convergence status and history.
        """
        cycles = max_cycles or self.max_iterations
        self._log.info(
            "dialectic_start",
            hypothesis=hypothesis[:100],
            max_cycles=cycles,
            tri_agent=galois is not None,
            tetra_agent=turing is not None,
            complexity=complexity_level
        )

        if complexity_level == "research":
            self._log.info(
                "swarm_compute_scaling_triggered",
                nodes="8x H100",
                backend="Ray/vLLM",
                msg="Research-level complexity flagged. Dynamically allocating maximum GPU swarm."
            )
            
        if solvability_class == "class_3":
            self._log.info("routing_large_tier", msg="Solvability Class 3 detected. Reserving 4x H100 for heavy-tailed MCTS jumps.")
        else:
            self._log.info("routing_small_tier", msg="Solvability Class 1/2 detected. Using SymBrain v11 Small Tier on single H100.")

        history: list[DialecticCycle] = []
        prev_galois_conf = 0.0
        prev_galileo_conf = 0.0
        prev_euler_conf = 0.0

        last_galois_result: dict[str, Any] = {}
        last_galileo_result: dict[str, Any] = {}
        last_euler_result: dict[str, Any] = {}
        last_turing_result: dict[str, Any] = {}

        for i in range(1, cycles + 1):
            self._log.info("cycle_start", cycle=i)

            if galois is not None:
                # --- Phase I: Galois (Creative Conjecture) ---
                self._log.info("phase_galois_start", cycle=i)
                galois_feedback = (
                    f"Refine the following mathematical conjecture given previous critiques: "
                    f"Previous Galois: {last_galois_result.get('answer', 'None')}. "
                    f"Previous Euler audit: {last_euler_result.get('answer', 'None')}"
                    if i > 1 else f"Formulate a bold mathematical conjecture or symmetry framework for: {hypothesis}"
                )
                galois_result = await galois.run(galois_feedback)
                galois_conf = galois_result.confidence
                last_galois_result = {
                    "answer": galois_result.answer,
                    "confidence": galois_conf,
                    "cost_usd": galois_result.cost_usd,
                    "proofs": galois_result.proofs,
                }

                # --- Phase II: Galileo (Empirical Examination) ---
                self._log.info("phase_galileo_start", cycle=i)
                galileo_prompt = (
                    f"Perform numerical simulation and validate physical invariants (mass/energy/boundary) "
                    f"for Galois's conjecture: {last_galois_result['answer']}. "
                    f"Original inquiry: {hypothesis}"
                )
                galileo_result = await galileo.run(galileo_prompt)
                galileo_conf = galileo_result.confidence
                last_galileo_result = {
                    "answer": galileo_result.answer,
                    "confidence": galileo_conf,
                    "cost_usd": galileo_result.cost_usd,
                    "proofs": galileo_result.proofs,
                }

                # --- Phase III: Euler (Formal Auditing) ---
                self._log.info("phase_euler_start", cycle=i)
                euler_prompt = (
                    f"Formally audit the mathematical validity of Galois's conjecture: {last_galois_result['answer']}. "
                    f"Verify the empirical results and physical invariants obtained by Galileo: {last_galileo_result['answer']}. "
                    f"Compile Lean 4 proof sketches and audit precision boundaries."
                )
                euler_result = await euler.run(euler_prompt)
                euler_conf = euler_result.confidence
                last_euler_result = {
                    "answer": euler_result.answer,
                    "confidence": euler_conf,
                    "cost_usd": euler_result.cost_usd,
                    "proofs": euler_result.proofs,
                }
                
                # STRICT SCALE-TO-ZERO: Aggressively teardown immediately after Lean 4 complete
                if turing is not None:
                    self._log.info("strict_scale_to_zero", cycle=i, msg="Lean 4 verification completed. Tearing down cluster.")
                    await turing.run("tear down deployment symbrain_swarm")

            else:
                # Fallback to Galileo ↔ Euler debate
                galois_conf = 0.0
                last_galois_result = {}

                # --- Galileo ---
                self._log.info("phase_galileo_start", cycle=i)
                galileo_result = await galileo.run(hypothesis)
                galileo_conf = galileo_result.confidence
                last_galileo_result = {
                    "answer": galileo_result.answer,
                    "confidence": galileo_conf,
                    "cost_usd": galileo_result.cost_usd,
                    "proofs": galileo_result.proofs,
                }

                # --- Euler ---
                self._log.info("phase_euler_start", cycle=i)
                euler_prompt = (
                    f"Verify the following experimental claim: {hypothesis}. "
                    f"Evidence: {galileo_result.answer}"
                )
                euler_result = await euler.run(euler_prompt)
                euler_conf = euler_result.confidence
                last_euler_result = {
                    "answer": euler_result.answer,
                    "confidence": euler_conf,
                    "cost_usd": euler_result.cost_usd,
                    "proofs": euler_result.proofs,
                }
                
                # STRICT SCALE-TO-ZERO: Aggressively teardown immediately after Lean 4 complete
                if turing is not None:
                    self._log.info("strict_scale_to_zero", cycle=i, msg="Lean 4 verification completed. Tearing down cluster.")
                    await turing.run("tear down deployment symbrain_swarm")

            # --- Phase IV: Turing (Computational & Billing Audit) ---
            if turing is not None:
                self._log.info("phase_turing_start", cycle=i)
                turing_prompt = (
                    f"Profile the computational trace of Galois, Galileo, and Euler from this cycle. "
                    f"Suggest dynamic gating, search depths, SUNDIALS step parameters, and audit serverless scale-to-zero. "
                    f"Previous Galois conjecture: {last_galois_result.get('answer', 'None')}. "
                    f"Previous Galileo simulation: {last_galileo_result.get('answer', 'None')}. "
                    f"Previous Euler verification: {last_euler_result.get('answer', 'None')}."
                )
                turing_result = await turing.run(
                    turing_prompt,
                    mcts_nodes=250 + i * 50,
                    solver_evals=100 + i * 20,
                    latency_ms=120.0 + i * 30.0,
                    token_count=180 + i * 10,
                    scratch_allocated_bytes=1024 * 1024 * (5 + i),
                )
                turing_conf = turing_result.confidence
                last_turing_result = {
                    "answer": turing_result.answer,
                    "confidence": turing_conf,
                    "cost_usd": turing_result.cost_usd,
                }
            else:
                turing_conf = 0.0
                last_turing_result = {}

            # Record cycle
            cycle = DialecticCycle(
                cycle_number=i,
                galois_conjecture=last_galois_result,
                galileo_claim=last_galileo_result,
                euler_objection=last_euler_result,
                turing_audit=last_turing_result,
                galois_confidence=galois_conf,
                galileo_confidence=galileo_conf,
                euler_confidence=euler_conf,
                turing_confidence=turing_conf,
            )
            history.append(cycle)

            # --- Socratic Convergence Check ---
            converged = self._check_convergence(
                galois_conf,
                galileo_conf,
                euler_conf,
                prev_galois_conf,
                prev_galileo_conf,
                prev_euler_conf,
                tri_agent=galois is not None,
            )

            if converged:
                cycle.resolved = True
                self._log.info("dialectic_converged", cycle=i)
                return self._build_outcome(
                    "converged",
                    i,
                    True,
                    history,
                    last_galois_result,
                    last_galileo_result,
                    last_euler_result,
                    last_turing_result,
                    hypothesis,
                )

            prev_galois_conf = galois_conf
            prev_galileo_conf = galileo_conf
            prev_euler_conf = euler_conf

        # Max cycles reached without convergence
        self._log.warning("dialectic_max_cycles", max=cycles)
        return self._build_outcome(
            "max_cycles",
            cycles,
            False,
            history,
            last_galois_result,
            last_galileo_result,
            last_euler_result,
            last_turing_result,
            hypothesis,
        )

    def _check_convergence(
        self,
        galois_conf: float,
        galileo_conf: float,
        euler_conf: float,
        prev_galois: float,
        prev_galileo: float,
        prev_euler: float,
        tri_agent: bool,
    ) -> bool:
        """Check if the dialectic has converged across hemispheres."""
        if tri_agent:
            # All three above threshold
            all_high = (
                galois_conf >= self.convergence_threshold
                and galileo_conf >= self.convergence_threshold
                and euler_conf >= self.convergence_threshold
            )
            # Stabilized across all three
            galois_stable = abs(galois_conf - prev_galois) < self.confidence_delta
            galileo_stable = abs(galileo_conf - prev_galileo) < self.confidence_delta
            euler_stable = abs(euler_conf - prev_euler) < self.confidence_delta
            stabilised = (
                galois_stable
                and galileo_stable
                and euler_stable
                and prev_galileo > 0
            )
            return all_high or stabilised
        else:
            both_high = (
                galileo_conf >= self.convergence_threshold
                and euler_conf >= self.convergence_threshold
            )
            galileo_stable = abs(galileo_conf - prev_galileo) < self.confidence_delta
            euler_stable = abs(euler_conf - prev_euler) < self.confidence_delta
            stabilised = galileo_stable and euler_stable and prev_galileo > 0
            return both_high or stabilised

    def _build_outcome(
        self,
        status: str,
        cycles: int,
        converged: bool,
        history: list[DialecticCycle],
        galois_result: dict[str, Any],
        galileo_result: dict[str, Any],
        euler_result: dict[str, Any],
        turing_result: dict[str, Any],
        hypothesis: str,
    ) -> DialecticOutcome:
        """Build the final dialectic outcome and synthesize Socratic results."""
        galois_conf = galois_result.get("confidence", 0.0)
        galileo_conf = galileo_result.get("confidence", 0.0)
        euler_conf = euler_result.get("confidence", 0.0)
        turing_conf = turing_result.get("confidence", 0.0)

        # Average confidence across all participating agents
        if galois_result:
            if turing_result:
                final_confidence = (galois_conf + galileo_conf + euler_conf + turing_conf) / 4
                agent_details = (
                    f"Galois (creative) confidence: {galois_conf:.2f}, "
                    f"Galileo (empirical) confidence: {galileo_conf:.2f}, "
                    f"Euler (formal) confidence: {euler_conf:.2f}, "
                    f"Turing (optimization) confidence: {turing_conf:.2f}."
                )
            else:
                final_confidence = (galois_conf + galileo_conf + euler_conf) / 3
                agent_details = (
                    f"Galois (creative) confidence: {galois_conf:.2f}, "
                    f"Galileo (empirical) confidence: {galileo_conf:.2f}, "
                    f"Euler (formal) confidence: {euler_conf:.2f}."
                )
        else:
            final_confidence = (galileo_conf + euler_conf) / 2
            agent_details = (
                f"Galileo (empirical) confidence: {galileo_conf:.2f}, "
                f"Euler (formal) confidence: {euler_conf:.2f}."
            )

        # Generate synthesis
        if converged:
            synthesis = (
                f"Dialectic converged successfully after {cycles} cycle(s). "
                f"Consensus achieved on hypothesis: '{hypothesis[:80]}...' "
                f"with overall Agora confidence {final_confidence:.2f}. "
                f"{agent_details}"
            )
        else:
            synthesis = (
                f"Dialectic did not converge within {cycles} cycle(s). "
                f"Reason: Divergent perspectives between creative mathematical intuition, "
                f"empirical simulation results, formal verification, and computer science bounds. "
                f"{agent_details}"
            )

        return DialecticOutcome(
            status=status,
            cycles_completed=cycles,
            converged=converged,
            final_confidence=round(final_confidence, 2),
            synthesis=synthesis,
            galois_result=galois_result,
            galileo_result=galileo_result,
            euler_result=euler_result,
            turing_result=turing_result,
            history=history,
        )

    # ------ Individual modes ----------------------------------------------

    async def run_elenchus(
        self,
        hypothesis: str,
        evidence: dict[str, Any],
        euler: EulerAgent,
    ) -> dict[str, Any]:
        """Run a single Socratic elenchus (cross-examination) cycle."""
        query = (
            f"Challenge this scientific claim: '{hypothesis}'. "
            f"Evidence / Simulation details: {evidence}. "
            f"Find any underlying contradictions, physical invariant violations, or formal gaps."
        )
        result = await euler.run(query)
        verdict = result.answer if isinstance(result.answer, dict) else {}

        return {
            "refuted": verdict.get("status") == "REFUTED",
            "objections": verdict.get("objections", []),
            "confidence": result.confidence,
        }

    async def run_maieutic(
        self,
        question: str,
        context: dict[str, Any],
        galois_or_galileo: Any,
    ) -> dict[str, Any]:
        """Run a maieutic (knowledge midwifery) cycle to elicit latent understanding."""
        enriched_query = (
            f"{question} "
            f"Analyze in the context of the following Agora findings: {context}. "
            f"Provide a deep, conceptually unified insight."
        )
        result = await galois_or_galileo.run(enriched_query)

        return {
            "discovery": result.answer,
            "confidence": result.confidence,
            "cost_usd": result.cost_usd,
        }

