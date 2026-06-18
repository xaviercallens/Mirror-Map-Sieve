#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Example: Running a budget-constrained scientific experiment.

Demonstrates the frugal-AI budget enforcement system:
  - $100 per experiment ceiling
  - $500 project total
  - min_replicas = 0 (serverless)
  - Cost estimation before execution
  - Budget guard preventing overspend

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.common.budget_guard import BudgetGuard, BudgetExceededError
from agents.galileo.tools.cost_estimator import estimate_cost
from agents.galileo.agent import GalileoAgent


async def run_budget_constrained() -> None:
    """Run experiments with budget constraints."""
    print("=" * 60)
    print("SocrateAI Agora — Budget-Constrained Experiment")
    print("Hard limits: $100/experiment, $500/project")
    print("=" * 60)

    # ---- Step 1: Cost estimation ----
    print("\n📊 Step 1: Cost Estimation")
    print("-" * 40)

    configs = [
        ("L4, 1 hour", "L4", 1.0, 1),
        ("L4, 10 hours", "L4", 10.0, 1),
        ("A100-80GB, 1 hour", "A100-80GB", 1.0, 1),
        ("A100-80GB, 30 hours", "A100-80GB", 30.0, 1),
        ("TPU-v5e, 5 hours", "TPU-v5e", 5.0, 1),
    ]

    for label, gpu, hours, replicas in configs:
        result = estimate_cost(gpu_type=gpu, hours=hours, replicas=replicas)
        status = "✅" if result["within_experiment_budget"] else "❌"
        print(
            f"  {status} {label:25s} → ${result['total_cost']:7.2f} "
            f"({'OK' if result['within_experiment_budget'] else 'OVER BUDGET'})"
        )

    # ---- Step 2: Budget guard ----
    print("\n🛡️  Step 2: Budget Guard Demo")
    print("-" * 40)

    guard = BudgetGuard(experiment_limit=100.0, project_limit=500.0)

    # Record some costs
    costs = [5.0, 15.0, 25.0, 30.0]
    for cost in costs:
        guard.record_cost(cost)
        summary = guard.summary()
        print(
            f"  Recorded ${cost:.2f} → "
            f"Experiment: ${summary['experiment_cost']:.2f}/"
            f"${summary['experiment_limit']:.2f} | "
            f"Project: ${summary['project_cost']:.2f}/"
            f"${summary['project_limit']:.2f}"
        )

    # Try to exceed budget
    print(f"\n  Attempting to spend $30.00 more...")
    try:
        guard.check_budget(30.0)
        print("  ✅ Budget check passed")
    except BudgetExceededError as exc:
        print(f"  ❌ Budget exceeded: {exc}")

    # Reset experiment
    print(f"\n  Resetting experiment budget...")
    guard.reset_experiment()
    summary = guard.summary()
    print(
        f"  Experiment: ${summary['experiment_cost']:.2f}/"
        f"${summary['experiment_limit']:.2f} (reset) | "
        f"Project: ${summary['project_cost']:.2f}/"
        f"${summary['project_limit']:.2f} (preserved)"
    )

    # ---- Step 3: Serverless assertion ----
    print("\n☁️  Step 3: Serverless Policy")
    print("-" * 40)

    for replicas in [0, 1, 3]:
        try:
            BudgetGuard.assert_serverless(replicas)
            print(f"  ✅ min_replicas={replicas}: OK")
        except Exception as exc:
            print(f"  ❌ min_replicas={replicas}: {exc}")

    # ---- Step 4: Run agent under budget ----
    print("\n🔬 Step 4: Agent Execution Under Budget")
    print("-" * 40)

    agent = GalileoAgent()
    result = await agent.run("Solve the Lotka-Volterra predator-prey system")

    print(f"  Confidence: {result.confidence}")
    print(f"  Cost:       ${result.cost_usd:.2f}")
    print(f"  Budget remaining:")
    summary = agent.budget_guard.summary()
    print(f"    Experiment: ${summary['experiment_remaining']:.2f}")
    print(f"    Project:    ${summary['project_remaining']:.2f}")

    print("\n" + "=" * 60)
    print("Done. Total project spend: "
          f"${agent.budget_guard.cumulative_cost:.2f}")


def main() -> None:
    """Entry point."""
    asyncio.run(run_budget_constrained())


if __name__ == "__main__":
    main()
