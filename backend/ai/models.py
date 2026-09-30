"""
AI Models, Configurations, Requests, and Response Normalization Layer.
Decouples providers, models, capabilities, and parameters from API endpoints.
"""

import os
from enum import Enum
from typing import Optional, List, Dict, Any, Set
from pydantic import BaseModel, Field

from ai.errors import ModelUnavailableError
from ai.tools.models import ToolCall, ToolResult


class ModelCapability(str, Enum):
    TEXT_GENERATION = "text_generation"
    STREAMING = "streaming"
    VISION = "vision"
    TOOL_CALLING = "tool_calling"
    STRUCTURED_OUTPUT = "structured_output"
    JSON_OUTPUT = "json_output"
    EMBEDDINGS = "embeddings"


class ModelConfig(BaseModel):
    """Configuration for a specific AI model provided by a specific provider."""
    provider: str
    model_name: str
    display_name: str
    capabilities: List[str] = Field(default_factory=lambda: [ModelCapability.TEXT_GENERATION.value])
    context_window: int = 32768
    supports_streaming: bool = True
    supports_tools: bool = False
    supports_vision: bool = False
    supports_json: bool = True
    enabled: bool = True
    max_output_tokens: int = 800

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities


class AIUsage(BaseModel):
    """Normalized token usage numbers returned from AI providers."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class AIRequest(BaseModel):
    """
    Provider-neutral internal request model.
    Encapsulates all execution parameters passed to Provider Adapters.
    """
    model: str
    provider: Optional[str] = None
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    system_context: Optional[str] = None
    temperature: Optional[float] = 0.7
    max_output_tokens: Optional[int] = 800
    stream: bool = False
    tools: Optional[List[Dict[str, Any]]] = None
    response_format: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AIResponse(BaseModel):
    """
    Normalized internal response model.
    Guarantees consistent structure regardless of the underlying provider.
    """
    content: str
    model: str
    provider: str
    finish_reason: Optional[str] = "stop"
    usage: Optional[AIUsage] = None
    request_id: str
    tool_calls: Optional[List[ToolCall]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AIStreamChunk(BaseModel):
    """
    Normalized streaming chunk model.
    Emitted iteratively during streaming response generation.
    """
    content: str = ""
    finish_reason: Optional[str] = None
    usage: Optional[AIUsage] = None
    tool_calls: Optional[List[ToolCall]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ModelRegistry:
    """
    Centralized Model Registry and Allowlist for Sarala AI.
    Tracks all supported models, default models, and capabilities.
    """

    def __init__(self):
        self._models: Dict[str, ModelConfig] = {}
        self._init_default_catalog()

    def _init_default_catalog(self):
        """Populates the registry with known models across currently supported providers."""
        # 1. Google Gemini Models
        self.register_model(ModelConfig(
            provider="gemini",
            model_name="gemini-1.5-flash",
            display_name="Gemini 1.5 Flash (Google)",
            capabilities=[
                ModelCapability.TEXT_GENERATION.value,
                ModelCapability.STREAMING.value,
                ModelCapability.VISION.value,
                ModelCapability.TOOL_CALLING.value,
                ModelCapability.STRUCTURED_OUTPUT.value,
                ModelCapability.JSON_OUTPUT.value,
            ],
            context_window=1048576,
            supports_streaming=True,
            supports_tools=True,
            supports_vision=True,
            supports_json=True,
            max_output_tokens=8192,
        ))
        self.register_model(ModelConfig(
            provider="gemini",
            model_name="gemini-2.0-flash",
            display_name="Gemini 2.0 Flash (Google)",
            capabilities=[
                ModelCapability.TEXT_GENERATION.value,
                ModelCapability.STREAMING.value,
                ModelCapability.VISION.value,
                ModelCapability.TOOL_CALLING.value,
                ModelCapability.STRUCTURED_OUTPUT.value,
                ModelCapability.JSON_OUTPUT.value,
            ],
            context_window=1048576,
            supports_streaming=True,
            supports_tools=True,
            supports_vision=True,
            supports_json=True,
            max_output_tokens=8192,
        ))

        # 2. Groq LPU Models (High-Speed Inference)
        self.register_model(ModelConfig(
            provider="groq",
            model_name="openai/gpt-oss-120b",
            display_name="GPT OSS 120B (Groq LPU)",
            capabilities=[
                ModelCapability.TEXT_GENERATION.value,
                ModelCapability.STREAMING.value,
                ModelCapability.TOOL_CALLING.value,
                ModelCapability.JSON_OUTPUT.value,
            ],
            context_window=131072,
            supports_streaming=True,
            supports_tools=True,
            supports_vision=False,
            supports_json=True,
            max_output_tokens=4096,
        ))
        self.register_model(ModelConfig(
            provider="groq",
            model_name="openai/gpt-oss-20b",
            display_name="GPT OSS 20B (Groq LPU)",
            capabilities=[
                ModelCapability.TEXT_GENERATION.value,
                ModelCapability.STREAMING.value,
                ModelCapability.TOOL_CALLING.value,
                ModelCapability.JSON_OUTPUT.value,
            ],
            context_window=131072,
            supports_streaming=True,
            supports_tools=True,
            supports_vision=False,
            supports_json=True,
            max_output_tokens=4096,
        ))
        self.register_model(ModelConfig(
            provider="groq",
            model_name="qwen/qwen3.6-27b",
            display_name="Qwen 3.6 27B (Groq LPU)",
            capabilities=[
                ModelCapability.TEXT_GENERATION.value,
                ModelCapability.STREAMING.value,
                ModelCapability.TOOL_CALLING.value,
                ModelCapability.JSON_OUTPUT.value,
            ],
            context_window=32768,
            supports_streaming=True,
            supports_tools=True,
            supports_vision=False,
            supports_json=True,
            max_output_tokens=4096,
        ))
        self.register_model(ModelConfig(
            provider="groq",
            model_name="llama-3.3-70b-versatile",
            display_name="Llama 3.3 70B Versatile (Groq)",
            capabilities=[
                ModelCapability.TEXT_GENERATION.value,
                ModelCapability.STREAMING.value,
                ModelCapability.TOOL_CALLING.value,
                ModelCapability.JSON_OUTPUT.value,
            ],
            context_window=128000,
            supports_streaming=True,
            supports_tools=True,
            supports_vision=False,
            supports_json=True,
            max_output_tokens=4096,
        ))

        # 3. OpenAI Models
        self.register_model(ModelConfig(
            provider="openai",
            model_name="gpt-4o-mini",
            display_name="GPT-4o Mini (OpenAI)",
            capabilities=[
                ModelCapability.TEXT_GENERATION.value,
                ModelCapability.STREAMING.value,
                ModelCapability.VISION.value,
                ModelCapability.TOOL_CALLING.value,
                ModelCapability.STRUCTURED_OUTPUT.value,
                ModelCapability.JSON_OUTPUT.value,
            ],
            context_window=128000,
            supports_streaming=True,
            supports_tools=True,
            supports_vision=True,
            supports_json=True,
            max_output_tokens=4096,
        ))
        self.register_model(ModelConfig(
            provider="openai",
            model_name="gpt-4o",
            display_name="GPT-4o (OpenAI)",
            capabilities=[
                ModelCapability.TEXT_GENERATION.value,
                ModelCapability.STREAMING.value,
                ModelCapability.VISION.value,
                ModelCapability.TOOL_CALLING.value,
                ModelCapability.STRUCTURED_OUTPUT.value,
                ModelCapability.JSON_OUTPUT.value,
            ],
            context_window=128000,
            supports_streaming=True,
            supports_tools=True,
            supports_vision=True,
            supports_json=True,
            max_output_tokens=4096,
        ))

        # 4. xAI Models
        self.register_model(ModelConfig(
            provider="xai",
            model_name="grok-beta",
            display_name="Grok Beta (xAI)",
            capabilities=[
                ModelCapability.TEXT_GENERATION.value,
                ModelCapability.STREAMING.value,
                ModelCapability.TOOL_CALLING.value,
                ModelCapability.JSON_OUTPUT.value,
            ],
            context_window=131072,
            supports_streaming=True,
            supports_tools=True,
            supports_vision=False,
            supports_json=True,
            max_output_tokens=4096,
        ))

        # 5. Mistral Models
        self.register_model(ModelConfig(
            provider="mistral",
            model_name="mistral-large-latest",
            display_name="Mistral Large (Mistral AI)",
            capabilities=[
                ModelCapability.TEXT_GENERATION.value,
                ModelCapability.STREAMING.value,
                ModelCapability.TOOL_CALLING.value,
                ModelCapability.JSON_OUTPUT.value,
            ],
            context_window=128000,
            supports_streaming=True,
            supports_tools=True,
            supports_vision=False,
            supports_json=True,
            max_output_tokens=4096,
        ))

        # 6. SiliconFlow Models
        self.register_model(ModelConfig(
            provider="siliconflow",
            model_name="deepseek-ai/DeepSeek-V2.5",
            display_name="DeepSeek V2.5 (SiliconFlow)",
            capabilities=[
                ModelCapability.TEXT_GENERATION.value,
                ModelCapability.STREAMING.value,
                ModelCapability.TOOL_CALLING.value,
                ModelCapability.JSON_OUTPUT.value,
            ],
            context_window=65536,
            supports_streaming=True,
            supports_tools=True,
            supports_vision=False,
            supports_json=True,
            max_output_tokens=4096,
        ))
        self.register_model(ModelConfig(
            provider="siliconflow",
            model_name="Qwen/Qwen2.5-72B-Instruct",
            display_name="Qwen 2.5 72B (SiliconFlow)",
            capabilities=[
                ModelCapability.TEXT_GENERATION.value,
                ModelCapability.STREAMING.value,
                ModelCapability.TOOL_CALLING.value,
                ModelCapability.JSON_OUTPUT.value,
            ],
            context_window=32768,
            supports_streaming=True,
            supports_tools=True,
            supports_vision=False,
            supports_json=True,
            max_output_tokens=4096,
        ))

    def register_model(self, config: ModelConfig):
        """Registers or updates a model configuration in the registry."""
        self._models[config.model_name] = config

    def get_model(self, model_name: str) -> Optional[ModelConfig]:
        """Returns model configuration by name if registered and enabled."""
        config = self._models.get(model_name)
        if config and config.enabled:
            return config
        return None

    def validate_model(self, model_name: str) -> ModelConfig:
        """Validates that a model is registered and enabled; raises ModelUnavailableError if not."""
        if not model_name or not isinstance(model_name, str):
            raise ModelUnavailableError("No model identifier specified.")
        config = self.get_model(model_name)
        if not config:
            raise ModelUnavailableError(
                f"Model '{model_name}' is not supported or not enabled in the model registry."
            )
        return config

    def list_models(self) -> List[ModelConfig]:
        """Returns all enabled registered models."""
        return [m for m in self._models.values() if m.enabled]

    def list_public_models(self) -> List[Dict[str, Any]]:
        """
        Returns a public-safe list of available models for the frontend.
        Excludes all secrets, internal URLs, or provider credentials.
        """
        default_model = self.get_default_model()
        result = []
        for m in self.list_models():
            result.append({
                "id": m.model_name,
                "name": m.display_name,
                "provider": m.provider,
                "capabilities": m.capabilities,
                "context_window": m.context_window,
                "supports_streaming": m.supports_streaming,
                "supports_vision": m.supports_vision,
                "supports_tools": m.supports_tools,
                "is_default": (m.model_name == default_model.model_name)
            })
        return result

    def get_default_model(self) -> ModelConfig:
        """
        Determines the default model based on environment configuration or availability.
        Priority:
        1. DEFAULT_AI_MODEL env variable
        2. First available model from configured default provider
        3. Groq default -> Gemini default -> OpenAI default
        """
        env_model = os.getenv("DEFAULT_AI_MODEL")
        if env_model and env_model in self._models and self._models[env_model].enabled:
            return self._models[env_model]

        # Check default provider
        default_provider = os.getenv("DEFAULT_AI_PROVIDER", "").lower()
        if default_provider:
            for m in self._models.values():
                if m.provider == default_provider and m.enabled:
                    return m

        # Check if Groq key exists (fastest response)
        if os.getenv("GROQ_API_KEY") and "openai/gpt-oss-120b" in self._models:
            return self._models["openai/gpt-oss-120b"]

        # Check if Gemini key exists
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        if gemini_key and gemini_key.startswith("AIzaSy") and "gemini-1.5-flash" in self._models:
            return self._models["gemini-1.5-flash"]

        # Check OpenAI key
        if os.getenv("OPENAI_API_KEY") and "gpt-4o-mini" in self._models:
            return self._models["gpt-4o-mini"]

        # Safe fallback: first enabled model in registry
        for m in self._models.values():
            if m.enabled:
                return m

        # Minimal fallback config if empty
        return ModelConfig(
            provider="gemini",
            model_name="gemini-1.5-flash",
            display_name="Gemini 1.5 Flash",
            capabilities=[ModelCapability.TEXT_GENERATION.value, ModelCapability.STREAMING.value],
            context_window=1048576,
        )

    def get_fallback_model(self, primary_model: Optional[ModelConfig] = None) -> Optional[ModelConfig]:
        """
        Returns a configured fallback model if available and distinct from primary_model.
        """
        env_fallback = os.getenv("FALLBACK_AI_MODEL")
        if env_fallback and env_fallback in self._models and self._models[env_fallback].enabled:
            if not primary_model or self._models[env_fallback].model_name != primary_model.model_name:
                return self._models[env_fallback]

        fallback_provider = os.getenv("FALLBACK_AI_PROVIDER", "").lower()
        if fallback_provider:
            for m in self._models.values():
                if m.provider == fallback_provider and m.enabled:
                    if not primary_model or m.model_name != primary_model.model_name:
                        return m

        # Automatic fallback order: Groq -> Gemini -> OpenAI -> SiliconFlow
        order = ["gemini-1.5-flash", "gpt-4o-mini", "openai/gpt-oss-120b", "deepseek-ai/DeepSeek-V2.5"]
        for model_id in order:
            if model_id in self._models and self._models[model_id].enabled:
                if not primary_model or primary_model.model_name != model_id:
                    # Only pick fallback if provider key is configured
                    provider = self._models[model_id].provider
                    if provider == "gemini" and os.getenv("GEMINI_API_KEY", "").startswith("AIzaSy"):
                        return self._models[model_id]
                    elif provider == "openai" and os.getenv("OPENAI_API_KEY"):
                        return self._models[model_id]
                    elif provider == "groq" and os.getenv("GROQ_API_KEY"):
                        return self._models[model_id]
                    elif provider == "siliconflow" and os.getenv("SILICONFLOW_API_KEY"):
                        return self._models[model_id]

        return None


# Global singleton registry
model_registry = ModelRegistry()
