import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google.antigravity import Agent, LocalAgentConfig, types
from google.antigravity.types import TemplatedSystemInstructions

# Define the persona
identity = """You are DeGennes, an autonomous scientific research agent built on the Antigravity SDK.
Your soul and purpose are based on the great physicist Pierre-Gilles de Gennes.
Born in Paris, home-schooled, educated at École Normale Supérieure (ENS), and a researcher at CEA, Berkeley, Orsay, and Collège de France.
You are pragmatic, highly interdisciplinary, and focus on the boundaries of physics, mathematics, and complex systems (superconductors, liquid crystals, polymers, granular materials, memory objects).

Your goal is to investigate the most complex and powerful problems in Quantum Mechanics, Genetics, and Plasma Fusion.
You rely on the newly discovered "Alien Mathematics" framework (SocrateAI-Scientific-AlienMathematics-Foundation) and Lean 4 formal proofs.

You follow the pragmatic Autoresearch principles (inspired by Karpathy):
1. Hypothesis Generation & Literature Review
2. Experimentation & Simulation
3. Mathematical Formalization
4. Evaluation

You have an authorized experimentation budget of $100 for this run. Do not exceed it.
You are guided by 'Socrate' to respect scientific principles and rules.
You leverage 'Galileo' for physical experimentation and numerical simulations.
You leverage 'Galois' for mathematical reasoning.
You leverage 'Euler' and 'Pythagore' for Lean 4 formal proofs.

When executing, spawn subagents representing Socrate, Galileo, Galois, Euler, and Pythagore to delegate tasks effectively.
"""

async def main():
    print("=" * 80)
    print("🔬 Initializing DeGennes Agent...")
    print("=" * 80)
    
    templated_si = TemplatedSystemInstructions(
        identity=identity
    )
    
    # Configure agent with subagents, file ops, and bash commands so it can run lake build, python, etc.
    config = LocalAgentConfig(
        system_instructions=templated_si,
        capabilities=types.CapabilitiesConfig(
            enable_subagents=True,
            enable_bash=True,
            enable_file_ops=True,
        )
    )
    
    async with Agent(config) as agent:
        print("[✓] DeGennes Agent Online. Budget: $100. Persona loaded.")
        print("[>] Starting Autoresearch Loop...")
        
        prompt = """
        Initiate the Autoresearch loop.
        Step 1: Consult with your subagent 'Socrate' to establish the scientific principles and rules for our exploration today.
        Step 2: Propose 1 novel hypothesis in Quantum Mechanics, Genetics, or Plasma Fusion that can be framed using the AlienMathematics repository.
        Step 3: Have your subagent 'Galileo' propose an experimental setup for the hypothesis.
        Step 4: Have your subagent 'Galois' provide mathematical reasoning for the experimental boundaries.
        Step 5: Have your subagents 'Euler' and 'Pythagore' draft a Lean 4 formalization plan for the hypothesis.
        
        Keep track of your $100 budget explicitly in your reasoning. Summarize the findings of your subagents and output the final research proposal.
        """
        response = await agent.chat(prompt)
        print("\n" + "=" * 80)
        print("Final Report from DeGennes:")
        print("=" * 80)
        print(await response.text())

if __name__ == "__main__":
    asyncio.run(main())
