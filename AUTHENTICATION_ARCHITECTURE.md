# Sarala AI — Authentication & Identity Architecture (Task 1.11 Finalization)

## 1. Architectural Overview & Dual-Database Responsibility Model

Sarala AI employs a **dual-database architecture** with strictly separated responsibilities:

1. **MongoDB Atlas** is the **sole authoritative authentication and identity provider**. It manages user credentials, salted PBKDF2 password hashes, session token issuance/verification, user active status, authoritative roles (`user` vs `admin`), and the generation of canonical `user_id` (UUID).
2. **Supabase PostgreSQL** is exclusively the **application data layer**. It stores user profiles, preferences, conversations, messages, memories, uploaded files metadata, tool execution audit records, and agent execution runs. It has no authority over authentication.
3. **FastAPI** forms the **security and authorization boundary**. Neither the frontend nor the AI model can determine identity or authorization; the backend derives canonical identity strictly from cryptographically signed session tokens verified against MongoDB Atlas.

```
                         SARALA AI
                            │
                            ▼
                    ┌───────────────┐
                    │    Next.js    │
                    │    Frontend   │
                    └───────┬───────┘
                            │
                      HTTPS │ (Bearer mga.<payload>.<sig>)
                            ▼
                    ┌───────────────┐
                    │    FastAPI    │
                    │ Security      │
                    │ Boundary      │
                    └───────┬───────┘
                            │
               ┌────────────┴────────────┐
               │                         │
               ▼                         ▼
      ┌────────────────┐        ┌────────────────┐
      │ MongoDB Atlas  │        │    Supabase    │
      │                │        │   PostgreSQL   │
      │ AUTHORITY      │        │ APP DATA       │
      │                │        │                │
      │ users          │        │ profiles       │
      │ passwords      │        │ preferences    │
      │ sessions       │        │ conversations  │
      │ roles          │        │ messages       │
      │ account state  │        │ memories       │
      │ canonical ID   │        │ files          │
      └────────────────┘        │ tools          │
                                │ agents         │
                                │ knowledge      │
                                └────────────────┘
```

---

## 2. Canonical User Identity & CurrentUser Model

### 2.1 Canonical Identity Rules
- **Canonical ID**: A stable string UUID (e.g. `11111111-1111-1111-1111-111111111111`), generated upon signup in MongoDB Atlas.
- **Prohibited Identities**: Email address is **never** used as a primary foreign key or ownership key. Emails are subject to change and are reserved purely for login credentials and user communication.
- **Immutable Server Identity**: The frontend cannot specify or override `user_id`. Request body `user_id`, query parameters (`?user_id=`), URL path variables, and custom headers (`X-User-ID`, `X-Role`) are completely ignored or rejected by the backend authorization layer.

### 2.2 CurrentUser Representation
Every authenticated request in FastAPI resolves a validated `CurrentUser` dataclass dependency:

```python
@dataclass
class CurrentUser:
    id: str           # Canonical user_id
    user_id: str      # Alias matching canonical user_id
    email: str        # Verified MongoDB email
    role: str         # Authoritative role ("user" | "admin")
    full_name: str    # User's full name
    nickname: str     # Optional nickname
    is_active: bool   # Account active state
```

---

## 3. MongoDB Atlas User Model & Password Security

### 3.1 MongoDB User Document Structure
Stored in collection `users` inside MongoDB Atlas:

```json
{
  "_id": "ObjectId(...)",
  "user_id": "11111111-1111-1111-1111-111111111111",
  "email": "user@example.com",
  "name": "Jane Doe",
  "full_name": "Jane Doe",
  "nickname": "JD",
  "password_hash": "a8f5b...[64 hex chars]",
  "password_salt": "9c12e...[32 hex chars]",
  "role": "user",
  "is_active": true,
  "created_at": "2026-10-01T22:00:00Z",
  "updated_at": "2026-10-01T22:00:00Z"
}
```

### 3.2 Password Hashing & Verification Standards
- **Algorithm**: `PBKDF2-HMAC-SHA256` with `100,000` iterations.
- **Salt**: 16 bytes (32 hex characters) generated via cryptographically secure `os.urandom(16)`.
- **Comparison**: Evaluated in constant time using `secrets.compare_digest` to prevent side-channel timing attacks.
- **Information Leakage**: Password hashes and salts are never returned across API boundaries, never logged, never stored in Supabase, and never passed into AI context prompts.

---

## 4. Session & Token Architecture

### 4.1 Token Format
Sarala AI uses HMAC-SHA256 authenticated session tokens:
```
mga.<base64_url_payload>.<hex_signature>
```
1. **Header Prefix**: `mga.` designates a MongoDB Atlas authenticated token.
2. **Payload**: Base64URL-encoded minimal JSON containing `id`, `user_id`, `email`, `role`, and `exp` (timestamp).
3. **Signature**: Cryptographic HMAC-SHA256 signature generated using `SESSION_SECRET` or `AUTH_SECRET`.

### 4.2 Security Constraints
- **Expiration**: Standard validity is 7 days. Expired tokens yield HTTP 401 Unauthorized.
- **Tampering Resistance**: Altering any character in the payload invalidates the signature and yields HTTP 401.
- **Live Status Verification**: Upon receiving a valid signature, the backend loads the user from MongoDB Atlas and verifies `is_active == True`. Deactivated accounts are instantly rejected (HTTP 401/403).

---

## 5. Authoritative Authentication Flows

