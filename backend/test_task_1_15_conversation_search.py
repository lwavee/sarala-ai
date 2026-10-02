#!/usr/bin/env python3
"""
TASK 1.15 — Comprehensive Test Suite: Searchable Conversation History

Tests:
 1. Search by title (case-insensitive substring)
 2. Search by message content (user's messages in user's conversations)
 3. No results (empty results returns 200 with data=[], total=0)
 4. Deduplication: multiple matching messages from one conversation return the conversation only once
 5. Sorting (last_message_at, updated_at, created_at, title; asc and desc)
 6. Pagination (limit, offset, total count)
 7. Empty query behavior (returns recent conversations with 200)
 8. Long query validation (>500 chars rejected with 400)
 9. User A isolation (User A never sees User B's conversations)
10. User B isolation (User B never sees User A's conversations)
11. User ID spoofing protection (?user_id=USER_B while auth as User A is ignored)
12. Authentication required (calling without auth header returns 401)
13. Result limit respected (limit <= 50, max 100)
14. Conversation can be opened from search result (ID retrieves conversation & messages)
15. Service-level deduplication and search consistency
"""

import os
import sys
import time
from typing import Dict, Any, List
from fastapi.testclient import TestClient

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from web.app import app
from core.mongodb_client import mongodb_manager, generate_token
from core.services import conversation_service, message_service

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
    print("TASK 1.15: SEARCHABLE CONVERSATION HISTORY VERIFICATION")
    print("=======================================================\n")

    # 1. Setup mock users
    user_a_id = "11111111-aaaa-1111-aaaa-111111111111"
    user_b_id = "22222222-bbbb-2222-bbbb-222222222222"

    user_a = {
        "id": user_a_id,
        "email": "alice_search@sarla.ai",
        "name": "Alice Search",
        "role": "user",
        "is_active": True,
    }
    user_b = {
        "id": user_b_id,
        "email": "bob_search@sarla.ai",
        "name": "Bob Search",
        "role": "user",
        "is_active": True,
    }

    mongodb_manager.enable_test_mock([user_a, user_b])

    token_a = generate_token(user_a)
    token_b = generate_token(user_b)

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # ─────────────────────────────────────────────────────────────
    print("[SECTION 1] Setup Test Data for User A & User B")
    # ─────────────────────────────────────────────────────────────
    # Create conversations for User A
    c_a1 = conversation_service.create_conversation(user_a_id, title="Quantum Computing Fundamentals", mode="normal")
    time.sleep(0.01)
    c_a2 = conversation_service.create_conversation(user_a_id, title="Website Redesign Architecture", mode="coder")
    time.sleep(0.01)
    c_a3 = conversation_service.create_conversation(user_a_id, title="Culinary Recipes and Baking", mode="normal")
    time.sleep(0.01)

    cid_a1 = str(c_a1["id"])
    cid_a2 = str(c_a2["id"])
    cid_a3 = str(c_a3["id"])

    # Add messages to c_a1
    message_service.create_message(user_a_id, cid_a1, role="user", content="Explain quantum superposition")
    message_service.create_message(user_a_id, cid_a1, role="assistant", content="Superposition allows qubits to be 0 and 1 simultaneously.")

    # Add messages to c_a2
    message_service.create_message(user_a_id, cid_a2, role="user", content="We need Next.js with Tailwind CSS")
    message_service.create_message(user_a_id, cid_a2, role="assistant", content="Next.js App Router is configured.")

    # Add messages to c_a3 with specific keyword in message content NOT in title
    message_service.create_message(user_a_id, cid_a3, role="user", content="How do I bake sourdough bread?")
    message_service.create_message(user_a_id, cid_a3, role="assistant", content="Fermentation takes 24 hours at room temperature.")
    # Add second matching message to c_a3 for deduplication testing
    message_service.create_message(user_a_id, cid_a3, role="user", content="My sourdough crust is very crunchy")

    # Create conversations for User B with identical or overlapping terms
    c_b1 = conversation_service.create_conversation(user_b_id, title="Website Redesign Architecture", mode="normal")
    c_b2 = conversation_service.create_conversation(user_b_id, title="Kubernetes Cluster Setup", mode="coder")
    cid_b1 = str(c_b1["id"])
    cid_b2 = str(c_b2["id"])

    # Add messages for User B
    message_service.create_message(user_b_id, cid_b1, role="user", content="Bob also loves sourdough bread")
    message_service.create_message(user_b_id, cid_b2, role="user", content="Deploying pods on Kubernetes")

    check("DATA SETUP: User A conversation 1 created", bool(cid_a1))
    check("DATA SETUP: User A conversation 2 created", bool(cid_a2))
    check("DATA SETUP: User A conversation 3 created", bool(cid_a3))
    check("DATA SETUP: User B conversations created", bool(cid_b1 and cid_b2))

    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 2] Search By Title (Test 1)")
    # ─────────────────────────────────────────────────────────────
    res_title = client.get("/api/conversations/search?q=Quantum", headers=headers_a)
    check("TEST 1: Search by title returns 200", res_title.status_code == 200)
    data_title = res_title.json().get("data", [])
    check("TEST 1: Exactly 1 conversation found for 'Quantum'", len(data_title) == 1)
    check("TEST 1: Matching conversation ID is correct", str(data_title[0].get("id")) == cid_a1)
    check("TEST 1: Matching title contains 'Quantum'", "Quantum" in data_title[0].get("title", ""))

    # Case-insensitivity check
    res_lower = client.get("/api/conversations/search?q=quantum", headers=headers_a)
    check("TEST 1: Search is case-insensitive", len(res_lower.json().get("data", [])) == 1)

    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 3] Search By Message Content (Test 2)")
    # ─────────────────────────────────────────────────────────────
    # "sourdough" appears in the messages of c_a3, but NOT in its title ("Culinary Recipes and Baking")
    res_content = client.get("/api/conversations/search?q=sourdough", headers=headers_a)
    check("TEST 2: Search by message content returns 200", res_content.status_code == 200)
    data_content = res_content.json().get("data", [])
    check("TEST 2: Conversation found by message content", len(data_content) == 1)
    check("TEST 2: Correct conversation retrieved", str(data_content[0].get("id")) == cid_a3)
    check("TEST 2: Result has title 'Culinary Recipes and Baking'", data_content[0].get("title") == "Culinary Recipes and Baking")

    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 4] Empty Results & Non-Matching Query (Test 3)")
    # ─────────────────────────────────────────────────────────────
    res_empty = client.get("/api/conversations/search?q=xyznonexistentterm12345", headers=headers_a)
    check("TEST 3: Non-matching search returns 200 (not 404 or 500)", res_empty.status_code == 200)
    body_empty = res_empty.json()
    check("TEST 3: Empty results has data=[]", body_empty.get("data") == [])
    check("TEST 3: Empty results has pagination.total=0", body_empty.get("pagination", {}).get("total") == 0)

    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 5] Result Deduplication (Test 4)")
    # ─────────────────────────────────────────────────────────────
    # c_a3 has two messages containing "sourdough". It must appear only ONCE in results.
    res_dedup = client.get("/api/conversations/search?q=sourdough", headers=headers_a)
    ids_found = [c["id"] for c in res_dedup.json().get("data", [])]
    check("TEST 4: Exactly 1 result returned despite multiple matching messages", len(ids_found) == 1)
    check("TEST 4: No duplicate conversation IDs in results", len(ids_found) == len(set(ids_found)))

    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 6] Sorting (Test 5)")
    # ─────────────────────────────────────────────────────────────
    # Search all conversations for User A using empty query or title search
    res_sort_desc = client.get("/api/conversations/search?q=&sort=title&order=desc", headers=headers_a)
    check("TEST 5: Sort title desc returns 200", res_sort_desc.status_code == 200)
    titles_desc = [c["title"] for c in res_sort_desc.json().get("data", [])]
    check("TEST 5: Titles are sorted in descending alphabetical order", titles_desc == sorted(titles_desc, reverse=True))

    res_sort_asc = client.get("/api/conversations/search?q=&sort=title&order=asc", headers=headers_a)
    titles_asc = [c["title"] for c in res_sort_asc.json().get("data", [])]
    check("TEST 5: Titles are sorted in ascending alphabetical order", titles_asc == sorted(titles_asc))

    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 7] Pagination (Test 6, 13)")
    # ─────────────────────────────────────────────────────────────
    # User A has 3 conversations
    res_p1 = client.get("/api/conversations/search?limit=2&offset=0", headers=headers_a)
    check("TEST 6: Page 1 with limit=2 returns 200", res_p1.status_code == 200)
    data_p1 = res_p1.json().get("data", [])
    check("TEST 6: Page 1 respects limit=2", len(data_p1) == 2)
    check("TEST 6: Total count is 3", res_p1.json().get("pagination", {}).get("total") == 3)

    res_p2 = client.get("/api/conversations/search?limit=2&offset=2", headers=headers_a)
    data_p2 = res_p2.json().get("data", [])
    check("TEST 6: Page 2 with offset=2 returns 1 remaining item", len(data_p2) == 1)
    check("TEST 6: Page 1 and Page 2 contain disjoint conversations", data_p1[0]["id"] != data_p2[0]["id"])

    # Result limit test: limit cannot exceed 100
    res_large_limit = client.get("/api/conversations/search?limit=150", headers=headers_a)
    check("TEST 13: Limit > 100 rejected with HTTP 422", res_large_limit.status_code == 422)

    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 8] Empty Query & Whitespace Handling (Test 7)")
    # ─────────────────────────────────────────────────────────────
    res_empty_q = client.get("/api/conversations/search?q=", headers=headers_a)
    check("TEST 7: Empty q parameter returns 200", res_empty_q.status_code == 200)
    check("TEST 7: Empty q returns all recent conversations for User A", len(res_empty_q.json().get("data", [])) == 3)

    res_spaces = client.get("/api/conversations/search?q=%20%20%20", headers=headers_a)
    check("TEST 7: Whitespace-only q returns 200", res_spaces.status_code == 200)
    check("TEST 7: Whitespace-only q returns recent conversations", len(res_spaces.json().get("data", [])) == 3)

    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 9] Long Query Validation (Test 8)")
    # ─────────────────────────────────────────────────────────────
    oversized_q = "a" * 501
    res_long = client.get(f"/api/conversations/search?q={oversized_q}", headers=headers_a)
    check("TEST 8: Query > 500 characters rejected with HTTP 400", res_long.status_code == 400)

    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 10] Two-User Security Isolation (Tests 9, 10)")
    # ─────────────────────────────────────────────────────────────
    # Both User A and User B have a conversation titled "Website Redesign Architecture"
    # User A search for "Website"
    res_a_web = client.get("/api/conversations/search?q=Website", headers=headers_a)
    a_results = res_a_web.json().get("data", [])
    check("TEST 9: User A finds 1 matching conversation", len(a_results) == 1)
    check("TEST 9: User A receives ONLY User A's conversation ID", str(a_results[0]["id"]) == cid_a2)
    check("TEST 9: User A does NOT receive User B's conversation ID", str(a_results[0]["id"]) != cid_b1)

    # User B search for "Website"
    res_b_web = client.get("/api/conversations/search?q=Website", headers=headers_b)
    b_results = res_b_web.json().get("data", [])
    check("TEST 10: User B finds 1 matching conversation", len(b_results) == 1)
    check("TEST 10: User B receives ONLY User B's conversation ID", str(b_results[0]["id"]) == cid_b1)
    check("TEST 10: User B does NOT receive User A's conversation ID", str(b_results[0]["id"]) != cid_a2)

    # User B searches for "Quantum" (which only User A has)
    res_b_quantum = client.get("/api/conversations/search?q=Quantum", headers=headers_b)
    check("TEST 10: User B searching for User A's topic returns 0 results", len(res_b_quantum.json().get("data", [])) == 0)

    # User A searches for "Kubernetes" (which only User B has)
    res_a_k8s = client.get("/api/conversations/search?q=Kubernetes", headers=headers_a)
    check("TEST 9: User A searching for User B's topic returns 0 results", len(res_a_k8s.json().get("data", [])) == 0)

    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 11] ID Spoofing Protection (Test 11)")
    # ─────────────────────────────────────────────────────────────
    # Authenticated as User A, attempt to pass ?user_id=USER_B
    res_spoof = client.get(f"/api/conversations/search?q=Kubernetes&user_id={user_b_id}", headers=headers_a)
    check("TEST 11: Spoofed query returns 200", res_spoof.status_code == 200)
    check("TEST 11: Spoofed user_id ignored; User A receives 0 results for User B content", len(res_spoof.json().get("data", [])) == 0)

    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 12] Authentication Enforcement (Test 12)")
    # ─────────────────────────────────────────────────────────────
    res_no_auth = client.get("/api/conversations/search?q=test")
    check("TEST 12: Unauthenticated search request rejected with HTTP 401", res_no_auth.status_code == 401)

    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 13] Open Conversation from Search Result (Test 14)")
    # ─────────────────────────────────────────────────────────────
    # Result contains ID, which can be retrieved and message history loaded
    first_result = data_title[0]
    opened_cid = str(first_result["id"])
    r_get = client.get(f"/api/conversations/{opened_cid}", headers=headers_a)
    check("TEST 14: Opened conversation by ID returns 200", r_get.status_code == 200)
    check("TEST 14: Opened conversation title matches search result", r_get.json().get("data", {}).get("title") == first_result["title"])

    r_msgs = client.get(f"/api/conversations/{opened_cid}/messages", headers=headers_a)
    check("TEST 14: Messages for search result conversation loaded with 200", r_msgs.status_code == 200)
    msgs = r_msgs.json().get("data") or r_msgs.json().get("messages") or []
    check("TEST 14: Full conversation message history intact", len(msgs) == 2)

    # ─────────────────────────────────────────────────────────────
    print("\n[SECTION 14] GET /api/conversations?search=... Unified Parity")
    # ─────────────────────────────────────────────────────────────
    res_alias = client.get("/api/conversations?search=sourdough", headers=headers_a)
    check("TEST 15: /api/conversations?search= returns 200", res_alias.status_code == 200)
    check("TEST 15: /api/conversations?search= returns matching conversation via message content", len(res_alias.json().get("data", [])) == 1)

    print("\n=======================================================")
    print(f"ALL {passed_tests}/{total_tests} TASK 1.15 ASSERTIONS PASSED SUCCESSFULLY! [OK]")
    print("=======================================================\n")


if __name__ == "__main__":
    run_tests()
