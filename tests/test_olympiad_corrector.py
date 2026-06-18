import pytest
from dataclasses import dataclass
from agents.euler.tools.olympiad_corrector import (
    correct_olympiad_solution, correct_solution_batch, OlympiadCorrectionReport,
    _audit_answer, _normalize, _answers_match, _has_sign_inconsistency,
    _contains_key_values, _find_vague_step, _compute_confidence_delta,
    FeedbackVerdict, ErrorClass
)

@dataclass
class DummyProblemType:
    value: str

@dataclass
class DummyProblemRecord:
    id: str
    problem_type: DummyProblemType
    solution_book: str
    numerical_answer: str

@dataclass
class DummySolution:
    final_answer: str
    reasoning_steps: list[str]
    confidence: float
    strategy_used: str

def test_correct_olympiad_solution_numeric_match():
    problem = DummyProblemRecord("test1", DummyProblemType("numeric"), "Sol", "42")
    sol = DummySolution("42", [], 0.5, "")
    fb = correct_olympiad_solution(problem, sol)
    assert fb.verdict == FeedbackVerdict.CORRECT
    assert fb.error_class == ErrorClass.NO_ERROR
    assert fb.confidence_delta > 0

def test_correct_olympiad_solution_vagueness():
    problem = DummyProblemRecord("test2", DummyProblemType("numeric"), "Sol", "42")
    sol = DummySolution("43", ["obviously x = 42"], 0.5, "")
    # Should get vagueness since "obviously" is used
    fb = correct_olympiad_solution(problem, sol)
    assert fb.verdict == FeedbackVerdict.PARTIAL
    assert fb.error_class == ErrorClass.VAGUENESS

def test_correct_olympiad_solution_sign_error():
    problem = DummyProblemRecord("test3", DummyProblemType("numeric"), "The answer is -42 and -5", "-42 and -5")
    sol = DummySolution("The answer is 42 and 6", ["so x=42"], 0.5, "")
    fb = correct_olympiad_solution(problem, sol)
    assert fb.verdict == FeedbackVerdict.COMPUTATION_ERROR
    assert fb.error_class == ErrorClass.SIGN_ERROR

def test_correct_olympiad_solution_incomplete():
    problem = DummyProblemRecord("test4", DummyProblemType("numeric"), "Sol", "123")
    sol = DummySolution("and therefore", ["we see that"], 0.5, "")
    fb = correct_olympiad_solution(problem, sol)
    assert fb.verdict == FeedbackVerdict.INCOMPLETE
    assert fb.error_class == ErrorClass.INCOMPLETE_SOLUTION

def test_correct_olympiad_solution_partial_key_values():
    problem = DummyProblemRecord("test5", DummyProblemType("numeric"), "Sol", "123.45 and 99")
    sol = DummySolution("I got 123.45 in the end maybe? Yes.", ["calc"], 0.5, "")
    fb = correct_olympiad_solution(problem, sol)
    assert fb.verdict == FeedbackVerdict.PARTIAL
    assert fb.error_class == ErrorClass.INCOMPLETE_SOLUTION

def test_correct_olympiad_solution_domain_violation():
    problem = DummyProblemRecord("test6", DummyProblemType("trigonometric"), "Sol", "0.5")
    sol = DummySolution("The final result is 1.5", ["calculate step"], 0.5, "")
    fb = correct_olympiad_solution(problem, sol)
    assert fb.verdict == FeedbackVerdict.PARTIAL
    assert fb.error_class == ErrorClass.DOMAIN_VIOLATION

def test_correct_olympiad_solution_wrong():
    problem = DummyProblemRecord("test7", DummyProblemType("numeric"), "Sol", "42")
    sol = DummySolution("The computed answer is 1337", ["did some stuff"], 0.5, "")
    fb = correct_olympiad_solution(problem, sol)
    assert fb.verdict == FeedbackVerdict.CONCEPTUAL_ERROR
    assert fb.error_class == ErrorClass.STRATEGY_ERROR

def test_correct_solution_batch():
    problem = DummyProblemRecord("test8", DummyProblemType("numeric"), "Sol", "42")
    sol1 = DummySolution("42", [], 0.5, "")
    sol2 = DummySolution("The computed answer is 1337", [], 0.5, "")
    
    report = correct_solution_batch([problem, problem], [sol1, sol2])
    assert report.total == 2
    assert report.correct == 1
    assert report.errors == 1
    assert report.score_pct == 50.0
    report.print_summary()

def test_proof_type_strategy_match():
    problem = DummyProblemRecord("test9", DummyProblemType("proof"), "The strategy uses dp and factoring", "")
    sol = DummySolution("we use d2pq and dp and factoring", ["d2pq is used"], 0.5, "algebraic_factoring")
    fb = correct_olympiad_solution(problem, sol, round_number=1)
    assert fb.verdict == FeedbackVerdict.CORRECT

def test_proof_type_semantic_match():
    problem = DummyProblemRecord("test10", DummyProblemType("proof"), "A long solution with contradiction and prime and infinite and euclid", "")
    sol = DummySolution("A long answer using contradiction prime infinite euclid", [], 0.5, "none")
    fb = correct_olympiad_solution(problem, sol, round_number=2)
    assert fb.verdict == FeedbackVerdict.CORRECT

def test_proof_type_partial():
    problem = DummyProblemRecord("test11", DummyProblemType("proof"), "Some words", "")
    sol = DummySolution("therefore it is proved", [], 0.5, "none")
    fb = correct_olympiad_solution(problem, sol)
    assert fb.verdict == FeedbackVerdict.PARTIAL
    assert fb.error_class == ErrorClass.LOGICAL_GAP

def test_normalize():
    assert _normalize("  HELLO   World.  ") == "hello world"

def test_answers_match():
    assert _answers_match("x=42", "42")
    assert not _answers_match("43", "42")
    assert _answers_match("42", "42")

def test_compute_confidence_delta():
    assert _compute_confidence_delta(FeedbackVerdict.CORRECT, 0.99) == pytest.approx(0.01)
    assert _compute_confidence_delta(FeedbackVerdict.PARTIAL, 0.5) < 0
    assert _compute_confidence_delta(FeedbackVerdict.COMPUTATION_ERROR, 0.5) < 0
    assert _compute_confidence_delta(FeedbackVerdict.CONCEPTUAL_ERROR, 0.5) < 0
    assert _compute_confidence_delta(FeedbackVerdict.INCOMPLETE, 0.5) < 0
