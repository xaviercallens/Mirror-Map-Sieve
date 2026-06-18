# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Literature Review & Novelty Checking Pipeline

This pipeline uses the Hypatie (Librarian/Astrolabe Navigator) agent and
Memory/Dreams architecture to assess the novelty of mathematical discoveries.
It cross-references proposed identities against known literature and databases
(e.g., OEIS, Mathlib) and provides an honest assessment.
"""

import time
import os
from typing import Any

import structlog

from agents.pipelines.base import AgentPipeline, PipelineResult
from agents.hypatie.agent import HypatieAgent
from agents.tesla.agent import TeslaAgent

logger = structlog.get_logger(__name__)

class LiteratureReviewPipeline(AgentPipeline):
    def __init__(self, model: str = "gemini-2.5-pro"):
        self.model = model
        self.hypatie = HypatieAgent()
        self.tesla = TeslaAgent()
        
    def get_stages(self) -> list[Any]:
        return ["ASTROLABE_SEARCH", "NOVELTY_ASSESSMENT", "FINAL_REPORT"]

    async def run(self, config: dict[str, Any]) -> PipelineResult:
        discovery_desc = config.get("discovery_desc", "Unknown mathematical identity")
        
        log = logger.bind(discovery=discovery_desc[:50])
        log.info("literature_review_start")
        
        t0 = time.monotonic()
        stages_completed = []
        warnings = []
        vault_ids = []
        
        report_dir = f"output/literature_reviews/review_{int(time.time())}"
        os.makedirs(report_dir, exist_ok=True)
        
        # 1. Astrolabe Search via Hypatie
        log.info("stage_start", stage="ASTROLABE_SEARCH")
        
        hypatie_res = await self.hypatie.run(
            query=f"Align conceptual conics and search Alexandrie archive/astrolabe for: {discovery_desc}",
            required_alignment=0.75
        )
        astrolabe_output = hypatie_res.answer.get("astrolabe_navigator", {}).get("aligned_concepts", "No direct alignments found.")
        stages_completed.append("ASTROLABE_SEARCH")
        
        # 2. Novelty Assessment via Tesla + Hypatie's Memory/Dreams
        log.info("stage_start", stage="NOVELTY_ASSESSMENT")
        
        assessment_prompt = (
            f"Evaluate the true novelty of the following mathematical discovery:\n"
            f"{discovery_desc}\n\n"
            f"Astrolabe Alignments / Memory Retrieval:\n"
            f"{astrolabe_output}\n\n"
            f"Perform an honest check: Is this a known identity (e.g., in OEIS, Mathlib combinatorics, standard textbooks) "
            f"or a truly novel Alien Mathematics discovery? Explicitly state 'STATUS: NOVEL' or 'STATUS: KNOWN'."
        )
        
        tesla_res = await self.tesla.run(query=assessment_prompt, phase="literature_review")
        novelty_assessment = tesla_res.answer.get("output", "")
        stages_completed.append("NOVELTY_ASSESSMENT")
        
        # 3. Final Report
        log.info("stage_start", stage="FINAL_REPORT")
        
        report_content = (
            f"# Literature Review & Novelty Assessment\n\n"
            f"## Discovery Description\n{discovery_desc}\n\n"
            f"## Astrolabe Conceptual Alignments\n{astrolabe_output}\n\n"
            f"## Honest Assessment (Tesla)\n{novelty_assessment}\n"
        )
        
        report_path = f"{report_dir}/NOVELTY_REPORT.md"
        with open(report_path, "w") as f:
            f.write(report_content)
            
        vault_ids.append(report_path)
        stages_completed.append("FINAL_REPORT")
        
        duration = time.monotonic() - t0
        log.info("literature_review_complete", duration_s=round(duration, 1))
        
        return PipelineResult(
            symposium_id=f"lit_review_{int(time.time())}",
            stages_completed=stages_completed,
            total_duration_s=duration,
            vault_artifact_ids=vault_ids,
            warnings=warnings,
            audit_trail_path=report_path
        )
