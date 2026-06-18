"""Sorry/Axiom Scanner for Lean 4 codebases.

Parses .lean files to extract every `sorry` and `axiom` occurrence with
its surrounding context (theorem signature, namespace, imports, nearby lemmas).
Produces structured `SorryTarget` / `AxiomTarget` objects for the completion engine.

Usage:
    python -m agents.hilbert.tools.sorry_scanner --root /path/to/Agora
"""
from __future__ import annotations

import re
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ─── Context Window Config ────────────────────────────────────────────────────
CONTEXT_LINES_BEFORE = 30   # lines of context before the sorry
CONTEXT_LINES_AFTER  = 10   # lines of context after the sorry


@dataclass
class SorryTarget:
    """A sorry gap to be completed."""
    file: str
    line: int
    theorem_name: str
    goal_signature: str       # the full theorem/def signature
    sorry_text: str           # the exact sorry line
    context_window: str       # surrounding code for LLM context
    namespace: str            # enclosing namespace
    imports: list[str]        # module imports
    difficulty: str           # "low", "medium", "hard", "extreme"
    tags: list[str] = field(default_factory=list)


@dataclass
class AxiomTarget:
    """An axiom stub that may be replaceable with a Mathlib definition."""
    file: str
    line: int
    axiom_name: str
    axiom_signature: str      # full `axiom` declaration
    context_window: str
    namespace: str
    imports: list[str]
    is_structural: bool       # True if it defines a Type (not provable)
    mathlib_candidate: str    # suggested Mathlib replacement, if any
    difficulty: str


@dataclass
class ScanResult:
    """Full scan result for a Lean 4 codebase."""
    sorry_targets: list[SorryTarget]
    axiom_targets: list[AxiomTarget]
    files_scanned: int
    total_sorrys: int
    total_axioms: int


# ─── Patterns ─────────────────────────────────────────────────────────────────
RE_SORRY     = re.compile(r'\bsorry\b')
RE_AXIOM     = re.compile(r'^\s*axiom\s+(\w+)', re.MULTILINE)
RE_THEOREM   = re.compile(r'^\s*(theorem|lemma|def|noncomputable\s+def)\s+(\w+)', re.MULTILINE)
RE_NAMESPACE = re.compile(r'^\s*namespace\s+(\S+)', re.MULTILINE)
RE_IMPORT    = re.compile(r'^\s*import\s+(\S+)', re.MULTILINE)
RE_COMMENT   = re.compile(r'--.*$|/\-[\s\S]*?\-/', re.MULTILINE)

# ─── Known Mathlib Replacements ───────────────────────────────────────────────
MATHLIB_REPLACEMENTS: dict[str, str] = {
    "Point":                "EllipticCurve.Point",
    "torsionSubgroup":      "EllipticCurve.torsionSubgroup",
    "canonicalHeight":      "EllipticCurve.canonicalHeight",
    "SelmerGroup":          "EllipticCurve.SelmerGroup",
    "TateShafarevich":      "EllipticCurve.TateShafarevich",
    "Coh_category":         "CategoryTheory.Abelian.Coh",
    "Coh_abelian":          "CategoryTheory.Abelian",
    "HasDerivedCategory":   "CategoryTheory.DerivedCategory",
}


def _difficulty_heuristic(context: str, theorem_name: str) -> str:
    """Estimate sorry difficulty based on heuristics."""
    ctx_lower = context.lower()
    # Extreme: Millennium Prize, derived categories, cohomology
    if any(k in ctx_lower for k in ("millennium", "bsd", "navier", "riemann_hypothesis",
                                     "derived_category", "galois_cohomology")):
        return "extreme"
    # Hard: real analysis, topology, advanced algebra
    if any(k in ctx_lower for k in ("real.log", "measurable", "bddbelow", "calabi",
                                     "mirror_symmetry", "holographic")):
        return "hard"
    # Medium: standard mathlib tactics likely suffice
    if any(k in ctx_lower for k in ("finset", "matrix", "nat", "zmod", "linear")):
        return "medium"
    return "low"


