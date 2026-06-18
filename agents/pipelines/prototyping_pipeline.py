# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Prototyping Pipeline v2 — Tesla's specification and test-driven prototype generation.

Enhanced with:
- Mistral peer review for controversial viewpoints
- Multi-LLM code peer review (Gemini + Mistral)
- Code optimization via deterministic open-source engines (ruff, ast analysis)
- Secret Manager integration for API keys on GCP

Implements the loop:
1. Technical Literature Review
2. Goal Initialization and SPECS.md / DESIGN.md generation (with 3 peer review loops)
3. Build & Validate Loop (5-10 iterations) updating LESSONS_LEARNT and MEMORY
4. Mistral Peer Review (controversial / adversarial viewpoint)
5. Code Optimization (deterministic engine: ruff + ast analysis)
6. Final Delivery
"""

from __future__ import annotations

import ast
import os
import time
import json
import subprocess
import textwrap
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

import structlog

from agents.pipelines.base import AgentPipeline, PipelineResult, agent_generate
from agents.tesla.agent import TeslaAgent

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Secret Manager helper — load API keys from GCP or .env
# ---------------------------------------------------------------------------

def _get_secret(secret_name: str, env_var: str) -> str:
    """Try GCP Secret Manager first, then fall back to environment variable."""
    # Try GCP Secret Manager
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        project = os.environ.get("GCP_PROJECT", "gen-lang-client-0625573011")
        name = f"projects/{project}/secrets/{secret_name}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception:
        pass
    
    # Fall back to environment variable
    return os.environ.get(env_var, "")


# ---------------------------------------------------------------------------
# Mistral helper — direct HTTP API call (no SDK dependency)
# ---------------------------------------------------------------------------

async def _mistral_generate(prompt: str, system: str = "", model: str = "mistral-large-latest") -> str:
    """Call Mistral API directly via HTTP for peer review."""
    import aiohttp
    
    api_key = _get_secret("mistral-api-key", "GALOIS_MISTRAL_KEY")
    if not api_key:
        return "[MISTRAL_UNAVAILABLE: No API key found in Secret Manager or environment]"
    
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 4096,
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.mistral.ai/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    return f"[MISTRAL_ERROR: HTTP {resp.status} — {error_text[:200]}]"
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[MISTRAL_ERROR: {str(e)[:200]}]"


# ---------------------------------------------------------------------------
# Deterministic Code Optimizer (no LLM — pure AST + ruff)
# ---------------------------------------------------------------------------

def _optimize_code(code: str, language: str = "python") -> dict[str, Any]:
    """Run deterministic code analysis and optimization.
    
    Uses:
    - Python ast module for structural analysis
    - ruff (if available) for linting
    - Custom complexity metrics
    """
    result = {
        "language": language,
        "original_lines": len(code.splitlines()),
        "issues": [],
        "optimizations": [],
        "complexity_score": 0,
    }
    
    if language == "python":
        # AST analysis
        try:
            tree = ast.parse(code)
            
            # Count functions, classes, complexity
            functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
            loops = [n for n in ast.walk(tree) if isinstance(n, (ast.For, ast.While))]
            conditionals = [n for n in ast.walk(tree) if isinstance(n, ast.If)]
            
            # Cyclomatic complexity approximation
            complexity = 1 + len(loops) + len(conditionals)
            result["complexity_score"] = complexity
            result["functions_count"] = len(functions)
            result["classes_count"] = len(classes)
            
            # Check for common issues
            for node in ast.walk(tree):
                if isinstance(node, ast.Raise) and node.exc is None:
                    result["issues"].append("Bare raise without exception type")
                if isinstance(node, ast.Global):
                    result["issues"].append(f"Global variable usage: {node.names}")
                    result["optimizations"].append("Consider passing variables as parameters instead of using global")
            
            # Check for deeply nested code
            max_depth = _max_nesting_depth(tree)
            if max_depth > 4:
                result["issues"].append(f"Deep nesting detected: {max_depth} levels")
                result["optimizations"].append("Refactor deeply nested code into helper functions")
                
        except SyntaxError as e:
            result["issues"].append(f"Syntax error: {e}")
    
    # Try ruff if available
    try:
        ruff_result = subprocess.run(
            ["ruff", "check", "--select", "E,W,F,C,I", "--output-format", "json", "-"],
            input=code, capture_output=True, text=True, timeout=10
        )
        if ruff_result.returncode == 0 or ruff_result.stdout:
            ruff_issues = json.loads(ruff_result.stdout) if ruff_result.stdout else []
            for issue in ruff_issues[:10]:  # cap at 10
                result["issues"].append(f"ruff {issue.get('code', '?')}: {issue.get('message', '?')}")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        result["optimizations"].append("Install ruff for additional static analysis: pip install ruff")
    
    return result


def _max_nesting_depth(node: ast.AST, depth: int = 0) -> int:
    """Calculate maximum nesting depth of an AST."""
    max_d = depth
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
            max_d = max(max_d, _max_nesting_depth(child, depth + 1))
        else:
            max_d = max(max_d, _max_nesting_depth(child, depth))
    return max_d


# ---------------------------------------------------------------------------
# Pipeline Stages
# ---------------------------------------------------------------------------

class PrototypingStage(IntEnum):
    """Stages of the Prototyping Pipeline v2."""
    LITERATURE_REVIEW = 1
    SPECS_AND_DESIGN = 2
    PROTOTYPE_LOOP = 3
    MISTRAL_PEER_REVIEW = 4
    CODE_OPTIMIZATION = 5
    FINAL_DELIVERY = 6


class PrototypingPipeline(AgentPipeline):
    """Pipeline for automatic prototyping by the Tesla Agent.
    
    Enhanced with multi-LLM peer review (Gemini + Mistral),
    deterministic code optimization, and Secret Manager integration.
    """

    def __init__(self, model: str = "gemini-2.5-pro", num_loops: int = 5):
        self.model = model
        self.num_loops = max(5, min(10, num_loops))  # enforce 5 to 10 loops
        self.tesla = TeslaAgent()
        
    def get_stages(self) -> list[PrototypingStage]:
        return list(PrototypingStage)

    async def run(self, config: dict[str, Any]) -> PipelineResult:
        topic = config.get("topic", "Unknown invention")
        log = logger.bind(topic=topic[:50])
        log.info("prototyping_pipeline_v2_start")

        t0_total = time.monotonic()
        warnings: list[str] = []
        vault_ids: list[str] = []
        stages_completed: list[str] = []
        
        timestamp = int(time.time())
        prototype_dir = f"alexandrie/prototype_{timestamp}"
        os.makedirs(prototype_dir, exist_ok=True)

        # ---------------------------------------------------------
        # Stage 1: Technical Literature Review
        # ---------------------------------------------------------
        log.info("stage_start", stage="LITERATURE_REVIEW")
        lit_review_res = await self.tesla.run(
            query=f"Perform a state-of-the-art technical literature review for building a prototype based on: {topic}",
            phase="literature_review"
        )
        lit_review_text = lit_review_res.answer.get("output", "")
        stages_completed.append("LITERATURE_REVIEW")
        
        with open(f"{prototype_dir}/LITERATURE_REVIEW.md", "w") as f:
            f.write(lit_review_text)
        vault_ids.append(f"{prototype_dir}/LITERATURE_REVIEW.md")

        # ---------------------------------------------------------
        # Stage 2: Specs and Design (with 3 peer review loops)
        # ---------------------------------------------------------
        log.info("stage_start", stage="SPECS_AND_DESIGN")
        specs_design_text = ""
        for i in range(3):
            specs_res = await self.tesla.run(
                query=(
                    f"Topic: {topic}\n"
                    f"Literature Review: {lit_review_text[:1500]}\n"
                    f"Previous Iteration Specs: {specs_design_text[:1500]}\n"
                    f"Refine and generate formal SPECS.md and DESIGN.md. "
                    f"Ensure test-driven and specification-driven concepts are paramount."
                ),
                phase="specs_and_design",
                iteration=i+1
            )
            specs_design_text = specs_res.answer.get("output", "")
        
        stages_completed.append("SPECS_AND_DESIGN")
        
        with open(f"{prototype_dir}/SPECS_AND_DESIGN.md", "w") as f:
            f.write(specs_design_text)
        vault_ids.append(f"{prototype_dir}/SPECS_AND_DESIGN.md")

        # ---------------------------------------------------------
        # Stage 3: Prototyping Loop (Build, Validate, Learn)
        # ---------------------------------------------------------
        log.info("stage_start", stage="PROTOTYPE_LOOP", loops=self.num_loops)
        
        memory = "Initial Memory: Starting prototype build based on design."
        lessons = "No lessons yet."
        all_code_snippets: list[str] = []
        
        for i in range(self.num_loops):
            log.info("prototype_iteration", iteration=i+1)
            loop_res = await self.tesla.run(
                query=(
                    f"Topic: {topic}\n"
                    f"Specs/Design: {specs_design_text[:1000]}\n"
                    f"Memory: {memory}\n"
                    f"Lessons Learnt: {lessons}\n\n"
                    f"Perform iteration {i+1} of the prototype build and numeric validation loop. "
                    f"Include Python code snippets for numeric experiments. "
                    f"Output the new MEMORY and LESSONS_LEARNT."
                ),
                phase="prototype_loop",
                iteration=i+1
            )
            output = loop_res.answer.get("output", "")
            
            # Extract memory and lessons
            if "MEMORY" in output:
                memory = output.split("MEMORY")[1][:1000]
            if "LESSONS_LEARNT" in output:
                lessons = output.split("LESSONS_LEARNT")[1][:1000]
            
            # Extract code snippets for optimization stage
            _extract_code_blocks(output, all_code_snippets)
                
            with open(f"{prototype_dir}/ITERATION_{i+1}.md", "w") as f:
                f.write(output)

        with open(f"{prototype_dir}/MEMORY.md", "w") as f:
            f.write(memory)
        with open(f"{prototype_dir}/LESSONS_LEARNT.md", "w") as f:
            f.write(lessons)
            
        vault_ids.extend([
            f"{prototype_dir}/MEMORY.md", 
            f"{prototype_dir}/LESSONS_LEARNT.md"
        ])
        stages_completed.append("PROTOTYPE_LOOP")

        # ---------------------------------------------------------
        # Stage 4: Multi-LLM Peer Review (Gemini + Mistral)
        # ---------------------------------------------------------
        log.info("stage_start", stage="MISTRAL_PEER_REVIEW")
        
        review_summary = specs_design_text[:2000] + "\n\nFinal Memory:\n" + memory[:500]
        
        # Gemini peer review (adversarial)
        gemini_review = await agent_generate(
            identity=(
                "You are a critical engineering peer reviewer. "
                "You are skeptical and adversarial. Challenge every assumption. "
                "Find potential failure modes, edge cases, and weaknesses. "
                "Rate the prototype specification on a scale of 1-10."
            ),
            prompt=f"Review this prototype specification for: {topic}\n\n{review_summary}",
            model="gemini-2.5-flash",
        )
        
        # Mistral peer review (controversial viewpoint)
        mistral_review = await _mistral_generate(
            prompt=(
                f"You are reviewing a prototype specification for: {topic}\n\n"
                f"{review_summary}\n\n"
                "As a CONTROVERSIAL and ADVERSARIAL reviewer:\n"
                "1. Challenge the fundamental assumptions\n"
                "2. Identify where the deterministic approach may FAIL\n"
                "3. Compare to existing industry solutions\n"
                "4. Rate on a scale of 1-10 for novelty, feasibility, and market readiness\n"
                "5. What would make this ACTUALLY work in production?"
            ),
            system="You are an experienced CTO who has seen many 'revolutionary' technologies fail. Be honest and direct.",
        )
        
        peer_review_report = (
            f"# Multi-LLM Peer Review Report\n\n"
            f"## Gemini 2.5 Flash Review (Adversarial)\n\n{gemini_review}\n\n"
            f"---\n\n"
            f"## Mistral Review (Controversial Viewpoint)\n\n{mistral_review}\n"
        )
        
        with open(f"{prototype_dir}/PEER_REVIEW.md", "w") as f:
            f.write(peer_review_report)
        vault_ids.append(f"{prototype_dir}/PEER_REVIEW.md")
        stages_completed.append("MISTRAL_PEER_REVIEW")
        
        # ---------------------------------------------------------
        # Stage 5: Code Optimization (Deterministic Engine)
        # ---------------------------------------------------------
        log.info("stage_start", stage="CODE_OPTIMIZATION")
        
        optimization_report = "# Code Optimization Report (Deterministic Engine)\n\n"
        optimization_report += "Engine: Python ast + ruff (no LLM — fully deterministic)\n\n"
        
        for idx, snippet in enumerate(all_code_snippets[:5], 1):  # analyze up to 5 snippets
            opt_result = _optimize_code(snippet, "python")
            optimization_report += f"## Snippet {idx}\n"
            optimization_report += f"- Lines: {opt_result['original_lines']}\n"
            optimization_report += f"- Complexity Score: {opt_result['complexity_score']}\n"
            optimization_report += f"- Functions: {opt_result.get('functions_count', 0)}\n"
            optimization_report += f"- Classes: {opt_result.get('classes_count', 0)}\n"
            if opt_result['issues']:
                optimization_report += f"- Issues:\n"
                for issue in opt_result['issues']:
                    optimization_report += f"  - {issue}\n"
            if opt_result['optimizations']:
                optimization_report += f"- Optimizations:\n"
                for opt in opt_result['optimizations']:
                    optimization_report += f"  - {opt}\n"
            optimization_report += "\n"
        
        if not all_code_snippets:
            optimization_report += "No code snippets extracted from prototype iterations.\n"
        
        with open(f"{prototype_dir}/CODE_OPTIMIZATION.md", "w") as f:
            f.write(optimization_report)
        vault_ids.append(f"{prototype_dir}/CODE_OPTIMIZATION.md")
        stages_completed.append("CODE_OPTIMIZATION")

        # ---------------------------------------------------------
        # Stage 6: Final Delivery
        # ---------------------------------------------------------
        log.info("stage_start", stage="FINAL_DELIVERY")
        
        final_report = (
            f"# Prototyping Final Delivery v2\n\n"
            f"## Topic\n{topic}\n\n"
            f"## Pipeline Stages Completed\n"
            + "\n".join(f"- ✅ {s}" for s in stages_completed)
            + f"\n\n## Literature Review\nSee LITERATURE_REVIEW.md\n\n"
            f"## Specification and Design\nSee SPECS_AND_DESIGN.md\n\n"
            f"## Prototype Iterations\n{self.num_loops} iterations completed.\n\n"
            f"## Multi-LLM Peer Review\nSee PEER_REVIEW.md (Gemini + Mistral)\n\n"
            f"## Code Optimization\nSee CODE_OPTIMIZATION.md (deterministic engine)\n\n"
            f"## Final Memory\n{memory}\n\n"
            f"## Final Lessons Learnt\n{lessons}\n"
        )
        
        report_path = f"{prototype_dir}/FINAL_DELIVERY.md"
        with open(report_path, "w") as f:
            f.write(final_report)
        vault_ids.append(report_path)
        stages_completed.append("FINAL_DELIVERY")

        total_duration = time.monotonic() - t0_total
        log.info("prototyping_pipeline_v2_complete", duration_s=round(total_duration, 1))

        return PipelineResult(
            symposium_id=f"prototype_{timestamp}",
            stages_completed=stages_completed,
            total_duration_s=total_duration,
            vault_artifact_ids=vault_ids,
            warnings=warnings,
            audit_trail_path=report_path
        )


def _extract_code_blocks(text: str, accumulator: list[str]) -> None:
    """Extract Python code blocks from markdown text."""
    import re
    pattern = r'```(?:python)?\s*\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    for match in matches:
        if len(match.strip()) > 20:  # skip trivially small snippets
            accumulator.append(match.strip())
