import sys
import json
import logging
from typing import List, Optional

from agents.galois.lean_repl import LeanREPL
from agents.galois.mcts_node import ProofNode
from agents.galois.mcts_policy import MCTSPolicy

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def trace_victory(node: ProofNode) -> List[str]:
    tactics = []
    curr = node
    while curr.parent is not None:
        tactics.append(curr.tactic_applied)
        curr = curr.parent
    return list(reversed(tactics))

def main():
    # 1. Initialize Policy and REPL
    policy = MCTSPolicy()
    
    theorem_content = """theorem my_and_comm (p q : Prop) : p ∧ q → q ∧ p := by
  sorry
"""
    
    logger.info("Initializing Lean REPL...")
    repl = LeanREPL(workspace_dir="/Users/xcallens/xdev/SocrateAI-Scientific-Agora/verifiers/lean4")
    
    init_res = repl.init_proof(theorem_content)
    logger.info(f"init_res: {json.dumps(init_res, indent=2)}")
    if "sorries" not in init_res or len(init_res["sorries"]) == 0:
        logger.error("No sorry found in theorem.")
        return
        
    root_state_id = init_res["sorries"][0]["proofState"]
    root_goal = init_res["sorries"][0]["goal"]
    
    root_node = ProofNode(state_id=root_state_id, goal_state=root_goal)
    
    max_iterations = 100
    
    for i in range(max_iterations):
        logger.info(f"\n--- MCTS Iteration {i+1} ---")
        
        # 1. Selection
        curr = root_node
        # Traverse until we find a node with no children, or all children are dead ends
        while curr.children:
            # Pick child with highest UCT
            best_child = None
            best_score = float('-inf')
            
            for child in curr.children:
                score = child.uct_score()
                if score > best_score:
                    best_score = score
                    best_child = child
                    
            if best_child is None or best_score == float('-inf'):
                # All children are dead ends
                break
                
            curr = best_child
            
        if curr.is_terminal:
            logger.info("Terminal node selected! Victory trace:")
            tactics = trace_victory(curr)
            for t in tactics:
                logger.info(f"  {t}")
            break
            
        if curr.is_dead_end or (curr.parent and curr.children and all(c.is_dead_end for c in curr.children)):
            logger.info("Selected a dead end or fully exhausted node. Marking as dead end.")
            curr.is_dead_end = True
            # Backprop failure
            temp = curr
            while temp:
                temp.visits += 1
                temp = temp.parent
            continue
            
        # 2. Expansion
        logger.info(f"Expanding Node {curr.state_id} | Goal: {curr.goal_state.replace(chr(10), ' ')}")
        tactics = policy.generate_tactics(curr.goal_state)
        
        if not tactics:
            logger.info("Policy returned no tactics. Marking as dead end.")
            curr.is_dead_end = True
            continue
            
        logger.info(f"Generated {len(tactics)} tactics: {tactics}")
        
        # 3. Simulation (Evaluate all expanded tactics)
        for tactic in tactics:
            logger.info(f"  -> Executing tactic: {tactic}")
            res = repl.execute_tactic(curr.state_id, tactic)
            
            # Check for errors
            is_error = False
            if "messages" in res:
                for msg in res["messages"]:
                    if msg.get("severity") == "error":
                        is_error = True
                        break
            
            if is_error or "proofState" not in res:
                logger.info(f"     [Error] Tactic failed.")
                child_node = ProofNode(state_id=-1, goal_state="", parent=curr, tactic_applied=tactic)
                child_node.is_dead_end = True
                curr.children.append(child_node)
            else:
                new_state_id = res["proofState"]
                # If goals is empty, it's terminal!
                if not res.get("goals"):
                    new_goal = ""
                else:
                    new_goal = res["goals"][0] # Just take first goal for toy example
                    
                logger.info(f"     [Success] New state ID: {new_state_id}")
                child_node = ProofNode(state_id=new_state_id, goal_state=new_goal, parent=curr, tactic_applied=tactic)
                curr.children.append(child_node)
                
                if child_node.is_terminal:
                    logger.info("\n🏆 TERMINAL STATE REACHED! 🏆")
                    tactics_trace = trace_victory(child_node)
                    logger.info("Proof Script:")
                    for t in tactics_trace:
                        logger.info(f"  {t}")
                    return

        # 4. Backpropagation
        # Since we expand and evaluate all children, we just consider it 1 visit.
        # No value network, so value=0. Exploration will drive it to try different nodes.
        temp = curr
        while temp:
            temp.visits += 1
            # Could add value heuristic here
            temp = temp.parent

if __name__ == "__main__":
    main()
