# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Abstract pipeline base for the Agora Symposium research pipeline.

Provides:
  - :class:`PipelineStage` — ordered enum of the 10-stage symposium pipeline.
  - :class:`PipelineResult` — structured output from a complete pipeline run.
  - :class:`AgentPipeline` — abstract base class for concrete pipeline implementations.
  - :func:`agent_generate` — thin wrapper around the ``google.antigravity`` Agent SDK
    with structured mock fallback when the SDK or API key is unavailable.

Architecture follows the neuro-symbolic, frugal-AI paradigm with strict
budget guards ($30/pipeline) and serverless-first deployment.

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

import structlog

from google.antigravity import Agent, LocalAgentConfig, types
from google.antigravity.types import (
    TemplatedSystemInstructions,
    GeminiConfig,
    ModelConfig,
    ModelEntry,
    GenerationConfig,
    ThinkingLevel,
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Pipeline Stages
# ---------------------------------------------------------------------------

class PipelineStage(IntEnum):
    """Ordered stages of the Agora Symposium pipeline.

    Each stage maps to a distinct agent or tool invocation in the
    research pipeline.  The integer value encodes execution order.
    """

    SOCRATE_RULES = 1
    HYPOTHESIS_GENERATION = 2
    ADVERSARIAL_REVIEW = 3
    LEAN4_FORMALIZATION = 4
    KERNEL_COMPILATION = 5
    NUMERICAL_SIMULATION = 6
    IMPACT_ASSESSMENT = 7
    MONOGRAPH_GENERATION = 8
    PEER_REVIEW_LOOP = 9
    PUBLICATION = 10


# ---------------------------------------------------------------------------
# Pipeline Result
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class PipelineResult:
    """Structured output from a complete Symposium pipeline run.

    Attributes:
        symposium_id: Unique identifier for this symposium execution.
        stages_completed: Ordered list of stages that finished successfully.
        total_duration_s: Wall-clock duration of the full pipeline in seconds.
        total_cost_usd: Cumulative LLM / compute cost in USD.
        pdf_path: Local path to the generated monograph PDF.
        tex_path: Local path to the generated monograph LaTeX source.
        vault_artifact_ids: Alexandrie Vault artifact IDs produced.
        audit_trail_path: Local path to the JSONL audit trail.
        hypotheses_count: Total number of hypotheses generated.
        top_k_scores: Scores of the top-K hypotheses selected.
        lean_verdicts: Per-hypothesis Lean 4 verification verdicts.
        warnings: Non-fatal issues encountered during the pipeline.
    """

    symposium_id: str
    stages_completed: list[Any] = field(default_factory=list)
    total_duration_s: float = 0.0
    total_cost_usd: float = 0.0
    pdf_path: str = ""
    tex_path: str = ""
    vault_artifact_ids: list[str] = field(default_factory=list)
    audit_trail_path: str = ""
    hypotheses_count: int = 0
    top_k_scores: list[float] = field(default_factory=list)
    lean_verdicts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "symposium_id": self.symposium_id,
            "stages_completed": [
                s.name if hasattr(s, 'name') else str(s)
                for s in self.stages_completed
            ],
            "total_duration_s": round(self.total_duration_s, 3),
            "total_cost_usd": round(self.total_cost_usd, 4),
            "pdf_path": self.pdf_path,
            "tex_path": self.tex_path,
            "vault_artifact_ids": self.vault_artifact_ids,
            "audit_trail_path": self.audit_trail_path,
            "hypotheses_count": self.hypotheses_count,
            "top_k_scores": [round(s, 4) for s in self.top_k_scores],
            "lean_verdicts": self.lean_verdicts,
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# Abstract Pipeline
# ---------------------------------------------------------------------------

class AgentPipeline(ABC):
    """Abstract base for Agora Symposium pipeline implementations.

    Concrete subclasses implement :meth:`run` to orchestrate the full
    10-stage research pipeline (or a subset thereof) and :meth:`get_stages`
    to declare which stages they support.
    """

    @abstractmethod
    async def run(self, config: Any) -> PipelineResult:
        """Execute the full pipeline for the given configuration.

        Args:
            config: A :class:`~agents.pipelines.config.SymposiumConfig`
                instance (or compatible dataclass) defining the symposium.

        Returns:
            Structured :class:`PipelineResult` with all outputs and metrics.
        """

    @abstractmethod
    def get_stages(self) -> list[PipelineStage]:
        """Return the ordered list of stages this pipeline implements.

        Returns:
            List of :class:`PipelineStage` values in execution order.
        """


# ---------------------------------------------------------------------------
# Agent Generation Helper
# ---------------------------------------------------------------------------


async def agent_generate(
    identity: str,
    prompt: str,
    model: str = "gemini-2.5-pro",
    thinking_level: ThinkingLevel = ThinkingLevel.HIGH,
    *,
    strict: bool = False,
) -> str:
    """Invoke an Agora agent via the ``google.antigravity`` SDK.

    Wraps :class:`Agent` instantiation, configuration, and
    :meth:`chat` into a single ergonomic helper.

    When *strict* is ``False`` (default, legacy behaviour), falls back
    to a ``[MOCK_FALLBACK: …]`` string on any error.  When *strict* is
    ``True`` (v4.4.0+), the exception propagates — callers must handle it.

    Args:
        identity: System instruction text defining the agent persona.
        prompt: The user/stage prompt to send to the model.
        model: Foundation model identifier (default ``"gemini-2.5-pro"``).
        thinking_level: Kept for API compatibility but not passed to SDK.
        strict: If True, raise on error instead of returning MOCK_FALLBACK.

    Returns:
        The model's text response, or a ``[MOCK_FALLBACK: …]`` string
         if the real call fails and *strict* is False.

    Raises:
        Exception: Re-raised from the SDK when *strict* is True.
    """
    log = logger.bind(agent_identity=identity[:40], model=model)

    # Prepend an explicit instruction to output raw text only.
    # This prevents the model from trying to use built-in tools
    # (e.g. write_to_file) which causes API 400 errors when
    # CapabilitiesConfig(enabled_tools=[]) is used.
    no_tools_prefix = (
        "CRITICAL: You must output your response as plain text directly. "
        "Do NOT use any tools, function calls, or file operations. "
        "Simply write your complete response as text output.\n\n"
    )
    augmented_identity = no_tools_prefix + identity

    try:
        if "mistral" in model.lower():
            # Mistral API does not support antigravity SDK
            mistral_key = os.environ.get("GALOIS_MISTRAL_KEY", "")
            if not mistral_key:
                raise ValueError("GALOIS_MISTRAL_KEY not set for Mistral API call")
            
            import httpx
            import json
            timeout = float(os.environ.get("MISTRAL_TIMEOUT", "60.0"))
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    "https://api.mistral.ai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {mistral_key}"},
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": augmented_identity},
                            {"role": "user", "content": prompt}
                        ]
                    }
                )
                resp.raise_for_status()
                data = resp.json()
                result_text = data["choices"][0]["message"]["content"]
        else:
            cfg = LocalAgentConfig(
                system_instructions=TemplatedSystemInstructions(
                    identity=augmented_identity
                ),
                model=model,
                # Do NOT set capabilities — empty enabled_tools=[] causes
                # API 400: "Function calling config is set without function_declarations"
            )
            t0 = time.monotonic()
            # SDK v0.1.3+: Agent must be used as async context manager
            async with Agent(config=cfg) as agent:
                response = await agent.chat(prompt)
                result_text = await response.text()
        elapsed_ms = (time.monotonic() - t0) * 1000
        log.info(
            "agent_generate_ok",
            elapsed_ms=round(elapsed_ms, 1),
            response_len=len(result_text),
        )
        return result_text

    except Exception as exc:
        error_msg = str(exc)[:120]
        log.warning("agent_generate_fallback", error=error_msg, strict=strict)
        if strict:
            raise
        return f"[MOCK_FALLBACK: {error_msg}]"


