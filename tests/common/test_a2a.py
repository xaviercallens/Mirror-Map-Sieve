import pytest
import asyncio
import os
from unittest.mock import MagicMock, AsyncMock
from agents.common.a2a import (
    A2AClient,
    A2AServerMixin,
    AgentCard,
    upload_artifact_to_gcs,
    get_artifact_from_gcs,
    _get_oidc_token,
)
from agents.common.a2a_state import get_task, update_task_status, create_task
import httpx

@pytest.fixture
def a2a_client():
    return A2AClient("http://mock-agent")

@pytest.fixture
def mock_card():
    return AgentCard(
        name="test-agent",
        description="A test agent",
        url="http://mock-agent"
    )

def test_get_oidc_token_success(mocker):
    mock_get = mocker.patch("httpx.Client.get", autospec=True)
    mock_resp = MagicMock()
    mock_resp.text = "mock-token"
    mock_get.return_value = mock_resp
    token = _get_oidc_token("aud")
    assert token == "mock-token"

def test_get_oidc_token_fail(mocker):
    mock_get = mocker.patch("httpx.Client.get", side_effect=Exception("error"))
    token = _get_oidc_token("aud")
    assert token is None

def test_a2a_auth_headers_disabled(a2a_client, monkeypatch):
    monkeypatch.setenv("OIDC_ENABLED", "0")
    assert a2a_client._auth_headers("aud") == {}

def test_a2a_auth_headers_enabled(a2a_client, monkeypatch, mocker):
    monkeypatch.setenv("OIDC_ENABLED", "1")
    mocker.patch("agents.common.a2a._get_oidc_token", return_value="mock-token")
    headers = a2a_client._auth_headers("aud")
    assert headers == {"Authorization": "Bearer mock-token"}

@pytest.mark.asyncio
async def test_get_agent_card(a2a_client, mocker):
    mock_get = mocker.patch.object(a2a_client.client, "get", new_callable=AsyncMock)
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"name": "test", "description": "desc", "url": "url"}
    mock_get.return_value = mock_resp
    
    card = await a2a_client.get_agent_card()
    assert card.name == "test"

@pytest.mark.asyncio
async def test_delegate_task(a2a_client, mocker):
    mock_post = mocker.patch.object(a2a_client.client, "post", new_callable=AsyncMock)
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": {"success": True}}
    mock_post.return_value = mock_resp
    
    res = await a2a_client.delegate_task("task_1", "prompt", {"ctx": 1})
    assert res == {"success": True}

@pytest.mark.asyncio
async def test_delegate_task_async(a2a_client, mocker):
    mock_post = mocker.patch.object(a2a_client.client, "post", new_callable=AsyncMock)
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": {"task_id": "returned_task_1"}}
    mock_post.return_value = mock_resp
    
    task_id = await a2a_client.delegate_task_async("prompt", {"ctx": 1}, "gs://bucket/blob")
    assert task_id == "returned_task_1"

@pytest.mark.asyncio
async def test_get_task_status(a2a_client, mocker):
    mock_post = mocker.patch.object(a2a_client.client, "post", new_callable=AsyncMock)
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": {"status": "running", "result": None}}
    mock_post.return_value = mock_resp
    
    status = await a2a_client.get_task_status("task_1")
    assert status.task_id == "task_1"
    assert status.status == "running"

@pytest.mark.asyncio
async def test_delegate_task_pubsub_success(mocker):
    # Mock pubsub
    mock_pub = mocker.patch("google.cloud.pubsub_v1.PublisherClient")
    client = A2AClient("http://mock-agent")
    mocker.patch.object(client, "get_task_status", return_value={"status": "complete", "result": 42})
    mock_publisher = MagicMock()
    mock_pub.return_value = mock_publisher
    
    mock_future = MagicMock()
    mock_future.result.return_value = "msg-123"
    mock_publisher.publish.return_value = mock_future
    
    task_id = await client.delegate_task_pubsub("euler", "prompt")
    assert type(task_id) == str
    assert len(task_id) > 10

@pytest.mark.asyncio
async def test_delegate_task_pubsub_retry_fail(mocker):
    # Mock pubsub
    mock_pub = mocker.patch("google.cloud.pubsub_v1.PublisherClient")
    client = A2AClient("http://mock-agent")
    mocker.patch.object(client, "get_task_status", side_effect=[{"status": "accepted"}] * 3)
    mock_publisher = MagicMock()
    mock_pub.return_value = mock_publisher
    
    # Fail repeatedly
    mock_publisher.publish.side_effect = Exception("pubsub error")
    
    # Fast forward sleep
    mocker.patch("asyncio.sleep", new_callable=AsyncMock)
    
    with pytest.raises(Exception, match="pubsub error"):
        await client.delegate_task_pubsub("euler", "prompt")

@pytest.mark.asyncio
async def test_aclose(a2a_client, mocker):
    mock_aclose = mocker.patch.object(a2a_client.client, "aclose", new_callable=AsyncMock)
    await a2a_client.aclose()
    mock_aclose.assert_called_once()

# A2AServerMixin tests
def test_a2a_server_mixin_init(mock_card):
    mixin = A2AServerMixin(mock_card)
    assert mixin.agent_card == mock_card

def test_register_executor(mock_card):
    mixin = A2AServerMixin(mock_card)
    async def mock_exec(p, c): pass
    mixin.register_executor(mock_exec)
    assert mixin._executor == mock_exec

