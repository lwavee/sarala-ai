"""
SiliconFlow Provider Adapter for Sarala AI.
Supports DeepSeek and Qwen models hosted on SiliconFlow.
"""

import os
from typing import Optional
from ai.providers.base import OpenAICompatibleAdapter


class SiliconFlowAdapter(OpenAICompatibleAdapter):
    """Adapter for SiliconFlow models (DeepSeek, Qwen)."""

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.getenv("SILICONFLOW_API_KEY", "")
        super().__init__(name="siliconflow", api_key=key, base_url="https://api.siliconflow.cn/v1")
