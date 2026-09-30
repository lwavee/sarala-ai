"""
Agent Execution Manager.
Coordinates execution of planned steps, dependency resolution, approval gates,
timeouts, retries, limits, cancellation, and pause/resume lifecycle.
"""

import time
import uuid
import json
import threading
import datetime
from typing import Dict, Any, List, Optional, Set
from core.logger import logger
from ai.agent.models import (
    AgentRunRecord,
    AgentStepRecord,
    AgentPlan,
    AgentRunStatus,
    StepStatus,
    StepType,
    ExecutionMode,
    AgentEventType,
)
from ai.agent.errors import (
    AgentEngineError,
    AgentNotFoundError,
    AgentNotOwnedError,
    AgentInvalidStateError,
    AgentPlanInvalidError,
    AgentDependencyError,
    AgentApprovalRequiredError,
    AgentLimitReachedError,
    AgentTimeoutError,
    AgentCancelledError,
    AgentToolFailedError,
)
from ai.agent.config import agent_config
from ai.agent.repository import agent_repository, AgentRepository
from ai.agent.planner import agent_planner, AgentPlanner
from ai.tools.executor import tool_executor, ToolExecutor
from ai.tools.models import ToolResult


class AgentExecutionManager:
    """
    Central Coordinator for multi-step agent execution.
    Deterministic, state-aware, and concurrency-safe.
    """

    def __init__(
        self,
        repository: Optional[AgentRepository] = None,
        planner: Optional[AgentPlanner] = None,
        executor: Optional[ToolExecutor] = None,
    ):
        self.repo = repository or agent_repository
        self.planner = planner or agent_planner
        self.tool_executor = executor or tool_executor
        self._locks_lock = threading.Lock()
        self._run_locks: Dict[str, threading.Lock] = {}

    def _get_run_lock(self, run_id: str) -> threading.Lock:
        """Returns or creates a thread-safe mutex for the given run_id."""
        with self._locks_lock:
            if run_id not in self._run_locks:
                self._run_locks[run_id] = threading.Lock()
            return self._run_locks[run_id]

    # ── RUN CREATION ─────────────────────────────────────────────────────────

    def create_run(
        self,
        user_id: str,
        role: str,
        goal: str,
        conversation_id: Optional[str] = None,
        initial_message_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        max_steps: Optional[int] = None,
        execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL,
        auto_execute: bool = True,
    ) -> AgentRunRecord:
        """
        Creates a new agent run with a validated execution plan.
        """
        if not user_id or not str(user_id).strip():
            raise AgentEngineError("User authentication is required to create an agent run.", status_code=401)

        # 0. Idempotency Check (Prevent duplicate execution of same operation)
        if idempotency_key and str(idempotency_key).strip():
            existing = self.repo.get_run_by_idempotency_key(user_id, str(idempotency_key).strip())
            if existing:
                logger.info(f"Duplicate request detected for idempotency_key '{idempotency_key}'. Returning existing run '{existing.id}'.")
                return existing

        run_id = f"run_{uuid.uuid4().hex[:16]}"
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        effective_max_steps = max_steps or agent_config.max_steps

        # 1. Generate Structured Plan
        plan = self.planner.create_plan(
            goal=goal,
            user_id=user_id,
            user_role=role,
            max_steps=effective_max_steps,
        )

        has_approval_step = any(s.requires_approval for s in plan.steps)

        # 2. Persist Agent Run Record
        run_record = AgentRunRecord(
            id=run_id,
            user_id=user_id,
            conversation_id=conversation_id,
            initial_message_id=initial_message_id,
            goal=goal,
            status=AgentRunStatus.PLANNED,
            execution_mode=execution_mode,
            current_step=0,
            total_steps=len(plan.steps),
            max_steps=effective_max_steps,
            requires_approval=has_approval_step,
            waiting_for_approval=False,
            created_at=now_iso,
            updated_at=now_iso,
            metadata={
                "idempotency_key": idempotency_key,
                "role": role,
            },
        )
        self.repo.create_run(run_record, idempotency_key=idempotency_key)
        self.repo.record_event(run_id, user_id, AgentEventType.AGENT_CREATED.value, metadata={"goal": goal[:80]})
        self.repo.record_event(run_id, user_id, AgentEventType.PLAN_CREATED.value, metadata={"total_steps": len(plan.steps)})
        self.repo.record_event(run_id, user_id, AgentEventType.PLAN_VALIDATED.value)

        # 3. Persist Step Records
        step_records: List[AgentStepRecord] = []
        for idx, sp in enumerate(plan.steps):
            step_records.append(AgentStepRecord(
                id=f"step_{uuid.uuid4().hex[:12]}",
                agent_run_id=run_id,
                user_id=user_id,
                step_index=idx,
                step_id=sp.step_id,
                title=sp.title,
                description=sp.description,
                step_type=sp.step_type,
                status=StepStatus.PENDING,
                tool_name=sp.tool_name,
                input=sp.input,
                depends_on=sp.depends_on,
                requires_approval=sp.requires_approval,
                max_retries=agent_config.max_retries,
                created_at=now_iso,
                updated_at=now_iso,
            ))
        self.repo.create_steps(step_records)

        # 4. Auto-execute if requested
        if auto_execute:
            return self.execute_run(run_id, user_id, role)

        return run_record

    # ── RUN EXECUTION ENGINE ─────────────────────────────────────────────────

    def execute_run(self, run_id: str, user_id: str, role: str) -> AgentRunRecord:
        """
        Executes eligible steps of the agent run in deterministic dependency order.
        Respects approval gates, timeouts, execution limits, and controlled retries.
        """
        run_lock = self._get_run_lock(run_id)

        # Non-blocking or serialized concurrency lock
        acquired = run_lock.acquire(blocking=False)
        if not acquired:
            logger.info(f"Agent run '{run_id}' is already executing in another task. Waiting or skipping duplicate invocation.")
            # Wait cleanly for concurrent execution to settle
            with run_lock:
                rec = self.repo.get_run(user_id, run_id)
                if not rec:
                    raise AgentNotFoundError(f"Agent run '{run_id}' not found.")
                return rec

        try:
            return self._execute_run_internal(run_id, user_id, role)
        finally:
            run_lock.release()

    def _execute_run_internal(self, run_id: str, user_id: str, role: str) -> AgentRunRecord:
        """Internal execution loop held under mutex."""
        run = self.repo.get_run(user_id, run_id)
        if not run:
            # Check unscoped to distinguish 404 from 403
            raw_unscoped = self.repo.get_run_unscoped(run_id)
            if raw_unscoped:
                raise AgentNotOwnedError(f"Access denied: Agent run '{run_id}' belongs to another user.")
            raise AgentNotFoundError(f"Agent run '{run_id}' not found.")

        # Guard against invalid states
        if run.status in (AgentRunStatus.COMPLETED, AgentRunStatus.FAILED, AgentRunStatus.CANCELLED):
            logger.info(f"Agent run '{run_id}' is already in terminal state '{run.status.value}'.")
            return run

        if run.status == AgentRunStatus.PAUSED:
            logger.info(f"Agent run '{run_id}' is currently paused. Resume required to continue.")
            return run

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        start_time = time.time()
        max_runtime = agent_config.max_runtime_seconds

        # Transition run to RUNNING
        run = self.repo.update_run(
            user_id,
            run_id,
            {
                "status": AgentRunStatus.RUNNING,
                "waiting_for_approval": False,
                "started_at": run.started_at or now_iso,
            }
        )
        assert run is not None

        total_tool_calls = 0

        while True:
            # Check maximum runtime timeout
            elapsed = time.time() - start_time
            if elapsed > max_runtime:
                logger.error(f"Agent run '{run_id}' exceeded max runtime ({max_runtime}s).")
                run = self.repo.update_run(
                    user_id,
                    run_id,
                    {
                        "status": AgentRunStatus.TIMED_OUT,
                        "failure_reason": f"Execution exceeded maximum permitted runtime of {max_runtime} seconds.",
                        "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    }
                )
                self.repo.record_event(run_id, user_id, AgentEventType.RUN_FAILED.value, metadata={"error": "TIMEOUT"})
                assert run is not None
                return run

            steps = self.repo.get_steps(run_id, user_id)
            step_map = {s.step_id: s for s in steps}
            completed_step_ids = {s.step_id for s in steps if s.status == StepStatus.COMPLETED}
            failed_step_ids = {s.step_id for s in steps if s.status == StepStatus.FAILED}

            # Check if any dependency failure blocks downstream steps
            if failed_step_ids:
                run = self.repo.update_run(
                    user_id,
                    run_id,
                    {
                        "status": AgentRunStatus.FAILED,
                        "failure_reason": f"Execution halted due to failed dependency steps: {list(failed_step_ids)}",
                        "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    }
                )
                self.repo.record_event(run_id, user_id, AgentEventType.RUN_FAILED.value, metadata={"failed_steps": list(failed_step_ids)})
                assert run is not None
                return run

            # Find next eligible step
            next_step: Optional[AgentStepRecord] = None
            for s in steps:
                if s.status == StepStatus.PENDING:
                    # Check if all dependencies are satisfied
                    deps_satisfied = all(dep in completed_step_ids for dep in s.depends_on)
                    if deps_satisfied:
                        next_step = s
                        break
                    else:
                        # Check if any dep failed
                        if any(dep in failed_step_ids for dep in s.depends_on):
                            self.repo.update_step(run_id, s.step_id, user_id, {
                                "status": StepStatus.FAILED,
                                "error": "One or more dependencies failed.",
                            })
                            # Trigger re-evaluation
                            continue

            # If no pending eligible steps found, check if all completed
            if not next_step:
                all_done = all(s.status == StepStatus.COMPLETED for s in steps)
                if all_done:
                    # All steps completed successfully!
                    final_summary = self._synthesize_final_result(steps)
                    now_done = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    run = self.repo.update_run(
                        user_id,
                        run_id,
                        {
                            "status": AgentRunStatus.COMPLETED,
                            "current_step": len(steps),
                            "final_result": final_summary,
                            "completed_at": now_done,
                        }
                    )
                    self.repo.record_event(run_id, user_id, AgentEventType.RUN_COMPLETED.value)
                    
                    # Persist final assistant response to conversation history if available
                    if run and run.conversation_id:
                        self._persist_chat_response(run, final_summary.get("summary", "Agent workflow completed successfully."))

                    assert run is not None
                    return run
                else:
                    # Some steps are stuck, paused, or waiting
                    waiting = [s for s in steps if s.status == StepStatus.WAITING_FOR_APPROVAL]
                    if waiting:
                        run = self.repo.update_run(user_id, run_id, {
                            "status": AgentRunStatus.WAITING_FOR_APPROVAL,
                            "waiting_for_approval": True,
                        })
                        assert run is not None
                        return run

                    # Stalled state
                    logger.warning(f"No eligible steps to run for agent_run '{run_id}'. Halting.")
                    break

            # ── Check Approval Gate for next_step ──
            if next_step.requires_approval and next_step.status != StepStatus.RUNNING:
                logger.info(f"Step '{next_step.step_id}' requires explicit human approval. Pausing execution.")
                self.repo.update_step(run_id, next_step.step_id, user_id, {
                    "status": StepStatus.WAITING_FOR_APPROVAL,
                })
                run = self.repo.update_run(user_id, run_id, {
                    "status": AgentRunStatus.WAITING_FOR_APPROVAL,
                    "waiting_for_approval": True,
                    "current_step": next_step.step_index,
                })
                self.repo.record_event(
                    run_id,
                    user_id,
                    AgentEventType.APPROVAL_REQUESTED.value,
                    step_id=next_step.step_id,
                    metadata={"tool_name": next_step.tool_name},
                )
                assert run is not None
                return run

            # ── Check Limits ──
            if next_step.step_index >= run.max_steps:
                logger.error(f"Step index {next_step.step_index} reached maximum step limit ({run.max_steps}).")
                run = self.repo.update_run(user_id, run_id, {
                    "status": AgentRunStatus.FAILED,
                    "failure_reason": f"Maximum step limit ({run.max_steps}) exceeded.",
                    "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                })
                assert run is not None
                return run

            # ── Execute the step ──
            step_start = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self.repo.update_step(run_id, next_step.step_id, user_id, {
                "status": StepStatus.RUNNING,
                "started_at": step_start,
            })
            self.repo.update_run(user_id, run_id, {"current_step": next_step.step_index})
            self.repo.record_event(run_id, user_id, AgentEventType.STEP_STARTED.value, step_id=next_step.step_id)

            # Resolve templated arguments from completed previous steps
            resolved_input = self._resolve_step_input(next_step.input, step_map)

            step_success = False
            step_output: Dict[str, Any] = {}
            step_error: Optional[str] = None

            if next_step.step_type == StepType.TOOL_CALL and next_step.tool_name:
                total_tool_calls += 1
                if total_tool_calls > agent_config.max_tool_calls:
                    run = self.repo.update_run(user_id, run_id, {
                        "status": AgentRunStatus.FAILED,
                        "failure_reason": f"Maximum tool call limit ({agent_config.max_tool_calls}) exceeded.",
                        "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    })
                    assert run is not None
                    return run

                # Execute tool with retry logic
                self.repo.record_event(
                    run_id,
                    user_id,
                    AgentEventType.TOOL_CALLED.value,
                    step_id=next_step.step_id,
                    metadata={"tool_name": next_step.tool_name},
                )

                tool_res = self._execute_tool_with_retries(
                    tool_name=next_step.tool_name,
                    arguments=resolved_input,
                    user_id=user_id,
                    role=role,
                    conversation_id=run.conversation_id or "",
                    max_retries=next_step.max_retries,
                    step_id=next_step.step_id,
                    run_id=run_id,
                )

                step_success = tool_res.success
                step_output = tool_res.data if isinstance(tool_res.data, dict) else {"result": tool_res.data}
                step_error = tool_res.error

                # Handle tool-level confirmation token requirement
                if tool_res.requires_confirmation:
                    self.repo.update_step(run_id, next_step.step_id, user_id, {
                        "status": StepStatus.WAITING_FOR_APPROVAL,
                        "metadata": {"confirmation_token": tool_res.confirmation_token},
                    })
                    run = self.repo.update_run(user_id, run_id, {
                        "status": AgentRunStatus.WAITING_FOR_APPROVAL,
                        "waiting_for_approval": True,
                    })
                    self.repo.record_event(
                        run_id,
                        user_id,
                        AgentEventType.APPROVAL_REQUESTED.value,
                        step_id=next_step.step_id,
                        metadata={"confirmation_token": tool_res.confirmation_token},
                    )
                    assert run is not None
                    return run

            else:
                # Internal reasoning / transformation step
                step_success = True
                step_output = {
                    "step_type": next_step.step_type.value,
                    "processed_input": resolved_input,
                    "status": "completed",
                }

            step_end = datetime.datetime.now(datetime.timezone.utc).isoformat()

            # Bound output size to avoid memory bloat
            bounded_output = self._bound_result_size(step_output)

            if step_success:
                self.repo.update_step(run_id, next_step.step_id, user_id, {
                    "status": StepStatus.COMPLETED,
                    "output": bounded_output,
                    "completed_at": step_end,
                })
                self.repo.record_event(run_id, user_id, AgentEventType.TOOL_COMPLETED.value, step_id=next_step.step_id)
            else:
                self.repo.update_step(run_id, next_step.step_id, user_id, {
                    "status": StepStatus.FAILED,
                    "error": step_error or "Step execution failed.",
                    "completed_at": step_end,
                })
                self.repo.record_event(
                    run_id,
                    user_id,
                    AgentEventType.STEP_FAILED.value,
                    step_id=next_step.step_id,
                    metadata={"error": step_error},
                )
                # Halt entire run
                run = self.repo.update_run(user_id, run_id, {
                    "status": AgentRunStatus.FAILED,
                    "failure_reason": f"Step '{next_step.step_id}' failed: {step_error}",
                    "completed_at": step_end,
                })
                self.repo.record_event(run_id, user_id, AgentEventType.RUN_FAILED.value, metadata={"failed_step": next_step.step_id})
                assert run is not None
                return run

        assert run is not None
        return run

    def _execute_tool_with_retries(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        user_id: str,
        role: str,
        conversation_id: str,
        max_retries: int,
        step_id: str,
        run_id: str,
    ) -> ToolResult:
        """Executes a tool and applies retry policy only on recoverable failures."""
        attempts = 0
        last_res: Optional[ToolResult] = None

        while attempts <= max_retries:
            attempts += 1
            res = self.tool_executor.execute(
                tool_name=tool_name,
                arguments=arguments,
                user_id=user_id,
                role=role,
                conversation_id=conversation_id,
                tool_call_id=f"step_call_{step_id}_{attempts}",
            )
            last_res = res

            if res.success or res.requires_confirmation:
                return res

            # Check if error is recoverable
            recoverable_codes = {"TIMEOUT", "RATE_LIMITED", "PROVIDER_UNAVAILABLE", "NETWORK_ERROR"}
            is_recoverable = res.error_code in recoverable_codes

            if not is_recoverable or attempts > max_retries:
                logger.warning(
                    f"Tool '{tool_name}' failed with non-retryable or exhausted error '{res.error_code}': {res.error}"
                )
                break

            logger.info(f"Retrying tool '{tool_name}' (Attempt {attempts}/{max_retries}) due to {res.error_code}...")
            time.sleep(agent_config.retry_delay_seconds)
            self.repo.update_step(run_id, step_id, user_id, {"retry_count": attempts})

        assert last_res is not None
        return last_res

    def _resolve_step_input(self, step_input: Dict[str, Any], step_map: Dict[str, AgentStepRecord]) -> Dict[str, Any]:
        """
        Replaces dynamic step references like '{{step_1.result}}' with values from earlier completed steps.
        """
        resolved: Dict[str, Any] = {}
        for k, v in step_input.items():
            if isinstance(v, str) and ("step_" in v):
                # Check for step references
                val_str = v
                for ref_id, completed_s in step_map.items():
                    if completed_s.output:
                        out_val = completed_s.output.get("result", completed_s.output)
                        token_double = "{{" + ref_id + ".result}}"
                        token_simple = "{" + ref_id + ".result}"
                        # Replace double braces first to prevent leaving stray single braces
                        val_str = val_str.replace(token_double, str(out_val))
                        val_str = val_str.replace(token_simple, str(out_val))
                resolved[k] = val_str
            else:
                resolved[k] = v
        return resolved

    def _bound_result_size(self, data: Any) -> Any:
        """Truncates oversized result dictionaries to prevent unbounded memory growth."""
        try:
            dumped = json.dumps(data)
            if len(dumped) > agent_config.max_result_size:
                logger.warning(f"Step result exceeded max size ({len(dumped)} > {agent_config.max_result_size}). Truncating.")
                return {
                    "truncated": True,
                    "original_size_bytes": len(dumped),
                    "preview": dumped[:agent_config.max_result_size // 2] + "... [TRUNCATED]",
                }
        except Exception:
            pass
        return data

    def _synthesize_final_result(self, steps: List[AgentStepRecord]) -> Dict[str, Any]:
        """Summarizes completed step outputs into a structured final result."""
        step_summaries = []
        for s in steps:
            step_summaries.append({
                "step_id": s.step_id,
                "title": s.title,
                "tool": s.tool_name,
                "output": s.output,
            })
        
        # Build human-readable synthesis
        last_step = steps[-1] if steps else None
        last_out = (last_step.output or {}).get("result") if last_step else "Task finished."
        
        return {
            "summary": f"All {len(steps)} steps completed successfully. Final output: {last_out}",
            "completed_steps_count": len(steps),
            "step_outputs": {s.step_id: s.output for s in steps},
        }

    def _persist_chat_response(self, run: AgentRunRecord, content: str) -> None:
        """Persists the agent's completed final response into conversation history."""
        try:
            from core.services.message_service import message_service
            if run.conversation_id:
                message_service.create_message(
                    user_id=run.user_id,
                    conversation_id=run.conversation_id,
                    role="assistant",
                    content=content,
                    message_type="agent_result",
                    metadata={"agent_run_id": run.id},
                )
        except Exception as e:
            logger.warning(f"Error persisting agent assistant message to conversation: {e}")

    # ── LIFECYCLE CONTROLS ───────────────────────────────────────────────────

    def pause_run(self, run_id: str, user_id: str) -> AgentRunRecord:
        """Pauses a running or queued agent run."""
        with self._get_run_lock(run_id):
            run = self.repo.get_run(user_id, run_id)
            if not run:
                raw = self.repo.get_run_unscoped(run_id)
                if raw:
                    raise AgentNotOwnedError(f"Access denied: Agent run '{run_id}' belongs to another user.")
                raise AgentNotFoundError(f"Agent run '{run_id}' not found.")

            if run.status not in (AgentRunStatus.RUNNING, AgentRunStatus.QUEUED, AgentRunStatus.PLANNED):
                raise AgentInvalidStateError(
                    f"Cannot pause agent run in status '{run.status.value}'. Must be RUNNING, QUEUED, or PLANNED."
                )

            updated = self.repo.update_run(user_id, run_id, {"status": AgentRunStatus.PAUSED})
            self.repo.record_event(run_id, user_id, AgentEventType.RUN_PAUSED.value)
            assert updated is not None
            return updated

    def resume_run(self, run_id: str, user_id: str, role: str) -> AgentRunRecord:
        """Resumes a paused agent run."""
        with self._get_run_lock(run_id):
            run = self.repo.get_run(user_id, run_id)
            if not run:
                raw = self.repo.get_run_unscoped(run_id)
                if raw:
                    raise AgentNotOwnedError(f"Access denied: Agent run '{run_id}' belongs to another user.")
                raise AgentNotFoundError(f"Agent run '{run_id}' not found.")

            if run.status != AgentRunStatus.PAUSED:
                raise AgentInvalidStateError(
                    f"Cannot resume agent run in status '{run.status.value}'. Must be PAUSED."
                )

            self.repo.update_run(user_id, run_id, {"status": AgentRunStatus.RUNNING})
            self.repo.record_event(run_id, user_id, AgentEventType.RUN_RESUMED.value)

        # Execute resumed run outside initial pause check lock
        return self.execute_run(run_id, user_id, role)

    def cancel_run(self, run_id: str, user_id: str) -> AgentRunRecord:
        """Cancels an active, paused, or queued agent run."""
        with self._get_run_lock(run_id):
            run = self.repo.get_run(user_id, run_id)
            if not run:
                raw = self.repo.get_run_unscoped(run_id)
                if raw:
                    raise AgentNotOwnedError(f"Access denied: Agent run '{run_id}' belongs to another user.")
                raise AgentNotFoundError(f"Agent run '{run_id}' not found.")

            if run.status in (AgentRunStatus.COMPLETED, AgentRunStatus.FAILED, AgentRunStatus.CANCELLED):
                raise AgentInvalidStateError(
                    f"Cannot cancel a finalized agent run (Current status: '{run.status.value}')."
                )

            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            updated = self.repo.update_run(
                user_id,
                run_id,
                {
                    "status": AgentRunStatus.CANCELLED,
                    "completed_at": now_iso,
                    "failure_reason": "Execution cancelled by user.",
                }
            )

            # Cancel remaining non-completed steps
            steps = self.repo.get_steps(run_id, user_id)
            for s in steps:
                if s.status in (StepStatus.PENDING, StepStatus.RUNNING, StepStatus.WAITING_FOR_APPROVAL):
                    self.repo.update_step(run_id, s.step_id, user_id, {"status": StepStatus.CANCELLED})

            self.repo.record_event(run_id, user_id, AgentEventType.RUN_CANCELLED.value)
            assert updated is not None
            return updated

    def approve_step(
        self,
        run_id: str,
        user_id: str,
        role: str,
        step_id: Optional[str] = None,
    ) -> AgentRunRecord:
        """Approves a step waiting for human authorization and resumes execution."""
        with self._get_run_lock(run_id):
            run = self.repo.get_run(user_id, run_id)
            if not run:
                raw = self.repo.get_run_unscoped(run_id)
                if raw:
                    raise AgentNotOwnedError(f"Access denied: Agent run '{run_id}' belongs to another user.")
                raise AgentNotFoundError(f"Agent run '{run_id}' not found.")

            if run.status != AgentRunStatus.WAITING_FOR_APPROVAL:
                raise AgentInvalidStateError(
                    f"Agent run is not waiting for approval (Current status: '{run.status.value}')."
                )

            steps = self.repo.get_steps(run_id, user_id)
            waiting_steps = [s for s in steps if s.status == StepStatus.WAITING_FOR_APPROVAL]
            if not waiting_steps:
                raise AgentInvalidStateError("No steps are currently waiting for approval in this run.")

            target_step = waiting_steps[0]
            if step_id and target_step.step_id != step_id:
                # Find specific step
                matched = [s for s in waiting_steps if s.step_id == step_id]
                if not matched:
                    raise AgentInvalidStateError(f"Step '{step_id}' is not waiting for approval.")
                target_step = matched[0]

            # Mark step as approved (requires_approval set to False to permit execution)
            self.repo.update_step(run_id, target_step.step_id, user_id, {
                "status": StepStatus.PENDING,
                "requires_approval": False,
            })
            self.repo.update_run(user_id, run_id, {
                "status": AgentRunStatus.RUNNING,
                "waiting_for_approval": False,
            })
            self.repo.record_event(
                run_id,
                user_id,
                AgentEventType.APPROVAL_RECEIVED.value,
                step_id=target_step.step_id,
            )

        # Resume execution
        return self.execute_run(run_id, user_id, role)

    def reject_step(
        self,
        run_id: str,
        user_id: str,
        step_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> AgentRunRecord:
        """Rejects a step waiting for human authorization, cancelling the run."""
        with self._get_run_lock(run_id):
            run = self.repo.get_run(user_id, run_id)
            if not run:
                raw = self.repo.get_run_unscoped(run_id)
                if raw:
                    raise AgentNotOwnedError(f"Access denied: Agent run '{run_id}' belongs to another user.")
                raise AgentNotFoundError(f"Agent run '{run_id}' not found.")

            if run.status != AgentRunStatus.WAITING_FOR_APPROVAL:
                raise AgentInvalidStateError(
                    f"Agent run is not waiting for approval (Current status: '{run.status.value}')."
                )

            steps = self.repo.get_steps(run_id, user_id)
            waiting_steps = [s for s in steps if s.status == StepStatus.WAITING_FOR_APPROVAL]
            if not waiting_steps:
                raise AgentInvalidStateError("No steps are currently waiting for approval in this run.")

            target_step = waiting_steps[0]
            if step_id and target_step.step_id != step_id:
                matched = [s for s in waiting_steps if s.step_id == step_id]
                if not matched:
                    raise AgentInvalidStateError(f"Step '{step_id}' is not waiting for approval.")
                target_step = matched[0]

            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            rejection_reason = reason or "Step rejected by user."

            self.repo.update_step(run_id, target_step.step_id, user_id, {
                "status": StepStatus.CANCELLED,
                "error": rejection_reason,
            })
            updated = self.repo.update_run(user_id, run_id, {
                "status": AgentRunStatus.CANCELLED,
                "waiting_for_approval": False,
                "failure_reason": rejection_reason,
                "completed_at": now_iso,
            })
            self.repo.record_event(
                run_id,
                user_id,
                AgentEventType.RUN_CANCELLED.value,
                step_id=target_step.step_id,
                metadata={"reason": rejection_reason},
            )
            assert updated is not None
            return updated


# Global singleton execution manager
agent_execution_manager = AgentExecutionManager()
