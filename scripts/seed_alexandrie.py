# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Alexandrie Day-Zero Memory Seeder.

Loads the HorizonMath .lean discoveries into the FAISS vector database
as foundational 'Day-Zero' memory entries. This ensures the Sentinel
never starts from absolute zero — it begins from the shoulders of
every HorizonMath proof it has already verified.

Usage:
    python scripts/seed_alexandrie.py [--vault-root /path/to/vault]
    python scripts/seed_alexandrie.py --lean-dir verifiers/lean4/Agora

Reference: AGORA v4: THE ALEXANDRIE MEMORY UPGRADE, Section 3.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import structlog

from alexandrie.hub import AlexandrieHub
from alexandrie.metadata import ArtifactType, RoomType

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Lean 4 Proof Extractor
# ---------------------------------------------------------------------------

# Patterns for extracting theorem/lemma names and their tactic blocks
_THEOREM_RE = re.compile(
    r"(?:theorem|lemma)\s+(\w+).*?:=\s*by\s*\n((?:[ \t]+.*\n)*)",
    re.MULTILINE,
)

# Pattern for sorry-free proven theorems
_SORRY_CHECK = re.compile(r"\bsorry\b")

# Pattern for tactic state comments (-- Goal: ...)
_STATE_COMMENT_RE = re.compile(r"--\s*(?:Goal|State|⊢):\s*(.+)")


def extract_proven_theorems(lean_source: str) -> list[dict[str, str]]:
    """Extract proven (sorry-free) theorems from Lean 4 source.

    Returns:
        List of dicts with keys: name, tactic_block, goal_state (if found).
    """
    results = []
    for match in _THEOREM_RE.finditer(lean_source):
        name = match.group(1)
        tactic_block = match.group(2).strip()

        # Skip sorry-containing theorems
        if _SORRY_CHECK.search(tactic_block):
            continue

        # Try to extract the goal state from comments
        goal_state = ""
        # Look backwards from the theorem for doc-comments or state annotations
        start_pos = match.start()
        context = lean_source[max(0, start_pos - 200):start_pos]
        state_match = _STATE_COMMENT_RE.search(context)
        if state_match:
            goal_state = state_match.group(1).strip()

        # Extract individual tactics
        tactics = []
        for line in tactic_block.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("--"):
                tactics.append(stripped)

        results.append({
            "name": name,
            "tactic_block": tactic_block,
            "tactics": tactics,
            "goal_state": goal_state,
        })

    return results


def extract_all_lean_theorems(lean_source: str) -> list[dict[str, str]]:
    """Extract ALL theorems (including sorry ones) for cataloging.

    Used for ingesting proof artifacts into Alexandrie's vault,
    even if the proofs are not yet complete.
    """
    results = []
    for match in _THEOREM_RE.finditer(lean_source):
        name = match.group(1)
        tactic_block = match.group(2).strip()
        has_sorry = bool(_SORRY_CHECK.search(tactic_block))

        results.append({
            "name": name,
            "tactic_block": tactic_block,
            "has_sorry": has_sorry,
        })

    return results


# ---------------------------------------------------------------------------
# Seeder
# ---------------------------------------------------------------------------

