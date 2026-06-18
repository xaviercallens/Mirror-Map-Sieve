#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Runner Script for New Theory Documentation Pipeline
--------------------------------------------------
Triggers the full documentation pipeline to compile the Experimental Mathematics note,
verify Lean 4 proofs, execute applications simulation, and archive generated artifacts.
"""

import asyncio
import sys
from agents.pipelines.newtheorydocumentation import NewTheoryDocumentationPipeline

async def main():
    print("Starting New Theory Documentation Pipeline...")
    pipeline = NewTheoryDocumentationPipeline()
    config = {
        "symposium_id": "symposium_s20_doc"
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
