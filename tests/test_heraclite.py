import pytest
from dataclasses import dataclass
from agents.heraclite.agent import HeracliteAgent, HeracliteComparisonReport
from alexandrie.metadata import ArtifactType, RoomType
from unittest.mock import MagicMock, patch

@dataclass
class DummyIMODomain:
    value: str

@dataclass
class DummyDifficulty:
    value: str

@dataclass
class DummyIMOProblem:
    id: str
    imo_domain: DummyIMODomain
    difficulty: DummyDifficulty
    title: str
    question: str
    lean4_template: str

@dataclass
class DummyVerdict:
    value: str

@dataclass
class DummyFeedback:
    problem_id: str
    verdict: DummyVerdict

@dataclass
class DummyProposal:
    problem_id: str
    strategy_used: str

def test_heraclite_comparison_report_print():
    report = HeracliteComparisonReport(
        round_number=1,
        approach_matches=10,
        total_problems=10,
        correct_solutions=5,
        novel_approaches=0,
        mean_alignment=0.9,
        mean_completeness=0.8
    )
    # Should not throw
    report.print_summary()

@pytest.mark.asyncio
async def test_heraclite_agent_lifecycle():
    agent = HeracliteAgent()
    # Mock Alexandrie Hub to avoid side effects
    agent._hub = MagicMock()
    
    res = await agent.think({"query": "test"})
    assert res == {"tools": [], "estimated_cost": 0.0}
    
    act_res = await agent.act(res)
    assert act_res == {}
    
    run_res = await agent.run("hello")
    assert run_res.answer == "Heraclite is standing ready."

def test_ingest_problems():
    agent = HeracliteAgent()
    agent._hub = MagicMock()
    
    probs = [
        DummyIMOProblem("A1", DummyIMODomain("Algebra"), DummyDifficulty("Easy"), "A1 Title", "Question?", "template"),
        DummyIMOProblem("C2", DummyIMODomain("Combinatorics"), DummyDifficulty("Hard"), "C2 Title", "Question?", None)
    ]
    
    agent.ingest_problems_to_alexandrie(probs)
    assert agent._hub.store_artifact.call_count == 2
    args, kwargs = agent._hub.store_artifact.call_args_list[0]
    assert kwargs["artifact_id"] == "sealed_problem_A1"

@patch("agents.heraclite.agent.get_official_solution")
def test_compare_proposals(mock_get_official):
    agent = HeracliteAgent()
    mock_get_official.return_value = "Official strategy involves concave function."
    
    prop1 = DummyProposal("A1", "I used a concave approach.")
    prop2 = DummyProposal("C2", "I used induction.")
    
    fb1 = DummyFeedback("A1", DummyVerdict("correct"))
    fb2 = DummyFeedback("C2", DummyVerdict("incorrect"))
    
    report = agent.compare_proposals([prop1, prop2], [fb1, fb2], round_number=1)
    
    assert report.total_problems == 2
    assert report.approach_matches == 1  # prop1 matches "concave"
    assert report.novel_approaches == 1  # prop2 doesn't match
    assert report.correct_solutions == 1 # fb1 is correct
    assert report.mean_alignment == 0.85

def test_store_comparison_report():
    agent = HeracliteAgent()
    agent._hub = MagicMock()
    
    report = HeracliteComparisonReport(
        round_number=2, approach_matches=1, total_problems=2,
        correct_solutions=1, novel_approaches=1, mean_alignment=0.8, mean_completeness=0.5
    )
    
    agent.store_comparison_report(report)
    assert agent._hub.store_artifact.call_count == 1
    args, kwargs = agent._hub.store_artifact.call_args_list[0]
    assert kwargs["artifact_id"] == "heraclite_comparison_round_2"
    assert kwargs["tags"] == ["heraclite-comparison", "round-2"]
