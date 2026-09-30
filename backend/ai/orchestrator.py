"""
Central AI Provider & Model Orchestrator for Sarala AI.
Coordinates model selection, capability verification, provider adapters,
retries, fallbacks, streaming, context limits, and safe telemetry.
"""

import os
import time
import uuid
import json
import asyncio
from typing import Optional, Dict, Any, AsyncIterator, List, Set
from core.logger import logger
from ai.models import (
    ModelConfig,
    ModelRegistry,
    model_registry,
    AIRequest,
    AIResponse,
    AIStreamChunk,
    AIUsage,
    ModelCapability,
)
from ai.errors import (
    AIError,
    AuthenticationError,
    CapabilityNotSupportedError,
    ContextTooLargeError,
    ModelUnavailableError,
    ProviderUnavailableError,
    RateLimitError,
    TimeoutError,
    normalize_provider_error,
)
from ai.providers import get_provider_adapter, list_available_providers
from ai.tools.registry import tool_registry
from ai.tools.executor import tool_executor
from ai.tools.models import ToolCall, ToolResult


class AIOrchestrator:
    """
    Central AI Orchestrator.
    Separates Chat API and Context Building from AI Providers and Model Selection.
    """

    def __init__(self, registry: Optional[ModelRegistry] = None):
        self.registry = registry or model_registry
        self.default_timeout = float(os.getenv("AI_TIMEOUT_SECONDS", "30.0"))
        self.max_retries = int(os.getenv("AI_RETRY_COUNT", "2"))
        self.max_tool_calls_per_request = int(os.getenv("MAX_TOOL_CALLS_PER_REQUEST", "5"))
        self._in_flight_requests: Set[str] = set()

    def _estimate_tokens(self, text: str) -> int:
        """Heuristic token estimator (average ~4 chars per token)."""
        if not text:
            return 0
        return max(1, len(text) // 4)

    def _validate_request_capabilities(self, request: AIRequest, model_config: ModelConfig):
        """Verifies that requested features are supported by the target model."""
        if request.stream and not model_config.supports_streaming:
            raise CapabilityNotSupportedError(
                f"Model '{model_config.model_name}' does not support streaming.",
                provider=model_config.provider,
                model=model_config.model_name,
            )

        if request.tools and not model_config.supports_tools:
            raise CapabilityNotSupportedError(
                f"Model '{model_config.model_name}' does not support tools or function calling.",
                provider=model_config.provider,
                model=model_config.model_name,
            )

        if request.response_format and not model_config.supports_json:
            raise CapabilityNotSupportedError(
                f"Model '{model_config.model_name}' does not support structured JSON output.",
                provider=model_config.provider,
                model=model_config.model_name,
            )

    def _validate_context_length(self, request: AIRequest, model_config: ModelConfig):
        """Validates that input context fits within the model's context window."""
        total_tokens = 0
        if request.system_context:
            total_tokens += self._estimate_tokens(request.system_context)

        for m in request.messages:
            total_tokens += self._estimate_tokens(str(m.get("content", "")))

        max_out = request.max_output_tokens or model_config.max_output_tokens
        if (total_tokens + max_out) > model_config.context_window:
            raise ContextTooLargeError(
                f"Request context size (~{total_tokens} tokens + {max_out} output) exceeds "
                f"maximum context window of {model_config.context_window} tokens for model '{model_config.model_name}'.",
                provider=model_config.provider,
                model=model_config.model_name,
            )

    def select_model(
        self,
        requested_model: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> ModelConfig:
        """
        Validates requested model against allowlist, or selects configured default.
        Never permits arbitrary endpoints or unauthorized model names.
        """
        if requested_model:
            return self.registry.validate_model(requested_model)

        # Task-type aware default selection if provided
        if task_type == "vision":
            for m in self.registry.list_models():
                if m.supports_vision:
                    adapter = get_provider_adapter(m.provider)
                    if adapter and adapter.is_available():
                        return m

        return self.registry.get_default_model()

    def generate(self, request: AIRequest) -> AIResponse:
        """
        Executes a non-streaming AI request through provider adapters with
        model validation, capability verification, controlled retries, and fallback.
        """
        req_id = request.metadata.get("request_id") or f"req_{uuid.uuid4().hex[:12]}"
        request.metadata["request_id"] = req_id

        # Deduplicate simultaneous duplicate submissions
        if req_id in self._in_flight_requests:
            logger.warning(f"Duplicate AI request detected for request_id: {req_id}. Allowing to proceed.")
        self._in_flight_requests.add(req_id)

        try:
            # 1. Model Resolution & Validation
            model_config = self.select_model(request.model, task_type=request.metadata.get("task_type"))
            request.model = model_config.model_name
            request.provider = model_config.provider

            # 2. Capability & Context Constraints
            self._validate_request_capabilities(request, model_config)
            self._validate_context_length(request, model_config)

            # 3. Provider Resolution
            adapter = get_provider_adapter(model_config.provider)
            if not adapter or not adapter.is_available():
                # Attempt immediate fallback if primary provider key is not configured
                fallback_config = self.registry.get_fallback_model(model_config)
                if fallback_config:
                    logger.info(
                        f"Primary provider '{model_config.provider}' unavailable. Falling back to '{fallback_config.provider}' ({fallback_config.model_name})."
                    )
                    request.model = fallback_config.model_name
                    request.provider = fallback_config.provider
                    adapter = get_provider_adapter(fallback_config.provider)
                    model_config = fallback_config

            if not adapter or not adapter.is_available():
                raise ProviderUnavailableError(
                    f"AI Provider '{model_config.provider}' is not configured or unavailable.",
                    provider=model_config.provider,
                    model=model_config.model_name,
                )

            # 4. Attempt Execution with Retries
            last_error: Optional[AIError] = None
            for attempt in range(self.max_retries + 1):
                try:
                    logger.info(
                        f"AI Request [{req_id}] -> Provider: {model_config.provider}, Model: {model_config.model_name} (Attempt {attempt+1}/{self.max_retries+1})"
                    )
                    response = adapter.generate(request)
                    self._log_safe_telemetry(req_id, response, fallback_used=False)
                    return response
                except Exception as err:
                    norm_err = normalize_provider_error(err, provider=model_config.provider, model=model_config.model_name)
                    last_error = norm_err
                    if norm_err.retryable and attempt < self.max_retries:
                        backoff = 0.25 * (2 ** attempt)
                        logger.warning(
                            f"Transient error with {model_config.provider} ({norm_err.code}): {norm_err.message}. Retrying in {backoff:.2f}s..."
                        )
                        time.sleep(backoff)
                        continue
                    else:
                        break

            # 5. Fallback Provider Handling (Reusing the SAME prepared context)
            fallback_config = self.registry.get_fallback_model(model_config)
            if fallback_config and last_error and (isinstance(last_error, (TimeoutError, ProviderUnavailableError, RateLimitError)) or getattr(last_error, 'retryable', False)):
                fb_adapter = get_provider_adapter(fallback_config.provider)
                if fb_adapter and fb_adapter.is_available():
                    error_msg = getattr(last_error, "message", str(last_error))
                    logger.warning(
                        f"Triggering Fallback: Switching from '{model_config.provider}' to '{fallback_config.provider}' ({fallback_config.model_name}) due to: {error_msg}"
                    )
                    fallback_req = request.model_copy(deep=True)
                    fallback_req.model = fallback_config.model_name
                    fallback_req.provider = fallback_config.provider
                    fallback_req.metadata["fallback_used"] = True
                    fallback_req.metadata["original_provider"] = model_config.provider
                    fallback_req.metadata["original_model"] = model_config.model_name

                    try:
                        fb_response = fb_adapter.generate(fallback_req)
                        fb_response.metadata["fallback_used"] = True
                        fb_response.metadata["original_provider"] = model_config.provider
                        fb_response.metadata["original_model"] = model_config.model_name
                        self._log_safe_telemetry(req_id, fb_response, fallback_used=True)
                        return fb_response
                    except Exception as fb_err:
                        logger.error(f"Fallback provider '{fallback_config.provider}' also failed: {fb_err}")

            if last_error:
                raise last_error

            raise ProviderUnavailableError("AI generation failed with no response generated.")

        finally:
            self._in_flight_requests.discard(req_id)

    async def stream(self, request: AIRequest) -> AsyncIterator[AIStreamChunk]:
        """
        Executes a streaming AI request through provider adapters with
        model validation, capability verification, and normalized chunk output.
        """
        req_id = request.metadata.get("request_id") or f"stream_req_{uuid.uuid4().hex[:12]}"
        request.metadata["request_id"] = req_id
        request.stream = True

        # 1. Model Resolution & Validation
        model_config = self.select_model(request.model, task_type=request.metadata.get("task_type"))
        request.model = model_config.model_name
        request.provider = model_config.provider

        # 2. Capability & Context Constraints
        self._validate_request_capabilities(request, model_config)
        self._validate_context_length(request, model_config)

        # 3. Provider Resolution
        adapter = get_provider_adapter(model_config.provider)
        if not adapter or not adapter.is_available():
            fallback_config = self.registry.get_fallback_model(model_config)
            if fallback_config:
                logger.info(
                    f"Primary provider '{model_config.provider}' unavailable for streaming. Falling back to '{fallback_config.provider}'."
                )
                request.model = fallback_config.model_name
                request.provider = fallback_config.provider
                adapter = get_provider_adapter(fallback_config.provider)
                model_config = fallback_config

        if not adapter or not adapter.is_available():
            raise ProviderUnavailableError(
                f"AI Provider '{model_config.provider}' is unavailable for streaming.",
                provider=model_config.provider,
                model=model_config.model_name,
            )

        logger.info(f"AI Stream [{req_id}] -> Provider: {model_config.provider}, Model: {model_config.model_name}")

        try:
            async for chunk in adapter.stream(request):
                yield chunk
        except Exception as e:
            norm_err = normalize_provider_error(e, provider=model_config.provider, model=model_config.model_name)
            logger.error(f"Stream error on provider '{model_config.provider}': {norm_err.message}")
            raise norm_err

    def generate_with_tools(
        self,
        request: AIRequest,
        user_id: str = "",
        user_role: str = "user",
        conversation_id: str = "",
        max_tool_iterations: Optional[int] = None,
    ) -> AIResponse:
        """
        Executes an AI request with controlled tool execution loop (Task 1.8).
        1. Injects authorized tool schemas into request.tools if target model supports tools.
        2. Loops up to max_tool_iterations:
           - Generates response from model.
           - If response has tool_calls:
             - For each tool call:
               - Checks loop storm protections.
               - Executes via tool_executor.execute().
               - If tool requires confirmation: returns pending confirmation response immediately.
               - Appends assistant tool_calls message and tool result messages.
           - Else:
             - Breaks and returns final natural-language AI response.
        """
        model_config = self.select_model(request.model, task_type=request.metadata.get("task_type"))

        # If model does not support tools, generate standard response directly
        if not model_config.supports_tools:
            return self.generate(request)

        # Retrieve available tool schemas for this user
        if not request.tools:
            schemas = tool_registry.get_schemas_for_model(
                user_role=user_role,
                authenticated=bool(user_id and str(user_id).strip()),
            )
            if schemas:
                request.tools = schemas

        # If no tools configured or available, run standard generation
        if not request.tools:
            return self.generate(request)

        max_iterations = max_tool_iterations or self.max_tool_calls_per_request
        executed_tools: List[Dict[str, Any]] = []
        call_fingerprints: Dict[str, int] = {}
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            response = self.generate(request)

            # If no tool calls requested by model, generation is complete
            if not response.tool_calls or response.finish_reason != "tool_calls":
                response.metadata["tool_executions"] = executed_tools
                return response

            # Model requested one or more tool calls
            # Append assistant message with tool calls to conversation context
            assistant_turn = {
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments) if isinstance(tc.arguments, dict) else str(tc.arguments),
                        }
                    }
                    for tc in response.tool_calls
                ]
            }
            request.messages.append(assistant_turn)

            # Process each requested tool call
            for tc in response.tool_calls:
                arg_repr = json.dumps(tc.arguments, sort_keys=True) if isinstance(tc.arguments, dict) else str(tc.arguments)
                fp = f"{tc.name}:{arg_repr}"
                call_fingerprints[fp] = call_fingerprints.get(fp, 0) + 1

                # Loop Storm Protection: prevent runaway repeat calls
                if call_fingerprints[fp] > 2:
                    logger.warning(f"Repeated tool call suppressed for '{tc.name}' to prevent infinite loop.")
                    tool_res = ToolResult(
                        tool_call_id=tc.id,
                        tool_name=tc.name,
                        success=False,
                        error="Repeated identical tool call suppressed to protect against infinite loops.",
                        error_code="RATE_LIMITED",
                    )
                else:
                    tool_res = tool_executor.execute(
                        tool_name=tc.name,
                        arguments=tc.arguments,
                        user_id=user_id,
                        role=user_role,
                        conversation_id=conversation_id,
                        tool_call_id=tc.id,
                    )

                executed_tools.append({
                    "tool_name": tc.name,
                    "tool_call_id": tc.id,
                    "success": tool_res.success,
                    "duration_ms": tool_res.duration_ms,
                    "requires_confirmation": tool_res.requires_confirmation,
                    "confirmation_token": tool_res.confirmation_token,
                    "error_code": tool_res.error_code,
                })

                # If confirmation is required, stop the loop and return structured confirmation state
                if tool_res.requires_confirmation:
                    tool_msg = {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": json.dumps(tool_res.to_dict()),
                    }
                    request.messages.append(tool_msg)
                    return AIResponse(
                        content=f"Action '{tc.name}' requires your explicit confirmation before proceeding.",
                        model=request.model,
                        provider=request.provider or model_config.provider,
                        finish_reason="stop",
                        request_id=request.metadata.get("request_id") or f"req_{int(time.time()*1000)}",
                        tool_calls=[tc],
                        metadata={
                            "requires_confirmation": True,
                            "confirmation_token": tool_res.confirmation_token,
                            "tool_executions": executed_tools,
                        }
                    )

                # Append tool result to context for next model iteration
                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "content": json.dumps(tool_res.to_dict()),
                }
                request.messages.append(tool_msg)

        # Loop limit reached: force final model synthesis without additional tool calls
        logger.warning(f"Max tool calls ({max_iterations}) reached. Generating final model synthesis.")
        request.tools = None
        final_resp = self.generate(request)
        final_resp.metadata["tool_executions"] = executed_tools
        return final_resp

    def generate_from_context(
        self,
        user_input: str,
        built_context: Any = None,
        external_context: str = "",
        theme_mode: str = "normal",
        model: Optional[str] = None,
        is_live: bool = False,
        task_type: Optional[str] = None,
        user_id: str = "",
        conversation_id: str = "",
        enable_tools: bool = True,
        role: str = "user",
    ) -> AIResponse:
        """
        Bridges AIContextBuilder (Task 1.6) with the AI Orchestration Layer.
        Extracts structured chat messages or prompt strings and routes to the selected provider.
        """
        req_id = f"ctx_req_{uuid.uuid4().hex[:12]}"
        metadata = {
            "request_id": req_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "theme_mode": theme_mode,
            "is_live": is_live,
            "task_type": task_type or "general_chat",
            "role": role,
        }

        # Resolve selected model first
        target_model = self.select_model(model, task_type=task_type)

        messages: List[Dict[str, Any]] = []
        system_context: Optional[str] = None

        if built_context is not None and hasattr(built_context, "to_chat_messages"):
            # Cleanly ingest structured 6-layer context from Task 1.6
            raw_messages = built_context.to_chat_messages()
            # Separate system prompt if first message is system
            if raw_messages and raw_messages[0].get("role") == "system":
                system_context = raw_messages[0].get("content")
                messages = raw_messages[1:]
            else:
                messages = raw_messages
        elif external_context:
            system_context = external_context
            messages = [{"role": "user", "content": user_input}]
        else:
            messages = [{"role": "user", "content": user_input}]

        max_tokens = 350 if is_live else (target_model.max_output_tokens or 800)

        ai_request = AIRequest(
            model=target_model.model_name,
            provider=target_model.provider,
            messages=messages,
            system_context=system_context,
            temperature=0.7,
            max_output_tokens=max_tokens,
            stream=False,
            metadata=metadata,
        )

        if enable_tools and target_model.supports_tools:
            return self.generate_with_tools(
                ai_request,
                user_id=user_id,
                user_role=role,
                conversation_id=conversation_id,
            )

        return self.generate(ai_request)

    async def stream_from_context(
        self,
        user_input: str,
        built_context: Any = None,
        theme_mode: str = "normal",
        model: Optional[str] = None,
        is_live: bool = False,
        task_type: Optional[str] = None,
        user_id: str = "",
        conversation_id: str = "",
    ) -> AsyncIterator[AIStreamChunk]:
        """
        Bridges AIContextBuilder with streaming AI generation.
        Yields normalized AIStreamChunk instances.
        """
        req_id = f"stream_ctx_{uuid.uuid4().hex[:12]}"
        metadata = {
            "request_id": req_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "theme_mode": theme_mode,
            "is_live": is_live,
            "task_type": task_type or "general_chat",
        }

        target_model = self.select_model(model, task_type=task_type)

        messages: List[Dict[str, Any]] = []
        system_context: Optional[str] = None

        if built_context is not None and hasattr(built_context, "to_chat_messages"):
            raw_messages = built_context.to_chat_messages()
            if raw_messages and raw_messages[0].get("role") == "system":
                system_context = raw_messages[0].get("content")
                messages = raw_messages[1:]
            else:
                messages = raw_messages
        else:
            messages = [{"role": "user", "content": user_input}]

        max_tokens = 350 if is_live else (target_model.max_output_tokens or 800)

        ai_request = AIRequest(
            model=target_model.model_name,
            provider=target_model.provider,
            messages=messages,
            system_context=system_context,
            temperature=0.7,
            max_output_tokens=max_tokens,
            stream=True,
            metadata=metadata,
        )

        async for chunk in self.stream(ai_request):
            yield chunk

    def _log_safe_telemetry(self, request_id: str, response: AIResponse, fallback_used: bool):
        """Safely logs request metadata without exposing conversation text or credentials."""
        duration_ms = response.metadata.get("duration_ms", 0)
        tokens_info = f"{response.usage.total_tokens} tokens" if response.usage else "tokens: N/A"
        logger.info(
            f"AI Completed [{request_id}]: Provider={response.provider}, Model={response.model}, "
            f"Latency={duration_ms:.1f}ms, Usage={tokens_info}, FallbackUsed={fallback_used}"
        )

    def get_health_status(self) -> Dict[str, Any]:
        """Returns health status of configured models and providers without expensive network calls."""
        provider_status = list_available_providers()
        default_model = self.registry.get_default_model()
        return {
            "status": "healthy" if any(provider_status.values()) else "degraded",
            "default_model": default_model.model_name,
            "default_provider": default_model.provider,
            "providers": provider_status,
            "total_registered_models": len(self.registry.list_models()),
        }


# Global singleton orchestrator
ai_orchestrator = AIOrchestrator()
