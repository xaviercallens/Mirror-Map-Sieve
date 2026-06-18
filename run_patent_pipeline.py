import asyncio
import json
from agents.pipelines.patent_generation import PatentGenerationPipeline

async def main():
    pipeline = PatentGenerationPipeline()
    topic = "hypercube bounds, Q-arithmetic, and ExactRationalWitness.lean"
    print(f"Running patent pipeline for topic: {topic}")
    result = await pipeline.run({"topic": topic})
    print("\n--- Pipeline Result ---")
    print(json.dumps(result.to_dict(), indent=2))
    
    print("\nVault Artifacts created:")
    for artifact in result.vault_artifact_ids:
        print(artifact)

if __name__ == "__main__":
    asyncio.run(main())
