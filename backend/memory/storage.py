import json
import os
import time
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Try to import supabase, but don't fail if not installed yet
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
        "is_naveen": True
    }
}

class MemoryStorage:
    """
    Handles:
    - User Authentication & Profiles (Naveen pre-seeded + new signups)
    - Long-term personal memory: saved permanently to Supabase (fallback to memory.json)
    - Short-term chat memory: auto-deletes entries older than 24 hours
    """
    def __init__(self, filepath="memory.json", users_filepath="users.json", max_history=10):
        self.filepath = filepath
        self.users_filepath = users_filepath
        self.max_history = max_history
        self.data = {}          # Long-term personal memory cache
        self.users = {}         # Registered users cache
        self.chat_history = []  # Short-term in-memory conversation log
        self.supabase = None
        
        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_KEY", "")
        
        self.use_supabase = (
            HAS_SUPABASE and 
            supabase_url and 
            supabase_key and 
            supabase_url != "your_supabase_url_here" and 
            supabase_key != "your_supabase_anon_key_here"
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
                with open(self.users_filepath, "r") as f:
                    saved_users = json.load(f)
                    self.users.update(saved_users)
            except Exception as e:
                logger.error(f"Failed to load users: {e}")

    def save_users(self):
        try:
            with open(self.users_filepath, "w") as f:
                json.dump(self.users, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save users: {e}")

    def authenticate_user(self, email: str, password: str):
        email_clean = email.strip().lower()
        user = self.users.get(email_clean)
        if user and user.get("password") == password:
            is_naveen = (email_clean == "loharavee@gmail.com" or user.get("name", "").lower() == "naveen")
            return {
                "success": True,
                "user": {
                    "name": user.get("name", "User"),
                    "nickname": user.get("nickname", ""),
                    "email": email_clean,
                    "is_naveen": is_naveen
                }
            }
        return {"success": False, "message": "Invalid email or password"}

    def register_user(self, name: str, nickname: str, email: str, password: str):
        email_clean = email.strip().lower()
        if email_clean in self.users:
            return {"success": False, "message": "Email is already registered"}
        
        is_naveen = (email_clean == "loharavee@gmail.com" or name.strip().lower() == "naveen")
        new_user = {
            "name": name.strip().title(),
            "nickname": nickname.strip().lower(),
            "email": email_clean,
            "password": password,
            "is_naveen": is_naveen
        }
        self.users[email_clean] = new_user
        self.save_users()

        if self.use_supabase:
            try:
                self.supabase.table("users").upsert(new_user).execute()
            except Exception as e:
                logger.error(f"Failed to save new user to Supabase: {e}")

        return {
            "success": True,
            "user": {
                "name": new_user["name"],
                "nickname": new_user["nickname"],
                "email": email_clean,
                "is_naveen": is_naveen
            }
        }

    # ---- Permanent Personal Memory (Supabase) ----
    def load(self):
        if self.use_supabase:
            try:
                response = self.supabase.table("memories").select("*").execute()
                for row in response.data:
                    self.data[row["key"]] = row["value"]
                logger.info(f"Loaded {len(self.data)} permanent memories from Supabase.")
                return
            except Exception as e:
                logger.error(f"Failed to load from Supabase, falling back to local memory.json: {e}")
                self.use_supabase = False
                
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {}

    def save(self):
        with open(self.filepath, "w") as f:
            json.dump(self.data, f, indent=4)

    def remember(self, key, value):
        """Save a long-term personal fact permanently (e.g. user_name = 'Naveen')"""
        self.data[key] = value
        
        if self.use_supabase:
            try:
                self.supabase.table("memories").upsert({"key": key, "value": value}).execute()
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
