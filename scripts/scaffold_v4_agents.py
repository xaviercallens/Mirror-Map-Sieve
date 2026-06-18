import os
import json

agents_to_scaffold = [
    {"name": "hilbert", "role": "THEORIST", "model": "gemini-2.5-pro", "desc": "Axiomatic Program Builder"},
    {"name": "einstein", "role": "THEORIST", "model": "gemini-2.5-pro", "desc": "Theory Unification"},
    {"name": "curie", "role": "EXPERIMENTER", "model": "gemini-2.5-pro", "desc": "Experimental validation (empty at the moment)"},
    {"name": "ramanujan", "role": "THEORIST", "model": "gemini-2.5-pro", "desc": "Intuitive number theory (empty at the moment)"},
    {"name": "noether", "role": "THEORIST", "model": "gemini-2.5-pro", "desc": "Symmetry and conservation (empty at the moment)"},
    {"name": "feynman", "role": "EXPLAINER", "model": "gemini-2.5-pro", "desc": "Quantum path integrals and pedagogy (empty at the moment)"},
    {"name": "pasteur", "role": "EXPERIMENTER", "model": "gemini-2.5-pro", "desc": "Biological heuristics (empty at the moment)"},
    {"name": "lovelace", "role": "COMPILER", "model": "gemini-2.5-pro", "desc": "Algorithmic translation (empty at the moment)"},
]

template_agent = """# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
\"\"\"{AgentTitle} Agent — {AgentDesc}.

Note: Scaffolded for v4.0 architecture. {EmptyNote}
\"\"\"

from typing import Any
import structlog
from agents.base import AbstractAgent, AgentConfig, AgentResult, AgentRole

logger = structlog.get_logger(__name__)

class {AgentClass}Agent(AbstractAgent):
    \"\"\"{AgentTitle}: {AgentDesc}.\"\"\"

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                name="{AgentName}",
                model="{AgentModel}",
                role=AgentRole.{AgentRoleEnum},
                budget_limit=10.0,
                project_budget=100.0,
            )
        super().__init__(config)
        self._log = logger.bind(agent="{AgentName}")

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        return {{}}

    async def act(self, plan: dict[str, Any]) -> dict[str, Any]:
        return {{"status": "not_implemented_yet"}}

    async def run(self, query: str, **kwargs: Any) -> AgentResult:
        self._guard_iterations()
        return AgentResult(answer=False, confidence=0.0)
"""

for agent in agents_to_scaffold:
    name = agent["name"]
    title = name.capitalize()
    
    os.makedirs(f"agents/{name}", exist_ok=True)
    
    with open(f"agents/{name}/__init__.py", "w") as f:
        f.write(f"from .agent import {title}Agent\n")
    
    empty_note = "empty at the moment" if "empty" in agent["desc"] else ""
    with open(f"agents/{name}/agent.py", "w") as f:
        f.write(template_agent.format(
            AgentTitle=title,
            AgentDesc=agent["desc"],
            EmptyNote=empty_note,
            AgentClass=title,
            AgentName=name,
            AgentModel=agent["model"],
            AgentRoleEnum=agent["role"]
        ))
        
    # A2A Card stub (usually /.well-known/agent.json, but keeping in agent folder as a template)
    card = {
        "name": name,
        "description": agent["desc"],
        "endpoints": {
            "rpc": f"https://{name}-service-xyz.a.run.app/rpc"
        },
        "model": agent["model"]
    }
    with open(f"agents/{name}/agent.json", "w") as f:
        json.dump(card, f, indent=2)

print("Scaffolded all v4 agents successfully.")
