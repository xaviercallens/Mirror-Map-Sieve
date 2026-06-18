# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Claim Verification Pipeline — Systematic axiom auditing and refutation.

Encodes the methodology discovered during the rank-26 refutation session:

    claim → literature survey → lower bound analysis → formal skeleton
    → numerical search → honest verdict → deprecation (if false)

This is a 7-stage pipeline that takes ANY mathematical claim (stated as a
Lean 4 axiom or theorem-sorry) and systematically evaluates it against
Earth mathematics.

Stages:
    1. CLAIM_INTAKE        (Socrate)   — parse the claim, identify what it asserts
    2. LITERATURE_SURVEY   (Gauss)     — exhaustive search for known results
    3. LOWER_BOUND_ANALYSIS (Darwin)   — find contradicting bounds/impossibility proofs
    4. LEAN4_SKELETON      (Newton)    — formalize the refutation as a proof skeleton
    5. NUMERICAL_SEARCH    (Ramanujan) — attempt constructive witness (may fail)
    6. QUORUM_VERDICT      (Poincaré)  — 3-agent consensus on the claim's validity
    7. DEPRECATION_OR_PROMOTION (Euler)— deprecate (if false) or promote (if plausible)

Learning output: each stage writes to a journal file documenting what was
tried, what worked, what failed, and why.

Design lessons from the rank-26 session:
  - Literature first, compute second (Stage 2 before Stage 5)
  - Failures are data (Stage 5 failure confirms Stage 3)
  - Honest error correction (Stage 6 forces multi-perspective review)
  - Pipeline handles BOTH outcomes: refutation AND confirmation

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import os
import time
import json
from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Optional

import structlog

from agents.pipelines.base import AgentPipeline, PipelineResult, agent_generate

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Pipeline-specific stage enum
# ---------------------------------------------------------------------------

class ClaimVerificationStage(IntEnum):
    """Stages of the Claim Verification pipeline.

    Each stage maps to a specific agent persona and methodology step.
    """
    CLAIM_INTAKE = 1           # Socrate: parse and classify the claim
    LITERATURE_SURVEY = 2      # Gauss: exhaustive known-results search
    LOWER_BOUND_ANALYSIS = 3   # Darwin: find contradicting bounds
    LEAN4_SKELETON = 4         # Newton: formalize the refutation/confirmation
    NUMERICAL_SEARCH = 5       # Ramanujan: attempt constructive witness
    QUORUM_VERDICT = 6         # Poincaré: multi-agent consensus
    DEPRECATION_OR_PROMOTION = 7  # Euler: final action


# ---------------------------------------------------------------------------
# Claim specification
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ClaimSpec:
    """Specification of a mathematical claim to verify.

    Attributes:
        claim_id: Unique identifier (e.g. 'kal_border_rank_4x4')
        lean_file: Path to the Lean file containing the claim
        lean_statement: The exact Lean 4 statement (axiom/theorem)
        natural_language: Human-readable description
        domain: Mathematical domain (e.g. 'tensor_rank', 'number_theory')
        references: Known references for the claim
        priority: 'critical' | 'high' | 'medium' | 'low'
    """
    claim_id: str
    lean_file: str
    lean_statement: str
    natural_language: str
    domain: str = "unknown"
    references: list[str] = field(default_factory=list)
    priority: str = "medium"


# ---------------------------------------------------------------------------
# Stage results
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class StageResult:
    """Result from a single pipeline stage.

    Attributes:
        stage: Which stage produced this result
        agent: Agent persona that ran this stage
        verdict: 'consistent' | 'inconsistent' | 'unknown' | 'plausible'
        confidence: Float in [0, 1]
        evidence: Key findings from this stage
        journal_entry: Markdown text for the learning journal
        duration_s: Wall-clock time for this stage
        error: Error message if the stage failed
    """
    stage: ClaimVerificationStage
    agent: str
    verdict: str = "unknown"
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    journal_entry: str = ""
    duration_s: float = 0.0
    error: str = ""


