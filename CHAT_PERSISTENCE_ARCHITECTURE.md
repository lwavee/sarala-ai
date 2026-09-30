# Persistent Chat Engine Integration Architecture

## 1. Executive Summary & Overview
This document specifies the technical architecture, security guarantees, data flows, context window management, and frontend-backend synchronization for **Task 1.4: Persistent Chat Engine Integration** in **Sarala AI**.

The chat engine is directly connected to the verified dual-database architecture:
- **MongoDB Atlas**: Serves as the authoritative Identity & Authentication Provider. It generates signed HMAC cryptographic tokens (`mga.<payload>.<sig>`) and establishes the canonical `user_id` (UUID).
- **FastAPI Backend**: Verifies bearer tokens via `get_current_user()` and enforces strict row-level tenant partitioning.
- **Supabase PostgreSQL**: Acts as the structured persistent store for `conversations` and `messages`.
- **AI Brain Engine**: Integrates conversation-scoped context (recent turns) into the LLM orchestration pipeline with situational awareness and real-time IST clock synchronization.

---

## 2. Complete End-to-End Chat Request Flow

```
                      ┌─────────────────────────────────┐
                      │        Client (Browser)         │
                      └────────────────┬────────────────┘
                                       │ 1. POST /chat or /api/chat
                                       │    Authorization: Bearer <token>
                                       │    Body: { message, conversation_id, client_message_id }
                                       ▼
                      ┌─────────────────────────────────┐
                      │         FastAPI Backend         │
                      │       get_current_user()        │
                      └────────────────┬────────────────┘
                                       │ 2. Extracts trusted MongoDB user_id
                                       ▼
        ┌───────────────────────────────────────────────────────────────┐
        │ ConversationService:                                          │
        │ • If no conversation_id or not found:                         │
        │     Auto-create conversation with auto-derived title          │
        │ • If title is default ('New Conversation'):                   │
        │     Auto-update title from first meaningful user prompt       │
        │ • If user renamed conversation:                               │
        │     Preserve user's custom title (immutable to auto-updates)  │
        └──────────────────────────────┬────────────────────────────────┘
                                       │ 3. Persist user turn
                                       ▼
        ┌───────────────────────────────────────────────────────────────┐
        │ MessageService:                                               │
        │ • Verify conversation belongs to authenticated user_id        │
        │ • Enforce idempotency: check client_message_id duplicate      │
        │ • Persist user message to Supabase PostgreSQL                 │
        │ • Update conversation last_message_at timestamp               │
        └──────────────────────────────┬────────────────────────────────┘
                                       │ 4. Generate AI response with context
                                       ▼
        ┌───────────────────────────────────────────────────────────────┐
        │ Brain.process_input:                                          │
        │ • Load recent conversation turns scoped to conversation_id    │
        │ • Build situational briefing (IST clock, emotions, mode)      │
        │ • Execute LLM engine (Groq, Gemini, OpenAI, etc.)             │
        └──────────────────────────────┬────────────────────────────────┘
                                       │ 5. Safe Assistant Persistence
                                       ▼
        ┌───────────────────────────────────────────────────────────────┐
        │ MessageService:                                               │
        │ • Persist assistant turn to Supabase PostgreSQL               │
        │ • Update conversation last_message_at timestamp               │
        └──────────────────────────────┬────────────────────────────────┘
                                       │ 6. Response Payload
                                       ▼
                      ┌─────────────────────────────────┐
                      │ Returns JSONResponse:           │
                      │ {                               │
                      │   "response": "...",            │
                      │   "conversation_id": "...",     │
                      │   "audio_url": "/voice/stream?.."│
                      │ }                               │
                      └─────────────────────────────────┘
```

---

## 3. Authentication & Canonical Ownership

### 3.1 Zero Frontend Identity Trust
- Frontend requests **NEVER** provide the authoritative `user_id` or `role`.
- Any `user_id` in the request body is stripped and ignored by backend Pydantic validation schemas.
- The backend derives `user_id` solely from the verified cryptographic HMAC token in the `Authorization: Bearer` header.

