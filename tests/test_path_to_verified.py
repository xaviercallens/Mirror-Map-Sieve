import asyncio
from agents.euler.agent import EulerAgent

async def test_path_to_verified():
    agent = EulerAgent()
    
    print("Testing Euler Agent 'Path to Verified' Strategy...")
    print("=" * 60)
    
    # 1. Test INCOMPLETE with sorry
    query_sorry = "Check the verified status of this proof."
    proof_sorry = """theorem add_zero (n : Nat) : n + 0 = n := by
  sorry
"""
    print("\n[Test 1: Proof with sorry]")
    result = await agent.run(query=query_sorry, proof_code=proof_sorry)
    print(f"Status: {result.answer.get('status')}")
    print(f"Objections: {result.answer.get('objections')}")
    
    # 2. Test VERIFIED without sorry
    query_valid = "Run the path to verified."
    proof_valid = """theorem add_zero (n : Nat) : n + 0 = n := by
  rfl
"""
    print("\n[Test 2: Complete Proof]")
    # We will simulate the cloud_lean_compiler returning success since we are
    # pointing to a dummy endpoint if not deployed. We can just check that the tools were called.
    result = await agent.run(query=query_valid, proof_code=proof_valid)
    print(f"Status: {result.answer.get('status')}")
    print(f"Objections: {result.answer.get('objections')}")
    
    print("\nObservations:")
    for tool, obs in result.answer.get("observations", {}).items():
        if isinstance(obs, dict) and "message" in obs:
            print(f"  - {tool}: {obs.get('message')}")
        elif isinstance(obs, dict) and "issues" in obs:
             print(f"  - {tool}: {len(obs.get('issues'))} issues found.")
        else:
            print(f"  - {tool}: Executed")

if __name__ == "__main__":
    asyncio.run(test_path_to_verified())