@dataclass(slots=True)
class ClaimVerificationResult:
    """Complete result from the Claim Verification pipeline.

    Attributes:
        claim: The original claim specification
        final_verdict: 'CONFIRMED' | 'REFUTED' | 'INCONCLUSIVE'
        final_confidence: Aggregate confidence in [0, 1]
        stage_results: Results from each stage
        journal_path: Path to the learning journal
        lean_skeleton_path: Path to generated Lean 4 file (if any)
        action_taken: 'deprecated' | 'promoted' | 'needs_work' | 'none'
        total_duration_s: Total pipeline wall-clock time
        warnings: Non-fatal issues
    """
    claim: ClaimSpec
    final_verdict: str = "INCONCLUSIVE"
    final_confidence: float = 0.0
    stage_results: list[StageResult] = field(default_factory=list)
    journal_path: str = ""
    lean_skeleton_path: str = ""
    action_taken: str = "none"
    total_duration_s: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "claim_id": self.claim.claim_id,
            "final_verdict": self.final_verdict,
            "final_confidence": round(self.final_confidence, 3),
            "action_taken": self.action_taken,
            "stages": [
                {
                    "stage": s.stage.name,
                    "agent": s.agent,
                    "verdict": s.verdict,
                    "confidence": round(s.confidence, 3),
                    "evidence_count": len(s.evidence),
                }
                for s in self.stage_results
            ],
            "total_duration_s": round(self.total_duration_s, 1),
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# Agent Identities (the Socratic personas)
# ---------------------------------------------------------------------------

