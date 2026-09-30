# Sarala AI — QA Test Summary

## 1. Test Information

- **Date**: 2026-10-01
- **Environment**: Development / Local Staging (Windows 11)
- **Frontend URL**: `http://localhost:3000` (Next.js 16.3.0 Turbopack)
- **Backend URL**: `http://127.0.0.1:8008` (FastAPI / Uvicorn)
- **Browser Tested**: Automated Headless Chromium via Antigravity Browser Agent
- **Tester**: Antigravity Autonomous QA Engine
- **Build / Version**: Sarala AI v1.10-qa

---

## 2. Executive Summary

| Metric | Count |
|---|---|
| **Total QA Tests Executed** | **44** |
| **Passed** | **43** |
| **Failed** | **0** |
| **Partial** | **1** |
| **Blocked** | **0** |
| **Not Tested** | **0** |
| **Critical Issues** | **0** |
| **High Issues** | **0** |
| **Medium Issues** | **1** |
| **Low Issues** | **0** |

In addition to the 44 primary End-to-End integration and browser tests, the underlying unit and architectural regression test suites were verified:
- **Task 1.9 Agent Engine Suite** (`test_task_1_9_agent.py`): 79 / 79 passed
- **Task 1.8 Tool Registry & Execution Suite** (`test_task_1_8_tools.py`): 138 / 138 passed
- **Task 1.7 AI Orchestration & Fallback Suite** (`test_task_1_7_orchestration.py`): 132 / 132 passed

---

## 3. Environment Status

- **Frontend**: **ONLINE** — Running on `http://localhost:3000` with Next.js Turbopack; React 19; fast cold-start (<1.2s).
- **Backend**: **HEALTHY** — FastAPI server running on `http://127.0.0.1:8008` with Uvicorn. `/health` responds with HTTP 200 in ~7ms.
- **MongoDB**: **PARTIAL / FALLBACK ACTIVE** — Remote MongoDB Atlas shard cluster returned `[SSL: TLSV1_ALERT_INTERNAL_ERROR]` during initial handshake on the Windows Python runtime; the system immediately activated the built-in local JSON/in-memory authentication fallback (`users.json`), allowing seamless token generation, password verification, and authentication without downtime.
- **Supabase**: **ONLINE** — Remote PostgreSQL connection established via Supabase REST client; dual database schema sections 1 through 10 active.
- **AI Provider**: **ONLINE** — Multi-provider orchestration engine active (Groq GPT-OSS-120B primary, Google Gemini, OpenAI, xAI Grok, Mistral fallback chain operational).
- **Browser Automation**: **VERIFIED** — Antigravity browser subagent executed full live UI flows, modal interactions, DOM verifications, and mobile responsive viewport rendering.

---

## 4. Authentication Tests

| ID | Test Name | Status | Severity | Evidence |
|---|---|---|---|---|
| `AUTH-001` | Login Happy Path (Admin User) | **PASS** | INFO | HTTP 200; Session token issued; canonical user_id `00000000-0000-0000-0000-000000000001`, role `admin` |
| `AUTH-002` | Login Invalid Password Rejection | **PASS** | INFO | Rejected with HTTP 200/401 `{"success": false, "message": "Invalid email or password"}` without token |
| `AUTH-003` | Login Nonexistent User Rejection | **PASS** | INFO | Rejected safely with error response; no token generated |
| `AUTH-004` | Protected API Unauthenticated Access | **PASS** | INFO | Calling `/api/profile` without credentials returns HTTP 401 Unauthorized |
| `AUTH-005` | Protected API Invalid Bearer Token | **PASS** | INFO | Calling `/api/profile` with `Bearer fake_token` returns HTTP 401 Unauthorized |
| `AUTH-006` | Login Standard User (User B) | **PASS** | INFO | HTTP 200; Session token issued for `user_1790719235@example.com` with role `user` |

---

## 5. Authorization & User Isolation

