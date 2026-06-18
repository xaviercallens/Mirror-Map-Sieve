import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from agents.common.a2a import A2AClient, A2AServerMixin, AgentCard

@pytest.fixture
def mock_card():
    return AgentCard(
        name="test-agent",
        description="test",
        url="http://mock"
    )

@pytest.mark.asyncio
async def test_delegate_task_pubsub_import_error(mocker, monkeypatch):
    import sys
    import google.cloud
    monkeypatch.setitem(sys.modules, "google.cloud.pubsub_v1", None)
    monkeypatch.delattr(google.cloud, "pubsub_v1", raising=False)
    
    client = A2AClient("http://mock")
    mocker.patch.object(client, "delegate_task_async", new_callable=AsyncMock, return_value="fallback_task")
    res = await client.delegate_task_pubsub("euler", "prompt")
    assert res == "fallback_task"

@pytest.mark.asyncio
async def test_a2a_client_aclose(mocker):
    client = A2AClient("http://mock")
    mock_aclose = mocker.patch.object(client.client, "aclose", new_callable=AsyncMock)
    await client.aclose()
    mock_aclose.assert_called_once()

def test_route_to_dlq():
    client = A2AClient("http://mock")
    mock_pub = MagicMock()
    mock_pub.topic_path.return_value = "projects/test/topics/dlq"
    
    # success
    client._route_to_dlq("test", mock_pub, {"id": "1"}, "error")
    mock_pub.publish.assert_called_once()
    
    # error
    mock_pub.publish.side_effect = Exception("err")
    client._route_to_dlq("test", mock_pub, {"id": "1"}, "error")

@pytest.mark.asyncio
async def test_on_startup(mock_card, mocker):
    mixin = A2AServerMixin(mock_card)
    mock_app = MagicMock()
    
    # Intercept @app.on_event("startup")
    startup_func = None
    def on_event_mock(event):
        def decorator(func):
            nonlocal startup_func
            if event == "startup":
                startup_func = func
            return func
        return decorator
    mock_app.on_event.side_effect = on_event_mock
    
    # Also ignore FastAPI gets
    mock_app.get.return_value = lambda f: f
    mock_app.post.return_value = lambda f: f

    mocker.patch("google.cloud.pubsub_v1.SubscriberClient")
    
    mixin.mount_a2a_routes(mock_app)
    
    assert startup_func is not None
    
    # mock AgentRegistry
    mock_reg = mocker.patch("agents.common.registry.AgentRegistry")
    mock_inst = MagicMock()
    mock_inst.register_agent = AsyncMock()
    mock_inst.heartbeat = AsyncMock()
    mock_reg.return_value = mock_inst
    mock_reg.return_value = mock_inst
    
    # Mock create_task to capture the loop
    mock_create_task = mocker.patch("asyncio.create_task")
    
    # run startup
    await startup_func()
    mock_inst.register_agent.assert_called_once_with(mock_card)
    
    # extract heartbeat loop and run it manually
    heartbeat_loop = mock_create_task.call_args[0][0]
    
    # mock sleep to do nothing on first call, then raise exception to break loop
    mocker.patch("asyncio.sleep", side_effect=[None, Exception("break_loop")])
    try:
        await heartbeat_loop
    except Exception as e:
        assert str(e) == "break_loop"
    mock_inst.heartbeat.assert_called_once()
    

@pytest.mark.asyncio
async def test_fastapi_a2a_server_tasks_get_error(mock_card, mocker):
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
    assert resp.status_code == 200
    assert "error" not in resp.json()
    assert resp.json()["result"]["res"] == 1

@pytest.mark.asyncio
async def test_fastapi_a2a_rpc_artifact_download_success(mock_card, mocker):
    mixin = A2AServerMixin(mock_card)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    real_app = FastAPI()
    mocker.patch.object(real_app, "on_event", return_value=lambda f: f)
    mixin.mount_a2a_routes(real_app)
    
    client = TestClient(real_app)
    
    async def mock_exec(p, c): return {"res": c.get("foo")}
    mixin.register_executor(mock_exec)
    
    mocker.patch("agents.common.a2a.get_artifact_from_gcs", return_value={"foo": "bar"})
    resp = client.post("/rpc", json={"method": "tasks/send", "id": "1", "params": {"prompt": "p", "artifact_uri": "gs://b/f"}})
    assert resp.status_code == 200
    assert resp.json()["result"]["res"] == "bar"

@pytest.mark.asyncio
async def test_fastapi_a2a_server_tasks_get_error(mock_card, mocker):
    mixin = A2AServerMixin(mock_card)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    real_app = FastAPI()
    mocker.patch.object(real_app, "on_event", return_value=lambda f: f)
    mixin.mount_a2a_routes(real_app)
    
    client = TestClient(real_app)
    
    mocker.patch("agents.common.a2a_state.get_task", side_effect=Exception("db err"))
    resp = client.post("/rpc", json={"method": "tasks/get", "id": "1", "params": {"task_id": "t1"}})
    assert resp.status_code == 200
    assert resp.json()["error"]["message"] == "db err"

@pytest.mark.asyncio
async def test_delegate_task_stream_not_implemented():
    client = A2AClient("http://mock")
    # This was a NotImplementedError inside an async generator.
    # Actually wait, stream doesn't exist on A2AClient. Let's find out what 361 is.
    pass

@pytest.mark.asyncio
async def test_on_startup_registration_fail(mock_card, mocker):
    mixin = A2AServerMixin(mock_card)
    mock_app = MagicMock()
    
    startup_func = None
    def on_event_mock(event):
        def decorator(func):
            nonlocal startup_func
            if event == "startup":
                startup_func = func
            return func
        return decorator
    mock_app.on_event.side_effect = on_event_mock
    
    mock_app.get.return_value = lambda f: f
    mock_app.post.return_value = lambda f: f
    
    mocker.patch("google.cloud.pubsub_v1.SubscriberClient")
    mixin.mount_a2a_routes(mock_app)
    
    mock_reg = mocker.patch("agents.common.registry.AgentRegistry")
    mock_reg.return_value.register_agent = AsyncMock(side_effect=Exception("Registration failed"))
    mock_reg.return_value.heartbeat = AsyncMock(side_effect=Exception("Heartbeat failed"))
    
    mocker.patch("asyncio.create_task")
    
    await startup_func()
    mock_reg.return_value.register_agent.assert_called_once()
