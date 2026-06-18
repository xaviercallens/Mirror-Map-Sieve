#!/usr/bin/env python3
"""
SocrateAI Agora — Lean 4 Comprehensive Compiler & Verifier
===========================================================
Per-module build harness with sorry/axiom classification.

Usage:
    cd verifiers/lean4
    python verify.py              # Full audit
    python verify.py --module saw_simple_cubic  # Single module

Output:
    proof/compilation_report.md   — Human-readable Markdown
    proof/audit.json              — Machine-readable JSON
"""

import subprocess
import json
import re
import os
import sys
import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

# ─── Configuration ───────────────────────────────────────────────────

LEAN4_ROOT = Path(__file__).parent
AGORA_DIR = LEAN4_ROOT / "Agora"
PROOF_DIR = LEAN4_ROOT / "proof"

# All known modules, grouped by verification tier
MODULES = {
    # Tier 1: Core verified (zero sorry, zero axiom)
    "tier1_verified": [
        "Agora.Basic",
        "Agora.AlienMath.KalTensorDecomposition",
        "Agora.AlienMath.NonCommutativeCryptography",
        "Agora.AlienMath.LyapunovFunctional",
        "Agora.AlienMath.StrassenVerified",
        "Agora.AlienMath.KalChargingMatrix",
        "Agora.AlienMath.ExactRationalWitness",
        "Agora.AlienMath.KalSliceConcatenation",
        "Agora.AlienMath.KalEntropy",
        "Agora.AlienMath.KalHolographicBorderRank",
        "Agora.AlienMath.TensorDeformations",
        "Agora.AlienMath.Applications.Cryptography",
        "Agora.AlienMath.Applications.Quantum",
    ],
    # Tier 2: Shattered axiom proofs (sorry on Earth gaps only)
    "tier2_shattered": [
        "Agora.saw_simple_cubic",
    ],
    # Tier 3: Axiomatic Local Contexts (external compute pending)
    "tier3_axiomatic": [
        "Agora.diff_basis_optimal_10000",
        "Agora.crossing_number_kn",
    ],
    # Tier 4: Heavy blueprints (many sorry — formalization frontier)
    "tier4_blueprints": [
        "Agora.E37BSD_v6_blueprint",
        "Agora.cmi_millennium_blueprints",
    ],
    # Tier 5: Infrastructure debt registry
    "tier5_infra": [
        "Agora.FormalizationDebt",
    ],
    # Tier 6: Callens Conjectures
    "tier6_callens_conjectures": [
        "Agora.Conjectures.LatticePacking",
        "Agora.Conjectures.SchurPositivity",
        "Agora.Conjectures.TownesSoliton",
        "Agora.Conjectures.MirrorSymmetry",
        "Agora.Conjectures.FeynmanSunrise",
    ],
}


# ─── Data Structures ────────────────────────────────────────────────

@dataclass
class ModuleAudit:
    module: str
    tier: str
    status: str = "unknown"  # verified, axiom_blocked, earth_gapped, sorry_blocked, build_failed
    build_ok: bool = False
    sorry_count: int = 0
    axiom_count: int = 0
    warning_count: int = 0
    error_messages: list = field(default_factory=list)
    sorry_locations: list = field(default_factory=list)
    axiom_names: list = field(default_factory=list)
    build_time_ms: int = 0
    raw_output: str = ""


# ─── Core Functions ─────────────────────────────────────────────────

