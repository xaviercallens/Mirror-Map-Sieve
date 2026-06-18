# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Hypatie LaTeX Synthesizer Tool.

Generates rigorous, high-standard LaTeX markup from raw mathematical proofs,
monographs, or general academic drafts, enforcing premium typesetting policies.
"""

from __future__ import annotations

from typing import Any
import structlog
from google import genai

logger = structlog.get_logger(__name__)


def generate_latex_source(
    title: str,
    raw_content: str,
    document_type: str = "general",  # "research", "monograph", "report", "letter", "general"
    document_class: str = "article",
    include_preamble: bool = True,
) -> dict[str, Any]:
    """Synthesize structured LaTeX source code from raw mathematical content.

    Args:
        title: The title of the document or section.
        raw_content: The raw text, proof steps, or dialectic to be formalized.
        document_type: The target layout type.
        document_class: LaTeX document class (e.g., article, book, report).
        include_preamble: Whether to generate a full compilable document or just a snippet.

    Returns:
        Dict containing the synthesized LaTeX code.
    """
    logger.info("latex_synthesis_start", title=title, type=document_type)

    # Establish layout hints based on document type
    layout_hints = ""
    if document_type == "research":
        layout_hints = """
- This is a formal academic research paper.
- Structure must include: Abstract, Introduction, Methodology, Main Results/Theorems, Discussion, and Bibliography.
- Use \\newtheorem definitions for Theorems, Lemmas, and Proofs.
- Enforce the use of standard citations (e.g. \\cite{...}).
"""
    elif document_type == "monograph":
        layout_hints = """
- This is a comprehensive mathematical monograph.
- Structure must include: Table of Contents, Introduction, Chapters, Sections, Lemmas/Theorems, and a formal References bibliography.
- Enforce elegant spacing, clear chapter transitions, and detailed mathematical proofs.
"""
    elif document_type == "report":
        layout_hints = """
- This is a formal technical report.
- Structure must include: Executive Summary, Table of Contents, Detailed Sections, and Verification Metrics.
- Enforce clean listing/code structures using the `listings` package if code is present.
"""
    elif document_type == "letter":
        layout_hints = """
- This is a formal letter or statement.
- Structure must include: Date, Addressee, Salutation, Body, and Closing.
- Keep the layout clean, concise, and professional.
"""

    prompt = f"""
You are Hypatie, the AI librarian and expert LaTeX typesetter for the Socrate AI Lab.
Your task is to take the following raw mathematical content and synthesize it into beautiful, high-standard LaTeX.

Title: {title}
Document Type: {document_type}
Document Class: {document_class}
Include Full Preamble: {include_preamble}

Raw Content to Formalize:
{raw_content}

Layout Hints for this Document Type:
{layout_hints}

STRICT TYPESETTING & COMPILATION CONSTRAINTS:
1. **Compilation Engine**: The output MUST be fully compatible with **lualatex**.
   - YOU MUST USE `fontspec` and `unicode-math`.
   - Set the main font to `DejaVu Serif` using `\\setmainfont{{DejaVu Serif}}`.
   - DO NOT use packages that require shell-escape (e.g., `minted` - use `listings` instead).
2. **Premium Table Aesthetics**:
   - For all tables, use the `booktabs` package (`\\toprule`, `\\midrule`, `\\bottomrule`).
   - STRICTLY FORBIDDEN: Vertical lines (`|`) in tables.
3. **Mathematical Formats**:
   - Use standard AMS packages (`amsmath`, `amssymb`, `amsthm`).
   - Use `align` or `equation` environments for equations. Avoid outdated `eqnarray`.
   - Ensure proper subscripts, superscripts, and operators are wrapped inside math mode (e.g., $x_{{i}}$ instead of x_i).
4. **Preamble Structure**:
   - If `include_preamble` is True, output a complete, compilable document starting with `\\documentclass` and ending with `\\end{{document}}`.
   - approved fonts: `lmodern` (default), `mathptmx` (Times), `helvet` (Helvetica), `courier`.
5. **Output Format**:
   - Output ONLY valid LaTeX code inside a markdown code block (```latex ... ```).
   - No explanations, no markdown prefix, no text outside the code block.
"""

    client = genai.Client()
    try:
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=prompt,
        )
        code = response.text
        if "```latex" in code:
            code = code.split("```latex")[1].split("```")[0].strip()
        elif "```" in code:
            code = code.split("```")[1].split("```")[0].strip()
            
    except Exception as e:
        logger.error("latex_synthesis_failed", error=str(e))
        return {"success": False, "latex_code": "", "message": str(e)}

    logger.info("latex_synthesis_complete", title=title)
    return {
        "success": True,
        "latex_code": code,
        "message": "LaTeX synthesized successfully.",
    }
