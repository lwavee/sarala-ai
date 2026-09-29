import json
import os
import time
import logging
from typing import Dict, Any, Optional, List, cast
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Try to import supabase
try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv()

# Legacy profile cache fallback (no passwords stored)
DEFAULT_USERS = {
    "loharavee@gmail.com": {
        "name": "Naveen",
        "nickname": "avee",
        "email": "loharavee@gmail.com",
        "role": "admin",
        "is_naveen": True
    }
}

class MemoryStorage:
    """
    Handles:
    - User Profiles & Supabase Auth integration
    - Long-term personal memory: saved permanently to Supabase (fallback to memory.json)
    - Short-term chat memory: auto-deletes entries older than 24 hours
    """
    def __init__(self, filepath="memory.json", users_filepath="users.json", max_history=20):
        backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if not os.path.isabs(filepath):
            filepath = os.path.join(backend_root, filepath)
        if not os.path.isabs(users_filepath):
            users_filepath = os.path.join(backend_root, users_filepath)
        self.filepath = filepath
        self.users_filepath = users_filepath
        self.max_history = max_history
        self.data = {}          # Long-term personal memory cache
        self.users = {}         # Registered users cache
        self.chat_history = []  # Short-term in-memory conversation log
        self.supabase = None
        
        supabase_url = os.environ.get("SUPABASE_URL", "").strip().strip('"').strip("'")
        supabase_key = os.environ.get("SUPABASE_KEY", "").strip().strip('"').strip("'")
        
        self.use_supabase = (
            HAS_SUPABASE and 
            supabase_url and 
            supabase_key and 
            "your_supabase" not in supabase_url
        )
        
        if self.use_supabase:
            try:
                self.supabase = create_client(supabase_url, supabase_key)
                logger.info("Supabase client initialized for MemoryStorage.")
            except Exception as e:
                logger.error(f"Failed to initialize Supabase: {e}")
                self.use_supabase = False
                
        self.load()
        self.load_users()

    # ---- User Accounts & Authentication ----
    def load_users(self):
        self.users = dict(DEFAULT_USERS)
        if os.path.exists(self.users_filepath):
            try:
                with open(self.users_filepath, "r", encoding="utf-8") as f:
                    saved_users = json.load(f)
                    # Strip any legacy passwords from memory
                    for u in saved_users.values():
                        if isinstance(u, dict) and "password" in u:
                            del u["password"]
                    self.users.update(saved_users)
            except Exception as e:
                logger.error(f"Failed to load users: {e}")

    def save_users(self):
        try:
            # Strip passwords before saving to disk
            clean_users = {}
            for k, u in self.users.items():
                if isinstance(u, dict):
                    clean_u = dict(u)
                    clean_u.pop("password", None)
                    clean_users[k] = clean_u
            with open(self.users_filepath, "w", encoding="utf-8") as f:
                json.dump(clean_users, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save users: {e}")

    def authenticate_user(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticates user via official Supabase Auth. Never compares passwords locally."""
        email_clean = email.strip().lower()

        if self.use_supabase and self.supabase:
            try:
                res = self.supabase.auth.sign_in_with_password(cast(Any, {
                    "email": email_clean,
                    "password": password
                }))
                if res and hasattr(res, "user") and res.user:
                    user_id = str(res.user.id)
                    # Fetch profile from profiles table
                    tbl = self.supabase.table("profiles")
                    prof_res = tbl.select("*").eq("id", user_id).execute()
                    p: Dict[str, Any] = {}
                    if prof_res and isinstance(prof_res.data, list) and len(prof_res.data) > 0:
                        first_row = prof_res.data[0]
                        if isinstance(first_row, dict):
                            p = cast(Dict[str, Any], first_row)

                    user_meta: Dict[str, Any] = getattr(res.user, "user_metadata", {}) or {}
                    if not isinstance(user_meta, dict):
                        user_meta = {}

                    role = p.get("role") or "user"
                    full_name = p.get("full_name") or user_meta.get("full_name") or "User"
                    nickname = p.get("nickname") or user_meta.get("nickname") or ""
                    is_active = p.get("is_active", True)

                    token = res.session.access_token if hasattr(res, "session") and res.session else None

                    return {
                        "success": True,
                        "token": token,
                        "user": {
                            "id": user_id,
                            "name": full_name,
                            "nickname": nickname,
                            "email": email_clean,
                            "role": role,
                            "is_active": is_active
                        }
                    }
            except Exception as e:
                logger.warning(f"Supabase auth failed: {e}")
                return {"success": False, "message": "Invalid email or password"}

        return {"success": False, "message": "Authentication service unavailable. Please check Supabase configuration."}

    def register_user(self, name: str, nickname: str, email: str, password: str, role: str = "user") -> Dict[str, Any]:
        """Registers user via official Supabase Auth. Default role is always 'user'."""
        email_clean = email.strip().lower()

        if self.use_supabase and self.supabase:
            try:
                clean_name = name.strip().title()
                clean_nick = nickname.strip().lower()
                res = self.supabase.auth.sign_up(cast(Any, {
                    "email": email_clean,
                    "password": password,
                    "options": {
                        "data": {
                            "full_name": clean_name,
                            "nickname": clean_nick
                        }
                    }
                }))
                if res and hasattr(res, "user") and res.user:
                    user_id = str(res.user.id)
                    # Ensure profile exists with role = 'user'
                    tbl = self.supabase.table("profiles")
                    tbl.upsert({
                        "id": user_id,
                        "email": email_clean,
                        "full_name": clean_name,
                        "nickname": clean_nick,
                        "role": "user",  # NEVER automatically grant admin
                        "is_active": True
                    }).execute()

                    return {
                        "success": True,
                        "user": {
                            "id": user_id,
                            "name": clean_name,
                            "nickname": clean_nick,
                            "email": email_clean,
                            "role": "user",
                            "is_active": True
                        }
                    }
            except Exception as e:
                logger.error(f"Supabase user registration failed: {e}")
                return {"success": False, "message": str(e)}

        return {"success": False, "message": "Registration service unavailable. Please check Supabase configuration."}

    # ---- Permanent Personal Memory (Supabase) ----
    def load(self):
        if self.use_supabase and self.supabase:
            try:
                tbl = self.supabase.table("memories") if hasattr(self.supabase, "table") else None
                if tbl is not None:
                    response = tbl.select("*").execute()
                    if response and isinstance(response.data, list):
                        for row in response.data:
                            if isinstance(row, dict) and "key" in row and "value" in row:
                                self.data[str(row["key"])] = row["value"]
                        logger.info(f"Loaded {len(self.data)} permanent memories from Supabase.")
                        return
            except Exception as e:
                logger.error(f"Failed to load from Supabase, falling back to local memory.json: {e}")
                
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {}

    def save(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving memory.json: {e}")

    def remember(self, key, value):
        """Save a long-term personal fact permanently (e.g. user_name = 'Naveen')"""
        self.data[key] = value
        
        if self.use_supabase and self.supabase:
            try:
                tbl = self.supabase.table("memories") if hasattr(self.supabase, "table") else None
                if tbl is not None:
                    tbl.upsert({"key": key, "value": str(value)}).execute()
                    logger.info(f"Saved memory '{key}' permanently to Supabase.")
            except Exception as e:
                logger.error(f"Failed to save memory to Supabase: {e}")
                
        self.save()

    def recall(self, key):
        return self.data.get(key, None)

    def get_all_facts(self) -> str:
        if not self.data:
            return ""
        lines = [f"{k}: {v}" for k, v in self.data.items()]
        return "Known personal facts: " + ", ".join(lines)

    # ---- Temporary Chat Memory (Auto-deletes after 24 hours) ----
    def _purge_expired_history(self):
        now = time.time()
        twenty_four_hours = 86400
        self.chat_history = [
            m for m in self.chat_history 
            if now - m.get("timestamp", now) < twenty_four_hours
        ]

    def add_to_history(self, role: str, text: str):
        self._purge_expired_history()
        self.chat_history.append({"role": role, "text": text, "timestamp": time.time()})
        if len(self.chat_history) > self.max_history:
            self.chat_history = self.chat_history[-self.max_history:]

    def get_history_context(self) -> str:
        self._purge_expired_history()
        if not self.chat_history:
            return ""
        lines = [f"{m['role'].capitalize()}: {m['text']}" for m in self.chat_history]
        return "\n".join(lines)
