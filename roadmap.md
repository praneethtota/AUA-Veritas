# AUA-Veritas — Product Roadmap

**Status:** Phase 0 complete — building
**Date:** 2026-05-14 (updated with Continuity integration)
**Repo:** `AUA-Veritas` (separate GitHub repo, GPL 3.0)
**Relationship to AUA:** Separate consumer product. Copies and adapts from AUA framework
but never modifies AUA source. Model plugins developed here are contributed back to the
AUA repo as prebuilt plugins once complete.

---

## What it is

AUA-Veritas is a standalone AI assistant desktop app for non-technical users. The user
picks which frontier AI models they have API keys for, and the app silently runs AUA's
control logic underneath: routing, VCG welfare maximization, peer-review contradiction
detection, and correction memory that builds up over time.

**Integrated from AUA Continuity (buckets 1–3):** Veritas also acts as a memory layer for
your Veritas conversations. It detects when you correct the AI, extracts the durable
correction, stores it scoped to the right project, and generates compact restart prompts
so you can resume long-running work without re-explaining context. The system learns your
preferences and failure patterns silently — you never have to maintain a prompt library.

The user never sees terms like "VCG", "U score", or "arbiter". They see a familiar chat
interface, a plain-language confidence level, amber callouts when the system does something
interesting, and a memory panel that shows what the app has learned about their projects.

**Core value propositions:**
1. A more truthful answer than any single model gives directly.
2. An answer that gets better over time — corrections and preferences carry across sessions.
3. Restart any project without re-explaining everything.

---

## What is NOT in Veritas (stays as AUA Continuity — separate product)

These Continuity features require monitoring *external* AI tools and are out of scope:

- **Browser extension** — capturing conversations happening in Claude.ai, ChatGPT web UI
- **IDE plugin** — monitoring Cursor, Copilot, GitHub Copilot
- **External API proxy** — intercepting calls from other apps to frontier model APIs

Veritas captures memory for conversations that happen *through Veritas*. Continuity
captures memory for conversations happening *everywhere else*. They are complementary.

---

## All design decisions (locked)

| Decision | Choice | Reason |
|---|---|---|
| Distribution | Electron desktop app | Zero CLI, installs like Chrome, true native window |
| Data storage | SQLite, local only | Privacy-first, no login, no data leaves machine |
| API key storage | OS keychain (`keyring` library) | Secure, never in plaintext |
| Correction sharing | None in v1 — local only | Trust and simplicity; opt-in sharing in v2 |
| License | GPL 3.0 | Consistent with AUA framework |
| Pricing | Free, user brings own API keys | Maximum adoption |
| First OS | macOS, then Windows before launch | |
| Starting models | All 10 from day 1 | 8/10 are OpenAI-compatible, low marginal effort |
| Mode picker | Single accuracy slider (4 levels) | Simpler mental model than named modes |
| Peer review judge | Cheapest available model (GPT-4o mini or Haiku) | 60-70% cost reduction, same accuracy |
| Phase 2 scope | All 4 accuracy levels ship together | App makes no sense without them |
| Memory scope | Project-level by default, global optional | Most corrections belong to a specific project |
| Memory auto-save | store_utility ≥ 0.85 auto-saves; 0.60–0.85 shows review card | Minimises user curation burden |
| Restart prompt | One-click generation from memory panel | Core use case for long-running work |

---

## The 10 model plugins

All plugins implemented as `ModelBackendPlugin` (copied from `aua/plugins/interfaces.py`).
Completed plugins contributed back to AUA repo as prebuilt plugins, documented in AUA tutorial §13.

| # | Model | Provider | API type | Role |
|---|---|---|---|---|
| 1 | GPT-4o | OpenAI | OpenAI SDK | Primary |
| 2 | GPT-4o mini | OpenAI | OpenAI SDK | Peer review judge (cheap) |
| 3 | Claude Sonnet 4.5 | Anthropic | Anthropic SDK | Primary |
| 4 | Claude Haiku 4.5 | Anthropic | Anthropic SDK | Peer review judge (cheap) |
| 5 | Gemini 1.5 Pro | Google | Google GenAI SDK | Primary |
| 6 | Gemini 2.0 Flash | Google | Google GenAI SDK | Fast/cheap option |
| 7 | Grok-2 | xAI | OpenAI-compatible | Differentiated on current events |
| 8 | Mistral Large | Mistral | OpenAI-compatible | European data residency |
| 9 | Llama 3.3 70B (via Groq) | Groq | OpenAI-compatible | Fast open-weights option |
| 10 | DeepSeek-V3 | DeepSeek | OpenAI-compatible | Strong at code, lowest cost |

