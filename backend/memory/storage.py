import json
import os
import time
import logging
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Try to import supabase for data storage
try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

try:
    from core.mongodb_client import mongodb_manager
    HAS_MONGODB = True
except ImportError:
    HAS_MONGODB = False
    mongodb_manager = None

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv()


class MemoryStorage:
    """
    Handles:
    - User Authentication: Strictly delegated to MongoDB Atlas (authoritative source of truth).
    - Long-term personal memory: saved permanently to Supabase (partitioned by user_id).
    - Short-term chat memory: auto-deletes entries older than 24 hours.
    All legacy local authentication (users.json, DEFAULT_USERS, plaintext credentials) has been decommissioned.
    """
    def __init__(self, filepath="memory.json", max_history=20):
        backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if not os.path.isabs(filepath):
            filepath = os.path.join(backend_root, filepath)
        self.filepath = filepath
        self.max_history = max_history
        self.data = {}          # Long-term personal memory cache
        self.chat_history = []  # Short-term in-memory conversation log
        self.supabase = None
        
        supabase_url = os.environ.get("SUPABASE_URL", "").strip().strip('"').strip("'")
        supabase_key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")).strip().strip('"').strip("'")
        
        self.use_supabase = (
            HAS_SUPABASE and 
            supabase_url and 
            supabase_key and 
            "your_supabase" not in supabase_url
        )
        
        if self.use_supabase:
            try:
                self.supabase = create_client(supabase_url, supabase_key)
                logger.info("Supabase client initialized for MemoryStorage data operations.")
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client in MemoryStorage: {e}")
                self.use_supabase = False
                
        self.load()

    # ---- User Accounts & Authentication (MongoDB Atlas Authority) ----
    def authenticate_user(self, email: str, password: str) -> Dict[str, Any]:
        """
        Authenticates user strictly via MongoDB Atlas.
        Zero fallback to Supabase Auth, local users.json, or hardcoded accounts.
        """
        email_clean = email.strip().lower()

        if not HAS_MONGODB or not mongodb_manager or not mongodb_manager.is_connected:
            return {
                "success": False,
                "message": "Database service is offline.",
                "code": "DB_OFFLINE"
            }

        mongo_res = mongodb_manager.authenticate_user(email_clean, password)
        if mongo_res.get("success") and mongo_res.get("user"):
            u = mongo_res["user"]
            user_id = str(u.get("user_id") or u.get("id"))
            # Synchronize to Supabase Application Profile & Preferences
            try:
                from core.services.profile_service import profile_service
                from core.services.preferences_service import preferences_service
                profile_service.sync_login(
                    user_id=user_id,
                    email=u.get("email", email_clean),
                    role=u.get("role", "user"),
                    full_name=u.get("full_name") or u.get("name") or "User",
                    nickname=u.get("nickname", ""),
                    is_active=u.get("is_active", True),
                )
                preferences_service.init_default_preferences(user_id)
            except Exception as e:
                logger.debug(f"Profile synchronization note: {e}")
            return mongo_res

        return mongo_res

    def register_user(self, name: str, nickname: str, email: str, password: str, role: str = "user") -> Dict[str, Any]:
        """
        Registers user strictly via MongoDB Atlas (the sole authentication authority).
        Zero fallback to Supabase Auth, local users.json, or mock accounts.
        """
        email_clean = email.strip().lower()

        if not HAS_MONGODB or not mongodb_manager or not mongodb_manager.is_connected:
            return {
                "success": False,
                "message": "Database service is offline.",
                "code": "DB_OFFLINE"
            }

        mongo_res = mongodb_manager.register_user(name, nickname, email_clean, password, role)
        if mongo_res.get("success") and mongo_res.get("user"):
            u = mongo_res["user"]
            user_id = str(u.get("user_id") or u.get("id"))
            try:
                from core.services.profile_service import profile_service
                from core.services.preferences_service import preferences_service
                profile_service.create_or_update_profile(
                    user_id=user_id,
                    email=email_clean,
                    full_name=u.get("full_name") or u.get("name") or name,
                    nickname=u.get("nickname") or nickname,
                    role=u.get("role", "user"),
                    is_active=True,
                )
                preferences_service.init_default_preferences(user_id)
            except Exception as e:
                logger.error(f"Error provisioning Supabase application profile for user {user_id}: {e}")
            return mongo_res

        return mongo_res

    # ---- Permanent Personal Memory (Supabase + User-Partitioned) ----
    def load(self):
        # Memory is partitioned per user via memory_service. Legacy global memory.json is only an offline reference.
        self.user_data: Dict[str, Dict[str, Any]] = {}
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    legacy = json.load(f)
                    admin_id = "00000000-0000-0000-0000-000000000001"
                    self.user_data[admin_id] = legacy
            except Exception:
                pass

    def save(self):
        # Preserves existing file for audit/rollback without writing private user data
        pass

    def remember(self, key: str, value: Any, user_id: str = ""):
        """Save a long-term personal fact permanently, scoped strictly to user_id."""
        target_user = user_id or "guest"
        if not hasattr(self, "user_data"):
            self.user_data = {}
        self.user_data.setdefault(target_user, {})[key] = value

        if user_id:
            try:
                from core.services.memory_service import memory_service
                memory_service.set_memory(user_id=user_id, memory_key=key, memory_value=str(value))
            except Exception as e:
                logger.debug(f"Failed to set user memory in service: {e}")

    def recall(self, key: str, user_id: str = ""):
        """Recall a personal fact strictly scoped to user_id."""
        if user_id:
            try:
                from core.services.memory_service import memory_service
                doc = memory_service.get_memory(user_id=user_id, identifier=key)
                if doc:
                    return doc.get("memory_value") or doc.get("value")
            except Exception as e:
                logger.debug(f"Failed to recall user memory from service: {e}")
            if hasattr(self, "user_data") and user_id in self.user_data:
                return self.user_data[user_id].get(key)
            return None

        # Guest partition only
        if hasattr(self, "user_data"):
            return self.user_data.get("guest", {}).get(key)
        return None

    def get_all_facts(self, user_id: str = "") -> str:
        """Returns personal facts belonging exclusively to the specified user_id."""
        if user_id:
            try:
                from core.services.memory_service import memory_service
                user_facts = memory_service.get_user_facts_string(user_id)
                if user_facts:
                    return user_facts
            except Exception as e:
                logger.debug(f"Failed to get user facts: {e}")
            if hasattr(self, "user_data") and user_id in self.user_data:
                lines = [f"{k}: {v}" for k, v in self.user_data[user_id].items()]
                return "Known user facts: " + ", ".join(lines) if lines else ""
            return ""

        # Guest mode
        if hasattr(self, "user_data"):
            guest_facts = self.user_data.get("guest", {})
            if guest_facts:
                lines = [f"{k}: {v}" for k, v in guest_facts.items()]
                return "Known user facts: " + ", ".join(lines)
        return ""

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
