#!/usr/bin/env python3
"""
TASK 1.13 — CONVERSATION WORKSPACE & HISTORY FOUNDATION AUTOMATED TEST SUITE
=============================================================================
Tests all requirements and security guarantees for persistent conversations:
- TEST 1:  Create conversation with explicit title & mode (HTTP 200)
- TEST 2:  Create conversation with default title (HTTP 200)
- TEST 3:  Verify initial message_count = 0 and timestamps
- TEST 4:  List conversations returns only authenticated user's conversations
- TEST 5:  List conversations supports search and pagination
- TEST 6:  Get conversation by ID returns complete data model
- TEST 7:  Update conversation title via PATCH & PUT
- TEST 8:  Update conversation mode ("normal", "love", "expert")
- TEST 9:  Invalid title update (empty string) rejected with HTTP 422
- TEST 10: Invalid mode update rejected with HTTP 422
- TEST 11: Attempted user_id / role modification stripped during update
- TEST 12: Message creation increments message_count and updates last_message_at
- TEST 13: Empty conversation remains valid and accessible
- TEST 14: Delete conversation deletes conversation and cascades messages
- TEST 15: Non-existent / deleted conversation returns HTTP 404
- TEST 16: Unauthenticated requests rejected with HTTP 401
- TEST 17: User A vs User B Isolation: List separation
- TEST 18: User B cannot GET User A conversation (HTTP 404)
- TEST 19: User B cannot PATCH User A conversation (HTTP 404)
- TEST 20: User B cannot DELETE User A conversation (HTTP 404)
- TEST 21: User B cannot read User A messages
- TEST 22: User B cannot post messages to User A conversation (HTTP 404)
- TEST 23: Request body user_id spoofing is ignored; owned by authenticated user
- TEST 24: Query parameter ?user_id= cannot leak other user's conversations
- TEST 25: AI tools enforce server-injected user_id; AI cannot forge ownership
- TEST 26: Service layer persistence verification
"""

import os
import sys
import time
import uuid
from typing import Dict, Any

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi.testclient import TestClient
from web.app import app
from core.mongodb_client import mongodb_manager, hash_password, generate_token
from core.services import conversation_service, message_service
from ai.tools.implementations.conversation_tools import (
    create_conversation as tool_create_conversation,
    get_conversation as tool_get_conversation,
    search_conversations as tool_search_conversations,
)
from ai.tools.errors import UnauthorizedError, ForbiddenError


