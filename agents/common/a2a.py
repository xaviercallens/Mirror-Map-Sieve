# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Agent-to-Agent (A2A) Protocol v1.1 Client and Server Mixins.

Implements the open A2A protocol (JSON-RPC over HTTPS) to allow
Agora agents to delegate tasks to each other without coupled imports.

v1.1 improvements:
  - OIDC token injection for GCP service-to-service authentication
  - Async Claim Check pattern (202 Accepted + task_id polling)
  - GCS artifact pointer passing (avoids 1 MiB Firestore document limits)
  - All A2A calls are real HTTP calls — no test bypass environment variables.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
import time
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class AgentCard(BaseModel):
    name: str
    description: str
    url: str
    version: str = "1.0.0"
    capabilities: dict[str, Any] = Field(default_factory=dict)
    skills: list[dict[str, str]] = Field(default_factory=list)

class A2ATaskRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str = "tasks/send"
    params: dict[str, Any]
    id: str

class A2ATaskStatusRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str = "tasks/get"
    params: dict[str, Any]
    id: str

class A2ATaskResult(BaseModel):
    task_id: str
    status: str  # "accepted" | "running" | "complete" | "failed"
    result: dict[str, Any] | None = None
    artifact_uri: str | None = None  # GCS pointer for large payloads
    error: str | None = None

# ---------------------------------------------------------------------------
# GCS Artifact Pointer Utilities
# ---------------------------------------------------------------------------

def upload_artifact_to_gcs(
    content: str | dict,
    bucket: str,
    blob_name: str,
) -> str:
    """Upload a heavy artifact to GCS and return a signed gs:// URI.

    Agents must pass GCS URIs between themselves rather than embedding
    large JSON payloads directly in A2A messages to avoid Firestore's
    1 MiB document limit.

    Args:
        content: Text or dict to serialize and upload.
        bucket: GCS bucket name (e.g. 'agora-checkpoints').
        blob_name: Object path within bucket (e.g. 'run-123/lean_draft.lean').

    Returns:
        'gs://{bucket}/{blob_name}'
    """
    from google.cloud import storage  # type: ignore[import]

    client = storage.Client()
    bkt = client.bucket(bucket)
    blob = bkt.blob(blob_name)

    if isinstance(content, dict):
        body = json.dumps(content, ensure_ascii=False)
    else:
        body = content

    blob.upload_from_string(body, content_type="application/json")
    uri = f"gs://{bucket}/{blob_name}"
    logger.info("artifact_uploaded_to_gcs", uri=uri, size=len(body))
    return uri


def get_artifact_from_gcs(uri: str) -> dict | str:
    """Download an artifact from a 'gs://' URI.

    Args:
        uri: GCS URI in the form 'gs://{bucket}/{blob}'.

    Returns:
        Parsed dict if JSON, raw string otherwise.
    """
    from google.cloud import storage  # type: ignore[import]

    if not uri.startswith("gs://"):
        raise ValueError(f"Expected gs:// URI, got: {uri!r}")

    path = uri[len("gs://"):]
    bucket_name, _, blob_name = path.partition("/")

    client = storage.Client()
    bkt = client.bucket(bucket_name)
    blob = bkt.blob(blob_name)
    body = blob.download_as_text()
    logger.info("artifact_downloaded_from_gcs", uri=uri, size=len(body))

    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return body


# ---------------------------------------------------------------------------
# OIDC Token Helper
# ---------------------------------------------------------------------------

def _get_oidc_token(audience: str) -> str | None:
    """Fetch an OIDC identity token from the GCP metadata server.

    Returns None if running outside GCP (e.g. local dev without emulation).
    """
    metadata_url = (
        f"http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/"
        f"default/identity?audience={audience}"
    )
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(
                metadata_url,
                headers={"Metadata-Flavor": "Google"},
            )
            resp.raise_for_status()
            return resp.text.strip()
    except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError, asyncio.TimeoutError, OSError) as exc:
        logger.warning("oidc_token_fetch_failed", error=str(exc))
        return None


# ---------------------------------------------------------------------------
# A2A Client
# ---------------------------------------------------------------------------

