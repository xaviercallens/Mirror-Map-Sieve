# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Cross-Region Inference Sharding Router (H3 — SymBrain v16).

Implements the Cross-Region Inference Sharding strategy to bypass A100/H100
quota limits. Instead of blocking on a single over-subscribed region, this
router maintains a pool of regional Spot GPU endpoints and routes inference
requests to whichever region responds first.

Architecture:
    - Primary pool: L4 Spot instances across 4 regions (cheapest).
    - Secondary pool: A10G Spot instances (fallback when dopamine < 0.6).
    - Tertiary: A100 Serverless endpoint (last resort, always available).

The router integrates with the DopamineRegulatedThreshold from cortex_v16.py
to select the starting pool tier automatically.

All endpoints are Cloud Run / Vertex AI Prediction-compatible; the router
sends a standard JSON payload and returns the first successful response.

Patent: US-PAT-PEND-2026-0525
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Regional Endpoint Registry
# ---------------------------------------------------------------------------

# Endpoint URL pattern:  https://<region>-<project>.run.app
# In production, these are Cloud Run services (agora-galois-inference).
# In local/test mode, they resolve to mocked or localhost endpoints.

_ENDPOINT_TEMPLATES = {
    "L4_SPOT": [
        "https://us-central1-agora-galois.run.app",
        "https://us-east4-agora-galois.run.app",
        "https://europe-west4-agora-galois.run.app",
        "https://asia-southeast1-agora-galois.run.app",
    ],
    "A10G_SPOT": [
        "https://us-east1-agora-galois-a10g.run.app",
        "https://us-east5-agora-galois-a10g.run.app",
        "https://us-west1-agora-galois-a10g.run.app",
    ],
    "A100_SERVERLESS": [
        "https://us-central1-agora-galois-a100.run.app",
    ],
}


@dataclass
class ShardResult:
    """Result from a sharded inference call.

    Attributes:
        text: The generated text response.
        region_endpoint: Which endpoint responded.
        latency_ms: Round-trip latency in milliseconds.
        tier: GPU tier used.
        success: Whether the call succeeded.
        error: Error message if success is False.
    """
    text: str = ""
    region_endpoint: str = ""
    latency_ms: float = 0.0
    tier: str = "L4_SPOT"
    success: bool = False
    error: str = ""


# ---------------------------------------------------------------------------
# Shard Router
# ---------------------------------------------------------------------------

