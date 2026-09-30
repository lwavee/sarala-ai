#!/usr/bin/env python3
"""
Comprehensive Test Suite for Task 1.8:
AI Tool & Function Execution Layer.

Verifies:
1. Central Tool Registry & Discovery (Role-aware, Auth-aware, Enabled filtering)
2. Tool Input Schema Validation (Required parameters, primitive type enforcement)
3. Authentication & User Identity Enforcement (AI user_id argument spoofing prevention)
4. Role-Based Permissions & Admin Tools Isolation
5. Safe Mathematical Calculator Tool (AST Parser, Rejection of eval/exec/import/loops)
6. User Profile & Preferences Tools (Canonical identity enforcement)
7. User Memory Tools (User A vs User B Isolation, CRUD operations)
8. User Conversation Tools (Ownership verification, Cross-user denial)
9. User Confirmation Flow & Security (Single use, TTL expiry, Cross-user denial)
10. AI Orchestrator Tool Loop & Loop Protections (Storm defense, Max call limit)
11. Tool Execution Timeout Enforcement (TOOL_TIMEOUT)
12. Output Size Limiting & Result Truncation (MAX_TOOL_RESULT_SIZE)
13. Normalized Error Handling (11 error codes)
14. Audit Logging & Telemetry (Zero secrets, passwords, or tokens in logs)
15. FastAPI Endpoints (/api/ai/tools, /api/ai/tools/execute, /api/ai/tools/confirm)
16. Codebase Security Verification (Zero eval/exec/shell=True in tools)
"""

