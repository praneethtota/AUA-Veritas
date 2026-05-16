# AUA-Veritas Bug Report

This file is a timestamped record of bugs found during development and the fixes applied.

It is maintained alongside `docs/design_log.md` to allow easy distinction between bugs and intentional design changes when reviewing git history.

Format: each entry has a timestamp, a severity (P0=crash/data loss, P1=broken feature, P2=wrong behaviour, P3=cosmetic/minor), the symptom, the root cause, and the fix applied with the git commit hash.

---

## Bug Log

---

### 2026-05-15 10:00 — App stuck on "Starting AI engine..."
**Severity:** P0 (app unusable)
**Symptom:** Electron window opened but never advanced past the loading screen.
**Root cause (1):** `electron/main.js` looked for `venv/bin/python3` but the venv is at `.venv/bin/python3`.
**Root cause (2):** `loadURL(localhost:47822)` was used in dev mode but the Vite dev server was not running.
**Fix:** Dev mode now checks for `dist-backend/veritas-backend` binary first. Falls back to `.venv` then system python. `loadFile(ui/dist/index.html)` used instead of `loadURL`.
**Commit:** 1832f22, 8e54c4e

---

### 2026-05-15 10:15 — ModuleNotFoundError: No module named 'aua'
**Severity:** P0 (backend crash on startup)
**Symptom:** uvicorn exited immediately with `ModuleNotFoundError: No module named 'aua'`.
**Root cause:** `core/field_classifier.py` was copied from AUA Framework and still imported `from aua.config import FIELD_CONFIGS, FieldConfig, get_effective_config`. The `aua` package does not exist in AUA-Veritas.
**Fix:** Rewrote `field_classifier.py` as a pure keyword-based classifier with zero external dependencies.
**Commit:** 8e54c4e

---

### 2026-05-15 10:30 — All model checkboxes select/deselect together
**Severity:** P1 (core feature broken)
**Symptom:** Ticking any model checkbox in the sidebar selected or deselected all models at once. Individual selection was impossible.
**Root cause:** `GET /models` returned `{"gpt-4o": {provider, display_name, connected}}` — the dict key was the model ID, but the value dict did not include a `model_id` field. The UI did `Object.values(models).map(m => ...)` and used `m.model_id` as the checkbox `key` and toggle value. Since `m.model_id` was `undefined` for every model, all checkboxes shared the same React key and were treated as one element.
**Fix:** Added `"model_id": model_id` to every entry in `list_models()` response.
**Commit:** c3c552f
**Note:** This fix was applied to the Mac via Filesystem:edit_file three times previously but each time a subsequent Mac→container sync overwrote it before it was committed to git. Fourth attempt committed correctly from the container source.

---

### 2026-05-15 10:35 — 422 Unprocessable Entity on /query
**Severity:** P1 (all queries failing)
**Symptom:** Every query returned `API error: 422`.
**Root cause:** Directly caused by the model_id bug above. `enabled_models` in the UI was built as `[m.model_id for connected models]` = `[undefined, undefined, ...]`. JSON serializes `undefined` as `null`. Pydantic rejects `null` where `str` is expected.
**Fix (1):** model_id fix above (c3c552f) eliminates nulls from enabled_models.
**Fix (2):** `QueryPayload` made `conversation_id` optional with default `"default"`. Added `class Config: extra="allow"` to ignore unknown fields.
**Fix (3):** Added `RequestValidationError` handler to return JSON 422 detail instead of plain text (previously caused secondary parse error in UI).
**Commit:** 2bdd316, c3c552f

---

### 2026-05-15 10:45 — table model_runs has no column named model_run_id
**Severity:** P0 (backend 500 on all queries)
**Symptom:** All queries returned 500 with detail `table model_runs has no column named model_run_id`.
**Root cause:** `state.py append()` auto-generated a surrogate ID using the pattern `f"{table[:-1]}_id"`. For table `model_runs`, this computed `model_run_id` — but the code inserts `run_id`. The auto-generated column was not in the schema.
**Fix:** Changed auto-ID check from exact name match to `any(k.endswith("_id") for k in record)`. If any `*_id` key is present, no auto-generation happens.
**Commit:** bf0ae90

