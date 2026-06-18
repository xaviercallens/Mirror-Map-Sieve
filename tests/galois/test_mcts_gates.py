import pytest
from agents.galois.init_repl import pre_load_env

def test_repl_immutability():
    """Verify that multiple tactic branches do not corrupt the REPL proofState."""
    env_id, proc = pre_load_env("verifiers/lean4")
    assert env_id is not None, "Failed to cache env ID"
    
    # TODO: Implement full REPL branch test
    # state1 = init_proof(theorem...)
    # state2 = execute_tactic(state1, "tactic A")
    # state3 = execute_tactic(state1, "tactic B")
    # Ensure executing from state1 multiple times doesn't mutate it
    
    if proc:
        proc.kill()

@pytest.mark.skip(reason='Not implemented — stub from v4.0 scaffolding')
def test_puct_pruning():
    """Verify that the PUCT algorithm correctly prunes low-probability branches."""
    # TODO: Implement mock tree and verify visit counts based on priors
    pass
