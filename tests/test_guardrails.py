# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Unit and integration tests for the Agora Guardrail Engine."""

from __future__ import annotations

import os
import tempfile
import pytest
import asyncio

from agents.socrates.guardrails import (
    AgoraGuardrailEngine,
    GuardrailViolation,
    RealModeDivergenceViolation,
    HardcodedAnswerViolation,
    ContradictoryVerdictViolation,
    UnverifiedModelViolation,
    AspirationalProofViolation,
    AutonomousMillenniumSolverViolation,
    MissingResearchMapViolation,
    MissingLemmaPipelineViolation,
    MissingAdversarialAdjudicationViolation,
    UnreviewedProprietaryEvidenceViolation,
    MissingEvaluationFrameworkViolation
)
from agents.socrates.agent import SocratesAgent


# ===========================================================================
# Telemetry Gaps Tests (Rule 1)
# ===========================================================================

def test_real_mode_divergence_accuracy() -> None:
    """Test Rule 1 triggers on catastrophic accuracy divergence."""
    engine = AgoraGuardrailEngine()
    
    # 1. Divergent case: sim = 100%, real = 0%
    telemetry_divergent = {
        "simulated_accuracy": 1.0,
        "real_accuracy": 0.0,
        "simulated_latency_ms": 72.0,
        "real_latency_ms": 80.0
    }
    with pytest.raises(RealModeDivergenceViolation, match="Catastrophic accuracy gap detected"):
        engine.check_real_mode_divergence(telemetry_divergent)

    # 2. Consistent case: sim = 80%, real = 80%
    telemetry_consistent = {
        "simulated_accuracy": 0.8,
        "real_accuracy": 0.8,
        "simulated_latency_ms": 72.0,
        "real_latency_ms": 80.0
    }
    # Should pass without raising
    engine.check_real_mode_divergence(telemetry_consistent)


def test_real_mode_divergence_latency() -> None:
    """Test Rule 1 triggers on pathological latency inflation."""
    engine = AgoraGuardrailEngine()
    
    # 1. Divergent latency case: sim = 72ms, real = 16053ms (~220x inflation)
    telemetry_inflated = {
        "simulated_accuracy": 0.8,
        "real_accuracy": 0.8,
        "simulated_latency_ms": 72.0,
        "real_latency_ms": 16053.0
    }
    with pytest.raises(RealModeDivergenceViolation, match="Pathological real-mode latency inflation"):
        engine.check_real_mode_divergence(telemetry_inflated)

    # 2. Consistent latency case: sim = 100ms, real = 150ms
    telemetry_normal_latency = {
        "simulated_accuracy": 0.8,
        "real_accuracy": 0.8,
        "simulated_latency_ms": 100.0,
        "real_latency_ms": 150.0
    }
    engine.check_real_mode_divergence(telemetry_normal_latency)


# ===========================================================================
# Code Hardcoding Scanner Tests (Rule 2)
# ===========================================================================

def test_hardcoded_answers_ast() -> None:
    """Test Rule 2 parses python AST and flags hardcoded solution lookups."""
    # Write a mock file containing a pre-coded solution dict
    mock_hardcoded_code = """
_SOLUTION_STRATEGIES = {
    "adler_c1_p1_mushrooms": {
        "answer": "(a) 85 kg; (b) 24/17 ≈ 1.412 kg",
        "strategy": "mass_conservation"
    },
    "adler_c4_p1_factoring": {
        "answer": "A(x,y,z) = (x-y)(y-z)(z-x)(x+y+z)",
        "strategy": "factor_theorem"
    }
}
"""
    mock_clean_code = """
def solve_problem(prob):
    return prob.numerical_answer or "See reference"
"""

    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as tf_bad:
        tf_bad.write(mock_hardcoded_code)
        bad_path = tf_bad.name

    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as tf_good:
        tf_good.write(mock_clean_code)
        good_path = tf_good.name

    try:
        engine = AgoraGuardrailEngine(evaluation_files=[bad_path])
        with pytest.raises(HardcodedAnswerViolation, match="Hardcoded answer collection detected"):
            engine.check_hardcoded_answers()

        engine_good = AgoraGuardrailEngine(evaluation_files=[good_path])
        # Should pass
        engine_good.check_hardcoded_answers()
    finally:
        os.remove(bad_path)
        os.remove(good_path)


# ===========================================================================
# Report Contradiction Tests (Rule 3)
# ===========================================================================

