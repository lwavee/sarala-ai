# Sarala AI — AI Tool & Function Execution Architecture (Task 1.8)

## 1. Overview & Architectural Pipeline

The **AI Tool & Function Execution Layer** provides Sarala AI with secure, deterministic, and sandboxed access to application capabilities, data structures, and mathematical computations.

The foundational design principle is **Zero Arbitrary Execution**: the AI model never executes arbitrary shell commands, raw Python code, or unrestricted SQL queries. Instead, the model acts as an intention engine that selects strictly typed and permission-governed tools registered in a central registry.

```
User (Web / Voice)
       │
       ▼
   FastAPI Gateway
       │
       ▼
MongoDB Authentication ──► Canonical Identity (user_id, role)
       │
       ▼
AI Context Builder (6 Layers)
       │
       ▼
AI Orchestrator ──► Discovers Authorized Tool Schemas
       │
       ▼
Target AI Model (Gemini / Groq / OpenAI)
       │
       ├── Model Requests ToolCall (name, arguments)
       ▼
Central Tool Registry ──► Validates Name, Enabled Status & Input Schema
       │
       ▼
Authorization Guard ──► Validates User Identity, Role & Authentication
       │
       ▼
Confirmation Guard ──► Verifies Token for State-Changing Operations
       │
       ▼
Central Tool Executor ──► Enforces Timeouts, Injects Canonical Identity & Bounds Output Size
       │
       ▼
Normalized ToolResult (success, data, error, metadata)
       │
       ▼
AI Orchestrator (Tool Loop) ──► Re-submits Tool Result Context to Model
       │
       ▼
Final Synthesized AI Response
       │
       ▼
Supabase Persistent Storage (Messages & Audit Telemetry)
```

---

## 2. Central Tool Registry

The `ToolRegistry` (`backend/ai/tools/registry.py`) is the single source of truth for all tools available across the platform.

### Key Responsibilities:
- **Registration & Lifecycle**: Tools are registered as strongly-typed `ToolDefinition` instances.
- **Model Schema Generation**: Translates registered definitions into standard OpenAI/Gemini/Anthropic function calling JSON schemas without leaking internal handlers or security policies.
- **Role-Based Discovery**: Automatically filters accessible tools based on the caller's verified authentication state and role (`user` vs `admin`).
- **Dynamic Enable/Disable**: Enables or disables tools at runtime without server restarts.

---

## 3. Tool Definition Model

Every registered tool is defined using the Pydantic model `ToolDefinition`:

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Unique Python identifier (e.g. `calculator`, `get_user_memories`). |
| `description` | `str` | Clear, detailed explanation of capability and parameter guidelines. |
| `category` | `ToolCategory` | Category classification (`calculation`, `user`, `memory`, `conversation`, `system`, `data`, `information`, `external`). |
| `action_type` | `ToolActionType` | `READ` (read-only query) or `WRITE` (state-modifying mutation). |
| `input_schema` | `Dict[str, Any]` | JSON Schema specification of acceptable arguments. |
| `output_schema` | `Optional[Dict]` | Optional output structure specification. |
| `requires_authentication` | `bool` | If `True`, unauthenticated/guest callers are rejected (`UNAUTHORIZED`). |
| `requires_confirmation` | `bool` | If `True`, requires explicit user confirmation token prior to execution. |
| `allowed_roles` | `List[str]` | Roles permitted to discover and execute the tool (`["user", "admin"]`). |
| `risk_level` | `RiskLevel` | Risk level classification (`LOW`, `MEDIUM`, `HIGH`). |
| `timeout` | `float` | Hard execution timeout in seconds. |
| `enabled` | `bool` | Flag controlling whether the tool is active. |
| `handler` | `Callable` | Backend Python function executing the operation (never exposed to AI). |

---

## 4. Tool Execution Interface & Pipeline

The central execution interface is `ToolExecutor.execute(...)` (`backend/ai/tools/executor.py`), implementing a strict 9-stage pipeline:

1. **Tool Existence & Enabled Check**: Unknown tools return `NOT_FOUND`; disabled tools return `TOOL_DISABLED`.
2. **Authentication Check**: If `requires_authentication=True` and caller is unauthenticated, returns `UNAUTHORIZED`.
3. **Authorization & Role Check**: Validates `caller.role in tool.allowed_roles`. Normal users calling admin tools return `FORBIDDEN`.
4. **Confirmation Check**: For state-changing tools where `requires_confirmation=True`:
   - If a valid confirmation token is provided, it is validated and consumed.
   - If no token is provided, a secure, time-bounded confirmation token is generated, and a `CONFIRMATION_REQUIRED` result is returned.
