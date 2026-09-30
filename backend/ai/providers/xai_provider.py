"""
xAI (Grok) Provider Adapter for Sarala AI.
"""

import os
from typing import Optional
from ai.providers.base import OpenAICompatibleAdapter


class XAIAdapter(OpenAICompatibleAdapter):
    """Adapter for xAI Grok models."""

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.getenv("XAI_API_KEY", "")
        super().__init__(name="xai", api_key=key, base_url="https://api.x.ai/v1")
