#!/usr/bin/env python3
"""
Comprehensive Verification Test Suite for Task 1.3:
Persistent User Data & Conversation API Layer.

Verifies:
1. Authentication & Token Verification (MongoDB token signed with mga.)
2. Profile API (GET, PATCH, role tampering prevention)
3. Preferences API (GET, PATCH, safe defaults, upsert)
4. Conversation API (POST, GET, PATCH, DELETE, pagination, search, status)
5. User Isolation for Conversations (User B cannot access User A's conversation)
6. Message API (POST, GET, pagination, conversation ownership enforcement)
7. User Isolation for Messages (User B cannot read/insert into User A's conversation)
8. Memory API (POST, GET, PATCH, DELETE, user-partitioned keys)
9. Memory Isolation (Same key for User A and User B without collision, User A cannot see User B)
10. File Metadata API (POST, GET, PATCH, DELETE, soft-delete, user isolation)
11. Security (401 on missing/invalid token, 403 on admin escalation)
12. Chat Persistence (POST /chat stores messages in persistent conversation)
"""

import os
import sys
import time
import json
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from web.app import app
from core.mongodb_client import generate_token, hash_password
from core.auth import get_or_create_profile
from core.services import (
    profile_service,
    preferences_service,
    conversation_service,
    message_service,
    memory_service,
    user_file_service,
)

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
    print("TASK 1.3: PERSISTENT USER DATA & CONVERSATION API TESTS")
    print("=======================================================\n")

    # Generate test users and signed MongoDB authentication tokens
    user_a_id = "11111111-1111-1111-1111-111111111111"
    user_a = {
        "id": user_a_id,
        "email": "alice_test@example.com",
        "name": "Alice Wonderland",
        "nickname": "Alice",
        "role": "user",
        "is_active": True,
    }
    token_a = generate_token(user_a)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    user_b_id = "22222222-2222-2222-2222-222222222222"
    user_b = {
        "id": user_b_id,
        "email": "bob_test@example.com",
        "name": "Bob Builder",
        "nickname": "Bob",
        "role": "user",
        "is_active": True,
    }
    token_b = generate_token(user_b)
    headers_b = {"Authorization": f"Bearer {token_b}"}

    admin_user = {
        "id": "00000000-0000-0000-0000-000000000001",
        "email": "loharavee@gmail.com",
        "name": "naveen panchal",
        "nickname": "Avee",
        "role": "admin",
        "is_active": True,
    }
    token_admin = generate_token(admin_user)
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    # ── 1. AUTHENTICATION & SECURITY ─────────────────────────────
    print("[TEST GROUP 1] Authentication & Token Verification")
    res_no_auth = client.get("/api/profile")
    assert_true(res_no_auth.status_code == 401, "Unauthenticated request receives 401 Unauthorized")

    res_bad_token = client.get("/api/profile", headers={"Authorization": "Bearer invalid.token.payload"})
    assert_true(res_bad_token.status_code == 401, "Invalid token receives 401 Unauthorized")

    res_auth_me_a = client.get("/api/auth/me", headers=headers_a)
    assert_true(res_auth_me_a.status_code == 200, "User A auth/me succeeds")
    me_a_data = res_auth_me_a.json()
    assert_true(me_a_data["user"]["user_id"] == user_a_id, "User A user_id derived from verified MongoDB token")
    assert_true(me_a_data["user"]["role"] == "user", "User A role is 'user'")

    # Admin access check
    res_admin_items = client.get("/api/admin/training", headers=headers_admin)
    assert_true(res_admin_items.status_code == 200, "Admin can access admin training endpoint")

    res_user_forbidden = client.get("/api/admin/training", headers=headers_a)
    assert_true(res_user_forbidden.status_code == 403, "Normal user forbidden from admin endpoints (403)")

    # ── 2. PROFILE API ───────────────────────────────────────────
    print("\n[TEST GROUP 2] Profile API (GET & PATCH)")
    res_prof_a = client.get("/api/profile", headers=headers_a)
    assert_true(res_prof_a.status_code == 200, "User A fetches profile")
    prof_a = res_prof_a.json()["data"]
    assert_true(prof_a["user_id"] == user_a_id, "Profile user_id matches User A")

    # Update profile fields
    res_update_prof = client.patch(
        "/api/profile",
        headers=headers_a,
        json={"full_name": "Alice In Wonderland", "bio": "Curiouser and curiouser!", "role": "admin"}
    )
    assert_true(res_update_prof.status_code == 200, "User A patches profile")
    updated_prof = res_update_prof.json()["data"]
    assert_true(updated_prof["full_name"] == "Alice In Wonderland", "Profile full_name updated")
    assert_true(updated_prof["bio"] == "Curiouser and curiouser!", "Profile bio updated")
    assert_true(updated_prof["role"] == "user", "CRITICAL: Attempted role escalation to 'admin' was stripped and blocked")

    # ── 3. PREFERENCES API ───────────────────────────────────────
    print("\n[TEST GROUP 3] Preferences API (GET & PATCH)")
    res_prefs_a = client.get("/api/preferences", headers=headers_a)
    assert_true(res_prefs_a.status_code == 200, "User A fetches preferences")
    prefs_a = res_prefs_a.json()["data"]
    assert_true(prefs_a["user_id"] == user_a_id, "Preferences user_id matches User A")
    assert_true(prefs_a.get("theme_mode") in ["normal", "expert", "love"], "Default theme_mode initialized")

    res_update_prefs = client.patch(
        "/api/preferences",
        headers=headers_a,
        json={"theme_mode": "love", "language": "en", "user_id": user_b_id}
    )
    assert_true(res_update_prefs.status_code == 200, "User A updates preferences")
    updated_prefs_a = res_update_prefs.json()["data"]
    assert_true(updated_prefs_a["theme_mode"] == "love", "User A theme_mode updated to 'love'")
    assert_true(updated_prefs_a["user_id"] == user_a_id, "CRITICAL: Injected user_id was ignored; ownership preserved")

    # Verify User B preferences are isolated
    res_prefs_b = client.get("/api/preferences", headers=headers_b)
    prefs_b = res_prefs_b.json()["data"]
    assert_true(prefs_b["user_id"] == user_b_id, "User B preferences owned by User B")
    assert_true(prefs_b["theme_mode"] != "love", "User B preferences completely isolated from User A updates")

    # ── 4. CONVERSATION API ──────────────────────────────────────
    print("\n[TEST GROUP 4] Conversation API & User Isolation")
    # User A creates a conversation
    res_create_conv = client.post(
        "/api/conversations",
        headers=headers_a,
        json={"title": "Project Alpha Planning", "mode": "expert", "user_id": user_b_id}
    )
    assert_true(res_create_conv.status_code == 200, "User A creates conversation")
    conv_a = res_create_conv.json()["data"]
    conv_a_id = conv_a["id"]
    assert_true(conv_a["user_id"] == user_a_id, "Conversation user_id assigned to User A, ignoring injected user_b_id")
    assert_true(conv_a["title"] == "Project Alpha Planning", "Conversation title set")

    # User A lists conversations
    res_list_convs_a = client.get("/api/conversations", headers=headers_a)
    assert_true(res_list_convs_a.status_code == 200, "User A lists conversations")
    list_a = res_list_convs_a.json()["data"]
    assert_true(any(c["id"] == conv_a_id for c in list_a), "Created conversation present in User A's list")

    # User B lists conversations - User A's conversation MUST NOT appear
    res_list_convs_b = client.get("/api/conversations", headers=headers_b)
    assert_true(res_list_convs_b.status_code == 200, "User B lists conversations")
    list_b = res_list_convs_b.json()["data"]
    assert_true(not any(c["id"] == conv_a_id for c in list_b), "User A conversation NOT visible in User B list")

    # User B attempts to fetch User A's conversation by ID -> MUST return 404
    res_b_access_a = client.get(f"/api/conversations/{conv_a_id}", headers=headers_b)
    assert_true(res_b_access_a.status_code == 404, "User B receives 404 when accessing User A conversation (No ID enumeration)")

    # User A updates conversation
    res_update_conv = client.patch(
        f"/api/conversations/{conv_a_id}",
        headers=headers_a,
        json={"title": "Project Alpha Final", "user_id": user_b_id}
    )
    assert_true(res_update_conv.status_code == 200, "User A updates conversation")
    assert_true(res_update_conv.json()["data"]["title"] == "Project Alpha Final", "Conversation title updated")
    assert_true(res_update_conv.json()["data"]["user_id"] == user_a_id, "Conversation ownership immutable")

    # User B attempts to patch User A's conversation -> MUST return 404
    res_b_patch_a = client.patch(
        f"/api/conversations/{conv_a_id}",
        headers=headers_b,
        json={"title": "Hacked Title"}
    )
    assert_true(res_b_patch_a.status_code == 404, "User B receives 404 when attempting to update User A conversation")

    # ── 5. MESSAGE API ───────────────────────────────────────────
    print("\n[TEST GROUP 5] Message API & User Isolation")
    # User A creates a message in User A's conversation
    res_msg_1 = client.post(
        f"/api/conversations/{conv_a_id}/messages",
        headers=headers_a,
        json={"role": "user", "content": "How do we structure our architecture?", "user_id": user_b_id}
    )
    assert_true(res_msg_1.status_code == 200, "User A adds message to conversation")
    msg_1 = res_msg_1.json()["data"]
    assert_true(msg_1["user_id"] == user_a_id, "Message user_id automatically assigned to User A")
    assert_true(msg_1["conversation_id"] == conv_a_id, "Message attached to correct conversation")

    # User A adds assistant response
    res_msg_2 = client.post(
        f"/api/conversations/{conv_a_id}/messages",
        headers=headers_a,
        json={"role": "assistant", "content": "We use a dual database architecture with MongoDB and Supabase."}
    )
    assert_true(res_msg_2.status_code == 200, "User A adds assistant reply to conversation")

    # User A lists messages
    res_msgs_a = client.get(f"/api/conversations/{conv_a_id}/messages", headers=headers_a)
    assert_true(res_msgs_a.status_code == 200, "User A retrieves message history")
    msgs_a = res_msgs_a.json()["data"]
    assert_true(len(msgs_a) >= 2, f"Retrieved {len(msgs_a)} messages in order")
    assert_true(msgs_a[0]["content"] == "How do we structure our architecture?", "Chronological order preserved")

    # User B attempts to read User A's messages -> MUST return 404
    res_b_msgs = client.get(f"/api/conversations/{conv_a_id}/messages", headers=headers_b)
    assert_true(res_b_msgs.status_code == 404 or (res_b_msgs.status_code == 200 and len(res_b_msgs.json()["data"]) == 0),
                "User B cannot read messages of User A's conversation")

    # User B attempts to insert message into User A's conversation -> MUST return 404
    res_b_insert = client.post(
        f"/api/conversations/{conv_a_id}/messages",
        headers=headers_b,
        json={"role": "user", "content": "Malicious injected message!"}
    )
    assert_true(res_b_insert.status_code == 404, "User B cannot insert message into User A's conversation (404)")

    # Message validation: empty content rejected
    res_empty_msg = client.post(
        f"/api/conversations/{conv_a_id}/messages",
        headers=headers_a,
        json={"role": "user", "content": "   "}
    )
    assert_true(res_empty_msg.status_code == 422, "Empty message rejected with 422 Validation Error")

    # Message validation: invalid role rejected
    res_bad_role = client.post(
        f"/api/conversations/{conv_a_id}/messages",
        headers=headers_a,
        json={"role": "superadmin", "content": "Hello"}
    )
    assert_true(res_bad_role.status_code == 422, "Invalid role rejected with 422 Validation Error")

    # ── 6. MEMORY API ────────────────────────────────────────────
    print("\n[TEST GROUP 6] Memory API & Key-Level Partitioning")
    # User A saves memory: favorite_language = Python
    res_mem_a = client.post(
        "/api/memories",
        headers=headers_a,
        json={"memory_key": "favorite_language", "memory_value": "Python", "importance": 2.0}
    )
    assert_true(res_mem_a.status_code == 200, "User A stores memory 'favorite_language'")
    mem_a = res_mem_a.json()["data"]
    assert_true(mem_a["user_id"] == user_a_id, "Memory owned by User A")

    # User B saves memory with SAME KEY: favorite_language = Rust
    res_mem_b = client.post(
        "/api/memories",
        headers=headers_b,
        json={"memory_key": "favorite_language", "memory_value": "Rust", "importance": 1.5}
    )
    assert_true(res_mem_b.status_code == 200, "User B stores memory 'favorite_language'")
    mem_b = res_mem_b.json()["data"]
    assert_true(mem_b["user_id"] == user_b_id, "Memory owned by User B")

    # User A reads 'favorite_language' -> Must be Python, NOT Rust
    res_read_a = client.get("/api/memories/favorite_language", headers=headers_a)
    assert_true(res_read_a.status_code == 200, "User A reads 'favorite_language'")
    assert_true(res_read_a.json()["data"]["memory_value"] == "Python", "User A reads 'Python' (no collision with User B)")

    # User B reads 'favorite_language' -> Must be Rust, NOT Python
    res_read_b = client.get("/api/memories/favorite_language", headers=headers_b)
    assert_true(res_read_b.status_code == 200, "User B reads 'favorite_language'")
    assert_true(res_read_b.json()["data"]["memory_value"] == "Rust", "User B reads 'Rust' (no collision with User A)")

    # User A updates memory
    res_patch_mem = client.patch(
        "/api/memories/favorite_language",
        headers=headers_a,
        json={"memory_value": "Python 3.12"}
    )
    assert_true(res_patch_mem.status_code == 200, "User A updates memory")
    assert_true(res_patch_mem.json()["data"]["memory_value"] == "Python 3.12", "User A updated value persisted")

    # User B value remains unchanged
    res_verify_b = client.get("/api/memories/favorite_language", headers=headers_b)
    assert_true(res_verify_b.json()["data"]["memory_value"] == "Rust", "User B memory unchanged after User A update")

    # User A deletes memory
    res_del_mem = client.delete("/api/memories/favorite_language", headers=headers_a)
    assert_true(res_del_mem.status_code == 200, "User A deletes memory")

    # User B memory still exists
    res_verify_b2 = client.get("/api/memories/favorite_language", headers=headers_b)
    assert_true(res_verify_b2.status_code == 200 and res_verify_b2.json()["data"]["memory_value"] == "Rust",
                "User B memory still exists after User A deletion")

    # ── 7. USER FILE METADATA API ────────────────────────────────
    print("\n[TEST GROUP 7] User File Metadata API & User Isolation")
    res_file_a = client.post(
        "/api/files",
        headers=headers_a,
        json={
            "original_name": "architecture_spec.pdf",
            "storage_key": "docs/architecture_spec_v1.pdf",
            "size_bytes": 204800,
            "mime_type": "application/pdf",
            "user_id": user_b_id,
        }
    )
    assert_true(res_file_a.status_code == 200, "User A records file metadata")
    file_a = res_file_a.json()["data"]
    file_a_id = file_a["id"]
    assert_true(file_a["user_id"] == user_a_id, "File user_id is User A, ignoring injected user_b_id")

    # User A lists files
    res_files_a = client.get("/api/files", headers=headers_a)
    assert_true(res_files_a.status_code == 200, "User A lists files")
    files_a = res_files_a.json()["data"]
    assert_true(any(f["id"] == file_a_id for f in files_a), "Recorded file appears in User A list")

    # User B lists files -> User A file MUST NOT appear
    res_files_b = client.get("/api/files", headers=headers_b)
    assert_true(res_files_b.status_code == 200, "User B lists files")
    files_b = res_files_b.json()["data"]
    assert_true(not any(f["id"] == file_a_id for f in files_b), "User A file NOT visible in User B list")

    # User B attempts to access User A's file -> MUST return 404
    res_b_file = client.get(f"/api/files/{file_a_id}", headers=headers_b)
    assert_true(res_b_file.status_code == 404, "User B receives 404 accessing User A file")

    # User A soft-deletes file
    res_del_file = client.delete(f"/api/files/{file_a_id}", headers=headers_a)
    assert_true(res_del_file.status_code == 200, "User A deletes file metadata")

    # File no longer appears in active list
    res_files_a_after = client.get("/api/files", headers=headers_a)
    assert_true(not any(f["id"] == file_a_id for f in res_files_a_after.json()["data"]), "Deleted file excluded from listing")

    # ── 8. PERSISTENT CHAT INTEGRATION ───────────────────────────
    print("\n[TEST GROUP 8] Persistent Chat Integration (POST /chat)")
    # Create a conversation for chat
    res_chat_conv = client.post(
        "/api/conversations",
        headers=headers_a,
        json={"title": "Interactive Chat Session", "mode": "normal"}
    )
    chat_conv_id = res_chat_conv.json()["data"]["id"]

    # Send message via /chat with conversation_id
    res_chat = client.post(
        "/chat",
        headers=headers_a,
        json={
            "message": "Hello Sarala! Please tell me what time it is.",
            "conversation_id": chat_conv_id,
            "theme_mode": "normal",
        }
    )
    assert_true(res_chat.status_code == 200, "Chat request succeeds")
    chat_resp = res_chat.json()
    assert_true(bool(chat_resp.get("response")), "Chat returns response text")
    assert_true(chat_resp.get("conversation_id") == chat_conv_id, "Chat echoes conversation_id")

    # Verify that the message history was persisted to conversation messages
    res_chat_msgs = client.get(f"/api/conversations/{chat_conv_id}/messages", headers=headers_a)
    assert_true(res_chat_msgs.status_code == 200, "Fetch conversation messages")
    saved_msgs = res_chat_msgs.json()["data"]
    assert_true(len(saved_msgs) >= 2, f"Persisted {len(saved_msgs)} messages (user + assistant turn)")
    assert_true(saved_msgs[0]["role"] == "user", "First saved message has role 'user'")
    assert_true(saved_msgs[1]["role"] == "assistant", "Second saved message has role 'assistant'")

    # User A deletes conversation
    res_del_conv = client.delete(f"/api/conversations/{chat_conv_id}", headers=headers_a)
    assert_true(res_del_conv.status_code == 200, "User A deletes chat conversation")

    print("\n=======================================================")
    print(f"ALL {passed_tests}/{total_tests} TESTS PASSED SUCCESSFULLY! [OK]")
    print("=======================================================\n")
    return True

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
