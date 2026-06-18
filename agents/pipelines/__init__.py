# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Agora Symposium Pipeline — reusable orchestration infrastructure.

Public API
----------
.. autoclass:: SymposiumPipeline
.. autoclass:: SymposiumConfig
.. autoclass:: PipelineStage
.. autoclass:: PipelineResult
.. autoclass:: SymposiumAuditTrail

Patent: US-PAT-PEND-2026-0525
"""

from agents.pipelines.base import (
    AgentPipeline as SymposiumPipeline,
    PipelineStage,
    PipelineResult,
    agent_generate,
)
from agents.pipelines.config import SymposiumConfig
from agents.pipelines.audit import SymposiumAuditTrail

__all__ = [
    "SymposiumPipeline",
    "SymposiumConfig",
    "PipelineStage",
    "PipelineResult",
    "SymposiumAuditTrail",
]
