import asyncio
import os
from agents.turing.agent import TuringAgent

async def main():
    turing = TuringAgent()
    print("Asking Turing to save images/configs and tear down the infrastructure...")
    result = await turing.run("Save all deployment images for fast redeployment in the container registry, backup deployment configurations, and tear down deployment symbrain_swarm to save cost.")
    print(f"Turing response: {result.answer}")

if __name__ == "__main__":
    asyncio.run(main())
