import pytest
from unittest.mock import MagicMock
from agents.galois.tools.mcts_reasoner import ThoughtNode, expand_node, process_reward_model_eval, MCTSReasoner, _REPLAY_BUFFER

from agents.socrates.dialectic_engine import DialecticEngine
from agents.socrates.agent import SocratesAgent

@pytest.mark.asyncio
async def test_galois_mcts_rpe_logic(mocker):
    """Test Dopaminergic RPE Logic and Hippocampal Replay in Galois MCTS."""
    # Clear the global replay buffer for this test
    _REPLAY_BUFFER.clear()
    
    # Mock genai Client
    mock_client = MagicMock()
    
    # We want expand_node to return a step "STEP: x = 1"
    class MockResponseExpand:
        text = "STEP: Let x = 1\nSTEP: Let y = 2"
    
    # We want PRM to return a high float score to trigger RPE
    class MockResponseEval:
        text = "The score is 0.95"
    
    def side_effect(*args, **kwargs):
        if "propose" in kwargs.get("contents", "").lower():
            return MockResponseExpand()
        return MockResponseEval()
        
    mock_client.models.generate_content.side_effect = side_effect
    mocker.patch("agents.galois.tools.mcts_reasoner.genai.Client", return_value=mock_client)
    
    # Run the MCTS search
    reasoner = MCTSReasoner(max_iterations=2, expansion_width=2)
    best_path = reasoner.run("Solve 2x = 2")
    
    assert "Let x = 1" in best_path or "Let y = 2" in best_path
    assert len(_REPLAY_BUFFER) > 0
    assert "Let x = 1" in _REPLAY_BUFFER[0] or "Let y = 2" in _REPLAY_BUFFER[0]

@pytest.mark.asyncio
async def test_socrates_dialectic_swarm_scaling_and_dopamine(mocker):
    """Test Socrates research-level complexity scaling and dopamine synthesis."""
    engine = DialecticEngine()
    
    # Create mock agents
    mock_galileo = MagicMock()
    class DummyResult:
        def __init__(self, answer, confidence, cost_usd=0.0):
            self.answer = answer
            self.confidence = confidence
            self.cost_usd = cost_usd
            self.proofs = []
    
    async def async_run_galileo(*args, **kwargs):
        return DummyResult("Galileo evidence", 0.90)
    mock_galileo.run = async_run_galileo
    
    mock_euler = MagicMock()
    async def async_run_euler(*args, **kwargs):
        return DummyResult({"status": "VERIFIED"}, 0.95)
    mock_euler.run = async_run_euler
    
    # Run dialectic with research complexity
    outcome = await engine.run(
        "Is P = NP?", 
        galileo=mock_galileo, 
        euler=mock_euler, 
        max_cycles=1, 
        complexity_level="research"
    )
    
    assert outcome.converged is True
    assert outcome.final_confidence == 0.93  # (0.9 + 0.95) / 2 = 0.925 -> rounds to 0.93 due to float representation
    
    # Test the agent synthesis for dopamine feedback
    plan = {"complexity": "research"}
    observations = {
        "dialectic": {
            "status": "converged",
            "cycles": 1,
            "converged": True,
            "final_confidence": outcome.final_confidence,
            "synthesis": outcome.synthesis
        }
    }
    synthesis_str = SocratesAgent._synthesise(plan, observations)
    assert "Dopamine Delta: +0.43" in synthesis_str
    assert "Tactic succeeded beyond expectations" in synthesis_str
