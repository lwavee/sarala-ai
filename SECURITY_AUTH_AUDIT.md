# Sarala AI — Security & Authentication Threat Audit (Task 1.11)

This audit documents the threat modeling, security mitigations, and verification results for the finalized dual-database authentication architecture in Sarala AI.

---

## Threat Matrix & Remediation Summary

### 1. Insecure Fallback to Local Authentication
- **Threat**: If MongoDB Atlas connection fails, legacy systems might fall back to local `users.json`, `DEFAULT_USERS`, or mock credentials with plaintext passwords.
- **Severity**: **CRITICAL**
- **Status**: **RESOLVED**
- **Fix**: Removed `DEFAULT_USERS` and `users.json` from `backend/memory/storage.py`. MongoDB Atlas is the sole authentication authority. When MongoDB is unavailable, login and signup fail safely with HTTP 503 (`DB_OFFLINE`), and token verification rejects requests with HTTP 401.
- **Verification**: Verified in `test_task_1_11_auth.py` Section 4. Zero local user files or fallback dicts remain active.

---

### 2. Client Identity Spoofing via Request Body or Headers
- **Threat**: Malicious clients sending `{"user_id": "victim-uuid"}` in request bodies, or headers like `X-User-ID`, `X-Role: admin` to impersonate other accounts or escalate privileges.
- **Severity**: **CRITICAL**
- **Status**: **RESOLVED**
- **Fix**: FastAPI dependency `get_current_user` extracts identity exclusively from cryptographically verified `mga.*` session tokens and live MongoDB documents. In all endpoints (conversations, messages, memories, files, tools, agent runs), user ownership is bound to `current_user.user_id`. Client-supplied `user_id` fields are ignored or overwritten.
- **Verification**: Verified in `test_task_1_11_auth.py` Section 2 (Test 14) and Section 5.

---

### 3. Privilege Escalation (Normal User to Admin)
- **Threat**: Standard users sending `{"role": "admin"}` during signup, profile update, or tool planning to gain administrative capabilities.
- **Severity**: **HIGH**
- **Status**: **RESOLVED**
- **Fix**: 
  - `POST /api/signup` forces `role="user"` regardless of request parameters.
  - `PATCH /api/profile` strips `role` from updates.
  - `get_current_admin` verifies `current_user.role == "admin"` against live MongoDB records.
  - Admin-only tools (e.g., `get_system_stats`) and endpoints enforce `get_current_admin` or `require_admin` at the Python handler level.
- **Verification**: Verified in `test_task_1_11_auth.py` Tests 11, 12, 13, and `test_task_1_8_tools.py` Group 4.

---

### 4. Cross-User Data Access (Horizontal Privilege Escalation)
- **Threat**: User B predicting or discovering User A's resource IDs (conversation ID, memory ID, file ID, agent run ID) and accessing or deleting their private data.
- **Severity**: **CRITICAL**
- **Status**: **RESOLVED**
- **Fix**: 
  - All Supabase queries in FastAPI filter by `user_id == current_user.user_id`.
  - Conversations, messages, memories, and files verify ownership and return HTTP 404 or 403 on mismatched `user_id`.
  - Agent run repository validates `run.user_id == current_user.user_id` before allowing status checks, pause, resume, or cancellation.
- **Verification**: Verified in `test_task_1_11_auth.py` Section 3 (Tests 15–19), `test_task_1_4_chat.py` Group 6, `test_task_1_5_memory.py` Group 1, and `test_task_1_9_agent.py` Group 6.

---

### 5. Session Token Tampering & Forgery
- **Threat**: An attacker tampering with the base64 payload in `mga.<payload>.<sig>` to alter `user_id` or `role`.
- **Severity**: **CRITICAL**
- **Status**: **RESOLVED**
- **Fix**: Every `mga.*` token is protected by an HMAC-SHA256 signature calculated over the base64 payload using `SESSION_SECRET` / `AUTH_SECRET`. Any byte change in payload causes signature verification to fail in constant time.
- **Verification**: Verified in `test_task_1_11_auth.py` Tests 6, 7, 9.

