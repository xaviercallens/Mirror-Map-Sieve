# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Galileo CAS Sandbox Tool.

Provides secure, sandboxed execution of deterministic Python scripts,
specifically targeting SymPy (Computer Algebra System) and Z3 (SMT solver).
Allows Galois to halt text generation, compute complex roots or combinatorial
explosions, and inject exact results back into the reasoning trace.
"""

from __future__ import annotations

import ast
import subprocess
import tempfile
from pathlib import Path
from typing import Any
import structlog

logger = structlog.get_logger(__name__)

# Basic safety checks for AST parsing
BANNED_IMPORTS = {"os", "sys", "subprocess", "socket", "urllib", "requests"}

def execute_sympy_sandbox(
    script_code: str,
    timeout_seconds: int = 15,
) -> dict[str, Any]:
    """Execute a Python script containing SymPy or Z3 logic in a secure temporary environment.

    Args:
        script_code: The exact Python source code to run. Must print the final result.
        timeout_seconds: Maximum allowed runtime.

    Returns:
        Dict containing success status and stdout (or error trace).
    """
    logger.info("cas_sandbox_execution_start", code_len=len(script_code))

    # Basic static safety check (naive but effective against accidental harm)
    try:
        tree = ast.parse(script_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    if name.name.split(".")[0] in BANNED_IMPORTS:
                        return {"success": False, "output": f"Security Error: Import of '{name.name}' is banned."}
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in BANNED_IMPORTS:
                    return {"success": False, "output": f"Security Error: Import from '{node.module}' is banned."}
    except SyntaxError as e:
        return {"success": False, "output": f"Syntax Error in script: {e}"}

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        script_file = temp_dir_path / "cas_compute.py"
        script_file.write_text(script_code, encoding="utf-8")

        try:
            # Execute with standard python
            proc = subprocess.run(
                ["python3", "cas_compute.py"],
                cwd=temp_dir_path,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )

            success = proc.returncode == 0
            # Return stdout if successful, otherwise error block
            output = proc.stdout.strip() if success else proc.stderr.strip()
            
            # Prevent context window overflow
            if len(output) > 5000:
                output = output[:5000] + "... [TRUNCATED]"

            if success:
                logger.info("cas_sandbox_execution_success")
            else:
                logger.warning("cas_sandbox_execution_failed")
                
            return {
                "success": success,
                "output": output,
            }

        except subprocess.TimeoutExpired:
            logger.error("cas_sandbox_execution_timeout")
            return {
                "success": False,
                "output": f"Timeout Error: Execution exceeded {timeout_seconds} seconds.",
            }