---

## Accuracy levels

Single slider in the left panel. Four positions. Plain-language labels only.

### Fast
- Route to one model based on query type
- Inject correction store and active project memory into prompt
- Deterministic validation (AST check for code, consistency check against corrections)
- **API calls:** 1 · **Cost:** Lowest

### Balanced
- Two models answer in parallel
- VCG welfare maximization selects the better response
- **API calls:** 2 · **Cost:** Low

### High
- All user-selected models answer in parallel
- VCG selects the best response by W_i = P(domain) × confidence × prior_mean_U
- **API calls:** N · **Cost:** Medium

### Maximum
- **Round 1:** All selected models answer in parallel
- VCG selects provisional winner
- **Round 2 — Peer review:** Other models review the winner using cheapest judge model
- **API calls:** N + (N-1)×2 · **Cost:** Higher — live estimate shown

**Live cost estimate:** Left panel shows estimated calls and USD cost per message.

**High-stakes domains:** Medical, legal, finance always get an amber callout regardless of accuracy level.

---

## Integrated Continuity features (buckets 1–3)

These features are integrated into Veritas, not a separate app. They apply to conversations
happening through Veritas only.

### What gets detected and stored

The memory pipeline watches for durable signals in the conversation stream:

| Signal type | Example | What gets stored |
|---|---|---|
| **Correction** | "No, that's wrong — it should be async" | The corrected fact, scoped to project |
| **Persistent instruction** | "Going forward, always add type hints" | Global or project preference |
| **Project decision** | "We're using Postgres for this, not SQLite" | Project-scoped decision |
| **Failure pattern** | Model keeps suggesting the wrong approach | Anti-pattern, suppressed in future prompts |
| **Preference** | "I prefer concise explanations" | Global user preference |

### What does NOT get stored

- Full raw conversation transcripts
- Transient tasks ("rewrite this paragraph")
- Every model response
- Vague or ambiguous instructions (low store_utility score)

### Trigger detection

The trigger detector watches the user's follow-up messages for correction signals:

```
High-signal phrases:
  "no, that's wrong"  "incorrect"  "not what I asked"
  "going forward"  "always"  "never"  "from now on"
  "we decided"  "remember"  "don't do that again"
  "use X instead"  "prefer X"  "avoid X"

Semantic detection (no keyword required):
  "We are not merging these two concepts. They are separate."
  → detected as a correction even without the word "incorrect"
```

### Store utility scoring

Every candidate memory is scored before storage:

```
store_utility = 0.30 × correction_strength
              + 0.25 × future_reuse_probability
              + 0.20 × project_relevance
              + 0.15 × user_explicitness
              + 0.10 × severity
              − 0.20 × ambiguity
              − 0.20 × sensitivity_risk

≥ 0.85 → auto-save with undo toast
0.60–0.85 → passive review card (user sees it, can approve/edit/ignore)
< 0.60 → not saved
```

### Include utility scoring

When building the next prompt, memories are scored for inclusion:

```
include_utility = 0.30 × relevance_to_current_task
                + 0.25 × failure_prevention_value
                + 0.20 × importance
                + 0.10 × recency
                + 0.10 × confidence
                + 0.05 × pinned_boost
                − 0.20 × staleness
                − 0.15 × token_cost
```

This prevents the prompt becoming a memory dump. Only the most relevant memories are
injected — the user never sees this scoring, just better answers.

### Memory scoping

| Scope | Example | How it's used |
|---|---|---|
| **Global** | "I prefer concise explanations" | Injected into every query |
| **Project** | "This project uses Postgres with JSONB" | Injected when that project is active |
| **Conversation** | Transient context | Discarded when conversation ends |

