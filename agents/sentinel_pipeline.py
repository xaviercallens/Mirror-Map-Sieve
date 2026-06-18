# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Agora Sentinel Pipeline — Full Verification Orchestration.

The enterprise pipeline that chains all Sentinel agents:
  Bourbaki → Aristotle → Galois+Euler → Descartes|Champollion

This module provides:
  1. `SentinelPipeline` — orchestrates the full verification flow
  2. `PipelineResult` — structured result of a pipeline run
  3. FastAPI integration via `create_pipeline_endpoint()`

Reference: 🏛️ SPECIFICATION: The Bourbaki Translation Layer v21.
Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import os
from agents.common.secrets import get_secret
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

import structlog

from agents.bourbaki.agent import BourbakiAgent, BourbakiIR
from agents.aristotle.agent import AristotleAgent
from agents.descartes.agent import DescartesAgent, ExploitVector
from agents.champollion.agent import ChampollionAgent

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Result Types
# ---------------------------------------------------------------------------

class VerificationOutcome(Enum):
    """Outcome of the verification pipeline."""
    SECURE = auto()           # All theorems proven — Certificate issued
    VULNERABLE = auto()       # Proof failed — Advisory + exploit issued
    INCOMPLETE = auto()       # Budget exhausted — partial results
    PARSE_FAILURE = auto()    # Bourbaki failed to parse the source
    FILTERED = auto()         # Aristotle rejected the decomposition


