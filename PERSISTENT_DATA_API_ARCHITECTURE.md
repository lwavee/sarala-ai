# Persistent User Data & Conversation API Layer Architecture

## 1. Executive Summary & Overview
This document specifies the technical architecture, security model, data models, and API contracts for the persistent user data and conversation layers in **Sarala AI**.

The system operates on an authenticated **Dual-Database Architecture**:
- **MongoDB Atlas**: Serves as the authoritative Identity, Authentication, and Security Provider.
- **Supabase (PostgreSQL)**: Serves as the Structured Application Data Store for user profiles, preferences, conversations, messages, personal memories, and file metadata.

---

## 2. Dual-Database Separation of Concerns

```
                  ┌───────────────────────────────────────────────┐
                  │              Client (Frontend)                │
                  └──────────────────────┬────────────────────────┘
                                         │ Bearer Token (HMAC signed)
                                         ▼
                  ┌───────────────────────────────────────────────┐
                  │              FastAPI Backend                  │
                  │   get_current_user() / get_current_admin()    │
                  └───────────────┬───────────────┬───────────────┘
                                  │               │
        Cryptographic Token       │               │ Canonical MongoDB user_id
        Verification & Creds      │               │ (UUID) Scoped Queries
                                  ▼               ▼
                   ┌────────────────────┐   ┌───────────────────────┐
                   │   MongoDB Atlas    │   │  Supabase PostgreSQL  │
                   ├────────────────────┤   ├───────────────────────┤
                   │ • Users & Passwords│   │ • profiles            │
                   │ • Active/Disabled  │   │ • user_preferences   │
                   │ • Canonical user_id│   │ • conversations       │
                   │ • Role Authority   │   │ • messages            │
                   │ • Security Audit   │   │ • memories            │
                   │                    │   │ • user_files          │
                   └────────────────────┘   └───────────────────────┘
```

| Layer | Technology | Responsibilities | Security Controls |
|---|---|---|---|
| **Identity & Auth** | MongoDB Atlas (`users`) | User credentials, PBKDF2/HMAC passwords, token generation (`mga.<payload>.<sig>`), roles (`user`/`admin`), account status. | Secret key signatures, timing-safe equality, token expiration. |
| **Application Domain** | Supabase (PostgreSQL) | Profile fields, UI preferences, conversation sessions, message turns, semantic memories, file tracking. | Row-level tenant partitioning via `user_id`, immutable ownership. |

---

## 3. Canonical Identity & Authorization Flow

### 3.1 The Canonical `user_id`
The canonical ownership identifier across the entire application is the **MongoDB `user_id`** (UUID v4 format).
- Generated at signup inside MongoDB.
- Stored as the primary key reference in all Supabase application tables.
- **NEVER** accepted from frontend request payloads (e.g. `request.body.user_id` is completely ignored or stripped).
- **NEVER** derived from unverified client parameters.

### 3.2 Authentication & Authorization Dependency
All protected endpoints depend on FastAPI's `get_current_user` dependency:
1. Client sends `Authorization: Bearer <token>`.
2. `auth_manager.verify_token(token)` checks the cryptographic HMAC-SHA256 signature using the server-side secret.
3. Token payload contains `{user_id, email, role, exp}`.
4. If MongoDB is connected, the account is validated for active status. If MongoDB is experiencing transient connectivity issues, cryptographically valid tokens continue to be honored safely.
5. The trusted `AuthenticatedUser(user_id, email, role, is_active)` object is injected into the route handler.

---

## 4. Persistent API Endpoints & Contracts

All responses follow the unified envelope:
```json
{
  "success": true,
  "data": { ... },
  "message": "Optional status message",
  "pagination": {
    "total": 42,
    "limit": 20,
    "offset": 0
  }
}
```

### 4.1 Profile API
- **`GET /api/profile`**: Returns the profile for the authenticated `user_id`. If missing, auto-initializes safe defaults.
- **`PATCH /api/profile`** / **`PUT /api/profile`**:
  - *Allowed fields*: `full_name`, `nickname`, `avatar_url`, `bio`.
  - *Protected fields*: `user_id`, `role`, `is_active`, `email`. Any attempts to modify these fields are strictly ignored and stripped by Pydantic validators.

