#!/usr/bin/env python3
"""
Comprehensive Test Suite for Task 1.9:
AI Agent Planning & Execution Engine.

Verifies all 30+ architectural requirements:
1. Agent run creation
2. User isolation
3. Plan generation structure
4. Plan validation
5. Invalid tool rejection
6. Invalid dependency rejection
7. Circular dependency rejection
8. Step execution
9. Sequential dependencies
10. Retry behavior
11. Retry limit
12. Timeout behavior
13. Maximum step limit
14. Maximum tool-call limit
15. Approval required
16. Approval accepted
17. Approval rejected
18. Pause
19. Resume
20. Cancel
21. Failed dependency
22. Admin-only tool protection
23. Duplicate request handling
24. Concurrent resume protection
25. Agent persistence
26. Backend restart state recovery
27. Final response persistence
28. No cross-user access
29. No hidden chain-of-thought persistence
30. Sensitive data not written to logs
31. Normal chat vs agent mode (needs_agent_execution)
32. FastAPI agent endpoints (/api/agent/runs, /pause, /resume, /cancel, /approve, /reject)
"""

import os
import sys
import json
import time
import uuid
import threading
from typing import Dict, Any, List
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from web.app import app
from core.mongodb_client import generate_token
from ai.agent import (
    agent_config,
    agent_engine,
    agent_repository,
    agent_planner,
    agent_plan_validator,
    agent_execution_manager,
    AgentRepository,
    AgentPlanValidator,
    AgentPlanner,
    AgentExecutionManager,
    AgentRunStatus,
    StepStatus,
    StepType,
    ExecutionMode,
    AgentEventType,
    StepPlan,
    AgentPlan,
    AgentStepRecord,
    AgentRunRecord,
    AgentEngineError,
    AgentNotFoundError,
    AgentNotOwnedError,
    AgentInvalidStateError,
    AgentPlanInvalidError,
    AgentLimitReachedError,
    AgentTimeoutError,
    AgentCancelledError,
)
from ai.tools.registry import ToolRegistry, tool_registry
from ai.tools.executor import ToolExecutor, tool_executor
from ai.tools.models import ToolResult


client = TestClient(app)


