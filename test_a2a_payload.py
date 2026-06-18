import asyncio
import os
import sys

# Add project root to PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from agents.common.a2a_models import ConjecturePayload, ContextBindingError
from agents.galois.tools.conjecture_generator import generate_conjecture_payload
from agents.euler.agent import EulerAgent

async def main():
    print("=== Testing V12.1 A2A Payload Update ===")
    
    # 1. Test Valid Generation
    print("\n--- Test 1: Valid Dynamic Generation ---")
    valid_payload_json = generate_conjecture_payload("prob_valid", "Solve the elliptic integral.")
    print(f"Generated Payload JSON:\n{valid_payload_json[:150]}...")
    
    euler = EulerAgent()
    result = await euler.audit_conjecture(valid_payload_json)
    print(f"Euler Audit Result: {result}")
    
    # 2. Test Hallucinated Mock Generator Catch
    print("\n--- Test 2: Catching Galois Hallucination ('solution manifold') ---")
    try:
        hallucinated_payload_json = generate_conjecture_payload("prob_hallucinate", "Please hallucinate")
        print("FAIL: Should have raised ContextBindingError on creation")
    except Exception as e:
        print(f"SUCCESS: Caught generation error: {e}")

    # 3. Test Poisoned Payload received by Euler (Euler Mock Catch)
    print("\n--- Test 3: Catching Euler Mock ('add_zero') in Payload Validation ---")
    poisoned_json = '{"problem_id": "prob_poison", "statement": "Valid statement", "lean4_sketch": {"code_base64": "dGhlb3JlbSBhZGRfemVybyAobjogTmF0KSA6IG4gKyAwID0gbiA6PSBieSBvcHJlYW0="}}'
    
    result_poisoned = await euler.audit_conjecture(poisoned_json)
    print(f"Euler Audit Result for Poisoned Payload: {result_poisoned}")
    
    # Verify the error string explicitly names the ContextBindingError
    assert "Euler Mock Leak Detected" in result_poisoned.get("error", ""), "Did not catch Euler mock!"
    print("\nAll schema validations are working as expected.")

if __name__ == "__main__":
    asyncio.run(main())
