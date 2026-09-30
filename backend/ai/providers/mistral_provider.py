"""
Mistral AI Provider Adapter for Sarala AI.
"""

import os
from typing import Optional
from ai.providers.base import OpenAICompatibleAdapter


class MistralAdapter(OpenAICompatibleAdapter):
    """Adapter for Mistral AI models."""

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.getenv("MISTRAL_API_KEY", "")
        super().__init__(name="mistral", api_key=key, base_url="https://api.mistral.ai/v1")
