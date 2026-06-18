# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""CLI entry point for the Bellman OR Pipeline.

Usage:
    python -m agents.or_pipeline_runner --template vehicle_routing
    python -m agents.or_pipeline_runner --template airline_revenue_or
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import sys
from pathlib import Path

import structlog

from agents.pipelines.or_pipeline import ORPipeline, ORPipelineConfig

logger = structlog.get_logger(__name__)


TEMPLATE_MAP = {
    "vehicle_routing": "agents.pipelines.templates.vehicle_routing",
    "airline_revenue_or": "agents.pipelines.templates.airline_revenue_or",
}
"""Map of template names to their importable module paths."""


async def run_or_pipeline(template_name: str) -> None:
    """Load a template config and execute the Bellman OR pipeline.

    Args:
        template_name: Key into TEMPLATE_MAP identifying which
            template configuration to use.
    """
    if template_name not in TEMPLATE_MAP:
        print(f"Unknown template: {template_name}")
        print(f"Available: {', '.join(TEMPLATE_MAP)}")
        sys.exit(1)

    # Dynamically import the template module and build config
    mod = importlib.import_module(TEMPLATE_MAP[template_name])
    config: ORPipelineConfig = mod.build_config()

    print(f"\n🔬 Bellman OR Pipeline — template: {template_name}")
    print(f"   Domain   : {config.problem_domain}")
    print(f"   Question : {config.research_question[:60]}...")
    print(f"   Class    : {config.problem_class}")
    print(f"   Suite    : {config.benchmark_suite}")
    print()

    pipeline = ORPipeline()
    result = await pipeline.run(config)

    # Write result to JSON
    out_path = config.output_dir / f"{config.pipeline_id}_result.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result.to_dict(), f, indent=2, default=str)

    print(f"\n📄 Result written to: {out_path}")


def main() -> None:
    """Parse CLI arguments and run the pipeline."""
    parser = argparse.ArgumentParser(
        description="Bellman OR Pipeline — Operations Research agent swarm",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--template", "-t",
        required=True,
        choices=list(TEMPLATE_MAP),
        help="Template config to use",
    )
    args = parser.parse_args()
    asyncio.run(run_or_pipeline(args.template))


if __name__ == "__main__":
    main()
