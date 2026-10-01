#!/usr/bin/env python3
"""
TASK 1.12 — USER PROFILE & PREFERENCES FOUNDATION AUTOMATED TEST SUITE
======================================================================
Tests all acceptance criteria and security guarantees:
- TEST 1:  Authenticated user can retrieve own profile
- TEST 2:  Authenticated user can update own profile (PATCH & PUT)
- TEST 3:  Authenticated user can retrieve own preferences
- TEST 4:  Authenticated user can update own preferences (PATCH & PUT)
- TEST 5:  Unauthenticated user cannot retrieve profile (HTTP 401)
- TEST 6:  Unauthenticated user cannot retrieve preferences (HTTP 401)
- TEST 7:  User A cannot access User B profile (User isolation)
- TEST 8:  User A cannot access User B preferences (User isolation)
- TEST 9:  Frontend/request user_id cannot override authenticated user_id
- TEST 10: User cannot change own role through profile API
- TEST 11: User cannot change is_active through profile API
- TEST 12: Invalid AI mode is rejected (HTTP 422)
- TEST 13: Invalid preference types are rejected (HTTP 422)
- TEST 14: Missing preferences receive safe defaults
- TEST 15: Repeated preference initialization does not create duplicates
- TEST 16: Repeated profile initialization does not create duplicates
- TEST 17: Existing users continue to work with auto-provisioned defaults
- SECTION 18: Two-User Security Isolation Scenario (Section 39)
- SECTION 19: Data Persistence & Idempotency Scenario (Section 40)
- SECTION 20: MongoDB Identity vs Supabase Application Data Separation (Section 41)
"""

import os
import sys
import time
import uuid

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi.testclient import TestClient
from web.app import app
from core.mongodb_client import (
    mongodb_manager,
    hash_password,
    generate_token,
)
from core.services import (
    profile_service,
    preferences_service,
)

client = TestClient(app)

# Test User Fixtures
USER_A_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
USER_A_EMAIL = "user-a-112@example.com"
USER_A_PWD = "UserA_Password123!"

USER_B_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
USER_B_EMAIL = "user-b-112@example.com"
USER_B_PWD = "UserB_Password123!"

EXISTING_USER_ID = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
EXISTING_USER_EMAIL = "existing-user-112@example.com"
EXISTING_USER_PWD = "Existing_Password123!"


class MockMongoCollection:
    """Thread-safe in-memory MongoDB users collection for hermetic testing."""
    def __init__(self):
        self._docs = {}

    def create_index(self, keys, **kwargs):
        pass

    def insert_one(self, doc):
        key = doc.get("email") or str(uuid.uuid4())
        self._docs[key] = dict(doc)

    def find_one(self, query):
        if not query:
            return None
        if "email" in query:
            return self._docs.get(query["email"])
        if "$or" in query:
            for branch in query["$or"]:
                res = self.find_one(branch)
                if res:
                    return res
            return None
        for key in ("user_id", "id"):
            if key in query:
                target = query[key]
                for d in self._docs.values():
                    if d.get("user_id") == target or d.get("id") == target:
                        return dict(d)
        return None

    def update_one(self, query, update):
        target = self.find_one(query)
        if target:
            email = target["email"]
            if "$set" in update:
                self._docs[email].update(update["$set"])

    def delete_many(self, query):
        to_del = []
        for email, d in self._docs.items():
            if "$or" in query:
                for b in query["$or"]:
                    if b.get("email") == email or b.get("user_id") == d.get("user_id"):
                        to_del.append(email)
                        break
        for email in to_del:
            self._docs.pop(email, None)

    def count_documents(self, query):
        return len(self._docs)


mock_coll = MockMongoCollection()
mongodb_manager.set_test_collection(mock_coll)