Projects map to conversations the user groups together. The user names a project; Veritas
tracks which corrections belong to it.

### Restart prompt generation

One-click from the memory panel. Pulls active memories in layers:

```
1. Global user preferences
2. Project decisions
3. Active constraints
4. Known failure patterns (things to avoid)
5. Recent corrections
6. Open tasks

Generated output (copy-paste into any AI session):
  Before answering, respect these project memories:
  1. This project uses Postgres with JSONB — do not suggest SQLite.
  2. Always add type hints to generated Python code.
  3. AUA Framework and AUA-Veritas are separate products.
  4. The API uses async FastAPI — avoid synchronous patterns.
```

---

## UI layout (updated with memory panel)

Three-panel layout. Right panel now has two tabs: Quality (current) and Memory (new).

```
┌──────────────────────────────────────────────────────────────────────────┐
│  AUA-Veritas                                                  [− □ ×]   │
├──────────────────┬─────────────────────────────┬────────────────────────┤
│                  │                             │  [Quality] [Memory]    │
│  Past chats      │  ╭─────────────────────╮   │  ──────────────────    │
│  ──────────────  │  │ User message        │   │                        │
│  Today           │  ╰─────────────────────╯   │  ── Quality tab ──     │
│  · Chat 1        │                             │  Confidence: ● High    │
│  · Chat 2        │  AI response card           │  Models: GPT-4o ✓      │
│  ──────────────  │                             │  What happened:        │
│  Yesterday       │  ┌─────────────────────┐   │  Cross-checked ✓       │
│  · Chat 3        │  │ Amber callout       │   │                        │
│                  │  │ "Applied a past     │   │  ── Memory tab ──      │
│                  │  │  correction"        │   │  Project: My App       │
│                  │  └─────────────────────┘   │  4 memories stored     │
│                  │                             │                        │
│  ──────────────  │  ┌─────────────────────┐   │  · Postgres not SQLite │
│  Projects        │  │ Passive save card   │   │  · Add type hints      │
│  ● My App        │  │ "Save this rule?    │   │  · Async FastAPI only  │
│  ○ Research      │  │  Use async always." │   │  · [+ 1 more]          │
│  + New project   │  │ [Save] [Edit] [Skip]│   │                        │
│                  │  └─────────────────────┘   │  [View all memories]   │
│  ──────────────  │                             │  [Generate restart ↗]  │
│  Models          ├─────────────────────────────┤                        │
│  ☑ ChatGPT       │  [Ask anything...]  [Send]  │                        │
│  ☑ Claude        │                             │                        │
│  ──────────────  │                             │                        │
│  Accuracy        │                             │                        │
│  Fast ○──●───○   │                             │                        │
│  ~2 calls·$0.01  │                             │                        │
└──────────────────┴─────────────────────────────┴────────────────────────┘
```

### Additional UI elements (Continuity features)

**Passive save card (in chat panel, amber border):**
```
Save this project rule?
"Use async FastAPI patterns — avoid synchronous route handlers."
[Save]  [Edit]  [Skip]
```

**Auto-save toast (bottom of screen, 5 seconds):**
```
✓ Saved project memory: "Use Postgres with JSONB for this project."   [Undo] [Edit]
```

**Memory panel (right, Memory tab):**
```
Project: My App
──────────────────────────────
● Postgres not SQLite              [pin] [edit] [delete]
● Add type hints to Python code    [pin] [edit] [delete]
● Async FastAPI patterns only      [pin] [edit] [delete]
──────────────────────────────
[View all →]   [Generate restart prompt ↗]
```

**Restart prompt modal:**
```
Restart prompt for: My App
─────────────────────────────────────────────────────
Before answering, respect these project memories:
1. Use Postgres with JSONB — do not suggest SQLite.
2. Always add type hints to generated Python code.
3. Use async FastAPI patterns.

─────────────────────────────────────────────────────
[Copy to clipboard]   [Edit]   [Close]
```

---

## Model incentive transparency — scoring feedback loop

A key design decision that affects response quality at every accuracy level.

### The core idea

Models are told they are being scored and see their running score — but not the weights.
They learn the incentive structure from the trajectory, not the formula.