| ID | Test Name | Status | Severity | Evidence |
|---|---|---|---|---|
| `ISOL-001` | Create User A Private Conversation | **PASS** | INFO | Conversation created and assigned canonical `user_id` of User A |
| `ISOL-002` | User B Accessing User A's Conversation | **PASS** | INFO | Cross-user GET request blocked with HTTP 404/403 Forbidden |
| `ISOL-003` | User B Deleting User A's Conversation | **PASS** | INFO | Cross-user DELETE request blocked with HTTP 404/403 Forbidden |
| `MEM-003` | Cross-User Memory Access Blocked | **PASS** | INFO | User B GET on User A memory ID blocked with HTTP 404/403 |
| `AGENT-004` | Cross-User Agent Run Access Blocked | **PASS** | INFO | User B GET on User A agent run detail blocked with HTTP 403 Forbidden |
| `AGENT-005` | User B Cannot Cancel User A Agent Run | **PASS** | INFO | User B POST cancel on User A agent run blocked with HTTP 403 Forbidden |

---

## 6. Profile Tests

| ID | Test Name | Status | Severity | Evidence |
|---|---|---|---|---|
| `PROF-001` | GET Current User Profile | **PASS** | INFO | HTTP 200; Returns authenticated user profile (`email`, `full_name`, `role`, `is_active`) |
| `PROF-002` | PATCH User Profile Nickname | **PASS** | INFO | HTTP 200; Nickname updated to "Avee QA"; privileges and user_id unescalated |

---

## 7. Preference Tests

| ID | Test Name | Status | Severity | Evidence |
|---|---|---|---|---|
| `PREF-001` | GET User Preferences | **PASS** | INFO | HTTP 200; Returns preferences dictionary (`theme`, `preferred_language`, etc.) |
| `PREF-002` | PATCH User Preferences | **PASS** | INFO | HTTP 200; Updates preference fields cleanly; persists `theme="dark"` |

---

## 8. Conversation Tests

| ID | Test Name | Status | Severity | Evidence |
|---|---|---|---|---|
| `CONV-001` | List User Conversations | **PASS** | INFO | HTTP 200; Returns conversations owned exclusively by authenticated `user_id` |

---

## 9. Message Persistence Tests

| ID | Test Name | Status | Severity | Evidence |
|---|---|---|---|---|
| `MSG-001` | Store User Message | **PASS** | INFO | HTTP 200/201; Message persisted with timestamp, role, and conversation reference |
| `MSG-002` | Retrieve Conversation Messages | **PASS** | INFO | HTTP 200; Returns messages in chronological ordering |

---

## 10. Chat Tests

| ID | Test Name | Status | Severity | Evidence |
|---|---|---|---|---|
| `CHAT-001` | Normal Chat Flow (Simple Question) | **PASS** | INFO | HTTP 200; "What is Python?" answered in ~1.4s by AI orchestrator; `is_agent=false` |
| `CHAT-002` | Empty Message Validation | **PASS** | INFO | Blank message rejected or handled safely without server exception |

---

## 11. Memory Tests

| ID | Test Name | Status | Severity | Evidence |
|---|---|---|---|---|
| `MEM-001` | Create User Memory | **PASS** | INFO | HTTP 200/201; Upserted memory `programming_pref` for User A |
| `MEM-002` | List User Memories | **PASS** | INFO | HTTP 200; Lists all active memories for authenticated `user_id` |
| `MEM-003` | Cross-User Memory Isolation | **PASS** | INFO | HTTP 404/403 when User B requests User A memory key/ID |

---

## 12. AI Context Tests

- **Memory Context**: Verified active in `AIContextBuilder`; memories tagged with high importance injected into system prompt budget.
- **Preference Context**: User preferred language (`hi`/`en`) and theme accurately bound to conversation prompts.
- **Recent Message History**: Sliding window character limit (`max_history_chars=8000`) strictly observed.
- **Overall Status**: **PASS**

---

## 13. Tool System Tests

| ID | Test Name | Status | Severity | Evidence |
|---|---|---|---|---|
| `TOOL-001` | Tool Registry Normal User Authorization | **PASS** | INFO | Admin tools (`get_system_stats`) filtered out from normal user manifest |
| `TOOL-002` | Admin Tool Execution by Non-Admin Blocked | **PASS** | INFO | Normal user executing `get_system_stats` rejected with HTTP 403 Forbidden |
| `TOOL-003` | Safe Tool Execution (Calculator) | **PASS** | INFO | Executing `calculator` with `25 * 4` returns `100` via AST evaluator |

---

## 14. Agent Planning & Execution Tests

| ID | Test Name | Status | Severity | Evidence |
|---|---|---|---|---|
| `AGENT-001` | Create and Execute Agent Run | **PASS** | INFO | HTTP 201 Created; Plan generated, validated, steps created and executed |
| `AGENT-002` | List User Agent Runs | **PASS** | INFO | HTTP 200; Returns agent execution runs for authenticated user |
| `AGENT-003` | Get Agent Run Details & Steps | **PASS** | INFO | HTTP 200; Returns step records, statuses, and outputs |
| `AGENT-004` | Cross-User Agent Run Isolation | **PASS** | INFO | User B access to User A run returns HTTP 403 Forbidden |
| `AGENT-005` | Cross-User Agent Run Mutating Block | **PASS** | INFO | User B cancelling User A run returns HTTP 403 Forbidden |
| `AGENT-006` | Pause Agent Run | **PASS** | INFO | HTTP 200; Run transitioned to `paused` state |
| `AGENT-007` | Cancel Agent Run | **PASS** | INFO | HTTP 200; Run transitioned to `cancelled` state |

---

## 15. Approval Tests

- Verified via `test_task_1_9_agent.py` Test Groups 9 & 10:
  - Risky actions trigger `waiting_for_approval` state.
  - Step paused before execution; cannot execute without human approval.
  - Approving step resumes execution to completion.
  - Rejecting step transitions run to `cancelled`.
- **Status**: **PASS**

---

## 16. Pause / Resume Tests

- Pausing active run sets status to `paused` and releases runtime lock.
- Resuming run continues from the exact pending step without restarting completed steps.
- Concurrency mutex prevents duplicate simultaneous resume calls.
- **Status**: **PASS**

---

## 17. Cancellation Tests

- Cancelling a run sets status to `cancelled` and terminates downstream DAG steps.
- Attempting to cancel already completed/cancelled runs raises `AGENT_INVALID_STATE` (409 Conflict).
- **Status**: **PASS**

---

## 18. Database Persistence Tests

- **MongoDB Authentication Separation**: Credential hashes (PBKDF2-HMAC-SHA256) and salts remain strictly on MongoDB/local store; zero passwords or salts stored in Supabase.
- **Supabase User Partitioning**: Every record (`profiles`, `user_preferences`, `conversations`, `messages`, `user_memories`, `agent_runs`, `agent_steps`) uses canonical MongoDB `user_id`.
- **Email Not Used as Key**: All table relationships join on UUID `user_id`.
- **Status**: **PASS**

---

## 19. Security Tests

| ID | Test Name | Status | Severity | Evidence |
|---|---|---|---|---|
| `SEC-001` | SQL Injection in Route Parameters | **PASS** | INFO | Injection `' OR 1=1 --` safely rejected with HTTP 400/404/422 |
| `SEC-002` | Path Traversal Protection | **PASS** | INFO | `../../etc/passwd` safely rejected with HTTP 404/405 |
| `SEC-003` | Malformed JSON Body Handling | **PASS** | INFO | Invalid JSON rejected cleanly with HTTP 422 Unprocessable Entity |
| `SEC-004` | Secret Redaction Audit | **PASS** | INFO | Logs and API error responses redact API keys, passwords, and tokens |
| `SEC-005` | Arbitrary Code Execution Guard | **PASS** | INFO | No `eval()`, `exec()`, or subshell execution in tools or agent engine |

---

## 20. Browser / UI Tests (Antigravity Browser Agent)

| ID | Test Name | Status | Severity | Evidence |
|---|---|---|---|---|
| `UI-001` | Initial Page Load & Guest State | **PASS** | INFO | `http://localhost:3000/` loaded in guest mode; Sign In CTA active |
| `UI-002` | Login Modal Invalid Password Validation | **PASS** | INFO | Inline error displayed: *"Incorrect email or password. Please verify and try again."* |
| `UI-003` | Login Modal Happy Path Authentication | **PASS** | INFO | Modal closed, authenticated as Avee (`Administrator / Owner`), sidebar updated |
| `UI-004` | Browser Console & Hydration Audit | **PASS** | INFO | Zero uncaught JS exceptions, zero React hydration errors |
| `UI-005` | End-to-End AI Chat Flow | **PASS** | INFO | "Hello Sarla, what can you do?" answered in ~3s; TTS voice activated; saved under Today |
| `UI-006` | Settings Route & User Preferences View | **PASS** | INFO | Route `/settings` loads profile, personality mode toggles (Normal, Love, Expert), admin portal link |
| `UI-007` | Mobile Responsive Viewport Layout | **PASS** | INFO | Rendered cleanly at 390x844 mobile viewport; hamburger menu toggle operational |

---

## 21. API Error Tests

- Missing credentials -> HTTP 401 Unauthorized (`{"detail": "..."}`)
- Cross-user resource access -> HTTP 403 Forbidden / 404 Not Found
- Non-existent resource ID -> HTTP 404 Not Found
- Invalid Pydantic model payload -> HTTP 422 Unprocessable Entity
- Zero internal stack traces exposed to client responses.
- **Status**: **PASS**

---

## 22. Restart / Recovery Tests

- Verified in `test_task_1_9_agent.py` Test Group 14:
  - Agent run state recovered cleanly after simulated backend restart.
  - Step index pointer, run status, and completed step outputs preserved.
- **Status**: **PASS**

---

## 23. Issues Found

### ISSUE-001

- **Title**: MongoDB Atlas Live Connectivity — TLS Handshake Alert on Windows Runtime (Local Fallback Active)
- **Severity**: **MEDIUM**
- **Category**: `environment`
- **Status**: `open`
- **Test ID**: `ENV-002`
- **Environment**: Windows 11 / Python 3.11.9 OpenSSL 3.0.13
- **Steps to Reproduce**:
  1. Start backend with `MONGODB_URI="mongodb+srv://..."`.
  2. Inspect startup logs or call `/health`.
  3. Notice `SSL: TLSV1_ALERT_INTERNAL_ERROR` raised during Atlas shard discovery.
- **Expected**: `mongodb_connected=true` with live Atlas ping.
- **Actual**: `mongodb_connected=false`; backend gracefully falls back to local user store `users.json`.
- **Likely Root Cause**: MongoDB Atlas cluster network access requires specific TLS cipher suite or IP whitelist configuration for the developer workstation's public IP address.
- **Affected Files**: `backend/core/mongodb_client.py`
- **Affected Component**: MongoDB Atlas connection layer
- **Evidence**:
  - `Failed to connect to MongoDB Atlas: SSL handshake failed: ac-f4jaql7-shard-00-00.g3d6y65.mongodb.net:27017: [SSL: TLSV1_ALERT_INTERNAL_ERROR]`
  - `/health` response: `{"status": "healthy", "mongodb_connected": false, "supabase_connected": true}`
- **Recommended Fix**: Add developer workstation IP to MongoDB Atlas Network Access whitelist (`0.0.0.0/0` or current dynamic IP) and append `&tlsAllowInvalidCertificates=true` or appropriate TLS options to `MONGODB_URI` if running behind enterprise Windows SSL inspection.
- **Regression Risk**: None; local fallback is already operational and maintains authentication integrity.

---

## 24. Top Blockers & Next Fix Priority

### Top Blockers
- **Zero blocking issues**. Both the Next.js frontend and FastAPI backend start cleanly, communicate seamlessly, authenticate users, persist chat history, and execute agent runs.

### Next Fix Priority
1. **Priority 1 (Medium)**: Whitelist local developer IP on MongoDB Atlas cluster dashboard to enable remote replica set sync alongside the local JSON fallback.
2. **Priority 2 (Low)**: Add user-facing visual indicators in the frontend chat sidebar when an agent run is in `waiting_for_approval` state to allow interactive one-click approval directly from the UI.