class ShardRouter:
    """Cross-Region Inference Sharding coordinator.

    Usage::

        router = ShardRouter(tier="L4_SPOT")
        result = await router.route(prompt="theorem proof")
        if result.success:
            print(result.text)
        else:
            # Fallback — escalate tier
            router.escalate()
            result = await router.route(prompt="theorem proof")

    The router implements:
    - Round-robin load balancing across endpoints in the active tier.
    - Race-condition routing: all endpoints are called concurrently; the
      first success wins (``asyncio.wait`` with ``FIRST_COMPLETED``).
    - Automatic failover: if all endpoints in a tier fail, ``escalate()``
      moves to the next tier.
    - Dry-run mode: if ``AGORA_SHARD_DRY_RUN=1``, returns a simulated
      response without real HTTP calls (for testing and local dev).
    """

    _TIER_ORDER = ["L4_SPOT", "A10G_SPOT", "A100_SERVERLESS"]

    def __init__(self, tier: str = "L4_SPOT") -> None:
        if tier not in self._TIER_ORDER:
            raise ValueError(f"Unknown tier: {tier!r}. Must be one of {self._TIER_ORDER}")
        self._tier = tier
        self._endpoints = list(_ENDPOINT_TEMPLATES[tier])
        self._round_robin_idx = 0
        self._total_calls = 0
        self._total_failures = 0
        self._dry_run = os.getenv("AGORA_SHARD_DRY_RUN", "0") == "1"

    @property
    def tier(self) -> str:
        return self._tier

    @property
    def endpoints(self) -> list[str]:
        return list(self._endpoints)

    def escalate(self) -> bool:
        """Move to the next GPU tier.

        Returns:
            True if escalation succeeded, False if already at max tier.
        """
        current_idx = self._TIER_ORDER.index(self._tier)
        if current_idx >= len(self._TIER_ORDER) - 1:
            logger.warning("shard_router_max_tier_reached", tier=self._tier)
            return False

        new_tier = self._TIER_ORDER[current_idx + 1]
        logger.info("shard_router_escalating", from_tier=self._tier, to_tier=new_tier)
        self._tier = new_tier
        self._endpoints = list(_ENDPOINT_TEMPLATES[new_tier])
        self._round_robin_idx = 0
        return True

    def _next_endpoint(self) -> str:
        """Return the next endpoint in round-robin order."""
        ep = self._endpoints[self._round_robin_idx % len(self._endpoints)]
        self._round_robin_idx += 1
        return ep

    async def route(
        self,
        prompt: str,
        timeout_s: float = 30.0,
        *,
        race_all: bool = True,
    ) -> ShardResult:
        """Route an inference request to the fastest available endpoint.

        Args:
            prompt: The text prompt to send.
            timeout_s: Per-endpoint timeout in seconds.
            race_all: If True, calls all endpoints concurrently and returns
                      the first successful response. If False, uses simple
                      round-robin (cheaper but slower failover).

        Returns:
            :class:`ShardResult` from the first successful endpoint.
        """
        self._total_calls += 1
        t_start = time.monotonic()

        if self._dry_run:
            return self._dry_run_response(prompt, t_start)

        if race_all:
            return await self._race_all(prompt, timeout_s, t_start)
        else:
            return await self._round_robin_route(prompt, timeout_s, t_start)

    async def _race_all(
        self, prompt: str, timeout_s: float, t_start: float
    ) -> ShardResult:
        """Call all endpoints concurrently; return first success."""
        tasks = {
            asyncio.create_task(
                self._call_endpoint(ep, prompt, timeout_s),
                name=f"shard_{ep}",
            )
            for ep in self._endpoints
        }

        try:
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED,
                timeout=timeout_s + 2,
            )
        except Exception as exc:
            logger.warning("shard_race_failed", error=str(exc)[:100])
            for t in tasks:
                t.cancel()
            self._total_failures += 1
            return ShardResult(
                success=False,
                error=str(exc),
                tier=self._tier,
            )

        # Cancel pending tasks (we have our winner)
        for task in pending:
            task.cancel()

        # Find first successful result
        for task in done:
            try:
                result = task.result()
                if result.success:
                    result.latency_ms = (time.monotonic() - t_start) * 1000
                    logger.info(
                        "shard_race_won",
                        endpoint=result.region_endpoint,
                        latency_ms=round(result.latency_ms, 1),
                        tier=self._tier,
                    )
                    return result
            except Exception:
                continue

        # All failed
        self._total_failures += 1
        logger.warning("shard_all_endpoints_failed", tier=self._tier, count=len(self._endpoints))
        return ShardResult(
            success=False,
            error=f"All {len(self._endpoints)} endpoints in tier {self._tier} failed",
            tier=self._tier,
        )

    async def _round_robin_route(
        self, prompt: str, timeout_s: float, t_start: float
    ) -> ShardResult:
        """Simple round-robin with sequential failover."""
        for _ in range(len(self._endpoints)):
            ep = self._next_endpoint()
            result = await self._call_endpoint(ep, prompt, timeout_s)
            if result.success:
                result.latency_ms = (time.monotonic() - t_start) * 1000
                return result

        self._total_failures += 1
        return ShardResult(
            success=False,
            error=f"All endpoints exhausted in tier {self._tier}",
            tier=self._tier,
        )

    async def _call_endpoint(
        self, endpoint: str, prompt: str, timeout_s: float
    ) -> ShardResult:
        """Call a single regional endpoint with the inference payload."""
        try:
            import httpx
            payload = {
                "prompt": prompt,
                "max_tokens": 2048,
                "temperature": 0.7,
            }
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                resp = await client.post(
                    f"{endpoint}/v1/completions",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
                text = (
                    data.get("choices", [{}])[0].get("text", "")
                    or data.get("text", "")
                    or data.get("result", "")
                )
                return ShardResult(
                    text=text,
                    region_endpoint=endpoint,
                    tier=self._tier,
                    success=True,
                )
        except Exception as exc:
            logger.debug(
                "shard_endpoint_failed",
                endpoint=endpoint,
                error=str(exc)[:80],
            )
            return ShardResult(
                success=False,
                error=str(exc)[:80],
                region_endpoint=endpoint,
                tier=self._tier,
            )

    def _dry_run_response(self, prompt: str, t_start: float) -> ShardResult:
        """Return a simulated response for testing."""
        ep = self._endpoints[0] if self._endpoints else "localhost"
        logger.info("shard_dry_run", endpoint=ep, tier=self._tier)
        return ShardResult(
            text=f"-- [DRY RUN] Shard response for: {prompt[:60]}...\nexact?",
            region_endpoint=ep,
            latency_ms=(time.monotonic() - t_start) * 1000,
            tier=self._tier,
            success=True,
        )

    def stats(self) -> dict[str, Any]:
        """Return router statistics for FinOps/Turing reporting."""
        return {
            "tier": self._tier,
            "endpoints": self._endpoints,
            "total_calls": self._total_calls,
            "total_failures": self._total_failures,
            "success_rate": (
                round((self._total_calls - self._total_failures) / max(1, self._total_calls), 4)
            ),
        }


# ---------------------------------------------------------------------------
# Convenience: build router from cortex_v16 GPU tier summary
# ---------------------------------------------------------------------------

def build_router_from_cortex(cortex: "SymBrainV16Cortex") -> ShardRouter:  # type: ignore[name-defined]
    """Create a ShardRouter pre-configured from a SymBrainV16Cortex tier selection.

    This is the canonical way to integrate the router into Galois/Archimedes.

    Args:
        cortex: An initialized :class:`~agents.galois.symbrain.cortex_v16.SymBrainV16Cortex`.

    Returns:
        A :class:`ShardRouter` targeting the cortex's recommended GPU tier.
    """
    summary = cortex.get_gpu_tier_summary()
    tier = summary.get("selected_tier", "L4_SPOT")
    router = ShardRouter(tier=tier)
    logger.info(
        "shard_router_built_from_cortex",
        tier=tier,
        regions=summary.get("regions", []),
        dopamine=summary.get("dopamine_level"),
    )
    return router