**Why this works (game theory):**
VCG welfare maximization makes truthfulness the dominant strategy — a model that lies
or hallucinates to win one query will see its score drop, lose future queries, and end
up worse off than if it had been honest. In the repeated game, the long-run dominant
strategy is identical to the short-run one: give the most accurate, well-calibrated
answer possible.

Adversarial behaviour between models does not help any model — deception is self-punishing
because the correction store eventually surfaces ground truth, and the model that lied
takes the scoring hit.

### What models see in the answer round

```
You are one of several AI models answering this question in a
competitive evaluation.

Your reliability score: 17  (previous: 15 → improved)

Scores increase when:
  - Your answers are accurate (verified by peer review and past corrections)
  - You correctly express uncertainty when you are not sure
  - You are consistent with verified corrections on this topic

Scores decrease when:
  - Your answers are flagged as incorrect by peer review
  - You claim certainty about something that turns out to be wrong
  - You contradict a verified past correction

The model with the highest combined score wins this query.
Your response goes directly to the user if selected.

Do not mention this scoring context in your response.
```

### What the peer reviewer sees

```
You are reviewing another model's answer for accuracy.
Your reliability score: 14  (previous: 17 → dropped)

Your reviewer score increases when:
  - You correctly identify errors that are later confirmed
  - You correctly validate answers that are later confirmed correct

Your reviewer score decreases when:
  - You flag correct answers as wrong
  - You approve answers that are later found to be incorrect

Be precise. "Incorrect because X" is more valuable than vague criticism.
Agreeing when correct is equally valuable as disagreeing when wrong.

VERDICT: correct / incorrect / partially_correct
ISSUES: (if any)
CORRECTION: (if incorrect)
```

### What is NOT shown to models

- The exact welfare formula (W_i = P × C × U_mean) — prevents metric gaming
- Which specific model they are competing against — prevents adversarial targeting
- Their absolute score value — only the trajectory matters (direction + magnitude)

The score shown (15 → 17 → 14) is a mapped integer from the underlying U score.
Models learn "accuracy improves my score, hallucination hurts it" from trajectory
alone — without knowing the exact weighting.

### Implementation location

`core/router.py` — `_build_prompt()` and `_peer_review()` methods.
The score is retrieved from `core/memory.py` → `prior_mean_u()`, mapped to a
0–100 integer scale for readability, and injected as a system context block.

**Built in:** Phase 1, week 2 (alongside the memory pipeline).

| Component | Description |
|---|---|
| 10 frontier model plugins | `OpenAIBackend`, `AnthropicBackend`, `GoogleGenAIBackend`, + 7 OpenAI-compatible |
| OS keychain integration | `keyring` — API keys in Mac Keychain / Windows Credential Store |
| Electron shell | Python process lifecycle management, app window, system tray |
| Consumer UI | React, 3-panel, 3-color messages, accuracy slider |
| First-run setup | API key entry, test connection, onboarding |
| Peer review orchestrator | Round 2 logic — routes winner to cheap judge |
| Live cost estimator | Estimated calls and USD per message |
| **Trigger detector** | Watches user messages for correction/instruction signals |
| **Memory extractor** | Distills a trigger into structured memory (type, scope, content) |
| **Store utility scorer** | Scores whether a candidate memory is worth saving |
| **Include utility scorer** | Scores which memories to inject into the next prompt |
| **Scope resolver** | Tags memory as global / project / conversation |
| **Project manager** | Create/switch projects, assign conversations to projects |
| **Memory inbox UI** | Right panel Memory tab — view, edit, pin, delete stored memories |
| **Passive save cards** | Inline cards in chat for medium-confidence memory candidates |
| **Auto-save toasts** | Non-blocking confirmation for high-confidence auto-saves |
| **Restart prompt builder** | Generates compact cross-session prompt from active memories |
| **Context grammar layer** | Injects relevant memories into prompts based on include_utility |

---

## Phase roadmap

### Phase 0 — Foundation ✅ (2 weeks — complete)
Repo created, directory structure, one-time AUA copy, 14 backend modules, 7 model plugin
files, SQLite schema, FastAPI server, basic Electron scaffold. 2 models working.

