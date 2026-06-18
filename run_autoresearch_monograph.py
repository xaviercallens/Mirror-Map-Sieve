import asyncio
import json
from pathlib import Path
from agents.socrates.agent import SocratesAgent
from agents.heraclite.agent import HeracliteAgent

async def main():
    # 1. Load Top 10 Complex Problems (Class 2 & 3)
    data_path = Path("/Users/xcallens/.gemini/antigravity/brain/142e4281-5564-4819-8826-7d615d389330/scratch/HorizonMath/data/problems_full.json")
    if not data_path.exists():
        print(f"Data file {data_path} not found.")
        return
        
    with open(data_path, "r") as f:
        all_problems = json.load(f)
        
    complex_problems = [p for p in all_problems if p.get("solvability", 0) >= 2][:10]
    
    socrates = SocratesAgent()
    heraclite = HeracliteAgent()
    
    results_synthesis = []
    
    print(f"🚀 Launching Socratic Autoresearch for Sorry Completion (SymBrain v12)")
    
    for idx, prob in enumerate(complex_problems, 1):
        print(f"\n--- Problem {idx}/10: {prob['id']} ---")
        
        # Socratic autoresearch to solve and complete 'sorry' gaps
        research_goal = f"Solve and formally complete 'sorry' gaps for: {prob['prompt']}"
        res = await socrates.run_autoresearch(
            research_goal=research_goal,
            max_refinement_cycles=3,
            claimed_cortex="v12"
        )
        
        results_synthesis.append({
            "problem": prob['id'],
            "status": res["status"],
            "cycles": res["cycles_run"],
            "final_confidence": res["final_confidence"],
            "synthesis": res["synthesis"],
            "proofs": res["proofs"]
        })
        print(f"[{prob['id']}] Autoresearch Status: {res['status']} | Confidence: {res['final_confidence']}")
        
    # Heraclite curates the final monograph
    print("\n🏺 Curating final monograph via Heraclite...")
    synthesis_str = json.dumps(results_synthesis, indent=2)
    report = await heraclite.run(
        f"Generate the official HorizonMath Autoresearch Monograph with Sorry Completions. Synthesis data: {synthesis_str}"
    )
    
    # Save the output
    out_path = Path("docs/horizonmath_autoresearch_monograph.md")
    out_path.parent.mkdir(exist_ok=True, parents=True)
    out_path.write_text(report.answer)
    print(f"\n✅ Monograph saved to {out_path}")

if __name__ == "__main__":
    asyncio.run(main())