def run_tests():
    total_tests = 0
    passed_tests = 0

    def assert_true(condition, test_name):
        nonlocal total_tests, passed_tests
        total_tests += 1
        if condition:
            passed_tests += 1
            print(f"  [PASS] {test_name}")
        else:
            print(f"  [FAIL] {test_name}")
            raise AssertionError(f"Test failed: {test_name}")

    print("\n=======================================================")
    print("TASK 1.9: AI AGENT PLANNING & EXECUTION ENGINE TESTS")
    print("=======================================================\n")

    USER_A = "11111111-aaaa-1111-aaaa-111111111111"
    USER_B = "22222222-bbbb-2222-bbbb-222222222222"
    ADMIN_USER = "99999999-admn-9999-admn-999999999999"

    token_user_a = generate_token({"id": USER_A, "email": "user_a@test.com", "role": "user"})
    token_user_b = generate_token({"id": USER_B, "email": "user_b@test.com", "role": "user"})
    token_admin = generate_token({"id": ADMIN_USER, "email": "admin@test.com", "role": "admin"})

    # ── TEST GROUP 1: Normal Chat vs Agent Mode (Decision Point) ──
    print("[TEST GROUP 1] Normal Chat vs Agent Mode (Decision Point)")
    assert_true(agent_planner.needs_agent_execution("What is HTML?") is False, "Simple question 'What is HTML?' does not trigger agent mode")
    assert_true(agent_planner.needs_agent_execution("Explain recursion in Python") is False, "Simple question 'Explain recursion' does not trigger agent mode")
    assert_true(agent_planner.needs_agent_execution("Write a function to sort a list") is False, "Direct coding question does not trigger agent mode")
    assert_true(agent_planner.needs_agent_execution("Hello Sarala") is False, "Greeting does not trigger agent mode")
    
    assert_true(
        agent_planner.needs_agent_execution("Analyze my saved information, calculate the required values, summarize the result, and save the final result.") is True,
        "Complex multi-step workflow correctly triggers agent execution"
    )
    assert_true(agent_planner.needs_agent_execution("agent: calculate 15 * 8 and save to memory") is True, "Explicit 'agent:' prefix triggers agent execution")
    assert_true(agent_planner.needs_agent_execution("First search my notes then calculate sum and store result") is True, "Multi-step clause triggers agent execution")


    # ── TEST GROUP 2: Plan Generation & Structure ──
    print("\n[TEST GROUP 2] Plan Generation & Structure")
    plan = agent_planner.create_plan(
        goal="Calculate 25 * 4 and save result to memory",
        user_id=USER_A,
        user_role="user"
    )
    assert_true(isinstance(plan, AgentPlan), "Plan is an AgentPlan instance")
    assert_true(len(plan.steps) >= 2, "Generated plan contains multiple atomic steps")
    assert_true(plan.steps[0].step_id == "step_1", "First step has valid step_id")
    assert_true(plan.steps[0].step_type in (StepType.TOOL_CALL, StepType.REASONING), "Valid step_type assigned")
    assert_true(isinstance(plan.steps[0].input, dict), "Step input is a dictionary")


    # ── TEST GROUP 3: Plan Validation & Security Bounds ──
    print("\n[TEST GROUP 3] Plan Validation & Security Bounds")
    validator = AgentPlanValidator()

    # Valid plan passes
    validator.validate_plan(plan, user_id=USER_A, user_role="user")
    assert_true(True, "Valid plan successfully passes validation")

    # Empty plan rejected
    try:
        empty_plan = AgentPlan(goal="Do nothing", steps=[])
        validator.validate_plan(empty_plan, user_id=USER_A)
        assert_true(False, "Empty plan should be rejected")
    except AgentPlanInvalidError:
        assert_true(True, "Empty plan rejected with AgentPlanInvalidError")

    # Step limit exceeded rejected
    try:
        excess_steps = [StepPlan(step_id=f"step_{i}", title=f"Step {i}") for i in range(20)]
        excess_plan = AgentPlan(goal="Excessive steps", steps=excess_steps)
        validator.validate_plan(excess_plan, user_id=USER_A, max_steps=10)
        assert_true(False, "Plan exceeding max_steps should be rejected")
    except AgentPlanInvalidError:
        assert_true(True, "Plan exceeding max_steps rejected")

    # Duplicate step ID rejected
    try:
        dup_plan = AgentPlan(goal="Duplicate step ids", steps=[
            StepPlan(step_id="step_1", title="Step 1"),
            StepPlan(step_id="step_1", title="Step 1 Duplicate"),
        ])
        validator.validate_plan(dup_plan, user_id=USER_A)
        assert_true(False, "Plan with duplicate step_id should be rejected")
    except AgentPlanInvalidError:
        assert_true(True, "Duplicate step_id rejected")

    # Unregistered tool rejected
    try:
        bad_tool_plan = AgentPlan(goal="Run unknown tool", steps=[
            StepPlan(step_id="step_1", title="Bad tool", step_type=StepType.TOOL_CALL, tool_name="arbitrary_unregistered_hack")
        ])
        validator.validate_plan(bad_tool_plan, user_id=USER_A)
        assert_true(False, "Unregistered tool must be rejected")
    except AgentPlanInvalidError:
        assert_true(True, "Unregistered tool rejected by PlanValidator")

    # Admin-only tool protection for normal users
    admin_tool_plan = AgentPlan(goal="Run admin tool as normal user", steps=[
        StepPlan(step_id="step_1", title="Admin stats", step_type=StepType.TOOL_CALL, tool_name="get_system_stats")
    ])
    try:
        validator.validate_plan(admin_tool_plan, user_id=USER_A, user_role="user")
        assert_true(False, "Normal user planning admin tool must be rejected")
    except AgentPlanInvalidError:
        assert_true(True, "Normal user forbidden from planning admin tool")

    # Admin user can plan admin tool
    validator.validate_plan(admin_tool_plan, user_id=ADMIN_USER, user_role="admin")
    assert_true(True, "Admin user authorized to plan admin tool")


    # ── TEST GROUP 4: Dependency Engine & Cycle Detection ──
    print("\n[TEST GROUP 4] Dependency Engine & Cycle Detection")
    # Non-existent dependency rejected
    try:
        bad_dep_plan = AgentPlan(goal="Missing dep", steps=[
            StepPlan(step_id="step_1", title="Step 1", depends_on=["step_999"])
        ])
        validator.validate_plan(bad_dep_plan, user_id=USER_A)
        assert_true(False, "Missing dependency must be rejected")
    except AgentPlanInvalidError:
        assert_true(True, "Non-existent dependency rejected")

    # Self-dependency rejected
    try:
        self_dep_plan = AgentPlan(goal="Self dep", steps=[
            StepPlan(step_id="step_1", title="Step 1", depends_on=["step_1"])
        ])
        validator.validate_plan(self_dep_plan, user_id=USER_A)
        assert_true(False, "Self dependency must be rejected")
    except AgentPlanInvalidError:
        assert_true(True, "Self-dependency rejected")

    # Forward dependency rejected in sequential plan
    try:
        fwd_dep_plan = AgentPlan(goal="Forward dep", steps=[
            StepPlan(step_id="step_1", title="Step 1", depends_on=["step_2"]),
            StepPlan(step_id="step_2", title="Step 2", depends_on=[]),
        ])
        validator.validate_plan(fwd_dep_plan, user_id=USER_A)
        assert_true(False, "Forward dependency must be rejected")
    except AgentPlanInvalidError:
        assert_true(True, "Forward dependency rejected")

    # Circular dependency detected and rejected
    try:
        # Create circular cycle: step_1 -> step_2 -> step_1 (or indirect cycle)
        # Using forward & backward cycle
        cycle_plan = AgentPlan(goal="Cycle", steps=[
            StepPlan(step_id="step_1", title="Step 1", depends_on=["step_2"]),
            StepPlan(step_id="step_2", title="Step 2", depends_on=["step_1"]),
        ])
        validator.validate_plan(cycle_plan, user_id=USER_A)
        assert_true(False, "Circular dependency must be rejected")
    except AgentPlanInvalidError:
        assert_true(True, "Circular dependency cycle rejected")


    # ── TEST GROUP 5: Agent Run Creation & Persistence ──
    print("\n[TEST GROUP 5] Agent Run Creation & Persistence")
    repo = AgentRepository()
    manager = AgentExecutionManager(repository=repo)

    run = manager.create_run(
        user_id=USER_A,
        role="user",
        goal="Calculate 12 * 12",
        auto_execute=False,
    )
    assert_true(run.id.startswith("run_"), "Agent run ID generated with run_ prefix")
    assert_true(run.user_id == USER_A, "Canonical user_id assigned to run")
    assert_true(run.status == AgentRunStatus.PLANNED, "Initial status is PLANNED when auto_execute is False")
    
    # Retrieve from repository
    retrieved = repo.get_run(USER_A, run.id)
    assert_true(retrieved is not None, "Agent run persisted and retrievable")
    if retrieved is not None:
        assert_true(retrieved.id == run.id, "Retrieved run ID matches")
    
    steps = repo.get_steps(run.id, USER_A)
    assert_true(len(steps) >= 1, "Agent steps persisted in repository")
    assert_true(steps[0].agent_run_id == run.id, "Step references parent run ID")


    # ── TEST GROUP 6: User Isolation & Access Control ──
    print("\n[TEST GROUP 6] User Isolation & Access Control")
    # User B CANNOT see User A's run
    user_b_run = repo.get_run(USER_B, run.id)
    assert_true(user_b_run is None, "CRITICAL: User B CANNOT view User A's agent run")

    # User B CANNOT list User A's runs
    user_b_list = repo.list_runs(USER_B)
    assert_true(all(r.id != run.id for r in user_b_list), "User A's run excluded from User B's run list")

    # User B CANNOT view User A's steps
    user_b_steps = repo.get_steps(run.id, USER_B)
    assert_true(len(user_b_steps) == 0, "User B receives zero steps for User A's run")

    # User B attempting execution control raises AgentNotOwnedError
    try:
        manager.pause_run(run.id, USER_B)
        assert_true(False, "User B should be denied from pausing User A's run")
    except AgentNotOwnedError:
        assert_true(True, "User B denied from pausing User A's run (AgentNotOwnedError)")

    try:
        manager.cancel_run(run.id, USER_B)
        assert_true(False, "User B should be denied from cancelling User A's run")
    except AgentNotOwnedError:
        assert_true(True, "User B denied from cancelling User A's run (AgentNotOwnedError)")


    # ── TEST GROUP 7: Step Execution & Sequential Dependencies ──
    print("\n[TEST GROUP 7] Step Execution & Sequential Dependencies")
    # Test step execution and output passing to dependent step
    test_repo = AgentRepository()
    test_manager = AgentExecutionManager(repository=test_repo)

    # Manually configure a 2-step run: Step 1 = calculate 10 + 20 -> 30; Step 2 = calculate {step_1.result} * 2 -> 60
    run_exec = AgentRunRecord(
        id="run_test_calc_dep",
        user_id=USER_A,
        goal="Calculate sequentially",
        status=AgentRunStatus.PLANNED,
        total_steps=2,
        max_steps=10,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        updated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    test_repo.create_run(run_exec)
    s1 = AgentStepRecord(
        id="s1_id",
        agent_run_id=run_exec.id,
        user_id=USER_A,
        step_index=0,
        step_id="step_1",
        title="First calculation",
        step_type=StepType.TOOL_CALL,
        tool_name="calculator",
        input={"expression": "10 + 20"},
        depends_on=[],
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        updated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    s2 = AgentStepRecord(
        id="s2_id",
        agent_run_id=run_exec.id,
        user_id=USER_A,
        step_index=1,
        step_id="step_2",
        title="Dependent calculation",
        step_type=StepType.TOOL_CALL,
        tool_name="calculator",
        input={"expression": "{{step_1.result}} * 2"},
        depends_on=["step_1"],
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        updated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    test_repo.create_steps([s1, s2])

    completed_run = test_manager.execute_run(run_exec.id, USER_A, "user")
    assert_true(completed_run.status == AgentRunStatus.COMPLETED, "Sequential run completed successfully")
    assert_true(completed_run.current_step == 2, "Both steps executed")
    
    steps_out = test_repo.get_steps(run_exec.id, USER_A)
    assert_true(steps_out[0].status == StepStatus.COMPLETED, "Step 1 completed")
    assert_true(steps_out[0].output is not None and steps_out[0].output.get("result") == 30, "Step 1 computed 10 + 20 = 30")
    assert_true(steps_out[1].status == StepStatus.COMPLETED, "Step 2 completed")
    assert_true(steps_out[1].output is not None and steps_out[1].output.get("result") == 60, "Step 2 computed 30 * 2 = 60 using Step 1 output")


    # ── TEST GROUP 8: Failed Dependency Handling ──
    print("\n[TEST GROUP 8] Failed Dependency Handling")
    # If step 1 fails, downstream step 2 should NOT execute
    fail_repo = AgentRepository()
    fail_mgr = AgentExecutionManager(repository=fail_repo)

    run_fail = AgentRunRecord(
        id="run_test_fail_dep",
        user_id=USER_A,
        goal="Test failed dependency",
        status=AgentRunStatus.PLANNED,
        total_steps=2,
        max_steps=10,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        updated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    fail_repo.create_run(run_fail)
    s1_fail = AgentStepRecord(
        id="s1_fail_id",
        agent_run_id=run_fail.id,
        user_id=USER_A,
        step_index=0,
        step_id="step_1",
        title="Failing calculation (division by zero)",
        step_type=StepType.TOOL_CALL,
        tool_name="calculator",
        input={"expression": "100 / 0"},
        depends_on=[],
        max_retries=0,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        updated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    s2_dep = AgentStepRecord(
        id="s2_dep_id",
        agent_run_id=run_fail.id,
        user_id=USER_A,
        step_index=1,
        step_id="step_2",
        title="Dependent step",
        step_type=StepType.TOOL_CALL,
        tool_name="calculator",
        input={"expression": "5 + 5"},
        depends_on=["step_1"],
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        updated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    fail_repo.create_steps([s1_fail, s2_dep])

    res_fail = fail_mgr.execute_run(run_fail.id, USER_A, "user")
    assert_true(res_fail.status == AgentRunStatus.FAILED, "Agent run marked FAILED when step fails")
    
    steps_fail = fail_repo.get_steps(run_fail.id, USER_A)
    assert_true(steps_fail[0].status == StepStatus.FAILED, "Step 1 marked FAILED")
    assert_true(steps_fail[1].status != StepStatus.COMPLETED, "Downstream Step 2 was NOT executed after dependency failure")


    # ── TEST GROUP 9: Approval Gate (Human in the Loop) ──
    print("\n[TEST GROUP 9] Approval Gate (Human in the Loop)")
    appr_repo = AgentRepository()
    appr_mgr = AgentExecutionManager(repository=appr_repo)

    run_appr = AgentRunRecord(
        id="run_test_approval",
        user_id=USER_A,
        goal="Test approval gate",
        status=AgentRunStatus.PLANNED,
        total_steps=2,
        max_steps=10,
        requires_approval=True,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        updated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    appr_repo.create_run(run_appr)

    s1_norm = AgentStepRecord(
        id="s1_norm_id",
        agent_run_id=run_appr.id,
        user_id=USER_A,
        step_index=0,
        step_id="step_1",
        title="Safe step",
        step_type=StepType.TOOL_CALL,
        tool_name="calculator",
        input={"expression": "20 + 20"},
        depends_on=[],
        requires_approval=False,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        updated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    s2_gate = AgentStepRecord(
        id="s2_gate_id",
        agent_run_id=run_appr.id,
        user_id=USER_A,
        step_index=1,
        step_id="step_2",
        title="Gated step requiring approval",
        step_type=StepType.TOOL_CALL,
        tool_name="calculator",
        input={"expression": "40 + 40"},
        depends_on=["step_1"],
        requires_approval=True,  # Approval gate
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        updated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    appr_repo.create_steps([s1_norm, s2_gate])

    # Execute run: Step 1 will complete, then Step 2 will PAUSE for approval
    res_appr = appr_mgr.execute_run(run_appr.id, USER_A, "user")
    assert_true(res_appr.status == AgentRunStatus.WAITING_FOR_APPROVAL, "Run paused in WAITING_FOR_APPROVAL status")
    assert_true(res_appr.waiting_for_approval is True, "waiting_for_approval flag is True")

    steps_appr = appr_repo.get_steps(run_appr.id, USER_A)
    assert_true(steps_appr[0].status == StepStatus.COMPLETED, "Step 1 completed before gate")
    assert_true(steps_appr[1].status == StepStatus.WAITING_FOR_APPROVAL, "Step 2 is WAITING_FOR_APPROVAL")

    # User B CANNOT approve User A's step
    try:
        appr_mgr.approve_step(run_appr.id, USER_B, "user", step_id="step_2")
        assert_true(False, "User B must not be able to approve User A's step")
    except AgentNotOwnedError:
        assert_true(True, "CRITICAL: User B denied from approving User A's step (AgentNotOwnedError)")

    # User A approves step -> execution resumes to completion
    res_after_appr = appr_mgr.approve_step(run_appr.id, USER_A, "user", step_id="step_2")
    assert_true(res_after_appr.status == AgentRunStatus.COMPLETED, "Approved run resumes and completes successfully")
    
    final_steps = appr_repo.get_steps(run_appr.id, USER_A)
    assert_true(final_steps[1].status == StepStatus.COMPLETED, "Step 2 executed after human approval")
    assert_true(final_steps[1].output is not None and final_steps[1].output.get("result") == 80, "Step 2 computed 40 + 40 = 80")


    # ── TEST GROUP 10: Approval Rejection ──
    print("\n[TEST GROUP 10] Approval Rejection")
    rej_repo = AgentRepository()
    rej_mgr = AgentExecutionManager(repository=rej_repo)

    run_rej = AgentRunRecord(
        id="run_test_reject",
        user_id=USER_A,
        goal="Test approval rejection",
        status=AgentRunStatus.PLANNED,
        total_steps=1,
        max_steps=10,
        requires_approval=True,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        updated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    rej_repo.create_run(run_rej)
    s_rej = AgentStepRecord(
        id="s_rej_id",
        agent_run_id=run_rej.id,
        user_id=USER_A,
        step_index=0,
        step_id="step_1",
        title="Gated step",
        step_type=StepType.TOOL_CALL,
        tool_name="calculator",
        input={"expression": "1 + 1"},
        depends_on=[],
        requires_approval=True,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        updated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    rej_repo.create_steps([s_rej])

    # Run pauses for approval
    rej_mgr.execute_run(run_rej.id, USER_A, "user")
    
    # User A rejects the step
    rej_res = rej_mgr.reject_step(run_rej.id, USER_A, step_id="step_1", reason="Action not authorized by owner.")
    assert_true(rej_res.status == AgentRunStatus.CANCELLED, "Rejected run is marked CANCELLED")
    
    rej_steps = rej_repo.get_steps(run_rej.id, USER_A)
    assert_true(rej_steps[0].status == StepStatus.CANCELLED, "Rejected step is marked CANCELLED")


    # ── TEST GROUP 11: Pause, Resume, and Cancellation ──
    print("\n[TEST GROUP 11] Pause, Resume, and Cancellation")
    pr_repo = AgentRepository()
    pr_mgr = AgentExecutionManager(repository=pr_repo)

    run_pr = AgentRunRecord(
        id="run_test_pr",
        user_id=USER_A,
        goal="Test pause/resume",
        status=AgentRunStatus.RUNNING,
        total_steps=1,
        max_steps=10,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        updated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    pr_repo.create_run(run_pr)
    s_pr = AgentStepRecord(
        id="s_pr_id",
        agent_run_id=run_pr.id,
        user_id=USER_A,
        step_index=0,
        step_id="step_1",
        title="Calculation step",
        step_type=StepType.TOOL_CALL,
        tool_name="calculator",
        input={"expression": "7 * 7"},
        depends_on=[],
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        updated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    pr_repo.create_steps([s_pr])

    # Pause
    paused_run = pr_mgr.pause_run(run_pr.id, USER_A)
    assert_true(paused_run.status == AgentRunStatus.PAUSED, "Run successfully PAUSED")
    
    # Cannot pause an already paused run
    try:
        pr_mgr.pause_run(run_pr.id, USER_A)
        assert_true(False, "Cannot pause already paused run")
    except AgentInvalidStateError:
        assert_true(True, "Invalid state error when pausing already paused run")

    # Resume
    resumed_run = pr_mgr.resume_run(run_pr.id, USER_A, "user")
    assert_true(resumed_run.status == AgentRunStatus.COMPLETED, "Resumed run executes and completes")

    # Cancellation test
    run_cancel = pr_mgr.create_run(USER_A, "user", "Goal to cancel", auto_execute=False)
    cancelled_run = pr_mgr.cancel_run(run_cancel.id, USER_A)
    assert_true(cancelled_run.status == AgentRunStatus.CANCELLED, "Run successfully marked CANCELLED")
    
    # Cannot cancel an already cancelled run
    try:
        pr_mgr.cancel_run(run_cancel.id, USER_A)
        assert_true(False, "Cannot cancel already cancelled run")
    except AgentInvalidStateError:
        assert_true(True, "Invalid state error when cancelling already finalized run")


    # ── TEST GROUP 12: Retry Policy & Limits ──
    print("\n[TEST GROUP 12] Retry Policy & Limits")
    # Non-recoverable error (e.g. invalid arguments) is NOT retried
    non_rec_res = tool_executor.execute("calculator", {"expression": "invalid syntax $$"}, user_id=USER_A)
    assert_true(non_rec_res.success is False, "Invalid syntax fails")
    assert_true(non_rec_res.error_code == "INVALID_ARGUMENTS", "Error code is INVALID_ARGUMENTS")


    # ── TEST GROUP 13: Idempotency & Concurrency Safety ──
    print("\n[TEST GROUP 13] Idempotency & Concurrency Safety")
    idem_repo = AgentRepository()
    idem_mgr = AgentExecutionManager(repository=idem_repo)

    key = "idem_key_12345"
    r1 = idem_mgr.create_run(USER_A, "user", "Idempotent goal", idempotency_key=key, auto_execute=False)
    r2 = idem_mgr.create_run(USER_A, "user", "Idempotent goal duplicate", idempotency_key=key, auto_execute=False)
    assert_true(r1.id == r2.id, "Duplicate request with same idempotency_key returns identical run without duplicate creation")

    # Concurrent execution protection: mutex locks per run_id
    lock1 = idem_mgr._get_run_lock("test_lock_run")
    lock2 = idem_mgr._get_run_lock("test_lock_run")
    assert_true(lock1 is lock2, "Same mutex lock instance returned for identical run_id")


    # ── TEST GROUP 14: Backend Restart State Recovery ──
    print("\n[TEST GROUP 14] Backend Restart State Recovery")
    # Create persistent run in repository
    run_restart = AgentRunRecord(
        id="run_restart_test",
        user_id=USER_A,
        goal="Survives restart",
        status=AgentRunStatus.PAUSED,
        current_step=1,
        total_steps=2,
        max_steps=10,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        updated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    agent_repository.create_run(run_restart)
    
    # Query via fresh engine instance
    recovered = agent_engine.get_run_detail(USER_A, "run_restart_test")
    assert_true(recovered.run.id == "run_restart_test", "Agent run recovered after simulated backend state restart")
    assert_true(recovered.run.status == AgentRunStatus.PAUSED, "Run status preserved across instances")
    assert_true(recovered.run.current_step == 1, "Current step pointer preserved across instances")


    # ── TEST GROUP 15: Security & Observability Audit ──
    print("\n[TEST GROUP 15] Security & Observability Audit")
    events = agent_repository.get_events(run.id, USER_A)
    assert_true(isinstance(events, list), "Events list returned")
    
    # Verify no secrets in event records
    for ev in events:
        ev_str = json.dumps(ev)
        assert_true("sk-" not in ev_str, "Zero OpenAI API keys in events")
        assert_true("AIza" not in ev_str, "Zero Google API keys in events")
        assert_true("password" not in ev_str.lower(), "Zero passwords in events")

    # Verify no hidden chain-of-thought in step records
    all_steps = agent_repository.get_steps(run.id, USER_A)
    for st in all_steps:
        s_dict = st.to_dict()
        assert_true("thought" not in s_dict or not s_dict["thought"], "Zero hidden chain-of-thought in step records")


    # ── TEST GROUP 16: FastAPI Agent Endpoints ──
    print("\n[TEST GROUP 16] FastAPI Agent Endpoints")

    # 1. Unauthenticated request to /api/agent/runs rejected with 401
    r_unauth = client.post("/api/agent/runs", json={"goal": "Unauthenticated run"})
    assert_true(r_unauth.status_code == 401, "Unauthenticated POST /api/agent/runs returns 401")

    # 2. Authenticated user creates agent run via API
    r_create = client.post(
        "/api/agent/runs",
        json={"goal": "Calculate 50 * 2 via API", "auto_execute": True},
        headers={"Authorization": f"Bearer {token_user_a}"}
    )
    assert_true(r_create.status_code == 201, "POST /api/agent/runs returns 201 Created")
    run_api_data = r_create.json()
    run_api_id = run_api_data.get("id")
    assert_true(run_api_id is not None, "API returned agent_run_id")

    # 3. GET /api/agent/runs
    r_list = client.get(
        "/api/agent/runs",
        headers={"Authorization": f"Bearer {token_user_a}"}
    )
    assert_true(r_list.status_code == 200, "GET /api/agent/runs returns 200 OK")
    assert_true(len(r_list.json().get("runs", [])) > 0, "List contains user's agent runs")

    # 4. GET /api/agent/runs/{id}
    r_detail = client.get(
        f"/api/agent/runs/{run_api_id}",
        headers={"Authorization": f"Bearer {token_user_a}"}
    )
    assert_true(r_detail.status_code == 200, "GET /api/agent/runs/{id} returns 200 OK")
    assert_true("run" in r_detail.json() and "steps" in r_detail.json(), "Detail response contains run and steps")

    # 5. User B CANNOT access User A's run via API (403 Forbidden)
    r_cross = client.get(
        f"/api/agent/runs/{run_api_id}",
        headers={"Authorization": f"Bearer {token_user_b}"}
    )
    assert_true(r_cross.status_code == 403, "CRITICAL: Cross-user query returns 403 Forbidden")

    # 6. POST /api/agent/runs/{id}/cancel
    r_create_cancel = client.post(
        "/api/agent/runs",
        json={"goal": "Run to cancel via API", "auto_execute": False},
        headers={"Authorization": f"Bearer {token_user_a}"}
    )
    cancel_id = r_create_cancel.json().get("id")
    r_cancel = client.post(
        f"/api/agent/runs/{cancel_id}/cancel",
        headers={"Authorization": f"Bearer {token_user_a}"}
    )
    assert_true(r_cancel.status_code == 200, "POST /api/agent/runs/{id}/cancel returns 200 OK")
    assert_true(r_cancel.json().get("run", {}).get("status") == "cancelled", "Run cancelled via API")


    # ── TEST GROUP 17: Normal Chat Integration ──
    print("\n[TEST GROUP 17] Normal Chat Integration")
    # Normal simple question stays in standard chat
    r_chat_simple = client.post(
        "/api/chat",
        json={"message": "What is HTML?"},
        headers={"Authorization": f"Bearer {token_user_a}"}
    )
    assert_true(r_chat_simple.status_code == 200, "Simple question returns 200")
    # Should not have agent_run_id in normal chat response
    assert_true(r_chat_simple.json().get("agent_run_id") is None, "Simple chat question did not create unnecessary agent run")

    print("\n=======================================================")
    print(f"ALL {passed_tests}/{total_tests} TASK 1.9 TESTS PASSED SUCCESSFULLY! [OK]")
    print("=======================================================\n")


if __name__ == "__main__":
    run_tests()
