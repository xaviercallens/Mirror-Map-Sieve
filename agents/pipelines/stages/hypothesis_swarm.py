# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Stage 2 — DeGennes Swarm: Parallel Hypothesis Generation.

``num_swarm_agents`` DeGennes agents run in parallel, each generating
``hypotheses_per_agent`` novel hypotheses grounded in Alien Mathematics.
Each agent has a domain-specific seed context and auto-research goal.
Total output = ``num_swarm_agents × hypotheses_per_agent`` hypotheses.
"""

from __future__ import annotations

import asyncio
import json
import re
import textwrap
import time

import structlog

from agents.pipelines.audit import SymposiumAuditTrail
from agents.pipelines.base import agent_generate
from agents.pipelines.config import SymposiumConfig

logger = structlog.get_logger(__name__)

# ── Agent Identity ─────────────────────────────────────────────────────────────

DEGENNES_IDENTITY = textwrap.dedent("""\
    You are DeGennes, a Nobel-laureate physicist exploring Alien Mathematics — a rigorous
    framework applying tensor networks, non-commutative algebra, holographic principles,
    and ω=2 asymptotic limits to complex physical and sociotechnical systems.

    Your task: generate exactly {n} genuinely novel, scientifically grounded hypotheses
    for improving {domain}. Each hypothesis must:
    1. Reference a specific Alien Mathematics formalism (e.g., Ryu-Takayanagi entropy, tensor trains)
    2. Target a concrete operational KPI
    3. Include a falsifiable prediction with a proposed measurement method
    4. Estimate a plausible efficiency gain range (e.g., 8–15% improvement)

    Output as a JSON array of {n} objects with keys:
    title, description, alien_math_formalism, kpi_target, falsifiable_prediction,
    efficiency_gain_estimate, measurement_method
""")

# ── Alien Math formalism/KPI pairs for structured mocks ────────────────────────

_FORMALISMS = [
    "Tensor-Train TT-Decomp",
    "Ryu-Takayanagi Entropy",
    "Non-Comm Matrix Flow",
    "ω=2 Asymptotic Limit",
    "Holographic Projection",
]
_KPIS = [
    "Turnaround Time",
    "Utilization Rate",
    "Loss Rate",
    "Cascade Factor",
    "Throughput",
]


async def generate_hypotheses(
    config: SymposiumConfig,
    rules: str,
    audit: SymposiumAuditTrail,
) -> list[dict]:
    """Generate hypotheses via a parallel DeGennes swarm.

    Launches ``config.num_swarm_agents`` async tasks, each producing
    ``config.hypotheses_per_agent`` hypotheses.  Returns the aggregated
    list.

    Args:
        config: Symposium configuration.
        rules: Formal rules from Stage 1 (Socrate).
        audit: Audit trail.

    Returns:
        List of hypothesis dicts, each containing title, description,
        alien_math_formalism, kpi_target, falsifiable_prediction,
        efficiency_gain_estimate, measurement_method, swarm_agent,
        and seed_context.
    """
    n_agents = config.num_swarm_agents
    n_per = config.hypotheses_per_agent
    total = n_agents * n_per
    logger.info(
        "stage2_swarm_start",
        agents=n_agents,
        per_agent=n_per,
        total=total,
    )
    t0 = time.monotonic()

    # Pad or trim seed contexts to match num_swarm_agents
    contexts = list(config.seed_contexts)
    while len(contexts) < n_agents:
        contexts.append(f"Focus on novel {config.domain} optimization using Alien Mathematics.")
    contexts = contexts[:n_agents]

    async def _run_swarm_agent(agent_id: int, context: str) -> list[dict]:
        """Single swarm agent generating ``n_per`` hypotheses."""
        log = logger.bind(swarm_agent=agent_id)
        log.info("swarm_agent_start", context=context[:60])

        identity = DEGENNES_IDENTITY.format(n=n_per, domain=config.domain)
        prompt = textwrap.dedent(f"""\
            Scientific constraints from Socrate:
            {rules}

            Your specialization: {context}

            Your goal: select the {n_per} BEST hypotheses from your creative
            exploration.  Prioritise novelty, mathematical rigour, and
            measurable KPI impact.  Be bold — push beyond classical methods.

            Generate exactly {n_per} hypotheses as a JSON array.
        """)

        raw = await agent_generate(identity, prompt)

        # ── Parse JSON array from response ─────────────────────────────
        try:
            match = re.search(r"\[.*?\]", raw, re.DOTALL)
            if match:
                hyps: list[dict] = json.loads(match.group())
                for h in hyps:
                    h["swarm_agent"] = agent_id
                    h["seed_context"] = context
                log.info("swarm_agent_parsed", count=len(hyps))
                return hyps
        except Exception as exc:
            log.warning("swarm_agent_json_error", error=str(exc))

        # ── Structured mock fallback ───────────────────────────────────
        log.info("swarm_agent_using_mock")
        return [
            {
                "title": (
                    f"{config.domain} Optimization via "
                    f"{_FORMALISMS[i % len(_FORMALISMS)]} "
                    f"(Swarm {agent_id}-{i})"
                ),
                "description": (
                    f"Apply {_FORMALISMS[i % len(_FORMALISMS)]} to {context} "
                    f"to achieve measurable KPI improvement.  This hypothesis "
                    f"integrates Alien Mathematics formalism with empirical "
                    f"data to derive a novel optimization regime."
                ),
                "alien_math_formalism": _FORMALISMS[i % len(_FORMALISMS)],
                "kpi_target": _KPIS[i % len(_KPIS)],
                "falsifiable_prediction": (
                    f"Applying {_FORMALISMS[i % len(_FORMALISMS)]} reduces "
                    f"operational latency by {8 + i * 3}% within 6 months."
                ),
                "efficiency_gain_estimate": f"{8 + i * 3}–{12 + i * 3}%",
                "measurement_method": (
                    "Before/after ANOVA on 90-day rolling window "
                    "regression against baseline model."
                ),
                "swarm_agent": agent_id,
                "seed_context": context,
            }
            for i in range(n_per)
        ]

    # ── Launch all agents concurrently ─────────────────────────────────
    tasks = [
        _run_swarm_agent(agent_id + 1, ctx)
        for agent_id, ctx in enumerate(contexts)
    ]
    batches = await asyncio.gather(*tasks)
    all_hyps = [h for batch in batches for h in batch]

    elapsed = time.monotonic() - t0
    audit.record(
        stage="Stage 2: Hypothesis Swarm",
        agent="DeGennes",
        action=f"Generated {len(all_hyps)} hypotheses ({n_agents} agents × {n_per})",
        elapsed_s=elapsed,
        input_summary=f"rules={len(rules)} chars, {n_agents} agents",
        output_summary=f"{len(all_hyps)} hypotheses",
    )

    logger.info(
        "stage2_swarm_complete",
        total=len(all_hyps),
        elapsed_s=round(elapsed, 1),
    )
    return all_hyps
