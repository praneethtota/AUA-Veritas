"""Tests for MistralBackend."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from core.plugins.mistral_backend import MistralBackend


@pytest.fixture
def backend():
    return MistralBackend(model_id="mistral-large-latest", api_key="ms-test")


def test_base_url(backend):
    assert "mistral.ai" in str(backend._client.base_url)


def test_default_model():
    b = MistralBackend(api_key="ms-test")
    assert b.model_id == "mistral-large-latest"


@pytest.mark.asyncio
async def test_health_ok(backend):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [{"id": "mistral-large-latest"}, {"id": "mistral-small-latest"}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(backend._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        result = await backend.health()

    assert result["status"] == "ok"
    assert result["model"] == "mistral-large-latest"


@pytest.mark.asyncio
async def test_health_model_not_in_account(backend):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [{"id": "mistral-small-latest"}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(backend._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        result = await backend.health()

    assert result["status"] == "error"
    assert "not in" in result["error"]


@pytest.mark.asyncio
async def test_health_invalid_key(backend):
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    with patch.object(backend._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_response
        )
        result = await backend.health()

    assert result["status"] == "error"
    assert "key" in result["error"].lower()


@pytest.mark.asyncio
async def test_complete_injects_model(backend):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "Mistral says hi."}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(backend._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await backend.complete({
            "messages": [{"role": "user", "content": "hello"}]
        })
        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == "mistral-large-latest"
    assert result["choices"][0]["message"]["content"] == "Mistral says hi."
