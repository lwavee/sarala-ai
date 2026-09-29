# DUAL DATABASE ARCHITECTURE: MONGODB ATLAS + SUPABASE POSTGRESQL

This document details the architectural foundation, security model, data separation, and synchronization mechanisms connecting **MongoDB Atlas** and **Supabase PostgreSQL** in the Sarala AI application.

---

## 1. Why MongoDB is Used

MongoDB Atlas serves as the **Authentication and Identity Source of Truth**.
- **Specialized Identity & Credential Engine**: Optimized for fast point-lookups on authentication tokens, user credentials, login timestamps, and account status (`is_active`, `role`).
- **Flexible Session & Security Metadata**: Authentication state often involves variable metadata (e.g., login attempts, salt versions, security tokens, session context) that maps naturally to document structures.
- **Authoritative Authorization Boundary**: MongoDB maintains administrative roles (`admin`, `user`) and account lifecycle status. Privilege escalation attempts in frontend or application layers are strictly blocked because MongoDB remains the sole trusted identity authority.

---

## 2. Why Supabase is Used

Supabase PostgreSQL acts as the **Relational Application Data Store**.
- **Structured Relational Integrity**: Application entities—such as conversations, threaded messages, user preferences, memory graphs, and file metadata—require relational integrity, foreign key constraints, and relational indexes.
- **Relational Querying & Indexing**: PostgreSQL enables compound indexes, such as `(user_id, memory_key)` and `(conversation_id, created_at)`, allowing efficient per-user queries and pagination without data collisions.
- **Independent Scaling**: High-volume conversational messages and memory records scale within PostgreSQL without burdening or risking the latency or security of the authentication database.

---

## 3. What MongoDB Stores

MongoDB strictly holds authentication and security-related fields in the `users` collection:
- `_id`: Canonical unique identifier (stable UUID string).
- `id`: Normalized string mirror of the stable ID.
- `email`: Normalized, unique login email (indexed uniquely).
- `password_hash`: Secure cryptographic hash (Argon2 / PBKDF2 with unique salt).
- `password_salt`: Cryptographic salt for verification.
- `role`: Authoritative role string (`admin` or `user`).
- `full_name`: Display name associated with account creation.
- `nickname`: Display moniker.
- `is_active`: Boolean account flag (disabled accounts are rejected at auth time).
- `created_at`: Account registration timestamp.
- `updated_at`: Account modification timestamp.
- `last_login_at`: Updated atomically upon successful login.
- `metadata`: Authentication and session metadata.

> **CRITICAL**: MongoDB **never** stores conversational chat histories, message records, or application files.

---

## 4. What Supabase Stores

Supabase holds all application domain data across dedicated relational tables, all tied to the user via `user_id`:
- **`profiles`**: Application profile display data (`user_id`, `email`, `full_name`, `nickname`, `avatar_url`, `bio`, `role`, `is_active`, `created_at`, `updated_at`, `last_login_at`).
- **`user_preferences`**: User-specific settings (`user_id`, `theme_mode`, `language`, `timezone`, `voice_enabled`, `assistant_personality`, `preferred_model`, `persona_settings`, etc.).
- **`conversations`**: Chat thread metadata (`id`, `user_id`, `title`, `mode`, `status`, `last_message_at`, `created_at`, `updated_at`).
- **`messages`**: Individual conversation turns (`id`, `conversation_id`, `user_id`, `role`, `content`, `message_type`, `metadata`, `created_at`).
- **`memories`**: User-partitioned long-term associative memory (`id`, `user_id`, `memory_key`, `memory_value`, `memory_type`, `importance`, `source`, `created_at`, `updated_at`).
- **`user_files`**: File metadata and ownership (`id`, `user_id`, `original_name`, `storage_provider`, `storage_key`, `mime_type`, `size_bytes`, `status`, `deleted_at`).

> **CRITICAL**: Supabase **never** stores `password_hash`, `password_salt`, or authentication token signing secrets.

---

## 5. Canonical User ID (`user_id`)

