import sys
import os
import json
import logging
import time
from typing import List, Dict, Any

from agents.galois.lean_repl import LeanREPL
from agents.galois.mcts_node import ProofNode
from agents.galois.mcts_policy import MCTSPolicy

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

STATUS_PATH = "/Users/xcallens/.gemini/antigravity/brain/142e4281-5564-4819-8826-7d615d389330/artifacts/validation_mcts_status.json"

THEOREMS = {
    "Level 1: AM-GM Bounds": """import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.Ring

theorem am_gm_2 (x y : ℝ) : 2 * x * y ≤ x^2 + y^2 := by
  sorry
""",
    "Level 2: Induction & Sub-Goals (Sum of Odds)": """import Mathlib.Tactic

open Finset
open scoped BigOperators

theorem sum_odds (n : ℕ) : (∑ i ∈ range n, (2 * i + 1)) = n ^ 2 := by
  sorry
""",
    "Level 3: Cantor's Theorem (Set Theory / Deep Logic)": """import Mathlib.Data.Set.Basic

theorem cantor_surjective {α : Type} (f : α → Set α) : ¬ Function.Surjective f := by
  sorry
"""
}

def trace_victory(node: ProofNode) -> List[str]:
    tactics = []
    curr = node
    while curr.parent is not None:
        tactics.append(curr.tactic_applied)
        curr = curr.parent
    return list(reversed(tactics))

