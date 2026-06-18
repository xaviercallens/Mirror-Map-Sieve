#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Bourbaki Translation Layer — End-to-End ERC-20 Demo.

Demonstrates the full pipeline:
  1. Bourbaki parses a Solidity ERC-20 contract
  2. Generates a Lean 4 file with sorry-gapped theorems
  3. Champollion generates a preliminary assessment report
  4. (Optional) Runs the vulnerable variant to show exploit detection

Usage:
    python scripts/bourbaki_demo.py                  # Secure ERC-20
    python scripts/bourbaki_demo.py --vuln            # Vulnerable ERC-20
    python scripts/bourbaki_demo.py --output out.lean # Write Lean output to file

Reference: 🏛️ SPECIFICATION: The Bourbaki Translation Layer v21 — Phase 2.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.bourbaki.parsers.solidity_parser import SolidityParser
from agents.bourbaki.codegen.type_mapper import TypeMapper
from agents.bourbaki.codegen.lean_codegen import LeanCodeGenerator
from agents.bourbaki.agent import BourbakiIR
from agents.champollion.agent import ChampollionAgent


# ---------------------------------------------------------------------------
# ANSI Colors for terminal output
# ---------------------------------------------------------------------------

class C:
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def banner():
    print(f"""
{C.CYAN}╔══════════════════════════════════════════════════════════════╗
║  🏛️  BOURBAKI TRANSLATION LAYER — ERC-20 FORMAL VERIFICATION  ║
║     SocrateAI Agora Sentinel v21 — Demo Pipeline               ║
╚══════════════════════════════════════════════════════════════╝{C.RESET}
""")


def step(n: int, msg: str):
    print(f"\n{C.BOLD}{C.GREEN}[Stage {n}]{C.RESET} {msg}")


