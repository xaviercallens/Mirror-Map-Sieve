import asyncio
import os
import glob
from agents.euler.agent import EulerAgent
import json

if "SSL_CERT_FILE" in os.environ and os.path.isdir(os.environ["SSL_CERT_FILE"]):
    del os.environ["SSL_CERT_FILE"]

async def run_15_problems():
    agent = EulerAgent()
    v16_dir = "/Users/xcallens/xdev/SocrateAI-Scientific-Agora/achievement_output/v16_offline"
    lean_files = sorted(glob.glob(os.path.join(v16_dir, "*.lean")))[:15]
    
    print(f"Found {len(lean_files)} problems to test.")
    
    status_report = []
    
    async def process_problem(lean_file):
        problem_name = os.path.basename(lean_file).replace(".lean", "")
        print(f"Starting [{problem_name}]...")
        with open(lean_file, "r") as f:
            proof_code = f.read()
            
        agent = EulerAgent()
        query = f"Run path to verified for {problem_name}."
        result = await agent.run(query=query, proof_code=proof_code)
        
        status = result.answer.get("status")
        objections = result.answer.get("objections", [])
        
        print(f"[{problem_name}] Status: {status}")
        return {
            "problem": problem_name,
            "status": status,
            "objections": objections,
            "cost": result.cost_usd
        }
        
    tasks = [process_problem(lf) for lf in lean_files]
    status_report = await asyncio.gather(*tasks)
        
    # Write report
    report_path = "/Users/xcallens/.gemini/antigravity/brain/142e4281-5564-4819-8826-7d615d389330/artifacts/euler_15_problems_status.md"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        f.write("# Euler Agent 'Path to Verified' Status Report\n\n")
        f.write("Testing 15 problems from v16_offline sketches:\n\n")
        for res in status_report:
            f.write(f"## {res['problem']}\n")
            f.write(f"- **Status**: `{res['status']}`\n")
            f.write(f"- **Cost**: ${res['cost']:.2f}\n")
            f.write("- **Objections**:\n")
            for obj in res['objections']:
                f.write(f"  - {obj}\n")
            f.write("\n")
            
    print("\nReport written successfully.")

if __name__ == "__main__":
    asyncio.run(run_15_problems())
