"""
core/plugins/deepseek_backend.py — DeepSeek backend plugin.
OpenAI-compatible endpoint.
To contribute back to AUA: copy to aua/plugins/prebuilt/deepseek_backend.py
"""
from core.plugins.openai_backend import OpenAIBackend

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"


class DeepSeekBackend(OpenAIBackend):
    """DeepSeek-V3 backend. OpenAI-compatible API."""

    def __init__(self, model_id: str = DEFAULT_MODEL, api_key: str = "") -> None:
        super().__init__(model_id=model_id, api_key=api_key, base_url=DEEPSEEK_BASE_URL)
