import pytest
import os
import json
from dataclasses import dataclass
from pathlib import Path
from agents.galois.olympiad.inference_transfer import InferenceTransferBank, TransferVector
from agents.galois.olympiad.olympiad_session import OlympiadSession, OlympiadRoundResult
from agents.galois.olympiad.rlfc_engine import RLFCSigmaUpdate, MistakeFingerprint, ErrorClass

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

def test_inference_transfer_bank(tmp_path):
    bank = InferenceTransferBank(vault_root=str(tmp_path))
    
    # Empty load
    assert bank.load() is None
    
    # Test record empty
    vec = bank.record_transfer([], [])
    assert vec.round_number == 0
    assert bank.load() is not None
    
    updates = [
        RLFCSigmaUpdate(delta_sigma_ded=0.1, delta_sigma_gen=-0.1, delta_sigma_mcts=1.0, batch_score=0.8, improvement=0.2),
        RLFCSigmaUpdate(delta_sigma_ded=0.05, delta_sigma_gen=-0.05, delta_sigma_mcts=0.5, batch_score=0.9, improvement=0.1)
    ]
    
    fps = [
        MistakeFingerprint("prob1", ErrorClass.SIGN_ERROR, "Fix signs", frequency=2),
        MistakeFingerprint("prob2", ErrorClass.LOGICAL_GAP, "Fix logic", frequency=1)
    ]
    
    vec2 = bank.record_transfer(updates, fps)
    assert vec2.round_number == 2
    assert vec2.cumulative_delta_ded == pytest.approx(0.15)
    assert vec2.best_score_seen == 0.9
    assert len(vec2.avoidance_strategies) == 2
    
    loaded = bank.load()
    assert loaded.round_number == 2
    assert loaded.best_score_seen == 0.9
    
    prompt = bank.get_avoidance_prompt_block()
    assert "SIGN_ERROR" in prompt
    assert "LOGICAL_GAP" in prompt

def test_apply_transfer(tmp_path):
    bank = InferenceTransferBank(vault_root=str(tmp_path))
    updates = [RLFCSigmaUpdate(delta_sigma_ded=0.2, delta_sigma_gen=0.2, delta_sigma_mcts=1.0, batch_score=1.0, improvement=0.0)]
    bank.record_transfer(updates, [])
    
    cortex = DummyCortex()
    res = bank.apply_transfer(cortex)
    assert res["applied"] is True
    assert cortex.routing.sigma_ded == pytest.approx(0.7)
    
    res_no_routing = bank.apply_transfer(object())
    assert res_no_routing["applied"] is False

def test_olympiad_session():
    session = OlympiadSession(session_name="Test")
    assert session.current_round == 0
    
    session.start_round()
    update1 = RLFCSigmaUpdate(improvement=0.0)
    res1 = session.end_round(10, 5, update1)
    
    assert res1.round_number == 1
    assert res1.score_pct == 50.0
    
    session.start_round()
    update2 = RLFCSigmaUpdate(improvement=20.0)
    res2 = session.end_round(10, 7, update2)
    
    assert res2.round_number == 2
    assert res2.score_pct == 70.0
    
    assert session.best_round == res2
    assert session.worst_round == res1
    assert session.improvement_trend() == pytest.approx(20.0)
    
    summary = session.summary()
    assert summary["total_rounds"] == 2
    assert summary["best_score"] == 70.0
    
    session.print_round_banner(res1)
    session.print_round_banner(res2)
