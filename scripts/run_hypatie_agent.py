# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Hypatie Agent CLI Runner.

Reads JSON payload from stdin, executes HypatieAgent, and outputs the JSON result to stdout.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from agents.hypatie.agent import HypatieAgent


def main() -> None:
    try:
        # Read JSON from stdin
        input_data = sys.stdin.read()
        if not input_data.strip():
            print(json.dumps({"error": "Empty input"}))
            sys.exit(1)

        payload = json.loads(input_data)
        query = payload.get("query")
        if not query:
            print(json.dumps({"error": "Missing 'query' field in JSON payload"}))
            sys.exit(1)

        # Extract extra keyword arguments
        kwargs: dict[str, Any] = {}
        for key, val in payload.items():
            if key != "query":
                kwargs[key] = val

        # Run HypatieAgent
        agent = HypatieAgent()
        
        # We need to run the async agent loop in a synchronous context
        import asyncio
        result = asyncio.run(agent.run(query, **kwargs))

        # Format and output the result
        output = {
            "success": True,
            "answer": result.answer,
            "confidence": result.confidence,
            "cost_usd": result.cost_usd,
            "telemetry": result.telemetry,
        }
        print(json.dumps(output, indent=2))

    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