### 4.2 User Preferences API
- **`GET /api/preferences`**: Returns the UI and interaction preferences for the authenticated `user_id`.
- **`PATCH /api/preferences`** / **`PUT /api/preferences`**:
  - *Allowed fields*: `theme_mode` (`"default"`, `"calm"`, `"focus"`, `"energy"`, `"love"`, `"earth"`), `voice_speed`, `auto_read`, `input_mode`, `language`, `settings`.
  - Idempotent upsert logic ensures single record per user.

### 4.3 Conversation API
- **`GET /api/conversations`**: Lists conversations belonging exclusively to `authenticated_user.user_id`.
  - *Query Params*: `limit` (1-100, default 50), `offset` (int), `search` (case-insensitive title filter), `status` (`"active"`/`"archived"`).
  - *Ordering*: `last_message_at DESC NULLS LAST, updated_at DESC`.
- **`POST /api/conversations`**: Creates a new conversation. `user_id` is automatically injected from the auth context.
- **`GET /api/conversations/{id}`**: Retrieves a single conversation. Enforces `WHERE id = :id AND user_id = :auth_user_id`. Returns `404 Not Found` if belonging to another user to prevent ID enumeration.
- **`PATCH /api/conversations/{id}`**: Updates `title`, `mode`, or `status`. Ownership is immutable.
- **`DELETE /api/conversations/{id}`**: Deletes the conversation. Verifies ownership before execution.

### 4.4 Message API
- **`GET /api/conversations/{id}/messages`**: Retrieves messages for the specified conversation.
  - *Ownership Guard*: Checks that `conversation.user_id == authenticated_user.user_id` before querying messages.
  - *Query Params*: `limit` (default 100), `offset` (default 0).
  - *Ordering*: `created_at ASC` (chronological conversation reconstruction).
- **`POST /api/conversations/{id}/messages`**: Persists a message turn.
  - *Validation*:
    - `role` must be one of `user`, `assistant`, `system`, `tool`.
    - `content` must be non-empty and `<= 50,000` characters. Unicode and multilingual text are fully preserved.
  - *Side Effect*: Updates parent conversation's `last_message_at = NOW()` and `updated_at = NOW()`.

### 4.5 Memory API
- **`GET /api/memories`**: Lists memories owned by `authenticated_user.user_id`. Supports `limit`, `offset`, and `search`.
- **`POST /api/memories`**: Upserts a memory record. Logical uniqueness is scoped to `(user_id, memory_key)`. User A creating key `"favorite_color"` never overwrites or collides with User B's `"favorite_color"`.
- **`GET /api/memories/{id}`**: Retrieves memory by UUID or `memory_key` scoped to `user_id`.
- **`PATCH /api/memories/{id}`**: Updates value or metadata for a memory.
- **`DELETE /api/memories/{id}`**: Deletes a memory record.

### 4.6 User File Metadata API
- **`GET /api/files`**: Lists uploaded file metadata owned by `authenticated_user.user_id`. Automatically filters out soft-deleted items (`deleted_at IS NULL`).
- **`POST /api/files/metadata`** / **`POST /api/files`**: Records new file metadata (`original_name`, `mime_type`, `size_bytes`, `storage_key`, `storage_provider`).
- **`GET /api/files/{id}`**: Retrieves file metadata verified by `user_id`.
- **`PATCH /api/files/{id}`**: Updates metadata or original name.
- **`DELETE /api/files/{id}`**: Performs soft-deletion by setting `deleted_at = NOW()`.

### 4.7 End-to-End Chat Integration (`POST /chat`)
- Accepts optional `conversation_id` in request payload.
- If `conversation_id` is omitted, automatically provisions a new conversation titled with the first user message.
- Automatically persists:
  1. The incoming user prompt to `messages`.
  2. The LLM assistant response to `messages`.
  3. Updates `conversations.last_message_at`.
- Returns `conversation_id` in the response payload for seamless frontend synchronization.

---

## 5. Security & Isolation Guarantees

1. **Zero Client Trust for Identities**:
   - `user_id`, `role`, `email`, and `is_active` are never accepted from client payloads.
   - Pydantic models in `backend/core/schemas.py` enforce strict field filters.
