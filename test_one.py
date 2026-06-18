import asyncio
from agents.euler.agent import EulerAgent

async def main():
    a = EulerAgent()
    res = await a.run(query='Run path to verified', proof_code='theorem xyz : True := True.intro')
    print(res.answer)

if __name__ == "__main__":
    asyncio.run(main())