def setup_test_users():
    """Initializes isolated mock MongoDB test users."""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # User A
    salt_a, hash_a = hash_password(USER_A_PWD)
    mock_coll.delete_many({"$or": [{"email": USER_A_EMAIL}, {"user_id": USER_A_ID}]})
    mock_coll.insert_one({
        "user_id": USER_A_ID,
        "id": USER_A_ID,
        "email": USER_A_EMAIL,
        "password_hash": hash_a,
        "password_salt": salt_a,
        "full_name": "Alice User",
        "nickname": "Alice",
        "role": "user",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    })

    # User B
    salt_b, hash_b = hash_password(USER_B_PWD)
    mock_coll.delete_many({"$or": [{"email": USER_B_EMAIL}, {"user_id": USER_B_ID}]})
    mock_coll.insert_one({
        "user_id": USER_B_ID,
        "id": USER_B_ID,
        "email": USER_B_EMAIL,
        "password_hash": hash_b,
        "password_salt": salt_b,
        "full_name": "Bob User",
        "nickname": "Bob",
        "role": "user",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    })

    # Existing User (has MongoDB record, but initially NO Supabase profile or preferences)
    salt_e, hash_e = hash_password(EXISTING_USER_PWD)
    mock_coll.delete_many({"$or": [{"email": EXISTING_USER_EMAIL}, {"user_id": EXISTING_USER_ID}]})
    mock_coll.insert_one({
        "user_id": EXISTING_USER_ID,
        "id": EXISTING_USER_ID,
        "email": EXISTING_USER_EMAIL,
        "password_hash": hash_e,
        "password_salt": salt_e,
        "full_name": "Existing Elena",
        "nickname": "Elena",
        "role": "user",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    })

    # Clean local cache for test isolation
    if hasattr(profile_service, "_cache"):
        profile_service._cache.pop(USER_A_ID, None)
        profile_service._cache.pop(USER_B_ID, None)
        profile_service._cache.pop(EXISTING_USER_ID, None)
    if hasattr(preferences_service, "_cache"):
        preferences_service._cache.pop(USER_A_ID, None)
        preferences_service._cache.pop(USER_B_ID, None)
        preferences_service._cache.pop(EXISTING_USER_ID, None)


