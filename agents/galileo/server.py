# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Galileo Agent ADK Server.

Serves the Galileo agent as a standalone Cloud Run
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
    HAVE_ADK = True
except ImportError:
    HAVE_ADK = False

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Server Definition
# ---------------------------------------------------------------------------

app = FastAPI(title="Galileo Agent")

agent_card = AgentCard(
    name="Galileo",
    description="Galileo agent.",
    url=os.getenv("AGENT_URL", "http://localhost:8080"),
    version="4.0.0",
    capabilities={"streaming": True},
    skills=[]
)

# Mount A2A routes
a2a_server = A2AServerMixin(agent_card)
a2a_server.mount_a2a_routes(app)

if HAVE_ADK:
    galileo_agent = ADKAgent(
        config=AgentConfig(
            name="Galileo",
            description="Galileo agent.",
            model=None, # Tool-only mode as per user request
        ),
        tools=[],
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
