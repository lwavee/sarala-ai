"""
AI Provider Adapters Registry and Factory for Sarala AI.
"""

from typing import Dict, Optional
from ai.providers.base import BaseProviderAdapter
from ai.providers.gemini_provider import GeminiAdapter
from ai.providers.groq_provider import GroqAdapter
from ai.providers.openai_provider import OpenAIAdapter
from ai.providers.xai_provider import XAIAdapter
from ai.providers.mistral_provider import MistralAdapter
from ai.providers.siliconflow_provider import SiliconFlowAdapter


_ADAPTER_REGISTRY: Dict[str, BaseProviderAdapter] = {}


def get_provider_adapter(provider_name: str) -> Optional[BaseProviderAdapter]:
    """Returns the singleton adapter instance for the specified provider."""
    normalized = provider_name.strip().lower()
    if normalized in _ADAPTER_REGISTRY:
        return _ADAPTER_REGISTRY[normalized]

    adapter: Optional[BaseProviderAdapter] = None
    if normalized == "gemini":
        adapter = GeminiAdapter()
    elif normalized == "groq":
        adapter = GroqAdapter()
    elif normalized == "openai":
        adapter = OpenAIAdapter()
    elif normalized == "xai":
        adapter = XAIAdapter()
    elif normalized == "mistral":
        adapter = MistralAdapter()
    elif normalized == "siliconflow":
        adapter = SiliconFlowAdapter()

    if adapter:
        _ADAPTER_REGISTRY[normalized] = adapter

    return adapter


def list_available_providers() -> Dict[str, bool]:
    """Returns a dict of supported providers and whether they are configured & available."""
    providers = ["gemini", "groq", "openai", "xai", "mistral", "siliconflow"]
    status = {}
    for p in providers:
        adapter = get_provider_adapter(p)
        status[p] = adapter.is_available() if adapter else False
    return status


__all__ = [
    "BaseProviderAdapter",
    "GeminiAdapter",
    "GroqAdapter",
    "OpenAIAdapter",
    "XAIAdapter",
    "MistralAdapter",
    "SiliconFlowAdapter",
    "get_provider_adapter",
    "list_available_providers",
]
