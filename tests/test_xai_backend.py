"""Tests for XAIBackend."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from core.plugins.xai_backend import XAIBackend


@pytest.fixture
def backend():
    return XAIBackend(model_id="grok-2", api_key="xai-test")


def test_inherits_openai_base_url(backend):
    assert "x.ai" in str(backend._client.base_url)


def test_default_model():
    b = XAIBackend(api_key="xai-test")
    assert b.model_id == "grok-2"


def test_custom_model():
    b = XAIBackend(model_id="grok-2-mini", api_key="xai-test")
    assert b.model_id == "grok-2-mini"


@pytest.mark.asyncio
async def test_health_ok(backend):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "ok"}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(backend._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await backend.health()

    assert result["status"] == "ok"
    assert result["model"] == "grok-2"


@pytest.mark.asyncio
async def test_health_invalid_key(backend):
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    with patch.object(backend._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_response
        )
        result = await backend.health()

    assert result["status"] == "error"
    assert "key" in result["error"].lower()


@pytest.mark.asyncio
async def test_health_rate_limited(backend):
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.text = "Too many requests"

    with patch.object(backend._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.HTTPStatusError(
            "429", request=MagicMock(), response=mock_response
        )
        result = await backend.health()

    assert result["status"] == "error"
    assert "rate" in result["error"].lower()


@pytest.mark.asyncio
async def test_complete_uses_openai_format(backend):
    """complete() is inherited from OpenAIBackend — verify it uses correct model."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "Grok says hi."}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(backend._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await backend.complete({
            "messages": [{"role": "user", "content": "hello"}]
        })
        # Verify model_id is injected
        call_payload = mock_post.call_args[1]["json"]
        assert call_payload["model"] == "grok-2"

    assert result["choices"][0]["message"]["content"] == "Grok says hi."