### 3.2 Dual Ownership Guard
Every message operation verifies two strict conditions:
1. `conversation.user_id == authenticated_user.user_id` (Parent conversation belongs to the caller).
2. `message.user_id == authenticated_user.user_id` (Message is persisted with caller's identity).

Accessing a conversation belonging to another user results in an immediate **`404 Not Found`**, completely preventing object identifier enumeration.

---

## 4. Conversation Lifecycle & Persistence

### 4.1 Creation
- When a user starts a conversation without a `conversation_id`, the system auto-creates a conversation record in Supabase:
  - `id`: Unique UUID v4.
  - `user_id`: Authenticated user's UUID.
  - `title`: Cleaned, auto-derived 5–6 word snippet from the user's first prompt (or "New Conversation").
  - `mode`: Active theme mode (`"normal"`, `"love"`, `"expert"`).
  - `status`: `"active"`.
  - `created_at`, `updated_at`, `last_message_at`: UTC timestamps.

### 4.2 Title Auto-Generation & Protection
- **Initial Auto-Title**: If a conversation has title `"New Conversation"` or `"Untitled Conversation"`, the first user message automatically updates the title to match the query topic.
- **User Rename Protection**: If a user manually renames a conversation via `PATCH /api/conversations/{id}`, the custom title is preserved and will **never** be overwritten by subsequent messages.

### 4.3 Safe Deletion
- Executed via `DELETE /api/conversations/{id}`.
- Ownership is verified before deletion.
- Soft-deleted / removed records are filtered out from `GET /api/conversations` and will return `404 Not Found` on direct access attempts.

---

## 5. Message Ordering & Pagination

- **Deterministic Chronological Ordering**: `GET /api/conversations/{id}/messages` sorts by `created_at ASC`, ensuring history is reliably reconstructed in exact chronological sequence (`user` → `assistant` → `user` → `assistant`).
- **Pagination Support**:
  - `limit`: Number of messages (default 100, max 200).
  - `offset`: Offset for pagination.
  - Returns metadata envelope with total message count for efficient client pagination.

---

## 6. Context Window & LLM Memory Management

- **Conversation-Scoped Context**: When continuing an active conversation, `Brain.process_input` loads the most recent 10 turns specifically for that `(user_id, conversation_id)` pair.
- **Zero Cross-Conversation Bleed**: Previous messages from other conversations or other users are never included in the prompt.
- **Situational Awareness Briefing**: Injects time-of-day phases (IST), valence, and recent conversational flow into the model prompt while preserving system limits.

---

## 7. Idempotency & Duplicate Protection

- Clients generate a unique `client_message_id` for user messages (e.g. `client_msg_<timestamp>_<random>`).
- Sent in request payloads and stored in `messages.metadata.client_message_id`.
- If a network retry occurs with the same `client_message_id`, `message_service` identifies the duplicate, suppresses re-insertion, and returns the existing message record.

---

## 8. Failure Handling & Resilience

### 8.1 User Message Preservation on AI Failure
- The user message is **persisted first** before invoking the AI model.
- If the AI engine or external provider experiences a network timeout or failure:
  - The user message remains safely stored in the database.
  - A controlled response with `retryable: true` and the active `conversation_id` is returned.
  - The conversation history is not corrupted, allowing the user to retry seamlessly.

### 8.2 Database Connectivity Resilience
- If Supabase PostgreSQL encounters transient network drops, the user-partitioned resilience cache in `conversation_service` and `message_service` absorbs writes and reads without downtime.

---

## 9. Frontend Integration & Multi-Session Behavior

### 9.1 Session Restoration & Page Refresh
1. User visits `/chatbot?id=<uuid>`.
2. `AuthContext` initializes and restores verified MongoDB session via `/api/auth/me`.
3. `loadChatById` queries `/api/conversations/<uuid>/messages` with the Bearer token.
4. Persistent messages render immediately.

### 9.2 Logout & User Switching Safety
- When `logout()` is triggered, `sarla_auth_updated` custom event fires.
- The `Sidebar` and `chatbot` page immediately clear all messages, active conversation ID, and conversation lists.
- Client-side cache keys are strictly user-partitioned (`sarla_chat_history_<user_id>` for authenticated users, `sarla_guest_chat_history` for guests).
- User A's chat state is **never** displayed to User B.

### 9.3 Multi-Device Continuity
- Conversations are stored centrally in the database. A user logged into Browser A can refresh or log into Browser B and access all previous conversations and messages.

---

## 10. Automated Test Verification Results

All tests pass 100% green across both new integration and regression suites:
- **`backend/test_task_1_4_chat.py`**: **45/45 Passed (100%)**
  - Conversation Creation & Auto-Title (12 tests)
  - Existing Conversation Continuity & Ordering (8 tests)
  - Title Protection & Renaming (4 tests)
  - Idempotency & Duplicate Protection (2 tests)
  - AI Failure & State Preservation (6 tests)
  - User Isolation & Security Boundaries (7 tests)
  - Multi-Session & Logout/Login Simulation (3 tests)
  - Safe Conversation Deletion (3 tests)
- **`backend/test_task_1_3_apis.py`**: **74/74 Passed (100%)**
- **`backend/test_persistence_and_voice.py`**: **Passed (100%)**
- **`backend/test_modes.py`**: **Passed (100%)**
- **`npm run build` (Frontend)**: **Passed with exit code 0** (Turbopack + TypeScript checks passed, all routes prerendered).
