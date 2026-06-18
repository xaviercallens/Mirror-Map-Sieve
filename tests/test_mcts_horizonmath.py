import sys
import json
import logging
from typing import List

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

def test_mcts_on_lean_file(filepath: str):
    with open(filepath, "r") as f:
        content = f.read()
        
    import pathlib
    workspace_dir = str(pathlib.Path(__file__).resolve().parent.parent / "verifiers" / "lean4")
    repl = LeanREPL(workspace_dir=workspace_dir)
    policy = MCTSPolicy()
    
    logger.info(f"Initializing Lean REPL on {filepath}...")
    init_res = repl.init_proof(content)
    logger.info(f"init_res: {json.dumps(init_res, indent=2)}")
    
    if "sorries" not in init_res or len(init_res["sorries"]) == 0:
        logger.error("No sorry found by REPL.")
        return
        
    target_sorry = init_res["sorries"][0]
    root_state_id = target_sorry["proofState"]
    root_goal = target_sorry["goal"]
    
    root_node = ProofNode(state_id=root_state_id, goal_state=root_goal)
    max_iterations = 10
    
    logger.info(f"Starting MCTS for goal: {root_goal}")
    
    for i in range(max_iterations):
        logger.info(f"\n--- MCTS Iteration {i+1} ---")
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
            logger.info(f"Terminal node selected! Victory trace: {tactics}")
            break
            
        if curr.is_dead_end or (curr.parent and curr.children and all(c.is_dead_end for c in curr.children)):
            logger.info("Selected a dead end. Marking as dead end.")
            curr.is_dead_end = True
            temp = curr
            while temp:
                temp.visits += 1
                temp = temp.parent
            continue
            
        logger.info(f"Expanding Node {curr.state_id}")
        tactics = policy.generate_tactics(curr.goal_state)
        
        if not tactics:
            curr.is_dead_end = True
            continue
            
        for tactic in tactics:
            logger.info(f"  -> Executing: {tactic}")
            res = repl.execute_tactic(curr.state_id, tactic)
            
            is_error = False
            if "messages" in res:
                for msg in res["messages"]:
                    if msg.get("severity") == "error":
                        is_error = True
                        break
            
            if is_error or "proofState" not in res:
                logger.info("     [Error] Tactic failed.")
                child_node = ProofNode(state_id=-1, goal_state="", parent=curr, tactic_applied=tactic)
                child_node.is_dead_end = True
                curr.children.append(child_node)
            else:
                new_state_id = res["proofState"]
                new_goal = res["goals"][0] if res.get("goals") else ""
                logger.info(f"     [Success] New state ID: {new_state_id}")
                child_node = ProofNode(state_id=new_state_id, goal_state=new_goal, parent=curr, tactic_applied=tactic)
                curr.children.append(child_node)
                
                if child_node.is_terminal:
                    logger.info("\n🏆 TERMINAL STATE REACHED! 🏆")
                    tactics_trace = trace_victory(child_node)
                    logger.info(f"Proof Script: {tactics_trace}")
                    return
        
        temp = curr
        while temp:
            temp.visits += 1
            temp = temp.parent

if __name__ == "__main__":
    test_mcts_on_lean_file("/Users/xcallens/xdev/SocrateAI-Scientific-Agora/achievement_output/v16_offline/inverse_galois_m23.lean")
