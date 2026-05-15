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
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core.config import (
    KEYCHAIN_SERVICE,
    PROVIDER_KEY_NAMES,
    SUPPORTED_MODELS,
    db_path,
)
from core.router import QueryRequest, VeritasRouter

from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("veritas.api")

# Global router instance
_router: VeritasRouter | None = None


# ── Single-entry keychain helpers ────────────────────────────────────────────
# All API keys stored as ONE JSON blob under account "api-keys".
# macOS asks for the keychain password exactly once per app launch.

import json as _json

KEYCHAIN_ACCOUNT = "api-keys"


def _read_all_keys() -> dict[str, str]:
    """Read all API keys from the single keychain blob. One prompt max."""
    try:
        blob = keyring.get_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT) or "{}"
        return _json.loads(blob)
    except Exception as e:
        log.warning("Keychain read failed: %s", e)
        return {}


def _write_all_keys(keys: dict[str, str]) -> None:
    """Write all API keys back as a single keychain blob."""
    keyring.set_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT, _json.dumps(keys))


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _router
    _router = VeritasRouter(db_path=str(db_path()))

    # Read ALL keys in ONE keychain call → single password prompt on launch
    all_keys = _read_all_keys()
    for key_name, api_key in all_keys.items():
        if not api_key:
            continue
        # Find which provider owns this key_name
        provider = next(
            (p for p, k in PROVIDER_KEY_NAMES.items() if k == key_name), None
        )
        if not provider:
            continue
        for model_id, spec in SUPPORTED_MODELS.items():
            if spec["provider"] == provider:
                _router.load_backend(model_id, api_key)
        log.info("Loaded keys for provider: %s", provider)

    log.info("Veritas router started. Loaded models: %s", _router.loaded_models())
    yield
    log.info("Veritas shutting down")


app = FastAPI(title="AUA-Veritas", version="0.1.0", lifespan=lifespan)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    log.error("Validation error: %s", exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors(), "body": str(exc)})

# Allow file:// (Electron loadFile), localhost Vite dev server, and null origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=r"(http://localhost:\d+|file://.*|null)",
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
    """Save an API key into the single keychain JSON blob, load its models."""
    key_name = PROVIDER_KEY_NAMES.get(req.provider)
    if not key_name:
        raise HTTPException(400, f"Unknown provider: {req.provider}")
    # Read current blob, update this key, write back — single keychain item
    all_keys = _read_all_keys()
    all_keys[key_name] = req.api_key
    _write_all_keys(all_keys)
    # Load models for this provider
    loaded = []
    if _router:
        for model_id, spec in SUPPORTED_MODELS.items():
            if spec["provider"] == req.provider:
                if _router.load_backend(model_id, req.api_key):
                    loaded.append(model_id)
    return {"saved": True, "loaded_models": loaded}


@app.delete("/keys/{provider}")
async def delete_api_key(provider: str):
    """Remove a provider's key from the keychain blob."""
    key_name = PROVIDER_KEY_NAMES.get(provider)
    if not key_name:
        raise HTTPException(400, f"Unknown provider: {provider}")
    all_keys = _read_all_keys()
    all_keys.pop(key_name, None)
    _write_all_keys(all_keys)
    return {"deleted": True}


@app.get("/keys/status")
async def get_key_status():
    """Return which providers have keys stored."""
    all_keys = _read_all_keys()
    return {
        provider: bool(all_keys.get(key_name, ""))
        for provider, key_name in PROVIDER_KEY_NAMES.items()
    }


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
            "model_id": model_id,
            "connected": model_id in loaded,
        }
        for model_id, spec in SUPPORTED_MODELS.items()
    }


# ── Query ─────────────────────────────────────────────────────────────────────

class QueryPayload(BaseModel):
    query: str
    conversation_id: str = "default"
    accuracy_level: str = "balanced"
    enabled_models: list[str] = []
    conversation_history: list[dict] = []

    class Config:
        extra = "allow"  # ignore unknown fields from UI


