"""
Base Provider Adapter Interface and OpenAI-Compatible Adapter Foundation.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, AsyncIterator
import time
import json
import re
from core.logger import logger
from ai.models import AIRequest, AIResponse, AIStreamChunk, AIUsage, ToolCall
from ai.errors import (
    AIError,
    AuthenticationError,
    CapabilityNotSupportedError,
    normalize_provider_error
)


class BaseProviderAdapter(ABC):
    """Abstract Base Class for all AI Provider Adapters."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def validate_configuration(self) -> bool:
        """Validates that necessary API keys and credentials are present and valid."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the provider is currently available and ready to accept requests."""
        pass

    @abstractmethod
    def generate(self, request: AIRequest) -> AIResponse:
        """Generates a complete non-streaming AI response."""
        pass

    @abstractmethod
    def stream(self, request: AIRequest) -> AsyncIterator[AIStreamChunk]:
        """Generates an asynchronous stream of normalized response chunks."""
        pass


class OpenAICompatibleAdapter(BaseProviderAdapter):
    """
    Standard adapter for providers implementing the OpenAI-compatible REST/Chat Completions API.
    Supports: OpenAI, Groq, xAI, Mistral, SiliconFlow.
    """

    def __init__(
        self,
        name: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0
    ):
        super().__init__(name)
        self.api_key = api_key or ""
        self.base_url = base_url
        self.timeout = timeout
        self.client: Any = None
        self._init_client()

    def _init_client(self):
        if not self.api_key:
            return
        try:
            from openai import OpenAI
            kwargs: Dict[str, Any] = {
                "api_key": self.api_key,
                "timeout": self.timeout,
            }
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self.client = OpenAI(**kwargs)
            logger.info(f"OpenAI-compatible client initialized for provider '{self.name}'.")
        except Exception as e:
            logger.warning(f"Failed to initialize client for provider '{self.name}': {e}")
            self.client = None

    def validate_configuration(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 5)

    def is_available(self) -> bool:
        return self.validate_configuration() and (self.client is not None)

    def _prepare_messages(self, request: AIRequest) -> List[Dict[str, Any]]:
        """Prepares messages, ensuring proper system role placement and content formatting."""
        messages: List[Dict[str, Any]] = []
        if request.system_context:
            messages.append({"role": "system", "content": request.system_context})
        for m in request.messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            # Ensure assistant role is standard
            if role in ("sarla", "assistant"):
                role = "assistant"
            elif role == "system":
                role = "system"
            else:
                role = "user"
            messages.append({"role": role, "content": content})
        return messages

    def _clean_content(self, text: str) -> str:
        """Removes model reasoning tags (e.g. <think>...</think>) for clean conversational output."""
        if not text:
            return ""
        if "<think>" in text and "</think>" in text:
            text = re.sub(r'<think>[\s\S]*?</think>', '', text).strip()
        return text

    def generate(self, request: AIRequest) -> AIResponse:
        if not self.is_available() or self.client is None:
            raise AuthenticationError(
                f"Provider '{self.name}' is not configured or missing API key.",
                provider=self.name,
                model=request.model
            )

        client = self.client
        messages = self._prepare_messages(request)
        start_time = time.time()

        try:
            kwargs: Dict[str, Any] = {
                "model": request.model,
                "messages": messages,
                "temperature": request.temperature if request.temperature is not None else 0.7,
                "max_tokens": request.max_output_tokens or 800,
                "stream": False,
            }
            if request.tools:
                kwargs["tools"] = request.tools
            if request.response_format:
                kwargs["response_format"] = request.response_format

            completion = client.chat.completions.create(**kwargs)

            content = ""
            finish_reason = "stop"
            raw_tool_calls = None
            if completion.choices and len(completion.choices) > 0:
                choice = completion.choices[0]
                content = choice.message.content or ""
                finish_reason = getattr(choice, "finish_reason", "stop") or "stop"
                raw_tool_calls = getattr(choice.message, "tool_calls", None)

            content = self._clean_content(content)
            duration_ms = (time.time() - start_time) * 1000

            normalized_tool_calls: Optional[List[ToolCall]] = None
            if raw_tool_calls:
                normalized_tool_calls = []
                for tc in raw_tool_calls:
                    tc_id = getattr(tc, "id", "") or f"call_{int(time.time()*1000)}"
                    tc_func = getattr(tc, "function", None)
                    func_name = getattr(tc_func, "name", "") if tc_func else ""
                    raw_args = getattr(tc_func, "arguments", "{}") if tc_func else "{}"
                    if isinstance(raw_args, str):
                        try:
                            parsed_args = json.loads(raw_args)
                        except Exception:
                            parsed_args = {}
                    elif isinstance(raw_args, dict):
                        parsed_args = raw_args
                    else:
                        parsed_args = {}
                    normalized_tool_calls.append(
                        ToolCall(
                            id=tc_id,
                            name=func_name,
                            arguments=parsed_args,
                            user_id=request.metadata.get("user_id"),
                            conversation_id=request.metadata.get("conversation_id"),
                        )
                    )

            usage = None
            if hasattr(completion, "usage") and completion.usage:
                usage = AIUsage(
                    input_tokens=getattr(completion.usage, "prompt_tokens", 0) or 0,
                    output_tokens=getattr(completion.usage, "completion_tokens", 0) or 0,
                    total_tokens=getattr(completion.usage, "total_tokens", 0) or 0,
                )

            req_id = request.metadata.get("request_id") or f"req_{int(time.time()*1000)}"

            return AIResponse(
                content=content,
                model=request.model,
                provider=self.name,
                finish_reason=finish_reason,
                usage=usage,
                request_id=req_id,
                tool_calls=normalized_tool_calls,
                metadata={
                    "duration_ms": duration_ms,
                    "provider": self.name,
                    "model": request.model
                }
            )

        except Exception as e:
            raise normalize_provider_error(e, provider=self.name, model=request.model)

    async def stream(self, request: AIRequest) -> AsyncIterator[AIStreamChunk]:
        if not self.is_available() or self.client is None:
            raise AuthenticationError(
                f"Provider '{self.name}' is not configured or missing API key.",
                provider=self.name,
                model=request.model
            )

        client = self.client
        messages = self._prepare_messages(request)

        try:
            kwargs: Dict[str, Any] = {
                "model": request.model,
                "messages": messages,
                "temperature": request.temperature if request.temperature is not None else 0.7,
                "max_tokens": request.max_output_tokens or 800,
                "stream": True,
            }
            if request.tools:
                kwargs["tools"] = request.tools
            if request.response_format:
                kwargs["response_format"] = request.response_format

            stream_response = client.chat.completions.create(**kwargs)

            for chunk in stream_response:
                if chunk.choices and len(chunk.choices) > 0:
                    choice = chunk.choices[0]
                    delta = getattr(choice, "delta", None)
                    content_chunk = delta.content if delta and delta.content else ""
                    finish_reason = getattr(choice, "finish_reason", None)

                    if content_chunk or finish_reason:
                        yield AIStreamChunk(
                            content=content_chunk or "",
                            finish_reason=finish_reason,
                            metadata={"provider": self.name, "model": request.model}
                        )

        except Exception as e:
            raise normalize_provider_error(e, provider=self.name, model=request.model)
