# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Euler Agent ADK Server.

Serves the Euler agent as a standalone Cloud Run
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

from agents.euler.tools.predict_lean_accuracy import predict_lean_accuracy
from agents.euler.tools.leanabell_prover import leanabell_prove_theorem

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Server Definition
# ---------------------------------------------------------------------------

app = FastAPI(title="Euler Agent")

agent_card = AgentCard(
    name="Euler",
    description="Mathematical verifier. Lean 4 formal proofs, DeepProbLog probabilistic logic, DeepSeek-Prover RL scoring.",
    url=os.getenv("AGENT_URL", "http://localhost:8080"),
    version="4.0.0",
    capabilities={"streaming": True},
    skills=[
        {"id": "lean4_verify", "name": "Lean 4 Formal Verification", "description": "Compiles and verifies Lean 4 theorem proofs against Mathlib."},
        {"id": "predict_lean_accuracy", "name": "ML Tactic Accuracy Prediction", "description": "Uses DeepSeek-Prover-V1.5-RL to predict tactic success probability."}
    ]
)

# Mount A2A routes
a2a_server = A2AServerMixin(agent_card)
a2a_server.mount_a2a_routes(app)

if HAVE_ADK:
    euler_agent = ADKAgent(
        config=AgentConfig(
            name="Euler",
            description="Mathematical verifier for formal proofs and probabilistic logic.",
            model=None, # Tool-only mode as per user request
        ),
        tools=[
            FunctionTool(predict_lean_accuracy),
            FunctionTool(leanabell_prove_theorem),
        ],
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
