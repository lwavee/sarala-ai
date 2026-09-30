"""
Google Gemini Provider Adapter for Sarala AI.
Supports Google GenAI SDK and Google GenerativeAI (legacy) with streaming and robust error normalization.
"""

import os
import time
from typing import Optional, List, Dict, Any, AsyncIterator
from core.logger import logger
from ai.models import AIRequest, AIResponse, AIStreamChunk, AIUsage
from ai.errors import (
    AuthenticationError,
    normalize_provider_error
)
from ai.providers.base import BaseProviderAdapter


class GeminiAdapter(BaseProviderAdapter):
    """Adapter for Google Gemini models."""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__("gemini")
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.client = None
        self.is_new_sdk = False
        self._init_client()

    def _init_client(self):
        if not self.api_key or not self.api_key.startswith("AIzaSy"):
            return

        # Attempt modern google.genai SDK first
        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            self.is_new_sdk = True
            logger.info("Gemini Client initialized using google.genai.")
            return
        except Exception as e:
            logger.debug(f"google.genai initialization skipped: {e}. Trying legacy...")

        # Fallback to legacy google.generativeai SDK
        try:
            import google.generativeai as genai_legacy
            genai_legacy.configure(api_key=self.api_key)
            self.client = genai_legacy
            self.is_new_sdk = False
            logger.info("Gemini Client initialized using legacy google.generativeai.")
        except Exception as e:
            logger.warning(f"Gemini initialization failed: {e}")
            self.client = None

    def validate_configuration(self) -> bool:
        return bool(self.api_key and self.api_key.startswith("AIzaSy"))

    def is_available(self) -> bool:
        return self.validate_configuration() and (self.client is not None)

    def _format_prompt(self, request: AIRequest) -> str:
        """Formats AIRequest into a coherent unified prompt for Gemini."""
        parts: List[str] = []
        if request.system_context:
            parts.append(request.system_context)

        for m in request.messages:
            role = m.get("role", "user")
            content = m.get("content", "").strip()
            if not content:
                continue
            r_label = "System" if role == "system" else ("Sarla" if role in ("assistant", "sarla") else "User")
            parts.append(f"{r_label}: {content}")

        return "\n\n".join(parts)

    def generate(self, request: AIRequest) -> AIResponse:
        if not self.is_available():
            raise AuthenticationError(
                "Gemini API key is missing or invalid (must start with 'AIzaSy').",
                provider=self.name,
                model=request.model
            )

        prompt = self._format_prompt(request)
        start_time = time.time()
        req_id = request.metadata.get("request_id") or f"gemini_req_{int(time.time()*1000)}"

        try:
            content = ""
            total_tokens = 0

            if self.is_new_sdk and hasattr(self.client, "models"):
                # New Google GenAI SDK
                response = self.client.models.generate_content(
                    model=request.model,
                    contents=prompt
                )
                if response and hasattr(response, "text"):
                    content = response.text or ""
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    total_tokens = getattr(response.usage_metadata, "total_token_count", 0) or 0
            else:
                # Legacy GenerativeModel
                model_instance = self.client.GenerativeModel(request.model)
                response = model_instance.generate_content(prompt)
                if response and hasattr(response, "text"):
                    content = response.text or ""

            duration_ms = (time.time() - start_time) * 1000

            usage = None
            if total_tokens > 0:
                usage = AIUsage(total_tokens=total_tokens)

            return AIResponse(
                content=content,
                model=request.model,
                provider=self.name,
                finish_reason="stop",
                usage=usage,
                request_id=req_id,
                metadata={
                    "duration_ms": duration_ms,
                    "provider": self.name,
                    "model": request.model
                }
            )

        except Exception as e:
            raise normalize_provider_error(e, provider=self.name, model=request.model)

    async def stream(self, request: AIRequest) -> AsyncIterator[AIStreamChunk]:
        if not self.is_available():
            raise AuthenticationError(
                "Gemini API key is missing or invalid (must start with 'AIzaSy').",
                provider=self.name,
                model=request.model
            )

        prompt = self._format_prompt(request)

        try:
            if self.is_new_sdk and hasattr(self.client, "models"):
                stream = self.client.models.generate_content_stream(
                    model=request.model,
                    contents=prompt
                )
                for chunk in stream:
                    text = getattr(chunk, "text", "") or ""
                    if text:
                        yield AIStreamChunk(
                            content=text,
                            metadata={"provider": self.name, "model": request.model}
                        )
            else:
                model_instance = self.client.GenerativeModel(request.model)
                stream = model_instance.generate_content(prompt, stream=True)
                for chunk in stream:
                    text = getattr(chunk, "text", "") or ""
                    if text:
                        yield AIStreamChunk(
                            content=text,
                            metadata={"provider": self.name, "model": request.model}
                        )

            yield AIStreamChunk(
                content="",
                finish_reason="stop",
                metadata={"provider": self.name, "model": request.model}
            )

        except Exception as e:
            raise normalize_provider_error(e, provider=self.name, model=request.model)
