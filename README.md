# AUA-Veritas

> A standalone AI assistant that asks multiple frontier models, then tells you who gave the most trustworthy answer.

**Status:** Phase 0 — in development  
**License:** GPL-3.0  
**Built on:** [AUA Framework](https://github.com/praneethtota/Adaptive-Utility-Agent)

## Status: Work in Progress

AUA Veritas is currently an active work in progress and is **not release-ready yet**.

The current repository is meant to show the product direction, architecture, and early implementation. Some features are incomplete, some flows may break, and there are known bugs that still need to be fixed before a public release.

Known issues and current bugs are being tracked in the docs folder:

👉 [Bug Report](docs/bug_report.md)

If you try the app locally, expect rough edges. Feedback, bug reports, and suggestions are welcome.

---

## What it does

AUA-Veritas wraps frontier AI models (ChatGPT, Claude, Gemini, and more) and runs AUA's
control logic silently underneath — routing, welfare-maximizing model selection, contradiction
detection, peer review, and correction memory that improves over time.

It shows you when the models agree, and warns you when they don’t.

## Accuracy levels

| Level | What happens | Cost vs direct | Time vs direct |
|---|---|---|---|
| **Fast** | One best model answers. Corrections injected. Local validator runs. | `1x` — identical | +1–2% |
| **Balanced** | Primary answers. Cheap judge model cross-checks factual queries + failures. | `1x–1.1x` (~1.05x avg) | +12% avg |
| **High** | All selected models answer in parallel. VCG picks the best. | `Nx` (N = models) | +5–15% (parallel) |
| **Maximum** | All models answer. Other models peer-review the winner (cheap judges). | `~N + 0.1×(N-1)x` e.g. 3.2x for 3 models | +50–70% |

Peer review uses the cheapest available model (GPT-4o mini or Claude Haiku) — not the primary model.

## Models supported

ChatGPT (GPT-4o, GPT-4o mini) · Claude (Sonnet, Haiku) · Gemini (1.5 Pro, 2.0 Flash)
· Grok-2 · Mistral Large · Llama 3.3 70B (via Groq) · DeepSeek-V3

You bring your own API keys. They're stored in your OS keychain — never in the cloud.

## Privacy

All data stays on your machine:
- Conversations stored in local SQLite
- API keys stored in your OS keychain
- Correction memory is private to you
- Nothing uploaded without your explicit action

## Relationship to AUA Framework

AUA-Veritas is a consumer product built on the [AUA Framework](https://github.com/praneethtota/Adaptive-Utility-Agent).
Model plugins developed here are contributed back to the AUA repo as prebuilt plugins.

See [docs/COPY-LOG.md](docs/COPY-LOG.md) for exactly which AUA modules were copied here.

## Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run the API server (normally started by Electron)
uvicorn api.main:app --port 47821 --reload

# Run tests
pytest
```

## Roadmap

See roadmap.md  for the full product roadmap.





# AUA-Veritas

**Ask multiple AIs. Know when they agree. Continue where you left off.**

AUA-Veritas is a desktop AI assistant that helps you use frontier AI models with more confidence and less repetition.

Instead of manually asking ChatGPT, Claude, Gemini, Grok, Mistral, and other AI models one by one, Veritas gives you one familiar chat window. Behind the scenes, it can compare answers across models, show you when they agree or disagree, remember your corrections, and carry important context forward when a conversation gets too long, stale, or inactive.

To you, it feels like one continuous chat.

Veritas handles the checking, memory, and context handoff in the background.

---

## Status: Early Development

AUA-Veritas is currently an active work in progress and is **not release-ready yet**.

The current repository shows the product direction, architecture, and early implementation. Some features are incomplete, some flows may break, and there are known bugs that still need to be fixed before a public release.

Known issues are tracked here:

👉 [Bug Report](docs/bug_report.md)

If you run the app locally, expect rough edges. Feedback, bug reports, and suggestions are welcome.

---

## What AUA-Veritas does

AUA-Veritas helps with three common AI problems:

1. **Knowing when to trust an answer**
2. **Continuing long chats without repeating yourself**
3. **Learning which AI models work best for your tasks**

---

## 1. Know when the AIs agree

Most AI tools give you one answer from one model.

But for important questions, the most useful signal is often not just the answer itself. It is whether multiple models agree.

AUA-Veritas can ask multiple frontier AI models and compare their responses.

When the models mostly agree, Veritas shows a **high-confidence green signal**.

When the models differ, Veritas shows a **medium- or low-confidence warning** so you know the answer needs a closer look.

That means you do not have to manually copy the same question into several AI tools just to see whether they converge.

Veritas does that work for you.

---

## 2. Continue where you left off

Long AI chats are fragile.

After enough messages, important rules get buried, context gets stale, and the model may forget decisions you already made.

AUA-Veritas is designed to prevent that.

When you leave a chat for a while — whether for 20 minutes, a few hours, or a day — Veritas can back up the important context automatically:

- project rules
- saved corrections
- preferences
- decisions already made
- open tasks
- things the AI should avoid repeating

When you come back, Veritas can start a fresh underlying model session with that context already loaded.

You keep working in the same app window.

You do not need to summarize the old conversation, paste the same instructions again, or start from a blank screen.

To you, it still feels like one continuous chat.

Behind the scenes, Veritas handles the handoff.

---

## 3. Learn which AIs work best for you

AUA-Veritas quietly tracks how each connected AI model performs over time.

Helpful answers can make a model more trusted for similar tasks. Repeated mistakes or ignored corrections can make Veritas trust that model less.

Preferences are handled differently from mistakes.

If you say, “Going forward, write shorter answers,” Veritas treats that as a preference to remember — not as a model failure. The model is not penalized the first time it misses a preference it did not know yet.

Most users do not need to see these scores.

By default, Veritas simply uses them in the background to compare answers more intelligently.

If you want more transparency, open **Look Under the Hood** from the top-right corner. There, you can see model rankings, score changes over time, confidence history, saved corrections, and why Veritas marked an answer as high, medium, or low confidence.

---

## How it works, in plain English

1. You ask a question.
2. Veritas decides how carefully to check it based on your accuracy setting.
3. It asks one or more AI models.
4. It compares their answers.
5. It checks for disagreement.
6. It uses your saved corrections and project context.
7. It returns one answer with a confidence signal.
8. If the chat gets too long or stale, it carries the important context forward automatically.

The technical scoring and model-selection logic stays hidden by default.

You see a normal chat app.

---

## Accuracy modes

AUA-Veritas uses a simple accuracy slider.

You choose how carefully you want the app to check an answer.

### Fast

Uses one AI.

Best for quick, low-stakes questions.

Fast mode can stream responses live.

### Balanced

Uses one AI and performs a lightweight second check when useful.

Recommended default for everyday use.

### High

Asks several selected AI models in parallel and compares their answers.

Best for important questions where you want to know whether models agree.

### Maximum

Asks multiple models and performs an extra peer-review pass.

Best for high-stakes work, critical code, research, medical, legal, financial, or decisions you would normally verify manually.

---

## Confidence signals

Veritas uses simple confidence labels.

```text
Green  = High confidence
Amber  = Medium confidence
Red    = Low confidence / needs review
```

Examples:

```text
High confidence
Most selected models agreed, and the answer matched your saved project context.

Medium confidence
Models disagreed on part of the answer. Review before relying on it.

Low confidence
Models gave conflicting answers or contradicted saved corrections.
```

Veritas does not guarantee truth.

It helps you see when answers are more or less trustworthy based on model agreement, checks, and your saved corrections.

---

## Seamless context backup

AUA-Veritas can keep long-running work alive across breaks and context limits.

By default, Veritas manages context backup automatically based on inactivity, conversation length, and how much important context has changed.

You can also configure it:

- automatic
- after 15–20 minutes of inactivity
- hourly
- daily
- manual only
- off

Context refresh uses model tokens, so you can choose the balance between convenience and cost.

---

## Things Veritas remembers

Veritas can remember corrections, preferences, and project decisions.

Examples:

```text
Use Postgres, not SQLite, for this project.
Always add type hints to generated Python code.
The framework and the app are separate products.
Prefer concise explanations.
Avoid synchronous FastAPI patterns.
```

You stay in control.

You can edit or delete saved memories at any time. If you delete a correction, Veritas will not include it in future context refreshes.

---

## Look Under the Hood

Most users can ignore the internals.

But if you want more transparency, open **Look Under the Hood** in the top-right corner.

You can see:

- which models agreed or disagreed
- which model Veritas selected
- confidence history
- model rankings over time
- when a model score went up or down
- saved corrections that influenced an answer
- context backups and refreshes
- why Veritas marked an answer as high, medium, or low confidence

This makes Veritas less of a black box without forcing technical details into the main chat experience.

---

## Privacy

AUA-Veritas is designed to be local-first.

The v1 design is:

- conversations stored locally
- correction memory stored locally
- API keys stored in your operating system keychain
- no shared correction service
- no cloud sync by default
- no account required for the app itself

You bring your own API keys for the AI providers you want to use.

Your data stays on your machine unless you explicitly send a prompt to a model provider through your own API key.

---

## Supported model providers

AUA-Veritas is designed to support multiple frontier model providers.

Planned provider support includes:

| Provider | Role |
|---|---|
| OpenAI / ChatGPT API | Primary model + lightweight judge model |
| Anthropic Claude | Primary model + lightweight judge model |
| Google Gemini | Primary / fast model |
| xAI Grok | Current-events model |
| Mistral | Primary model |
| Groq-hosted Llama | Fast open-weights option |
| DeepSeek | Coding / low-cost option |

Not all providers are fully wired yet.

See the roadmap for implementation status.

---

## What AUA-Veritas is not

AUA-Veritas is not a guarantee of truth.

It is not a replacement for expert review in high-stakes situations.

It is not meant to expose research jargon or technical scoring details to normal users.

It is a practical desktop app for people who want:

- fewer repeated AI mistakes
- clearer confidence signals
- less manual comparison across models
- automatic project continuity
- local correction memory
- one continuous chat experience

---

## Relationship to AUA Framework

AUA-Veritas is a sister project to the Adaptive Utility Agent Framework.

The framework is for developers, MLEs, and AI infrastructure teams building adaptive multi-model systems.

AUA-Veritas is the consumer-facing desktop app.

It uses the ideas behind AUA — model comparison, confidence scoring, correction memory, and control logic — but hides the technical details behind a simple chat interface.

AUA Framework:

👉 https://github.com/praneethtota/Adaptive-Utility-Agent

AUA-Veritas:

👉 https://github.com/praneethtota/AUA-Veritas

---

## For technical readers

The main app is intentionally simple.

If you want the deeper design details, see the docs and roadmap:

- [Roadmap](roadmap.md)
- [Bug Report](docs/bug_report.md)
- Technical architecture docs coming soon

The technical design includes:

- model comparison
- confidence scoring
- peer review
- correction detection
- project-scoped memory
- context backup
- local model performance scoring
- model provider plugins

These details are hidden from normal users by default.

---

## Development status

AUA-Veritas is currently being built in phases.

### Phase 0

Foundation and early backend scaffolding.

### Phase 1

Model provider plugins and memory backend.

### Phase 2

Consumer desktop UI.

### Phase 3

Packaging and distribution.

### Phase 4

Polish for public launch.

See [roadmap.md](roadmap.md) for the current detailed plan.

---

## Run locally

AUA-Veritas is intended to become a desktop app.

During development, contributors can run the backend locally.

```bash
uvicorn api.main:app --port 47821 --reload
```

More complete setup instructions will be added as the app stabilizes.

---

## License

GPL-3.0

