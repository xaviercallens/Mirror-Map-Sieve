# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Lean 4 proof compiler and type-checker.

Invokes the system ``lean`` compiler to type-check Lean 4 proof code.
A proof is considered verified if and only if:
  1. Exit code is 0 (no type errors)
  2. No ``sorry`` gaps are present
  3. All goals are closed

Reference: de Moura, L. et al. (2021). "The Lean 4 Theorem Prover
and Programming Language". CADE-28.

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CompilationResult:
    """Lean 4 compilation result.

    Attributes:
        success: ``True`` if type-checking passed with exit code 0.
        has_sorry: ``True`` if the proof contains ``sorry`` gaps.
        exit_code: Lean compiler exit code.
        stdout: Compiler stdout.
        stderr: Compiler stderr.
        theorems_found: List of theorem/lemma names found in the source.
        sorry_locations: List of line numbers containing ``sorry``.
        message: Human-readable summary.
    """

    success: bool = False
    has_sorry: bool = False
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    theorems_found: list[str] = field(default_factory=list)
    sorry_locations: list[int] = field(default_factory=list)
    message: str = ""


# ---------------------------------------------------------------------------
# Source analysis
# ---------------------------------------------------------------------------

_SORRY_PATTERN = re.compile(r'\bsorry\b', re.IGNORECASE)
_THEOREM_PATTERN = re.compile(
    r'(?:theorem|lemma|def|noncomputable\s+def)\s+(\w+)', re.IGNORECASE,
)


def _analyse_source(source: str) -> tuple[list[str], list[int]]:
    """Statically analyse Lean 4 source for theorems and sorry gaps.

    Args:
        source: Lean 4 source code.

    Returns:
        Tuple of (theorem_names, sorry_line_numbers).
    """
    lines = source.splitlines()
    theorems = _THEOREM_PATTERN.findall(source)

    sorry_lines = [
        i + 1 for i, line in enumerate(lines)
        if _SORRY_PATTERN.search(line)
        and not line.strip().startswith("--")  # Ignore comments
    ]

    return theorems, sorry_lines


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compile_lean4_proof(
    proof_code: str,
    timeout: int = 120,
) -> dict[str, Any]:
    """Compile and type-check a Lean 4 proof.

    Writes the proof to a temporary ``.lean`` file and invokes the
    ``lean`` compiler.  A proof is considered fully verified only if:

    1. The compiler exits with code 0 (all types check)
    2. No ``sorry`` tactics appear in the source (no axiom gaps)

    Args:
        proof_code: Lean 4 source code as a string.
        timeout: Compilation timeout in seconds.

    Returns:
        Dict representation of :class:`CompilationResult`.

    Example::

        code = '''
        theorem add_comm (a b : Nat) : a + b = b + a := by
          omega
        '''
        result = compile_lean4_proof(code)
        assert result["success"]
        assert not result["has_sorry"]
    """
    logger.info("lean4_compile_start", code_length=len(proof_code))

    # Static analysis
    theorems, sorry_lines = _analyse_source(proof_code)
    has_sorry = len(sorry_lines) > 0

    if has_sorry:
        logger.warning(
            "lean4_sorry_detected",
            sorry_lines=sorry_lines,
            msg="Proof contains 'sorry' gaps — will compile but is incomplete",
        )

    # Check for lean binary
    lean_binary = shutil.which("lean")
    if lean_binary is None:
        logger.warning("lean4_not_found", msg="Lean 4 compiler not installed")
        return {
            "success": False,
            "has_sorry": has_sorry,
            "exit_code": -1,
            "stdout": "",
            "stderr": "Lean 4 compiler not found on PATH",
            "theorems_found": theorems,
            "sorry_locations": sorry_lines,
            "message": (
                "Lean 4 compiler not found. Install from "
                "https://leanprover.github.io/lean4/doc/setup.html"
            ),
        }

    # Write to temp file and compile
    with tempfile.NamedTemporaryFile(
        suffix=".lean", mode="w", delete=False, encoding="utf-8",
    ) as f:
        f.write(proof_code)
        temp_path = Path(f.name)

    try:
        proc = subprocess.run(
            [lean_binary, str(temp_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        success = proc.returncode == 0
        import os
        if os.getenv("AGORA_STRICT_MODE") == "1" and not success:
            raise RuntimeError(f"Lean 4 compilation failed under AGORA_STRICT_MODE: {proc.stderr}")
            
        message_parts: list[str] = []

        if success:
            message_parts.append("Type-checking PASSED ✓")
        else:
            message_parts.append("Type-checking FAILED ✗")
            message_parts.append(proc.stderr[:500] if proc.stderr else "")

        if has_sorry:
            message_parts.append(
                f"WARNING: {len(sorry_lines)} 'sorry' gap(s) at "
                f"line(s) {sorry_lines} — proof is INCOMPLETE"
            )

        if theorems:
            message_parts.append(f"Theorems/defs found: {theorems}")

        result = CompilationResult(
            success=success,
            has_sorry=has_sorry,
            exit_code=proc.returncode,
            stdout=proc.stdout[:2000],
            stderr=proc.stderr[:2000],
            theorems_found=theorems,
            sorry_locations=sorry_lines,
            message=" | ".join(message_parts),
        )

        logger.info(
            "lean4_compile_done",
            success=success,
            has_sorry=has_sorry,
            theorems=theorems,
        )

        return {
            "success": result.success,
            "has_sorry": result.has_sorry,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "theorems_found": result.theorems_found,
            "sorry_locations": result.sorry_locations,
            "message": result.message,
        }

    except subprocess.TimeoutExpired:
        logger.error("lean4_timeout", timeout=timeout)
        import os
        if os.getenv("AGORA_STRICT_MODE") == "1":
            raise RuntimeError(f"Lean 4 compilation timed out after {timeout}s under AGORA_STRICT_MODE")
        return {
            "success": False,
            "has_sorry": has_sorry,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Compilation timed out after {timeout}s",
            "theorems_found": theorems,
            "sorry_locations": sorry_lines,
            "message": f"Lean 4 compilation timed out after {timeout} seconds",
        }
    finally:
        temp_path.unlink(missing_ok=True)