class AlexandrieSeeder:
    """Seeds the Alexandrie FAISS memory with HorizonMath .lean artifacts.

    Two-layer ingestion:
    1. **Vault layer**: Store the full .lean file as a scientific artifact.
    2. **Memory layer**: Extract proven theorems and index their tactic
       states in FAISS for RAG retrieval.
    """

    def __init__(self, hub: AlexandrieHub) -> None:
        self.hub = hub
        self._stats = {
            "files_scanned": 0,
            "theorems_found": 0,
            "theorems_proven": 0,
            "theorems_sorry": 0,
            "memory_entries_added": 0,
            "vault_artifacts_stored": 0,
        }

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)

    def seed_from_directory(
        self,
        lean_dir: str,
        room: str = "open",
        recursive: bool = True,
    ) -> dict[str, int]:
        """Scan a directory for .lean files and seed Alexandrie.

        Args:
            lean_dir: Path to directory containing .lean files.
            room: Alexandrie room ('open' or 'private').
            recursive: Whether to scan subdirectories.

        Returns:
            Statistics dict.
        """
        lean_files = []
        for root, dirs, files in os.walk(lean_dir):
            for f in files:
                if f.endswith(".lean") and not f.startswith("."):
                    lean_files.append(os.path.join(root, f))
            if not recursive:
                break

        logger.info("seeder_scan", directory=lean_dir, files_found=len(lean_files))

        for lean_path in sorted(lean_files):
            self._seed_single_file(lean_path, room)

        logger.info("seeder_complete", **self._stats)
        return dict(self._stats)

    def _seed_single_file(self, lean_path: str, room: str) -> None:
        """Seed a single .lean file."""
        self._stats["files_scanned"] += 1

        with open(lean_path, "r", encoding="utf-8") as f:
            source = f.read()

        filename = os.path.basename(lean_path)
        rel_path = lean_path  # Keep full path for traceability

        # --- Layer 1: Vault Artifact ---
        try:
            room_type = RoomType.OPEN_ACCESS if room == "open" else RoomType.PRIVATE
            artifact_id = f"horizonmath_{filename.replace('.lean', '').lower()}"
            self.hub.store_artifact(
                artifact_id=artifact_id,
                title=f"HorizonMath/{filename}",
                content=source,
                artifact_type=ArtifactType.PROOF,
                room_type=room_type,
                creator="alexandrie_seeder",
                tags=["horizonmath", "lean4", "day-zero"],
                extra_attributes={
                    "source_path": rel_path,
                    "line_count": source.count("\n"),
                },
            )
            self._stats["vault_artifacts_stored"] += 1
        except Exception as exc:
            logger.warning("vault_store_failed", file=filename, error=str(exc))

        # --- Layer 2: FAISS Memory Entries ---
        all_theorems = extract_all_lean_theorems(source)
        proven_theorems = extract_proven_theorems(source)

        self._stats["theorems_found"] += len(all_theorems)
        self._stats["theorems_proven"] += len(proven_theorems)
        self._stats["theorems_sorry"] += sum(1 for t in all_theorems if t.get("has_sorry"))

        if self.hub.semantic_memory is None:
            return

        for theorem in proven_theorems:
            # Build the Lean state string for embedding
            # If we have a goal state from comments, use it
            lean_state = theorem.get("goal_state", "")
            if not lean_state:
                # Construct a synthetic state from the theorem name + tactic block
                lean_state = f"⊢ {theorem['name']} := by {theorem['tactic_block'][:200]}"

            winning_tactic = "; ".join(theorem["tactics"])

            try:
                self.hub.semantic_memory.memorize(
                    lean_state=lean_state,
                    winning_tactic=winning_tactic,
                    informal_blueprint=f"HorizonMath proof: {theorem['name']} from {filename}",
                )
                self._stats["memory_entries_added"] += 1
            except Exception as exc:
                logger.warning(
                    "memory_index_failed",
                    theorem=theorem["name"],
                    error=str(exc),
                )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Seed Alexandrie FAISS memory with HorizonMath .lean discoveries"
    )
    parser.add_argument(
        "--lean-dir",
        type=str,
        default=None,
        help="Directory containing .lean files (default: verifiers/lean4/Agora)",
    )
    parser.add_argument(
        "--vault-root",
        type=str,
        default=None,
        help="Alexandrie vault root directory",
    )
    parser.add_argument(
        "--room",
        type=str,
        default="open",
        choices=["open", "private"],
        help="Alexandrie room for artifacts",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Don't scan subdirectories",
    )
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    lean_dir = args.lean_dir or os.path.join(project_root, "verifiers", "lean4", "Agora")
    vault_root = args.vault_root or os.path.join(
        os.path.expanduser("~"), ".gemini", "antigravity", "alexandrie_vault"
    )

    if not os.path.isdir(lean_dir):
        print(f"ERROR: Lean directory not found: {lean_dir}")
        sys.exit(1)

    print(f"\n🏛️  ALEXANDRIE DAY-ZERO MEMORY SEEDER")
    print(f"    Lean directory:  {lean_dir}")
    print(f"    Vault root:      {vault_root}")
    print(f"    Room:            {args.room}")
    print()

    hub = AlexandrieHub(
        vault_root=vault_root,
        enable_semantic_memory=True,
    )

    seeder = AlexandrieSeeder(hub)
    t0 = time.perf_counter()

    stats = seeder.seed_from_directory(
        lean_dir=lean_dir,
        room=args.room,
        recursive=not args.no_recursive,
    )

    elapsed = (time.perf_counter() - t0) * 1000

    print(f"\n📊 SEEDING RESULTS")
    print(f"    Files scanned:        {stats['files_scanned']}")
    print(f"    Theorems found:       {stats['theorems_found']}")
    print(f"    Theorems proven:      {stats['theorems_proven']}")
    print(f"    Theorems with sorry:  {stats['theorems_sorry']}")
    print(f"    Memory entries added: {stats['memory_entries_added']}")
    print(f"    Vault artifacts:      {stats['vault_artifacts_stored']}")
    print(f"    Total time:           {elapsed:.1f}ms")
    print()


if __name__ == "__main__":
    main()
