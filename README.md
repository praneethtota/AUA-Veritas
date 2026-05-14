# AUA-Veritas

> A standalone AI assistant that asks multiple frontier models, then tells you who gave the most trustworthy answer.

**Status:** Phase 0 — in development  
**License:** GPL-3.0  
**Built on:** [AUA Framework](https://github.com/praneethtota/Adaptive-Utility-Agent)

---

## What it does

AUA-Veritas wraps frontier AI models (ChatGPT, Claude, Gemini, and more) and runs AUA's
control logic silently underneath — routing, welfare-maximizing model selection, contradiction
detection, peer review, and correction memory that improves over time.

You get a more truthful answer than any single model gives directly.

## Accuracy levels

| Level | What happens | Relative cost |
|---|---|---|
| **Fast** | One best model answers. Past corrections injected. | $ |
| **Balanced** | Two models answer. Best selected by welfare score. | $$ |
| **High** | All selected models answer. VCG picks the best. | $$$ |
| **Maximum** | All models answer. Other models peer-review the winner. | $$$$ |

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
