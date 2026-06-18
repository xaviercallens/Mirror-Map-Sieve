# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Hypatie LaTeX Compiler Tool.

Compiles LaTeX source code to PDF using standard local toolchains (pdflatex).
Captures compilation errors and parses them to feed back into the self-healing reviewer loop.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any
import structlog

logger = structlog.get_logger(__name__)


def parse_errors_from_log(log_text: str) -> list[dict[str, Any]]:
    """Parse pdflatex log to extract line numbers and error details."""
    errors = []
    
    # Match "! ErrorMessage" followed by "l.LineNum Context"
    pattern = re.compile(r'!\s+([^\n]+)\n(?:.*?\n)*?l\.(\d+)\s*([^\n]*)', re.DOTALL)
    for match in pattern.finditer(log_text):
        msg = match.group(1).replace('\n', ' ').strip().rstrip('.')
        try:
            line_num = int(match.group(2))
        except ValueError:
            line_num = 0
        context = match.group(3).strip()
        errors.append({
            "line": line_num,
            "message": msg,
            "context": context
        })
        
    # Standard LaTeX Error check (e.g. line number specified inside error text)
    if not errors:
        latex_err_pattern = re.compile(r'LaTeX Error:\s+([^\n]+)\s+on input line (\d+)', re.IGNORECASE)
        for match in latex_err_pattern.finditer(log_text):
            msg = match.group(1).strip()
            try:
                line_num = int(match.group(2))
            except ValueError:
                line_num = 0
            errors.append({
                "line": line_num,
                "message": f"LaTeX Error: {msg}",
                "context": ""
            })
            
    # Generic undefined control sequence
    if not errors:
        undef_pattern = re.compile(r'Undefined control sequence\.\s*\n(?:.*?\n)*?l\.(\d+)\s*([^\n]*)')
        for match in undef_pattern.finditer(log_text):
            try:
                line_num = int(match.group(1))
            except ValueError:
                line_num = 0
            context = match.group(2).strip()
            errors.append({
                "line": line_num,
                "message": "Undefined control sequence",
                "context": context
            })
            
    return errors


def compile_latex_to_pdf(
    latex_code: str,
    timeout: int = 60,
) -> dict[str, Any]:
    """Compile LaTeX source to a PDF document.

    Args:
        latex_code: The LaTeX source string.
        timeout: Compilation timeout in seconds.

    Returns:
        Dict containing success status, PDF path (if successful), parsed errors, and compilation logs.
    """
    logger.info("latex_compile_start", code_len=len(latex_code))

    # Check for lualatex
    compiler = shutil.which("lualatex")
    if not compiler:
        logger.warning("lualatex_not_found")
        return {
            "success": False,
            "pdf_path": None,
            "errors": [{"line": 0, "message": "lualatex not found on system PATH", "context": ""}],
            "logs": "lualatex not found on PATH. Please install MacTeX or TeXLive.",
        }

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        tex_file = temp_dir_path / "document.tex"
        tex_file.write_text(latex_code, encoding="utf-8")

        try:
            # Run lualatex (non-interactive mode)
            proc = subprocess.run(
                [compiler, "-interaction=nonstopmode", "-halt-on-error", "document.tex"],
                cwd=temp_dir_path,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            success = proc.returncode == 0
            logs = proc.stdout + "\n" + proc.stderr
            
            # Read log file if it exists, as stdout might be incomplete
            log_file = temp_dir_path / "document.log"
            log_content = logs
            if log_file.exists():
                try:
                    log_content = log_file.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    pass

            parsed_errors = parse_errors_from_log(log_content)

            if success:
                pdf_file = temp_dir_path / "document.pdf"
                if pdf_file.exists():
                    # Move to a permanent location (artifacts)
                    out_dir = Path("/Users/xcallens/.gemini/antigravity/brain/76a159bf-7ca4-49cd-b89c-ab627201e5fd")
                    out_dir.mkdir(parents=True, exist_ok=True)
                    final_pdf = out_dir / "hypatie_compiled.pdf"
                    shutil.copy(pdf_file, final_pdf)
                    
                    logger.info("latex_compile_success", path=str(final_pdf))
                    return {
                        "success": True,
                        "pdf_path": str(final_pdf),
                        "errors": [],
                        "logs": log_content[:2000],  # Truncate logs for agent context
                    }

            logger.warning("latex_compile_failed", error_count=len(parsed_errors))
            return {
                "success": False,
                "pdf_path": None,
                "errors": parsed_errors,
                "logs": log_content[:5000],
            }

        except subprocess.TimeoutExpired:
            logger.error("latex_compile_timeout")
            return {
                "success": False,
                "pdf_path": None,
                "errors": [{"line": 0, "message": f"Compilation timed out after {timeout} seconds.", "context": ""}],
                "logs": f"Compilation timed out after {timeout} seconds.",
            }
