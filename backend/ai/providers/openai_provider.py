"""
OpenAI Provider Adapter for Sarala AI.
"""

import os
from typing import Optional
from ai.providers.base import OpenAICompatibleAdapter


class OpenAIAdapter(OpenAICompatibleAdapter):
    """Adapter for official OpenAI models (GPT-4o, GPT-4o-mini)."""

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.getenv("OPENAI_API_KEY", "")
        super().__init__(name="openai", api_key=key, base_url=None)
