# AI Provider & Model Orchestration Layer Architecture (Task 1.7)

This document describes the design, implementation, error normalization, retry/fallback policies, and security architecture of the centralized **AI Provider & Model Orchestration Layer** in Sarala AI.

---

## 1. High-Level System Architecture

The AI layer strictly decouples HTTP endpoints, authentication, context preparation, and model execution:

```
[ Frontend Client ]
        │
        ▼ (POST /chat or /api/chat/stream, with optional model & task_type)
[ FastAPI Chat API ] (backend/web/app.py)
        │
        ▼ (Extracts canonical authenticated MongoDB user identity)
[ Authentication & Idempotency ]
        │
        ▼ (Layered system prompt, mode personality, user prefs, memory, RAG, history)
[ AI Context Builder (Task 1.6) ] (core/services/ai_context_builder.py)
        │
        ▼ (Prepared BuiltContext: 6-layer bounds, token budgeting, injection-proof)
[ AI Orchestrator ] (ai/orchestrator.py)
        │
        ├─► [ Model Registry & Allowlist Validation ] (ai/models.py)
        ├─► [ Capability Verification ] (streaming, tools, json, vision)
        ├─► [ Context Window Limit Check ] (ContextTooLargeError prevention)
        ├─► [ Provider Selection & Adapter Resolution ] (ai/providers/)
        │         ├── GeminiAdapter (Google GenAI / legacy)
        │         ├── GroqAdapter (High-speed LPU)
        │         ├── OpenAIAdapter (GPT-4o, GPT-4o-mini)
        │         ├── XAIAdapter (Grok)
        │         ├── MistralAdapter (Mistral Large)
        │         └── SiliconFlowAdapter (DeepSeek, Qwen)
        │
        ├─► [ Controlled Retries & Backoff ] (Transient network / 503 / 504 / 429)
        ├─► [ Provider Fallback ] (Reuses same prepared context on failure)
        │
        ▼
[ Normalized Response (AIResponse / AIStreamChunk) ]
        │
        ▼
[ Message Persistence (Supabase) ] (Single message saved on complete)
        │
        ▼
[ JSON / SSE Stream Response to Frontend ]
```

---

## 2. Directory Structure

```
backend/
  ai/
    __init__.py              # Central module exports
    errors.py                # Canonical AIError hierarchy & error normalizer
    models.py                # ModelConfig, ModelRegistry, AIRequest, AIResponse, AIStreamChunk
    orchestrator.py          # AIOrchestrator singleton, retries, fallback, metrics
    providers/
      __init__.py            # Provider registry factory
      base.py                # BaseProviderAdapter & OpenAICompatibleAdapter
      gemini_provider.py     # Google Gemini adapter
      groq_provider.py       # Groq LPU adapter
      openai_provider.py     # OpenAI official adapter
      xai_provider.py        # xAI Grok adapter
      mistral_provider.py    # Mistral AI adapter
      siliconflow_provider.py# SiliconFlow (DeepSeek/Qwen) adapter
```

---

## 3. Central Model Registry (`backend/ai/models.py`)

The `ModelRegistry` maintains the backend allowlist of supported models and their capabilities.

### Registered Models

| Model ID | Provider | Context Window | Capabilities |
|---|---|---|---|
| `openai/gpt-oss-120b` | `groq` | 131,072 | text, streaming, tools, json |
| `openai/gpt-oss-20b` | `groq` | 131,072 | text, streaming, tools, json |
| `qwen/qwen3.6-27b` | `groq` | 32,768 | text, streaming, tools, json |
| `llama-3.3-70b-versatile` | `groq` | 128,000 | text, streaming, tools, json |
| `gemini-1.5-flash` | `gemini` | 1,048,576 | text, streaming, vision, tools, json |
| `gemini-2.0-flash` | `gemini` | 1,048,576 | text, streaming, vision, tools, json |
| `gpt-4o-mini` | `openai` | 128,000 | text, streaming, vision, tools, json |
| `gpt-4o` | `openai` | 128,000 | text, streaming, vision, tools, json |
| `grok-beta` | `xai` | 131,072 | text, streaming, tools, json |
| `mistral-large-latest` | `mistral` | 128,000 | text, streaming, tools, json |
| `deepseek-ai/DeepSeek-V2.5` | `siliconflow` | 65,536 | text, streaming, tools, json |
| `Qwen/Qwen2.5-72B-Instruct` | `siliconflow` | 32,768 | text, streaming, tools, json |

