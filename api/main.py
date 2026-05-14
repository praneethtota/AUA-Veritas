"""
api/main.py — AUA-Veritas FastAPI server.

Runs headless, started by Electron on app launch.
Port: 47821 (chosen to avoid conflicts with common dev ports).
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import keyring
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.config import (
    KEYCHAIN_SERVICE,
    PROVIDER_KEY_NAMES,
    SUPPORTED_MODELS,
    db_path,
)
from core.router import QueryRequest, VeritasRouter

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("veritas.api")

# Global router instance
_router: VeritasRouter | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _router
    _router = VeritasRouter(db_path=str(db_path()))
    # Load any models whose API keys are already in the keychain
    for model_id, spec in SUPPORTED_MODELS.items():
        key_name = PROVIDER_KEY_NAMES.get(spec["provider"])
        if key_name:
            api_key = keyring.get_password(KEYCHAIN_SERVICE, key_name) or ""
            if api_key:
                _router.load_backend(model_id, api_key)
    log.info("Veritas router started. Loaded models: %s", _router.loaded_models())
    yield
    log.info("Veritas shutting down")


app = FastAPI(title="AUA-Veritas", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:47822"],  # Electron renderer
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "loaded_models": _router.loaded_models() if _router else []}


# ── API Keys ──────────────────────────────────────────────────────────────────

class ApiKeyRequest(BaseModel):
    provider: str
    api_key: str


@app.post("/keys/save")
async def save_api_key(req: ApiKeyRequest):
    """Save an API key to the OS keychain and load its models."""
    key_name = PROVIDER_KEY_NAMES.get(req.provider)
    if not key_name:
        raise HTTPException(400, f"Unknown provider: {req.provider}")
    keyring.set_password(KEYCHAIN_SERVICE, key_name, req.api_key)
    # Load all models for this provider
    loaded = []
    for model_id, spec in SUPPORTED_MODELS.items():
        if spec["provider"] == req.provider:
            success = _router.load_backend(model_id, req.api_key)
            if success:
                loaded.append(model_id)
    return {"saved": True, "loaded_models": loaded}


@app.delete("/keys/{provider}")
async def delete_api_key(provider: str):
    """Remove an API key from the OS keychain."""
    key_name = PROVIDER_KEY_NAMES.get(provider)
    if not key_name:
        raise HTTPException(400, f"Unknown provider: {provider}")
    keyring.delete_password(KEYCHAIN_SERVICE, key_name)
    return {"deleted": True}


@app.get("/keys/status")
async def key_status():
    """Return which providers have API keys saved."""
    status = {}
    for provider, key_name in PROVIDER_KEY_NAMES.items():
        key = keyring.get_password(KEYCHAIN_SERVICE, key_name)
        status[provider] = bool(key)
    return status


@app.post("/keys/test/{model_id}")
async def test_model_connection(model_id: str):
    """Test that a model's API key works."""
    backend = _router._backends.get(model_id)
    if not backend:
        return {"status": "not_connected", "model_id": model_id}
    result = await backend.health()
    return result


# ── Models ────────────────────────────────────────────────────────────────────

@app.get("/models")
async def list_models():
    """Return all supported models with their connection status."""
    loaded = set(_router.loaded_models()) if _router else set()
    return {
        model_id: {
            **spec,
            "connected": model_id in loaded,
        }
        for model_id, spec in SUPPORTED_MODELS.items()
    }


# ── Query ─────────────────────────────────────────────────────────────────────

class QueryPayload(BaseModel):
    query: str
    conversation_id: str
    accuracy_level: str = "balanced"
    enabled_models: list[str] = []


@app.post("/query")
async def route_query(payload: QueryPayload):
    """Route a user query through the selected models."""
    if not _router:
        raise HTTPException(503, "Router not initialized")
    req = QueryRequest(
        query=payload.query,
        conversation_id=payload.conversation_id,
        accuracy_level=payload.accuracy_level,
        enabled_models=payload.enabled_models,
    )
    result = await _router.route(req)
    return {
        "response": result.response,
        "primary_model": result.primary_model,
        "all_models_used": result.all_models_used,
        "confidence_label": result.confidence_label,
        "callout_type": result.callout_type,
        "callout_text": result.callout_text,
        "welfare_scores": result.welfare_scores,
        "peer_review_used": result.peer_review_used,
        "corrections_applied": result.corrections_applied,
        "latency_ms": result.latency_ms,
    }


# ── Conversations ─────────────────────────────────────────────────────────────

@app.get("/conversations")
async def list_conversations():
    return _router._state.query("conversations", limit=100)


@app.post("/conversations")
async def create_conversation(body: dict):
    import uuid, time
    conv_id = str(uuid.uuid4())
    _router._state.append("conversations", {
        "conversation_id": conv_id,
        "title": body.get("title", "New Chat"),
        "created_at": time.time(),
        "updated_at": time.time(),
    })
    return {"conversation_id": conv_id}


@app.get("/conversations/{conv_id}/messages")
async def get_messages(conv_id: str):
    return _router._state.query("messages", filters={"conversation_id": conv_id}, limit=500)
