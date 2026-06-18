import asyncio
import json
from agents.pipelines.patent_generation import PatentGenerationPipeline

async def main():
    pipeline = PatentGenerationPipeline()
    topic = (
        "Hypercube bounds and Q-arithmetic applied to ExactRationalWitness.lean: "
        "a generalized certificate mapping hypercube bounds onto computable "
        "Q-arithmetic, with potential Lean 4 verified solvers for autonomous "
        "systems, financial trading, and precision robotics"
    )
    print(f"Running enhanced patent pipeline v2 for topic:\n  {topic}\n")
    result = await pipeline.run({
        "topic": topic,
        "peer_review_model": "mistral-large-latest",
    })
    print("\n" + "="*60)
    print("PIPELINE RESULT")
    print("="*60)
    print(json.dumps(result.to_dict(), indent=2))

if __name__ == "__main__":
    asyncio.run(main())