### Allowlist Enforcement
- Frontend clients can request a model ID (`"model": "gemini-1.5-flash"`).
- Backend validates every model ID against `model_registry.validate_model(model_name)`.
- If an unsupported or unknown model is submitted, the backend immediately rejects it with `HTTP 400 MODEL_UNAVAILABLE` without contacting external providers.
- Arbitrary endpoints, external URLs, or custom provider URLs from clients are strictly rejected.

---

## 4. Provider Adapters (`backend/ai/providers/`)

All provider adapters inherit from `BaseProviderAdapter`:

- `validate_configuration() -> bool`: Verifies credentials exist.
- `is_available() -> bool`: Verifies adapter is initialized and ready.
- `generate(request: AIRequest) -> AIResponse`: Executes non-streaming completion.
- `stream(request: AIRequest) -> AsyncIterator[AIStreamChunk]`: Yields normalized stream chunks.

`OpenAICompatibleAdapter` serves as a unified foundation for OpenAI, Groq, xAI, Mistral, and SiliconFlow, avoiding duplicate network code while standardizing message preparation, reasoning tag cleanup (`<think>`), and token telemetry.

---

## 5. Normalized Internal Data Models

### `AIRequest`
- `model`: Target model ID
- `provider`: Target provider ID
- `messages`: Standardized role/content list (`system`, `user`, `assistant`)
- `system_context`: Optional system prompt block
- `temperature`: Sampling temperature (default: 0.7)
- `max_output_tokens`: Maximum tokens to generate (default: 800, or 350 for live voice)
- `stream`: Boolean indicating streaming mode
- `tools`: Optional function definitions
- `response_format`: Optional structured output configuration
- `metadata`: Tracing metadata (`request_id`, `user_id`, `conversation_id`, `mode`, `is_live`)

### `AIResponse`
- `content`: Generated text response
- `model`: Model name used for generation
- `provider`: Provider that fulfilled the generation
- `finish_reason`: Completion reason (`stop`, `length`, `tool_calls`)
- `usage`: `AIUsage(input_tokens, output_tokens, total_tokens)`
- `request_id`: Unique tracing ID
- `metadata`: Execution metrics (duration, fallback status, etc.)

### `AIStreamChunk`
- `content`: Incremental text fragment
- `finish_reason`: Completion signal on final chunk
- `usage`: Usage numbers if emitted
- `metadata`: Provider and model metadata

---

## 6. Error Normalization (`backend/ai/errors.py`)

All provider-specific SDK exceptions are caught and converted to standardized `AIError` subclasses:

| Normalized Code | Class | Retryable? | HTTP Status |
|---|---|---|---|
| `AUTHENTICATION_ERROR` | `AuthenticationError` | No | 401 |
| `RATE_LIMIT_ERROR` | `RateLimitError` | Yes | 429 |
| `TIMEOUT_ERROR` | `TimeoutError` | Yes | 504 |
| `PROVIDER_UNAVAILABLE` | `ProviderUnavailableError` | Yes | 503 |
| `MODEL_UNAVAILABLE` | `ModelUnavailableError` | No | 404 |
| `INVALID_REQUEST` | `InvalidRequestError` | No | 400 |
| `CONTEXT_TOO_LARGE` | `ContextTooLargeError` | No | 413 |
| `CAPABILITY_NOT_SUPPORTED` | `CapabilityNotSupportedError` | No | 400 |
| `UNKNOWN_PROVIDER_ERROR` | `UnknownProviderError` | No | 500 |

*Security Rule:* Raw API keys, connection strings, and internal stack traces are stripped before errors are surfaced.

---

## 7. Retry & Fallback Policies

