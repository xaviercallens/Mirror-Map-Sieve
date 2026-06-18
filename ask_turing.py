import asyncio
from agents.turing.agent import TuringAgent

async def main():
    turing = TuringAgent()
    res = await turing.run("Please tear down SymBrain v11 on H100 GPU and ensure min replicate is set to 0 to avoid costs. Monitor and confirm it's torn down.")
    print("Turing Response:", res.answer)

if __name__ == "__main__":
    asyncio.run(main())
