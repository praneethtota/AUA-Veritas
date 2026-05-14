"""
core/plugins/groq_backend.py — Groq backend plugin (Llama 3.3 70B).
OpenAI-compatible endpoint.
To contribute back to AUA: copy to aua/plugins/prebuilt/groq_backend.py
"""
from core.plugins.openai_backend import OpenAIBackend

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "llama-3.3-70b-versatile"


class GroqBackend(OpenAIBackend):
    """Groq backend (Llama 3.3 70B). OpenAI-compatible API."""

    def __init__(self, model_id: str = DEFAULT_MODEL, api_key: str = "") -> None:
        super().__init__(model_id=model_id, api_key=api_key, base_url=GROQ_BASE_URL)
