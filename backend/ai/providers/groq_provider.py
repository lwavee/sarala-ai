"""
Groq LPU Provider Adapter for Sarala AI.
Ultra-fast sub-second LLM inference via Groq LPUs.
"""

import os
from typing import Optional
from core.logger import logger
from ai.providers.base import OpenAICompatibleAdapter


class GroqAdapter(OpenAICompatibleAdapter):
    """Adapter for Groq LPU high-speed inference."""

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.getenv("GROQ_API_KEY", "")
        # Groq can be initialized using Groq SDK or OpenAI client with Groq base URL
        super().__init__(name="groq", api_key=key, base_url="https://api.groq.com/openai/v1")

    def _init_client(self):
        if not self.api_key:
            return
        # Try native Groq client first if installed
        try:
            from groq import Groq
            self.client = Groq(api_key=self.api_key, timeout=self.timeout)
            logger.info("Groq native Client initialized.")
            return
        except Exception as e:
            logger.debug(f"Native Groq init skipped: {e}. Falling back to OpenAI compatible client.")

        # Fallback to OpenAICompatibleAdapter client
        super()._init_client()
