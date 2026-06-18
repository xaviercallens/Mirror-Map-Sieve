# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Galois Agent ADK Server.

Serves the Galois agent as a standalone Cloud Run
service with an A2A Agent Card.
"""

from __future__ import annotations

import os
from fastapi import FastAPI
from pydantic import BaseModel

import structlog
from agents.common.a2a import AgentCard, A2AServerMixin

try:
    from google.adk import Agent as ADKAgent, AgentConfig
    from google.adk.tools import FunctionTool
    HAVE_ADK = True
except ImportError:
    HAVE_ADK = False

from agents.galois.tools.conjecture_generator import generate_conjectures as generate_conjecture
from agents.galois.tools.mcts_reasoner import run_mcts

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Server Definition
# ---------------------------------------------------------------------------

app = FastAPI(title="Galois Agent")

agent_card = AgentCard(
    name="Galois",
    description="Creative Mathematician. Generates conjectures via SymBrain MCTS.",
    url=os.getenv("AGENT_URL", "http://localhost:8080"),
    version="4.0.0",
    capabilities={"streaming": True},
    skills=[
        {"id": "generate_conjecture", "name": "Generate Conjecture", "description": "Generates a mathematical conjecture."},
        {"id": "run_mcts", "name": "Run MCTS", "description": "Runs Monte Carlo Tree Search for proof generation."}
    ]
)

# Mount A2A routes
a2a_server = A2AServerMixin(agent_card)
a2a_server.mount_a2a_routes(app)

if HAVE_ADK:
    galois_agent = ADKAgent(
        config=AgentConfig(
            name="Galois",
            description="Creative mathematician.",
            model=None, # Tool-only mode as per user request
        ),
        tools=[
            FunctionTool(generate_conjecture),
            FunctionTool(run_mcts),
        ],
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