---

### 6. Expired or Deactivated Session Continuation
- **Threat**: Users retaining valid sessions past the expiration window, or continuing to use tokens after an administrator has deactivated their account (`is_active = false`).
- **Severity**: **HIGH**
- **Status**: **RESOLVED**
- **Fix**: 
  - `verify_token` checks `exp > time.time()`. Expired tokens return HTTP 401.
  - `verify_auth_token` queries MongoDB Atlas to check `user.get("is_active")`. If deactivated, session is immediately rejected with HTTP 401/403.
- **Verification**: Verified in `test_task_1_11_auth.py` Tests 4 and 8.

---

### 7. AI Model Identity Override & Tool Escalation
- **Threat**: An LLM returning function call arguments like `{"user_id": "other-user", "role": "admin"}` attempting to manipulate data or invoke restricted tools.
- **Severity**: **HIGH**
- **Status**: **RESOLVED**
- **Fix**: The AI model is treated as untrusted. The Tool Executor (`ai/tools/executor.py`) and Agent Engine (`ai/agent/engine.py`) automatically override any `user_id` or `role` parameters in tool arguments with the verified identity of the calling `CurrentUser`.
- **Verification**: Verified in `test_task_1_8_tools.py` Group 3 and `test_task_1_9_agent.py` Group 3.

---

### 8. Brute-Force Password Guessing & Credential Stuffing
- **Threat**: Automated scripts spamming `POST /api/login` with candidate passwords.
- **Severity**: **MEDIUM**
- **Status**: **RESOLVED**
- **Fix**: Implemented in-memory IP and account rate limiter in `backend/web/app.py`. Allows a maximum of 5 failed attempts per 5-minute sliding window; subsequent attempts are throttled with HTTP 429 Too Many Requests for 60 seconds.
- **Verification**: Verified in `test_task_1_11_auth.py` Section 6.

---

### 9. Leakage of Sensitive Credentials & Hashes
- **Threat**: Accidental leakage of password hashes, salts, or Supabase service keys in API responses, logs, or frontend code.
- **Severity**: **CRITICAL**
- **Status**: **RESOLVED**
- **Fix**:
  - `mongodb_manager.get_user_by_email` and `get_user_by_id` strip `password_hash` and `password_salt` before returning user dicts unless explicitly queried for internal verification.
  - `SUPABASE_SERVICE_ROLE_KEY` is strictly confined to backend `.env` and never referenced in Next.js public bundles.
  - `admin.ts` and `AuthContext.tsx` in frontend make HTTP requests exclusively to FastAPI with Bearer tokens; no direct database credentials exist in browser memory.
- **Verification**: Full repository audit and `test_task_1_8_tools.py` Group 12 audit logs check.

---

### 10. CORS Origin Configuration
- **Threat**: Overly permissive CORS settings (`allow_origins=["*"]`) combined with `allow_credentials=True`.
- **Severity**: **MEDIUM**
- **Status**: **RESOLVED**
- **Fix**: CORS in `backend/web/app.py` specifies explicit development origins (`http://localhost:3000`, `http://127.0.0.1:3000`, `http://localhost:8000`, `http://127.0.0.1:8000`) and reads `ALLOWED_ORIGINS` from environment for production deployments.
- **Verification**: Verified configuration in `backend/web/app.py`.

---

### 11. Partial Provisioning Failure Strategy
- **Threat**: MongoDB user created during signup, but Supabase profile creation fails due to network failure.
- **Severity**: **MEDIUM**
- **Status**: **RESOLVED**
- **Fix**: 
  - Signup guarantees MongoDB record creation first.
  - If Supabase profile/preferences initialization encounters a network error, backend logs an internal warning and returns the user with status 201.
  - On subsequent logins or `GET /api/auth/me`, `get_or_create_profile` acts idempotently, ensuring the missing Supabase profile is self-healed and synchronized transparently without duplicate user errors.
- **Verification**: Tested in `backend/test_task_1_11_auth.py`.
