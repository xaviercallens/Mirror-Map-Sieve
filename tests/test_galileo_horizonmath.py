import asyncio
import json
import os
from agents.galileo.agent import GalileoAgent

async def test_galileo():
    agent = GalileoAgent()
    
    problems_to_test = [
        "feigenbaum_delta",        # constant
        "A21_10_binary_code",      # construction
        "lane_emden_polytrope"     # function
    ]
    
    print("Testing Galileo Agent with HorizonMath Problems...")
    print("=" * 60)
    
    for prob in problems_to_test:
        print(f"\n[Problem: {prob}]")
        query = f"Verify the solution for HorizonMath problem {prob}. Use symbolic, numerical, and precision validation steps."
        
        result = await agent.run(query)
        print(f"Cost: ${result.cost_usd:.2f}")
        print(f"Telemetry: {result.telemetry}")
        print("Observations:")
        for tool, obs in result.answer.items():
            print(f"  - {tool}: {obs}")

if __name__ == "__main__":
    asyncio.run(test_galileo())