def run_demo(sol_path: str, output_path: str | None, verbose: bool):
    banner()

    # --- Load Solidity source ---
    print(f"{C.DIM}Loading: {sol_path}{C.RESET}")
    with open(sol_path, "r") as f:
        source_code = f.read()

    contract_name = "SimpleERC20"
    if "VulnerableERC20" in source_code:
        contract_name = "VulnerableERC20"

    line_count = source_code.count("\n")
    print(f"  Source: {line_count} lines of Solidity")

    # =========================================================================
    # STAGE 1: AST Parsing
    # =========================================================================
    step(1, "AST Parsing — Extracting function signatures and state variables")
    t0 = time.perf_counter()

    parser = SolidityParser()
    state_vars = parser.detect_state_variables(source_code)
    functions = parser.parse(source_code)

    elapsed1 = (time.perf_counter() - t0) * 1000
    print(f"  {C.CYAN}State variables:{C.RESET}")
    for name, stype in state_vars.items():
        print(f"    • {name} : {stype}")
    print(f"  {C.CYAN}Functions extracted:{C.RESET} {len(functions)}")
    for func in functions:
        vis = func.visibility
        payable = " 💰" if func.is_payable else ""
        precond = f" [guards: {len(func.preconditions)}]" if func.preconditions else ""
        writes = f" → writes: {list(func.state_writes.keys())}" if func.state_writes else ""
        print(f"    • {func.name}({', '.join(func.params.keys())}) {vis}{payable}{precond}{writes}")
    print(f"  ⏱  {elapsed1:.1f}ms")

    # =========================================================================
    # STAGE 2: Transition Mapping — IR Generation
    # =========================================================================
    step(2, "Transition Mapping — Building StateT monad intermediate representation")
    t0 = time.perf_counter()

    mapper = TypeMapper()
    ir_state_fields: dict[str, str] = {}
    for func in functions:
        for var_name, var_type in func.state_reads.items():
            ir_state_fields[var_name] = mapper.map_type(var_type, "solidity")
        for var_name, var_type in func.state_writes.items():
            ir_state_fields[var_name] = mapper.map_type(var_type, "solidity")

    ir = BourbakiIR(
        source_language="solidity",
        contract_name=contract_name,
        state_fields=ir_state_fields,
        functions=functions,
        raw_source=source_code,
    )

    elapsed2 = (time.perf_counter() - t0) * 1000
    print(f"  {C.CYAN}Lean 4 state fields:{C.RESET}")
    for name, ltype in ir.state_fields.items():
        print(f"    • {name} : {ltype}")
    print(f"  ⏱  {elapsed2:.1f}ms")

    # =========================================================================
    # STAGE 3: Lean 4 Code Generation
    # =========================================================================
    step(3, "Invariant Generation — Producing Lean 4 with sorry-gapped theorems")
    t0 = time.perf_counter()

    codegen = LeanCodeGenerator(mapper)
    lean_code, theorems, diagnostics = codegen.generate(ir)

    elapsed3 = (time.perf_counter() - t0) * 1000
    lean_lines = lean_code.count("\n")
    print(f"  {C.CYAN}Lean 4 output:{C.RESET} {lean_lines} lines")
    print(f"  {C.CYAN}Theorems (sorry gaps for Galois):{C.RESET}")
    for t in theorems:
        print(f"    • {C.YELLOW}{t}{C.RESET} — sorry")

    if diagnostics:
        print(f"  {C.RED}Diagnostics:{C.RESET}")
        for d in diagnostics:
            print(f"    ⚠  {d}")
    print(f"  ⏱  {elapsed3:.1f}ms")

    # --- Print or save the generated Lean 4 code ---
    if verbose:
        print(f"\n{C.DIM}{'─' * 60}{C.RESET}")
        print(f"{C.BOLD}Generated Lean 4 Code:{C.RESET}")
        print(f"{C.DIM}{'─' * 60}{C.RESET}")
        for i, line in enumerate(lean_code.split("\n"), 1):
            print(f"  {C.DIM}{i:3d}{C.RESET}  {line}")
        print(f"{C.DIM}{'─' * 60}{C.RESET}")

    if output_path:
        with open(output_path, "w") as f:
            f.write(lean_code)
        print(f"\n  {C.GREEN}✅ Lean 4 file written to: {output_path}{C.RESET}")

    # =========================================================================
    # STAGE 4: Champollion Assessment
    # =========================================================================
    step(4, "Champollion — Generating preliminary assessment report")
    t0 = time.perf_counter()

    champollion = ChampollionAgent()

    if "Vulnerable" in contract_name:
        # Generate advisory for the vulnerable contract
        report = champollion.generate_advisory(
            contract_name=contract_name,
            vulnerability_type="potential_solvency_violation",
            severity="HIGH",
            exploit_description=(
                f"The Bourbaki analysis identified {len(functions)} state-mutating "
                f"functions with {sum(len(f.preconditions) for f in functions)} "
                f"guard conditions. Missing guards detected on: "
                f"{', '.join(f.name for f in functions if not f.preconditions)}"
            ),
            exploit_payload="# Awaiting Galois MCTS proof failure + Descartes synthesis",
            affected_function=", ".join(
                f.name for f in functions if f.state_writes
            ),
            remediation="Add require(to != address(0)) and SafeMath overflow checks.",
            cwe_id="CWE-190",
            lean_contradiction="-- Awaiting Galois MCTS output",
        )
        print(f"  {C.RED}⚠  PRELIMINARY ADVISORY generated (proof pending){C.RESET}")
    else:
        # Generate preliminary certificate (pending proof)
        report = champollion.generate_certificate(
            contract_name=contract_name,
            theorems_proven=[f"{t} (PENDING — sorry gap)" for t in theorems],
            proof_summary=(
                f"Bourbaki translated {line_count} lines of Solidity into "
                f"{lean_lines} lines of Lean 4 with {len(theorems)} sorry-gapped "
                f"theorems. Awaiting Galois MCTS autonomous proof search."
            ),
        )
        print(f"  {C.GREEN}📜 PRELIMINARY CERTIFICATE generated (proof pending){C.RESET}")

    elapsed4 = (time.perf_counter() - t0) * 1000
    print(f"  ⏱  {elapsed4:.1f}ms")

    # =========================================================================
    # Summary
    # =========================================================================
    total_ms = elapsed1 + elapsed2 + elapsed3 + elapsed4
    print(f"""
{C.CYAN}╔══════════════════════════════════════════════════════════════╗
║  PIPELINE SUMMARY                                            ║
╠══════════════════════════════════════════════════════════════╣
║  Contract:      {contract_name:<43}║
║  Solidity:      {line_count:<3} lines                                      ║
║  Lean 4:        {lean_lines:<3} lines                                      ║
║  Theorems:      {len(theorems):<3} sorry gaps for Galois MCTS               ║
║  Total time:    {total_ms:.1f}ms                                       ║
║                                                              ║
║  NEXT: Feed .lean file into Galois MCTS for autonomous proof ║
╚══════════════════════════════════════════════════════════════╝{C.RESET}
""")

    return lean_code, theorems, report


def main():
    parser = argparse.ArgumentParser(
        description="Bourbaki ERC-20 Formal Verification Demo"
    )
    parser.add_argument(
        "--vuln", action="store_true",
        help="Use the intentionally vulnerable ERC-20 contract"
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Path to write the generated Lean 4 file"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print the full generated Lean 4 code"
    )
    parser.add_argument(
        "--source", "-s", type=str, default=None,
        help="Path to a custom Solidity source file"
    )
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if args.source:
        sol_path = args.source
    elif args.vuln:
        sol_path = os.path.join(project_root, "examples", "erc20_vuln.sol")
    else:
        sol_path = os.path.join(project_root, "examples", "erc20_token.sol")

    if not os.path.exists(sol_path):
        print(f"{C.RED}ERROR: Solidity file not found: {sol_path}{C.RESET}")
        sys.exit(1)

    run_demo(sol_path, args.output, args.verbose)


if __name__ == "__main__":
    main()
