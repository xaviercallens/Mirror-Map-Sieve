# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Lean 4 Semantic REPL Wrapper.

Provides interactive semantic feedback to Archimedes by compiling snippet
theorems against the current Mathlib context and returning the exact
type-checking errors or tactic state outputs.

This upgrades Archimedes from syntactic guessing to semantic resolution.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_LEAN4_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent / "verifiers" / "lean4"
_AGORA_MODULE_DIR = _LEAN4_PROJECT_ROOT / "Agora"

def evaluate_tactic_state(lemma_name: str, imports: str, lemma_statement: str, proof_tactics: str, timeout: int = 30) -> dict[str, Any]:
    """Evaluate a sequence of Lean 4 tactics and return the compiler feedback.
    
    By injecting the tactics into a temporary file and running lake build,
    this provides exact semantic errors (e.g., 'type mismatch', 'unknown identifier')
    so Archimedes can dynamically correct its MCTS path.
    
    Args:
        lemma_name: Name of the lemma being proven.
        imports: Required Lean 4 import statements (e.g., 'import Mathlib').
        lemma_statement: The theorem signature.
        proof_tactics: The sequence of tactics to evaluate.
        timeout: Maximum execution time for lake build.
        
    Returns:
        Dict with keys: success, stdout, stderr, error_message
    """
    lake_bin = shutil.which("lake")
    if not lake_bin:
        return {"success": False, "stdout": "", "stderr": "lake binary not found", "error_message": "Missing lake environment"}

    ts = int(time.time() * 1000)
    module_name = f"ReplEval_{ts}"
    module_file = _AGORA_MODULE_DIR / f"{module_name}.lean"

    full_code = f"""{imports}

{lemma_statement} := by
{proof_tactics}
"""

    logger.debug("lean_repl_eval", module=module_name, tactics=proof_tactics)

    try:
        _AGORA_MODULE_DIR.mkdir(parents=True, exist_ok=True)
        module_file.write_text(full_code, encoding="utf-8")

        env = os.environ.copy()
        if "SSL_CERT_FILE" in env and os.path.isdir(env["SSL_CERT_FILE"]):
            del env["SSL_CERT_FILE"]

        proc = subprocess.run(
            [lake_bin, "build", f"Agora.{module_name}"],
            cwd=str(_LEAN4_PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

        success = proc.returncode == 0
        
        # Extract the specific error line if it exists
        error_message = ""
        for line in proc.stderr.splitlines():
            if "error:" in line:
                error_message = line.split("error:", 1)[1].strip()
                break

        return {
            "success": success,
            "stdout": proc.stdout[:2000],
            "stderr": proc.stderr[:2000],
            "error_message": error_message if not success else "No errors.",
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "Timeout", "error_message": "Tactic evaluation timed out."}
    except Exception as exc:
        return {"success": False, "stdout": "", "stderr": str(exc), "error_message": f"Execution failed: {exc}"}
    finally:
        if module_file.exists():
            module_file.unlink(missing_ok=True)
