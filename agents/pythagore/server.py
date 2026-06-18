# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Pythagore Agent ADK Server.

Serves the Pythagore agent as a standalone Cloud Run
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

from agents.pythagore.tools.generate_research_hypotheses import generate_research_hypotheses
from agents.pythagore.tools.extract_lean_states import extract_lean_states

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Server Definition
# ---------------------------------------------------------------------------

app = FastAPI(title="Pythagore Agent")

agent_card = AgentCard(
    name="Pythagore",
    description="Astronomical Librarian. RAG search, dataset ingestion, and Lean state extraction.",
    url=os.getenv("AGENT_URL", "http://localhost:8080"),
    version="4.0.0",
    capabilities={"streaming": True},
    skills=[
        {"id": "generate_research_hypotheses", "name": "Generate Research Hypotheses", "description": "Fetches and streams research hypotheses from datasets."},
        {"id": "extract_lean_states", "name": "Extract Lean States", "description": "Extracts Lean Dojo state_before and tactic traces."}
    ]
)

# Mount A2A routes
a2a_server = A2AServerMixin(agent_card)
a2a_server.mount_a2a_routes(app)

if HAVE_ADK:
    pythagore_agent = ADKAgent(
        config=AgentConfig(
            name="Pythagore",
            description="Librarian and researcher.",
            model=None, # Tool-only mode as per user request
        ),
        tools=[
            FunctionTool(generate_research_hypotheses),
            FunctionTool(extract_lean_states),
        ],
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
