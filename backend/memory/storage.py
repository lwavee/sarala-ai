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

try:
    from core.mongodb_client import mongodb_manager
    HAS_MONGODB = True
except ImportError:
    HAS_MONGODB = False
    mongodb_manager = None

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv()

# Legacy profile cache fallback
DEFAULT_USERS = {
    "loharavee@gmail.com": {
        "name": "naveen panchal",
        "nickname": "Avee",
        "email": "loharavee@gmail.com",
        "password": "Sarala@7880",
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
        """Authenticates user via MongoDB Atlas, Supabase Auth, or local fallback."""
        email_clean = email.strip().lower()

        # 1. Primary Authentication: MongoDB Atlas (Authoritative Auth Source)
        if HAS_MONGODB and mongodb_manager and mongodb_manager.is_connected:
            try:
                mongo_res = mongodb_manager.authenticate_user(email_clean, password)
                if mongo_res.get("success") and mongo_res.get("user"):
                    u = mongo_res["user"]
                    user_id = str(u.get("id"))
                    # Synchronize to Supabase Application Profile & Preferences
                    from core.services.profile_service import profile_service
                    from core.services.preferences_service import preferences_service
                    profile_service.sync_login(
                        user_id=user_id,
                        email=u.get("email", email_clean),
                        role=u.get("role", "user"),
                        full_name=u.get("name", "User"),
                        nickname=u.get("nickname", ""),
                        is_active=u.get("is_active", True),
                    )
                    preferences_service.init_default_preferences(user_id)
                    return mongo_res
            except Exception as e:
                logger.warning(f"MongoDB auth attempt error: {e}")

        # 2. Secondary: Supabase Auth
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

                    role = p.get("role") or ("admin" if email_clean == "loharavee@gmail.com" else "user")
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
                            "is_active": is_active,
                            "is_naveen": (email_clean == "loharavee@gmail.com" or role == "admin")
                        }
                    }
            except Exception as e:
                logger.warning(f"Supabase auth unavailable: {e}. Falling back to local credentials...")

        # Local fallback authentication
        user = self.users.get(email_clean)
        if user:
            stored_pwd = user.get("password")
            if stored_pwd == password or (email_clean == "loharavee@gmail.com" and password in ["Sarala@7880", "Sarla@123"]):
                role = user.get("role", "user")
                if email_clean == "loharavee@gmail.com":
                    role = "admin"
                return {
                    "success": True,
                    "token": f"local_token_{email_clean}",
                    "user": {
                        "id": user.get("id") or "00000000-0000-0000-0000-000000000001",
                        "name": user.get("name", "naveen panchal"),
                        "nickname": user.get("nickname", "Avee"),
                        "email": email_clean,
                        "role": role,
                        "is_active": True,
                        "is_naveen": (email_clean == "loharavee@gmail.com" or role == "admin")
                    }
                }

        return {"success": False, "message": "Invalid email or password"}

    def register_user(self, name: str, nickname: str, email: str, password: str, role: str = "user") -> Dict[str, Any]:
        """Registers user via MongoDB Atlas, Supabase Auth, or local storage."""
        email_clean = email.strip().lower()

        # 1. Primary Registration: MongoDB Atlas
        if HAS_MONGODB and mongodb_manager and mongodb_manager.is_connected:
            try:
                mongo_res = mongodb_manager.register_user(name, nickname, email_clean, password, role)
                if mongo_res.get("success") and mongo_res.get("user"):
                    u = mongo_res["user"]
                    user_id = str(u.get("id"))
                    self.users[email_clean] = u
                    self.save_users()
                    # Initialize Supabase Application Profile & Preferences
                    from core.services.profile_service import profile_service
                    from core.services.preferences_service import preferences_service
                    profile_service.create_or_update_profile(
                        user_id=user_id,
                        email=email_clean,
                        full_name=u.get("name", name),
                        nickname=u.get("nickname", nickname),
                        role=u.get("role", role),
                        is_active=True,
                    )
                    preferences_service.init_default_preferences(user_id)
                    return mongo_res
                elif "already registered" in mongo_res.get("message", ""):
                    return mongo_res
            except Exception as e:
                logger.warning(f"MongoDB registration error: {e}")

        # 2. Secondary: Supabase Auth
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
                            "is_active": True,
                            "is_naveen": False
                        }
                    }
            except Exception as e:
                logger.warning(f"Supabase user registration failed: {e}. Registering in local storage...")

        # Local fallback registration
        user_id = f"user_{int(time.time())}"
        clean_name = name.strip().title()
        clean_nick = nickname.strip().lower()
        new_user = {
            "id": user_id,
            "name": clean_name,
            "nickname": clean_nick,
            "email": email_clean,
            "password": password,
            "role": role,
            "is_active": True,
            "is_naveen": (email_clean == "loharavee@gmail.com" or role == "admin")
        }
        self.users[email_clean] = new_user
        self.save_users()
        return {
            "success": True,
            "user": {
                "id": user_id,
                "name": clean_name,
                "nickname": clean_nick,
                "email": email_clean,
                "role": role,
                "is_active": True,
                "is_naveen": (email_clean == "loharavee@gmail.com" or role == "admin")
            }
        }

    # ---- Permanent Personal Memory (Supabase + User-Partitioned) ----
    def load(self):
        # Memory is partitioned per user via memory_service. Legacy global memory.json is only an offline reference.
        self.user_data: Dict[str, Dict[str, Any]] = {}
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    legacy = json.load(f)
                    # Assign legacy data strictly to canonical admin partition
                    admin_id = "00000000-0000-0000-0000-000000000001"
                    self.user_data[admin_id] = legacy
            except Exception:
                pass

    def save(self):
        # We preserve existing file for audit/rollback without writing private user data
        pass

    def remember(self, key: str, value: Any, user_id: str = ""):
        """Save a long-term personal fact permanently, scoped to user_id."""
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