def _find_enclosing_theorem(lines: list[str], sorry_line: int) -> tuple[str, str]:
    """Walk backwards from the sorry line to find the enclosing theorem/def."""
    for i in range(sorry_line - 1, max(sorry_line - 40, -1), -1):
        m = RE_THEOREM.match(lines[i])
        if m:
            # Collect the full signature up to `:=` or `where`
            sig_lines = []
            for j in range(i, min(i + 8, len(lines))):
                sig_lines.append(lines[j])
                if ':=' in lines[j] or 'where' in lines[j] or 'by' in lines[j]:
                    break
            return m.group(2), '\n'.join(sig_lines)
    return "unknown", ""


def _find_namespace(lines: list[str], target_line: int) -> str:
    """Find the innermost enclosing namespace."""
    depth = 0
    ns = ""
    for i in range(target_line, -1, -1):
        line = lines[i].strip()
        if line.startswith("end "):
            depth += 1
        m = RE_NAMESPACE.match(lines[i])
        if m:
            if depth > 0:
                depth -= 1
            else:
                ns = m.group(1)
                break
    return ns


def _context_window(lines: list[str], target_line: int) -> str:
    """Extract a window of code around the target line."""
    start = max(0, target_line - CONTEXT_LINES_BEFORE)
    end   = min(len(lines), target_line + CONTEXT_LINES_AFTER + 1)
    return '\n'.join(lines[start:end])


def _is_in_comment(content: str, match_start: int) -> bool:
    """Check if a match position falls inside a comment."""
    # Check line comment
    line_start = content.rfind('\n', 0, match_start) + 1
    line_prefix = content[line_start:match_start]
    if '--' in line_prefix:
        return True
    # Check block comment
    block_start = content.rfind('/-', 0, match_start)
    if block_start != -1:
        block_end = content.find('-/', block_start)
        if block_end == -1 or block_end > match_start:
            return True
    return False


def scan_file(filepath: Path) -> tuple[list[SorryTarget], list[AxiomTarget]]:
    """Scan a single .lean file for sorry and axiom targets."""
    content = filepath.read_text(encoding='utf-8', errors='replace')
    lines   = content.split('\n')

    # Extract imports
    imports = RE_IMPORT.findall(content)

    sorrys: list[SorryTarget] = []
    axioms: list[AxiomTarget] = []

    # ── Scan for sorry ────────────────────────────────────────────────────
    for match in RE_SORRY.finditer(content):
        if _is_in_comment(content, match.start()):
            continue
        line_no = content[:match.start()].count('\n')
        thm_name, thm_sig = _find_enclosing_theorem(lines, line_no)
        ns = _find_namespace(lines, line_no)
        ctx = _context_window(lines, line_no)
        diff = _difficulty_heuristic(ctx, thm_name)
        sorrys.append(SorryTarget(
            file=str(filepath),
            line=line_no + 1,
            theorem_name=thm_name,
            goal_signature=thm_sig,
            sorry_text=lines[line_no].strip(),
            context_window=ctx,
            namespace=ns,
            imports=imports,
            difficulty=diff,
        ))

    # ── Scan for axiom ────────────────────────────────────────────────────
    for match in RE_AXIOM.finditer(content):
        if _is_in_comment(content, match.start()):
            continue
        line_no = content[:match.start()].count('\n')
        ax_name = match.group(1)
        ax_sig  = lines[line_no].strip()
        ns      = _find_namespace(lines, line_no)
        ctx     = _context_window(lines, line_no)

        # Check if axiom defines a Type (structural) vs a Prop (provable)
        is_structural = ': Type' in ax_sig or '→ Type' in ax_sig
        mathlib_cand  = MATHLIB_REPLACEMENTS.get(ax_name, "")
        diff = "extreme" if is_structural else _difficulty_heuristic(ctx, ax_name)

        axioms.append(AxiomTarget(
            file=str(filepath),
            line=line_no + 1,
            axiom_name=ax_name,
            axiom_signature=ax_sig,
            context_window=ctx,
            namespace=ns,
            imports=imports,
            is_structural=is_structural,
            mathlib_candidate=mathlib_cand,
            difficulty=diff,
        ))

    return sorrys, axioms


