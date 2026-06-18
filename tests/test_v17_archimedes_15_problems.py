import asyncio
import os
import glob
from agents.archimedes.agent import ArchimedesAgent
import json
import logging

logging.basicConfig(level=logging.INFO)

if "SSL_CERT_FILE" in os.environ and os.path.isdir(os.environ["SSL_CERT_FILE"]):
    del os.environ["SSL_CERT_FILE"]

async def run_archimedes_15_problems():
    agent = ArchimedesAgent()
    v16_dir = "/Users/xcallens/xdev/SocrateAI-Scientific-Agora/achievement_output/v16_offline"
    lean_files = sorted(glob.glob(os.path.join(v16_dir, "*.lean")))[:15]
    
    print(f"Found {len(lean_files)} problems to test with upgraded Archimedes (Semantic REPL + Topological Sort).")
    
    results = []
    
    async def process_problem(lean_file):
        problem_name = os.path.basename(lean_file).replace(".lean", "")
        print(f"Starting Archimedes on [{problem_name}]...")
        with open(lean_file, "r") as f:
            proof_code = f.read()
            
        original_sorry = proof_code.count("sorry")
        if original_sorry == 0:
            return {"problem": problem_name, "status": "No sorry found", "reduction": 0, "cost": 0.0}
            
        agent = ArchimedesAgent()
        # We pass lean4_sketch = proof_code
        # domain = "test" (or we could extract it, but it defaults)
        result = await agent.run(
            query=f"Resolve sorry gaps for {problem_name}.", 
            lean4_sketch=proof_code,
            domain="mathematical_physics"
        )
        
        final_sorry = result.answer.get("sorry_count", 0)
        reduction = result.answer.get("reduction", 0)
        improvement = result.answer.get("improvement_pct", 0)
        
        print(f"[{problem_name}] Sorry Count: {original_sorry} -> {final_sorry} ({improvement:.1f}%)")
        return {
            "problem": problem_name,
            "original_sorry": original_sorry,
            "final_sorry": final_sorry,
            "reduction": reduction,
            "improvement": improvement,
            "cost": result.cost_usd
        }
        
    tasks = [process_problem(lf) for lf in lean_files]
    status_report = await asyncio.gather(*tasks)
        
    # Write report
    report_path = "/Users/xcallens/.gemini/antigravity/brain/142e4281-5564-4819-8826-7d615d389330/artifacts/archimedes_v17_15_problems_status.md"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        f.write("# Archimedes v17 (REPL + Topological) Resolution Report\\n\\n")
        f.write("Testing 15 problems from v16_offline sketches with Semantic REPL and Topological Sequential Resolution:\\n\\n")
        
        total_original = 0
        total_final = 0
        total_cost = 0.0
        
        for res in status_report:
            f.write(f"## {res['problem']}\\n")
            if "status" in res:
                f.write(f"- Status: {res['status']}\\n\\n")
                continue
                
            f.write(f"- **Sorry Gaps**: {res['original_sorry']} → {res['final_sorry']}\\n")
            f.write(f"- **Improvement**: {res['improvement']:.1f}%\\n")
            f.write(f"- **Cost**: ${res['cost']:.2f}\\n\\n")
            
            total_original += res['original_sorry']
            total_final += res['final_sorry']
            total_cost += res['cost']
            
        f.write(f"\\n### Summary\\n")
        f.write(f"- **Total Sorry Gaps Before**: {total_original}\\n")
        f.write(f"- **Total Sorry Gaps After**: {total_final}\\n")
        overall_imp = ((total_original - total_final) / total_original * 100) if total_original > 0 else 0
        f.write(f"- **Overall Resolution Rate**: {overall_imp:.1f}%\\n")
        f.write(f"- **Total Cost**: ${total_cost:.2f}\\n")
            
    print("\\nArchimedes Report written successfully.")

if __name__ == "__main__":
    asyncio.run(run_archimedes_15_problems())