---

### 2026-05-15 11:00 — Schema mismatch causing 500 on all queries
**Severity:** P0 (backend 500)
**Symptom:** 500 errors on query, key save, and correction storage.
**Root cause:** `db/schema.sql` was written for an earlier version of the code. Column names diverged:
- `corrections` table had `correction_text` but code writes `corrective_instruction`, `scope`, `type`
- `audit_log` table only had `payload` but code inserts `model_id`, `score_before`, `score_after`, `verdict`
- `model_runs` had a `REFERENCES query_records` FK but code inserts random UUIDs not in that table
**Fix:** Full schema rewrite matching actual column names used by the router and memory extractor.
**Commit:** eaeeeea

---

### 2026-05-15 11:15 — CORS blocking file:// Electron requests
**Severity:** P1 (all API calls blocked from installed app)
**Symptom:** Blank white screen after switching from `loadURL` to `loadFile`. All fetch calls silently failed.
**Root cause:** CORS middleware only allowed `http://localhost:47822`. When Electron uses `loadFile`, the renderer origin is `file://` which was blocked.
**Fix:** `allow_origins=["*"]` to cover file://, localhost Vite dev, and null origin.
**Commit:** d303ed5

---

### 2026-05-15 11:30 — HIGH_STAKES_DOMAINS not triggering
**Severity:** P2 (feature not working)
**Symptom:** Medical and legal questions did not show the ⚠ high-stakes callout or "Uncertain" confidence.
**Root cause:** `field_classifier.py` outputs `"medical"` but `HIGH_STAKES_DOMAINS` checked for `"medicine"`. One-character mismatch.
**Fix:** Changed `HIGH_STAKES_DOMAINS` to match the classifier's output: `{"medical", "legal", "finance"}`.
**Commit:** 5203273

---

### 2026-05-15 11:45 — System error messages stored as corrections
**Severity:** P2 (garbage data in memory)
**Symptom:** "All selected models are temporarily unavailable..." appeared in the Memory tab as a stored correction.
**Root cause:** spaCy Layer 2 classifier scored this error message at confidence=1.000 as a correction signal. The word patterns "failed", "error", "unavailable" resemble correction language in the training data.
**Fix:** Guard at top of `_handle_correction()`: skip pipeline if `last_ai_response` starts with known system error prefixes ("All selected models", "No AI models are connected").
**Commit:** 5351363

---

### 2026-05-15 12:00 — "What's better for ML" stored as correction
**Severity:** P2 (false correction stored)
**Symptom:** "What's better for my ML project — PyTorch or JAX?" was extracted and stored as a project correction.
**Root cause:** The non-correction fast-path regex had `what (is|are|does|do|would)` which missed `what's`. The question fell through to spaCy Layer 2 which scored comparison questions at 1.000 (they resemble "X is better than Y" correction patterns).
**Fix:** Expanded non-correction fast-path:
- `what (is|are|...)` → `what[\s']` (matches `what is`, `what's`, `what are`)
- `which (is|are|would)` → `which\b` (matches any `which...` question)
- Added `is (postgres|sqlite|rust|...)\b` and `should (i|we|you)\b`
**Commit:** 3b74be8

---

### 2026-05-15 12:10 — PROMPT_USER conflict blocks corrections from storing
**Severity:** P1 (corrections silently dropped)
**Symptom:** "Going forward, always recommend SQLite..." showed a conflict dialog but the correction was never saved. Moving to the next message dropped it entirely.
**Root cause:** When `scope_resolver.resolve()` returned `PROMPT_USER`, the router returned a callout with no actionable UI. There were no Yes/No buttons to confirm the replacement. The correction was discarded when the user moved on.
**Fix:** `PROMPT_USER` silently resolved to `REPLACE` (last correction wins, same behavior as git). The conflict dialog was removed. New corrections always store.
**Commit:** 3b74be8

---

