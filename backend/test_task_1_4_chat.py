#!/usr/bin/env python3
"""
Comprehensive Integration Test Suite for Task 1.4:
Persistent Chat Engine Integration.

Verifies:
1. Conversation Creation & Auto-Title Generation
2. User & Assistant Message Persistence
3. Message Ordering & Pagination
4. Continuing an Existing Conversation with Context Window
5. Title Protection (Auto-update for default title, immutable for user-renamed title)
6. Idempotency & Duplicate Message Protection (client_message_id)
7. Controlled Error Handling on AI Failure (user message safely preserved)
8. User Isolation & Authorization (User A vs User B)
9. Session Restoration Simulation (reloading across logout/login)
10. Safe Conversation Renaming and Deletion
"""

import os
import sys
import time
import json
from unittest.mock import patch
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from web.app import app
from core.mongodb_client import generate_token, mongodb_manager
from core.services import conversation_service, message_service

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
    print("TASK 1.4: PERSISTENT CHAT ENGINE INTEGRATION TESTS")
    print("=======================================================\n")

    # Setup 2 distinct mock users with signed MongoDB tokens
    user_a_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    user_b_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    user_a = {
        "id": user_a_id,
        "email": "alice_task14@sarla.ai",
        "name": "Alice",
        "role": "user",
        "is_active": True,
    }
    user_b = {
        "id": user_b_id,
        "email": "bob_task14@sarla.ai",
        "name": "Bob",
        "role": "user",
        "is_active": True,
    }

    mongodb_manager.enable_test_mock([user_a, user_b])

    token_a = generate_token(user_a)
    token_b = generate_token(user_b)

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # ─────────────────────────────────────────────────────────────
    print("[TEST GROUP 1] Conversation Creation & First Message Flow")
    # ─────────────────────────────────────────────────────────────
    # User A sends initial message without conversation_id
    r1 = client.post(
        "/api/chat",
        headers=headers_a,
        json={
            "message": "Explain quantum computing and quantum superposition simply",
            "client_message_id": "client_msg_001",
            "theme_mode": "normal"
        }
    )
    assert_true(r1.status_code == 200, "POST /api/chat alias succeeds with 200")
    d1 = r1.json()
    assert_true(bool(d1.get("response")), "Chat returns AI response text")
    conv_id = d1.get("conversation_id")
    assert_true(bool(conv_id), "Auto-provisioned new conversation_id returned")

    # Verify conversation title was auto-generated from prompt
    conv_obj = conversation_service.get_conversation(user_a_id, conv_id)
    assert_true(conv_obj is not None, "Conversation stored in persistent database")
    assert conv_obj is not None  # Narrows type for IDE type checkers
    assert_true(conv_obj.get("user_id") == user_a_id, "Conversation owned by User A")
    conv_title = conv_obj.get("title") or ""
    assert_true("quantum" in conv_title.lower(), f"Conversation title auto-derived: '{conv_title}'")

    # Verify user message and assistant message persisted
    msgs, total = message_service.list_messages(user_a_id, conv_id)
    assert_true(total == 2, f"Persisted exactly 2 messages in conversation (found {total})")
    assert_true(msgs[0]["role"] == "user", "First message is user role")
    assert_true(msgs[0]["content"] == "Explain quantum computing and quantum superposition simply", "User message content matches")
    assert_true(msgs[0]["metadata"].get("client_message_id") == "client_msg_001", "Client message ID stored in metadata")
    assert_true(msgs[1]["role"] == "assistant", "Second message is assistant role")
    assert_true(msgs[1]["content"] == d1["response"], "Assistant message content matches returned response")

    # ─────────────────────────────────────────────────────────────
    print("\n[TEST GROUP 2] Continuing Existing Conversation & Ordering")
    # ─────────────────────────────────────────────────────────────
    # Send second turn in the same conversation
    r2 = client.post(
        "/chat",
        headers=headers_a,
        json={
            "message": "Can you give me an example with qubits?",
            "conversation_id": conv_id,
            "client_message_id": "client_msg_002",
            "theme_mode": "normal"
        }
    )
    assert_true(r2.status_code == 200, "Second turn succeeds")
    d2 = r2.json()
    assert_true(d2.get("conversation_id") == conv_id, "Response echoes active conversation_id")

    # Retrieve message history via API
    r_msgs = client.get(f"/api/conversations/{conv_id}/messages", headers=headers_a)
    assert_true(r_msgs.status_code == 200, "GET /api/conversations/{id}/messages succeeds")
    history_data = r_msgs.json().get("data", [])
    assert_true(len(history_data) == 4, f"Total 4 messages in history (found {len(history_data)})")

    # Verify deterministic chronological ordering
    roles = [m["role"] for m in history_data]
    assert_true(roles == ["user", "assistant", "user", "assistant"], f"Strict chronological order preserved: {roles}")

    # Verify pagination support
    r_page = client.get(f"/api/conversations/{conv_id}/messages?limit=2&offset=0", headers=headers_a)
    assert_true(r_page.status_code == 200, "Pagination request succeeds")
    p_data = r_page.json()
    assert_true(len(p_data.get("data", [])) == 2, "Pagination limit respected")
    assert_true(p_data.get("pagination", {}).get("total") == 4, "Total count in pagination header is 4")

    # ─────────────────────────────────────────────────────────────
    print("\n[TEST GROUP 3] Conversation Renaming & Title Protection")
    # ─────────────────────────────────────────────────────────────
    # User manually renames the conversation
    custom_title = "Quantum Physics Deep Dive"
    r_rename = client.patch(
        f"/api/conversations/{conv_id}",
        headers=headers_a,
        json={"title": custom_title}
    )
    assert_true(r_rename.status_code == 200, "PATCH /api/conversations/{id} succeeds")
    assert_true(r_rename.json().get("data", {}).get("title") == custom_title, "Title updated to custom name")

    # Send third message in conversation
    r3 = client.post(
        "/chat",
        headers=headers_a,
        json={
            "message": "What about quantum entanglement?",
            "conversation_id": conv_id,
            "client_message_id": "client_msg_003"
        }
    )
    assert_true(r3.status_code == 200, "Third turn succeeds")

    # CRITICAL: Verify that the custom user title was NOT overwritten
    conv_check = conversation_service.get_conversation(user_a_id, conv_id)
    assert_true(conv_check is not None, "Conversation exists for title check")
    assert conv_check is not None  # Narrows type for IDE type checkers
    conv_title = conv_check.get("title")
    assert_true(conv_title == custom_title, f"CRITICAL: User-renamed title was preserved: '{conv_title}'")

    # ─────────────────────────────────────────────────────────────
    print("\n[TEST GROUP 4] Idempotency & Duplicate Protection")
    # ─────────────────────────────────────────────────────────────
    # Re-send the exact same user message with client_msg_003 (simulating network retry)
    dup_msg = message_service.create_message(
        user_id=user_a_id,
        conversation_id=conv_id,
        role="user",
        content="What about quantum entanglement?",
        client_message_id="client_msg_003"
    )
    assert_true(dup_msg is not None, "Message service handles duplicate call gracefully")
    # Check total messages count did not increase
    msgs_after, total_after = message_service.list_messages(user_a_id, conv_id)
    assert_true(total_after == 6, f"Duplicate message suppressed; message count remains 6 (got {total_after})")

    # ─────────────────────────────────────────────────────────────
    print("\n[TEST GROUP 5] AI Failure & Error State Handling")
    # ─────────────────────────────────────────────────────────────
    # Simulate an AI engine exception during generation
    with patch("web.app.brain.process_input", side_effect=RuntimeError("AI Provider Timeout")):
        r_fail = client.post(
            "/chat",
            headers=headers_a,
            json={
                "message": "Explain Shor's algorithm please",
                "conversation_id": conv_id,
                "client_message_id": "client_msg_fail_test"
            }
        )
        assert_true(r_fail.status_code == 200, "Controlled failure response returned (200)")
        fail_json = r_fail.json()
        assert_true(fail_json.get("retryable") is True, "Response indicates retryable state")
        assert_true(fail_json.get("conversation_id") == conv_id, "Conversation ID preserved in error response")

    # CRITICAL: Verify the user message was safely preserved despite AI failure!
    msgs_fail, total_fail = message_service.list_messages(user_a_id, conv_id)
    assert_true(total_fail == 7, f"User message was retained in database despite AI failure (count {total_fail})")
    assert_true(msgs_fail[-1]["content"] == "Explain Shor's algorithm please", "Preserved message content is intact")
    assert_true(msgs_fail[-1]["role"] == "user", "Preserved message role is user")

    # ─────────────────────────────────────────────────────────────
    print("\n[TEST GROUP 6] User Isolation & Security Boundaries")
    # ─────────────────────────────────────────────────────────────
    # User B attempts to access User A's conversation
    r_b_get = client.get(f"/api/conversations/{conv_id}", headers=headers_b)
    assert_true(r_b_get.status_code == 404, "User B gets 404 accessing User A conversation")

    # User B attempts to view User A's conversation messages
    r_b_msgs = client.get(f"/api/conversations/{conv_id}/messages", headers=headers_b)
    assert_true(r_b_msgs.status_code == 200, "User B message query executes")
    assert_true(len(r_b_msgs.json().get("data", [])) == 0, "User B receives empty list, zero messages from User A")

    # User B attempts to post a message into User A's conversation
    r_b_post = client.post(
        f"/api/conversations/{conv_id}/messages",
        headers=headers_b,
        json={"content": "I am an attacker trying to inject a message"}
    )
    assert_true(r_b_post.status_code == 404, "User B blocked from inserting into User A conversation (404)")

    # User B attempts to rename User A's conversation
    r_b_rename = client.patch(
        f"/api/conversations/{conv_id}",
        headers=headers_b,
        json={"title": "Hacked Conversation"}
    )
    assert_true(r_b_rename.status_code == 404, "User B blocked from renaming User A conversation (404)")

    # User B attempts to delete User A's conversation
    r_b_del = client.delete(f"/api/conversations/{conv_id}", headers=headers_b)
    assert_true(r_b_del.status_code == 404, "User B blocked from deleting User A conversation (404)")

    # User B lists conversations: User A's conversation must not appear
    r_b_list = client.get("/api/conversations", headers=headers_b)
    b_convs = r_b_list.json().get("data", [])
    b_ids = [c["id"] for c in b_convs]
    assert_true(conv_id not in b_ids, "User A conversation not present in User B conversation list")

    # ─────────────────────────────────────────────────────────────
    print("\n[TEST GROUP 7] Multi-Session & Logout / Login Simulation")
    # ─────────────────────────────────────────────────────────────
    # User A lists conversations: conv_id must be present
    r_a_list = client.get("/api/conversations", headers=headers_a)
    a_convs = r_a_list.json().get("data", [])
    a_ids = [c["id"] for c in a_convs]
    assert_true(conv_id in a_ids, "User A conversation visible in User A list")

    # Simulate User A logging in from a new session / device with fresh token
    new_token_a = generate_token(user_a)
    new_headers_a = {"Authorization": f"Bearer {new_token_a}"}

    r_a_new_session = client.get(f"/api/conversations/{conv_id}/messages", headers=new_headers_a)
    assert_true(r_a_new_session.status_code == 200, "New session for User A loads conversation history successfully")
    assert_true(len(r_a_new_session.json().get("data", [])) == 7, "All 7 historical messages restored for User A")

    # ─────────────────────────────────────────────────────────────
    print("\n[TEST GROUP 8] Safe Conversation Deletion")
    # ─────────────────────────────────────────────────────────────
    # User A deletes the conversation
    r_del = client.delete(f"/api/conversations/{conv_id}", headers=headers_a)
    assert_true(r_del.status_code == 200, "DELETE /api/conversations/{id} succeeds for owner")

    # Verify conversation is excluded from list
    r_list_after_del = client.get("/api/conversations", headers=headers_a)
    remaining_ids = [c["id"] for c in r_list_after_del.json().get("data", [])]
    assert_true(conv_id not in remaining_ids, "Deleted conversation excluded from list")

    # Getting deleted conversation returns 404
    r_get_deleted = client.get(f"/api/conversations/{conv_id}", headers=headers_a)
    assert_true(r_get_deleted.status_code == 404, "Deleted conversation returns 404")

    print("\n=======================================================")
    print(f"ALL {passed_tests}/{total_tests} TASK 1.4 TESTS PASSED SUCCESSFULLY! [OK]")
    print("=======================================================\n")

if __name__ == "__main__":
    run_tests()