@dataclass(slots=True)
class PipelineResult:
    """Structured result of a Sentinel Pipeline run.

    Attributes:
        outcome: High-level verification result.
        contract_name: Name of the verified contract.
        source_language: Source language (e.g., 'solidity').
        lean_code: Generated Lean 4 code.
        theorems: List of theorem names.
        report: Champollion-generated report (certificate or advisory).
        exploits: List of ExploitVector if vulnerabilities found.
        diagnostics: Warnings and info from the pipeline.
        elapsed_ms: Total pipeline time in milliseconds.
        compute_cost_usd: Estimated compute cost.
    """
    outcome: VerificationOutcome
    contract_name: str = ""
    source_language: str = ""
    lean_code: str = ""
    theorems: list[str] = field(default_factory=list)
    report: str = ""
    exploits: list[ExploitVector] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0
    compute_cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.name,
            "contract_name": self.contract_name,
            "source_language": self.source_language,
            "lean_code": self.lean_code,
            "theorems": self.theorems,
            "report": self.report,
            "exploits": [e.to_dict() for e in self.exploits],
            "diagnostics": self.diagnostics,
            "elapsed_ms": self.elapsed_ms,
            "compute_cost_usd": self.compute_cost_usd,
        }


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class SentinelPipeline:
    """Orchestrates the full Agora Sentinel verification pipeline.

    The pipeline is:
      1. **Bourbaki** — Translate source code → Lean 4 + sorry theorems
      2. **Aristotle** — (Optional) Pre-screen decomposition quality
      3. **Galois+Euler** — MCTS proof search to close sorry gaps
      4. **Descartes** — If proof fails, synthesize exploit
      5. **Champollion** — Generate executive report

    Steps 3-4 require a live Lean REPL and Galois MCTS engine. In this
    MVP implementation, they are represented as hook points. The pipeline
    returns the Lean code + report for manual or automated downstream use.
    """

    def __init__(
        self,
        bourbaki: BourbakiAgent | None = None,
        aristotle: AristotleAgent | None = None,
        descartes: DescartesAgent | None = None,
        champollion: ChampollionAgent | None = None,
    ) -> None:
        self.bourbaki = bourbaki or BourbakiAgent()
        self.aristotle = aristotle or AristotleAgent()
        self.descartes = descartes or DescartesAgent()
        self.champollion = champollion or ChampollionAgent()
        self._log = logger.bind(component="sentinel_pipeline")

    async def run(
        self,
        source_code: str,
        language: str = "solidity",
        contract_name: str | None = None,
        run_galois: bool = False,
    ) -> PipelineResult:
        """Execute the full Sentinel verification pipeline.

        Args:
            source_code: The source code to verify.
            language: Source language ('solidity', 'python', 'rust').
            contract_name: Override contract name detection.
            run_galois: If True, attempt to run Galois MCTS (requires Lean REPL).

        Returns:
            PipelineResult with the verification outcome.
        """
        t_start = time.perf_counter()
        diagnostics: list[str] = []

        # ======================================
        # Stage 1: Bourbaki — Source → Lean 4
        # ======================================
        self._log.info("pipeline_stage", stage=1, name="bourbaki")

        try:
            bourbaki_result = await self.bourbaki.run(
                source_code,
                language=language,
                contract_name=contract_name,
            )
            ir: BourbakiIR = bourbaki_result.answer.get("ir")
            lean_code: str = bourbaki_result.answer.get("lean_code", "")
            theorems: list[str] = bourbaki_result.answer.get("theorems", [])
            stage_diagnostics: list[str] = bourbaki_result.answer.get("diagnostics", [])
            diagnostics.extend(stage_diagnostics)
        except Exception as exc:
            self._log.error("bourbaki_failed", error=str(exc))
            return PipelineResult(
                outcome=VerificationOutcome.PARSE_FAILURE,
                diagnostics=[f"Bourbaki parse failure: {exc}"],
                elapsed_ms=(time.perf_counter() - t_start) * 1000,
            )

        detected_name = ir.contract_name if ir else (contract_name or "Unknown")

        if not lean_code:
            return PipelineResult(
                outcome=VerificationOutcome.PARSE_FAILURE,
                contract_name=detected_name,
                diagnostics=diagnostics + ["No Lean code generated"],
                elapsed_ms=(time.perf_counter() - t_start) * 1000,
            )

        # ======================================
        # Stage 2: Aristotle — Decomposition QA
        # ======================================
        self._log.info("pipeline_stage", stage=2, name="aristotle")
        diagnostics.append("Aristotle: wired as MCTS pre-filter in DAGSearchController")

        # ======================================
        # Stage 3: Galois — DAG-Aware MCTS Search
        # ======================================
        proof_succeeded = False
        dead_end_states: list[str] = []

        if run_galois:
            self._log.info("pipeline_stage", stage=3, name="galois_dag_search")

            try:
                from agents.galois.search.dag_search_controller import (
                    DAGSearchController,
                    SearchOutcome,
                )
                from agents.galois.search.dag_memory import GlobalLemmaCache
                from agents.galois.euler_bridge import EulerBridge

                # Initialize Euler REPL bridge
                lean_workspace = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "verifiers", "lean4",
                )
                euler = EulerBridge(workspace_dir=lean_workspace)
                repl_ready = euler.initialize()

                if not repl_ready:
                    diagnostics.append("Euler REPL: failed to initialize — falling back to offline mode")
                    euler = None

                # Build MCTSPolicy with Alexandrie RAG (if available)
                mcts_policy = None
                alexandrie_hub = None
                try:
                    from agents.galois.mcts_policy import MCTSPolicy
                    api_key = get_secret("GEMINI_API_KEY")
                    if api_key:
                        try:
                            from alexandrie.hub import AlexandrieHub
                            alexandrie_hub = AlexandrieHub(enable_semantic_memory=True)
                            diagnostics.append("Alexandrie RAG: enabled")
                        except Exception:
                            diagnostics.append("Alexandrie RAG: unavailable (non-critical)")

                        mcts_policy = MCTSPolicy(
                            api_key=api_key,
                            alexandrie_hub=alexandrie_hub,
                        )
                except Exception as exc:
                    diagnostics.append(f"MCTSPolicy: {exc}")

                # Create DAG search controller
                controller = DAGSearchController(
                    cache=GlobalLemmaCache(),
                    policy=mcts_policy,
                    aristotle=self.aristotle,
                    alexandrie_hub=alexandrie_hub,
                    lean_repl=euler,
                    max_iterations=1000,
                )

                # Run search for each sorry theorem
                for theorem_name in theorems:
                    goal = f"⊢ {theorem_name}"
                    self._log.info("dag_search_start", theorem=theorem_name)
                    result = controller.search(root_goal=goal)

                    if result.outcome == SearchOutcome.PROVEN:
                        diagnostics.append(f"✅ {theorem_name}: PROVEN ({result.elapsed_ms:.1f}ms)")
                    elif result.outcome == SearchOutcome.CONTRADICTION:
                        diagnostics.append(f"❌ {theorem_name}: CONTRADICTION found")
                        dead_end_states.extend(result.dead_end_states)
                    else:
                        diagnostics.append(f"⏳ {theorem_name}: {result.outcome.name}")

                # Determine overall result
                proof_succeeded = all(
                    f"✅ {t}:" in " ".join(diagnostics) for t in theorems
                )

                if euler:
                    euler.close()

            except ImportError as exc:
                diagnostics.append(f"DAG search: import error — {exc}")
            except Exception as exc:
                self._log.error("galois_search_failed", error=str(exc))
                diagnostics.append(f"Galois MCTS error: {exc}")
        else:
            diagnostics.append("Galois MCTS: skipped (run_galois=False)")

        # ======================================
        # Stage 4/5: Descartes or Champollion
        # ======================================
        exploits: list[ExploitVector] = []

        if proof_succeeded:
            # SUCCESS path → Champollion certificate
            self._log.info("pipeline_stage", stage=5, name="champollion_certificate")
            report = self.champollion.generate_certificate(
                contract_name=detected_name,
                theorems_proven=theorems,
                proof_summary=(
                    f"Galois MCTS proved all {len(theorems)} security invariants "
                    f"with zero sorry gaps."
                ),
                compute_cost_usd=0.0,
            )
            outcome = VerificationOutcome.SECURE
        elif dead_end_states:
            # FAILURE path → Descartes exploit + Champollion advisory
            self._log.info("pipeline_stage", stage=4, name="descartes_exploit")
            for state in dead_end_states:
                exploit = await self.descartes.synthesize_exploit(
                    dead_end_state=state,
                    source_language=language,
                    source_function="",
                )
                exploits.append(exploit)

            self._log.info("pipeline_stage", stage=5, name="champollion_advisory")
            report = self.champollion.generate_advisory(
                contract_name=detected_name,
                vulnerability_type=exploits[0].vulnerability_type if exploits else "unknown",
                severity=exploits[0].severity if exploits else "HIGH",
                exploit_description=exploits[0].english_description if exploits else "",
                exploit_payload=exploits[0].exploit_payload if exploits else "",
                affected_function=exploits[0].affected_function if exploits else "",
                remediation=exploits[0].remediation if exploits else "",
                cwe_id=exploits[0].cwe_id if exploits else "",
                lean_contradiction=dead_end_states[0] if dead_end_states else "",
            )
            outcome = VerificationOutcome.VULNERABLE
        else:
            # INCOMPLETE — sorry gaps remain, no exploit
            self._log.info("pipeline_stage", stage=5, name="champollion_preliminary")
            report = self.champollion.generate_certificate(
                contract_name=detected_name,
                theorems_proven=[f"{t} (PENDING)" for t in theorems],
                proof_summary=(
                    f"Bourbaki translated the source into Lean 4 with "
                    f"{len(theorems)} sorry gaps. Galois MCTS proof search "
                    f"not yet executed."
                ),
            )
            outcome = VerificationOutcome.INCOMPLETE

        elapsed = (time.perf_counter() - t_start) * 1000
        self._log.info(
            "pipeline_complete",
            outcome=outcome.name,
            contract=detected_name,
            theorems=len(theorems),
            elapsed_ms=elapsed,
        )

        return PipelineResult(
            outcome=outcome,
            contract_name=detected_name,
            source_language=language,
            lean_code=lean_code,
            theorems=theorems,
            report=report,
            exploits=exploits,
            diagnostics=diagnostics,
            elapsed_ms=elapsed,
        )