### 5.1 Signup Flow (`POST /api/signup`)
1. Frontend submits `{ email, password, full_name, nickname }`.
2. Backend validates format, email syntax, and minimum password complexity (>= 8 characters).
3. MongoDB Atlas checked for existing email (409 Conflict if duplicate).
4. Secure random salt generated; PBKDF2 hash calculated.
5. Canonical UUID `user_id` created; role is strictly forced to `"user"` (client-supplied `admin` roles ignored).
6. User document persisted in MongoDB Atlas `users` collection.
7. Supabase application profile and default preferences provisioned.
8. Signed `mga.*` session token generated and returned with sanitized user metadata (status 201 Created).

### 5.2 Login Flow (`POST /api/login`)
1. Rate limiter checks IP and email failed attempts (5 failures in 5 min triggers 60s lockout, HTTP 429).
2. Backend queries MongoDB Atlas `users` by normalized lowercase email.
3. If user does not exist: generic HTTP 401 Unauthorized (avoids user enumeration).
4. Password verified with stored salt using constant-time PBKDF2. If mismatched: HTTP 401.
5. If `is_active` is false: HTTP 403 Forbidden.
6. Supabase profile/preferences verified/synced.
7. Signed `mga.*` token issued and returned with safe user information (status 200 OK).

### 5.3 Session Restoration (`GET /api/auth/me`)
1. Client sends `Authorization: Bearer mga.<payload>.<sig>`.
2. Signature verified; expiration validated.
3. Live user fetched from MongoDB Atlas.
4. Active status confirmed.
5. Live MongoDB user identity returned. Cached frontend identity is never authoritative.

### 5.4 Logout (`POST /api/logout`)
1. Client requests logout.
2. Frontend purges `sarla_auth_token` and `sarla_user_session` from storage.
3. Next.js AuthContext resets user state to null.

---

## 6. Authorization & RBAC Boundary

### 6.1 Role Enforcement
- Two authoritative roles: `"user"` and `"admin"`.
- Role is determined strictly by MongoDB Atlas.
- Admin endpoints use the FastAPI dependency `get_current_admin`:
  ```python
  def get_current_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
      if current_user.role != "admin":
          raise HTTPException(status_code=403, detail="Admin access required.")
      return current_user
  ```
- Normal users accessing `/api/admin/*` receive HTTP 403 Forbidden.

### 6.2 Client Spoofing Defenses
- Request body `{"user_id": "other-user"}` is ignored.
- Custom headers (`X-User-ID`, `X-Role`, `X-Admin`) cannot bypass or override the authenticated session.
- AI tools and orchestrators receive identity injected by FastAPI, never from user prompts or model completions.

---

## 7. Supabase PostgreSQL Data Layer & User Isolation

### 7.1 Table Ownership Architecture
All tables in Supabase maintain `user_id` referencing MongoDB canonical UUID:
- `profiles`: Primary key `user_id` (UUID).
- `user_preferences`: Primary key `user_id` (UUID).
- `conversations`: Column `user_id` indexed for fast scoped retrieval.
- `messages`: Scoped by `user_id` and `conversation_id`.
- `memories`: Unique constraint `(user_id, memory_key)` with soft deletion.
- `user_files`: Scoped by `user_id` and file `id`.
- `tool_executions`: Audit trail scoped by `user_id`.
- `agent_runs` & `agent_steps`: Scoped by `user_id`.

### 7.2 Backend Enforcement Boundary
FastAPI queries Supabase using the backend-only `SUPABASE_SERVICE_ROLE_KEY`, enforcing user scoping in every REST query:
```python
# Messages query scoped strictly by conversation and user
supabase.table("messages").select("*").eq("conversation_id", conv_id).eq("user_id", current_user.user_id).execute()
```
If User B attempts to access User A's conversation, message, memory, file, or agent run, the query returns 0 rows, resulting in an immediate HTTP 404 or 403.

---

## 8. Controlled Failure Mode

If MongoDB Atlas is disconnected or unreachable:
1. `POST /api/login` and `POST /api/signup` immediately return **HTTP 503 Service Unavailable** (`{"error": "Authentication service is temporarily unavailable."}`).
2. Protected endpoints reject incoming tokens with **HTTP 401 Unauthorized**.
3. Zero fallback to local files (`users.json`), in-memory dictionaries (`DEFAULT_USERS`), mock users, or Supabase Auth.
4. `/health` explicitly reports:
   ```json
   {
     "status": "degraded",
     "database": {
       "mongodb": "disconnected",
       "supabase": "connected"
     },
     "authentication": {
       "provider": "mongodb",
       "status": "unavailable"
     }
   }
   ```

---

## 9. Environment Security & Credentials

Required production environment variables:
| Variable | Responsibility | Scope |
| :--- | :--- | :--- |
| `MONGODB_URI` | MongoDB Atlas cluster connection string | Backend Only |
| `MONGODB_DB_NAME` | Database name (e.g., `sarala_ai`) | Backend Only |
| `SESSION_SECRET` / `AUTH_SECRET` | HMAC-SHA256 signing secret for session tokens | Backend Only |
| `SUPABASE_URL` | Supabase Project REST URL | Backend & Frontend |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend administrative database key | Backend Only (NEVER IN BROWSER) |
| `NEXT_PUBLIC_SUPABASE_URL` | Public endpoint for static assets | Frontend |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Public anon key for public assets | Frontend |
