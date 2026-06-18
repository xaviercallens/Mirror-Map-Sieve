import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from agents.common.a2a import A2AClient, A2AServerMixin, AgentCard

@pytest.fixture
def mock_card():
    return AgentCard(name="test", description="test", url="http://mock")

@pytest.mark.asyncio
async def test_fastapi_a2a_rpc_artifact_download_failed(mock_card, mocker):
    mixin = A2AServerMixin(mock_card)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    real_app = FastAPI()
    mocker.patch.object(real_app, "on_event", return_value=lambda f: f)
    mixin.mount_a2a_routes(real_app)
    
    
    client = TestClient(real_app)
    
    async def mock_exec(p, c): return {"res": 1}
    mixin.register_executor(mock_exec)
    
    mocker.patch("agents.common.a2a.get_artifact_from_gcs", side_effect=Exception("gcs err"))
    resp = client.post("/rpc", json={"method": "tasks/send", "id": "1", "params": {"prompt": "p", "artifact_uri": "gs://b/f"}})
    print("DEBUG RESP1:", resp.json())
    assert resp.status_code == 200
    assert resp.json()["result"]["res"] == 1

@pytest.mark.asyncio
async def test_fastapi_a2a_rpc_async_executor_fails(mock_card, mocker):
    mixin = A2AServerMixin(mock_card)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    real_app = FastAPI()
    mocker.patch.object(real_app, "on_event", return_value=lambda f: f)
    mixin.mount_a2a_routes(real_app)
    
    
    client = TestClient(real_app)
    
    async def mock_exec(p, c): raise Exception("exec fail")
    mixin.register_executor(mock_exec)
    
    mock_update = mocker.patch("agents.common.a2a_state.update_task_status", new_callable=AsyncMock)
    
    resp = client.post("/rpc", json={"method": "tasks/send", "id": "1", "params": {"prompt": "p", "async": True}})
    print("DEBUG RESP2:", resp.json())
    assert resp.json()["result"]["status"] == "accepted"
    
    await asyncio.sleep(0.1)
    mock_update.assert_called_with("1", "failed", {"error": "exec fail"})

@pytest.mark.asyncio
async def test_fastapi_a2a_rpc_async_executor_fails_and_db_fails(mock_card, mocker):
    mixin = A2AServerMixin(mock_card)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    real_app = FastAPI()
    mocker.patch.object(real_app, "on_event", return_value=lambda f: f)
    mixin.mount_a2a_routes(real_app)
    
    
    client = TestClient(real_app)
    
    async def mock_exec(p, c): raise Exception("exec fail")
    mixin.register_executor(mock_exec)
    
    mocker.patch("agents.common.a2a_state.update_task_status", side_effect=Exception("db fail"))
    
    resp = client.post("/rpc", json={"method": "tasks/send", "id": "2", "params": {"prompt": "p", "async": True}})
    print("DEBUG RESP3:", resp.json())
    assert resp.json()["result"]["status"] == "accepted"
    
    await asyncio.sleep(0.1)
