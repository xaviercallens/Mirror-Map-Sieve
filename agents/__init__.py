# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""SocrateAI Scientific Agora — Multi-Agent Framework.

This package provides nine dialectically-interacting AI agents:
  • **Galileo**     — Scientific Experimenter (hypothesis testing, ODE solving, NIM)
  • **Euler**       — Mathematical Verifier (Lean 4 proofs, DeepProbLog, auditing)
  • **Socrates**    — Dialectical Orchestrator (elenchus/maieutic cycles)
  • **Galois**      — Creative Mathematician (SymBrain v4, conjectures, MCTS)
  • **Hypatie**     — Astronomical Librarian (Alexandrie cataloging, astrolabe)
  • **Turing**      — Computation Agent (benchmarks, hardware diagnostics)
  • **Bourbaki**    — Code-to-Lean Translator (AST parsing, StateT monads)
  • **Aristotle**   — Semantic Guillotine (decomposition validity filter)
  • **Descartes**   — Exploit Synthesizer (zero-day payload generation)
  • **Champollion** — Executive Decoder (certification reports)

Architecture follows the neuro-symbolic, frugal-AI paradigm with strict
budget guards ($100/experiment, $500/project) and serverless-first deployment
(``min_replicas=0``).

Patent: US-PAT-PEND-2026-0525
"""

from agents.base import AbstractAgent, AgentConfig, AgentResult
from agents.galileo.agent import GalileoAgent
from agents.euler.agent import EulerAgent
from agents.socrates.agent import SocratesAgent
from agents.galois.agent import GaloisAgent
from agents.hypatie.agent import HypatieAgent
from agents.turing.agent import TuringAgent
from agents.bourbaki.agent import BourbakiAgent
from agents.aristotle.agent import AristotleAgent
from agents.descartes.agent import DescartesAgent
from agents.champollion.agent import ChampollionAgent
from agents.common.budget_guard import BudgetGuard
from agents.common.telemetry import AgentTelemetry

__all__ = [
    "AbstractAgent",
    "AgentConfig",
    "AgentResult",
    "GalileoAgent",
    "EulerAgent",
    "SocratesAgent",
    "GaloisAgent",
    "HypatieAgent",
    "TuringAgent",
    "BourbakiAgent",
    "AristotleAgent",
    "DescartesAgent",
    "ChampollionAgent",
    "BudgetGuard",
    "AgentTelemetry",
]

__version__ = "0.2.0"
__author__ = "Xavier Callens <callensxavier@gmail.com>"
__license__ = "Apache-2.0"

