"""
core/plugins/mistral_backend.py — Mistral AI backend plugin.
OpenAI-compatible endpoint.
To contribute back to AUA: copy to aua/plugins/prebuilt/mistral_backend.py
"""
from core.plugins.openai_backend import OpenAIBackend

MISTRAL_BASE_URL = "https://api.mistral.ai/v1"
DEFAULT_MODEL = "mistral-large-latest"


class MistralBackend(OpenAIBackend):
    """Mistral Large backend. OpenAI-compatible API."""

    def __init__(self, model_id: str = DEFAULT_MODEL, api_key: str = "") -> None:
        super().__init__(model_id=model_id, api_key=api_key, base_url=MISTRAL_BASE_URL)