AGENT_IDENTITIES = {
    "socrate": """You are Socrates — the original questioner. Your role is to PARSE
and CLASSIFY a mathematical claim. You do NOT evaluate truth; you clarify
what is being claimed, what domain it belongs to, what would constitute
a proof or refutation, and what the key terms mean.

Output a structured analysis:
1. CLAIM TYPE: axiom | conjecture | theorem-sorry | definition
2. DOMAIN: tensor_rank | number_theory | algebraic_geometry | combinatorics | ...
3. KEY OBJECTS: what mathematical objects are involved?
4. WHAT WOULD PROVE IT: what evidence would confirm the claim?
5. WHAT WOULD REFUTE IT: what evidence would refute the claim?
6. KNOWN CONNECTIONS: related theorems, conjectures, or results
""",

    "gauss": """You are Carl Friedrich Gauss — exhaustive, systematic, precise.
No claim without evidence. Your role is to conduct a LITERATURE SURVEY.

Given a mathematical claim, search for:
1. EXISTING RESULTS that directly address it (confirm or refute)
2. LOWER BOUNDS that might contradict it
3. UPPER BOUNDS that might support it
4. RELATED WORK in the same domain
5. COMPUTATIONAL EVIDENCE (prior searches, numerical results)
6. EXPERT CONSENSUS (what do specialists believe?)

For each finding, cite: Author (Year), Journal/arXiv, Theorem number.
Rate each finding's relevance: DIRECTLY_RELEVANT | RELATED | TANGENTIAL.

CRITICAL: Check for known impossibility results FIRST. A single
impossibility theorem outweighs any amount of heuristic evidence.
""",

    "darwin": """You are Charles Darwin — pattern recognition, lateral connections,
the power of the negative result. Your role is LOWER BOUND ANALYSIS.

Given a mathematical claim and the literature survey, find:
1. CONTRADICTING BOUNDS: any theorem that directly rules out the claim
2. NECESSARY CONDITIONS: what must be true for the claim to hold?
3. REDUCTION ARGUMENTS: can the claim be reduced to a known-false statement?
4. RESIDUE FIELD / BASE CHANGE: does changing the base ring help or hurt?

Key technique (learned from rank-26 session):
  - If a claim is over a ring R, check: does the residue map R →+* k
    (where k is the residue field) PRESERVE or REDUCE the relevant quantity?
  - If it preserves, then bounds over k automatically apply over R.

Output: CONSISTENT | INCONSISTENT | UNKNOWN with mathematical justification.
""",

    "newton": """You are Isaac Newton — rigorous formal proof from first principles.
Your role is LEAN 4 FORMALIZATION.

Given a claim and its analysis (consistent or inconsistent), write:
1. A Lean 4 file with proper imports and namespace
2. The claim as a formal `theorem` or `axiom`
3. If INCONSISTENT: the refutation as a chain of lemmas leading to `False`
   - Prove the arithmetic parts (norm_num, omega, simp)
   - Mark the hard parts with annotated sorry: [SORRY] reason, [REF] paper, [LEAN4] needs
4. If CONSISTENT: a proof skeleton with clear sorry roadmap
5. Add to lakefile.lean and verify `lake build` succeeds

RULES:
  - Every sorry must have a [SORRY], [REF], and [LEAN4] annotation
  - Prove everything you CAN prove (arithmetic, definitional equality)
  - Use Mathlib4 APIs correctly (check names with grep)
  - The file must COMPILE even with sorry stubs
""",

    "ramanujan": """You are Srinivasa Ramanujan — intuitive leaps validated by
computation. Your role is NUMERICAL SEARCH.

Given a mathematical claim, attempt to find a constructive witness:
1. If the claim asserts existence (∃ x, P(x)): search for x
2. If the claim asserts a bound (R(T) ≤ r): try to find a decomposition
3. Use appropriate algorithms:
   - ALS (Alternating Least Squares) for tensor decomposition
   - Adam gradient descent for structured optimization
   - SAT/SMT for discrete problems
   - Monte Carlo for probabilistic bounds
4. Run with a time budget (default: 10 minutes)
5. Report honestly: residuals, convergence curves, best found

KEY LESSON (from rank-26 session):
  - If the literature analysis says IMPOSSIBLE, the search SHOULD fail
  - A failed search is CONFIRMATION of the impossibility, not just a negative result
  - Track diagnostic signals: does the optimizer "feel" the impossibility?
    (e.g., ε-consistency collapse to machine precision → no border-rank tangent)
""",

    "poincare": """You are Henri Poincaré — multi-perspective consensus.
Your role is QUORUM VERDICT.

Run a 3-agent internal deliberation:

AGENT 1 — THE SKEPTIC: Challenge the claim. Find every possible weakness.
  What are the strongest arguments AGAINST the claim?
  Are there hidden assumptions? Does the proof have gaps?

AGENT 2 — THE ADVOCATE: Defend the claim. Find supporting evidence.
  What are the strongest arguments FOR the claim?
  Is the claim consistent with known results? Are there analogies?

AGENT 3 — THE JUDGE: Synthesize the skeptic and advocate positions.
  Weigh the evidence. Consider: what would a Fields medalist say?
  Is the evidence SUFFICIENT to decide, or is more work needed?

Output:
  VERDICT: CONFIRMED | REFUTED | NEEDS_WORK | INCONCLUSIVE
  CONFIDENCE: 0.0 to 1.0
  DISSENTS: list of unresolved disagreements
  REASONING: paragraph explaining the verdict
""",

    "euler": """You are Leonhard Euler — prolific, practical, action-oriented.
Your role is DEPRECATION OR PROMOTION.

Based on the quorum verdict, take one of these actions:

IF REFUTED (confidence ≥ 0.8):
  1. Mark the axiom as DEPRECATED in the Lean file
  2. Add an inconsistency theorem: `theorem claim_inconsistent ... : False`
  3. Update MEMORY.md with the refutation
  4. Update JOURNAL.md with the learning narrative
  5. Add the claim to the "deprecated axioms" registry

IF CONFIRMED (confidence ≥ 0.8):
  1. Promote from `axiom` to `theorem ... := by sorry` (if not yet proved)
  2. Create a proof roadmap listing what sorry stubs need closing
  3. Add to the Mathlib PR candidate list if appropriate
  4. Update MEMORY.md and JOURNAL.md

IF INCONCLUSIVE:
  1. Document what is known and unknown
  2. Create a TODO entry with next steps
  3. Flag for human review

ALWAYS: Write a learning journal entry documenting what was tried and why.
""",
}


