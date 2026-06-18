#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Runner Script for Post-Discovery Interpretation and Mirror Symmetry Pipeline
----------------------------------------------------------------------------
Triggers the post-discovery mirror pipeline to run the mirror solver,
observe N=15, and update the LaTeX and JSX documentation with the Corollary.
"""

import asyncio
import sys
from agents.pipelines.post_discovery_mirror_pipeline import PostDiscoveryMirrorPipeline

async def main():
    print("Starting Post-Discovery Mirror Interpretation Pipeline...")
    pipeline = PostDiscoveryMirrorPipeline()
    config = {
        "symposium_id": "symposium_s20_mirror_post"
    }
    
    result = await pipeline.run(config)
    
    print("\n--- Pipeline Run Summary ---")
    print(f"Symposium ID:      {result.symposium_id}")
    print(f"Stages Completed:  {', '.join(result.stages_completed)}")
    print(f"Total Duration:    {result.total_duration_s:.2f} seconds")
    print(f"PDF Output Path:   {result.pdf_path}")
    print(f"TeX Output Path:   {result.tex_path}")
    print(f"Vault Artifacts:   {', '.join(result.vault_artifact_ids)}")
    
    if result.warnings:
        print("\n--- Warnings ---")
        for warning in result.warnings:
            print(f"- {warning}")
        sys.exit(1)
        
    print("\nPipeline completed successfully with zero warnings!")
    sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
