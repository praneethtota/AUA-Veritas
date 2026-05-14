"""Tests for GroqBackend."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from core.plugins.groq_backend import GroqBackend, GROQ_CONTEXT_LIMITS


@pytest.fixture
def backend():
    return GroqBackend(model_id="llama-3.3-70b-versatile", api_key="gsk-test")


def test_base_url(backend):
    assert "groq.com" in str(backend._client.base_url)


def test_default_model():
    b = GroqBackend(api_key="gsk-test")
    assert b.model_id == "llama-3.3-70b-versatile"


def test_context_window_known_model(backend):
    assert backend.context_window == 128_000


def test_context_window_unknown_model():
    b = GroqBackend(model_id="unknown-model", api_key="gsk-test")
    assert b.context_window == 8_192  # safe default


def test_context_limits_table():
    assert GROQ_CONTEXT_LIMITS["mixtral-8x7b-32768"] == 32_768
    assert GROQ_CONTEXT_LIMITS["llama-3.1-8b-instant"] == 128_000


@pytest.mark.asyncio
async def test_health_ok(backend):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {"id": "llama-3.3-70b-versatile"},
            {"id": "llama-3.1-8b-instant"},
        ]
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(backend._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        result = await backend.health()

    assert result["status"] == "ok"
    assert result["model"] == "llama-3.3-70b-versatile"
    assert result["context_window"] == 128_000
    assert "free tier" in result["note"].lower()


@pytest.mark.asyncio
async def test_health_model_not_available(backend):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [{"id": "llama-3.1-8b-instant"}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(backend._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        result = await backend.health()

    assert result["status"] == "error"
    assert "not available" in result["error"]
    assert "llama-3.1-8b-instant" in result["error"]


@pytest.mark.asyncio
async def test_health_invalid_key(backend):
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Invalid API Key"

    with patch.object(backend._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_response
        )
        result = await backend.health()

    assert result["status"] == "error"
    assert "key" in result["error"].lower()


@pytest.mark.asyncio
async def test_health_rate_limited(backend):
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.text = "Rate limit exceeded"

    with patch.object(backend._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.HTTPStatusError(
            "429", request=MagicMock(), response=mock_response
        )
        result = await backend.health()

    assert result["status"] == "error"
    assert "rate limit" in result["error"].lower()


@pytest.mark.asyncio
async def test_complete_injects_model(backend):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "Llama says hi."}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(backend._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await backend.complete({
            "messages": [{"role": "user", "content": "hello"}]
        })
        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == "llama-3.3-70b-versatile"

    assert result["choices"][0]["message"]["content"] == "Llama says hi."