### Safe Retries
- Transient errors (`TimeoutError`, `ProviderUnavailableError`, `RateLimitError`) are retried up to `AI_RETRY_COUNT` (default: 2) times.
- Exponential backoff is applied: `0.25s * (2 ^ attempt)`.
- Permanent failures (`AuthenticationError`, `InvalidRequestError`, `CapabilityNotSupportedError`, `ContextTooLargeError`) are **never retried**.

### Automatic Provider Fallback
- If the primary provider fails after retries on a transient or unavailable error:
  1. The orchestrator queries `model_registry.get_fallback_model(primary_model)`.
  2. The fallback adapter is checked for readiness.
  3. The **EXACT SAME prepared context** (`AIRequest`) is dispatched to the fallback provider without querying memory, database, or re-running context building.
  4. Response metadata records `fallback_used = True`, `original_provider = ...`, and `original_model = ...`.

---

## 8. Capability & Context Window Verification

Before making any provider network calls:
1. **Capability Check:**
   - If `request.stream` is True and `model_config.supports_streaming` is False -> raises `CapabilityNotSupportedError`.
   - If `request.tools` is passed and `model_config.supports_tools` is False -> raises `CapabilityNotSupportedError`.
   - If `request.response_format` is requested and `model_config.supports_json` is False -> raises `CapabilityNotSupportedError`.
2. **Context Window Check:**
   - The orchestrator calculates input tokens + output token budget.
   - If estimated total exceeds `model_config.context_window`, raises `ContextTooLargeError` before calling the provider API.

---

## 9. Message Persistence Architecture

- **User Message:** Persisted to Supabase before calling the AI provider, supporting client-generated idempotency keys (`client_message_id`).
- **Non-Streaming Generation:** Persists exactly **one** assistant message upon successful response.
- **Streaming Generation:** Token chunks are streamed dynamically via Server-Sent Events (SSE). The full assistant response is accumulated in memory and persisted as **one final message** to Supabase upon stream completion.
- **Failed Generation:** If all providers fail, no partial or corrupted assistant message is saved.

---

## 10. Frontend API Contract

### Discovery: `GET /api/ai/models`
Returns public-safe catalog:
```json
{
  "models": [
    {
      "id": "gemini-1.5-flash",
      "name": "Gemini 1.5 Flash (Google)",
      "provider": "gemini",
      "capabilities": ["text_generation", "streaming", "vision", "tool_calling", "structured_output", "json_output"],
      "context_window": 1048576,
      "supports_streaming": true,
      "supports_vision": true,
      "supports_tools": true,
      "is_default": true
    }
  ],
  "default_model": "gemini-1.5-flash"
}
```

### Health: `GET /api/ai/health`
```json
{
  "status": "healthy",
  "default_model": "gemini-1.5-flash",
  "default_provider": "gemini",
  "providers": {
    "gemini": true,
    "groq": true,
    "openai": true,
    "xai": true,
    "mistral": true,
    "siliconflow": true
  },
  "total_registered_models": 12
}
```

### Synchronous Chat: `POST /chat` or `POST /api/chat`
```json
{
  "message": "Explain quantum computing in Hindi",
  "conversation_id": "optional-uuid",
  "model": "gemini-1.5-flash",
  "theme_mode": "normal"
}
```

### Streaming Chat: `POST /api/chat/stream`
Returns `text/event-stream` with SSE chunks:
```
data: {"type": "chunk", "content": "Quantum "}

data: {"type": "chunk", "content": "computing "}

data: {"type": "done", "conversation_id": "...", "response": "Quantum computing..."}
```

---

## 11. Security & Privacy Guarantees

1. **No Frontend API Keys:** API keys remain strictly in backend environment variables (`.env`).
2. **No Arbitrary Provider Endpoints:** Frontend cannot specify provider URLs or unapproved models.
3. **No Credential Leakage:** System credentials (MongoDB URI, Supabase Service Key, JWT Secret) are excluded from AI prompts and logs.
4. **Multi-User Isolation:** Context building is strictly isolated by authenticated MongoDB `user_id`. Context from User A is never passed to User B.
5. **Safe Logging:** Telemetry logs only record `request_id`, `provider`, `model`, latency, and token metrics.
