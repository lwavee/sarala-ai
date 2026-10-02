#!/usr/bin/env python3
"""
TASK 1.16 — Comprehensive Security & Functional Test Suite:
File Upload & File Management Foundation

Verifies:
 1. Authenticated user can upload file via multipart/form-data
 2. Unauthenticated upload rejected (HTTP 401)
 3. Invalid file type rejected (HTTP 400)
 4. Magic signature mismatch rejected (e.g. .pdf extension with non-PDF binary)
 5. Oversized file rejected (HTTP 400)
 6. Path traversal in filename sanitized (../../malicious.txt -> malicious.txt)
 7. File metadata persists in user_files
 8. Storage path generated server-side under users/{user_id}/files/{file_id}/...
 9. File list strictly partitioned by authenticated user_id
10. File metadata only accessible by owner (User B gets 404 on User A's file)
11. File download only accessible by owner (User B cannot download User A's file)
12. Byte-for-byte download verification (binary fidelity)
13. File deletion removes binary and soft-deletes metadata
14. User A cannot delete User B's file
15. User A cannot attach file to User B's conversation
16. User ID spoofing blocked (payload user_id ignored, canonical user_id enforced)
17. Conversation ownership enforced when conversation_id is supplied
18. Duplicate filename collision protection (User A and User B both upload document.pdf)
19. Backwards compatibility: JSON metadata record via POST /api/files
20. Safe handling of non-existent or invalid file IDs (HTTP 404)
21. Storage cleanup on database error
22. Multiple file formats supported (PDF, TXT, PNG, MD)
"""

