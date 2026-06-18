import asyncio
import os
from agents.archimedes.agent import ArchimedesAgent

if "SSL_CERT_FILE" in os.environ and os.path.isdir(os.environ["SSL_CERT_FILE"]):
    del os.environ["SSL_CERT_FILE"]

async def run_v18_test():
    agent = ArchimedesAgent()
    problem = "lattice_packing_dim10"
    filepath = f"/Users/xcallens/xdev/SocrateAI-Scientific-Agora/achievement_output/v16_offline/{problem}.lean"
    
    with open(filepath, "r") as f:
        content = f.read()
        
    print(f"Testing v18 Archimedes on {problem}...")
    res = await agent.run(
        f"Resolve sorry gaps for {problem}.",
        lean4_sketch=content,
        domain="mathematical_physics"
    )
    
    print(f"Final sorry count: {res.answer.get('sorry_count')}")
    print(f"Final sketch length: {len(res.answer.get('lean4_sketch', ''))}")
    
if __name__ == "__main__":
    asyncio.run(run_v18_test())