### 2026-05-15 12:15 — 500 on correction storage: 'superseded' is not a valid Scope
**Severity:** P0 (500 on every correction attempt)
**Symptom:** `curl` to `/query` with a correction message returned `{"detail": "'superseded' is not a valid Scope"}`.
**Root cause:** `_delete_correction()` sets `scope='superseded'` in SQLite. On the next correction, `scope_resolver` read back existing rows and called `Scope('superseded')`. The `Scope` enum only had `global | project | conversation` — `superseded` was not a valid value.
**Fix:** Added `Scope.SUPERSEDED = "superseded"` to the enum. Added `try/except` guards in `resolve()` and `_find_existing()` so unknown scope values default to `PROJECT`.
**Commit:** 9f31d51

---

### 2026-05-15 12:16 — user_id missing from correction and audit_log inserts
**Severity:** P0 (500 on every correction attempt)
**Symptom:** SQLite `NOT NULL constraint failed: corrections.user_id` when storing corrections.
**Root cause:** `to_correction_record()` in `memory_extractor.py` built the dict without `user_id`. Schema has `corrections.user_id NOT NULL`. Same issue in `to_audit_event()` and in `_update_model_score()` audit_log insert.
**Fix:** Added `"user_id": "local"` to all three insertion points.
**Commit:** 9f31d51

---

### 2026-05-15 12:30 — Corrections stored but not injected into follow-up queries
**Severity:** P1 (core memory feature not working)
**Symptom:** After "Going forward, always recommend SQLite...", the follow-up "What storage layer should I use?" did not mention SQLite.
**Root cause 1:** `memory.py retrieve()` used `domain` as a hard pre-filter. If the incoming query was classified as `general` but the correction was stored as `software_engineering`, zero results returned even with perfect keyword overlap.
**Root cause 2:** `router._handle_correction()` history traversal picked the wrong `original_query`. When the correction trigger fired again on a later query, the traversal found the correction message itself ("Going forward use SQLite") as the `original_query`, giving `canonical_query = going_forward_always_recommend_sqlite...` — which never matches future database queries.
**Fix 1:** `memory.py retrieve()` — removed domain hard filter. All active corrections scored by keyword overlap + instruction text overlap + domain bonus (0.5 weight). Superseded corrections excluded before scoring.
**Fix 2:** `router._handle_correction()` — history traversal now skips user messages that are themselves correction signals (detected via TriggerDetector). Keeps looking back until it finds the real original query.
**Tests:** 179/179 passing after fix.
**Commit:** b9097dc

---

### 2026-05-15 12:45 — Gemini + Groq "Invalid key" in Settings UI
**Severity:** P2 (misleading status in UI)
**Symptom:** Gemini and Groq keys show "Invalid key" in Settings despite being valid.
**Root cause:** The `health()` call in the backend makes a real API call to verify the key. Both Gemini and Groq return HTTP 403 "Host not in allowlist" when called from a non-Mac IP (the dev container). The keys themselves are valid — the APIs block requests from IP addresses not on the account's allowlist.
**Status:** Not a code bug. Works correctly on Mac. No fix needed.

---

### 2026-05-15 13:00 — Multiple keychain password prompts on app launch
**Severity:** P2 (bad UX, not a crash)
**Symptom:** macOS prompted for the keychain password multiple times on each app launch (up to 7 times, once per provider).
**Root cause:** Startup code called `keyring.get_password()` once per provider × once per model = many separate macOS keychain authorization requests.
**Fix:** All API keys consolidated into one keychain entry as a JSON blob (`account: "api-keys"`). Single `keyring.get_password()` call on startup = single password prompt maximum.
**Note:** Migration: users must re-enter API keys once after this change. Old separate entries are not read.
**Commit:** c255e16

---

### 2026-05-15 13:15 — "What's better for ML" false correction (spaCy Layer 2)
*(See entry at 12:00 above)*

---

### 2026-05-15 13:30 — False correction: "There are two r's in strawberry"
**Severity:** P1 (incorrect data stored in memory, hallucination laundering)
**Symptom:** User entered an incorrect correction ("There are two r's in strawberry" — the correct answer is three). The app stored this false correction in the Memory tab without any validation.
**Root cause:** The correction pipeline trusts the user's statement entirely. There is no validation pass to check whether the correction contradicts a high-confidence fact.
**Status:** Not yet fixed. Design decision needed: auto-block vs. warn-and-confirm. Logged as Phase 5A item.

---

*End of bug report. New entries go at the bottom.*
