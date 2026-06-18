#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Example: Galileo ↔ Euler dialectic reasoning cycle.

Demonstrates the Socratic method applied to scientific claims:
  1. Galileo produces experimental evidence
  2. Euler challenges with formal verification
  3. Socrates orchestrates and synthesises

This example runs a full dialectic cycle on the question:
"Does the Robertson ODE system conserve mass?"

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.socrates.agent import SocratesAgent


async def run_dialectic() -> None:
    """Run a dialectic debate between Galileo and Euler."""
    print("=" * 60)
    print("SocrateAI Agora — Dialectic Reasoning Example")
    print("Socrates orchestrates Galileo ↔ Euler debate")
    print("=" * 60)

    # Create the Socrates orchestrator (which contains Galileo and Euler)
    socrates = SocratesAgent()

    # Pose a scientific question that requires both experiment and proof
    question = (
        "Verify that the Robertson chemical kinetics ODE system "
        "conserves total mass (y₁ + y₂ + y₃ = constant) and that "
        "the numerical solver maintains this invariant to machine precision."
    )

    print(f"\n📜 Question: {question}")
    print("\n▶ Running Socratic dialectic...\n")

    result = await socrates.run(question)

    # Display results
    print("=" * 60)
    print("DIALECTIC RESULTS")
    print("=" * 60)

    answer = result.answer
    if isinstance(answer, dict):
        complexity = answer.get("complexity", "unknown")
        print(f"\n  Complexity: {complexity}")

        synthesis = answer.get("synthesis", "")
        print(f"  Synthesis:  {synthesis}")

        observations = answer.get("observations", {})
        if "dialectic" in observations:
            d = observations["dialectic"]
            print(f"\n  Dialectic Status:  {d.get('status', 'N/A')}")
            print(f"  Cycles Completed:  {d.get('cycles', 'N/A')}")
            print(f"  Converged:         {d.get('converged', 'N/A')}")
            print(f"  Final Confidence:  {d.get('final_confidence', 'N/A')}")

        for key in ("galileo", "euler"):
            if key in observations:
                agent_obs = observations[key]
                print(f"\n  {key.capitalize()}:")
                print(f"    Confidence: {agent_obs.get('confidence', 'N/A')}")
                print(f"    Cost:       ${agent_obs.get('cost_usd', 0):.2f}")

    print(f"\n  Overall Confidence: {result.confidence}")
    print(f"  Total Cost:         ${result.cost_usd:.2f}")

    if result.proofs:
        print(f"\n  Formal Proofs:")
        for proof in result.proofs:
            print(f"    ✓ {proof}")

    print(f"\n  Telemetry:")
    for key, value in result.telemetry.items():
        if key != "latencies_ms":
            print(f"    {key}: {value}")

    print("\n" + "=" * 60)
    print("Done.")


def main() -> None:
    """Entry point."""
    asyncio.run(run_dialectic())


if __name__ == "__main__":
    main()