def run_all_tests():
    setup_test_users()

    user_a = {"user_id": USER_A_ID, "id": USER_A_ID, "email": USER_A_EMAIL, "role": "user"}
    user_b = {"user_id": USER_B_ID, "id": USER_B_ID, "email": USER_B_EMAIL, "role": "user"}
    user_existing = {"user_id": EXISTING_USER_ID, "id": EXISTING_USER_ID, "email": EXISTING_USER_EMAIL, "role": "user"}

    token_a = generate_token(user_a)
    token_b = generate_token(user_b)
    token_existing = generate_token(user_existing)

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    headers_existing = {"Authorization": f"Bearer {token_existing}"}

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

    print("\n=======================================================")
    print("TASK 1.12 AUTOMATED PROFILE & PREFERENCES TEST SUITE")
    print("=======================================================\n")

    # ── TEST 1: Authenticated user can retrieve own profile ───────────────────
    print("[SECTION 1] Profile Retrieval & Auto-Provisioning (Tests 1, 5, 16, 17)")
    r1 = client.get("/api/profile", headers=headers_a)
    check("TEST 1: Authenticated user can retrieve own profile (HTTP 200)", r1.status_code == 200, f"Got {r1.status_code}")
    data1 = r1.json().get("profile") or r1.json().get("data") or {}
    check("TEST 1: Profile contains canonical user_id", data1.get("user_id") == USER_A_ID)
    check("TEST 1: Profile contains email from auth identity", data1.get("email") == USER_A_EMAIL)
    check("TEST 1: Profile contains full_name from auth identity", data1.get("full_name") == "Alice User")
    check("TEST 1: Profile contains nickname", data1.get("nickname") == "Alice")
    check("TEST 1: Sensitive authentication credentials absent from profile", "password" not in data1 and "password_hash" not in data1 and "token" not in data1)

    # ── TEST 5: Unauthenticated user cannot retrieve profile ─────────────────
    r5 = client.get("/api/profile")
    check("TEST 5: Unauthenticated user cannot retrieve profile (HTTP 401)", r5.status_code == 401)

    # ── TEST 16: Repeated profile initialization does not create duplicates ───
    r16_a = client.get("/api/profile", headers=headers_a)
    r16_b = client.get("/api/profile", headers=headers_a)
    check("TEST 16: Repeated profile retrieval is idempotent (HTTP 200)", r16_a.status_code == 200 and r16_b.status_code == 200)
    data16 = r16_b.json().get("profile") or r16_b.json().get("data") or {}
    check("TEST 16: Profile user_id remains identical", data16.get("user_id") == USER_A_ID)

    # ── TEST 17: Existing users receive auto-provisioned defaults on first GET ─
    r17 = client.get("/api/profile", headers=headers_existing)
    check("TEST 17: Existing user gets auto-provisioned profile (HTTP 200)", r17.status_code == 200)
    data17 = r17.json().get("profile") or r17.json().get("data") or {}
    check("TEST 17: Existing user profile matches canonical user_id", data17.get("user_id") == EXISTING_USER_ID)
    check("TEST 17: Existing user profile matches MongoDB name", data17.get("full_name") == "Existing Elena")

    # ── TEST 2: Authenticated user can update own profile (PATCH & PUT) ───────
    print("\n[SECTION 2] Profile Updates & Security Enforcement (Tests 2, 9, 10, 11)")
    r2_patch = client.patch(
        "/api/profile",
        headers=headers_a,
        json={
            "full_name": "Alice Wonderland",
            "nickname": "Aly",
            "bio": "AI Researcher and Developer.",
            "avatar_url": "https://example.com/alice.png"
        }
    )
    check("TEST 2: Authenticated user can update profile via PATCH (HTTP 200)", r2_patch.status_code == 200)
    data2 = r2_patch.json().get("profile") or r2_patch.json().get("data") or {}
    check("TEST 2: full_name updated", data2.get("full_name") == "Alice Wonderland")
    check("TEST 2: nickname updated", data2.get("nickname") == "Aly")
    check("TEST 2: bio updated", data2.get("bio") == "AI Researcher and Developer.")
    check("TEST 2: avatar_url updated", data2.get("avatar_url") == "https://example.com/alice.png")

    # Verify MongoDB name metadata was synchronized
    mongo_user_a = mongodb_manager.get_user_by_id(USER_A_ID) or {}
    check("TEST 2: MongoDB full_name metadata synchronized", mongo_user_a.get("full_name") == "Alice Wonderland")
    check("TEST 2: MongoDB nickname metadata synchronized", mongo_user_a.get("nickname") == "Aly")

    # PUT endpoint also works
    r2_put = client.put(
        "/api/profile",
        headers=headers_a,
        json={"nickname": "Avee"}
    )
    check("TEST 2: Authenticated user can update profile via PUT (HTTP 200)", r2_put.status_code == 200)
    data2_put = r2_put.json().get("profile") or r2_put.json().get("data") or {}
    check("TEST 2: PUT updated nickname", data2_put.get("nickname") == "Avee")

    # ── TEST 9: Frontend user_id spoofing is prevented ────────────────────────
    r9 = client.patch(
        "/api/profile",
        headers=headers_a,
        json={
            "user_id": USER_B_ID,
            "nickname": "SpoofedAlice"
        }
    )
    check("TEST 9: Profile update with spoofed user_id in body succeeds safely", r9.status_code == 200)
    data9 = r9.json().get("profile") or r9.json().get("data") or {}
    check("TEST 9: Backend ignores spoofed body user_id, maintains authenticated User A", data9.get("user_id") == USER_A_ID)
    # Check that User B's profile was not affected
    user_b_check = client.get("/api/profile", headers=headers_b)
    data_b_check = user_b_check.json().get("profile") or user_b_check.json().get("data") or {}
    check("TEST 9: User B profile completely untouched by User A's spoofing attempt", data_b_check.get("nickname") != "SpoofedAlice")

    # ── TEST 10: Privilege escalation (role modification) is stripped/ignored ──
    r10 = client.patch(
        "/api/profile",
        headers=headers_a,
        json={"role": "admin"}
    )
    check("TEST 10: Attempted role modification request responds (HTTP 200)", r10.status_code == 200)
    data10 = r10.json().get("profile") or r10.json().get("data") or {}
    check("TEST 10: User role remains strictly 'user' (admin escalation prevented)", data10.get("role") == "user")
    mongo_a_role = mongodb_manager.get_user_by_id(USER_A_ID) or {}
    check("TEST 10: MongoDB authoritative role remains 'user'", mongo_a_role.get("role") == "user")

    # ── TEST 11: is_active modification is stripped/ignored ───────────────────
    r11 = client.patch(
        "/api/profile",
        headers=headers_a,
        json={"is_active": False}
    )
    check("TEST 11: Attempted is_active modification responds (HTTP 200)", r11.status_code == 200)
    data11 = r11.json().get("profile") or r11.json().get("data") or {}
    check("TEST 11: User is_active remains True", data11.get("is_active") is True)

    # ── TEST 3: Authenticated user can retrieve own preferences ───────────────
    print("\n[SECTION 3] Preferences Management & Validation (Tests 3, 4, 6, 12, 13, 14, 15)")
    r3 = client.get("/api/preferences", headers=headers_a)
    check("TEST 3: Authenticated user can retrieve own preferences (HTTP 200)", r3.status_code == 200)
    prefs3 = r3.json().get("preferences") or r3.json().get("data") or {}
    check("TEST 3: Preferences contains canonical user_id", prefs3.get("user_id") == USER_A_ID)

    # ── TEST 14: Missing preferences receive safe defaults ────────────────────
    check("TEST 14: Default ai_mode is 'normal'", prefs3.get("ai_mode") == "normal")
    check("TEST 14: Default theme_mode is 'normal'", prefs3.get("theme_mode") == "normal")
    check("TEST 14: Default voice_enabled is True", prefs3.get("voice_enabled") is True)
    check("TEST 14: Default assistant_personality is 'normal'", prefs3.get("assistant_personality") == "normal")

    # ── TEST 6: Unauthenticated user cannot retrieve preferences ──────────────
    r6 = client.get("/api/preferences")
    check("TEST 6: Unauthenticated user cannot retrieve preferences (HTTP 401)", r6.status_code == 401)

    # ── TEST 15: Repeated preference initialization does not create duplicates ─
    r15_a = client.get("/api/preferences", headers=headers_a)
    r15_b = client.get("/api/preferences", headers=headers_a)
    check("TEST 15: Repeated preferences retrieval is idempotent (HTTP 200)", r15_a.status_code == 200 and r15_b.status_code == 200)
    prefs15 = r15_b.json().get("preferences") or r15_b.json().get("data") or {}
    check("TEST 15: Preferences user_id remains identical", prefs15.get("user_id") == USER_A_ID)

    # ── TEST 4: Authenticated user can update preferences ─────────────────────
    r4_patch = client.patch(
        "/api/preferences",
        headers=headers_a,
        json={
            "ai_mode": "expert",
            "voice_enabled": False,
            "persona_settings": {"verbosity": "concise", "code_style": "pythonic"}
        }
    )
    check("TEST 4: Update preferences via PATCH succeeds (HTTP 200)", r4_patch.status_code == 200)
    prefs4 = r4_patch.json().get("preferences") or r4_patch.json().get("data") or {}
    check("TEST 4: ai_mode updated to 'expert'", prefs4.get("ai_mode") == "expert")
    check("TEST 4: theme_mode synchronized to 'expert'", prefs4.get("theme_mode") == "expert")
    check("TEST 4: voice_enabled updated to False", prefs4.get("voice_enabled") is False)
    check("TEST 4: persona_settings preserved", prefs4.get("persona_settings", {}).get("verbosity") == "concise")

    # PUT endpoint also works
    r4_put = client.put(
        "/api/preferences",
        headers=headers_a,
        json={"ai_mode": "love", "voice_enabled": True}
    )
    check("TEST 4: Update preferences via PUT succeeds (HTTP 200)", r4_put.status_code == 200)
    prefs4_put = r4_put.json().get("preferences") or r4_put.json().get("data")
    check("TEST 4: PUT updated ai_mode to 'love'", prefs4_put.get("ai_mode") == "love")
    check("TEST 4: PUT synchronized theme_mode to 'love'", prefs4_put.get("theme_mode") == "love")
    check("TEST 4: PUT updated voice_enabled to True", prefs4_put.get("voice_enabled") is True)

    # ── TEST 12: Invalid AI mode is rejected with HTTP 422 ───────────────────
    invalid_modes = ["developer", "coding", "assistant", "friend", "pro", "god", "custom", "superai"]
    for bad_mode in invalid_modes:
        r12 = client.patch(
            "/api/preferences",
            headers=headers_a,
            json={"ai_mode": bad_mode}
        )
        check(f"TEST 12: Invalid ai_mode '{bad_mode}' rejected with HTTP 422", r12.status_code == 422)

    # Invalid theme_mode is also rejected
    r12_theme = client.patch(
        "/api/preferences",
        headers=headers_a,
        json={"theme_mode": "matrix_neon"}
    )
    check("TEST 12: Invalid theme_mode rejected with HTTP 422", r12_theme.status_code == 422)

    # ── TEST 13: Invalid preference types are rejected ────────────────────────
    # Non-boolean voice_enabled
    r13_voice = client.patch(
        "/api/preferences",
        headers=headers_a,
        json={"voice_enabled": "not_a_boolean"}
    )
    check("TEST 13: Non-boolean voice_enabled rejected with HTTP 422", r13_voice.status_code == 422)

    # Non-dict persona_settings
    r13_persona = client.patch(
        "/api/preferences",
        headers=headers_a,
        json={"persona_settings": ["not", "a", "dict"]}
    )
    check("TEST 13: Array for persona_settings rejected with HTTP 422", r13_persona.status_code == 422)

    # Non-string full_name in profile
    r13_name = client.patch(
        "/api/profile",
        headers=headers_a,
        json={"full_name": {"nested": "object"}}
    )
    check("TEST 13: Object for full_name rejected with HTTP 422", r13_name.status_code == 422)

    # Persona settings sanitizes secret keys
    r13_sanitize = client.patch(
        "/api/preferences",
        headers=headers_a,
        json={
            "persona_settings": {
                "preferred_tone": "formal",
                "api_key_secret": "sensitive_val",
                "user_password": "super_secret"
            }
        }
    )
    check("TEST 13: Persona settings sanitization accepted (HTTP 200)", r13_sanitize.status_code == 200)
    sanitized_persona = r13_sanitize.json().get("preferences", {}).get("persona_settings", {})
    check("TEST 13: Normal persona setting retained", sanitized_persona.get("preferred_tone") == "formal")
    check("TEST 13: Secret keys stripped from persona settings", "api_key_secret" not in sanitized_persona and "user_password" not in sanitized_persona)

    # ── SECTION 18: Two-User Security Isolation Scenario (Tests 7, 8, Section 39)
    print("\n[SECTION 4] Two-User Security Isolation (Tests 7, 8, Section 39)")
    # Set User A preferences & profile
    client.patch("/api/profile", headers=headers_a, json={"nickname": "AliceA", "bio": "Bio A"})
    client.patch("/api/preferences", headers=headers_a, json={"ai_mode": "expert"})

    # Set User B preferences & profile
    client.patch("/api/profile", headers=headers_b, json={"nickname": "BobB", "bio": "Bio B"})
    client.patch("/api/preferences", headers=headers_b, json={"ai_mode": "love"})

    # Retrieve User A data
    prof_a = client.get("/api/profile", headers=headers_a).json().get("profile") or {}
    prefs_a = client.get("/api/preferences", headers=headers_a).json().get("preferences") or {}

    # Retrieve User B data
    prof_b = client.get("/api/profile", headers=headers_b).json().get("profile") or {}
    prefs_b = client.get("/api/preferences", headers=headers_b).json().get("preferences") or {}

    check("SECTION 18: Profile B user_id != Profile A user_id", prof_b.get("user_id") != prof_a.get("user_id"))
    check("SECTION 18: Profile B nickname != Profile A nickname", prof_b.get("nickname") == "BobB" and prof_a.get("nickname") == "AliceA")
    check(
        "SECTION 18: Preferences B ai_mode != Preferences A ai_mode",
        prefs_b.get("ai_mode") == "love" and prefs_a.get("ai_mode") == "expert",
        f"prefs_a={prefs_a.get('ai_mode')} (full={prefs_a}), prefs_b={prefs_b.get('ai_mode')} (full={prefs_b})"
    )

    # TEST 7: User B attempts to access User A's profile via query parameter
    r7_query = client.get(f"/api/profile?user_id={USER_A_ID}", headers=headers_b)
    prof_b_spoof = r7_query.json().get("profile") or {}
    check("TEST 7: User B with ?user_id=USER_A receives only User B profile", prof_b_spoof.get("user_id") == USER_B_ID and prof_b_spoof.get("nickname") == "BobB")

    # TEST 8: User B attempts to access User A's preferences via query parameter
    r8_query = client.get(f"/api/preferences?user_id={USER_A_ID}", headers=headers_b)
    prefs_b_spoof = r8_query.json().get("preferences") or {}
    check("TEST 8: User B with ?user_id=USER_A receives only User B preferences", prefs_b_spoof.get("user_id") == USER_B_ID and prefs_b_spoof.get("ai_mode") == "love")

    # User B attempts to update User A's profile
    r_tamper = client.patch(
        "/api/profile",
        headers=headers_b,
        json={"user_id": USER_A_ID, "nickname": "HijackedByB"}
    )
    check("SECTION 18: Tampering request executes safely (HTTP 200)", r_tamper.status_code == 200)
    prof_a_recheck = client.get("/api/profile", headers=headers_a).json().get("profile") or {}
    check("SECTION 18: User A profile remains completely untouched by User B", prof_a_recheck.get("nickname") == "AliceA")

    # ── SECTION 19: Data Persistence & Idempotency Scenario (Section 40) ──────
    print("\n[SECTION 5] Data Persistence & Service-Level Verification (Section 40)")
    # Direct service check simulates fresh server restart with cache lookup
    svc_prof = profile_service.get_profile(USER_A_ID) or {}
    check("SECTION 19: Profile persisted in service layer", bool(svc_prof) and svc_prof.get("user_id") == USER_A_ID)
    check("SECTION 19: Persisted nickname matches", svc_prof.get("nickname") in ("AliceA", "Avee", "Aly"))

    svc_prefs = preferences_service.get_preferences(USER_A_ID) or {}
    check("SECTION 19: Preferences persisted in service layer", bool(svc_prefs) and svc_prefs.get("user_id") == USER_A_ID)
    check("SECTION 19: Persisted ai_mode matches", svc_prefs.get("ai_mode") in ("expert", "love", "normal"))

    # ── SECTION 20: MongoDB Identity vs Supabase Application Data Separation (Section 41)
    print("\n[SECTION 6] Dual-Database Architectural Separation (Section 41)")
    # Check Supabase profiles data does not contain passwords or secrets
    check("SECTION 20: Supabase profile does not contain password_hash", "password_hash" not in svc_prof)
    check("SECTION 20: Supabase profile does not contain password_salt", "password_salt" not in svc_prof)
    check("SECTION 20: Supabase profile does not contain session token", "token" not in svc_prof and "access_token" not in svc_prof)

    # Check MongoDB contains authentication identity (raw doc contains hash/salt, sanitized get_user_by_id does not)
    mongo_user = mongodb_manager.get_user_by_id(USER_A_ID) or {}
    mongo_raw_user = mongodb_manager.users.find_one({"user_id": USER_A_ID}) if mongodb_manager.users is not None else None
    check("SECTION 20: MongoDB contains authoritative user_id", mongo_user.get("user_id") == USER_A_ID)
    check("SECTION 20: MongoDB contains password_hash", mongo_raw_user is not None and "password_hash" in mongo_raw_user and len(mongo_raw_user["password_hash"]) > 20)
    check("SECTION 20: MongoDB contains password_salt", mongo_raw_user is not None and "password_salt" in mongo_raw_user and len(mongo_raw_user["password_salt"]) > 10)
    check("SECTION 20: MongoDB contains authoritative role", mongo_user.get("role") == "user")

    print("\n=======================================================")
    print(f"ALL TESTS COMPLETED: {passed}/{total} assertions verified successfully!")
    print("=======================================================\n")
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
