import pytest
from unittest.mock import patch, MagicMock

# 1. Test Galois Agent Query Routing (No hardcoded "Generate innovative mathematics")
from agents.galois.agent import GaloisAgent

@pytest.mark.asyncio
async def test_galois_agent_uses_dynamic_query():
    agent = GaloisAgent()
    # Mock the tool to see what argument it receives
    mock_conjecture_generator = MagicMock(return_value={"status": "mocked"})
    agent._tools["conjecture_generator"] = mock_conjecture_generator
    
    # We pass a specific query
    plan = await agent.think({"query": "Prove the Riemann Hypothesis"})
    await agent.act(plan)
    
    # Verify the tool was called with the actual query, not the hardcoded string
    # Assuming the tool might be called if the PFC routed to it. Let's force it:
    plan["tools"] = ["conjecture_generator"]
    await agent.act(plan)
    
    mock_conjecture_generator.assert_called_with(problem="Prove the Riemann Hypothesis")


# 2. Test SymBrain v6 Cortex (No hardcoded math.sin Levy simulation)
from agents.galois.symbrain.cortex_v6 import SymBrainV6Cortex

def test_cortex_v6_uses_dynamic_energy_metrics():
    cortex = SymBrainV6Cortex()
    result = cortex.optimize_fractional_rlcf(loss=0.5)
    
    # The old hardcoded energy_saved_mj was always exactly 2.45
    assert result.get("energy_saved_mj", 0.0) != 2.45, "Should not use hardcoded 2.45 MJ"


# 3. Test MCTS Reasoner (Wires V11 cortex instead of isolated RPE)
from agents.galois.tools.mcts_reasoner import MCTSReasoner

def test_mcts_reasoner_cortex_dependency():
    """Verify that MCTS Reasoner accepts and uses the cortex object via dependency injection."""
    from agents.galois.symbrain.cortex_v11 import SymBrainV11Cortex
    from agents.galois.symbrain.cortex_v4 import GaloisCortexConfig
    
    config = GaloisCortexConfig()
    mock_cortex = MagicMock(spec=SymBrainV11Cortex(config))
    mock_cortex.calculate_reward_prediction_error.return_value = 0.6
    
    # We don't want to actually run the genai client, so just check instantiation
    reasoner = MCTSReasoner(max_iterations=1, expansion_width=1, cortex=mock_cortex)
    
    with patch("agents.galois.tools.mcts_reasoner.process_reward_model_eval", return_value=0.9):
        with patch("agents.galois.tools.mcts_reasoner.expand_node"):
            # Mock genai Client
            with patch("agents.galois.tools.mcts_reasoner.genai.Client"):
                reasoner.run("Problem")
            
    # Verify the cortex was actually consulted for RPE
    mock_cortex.calculate_reward_prediction_error.assert_called()


# 4. Test NVIDIA NIM (Uses httpx instead of simulating silently)
from agents.galileo.tools.nvidia_nim import query_nvidia_nim
import os

@patch("agents.galileo.tools.nvidia_nim.NIM_API_KEY", "dummy_key")
@patch("httpx.Client.post")
def test_nvidia_nim_makes_real_request(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {"total_mass": 5610.0, "embeddings": []}
    mock_post.return_value = mock_response

    input_data = {"sequence": "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSH"}
    result = query_nvidia_nim("BioNeMo-ESM2", input_data)
    
    # Ensure it actually tried to post
    mock_post.assert_called_once()



# 5. Test SymBrain v12 PSLQ Evaluator (No hardcoded identity matches)
from agents.galois.tools.pslq_leaf_evaluator import PSLQLeafEvaluator
import mpmath

def test_pslq_leaf_evaluator_uses_mpmath_pslq():
    """Verify that PSLQLeafEvaluator dynamically delegates to mpmath.pslq instead of stubs."""
    evaluator = PSLQLeafEvaluator(dps=50)
    
    with patch("agents.galois.pslq_reduction.mpmath.pslq", return_value=[1, -1, 0, 0, 0, 0]) as mock_pslq:
        # Evaluate candidate to trigger pass A (hunt_linear)
        evaluator.evaluate_candidate(target=mpmath.mpf("3.14"), candidate_expr="3.14")
        
        # Verify mpmath.pslq was called
        mock_pslq.assert_called()