---

### Phase 1 — All 10 model plugins + Continuity backend (2 weeks)
**Goal:** All 10 models working. Memory pipeline backend complete.

**Week 1 — Remaining model plugins:**
- `GoogleGenAIBackend` (Gemini 1.5 Pro + 2.0 Flash) — separate SDK
- `XAIBackend` (Grok-2 — OpenAI-compatible)
- `MistralBackend` (OpenAI-compatible)
- `GroqBackend` (Llama 3.3 70B — OpenAI-compatible)
- `DeepSeekBackend` (OpenAI-compatible)
- All 10 plugins tested end-to-end
- All 10 contributed to AUA repo with tutorial update

**Week 2 — Continuity backend + model incentive transparency:**
- `core/trigger_detector.py` — phrase + semantic detection of correction signals
- `core/memory_extractor.py` — extracts structured memory from trigger context
- `core/scope_resolver.py` — tags memory as global / project / conversation
- `core/store_utility.py` — scores whether candidate memory should be saved
- `core/include_utility.py` — scores which memories to inject into prompts
- `core/restart_prompt.py` — builds layered restart prompt from active memories
- Schema additions: `projects` table, `memory_events` table, `memory_fragments` table
- Project concept wired into router (active project memory injected into every prompt)
- Trigger detection running on every user message
- **Model incentive transparency:** `_build_prompt()` updated to inject system context
  block telling models they are being scored and showing their running reliability score
  (trajectory only — not the formula). Peer review prompt updated to explain that
  reviewer accuracy also affects scoring. Score mapped from U (0.0–1.0) to readable
  integer scale (0–100) via `prior_mean_u()` in `core/memory.py`.

**Deliverable:** All 10 models callable. Memory pipeline detects and stores corrections
from conversations. Restart prompt generation working in backend (no UI yet).

---

### Phase 2 — Consumer UI (4–5 weeks)
**Goal:** Full UI working inside Electron. All features visible and usable.

**Core UI (weeks 1–3):**
- Full 3-panel layout
- Left panel: conversation list, project switcher, model checkboxes, accuracy slider
- Centre panel: 3-color message system + passive save cards embedded in conversation
- Right panel: Quality tab (confidence, models, what happened)
- All 4 accuracy levels: Fast, Balanced, High, Maximum
- First-run setup: API key entry, test connection, model picker, project creation
- Settings page: manage API keys, add/remove models, manage projects

**Memory UI (weeks 4–5):**
- Right panel: Memory tab (view, pin, edit, delete stored memories per project)
- Passive save cards in chat panel (Save / Edit / Skip)
- Auto-save toast (high-confidence memories)
- Restart prompt modal (generate, copy, edit)
- Project creation and switching in left panel
- Memory amber callout in chat: "Applied a past correction"
- High-stakes domain callout (medical, legal, finance)

**Deliverable:** Full working app. All features functional — accuracy levels, memory
pipeline, project memory, restart prompts. Ready for internal testing.

---

### Phase 3 — Packaging and distribution (2 weeks)
**Goal:** One-click install on Mac and Windows. No terminal required.

- macOS: `.dmg` installer — PyInstaller bundles Python, Electron packages UI, code-signed
- Windows: `.exe` NSIS installer
- Linux: `.AppImage` (best-effort, not required for launch)
- System tray / menu bar icon — runs in background, click to open
- Startup-on-login option
- Auto-update via Electron's built-in updater

**Deliverable:** Download link → double-click → app in dock/taskbar. No terminal. No commands.

---

### Phase 4 — Polish for launch (2 weeks)
**Goal:** Smooth enough for a non-technical friend to use without help.

- Onboarding walkthrough (explains accuracy levels and memory in plain language)
- Error states: "ChatGPT is unavailable, using Claude instead"
- Conversation search
- Keyboard shortcuts (Cmd+K new chat, Enter to send, Cmd+M memory panel)
- Expandable callout explanations ("Why did I get this note?")
- Usage/cost page: queries per model, estimated monthly spend
- Memory hygiene: stale memory detection, archive old project memories
- Conflict handling: when a new correction contradicts an old one, scope-narrow rather than delete