2. **Horizontal Privilege Escalation Prevention**:
   - Every database query in services filters by `user_id = authenticated_user.user_id`.
   - Attempts to access other users' resources return `404 Not Found` rather than `403 Forbidden` to prevent object identifier enumeration.
3. **No Cross-User Memory/Cache Bleed**:
   - The memory store (`PersonalMemoryStorage` in `backend/memory/storage.py`) is strictly user-partitioned: `Dict[str, Dict[str, MemoryEntry]]`.
   - There are no global shared memory dictionaries.
4. **Credential & Secret Protection**:
   - Supabase Service Role keys and MongoDB connection strings remain securely on the backend server.
   - The frontend never connects directly to Supabase with privileged keys.
   - Stack traces and raw database errors are masked; safe error envelopes are returned to the client.

---

## 6. Resilience & Fault Tolerance Strategy

The backend includes a dual-layer resilience system:
1. **Primary Persistence**: Requests are committed to Supabase PostgreSQL using REST API v1.
2. **Graceful Fallback & Partitioned Cache**: If Supabase or MongoDB Atlas encounters network timeouts, IP whitelist re-indexing, or maintenance downtime:
   - The service layer logs the failure securely.
   - The user-partitioned memory cache absorbs reads and writes with zero downtime.
   - No cross-tenant data leakage occurs because cache instances are strictly keyed by `user_id`.
   - When the database resumes connectivity, operations continue smoothly.

---

## 7. Frontend Integration & Session Restoration

### 7.1 Lifecycle & Flow
```
User navigates to App
       │
       ▼
AuthContext initializes
       │
       ▼
Reads token from localStorage / memory
       │
       ▼
Calls GET /api/auth/me with Bearer token
       │
       ├── Token valid ──► Authenticated state set (user_id, role, name)
       │                        │
       │                        ▼
       │                   Sidebar loads GET /api/conversations
       │                   Chatbot loads GET /api/conversations/{id}/messages
       │                   Settings loads GET /api/preferences
       │
       └── Token invalid ─► Clear auth state, redirect to /login
```

### 7.2 Updated Frontend Components
- **`frontend/src/app/chatbot/page.tsx`**:
  - `loadChatById`: Fetches message turns directly from `/api/conversations/{id}/messages`.
  - `handleSend`: Sends `conversation_id` in `/chat` body and receives persistent `conversation_id`.
- **`frontend/src/components/layout/Sidebar.tsx`**:
  - `loadHistory`: Populates conversation history from `GET /api/conversations`.
  - `handleDeleteChat`: Calls `DELETE /api/conversations/{id}`.
- **`frontend/src/app/settings/page.tsx`**:
  - `handleModeChange`: Synchronizes selected visual theme to `PATCH /api/preferences`.

---

## 8. Verification & Test Suite

The test suite in [`backend/test_task_1_3_apis.py`](file:///e:/sarlaai/sarala-ai/backend/test_task_1_3_apis.py) verifies all components across 74 automated tests:

1. **Authentication & Token Verification**:
   - 401 on missing or forged tokens.
   - Role extraction and verification (`user` vs `admin`).
   - Admin route protection.
2. **Profile API**:
   - Correct user retrieval and update.
   - Blocked privilege escalation (`role` injection stripped).
3. **Preferences API**:
   - Default initialization.
   - Scoped update.
   - Injected `user_id` ignored.
   - User A and User B preferences fully isolated.
4. **Conversation API**:
   - User-scoped creation, listing, retrieval, update, deletion.
   - User B receives 404 accessing User A conversation.
   - Immutable ownership.
5. **Message API**:
   - Chronological retrieval.
   - User B cannot read or append to User A conversation.
   - Validation rejection for empty content or invalid roles.
6. **Memory API**:
   - Isolated `(user_id, memory_key)` scoping.
   - No collision between identical keys of different users.
   - Scoped update and deletion.
7. **User File Metadata API**:
   - Scoped creation, listing, update, soft-delete.
   - Cross-user file isolation.
8. **Persistent Chat Flow**:
   - Complete `/chat` turn with automatic message persistence to conversation history.