def build_module(module: str) -> tuple[bool, str, str]:
    """Build a single Lean module via lake. Returns (success, stdout, stderr)."""
    try:
        result = subprocess.run(
            [os.path.expanduser("~/.elan/bin/lake"), "build", module],
            capture_output=True, text=True, timeout=600,
            cwd=str(LEAN4_ROOT)
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "BUILD TIMEOUT (600s)"
    except FileNotFoundError:
        return False, "", "'lake' not found. Ensure Lean toolchain is active."


def scan_file_for_sorry(filepath: Path) -> list[dict]:
    """Scan a .lean file for sorry occurrences (excluding comments and strings)."""
    locations = []
    in_block_comment = False
    try:
        with open(filepath, 'r') as f:
            for i, line in enumerate(f, 1):
                stripped = line.strip()
                # Track block comments
                if "/-" in stripped:
                    in_block_comment = True
                if "-/" in stripped:
                    in_block_comment = False
                    continue
                if in_block_comment:
                    continue
                # Skip single-line comments
                if stripped.startswith("--"):
                    continue
                # Skip lines where sorry only appears in a string literal
                if '"' in stripped:
                    # Remove string contents before checking
                    no_strings = re.sub(r'"[^"]*"', '""', stripped)
                    if not re.search(r'\bsorry\b', no_strings):
                        continue
                if re.search(r'\bsorry\b', stripped):
                    locations.append({"line": i, "content": stripped})
    except FileNotFoundError:
        pass
    return locations


def scan_file_for_axioms(filepath: Path) -> list[str]:
    """Scan a .lean file for axiom declarations."""
    axioms = []
    try:
        with open(filepath, 'r') as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("axiom "):
                    name = stripped.split()[1].split("(")[0].split(":")[0].strip()
                    axioms.append(name)
    except FileNotFoundError:
        pass
    return axioms


def module_to_filepath(module: str) -> Path:
    """Convert a Lean module name to its filesystem path."""
    relative = module.replace(".", "/") + ".lean"
    return LEAN4_ROOT / relative


def classify_module(audit: ModuleAudit) -> str:
    """Classify a module's verification status."""
    if not audit.build_ok:
        return "build_failed"
    if audit.sorry_count == 0 and audit.axiom_count == 0:
        return "verified"
    if audit.sorry_count == 0 and audit.axiom_count > 0:
        return "axiom_blocked"
    if audit.axiom_count > 0 and audit.sorry_count > 0:
        return "earth_gapped"
    return "sorry_blocked"


STATUS_EMOJI = {
    "verified": "🟢",
    "axiom_blocked": "🟡",
    "earth_gapped": "🟠",
    "sorry_blocked": "🔴",
    "build_failed": "⚪",
    "unknown": "❓",
}

STATUS_LABEL = {
    "verified": "Verified",
    "axiom_blocked": "Axiom-blocked",
    "earth_gapped": "Earth-gapped",
    "sorry_blocked": "Sorry-blocked",
    "build_failed": "Build Failed",
    "unknown": "Unknown",
}


# ─── Audit Pipeline ─────────────────────────────────────────────────

def audit_module(module: str, tier: str) -> ModuleAudit:
    """Full audit of a single module: build + scan."""
    audit = ModuleAudit(module=module, tier=tier)
    filepath = module_to_filepath(module)

    # Static analysis
    audit.sorry_locations = scan_file_for_sorry(filepath)
    audit.sorry_count = len(audit.sorry_locations)
    audit.axiom_names = scan_file_for_axioms(filepath)
    audit.axiom_count = len(audit.axiom_names)

    # Build
    print(f"  [{tier}] Building {module}...", end=" ", flush=True)
    import time
    t0 = time.time()
    ok, stdout, stderr = build_module(module)
    elapsed = int((time.time() - t0) * 1000)
    audit.build_time_ms = elapsed
    audit.build_ok = ok
    audit.raw_output = stdout + stderr

    if ok:
        # Count warnings from build output
        audit.warning_count = audit.raw_output.count("warning:")
        print(f"✔ ({elapsed}ms, {audit.sorry_count}s/{audit.axiom_count}a)")
    else:
        # Extract error messages
        errors = [line for line in audit.raw_output.split("\n") if "error:" in line]
        audit.error_messages = errors[:5]  # Keep first 5
        print(f"✖ ({elapsed}ms)")
        for err in audit.error_messages[:2]:
            print(f"    {err.strip()[:120]}")

    audit.status = classify_module(audit)
    return audit


def run_full_audit(filter_module: Optional[str] = None) -> list[ModuleAudit]:
    """Run audit on all modules (or a filtered subset)."""
    results = []
    for tier, modules in MODULES.items():
        for module in modules:
            if filter_module and filter_module not in module:
                continue
            audit = audit_module(module, tier)
            results.append(audit)
    return results


# ─── Report Generation ──────────────────────────────────────────────

def generate_markdown_report(results: list[ModuleAudit]) -> str:
    """Generate the human-readable compilation report."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    total = len(results)
    verified = sum(1 for r in results if r.status == "verified")
    axiom_blocked = sum(1 for r in results if r.status == "axiom_blocked")
    earth_gapped = sum(1 for r in results if r.status == "earth_gapped")
    sorry_blocked = sum(1 for r in results if r.status == "sorry_blocked")
    build_failed = sum(1 for r in results if r.status == "build_failed")
    total_sorry = sum(r.sorry_count for r in results)
    total_axiom = sum(r.axiom_count for r in results)

    lines = []
    lines.append("# SocrateAI Agora — Lean 4 Compilation Report")
    lines.append("")
    lines.append(f"**Generated:** {now}")
    lines.append(f"**Toolchain:** leanprover/lean4:v4.14.0")
    lines.append(f"**Mathlib:** v4.14.0")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Metric | Count |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total modules | {total} |")
    lines.append(f"| 🟢 Verified | {verified} |")
    lines.append(f"| 🟡 Axiom-blocked | {axiom_blocked} |")
    lines.append(f"| 🟠 Earth-gapped | {earth_gapped} |")
    lines.append(f"| 🔴 Sorry-blocked | {sorry_blocked} |")
    lines.append(f"| ⚪ Build failed | {build_failed} |")
    lines.append(f"| Total `sorry` | {total_sorry} |")
    lines.append(f"| Total `axiom` | {total_axiom} |")
    lines.append("")
    lines.append(f"**Verification score:** {verified}/{total} modules fully verified ({100*verified//max(total,1)}%)")
    lines.append("")

    # Per-tier breakdown
    for tier_name, tier_label in [
        ("tier1_verified", "Tier 1: Core Verified"),
        ("tier2_shattered", "Tier 2: Shattered Axiom Proofs"),
        ("tier3_axiomatic", "Tier 3: Axiomatic Local Contexts"),
        ("tier4_blueprints", "Tier 4: Heavy Blueprints"),
        ("tier5_infra", "Tier 5: Infrastructure"),
        ("tier6_callens_conjectures", "Tier 6: Callens Conjectures"),
    ]:
        tier_results = [r for r in results if r.tier == tier_name]
        if not tier_results:
            continue
        lines.append(f"### {tier_label}")
        lines.append("")
        lines.append("| Status | Module | `sorry` | `axiom` | Build |")
        lines.append("|--------|--------|---------|---------|-------|")
        for r in tier_results:
            emoji = STATUS_EMOJI.get(r.status, "❓")
            build_str = f"✔ {r.build_time_ms}ms" if r.build_ok else "✖ FAIL"
            short_module = r.module.replace("Agora.", "")
            lines.append(f"| {emoji} | `{short_module}` | {r.sorry_count} | {r.axiom_count} | {build_str} |")
        lines.append("")

    # Sorry locations
    sorry_modules = [r for r in results if r.sorry_count > 0]
    if sorry_modules:
        lines.append("## Sorry Gap Locations")
        lines.append("")
        for r in sorry_modules:
            lines.append(f"### `{r.module}`")
            for loc in r.sorry_locations:
                lines.append(f"- Line {loc['line']}: `{loc['content'][:100]}`")
            lines.append("")

    # Axiom inventory
    axiom_modules = [r for r in results if r.axiom_count > 0]
    if axiom_modules:
        lines.append("## Axiom Inventory")
        lines.append("")
        for r in axiom_modules:
            lines.append(f"### `{r.module}` ({r.axiom_count} axioms)")
            for name in r.axiom_names:
                lines.append(f"- `{name}`")
            lines.append("")

    # Build failures
    failed = [r for r in results if not r.build_ok]
    if failed:
        lines.append("## Build Failures")
        lines.append("")
        for r in failed:
            lines.append(f"### `{r.module}`")
            for err in r.error_messages:
                lines.append(f"```")
                lines.append(err.strip()[:200])
                lines.append(f"```")
            lines.append("")

    lines.append("---")
    lines.append(f"*Report generated by `verify.py` — SocrateAI Scientific Agora*")
    return "\n".join(lines)


def generate_json_audit(results: list[ModuleAudit]) -> dict:
    """Generate the machine-readable JSON audit."""
    return {
        "generated": datetime.datetime.now().isoformat(),
        "toolchain": "leanprover/lean4:v4.14.0",
        "mathlib": "v4.14.0",
        "summary": {
            "total": len(results),
            "verified": sum(1 for r in results if r.status == "verified"),
            "axiom_blocked": sum(1 for r in results if r.status == "axiom_blocked"),
            "earth_gapped": sum(1 for r in results if r.status == "earth_gapped"),
            "sorry_blocked": sum(1 for r in results if r.status == "sorry_blocked"),
            "build_failed": sum(1 for r in results if r.status == "build_failed"),
            "total_sorry": sum(r.sorry_count for r in results),
            "total_axiom": sum(r.axiom_count for r in results),
        },
        "modules": [
            {
                "module": r.module,
                "tier": r.tier,
                "status": r.status,
                "build_ok": r.build_ok,
                "sorry_count": r.sorry_count,
                "axiom_count": r.axiom_count,
                "axiom_names": r.axiom_names,
                "sorry_locations": r.sorry_locations,
                "build_time_ms": r.build_time_ms,
                "error_messages": r.error_messages,
            }
            for r in results
        ],
    }


# ─── Main ────────────────────────────────────────────────────────────

def main():
    filter_module = None
    if "--module" in sys.argv:
        idx = sys.argv.index("--module")
        if idx + 1 < len(sys.argv):
            filter_module = sys.argv[idx + 1]

    print("=" * 60)
    print("SocrateAI Agora — Lean 4 Comprehensive Verifier")
    print("=" * 60)
    print()

    results = run_full_audit(filter_module)

    # Ensure proof/ directory exists
    PROOF_DIR.mkdir(parents=True, exist_ok=True)

    # Write Markdown report
    md_report = generate_markdown_report(results)
    report_path = PROOF_DIR / "compilation_report.md"
    with open(report_path, "w") as f:
        f.write(md_report)
    print(f"\n📄 Report written to: {report_path}")

    # Write JSON audit
    json_audit = generate_json_audit(results)
    audit_path = PROOF_DIR / "audit.json"
    with open(audit_path, "w") as f:
        json.dump(json_audit, f, indent=2)
    print(f"📊 Audit written to: {audit_path}")

    # Print summary
    print()
    verified = sum(1 for r in results if r.status == "verified")
    total = len(results)
    print(f"Verification score: {verified}/{total} modules fully verified")
    for r in results:
        emoji = STATUS_EMOJI.get(r.status, "❓")
        print(f"  {emoji} {r.module}: {STATUS_LABEL.get(r.status, '?')}")


if __name__ == "__main__":
    main()