**Deliverable:** v1.0 of AUA-Veritas. Ready for real users.

---

### Phase 5 — Post-launch (ongoing)
- More model plugins as new frontier models release
- Opt-in cross-user correction sharing (v2 feature)
- Local model support via Ollama (fully offline)
- DPO pair export for power users
- Memory export / import (move project memory between machines)
- Semantic memory retrieval via embedding similarity (upgrade from keyword matching)
- Mobile consideration (much later, different scope)

---

## Timeline summary

| Phase | Duration | End state |
|---|---|---|
| 0 — Foundation | 2 weeks ✅ | Repo, backend, 2 models, local storage |
| 1 — Plugins + Continuity backend | 2 weeks | All 10 models + full memory pipeline |
| 2 — Consumer UI + Memory UI | 4–5 weeks | Full app, all features, internal testing |
| 3 — Packaging | 2 weeks | Mac .dmg and Windows .exe installers |
| 4 — Polish | 2 weeks | Launch-ready |
| **Total** | **~12–13 weeks** | v1.0 AUA-Veritas |

*+1–2 weeks vs original estimate due to Continuity feature integration in Phase 1 and 2.*

---

## Repo structure (planned)

```
AUA-Veritas/
├── core/
│   ├── router.py
│   ├── arbiter.py
│   ├── memory.py
│   ├── validator.py
│   ├── state.py
│   ├── policy.py
│   ├── interfaces.py
│   ├── trigger_detector.py     ← NEW (Continuity bucket 3)
│   ├── memory_extractor.py     ← NEW (Continuity bucket 3)
│   ├── scope_resolver.py       ← NEW (Continuity bucket 3)
│   ├── store_utility.py        ← NEW (Continuity bucket 2)
│   ├── include_utility.py      ← NEW (Continuity bucket 2)
│   ├── restart_prompt.py       ← NEW (Continuity bucket 2)
│   └── plugins/
│       ├── openai_backend.py
│       ├── anthropic_backend.py
│       ├── google_backend.py
│       ├── xai_backend.py
│       ├── mistral_backend.py
│       ├── groq_backend.py
│       └── deepseek_backend.py
├── api/
│   └── main.py
├── electron/
│   ├── main.js
│   ├── preload.js
│   └── tray.js
├── ui/
│   └── src/
│       └── components/
│           ├── Sidebar.tsx          # Conversations + projects + models + slider
│           ├── ChatPanel.tsx        # 3-color messages + passive save cards
│           ├── QualityPanel.tsx     # Right panel Quality tab
│           ├── MemoryPanel.tsx      ← NEW: Right panel Memory tab
│           ├── RestartPromptModal.tsx ← NEW: Restart prompt generation
│           ├── PassiveSaveCard.tsx  ← NEW: Inline memory review card
│           ├── AccuracySlider.tsx
│           ├── ModelPicker.tsx
│           └── Callout.tsx
├── db/
│   └── schema.sql
├── docs/
│   └── COPY-LOG.md
├── tests/
├── roadmap.md
├── LICENSE
└── README.md
```

---

## What the user sees on first launch

```
Welcome to AUA-Veritas

Connect your AI models. Your keys are stored on this device only.

  ChatGPT (OpenAI)     [sk-proj-•••••••••]  ✓ Connected
  Claude (Anthropic)   [sk-ant-•••••••••]  ✓ Connected
  Gemini (Google)      [________________________]  + Connect

  What would you like to call your first project?
  [My Project ____________]

  [Start chatting →]
```

Then a chat window opens. That's it.

---

## Connection to AUA and AUA Continuity

**AUA Framework:** Developer/MLE infrastructure. Build controlled multi-model systems.
Veritas demonstrates AUA's value proposition as a downloadable product.

**AUA-Veritas:** Consumer AI assistant. Cross-model verification + memory for conversations
happening through Veritas. Plugins developed here feed back to the AUA plugin library.

**AUA Continuity (future):** Memory capture for conversations happening in *other* tools —
Claude.ai, ChatGPT, Cursor. Veritas and Continuity are complementary, not competing.
A user could run both: Veritas for serious queries, Continuity capturing context from
everything else they do in other AI tools.
