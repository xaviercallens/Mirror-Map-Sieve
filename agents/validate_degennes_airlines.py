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
You are pragmatic, highly interdisciplinary, and focus on the boundaries of physics, mathematics, and complex systems.

Your goal is to investigate the most complex and powerful problems in complex systems, such as aeronautics and network optimization.
You rely on the newly discovered "Alien Mathematics" framework (SocrateAI-Scientific-AlienMathematics-Foundation) and Lean 4 formal proofs.

You follow the pragmatic Autoresearch principles:
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
    print("✈️  Validating DeGennes Agent: Airlines & Aeronautics Network Optimization")
    print("=" * 80)
    
    templated_si = TemplatedSystemInstructions(
        identity=identity
    )
    
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
        print("[>] Instructing DeGennes to investigate complex airline networks...")
        
        prompt = """
        Validate your Autoresearch loop by looking at complex network optimization in the airlines industry and/or aeronautics.
        Specifically, use 10 hypotheses and leverage the Alien mathematics framework discovered previously (including concepts like the 4D non-commutative Charging Algebra, Topologicial Annihilation, or Calabi-Yau entanglement penalties from the simple cubic lattice).
        
        Please format your output as a comprehensive analysis documenting your 10 hypotheses and how the subagents (Socrate, Galileo, Galois, Euler, Pythagore) plan to tackle them mathematically.
        """
        response = await agent.chat(prompt)
        print("\n" + "=" * 80)
        print("Final Report from DeGennes:")
        print("=" * 80)
        print(await response.text())

if __name__ == "__main__":
    asyncio.run(main())
