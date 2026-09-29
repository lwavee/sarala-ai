#!/usr/bin/env python3
"""
Legacy Data Migration Script for Sarala AI Dual Database Architecture.
Migrates:
- backend/users.json -> MongoDB Auth & Supabase Profiles / Preferences
- backend/memory.json -> Supabase User-Scoped Memories (assigned to canonical admin user)
Preserves original files without deleting them.
"""

import os
import sys
import json
import logging
from typing import Dict, Any

# Ensure backend root is in sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from core.mongodb_client import mongodb_manager, hash_password
from core.supabase_client import supabase_manager
from core.services.profile_service import profile_service
from core.services.preferences_service import preferences_service
from core.services.memory_service import memory_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sarala.migration")


def migrate_users(users_filepath: str) -> Dict[str, Any]:
    """Migrates users from users.json into MongoDB and Supabase."""
    results = {"total": 0, "migrated_to_mongo": 0, "migrated_to_supabase": 0, "skipped": 0, "errors": []}

    if not os.path.exists(users_filepath):
        logger.warning(f"File not found: {users_filepath}")
        return results

    try:
        with open(users_filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read {users_filepath}: {e}")
        results["errors"].append(str(e))
        return results

    results["total"] = len(data)
    logger.info(f"Auditing {len(data)} legacy user records from {users_filepath}...")

    for email_key, udata in data.items():
        email = udata.get("email") or email_key
        email_clean = email.strip().lower()
        full_name = udata.get("name") or email_clean.split("@")[0].title()
        nickname = udata.get("nickname") or full_name.split()[0]
        role = udata.get("role", "user")
        if email_clean == "loharavee@gmail.com":
            role = "admin"

        user_id = udata.get("id")

        # 1. MongoDB check/sync
        if mongodb_manager.is_connected and mongodb_manager.users is not None:
            existing = mongodb_manager.users.find_one({"email": email_clean})
            if not existing:
                import uuid
                if not user_id:
                    user_id = "00000000-0000-0000-0000-000000000001" if email_clean == "loharavee@gmail.com" else str(uuid.uuid4())
                pwd = udata.get("password") or "Sarala@123"
                doc = {
                    "id": user_id,
                    "email": email_clean,
                    "password_hash": hash_password(pwd),
                    "name": full_name,
                    "nickname": nickname,
                    "role": role,
                    "is_active": udata.get("is_active", True),
                    "is_naveen": (email_clean == "loharavee@gmail.com" or role == "admin"),
                    "created_at": "2026-09-29T00:00:00Z",
                    "updated_at": "2026-09-30T00:00:00Z",
                }
                mongodb_manager.users.insert_one(doc)
                results["migrated_to_mongo"] += 1
                logger.info(f"Migrated user to MongoDB: {email_clean} ({user_id})")
            else:
                user_id = existing.get("id") or str(existing.get("_id"))
                results["skipped"] += 1
        else:
            if not user_id:
                user_id = "00000000-0000-0000-0000-000000000001" if email_clean == "loharavee@gmail.com" else f"user_{abs(hash(email_clean))}"

        # 2. Supabase Profile and Preferences sync
        try:
            profile_service.sync_login(
                user_id=user_id,
                email=email_clean,
                role=role,
                full_name=full_name,
                nickname=nickname,
                is_active=udata.get("is_active", True),
            )
            preferences_service.init_default_preferences(user_id)
            results["migrated_to_supabase"] += 1
        except Exception as e:
            logger.warning(f"Error syncing {email_clean} to Supabase: {e}")
            results["errors"].append(f"{email_clean}: {e}")

    return results


def migrate_memory(memory_filepath: str, default_admin_id: str = "00000000-0000-0000-0000-000000000001") -> Dict[str, Any]:
    """Migrates legacy global memory.json into Supabase user-scoped memories table."""
    results = {"total_keys": 0, "migrated": 0, "errors": []}

    if not os.path.exists(memory_filepath):
        logger.warning(f"File not found: {memory_filepath}")
        return results

    try:
        with open(memory_filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read {memory_filepath}: {e}")
        results["errors"].append(str(e))
        return results

    results["total_keys"] = len(data)
    logger.info(f"Auditing {len(data)} memory keys from {memory_filepath} (Target User: {default_admin_id})...")

    for k, v in data.items():
        try:
            # Flatten lists or dicts to readable strings
            val_str = json.dumps(v) if isinstance(v, (list, dict)) else str(v)
            memory_service.set_memory(
                user_id=default_admin_id,
                memory_key=str(k),
                memory_value=val_str,
                memory_type="personal",
                source="legacy_memory_json",
            )
            results["migrated"] += 1
            logger.info(f"Migrated memory key '{k}' -> user '{default_admin_id}'")
        except Exception as e:
            logger.error(f"Error migrating memory key '{k}': {e}")
            results["errors"].append(f"{k}: {e}")

    return results


def run_migration():
    logger.info("==================================================")
    logger.info("STARTING DUAL DATABASE LEGACY DATA MIGRATION")
    logger.info("==================================================")

    users_file = os.path.join(backend_dir, "users.json")
    memory_file = os.path.join(backend_dir, "memory.json")

    user_stats = migrate_users(users_file)
    logger.info(f"User Migration Results: {user_stats}")

    memory_stats = migrate_memory(memory_file)
    logger.info(f"Memory Migration Results: {memory_stats}")

    logger.info("==================================================")
    logger.info("MIGRATION COMPLETED SUCCESSFULLY")
    logger.info("Note: Original users.json and memory.json were preserved.")
    logger.info("==================================================")


if __name__ == "__main__":
    run_migration()