5. **Schema Validation**: Validates `arguments` against `input_schema` for required fields and expected types (`INVALID_ARGUMENTS`).
6. **Identity Enforcement**: AI-supplied `user_id` or `role` parameters are stripped. The canonical `user_id` from backend authentication is injected directly.
7. **Timeout-Bounded Execution**: Handlers execute inside worker threads bounded by `tool.timeout` (default 10s, calculator 3s). Exceeded timeouts return `TIMEOUT` (`TOOL_TIMEOUT`).
8. **Result Size Bounding**: Serialized outputs exceeding `MAX_TOOL_RESULT_SIZE` (16 KB) are safely truncated with an explicit notice to prevent context window exhaustion.
9. **Audit Logging & Telemetry**: Creates a sanitized `ToolExecutionAudit` record and returns a normalized `ToolResult`.

---

## 5. Authentication & Canonical User Identity

- **MongoDB as Identity Authority**: The caller's identity is verified via signed MongoDB JWT tokens.
- **AI Argument Poisoning Defense**: When an AI model generates arguments like `{"user_id": "victim_user_123"}`, the execution layer explicitly removes that parameter and injects the authenticated `user_id`.
- **Guest Handling**: Unauthenticated users can only invoke tools where `requires_authentication=False` (e.g. `calculator`). All user, memory, and conversation tools are strictly locked.

---

## 6. Permissions & Role-Based Access Control (RBAC)

- Every tool declares `allowed_roles: List[str]`.
- Normal users (`role = 'user'`) cannot discover or execute tools configured for `admin` only (e.g. `get_system_stats`).
- AI model outputs and frontend payloads cannot elevate user roles or bypass role checks.

---

## 7. Confirmation System

For state-changing operations (such as `delete_user_memory`), explicit user confirmation is enforced via `ConfirmationManager` (`backend/ai/tools/confirmation.py`):

- **Bound Tokens**: Cryptographically secure tokens (`conf_<32-bytes>`) are bound to `(user_id, conversation_id, tool_call_id, tool_name, arguments_hash)`.
- **Cross-User Protection**: User A cannot use their token to authorize User B's pending action.
- **TTL Expiry**: Tokens expire automatically after 5 minutes (300 seconds).
- **Single-Use Replay Protection**: Tokens are deleted immediately upon successful validation, preventing replay attacks.

---

## 8. Tool Schemas

Strict JSON Schemas are declared for every tool:

### 1. `calculator`
```json
{
  "type": "object",
  "properties": {
    "expression": {
      "type": "string",
      "description": "Mathematical expression to evaluate, e.g. '25 * 4' or 'sqrt(64) * 10'"
    }
  },
  "required": ["expression"]
}
```

### 2. `get_current_user_profile` & `get_user_preferences`
```json
{
  "type": "object",
  "properties": {}
}
```

### 3. `search_user_memories`
```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Query term to find specific memories"
    }
  },
  "required": ["query"]
}
```

### 4. `create_user_memory`
```json
{
  "type": "object",
  "properties": {
    "key": { "type": "string" },
    "value": { "type": "string" },
    "memory_type": { "type": "string", "enum": ["personal", "fact", "preference"] }
  },
  "required": ["key", "value"]
}
```

### 5. `delete_user_memory`
```json
{
  "type": "object",
  "properties": {
    "key": { "type": "string" }
  },
  "required": ["key"]
}
```

---

## 9. AI Provider Tool-Calling Integration

- **Normalized `ToolCall`**: Provider-specific tool call payloads (e.g. OpenAI `choice.message.tool_calls`) are parsed into normalized `ToolCall(id, name, arguments, user_id, conversation_id)`.
- **Capability Check**: `AIOrchestrator` verifies whether the target model has `supports_tools=True`. If not, schemas are omitted and standard text generation proceeds safely.
- **Provider Adapters**: Provider adapters (OpenAI, Groq, Mistral, xAI, SiliconFlow) map tool definitions into the provider's native format and return normalized `ToolCall` instances inside `AIResponse.tool_calls`.

---

## 10. Autonomous Tool Execution Loop & Loop Protections

The `AIOrchestrator.generate_with_tools(...)` method manages the execution loop:

1. Injects authorized tool schemas into `request.tools`.
2. Model generates response:
   - If `finish_reason == "tool_calls"`, parses requested calls.
   - For each tool call:
     - **Storm Protection**: Tracks call fingerprints (`tool_name + arguments_hash`). Suppresses executions repeated more than twice.
     - Executes tool via `tool_executor.execute()`.
     - Appends assistant message (with `tool_calls`) and tool result message (`role="tool"`) to the conversation messages.
   - Loop continues back to model so it can synthesize a final response with the new context.