@app.post("/query")
async def route_query(payload: QueryPayload):  # noqa: C901
    """Route a user query through the selected models."""
    if not _router:
        raise HTTPException(503, "Router not initialized")
    try:
        req = QueryRequest(
            query=payload.query,
            conversation_id=payload.conversation_id,
            accuracy_level=payload.accuracy_level,
            enabled_models=payload.enabled_models,
            conversation_history=payload.conversation_history,
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
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Query route error: %s", exc)
        raise HTTPException(500, detail=str(exc))


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


# ── Memory (corrections) ──────────────────────────────────────────────────────

@app.get("/memory")
async def get_memories(project: str = None, user_id: str = "local"):
    """Return stored corrections for a user, optionally filtered by project scope."""
    if not _router:
        return []
    corrections = _router._state.query(
        "corrections",
        filters={"user_id": user_id},
        limit=200,
    )
    # Exclude superseded
    active = [c for c in corrections if c.get("scope") != "superseded"]
    if project:
        active = [c for c in active if c.get("scope") == "project"]
    return active


@app.patch("/memory/{correction_id}")
async def update_memory(correction_id: str, body: dict):
    """Update a correction (pin, edit instruction)."""
    if not _router:
        raise HTTPException(503, "Router not initialized")
    try:
        updates = []
        params = []
        if "pinned" in body:
            updates.append("scope = ?")
            params.append("project" if body["pinned"] else "project")
        if "corrective_instruction" in body:
            updates.append("corrective_instruction = ?")
            params.append(body["corrective_instruction"])
        if not updates:
            return {"updated": False}
        params.append(correction_id)
        with _router._state._conn() as conn:
            conn.execute(
                f"UPDATE corrections SET {', '.join(updates)} WHERE correction_id = ?",
                params,
            )
        # Handle pinned separately (custom column not in schema yet)
        if "pinned" in body:
            try:
                with _router._state._conn() as conn:
                    conn.execute(
                        "ALTER TABLE corrections ADD COLUMN pinned INTEGER DEFAULT 0"
                    )
            except Exception:
                pass
            with _router._state._conn() as conn:
                conn.execute(
                    "UPDATE corrections SET pinned = ? WHERE correction_id = ?",
                    (1 if body["pinned"] else 0, correction_id),
                )
        return {"updated": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.delete("/memory/{correction_id}")
async def delete_memory(correction_id: str):
    """Soft-delete a correction (set scope to superseded)."""
    if not _router:
        raise HTTPException(503, "Router not initialized")
    _router._scope_resolver._delete_correction(correction_id)
    return {"deleted": True}


# ── Restart prompt ─────────────────────────────────────────────────────────────

@app.get("/restart-prompt")
async def get_restart_prompt(project: str = None, user_id: str = "local"):
    """Generate a restart prompt from active project memories."""
    if not _router:
        return {"veritas_format": "", "ide_format": "", "item_count": 0, "layer_counts": {}}
    from core.restart_prompt import RestartPromptBuilder
    builder = RestartPromptBuilder(_router._state)
    result = builder.build(
        active_project=project,
        user_id=user_id,
        include_global=True,
    )
    return {
        "project": result.project,
        "veritas_format": result.veritas_format,
        "ide_format": result.ide_format,
        "item_count": result.item_count,
        "layer_counts": result.layer_counts,
    }


# ── Projects ───────────────────────────────────────────────────────────────────

@app.get("/projects")
async def list_projects(user_id: str = "local"):
    """List all projects for a user."""
    if not _router:
        return []
    try:
        return _router._state.query("projects", filters={"user_id": user_id}, limit=100)
    except Exception:
        # projects table might not exist yet — return empty
        return []


@app.post("/projects")
async def create_project(body: dict, user_id: str = "local"):
    """Create a new project."""
    import uuid, time
    if not _router:
        raise HTTPException(503, "Router not initialized")
    project_id = str(uuid.uuid4())
    try:
        # Create projects table if not exists
        with _router._state._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT 'local',
                    name TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
        _router._state.append("projects", {
            "project_id": project_id,
            "user_id": user_id,
            "name": body.get("name", "New Project"),
            "created_at": time.time(),
        })
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"project_id": project_id, "name": body.get("name", "New Project")}


# ── Look Under the Hood — model reliability history ───────────────────────────

@app.get("/reliability")
async def get_reliability():
    """
    Return per-model reliability score history for the Look Under the Hood panel.
    Returns models with their audit_log events, sorted by created_at asc.
    """
    if not _router:
        return []
    try:
        from core.config import SUPPORTED_MODELS
        events = _router._state.query("audit_log", filters={"event_type": "score_update"}, limit=500)
        # Group by model_id
        model_events: dict[str, list] = {}
        for e in sorted(events, key=lambda x: x.get("created_at", 0)):
            mid = e.get("model_id", "")
            if mid:
                model_events.setdefault(mid, []).append(e)

        result = []
        for model_id, evts in model_events.items():
            if not evts:
                continue
            scores = [e.get("score_after", 70) for e in evts]
            current = scores[-1] if scores else 70
            trend = "up" if len(scores) >= 2 and scores[-1] > scores[-2] else \
                    "down" if len(scores) >= 2 and scores[-1] < scores[-2] else "flat"
            spec = SUPPORTED_MODELS.get(model_id, {})
            result.append({
                "model_id": model_id,
                "display_name": spec.get("display_name", model_id),
                "events": evts,
                "current_score": current,
                "trend": trend,
            })
        return result
    except Exception as e:
        log.error("reliability endpoint error: %s", e)
        return []


# ── Usage statistics ──────────────────────────────────────────────────────────

@app.get("/usage")
async def get_usage():
    """Return per-model query counts and estimated costs."""
    if not _router:
        return {"models": [], "total_cost": 0, "total_queries": 0}
    try:
        from core.config import SUPPORTED_MODELS
        runs = _router._state.query("model_runs", limit=5000)
        model_counts: dict[str, dict] = {}
        for r in runs:
            mid = r.get("model_id", "")
            if not mid:
                continue
            if mid not in model_counts:
                model_counts[mid] = {"count": 0, "last_used": None}
            model_counts[mid]["count"] += 1
            ts = r.get("created_at")
            if ts and (not model_counts[mid]["last_used"] or ts > model_counts[mid]["last_used"]):
                model_counts[mid]["last_used"] = ts

        models_out = []
        total_cost = 0.0
        total_queries = 0
        for model_id, data in model_counts.items():
            count = data["count"]
            spec = SUPPORTED_MODELS.get(model_id, {})
            is_judge = spec.get("is_cheap_judge", False)
            cost_per = 0.001 if is_judge else 0.01
            cost = count * cost_per
            total_cost += cost
            total_queries += count
            models_out.append({
                "model_id": model_id,
                "display_name": spec.get("display_name", model_id),
                "query_count": count,
                "estimated_cost": round(cost, 6),
                "last_used": data["last_used"],
            })

        models_out.sort(key=lambda x: -x["query_count"])
        return {
            "models": models_out,
            "total_cost": round(total_cost, 6),
            "total_queries": total_queries,
        }
    except Exception as e:
        log.error("usage endpoint error: %s", e)
        return {"models": [], "total_cost": 0, "total_queries": 0}
