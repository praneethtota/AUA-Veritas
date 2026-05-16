# AUA-Veritas Design Log

This file is a timestamped record of design decisions made during development.

Its purpose is to help distinguish between design choices and bug fixes when reviewing git history, and to allow design branches to be reverted independently from bug fixes.

Format: each entry has a timestamp, a type (DESIGN or BUG-FIX or ARCH), and a plain English description of what changed and why.

Bug fixes are also listed here so that no fix is missed when branching back to an earlier design point. The bug_report.md file has more detail on each bug.

---

## Log

---

### 2026-05-15 — Phase 1: Model plugins + spaCy classifier

**[ARCH]** Five model backend plugins contributed to AUA framework:
- GoogleBackend, XAIBackend, MistralBackend, GroqBackend, DeepSeekBackend
- Each plugin implements a standard interface: `complete()`, `health()`, `aclose()`

**[ARCH]** spaCy trigger classifier trained with 270 examples, F1=1.000.
- Two-layer detection: Layer 1 is regex fast-path, Layer 2 is spaCy classifier
- Classifies user messages as correction signals or normal queries

**[ARCH]** Core memory pipeline implemented:
- `memory_extractor.py` — LLM or rule-based extraction of corrections from user messages
- `scope_resolver.py` — OOP inheritance model (project overrides global silently)
- `store_utility.py` — 7-factor formula, AUTO_SAVE (≥0.85), REVIEW_CARD (0.60–0.85), DISCARD (<0.60)
- `include_utility.py` — 8-factor selection, exponential recency decay
- `restart_prompt.py` — generates 5-layer restart prompt in Veritas format and IDE format

---

### 2026-05-15 — Phase 2: Consumer UI

**[ARCH]** 3-panel layout: Sidebar (conversations, project switcher, models, accuracy) | Chat panel | Quality/Memory panel.

**[DESIGN]** Accuracy slider has 4 levels: Fast (1 model), Balanced (~1.05× cost), High (all models, VCG picks best), Maximum (all models + peer review).

**[DESIGN]** High and Maximum modes locked unless 2+ providers are connected. Shown greyed with tooltip explaining why.

**[DESIGN]** Confidence shown in plain language: High (green), Medium (amber), Uncertain (red). Technical scoring hidden from users.

**[DESIGN]** Three-color message system in chat:
- Dark bubble = user message
- Light card = AI response
- Amber left-border card = system callout (correction applied, crosscheck, disagreement, high-stakes)

**[DESIGN]** Callouts have a `?` button that expands a plain-language explanation of why the callout appeared. Six callout types covered: correction, crosscheck, disagreement, highstakes, conflict, context_reset.

**[DESIGN]** Memory tab shows stored corrections with type badges: Fact, Rule, Decision, Preference, Pattern — each with domain-specific colors.

**[DESIGN]** Passive save cards (store_utility 0.60–0.85): shown inline in chat, user can Save / Edit / Skip without leaving conversation.

**[DESIGN]** Auto-save toast (store_utility ≥0.85): 5-second countdown, Undo + Edit buttons.

**[DESIGN]** Restart prompt modal has two format tabs: IDE format (plain numbered list for Claude Code / Cursor) and Veritas format (layered). Copy button per format.

**[DESIGN]** Look Under the Hood (🔩 icon): SVG time-series graphs of model reliability scores. Clickable data points show query preview, verdict, score delta. Explained in plain language. Not surfaced in main UI — discovery by curious users.

**[DESIGN]** Usage & Cost page (📊 icon): per-model query counts and estimated costs with horizontal bars. Cost disclaimer included.

**[ARCH]** Keyboard shortcuts: Cmd/Ctrl+K = new chat, Cmd/Ctrl+M = memory tab, Escape = close all modals.

**[ARCH]** Onboarding walkthrough: 5-step first-launch modal. Persisted to localStorage. Skip always available. App flow: setup → onboarding → chat.

---

### 2026-05-15 — Phase 3: macOS DMG packaging

**[ARCH]** PyInstaller bundles the Python backend into a single binary (`dist-backend/veritas-backend`). No Python installation required on user machine.

**[ARCH]** Electron loads `ui/dist/index.html` directly (not a Vite dev server) in production. Dev mode: checks for `dist-backend/veritas-backend` first, falls back to `.venv/bin/python3`.

**[ARCH]** Distribution: direct download from `praneethtota.github.io/AUA-Veritas`, not the App Store. No Apple Developer account ($99/year) required for v1. Users bypass Gatekeeper with right-click → Open (one-time, first launch only). Documented in the installer and on the distribution page.

**[ARCH]** GitHub Pages distribution page (`docs/index.html`) has a dynamic download button that reads the latest release from the GitHub API. Falls back to the releases page if GitHub API is unavailable.

---

### 2026-05-15 — Phase 4: Polish

**[DESIGN]** Model selection: only the first connected model is auto-enabled on first launch. After that, user's manual checkbox selections are preserved across Settings opens and model reloads.

**[DESIGN]** Sidebar conversation search: inline, filters by title in real time. No API call — client-side only.

**[DESIGN]** Settings page shows per-provider connection status, Remove button, inline key input + Connect. Free tier badges for Google and Groq. Keys stored in macOS Keychain notice.

---

### 2026-05-15 — Keychain architecture decision

**[DESIGN]** All API keys stored as a single JSON blob under one keychain entry (`service: AUA-Veritas, account: api-keys`).

Reason: storing each provider key as a separate keychain entry caused macOS to prompt for the keychain password once per entry (up to 7 prompts on app launch). Single entry = single prompt maximum, ever.

Trade-off: changing the storage format requires users to re-enter API keys once after upgrading. Documented in release notes.

