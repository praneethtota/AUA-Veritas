"""
core/plugins/google_backend.py — Google Gemini backend plugin.
Uses Google GenAI SDK (NOT OpenAI-compatible — different auth + request format).
Status: Phase 1 — full implementation.
To contribute back to AUA: copy to aua/plugins/prebuilt/google_backend.py
"""
from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator

import httpx

log = logging.getLogger(__name__)

GOOGLE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GoogleBackend:
    """
    Google Gemini backend. Uses the Google Generative Language API.
    NOT OpenAI-compatible — uses a different endpoint and auth pattern.

    Args:
        model_id: e.g. "gemini-1.5-pro" or "gemini-2.0-flash"
        api_key:  Google AI Studio API key (AIza...)
    """

    def __init__(self, model_id: str = "gemini-1.5-pro", api_key: str = "") -> None:
        self.model_id = model_id
        self._api_key = api_key
        self._client = httpx.AsyncClient(timeout=60.0)

    def _endpoint(self, method: str) -> str:
        model = self.model_id.replace(".", "-")
        return f"{GOOGLE_BASE_URL}/models/{model}:{method}?key={self._api_key}"

    def _to_google_request(self, request: dict) -> dict:
        """Convert OpenAI-compatible request to Google format."""
        messages = request.get("messages", [])
        contents = []
        for m in messages:
            role = "user" if m["role"] in ("user", "system") else "model"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
        return {
            "contents": contents,
            "generationConfig": {
                "temperature": request.get("temperature", 0.2),
                "maxOutputTokens": request.get("max_tokens", 2048),
            },
        }

    def _from_google_response(self, response: dict) -> dict:
        """Convert Google response to OpenAI-compatible format."""
        try:
            text = response["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            text = ""
        return {
            "choices": [{"message": {"role": "assistant", "content": text}}],
            "model": self.model_id,
        }

    async def complete(self, request: dict) -> dict:
        payload = self._to_google_request(request)
        try:
            r = await self._client.post(
                self._endpoint("generateContent"),
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            r.raise_for_status()
            return self._from_google_response(r.json())
        except httpx.HTTPStatusError as e:
            log.error("Google API error %d: %s", e.response.status_code, e.response.text[:200])
            raise

    async def stream(self, request: dict) -> AsyncIterator[str]:
        """Streaming completion via Google SSE."""
        import json
        payload = self._to_google_request(request)
        async with self._client.stream(
            "POST",
            self._endpoint("streamGenerateContent"),
            json=payload,
            headers={"Content-Type": "application/json"},
        ) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line.strip() or line.strip() == "[":
                    continue
                try:
                    data = line.lstrip(",").strip()
                    if data in ("[", "]"):
                        continue
                    chunk = json.loads(data)
                    text = chunk["candidates"][0]["content"]["parts"][0]["text"]
                    if text:
                        yield text
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

    async def health(self) -> dict:
        t0 = time.time()
        try:
            payload = {
                "contents": [{"role": "user", "parts": [{"text": "Say ok"}]}],
                "generationConfig": {"maxOutputTokens": 5},
            }
            r = await self._client.post(
                self._endpoint("generateContent"),
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            r.raise_for_status()
            return {"status": "ok", "model": self.model_id,
                    "latency_ms": round((time.time() - t0) * 1000, 1)}
        except Exception as e:
            return {"status": "error", "error": str(e),
                    "latency_ms": round((time.time() - t0) * 1000, 1)}

    async def aclose(self) -> None:
        await self._client.aclose()
