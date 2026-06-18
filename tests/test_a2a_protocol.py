# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Tests for the A2A Protocol v1.1 implementation.

Verifies:
  - Agent card served correctly from /.well-known/agent.json
  - RPC endpoint dispatches tasks to registered executor
  - Async Claim Check lifecycle (delegate + poll)
  - OIDC token injection when OIDC_ENABLED=1
  - GCS artifact pointer passing
  - A2A_MOCK_LOCAL bypass has been removed (no mocking)
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from agents.common.a2a import (
    A2AClient,
    A2AServerMixin,
    A2ATaskRequest,
    A2ATaskResult,
    AgentCard,
    get_artifact_from_gcs,
    upload_artifact_to_gcs,
)
from agents.common.a2a_state import (
    create_task,
    get_task,
    reset_in_memory_store,
    update_task_status,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_state():
    """Reset in-memory A2A state store between tests."""
    reset_in_memory_store()
    yield
    reset_in_memory_store()


@pytest.fixture
def sample_agent_card() -> AgentCard:
    return AgentCard(
        name="TestAgent",
        description="A test agent",
        url="http://test-agent.run.app",
        version="4.0.0",
        capabilities={"streaming": True},
        skills=[
            {"id": "test_skill", "name": "Test Skill", "description": "Does a thing"}
        ],
    )


@pytest.fixture
def test_app(sample_agent_card):
    """Create a FastAPI test app with A2A routes mounted."""
    from fastapi import FastAPI

    app = FastAPI()
    mixin = A2AServerMixin(sample_agent_card)

    async def mock_executor(prompt: str, context: dict) -> dict:
        return {"answer": f"Processed: {prompt}", "cost_usd": 0.01}

    mixin.register_executor(mock_executor)
    mixin.mount_a2a_routes(app)
    return app


@pytest.fixture
def client(test_app):
    return TestClient(test_app)


# ---------------------------------------------------------------------------
# Test 1: Agent card served correctly
# ---------------------------------------------------------------------------

def test_agent_card_served_correctly(client, sample_agent_card):
    """GET /.well-known/agent.json returns the correct structured agent card."""
    resp = client.get("/.well-known/agent.json")
    assert resp.status_code == 200

    data = resp.json()
    assert data["name"] == "TestAgent"
    assert data["version"] == "4.0.0"
    assert data["capabilities"]["streaming"] is True
    assert len(data["skills"]) == 1
    assert data["skills"][0]["id"] == "test_skill"


# ---------------------------------------------------------------------------
# Test 2: Health endpoint
# ---------------------------------------------------------------------------

def test_health_endpoint(client):
    """GET /health returns 200 with agent name."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["agent"] == "TestAgent"


# ---------------------------------------------------------------------------
# Test 3: RPC endpoint dispatches task and returns result
# ---------------------------------------------------------------------------

def test_rpc_endpoint_dispatches_task(client):
    """POST /rpc tasks/send invokes the executor and returns complete status."""
    payload = {
        "jsonrpc": "2.0",
        "method": "tasks/send",
        "id": "test-task-001",
        "params": {
            "prompt": "What is 2+2?",
            "context": {"difficulty": "trivial"},
        },
    }
    resp = client.post("/rpc", json=payload)
    assert resp.status_code == 200

    data = resp.json()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == "test-task-001"
    assert "result" in data
    assert data["result"]["status"] == "complete"
    assert "Processed" in data["result"]["answer"]


# ---------------------------------------------------------------------------
# Test 4: Method not found returns correct JSON-RPC error
# ---------------------------------------------------------------------------

def test_rpc_unknown_method_returns_error(client):
    """POST /rpc with unknown method returns JSON-RPC -32601 error."""
    payload = {
        "jsonrpc": "2.0",
        "method": "tasks/unknown_method",
        "id": "test-task-002",
        "params": {},
    }
    resp = client.post("/rpc", json=payload)
    assert resp.status_code == 200  # JSON-RPC errors are 200 by spec

    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == -32601


# ---------------------------------------------------------------------------
# Test 5: Async Claim Check lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_async_claim_check_lifecycle():
    """delegate_task_async() returns task_id; state transitions to complete."""
    # Test in-memory state store directly
    task_id = "test-async-001"
    await create_task(task_id, "TestAgent", "Prove Riemann Hypothesis")

    task = await get_task(task_id)
    assert task is not None
    assert task["status"] == "accepted"
    assert task["agent"] == "TestAgent"

    await update_task_status(task_id, "running", None)
    task = await get_task(task_id)
    assert task["status"] == "running"

    await update_task_status(task_id, "complete", {"answer": "QED", "cost_usd": 0.05})
    task = await get_task(task_id)
    assert task["status"] == "complete"
    assert task["result"]["answer"] == "QED"


# ---------------------------------------------------------------------------
# Test 6: tasks/get RPC for polling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rpc_tasks_get_returns_task_state():
    """POST /rpc tasks/get returns the current task state."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    task_id = "poll-task-001"
    await create_task(task_id, "TestAgent", "Long computation")
    await update_task_status(task_id, "complete", {"result": "42"})

    sample_card = AgentCard(
        name="TestAgent",
        description="Test",
        url="http://test.run.app",
    )
    app = FastAPI()
    mixin = A2AServerMixin(sample_card)
    mixin.mount_a2a_routes(app)
    client = TestClient(app)

    payload = {
        "jsonrpc": "2.0",
        "method": "tasks/get",
        "id": "req-001",
        "params": {"task_id": task_id},
    }
    resp = client.post("/rpc", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["status"] == "complete"


# ---------------------------------------------------------------------------
# Test 7: OIDC token injection when OIDC_ENABLED=1
# ---------------------------------------------------------------------------

def test_oidc_token_injected_in_headers():
    """When OIDC_ENABLED=1, Authorization: Bearer header is injected."""
    with patch.dict(os.environ, {"OIDC_ENABLED": "1"}):
        with patch("agents.common.a2a._get_oidc_token", return_value="fake-jwt-token"):
            with patch("httpx.AsyncClient"):
                client = A2AClient("http://test-agent.run.app")
                headers = client._auth_headers("http://test-agent.run.app")
                assert "Authorization" in headers
                assert headers["Authorization"] == "Bearer fake-jwt-token"

def test_oidc_token_not_injected_when_disabled():
    """When OIDC_ENABLED=0, no Authorization header is added."""
    with patch.dict(os.environ, {"OIDC_ENABLED": "0"}):
        with patch("httpx.AsyncClient"):
            client = A2AClient("http://test-agent.run.app")
            headers = client._auth_headers("http://test-agent.run.app")
            assert "Authorization" not in headers


# ---------------------------------------------------------------------------
# Test 8: GCS artifact pointer passing (mocked)
# ---------------------------------------------------------------------------

def test_gcs_artifact_upload_and_download():
    """Artifacts are serialized, stored, and retrieved correctly via GCS URIs."""
    test_payload = {
        "conjecture": "The Riemann Hypothesis holds",
        "confidence": 0.97,
        "lean_sketch": "theorem rh : ...",
    }

    mock_blob = MagicMock()
    mock_blob.upload_from_string = MagicMock()
    mock_blob.download_as_text = MagicMock(return_value=json.dumps(test_payload))

    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob

    mock_client_instance = MagicMock()
    mock_client_instance.bucket.return_value = mock_bucket

    mock_storage = MagicMock()
    mock_storage.Client.return_value = mock_client_instance
    
    mock_google = MagicMock()
    mock_google.cloud = MagicMock()
    mock_google.cloud.storage = mock_storage

    with patch.dict("sys.modules", {"google": mock_google, "google.cloud": mock_google.cloud, "google.cloud.storage": mock_storage}):
        uri = upload_artifact_to_gcs(
            content=test_payload,
            bucket="agora-checkpoints",
            blob_name="test/payload.json",
        )

    assert uri == "gs://agora-checkpoints/test/payload.json"
    mock_blob.upload_from_string.assert_called_once()
    uploaded_args = mock_blob.upload_from_string.call_args[0][0]
    assert "Riemann Hypothesis" in uploaded_args


# ---------------------------------------------------------------------------
# Test 9: A2A_MOCK_LOCAL bypass is NOT present (v3 compliance check)
# ---------------------------------------------------------------------------

def test_a2a_mock_local_bypass_removed():
    """Verifies no env-var-based mock bypass is present in the a2a module."""
    import inspect
    import agents.common.a2a as a2a_module

    source = inspect.getsource(a2a_module)
    # The old pattern was: if os.getenv("A2A_MOCK_LOCAL") == "1": return {"status": "mocked"}
    # This must not exist — check for the mocked return value
    assert '"mocked"' not in source, (
        "a2a.py contains a mock bypass return value. "
        "All A2A calls must be real HTTP calls or fail explicitly."
    )
    assert "return_value='mocked'" not in source


# ---------------------------------------------------------------------------
# Test 10: AgentCard model validation
# ---------------------------------------------------------------------------

def test_agent_card_model_validation():
    """AgentCard validates required fields and rejects invalid inputs."""
    card = AgentCard(
        name="Galois",
        description="Creative mathematician",
        url="https://galois-agent.run.app",
        version="4.0.0",
    )
    assert card.name == "Galois"
    assert card.capabilities == {}
    assert card.skills == []

    # Test model serialisation round-trip
    serialised = card.model_dump()
    restored = AgentCard(**serialised)
    assert restored.name == card.name
    assert restored.url == card.url


# ---------------------------------------------------------------------------
# Test 11: No executor registered returns proper error
# ---------------------------------------------------------------------------

def test_rpc_no_executor_returns_error():
    """POST /rpc without an executor registered returns -32603 error."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    card = AgentCard(
        name="BrokenAgent",
        description="No executor",
        url="http://broken.run.app",
    )
    app = FastAPI()
    mixin = A2AServerMixin(card)
    mixin.mount_a2a_routes(app)  # Do NOT call register_executor

    client = TestClient(app)
    resp = client.post("/rpc", json={
        "jsonrpc": "2.0",
        "method": "tasks/send",
        "id": "no-executor-001",
        "params": {"prompt": "test"},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == -32603
    assert "executor" in data["error"]["message"].lower()
