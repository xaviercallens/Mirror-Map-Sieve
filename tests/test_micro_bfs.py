import os
import sys
import json
import glob

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.galois.lean_repl import LeanREPL

def main():
    workspace = "/Users/xcallens/xdev/SocrateAI-Scientific-Agora/verifiers/lean4"
    repl = LeanREPL(workspace)
    
    # ---------------------------------------------------------
    # Test 1: Micro-BFS on a simple theorem
    # ---------------------------------------------------------
    print("--- Test 1: Simple Theorem Micro-BFS ---")
    content = """theorem id_test (p : Prop) (h : p) : p := by
  sorry
"""
    print("Initializing REPL with simple theorem...")
    res = repl.init_proof(content)
    print("Init response:", json.dumps(res, indent=2))
    
    sorries = res.get("sorries", [])
    if not sorries:
        print("No sorries found in Test 1!")
        repl.close()
        return
        
    proof_state = sorries[0]["proofState"]
    goal = sorries[0]["goal"]
    print(f"\nExtracted proofState: {proof_state}")
    print(f"Goal:\n{goal}")
    
    # Send a known working tactic: "exact h"
    tactic = "exact h"
    print(f"\nExecuting tactic: {tactic}")
    tac_res = repl.execute_tactic(proof_state, tactic)
    print("Tactic response:", json.dumps(tac_res, indent=2))
    
    if "goals" in tac_res and isinstance(tac_res["goals"], list):
        print(f"SUCCESS! Got {len(tac_res['goals'])} new subgoals.")
        for i, g in enumerate(tac_res["goals"]):
            print(f"Subgoal {i+1}:\n{g}\n")
    else:
        print("FAILED to get next goals.")
        
    # ---------------------------------------------------------
    # Test 2: First HorizonMath problem
    # ---------------------------------------------------------
    print("\n--- Test 2: First HorizonMath Problem ---")
    v16_dir = "/Users/xcallens/xdev/SocrateAI-Scientific-Agora/achievement_output/v16_offline"
    lean_files = glob.glob(os.path.join(v16_dir, "*.lean"))
    if not lean_files:
        print("Could not find any HorizonMath .lean files in v16_offline.")
        repl.close()
        return
        
    lean_files.sort()
    first_problem_file = lean_files[0]
    print(f"Testing on {os.path.basename(first_problem_file)}...")
    
    with open(first_problem_file, "r") as f:
        hm_content = f.read()
        
    # Find a sorry and send it to REPL
    print("Sending full problem to REPL...")
    hm_res = repl.init_proof(hm_content)
    # The response might be large, just show summary
    hm_sorries = hm_res.get("sorries", [])
    
    if hm_sorries:
        print(f"SUCCESS! Found {len(hm_sorries)} sorries.")
        hm_ps = hm_sorries[0]["proofState"]
        hm_goal = hm_sorries[0]["goal"]
        print(f"First gap proofState: {hm_ps}")
        print(f"Goal context:\n{hm_goal}")
        
        # Test an arbitrary tactic like "simp" just to see connection works
        print("\nSending 'simp' tactic to the first gap...")
        tac_res_hm = repl.execute_tactic(hm_ps, "simp")
        print("Tactic response:", json.dumps(tac_res_hm, indent=2))
        if "goals" in tac_res_hm:
            print("Successfully received tactic state for HorizonMath problem!")
    else:
        print("No sorries found in HorizonMath problem or REPL error:")
        print(json.dumps(hm_res, indent=2))

    repl.close()

if __name__ == "__main__":
    main()
