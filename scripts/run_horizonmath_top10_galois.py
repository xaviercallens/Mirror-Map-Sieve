import asyncio
import json
from pathlib import Path

from agents.galois.agent import GaloisAgent
from agents.euler.agent import EulerAgent
from agents.pythagore.agent import PythagoreAgent
from agents.heraclite.agent import HeracliteAgent
from agents.turing.agent import TuringAgent

async def main():
    # 1. Load Top 10 Complex Problems (Class 2 & 3)
    data_path = Path("/Users/xcallens/.gemini/antigravity/brain/142e4281-5564-4819-8826-7d615d389330/scratch/HorizonMath/data/problems_full.json")
    if not data_path.exists():
        print(f"Data file {data_path} not found.")
        return
        
    with open(data_path, "r") as f:
        all_problems = json.load(f)
        
    complex_problems = [p for p in all_problems if p.get("solvability", 0) >= 2][:10]
    
    # Initialize agents
    galois = GaloisAgent()
    euler = EulerAgent()
    pythagore = PythagoreAgent()
    heraclite = HeracliteAgent()
    turing = TuringAgent()
    
    results_synthesis = []
    
    print(f"🚀 Launching HorizonMath Top 10 Execution (SymBrain v12)")
    
    for idx, prob in enumerate(complex_problems, 1):
        print(f"\n--- Problem {idx}/10: {prob['id']} ---")
        
        solvability_class = "class_3" if prob.get("solvability") == 3 else "class_2"
        
        # A. Trigger Turing Deployment based on Solvability Class
        print(f"[{prob['id']}] Turing: Deploying GPU cluster for {solvability_class}...")
        await turing.run(
            f"Deploy SymBrain v12 for {solvability_class}",
            solvability_class=solvability_class
        )
        
        # B. Galois solves problem
        print(f"[{prob['id']}] Galois: Attempting solution with SymBrain v12...")
        galois_res = await galois.run(
            f"Solve this complex mathematical problem using SymBrain v12: {prob['prompt']}",
            symbrain_version="v12_large" if solvability_class == "class_3" else "v11_small"
        )
        
        # C. Euler verifies
        print(f"[{prob['id']}] Euler: Verifying Galois solution...")
        euler_res = await euler.run(
            f"Verify Galois's solution: {galois_res.answer}. Problem: {prob['prompt']}"
        )
        
        # D. Pythagore generates formal draft
        print(f"[{prob['id']}] Pythagore: Formalizing draft...")
        pyth_res = await pythagore.run(
            f"Generate a formal proof draft based on Euler's verification: {euler_res.answer}"
        )
        
        # E. Turing strict scale-to-zero
        print(f"[{prob['id']}] Turing: Tearing down cluster...")
        await turing.run("tear down deployment symbrain_swarm")
        
        results_synthesis.append({
            "problem": prob['id'],
            "galois_solution": str(galois_res.answer),
            "euler_verdict": str(euler_res.answer),
            "pythagore_draft": str(pyth_res.answer),
        })
        
    # 3. Heraclite curates the final monograph
    print("\n🏺 Curating final monograph via Heraclite...")
    synthesis_str = json.dumps(results_synthesis, indent=2)
    report = await heraclite.run(
        f"Generate the official HorizonMath Top 10 Evaluation Monograph. Synthesis data: {synthesis_str}"
    )
    
    # Save the output
    out_path = Path("docs/horizonmath_top10_monograph.md")
    out_path.parent.mkdir(exist_ok=True, parents=True)
    out_path.write_text(report.answer)
    print(f"\n✅ Monograph saved to {out_path}")

if __name__ == "__main__":
    asyncio.run(main())
