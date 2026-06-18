import asyncio
from agents.turing.agent import TuringAgent

async def main():
    turing = TuringAgent()
    print("Asking Turing to tear down the infrastructure...")
    result = await turing.run("tear down deployment symbrain_swarm")
    print(f"Turing response: {result.answer}")

if __name__ == "__main__":
    asyncio.run(main())