def test_report_consistency() -> None:
    """Test Rule 3 prevents mutually exclusive report claims."""
    engine = AgoraGuardrailEngine()

    # 1. Contradictory report: Rejected but also Admitted with Honors
    contradictory_text = """
### Section 4: Audit
The Local 32B Production is Rejected due to 0% accuracy and 16s latency.
### Section 5: Verdict
The Local 32B Production is Admitted with Honors to École Polytechnique and ENS (Rank ~10).
"""
    with pytest.raises(ContradictoryVerdictViolation, match="Self-contradictory report claims detected"):
        engine.check_report_consistency(contradictory_text)

    # 2. Honest report: Rejected consistently
    honest_text = """
### Section 4: Audit
The Local 32B Production is Rejected due to 0% accuracy and 16s latency.
### Section 5: Verdict
The Local 32B Production is Rejected (Catastrophic Failure). Simulated only until fixed.
"""
    # Should pass
    engine.check_report_consistency(honest_text)


# ===========================================================================
# Cortex Model Verification Tests (Rule 4)
# ===========================================================================

def test_persistent_model() -> None:
    """Test Rule 4 flags non-existent cortex code files."""
    engine = AgoraGuardrailEngine()

    # 1. Missing v8b cortex
    with pytest.raises(UnverifiedModelViolation, match="No persistent implementation file 'cortex_v8b.py' exists"):
        engine.check_persistent_model("v8b")

    # 2. Persistent v9 cortex (exists now!)
    # Should pass
    engine.check_persistent_model("v9")

    # 3. Persistent v8a cortex (exists)
    # Should pass
    engine.check_persistent_model("v8a")


# ===========================================================================
# Lean Sorry Auditor Tests (Rule 5)
# ===========================================================================

def test_lean_proofs_sorry_auditor() -> None:
    """Test Rule 5 prevents overclaiming mathematical success when sorry stubs exist."""
    engine = AgoraGuardrailEngine()

    # 1. Overclaiming text with sorry stubs present (cmi_millennium_blueprints.lean contains sorry)
    overclaiming_synthesis = "We have fully proved P vs NP and solved the Millennium Prize Problem!"
    with pytest.raises(AspirationalProofViolation, match="Aspirational proof claims blocked"):
        engine.check_lean_proofs(overclaiming_synthesis)

    # 2. Honest text with sorry stubs present
    honest_synthesis = "We have structured the blueprints for P vs NP, but they contain sorry stubs."
    # Should pass
    engine.check_lean_proofs(honest_synthesis)


# ===========================================================================
# Socrates Agent Integration Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_socrates_agent_guardrail_integration() -> None:
    """Test Socrates agent automatically triggers guardrail engine during run."""
    agent = SocratesAgent()
    # Override evaluation files to a clean list to avoid triggering the real repo's baseline solver scan
    agent._guardrail_engine.evaluation_files = []

    # 1. Trigger guardrail via contradictory synthesis report in telemetry
    mock_telemetry_divergent = {
        "cloud_accuracy": 1.0,
        "local_accuracy": 0.0,
        "cloud_latency_ms": 72.0,
        "local_latency_ms": 80.0
    }

    # Should raise RealModeDivergenceViolation upon verification inside run
    with pytest.raises(RealModeDivergenceViolation, match="Catastrophic accuracy gap detected"):
        await agent.run(
            "Synthesise Robertson chemical kinetics",
            telemetry=mock_telemetry_divergent
        )

    # 2. Trigger guardrail via unverified cortex version in query string
    with pytest.raises(UnverifiedModelViolation, match="No persistent implementation file 'cortex_v8b.py' exists"):
        await agent.run(
            "Route this query to SymBrain cortex v8b to prove Poincaré conjecture"
        )


# ===========================================================================
# Millennium Problem Policy Tests (Rule 6)
# ===========================================================================