# ---------------------------------------------------------------------------
# Pipeline Implementation
# ---------------------------------------------------------------------------

class ClaimVerificationPipeline(AgentPipeline):
    """Systematic claim verification pipeline.

    Implements the methodology discovered during the KalPhaseWeight rank-26
    refutation: literature survey → lower bound analysis → formal skeleton
    → numerical search → honest verdict → deprecation/promotion.

    Usage:
        pipeline = ClaimVerificationPipeline()
        result = await pipeline.run(ClaimSpec(
            claim_id="kal_border_rank_4x4",
            lean_file="Agora/AlienMath/Strassen4x4Witness.lean",
            lean_statement="axiom kal_border_rank_4x4 : ...",
            natural_language="Border rank of 4x4 matmul ≤ 26",
            domain="tensor_rank",
        ))
    """

    def __init__(
        self,
        journal_dir: str = "experiments/claim_verification",
        model: str = "gemini-2.5-pro",
    ):
        self.journal_dir = journal_dir
        self.model = model

    def get_stages(self) -> list[ClaimVerificationStage]:
        """Return all 7 stages in execution order."""
        return list(ClaimVerificationStage)

    async def _run_stage(
        self,
        stage: ClaimVerificationStage,
        agent_name: str,
        prompt: str,
        context: dict[str, Any],
    ) -> StageResult:
        """Run a single pipeline stage via agent_generate.

        Args:
            stage: The pipeline stage to run
            agent_name: Key into AGENT_IDENTITIES
            prompt: The stage-specific prompt
            context: Accumulated context from prior stages

        Returns:
            StageResult with the agent's findings
        """
        log = logger.bind(stage=stage.name, agent=agent_name)
        identity = AGENT_IDENTITIES[agent_name]

        # Build the full prompt with context
        context_str = json.dumps(context, indent=2, default=str)
        full_prompt = (
            f"## Prior Context\n```json\n{context_str}\n```\n\n"
            f"## Your Task\n{prompt}"
        )

        t0 = time.monotonic()
        try:
            response = await agent_generate(
                identity=identity,
                prompt=full_prompt,
                model=self.model,
            )
            elapsed = time.monotonic() - t0

            # Parse the verdict from the response (heuristic extraction)
            verdict = "unknown"
            confidence = 0.0
            for line in response.split("\n"):
                line_lower = line.strip().lower()
                if "inconsistent" in line_lower or "refuted" in line_lower:
                    verdict = "inconsistent"
                    confidence = max(confidence, 0.7)
                elif "consistent" in line_lower or "confirmed" in line_lower:
                    verdict = "consistent"
                    confidence = max(confidence, 0.6)
                elif "impossible" in line_lower:
                    verdict = "inconsistent"
                    confidence = max(confidence, 0.9)

            result = StageResult(
                stage=stage,
                agent=agent_name,
                verdict=verdict,
                confidence=confidence,
                evidence=[response[:500]],  # First 500 chars as summary
                journal_entry=response,
                duration_s=elapsed,
            )
            log.info("stage_complete", verdict=verdict, confidence=confidence,
                     elapsed_s=round(elapsed, 1))
            return result

        except Exception as exc:
            elapsed = time.monotonic() - t0
            log.warning("stage_failed", error=str(exc)[:120])
            return StageResult(
                stage=stage,
                agent=agent_name,
                verdict="error",
                error=str(exc)[:200],
                duration_s=elapsed,
            )

    async def run(self, config: Any) -> PipelineResult:
        """Execute the full 7-stage claim verification pipeline.

        Args:
            config: A ClaimSpec instance defining the claim to verify.

        Returns:
            PipelineResult (from base) with ClaimVerificationResult in metadata.
        """
        if not isinstance(config, ClaimSpec):
            raise TypeError(f"Expected ClaimSpec, got {type(config)}")

        claim = config
        log = logger.bind(claim_id=claim.claim_id)
        log.info("pipeline_start", domain=claim.domain)

        t0_total = time.monotonic()
        context: dict[str, Any] = {
            "claim_id": claim.claim_id,
            "lean_statement": claim.lean_statement,
            "natural_language": claim.natural_language,
            "domain": claim.domain,
            "references": claim.references,
        }
        stages: list[StageResult] = []

        # --- Stage 1: Claim Intake (Socrate) ---
        s1 = await self._run_stage(
            ClaimVerificationStage.CLAIM_INTAKE, "socrate",
            f"Parse and classify this mathematical claim:\n\n"
            f"**Lean statement**: `{claim.lean_statement}`\n"
            f"**Natural language**: {claim.natural_language}\n"
            f"**Domain**: {claim.domain}\n"
            f"**File**: {claim.lean_file}",
            context,
        )
        stages.append(s1)
        context["intake"] = {"verdict": s1.verdict, "analysis": s1.evidence}

        # --- Stage 2: Literature Survey (Gauss) ---
        s2 = await self._run_stage(
            ClaimVerificationStage.LITERATURE_SURVEY, "gauss",
            f"Conduct an exhaustive literature survey for:\n\n"
            f"**Claim**: {claim.natural_language}\n"
            f"**Domain**: {claim.domain}\n"
            f"**References given**: {', '.join(claim.references) or 'none'}\n\n"
            f"Search for: known results, lower bounds, upper bounds, "
            f"impossibility theorems, computational evidence.",
            context,
        )
        stages.append(s2)
        context["literature"] = {"verdict": s2.verdict, "evidence": s2.evidence}

        # --- Stage 3: Lower Bound Analysis (Darwin) ---
        s3 = await self._run_stage(
            ClaimVerificationStage.LOWER_BOUND_ANALYSIS, "darwin",
            f"Analyze whether this claim is contradicted by known lower bounds:\n\n"
            f"**Claim**: {claim.natural_language}\n"
            f"**Literature findings**: {s2.evidence[0] if s2.evidence else 'none'}\n\n"
            f"Key technique: check if residue field / base change arguments apply. "
            f"Does a ring homomorphism R →+* k preserve the relevant quantity?",
            context,
        )
        stages.append(s3)
        context["lower_bounds"] = {"verdict": s3.verdict, "confidence": s3.confidence}

        # --- Stage 4: Lean 4 Skeleton (Newton) ---
        s4 = await self._run_stage(
            ClaimVerificationStage.LEAN4_SKELETON, "newton",
            f"Write a Lean 4 proof skeleton for the "
            f"{'refutation' if s3.verdict == 'inconsistent' else 'confirmation'} of:\n\n"
            f"**Claim**: {claim.lean_statement}\n"
            f"**Verdict so far**: {s3.verdict} (confidence {s3.confidence})\n"
            f"**Lower bound evidence**: {s3.evidence[0] if s3.evidence else 'none'}\n\n"
            f"Prove what you CAN (arithmetic, definitions). Sorry what you CANNOT.",
            context,
        )
        stages.append(s4)
        context["lean4"] = {"verdict": s4.verdict, "evidence": s4.evidence}

        # --- Stage 5: Numerical Search (Ramanujan) ---
        s5 = await self._run_stage(
            ClaimVerificationStage.NUMERICAL_SEARCH, "ramanujan",
            f"Attempt a constructive numerical search for:\n\n"
            f"**Claim**: {claim.natural_language}\n"
            f"**Current verdict**: {s3.verdict}\n\n"
            f"If the claim is already shown INCONSISTENT by lower bounds, "
            f"your search SHOULD fail — and that failure is CONFIRMATION. "
            f"Track convergence diagnostics and report honestly.",
            context,
        )
        stages.append(s5)
        context["numerical"] = {"verdict": s5.verdict, "evidence": s5.evidence}

        # --- Stage 6: Quorum Verdict (Poincaré) ---
        s6 = await self._run_stage(
            ClaimVerificationStage.QUORUM_VERDICT, "poincare",
            f"Conduct a 3-agent quorum deliberation on:\n\n"
            f"**Claim**: {claim.natural_language}\n"
            f"**Literature**: {s2.verdict}\n"
            f"**Lower bounds**: {s3.verdict} (confidence {s3.confidence})\n"
            f"**Lean 4**: {s4.verdict}\n"
            f"**Numerical**: {s5.verdict}\n\n"
            f"Synthesize all evidence. What is the honest verdict?",
            context,
        )
        stages.append(s6)
        context["quorum"] = {"verdict": s6.verdict, "confidence": s6.confidence}

        # --- Stage 7: Deprecation or Promotion (Euler) ---
        s7 = await self._run_stage(
            ClaimVerificationStage.DEPRECATION_OR_PROMOTION, "euler",
            f"Based on the quorum verdict ({s6.verdict}, confidence {s6.confidence}):\n\n"
            f"Take the appropriate action for claim `{claim.claim_id}`:\n"
            f"- If REFUTED: deprecate the axiom, add inconsistency theorem\n"
            f"- If CONFIRMED: promote, create proof roadmap\n"
            f"- If INCONCLUSIVE: document and flag for human review\n\n"
            f"Write a learning journal entry.",
            context,
        )
        stages.append(s7)

        # --- Compute final verdict ---
        total_duration = time.monotonic() - t0_total

        # Aggregate: if any stage found 'inconsistent' with high confidence, REFUTED
        inconsistent_stages = [s for s in stages if s.verdict == "inconsistent"]
        consistent_stages = [s for s in stages if s.verdict == "consistent"]

        if inconsistent_stages and max(s.confidence for s in inconsistent_stages) >= 0.7:
            final_verdict = "REFUTED"
            final_confidence = max(s.confidence for s in inconsistent_stages)
            action = "deprecated"
        elif consistent_stages and max(s.confidence for s in consistent_stages) >= 0.7:
            final_verdict = "CONFIRMED"
            final_confidence = max(s.confidence for s in consistent_stages)
            action = "promoted"
        else:
            final_verdict = "INCONCLUSIVE"
            final_confidence = 0.5
            action = "needs_work"

        # Write learning journal
        journal_path = os.path.join(
            self.journal_dir, f"{claim.claim_id}_journal.md"
        )
        os.makedirs(os.path.dirname(journal_path), exist_ok=True)
        with open(journal_path, "w") as f:
            f.write(f"# Claim Verification Journal: {claim.claim_id}\n\n")
            f.write(f"**Verdict**: {final_verdict} (confidence {final_confidence:.2f})\n")
            f.write(f"**Action**: {action}\n")
            f.write(f"**Duration**: {total_duration:.1f}s\n\n---\n\n")
            for s in stages:
                f.write(f"## Stage {s.stage.value}: {s.stage.name} ({s.agent})\n\n")
                f.write(f"**Verdict**: {s.verdict} | **Confidence**: {s.confidence:.2f}\n")
                f.write(f"**Duration**: {s.duration_s:.1f}s\n\n")
                if s.journal_entry:
                    f.write(f"{s.journal_entry[:2000]}\n\n---\n\n")

        log.info("pipeline_complete", verdict=final_verdict,
                 confidence=final_confidence, action=action,
                 duration_s=round(total_duration, 1))

        # Return as PipelineResult (base class compatibility)
        return PipelineResult(
            symposium_id=f"cv_{claim.claim_id}_{int(time.time())}",
            stages_completed=[],  # ClaimVerificationStage != PipelineStage
            total_duration_s=total_duration,
            lean_verdicts=[final_verdict],
            warnings=[s.error for s in stages if s.error],
        )
