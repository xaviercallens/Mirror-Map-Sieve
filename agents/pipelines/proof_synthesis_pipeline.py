# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0
"""
Automated Lean 4 Proof Synthesis Pipeline

This pipeline integrates with the Tesla agent and the verify.py harness
to automatically synthesize and self-correct Lean 4 proofs. It uses
compiler feedback (errors and remaining sorries) to iterate on a proof
until it is fully verified (zero sorry, zero axiom) or hits the max retries.
"""

import os
import json
import subprocess
import time
from typing import Any

import structlog

from agents.pipelines.base import AgentPipeline, PipelineResult
from agents.tesla.agent import TeslaAgent

logger = structlog.get_logger(__name__)

class ProofSynthesisPipeline(AgentPipeline):
    def __init__(self, model: str = "gemini-2.5-pro", max_retries: int = 5):
        self.model = model
        self.max_retries = max_retries
        self.tesla = TeslaAgent()
        
    def get_stages(self) -> list[Any]:
        return ["INITIAL_SYNTHESIS", "SELF_CORRECTION_LOOP", "FINAL_VERIFICATION"]

    async def run(self, config: dict[str, Any]) -> PipelineResult:
        module_name = config.get("module_name", "Agora.AlienMath.TestProof")
        identity_desc = config.get("identity_desc", "A mathematical identity")
        
        log = logger.bind(module=module_name)
        log.info("proof_synthesis_start")
        
        t0 = time.monotonic()
        stages_completed = []
        warnings = []
        vault_ids = []
        
        # Paths
        lean_root = "SocrateAI-Scientific-AlienMathematics-Foundation"
        verify_script = "verify.py"
        audit_file = f"{lean_root}/proof/audit.json"
        
        module_path = module_name.replace(".", "/") + ".lean"
        full_module_path = os.path.join(lean_root, module_path)
        
        # 1. Initial Synthesis
        log.info("stage_start", stage="INITIAL_SYNTHESIS")
        prompt = (
            f"Generate a full Lean 4 proof for the following identity/theorem:\n"
            f"{identity_desc}\n\n"
            f"Requirements:\n"
            f"1. Use 'import Mathlib'\n"
            f"2. Put the proof in module {module_name}\n"
            f"3. Aim for zero sorries and zero axioms.\n"
            f"4. Output ONLY the raw Lean 4 code inside a ```lean code block."
        )
        
        res = await self.tesla.run(query=prompt, phase="proof_synthesis")
        initial_code = res.answer.get("output", "")
        
        # Extract code block
        if "```lean" in initial_code:
            code = initial_code.split("```lean")[1].split("```")[0].strip()
        elif "```" in initial_code:
            code = initial_code.split("```")[1].split("```")[0].strip()
        else:
            code = initial_code.strip()
            
        os.makedirs(os.path.dirname(full_module_path), exist_ok=True)
        with open(full_module_path, "w") as f:
            f.write(code)
            
        stages_completed.append("INITIAL_SYNTHESIS")
        vault_ids.append(full_module_path)
        
        # 2. Self-Correction Loop
        log.info("stage_start", stage="SELF_CORRECTION_LOOP")
        
        for attempt in range(1, self.max_retries + 1):
            log.info("verify_attempt", attempt=attempt)
            
            # Run verify.py for this specific module
            try:
                subprocess.run(
                    ["python", verify_script, "--module", module_name],
                    cwd=lean_root,
                    capture_output=True,
                    timeout=300
                )
            except Exception as e:
                warnings.append(f"verify.py execution failed: {e}")
                break
                
            # Parse audit.json
            if not os.path.exists(audit_file):
                warnings.append("audit.json not generated.")
                break
                
            with open(audit_file, "r") as f:
                audit_data = json.load(f)
                
            # Find our module in the audit
            module_audit = next((m for m in audit_data.get("modules", []) if m["module"] == module_name), None)
            
            if not module_audit:
                warnings.append(f"Module {module_name} not found in audit.json")
                break
                
            status = module_audit["status"]
            if status == "verified":
                log.info("proof_verified", attempt=attempt)
                break
                
            # Proof failed or has sorries. Prepare feedback for LLM
            log.info("proof_needs_correction", status=status, sorry_count=module_audit["sorry_count"])
            
            feedback = (
                f"The Lean 4 compiler returned the following status: {status}\n\n"
            )
            if not module_audit["build_ok"]:
                feedback += "Build failed with errors:\n"
                for err in module_audit["error_messages"]:
                    feedback += f"- {err}\n"
            
            if module_audit["sorry_count"] > 0:
                feedback += f"\nThere are {module_audit['sorry_count']} remaining sorries:\n"
                for loc in module_audit["sorry_locations"]:
                    feedback += f"- Line {loc['line']}: {loc['content']}\n"
                    
            repair_prompt = (
                f"Your previous Lean 4 proof for {module_name} failed verification.\n"
                f"{feedback}\n\n"
                f"Here is the current code:\n```lean\n{code}\n```\n\n"
                f"Please fix the errors and close the sorries. Output the complete, fixed Lean 4 code inside a ```lean code block."
            )
            
            res = await self.tesla.run(query=repair_prompt, phase="proof_repair")
            repair_output = res.answer.get("output", "")
            
            if "```lean" in repair_output:
                code = repair_output.split("```lean")[1].split("```")[0].strip()
            elif "```" in repair_output:
                code = repair_output.split("```")[1].split("```")[0].strip()
            else:
                code = repair_output.strip()
                
            with open(full_module_path, "w") as f:
                f.write(code)
                
        stages_completed.append("SELF_CORRECTION_LOOP")
        stages_completed.append("FINAL_VERIFICATION")
        
        duration = time.monotonic() - t0
        log.info("proof_synthesis_complete", duration_s=round(duration, 1))
        
        return PipelineResult(
            symposium_id=f"proof_synth_{int(time.time())}",
            stages_completed=stages_completed,
            total_duration_s=duration,
            vault_artifact_ids=vault_ids,
            warnings=warnings,
            audit_trail_path=full_module_path
        )
