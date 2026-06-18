# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Euler Lean 4 REPL Interactive Loop Tool.

Provides an interactive compilation loop for the Pythagore formalizer agent.
Pythagore proposes tactics, and Euler evaluates them through the `lean` binary,
returning the compiler state (or exact error logs) until the `No goals` state
is reached.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any
import structlog

logger = structlog.get_logger(__name__)

def execute_lean4_repl_step(
    proof_state_code: str,
    timeout_seconds: int = 15,
) -> dict[str, Any]:
    """Execute a single step of the Lean 4 REPL interactive loop.

    Enforces zero-sorry policy.

    Args:
        proof_state_code: The full Lean 4 code with the current tactic applied.
        timeout_seconds: Execution timeout.

    Returns:
        Dict containing success, compiler output, and whether 'sorry' is present.
    """
    logger.info("lean4_repl_step_start", code_len=len(proof_state_code))

    # Zero-sorry enforcement (Parser level)
    if "sorry" in proof_state_code or "sorryAx" in proof_state_code or "admit" in proof_state_code or "True := by trivial" in proof_state_code:
        return {
            "success": False,
            "status": "FAILED_OPEN_GAPS",
            "output": "REJECTED: Proof contains 'sorry', 'sorryAx', 'admit', or an empty tautology. Zero-sorry policy enforced.",
            "has_sorry": True,
            "value": -1.0,
        }

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        lean_file = temp_dir_path / "ReplDraft.lean"
        lean_file.write_text(proof_state_code, encoding="utf-8")

        try:
            # We assume lean is in path
            proc = subprocess.run(
                ["lean", "ReplDraft.lean"],
                cwd=temp_dir_path,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )

            success = proc.returncode == 0
            
            output = proc.stderr.strip() if proc.stderr else proc.stdout.strip()
            if not output and success:
                output = "Compilation successful. No goals remaining."

            return {
                "success": success,
                "output": output,
                "has_sorry": False,
            }

        except subprocess.TimeoutExpired:
            logger.error("lean4_repl_timeout")
            return {
                "success": False,
                "output": f"Timeout Error: Lean 4 compilation exceeded {timeout_seconds} seconds.",
                "has_sorry": False,
            }
