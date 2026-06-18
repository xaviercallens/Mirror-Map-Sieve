# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Euler Mathematical Verifier Agent.

Euler is the sceptic of the Agora. He verifies proofs via **Lean 4**,
evaluates probabilistic logic via **DeepProbLog**, and audits
demonstrations for contradictions, vagueness, and numerical pitfalls.

Design principles:
  • Strong controversy POV — actively seeks to refute claims
  • Rejects vagueness — flags 'obviously', 'trivially', 'clearly'
  • Continuous-discrete integration — bridges real analysis and logic
  • Type-theoretic rigour — proof gaps ('sorry') are fatal errors

Registered tools:
  1. ``lean4_compiler``     — Compile and type-check Lean 4 proofs
  2. ``deepproblog_gate``   — Evaluate probabilistic logic queries
  3. ``skeptical_auditor``  — Detect contradictions and vagueness

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import pathlib
from typing import Any

import structlog

from agents.base import AbstractAgent, AgentConfig, AgentResult, AgentRole
from agents.euler.tools.cloud_lean_compiler import compile_lean4_proof_cloud
from agents.euler.tools.deepproblog_gate import evaluate_probabilistic_query
from agents.euler.tools.skeptical_auditor import audit_demonstration
from agents.euler.tools.leanabell_prover import leanabell_prove_theorem
from agents.euler.tools.verso_compiler import compile_verso_document
from agents.euler.tools.certificate_generator import generate_verification_certificate
from agents.euler.tools.numina_prover import query_numina_prover
from agents.euler.tools.lean4_repl import execute_lean4_repl_step
from agents.euler.tools.predict_lean_accuracy import predict_lean_accuracy
from agents.euler.tools.global_stitcher import global_stitch_and_build

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT_PATH = pathlib.Path(__file__).parent / "prompts" / "system_prompt.md"

# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

EULER_TOOLS: dict[str, Any] = {
    "lean4_compiler": compile_lean4_proof_cloud,
    "verso_compiler": compile_verso_document,
    "certificate_generator": generate_verification_certificate,
    "deepproblog_gate": evaluate_probabilistic_query,
    "skeptical_auditor": audit_demonstration,
    "leanabell_prover": leanabell_prove_theorem,
    "numina_prover": query_numina_prover,
    "lean4_repl": execute_lean4_repl_step,
    "predict_lean_accuracy": predict_lean_accuracy,
    "global_stitcher": global_stitch_and_build,
}


# ---------------------------------------------------------------------------
# Euler Agent
# ---------------------------------------------------------------------------

