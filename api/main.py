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
            "disagreement_options": result.disagreement_options if hasattr(result, "disagreement_options") else None,
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


# ── Full analytics dashboard ─────────────────────────────────────────────────

@app.get("/analytics")
async def get_analytics():
    """
    Comprehensive analytics for the Look Under the Hood dashboard.
    Returns model stats, confidence distribution, correction stats,
    domain distribution, recent decision traces, and VCG data.
    """
    if not _router:
        return {}
    try:
        from core.config import SUPPORTED_MODELS
        import time as _time

        runs   = _router._state.query("model_runs",  limit=5000)
        audits = _router._state.query("audit_log",   limit=5000)
        corrs  = _router._state.query("corrections",  limit=1000)
        convs  = _router._state.query("conversations", limit=1000)

        loaded = set(_router.loaded_models())

        # ── Per-model stats ───────────────────────────────────────────────────
        model_stats: dict[str, dict] = {}
        for mid in SUPPORTED_MODELS:
            model_stats[mid] = {
                "model_id":     mid,
                "display_name": SUPPORTED_MODELS[mid].get("display_name", mid),
                "connected":    mid in loaded,
                "is_judge":     SUPPORTED_MODELS[mid].get("is_cheap_judge", False),
                "total_runs":   0,
                "winner_count": 0,
                "total_latency_ms": 0.0,
                "welfare_scores":   [],
                "confidence_scores": [],
            }

        for r in runs:
            mid = r.get("model_id", "")
            if mid not in model_stats:
                continue
            model_stats[mid]["total_runs"] += 1
            if r.get("vcg_winner"):
                model_stats[mid]["winner_count"] += 1
            lat = r.get("latency_ms")
            if lat:
                model_stats[mid]["total_latency_ms"] += lat
            ws = r.get("vcg_welfare_score")
            if ws is not None:
                model_stats[mid]["welfare_scores"].append(ws)
            cs = r.get("confidence_score")
            if cs is not None:
                model_stats[mid]["confidence_scores"].append(cs)

        models_out = []
        for mid, s in model_stats.items():
            if not s["connected"] and s["total_runs"] == 0:
                continue
            # Reliability score from audit_log
            model_audits = [a for a in audits if a.get("model_id") == mid]
            current_score = 70
            if model_audits:
                latest = max(model_audits, key=lambda a: a.get("created_at", 0))
                current_score = latest.get("score_after", 70)
            n = s["total_runs"] or 1
            avg_ws = round(sum(s["welfare_scores"]) / len(s["welfare_scores"]), 3) if s["welfare_scores"] else None
            avg_lat = round(s["total_latency_ms"] / n, 1) if s["total_runs"] else None
            win_rate = round(s["winner_count"] / n * 100, 1) if s["total_runs"] else 0
            # Score events for mini sparkline
            events = sorted([a for a in audits if a.get("model_id") == mid],
                            key=lambda a: a.get("created_at", 0))
            trend = "flat"
            if len(events) >= 2:
                trend = ("up" if events[-1].get("score_after", 70) > events[-2].get("score_after", 70)
                         else "down" if events[-1].get("score_after", 70) < events[-2].get("score_after", 70)
                         else "flat")
            models_out.append({
                "model_id":       mid,
                "display_name":   s["display_name"],
                "connected":      s["connected"],
                "is_judge":       s["is_judge"],
                "reliability_score": current_score,
                "trend":          trend,
                "total_runs":     s["total_runs"],
                "winner_count":   s["winner_count"],
                "win_rate_pct":   win_rate,
                "avg_latency_ms": avg_lat,
                "avg_welfare_score": avg_ws,
                "score_events":   events[-20:],  # last 20 for sparkline
            })
        models_out.sort(key=lambda m: -m["reliability_score"])

        # ── Confidence distribution ───────────────────────────────────────────
        winner_runs   = [r for r in runs if r.get("vcg_winner")]
        conf_hi = conf_med = conf_lo = 0
        for r in winner_runs:
            cs = r.get("confidence_score", 0.5)
            if cs >= 0.75:  conf_hi  += 1
            elif cs >= 0.50: conf_med += 1
            else:            conf_lo  += 1
        total_answered = len(winner_runs) or 1

        # ── Correction stats ──────────────────────────────────────────────────
        active_corrs = [c for c in corrs if c.get("scope") != "superseded"]
        corr_by_type: dict[str, int] = {}
        corr_by_domain: dict[str, int] = {}
        for c in active_corrs:
            t = c.get("type", "unknown")
            d = c.get("domain", "general")
            corr_by_type[t]   = corr_by_type.get(t, 0) + 1
            corr_by_domain[d] = corr_by_domain.get(d, 0) + 1

        # ── Domain distribution ───────────────────────────────────────────────
        domain_counts: dict[str, int] = {}
        for r in winner_runs:
            # infer domain from canonical_query of matching correction if possible
            pass  # approximated from corrections
        for c in corrs:
            d = c.get("domain", "general")
            domain_counts[d] = domain_counts.get(d, 0) + 1

        # ── Recent decision traces (from model_runs, grouped by query_id) ─────
        from itertools import groupby
        query_groups: dict[str, list] = {}
        for r in sorted(runs, key=lambda x: x.get("created_at", 0), reverse=True):
            qid = r.get("query_id", "")
            if qid:
                query_groups.setdefault(qid, []).append(r)
        recent_decisions = []
        for qid, qruns in list(query_groups.items())[:15]:
            winner = next((r for r in qruns if r.get("vcg_winner")), qruns[0] if qruns else {})
            all_mids = [r.get("model_id", "") for r in qruns]
            # Map corrections applied
            corr_ids_raw = winner.get("corrections_applied", "[]")
            try:
                import ast
                corr_ids = ast.literal_eval(corr_ids_raw) if isinstance(corr_ids_raw, str) else corr_ids_raw
            except Exception:
                corr_ids = []
            applied_corrs = [c for c in corrs if c.get("correction_id") in corr_ids]
            recent_decisions.append({
                "query_id":           qid,
                "created_at":         winner.get("created_at"),
                "winner_model":       winner.get("model_id", ""),
                "all_models":         list(dict.fromkeys(all_mids)),
                "confidence_score":   winner.get("confidence_score"),
                "vcg_welfare_score":  winner.get("vcg_welfare_score"),
                "latency_ms":         winner.get("latency_ms"),
                "corrections_applied": [{
                    "type":  c.get("type"),
                    "scope": c.get("scope"),
                    "instruction": (c.get("corrective_instruction") or "")[:120],
                } for c in applied_corrs],
                "peer_review":        any(r.get("round") == "peer_review" for r in qruns),
            })

        # ── VCG welfare score distribution ────────────────────────────────────
        all_welfare = [r.get("vcg_welfare_score") for r in runs if r.get("vcg_welfare_score") is not None]
        welfare_avg = round(sum(all_welfare) / len(all_welfare), 3) if all_welfare else None
        welfare_max = round(max(all_welfare), 3) if all_welfare else None
        welfare_min = round(min(all_welfare), 3) if all_welfare else None

        return {
            "models":               models_out,
            "confidence_dist":      {"high": conf_hi, "medium": conf_med, "uncertain": conf_lo, "total": total_answered},
            "correction_stats":     {"total_active": len(active_corrs), "by_type": corr_by_type, "by_domain": corr_by_domain},
            "domain_dist":          domain_counts,
            "recent_decisions":     recent_decisions,
            "welfare_summary":      {"avg": welfare_avg, "max": welfare_max, "min": welfare_min, "total_scored": len(all_welfare)},
            "total_conversations":  len(convs),
            "total_model_runs":     len(runs),
        }
    except Exception as e:
        log.error("analytics error: %s", e, exc_info=True)
        return {}


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


