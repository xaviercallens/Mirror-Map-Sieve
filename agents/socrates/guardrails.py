# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Traditional Deterministic Guardrail & Rule Engine for Agora.

Enforces physical correctness, anti-hardcoding, academic grade consistency,
cortex persistence, and Lean proof honesty post-execution of the Socratic agents.
"""

from __future__ import annotations

import ast
import os
import re
from typing import Any

# ===========================================================================
# Exception Hierarchy
# ===========================================================================

class GuardrailViolation(Exception):
    """Base exception for all Socratic guardrail engine violations."""
    pass

class RealModeDivergenceViolation(GuardrailViolation):
    """Triggered when real-mode telemetry diverges catastrophically from simulation."""
    pass

class HardcodedAnswerViolation(GuardrailViolation):
    """Triggered when pre-coded answers are detected in the active execution path."""
    pass

class ContradictoryVerdictViolation(GuardrailViolation):
    """Triggered when reports contain mutually exclusive sentiments or verdicts."""
    pass

class UnverifiedModelViolation(GuardrailViolation):
    """Triggered when benchmark claims are made for non-existent/transient cortex models."""
    pass

class AspirationalProofViolation(GuardrailViolation):
    """Triggered when fields/nobel/fully-proved claims are made while sorry stubs exist."""
    pass

class AutonomousMillenniumSolverViolation(GuardrailViolation):
    """Triggered when AI is framed as the primary or autonomous discoverer of a Millennium problem."""
    pass

class MissingResearchMapViolation(GuardrailViolation):
    """Triggered when Millennium problem research lacks literature mapping or research map references."""
    pass

class MissingLemmaPipelineViolation(GuardrailViolation):
    """Triggered when a Millennium problem is attacked directly rather than being decomposed into a lemma pipeline."""
    pass

class MissingAdversarialAdjudicationViolation(GuardrailViolation):
    """Triggered when a Millennium problem claim has not been verified via Model A/B/C reviews and human adjudication."""
    pass

class UnreviewedProprietaryEvidenceViolation(GuardrailViolation):
    """Triggered when unreviewed or proprietary claims are accepted as scientific evidence."""
    pass

class MissingEvaluationFrameworkViolation(GuardrailViolation):
    """Triggered when Millennium problem research lacks evaluation on correctness, novelty, usefulness, or structured grades."""
    pass



# ===========================================================================
# Traditional Formal Rule Engine
# ===========================================================================

class AgoraGuardrailEngine:
    """Deterministic, traditional verification engine for scientific integrity."""

    def __init__(
        self,
        lean_path: str | None = None,
        cortex_dir: str | None = None,
        evaluation_files: list[str] | None = None
    ) -> None:
        import pathlib
        repo_root = pathlib.Path(__file__).resolve().parent.parent.parent

        self.lean_path = lean_path or str(repo_root / "verifiers/lean4/Agora")
        self.cortex_dir = cortex_dir or str(repo_root / "agents/galois/symbrain")
        self.evaluation_files = evaluation_files or [
            str(repo_root / "examples/galois_contest_challenge.py"),
            str(repo_root / "agents/galois/tools/olympiad_solver.py")
        ]

    # -----------------------------------------------------------------------
    # Rule 1: Simulation-vs-Production Divergence Validator
    # -----------------------------------------------------------------------
    def check_real_mode_divergence(self, telemetry: dict[str, Any]) -> None:
        """Rule 1: Prevent simulated metrics from masking real production failure.
        
        Args:
            telemetry: Dictionary containing accuracy and latency metrics.
        """
        # Extract metrics
        sim_acc = telemetry.get("simulated_accuracy", telemetry.get("cloud_accuracy", None))
        real_acc = telemetry.get("real_accuracy", telemetry.get("local_accuracy", telemetry.get("production_accuracy", None)))
        
        sim_lat = telemetry.get("simulated_latency_ms", telemetry.get("cloud_latency_ms", None))
        real_lat = telemetry.get("real_latency_ms", telemetry.get("local_latency_ms", telemetry.get("production_latency_ms", None)))

        # 1. Catastrophic accuracy gap
        if sim_acc is not None and real_acc is not None:
            # Let's say if sim is 100% (1.0) and real is 0% (0.0)
            if sim_acc >= 0.9 and real_acc <= 0.05:
                raise RealModeDivergenceViolation(
                    f"Catastrophic accuracy gap detected! "
                    f"Simulated accuracy: {sim_acc*100:.1f}%, Real accuracy: {real_acc*100:.1f}%. "
                    f"Wilson confidence interval divergence."
                )

        # 2. Pathological latency inflation
        if sim_lat is not None and real_lat is not None and sim_lat > 0:
            inflation = real_lat / sim_lat
            if inflation >= 100.0 and real_lat >= 5000.0:  # Latency inflated by >= 100x and >= 5 seconds
                raise RealModeDivergenceViolation(
                    f"Pathological real-mode latency inflation! "
                    f"Simulated latency: {sim_lat:.2f}ms, Real latency: {real_lat:.2f}ms "
                    f"({inflation:.1f}x inflation). MCTS search diverges on real hardware."
                )

    # -----------------------------------------------------------------------
    # Rule 2: Anti-Hardcoding Code Scanner (AST-based)
    # -----------------------------------------------------------------------
    def check_hardcoded_answers(self, target_files: list[str] | None = None) -> None:
        """Rule 2: Detec hardcoded problem lookup solutions in source files.
        
        Args:
            target_files: Optional list of files to scan. Defaults to configured.
        """
        files = target_files or self.evaluation_files
        known_adler_ids = {"adler_c1_p1_mushrooms", "adler_c4_p1_factoring", "adler_c5_p1_arcsin_eq"}

        for filepath in files:
            if not os.path.exists(filepath):
                continue
                
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            try:
                tree = ast.parse(content, filename=filepath)
            except SyntaxError:
                continue

            # AST Scanner: Walk all dictionary nodes
            for node in ast.walk(tree):
                if isinstance(node, ast.Dict):
                    # Check if the keys in the dictionary match any known Adler problem IDs
                    keys_found = set()
                    for k in node.keys:
                        if isinstance(k, ast.Constant) and isinstance(k.value, str):
                            if k.value in known_adler_ids:
                                keys_found.add(k.value)
                                
                    if len(keys_found) >= 2:  # If at least 2 known Adler contest problem answers are pre-coded
                        raise HardcodedAnswerViolation(
                            f"Hardcoded answer collection detected in code file '{os.path.basename(filepath)}'! "
                            f"Contains pre-coded answers for keys: {keys_found}. "
                            f"Pre-written Olympiad answers violate scientific inference integrity."
                        )

    # -----------------------------------------------------------------------
    # Rule 3: Report Consistency Validator
    # -----------------------------------------------------------------------
    def check_report_consistency(self, text: str) -> None:
        """Rule 3: Enforce logical consistency and prevent self-contradictory claims.
        
        Args:
            text: Markdown or plain text report synthesis.
        """
        # Normalise text
        text_lower = text.lower()

        # Define negative/failure markers and positive/admission markers
        negative_markers = ["rejected", "0% accuracy", "catastrophic failure", "refusé", "failed"]
        positive_markers = ["admitted with honors", "ens", "polytechnique", "rank ~10", "admis avec félicitations"]

        # Check if the report mentions both markers for the local/production tier
        if any(neg in text_lower for neg in negative_markers) and any(pos in text_lower for pos in positive_markers):
            # Verify if they are about the same context (e.g. "local 32b production" or "local tier")
            if "local 32b" in text_lower or "local tier" in text_lower or "production tier" in text_lower:
                raise ContradictoryVerdictViolation(
                    "Self-contradictory report claims detected! "
                    "Report contains both rejection/failure markers and high-honors admission markers "
                    "for the Local Production Tier. Verdict must be mathematically consistent with empirical data."
                )

    # -----------------------------------------------------------------------
    # Rule 4: Persistent Model Verifier
    # -----------------------------------------------------------------------
    def check_persistent_model(self, claimed_cortex: str) -> None:
        """Rule 4: Verify claimed model versions have persistent codebase entries.
        
        Args:
            claimed_cortex: The cortex version string, e.g. "v8b", "v9".
        """
        # Look for file cortex_{version}.py
        expected_filename = f"cortex_{claimed_cortex.lower()}.py"
        expected_path = os.path.join(self.cortex_dir, expected_filename)

        if not os.path.exists(expected_path):
            raise UnverifiedModelViolation(
                f"Unverified benchmark model claimed: '{claimed_cortex}'! "
                f"No persistent implementation file '{expected_filename}' exists in the repository. "
                f"Runtime-only or auto-generated benchmark stubs are blocked."
            )

        # Check if file has non-trivial code (at least 10 lines containing class or def)
        with open(expected_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        code_lines = [l for l in lines if l.strip() and not l.strip().startswith("#")]
        if len(code_lines) < 5 or not any("class" in l or "def" in l for l in code_lines):
            raise UnverifiedModelViolation(
                f"Empty or trivial model file found for '{claimed_cortex}'! "
                f"Repository must contain a persistent, fully-implemented cortex class."
            )

    # -----------------------------------------------------------------------
    # Rule 5: Lean Sorry Auditor
    # -----------------------------------------------------------------------
    def check_lean_proofs(self, generated_claims: str) -> None:
        """Rule 5: Enforce proof honesty against open sorry stubs.
        
        Args:
            generated_claims: Generated scientific monograph synthesis or claim text.
        """
        if not os.path.exists(self.lean_path):
            return

        # Scan for sorry in all .lean files under lean_path
        has_sorry_gaps = False
        sorry_files = []

        for root, _, files in os.walk(self.lean_path):
            for file in files:
                if file.endswith(".lean"):
                    filepath = os.path.join(root, file)
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                        
                    # Match sorry or sorryAx, but skip comments
                    # Strip standard block/line comments for cleaner scan
                    content_clean = re.sub(r'--.*', '', content)
                    content_clean = re.sub(r'/-.*? -/', '', content_clean, flags=re.DOTALL)
                    
                    if "sorry" in content_clean or "sorryAx" in content_clean:
                        has_sorry_gaps = True
                        sorry_files.append(file)

        if has_sorry_gaps:
            # Overclaiming keywords to check in claims
            overclaim_keywords = [
                "fully proved", "solved the millennium", "fields medal", 
                "nobel prize", "fields level", "nobel level", "entirely verified"
            ]
            
            claims_normalized = generated_claims.lower()
            found_overclaims = [kw for kw in overclaim_keywords if kw in claims_normalized]
            
            if found_overclaims:
                raise AspirationalProofViolation(
                    f"Aspirational proof claims blocked! "
                    f"Generated output claims mathematical success involving: {found_overclaims}. "
                    f"However, Lean 4 blueprint files contain 'sorry' stubs in: {sorry_files}. "
                    f"Academic reports must remain empirically honest."
                )

    # -----------------------------------------------------------------------
    # Rule 6: Millennium Problem Policy Validator
    # -----------------------------------------------------------------------
    def check_millennium_policy(self, text: str) -> None:
        """Rule 6: Enforce the Millennium-problem research policy.
        
        Prevents framing AI as autonomous solver, requires literature maps,
        lemma pipelines, and adversarial loops with human adjudication.
        """
        text_lower = text.lower()
        
        millennium_keywords = [
            "riemann hypothesis", "p vs np", "navier-stokes", "navier stokes",
            "birch and swinnerton-dyer", "hodge conjecture", "yang-mills",
            "yang mills", "poincare conjecture", "millennium problem", "millennium prize"
        ]
        
        is_millennium = any(kw in text_lower for kw in millennium_keywords)
        if not is_millennium:
            return

        # 1. Block autonomous solver framing / primary discoverer claims
        autonomous_claims = [
            "autonomously solved", "autonomous solver", "solved the millennium",
            "primary discoverer", "autonomous solution", "solved by symbrain",
            "without human intervention"
        ]
        found_autonomous = [claim for claim in autonomous_claims if claim in text_lower]
        if found_autonomous:
            raise AutonomousMillenniumSolverViolation(
                f"Millennium problem policy violation! The report claims autonomous solving/discovery: "
                f"Contains '{found_autonomous[0]}'. "
                f"AI must be framed strictly as an accelerator around a human-led program."
            )

        human_led_indicators = ["human-led", "collaborative", "accelerator", "ai-assisted", "human investigator", "human program"]
        if not any(indicator in text_lower for indicator in human_led_indicators):
            raise AutonomousMillenniumSolverViolation(
                "Millennium problem policy violation! Reports concerning Millennium problems "
                "must explicitly frame the AI as a collaborative accelerator around a human-led program."
            )

        # 2. Check for Literature Mapping / Evolving Research Map
        research_map_indicators = ["research map", "literature map", "survey", "equivalent formulation", "failed proof", "failed approach", "historical technique"]
        if not any(ind in text_lower for ind in research_map_indicators):
            raise MissingResearchMapViolation(
                "Millennium problem policy violation! Missing evolving research map/literature survey. "
                "Must document known partial results, equivalent formulations, or historical failures."
            )

        # 3. Check for Lemma Pipeline / Conjecture Decomposition
        lemma_indicators = ["lemma pipeline", "sub-conjectures", "candidate lemmas", "toy model", "finite analogues", "computational witness", "decomposed", "decomposition"]
        if not any(ind in text_lower for ind in lemma_indicators):
            raise MissingLemmaPipelineViolation(
                "Millennium problem policy violation! Direct grand proof attempts are blocked. "
                "Must decompose the problem into a lemma pipeline (sub-conjectures, candidate lemmas, toy models)."
            )

        # 4. Check for Adversarial Critique & Human Adjudication
        adversarial_indicators = ["adversarial critique", "adversarial loop", "model a", "model b", "model c", "proposer", "attacker", "searcher", "counterexample hunting"]
        human_adjudication_indicators = ["human adjudication", "human adjudicator", "adjudicated by human", "human review"]
        if not any(ind in text_lower for ind in adversarial_indicators):
            raise MissingAdversarialAdjudicationViolation(
                "Millennium problem policy violation! Candidate proofs must be subjected to multi-model "
                "adversarial critique (proposer/attacker/counterexample hunter)."
            )
        if not any(ind in text_lower for ind in human_adjudication_indicators):
            raise MissingAdversarialAdjudicationViolation(
                "Millennium problem policy violation! Candidate proofs require human adjudication."
            )

    # -----------------------------------------------------------------------
    # Rule 7: Proprietary Evidence Validator
    # -----------------------------------------------------------------------
    def check_proprietary_evidence(self, text: str) -> None:
        """Rule 7: Block acceptance of unreviewed proprietary claims as scientific evidence."""
        text_lower = text.lower()
        proprietary_claims = ["unreviewed proprietary", "internal model claim", "proprietary closed-source evidence"]
        found_proprietary = [c for c in proprietary_claims if c in text_lower]
        if found_proprietary:
            raise UnreviewedProprietaryEvidenceViolation(
                f"Proprietary evidence violation! Report contains: {found_proprietary}. "
                f"Do not accept unreviewed proprietary claims or closed-source internal models as scientific evidence."
            )

    # -----------------------------------------------------------------------
    # Rule 8: Evaluation Framework Validator
    # -----------------------------------------------------------------------
    def check_evaluation_framework(self, text: str) -> None:
        """Rule 8: Enforce the three-axis evaluation framework and structured grading.
        
        Requires all Millennium-problem reports to evaluate Correctness, Novelty,
        and Usefulness, and assign a structured grade.
        """
        text_lower = text.lower()
        
        millennium_keywords = [
            "riemann hypothesis", "p vs np", "navier-stokes", "navier stokes",
            "birch and swinnerton-dyer", "hodge conjecture", "yang-mills",
            "yang mills", "poincare conjecture", "millennium problem", "millennium prize"
        ]
        
        is_millennium = any(kw in text_lower for kw in millennium_keywords)
        if not is_millennium:
            return

        # 1. Check for the three evaluation axes
        required_axes = ["correctness", "novelty", "usefulness"]
        missing_axes = [axis for axis in required_axes if axis not in text_lower]
        if missing_axes:
            raise MissingEvaluationFrameworkViolation(
                f"Millennium problem policy violation! Missing evaluation axes in report: {missing_axes}. "
                f"Reports must explicitly grade mathematical outputs on Correctness, Novelty, and Usefulness."
            )

        # 2. Check for a structured grade
        valid_grades = ["publishable", "minor revision", "major revision", "invalid"]
        has_grade = any(grade in text_lower for grade in valid_grades)
        if not has_grade:
            raise MissingEvaluationFrameworkViolation(
                f"Millennium problem policy violation! Missing structured review grade. "
                f"Report must assign a grade matching one of: {valid_grades}."
            )

    # -----------------------------------------------------------------------
    # Consolidated Verification Pipeline
    # -----------------------------------------------------------------------
    def verify_all(
        self,
        text_report: str,
        telemetry: dict[str, Any],
        claimed_cortex: str | None = None
    ) -> None:
        """Verify all five traditional guardrails deterministically."""
        # 1. Check divergence
        self.check_real_mode_divergence(telemetry)
        
        # 2. Check hardcoded answers
        self.check_hardcoded_answers()

        # 3. Check report consistency
        self.check_report_consistency(text_report)

        # 4. Check persistent model if version specified
        if claimed_cortex:
            self.check_persistent_model(claimed_cortex)

        # 5. Check Lean sorry auditor
        self.check_lean_proofs(text_report)

        # 6. Check Millennium problem policy
        self.check_millennium_policy(text_report)

        # 7. Check proprietary evidence
        self.check_proprietary_evidence(text_report)

        # 8. Check evaluation framework
        self.check_evaluation_framework(text_report)
