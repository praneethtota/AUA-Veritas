"""Tests for DeepSeekBackend."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from core.plugins.deepseek_backend import DeepSeekBackend


@pytest.fixture
def backend():
    return DeepSeekBackend(model_id="deepseek-chat", api_key="sk-ds-test")


@pytest.fixture
def reasoner():
    return DeepSeekBackend(model_id="deepseek-reasoner", api_key="sk-ds-test")


def test_base_url(backend):
    assert "deepseek.com" in str(backend._client.base_url)


def test_default_model():
    b = DeepSeekBackend(api_key="sk-test")
    assert b.model_id == "deepseek-chat"


def test_reasoner_model(reasoner):
    assert reasoner.model_id == "deepseek-reasoner"


@pytest.mark.asyncio
async def test_health_ok(backend):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "ok"}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(backend._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await backend.health()

    assert result["status"] == "ok"
    assert result["model"] == "deepseek-chat"
    assert "cheaper" in result["note"].lower()


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
async def test_health_insufficient_credits(backend):
    mock_response = MagicMock()
    mock_response.status_code = 402
    mock_response.text = "Payment required"

    with patch.object(backend._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.HTTPStatusError(
            "402", request=MagicMock(), response=mock_response
        )
        result = await backend.health()

    assert result["status"] == "error"
    assert "credits" in result["error"].lower()


@pytest.mark.asyncio
async def test_health_server_overloaded(backend):
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_response.text = "Service unavailable"

    with patch.object(backend._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.HTTPStatusError(
            "503", request=MagicMock(), response=mock_response
        )
        result = await backend.health()

    assert result["status"] == "error"
    assert "overloaded" in result["error"].lower()


@pytest.mark.asyncio
async def test_complete_strips_reasoning_content(reasoner):
    """deepseek-reasoner returns reasoning_content — verify it's stripped."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "The answer is 42.",
                "reasoning_content": "Let me think step by step... (long chain of thought)",
            }
        }]
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(reasoner._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await reasoner.complete({
            "messages": [{"role": "user", "content": "What is 6 × 7?"}]
        })

    msg = result["choices"][0]["message"]
    assert msg["content"] == "The answer is 42."
    assert "reasoning_content" not in msg


@pytest.mark.asyncio
async def test_complete_normal_model_unaffected(backend):
    """Non-reasoner model response passes through unchanged."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "DeepSeek says hi."}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(backend._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await backend.complete({
            "messages": [{"role": "user", "content": "hello"}]
        })
        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == "deepseek-chat"

    assert result["choices"][0]["message"]["content"] == "DeepSeek says hi."
