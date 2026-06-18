# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Hypatie LaTeX Reviewer Tool ("Fix with AI").

Analyzes LaTeX strings for syntactic and stylistic errors and automatically repairs them
using an iterative self-healing loop guided by pdflatex compilation logs.
"""

from __future__ import annotations

import re
from typing import Any
import structlog
from google import genai

from agents.hypatie.tools.latex_compiler import compile_latex_to_pdf

logger = structlog.get_logger(__name__)


def review_and_repair_latex(
    latex_code: str,
    focus_errors: str = "Syntax, unclosed environments, math mode boundary violations",
    max_iterations: int = 3,
) -> dict[str, Any]:
    """Review and automatically repair LaTeX code using an iterative self-healing compilation loop.

    Args:
        latex_code: The broken or unpolished LaTeX source.
        focus_errors: Specific manual guidelines or initial errors.
        max_iterations: Maximum compile-fix iterations to run.

    Returns:
        Dict containing success status, repaired LaTeX code, pdf path, and a summary of fixes.
    """
    logger.info("latex_repair_start", code_len=len(latex_code), max_iterations=max_iterations)

    current_code = latex_code
    iteration = 0
    compilation_success = False
    pdf_path = None
    last_errors: list[dict[str, Any]] = []
    repair_summary = ""

    # First, run a baseline compilation check
    comp_result = compile_latex_to_pdf(current_code)
    if comp_result["success"]:
        logger.info("latex_repair_early_success")
        return {
            "success": True,
            "repaired_code": current_code,
            "pdf_path": comp_result["pdf_path"],
            "summary": "Document compiled successfully without any modifications.",
            "iterations": 0,
        }
    
    last_errors = comp_result.get("errors", [])
    logger.info("latex_repair_baseline_failed", error_count=len(last_errors))

    client = genai.Client()

    while iteration < max_iterations:
        iteration += 1
        logger.info("latex_repair_loop_iteration", iteration=iteration)

        # Build error context for prompt
        error_context = ""
        for idx, err in enumerate(last_errors):
            error_context += f"Error {idx+1}:\n"
            error_context += f"  Line: {err.get('line', 'Unknown')}\n"
            error_context += f"  Message: {err.get('message', 'Unknown')}\n"
            if err.get("context"):
                error_context += f"  Context around error: {err.get('context')}\n"
            error_context += "\n"

        prompt = f"""
You are Hypatie, the AI librarian and expert LaTeX typesetter for the Socrate AI Lab.
Your task is to "Fix with AI". Review the provided LaTeX code, repair all syntax and formatting errors, and ensure it compiles cleanly with pdflatex.

We just compiled the document, and it failed with the following errors:
{error_context}

Original Focus / Intent:
{focus_errors}

Current LaTeX Source Code:
```latex
{current_code}
```

CRITICAL INSTRUCTIONS:
1. TARGET THE SPECIFIC ERRORS: Check the line numbers and messages provided above. Fix unclosed environments, math boundary violations (like underscores outside math mode), missing packages, or duplicate macro definitions.
2. Maintain all document content. Do not truncate sections or omit user text.
3. Provide the fully repaired LaTeX source code in a single markdown block (```latex ... ```).
4. After the code block, provide a brief bulleted summary of the changes you made in this iteration.
"""

        try:
            response = client.models.generate_content(
                model='gemini-2.5-pro',
                contents=prompt,
            )
            output = response.text
            
            # Extract code
            repaired_chunk = ""
            if "```latex" in output:
                repaired_chunk = output.split("```latex")[1].split("```")[0].strip()
            elif "```" in output:
                repaired_chunk = output.split("```")[1].split("```")[0].strip()
            else:
                # Regex search fallback
                match = re.search(r'\\documentclass.*\\end\{document\}', output, re.DOTALL)
                if match:
                    repaired_chunk = match.group(0)
                else:
                    repaired_chunk = current_code # Fallback to current state
            
            # Extract summary
            summary = output.split("```")[-1].strip() if "```" in output else "No summary provided."
            repair_summary += f"\n--- Iteration {iteration} ---\n{summary}\n"

            # Re-compile
            current_code = repaired_chunk
            comp_result = compile_latex_to_pdf(current_code)
            
            if comp_result["success"]:
                compilation_success = True
                pdf_path = comp_result["pdf_path"]
                logger.info("latex_repair_loop_success", iteration=iteration)
                break
                
            last_errors = comp_result.get("errors", [])
            logger.info("latex_repair_loop_failed_recompile", iteration=iteration, error_count=len(last_errors))

        except Exception as e:
            logger.error("latex_repair_loop_exception", iteration=iteration, error=str(e))
            break

    if compilation_success:
        return {
            "success": True,
            "repaired_code": current_code,
            "pdf_path": pdf_path,
            "summary": f"Successfully repaired and compiled after {iteration} iterations:\n{repair_summary}",
            "iterations": iteration,
        }
    else:
        logger.warning("latex_repair_loop_failed_all_iterations")
        return {
            "success": False,
            "repaired_code": current_code,
            "pdf_path": None,
            "summary": f"Failed to fully compile within {max_iterations} iterations. Last compilation logs had {len(last_errors)} errors:\n{repair_summary}",
            "errors": last_errors,
            "iterations": iteration,
        }
