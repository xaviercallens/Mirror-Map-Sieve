# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Lean 4 Gap Mapper Tool.

Scans the Lean 4 specification library recursively, locating all `sorry` occurrences,
extracting unproven theorem signatures, and compiling a structured gap audit.
"""

from __future__ import annotations

import os
import re
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def map_lean_proof_gaps(library_path: str | None = None) -> dict[str, Any]:
    """Scan all Lean 4 files inside the specification library to report sorry stubs.

    Args:
        library_path: Optional custom path to verifiers/lean4/Agora/.
            Defaults to standard Agora codebase.

    Returns:
        Structured gap report including overall metrics and detailed file audits.
    """
    if library_path is None:
        # Resolve to standard Agora path
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        library_path = os.path.join(base_dir, "verifiers", "lean4", "Agora")

    logger.info("lean_gap_mapping_start", path=library_path)

    if not os.path.exists(library_path):
        logger.error("library_path_not_found", path=library_path)
        return {
            "success": False,
            "message": f"Library path not found: {library_path}",
            "total_gaps": 0,
            "files_audited": 0,
            "details": [],
        }

    total_gaps = 0
    details = []
    lean_files = []

    for root, _, files in os.walk(library_path):
        for f in files:
            if f.endswith(".lean"):
                lean_files.append(os.path.join(root, f))

    for filepath in sorted(lean_files):
        rel_path = os.path.relpath(filepath, library_path)
        
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Count sorries
        sorries = content.count("sorry")
        total_gaps += sorries

        # Parse unproven theorems/lemmas
        unproven_theorems = []
        
        # Regex to match theorem / lemma blocks
        # e.g. theorem foo (x : ℝ) : bar := by ... sorry
        matches = re.finditer(
            r"(?:theorem|lemma)\s+([a-zA-Z0-9_\.]+)\s*(?:[^:=]*)\s*:\s*(?:[^:=]*)\s*:=\s*by\s*(?:.*?)(?=theorem|lemma|def|structure|namespace|end|$)",
            content,
            re.DOTALL
        )

        for m in matches:
            block = m.group(0)
            if "sorry" in block:
                name = m.group(1)
                # Clean signature
                sig_lines = block.split(":=")[0].strip().split("\n")
                signature = " ".join(line.strip() for line in sig_lines)
                unproven_theorems.append({
                    "name": name,
                    "signature": signature,
                })

        details.append({
            "file_name": rel_path,
            "sorry_count": sorries,
            "gaps": unproven_theorems,
            "total_theorems": len(re.findall(r"\b(theorem|lemma)\b", content)),
        })

    success = True
    logger.info("lean_gap_mapping_complete", total_gaps=total_gaps, files=len(details))

    return {
        "success": success,
        "total_gaps": total_gaps,
        "files_audited": len(details),
        "details": details,
        "summary": f"Audited {len(details)} Lean files. Found {total_gaps} unproven sorry stubs.",
    }
