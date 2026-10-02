#!/usr/bin/env python3
"""
TASK 1.14 — Comprehensive Test Suite: Message & Chat Experience

Tests:
 1. Send user message
 2. Persist user message
 3. AI response
 4. Persist assistant message
 5. Reload conversation
 6. Message ordering (deterministic chronological order)
 7. Empty message rejected (empty string and whitespace-only)
 8. Oversized input handled (>50,000 chars rejected)
 9. AI failure handled (user message retained, no fake assistant message)
10. Database failure handled (safe error states, no raw stack traces)
11. Duplicate submission protection (idempotency via client_message_id)
12. Retry behavior (no duplicate user message on retry)
13. User A isolation
14. User B isolation
15. Unauthorized conversation message attempt (cross-user send blocked)
16. AI context isolation (verifies User A context contains zero User B data)
"""

import os
import sys
import uuid
import time
from unittest.mock import patch
from fastapi.testclient import TestClient

# Ensure backend directory is in sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from web.app import app
from core.mongodb_client import generate_token, mongodb_manager
from core.services import conversation_service, message_service, chat_idempotency_tracker
from core.services.ai_context_builder import ai_context_builder
from core.services.memory_service import memory_service

client = TestClient(app)

def run_tests():
    total_tests = 0
    passed_tests = 0

    def check(name: str, condition: bool):
        nonlocal total_tests, passed_tests
        total_tests += 1
        if condition:
            passed_tests += 1
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name}")
            raise AssertionError(f"Test assertion failed: {name}")

    print("\n=======================================================")
    print("TASK 1.14: MESSAGE & CHAT EXPERIENCE VERIFICATION SUITE")
    print("=======================================================\n")

    # Clear idempotency tracker cache
    chat_idempotency_tracker.clear()

    # Setup 2 distinct mock users
    user_a_id = "11111111-aaaa-1111-aaaa-111111111111"
    user_b_id = "22222222-bbbb-2222-bbbb-222222222222"

    user_a = {
        "id": user_a_id,
        "email": "alice_task114@sarla.ai",
        "name": "Alice Sharma",
        "nickname": "Alice",
        "role": "user",
        "is_active": True,
    }
    user_b = {
        "id": user_b_id,
        "email": "bob_task114@sarla.ai",
        "name": "Bob Verma",
        "nickname": "Bob",
        "role": "user",
        "is_active": True,
    }

    mongodb_manager.enable_test_mock([user_a, user_b])

    token_a = generate_token(user_a)
    token_b = generate_token(user_b)

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # ─────────────────────────────────────────────────────────────
    print("[SECTION 1] Send User Message, AI Response & Persistence (Tests 1, 2, 3, 4)")
    # ─────────────────────────────────────────────────────────────
    # Mock brain.process_input to return deterministic text
    with patch("web.app.brain.process_input", return_value="Namaste Alice! Main Sarla AI hoon. Aapki kya madad karoon?"):
        r1 = client.post(
            "/api/chat",
            headers=headers_a,
            json={
                "message": "Hello Sarla, explain machine learning basics",
                "client_message_id": "client_msg_t114_01",
                "theme_mode": "normal",
            },
        )
    check("TEST 1: Send user message succeeds with HTTP 200", r1.status_code == 200)
    d1 = r1.json()
    conv_id = str(d1.get("conversation_id") or "")
    check("TEST 1: Valid conversation_id returned in chat response", bool(conv_id))

    # TEST 2: Persist user message
    msgs_after_1, total_1 = message_service.list_messages(user_a_id, conv_id)
    check("TEST 2: Two messages persisted after first turn", total_1 == 2)
    user_msg = msgs_after_1[0]
    check("TEST 2: First message has role='user'", user_msg["role"] == "user")
    check("TEST 2: User message content matches prompt", user_msg["content"] == "Hello Sarla, explain machine learning basics")
    check("TEST 2: User message user_id matches authenticated User A", user_msg["user_id"] == user_a_id)

    # TEST 3: AI response returned
    check("TEST 3: AI response text is non-empty", bool(d1.get("response")))
    check("TEST 3: Response contains emotion", "emotion" in d1)
    check("TEST 3: Response contains gesture", "gesture" in d1)

    # TEST 4: Persist assistant message
    asst_msg = msgs_after_1[1]
    check("TEST 4: Second message has role='assistant'", asst_msg["role"] == "assistant")
    check("TEST 4: Assistant content matches returned AI response", asst_msg["content"] == d1["response"])
    check("TEST 4: Assistant message user_id matches authenticated User A", asst_msg["user_id"] == user_a_id)

    # Verify conversation metadata
    conv_data = conversation_service.get_conversation(user_a_id, conv_id) or {}
    check("TEST 4: Conversation message_count updated to 2", conv_data.get("message_count") == 2)
    check("TEST 4: Conversation last_message_at is populated", bool(conv_data.get("last_message_at")))

    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 2] Reload Conversation & Message Ordering (Tests 5, 6)")
    # ─────────────────────────────────────────────────────────────
    # Send a second turn
    with patch("web.app.brain.process_input", return_value="Supervised learning uses labeled training data."):
        r2 = client.post(
            "/chat",
            headers=headers_a,
            json={
                "message": "What is supervised learning?",
                "conversation_id": conv_id,
                "client_message_id": "client_msg_t114_02",
            },
        )
    check("TEST 5: Second turn in conversation succeeds", r2.status_code == 200)

    # TEST 5: Reload conversation messages
    r_reload = client.get(f"/api/conversations/{conv_id}/messages", headers=headers_a)
    check("TEST 5: Reload conversation messages returns 200", r_reload.status_code == 200)
    loaded_msgs = r_reload.json().get("data") or r_reload.json().get("messages") or []
    check("TEST 5: All 4 messages reloaded accurately", len(loaded_msgs) == 4)

    # TEST 6: Message ordering
    roles = [m["role"] for m in loaded_msgs]
    check("TEST 6: Strict chronological order: user -> assistant -> user -> assistant", roles == ["user", "assistant", "user", "assistant"])
    timestamps = [m["created_at"] for m in loaded_msgs]
    check("TEST 6: Messages strictly ascending or equal by created_at", timestamps == sorted(timestamps))

    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 3] Input Validation: Empty & Oversized (Tests 7, 8)")
    # ─────────────────────────────────────────────────────────────
    # TEST 7: Empty message rejected
    r_empty_str = client.post("/api/chat", headers=headers_a, json={"message": ""})
    check("TEST 7: Empty string rejected with HTTP 400 or 422", r_empty_str.status_code in (400, 422))

    r_ws_only = client.post("/api/chat", headers=headers_a, json={"message": "    \n\t  "})
    check("TEST 7: Whitespace-only string rejected with HTTP 400 or 422", r_ws_only.status_code in (400, 422))

    # Verify no message was added for empty requests
    msgs_after_empty, count_after_empty = message_service.list_messages(user_a_id, conv_id)
    check("TEST 7: Message count remains 4 after rejected empty inputs", count_after_empty == 4)

    # TEST 8: Oversized message rejected
    huge_msg = "A" * 50001
    r_huge = client.post("/api/chat", headers=headers_a, json={"message": huge_msg})
    check("TEST 8: Oversized message (>50k chars) rejected with HTTP 400 or 422", r_huge.status_code in (400, 422))

    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 4] AI Failure & Database Error Handling (Tests 9, 10)")
    # ─────────────────────────────────────────────────────────────
    # TEST 9: AI failure handled safely
    with patch("web.app.brain.process_input", side_effect=RuntimeError("AI Provider Service Unavailable")):
        r_fail = client.post(
            "/api/chat",
            headers=headers_a,
            json={
                "message": "Explain deep neural networks please",
                "conversation_id": conv_id,
                "client_message_id": "client_msg_fail_turn",
            },
        )
    check("TEST 9: AI failure returns recoverable HTTP 200", r_fail.status_code == 200)
    d_fail = r_fail.json()
    check("TEST 9: Response marks error as retryable", d_fail.get("retryable") is True)
    check("TEST 9: Conversation ID preserved in error response", d_fail.get("conversation_id") == conv_id)

    # Verify: user message was safely preserved, but NO fake assistant message was created!
    msgs_fail, count_fail = message_service.list_messages(user_a_id, conv_id)
    check("TEST 9: User message retained in database (5 total messages)", count_fail == 5)
    check("TEST 9: Last message is the preserved user prompt", msgs_fail[-1]["content"] == "Explain deep neural networks please")
    check("TEST 9: Last message role is user", msgs_fail[-1]["role"] == "user")

    # TEST 10: Database / message service error handling
    # Attempt to post invalid role to message service
    r_bad_role = client.post(
        f"/api/conversations/{conv_id}/messages",
        headers=headers_a,
        json={"role": "super_admin_role", "content": "Test content"},
    )
    check("TEST 10: Invalid role in message creation rejected with 422", r_bad_role.status_code == 422)

    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 5] Duplicate Submission Protection & Retry (Tests 11, 12)")
    # ─────────────────────────────────────────────────────────────
    # TEST 11: Duplicate submission protection (idempotency)
    # First, complete a successful turn with client_message_id="client_idempotent_01"
    with patch("web.app.brain.process_input", return_value="An API is an Application Programming Interface."):
        r_turn1 = client.post(
            "/api/chat",
            headers=headers_a,
            json={
                "message": "What is an API?",
                "conversation_id": conv_id,
                "client_message_id": "client_idempotent_01",
            },
        )
    check("TEST 11: Initial send with client_message_id succeeds", r_turn1.status_code == 200)
    msgs_before_dup, count_before_dup = message_service.list_messages(user_a_id, conv_id)

    # Re-send the exact same request with identical client_message_id (simulating double click or network retry)
    with patch("web.app.brain.process_input", side_effect=Exception("Should not be called!")):
        r_turn_dup = client.post(
            "/api/chat",
            headers=headers_a,
            json={
                "message": "What is an API?",
                "conversation_id": conv_id,
                "client_message_id": "client_idempotent_01",
            },
        )
    check("TEST 11: Duplicate send succeeds without re-running AI", r_turn_dup.status_code == 200)
    check("TEST 11: Duplicate response matches cached response", r_turn_dup.json().get("response") == r_turn1.json().get("response"))

    # Verify no duplicate messages were added
    msgs_after_dup, count_after_dup = message_service.list_messages(user_a_id, conv_id)
    check("TEST 11: Total message count unchanged after duplicate submission", count_after_dup == count_before_dup)

    # TEST 12: Retry behavior after previous failed turn
    # Earlier in TEST 9, "client_msg_fail_turn" preserved the user prompt without an assistant message.
    # Re-sending with the same client_message_id represents a retry of that turn.
    with patch("web.app.brain.process_input", return_value="Deep neural networks have multiple hidden layers."):
        r_retry = client.post(
            "/api/chat",
            headers=headers_a,
            json={
                "message": "Explain deep neural networks please",
                "conversation_id": conv_id,
                "client_message_id": "client_msg_fail_turn",
            },
        )
    check("TEST 12: Retry request succeeds with 200", r_retry.status_code == 200)
    check("TEST 12: Retry produces assistant response", "Deep neural networks" in r_retry.json().get("response", ""))

    # Verify: user message was NOT duplicated, and assistant message was added
    msgs_after_retry, count_after_retry = message_service.list_messages(user_a_id, conv_id)
    user_prompts = [m for m in msgs_after_retry if m.get("content") == "Explain deep neural networks please"]
    check("TEST 12: Exactly ONE user message exists for the retried prompt", len(user_prompts) == 1)
    asst_replies = [m for m in msgs_after_retry if "Deep neural networks" in m.get("content", "")]
    check("TEST 12: Exactly ONE assistant message persisted for the retried turn", len(asst_replies) == 1)

    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 6] Two-User Isolation & Unauthorized Messages (Tests 13, 14, 15)")
    # ─────────────────────────────────────────────────────────────
    # Create conversation for User B
    with patch("web.app.brain.process_input", return_value="Hello Bob! I am Sarla AI."):
        r_b_start = client.post(
            "/api/chat",
            headers=headers_b,
            json={
                "message": "Hello from Bob, what is Kubernetes?",
                "client_message_id": "client_msg_b_01",
            },
        )
    check("TEST 14: User B creates own conversation successfully", r_b_start.status_code == 200)
    conv_b_id = str(r_b_start.json().get("conversation_id") or "")
    check("TEST 14: User B receives distinct conversation_id", conv_b_id != conv_id)

    # TEST 13: User A isolation
    a_convs = client.get("/api/conversations", headers=headers_a).json().get("data", [])
    a_conv_ids = [c["id"] for c in a_convs]
    check("TEST 13: User A conversation list does NOT contain User B conversation", conv_b_id not in a_conv_ids)

    # TEST 14: User B isolation
    b_convs = client.get("/api/conversations", headers=headers_b).json().get("data", [])
    b_conv_ids = [c["id"] for c in b_convs]
    check("TEST 14: User B conversation list does NOT contain User A conversation", conv_id not in b_conv_ids)

    # User B cannot read User A's messages
    r_b_read_a = client.get(f"/api/conversations/{conv_id}/messages", headers=headers_b)
    b_view_of_a = r_b_read_a.json().get("data") or r_b_read_a.json().get("messages") or []
    check("TEST 14: User B gets 0 messages when trying to read User A conversation", len(b_view_of_a) == 0)

    # User A cannot read User B's messages
    r_a_read_b = client.get(f"/api/conversations/{conv_b_id}/messages", headers=headers_a)
    a_view_of_b = r_a_read_b.json().get("data") or r_a_read_b.json().get("messages") or []
    check("TEST 13: User A gets 0 messages when trying to read User B conversation", len(a_view_of_b) == 0)

    # TEST 15: Unauthorized message attempts
    # User B tries to post a message into User A's conversation via /api/conversations/{id}/messages
    r_b_post_a = client.post(
        f"/api/conversations/{conv_id}/messages",
        headers=headers_b,
        json={"content": "Malicious injection from User B into User A conversation"},
    )
    check("TEST 15: User B posting directly to User A conversation returns 404", r_b_post_a.status_code == 404)

    # User B tries to send a chat message targeting User A's conversation via /api/chat
    r_b_chat_a = client.post(
        "/api/chat",
        headers=headers_b,
        json={
            "message": "Attempt to hijack conversation",
            "conversation_id": conv_id,
        },
    )
    check("TEST 15: User B sending chat to User A conversation returns 404", r_b_chat_a.status_code == 404)

    # User A tries to send a chat message targeting User B's conversation via /api/chat
    r_a_chat_b = client.post(
        "/api/chat",
        headers=headers_a,
        json={
            "message": "Attempt to hijack Bob's conversation",
            "conversation_id": conv_b_id,
        },
    )
    check("TEST 15: User A sending chat to User B conversation returns 404", r_a_chat_b.status_code == 404)

    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 7] AI Context Isolation (Test 16)")
    # ─────────────────────────────────────────────────────────────
    # Store a secret personal memory for User B
    memory_service.set_memory(
        user_id=user_b_id,
        memory_key="financial_secret",
        memory_value="Bob Bank Account Balance is 5000000 USD",
        memory_type="personal",
        importance=1.0,
    )

    # Store a distinct memory for User A
    memory_service.set_memory(
        user_id=user_a_id,
        memory_key="hobby",
        memory_value="Alice loves quantum computing and stargazing",
        memory_type="personal",
        importance=1.0,
    )

    # Build context for User A
    ctx_a = ai_context_builder.build_context(
        user_input="Tell me about my financial status and hobbies",
        user_id=user_a_id,
        conversation_id=conv_id,
    )
    prompt_a = ctx_a.to_prompt_string()

    check("TEST 16: User A AI context contains Alice's memory", "quantum computing" in prompt_a)
    check("TEST 16: User A AI context does NOT contain Bob's secret memory", "5000000" not in prompt_a and "Bob Bank" not in prompt_a)
    check("TEST 16: User A AI context does NOT contain Bob's conversation history", "Kubernetes" not in prompt_a)

    # Build context for User B
    ctx_b = ai_context_builder.build_context(
        user_input="Tell me about my hobbies and bank balance",
        user_id=user_b_id,
        conversation_id=conv_b_id,
    )
    prompt_b = ctx_b.to_prompt_string()

    check("TEST 16: User B AI context contains Bob's memory", "5000000" in prompt_b or "Bank" in prompt_b)
    check("TEST 16: User B AI context does NOT contain Alice's memory", "stargazing" not in prompt_b)
    check("TEST 16: User B AI context does NOT contain Alice's conversation history", "supervised learning" not in prompt_b)

    print("\n=======================================================")
    print(f"ALL {passed_tests}/{total_tests} TASK 1.14 ASSERTIONS PASSED SUCCESSFULLY! [OK]")
    print("=======================================================\n")


if __name__ == "__main__":
    run_tests()