def scan_directory(root: str | Path, glob: str = "**/*.lean") -> ScanResult:
    """Recursively scan a directory for all sorry/axiom targets."""
    root_path = Path(root)
    all_sorrys: list[SorryTarget] = []
    all_axioms: list[AxiomTarget] = []
    files_scanned = 0

    for filepath in sorted(root_path.glob(glob)):
        if '.lake' in str(filepath) or 'build' in str(filepath):
            continue
        try:
            s, a = scan_file(filepath)
            all_sorrys.extend(s)
            all_axioms.extend(a)
            files_scanned += 1
        except Exception as e:
            logger.warning("scan_error", file=str(filepath), error=str(e))

    result = ScanResult(
        sorry_targets=all_sorrys,
        axiom_targets=all_axioms,
        files_scanned=files_scanned,
        total_sorrys=len(all_sorrys),
        total_axioms=len(all_axioms),
    )
    logger.info(
        "scan_complete",
        files=files_scanned,
        sorrys=result.total_sorrys,
        axioms=result.total_axioms,
    )
    return result


def scan_sorrys(root: str = "Agora") -> dict[str, Any]:
    """A2A tool entry point: scan for sorry/axiom targets.
    
    Returns a structured dict with all targets, grouped by difficulty.
    """
    result = scan_directory(root)
    return {
        "files_scanned": result.files_scanned,
        "total_sorrys": result.total_sorrys,
        "total_axioms": result.total_axioms,
        "sorry_targets": [
            {
                "file": t.file,
                "line": t.line,
                "theorem_name": t.theorem_name,
                "goal_signature": t.goal_signature,
                "difficulty": t.difficulty,
                "namespace": t.namespace,
            }
            for t in sorted(result.sorry_targets, key=lambda x: (
                {"low": 0, "medium": 1, "hard": 2, "extreme": 3}[x.difficulty]
            ))
        ],
        "axiom_targets": [
            {
                "file": t.file,
                "line": t.line,
                "axiom_name": t.axiom_name,
                "is_structural": t.is_structural,
                "mathlib_candidate": t.mathlib_candidate,
                "difficulty": t.difficulty,
            }
            for t in result.axiom_targets
        ],
    }


# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse, json
    parser = argparse.ArgumentParser(description="Scan Lean 4 files for sorry/axiom targets")
    parser.add_argument("--root", default="Agora", help="Root directory to scan")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    result = scan_sorrys(args.root)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"Sorry/Axiom Scan Results — {result['files_scanned']} files")
        print(f"{'='*60}")
        print(f"  Total sorrys: {result['total_sorrys']}")
        print(f"  Total axioms: {result['total_axioms']}")
        print(f"\n--- Sorry Targets (by difficulty) ---")
        for t in result["sorry_targets"]:
            icon = {"low": "🟢", "medium": "🟡", "hard": "🟠", "extreme": "🔴"}[t["difficulty"]]
            print(f"  {icon} {t['theorem_name']:40s} | {t['difficulty']:8s} | {t['file']}:{t['line']}")
        print(f"\n--- Axiom Targets ---")
        for t in result["axiom_targets"]:
            struct = "📦 structural" if t["is_structural"] else "🔓 provable"
            ml = f" → {t['mathlib_candidate']}" if t["mathlib_candidate"] else ""
            print(f"  {struct:16s} {t['axiom_name']:40s} | {t['file']}:{t['line']}{ml}")