# ── Streaming query (Fast mode SSE) ──────────────────────────────────────────

from fastapi.responses import StreamingResponse as _StreamingResponse


@app.post("/query/stream")
async def stream_query(payload: QueryPayload):
    """
    Fast-mode streaming endpoint. Returns Server-Sent Events.
    Streams tokens live as they arrive from the selected model.
    Falls back gracefully if the backend does not support streaming.

    SSE format:
      data: {"type": "token", "text": "..."}
      data: {"type": "done", "response": {...}}
      data: [DONE]
    """
    if not _router:
        raise HTTPException(503, "Router not initialized")

    async def event_generator():
        import json as _j
        import time as _t
        try:
            # Pick first enabled non-judge model
            loaded = set(_router.loaded_models())
            enabled = [m for m in (payload.enabled_models or []) if m in loaded]
            if not enabled:
                enabled = [
                    m for m in loaded
                    if not SUPPORTED_MODELS.get(m, {}).get("is_cheap_judge", False)
                ]
            if not enabled:
                yield f"data: {_j.dumps({'type': 'done', 'response': {'response': 'No models connected. Please add an API key in Settings.', 'primary_model': '', 'all_models_used': [], 'confidence_label': 'Uncertain', 'callout_type': None, 'callout_text': None, 'welfare_scores': None, 'peer_review_used': False, 'corrections_applied': [], 'latency_ms': 0}})}\n\n"
                yield "data: [DONE]\n\n"
                return

            model_id = enabled[0]
            backend  = _router._backends.get(model_id)

            if not backend or not hasattr(backend, "stream"):
                # No stream() method — run full route, fake-stream result
                req = QueryRequest(
                    query=payload.query,
                    conversation_id=payload.conversation_id,
                    accuracy_level="fast",
                    enabled_models=enabled,
                    conversation_history=payload.conversation_history,
                )
                result = await _router.route(req)
                yield f"data: {_j.dumps({'type': 'token', 'text': result.response})}\n\n"
                yield f"data: {_j.dumps({'type': 'done', 'response': {'response': result.response, 'primary_model': result.primary_model, 'all_models_used': result.all_models_used, 'confidence_label': result.confidence_label, 'callout_type': result.callout_type, 'callout_text': result.callout_text, 'welfare_scores': result.welfare_scores, 'peer_review_used': result.peer_review_used, 'corrections_applied': result.corrections_applied, 'latency_ms': result.latency_ms}})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # Build prompt with injected corrections
            t0 = _t.time()
            from core.field_classifier import FieldClassifier as _FC
            domain_dist = _FC().classify(payload.query)
            primary_domain = max(domain_dist, key=lambda k: domain_dist[k])
            corrections = _router._memory.retrieve(query=payload.query, domain=primary_domain)
            from core.include_utility import IncludeUtilityScorer as _IU
            selected = _IU().select(
                query=payload.query, domain=primary_domain,
                corrections=corrections,
                active_project=payload.conversation_id, max_corrections=5,
            )
            prompt = _router._build_prompt(payload.query, selected, primary_domain)

            messages = []
            for h in (payload.conversation_history or []):
                if h.get("role") in ("user", "assistant"):
                    messages.append({"role": h["role"], "content": h["content"]})
            messages.append({"role": "user", "content": prompt})

            full_text = ""
            async for token in backend.stream({"messages": messages, "temperature": 0.7, "max_tokens": 2048}):
                if token:
                    full_text += token
                    yield f"data: {_j.dumps({'type': 'token', 'text': token})}\n\n"

            latency_ms = round((_t.time() - t0) * 1000, 1)
            corr_ids = [c.get("correction_id", "") for c in selected]
            yield f"data: {_j.dumps({'type': 'done', 'response': {'response': full_text, 'primary_model': model_id, 'all_models_used': [model_id], 'confidence_label': 'Medium', 'callout_type': None, 'callout_text': None, 'welfare_scores': None, 'peer_review_used': False, 'corrections_applied': corr_ids, 'latency_ms': latency_ms}})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            log.exception("Stream error: %s", e)
            import json as _je
            yield f"data: {_je.dumps({'type': 'error', 'message': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    return _StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
