#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Agora Symposium Runner — Cloud Run Job entry point.

Loads a pre-configured research template and executes the full 10-stage
Symposium pipeline.  Secrets are injected from GCP Secret Manager via
environment variables at deployment time.

Usage:
  SYMPOSIUM_TEMPLATE=cycloreactor_environment python3 agents/symposium_runner.py
  SYMPOSIUM_TEMPLATE=plasma_fusion_iter python3 agents/symposium_runner.py
  SYMPOSIUM_TEMPLATE=quantum_computing python3 agents/symposium_runner.py
  SYMPOSIUM_TEMPLATE=airline_revenue_mgmt python3 agents/symposium_runner.py
  SYMPOSIUM_TEMPLATE=airport_operations python3 agents/symposium_runner.py

Environment variables:
  SYMPOSIUM_TEMPLATE  — template name (default: 'cycloreactor_environment')
  GEMINI_API_KEY      — Google Gemini API key
  MISTRAL_API_KEY     — Mistral AI API key (for adversarial review)
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# ─── Path setup ──────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.pipelines.symposium import SymposiumPipeline, SymposiumConfig
from agents.pipelines.templates import load_template

# ─── Secrets / environment variables ─────────────────────────────────────────
# In Cloud Run these are injected from GCP Secret Manager via --set-secrets.
# Locally, fall back to .env file values.
# IMPORTANT: .strip() is critical — Secret Manager values often have trailing \n
# which breaks HTTP Authorization headers (especially Mistral).
GEMINI_API_KEY = (
    os.getenv("GEMINI_API_KEY")
    or os.getenv("GALOIS_GEMINI_KEY")
    or ""
).strip()

MISTRAL_API_KEY = (
    os.getenv("MISTRAL_API_KEY")
    or os.getenv("GALOIS_MISTRAL_KEY")
    or ""
).strip()

if GEMINI_API_KEY:
    os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
    os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    """Load template, run pipeline, print summary."""
    template_name = os.getenv("SYMPOSIUM_TEMPLATE", "cycloreactor_environment")

    print("=" * 80)
    print("🏛️   AGORA SYMPOSIUM RUNNER")
    print(f"    Template: {template_name}")
    print(f"    GEMINI_API_KEY : "
          f"{'✅ loaded' if GEMINI_API_KEY else '❌ missing — using mocks'}")
    print(f"    MISTRAL_API_KEY: "
          f"{'✅ loaded' if MISTRAL_API_KEY else '❌ missing — using structured mocks'}")
    print("=" * 80)

    # Load research configuration from template
    try:
        config: SymposiumConfig = load_template(template_name)
    except KeyError:
        print(f"\n❌ Unknown template: '{template_name}'")
        print("   Available templates:")
        from agents.pipelines.templates import TEMPLATE_REGISTRY
        for name in sorted(TEMPLATE_REGISTRY):
            print(f"     • {name}")
        sys.exit(1)

    # Execute the 10-stage Symposium pipeline
    pipeline = SymposiumPipeline()
    result = await pipeline.run(config)

    # Final status
    if result.success:
        print(f"\n✅ Symposium '{template_name}' completed successfully.")
        print(f"   Cost: ${result.total_cost_usd:.2f} | "
              f"Time: {result.duration_s:.0f}s")
        if result.monograph_path:
            print(f"   PDF: {result.monograph_path}")
        if result.gcs_uri:
            print(f"   GCS: {result.gcs_uri}")
    else:
        print(f"\n❌ Symposium '{template_name}' completed with errors.")
        for w in result.warnings:
            print(f"   ⚠️  {w}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