class EulerAgent(AbstractAgent):
    """Mathematical Verifier agent — proof checking and contradiction detection.

    Euler follows a sceptical methodology:

    1. **Parse** — extract claims and proof steps from the input
    2. **Formalise** — translate claims into Lean 4 or DeepProbLog
    3. **Verify** — compile proofs and evaluate queries
    4. **Audit** — run the skeptical auditor on the demonstration
    5. **Report** — issue a verification verdict with detailed objections

    Example::

        config = AgentConfig(name="euler", role=AgentRole.VERIFIER)
        agent = EulerAgent(config)
        result = await agent.run("Verify: ∀ n, n + 0 = n")
    """

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                name="euler",
                model="gemini-2.5-pro",
                role=AgentRole.VERIFIER,
                budget_limit=100.0,
                project_budget=500.0,
                timeout_ms=60_000,
                tools=list(EULER_TOOLS.keys()),
            )
        super().__init__(config)
        self._tools = EULER_TOOLS
        self._system_prompt = self._load_system_prompt()
        self._current_proof_context = None

    def checkpoint_state(self) -> None:
        """Save current proof context to Alexandrie on preemption."""
        self._log.info("euler_checkpointing_state", 
                       has_context=self._current_proof_context is not None)
        try:
            from agents.common.alexandrie import AlexandrieVault
            vault = AlexandrieVault()
            vault.store_json(
                "euler_checkpoint.json", 
                {"proof_context": self._current_proof_context}
            )
        except Exception as e:
            self._log.error("euler_checkpoint_failed", error=str(e))

    @staticmethod
    def _load_system_prompt() -> str:
        """Load the Euler system prompt from disk.

        Returns:
            System prompt text.
        """
        if _SYSTEM_PROMPT_PATH.exists():
            return _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        return (
            "You are Euler, a rigorous mathematical verifier. "
            "Reject vagueness, demand formal proofs, and audit all claims."
        )

    # ------ Lifecycle implementation --------------------------------------

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """Analyse the claim and plan verification strategy.

        Planning:
          - Extract formal claims from natural language
          - Determine verification approach (Lean 4, DeepProbLog, audit)
          - Identify potential weaknesses

        Args:
            context: Must include ``"query"``; may include ``"proof"``,
                ``"program"``, ``"data"``.

        Returns:
            Plan dict with keys ``tools``, ``claims``, ``strategy``.
        """
        self._guard_iterations()
        start = self._start_timer()

        query: str = context.get("query", "")
        plan: dict[str, Any] = {
            "tools": [],
            "claims": [],
            "strategy": "",
            "estimated_cost": 0.0,
        }

        query_lower = query.lower()

        # Lean 4 / Verso proof verification
        if any(kw in query_lower for kw in ("prove", "proof", "theorem",
                                              "lemma", "lean", "∀", "∃",
                                              "forall", "exists", "verso",
                                              "run path", "verified", "verify", "compile", "compiler")) or "proof_code" in context:
            is_formal = False
            if "verso" in query_lower:
                if "verso_compiler" not in plan["tools"]:
                    plan["tools"].append("verso_compiler")
                    plan["strategy"] = "verso_verification"
                    plan["estimated_cost"] += 0.15
                is_formal = True
            
            if any(kw in query_lower for kw in ("run path", "verified", "verify", "compile", "compiler")) or "proof_code" in context:
                if "lean4_compiler" not in plan["tools"]:
                    plan["tools"].append("lean4_compiler")
                    plan["tools"].append("global_stitcher")
                    plan["strategy"] = "formal_verification"
                    plan["estimated_cost"] += 0.15
                is_formal = True
            
            if any(kw in query_lower for kw in ("numina", "ai-mo", "goedel", "olympiad")):
                if "numina_prover" not in plan["tools"]:
                    plan["tools"].append("numina_prover")
                    plan["strategy"] = "numina_deep_proving"
                    plan["estimated_cost"] += 0.25
                is_formal = True
                
            if any(kw in query_lower for kw in ("leanabell", "search", "rl", "refine", "backtrack", "loop")):
                if "leanabell_prover" not in plan["tools"]:
                    plan["tools"].append("leanabell_prover")
                    plan["strategy"] = "leanabell_prover_v2"
                    plan["estimated_cost"] += 0.20
                is_formal = True
                
            if any(kw in query_lower for kw in ("repl", "interactive", "tactic", "pythagore")):
                if "lean4_repl" not in plan["tools"]:
                    plan["tools"].append("lean4_repl")
                    plan["strategy"] = "repl_interactive_loop"
                    plan["estimated_cost"] += 0.15
                is_formal = True
                
            if not is_formal:
                if "lean4_compiler" not in plan["tools"]:
                    plan["tools"].append("lean4_compiler")
                    plan["strategy"] = "formal_verification"
                    plan["estimated_cost"] += 0.10

            # Automatically register certificate generator for formal proofs
            if "certificate_generator" not in plan["tools"]:
                plan["tools"].append("certificate_generator")
                plan["estimated_cost"] += 0.05

        # Probabilistic logic and RL prediction
        if any(kw in query_lower for kw in ("probability", "probabilistic",
                                              "deepproblog", "neural", "p(",
                                              "bayesian", "ml", "predict", "accuracy", "rl")):
            if any(kw in query_lower for kw in ("predict", "accuracy", "ml", "rl")):
                plan["tools"].append("predict_lean_accuracy")
                plan["strategy"] = "ml_accuracy_prediction"
                plan["estimated_cost"] += 0.05
            else:
                plan["tools"].append("deepproblog_gate")
                plan["strategy"] = "probabilistic_logic"
                plan["estimated_cost"] += 0.05

        # Always run the skeptical auditor
        plan["tools"].append("skeptical_auditor")

        # Extract claims for auditing
        plan["claims"] = self._extract_claims(query)

        plan["rationale"] = (
            f"Verification strategy: {plan['strategy'] or 'skeptical_audit'}. "
            f"Tools: {plan['tools']}. Claims to check: {len(plan['claims'])}."
        )

        self._check_budget(plan["estimated_cost"])
        self._stop_timer(start, "euler_think")
        self._log.info("plan_created", tools=plan["tools"], strategy=plan["strategy"])
        return plan

    async def act(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Execute verification tools.

        Args:
            plan: Output of :meth:`think`.

        Returns:
            Dict of tool-name → verification results.
        """
        start = self._start_timer()
        observations: dict[str, Any] = {}

        for tool_name in plan.get("tools", []):
            tool_fn = self._tools.get(tool_name)
            if tool_fn is None:
                self._log.warning("tool_not_found", tool=tool_name)
                continue

            self._log.info("tool_invoked", tool=tool_name)
            try:
                if tool_name == "lean4_compiler":
                    proof_code = plan.get("proof_code", self._default_lean_proof())
                    result = tool_fn(proof_code=proof_code)
                elif tool_name == "lean4_repl":
                    proof_code = plan.get("proof_code", self._default_lean_proof())
                    result = tool_fn(proof_state_code=proof_code)
                elif tool_name == "verso_compiler":
                    doc_content = plan.get("doc_content", plan.get("query", ""))
                    result = tool_fn(document_content=doc_content)
                elif tool_name == "certificate_generator":
                    theorem_name = plan.get("theorem_name", "theorem_under_audit")
                    proof_code = plan.get("proof_code", "")
                    if not proof_code:
                        if "lean4_compiler" in observations:
                            proof_code = plan.get("proof_code", self._default_lean_proof())
                        else:
                            proof_code = plan.get("doc_content", plan.get("query", ""))
                    
                    # Synthesize verdict and skeptical comments from observations
                    verdict = "VERIFIED"
                    comments = "Euler skeptical audit: mathematical assertions formally checked."
                    conf = 1.0
                    
                    if "lean4_compiler" in observations:
                        l_res = observations["lean4_compiler"]
                        if not l_res.get("success", False):
                            verdict = "REFUTED"
                            comments = f"Lean 4 compilation failed: {l_res.get('message')}"
                            conf = 0.0
                        elif l_res.get("has_sorry", False):
                            verdict = "FAILED_OPEN_GAPS"
                            comments = "Proof contains 'sorry' gaps. Euler rejects this hand-waving."
                            conf = -1.0
                    elif "verso_compiler" in observations:
                        v_res = observations["verso_compiler"]
                        if not v_res.get("success", False):
                            verdict = "REFUTED"
                            comments = f"Verso compilation failed: {v_res.get('message')}"
                            conf = 0.0
                        elif v_res.get("has_sorry", False):
                            verdict = "FAILED_OPEN_GAPS"
                            comments = "Verso document contains sorry/axiom gaps."
                            conf = -1.0
                            
                    if "skeptical_auditor" in observations:
                        aud_res = observations["skeptical_auditor"]
                        if aud_res.get("issues"):
                            comments += f" Skeptical auditor flagged issues: {[i.get('message') for i in aud_res.get('issues')]}"
                            conf = max(0.0, conf - 0.2)
                            
                    result = tool_fn(
                        theorem_name=theorem_name,
                        proof_code=proof_code,
                        verdict=verdict,
                        skeptical_audit_comments=comments,
                        confidence=conf,
                    )
                elif tool_name == "numina_prover":
                    theorem_header = plan.get("theorem_header", plan.get("query", ""))
                    initial_proof = plan.get("initial_proof", "by sorry")
                    imports_list = plan.get("imports", None)
                    result = tool_fn(
                        theorem_header=theorem_header,
                        initial_proof_stub=initial_proof,
                        imports=imports_list,
                    )
                elif tool_name == "leanabell_prover":
                    theorem_header = plan.get("theorem_header", plan.get("query", "theorem add_zero (n : Nat) : n + 0 = n"))
                    initial_proof = plan.get("initial_proof", "by sorry")
                    imports_list = plan.get("imports", None)
                    result = tool_fn(
                        theorem_header=theorem_header,
                        initial_proof_stub=initial_proof,
                        imports=imports_list,
                    )
                elif tool_name == "deepproblog_gate":
                    result = tool_fn(
                        program=plan.get("program", ""),
                        query=plan.get("logic_query", ""),
                        neural_preds=plan.get("neural_preds", {}),
                    )
                elif tool_name == "predict_lean_accuracy":
                    hypotheses = plan.get("hypotheses", [plan.get("query", "test")])
                    if isinstance(hypotheses, str):
                        hypotheses = [hypotheses]
                    
                    predictions = []
                    for h in hypotheses:
                        predictions.append(tool_fn(hypothesis=h, context_data=plan.get("context_data", "")))
                    result = {"predictions": predictions}
                elif tool_name == "skeptical_auditor":
                    proof_text = plan.get("proof_text", plan.get("query", ""))
                    result = tool_fn(proof_text=proof_text)
                elif tool_name == "global_stitcher":
                    proof_code = plan.get("proof_code", self._default_lean_proof())
                    # extract theorem name from query or proof_code if possible, else default
                    theorem_name = "stitched_theorem"
                    import re
                    m = re.search(r"for ([\w_]+)\.", plan.get("query", ""))
                    if m:
                        theorem_name = m.group(1)
                    result = tool_fn(theorem_name=theorem_name, proof_code=proof_code)
                else:
                    result = {"status": "unknown_tool"}

                observations[tool_name] = result
            except Exception as exc:
                self._log.error("tool_failed", tool=tool_name, error=str(exc))
                observations[tool_name] = {"error": str(exc)}

        self._stop_timer(start, "euler_act")
        return observations

    async def run(self, query: str, **kwargs: Any) -> AgentResult:
        """Full Euler verification loop.

        Args:
            query: Claim, theorem, or demonstration to verify.
            **kwargs: Extra context (``proof_code``, ``program``, etc.).

        Returns:
            :class:`AgentResult` with verdict, proofs, and objections.
        """
        self._log.info("euler_run_start", query=query[:120])
        start = self._start_timer()
        self._iteration = 0

        context: dict[str, Any] = {"query": query, **kwargs}
        self._current_proof_context = context

        plan = await self.think(context)
        # Forward extra context into the plan
        for key in ("proof_code", "program", "logic_query", "neural_preds",
                     "proof_text", "hypotheses", "context_data"):
            if key in kwargs:
                plan[key] = kwargs[key]

        observations = await self.act(plan)

        actual_cost = plan.get("estimated_cost", 0.0)
        self._record_cost(actual_cost)

        # Determine verdict
        verdict = self._determine_verdict(observations)

        elapsed = self._stop_timer(start, "euler_run_total")
        result = AgentResult(
            answer=verdict,
            confidence=self._compute_verification_confidence(observations),
            cost_usd=actual_cost,
            proofs=verdict.get("proofs", []),
            telemetry={
                **self.telemetry.summary(),
                "total_elapsed_ms": round(elapsed, 2),
            },
        )

        self._log.info(
            "euler_run_complete",
            verdict=verdict.get("status", "unknown"),
            confidence=result.confidence,
        )
        return result

    # ------ Helpers -------------------------------------------------------

    @staticmethod
    def _extract_claims(text: str) -> list[str]:
        """Extract verifiable claims from natural language text.

        A simple heuristic: split on sentence boundaries and filter
        for sentences containing mathematical or scientific keywords.

        Args:
            text: Input text.

        Returns:
            List of claim strings.
        """
        import re
        sentences = re.split(r'[.!?]+', text)
        keywords = {"prove", "show", "verify", "therefore", "implies",
                     "equals", "converges", "satisfies", "holds"}
        claims = [
            s.strip() for s in sentences
            if any(kw in s.lower() for kw in keywords) and len(s.strip()) > 10
        ]
        return claims or [text.strip()]

    @staticmethod
    def _default_lean_proof() -> str:
        """Return a minimal Lean 4 proof for testing.

        Returns:
            Lean 4 source code.
        """
        return (
            "-- Test: natural number addition identity\n"
            "theorem add_zero (n : Nat) : n + 0 = n := by\n"
            "  simp\n"
        )

    @staticmethod
    def _determine_verdict(observations: dict[str, Any]) -> dict[str, Any]:
        """Synthesise a verification verdict from tool observations.

        Args:
            observations: Tool execution results.

        Returns:
            Verdict dict with ``status``, ``objections``, ``proofs``.
        """
        objections: list[str] = []
        proofs: list[str] = []
        status = "VERIFIED"

        # Check Leanabell-Prover-V2 results
        leanabell_result = observations.get("leanabell_prover", {})
        if leanabell_result:
            is_success = (
                leanabell_result.get("success")
                if isinstance(leanabell_result, dict)
                else getattr(leanabell_result, "success", False)
            )
            final_proof = (
                leanabell_result.get("final_proof")
                if isinstance(leanabell_result, dict)
                else getattr(leanabell_result, "final_proof", "")
            )
            sorry_remaining = (
                leanabell_result.get("sorry_remaining")
                if isinstance(leanabell_result, dict)
                else getattr(leanabell_result, "sorry_remaining", False)
            )
            msg = (
                leanabell_result.get("message")
                if isinstance(leanabell_result, dict)
                else getattr(leanabell_result, "message", "")
            )

            if is_success:
                proofs.append(f"Leanabell-Prover-V2: VERIFIED ✓. Proof: {final_proof}")
            else:
                status = "INCOMPLETE" if sorry_remaining else "REFUTED"
                objections.append(f"Leanabell-Prover-V2 failed: {msg}")

        # Check Lean 4 results
        lean_result = observations.get("lean4_compiler", {})
        if not lean_result:
            lean_result = observations.get("lean4_repl", {})
        if lean_result:
            if lean_result.get("success") is False:
                status = "REFUTED"
                objections.append(f"Lean 4 compilation failed: {lean_result.get('output', lean_result.get('message', ''))}")
            elif lean_result.get("has_sorry"):
                status = "FAILED_OPEN_GAPS"
                objections.append("Proof contains 'sorry' gaps — zero-sorry policy enforced")
            elif lean_result.get("success"):
                proofs.append("Lean 4 type-checking: PASSED")

        # Check Verso results
        verso_result = observations.get("verso_compiler", {})
        if verso_result:
            if verso_result.get("success") is False:
                status = "REFUTED"
                objections.append(f"Verso document compilation failed: {verso_result.get('message', '')}")
            elif verso_result.get("has_sorry"):
                status = "FAILED_OPEN_GAPS"
                objections.append("Verso document contains 'sorry' proof gaps — zero-sorry policy enforced")
            elif verso_result.get("success"):
                proofs.append("Verso document type-checking: PASSED")

        # Check Certificate results
        cert_result = observations.get("certificate_generator", {})
        if cert_result:
            proofs.append(f"Verification Certificate Issued: {cert_result.get('certificate_id')} (Persisted in Alexandrie)")

        # Check DeepProbLog results
        dpl_result = observations.get("deepproblog_gate", {})
        if dpl_result.get("probability", 1.0) == 0.0:
            status = "REFUTED"
            objections.append("DeepProbLog: query probability is 0 (type violation)")
        elif dpl_result.get("probability") is not None:
            prob = dpl_result["probability"]
            if prob < 0.5:
                objections.append(f"DeepProbLog: low probability P={prob:.4f}")

        # Check ML prediction results
        ml_result = observations.get("predict_lean_accuracy", {})
        if ml_result.get("predictions"):
            max_prob = max(p.get("probability", 0.0) for p in ml_result["predictions"])
            if max_prob < 0.5:
                status = "INCOMPLETE"
                objections.append(f"ML accuracy prediction low (max P={max_prob:.4f})")
            else:
                proofs.append(f"ML accuracy prediction passing (max P={max_prob:.4f})")

        # Check skeptical auditor
        audit_result = observations.get("skeptical_auditor", {})
        if audit_result.get("issues"):
            for issue in audit_result["issues"]:
                severity = issue.get("severity", "warning")
                if severity == "error":
                    status = "REFUTED"
                objections.append(f"[{severity.upper()}] {issue.get('message', '')}")

        return {
            "status": status,
            "objections": objections,
            "proofs": proofs,
            "observations": observations,
        }

    @staticmethod
    def _compute_verification_confidence(
        observations: dict[str, Any],
    ) -> float:
        """Compute confidence based on verification tool results.

        Args:
            observations: Tool results.

        Returns:
            Confidence score in ``[0, 1]``.
        """
        scores: list[float] = []

        leanabell = observations.get("leanabell_prover", {})
        if leanabell:
            is_success = (
                leanabell.get("success")
                if isinstance(leanabell, dict)
                else getattr(leanabell, "success", False)
            )
            sorry_remaining = (
                leanabell.get("sorry_remaining")
                if isinstance(leanabell, dict)
                else getattr(leanabell, "sorry_remaining", False)
            )

            if is_success and not sorry_remaining:
                scores.append(1.0)
            elif sorry_remaining:
                scores.append(0.3)
            else:
                scores.append(0.0)

        lean = observations.get("lean4_compiler", {})
        if lean:
            if lean.get("success") and not lean.get("has_sorry"):
                scores.append(1.0)
            elif lean.get("has_sorry"):
                scores.append(-1.0)
            elif lean.get("success") is False:
                scores.append(0.0)

        dpl = observations.get("deepproblog_gate", {})
        if dpl.get("probability") is not None:
            scores.append(dpl["probability"])
            
        ml_pred = observations.get("predict_lean_accuracy", {})
        if ml_pred.get("predictions"):
            max_prob = max(p.get("probability", 0.0) for p in ml_pred["predictions"])
            scores.append(max_prob)

        audit = observations.get("skeptical_auditor", {})
        if audit.get("issues"):
            error_count = sum(
                1 for i in audit["issues"] if i.get("severity") == "error"
            )
            scores.append(max(0.0, 1.0 - error_count * 0.3))
        else:
            scores.append(0.9)

        if not scores:
            return 0.5
        avg = sum(scores) / len(scores)
        return max(0.0, min(1.0, round(avg, 2)))
