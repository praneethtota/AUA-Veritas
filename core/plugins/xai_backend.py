"""
core/plugins/xai_backend.py — xAI Grok backend plugin.
OpenAI-compatible endpoint.
To contribute back to AUA: copy to aua/plugins/prebuilt/xai_backend.py
"""
from core.plugins.openai_backend import OpenAIBackend

XAI_BASE_URL = "https://api.x.ai/v1"
DEFAULT_MODEL = "grok-2"


class XAIBackend(OpenAIBackend):
    """xAI Grok-2 backend. OpenAI-compatible API."""

    def __init__(self, model_id: str = DEFAULT_MODEL, api_key: str = "") -> None:
        super().__init__(model_id=model_id, api_key=api_key, base_url=XAI_BASE_URL)
