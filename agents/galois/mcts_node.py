import math
from typing import List, Optional

class ProofNode:
    def __init__(self, state_id: int, goal_state: str, parent=None, tactic_applied=None):
        self.state_id = state_id          # The Lean REPL proofState ID (e.g., 0, 1, 2)
        self.goal_state = goal_state      # The string representation of the current target
        self.tactic_applied = tactic_applied # What Mistral/Gemini typed to get here
        self.parent: Optional['ProofNode'] = parent
        self.children: List['ProofNode'] = []
        
        # Engine Flags & Stats
        self.is_terminal = ("goals: []" in goal_state) or (goal_state.strip() == "")
        self.is_dead_end = False          # True if Lean compiler threw an error
        self.visits = 0
        self.value = 0.0

    def uct_score(self, c_param=1.414) -> float:
        """Upper Confidence Bound 1 (UCB1) applied to trees."""
        if self.is_dead_end:
            return float('-inf') # Never pick broken compilation branches
        if self.visits == 0:
            return float('inf')  # Always explore unvisited nodes first
        exploitation = self.value / self.visits
        exploration = c_param * math.sqrt(math.log(self.parent.visits) / self.visits)
        return exploitation + exploration