---

### 2026-05-15 — Disagreement resolution (design intent, not yet built — Phase 5A)

**[DESIGN — PENDING]** When models disagree, show answers side-by-side in distinct pastel colors. User clicks the answer they prefer.

The picked answer becomes a correction injected to the *other* models only (not the model that gave the preferred answer). Framed as a preference, not a factual claim: "the user prefers this answer to yours."

Positive score for picked model. Negative score for others.

Tracked in a new `correction_models` relation table: `correction_id | model_id` indicating which models a correction applies to. This prevents global corrections from being injected into the model that was already correct.

**[DESIGN — PENDING]** Do not penalize a model repeatedly for the same mistake once a correction has been accepted. Track corrected topics per model. Score drop only happens once per topic unless expert verification overturns the correction.

**[DESIGN — PENDING]** Expert arbitration (future, later version): when models disagree on factual ground (not preference), external arbitration protocol (subject matter experts, citations) available as a dropdown. Not Phase 5.

---

### 2026-05-15 — Context backup (design intent, not yet built — Phase 5B)

**[DESIGN — PENDING]** Seamless context backup: when a conversation gets long (approaching model context window limit) or the user is inactive for a configurable period, Veritas auto-generates a context prompt, starts a fresh underlying model session, and injects the backup. User sees one continuous chat window with no interruption.

Context prompt includes: project rules, saved corrections, preferences, decisions made, open tasks, things to avoid repeating.

**[DESIGN — PENDING]** Backup frequency configurable: automatic (app manages based on inactivity and context length), 15–20 min, hourly, daily, manual only, off.

**[DESIGN — PENDING]** App maintains a shadow token count per conversation. Triggers backup before the model hits its context limit (model context window − buffer). Each model's context window size is tracked in config.

**[DESIGN — PENDING]** Context backup is toggleable in settings. Default: on. If a correction is deleted, it is not included in future context prompts.

---

### 2026-05-15 — Design log and bug report rule

**[ARCH]** `docs/design_log.md` created — this file. All future design decisions, architectural choices, and intentional behavior changes must be logged here with a timestamp before being implemented.

**[ARCH]** `docs/bug_report.md` created — timestamped record of all bugs found and fixes applied. See that file for the full bug history.

Purpose: distinguish design choices from bug fixes in git history. Allows reverting design branches without losing bug fixes, and vice versa.

---

### 2026-05-16 — Per-model context backup architecture

**[DESIGN]** Context backups are generated per-model, not shared across models.

When a conversation has multiple models (e.g. GPT-4o, Claude, Llama), each model tracks its own token count independently against its own context window limit. When any one model approaches its limit, Veritas asks **that specific model** to generate its own context summary:

> "Summarise the context needed to continue this conversation in a new window without losing preferences, decisions, corrections, or open tasks. Max 500 tokens."

The summary is stored in SQLite with both `model_id` and `conversation_id`. Model A's backup is only ever injected back into Model A. Model B's backup only goes to Model B. They never cross.

Reason: each model tracks the conversation through its own lens, phrasing, and reasoning style. A shared summary would be a lossy average. Per-model summaries are faithful to each model's own understanding.

A 3-model conversation has 3 independent context counters and potentially 3 separate backup records. At any moment, models may be at different refresh stages — one on its original thread, another on its third refresh. The user sees none of this.

---

### 2026-05-16 — Context backup is invisible by default, opt-out in Settings

**[DESIGN]** The context backup system is entirely hidden from the user. No prompts, no interruptions, no "do you want me to save context?" questions. The model handles it silently in the background.

The user has one Settings toggle: **Context backup** — On / Off.

Default: **On.**

Why opt-out rather than opt-in: the feature only has value if it runs automatically. An opt-in feature that most users never find helps nobody.

The Settings section must clearly explain two things before the toggle:
1. **Tokens:** Each backup uses approximately 500 tokens from the model that generates it. With 3 models, that is up to 1,500 tokens per backup event. The frequency setting (auto / 15 min / hourly / daily / manual) controls how often this happens.
2. **Privacy:** The backup prompt asks the model to summarise your conversation. That summary is sent to the model provider's API as a normal API call — subject to the same privacy terms as any other message you send through Veritas. If you do not want conversation summaries sent to model providers, turn this off.

The toggle lives under a dedicated **Context backup** section in Settings, separate from API keys. It has:
- On / Off toggle (default On)
- Frequency selector (only shown when On): Automatic / Every 15–20 min / Hourly / Daily / Manual only
- One-line cost estimate: "Approximately X tokens per backup event across your connected models"
- Privacy note: "Backup summaries are sent to your connected model providers as normal API calls."

No other UI. The user never sees backup events happening, which models have been refreshed, or how many times a refresh has occurred — unless they open Look Under the Hood (Phase 6.5).

---

### 2026-05-16 — Rolling backups every 20 messages, not one-shot at 70%

**[DESIGN]** Context backups are not a one-shot event at the 70% context threshold. They roll continuously for the life of the conversation.

Two triggers, both running in parallel per model:
1. **Token threshold** — when a model's estimated token count hits 70% of its context window. After a refresh, the counter resets for the new thread and triggers again at 70% of that thread.
2. **Message count** — every 20 messages regardless of token count. Keeps the backup fresh throughout a long conversation.

The `context_backups` table is append-only. Each backup is a new row. Old rows are never deleted — they are an audit trail. The router always injects the single most recent row for `(model_id, conversation_id)`.

Result: a model on its third refresh thread, 200 messages into that thread, has a backup that reflects those 200 messages — not the original session summary from before the first refresh.

---

*End of log. New entries go at the bottom.*
