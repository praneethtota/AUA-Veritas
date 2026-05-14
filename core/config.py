"""
core/config.py — AUA-Veritas configuration.

Simplified config for single-user consumer app.
No YAML specialists, no vLLM/Ollama setup. All configuration
comes from user preferences stored in SQLite + API keys from OS keychain.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


# ── App paths ─────────────────────────────────────────────────────────────────

def app_data_dir() -> Path:
    """Platform-appropriate data directory for AUA-Veritas."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif os.uname().sysname == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    d = base / "AUA-Veritas"
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path() -> Path:
    return app_data_dir() / "veritas.db"


def log_path() -> Path:
    return app_data_dir() / "veritas.log"


# ── Accuracy levels ───────────────────────────────────────────────────────────

ACCURACY_LEVELS = {
    "fast":     {"label": "Fast",     "max_models": 1, "peer_review": False},
    "balanced": {"label": "Balanced", "max_models": 2, "peer_review": False},
    "high":     {"label": "High",     "max_models": 9, "peer_review": False},
    "maximum":  {"label": "Maximum",  "max_models": 9, "peer_review": True},
}


# ── Model registry ────────────────────────────────────────────────────────────

SUPPORTED_MODELS: dict[str, dict] = {
    "gpt-4o": {
        "provider": "openai",
        "display_name": "GPT-4o",
        "plugin_class": "core.plugins.openai_backend:OpenAIBackend",
        "is_cheap_judge": False,
        "context_window": 128000,
    },
    "gpt-4o-mini": {
        "provider": "openai",
        "display_name": "GPT-4o mini",
        "plugin_class": "core.plugins.openai_backend:OpenAIBackend",
        "is_cheap_judge": True,   # used as peer-review judge
        "context_window": 128000,
    },
    "claude-sonnet-4-6": {
        "provider": "anthropic",
        "display_name": "Claude Sonnet",
        "plugin_class": "core.plugins.anthropic_backend:AnthropicBackend",
        "is_cheap_judge": False,
        "context_window": 200000,
    },
    "claude-haiku-4-5-20251001": {
        "provider": "anthropic",
        "display_name": "Claude Haiku",
        "plugin_class": "core.plugins.anthropic_backend:AnthropicBackend",
        "is_cheap_judge": True,   # used as peer-review judge
        "context_window": 200000,
    },
    "gemini-1.5-pro": {
        "provider": "google",
        "display_name": "Gemini 1.5 Pro",
        "plugin_class": "core.plugins.google_backend:GoogleBackend",
        "is_cheap_judge": False,
        "context_window": 1000000,
    },
    "gemini-2.0-flash": {
        "provider": "google",
        "display_name": "Gemini 2.0 Flash",
        "plugin_class": "core.plugins.google_backend:GoogleBackend",
        "is_cheap_judge": True,
        "context_window": 1000000,
    },
    "grok-2": {
        "provider": "xai",
        "display_name": "Grok-2",
        "plugin_class": "core.plugins.xai_backend:XAIBackend",
        "is_cheap_judge": False,
        "context_window": 131072,
    },
    "mistral-large-latest": {
        "provider": "mistral",
        "display_name": "Mistral Large",
        "plugin_class": "core.plugins.mistral_backend:MistralBackend",
        "is_cheap_judge": False,
        "context_window": 128000,
    },
    "llama-3.3-70b-versatile": {
        "provider": "groq",
        "display_name": "Llama 3.3 70B",
        "plugin_class": "core.plugins.groq_backend:GroqBackend",
        "is_cheap_judge": False,
        "context_window": 128000,
    },
    "deepseek-chat": {
        "provider": "deepseek",
        "display_name": "DeepSeek-V3",
        "plugin_class": "core.plugins.deepseek_backend:DeepSeekBackend",
        "is_cheap_judge": False,
        "context_window": 64000,
    },
}

# Provider → API key name in OS keychain
KEYCHAIN_SERVICE = "AUA-Veritas"
PROVIDER_KEY_NAMES: dict[str, str] = {
    "openai":    "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google":    "GOOGLE_API_KEY",
    "xai":       "XAI_API_KEY",
    "mistral":   "MISTRAL_API_KEY",
    "groq":      "GROQ_API_KEY",
    "deepseek":  "DEEPSEEK_API_KEY",
}

# High-stakes domains — skip automated retry, always add disclaimer callout
HIGH_STAKES_DOMAINS = frozenset({"medicine", "legal", "finance", "aviation", "surgery"})

# Peer review prompt template
PEER_REVIEW_PROMPT = """You are reviewing an AI-generated answer for accuracy.

Question: {query}

Answer to review:
{answer}

Is this answer correct? Respond with:
1. VERDICT: correct / incorrect / partially_correct
2. ISSUES: (if any) what is wrong and why
3. CORRECTION: (if incorrect/partial) what the correct answer is

Be concise and specific."""