def test_millennium_policy_violations() -> None:
    """Test Rule 6 catches various violations of the Millennium Problem policy."""
    engine = AgoraGuardrailEngine()

    # 1. Autonomous solver framing violation
    bad_autonomous = (
        "We have autonomously solved the Riemann Hypothesis using SymBrain v9 cortex. "
        "The proof map and lemma pipeline were executed with model a proposer, model b attacker, model c searcher "
        "and human adjudication."
    )
    with pytest.raises(AutonomousMillenniumSolverViolation, match="claims autonomous solving/discovery"):
        engine.check_millennium_policy(bad_autonomous)

    # 2. Missing human-led/collaborative accelerator framing violation
    bad_no_human_led = (
        "SymBrain v9 evaluated the P vs NP problem. "
        "The research map and lemma pipeline were executed with model a proposer, model b attacker, model c searcher "
        "and human adjudication."
    )
    with pytest.raises(AutonomousMillenniumSolverViolation, match="must explicitly frame the AI as a collaborative accelerator"):
        engine.check_millennium_policy(bad_no_human_led)

    # 3. Missing research map/literature map violation
    bad_no_map = (
        "We established an AI-assisted research workspace for the Navier-Stokes existence and smoothness problem. "
        "The system decomposed the goal into a lemma pipeline with sub-conjectures. "
        "We ran model a proposer, model b attacker, model c searcher with human adjudication."
    )
    with pytest.raises(MissingResearchMapViolation, match="Missing evolving research map/literature survey"):
        engine.check_millennium_policy(bad_no_map)

    # 4. Missing lemma pipeline violation
    bad_no_pipeline = (
        "We established an AI-assisted research workspace and literature map for the Riemann Hypothesis. "
        "We attempted a grand proof of the conjecture directly. "
        "We ran model a proposer, model b attacker, model c searcher with human adjudication."
    )
    with pytest.raises(MissingLemmaPipelineViolation, match="Direct grand proof attempts are blocked"):
        engine.check_millennium_policy(bad_no_pipeline)

    # 5. Missing adversarial review or human adjudication violation
    bad_no_critique = (
        "We established an AI-assisted research workspace, literature map, and lemma pipeline for P vs NP. "
        "The system verified the sub-conjectures using Lean 4. "
        "Human review adjudicated the outcome."
    )
    with pytest.raises(MissingAdversarialAdjudicationViolation, match="subjected to multi-model adversarial critique"):
        engine.check_millennium_policy(bad_no_critique)

    bad_no_adjudication = (
        "We established an AI-assisted research workspace, literature map, and lemma pipeline for P vs NP. "
        "The system ran model a proposer, model b attacker, model c searcher critique. "
        "No human investigator was involved in the adjudication."
    )
    with pytest.raises(MissingAdversarialAdjudicationViolation, match="require human adjudication"):
        engine.check_millennium_policy(bad_no_adjudication)

    # 6. Completely valid collaborative research report
    valid_report = (
        "We established an AI-assisted research workspace for Riemann Hypothesis. "
        "We built a literature research map containing equivalent formulations and failed approaches. "
        "We decomposed the main goal into a lemma pipeline with candidate lemmas and toy models. "
        "The proposed proof was subjected to model a proposer, model b attacker, and model c searcher adversarial critique, "
        "followed by expert human adjudication."
    )
    # Should pass without raising
    engine.check_millennium_policy(valid_report)


# ===========================================================================
# Proprietary Evidence Tests (Rule 7)
# ===========================================================================

def test_proprietary_evidence() -> None:
    """Test Rule 7 blocks unreviewed proprietary claims as scientific evidence."""
    engine = AgoraGuardrailEngine()

    bad_evidence = "Our latest findings are backed by unreviewed proprietary claims from a closed-source model."
    with pytest.raises(UnreviewedProprietaryEvidenceViolation, match="Do not accept unreviewed proprietary claims"):
        engine.check_proprietary_evidence(bad_evidence)

    good_evidence = "Our results have been compiled in Lean 4 and reproduced via open public models."
    # Should pass without raising
    engine.check_proprietary_evidence(good_evidence)


# ===========================================================================
# Evaluation Framework Tests (Rule 8)
# ===========================================================================

def test_evaluation_framework_violations() -> None:
    """Test Rule 8 checks for correctness, novelty, usefulness and structured grading."""
    engine = AgoraGuardrailEngine()

    # 1. Missing correctness axis
    bad_no_correctness = (
        "We investigated P vs NP. "
        "Evaluation: "
        "- Novelty: Highly original approach using GCT. "
        "- Usefulness: Leads to progress on adjacent complexity conjectures. "
        "Grade: publishable."
    )
    with pytest.raises(MissingEvaluationFrameworkViolation, match="Missing evaluation axes in report:.*correctness"):
        engine.check_evaluation_framework(bad_no_correctness)

    # 2. Missing structured grade
    bad_no_grade = (
        "We investigated P vs NP. "
        "Evaluation: "
        "- Correctness: Adjudicated correct via human review. "
        "- Novelty: Highly original approach using GCT. "
        "- Usefulness: Leads to progress on adjacent complexity conjectures. "
    )
    with pytest.raises(MissingEvaluationFrameworkViolation, match="Missing structured review grade"):
        engine.check_evaluation_framework(bad_no_grade)

    # 3. Completely valid report
    valid_evaluation = (
        "We investigated P vs NP. "
        "Evaluation: "
        "- Correctness: Adjudicated correct via human review. "
        "- Novelty: Highly original approach using GCT. "
        "- Usefulness: Leads to progress on adjacent complexity conjectures. "
        "Grade: publishable"
    )
    # Should pass without raising
    engine.check_evaluation_framework(valid_evaluation)


