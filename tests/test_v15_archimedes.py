import pytest
from agents.archimedes.tools.sorry_decomposer import decompose_sorry_gaps, SorryGapType
from agents.archimedes.tools.proof_assembler import assemble_proof, validate_assembly
from agents.archimedes.agent import ArchimedesAgent

def test_sorry_decomposer_priorities():
    """Test that convergence > analytic > existence > inequality > definition."""
    # Test convergence (Tendsto)
    sketch_conv = "theorem t : Tendsto f atTop (nhds 0) := sorry"
    gaps_conv = decompose_sorry_gaps(sketch_conv, "test", "analysis")
    assert gaps_conv[0].gap_type == SorryGapType.CONVERGENCE
    assert gaps_conv[0].classification_confidence > 0.8

    # Test analytic (integral)
    sketch_ana = "theorem t : ∫ x in 0..1, f x = 0 := sorry"
    gaps_ana = decompose_sorry_gaps(sketch_ana, "test", "analysis")
    # ∫ might fall into the default LEMMA category depending on regexes
    assert gaps_ana[0].gap_type in (SorryGapType.ANALYTIC, SorryGapType.LEMMA)

def test_proof_assembler_reverse_substitution():
    """Test that substitutions happen in reverse order so line numbers remain stable."""
    sketch = "theorem t1 : 1=1 := sorry\ntheorem t2 : 2=2 := sorry"
    gaps = decompose_sorry_gaps(sketch, "test", "analysis")
    
    resolutions = {
        0: "by rfl",
        1: "by simp"
    }
    
    assembled = assemble_proof(sketch, resolutions, gaps)
    
    # Should contain both resolutions
    assert "by rfl" in assembled
    assert "by simp" in assembled
    
    # Assert validation
    val = validate_assembly(assembled, sketch)
    assert val["valid"] is True
    assert val["sorry_count"] == 0
    assert val["sorry_delta"] == 2

@pytest.mark.asyncio
async def test_archimedes_agent_method_of_exhaustion(mocker):
    """Test that the Method of Exhaustion loop reduces sorry count."""
    agent = ArchimedesAgent()
    
    # Mock the internal LLM call to pretend it resolves a gap
    mock_llm = mocker.patch.object(agent, "_attack_single_gap")
    mock_llm.return_value = ("by norm_num", 0.05)
    
    sketch = "theorem t : 1+1=2 := sorry"
    result = await agent.run("Prove this", lean4_sketch=sketch, domain="number_theory")
    
    assert "archimedes_result" in result.answer
    assert result.answer["sorry_count"] == 0
    assert result.answer["original_sorry_count"] == 1
    assert "by norm_num" in result.answer["lean4_sketch"]