The stable identifier created by MongoDB during user registration serves as the universal `user_id`:
```
MongoDB users._id (UUID String)
       ↓
Canonical user_id
       ↓
Supabase profiles.user_id
Supabase user_preferences.user_id
Supabase conversations.user_id
Supabase messages.user_id
Supabase memories.user_id
Supabase user_files.user_id
```

- **Why Not Email?** Email addresses can be changed, typo-corrected, or transferred. Using email as a foreign key leads to cascading update failures or orphaned records.
- **Why Not a Second Supabase Auth ID?** Generating an unrelated Supabase Auth ID introduces split-brain authentication and dual-account synchronization bugs. A single stable `user_id` links both databases cleanly.

---

## 6. How MongoDB and Supabase are Connected

MongoDB and Supabase are connected **only through the trusted FastAPI Backend Service Layer**. They never communicate directly with each other, nor does the frontend talk directly to either database with administrative permissions.

```
┌────────────────────────────────────────────────────────┐
│                        FRONTEND                        │
└───────────────────────────┬────────────────────────────┘
                            │ Bearer mga.<signed_token>
                            ▼
┌────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND                     │
│  - get_current_user() validates token via MongoDB      │
│  - Extracts trusted user_id and authoritative role     │
│  - Dispatches to Domain Services                       │
└───────────────┬────────────────────────┬───────────────┘
                │                        │
     Auth queries & status       Application data queries
                │                filtered by trusted user_id
                ▼                        ▼
┌────────────────────────┐      ┌────────────────────────┐
│     MONGODB ATLAS      │      │  SUPABASE POSTGRESQL   │
│   (users, credentials) │      │  (profiles, chats,     │
│                        │      │   memories, files)     │
└────────────────────────┘      └────────────────────────┘
```

---

## 7. Authentication Flow

1. **Client Submission**: Client sends credentials (`POST /auth/login` or `POST /auth/signup`) over TLS.
2. **MongoDB Verification / Creation**:
   - `signup`: MongoDB verifies `email` is not already registered. Generates secure salt and hashes password. Inserts document with stable UUID `_id`.
   - `login`: MongoDB fetches user by normalized `email`. Hashes password with stored salt; verifies match. Verifies `is_active == True`. Updates `last_login_at`.
3. **Signed Token Generation**: Backend signs a cryptographic bearer token (`mga.<token>`) encoding user ID and email.
4. **Application Profile Synchronization**: FastAPI invokes `ProfileService.sync_login()` and `PreferencesService.init_default_preferences()` to guarantee the user's application profile and preferences exist in Supabase.
5. **Client Response**: Token and non-sensitive user identity (`user_id`, `email`, `role`, `full_name`) are returned to the client.

---

## 8. Application Data Flow

All application requests follow a strict verified pipeline:

```
1. Request: GET /api/conversations
   Header: Authorization: Bearer mga.<token>

2. Dependency: get_current_user()
   - Decodes token
   - Verifies against MongoDB users collection
   - Confirms user is active
   - Returns trusted CurrentUser object (user_id="usr-123", role="user")

3. Service Call: ConversationService.get_user_conversations(user_id="usr-123")
   - Builds query: SELECT * FROM conversations WHERE user_id = 'usr-123'
   - Executes query against Supabase

4. Ownership Verification:
   - If an endpoint requests a specific resource (e.g. GET /api/conversations/{id}/messages):
     ConversationService verifies conversation.user_id == current_user.user_id.
     If mismatch, returns HTTP 404 (or 403 Forbidden).
```

---

## 9. Profile Synchronization

Synchronization between MongoDB and Supabase follows an **idempotent authoritative sync pattern**:
- **Authoritative System for Auth/Role**: MongoDB owns `role` and `is_active`.
- **Authoritative System for Profile Extras**: Supabase owns `bio`, `avatar_url`, and custom display details.
- **Sync on Login (`ProfileService.sync_login`)**:
  - Checks if a profile exists for `user_id`.
  - If missing: Inserts new profile inheriting `email`, `full_name`, `nickname`, and MongoDB's `role`.
  - If existing: Updates only `last_login_at`, `email`, and authoritative `role`. Preserves user-customized `bio`, `avatar_url`, and display settings.
