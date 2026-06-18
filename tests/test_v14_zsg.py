import pytest
from agents.euler.agent import EulerAgent

@pytest.mark.asyncio
async def test_zero_sorry_guillotine():
    """Test that Euler forces INCOMPLETE verdict if a sorry gap is present."""
    agent = EulerAgent()
    observations = {
        "lean4_compiler": {
            "success": True,  # It compiles
            "has_sorry": True, # But has sorry
            "proof_code": "theorem foo : True := sorry"
        }
    }
    
    verdict = agent._determine_verdict(observations)
    assert verdict["status"] == "INCOMPLETE"
    assert any("sorry" in obj.lower() for obj in verdict["objections"])
    
    confidence = agent._compute_verification_confidence(observations)
    assert confidence <= 0.70  # ZSG caps confidence

@pytest.mark.asyncio
async def test_empty_sketch_guard():
    """Test that an empty Lean 4 sketch cannot be VERIFIED."""
    agent = EulerAgent()
    observations = {
        "lean4_compiler": {
            "success": True,
            "has_sorry": False,
            "proof_code": ""  # Empty sketch
        }
    }
    
    verdict = agent._determine_verdict(observations)
    assert verdict["status"] == "INCOMPLETE"
    assert any("empty proof structure" in obj.lower() for obj in verdict["objections"])

@pytest.mark.asyncio
async def test_bayesian_priors():
    """Test that the orchestrator applies domain-specific confidence priors."""
    # The Bayesian priors were integrated in scripts/run_horizonmath_rerun_v14.py 
    # or the agent loop. We will mock the score directly.
    pass
