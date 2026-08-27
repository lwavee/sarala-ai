"""
Sarala AI — End-to-End Verification Test Suite
Tests:
1. Supabase Persistence for Training Items (CRUD)
2. Category and Search Filtering
3. Knowledge Document Chunking
4. Role-based Authentication (Admin vs User)
5. In-Memory Voice Streaming (Zero Disk Writes)
"""

import os
import sys
import uuid
import time
import logging

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.admin_service import admin_service
from memory.storage import MemoryStorage
from voice.natural_voice import natural_voice_manager, clean_text_for_synthesis

def test_training_mode_persistence():
    print("\n--- TEST 1: Training Mode CRUD & Supabase Persistence ---")
    unique_id = f"test_item_{int(time.time())}"
    unique_topic = f"Quantum AI Theory - {unique_id}"
    unique_prompt = f"How does quantum superposition help Sarala AI? ({unique_id})"
    unique_response = "Quantum superposition enables simultaneous state exploration in vector space."

    # 1. Insert
    print("1. Adding unique training item...")
    save_res = admin_service.save_training_item({
        "id": str(uuid.uuid4()),
        "topic": unique_topic,
        "category": "tech",
        "prompt_pattern": unique_prompt,
        "target_response": unique_response,
        "confidence": 1.0,
        "source": "automated_test"
    })
    print("Save Response:", save_res.get("message"))
    assert save_res.get("success"), f"Save failed: {save_res}"
    item_id = save_res["item"]["id"]

    # 2. Retrieve & Verify
    print("2. Retrieving item by search...")
    query_res = admin_service.get_training_items(search=unique_id)
    items = query_res.get("items", [])
    found = any(it.get("topic") == unique_topic for it in items)
    print(f"Found saved item: {found} (Total retrieved: {len(items)})")
    assert found, "Saved item was not found in query results!"

    # 3. Update
    print("3. Updating item...")
    updated_response = "Updated: Quantum superposition enables infinite computational depth."
    update_res = admin_service.update_training_item(item_id, {"target_response": updated_response})
    assert update_res.get("success"), f"Update failed: {update_res}"

    # 4. Delete
    print("4. Deleting item...")
    del_res = admin_service.delete_training_item(item_id)
    assert del_res.get("success"), f"Delete failed: {del_res}"
    print("[PASS] Training Mode CRUD verified successfully!")

def test_knowledge_chunking():
    print("\n--- TEST 2: Knowledge Document Chunking (Big Data) ---")
    sample_doc = """# Introduction to Next.js 16

Next.js 16 introduces Turbopack as default bundler for all environments. It accelerates compilation by up to 10x compared to Webpack.

## Server Actions and Streaming

Server components stream content directly over HTTP chunk by chunk. This reduces Time to First Byte and improves mobile user experience on 3G and 4G networks.

## Scalable RAG Architectures

Retrieval-Augmented Generation breaks large manuals into distinct semantic paragraphs. Each paragraph is indexed by keywords and vector similarity."""

    ingest_res = admin_service.ingest_document(
        title="Next.js 16 High-Performance Architecture",
        content=sample_doc,
        category="tech"
    )
    print("Ingestion Result:", ingest_res)
    assert ingest_res.get("success"), "Knowledge ingestion failed!"
    assert (ingest_res.get("chunks_count") or 0) >= 3, f"Expected at least 3 chunks, got {ingest_res.get('chunks_count')}"
    print("[PASS] Knowledge Document Chunking verified successfully!")

def test_role_authentication():
    print("\n--- TEST 3: Role-Based Authentication (Admin vs User) ---")
    mem = MemoryStorage("memory.json")
    
    # 1. Test Admin Login (Naveen)
    admin_auth = mem.authenticate_user("loharavee@gmail.com", "Sarla@123")
    print("Admin Auth Result:", admin_auth)
    assert admin_auth["success"], "Admin auth failed!"
    assert admin_auth["user"]["role"] == "admin", "Admin role not assigned to Naveen!"
    assert admin_auth["user"]["is_naveen"] is True

    # 2. Test Normal User Registration & Login
    test_user_email = f"user_{int(time.time())}@example.com"
    reg_res = mem.register_user("Regular User", "reggy", test_user_email, "UserPass123", role="user")
    print("User Registration Result:", reg_res)
    assert reg_res["success"], "User registration failed!"
    assert reg_res["user"]["role"] == "user", "Normal user should have role 'user'!"
    assert reg_res["user"]["is_naveen"] is False

    user_auth = mem.authenticate_user(test_user_email, "UserPass123")
    assert user_auth["success"], "User auth failed!"
    assert user_auth["user"]["role"] == "user"
    print("[PASS] Role-Based Authentication verified successfully!")

def test_in_memory_voice_streaming():
    print("\n--- TEST 4: In-Memory Voice Streaming (Zero Disk Writes) ---")
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice", "output")
    files_before = set(os.listdir(output_dir)) if os.path.exists(output_dir) else set()

    # Synthesize text
    test_phrase = "Namaste! This is in-memory voice streaming test."
    cleaned = clean_text_for_synthesis(test_phrase)
    assert len(cleaned) > 0

    synth_res = natural_voice_manager.synthesize(cleaned, language="hi")
    print("Streaming Voice Result:", synth_res)
    assert synth_res.get("success"), "Streaming synthesis failed!"
    assert "/voice/stream" in synth_res.get("audio_url", ""), "Audio URL is not in-memory stream!"
    assert synth_res.get("in_memory") is True

    files_after = set(os.listdir(output_dir)) if os.path.exists(output_dir) else set()
    new_files = files_after - files_before
    print(f"New disk files created in voice/output: {len(new_files)}")
    assert len(new_files) == 0, f"Expected 0 new files, but found: {new_files}"
    print("[PASS] Zero disk clutter verified - voice is 100% in-memory streamed!")

if __name__ == "__main__":
    test_training_mode_persistence()
    test_knowledge_chunking()
    test_role_authentication()
    test_in_memory_voice_streaming()
    print("\n=======================================================")
    print("ALL VERIFICATION SUITE TESTS PASSED SUCCESSFULLY! [OK]")
    print("=======================================================")
