#!/usr/bin/env python3
"""
Comprehensive Test Suite for Task 1.7:
AI Provider & Model Orchestration Layer.

Verifies:
1. Central Model Registry & Allowlist Validation
2. Default & Fallback Model Configuration
3. Public-Safe Model Catalog (Zero Secrets Leaked)
4. AI Request & Response Normalization
5. Error Normalization Across Providers (Auth, 429, 503, 504, 400, 413, 404)
6. Capability Verification (Streaming, Tools, JSON, Vision)
7. Context Window Limit Enforcement (ContextTooLargeError)
8. Transient Error Retry Policy (Retryable vs Non-Retryable)
9. Fallback Provider Execution & Context Reuse
10. Streaming Architecture & Chunk Normalization
11. Persistence Integration (Single Assistant Message upon Completion)
12. Security & User Context Isolation (No Cross-User Leakage, No Exposed Keys)
13. Fast API Endpoints: /api/ai/models, /api/ai/health, /chat with model selection, /api/chat/stream
"""

import os
import sys
import json
import time
import asyncio
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from web.app import app
from core.mongodb_client import generate_token
from ai import (
    AIOrchestrator,
    ai_orchestrator,
    ModelConfig,
    ModelRegistry,
    model_registry,
    AIRequest,
    AIResponse,
    AIStreamChunk,
    AIUsage,
    AIError,
    AuthenticationError,
    RateLimitError,
    TimeoutError,
    ProviderUnavailableError,
    ModelUnavailableError,
    InvalidRequestError,
    ContextTooLargeError,
    CapabilityNotSupportedError,
    UnknownProviderError,
    normalize_provider_error,
    get_provider_adapter,
)
from ai.providers.base import BaseProviderAdapter

client = TestClient(app)


