"""Tests for GoogleBackend — request/response conversion and error handling."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.plugins.google_backend import GoogleBackend


@pytest.fixture
def backend():
    return GoogleBackend(model_id="gemini-1.5-pro", api_key="AIza-test")


# ── URL construction ──────────────────────────────────────────────────────────

def test_url_includes_api_key(backend):
    url = backend._url("generateContent")
    assert "key=AIza-test" in url
    assert "generateContent" in url
    assert "gemini-1.5-pro" in url


def test_url_stream_endpoint(backend):
    url = backend._url("streamGenerateContent")
    assert "streamGenerateContent" in url


# ── Request conversion ────────────────────────────────────────────────────────

def test_to_google_simple_user_message():
    req = {"messages": [{"role": "user", "content": "Hello"}], "max_tokens": 100}
    payload = GoogleBackend._to_google(req)
    assert payload["contents"][0]["role"] == "user"
    assert payload["contents"][0]["parts"][0]["text"] == "Hello"
    assert payload["generationConfig"]["maxOutputTokens"] == 100


def test_to_google_assistant_becomes_model():
    req = {"messages": [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello there"},
    ]}
    payload = GoogleBackend._to_google(req)
    assert payload["contents"][1]["role"] == "model"


def test_to_google_system_prepended_to_first_user():
    req = {"messages": [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Explain VCG."},
    ]}
    payload = GoogleBackend._to_google(req)
    # System role removed, content prepended to first user turn
    assert len(payload["contents"]) == 1
    assert "You are helpful." in payload["contents"][0]["parts"][0]["text"]
    assert "Explain VCG." in payload["contents"][0]["parts"][0]["text"]


def test_to_google_temperature_passed():
    req = {"messages": [{"role": "user", "content": "x"}], "temperature": 0.7}
    payload = GoogleBackend._to_google(req)
    assert payload["generationConfig"]["temperature"] == 0.7


def test_to_google_no_gen_config_when_no_params():
    req = {"messages": [{"role": "user", "content": "x"}]}
    payload = GoogleBackend._to_google(req)
    assert "generationConfig" not in payload


# ── Response conversion ───────────────────────────────────────────────────────

def test_from_google_extracts_text():
    google_resp = {
        "candidates": [{
            "content": {"parts": [{"text": "Here is the answer."}]}
        }]
    }
    result = GoogleBackend._from_google(google_resp)
    assert result["choices"][0]["message"]["content"] == "Here is the answer."
    assert result["choices"][0]["message"]["role"] == "assistant"


def test_from_google_safety_blocked():
    google_resp = {
        "candidates": [{"finishReason": "SAFETY"}]
    }
    result = GoogleBackend._from_google(google_resp)
    assert "blocked" in result["choices"][0]["message"]["content"].lower()


def test_from_google_empty_candidates():
    result = GoogleBackend._from_google({"candidates": []})
    assert result["choices"][0]["message"]["content"] == ""


def test_from_google_missing_candidates():
    result = GoogleBackend._from_google({})
    assert result["choices"][0]["message"]["content"] == ""


# ── Health check ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_ok(backend):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "ok"}]}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(backend._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await backend.health()

    assert result["status"] == "ok"
    assert result["model"] == "gemini-1.5-pro"
    assert "latency_ms" in result


@pytest.mark.asyncio
async def test_health_invalid_key(backend):
    import httpx

    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.text = "API key invalid"

    with patch.object(backend._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.HTTPStatusError(
            "403", request=MagicMock(), response=mock_response
        )
        result = await backend.health()

    assert result["status"] == "error"
    assert "key" in result["error"].lower() or "quota" in result["error"].lower()


@pytest.mark.asyncio
async def test_health_model_not_found(backend):
    import httpx

    bad_backend = GoogleBackend(model_id="gemini-99-fake", api_key="AIza-test")
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Model not found"

    with patch.object(bad_backend._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_response
        )
        result = await bad_backend.health()

    assert result["status"] == "error"
    assert "not found" in result["error"].lower()


# ── complete() ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_complete_returns_openai_format(backend):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "Gemini says hello."}]}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(backend._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await backend.complete({
            "messages": [{"role": "user", "content": "hello"}]
        })

    assert result["choices"][0]["message"]["content"] == "Gemini says hello."