- **Default Preferences (`PreferencesService.init_default_preferences`)**:
  - Idempotently creates default settings (`theme_mode='system'`, `assistant_personality='friendly'`, etc.) if no preferences row exists for `user_id`.

---

## 10. User Isolation

Data isolation is guaranteed at the architectural, service, and database levels:
1. **Explicit `user_id` Parameterization**: Service methods never accept a `user_id` query parameter from user input. They only accept `current_user.user_id` injected by `get_current_user()`.
2. **Dual Ownership Verification on Relational Children**:
   - Creating or fetching messages verifies both `conversation_id` AND `conversation.user_id == current_user.user_id`.
3. **Compound Memory Isolation**:
   - Database constraint: `UNIQUE(user_id, memory_key)`.
   - User A storing `favorite_color = blue` and User B storing `favorite_color = crimson` reside in separate partitions without key collisions.
4. **File Metadata Isolation**:
   - File queries and deletions are scoped strictly to `WHERE user_id = :authenticated_user_id AND deleted_at IS NULL`.

---

## 11. RLS and Backend Authorization Strategy

- **Architectural Security Model**: The FastAPI backend is the trusted intermediary.
  - The client **never** receives `SUPABASE_SERVICE_ROLE_KEY` or MongoDB connection URIs.
  - Supabase client queries dispatched by backend services operate with backend credentials and explicitly enforce `WHERE user_id = :trusted_id`.
- **Supabase PostgreSQL RLS**:
  - Supabase tables are configured with Row Level Security (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY`).
  - Policies are established (`service_role_all`) granting full backend access, while default client queries are locked down.
  - Permissive policies such as `USING (true)` are prohibited on private user data.

---

## 12. Migration Strategy

Legacy versions of Sarala AI stored user identity in `users.json` and memory facts in `memory.json` or keyed by email.
The migration path (`backend/migrations/migrate_legacy_data.py`) executes safely:
1. **Inspection**: Reads legacy records from `users.json` without modifying or deleting the file.
2. **MongoDB Seeding**: Migrates legacy users into MongoDB Atlas, generating canonical UUIDs while preserving password hashes and roles.
3. **Supabase Hydration**: Idempotently seeds `profiles` and `user_preferences` for each migrated user.
4. **Memory Association**: Reads legacy facts from `memory.json` and links them to the primary administrative user in Supabase's `memories` table.
5. **Preservation**: The original `users.json` and `memory.json` files are preserved on disk for auditing and rollback safety.

---

## 13. Security Model

| Threat / Attack Vector | Mitigation in Dual Database Architecture |
| :--- | :--- |
| **`user_id` Spoofing** | APIs ignore query/body `user_id`. Only `current_user.user_id` from cryptographically signed token is used. |
| **Role Escalation** | `ProfileService.update_user_profile()` strips `role`, `is_active`, and `user_id` from updates. Roles originate exclusively from MongoDB. |
| **Credential Theft from App DB** | Supabase has zero credential columns (`password_hash`, `salt`). Compromising the application database yields no credentials. |
| **Tampered Email** | Token verification validates MongoDB `_id`; email updates in Supabase profile do not alter authentication identity. |
| **Disabled Account Access** | Every request resolves `get_current_user()`, which validates `is_active == True` in MongoDB. |
| **Cross-Tenant Data Leakage** | All service queries enforce `user_id` filtering; conversational hierarchy is verified prior to message retrieval. |

---

## 14. Failure and Retry Behavior

To guarantee high availability and prevent downtime when one database encounters network latency:
- **Resilient Fallback Storage**: Every backend service (`ProfileService`, `PreferencesService`, `ConversationService`, `MessageService`, `MemoryService`, `UserFileService`) contains an internal resilient cache layer. If Supabase is unreachable or undergoing maintenance, queries seamlessly fall back to local cached memory structures without crashing the application.
- **Atomic Operations**: MongoDB updates use atomic modifiers (`$set`, `$currentDate`).
- **Health Check Endpoint (`/health`)**: Separately reports connectivity states:
  ```json
  {
    "status": "healthy",
    "mongodb_connected": true,
    "supabase_connected": true
  }
  ```
  Secrets, connection strings, and internal URIs are never exposed in diagnostics.
