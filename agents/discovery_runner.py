#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Agora Discovery Runner — Cloud Run Job entry point.

Loads a pre-configured discovery template and executes the 6-stage
Discovery Pipeline.  Secrets are injected from GCP Secret Manager via
environment variables at deployment time.

Usage (local):
  DISCOVERY_TEMPLATE=h1_strassen_witness python3 agents/discovery_runner.py
  DISCOVERY_TEMPLATE=h1_strassen_witness DRY_RUN=true python3 agents/discovery_runner.py

Usage (Cloud Run Job):
  Triggered automatically via gcloud run jobs execute discovery-pipeline
  with --set-env-vars DISCOVERY_TEMPLATE=h1_strassen_witness

Environment variables:
  DISCOVERY_TEMPLATE  — template name (default: 'h1_strassen_witness')
  GEMINI_API_KEY      — Google Gemini API key (from Secret Manager in Cloud Run)
  DRY_RUN             — if 'true', runs with mocks only (for CI validation)
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# ─── Path setup ──────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.pipelines.discovery import DiscoveryPipeline, DiscoveryConfig
from agents.pipelines.templates.discovery import load_discovery_template, DISCOVERY_TEMPLATE_REGISTRY

# ─── Secrets / environment variables ─────────────────────────────────────────
# In Cloud Run these are injected from GCP Secret Manager via --set-secrets.
# Locally, fall back to .env file values.
# IMPORTANT: .strip() is critical — Secret Manager values often have trailing \n
# which breaks HTTP Authorization headers.
GEMINI_API_KEY = (
    os.getenv("GEMINI_API_KEY")
    or os.getenv("GALOIS_GEMINI_KEY")
    or ""
).strip()

DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

if GEMINI_API_KEY:
    os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
    os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    """Load discovery template, run pipeline, print summary."""
    template_name = os.getenv("DISCOVERY_TEMPLATE", "h1_strassen_witness")

    print("=" * 80)
    print("🔬  AGORA DISCOVERY RUNNER")
    print(f"    Template : {template_name}")
    print(f"    Dry Run  : {DRY_RUN}")
    print(f"    GEMINI_API_KEY : "
          f"{'✅ loaded' if GEMINI_API_KEY else '❌ missing — using mocks'}")
    print("=" * 80)

    # ── Load discovery configuration from template ────────────────────────────
    try:
        config: DiscoveryConfig = load_discovery_template(template_name)
    except KeyError:
        print(f"\n❌ Unknown template: '{template_name}'")
        print("   Available templates:")
        for name in sorted(DISCOVERY_TEMPLATE_REGISTRY):
            print(f"     • {name}")
        sys.exit(1)

    # ── Dry-run override: limit scale for validation ──────────────────────────
    if DRY_RUN:
        print("\n⚡ DRY RUN mode — reducing scale for fast validation:")
        config = DiscoveryConfig(
            target_domain=config.target_domain,
            discovery_id=config.discovery_id,
            num_conjectures=2,                 # Minimal conjecture count
            num_degennes_agents=1,             # Single agent (fast)
            enable_leanbert=False,             # Skip LeanBert (no model loaded)
            enable_deepseek=False,             # Skip DeepSeek (no GPU)
            model=config.model,
            max_budget_usd=5.0,                # Hard $5 cap for validation
            alexandrie_bucket=config.alexandrie_bucket,
            require_human_approval=False,      # Non-interactive for CI
            output_dir=config.output_dir,
        )
        print(f"   Conjectures : {config.num_conjectures}")
        print(f"   Budget cap  : ${config.max_budget_usd}")

    # ── Create output directory ───────────────────────────────────────────────
    config.output_dir.mkdir(parents=True, exist_ok=True)

    # ── Run the Discovery Pipeline ────────────────────────────────────────────
    pipeline = DiscoveryPipeline(config)

    print(f"\n🚀 Starting Discovery Pipeline — {template_name}")
    print(f"   Domain   : {config.target_domain}")
    print(f"   Budget   : ${config.max_budget_usd:.2f}")
    print(f"   LeanBert : {'enabled' if config.enable_leanbert else 'disabled'}")
    print(f"   DeepSeek : {'enabled' if config.enable_deepseek else 'disabled'}")
    print()

    result = await pipeline.run(config)

    # ── Print summary ─────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("🏆  DISCOVERY PIPELINE COMPLETE")
    print("=" * 80)
    print(f"  Stages completed     : {len(result.stages_completed)}/6")
    print(f"  Total time           : {result.total_duration_s:.1f}s")
    print(f"  Total cost           : ${result.total_cost_usd:.4f}")
    print(f"  Conjectures generated: {result.conjectures_generated}")
    print(f"  Conjectures formal.  : {result.conjectures_formalized}")
    print(f"  Proofs completed     : {result.proofs_completed} (sorry-free)")
    print(f"  Proofs with sorry    : {result.proofs_with_sorry}")
    print(f"  Kernel verified      : {result.kernel_verified}")
    print(f"  LaTeX index          : {result.latex_index_path or '(none)'}")
    print(f"  Open artifacts       : {len(result.vault_open_artifacts)}")
    print(f"  Private artifacts    : {len(result.vault_private_artifacts)}")
    if result.warnings:
        print(f"\n  ⚠️  Warnings ({len(result.warnings)}):")
        for w in result.warnings:
            print(f"     • {w}")
    print("=" * 80)

    # ── Exit code reflects whether at least 1 proof passed kernel ────────────
    if result.kernel_verified == 0 and not DRY_RUN:
        print("\n❌  No proofs passed kernel verification.")
        sys.exit(1)
    else:
        print("\n✅  Discovery run complete.")


if __name__ == "__main__":
    asyncio.run(main())
