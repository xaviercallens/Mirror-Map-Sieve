import asyncio
import json
from agents.pipelines.patent_generation import PatentGenerationPipeline

async def main():
    pipeline = PatentGenerationPipeline()
    topic = (
        "Callens-Schmidt sequence S_20(n) = Sum_{k=0..n} choose(n, k)^4 * choose(n+k, k) "
        "and its Calabi-Yau period diagonal representation, applied to transonic airfoil "
        "optimization, topological quantum walk returning probabilities, and algebraic "
        "search space complexity scaling for cryptography."
    )
    print(f"Running enhanced patent pipeline v2 for S20:\n  {topic}\n")
    result = await pipeline.run({
        "topic": topic,
        "peer_review_model": "gemini-2.5-pro",
    })
    print("\n" + "="*60)
    print("PIPELINE RESULT")
    print("="*60)
    print(json.dumps(result.to_dict(), indent=2))

if __name__ == "__main__":
    asyncio.run(main())
