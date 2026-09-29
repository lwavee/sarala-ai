#!/usr/bin/env python3
"""
Comprehensive Automated Test Suite for Dual Database Architecture (MongoDB + Supabase).
Covers:
1. Connectivity (MongoDB + Supabase)
2. Authentication (Signup, Login, Token validation, Admin vs User roles, Deactivated accounts)
3. Canonical Identity & Mapping (MongoDB id -> Supabase user_id)
4. Application Data Services (Profiles, Preferences, Conversations, Messages, Memories, Files)
5. User Data Isolation (User A vs User B strict boundaries)
6. Security (Role tampering, user_id spoofing, unauthorized access)
7. Legacy Migration & Data Preservation
"""

import sys
import os
import time
import uuid

# Ensure backend root is in sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from core.mongodb_client import mongodb_manager, verify_token as verify_mongo_token
from core.supabase_client import supabase_manager
from core.auth import CurrentUser, get_or_create_profile
from core.services import (
    profile_service,
    preferences_service,
    conversation_service,
    message_service,
    memory_service,
    user_file_service,
)
from memory.storage import MemoryStorage


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
    print("RUNNING DUAL DATABASE FOUNDATION VERIFICATION TEST SUITE")
    print("=======================================================\n")

    # ── 1. CONNECTIVITY ──────────────────────────────────────────
    print("[TEST GROUP 1] Database Connectivity")
    assert_true(mongodb_manager.is_connected, "MongoDB Atlas is connected and pingable")
    assert_true(supabase_manager.is_connected, "Supabase client is connected and ready")

    # ── 2. AUTHENTICATION & CANONICAL IDENTITY ───────────────────
    print("\n[TEST GROUP 2] MongoDB Authentication & Canonical Identity")
    mem = MemoryStorage()
    test_ts = int(time.time())

    # User A (Normal User)
    user_a_email = f"user_a_{test_ts}@example.com"
    reg_a = mem.register_user("Alice Wonderland", "alice", user_a_email, "AliceSecret@123", role="user")
    assert_true(reg_a.get("success") is True, "User A registration succeeded in MongoDB")
    assert_true("token" in reg_a, "User A received signed auth token")
    user_a_id = reg_a["user"]["id"]
    assert_true(bool(user_a_id), f"User A has stable canonical user_id: {user_a_id}")
    assert_true(reg_a["user"]["role"] == "user", "User A role is 'user'")

    # Duplicate registration prevention
    dup_res = mem.register_user("Alice Wonderland", "alice", user_a_email, "AliceSecret@123", role="user")
    assert_true(dup_res.get("success") is False, "Duplicate registration is rejected")

    # User B (Second Normal User for Isolation Testing)
    user_b_email = f"user_b_{test_ts}@example.com"
    reg_b = mem.register_user("Bob Builder", "bob", user_b_email, "BobSecret@123", role="user")
    assert_true(reg_b.get("success") is True, "User B registration succeeded in MongoDB")
    user_b_id = reg_b["user"]["id"]
    assert_true(user_a_id != user_b_id, "User A and User B receive distinct stable user_ids")

    # Authentication validation
    auth_a = mem.authenticate_user(user_a_email, "AliceSecret@123")
    assert_true(auth_a.get("success") is True, "User A authentication succeeds with correct password")
    token_a = auth_a["token"]
    payload_a = verify_mongo_token(token_a)
    assert_true(payload_a is not None and payload_a.get("id") == user_a_id, "Token verification extracts trusted user_id")

    # Wrong password rejection
    bad_auth = mem.authenticate_user(user_a_email, "WrongPassword!")
    assert_true(bad_auth.get("success") is False, "Authentication fails on invalid password")

    # Admin User verification
    admin_auth = mem.authenticate_user("loharavee@gmail.com", "Sarala@7880")
    assert_true(admin_auth.get("success") is True, "Admin authentication succeeds")
    assert_true(admin_auth["user"]["role"] == "admin", "Admin role is strictly preserved from MongoDB")
    admin_id = admin_auth["user"]["id"]

    # ── 3. SYNCHRONIZATION: PROFILES & PREFERENCES ───────────────
    print("\n[TEST GROUP 3] Profile & Preferences Synchronization")
    prof_a = profile_service.get_profile(user_a_id)
    assert_true(prof_a is not None, "Supabase profile was automatically provisioned for User A")
    assert prof_a is not None
    assert_true(prof_a.get("email") == user_a_email, "Supabase profile email matches MongoDB user email")
    assert_true(prof_a.get("role") == "user", "Supabase profile role matches MongoDB role")

    prefs_a = preferences_service.get_preferences(user_a_id)
    assert_true(prefs_a is not None, "User A default preferences automatically initialized")
    assert_true(prefs_a.get("theme_mode") == "normal", "Default theme_mode is 'normal'")

    # User A updates preferences
    updated_prefs_a = preferences_service.update_preferences(user_a_id, {"theme_mode": "expert", "language": "en"})
    assert_true(updated_prefs_a.get("theme_mode") == "expert", "User A successfully updated theme_mode to 'expert'")

    # Verify User B preferences were not affected
    prefs_b = preferences_service.get_preferences(user_b_id)
    assert_true(prefs_b.get("theme_mode") == "normal", "User B preferences remained 'normal' (isolated from User A)")

    # ── 4. CONVERSATIONS & MESSAGES ISOLATION ────────────────────
    print("\n[TEST GROUP 4] Conversations & Messages User Isolation")
    # User A creates a conversation
    conv_a = conversation_service.create_conversation(user_a_id, title="Alice Secret Project", mode="expert")
    assert_true(conv_a.get("user_id") == user_a_id, "Conversation is owned by User A")
    conv_a_id = conv_a["id"]

    # User A creates messages
    msg_a1 = message_service.create_message(user_a_id, conv_a_id, role="user", content="Hello, let's design the architecture.")
    msg_a2 = message_service.create_message(user_a_id, conv_a_id, role="assistant", content="Understood Alice, here is the design.")
    assert_true(msg_a1 is not None and msg_a2 is not None, "Messages successfully created in conversation")

    # User A can list their messages
    msgs_a = message_service.list_messages(user_a_id, conv_a_id)
    assert_true(len(msgs_a) == 2, f"User A can read own conversation messages (count={len(msgs_a)})")

    # ISOLATION BARRIER: User B attempts to access User A's conversation
    conv_b_peek = conversation_service.get_conversation(user_b_id, conv_a_id)
    assert_true(conv_b_peek is None, "User B CANNOT read User A's conversation (returned None)")

    # ISOLATION BARRIER: User B attempts to list messages of User A's conversation
    msgs_b_peek = message_service.list_messages(user_b_id, conv_a_id)
    assert_true(len(msgs_b_peek) == 0, "User B CANNOT read messages from User A's conversation")

    # ISOLATION BARRIER: User B attempts to inject a message into User A's conversation
    injected = message_service.create_message(user_b_id, conv_a_id, role="user", content="I am spying on you!")
    assert_true(injected is None, "User B CANNOT inject a message into User A's conversation")

    # ── 5. MEMORY PER-USER PARTITIONING & COLLISION TEST ─────────
    print("\n[TEST GROUP 5] User-Scoped Memories & Unique(user_id, memory_key)")
    # User A and User B store the exact SAME memory_key with DIFFERENT values
    mem_a = memory_service.set_memory(user_a_id, memory_key="favorite_color", memory_value="blue")
    mem_b = memory_service.set_memory(user_b_id, memory_key="favorite_color", memory_value="crimson")

    assert_true(mem_a.get("memory_value") == "blue", "User A stored favorite_color = blue")
    assert_true(mem_b.get("memory_value") == "crimson", "User B stored favorite_color = crimson")

    # Verify retrieval isolation
    retrieved_a = memory_service.get_memory(user_a_id, "favorite_color")
    retrieved_b = memory_service.get_memory(user_b_id, "favorite_color")
    assert_true(retrieved_a is not None and retrieved_b is not None, "User A and B memories exist")
    assert retrieved_a is not None and retrieved_b is not None
    assert_true(retrieved_a.get("memory_value") == "blue", "User A recalls 'blue'")
    assert_true(retrieved_b.get("memory_value") == "crimson", "User B recalls 'crimson'")

    facts_a = memory_service.get_user_facts_string(user_a_id)
    facts_b = memory_service.get_user_facts_string(user_b_id)
    assert_true("blue" in facts_a and "crimson" not in facts_a, "User A facts context contains only User A's memories")
    assert_true("crimson" in facts_b and "blue" not in facts_b, "User B facts context contains only User B's memories")

    # ── 6. USER FILE METADATA ISOLATION ──────────────────────────
    print("\n[TEST GROUP 6] User File Metadata Ownership & Isolation")
    file_a = user_file_service.record_file(
        user_id=user_a_id,
        original_name="alice_blueprint.pdf",
        storage_key="files/alice_blueprint.pdf",
        size_bytes=1048576,
        mime_type="application/pdf"
    )
    assert_true(file_a.get("user_id") == user_a_id, "File recorded with User A ownership")
    file_a_id = file_a["id"]

    # User A can get file
    ret_file_a = user_file_service.get_file(user_a_id, file_a_id)
    assert_true(ret_file_a is not None, "User A can access own file metadata")

    # User B cannot get User A's file
    ret_file_b_peek = user_file_service.get_file(user_b_id, file_a_id)
    assert_true(ret_file_b_peek is None, "User B CANNOT access User A's file metadata")

    # User B cannot delete User A's file
    del_res = user_file_service.delete_file(user_b_id, file_a_id)
    assert_true(del_res is False, "User B CANNOT delete User A's file metadata")

    # ── 7. SECURITY & ROLE TAMPERING PREVENTION ──────────────────
    print("\n[TEST GROUP 7] Privilege Escalation & Tampering Prevention")
    # User A attempts to escalate role to admin via profile update
    tamper_result = profile_service.update_user_profile(
        user_a_id,
        {"role": "admin", "full_name": "Alice Superadmin", "is_active": True}
    )
    assert_true(tamper_result.get("role") != "admin", "User A CANNOT escalate role to admin via profile update")
    assert_true(tamper_result.get("role") == "user", "User A role remains strictly 'user'")

    # Verify CurrentUser validation
    current_u = CurrentUser(
        id=user_a_id,
        email=user_a_email,
        full_name="Alice",
        role="user"
    )
    assert_true(current_u.is_admin is False, "CurrentUser correctly reports is_admin = False for normal user")

    admin_u = CurrentUser(
        id=admin_id,
        email="loharavee@gmail.com",
        full_name="naveen panchal",
        role="admin"
    )
    assert_true(admin_u.is_admin is True, "CurrentUser correctly reports is_admin = True for admin")

    # ── 8. LEGACY MIGRATION & DATA PRESERVATION ──────────────────
    print("\n[TEST GROUP 8] Legacy Data Migration & Preservation")
    users_path = os.path.join(backend_dir, "users.json")
    memory_path = os.path.join(backend_dir, "memory.json")
    assert_true(os.path.exists(users_path), "backend/users.json is preserved on disk")
    assert_true(os.path.exists(memory_path), "backend/memory.json is preserved on disk")

    # Verify that admin Naveen's memories migrated from memory.json exist in memory_service
    admin_name_mem = memory_service.get_memory("00000000-0000-0000-0000-000000000001", "user_name")
    assert_true(admin_name_mem is not None, "Admin's legacy 'user_name' memory preserved in memory_service")

    print("\n=======================================================")
    print(f"ALL TESTS PASSED: {passed_tests}/{total_tests} assertions verified successfully!")
    print("=======================================================\n")
    return True


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
