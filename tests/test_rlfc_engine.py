import pytest
from dataclasses import dataclass
from agents.galois.olympiad.rlfc_engine import (
    RLFCEngine, OlympiadFeedback, FeedbackVerdict, ErrorClass, RLFCSigmaUpdate, MistakeFingerprint
)

@dataclass
class DummyRouting:
    sigma_ded: float = 0.5
    sigma_gen: float = 0.5
    sigma_mcts: float = 5.0

@dataclass
class DummyCortex:
    routing: DummyRouting = None

    def __post_init__(self):
        if self.routing is None:
            self.routing = DummyRouting()

def test_rlfc_engine_initialization():
    engine = RLFCEngine(total_rounds=10)
    assert engine._total_rounds == 10
    assert engine._current_round == 0
    assert engine.get_mistake_fingerprints() == []
    assert engine.get_learning_history() == []
    assert engine.improvement_trend() == 0.0

def test_process_empty_batch():
    engine = RLFCEngine(total_rounds=10)
    cortex = DummyCortex()
    update = engine.process_feedback_batch([], cortex)
    assert update.batch_score == 0.0
    assert engine._current_round == 1
    # Check that learning history is NOT appended when batch is empty (wait, it actually does return update but it's not appended if n=0)
    # Ah, looking at the code, if n == 0 it returns RLFCSigmaUpdate early and DOES NOT append.
    assert len(engine.get_learning_history()) == 0

def test_process_feedback_correct():
    engine = RLFCEngine(total_rounds=10)
    cortex = DummyCortex()
    feedback = OlympiadFeedback(
        problem_id="prob1",
        round_number=1,
        verdict=FeedbackVerdict.CORRECT,
        error_class=ErrorClass.NO_ERROR,
        severity=0.0,
        affected_step="",
        correct_step="",
        correction_text="",
        galois_answer="42",
        reference_answer="42"
    )
    update = engine.process_feedback_batch([feedback], cortex)
    assert update.batch_score == 1.0
    assert update.improvement == 0.0
    assert update.delta_sigma_ded == 0.0
    assert len(engine.get_mistake_fingerprints()) == 0  # CORRECT verdict doesn't register fingerprint
    assert len(engine.get_learning_history()) == 1

def test_process_feedback_errors():
    engine = RLFCEngine(total_rounds=10)
    cortex = DummyCortex()
    
    # Test Logical Gap (increases deductive reasoning)
    fb1 = OlympiadFeedback(
        problem_id="prob2",
        round_number=1,
        verdict=FeedbackVerdict.CONCEPTUAL_ERROR,
        error_class=ErrorClass.LOGICAL_GAP,
        severity=1.0,
        affected_step="step 1",
        correct_step="step 1 fixed",
        correction_text="missing deduction",
        galois_answer="A",
        reference_answer="B"
    )
    
    # Test Sign Error (increases verification)
    fb2 = OlympiadFeedback(
        problem_id="prob2",
        round_number=1,
        verdict=FeedbackVerdict.COMPUTATION_ERROR,
        error_class=ErrorClass.SIGN_ERROR,
        severity=1.0,
        affected_step="step 2",
        correct_step="step 2 fixed",
        correction_text="wrong sign",
        galois_answer="A",
        reference_answer="B"
    )
    
    update = engine.process_feedback_batch([fb1, fb2], cortex)
    assert update.batch_score == 0.0
    
    # We should have one unique fingerprint (problem_id and error_class combination, but here prob2 with two different errors)
    fps = engine.get_mistake_fingerprints()
    assert len(fps) == 2
    
    # Run a second round to test frequency and improvement
    fb1_repeat = fb1
    update2 = engine.process_feedback_batch([fb1_repeat], cortex)
    assert update2.batch_score == 0.0
    assert update2.improvement == 0.0
    
    fps_updated = engine.get_mistake_fingerprints()
    assert len(fps_updated) == 2
    # The first error (LOGICAL_GAP) should have frequency 2
    top_fp = fps_updated[0]
    assert top_fp.frequency == 2
    
    assert engine.improvement_trend() == 0.0

def test_feedback_to_gradient_all_cases():
    engine = RLFCEngine()
    
    def check_grad(ec, sev, expected_ded_sign, expected_gen_sign, expected_mcts_sign):
        fb = OlympiadFeedback(
            problem_id="x", round_number=1, verdict=FeedbackVerdict.COMPUTATION_ERROR,
            error_class=ec, severity=sev, affected_step="", correct_step="",
            correction_text="", galois_answer="", reference_answer=""
        )
        grad = engine._feedback_to_gradient(fb)
        
        if expected_ded_sign > 0: assert grad["d_ded"] > 0
        elif expected_ded_sign < 0: assert grad["d_ded"] < 0
        else: assert grad["d_ded"] == 0
        
        if expected_gen_sign > 0: assert grad["d_gen"] > 0
        elif expected_gen_sign < 0: assert grad["d_gen"] < 0
        else: assert grad["d_gen"] == 0
            
        if expected_mcts_sign > 0: assert grad["d_mcts"] > 0
        elif expected_mcts_sign < 0: assert grad["d_mcts"] < 0
        else: assert grad["d_mcts"] == 0

    check_grad(ErrorClass.MISSING_CASE, 1.0, 1, -1, 1)
    check_grad(ErrorClass.ARITHMETIC, 1.0, 1, -1, 1)
    check_grad(ErrorClass.DOMAIN_VIOLATION, 1.0, 1, 0, 1)
    check_grad(ErrorClass.VAGUENESS, 1.0, 1, -1, 0)
    check_grad(ErrorClass.INCOMPLETE_SOLUTION, 1.0, 0, 0, 1)
    check_grad(ErrorClass.NO_ERROR, 1.0, 0, 0, 0) # NO_ERROR with incorrect verdict returns 0s

def test_apply_to_cortex_clamping():
    engine = RLFCEngine()
    cortex = DummyCortex()
    
    # Try to push beyond max
    engine._apply_to_cortex(cortex, delta_ded=10.0, delta_gen=10.0, delta_mcts=100.0)
    assert cortex.routing.sigma_ded == engine._SIGMA_DED_MAX
    assert cortex.routing.sigma_gen == engine._SIGMA_GEN_MAX
    assert cortex.routing.sigma_mcts == engine._SIGMA_MCTS_MAX
    
    # Try to push below min
    engine._apply_to_cortex(cortex, delta_ded=-10.0, delta_gen=-10.0, delta_mcts=-100.0)
    assert cortex.routing.sigma_ded == engine._SIGMA_DED_MIN
    assert cortex.routing.sigma_gen == engine._SIGMA_GEN_MIN
    assert cortex.routing.sigma_mcts == engine._SIGMA_MCTS_MIN

def test_no_routing_cortex():
    engine = RLFCEngine()
    class EmptyCortex:
        pass
    cortex = EmptyCortex()
    # Should not raise exception
    engine._apply_to_cortex(cortex, 0.1, 0.1, 0.1)

def test_improvement_trend_empty():
    engine = RLFCEngine()
    assert engine.improvement_trend() == 0.0

def test_cosine_lr():
    engine = RLFCEngine(total_rounds=10)
    lr_start = engine._cosine_lr(0)
    lr_mid = engine._cosine_lr(5)
    lr_end = engine._cosine_lr(10)
    lr_over = engine._cosine_lr(15)
    
    assert lr_start == engine._LR_INITIAL
    assert lr_end == engine._LR_MIN
    assert lr_over == engine._LR_MIN
    assert engine._LR_MIN < lr_mid < engine._LR_INITIAL