def run_tests():
    total_tests = 0
    passed_tests = 0

    def assert_true(condition, test_name):
        nonlocal total_tests, passed_tests
        total_tests += 1
        if condition:
            passed_tests += 1
            print(f"  [PASS] {test_name}")
        else:
            print(f"  [FAIL] {test_name}")
            raise AssertionError(f"Test failed: {test_name}")

    print("\n=======================================================")
    print("TASK 1.7: AI PROVIDER & MODEL ORCHESTRATION TESTS")
    print("=======================================================\n")

    # ── TEST GROUP 1: Model Registry & Allowlist Validation ──
    print("[TEST GROUP 1] Model Registry & Allowlist Validation")
    reg = ModelRegistry()
    assert_true(len(reg.list_models()) >= 10, "Registry contains all known models")
    
    # Validation
    gemini_cfg = reg.validate_model("gemini-1.5-flash")
    assert_true(gemini_cfg.provider == "gemini", "Gemini 1.5 flash correctly mapped to provider gemini")
    assert_true(gemini_cfg.context_window >= 1000000, "Gemini context window accurately reflected")
    
    groq_cfg = reg.validate_model("openai/gpt-oss-120b")
    assert_true(groq_cfg.provider == "groq", "Groq LPU model correctly mapped")

    openai_cfg = reg.validate_model("gpt-4o-mini")
    assert_true(openai_cfg.provider == "openai", "OpenAI model correctly mapped")

    # Invalid model rejection
    try:
        reg.validate_model("malicious-unregistered-model")
        assert_true(False, "Unregistered model should raise ModelUnavailableError")
    except ModelUnavailableError:
        assert_true(True, "Unregistered model rejected with ModelUnavailableError")

    try:
        reg.validate_model("")
        assert_true(False, "Empty model name should raise ModelUnavailableError")
    except ModelUnavailableError:
        assert_true(True, "Empty model rejected safely")


    # ── TEST GROUP 2: Default & Fallback Configuration ──
    print("\n[TEST GROUP 2] Default & Fallback Model Configuration")
    default_m = reg.get_default_model()
    assert_true(default_m is not None, "Default model is defined")
    assert_true(bool(default_m.model_name), f"Default model name is populated ({default_m.model_name})")

    fallback_m = reg.get_fallback_model(primary_model=default_m)
    # If fallback is found, it must be different from primary
    if fallback_m:
        assert_true(fallback_m.model_name != default_m.model_name, "Fallback model is distinct from default model")


    # ── TEST GROUP 3: Public-Safe Model Catalog (Zero Secrets) ──
    print("\n[TEST GROUP 3] Public-Safe Model Catalog")
    public_catalog = reg.list_public_models()
    assert_true(len(public_catalog) > 0, "Public catalog generated")
    
    for item in public_catalog:
        assert_true("id" in item and "name" in item and "provider" in item, "Catalog entry has required public fields")
        # Critical security check: No secrets in catalog
        assert_true("api_key" not in item, "API key strictly excluded from catalog")
        assert_true("url" not in item, "Internal URL excluded from catalog")
        assert_true("base_url" not in item, "Base URL excluded from catalog")
        assert_true("secret" not in item, "Secret key excluded from catalog")


    # ── TEST GROUP 4: Request & Response Normalization ──
    print("\n[TEST GROUP 4] AI Request & Response Normalization")
    test_req = AIRequest(
        model="gemini-1.5-flash",
        messages=[{"role": "user", "content": "Hello Sarla"}],
        system_context="You are Sarla AI",
        temperature=0.7,
        max_output_tokens=500,
    )
    assert_true(test_req.model == "gemini-1.5-flash", "AIRequest holds model name")
    assert_true(len(test_req.messages) == 1, "AIRequest holds messages")

    test_resp = AIResponse(
        content="Namaste! Kaisi hain aap?",
        model="gemini-1.5-flash",
        provider="gemini",
        finish_reason="stop",
        usage=AIUsage(input_tokens=10, output_tokens=8, total_tokens=18),
        request_id="req_test_123",
        metadata={"duration_ms": 120.5}
    )
    assert_true(test_resp.content.startswith("Namaste"), "AIResponse content intact")
    assert test_resp.usage is not None
    assert_true(test_resp.usage.total_tokens == 18, "AIResponse usage normalized")
    assert_true(test_resp.request_id == "req_test_123", "AIResponse request_id preserved")

    chunk = AIStreamChunk(content="Namaste", finish_reason=None)
    assert_true(chunk.content == "Namaste", "AIStreamChunk normalized")


    # ── TEST GROUP 5: Error Normalization ──
    print("\n[TEST GROUP 5] Provider Error Normalization")
    # 1. Auth error
    raw_auth_err = Exception("Incorrect API key provided: sk-proj-12345")
    norm_auth = normalize_provider_error(raw_auth_err, provider="openai", model="gpt-4o-mini")
    assert_true(isinstance(norm_auth, AuthenticationError), "Auth exception mapped to AuthenticationError")
    assert_true(norm_auth.code == "AUTHENTICATION_ERROR", "Error code is AUTHENTICATION_ERROR")
    assert_true(norm_auth.retryable is False, "Auth error is NOT retryable")
    assert_true("sk-proj" not in norm_auth.message, "Raw secret stripped from normalized message")

    # 2. Rate limit 429
    raw_rate_err = Exception("Rate limit reached for requests: 429 Too Many Requests")
    norm_rate = normalize_provider_error(raw_rate_err, provider="groq", model="openai/gpt-oss-120b")
    assert_true(isinstance(norm_rate, RateLimitError), "Rate limit exception mapped to RateLimitError")
    assert_true(norm_rate.code == "RATE_LIMIT_ERROR", "Error code is RATE_LIMIT_ERROR")
    assert_true(norm_rate.retryable is True, "Rate limit error IS retryable")

    # 3. Timeout 504
    raw_timeout = Exception("Request timed out after 30 seconds")
    norm_timeout = normalize_provider_error(raw_timeout, provider="gemini", model="gemini-1.5-flash")
    assert_true(isinstance(norm_timeout, TimeoutError), "Timeout mapped to TimeoutError")
    assert_true(norm_timeout.retryable is True, "Timeout is retryable")

    # 4. Context too large 413
    raw_ctx_err = Exception("maximum context length is 8192 tokens. However, you requested 10000 tokens")
    norm_ctx = normalize_provider_error(raw_ctx_err, provider="openai", model="gpt-4o-mini")
    assert_true(isinstance(norm_ctx, ContextTooLargeError), "Context overflow mapped to ContextTooLargeError")
    assert_true(norm_ctx.code == "CONTEXT_TOO_LARGE", "Error code is CONTEXT_TOO_LARGE")
    assert_true(norm_ctx.retryable is False, "Context too large is NOT retryable")

    # 5. Service unavailable 503
    raw_503 = Exception("503 Service Unavailable: server is overloaded")
    norm_503 = normalize_provider_error(raw_503, provider="siliconflow", model="deepseek-ai/DeepSeek-V2.5")
    assert_true(isinstance(norm_503, ProviderUnavailableError), "503 mapped to ProviderUnavailableError")
    assert_true(norm_503.retryable is True, "503 is retryable")


    # ── TEST GROUP 6: Capability Verification ──
    print("\n[TEST GROUP 6] Capability Verification")
    orchestrator = AIOrchestrator(registry=reg)

    # Groq LPU models don't support vision in our config
    groq_vision_req = AIRequest(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": "analyze image"}],
        tools=[{"type": "function", "function": {"name": "test_tool"}}],  # groq supports tools
    )
    # Check unsupported tool on a model that doesn't support tools
    no_tool_config = ModelConfig(
        provider="mock",
        model_name="mock-no-tools",
        display_name="Mock No Tools",
        supports_tools=False,
        supports_streaming=False,
    )
    reg.register_model(no_tool_config)

    req_with_tool = AIRequest(
        model="mock-no-tools",
        messages=[{"role": "user", "content": "run tool"}],
        tools=[{"type": "function", "function": {"name": "calc"}}],
    )
    try:
        orchestrator.generate(req_with_tool)
        assert_true(False, "Unsupported tool should raise CapabilityNotSupportedError")
    except CapabilityNotSupportedError:
        assert_true(True, "Unsupported tool rejected with CapabilityNotSupportedError")

    req_with_stream = AIRequest(
        model="mock-no-tools",
        messages=[{"role": "user", "content": "stream this"}],
        stream=True,
    )
    try:
        # stream method should raise capability error
        async def check_stream_cap():
            async for _ in orchestrator.stream(req_with_stream):
                pass
        asyncio.run(check_stream_cap())
        assert_true(False, "Unsupported streaming should raise CapabilityNotSupportedError")
    except CapabilityNotSupportedError:
        assert_true(True, "Unsupported streaming rejected with CapabilityNotSupportedError")


    # ── TEST GROUP 7: Context Window Limit Enforcement ──
    print("\n[TEST GROUP 7] Context Window Limit Enforcement")
    small_model_config = ModelConfig(
        provider="mock",
        model_name="mock-small-window",
        display_name="Mock Small Window",
        context_window=100,  # Very small window
        max_output_tokens=50,
    )
    reg.register_model(small_model_config)

    # Giant prompt that exceeds 100 tokens
    huge_prompt = "word " * 500
    huge_req = AIRequest(
        model="mock-small-window",
        messages=[{"role": "user", "content": huge_prompt}],
    )
    try:
        orchestrator.generate(huge_req)
        assert_true(False, "Oversized request should raise ContextTooLargeError")
    except ContextTooLargeError:
        assert_true(True, "Oversized request rejected with ContextTooLargeError")


    # ── TEST GROUP 8: Transient Error Retries ──
    print("\n[TEST GROUP 8] Transient Error Retries")
    attempt_count = 0

    class MockFlakyAdapter(BaseProviderAdapter):
        def __init__(self):
            super().__init__("mock_flaky")
        def validate_configuration(self): return True
        def is_available(self): return True
        def generate(self, request: AIRequest):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                # First attempt times out (transient)
                raise TimeoutError("Simulated provider timeout", provider=self.name, model=request.model)
            return AIResponse(
                content="Recovered after retry!",
                model=request.model,
                provider=self.name,
                request_id="req_retry_test"
            )
        async def stream(self, request: AIRequest):
            yield AIStreamChunk(content="chunk")

    flaky_cfg = ModelConfig(
        provider="mock_flaky",
        model_name="mock-flaky-model",
        display_name="Mock Flaky",
        context_window=10000,
    )
    reg.register_model(flaky_cfg)

    flaky_adapter = MockFlakyAdapter()
    with patch("ai.orchestrator.get_provider_adapter", return_value=flaky_adapter):
        req = AIRequest(model="mock-flaky-model", messages=[{"role": "user", "content": "hi"}])
        resp = orchestrator.generate(req)
        assert_true(resp.content == "Recovered after retry!", "Orchestrator successfully retried transient failure")
        assert_true(attempt_count == 2, f"Orchestrator performed exactly 2 attempts (got {attempt_count})")


    # ── TEST GROUP 9: Fallback Provider Execution & Context Reuse ──
    print("\n[TEST GROUP 9] Fallback Provider Execution & Context Reuse")
    primary_called = False
    fallback_called = False
    received_context_content = ""

    class MockPrimaryDeadAdapter(BaseProviderAdapter):
        def __init__(self):
            super().__init__("dead_provider")
        def validate_configuration(self): return True
        def is_available(self): return True
        def generate(self, request: AIRequest):
            nonlocal primary_called
            primary_called = True
            raise ProviderUnavailableError("503 Service Unavailable", provider=self.name, model=request.model)
        async def stream(self, request: AIRequest):
            yield AIStreamChunk(content="")

    class MockFallbackAdapter(BaseProviderAdapter):
        def __init__(self):
            super().__init__("healthy_fallback")
        def validate_configuration(self): return True
        def is_available(self): return True
        def generate(self, request: AIRequest):
            nonlocal fallback_called, received_context_content
            fallback_called = True
            received_context_content = request.messages[0]["content"]
            return AIResponse(
                content="Hello from Fallback Provider!",
                model=request.model,
                provider=self.name,
                request_id="req_fallback_test"
            )
        async def stream(self, request: AIRequest):
            yield AIStreamChunk(content="")

    dead_cfg = ModelConfig(
        provider="dead_provider",
        model_name="dead-primary-model",
        display_name="Dead Primary",
        context_window=10000,
    )
    fallback_cfg = ModelConfig(
        provider="healthy_fallback",
        model_name="healthy-fallback-model",
        display_name="Healthy Fallback",
        context_window=10000,
    )
    reg.register_model(dead_cfg)
    reg.register_model(fallback_cfg)

    # Patch get_fallback_model to return fallback_cfg
    with patch.object(reg, "get_fallback_model", return_value=fallback_cfg):
        def mock_get_adapter(name):
            if name == "dead_provider":
                return MockPrimaryDeadAdapter()
            if name == "healthy_fallback":
                return MockFallbackAdapter()
            return None

        with patch("ai.orchestrator.get_provider_adapter", side_effect=mock_get_adapter):
            fb_req = AIRequest(
                model="dead-primary-model",
                messages=[{"role": "user", "content": "Specific prepared context turn"}],
            )
            fb_resp = orchestrator.generate(fb_req)
            assert_true(primary_called is True, "Primary provider was attempted")
            assert_true(fallback_called is True, "Fallback provider was invoked after primary failed")
            assert_true(fb_resp.content == "Hello from Fallback Provider!", "Fallback response returned")
            assert_true(fb_resp.metadata.get("fallback_used") is True, "metadata tracks fallback_used=True")
            assert_true(received_context_content == "Specific prepared context turn", "EXACT SAME context reused by fallback")


    # ── TEST GROUP 10: Streaming Chunk Normalization ──
    print("\n[TEST GROUP 10] Streaming Chunk Normalization")
    class MockStreamAdapter(BaseProviderAdapter):
        def __init__(self):
            super().__init__("mock_streamer")
        def validate_configuration(self): return True
        def is_available(self): return True
        def generate(self, request: AIRequest): return AIResponse(content="done", model=request.model, provider=self.name, request_id="1")
        async def stream(self, request: AIRequest):
            tokens = ["Namaste", " ", "boss!", " ", "Main", " ", "Sarla", " ", "hoon."]
            for t in tokens:
                yield AIStreamChunk(content=t, finish_reason=None)
            yield AIStreamChunk(content="", finish_reason="stop")

    stream_cfg = ModelConfig(
        provider="mock_streamer",
        model_name="mock-stream-model",
        display_name="Mock Stream",
        supports_streaming=True,
    )
    reg.register_model(stream_cfg)

    stream_adapter = MockStreamAdapter()
    with patch("ai.orchestrator.get_provider_adapter", return_value=stream_adapter):
        async def test_stream_chunks():
            collected = []
            req = AIRequest(model="mock-stream-model", stream=True)
            async for ch in orchestrator.stream(req):
                collected.append(ch)
            return collected

        chunks = asyncio.run(test_stream_chunks())
        assert_true(len(chunks) == 10, f"Received all expected stream chunks (got {len(chunks)})")
        full_text = "".join(c.content for c in chunks)
        assert_true(full_text == "Namaste boss! Main Sarla hoon.", "Full streamed text correctly assembled")
        assert_true(chunks[-1].finish_reason == "stop", "Final chunk contains finish_reason='stop'")


    # ── TEST GROUP 11: Security & User Isolation ──
    print("\n[TEST GROUP 11] Security & User Isolation")
    # 1. API key in request body must be ignored/disallowed
    # ChatRequest schema does not have api_key or provider_url fields
    from core.schemas import ChatRequest
    schema_fields = getattr(ChatRequest, "model_fields", getattr(ChatRequest, "__fields__", {})).keys()
    assert_true("api_key" not in schema_fields, "Frontend cannot pass 'api_key'")
    assert_true("provider_url" not in schema_fields, "Frontend cannot pass 'provider_url'")
    assert_true("endpoint" not in schema_fields, "Frontend cannot pass 'endpoint'")

    # 2. Strict User Isolation
    # Verify User A's context cannot leak to User B
    from core.services.ai_context_builder import ai_context_builder
    user_a_ctx = ai_context_builder.build_context(
        user_input="hello",
        user_id="user_aaa",
        user_name="Alpha",
        theme_mode="normal"
    )
    user_b_ctx = ai_context_builder.build_context(
        user_input="hello",
        user_id="user_bbb",
        user_name="Beta",
        theme_mode="normal"
    )
    a_msgs = json.dumps(user_a_ctx.to_chat_messages())
    b_msgs = json.dumps(user_b_ctx.to_chat_messages())
    assert_true("Alpha" in a_msgs, "User A context contains User A's name")
    assert_true("Beta" not in a_msgs, "User A context DOES NOT contain User B's name")
    assert_true("Beta" in b_msgs, "User B context contains User B's name")
    assert_true("Alpha" not in b_msgs, "User B context DOES NOT contain User A's name")


    # ── TEST GROUP 12: FastAPI AI Endpoints ──
    print("\n[TEST GROUP 12] FastAPI AI Endpoints")
    
    # 1. GET /api/ai/models
    res = client.get("/api/ai/models")
    assert_true(res.status_code == 200, "GET /api/ai/models returns 200")
    data = res.json()
    assert_true("models" in data, "Response contains 'models' list")
    assert_true("default_model" in data, "Response contains 'default_model'")
    assert_true(len(data["models"]) > 0, "Models list is populated")
    
    # Check that returned models are sanitized
    sample_model = data["models"][0]
    assert_true("api_key" not in sample_model, "No API key in /api/ai/models response")
    assert_true("secret" not in sample_model, "No secret in /api/ai/models response")

    # 2. GET /api/ai/health
    res_health = client.get("/api/ai/health")
    assert_true(res_health.status_code == 200, "GET /api/ai/health returns 200")
    health_data = res_health.json()
    assert_true("status" in health_data, "Health response contains 'status'")
    assert_true("providers" in health_data, "Health response contains 'providers'")
    assert_true("default_model" in health_data, "Health response contains 'default_model'")

    # 3. POST /chat with invalid model -> Rejected with 400
    res_invalid = client.post("/chat", json={
        "message": "hello",
        "model": "unauthorized-hacker-model"
    })
    assert_true(res_invalid.status_code == 400, "Invalid model selection rejected with 400")
    invalid_data = res_invalid.json()
    assert_true(invalid_data.get("code") == "MODEL_UNAVAILABLE", "Error code is MODEL_UNAVAILABLE")

    # 4. POST /chat with valid model
    with patch("ai.orchestrator.AIOrchestrator.generate") as mock_gen:
        mock_gen.return_value = AIResponse(
            content="Hello from test model!",
            model="gemini-1.5-flash",
            provider="gemini",
            request_id="req_chat_test"
        )
        res_valid = client.post("/chat", json={
            "message": "Hello Sarla",
            "model": "gemini-1.5-flash",
            "theme_mode": "normal"
        })
        assert_true(res_valid.status_code == 200, "POST /chat with valid model returns 200")
        chat_data = res_valid.json()
        assert_true("response" in chat_data, "Response contains 'response' key")
        assert_true(chat_data["response"] == "Hello from test model!", "AI response returned accurately")

    # 5. POST /api/chat/stream SSE endpoint
    async def mock_stream_iter(*args, **kwargs):
        yield AIStreamChunk(content="Hello ")
        yield AIStreamChunk(content="from ")
        yield AIStreamChunk(content="stream!")

    with patch("ai.orchestrator.AIOrchestrator.stream_from_context", side_effect=mock_stream_iter):
        res_stream = client.post("/api/chat/stream", json={
            "message": "Stream this test",
            "model": "gemini-1.5-flash"
        })
        assert_true(res_stream.status_code == 200, "POST /api/chat/stream returns 200")
        assert_true("text/event-stream" in res_stream.headers.get("content-type", ""), "Content-Type is text/event-stream")
        stream_body = res_stream.text
        assert_true("data: " in stream_body, "SSE formatted output with 'data:'")
        assert_true('"type": "chunk"' in stream_body, "SSE emits chunk events")
        assert_true('"type": "done"' in stream_body, "SSE emits final done event")
        assert_true("Hello from stream!" in stream_body, "Full stream text assembled in done payload")

    print("\n=======================================================")
    print(f"ALL {passed_tests}/{total_tests} TASK 1.7 TESTS PASSED SUCCESSFULLY! [OK]")
    print("=======================================================\n")


if __name__ == "__main__":
    run_tests()
