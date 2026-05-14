# AUA-Veritas — Copy Log

This document records every file copied from the AUA Framework repo into AUA-Veritas.

**Rule:** After this initial copy, no further files may be copied from the AUA repo
(`praneethtota/Adaptive-Utility-Agent`) without explicit user permission. All future
changes to these files happen in AUA-Veritas only — the AUA source is never modified
from this project.

---

## Initial copy — 2026-05-14

Source repo: `https://github.com/praneethtota/Adaptive-Utility-Agent`
Source commit at time of copy: see AUA repo at this date

| Source (AUA repo) | Destination (Veritas) | Purpose |
|---|---|---|
| `aua/arbiter.py` | `core/arbiter.py` | 4-check contradiction detection + peer review |
| `aua/assertions_store.py` | `core/memory.py` | Correction memory store (modified: per-user scope) |
| `aua/contradiction_detector.py` | `core/validator.py` | Response validation logic |
| `aua/state.py` | `core/state.py` | SQLite state (modified: simplified schema) |
| `aua/guard.py` | `core/guard.py` | Assertions engine (BLOCKING/SOFT/INFO levels) |
| `aua/policy.py` | `core/policy.py` | Policy system + YAML loader |
| `aua/plugins/interfaces.py` | `core/interfaces.py` | ModelBackendPlugin Protocol |
| `aua/field_classifier.py` | `core/field_classifier.py` | Domain classification |
| `aua/utility_scorer.py` | `core/utility_scorer.py` | U = w_e·E + w_c·C + w_k·K |
| `aua/confidence_updater.py` | `core/confidence_updater.py` | Kalman confidence tracking |
| `aua/secrets.py` | `core/secrets.py` | API key resolution (modified: OS keychain) |
| `aua/session.py` | `core/session.py` | Session context management |
| `aua/hooks.py` | `core/hooks.py` | Lifecycle hook system |
| `aua/correction_loop.py` | `core/correction_loop.py` | DPO pair accumulation |

## Files NOT copied (written fresh for Veritas)

| File | Reason |
|---|---|
| `aua/router.py` | Too AUA-specific (vLLM/Ollama plumbing). Veritas router written fresh. |
| `aua/blue_green.py` | Not applicable — no model deployment in Veritas |
| `aua/rollback.py` | Not applicable |
| `aua/serve.py` | Replaced by Electron process management |
| `aua/cli.py` | No CLI in Veritas — Electron handles startup |
| `aua/auth.py` | Single user — no token auth needed |
| `aua/otel.py` | Not needed in v1 |
| `aua/eval.py` | Not needed in v1 |
| `aua/metrics.py` | Simplified version written fresh |
| `aua/config.py` | Simplified config written fresh for Veritas |

## Future copies from AUA

Any future copy from `praneethtota/Adaptive-Utility-Agent` must be logged here
with explicit user approval noted.

| Date | File | Approved by | Reason |
|---|---|---|---|
| (none yet) | | | |