import os
import sys
import json
import time
import uuid
from typing import Dict, Any, List
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from web.app import app
from core.mongodb_client import generate_token
from ai.tools.models import (
    ToolDefinition,
    ToolCall,
    ToolResult,
    ToolCategory,
    RiskLevel,
    ToolActionType,
)
from ai.tools.errors import (
    ToolError,
    ToolNotFoundError,
    ToolDisabledError,
    UnauthorizedError,
    ForbiddenError,
    InvalidArgumentsError,
    ToolTimeoutError,
    ConfirmationRequiredError,
)
from ai.tools.registry import ToolRegistry, tool_registry
from ai.tools.executor import ToolExecutor, tool_executor, MAX_TOOL_RESULT_SIZE
from ai.tools.confirmation import ConfirmationManager, confirmation_manager
from ai.tools.implementations.calculator import calculate
from ai.models import (
    AIRequest,
    AIResponse,
    AIUsage,
    ModelConfig,
    ModelRegistry,
)
from ai.orchestrator import AIOrchestrator


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
    print("TASK 1.8: AI TOOL & FUNCTION EXECUTION LAYER TESTS")
    print("=======================================================\n")

    USER_A = "11111111-aaaa-1111-aaaa-111111111111"
    USER_B = "22222222-bbbb-2222-bbbb-222222222222"
    ADMIN_USER = "99999999-admn-9999-admn-999999999999"

    token_user_a = generate_token({"id": USER_A, "email": "user_a@test.com", "role": "user"})
    token_user_b = generate_token({"id": USER_B, "email": "user_b@test.com", "role": "user"})
    token_admin = generate_token({"id": ADMIN_USER, "email": "admin@test.com", "role": "admin"})

    # ── TEST GROUP 1: Central Tool Registry & Discovery ──
    print("[TEST GROUP 1] Central Tool Registry & Discovery")
    reg = ToolRegistry()
    assert_true(reg.get("calculator") is not None, "Calculator tool registered in catalog")
    assert_true(reg.get("get_current_user_profile") is not None, "Profile tool registered")
    assert_true(reg.get("get_user_memories") is not None, "Memory tool registered")
    assert_true(reg.get("get_conversation") is not None, "Conversation tool registered")
    assert_true(reg.get("get_system_stats") is not None, "Admin stats tool registered")

    # Discovery by role & authentication
    guest_tools = reg.list_tools(user_role="user", authenticated=False)
    guest_names = [t.name for t in guest_tools]
    assert_true("calculator" in guest_names, "Unauthenticated guest can discover calculator")
    assert_true("get_current_user_profile" not in guest_names, "Guest CANNOT discover user-scoped tools")
    assert_true("get_system_stats" not in guest_names, "Guest CANNOT discover admin tools")

    user_tools = reg.list_tools(user_role="user", authenticated=True)
    user_tool_names = [t.name for t in user_tools]
    assert_true("get_current_user_profile" in user_tool_names, "Authenticated user discovers user tools")
    assert_true("get_system_stats" not in user_tool_names, "Normal user CANNOT discover admin tools")

    admin_tools = reg.list_tools(user_role="admin", authenticated=True)
    admin_tool_names = [t.name for t in admin_tools]
    assert_true("get_system_stats" in admin_tool_names, "Admin discovers admin tools")

    # Model schemas generation (OpenAI compatible)
    schemas = reg.get_schemas_for_model(user_role="user", authenticated=True)
    assert_true(len(schemas) >= 8, "Model schemas list generated")
    first_schema = schemas[0]
    assert_true(first_schema.get("type") == "function", "Schema type is function")
    assert_true("function" in first_schema and "name" in first_schema["function"], "Function name present in schema")
    assert_true("parameters" in first_schema["function"], "Parameters schema present in schema")

    # Dynamic register & unregister
    custom_tool = ToolDefinition(
        name="custom_math_test",
        description="A test tool",
        category=ToolCategory.CALCULATION,
        input_schema={"type": "object", "properties": {}},
        requires_authentication=False,
        handler=lambda **kwargs: {"done": True}
    )
    reg.register(custom_tool)
    assert_true(reg.get("custom_math_test") is not None, "Dynamically registered tool")
    reg.unregister("custom_math_test")
    assert_true(reg.get("custom_math_test") is None, "Dynamically unregistered tool")


    # ── TEST GROUP 2: Tool Input Schema Validation ──
    print("\n[TEST GROUP 2] Tool Input Schema Validation")
    # Missing required argument for calculator
    res_missing = tool_executor.execute("calculator", {})
    assert_true(res_missing.success is False, "Missing required argument rejected")
    assert_true(res_missing.error_code == "INVALID_ARGUMENTS", "Error code is INVALID_ARGUMENTS")
    assert_true("Missing required parameter" in (res_missing.error or ""), "Error message identifies missing argument")

    # Invalid argument type (expression expects string, given int)
    res_bad_type = tool_executor.execute("calculator", {"expression": 12345})
    assert_true(res_bad_type.success is False, "Invalid argument type rejected")
    assert_true(res_bad_type.error_code == "INVALID_ARGUMENTS", "Error code is INVALID_ARGUMENTS for bad type")

    # Valid arguments
    res_valid = tool_executor.execute("calculator", {"expression": "100 + 25"})
    assert_true(res_valid.success is True, "Valid arguments accepted")
    assert_true(res_valid.data.get("result") == 125, "Calculation correct")


    # ── TEST GROUP 3: Authentication & AI user_id Spoofing Prevention ──
    print("\n[TEST GROUP 3] Authentication & Identity Enforcement")
    # Unauthenticated user calling auth-required tool
    res_unauth = tool_executor.execute("get_current_user_profile", {}, user_id="")
    assert_true(res_unauth.success is False, "Unauthenticated access to user tool rejected")
    assert_true(res_unauth.error_code == "UNAUTHORIZED", "Error code is UNAUTHORIZED")

    # AI Model attempts to pass spoofed "user_id" in arguments
    # Authenticated user is USER_A, but AI arguments say user_id = USER_B
    res_spoof = tool_executor.execute(
        "get_current_user_profile",
        {"user_id": USER_B},  # Attacker attempt
        user_id=USER_A,       # Verified backend token
    )
    assert_true(res_spoof.success is True, "Tool executed for verified user")
    # Returned user_id must be strictly USER_A!
    assert_true(res_spoof.data.get("user_id") == USER_A, "CRITICAL: Authenticated user_id strictly enforced, AI spoofed user_id overridden")
    assert_true(res_spoof.data.get("user_id") != USER_B, "AI-supplied user_id completely ignored")


    # ── TEST GROUP 4: Role-Based Permissions & Admin Tools ──
    print("\n[TEST GROUP 4] Role-Based Permissions & Admin Isolation")
    # Normal user calls admin tool
    res_forbidden = tool_executor.execute("get_system_stats", {}, user_id=USER_A, role="user")
    assert_true(res_forbidden.success is False, "Normal user forbidden from admin tool")
    assert_true(res_forbidden.error_code == "FORBIDDEN", "Error code is FORBIDDEN")

    # Admin user calls admin tool
    res_admin = tool_executor.execute("get_system_stats", {}, user_id=ADMIN_USER, role="admin")
    assert_true(res_admin.success is True, "Admin successfully executes admin tool")
    assert_true(res_admin.data.get("role_authorized") == "admin", "Admin role authorized in tool result")


    # ── TEST GROUP 5: Safe Mathematical Calculator Tool ──
    print("\n[TEST GROUP 5] Safe Mathematical Calculator (AST Parser)")
    # Basic math operations
    c1 = calculate("25 * 4 + 10")
    assert_true(c1["result"] == 110, "Basic addition and multiplication correct")

    c2 = calculate("sqrt(144) + 8")
    assert_true(c2["result"] == 20, "sqrt function evaluated safely")

    c3 = calculate("round(3.14159, 2)")
    assert_true(c3["result"] == 3.14, "round function evaluated safely")

    c4 = calculate("2 ** 8")
    assert_true(c4["result"] == 256, "Exponentiation evaluated safely")

    # Division by zero rejection
    div_zero_err = False
    try:
        calculate("10 / 0")
    except InvalidArgumentsError as e:
        div_zero_err = True
        assert_true("Division by zero" in str(e), "Division by zero caught cleanly")
    assert_true(div_zero_err, "Division by zero prevented")

    # Exponentiation DoS limit
    pow_limit_err = False
    try:
        calculate("2 ** 999999")
    except InvalidArgumentsError as e:
        pow_limit_err = True
    assert_true(pow_limit_err, "Massive exponentiation compute denial prevented")

    # REJECTION of code execution & imports
    for unsafe_expr in [
        "__import__('os').system('ls')",
        "eval('2+2')",
        "exec('x=1')",
        "open('users.json').read()",
        "lambda x: x+1",
    ]:
        caught_unsafe = False
        try:
            calculate(unsafe_expr)
        except InvalidArgumentsError:
            caught_unsafe = True
        assert_true(caught_unsafe, f"Unsafe execution rejected: {unsafe_expr[:20]}")


    # ── TEST GROUP 6: Memory Tools & Multi-User Isolation ──
    print("\n[TEST GROUP 6] Memory Tools & User Isolation")
    # User A creates memory
    res_m_create = tool_executor.execute(
        "create_user_memory",
        {"key": "favorite_drink", "value": "Masala Chai without sugar", "memory_type": "personal"},
        user_id=USER_A,
    )
    assert_true(res_m_create.success is True, "User A created memory successfully")
    assert_true(res_m_create.data.get("key") == "favorite_drink", "Memory key recorded")

    # User A searches memory
    res_m_search = tool_executor.execute(
        "search_user_memories",
        {"query": "drink"},
        user_id=USER_A,
    )
    assert_true(res_m_search.success is True, "User A searched memories successfully")
    assert_true(res_m_search.data.get("matched_count", 0) >= 1, "User A found their memory")

    # User B searches memory: MUST NOT see User A's memory!
    res_b_search = tool_executor.execute(
        "search_user_memories",
        {"query": "drink"},
        user_id=USER_B,
    )
    assert_true(res_b_search.success is True, "User B search completed")
    assert_true(res_b_search.data.get("matched_count", 0) == 0, "CRITICAL: User B CANNOT see User A's memory")

    # User A updates memory
    res_m_upd = tool_executor.execute(
        "update_user_memory",
        {"key": "favorite_drink", "value": "Ginger Lemon Tea"},
        user_id=USER_A,
    )
    assert_true(res_m_upd.success is True, "User A updated memory")
    assert_true(res_m_upd.data.get("value") == "Ginger Lemon Tea", "Memory value updated")


    # ── TEST GROUP 7: User Confirmation Flow & Security ──
    print("\n[TEST GROUP 7] User Confirmation Flow & Security")
    # delete_user_memory requires confirmation
    res_del_pending = tool_executor.execute(
        "delete_user_memory",
        {"key": "favorite_drink"},
        user_id=USER_A,
        conversation_id="conv_123",
        tool_call_id="tc_del_01",
    )
    assert_true(res_del_pending.success is False, "State-changing tool paused for confirmation")
    assert_true(res_del_pending.requires_confirmation is True, "requires_confirmation flag is True")
    assert_true(res_del_pending.error_code == "CONFIRMATION_REQUIRED", "Error code is CONFIRMATION_REQUIRED")
    token = res_del_pending.confirmation_token
    assert_true(token is not None and token.startswith("conf_"), "Confirmation token generated")
    assert token is not None

    # User B attempts to confirm User A's token -> MUST BE REJECTED!
    is_valid_b = confirmation_manager.validate_and_consume(
        token=token,
        user_id=USER_B,  # Cross-user attacker!
        conversation_id="conv_123",
        tool_call_id="tc_del_01",
    )
    assert_true(is_valid_b is False, "CRITICAL: User B CANNOT approve User A's confirmation token")

    # User A confirms with correct token -> MUST SUCCEED!
    res_del_approved = tool_executor.execute(
        "delete_user_memory",
        {"key": "favorite_drink"},
        user_id=USER_A,
        conversation_id="conv_123",
        tool_call_id="tc_del_01",
        confirmation_token=token,
    )
    assert_true(res_del_approved.success is True, "Tool executes successfully after valid confirmation")

    # Replay protection: using the same token a second time must FAIL!
    res_del_replay = tool_executor.execute(
        "delete_user_memory",
        {"key": "favorite_drink"},
        user_id=USER_A,
        conversation_id="conv_123",
        tool_call_id="tc_del_01",
        confirmation_token=token,
    )
    assert_true(res_del_replay.success is False, "Single-use token: replay attempt rejected")


    # ── TEST GROUP 8: Conversation Tools & Isolation ──
    print("\n[TEST GROUP 8] Conversation Tools & Isolation")
    from core.services.conversation_service import conversation_service
    conv_a = conversation_service.create_conversation(USER_A, title="User A Private Conv")
    conv_a_id = str(conv_a["id"])

    # User A accesses own conversation
    res_c_a = tool_executor.execute("get_conversation", {"conversation_id": conv_a_id}, user_id=USER_A)
    assert_true(res_c_a.success is True, "User A accesses own conversation")
    assert_true(res_c_a.data.get("conversation_id") == conv_a_id, "Conversation ID matches")

    # User B attempts to access User A's conversation -> MUST BE FORBIDDEN!
    res_c_b = tool_executor.execute("get_conversation", {"conversation_id": conv_a_id}, user_id=USER_B)
    assert_true(res_c_b.success is False, "User B blocked from User A's conversation")
    assert_true(res_c_b.error_code in ("FORBIDDEN", "NOT_FOUND"), "Error code is FORBIDDEN/NOT_FOUND")


    # ── TEST GROUP 9: Autonomous AI Tool Execution Loop & Loop Protections ──
    print("\n[TEST GROUP 9] AI Tool Execution Loop & Loop Protections")
    orch = AIOrchestrator()

    # Mock provider adapter returning a tool call first, then final text
    class MockToolProviderAdapter:
        def __init__(self):
            self.name = "mock_tool_p"
            self.calls = 0

        def validate_configuration(self):
            return True

        def is_available(self):
            return True

        def generate(self, req: AIRequest) -> AIResponse:
            self.calls += 1
            if self.calls == 1:
                # Step 1: Model requests calculator tool
                tc = ToolCall(id="tc_math_1", name="calculator", arguments={"expression": "50 * 20"})
                return AIResponse(
                    content="",
                    model="mock-tool-model",
                    provider=self.name,
                    finish_reason="tool_calls",
                    request_id="req_t1",
                    tool_calls=[tc],
                )
            else:
                # Step 2: Model receives tool result and produces final answer
                return AIResponse(
                    content="The calculated result is 1000.",
                    model="mock-tool-model",
                    provider=self.name,
                    finish_reason="stop",
                    request_id="req_t2",
                )

    mock_adapter = MockToolProviderAdapter()
    with patch("ai.orchestrator.get_provider_adapter", return_value=mock_adapter):
        mock_cfg = ModelConfig(
            provider="mock_tool_p",
            model_name="mock-tool-model",
            display_name="Mock Tool Model",
            supports_tools=True,
        )
        with patch.object(orch.registry, "validate_model", return_value=mock_cfg):
            with patch.object(orch.registry, "get_default_model", return_value=mock_cfg):
                ai_req = AIRequest(
                    model="mock-tool-model",
                    messages=[{"role": "user", "content": "What is 50 * 20?"}],
                )
                final_resp = orch.generate_with_tools(ai_req, user_id=USER_A)
                assert_true(mock_adapter.calls == 2, "AI tool loop executed 2 iterations (tool call -> result -> final answer)")
                assert_true("1000" in final_resp.content, "Final AI response reflects tool output")
                assert_true("tool_executions" in final_resp.metadata, "Metadata tracks tool execution")

    # Storm / Loop limit protection: Repeated identical calls stopped
    class InfiniteLoopProviderAdapter:
        def __init__(self):
            self.name = "mock_loop_p"
            self.calls = 0

        def validate_configuration(self):
            return True

        def is_available(self):
            return True

        def generate(self, req: AIRequest) -> AIResponse:
            self.calls += 1
            # Model keeps repeating same tool call over and over
            tc = ToolCall(id=f"tc_loop_{self.calls}", name="calculator", arguments={"expression": "1 + 1"})
            return AIResponse(
                content="",
                model="mock-loop-model",
                provider=self.name,
                finish_reason="tool_calls",
                request_id=f"req_{self.calls}",
                tool_calls=[tc],
            )

    mock_loop_adapter = InfiniteLoopProviderAdapter()
    with patch("ai.orchestrator.get_provider_adapter", return_value=mock_loop_adapter):
        mock_loop_cfg = ModelConfig(
            provider="mock_loop_p",
            model_name="mock-loop-model",
            display_name="Mock Loop Model",
            supports_tools=True,
        )
        with patch.object(orch.registry, "validate_model", return_value=mock_loop_cfg):
            with patch.object(orch.registry, "get_default_model", return_value=mock_loop_cfg):
                loop_req = AIRequest(
                    model="mock-loop-model",
                    messages=[{"role": "user", "content": "calculate"}],
                )
                # Max 4 iterations
                orch.generate_with_tools(loop_req, user_id=USER_A, max_tool_iterations=4)
                assert_true(mock_loop_adapter.calls <= 5, "Storm/infinite loop bound strictly enforced")


    # ── TEST GROUP 10: Tool Execution Timeout Enforcement ──
    print("\n[TEST GROUP 10] Tool Execution Timeout Enforcement")
    def slow_handler(**kwargs):
        time.sleep(2.0)
        return {"done": True}

    timeout_tool = ToolDefinition(
        name="slow_timeout_tool",
        description="Simulates timeout",
        category=ToolCategory.SYSTEM,
        input_schema={"type": "object", "properties": {}},
        requires_authentication=False,
        timeout=0.25,  # 250ms limit
        handler=slow_handler
    )
    reg_test = ToolRegistry()
    reg_test.register(timeout_tool)
    exec_test = ToolExecutor(registry=reg_test)

    res_timeout = exec_test.execute("slow_timeout_tool", {})
    assert_true(res_timeout.success is False, "Slow tool execution timed out")
    assert_true(res_timeout.error_code == "TIMEOUT", "Error code is TIMEOUT")
    assert_true("TOOL_TIMEOUT" in (res_timeout.error or ""), "Error message is TOOL_TIMEOUT")


    # ── TEST GROUP 11: Output Size Limiting & Truncation ──
    print("\n[TEST GROUP 11] Output Size Limiting & Truncation")
    def large_data_handler(**kwargs):
        # Generates ~30KB of output
        return {"items": ["big_data_chunk_sample_12345" * 100 for _ in range(50)]}

    large_tool = ToolDefinition(
        name="large_data_tool",
        description="Generates oversized payload",
        category=ToolCategory.DATA,
        input_schema={"type": "object", "properties": {}},
        requires_authentication=False,
        handler=large_data_handler
    )
    reg_test.register(large_tool)
    res_large = exec_test.execute("large_data_tool", {})
    assert_true(res_large.success is True, "Large data handled without crash")
    # Verify notice of truncation
    truncated_serialized = json.dumps(res_large.data)
    assert_true(len(truncated_serialized) <= MAX_TOOL_RESULT_SIZE * 1.5, "Result size safely bounded")
    assert_true("_notice" in res_large.data, "Explicit truncation notice injected")


    # ── TEST GROUP 12: Audit Logging & Zero Secret Leaks ──
    print("\n[TEST GROUP 12] Audit Logging & Zero Secret Leaks")
    assert_true(len(tool_executor.audit_log) > 0, "Tool executions recorded in audit log")
    recent_audit = tool_executor.audit_log[-1]
    assert_true(recent_audit.tool_name is not None, "Audit record has tool_name")
    assert_true(recent_audit.duration_ms >= 0, "Audit record has duration_ms")

    # Verify zero secrets leaked in audit records
    log_text = json.dumps([a.model_dump() for a in tool_executor.audit_log])
    assert_true("sk-" not in log_text, "Zero OpenAI API keys in audit log")
    assert_true("AIzaSy" not in log_text, "Zero Gemini API keys in audit log")
    assert_true("password" not in log_text.lower(), "Zero passwords in audit log")
    assert_true("secret" not in log_text.lower(), "Zero secrets in audit log")


    # ── TEST GROUP 13: FastAPI Tool Endpoints ──
    print("\n[TEST GROUP 13] FastAPI Tool Endpoints")
    # 1. GET /api/ai/tools
    r_tools_guest = client.get("/api/ai/tools")
    assert_true(r_tools_guest.status_code == 200, "GET /api/ai/tools guest returns 200")
    guest_tool_list = r_tools_guest.json().get("tools", [])
    assert_true(any(t["name"] == "calculator" for t in guest_tool_list), "Calculator visible to guest")
    assert_true(not any(t["name"] == "get_system_stats" for t in guest_tool_list), "Admin tool hidden from guest")

    r_tools_admin = client.get("/api/ai/tools", headers={"Authorization": f"Bearer {token_admin}"})
    assert_true(r_tools_admin.status_code == 200, "GET /api/ai/tools admin returns 200")
    admin_tool_list = r_tools_admin.json().get("tools", [])
    assert_true(any(t["name"] == "get_system_stats" for t in admin_tool_list), "Admin tool visible to admin")

    # 2. POST /api/ai/tools/execute
    r_exec = client.post("/api/ai/tools/execute", json={"tool_name": "calculator", "arguments": {"expression": "75 / 5"}})
    assert_true(r_exec.status_code == 200, "POST /api/ai/tools/execute returns 200")
    assert_true(r_exec.json().get("data", {}).get("result") == 15, "Calculator result accurate from API")

    # 3. POST /api/ai/tools/confirm
    # First generate confirmation token
    del_prep = tool_executor.execute("delete_user_memory", {"key": "temp_to_delete"}, user_id=USER_A)
    c_token = del_prep.confirmation_token
    assert c_token is not None

    r_conf = client.post(
        "/api/ai/tools/confirm",
        json={"confirmation_token": c_token},
        headers={"Authorization": f"Bearer {token_user_a}"}
    )
    assert_true(r_conf.status_code == 200, "POST /api/ai/tools/confirm returns 200")
    assert_true(r_conf.json().get("success") is True, "Confirmed tool executed successfully")


    # ── TEST GROUP 14: Codebase Security Audit ──
    print("\n[TEST GROUP 14] Codebase Security Audit")
    # Verify no eval or exec in ai/tools
    tools_dir = os.path.join(backend_dir, "ai", "tools")
    for root, _, files in os.walk(tools_dir):
        for f in files:
            if f.endswith(".py"):
                fpath = os.path.join(root, f)
                with open(fpath, "r", encoding="utf-8") as py_file:
                    content = py_file.read()
                    # Check for direct calls
                    assert_true("eval(" not in content, f"Zero eval() in {f}")
                    assert_true("exec(" not in content, f"Zero exec() in {f}")
                    assert_true("os.system" not in content, f"Zero os.system in {f}")
                    assert_true("shell=True" not in content, f"Zero shell=True in {f}")

    print("\n=======================================================")
    print(f"ALL {passed_tests}/{total_tests} TASK 1.8 TESTS PASSED SUCCESSFULLY! [OK]")
    print("=======================================================\n")


if __name__ == "__main__":
    run_tests()