class A2AClient:
    """Client for delegating tasks to remote agents via A2A protocol.

    Supports:
      - Synchronous task delegation (``delegate_task``)
      - Asynchronous Claim Check delegation (``delegate_task_async``)
      - OIDC-authenticated requests when ``OIDC_ENABLED=1``
      - GCS artifact pointer passing for large payloads
    """

    def __init__(self, agent_url: str):
        self.agent_url = agent_url.rstrip("/")
        # Long timeout for MCTS — Cloud Run max request is 3600s
        self.client = httpx.AsyncClient(timeout=3600.0)

    def _auth_headers(self, audience: str) -> dict[str, str]:
        """Build Authorization header with OIDC token if enabled."""
        if os.getenv("OIDC_ENABLED", "0") == "1":
            token = _get_oidc_token(audience)
            if token:
                return {"Authorization": f"Bearer {token}"}
        return {}

    async def get_agent_card(self) -> AgentCard:
        """Fetch the agent card to discover capabilities."""
        headers = self._auth_headers(self.agent_url)
        resp = await self.client.get(
            f"{self.agent_url}/.well-known/agent.json",
            headers=headers,
        )
        resp.raise_for_status()
        return AgentCard(**resp.json())

    async def delegate_task(
        self,
        task_id: str,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a synchronous task to the remote agent.

        For long-running tasks (MCTS Class 3), prefer ``delegate_task_async``.
        """
        req = A2ATaskRequest(
            id=task_id,
            params={"prompt": prompt, "context": context or {}},
        )
        headers = self._auth_headers(self.agent_url)
        logger.info(
            "a2a_delegating_task",
            target=self.agent_url,
            task_id=task_id,
        )
        resp = await self.client.post(
            f"{self.agent_url}/rpc",
            json=req.model_dump(),
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json().get("result", {})

    async def delegate_task_async(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        artifact_uri: str | None = None,
    ) -> str:
        """Send a task and immediately receive a task_id (202 Accepted).

        The caller must poll ``get_task_status(task_id)`` or rely on
        Firestore state listeners for completion.

        Use this for long MCTS searches to avoid Cloud Run's 60-minute
        synchronous request timeout.

        Args:
            prompt: Task description for the agent.
            context: Optional structured context dict.
            artifact_uri: Optional GCS URI for a pre-uploaded large payload.

        Returns:
            task_id string for polling.
        """
        task_id = str(uuid.uuid4())
        req = A2ATaskRequest(
            id=task_id,
            params={
                "prompt": prompt,
                "context": context or {},
                "artifact_uri": artifact_uri,
                "async": True,
            },
        )
        headers = self._auth_headers(self.agent_url)
        logger.info(
            "a2a_delegating_task_async",
            target=self.agent_url,
            task_id=task_id,
        )
        resp = await self.client.post(
            f"{self.agent_url}/rpc",
            json=req.model_dump(),
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        # Server MUST return HTTP 202 and include task_id in result
        returned_task_id = data.get("result", {}).get("task_id", task_id)
        return returned_task_id

    async def get_task_status(self, task_id: str) -> A2ATaskResult:
        """Poll for the status of an async task by task_id.

        Args:
            task_id: ID returned by ``delegate_task_async``.

        Returns:
            A2ATaskResult with current status and optional result/artifact.
        """
        req = A2ATaskStatusRequest(
            id=str(uuid.uuid4()),
            params={"task_id": task_id},
        )
        headers = self._auth_headers(self.agent_url)
        resp = await self.client.post(
            f"{self.agent_url}/rpc",
            json=req.model_dump(),
            headers=headers,
        )
        resp.raise_for_status()
        result = resp.json().get("result", {})
        return A2ATaskResult(
            task_id=task_id,
            status=result.get("status", "unknown"),
            result=result.get("result"),
            artifact_uri=result.get("artifact_uri"),
            error=result.get("error"),
        )

    async def delegate_task_pubsub(
        self,
        target_agent: str,
        prompt: str,
        context: dict[str, Any] | None = None,
        artifact_uri: str | None = None,
    ) -> str:
        """Publish a task to Google Cloud Pub/Sub with exponential backoff.
        
        Args:
            target_agent: Topic name (e.g., 'agora-task-dispatch-euler')
            prompt: Task description
            context: Optional context
            artifact_uri: Optional GCS URI
            
        Returns:
            task_id string
        """
        try:
            from google.cloud import pubsub_v1
        except ImportError:
            logger.warning("google-cloud-pubsub not installed, falling back to HTTP async")
            return await self.delegate_task_async(prompt, context, artifact_uri)

        project_id = os.environ.get("GCP_PROJECT", "gen-lang-client-0625573011")
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(project_id, f"agora-task-dispatch-{target_agent}")

        task_id = str(uuid.uuid4())
        payload = {
            "id": task_id,
            "method": "tasks/send",
            "params": {
                "prompt": prompt,
                "context": context or {},
                "artifact_uri": artifact_uri,
                "async": True,
            }
        }
        
        data = json.dumps(payload).encode("utf-8")
        
        # Exponential backoff for Pub/Sub publishing
        max_retries = 5
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                future = publisher.publish(topic_path, data)
                message_id = future.result(timeout=10)
                logger.info("pubsub_task_published", task_id=task_id, message_id=message_id, topic=topic_path)
                return task_id
            except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError, asyncio.TimeoutError, OSError) as e:
                if attempt == max_retries - 1:
                    logger.error("pubsub_publish_failed_dlq", task_id=task_id, error=str(e))
                    # Route to DLQ conceptually
                    self._route_to_dlq(project_id, publisher, payload, str(e))
                    raise
                delay = base_delay * (2 ** attempt)
                logger.warning("pubsub_publish_retry", attempt=attempt+1, delay=delay, error=str(e))
                await asyncio.sleep(delay)
                
        return task_id

    def _route_to_dlq(self, project_id: str, publisher: Any, payload: dict, error_msg: str) -> None:
        """Publish to Dead Letter Queue."""
        try:
            dlq_path = publisher.topic_path(project_id, "agora-task-dispatch-dlq")
            payload["dlq_reason"] = error_msg
            publisher.publish(dlq_path, json.dumps(payload).encode("utf-8"))
            logger.info("routed_to_dlq", task_id=payload["id"])
        except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError, asyncio.TimeoutError, OSError) as e:
            logger.error("dlq_routing_failed", error=str(e))

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()


# ---------------------------------------------------------------------------
# Server Mixin (for ADK Agents)
# ---------------------------------------------------------------------------

class A2AServerMixin:
    """Mixin to add A2A endpoints to a Google ADK FastAPI server.

    The ``/rpc`` handler dispatches to ``self.agent_executor`` — a callable
    that takes ``(prompt, context)`` and returns a result dict.
    Register the executor via ``register_executor()``.
    """

    def __init__(self, agent_card: AgentCard):
        self.agent_card = agent_card
        self._executor: Any = None

    def register_executor(self, executor: Any) -> None:
        """Register the agent's async execute callable.

        The executor must have signature:
            async def execute(prompt: str, context: dict) -> dict
        """
        self._executor = executor

    def mount_a2a_routes(self, app: Any) -> None:
        """Mount standard A2A routes onto a FastAPI/ADK app."""

        @app.on_event("startup")
        async def on_startup():
            from agents.common.registry import AgentRegistry
            import asyncio
            registry = AgentRegistry()
            try:
                await registry.register_agent(self.agent_card)
            except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError, asyncio.TimeoutError, OSError) as e:
                logger.warning("agent_registration_failed", error=str(e))
                
            async def heartbeat_loop():
                while True:
                    await asyncio.sleep(60)
                    try:
                        await registry.heartbeat(self.agent_card.name)
                    except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError, asyncio.TimeoutError, OSError) as e:
                        logger.warning("agent_heartbeat_failed", error=str(e))
            
            asyncio.create_task(heartbeat_loop())

        @app.get("/.well-known/agent.json")
        async def serve_agent_card() -> dict:
            return self.agent_card.model_dump()

        @app.get("/health")
        async def health() -> dict:
            return {"status": "ok", "agent": self.agent_card.name}

        @app.post("/rpc")
        async def handle_rpc(req: dict) -> dict:
            method = req.get("method")
            req_id = req.get("id", str(uuid.uuid4()))
            params = req.get("params", {})

            if method == "tasks/send":
                if self._executor is None:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32603, "message": "No executor registered"},
                    }

                is_async = params.get("async", False)
                prompt = params.get("prompt", "")
                context = params.get("context", {})
                artifact_uri = params.get("artifact_uri")

                # If a GCS pointer was provided, download and merge into context
                if artifact_uri:
                    try:
                        extra = get_artifact_from_gcs(artifact_uri)
                        if isinstance(extra, dict):
                            context.update(extra)
                    except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError, asyncio.TimeoutError, OSError) as exc:
                        logger.warning(
                            "artifact_download_failed",
                            uri=artifact_uri,
                            error=str(exc),
                        )

                task_id = req_id
                logger.info(
                    "a2a_task_received",
                    agent=self.agent_card.name,
                    task_id=task_id,
                    async_mode=is_async,
                )

                if is_async:
                    # Async Claim Check: spawn background task and return 202
                    import asyncio

                    async def _run_background() -> None:
                        try:
                            from agents.common.a2a_state import update_task_status
                            result = await self._executor(prompt, context)
                            await update_task_status(task_id, "complete", result)
                        except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError, asyncio.TimeoutError, OSError) as exc:
                            logger.error(
                                "a2a_async_task_failed",
                                task_id=task_id,
                                error=str(exc),
                            )
                            try:
                                from agents.common.a2a_state import update_task_status
                                await update_task_status(
                                    task_id, "failed", {"error": str(exc)}
                                )
                            except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError, asyncio.TimeoutError, OSError):
                                pass

                    asyncio.create_task(_run_background())
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"status": "accepted", "task_id": task_id},
                    }
                else:
                    # Synchronous execution
                    try:
                        result = await self._executor(prompt, context)
                        return {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "result": {"status": "complete", "task_id": task_id, **result},
                        }
                    except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError, asyncio.TimeoutError, OSError) as exc:
                        logger.error(
                            "a2a_sync_task_failed",
                            task_id=task_id,
                            error=str(exc),
                        )
                        return {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": -32603, "message": str(exc)},
                        }

            elif method == "tasks/get":
                task_id = params.get("task_id", "")
                try:
                    from agents.common.a2a_state import get_task
                    task = await get_task(task_id)
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": task or {"status": "not_found", "task_id": task_id},
                    }
                except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError, asyncio.TimeoutError, OSError) as exc:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32603, "message": str(exc)},
                    }

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }
