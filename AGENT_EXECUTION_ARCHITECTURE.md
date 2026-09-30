# Sarala AI — AI Agent Planning & Execution Architecture (Task 1.9)

## 1. Purpose of the Agent Engine
The **Sarala AI Agent Planning & Execution Engine** provides production-grade orchestration for complex, multi-step workflows. While simple conversational queries ("What is HTML?", "Explain recursion") continue using direct AI chat paths, tasks requiring compound actions (such as searching saved notes, calculating values, summarizing findings, and persisting results) are decomposed into a controlled, deterministic Directed Acyclic Graph (DAG) of steps.

The engine guarantees:
- **No arbitrary code execution**: Zero Python `eval()`, `exec()`, or uncontrolled shell commands.
- **Strict tool authorization**: Every executed action must pass through the centralized Task 1.8 `ToolRegistry` and `ToolExecutor`.
- **Human approval gates**: Destructive or high-risk actions pause execution until explicitly approved by the owner.
- **Resilient persistence**: Full state (runs, steps, observability events) persists to Supabase PostgreSQL with in-memory caching.
- **Canonical user isolation**: Every query and action is scoped to the MongoDB `user_id`.

---

## 2. End-to-End System Architecture

```mermaid
graph TD
    User([Authenticated User]) --> Auth[MongoDB JWT / Bearer Auth]
    Auth --> FastAPI[FastAPI Gateway]
    FastAPI --> UserID[Canonical user_id & Role]
    
    FastAPI --> Decision{needs_agent_execution?}
    Decision -- "Simple Chat" --> Brain[Standard Chat / Brain]
    Decision -- "Multi-Step Workflow" --> AgentEngine[Agent Engine Facade]
    
    AgentEngine --> Planner[AgentPlanner]
    Planner --> Orchestrator[AI Orchestrator (Task 1.7)]
    Planner --> Validator[AgentPlanValidator]
    Validator --> ToolReg[ToolRegistry (Task 1.8)]
    
    Validator --> Manager[AgentExecutionManager]
    Manager --> Repo[(Supabase: agent_runs, agent_steps, agent_events)]
    
    Manager --> StepLoop{Next Eligible Step}
    StepLoop -- "requires_approval" --> Gate[Approval Gate: WAITING_FOR_APPROVAL]
    Gate --> Human([Human Approval / Approve Endpoint])
    Human --> StepLoop
    
    StepLoop -- "tool_call" --> ToolExec[ToolExecutor (Task 1.8)]
    ToolExec --> Result[ToolResult]
    Result --> Manager
    
    StepLoop -- "all done" --> Synthesize[Synthesize Final Result]
    Synthesize --> MessageService[Supabase Messages Persistence]
    MessageService --> Response([Final Response to User])
```

---

## 3. Agent Run Lifecycle

An **Agent Run** is tracked by a unique `agent_run_id` (e.g. `run_3f91...`) belonging to exactly one authenticated user.

```
QUEUED ──> PLANNING ──> PLANNED ──> VALIDATING ──> RUNNING ──> COMPLETED
                                                     │   ▲
                                          pause/gate │   │ resume/approve
                                                     ▼   │
                                             PAUSED / WAITING_FOR_APPROVAL
                                                     │
                                            error or │ cancel
                                                     ▼
                                              FAILED / CANCELLED / TIMED_OUT
```

### Controlled Status Enum (`AgentRunStatus`):
- `QUEUED`: Initial state awaiting dispatch.
- `PLANNING`: Goal is being analyzed by `AgentPlanner`.
- `PLANNED`: Valid structured plan has been compiled.
- `VALIDATING`: Plan constraints and tool permissions verified.
- `RUNNING`: Step execution loop is currently active.
- `WAITING_FOR_APPROVAL`: Paused at a human confirmation gate.
- `PAUSED`: Execution paused by user request (`/pause`).
- `COMPLETED`: All planned steps completed successfully.
- `FAILED`: Execution stopped due to an unrecoverable error.
- `CANCELLED`: User or owner cancelled the run (`/cancel`).
- `TIMED_OUT`: Total runtime exceeded `AGENT_MAX_RUNTIME_SECONDS`.

---

## 4. Agent Step Lifecycle

Each step in a plan corresponds to an `AgentStepRecord`:
- **`step_id`**: Deterministic identifier (e.g. `step_1`, `step_2`).
- **`step_type`**: `reasoning`, `tool_call`, `validation`, `transformation`, or `final_response`.
- **`status`**: `pending` → `running` → `completed` (or `failed`, `skipped`, `cancelled`, `waiting_for_approval`).
- **`input`**: JSON parameters, supporting template substitutions from dependencies.
- **`output`**: Normalized JSON execution output, bounded by `AGENT_MAX_RESULT_SIZE`.

---

## 5. Planner (`AgentPlanner`)

The planner provides two primary mechanisms:
1. **Decision Gate (`needs_agent_execution`)**:
   - Inspects queries using heuristic semantic analysis and regex rules.
   - Filters out greetings, definitions, single questions ("What is HTML?"), routing them to normal chat.
   - Detects multi-stage goals ("analyze... calculate... save...", "first... then..."), routing them to the planning engine.
2. **Plan Synthesis**:
   - Assembles available tools allowed for `user_role` and `is_authenticated`.
   - Sends a low-temperature JSON planning prompt to `ai_orchestrator`.
   - If the AI provider is offline or returns malformed syntax, falls back to a deterministic planner that parses math and memory intents.

---

## 6. Plan Validation (`AgentPlanValidator`)

Before any run can start, the plan is checked against strict security and structural gates:
- **Step Limits**: `1 <= len(steps) <= AGENT_MAX_STEPS`.
- **Unique Step IDs**: No duplicate step identifiers permitted.
- **Tool Existence & Enabled Status**: `tool_name` must exist in `ToolRegistry` and have `enabled = True`.
- **Role Authority**: Steps calling admin tools (e.g. `get_system_stats`) are rejected if `user_role != "admin"`.
- **DAG Verification**:
  - All `depends_on` entries must reference prior steps in the plan.
  - Forward dependencies and self-dependencies are rejected.
  - Cycle detection using DFS ensures zero circular deadlocks.

---

## 7. Tool Execution & Task 1.8 Bridge

All tool executions delegate to `ai.tools.executor.tool_executor`:
1. Schema validation against declared parameter types.
2. Canonical `user_id` injection (preventing AI argument spoofing).
3. Role-based execution checks.
4. Tool timeout handling.
5. Audit logging with zero secret leaks.

---

## 8. Dependencies & Context Flow

Steps execute in topological order:
- A step is eligible when all `depends_on` steps have `status == "completed"`.
- Output from Step 1 can be dynamically injected into Step 2 inputs using `{{step_1.result}}` or `{step_1.result}` syntax.
- If an upstream dependency fails, downstream dependent steps are marked `FAILED` and prevented from running.

---

## 9. Controlled Retry Strategy

Only transient, recoverable errors are retried:
- **Recoverable**: `TIMEOUT`, `RATE_LIMITED`, `PROVIDER_UNAVAILABLE`, `NETWORK_ERROR`.
- **Non-Recoverable**: `UNAUTHORIZED`, `FORBIDDEN`, `INVALID_ARGUMENTS`, `NOT_FOUND`.
- `max_retries` (default `2`) and `retry_delay_seconds` (default `1.0s`) are strictly bounded.

---

## 10. Timeout Strategy

- **Step Timeout**: Enforced by `ToolExecutor` per individual tool (default 10s).
- **Run Timeout**: Enforced by `AgentExecutionManager` checking elapsed wall-clock time against `AGENT_MAX_RUNTIME_SECONDS` (default 120s). If exceeded, status transitions cleanly to `TIMED_OUT`.

---

## 11. Approval System (Human in the Loop)

State-changing tools (e.g., `delete_user_memory`) or steps explicitly marked `requires_approval = True`:
1. Execution halts before running the step.
2. Step status transitions to `waiting_for_approval`.
3. Run status transitions to `waiting_for_approval`.
4. User calls `POST /api/agent/runs/{id}/approve` to resume execution, or `POST /api/agent/runs/{id}/reject` to cancel the run.
5. Approvals strictly verify owner identity—User B cannot approve User A's steps.

---

## 12. Pause / Resume / Cancellation

- `POST /api/agent/runs/{id}/pause`: Safely pauses execution after the currently executing step completes.
- `POST /api/agent/runs/{id}/resume`: Resumes execution from the next pending step.
- `POST /api/agent/runs/{id}/cancel`: Cancels run and sets remaining steps to `cancelled`. Terminal runs cannot be cancelled.

---

## 13. Execution Limits & Configuration

Configured in `backend/.env` with safe defaults:
| Setting | Default | Description |
|---|---|---|
| `AGENT_ENABLED` | `true` | Master feature flag for Agent Engine |
| `AGENT_MAX_STEPS` | `10` | Maximum steps allowed in a plan |
| `AGENT_MAX_TOOL_CALLS` | `15` | Storm defense against runaway tool calls |
| `AGENT_MAX_RUNTIME_SECONDS` | `120.0` | Maximum lifetime for a single run |
| `AGENT_MAX_RETRIES` | `2` | Maximum retry attempts for recoverable errors |
| `AGENT_MAX_RESULT_SIZE` | `16384` | Max serialized size (16KB) before output truncation |

---

## 14. Persistence & Database Schema

Supabase PostgreSQL tables:
- `public.agent_runs`: Stores run metadata, current step pointer, status, and final synthesis.
- `public.agent_steps`: Stores step specifications, status, input parameters, output results, and errors.
- `public.agent_events`: Stores chronological audit events (`agent_created`, `step_started`, `tool_called`, etc.).
- Dual-tier resilience: In-memory cache protects execution if Supabase is offline or migrating.

---

## 15. User Isolation & Multi-Tenancy

- All database queries and execution methods enforce `user_id == current_user.user_id`.
- Attempts to query or control another user's agent run return `403 Forbidden` (`AgentNotOwnedError`).
- Emails and frontend-provided IDs are never trusted as authorization keys.

---

## 16. Admin Security

- Admin tools (e.g. `get_system_stats`) verify `current_user.role == "admin"`.
- The planner cannot elevate user privileges—a normal user's plan containing an admin tool is rejected at validation time.

---

## 17. Error Response Hierarchy

Consistent JSON responses with standardized codes:
- `AGENT_NOT_FOUND` (404)
- `AGENT_NOT_OWNED` (403)
- `AGENT_INVALID_STATE` (400)
- `AGENT_PLAN_INVALID` (400)
- `AGENT_STEP_INVALID` (400)
- `AGENT_DEPENDENCY_ERROR` (400)
- `AGENT_APPROVAL_REQUIRED` (400)
- `AGENT_APPROVAL_INVALID` (400)
- `AGENT_LIMIT_REACHED` (400)
- `AGENT_TIMEOUT` (504)
- `AGENT_CANCELLED` (400)
- `AGENT_TOOL_FAILED` (500)
- `AGENT_DISABLED` (503)

---

## 18. Chat & Message Persistence Integration

- In `/api/chat`, if `needs_agent_execution(msg)` is triggered, the engine executes the workflow and returns structured results.
- When an agent run belonging to a `conversation_id` completes, the final summary is saved to the `public.messages` table via `message_service.create_message`.

---

## 19. Security Boundaries

- **Zero Arbitrary Execution**: No Python `eval()`, `exec()`, or dynamic language execution.
- **Zero OS Shell Access**: No `os.system` or `subprocess.Popen(shell=True)`.
- **Zero Secret Leaks**: Audit logs and event records strip all API keys and credentials.
- **No Hidden Chain-of-Thought**: Private model thoughts are never stored in database records.

---

## 20. Idempotency & Concurrency Safety

- `idempotency_key`: Duplicate requests return the existing run without re-executing steps.
- Per-run mutex locks prevent race conditions during concurrent resume or approval calls.

---

## 21. Testing Strategy & Verification

Implemented in `backend/test_task_1_9_agent.py`:
- 17 test groups covering 79 distinct assertions.
- 100% pass rate with zero regressions across Task 1.7 (132/132) and Task 1.8 (138/138).
