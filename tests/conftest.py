import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

# Global fixture to mock httpx to prevent network hangs
@pytest.fixture(autouse=True)
def mock_httpx_clients(mocker, request):
    # Do not mock httpx if test uses TestClient (API tests) or tests a2a protocol explicitly
    exclude_tests = ["test_fastapi", "test_api", "test_rpc", "test_oidc", "test_gcs", "test_health", "test_prove", "test_agent_card"]
    if any(ex in request.node.name for ex in exclude_tests):
        yield
        return

    # Mock synchronous post
    mock_post = mocker.patch("httpx.Client.post", autospec=True)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True, "result": "mocked", "choices": [{"message": {"content": '{"statement": "mocked", "natural_language": "mocked", "lean4_code": "theorem mock : True := trivial", "confidence": 0.8}'}}]}
    mock_post.return_value = mock_resp

    # Mistral uses httpx.post directly
    mock_post_direct = mocker.patch("httpx.post", autospec=True)
    mock_post_direct.return_value = mock_resp
    
    # Mock async post
    mock_async_post = mocker.patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    mock_async_resp = MagicMock()
    mock_async_resp.status_code = 200
    mock_async_resp.json.return_value = {"success": True, "result": "mocked"}
    mock_async_post.return_value = mock_async_resp
    
    # Mock genai client if used directly
    try:
        mock_client = MagicMock()
        mock_generate_content = MagicMock()
        mock_async_generate = AsyncMock()
        mock_response = MagicMock()
        mock_response.text = '{"statement": "mocked", "natural_language": "mocked", "conjecture_type": "STRUCTURAL", "lean4_code": "theorem mock : True := trivial", "confidence": 0.8}'
        mock_generate_content.return_value = mock_response
        mock_async_generate.return_value = mock_response
        mock_client.return_value.models.generate_content = mock_generate_content
        mock_client.return_value.aio = MagicMock()
        mock_client.return_value.aio.models.generate_content = mock_async_generate
        mocker.patch("google.genai.Client", mock_client)
    except Exception:
        pass
        
    yield

# Also mock asyncio subprocess creation to prevent GCP CLI calls from hanging
@pytest.fixture(autouse=True)
def mock_asyncio_subprocess(mocker):
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"mocked output", b"")
    mock_process.returncode = 0
    mocker.patch("asyncio.create_subprocess_exec", return_value=mock_process)
    yield

@pytest.fixture(autouse=True)
def bypass_ssl_cert_file(monkeypatch):
    """Bypass the SSL_CERT_FILE env var to avoid IsADirectoryError when testing."""
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)

@pytest.fixture(autouse=True)
def mock_gcp_clients(mocker):
    """Mock GCP clients globally to prevent background gRPC threads from hanging tests."""
    try:
        mocker.patch("google.cloud.firestore.AsyncClient", autospec=True)
    except Exception:
        pass
    try:
        mocker.patch("google.cloud.pubsub_v1.PublisherClient", autospec=True)
        mocker.patch("google.cloud.pubsub_v1.SubscriberClient", autospec=True)
    except Exception:
        pass
    yield
