# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Socrates Agent ADK Server.

Serves the Socrates Dialectical Orchestrator as a standalone Cloud Run
service with an A2A Agent Card. Routes mathematical problems by
solvability class using the real SocratesAgent classification logic.
"""

from __future__ import annotations

import os
from fastapi import FastAPI

import structlog
from agents.common.a2a import AgentCard, A2AServerMixin

try:
    from google.adk import Agent as ADKAgent, AgentConfig
    from google.adk.tools import FunctionTool
    HAVE_ADK = True
except ImportError:
    HAVE_ADK = False

from agents.socrates.agent import SolvabilityClass, ComplexityLevel

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Real skill implementations (wired to SocratesAgent logic)
# ---------------------------------------------------------------------------

def classify_solvability(problem: str) -> str:
    """Classifies a mathematical problem's solvability class.

    Routes to the real SolvabilityClass.classify() — no hard-coded stubs.

    Args:
        problem: Mathematical problem description.

    Returns:
        Solvability class string: 'class_1', 'class_2', or 'class_3'.
    """
    return SolvabilityClass.classify(problem)


def classify_complexity(query: str) -> str:
    """Classifies query complexity for dialectic routing.

    Routes to the real ComplexityLevel.classify() — no hard-coded stubs.

    Args:
        query: User query or mathematical problem description.

    Returns:
        Complexity level: 'simple', 'moderate', 'complex', or 'research'.
    """
    return ComplexityLevel.classify(query)


# ---------------------------------------------------------------------------
# Server Definition
# ---------------------------------------------------------------------------

app = FastAPI(title="Socrates Agent")

agent_card = AgentCard(
    name="Socrates",
    description=(
        "Dialectical orchestrator. Routes mathematical problems by solvability class "
        "using PFC-inspired heuristics and manages the Galois ↔ Euler Elenchus loop."
    ),
    url=os.getenv("AGENT_URL", "http://localhost:8080"),
    version="4.0.0",
    capabilities={"streaming": True, "pushNotifications": True},
    skills=[
        {
            "id": "classify_solvability",
            "name": "Problem Solvability Classification",
            "description": "Classifies a mathematical problem into Class 1/2/3 for compute routing.",
        },
        {
            "id": "classify_complexity",
            "name": "Query Complexity Classification",
            "description": "Classifies query complexity for dialectic routing decisions.",
        },
        {
            "id": "socrates_taste_sieve",
            "name": "Socrates Taste Sieve",
            "description": "Applies Socratic elenchus, structural constraints, and the OEIS live novelty sieve to filter out trivial conjectures and ensure high mathematical taste.",
        },
    ],
)

# Mount A2A routes
a2a_server = A2AServerMixin(agent_card)
a2a_server.mount_a2a_routes(app)


async def _socrates_executor(prompt: str, context: dict) -> dict:
    """A2A executor — dispatches to the real SocratesAgent.run()."""
    from agents.socrates.agent import SocratesAgent
    agent = SocratesAgent()
    result = await agent.run(prompt, **context)
    return {"answer": str(result.answer), "cost_usd": result.cost_usd}


a2a_server.register_executor(_socrates_executor)

if HAVE_ADK:
    socrates_agent = ADKAgent(
        config=AgentConfig(
            name="Socrates",
            description="Dialectical orchestrator for mathematical problem routing.",
            model=None,  # Tool-only mode: deterministic classification, no LLM needed
        ),
        tools=[
            FunctionTool(classify_solvability),
            FunctionTool(classify_complexity),
        ],
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