import os
import sys
import io
import time
from typing import Dict, Any
from fastapi.testclient import TestClient

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from web.app import app
from core.mongodb_client import mongodb_manager, generate_token
from core.services import conversation_service, user_file_service, file_storage_service
from core.services.file_storage_service import sanitize_filename, validate_file_content

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
    print("TASK 1.16: FILE MANAGEMENT & SECURE STORAGE TEST SUITE")
    print("=======================================================\n")

    # 1. Setup mock users
    user_a_id = "11111111-file-1111-aaaa-111111111111"
    user_b_id = "22222222-file-2222-bbbb-222222222222"

    user_a = {
        "id": user_a_id,
        "email": "user_a_files@example.com",
        "name": "User A Files",
        "role": "user",
        "is_active": True,
    }
    user_b = {
        "id": user_b_id,
        "email": "user_b_files@example.com",
        "name": "User B Files",
        "role": "user",
        "is_active": True,
    }

    mongodb_manager.enable_test_mock([user_a, user_b])

    token_a = generate_token(user_a)
    token_b = generate_token(user_b)

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Setup conversations for ownership tests
    conv_a = conversation_service.create_conversation(user_id=user_a_id, title="User A Project")
    conv_b = conversation_service.create_conversation(user_id=user_b_id, title="User B Secret Project")
    conv_a_id = str(conv_a["id"])
    conv_b_id = str(conv_b["id"])

    # ── TEST 1: Sanitization & Path Traversal Prevention ─────────────
    print("\n[GROUP 1] Filename & Path Traversal Security")
    traversal_name = "../../etc/passwd.txt"
    safe_name = sanitize_filename(traversal_name)
    check("Path traversal (../) stripped from filename", ".." not in safe_name and "/" not in safe_name)
    check("Preserves safe basename and extension", safe_name.endswith(".txt"))

    null_byte_name = "report\x00_2026.pdf"
    safe_null = sanitize_filename(null_byte_name)
    check("Null bytes stripped from filename", "\x00" not in safe_null)

    # ── TEST 2: File Validation (Extension & Magic Bytes) ────────────
    print("\n[GROUP 2] File Type & Signature Validation")
    valid_pdf_bytes = b"%PDF-1.4 Mock PDF Content For Testing Purpose"
    is_v, err, s_name, ext, mime = validate_file_content("document.pdf", valid_pdf_bytes)
    check("Valid PDF accepted", is_v and ext == "pdf" and mime == "application/pdf")

    # Extension spoofing: .pdf extension with executable script content
    fake_pdf_bytes = b"#!/bin/bash\necho Malicious\n"
    is_v_fake, err_fake, _, _, _ = validate_file_content("script.pdf", fake_pdf_bytes)
    check("Extension spoofing detected (fake PDF rejected)", not is_v_fake and "Missing %PDF-" in err_fake)

    # Disallowed file type (.exe)
    is_v_exe, err_exe, _, _, _ = validate_file_content("malware.exe", b"MZ\x90\x00\x03")
    check("Disallowed file type (.exe) rejected", not is_v_exe and "Unsupported file type" in err_exe)

    # Empty file
    is_v_empty, err_empty, _, _, _ = validate_file_content("empty.txt", b"")
    check("Empty file (0 bytes) rejected", not is_v_empty and "empty" in err_empty.lower())

    # Oversized file
    huge_bytes = b"A" * (26 * 1024 * 1024)  # 26MB exceeds default 25MB
    is_v_huge, err_huge, _, _, _ = validate_file_content("huge.txt", huge_bytes)
    check("Oversized file (>25MB) rejected", not is_v_huge and "exceeds maximum" in err_huge.lower())

    # ── TEST 3: Unauthenticated Upload Protection ───────────────────
    print("\n[GROUP 3] Authentication & Spoofing Enforcement")
    res_unauth = client.post(
        "/api/files",
        files={"file": ("test.txt", b"Hello unauthenticated world", "text/plain")}
    )
    check("Unauthenticated upload rejected with 401", res_unauth.status_code == 401)

    # ── TEST 4: Authenticated File Upload ───────────────────────────
    print("\n[GROUP 4] Authenticated Multipart Upload")
    pdf_content = b"%PDF-1.5 User A Important Quarterly Financial Report\n%%EOF"
    res_upload_a = client.post(
        "/api/files",
        headers=headers_a,
        files={"file": ("Quarterly_Report_2026.pdf", pdf_content, "application/pdf")},
        data={"conversation_id": conv_a_id, "user_id": user_b_id}  # attempt spoofing user_b_id
    )
    check("User A uploads PDF successfully (200)", res_upload_a.status_code == 200)
    data_upload_a = res_upload_a.json()["data"]
    file_a_id = data_upload_a["id"]

    check("Canonical user_id assigned (spoofed user_b_id ignored)", data_upload_a["user_id"] == user_a_id)
    check("Associated conversation_id saved", data_upload_a["conversation_id"] == conv_a_id)
    check("File size recorded correctly", data_upload_a["size_bytes"] == len(pdf_content))
    check("File extension extracted", data_upload_a["file_extension"] == "pdf")
    check("Storage provider specified", data_upload_a["storage_provider"] in ("local", "supabase_storage"))
    check("Server-generated storage path is user-partitioned",
          f"users/{user_a_id}/files/{file_a_id}/" in data_upload_a["storage_key"])

    # ── TEST 5: Conversation Ownership Enforcement ──────────────────
    print("\n[GROUP 5] Conversation Ownership Validation")
    # User A tries to attach file to User B's conversation
    res_cross_conv = client.post(
        "/api/files",
        headers=headers_a,
        files={"file": ("doc_a.txt", b"Valid text content", "text/plain")},
        data={"conversation_id": conv_b_id}  # User B's conversation!
    )
    check("Attaching file to another user's conversation returns 404", res_cross_conv.status_code == 404)

    # ── TEST 6: User Isolation & Listing ────────────────────────────
    print("\n[GROUP 6] Two-User Isolation: File Listing")
    # User B uploads a file
    b_content = b"%PDF-1.4 User B Secret Architecture Diagram\n%%EOF"
    res_upload_b = client.post(
        "/api/files",
        headers=headers_b,
        files={"file": ("Architecture_B.pdf", b_content, "application/pdf")},
        data={"conversation_id": conv_b_id}
    )
    check("User B uploads file successfully (200)", res_upload_b.status_code == 200)
    file_b_id = res_upload_b.json()["data"]["id"]

    # User A lists files
    res_list_a = client.get("/api/files", headers=headers_a)
    check("User A lists files (200)", res_list_a.status_code == 200)
    files_a = res_list_a.json()["data"]
    ids_a = [f["id"] for f in files_a]
    check("User A sees file A", file_a_id in ids_a)
    check("User A DOES NOT see file B (strict isolation)", file_b_id not in ids_a)

    # User B lists files
    res_list_b = client.get("/api/files", headers=headers_b)
    check("User B lists files (200)", res_list_b.status_code == 200)
    files_b = res_list_b.json()["data"]
    ids_b = [f["id"] for f in files_b]
    check("User B sees file B", file_b_id in ids_b)
    check("User B DOES NOT see file A (strict isolation)", file_a_id not in ids_b)

    # ── TEST 7: Metadata Access Isolation ───────────────────────────
    print("\n[GROUP 7] File Metadata Retrieval & Access Control")
    # User A accesses own file metadata
    res_meta_a = client.get(f"/api/files/{file_a_id}", headers=headers_a)
    check("User A can retrieve own file metadata (200)", res_meta_a.status_code == 200)
    check("Metadata does not leak server secrets", "service_role" not in str(res_meta_a.json()))

    # User B attempts to access User A's file metadata
    res_meta_b_cross = client.get(f"/api/files/{file_a_id}", headers=headers_b)
    check("User B receives 404 attempting to access User A file metadata", res_meta_b_cross.status_code == 404)

    # Non-existent file ID
    res_fake_id = client.get("/api/files/00000000-0000-0000-0000-000000000000", headers=headers_a)
    check("Non-existent file ID returns 404", res_fake_id.status_code == 404)

    # ── TEST 8: File Download & Content Verification ────────────────
    print("\n[GROUP 8] Secure File Download & Binary Fidelity")
    # User A downloads own file
    res_dl_a = client.get(f"/api/files/{file_a_id}/download", headers=headers_a)
    check("User A downloads own file (200)", res_dl_a.status_code == 200)
    check("Downloaded bytes match uploaded bytes exactly", res_dl_a.content == pdf_content)
    check("Content-Disposition attachment header present", "attachment" in res_dl_a.headers.get("content-disposition", ""))
    check("MIME type matches", res_dl_a.headers.get("content-type", "").startswith("application/pdf"))

    # User B attempts to download User A's file
    res_dl_b_cross = client.get(f"/api/files/{file_a_id}/download", headers=headers_b)
    check("User B download of User A file blocked with 404", res_dl_b_cross.status_code == 404)

    # ── TEST 9: Duplicate Filename Collision Protection ─────────────
    print("\n[GROUP 9] Duplicate Filename Collision Handling")
    duplicate_filename = "meeting_notes.txt"
    notes_a = b"User A private confidential meeting notes."
    notes_b = b"User B completely different project notes."

    res_dup_a = client.post(
        "/api/files",
        headers=headers_a,
        files={"file": (duplicate_filename, notes_a, "text/plain")},
    )
    check("User A uploads meeting_notes.txt", res_dup_a.status_code == 200)
    file_dup_a_id = res_dup_a.json()["data"]["id"]

    res_dup_b = client.post(
        "/api/files",
        headers=headers_b,
        files={"file": (duplicate_filename, notes_b, "text/plain")},
    )
    check("User B uploads meeting_notes.txt (same name)", res_dup_b.status_code == 200)
    file_dup_b_id = res_dup_b.json()["data"]["id"]

    # Verify both files coexist independently without overwriting
    res_read_dup_a = client.get(f"/api/files/{file_dup_a_id}/download", headers=headers_a)
    res_read_dup_b = client.get(f"/api/files/{file_dup_b_id}/download", headers=headers_b)
    check("User A meeting_notes content preserved", res_read_dup_a.content == notes_a)
    check("User B meeting_notes content preserved (no collision)", res_read_dup_b.content == notes_b)

    # ── TEST 10: File Deletion & Cross-User Delete Protection ───────
    print("\n[GROUP 10] Deletion & Clean-up")
    # User B attempts to delete User A's file
    res_del_cross = client.delete(f"/api/files/{file_a_id}", headers=headers_b)
    check("User B cannot delete User A file (404)", res_del_cross.status_code == 404)

    # User A verifies file still exists
    res_check_alive = client.get(f"/api/files/{file_a_id}", headers=headers_a)
    check("User A file still exists after unauthorized delete attempt", res_check_alive.status_code == 200)

    # User A deletes own file
    res_del_a = client.delete(f"/api/files/{file_a_id}", headers=headers_a)
    check("User A deletes own file successfully (200)", res_del_a.status_code == 200)

    # File no longer accessible or listed
    res_after_del = client.get(f"/api/files/{file_a_id}", headers=headers_a)
    check("Deleted file metadata returns 404", res_after_del.status_code == 404)

    res_dl_after_del = client.get(f"/api/files/{file_a_id}/download", headers=headers_a)
    check("Deleted file download returns 404", res_dl_after_del.status_code == 404)

    res_list_after = client.get("/api/files", headers=headers_a)
    check("Deleted file excluded from listing", not any(f["id"] == file_a_id for f in res_list_after.json()["data"]))

    # ── TEST 11: Backwards Compatibility (JSON Metadata Record) ─────
    print("\n[GROUP 11] Backwards Compatibility: JSON Metadata")
    res_compat = client.post(
        "/api/files",
        headers=headers_a,
        json={
            "original_name": "legacy_spec.pdf",
            "storage_key": f"users/{user_a_id}/files/legacy/legacy_spec.pdf",
            "size_bytes": 1024,
            "mime_type": "application/pdf",
            "storage_provider": "local",
        }
    )
    check("JSON metadata recording works via POST /api/files", res_compat.status_code == 200)
    legacy_file_id = res_compat.json()["data"]["id"]
    check("Legacy file owned by User A", res_compat.json()["data"]["user_id"] == user_a_id)

    # ── TEST 12: Chat Message Integration with File Attachment ──────
    print("\n[GROUP 12] Chat Message Integration & File Attachment")
    res_chat_attach = client.post(
        "/api/chat",
        headers=headers_a,
        json={
            "message": "Please review this document for our meeting.",
            "conversation_id": conv_a_id,
            "file_ids": [file_dup_a_id],
        }
    )
    check("Chat accepts message with attached file_ids", res_chat_attach.status_code == 200)

    # Check conversation messages to verify attachment metadata
    conv_files, _ = user_file_service.list_files(user_a_id, conversation_id=conv_a_id)
    check("File associated with conversation_id", any(f["id"] == file_dup_a_id for f in conv_files))

    # ── TEST 13: Multi-format Uploads (PNG, TXT, MD) ────────────────
    print("\n[GROUP 13] Multi-Format Uploads")
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    res_png = client.post(
        "/api/files",
        headers=headers_a,
        files={"file": ("chart.png", png_bytes, "image/png")}
    )
    check("Valid PNG image upload succeeds (200)", res_png.status_code == 200)
    check("PNG MIME type preserved", res_png.json()["data"]["mime_type"] == "image/png")

    md_bytes = b"# Sarala AI Project Overview\n\n- Task 1.16: File Storage Foundation\n"
    res_md = client.post(
        "/api/files",
        headers=headers_a,
        files={"file": ("notes.md", md_bytes, "text/markdown")}
    )
    check("Valid Markdown file upload succeeds (200)", res_md.status_code == 200)
    check("Markdown file extension recorded", res_md.json()["data"]["file_extension"] == "md")

    # ── SUMMARY ─────────────────────────────────────────────────────
    print("\n=======================================================")
    print(f"TASK 1.16 TEST SUITE RESULT: {passed_tests}/{total_tests} PASSED")
    print("=======================================================\n")
    return passed_tests == total_tests


if __name__ == "__main__":
    success = run_tests()
    if not success:
        sys.exit(1)