@pytest.mark.asyncio
async def test_fastapi_a2a_server_routes(mock_card, mocker):
    mixin = A2AServerMixin(mock_card)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    real_app = FastAPI()
    mocker.patch.object(real_app, "on_event", return_value=lambda f: f)
    mixin.mount_a2a_routes(real_app)
    
    
    client = TestClient(real_app)
    
    # Test /.well-known/agent.json
    resp = client.get("/.well-known/agent.json")
    assert resp.status_code == 200
    assert resp.json()["name"] == "test-agent"
    
    # Test /health
    resp = client.get("/health")
    assert resp.status_code == 200
    
    # Test /rpc without executor
    resp = client.post("/rpc", json={"method": "tasks/send", "id": "1", "params": {}})
    assert resp.json().get("error", {}).get("message") == "No executor registered"

    # Register executor
    async def mock_exec(p, c):
        if p == "fail":
            raise Exception("exec fail")
        return {"output": "done"}
    mixin.register_executor(mock_exec)

    # Test /rpc with executor sync success
    resp = client.post("/rpc", json={"method": "tasks/send", "id": "1", "params": {"prompt": "do"}})
    assert resp.json()["result"]["output"] == "done"

    # Test /rpc with executor sync fail
    resp = client.post("/rpc", json={"method": "tasks/send", "id": "1", "params": {"prompt": "fail"}})
    assert "error" in resp.json()

    # Test /rpc with async
    mocker.patch("agents.common.a2a_state.update_task_status", new_callable=AsyncMock)
    resp = client.post("/rpc", json={"method": "tasks/send", "id": "2", "params": {"prompt": "do", "async": True}})
    assert resp.json()["result"]["status"] == "accepted"
    
    # Wait for background task to finish
    await asyncio.sleep(0.1)

    # Test /rpc tasks/get
    mocker.patch("agents.common.a2a_state.get_task", return_value={"status": "complete"})
    resp = client.post("/rpc", json={"method": "tasks/get", "id": "3", "params": {"task_id": "2"}})
    assert resp.json()["result"]["status"] == "complete"

    # Test unknown method
    resp = client.post("/rpc", json={"method": "unknown", "id": "4", "params": {}})
    assert resp.json()["error"]["code"] == -32601

# GCS tools
def test_upload_artifact_to_gcs(mocker):
    mock_storage = mocker.patch("google.cloud.storage.Client")
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_storage.return_value.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob
    
    uri = upload_artifact_to_gcs({"data": "test"}, "bucket", "blob")
    assert uri == "gs://bucket/blob"
    mock_blob.upload_from_string.assert_called_once()
    
def test_upload_artifact_to_gcs_string(mocker):
    mock_storage = mocker.patch("google.cloud.storage.Client")
    uri = upload_artifact_to_gcs("test string", "bucket", "blob")
    assert uri == "gs://bucket/blob"

def test_get_artifact_from_gcs_json(mocker):
    mock_storage = mocker.patch("google.cloud.storage.Client")
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    # Explicitly return string
    mock_blob.download_as_text.return_value = '{"data": "test"}'
    mock_storage.return_value.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob
    
    res = get_artifact_from_gcs("gs://bucket/blob")
    assert res == {"data": "test"}

def test_get_artifact_from_gcs_string(mocker):
    mock_storage = mocker.patch("google.cloud.storage.Client")
    mock_storage.return_value.bucket.return_value.blob.return_value.download_as_text.return_value = 'not json'
    
    res = get_artifact_from_gcs("gs://bucket/blob")
    assert res == "not json"

def test_get_artifact_from_gcs_bad_uri():
    with pytest.raises(ValueError):
        get_artifact_from_gcs("http://bad-uri")

@pytest.mark.asyncio
async def test_a2a_state_firestore(mocker, monkeypatch):
    monkeypatch.setenv("FIRESTORE_ENABLED", "1")
    mock_db = mocker.patch("google.cloud.firestore.AsyncClient")
    mock_doc = MagicMock()
    mock_db.return_value.collection.return_value.document.return_value = mock_doc
    
    # create_task
    mock_doc.set = AsyncMock()
    await create_task("0", "euler", "prompt")
    mock_doc.set.assert_called_once()

    # get_task exists
    mock_snap = MagicMock()
    mock_snap.exists = True
    mock_snap.to_dict.return_value = {"status": "ok"}
    mock_doc.get = AsyncMock(return_value=mock_snap)
    
    t = await get_task("1")
    assert t == {"status": "ok"}
    
    # get_task not exists
    mock_snap.exists = False
    t = await get_task("2")
    assert t is None
    
    # update_task_status
    mock_doc.update = AsyncMock()
    await update_task_status("3", "done", {"res": 1})
    mock_doc.update.assert_called_once()
    
    # get_firestore_client fail
    mocker.patch("google.cloud.firestore.AsyncClient", side_effect=Exception("error"))
    
    # Fallback to in-memory is triggered
    await update_task_status("3", "done", {"res": 1})

@pytest.mark.asyncio
async def test_a2a_state_memory():
    # create
    await create_task("5", "euler", "p")
    t = await get_task("5")
    assert t is not None
    
    await update_task_status("5", "running", {})
    
    # update non existant
    await update_task_status("6", "running", {})
    
    from agents.common.a2a_state import reset_in_memory_store
    reset_in_memory_store()
    t = await get_task("5")
    assert t is None
