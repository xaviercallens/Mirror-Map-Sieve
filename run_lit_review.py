import asyncio
import json
from agents.pipelines.literature_review import LiteratureReviewPipeline

async def main():
    pipeline = LiteratureReviewPipeline()
    topic = "investigate the usage of the hypercube bounds and Q-arithmetic to understand the potential of ExactRationalWitness.lean: A generalized certificate mapping hypercube bounds onto computable Q-arithmetic and potential Solver with Lean 4 verification."
    print(f"Running pipeline for topic: {topic}")
    result = await pipeline.run({"topic": topic})
    print("\n--- Pipeline Result ---")
    print(json.dumps(result.to_dict(), indent=2))
    
    print("\n--- Audit Trail (Graph) ---")
    with open(result.audit_trail_path, 'r') as f:
        print(f.read())

if __name__ == "__main__":
    asyncio.run(main())