3. **Loop Bound**: Bounded by `MAX_TOOL_CALLS_PER_REQUEST = 5`. If reached, tools are stripped and the model produces a final natural-language summary.

---

## 11. Retry & Idempotency Policy

- **Read Tools**: Can be queried again across turns if context changes.
- **Write Tools**: State-changing operations use deterministic keys and idempotency identifiers (`tool_call_id`).
- **Confirmation Isolation**: Pending write operations do not execute repeatedly during transient retries.

---

## 12. Timeout Policy

- All tool executions are strictly time-bounded using worker thread timeouts.
- **Calculator**: 3.0 seconds max.
- **Database / Memory / Profile Tools**: 5.0 seconds max.
- **Default Timeout**: 10.0 seconds max.
- If a timeout occurs, execution halts safely and returns `error_code="TIMEOUT"`, `error="TOOL_TIMEOUT"`.

---

## 13. Normalized Error Handling

Tool errors are mapped to normalized codes:

| Error Code | Description |
|---|---|
| `INVALID_ARGUMENTS` | Missing required parameters or incorrect types. |
| `UNAUTHORIZED` | Authentication required for user-scoped tool. |
| `FORBIDDEN` | Insufficient role permissions or cross-user resource access violation. |
| `NOT_FOUND` | Tool is not registered in catalog. |
| `TOOL_DISABLED` | Tool is registered but currently disabled. |
| `TIMEOUT` | Tool execution exceeded configured time limit. |
| `CONFIRMATION_REQUIRED` | State-changing operation requires explicit approval token. |
| `RATE_LIMITED` | Call storm or loop detection triggered. |
| `SERVICE_UNAVAILABLE` | Underlying database service failed. |
| `EXECUTION_ERROR` | Internal handler exception (stack trace sanitized). |
| `RESULT_TOO_LARGE` | Output exceeded maximum size bound. |

---

## 14. Audit Logging & Telemetry

Every execution is recorded as a `ToolExecutionAudit` record:
- Records: `id`, `user_id`, `conversation_id`, `tool_call_id`, `tool_name`, `status`, `duration_ms`, `error_code`, `started_at`, `completed_at`.
- **Sanitization**: Password hashes, salts, JWT tokens, and API keys are strictly excluded.

---

## 15. Database Persistence

- **Supabase Schema**: A dedicated `public.tool_executions` table stores tool telemetry with Row Level Security enabled.
- **In-Memory Fallback**: When Supabase is unavailable, audit records remain preserved in an in-memory buffer.

---

## 16. Security & Sandboxing

### Arbitrary Code Execution Restrictions:
- **No `eval()`**: Prohibited throughout all tools and services.
- **No `exec()`**: Prohibited throughout all tools and services.
- **No `subprocess` / `os.system` / `shell=True`**: Prohibited for AI tool execution.
- **No Raw AI SQL**: SQL queries are never generated or executed from AI prompts; predefined Supabase service methods are used exclusively.
- **Safe Calculator AST Parser**: Mathematical expressions are evaluated strictly using recursive AST traversal with whitelisted nodes (`Add`, `Sub`, `Mult`, `Div`, `Pow`, `abs`, `sqrt`, `round`, `sin`, `cos`, `tan`, `log`).

---

## 17. Secrets Protection

- **Provider API Keys**: Stored in backend environment variables (`.env`), never sent to frontend or AI model outputs.
- **Database Credentials**: MongoDB connection strings and Supabase service keys are kept strictly server-side.
- **Zero Secrets in Logs**: Sanitized error messages prevent leaking connection URLs or API tokens.

---

## 18. Testing & Verification

The test suite in `backend/test_task_1_8_tools.py` verifies all 18 aspects:
1. Central Tool Registry registration, schema generation, and tool discovery.
2. Input schema validation (missing parameters, invalid types).
3. Authentication enforcement and AI `user_id` spoofing prevention.
4. Role-based authorization (`user` vs `admin`).
5. Safe mathematical calculator (AST parser, division by zero, exponentiation limits, rejection of `eval`/`exec`/`import`).
6. Memory tools (User A vs User B isolation, CRUD operations).
7. Conversation tools (User A vs User B isolation, ownership enforcement).
8. Confirmation workflow (token generation, expiration, single-use, cross-user denial).
9. Autonomous tool execution loop and storm/infinite loop protection.
10. Timeout enforcement (`TOOL_TIMEOUT`).
11. Output size limiting and truncation (`MAX_TOOL_RESULT_SIZE`).
12. Error normalization across all 11 error codes.
13. Audit logging and persistence verification.
14. FastAPI endpoints (`GET /api/ai/tools`, `POST /api/ai/tools/execute`, `POST /api/ai/tools/confirm`).