def write_status(status_dict: dict):
    try:
        os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
        with open(STATUS_PATH, "w") as f:
            json.dump(status_dict, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write status: {e}")

def run_mcts(theorem_name: str, theorem_code: str, policy: MCTSPolicy, status_dict: dict) -> bool:
    logger.info(f"Starting MCTS for {theorem_name}...")
    status_dict[theorem_name] = {
        "status": "RUNNING",
        "iterations": 0,
        "current_goal": "Initializing REPL...",
        "tactics_tried": [],
        "proof_found": None,
        "error_message": None,
        "start_time": time.time(),
        "elapsed_seconds": 0
    }
    write_status(status_dict)
    
    repl = None
    try:
        repl = LeanREPL(workspace_dir="/Users/xcallens/xdev/SocrateAI-Scientific-Agora/verifiers/lean4")
        init_res = repl.init_proof(theorem_code)
        
        if "sorries" not in init_res or len(init_res["sorries"]) == 0:
            status_dict[theorem_name]["status"] = "FAILED"
            status_dict[theorem_name]["error_message"] = "No sorry found in theorem."
            write_status(status_dict)
            return False
            
        root_state_id = init_res["sorries"][0]["proofState"]
        root_goal = init_res["sorries"][0]["goal"]
        
        root_node = ProofNode(state_id=root_state_id, goal_state=root_goal)
        status_dict[theorem_name]["current_goal"] = root_goal
        write_status(status_dict)
        
        max_iterations = 250
        tactics_tried_set = set()
        failed_tactics_by_goal = {}
        
        for i in range(max_iterations):
            status_dict[theorem_name]["iterations"] = i + 1
            status_dict[theorem_name]["elapsed_seconds"] = int(time.time() - status_dict[theorem_name]["start_time"])
            write_status(status_dict)
            
            logger.info(f"[{theorem_name}] Iteration {i+1}/{max_iterations}")
            
            # 1. Selection
            curr = root_node
            while curr.children:
                best_child = None
                best_score = float('-inf')
                for child in curr.children:
                    score = child.uct_score()
                    if score > best_score:
                        best_score = score
                        best_child = child
                if best_child is None or best_score == float('-inf'):
                    break
                curr = best_child
                
            if curr.is_terminal:
                tactics = trace_victory(curr)
                status_dict[theorem_name]["status"] = "SUCCESS"
                status_dict[theorem_name]["proof_found"] = tactics
                status_dict[theorem_name]["current_goal"] = "Proof Solved!"
                write_status(status_dict)
                logger.info(f"🏆 Proved {theorem_name}! Tactics: {tactics}")
                return True
                
            if curr.is_dead_end or (curr.parent and curr.children and all(c.is_dead_end for c in curr.children)):
                curr.is_dead_end = True
                temp = curr
                while temp:
                    temp.visits += 1
                    temp = temp.parent
                continue
                
            # 2. Expansion
            logger.info(f"[{theorem_name}] Expanding state {curr.state_id} | Goal: {curr.goal_state.replace('\n', ' ')}")
            status_dict[theorem_name]["current_goal"] = curr.goal_state
            write_status(status_dict)
            
            failed_tactics = failed_tactics_by_goal.get(curr.goal_state.strip(), [])
            tactics = policy.generate_tactics(curr.goal_state, failed_tactics=failed_tactics)
            if not tactics:
                curr.is_dead_end = True
                continue
                
            logger.info(f"[{theorem_name}] Policy generated: {tactics}")
            
            # 3. Simulation
            for tactic in tactics:
                tactics_tried_set.add(tactic)
                status_dict[theorem_name]["tactics_tried"] = list(tactics_tried_set)
                write_status(status_dict)
                
                logger.info(f"  -> Executing: {tactic}")
                res = repl.execute_tactic(curr.state_id, tactic)
                
                is_error = False
                if "messages" in res:
                    for msg in res["messages"]:
                        if msg.get("severity") == "error":
                            is_error = True
                            break
                            
                if is_error or "proofState" not in res:
                    child_node = ProofNode(state_id=-1, goal_state="", parent=curr, tactic_applied=tactic)
                    child_node.is_dead_end = True
                    child_node.value = -1.0
                    curr.children.append(child_node)
                    failed_tactics_by_goal.setdefault(curr.goal_state.strip(), []).append(tactic)
                else:
                    new_state_id = res["proofState"]
                    new_goal = "" if not res.get("goals") else res["goals"][0]
                    child_node = ProofNode(state_id=new_state_id, goal_state=new_goal, parent=curr, tactic_applied=tactic)
                    
                    if new_goal.strip() == curr.goal_state.strip():
                        child_node.is_dead_end = True
                        child_node.value = -1.0
                        failed_tactics_by_goal.setdefault(curr.goal_state.strip(), []).append(tactic)
                        
                    curr.children.append(child_node)
                    
                    if child_node.is_terminal:
                        tactics_trace = trace_victory(child_node)
                        status_dict[theorem_name]["status"] = "SUCCESS"
                        status_dict[theorem_name]["proof_found"] = tactics_trace
                        status_dict[theorem_name]["current_goal"] = "Proof Solved!"
                        write_status(status_dict)
                        logger.info(f"🏆 Proved {theorem_name}! Tactics: {tactics_trace}")
                        return True
                        
            # 4. Backpropagation
            temp = curr
            while temp:
                temp.visits += 1
                temp = temp.parent
                
        status_dict[theorem_name]["status"] = "FAILED"
        status_dict[theorem_name]["error_message"] = "Max iterations reached without proof."
        write_status(status_dict)
        return False
        
    except Exception as e:
        logger.error(f"Error running MCTS for {theorem_name}: {e}", exc_info=True)
        status_dict[theorem_name]["status"] = "FAILED"
        status_dict[theorem_name]["error_message"] = str(e)
        write_status(status_dict)
        return False
    finally:
        if repl:
            repl.close()

def main():
    policy = MCTSPolicy()
    
    status_dict = {}
    for name in THEOREMS.keys():
        status_dict[name] = {
            "status": "PENDING",
            "iterations": 0,
            "current_goal": None,
            "tactics_tried": [],
            "proof_found": None,
            "error_message": None,
            "elapsed_seconds": 0
        }
    write_status(status_dict)
    
    for name, code in THEOREMS.items():
        run_mcts(name, code, policy, status_dict)
        
    logger.info("Validation run finished.")

if __name__ == "__main__":
    main()