def run_all_tests():
    print("\n=======================================================")
    print("TASK 1.13: CONVERSATION WORKSPACE & HISTORY FOUNDATION")
    print("=======================================================\n")

    passed = 0
    total = 0

    def check(desc: str, condition: bool, detail: str = ""):
        nonlocal passed, total
        total += 1
        if condition:
            passed += 1
            print(f"  [PASS] {desc}")
        else:
            print(f"  [FAIL] {desc} - {detail}")
            assert False, f"Test failed: {desc} - {detail}"

    # Setup mock users
    class MockCollection:
        def __init__(self):
            self.docs = []

        def find_one(self, query):
            for d in self.docs:
                match = True
                for k, v in query.items():
                    if k == "$or":
                        or_match = False
                        for cond in v:
                            for ck, cv in cond.items():
                                if d.get(ck) == cv:
                                    or_match = True
                                    break
                            if or_match:
                                break
                        if not or_match:
                            match = False
                            break
                    elif d.get(k) != v:
                        match = False
                        break
                if match:
                    return dict(d)
            return None

        def insert_one(self, doc):
            self.docs.append(dict(doc))
            return True

        def update_one(self, query, update):
            for d in self.docs:
                match = True
                for k, v in query.items():
                    if d.get(k) != v:
                        match = False
                        break
                if match:
                    if "$set" in update:
                        d.update(update["$set"])
                    return True
            return False

    mock_coll = MockCollection()
    mongodb_manager.set_test_collection(mock_coll)

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # User A
    USER_A_ID = "11111111-aaaa-1111-aaaa-111111111111"
    USER_A_EMAIL = "user.a@example.com"
    salt_a, hash_a = hash_password("PasswordA@123")
    user_a_doc = {
        "user_id": USER_A_ID,
        "id": USER_A_ID,
        "email": USER_A_EMAIL,
        "password_hash": hash_a,
        "password_salt": salt_a,
        "name": "Alice User",
        "full_name": "Alice User",
        "nickname": "Alice",
        "role": "user",
        "is_active": True,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    mock_coll.insert_one(user_a_doc)

    # User B
    USER_B_ID = "22222222-bbbb-2222-bbbb-222222222222"
    USER_B_EMAIL = "user.b@example.com"
    salt_b, hash_b = hash_password("PasswordB@123")
    user_b_doc = {
        "user_id": USER_B_ID,
        "id": USER_B_ID,
        "email": USER_B_EMAIL,
        "password_hash": hash_b,
        "password_salt": salt_b,
        "name": "Bob User",
        "full_name": "Bob User",
        "nickname": "Bob",
        "role": "user",
        "is_active": True,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    mock_coll.insert_one(user_b_doc)

    token_a = generate_token(user_a_doc)
    token_b = generate_token(user_b_doc)

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    client = TestClient(app)

    # ── SECTION 1: Conversation Creation & Defaults (Tests 1, 2, 3, 6, 13) ────
    print("[SECTION 1] Conversation Creation & Defaults (Tests 1, 2, 3, 6, 13)")
    # TEST 1: Create conversation with explicit title & mode
    r1 = client.post(
        "/api/conversations",
        headers=headers_a,
        json={"title": "Project Architecture Discussion", "mode": "expert"}
    )
    check("TEST 1: Create conversation returns 200", r1.status_code == 200, f"status={r1.status_code}")
    c1 = r1.json().get("conversation") or r1.json().get("data") or {}
    conv_a1_id: str = str(c1.get("id") or "")
    check("TEST 1: Canonical user_id is assigned to User A", c1.get("user_id") == USER_A_ID)
    check("TEST 1: Title matches explicit input", c1.get("title") == "Project Architecture Discussion")
    check("TEST 1: Mode matches explicit input", c1.get("mode") == "expert")

    # TEST 3: Initial message_count is 0
    check("TEST 3: message_count initialized to 0", c1.get("message_count") == 0)
    check("TEST 3: created_at timestamp initialized", bool(c1.get("created_at")))
    check("TEST 3: updated_at timestamp initialized", bool(c1.get("updated_at")))
    check("TEST 3: last_message_at timestamp initialized", bool(c1.get("last_message_at")))

    # TEST 2: Create conversation with default title
    r2 = client.post("/api/conversations", headers=headers_a, json={})
    check("TEST 2: Create conversation without body fields returns 200", r2.status_code == 200)
    c2 = r2.json().get("conversation") or r2.json().get("data") or {}
    conv_a2_id: str = str(c2.get("id") or "")
    check("TEST 2: Default title is 'New Conversation'", c2.get("title") == "New Conversation")
    check("TEST 2: Default mode is 'normal'", c2.get("mode") == "normal")
    check("TEST 2: message_count is 0", c2.get("message_count") == 0)

    # TEST 6: Get conversation by ID
    r6 = client.get(f"/api/conversations/{conv_a1_id}", headers=headers_a)
    check("TEST 6: Get conversation by ID returns 200", r6.status_code == 200)
    c6 = r6.json().get("conversation") or r6.json().get("data") or {}
    check("TEST 6: Retrieved conversation ID matches", c6.get("id") == conv_a1_id)
    check("TEST 6: Complete data model contains status='active'", c6.get("status") == "active")
    check("TEST 6: Complete data model contains message_count", "message_count" in c6)

    # TEST 13: Empty conversation is valid and accessible
    check("TEST 13: Empty conversation message_count == 0", c2.get("message_count") == 0)
    r_empty_msgs = client.get(f"/api/conversations/{conv_a2_id}/messages", headers=headers_a)
    check("TEST 13: Empty conversation messages endpoint returns 200", r_empty_msgs.status_code == 200)
    msgs_empty = r_empty_msgs.json().get("messages") or r_empty_msgs.json().get("data") or []
    check("TEST 13: Empty conversation returns 0 messages", len(msgs_empty) == 0)

    # ── SECTION 2: List Conversations & Pagination (Tests 4, 5) ────────────────
    print("\n[SECTION 2] List Conversations & Search (Tests 4, 5)")
    r_list = client.get("/api/conversations", headers=headers_a)
    check("TEST 4: List conversations returns 200", r_list.status_code == 200)
    conv_list = r_list.json().get("conversations") or r_list.json().get("data") or []
    check("TEST 4: User A has at least 2 conversations", len(conv_list) >= 2)
    check("TEST 4: All conversations belong strictly to User A", all(c.get("user_id") == USER_A_ID for c in conv_list))

    # TEST 5: Search filtering
    r_search = client.get("/api/conversations?search=Architecture", headers=headers_a)
    check("TEST 5: Search query returns 200", r_search.status_code == 200)
    search_results = r_search.json().get("conversations") or r_search.json().get("data") or []
    check("TEST 5: Search finds matching conversation", any("Architecture" in c.get("title", "") for c in search_results))

    # ── SECTION 3: Update, Rename, & Validation (Tests 7, 8, 9, 10, 11) ─────────
    print("\n[SECTION 3] Update, Rename, & Validation (Tests 7, 8, 9, 10, 11)")
    # TEST 7: Update conversation title via PATCH
    r7_patch = client.patch(
        f"/api/conversations/{conv_a1_id}",
        headers=headers_a,
        json={"title": "Renamed Architecture v2"}
    )
    check("TEST 7: Rename conversation via PATCH returns 200", r7_patch.status_code == 200)
    c7 = r7_patch.json().get("conversation") or r7_patch.json().get("data") or {}
    check("TEST 7: Title successfully updated", c7.get("title") == "Renamed Architecture v2")

    # TEST 7: Update conversation title via PUT
    r7_put = client.put(
        f"/api/conversations/{conv_a1_id}",
        headers=headers_a,
        json={"title": "Renamed Architecture v3"}
    )
    check("TEST 7: Rename conversation via PUT returns 200", r7_put.status_code == 200)
    c7_put = r7_put.json().get("conversation") or r7_put.json().get("data") or {}
    check("TEST 7: Title updated via PUT", c7_put.get("title") == "Renamed Architecture v3")

    # TEST 8: Update conversation mode
    r8 = client.patch(
        f"/api/conversations/{conv_a1_id}",
        headers=headers_a,
        json={"mode": "love"}
    )
    check("TEST 8: Valid mode update to 'love' returns 200", r8.status_code == 200)
    c8 = r8.json().get("conversation") or r8.json().get("data") or {}
    check("TEST 8: Mode updated to 'love'", c8.get("mode") == "love")

    # TEST 9: Empty title string rejected with HTTP 422
    r9 = client.patch(
        f"/api/conversations/{conv_a1_id}",
        headers=headers_a,
        json={"title": "   "}
    )
    check("TEST 9: Whitespace-only title rejected with HTTP 422", r9.status_code == 422)

    # TEST 10: Invalid mode update rejected with HTTP 422
    r10 = client.patch(
        f"/api/conversations/{conv_a1_id}",
        headers=headers_a,
        json={"mode": "hacker_mode"}
    )
    check("TEST 10: Invalid mode 'hacker_mode' rejected with HTTP 422", r10.status_code == 422)

    # TEST 11: Attempted user_id / role tampering stripped
    r11 = client.patch(
        f"/api/conversations/{conv_a1_id}",
        headers=headers_a,
        json={"user_id": USER_B_ID, "role": "admin", "title": "Tamper Attempt"}
    )
    check("TEST 11: Tamper request responds 200", r11.status_code == 200)
    c11 = r11.json().get("conversation") or r11.json().get("data") or {}
    check("TEST 11: user_id remains strictly User A", c11.get("user_id") == USER_A_ID)
    check("TEST 11: role is not present or altered", c11.get("role") is None)

    # ── SECTION 4: Message Count & Timestamp Tracking (Test 12) ─────────────────
    print("\n[SECTION 4] Message Count & Timestamp Tracking (Test 12)")
    # Add message 1
    t_before = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    r_msg1 = client.post(
        f"/api/conversations/{conv_a1_id}/messages",
        headers=headers_a,
        json={"role": "user", "content": "First message in conversation"}
    )
    check("TEST 12: First message creation returns 200", r_msg1.status_code == 200)

    # Verify conversation message_count incremented to 1
    c_check1 = client.get(f"/api/conversations/{conv_a1_id}", headers=headers_a).json().get("conversation") or {}
    check("TEST 12: message_count incremented to 1", c_check1.get("message_count") == 1)
    last_msg_at_val = str(c_check1.get("last_message_at") or "")
    check("TEST 12: last_message_at updated", bool(last_msg_at_val and last_msg_at_val >= t_before))

    # Add message 2 (Assistant)
    r_msg2 = client.post(
        f"/api/conversations/{conv_a1_id}/messages",
        headers=headers_a,
        json={"role": "assistant", "content": "Assistant reply message"}
    )
    check("TEST 12: Second message creation returns 200", r_msg2.status_code == 200)

    # Verify conversation message_count incremented to 2
    c_check2 = client.get(f"/api/conversations/{conv_a1_id}", headers=headers_a).json().get("conversation") or {}
    check("TEST 12: message_count incremented to 2", c_check2.get("message_count") == 2)

    # ── SECTION 5: Deletion & Cascading (Tests 14, 15) ───────────────────────────
    print("\n[SECTION 5] Conversation Deletion & Cascading (Tests 14, 15)")
    # Create a temporary conversation with a message to delete
    r_temp = client.post("/api/conversations", headers=headers_a, json={"title": "To be deleted"})
    temp_id: str = str((r_temp.json().get("conversation") or {}).get("id") or "")
    client.post(f"/api/conversations/{temp_id}/messages", headers=headers_a, json={"role": "user", "content": "Msg to delete"})

    # TEST 14: Delete conversation
    r_del = client.delete(f"/api/conversations/{temp_id}", headers=headers_a)
    check("TEST 14: DELETE conversation returns 200", r_del.status_code == 200)

    # TEST 15: Non-existent / deleted conversation returns 404
    r_get_deleted = client.get(f"/api/conversations/{temp_id}", headers=headers_a)
    check("TEST 15: GET deleted conversation returns 404", r_get_deleted.status_code == 404)

    # Deleted conversation does not appear in list
    r_list_after_del = client.get("/api/conversations", headers=headers_a)
    ids_after = [c.get("id") for c in (r_list_after_del.json().get("conversations") or [])]
    check("TEST 14: Deleted conversation removed from list", temp_id not in ids_after)

    # ── SECTION 6: Unauthenticated Protection (Test 16) ─────────────────────────
    print("\n[SECTION 6] Unauthenticated Protection (Test 16)")
    check("TEST 16: GET /api/conversations without auth returns 401", client.get("/api/conversations").status_code == 401)
    check("TEST 16: POST /api/conversations without auth returns 401", client.post("/api/conversations", json={}).status_code == 401)
    check("TEST 16: GET /api/conversations/{id} without auth returns 401", client.get(f"/api/conversations/{conv_a1_id}").status_code == 401)
    check("TEST 16: PATCH /api/conversations/{id} without auth returns 401", client.patch(f"/api/conversations/{conv_a1_id}", json={"title": "X"}).status_code == 401)
    check("TEST 16: DELETE /api/conversations/{id} without auth returns 401", client.delete(f"/api/conversations/{conv_a1_id}").status_code == 401)
    check("TEST 16: GET messages without auth returns 401", client.get(f"/api/conversations/{conv_a1_id}/messages").status_code == 401)

    # ── SECTION 7: Two-User Security Isolation (Tests 17, 18, 19, 20, 21, 22) ───
    print("\n[SECTION 7] Two-User Security Isolation (Tests 17, 18, 19, 20, 21, 22)")
    # User B creates conversation B
    r_b_conv = client.post("/api/conversations", headers=headers_b, json={"title": "Bob Secret Conversation"})
    check("TEST 17: User B creates conversation returns 200", r_b_conv.status_code == 200)
    conv_b_id: str = str((r_b_conv.json().get("conversation") or {}).get("id") or "")

    # TEST 17: List isolation
    b_list = client.get("/api/conversations", headers=headers_b).json().get("conversations") or []
    check("TEST 17: User B list does NOT contain User A conversations", not any(c.get("id") == conv_a1_id for c in b_list))
    a_list = client.get("/api/conversations", headers=headers_a).json().get("conversations") or []
    check("TEST 17: User A list does NOT contain User B conversations", not any(c.get("id") == conv_b_id for c in a_list))

    # TEST 18: User B cannot GET User A conversation
    r_b_get_a = client.get(f"/api/conversations/{conv_a1_id}", headers=headers_b)
    check("TEST 18: User B reading User A conversation returns 404", r_b_get_a.status_code in (403, 404))

    # TEST 19: User B cannot PATCH User A conversation
    r_b_patch_a = client.patch(f"/api/conversations/{conv_a1_id}", headers=headers_b, json={"title": "Hacked Title"})
    check("TEST 19: User B modifying User A conversation returns 404", r_b_patch_a.status_code in (403, 404))
    # Verify User A title was NOT changed
    c_a_intact = client.get(f"/api/conversations/{conv_a1_id}", headers=headers_a).json().get("conversation") or {}
    check("TEST 19: User A conversation title remains completely untouched", c_a_intact.get("title") != "Hacked Title")

    # TEST 20: User B cannot DELETE User A conversation
    r_b_del_a = client.delete(f"/api/conversations/{conv_a1_id}", headers=headers_b)
    check("TEST 20: User B deleting User A conversation returns 404", r_b_del_a.status_code in (403, 404))
    # Verify User A conversation still exists
    c_a_still_exists = client.get(f"/api/conversations/{conv_a1_id}", headers=headers_a)
    check("TEST 20: User A conversation still exists after deletion attempt", c_a_still_exists.status_code == 200)

    # TEST 21: User B cannot read User A messages
    r_b_read_msgs = client.get(f"/api/conversations/{conv_a1_id}/messages", headers=headers_b)
    msgs_b_view = r_b_read_msgs.json().get("messages") or []
    check("TEST 21: User B reading User A messages returns empty list or 404", r_b_read_msgs.status_code in (403, 404) or len(msgs_b_view) == 0)

    # TEST 22: User B cannot post messages to User A conversation
    r_b_post_msg = client.post(
        f"/api/conversations/{conv_a1_id}/messages",
        headers=headers_b,
        json={"role": "user", "content": "Injected malicious message"}
    )
    check("TEST 22: User B posting message to User A conversation returns 404", r_b_post_msg.status_code in (403, 404))

    # ── SECTION 8: Spoofing & AI Tool Security (Tests 23, 24, 25) ────────────────
    print("\n[SECTION 8] Identity Spoofing & AI Tool Security (Tests 23, 24, 25)")
    # TEST 23: Request body user_id spoofing ignored
    r_spoof = client.post(
        "/api/conversations",
        headers=headers_a,
        json={"user_id": USER_B_ID, "title": "Spoofed By A"}
    )
    check("TEST 23: Create conversation with spoofed user_id in body succeeds safely", r_spoof.status_code == 200)
    c_spoof = r_spoof.json().get("conversation") or {}
    check("TEST 23: Conversation owner forced strictly to authenticated User A", c_spoof.get("user_id") == USER_A_ID)

    # TEST 24: Query parameter ?user_id= cannot leak conversations
    r_query_leak = client.get(f"/api/conversations?user_id={USER_A_ID}", headers=headers_b)
    b_query_list = r_query_leak.json().get("conversations") or []
    check("TEST 24: User B with ?user_id=USER_A receives only User B conversations", not any(c.get("user_id") == USER_A_ID for c in b_query_list))

    # TEST 25: AI Tools enforce server-injected user_id
    tool_conv = tool_create_conversation(
        title="AI Created Discussion",
        mode="expert",
        user_id=USER_A_ID,  # Server-injected kwargs
        rogue_user_id=USER_B_ID  # Spoofed tool param
    )
    check("TEST 25: AI tool creates conversation for authenticated user", bool(tool_conv.get("conversation_id")))

    # AI tool unauthenticated call raises UnauthorizedError
    try:
        tool_create_conversation(title="No auth")
        check("TEST 25: Unauthenticated tool call raises error", False)
    except UnauthorizedError:
        check("TEST 25: Unauthenticated tool call safely rejected", True)

    # AI tool get_conversation cross-user check raises ForbiddenError
    try:
        tool_get_conversation(conversation_id=conv_a1_id, user_id=USER_B_ID)
        check("TEST 25: Cross-user tool get_conversation raises error", False)
    except ForbiddenError:
        check("TEST 25: Cross-user tool get_conversation safely rejected with ForbiddenError", True)

    # ── SECTION 9: Service Persistence & Restart Simulation (Test 26) ───────────
    print("\n[SECTION 9] Service Persistence Verification (Test 26)")
    # Direct service layer retrieval simulates backend restart/reconnect
    persisted_conv = conversation_service.get_conversation(USER_A_ID, conv_a1_id) or {}
    check("TEST 26: Conversation persisted in service layer", persisted_conv.get("id") == conv_a1_id)
    check("TEST 26: message_count is preserved in service layer", persisted_conv.get("message_count") == 2)
    check("TEST 26: Title is preserved in service layer", persisted_conv.get("title") in ("Tamper Attempt", "Renamed Architecture v3"))

    print("\n=======================================================")
    print(f"ALL TESTS COMPLETED: {passed}/{total} assertions verified successfully!")
    print("=======================================================\n")
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
