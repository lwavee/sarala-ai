import json
import os
import time
import logging
from typing import Dict, Any, Optional, List
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

DEFAULT_USERS = {
    "loharavee@gmail.com": {
        "name": "Naveen",
        "nickname": "avee",
        "email": "loharavee@gmail.com",
        "password": "Sarla@123",
        "role": "admin",
        "is_naveen": True
    }
}

class MemoryStorage:
    """
    Handles:
    - User Authentication & Role Profiles (admin vs user)
    - Long-term personal memory: saved permanently to Supabase (fallback to memory.json)
    - Short-term chat memory: auto-deletes entries older than 24 hours
    """
    def __init__(self, filepath="memory.json", users_filepath="users.json", max_history=10):
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
                    self.users.update(saved_users)
            except Exception as e:
                logger.error(f"Failed to load users: {e}")

    def save_users(self):
        try:
            with open(self.users_filepath, "w", encoding="utf-8") as f:
                json.dump(self.users, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save users: {e}")

    def authenticate_user(self, email: str, password: str) -> Dict[str, Any]:
        email_clean = email.strip().lower()
        user = self.users.get(email_clean)

        # Check Supabase profiles if user not found locally
        if not user and self.use_supabase and self.supabase:
            try:
                tbl = self.supabase.table("profiles") if hasattr(self.supabase, "table") else None
                if tbl is not None:
                    res = tbl.select("*").eq("email", email_clean).execute()
                    if res and isinstance(res.data, list) and len(res.data) > 0:
                        p = res.data[0]
                        if isinstance(p, dict):
                            user = {
                                "name": p.get("full_name", "User"),
                                "nickname": p.get("nickname", ""),
                                "email": email_clean,
                                "password": password,
                                "role": p.get("role", "user"),
                                "is_naveen": (email_clean == "loharavee@gmail.com" or p.get("role") == "admin")
                            }
                            self.users[email_clean] = user
                            self.save_users()
            except Exception as e:
                logger.warning(f"Error checking profile in Supabase: {e}")

        if user and user.get("password") == password:
            role = user.get("role") or ("admin" if email_clean == "loharavee@gmail.com" else "user")
            is_naveen = (email_clean == "loharavee@gmail.com" or role == "admin")
            return {
                "success": True,
                "user": {
                    "name": user.get("name", "User"),
                    "nickname": user.get("nickname", ""),
                    "email": email_clean,
                    "role": role,
                    "is_naveen": is_naveen
                }
            }
        return {"success": False, "message": "Invalid email or password"}

    def register_user(self, name: str, nickname: str, email: str, password: str, role: str = "user") -> Dict[str, Any]:
        email_clean = email.strip().lower()
        if email_clean in self.users:
            return {"success": False, "message": "Email is already registered"}
        
        assigned_role = "admin" if email_clean == "loharavee@gmail.com" else role
        is_naveen = (email_clean == "loharavee@gmail.com" or assigned_role == "admin")
        new_user = {
            "name": name.strip().title(),
            "nickname": nickname.strip().lower(),
            "email": email_clean,
            "password": password,
            "role": assigned_role,
            "is_naveen": is_naveen
        }
        self.users[email_clean] = new_user
        self.save_users()

        if self.use_supabase and self.supabase:
            try:
                profile_record = {
                    "email": email_clean,
                    "role": assigned_role,
                    "full_name": new_user["name"],
                    "nickname": new_user["nickname"],
                    "is_active": True
                }
                tbl = self.supabase.table("profiles") if hasattr(self.supabase, "table") else None
                if tbl is not None:
                    tbl.upsert(profile_record).execute()
            except Exception as e:
                logger.error(f"Failed to save profile to Supabase: {e}")

        return {
            "success": True,
            "user": {
                "name": new_user["name"],
                "nickname": new_user["nickname"],
                "email": email_clean,
                "role": assigned_role,
                "is_naveen": is_naveen
            }
        }

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
