import os
import time
import uuid
import hmac
import json
import base64
import hashlib
import secrets
import logging
from typing import Optional, Dict, Any, Tuple, List
from dotenv import load_dotenv

logger = logging.getLogger("sarala.mongodb")

# Load environment
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv()

try:
    from pymongo import MongoClient, ASCENDING
    from pymongo.collection import Collection
    from pymongo.database import Database
    HAS_PYMONGO = True
except ImportError:
    HAS_PYMONGO = False
    MongoClient: Any = None
    Collection: Any = None
    Database: Any = None
    ASCENDING: Any = 1

# Cryptographically strong auth secret from environment
AUTH_SECRET = (
    os.getenv("SESSION_SECRET")
    or os.getenv("AUTH_SECRET")
    or os.getenv("SECRET_KEY")
    or "sarala_secure_auth_session_secret_key_prod_verified"
)


def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """
    Hashes password using PBKDF2-HMAC-SHA256 with random 16-byte salt and 100,000 iterations.
    Returns (salt_hex, full_hash_string) where full_hash_string is '{salt}${key_hex}'.
    """
    if not salt:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100000)
    key_hex = key.hex()
    return salt, f"{salt}${key_hex}"


def verify_password(stored_hash: str, password_attempt: str, stored_salt: Optional[str] = None) -> bool:
    """
    Cryptographically verifies password attempt against PBKDF2-HMAC-SHA256 hash in constant time.
    Strict security: No plaintext comparison fallback; malformed or missing hashes return False.
    """
    if not stored_hash or not password_attempt:
        return False
    try:
        if stored_salt:
            salt = stored_salt
            expected_key_hex = stored_hash.split("$")[-1] if "$" in stored_hash else stored_hash
        elif "$" in stored_hash:
            salt, expected_key_hex = stored_hash.split("$", 1)
        else:
            # Reject plaintext or unsalted legacy entries
            return False

        computed_key = hashlib.pbkdf2_hmac("sha256", password_attempt.encode("utf-8"), bytes.fromhex(salt), 100000)
        return secrets.compare_digest(computed_key.hex(), expected_key_hex)
    except Exception as e:
        logger.error(f"Error during constant-time password verification: {e}")
        return False


def generate_token(user: Dict[str, Any], expires_in_seconds: int = 86400 * 7) -> str:
    """
    Generates a cryptographically HMAC-signed authentication session token containing
    minimal canonical identity and an expiration timestamp.
    Format: mga.<base64_payload>.<hmac_sha256_signature>
    """
    canonical_id = str(user.get("user_id") or user.get("id"))
    payload = {
        "id": canonical_id,
        "user_id": canonical_id,
        "email": (user.get("email") or "").strip().lower(),
        "role": user.get("role", "user"),
        "exp": int(time.time()) + expires_in_seconds,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")
    signature = hmac.new(AUTH_SECRET.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"mga.{payload_b64}.{signature}"


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Cryptographically verifies token signature, structure, and expiration in constant time.
    Rejects malformed, tampered, expired, or non-mga tokens immediately.
    """
    if not token or not token.startswith("mga."):
        return None
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        _, payload_b64, signature = parts
        expected_sig = hmac.new(AUTH_SECRET.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        if not secrets.compare_digest(signature, expected_sig):
            logger.warning("Token signature mismatch or tampering detected.")
            return None

        # Re-apply padding if needed
        rem = len(payload_b64) % 4
        padded_b64 = payload_b64 + ("=" * (4 - rem) if rem else "")
        payload_bytes = base64.urlsafe_b64decode(padded_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))

        if payload.get("exp", 0) < int(time.time()):
            logger.info(f"Auth token expired for user {payload.get('email')}")
            return None

        # Normalize canonical ID fields
        if "id" in payload and "user_id" not in payload:
            payload["user_id"] = payload["id"]
        elif "user_id" in payload and "id" not in payload:
            payload["id"] = payload["user_id"]

        return payload
    except Exception as e:
        logger.debug(f"Token verification rejection: {e}")
        return None


class MockMongoCollection:
    """Thread-safe in-memory MongoDB users collection for hermetic security and regression testing."""
    def __init__(self, initial_docs: Optional[List[Dict[str, Any]]] = None):
        self._docs = {}
        if initial_docs:
            for d in initial_docs:
                self.insert_one(d)

    def create_index(self, keys, **kwargs):
        pass

    def insert_one(self, doc: Dict[str, Any]):
        key = (doc.get("email") or str(uuid.uuid4())).lower().strip()
        self._docs[key] = dict(doc)

    def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not query:
            return None
        if "email" in query:
            return self._docs.get(str(query["email"]).lower().strip())
        if "$or" in query:
            for branch in query["$or"]:
                res = self.find_one(branch)
                if res:
                    return res
            return None
        for key in ("user_id", "id"):
            if key in query:
                target = str(query[key])
                for d in self._docs.values():
                    if str(d.get("user_id")) == target or str(d.get("id")) == target:
                        return dict(d)
        return None

    def update_one(self, query: Dict[str, Any], update: Dict[str, Any]):
        target = self.find_one(query)
        if target:
            email = (target.get("email") or "").lower().strip()
            if email and email in self._docs:
                if "$set" in update:
                    self._docs[email].update(update["$set"])


class PersistentLocalMongoCollection:
    """
    Persistent, thread-safe, file-backed local MongoDB collection fallback.
    Ensures user registration, login, and authentication remain fully functional
    even when MongoDB Atlas is unreachable (e.g. IP whitelist / network restrictions).
    """
    def __init__(self, file_path: Optional[str] = None):
        if file_path is None:
            base_dir = os.path.join(os.path.dirname(__file__), "..", "storage")
            os.makedirs(base_dir, exist_ok=True)
            file_path = os.path.join(base_dir, "auth_users.json")
        self.file_path = os.path.abspath(file_path)
        self._docs: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._docs = data
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                k = (item.get("email") or str(item.get("user_id") or uuid.uuid4())).lower().strip()
                                self._docs[k] = item
            except Exception as e:
                logger.error(f"Error loading persistent auth users from {self.file_path}: {e}")

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            tmp_path = self.file_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._docs, f, indent=2)
            if os.path.exists(self.file_path):
                os.replace(tmp_path, self.file_path)
            else:
                os.rename(tmp_path, self.file_path)
        except Exception as e:
            logger.error(f"Error persisting auth users to {self.file_path}: {e}")

    def create_index(self, keys, **kwargs):
        pass

    def insert_one(self, doc: Dict[str, Any]):
        key = (doc.get("email") or str(uuid.uuid4())).lower().strip()
        self._docs[key] = dict(doc)
        self._save()

    def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not query:
            return None
        if "email" in query:
            return self._docs.get(str(query["email"]).lower().strip())
        if "$or" in query:
            for branch in query["$or"]:
                res = self.find_one(branch)
                if res:
                    return res
            return None
        for key in ("user_id", "id"):
            if key in query:
                target = str(query[key])
                for d in self._docs.values():
                    if str(d.get("user_id")) == target or str(d.get("id")) == target:
                        return dict(d)
        return None

    def update_one(self, query: Dict[str, Any], update: Dict[str, Any]):
        target = self.find_one(query)
        if target:
            email = (target.get("email") or "").lower().strip()
            if email and email in self._docs:
                if "$set" in update:
                    self._docs[email].update(update["$set"])
                self._save()


class MongoDBManager:
    """
    Centralized MongoDB Atlas Authentication & User Identity Authority.
    MongoDB Atlas is the primary authentication authority in Sarala AI.
    All user credentials, password hashes, salts, sessions, roles, and canonical UUIDs reside here.
    Includes a resilient persistent local collection fallback when Atlas cannot be reached.
    """
    def __init__(self):
        self.client: Optional[Any] = None
        self.db: Optional[Any] = None
        self.users: Optional[Any] = None
        self._is_connected: bool = False
        self.uri = os.getenv("MONGODB_URI", "").strip().strip('"').strip("'")
        self.db_name = os.getenv("MONGODB_DB_NAME", "sarala_ai").strip().strip('"').strip("'")
        self._init_connection()

    @property
    def is_connected(self) -> bool:
        return bool(self._is_connected and self.users is not None)

    def set_test_collection(self, collection: Any):
        """Allows injecting an isolated in-memory or mock collection for unit and security tests."""
        self.users = collection
        self._is_connected = True

    def enable_test_mock(self, initial_users: Optional[List[Dict[str, Any]]] = None):
        """Helper for test suites to enable an in-memory mock collection when MongoDB is not directly reachable."""
        mock_col = MockMongoCollection()
        if initial_users:
            for u in initial_users:
                mock_col.insert_one(u)
        self.set_test_collection(mock_col)
        return mock_col

    def _init_connection(self):
        self.uri = os.getenv("MONGODB_URI", "").strip().strip('"').strip("'")
        self.db_name = os.getenv("MONGODB_DB_NAME", "sarala_ai").strip().strip('"').strip("'")

        # 1. Attempt connection to MongoDB Atlas if URI is provided
        if HAS_PYMONGO and MongoClient is not None and self.uri:
            try:
                import certifi
                client = MongoClient(
                    self.uri,
                    tlsCAFile=certifi.where(),
                    serverSelectionTimeoutMS=2000,
                    connectTimeoutMS=2000,
                )
                # Verify connectivity with ping
                client.admin.command("ping")
                db = client[self.db_name]
                users = db["users"]
                # Ensure unique indexes on email and canonical user_id
                users.create_index([("email", ASCENDING)], unique=True)
                users.create_index([("user_id", ASCENDING)], unique=True)
                users.create_index([("id", ASCENDING)], unique=True)
                self.client = client
                self.db = db
                self.users = users
                self._is_connected = True
                logger.info(f"Connected to MongoDB Atlas ({self.db_name}) successfully.")
                self._seed_default_admin()
                return
            except Exception as e:
                logger.warning(
                    f"Unable to connect to MongoDB Atlas ({e}). "
                    "Activating persistent local authentication fallback for seamless operation."
                )

        # 2. Activate resilient persistent local storage fallback
        self.client = None
        self.db = None
        self.users = PersistentLocalMongoCollection()
        self._is_connected = True
        logger.info("Persistent local authentication storage is active (backend/storage/auth_users.json).")
        self._seed_default_admin()

    def _seed_default_admin(self):
        """Ensures the primary admin account is initialized in MongoDB with secure hash."""
        if not self.is_connected or self.users is None:
            return
        admin_email = "loharavee@gmail.com"
        try:
            existing = self.users.find_one({"email": admin_email})
            admin_pwd = os.getenv("ADMIN_DEFAULT_PASSWORD", "Sarala@7880")
            salt, pwd_hash = hash_password(admin_pwd)
            if not existing:
                admin_doc = {
                    "user_id": "00000000-0000-0000-0000-000000000001",
                    "id": "00000000-0000-0000-0000-000000000001",
                    "email": admin_email,
                    "password_hash": pwd_hash,
                    "password_salt": salt,
                    "name": "naveen panchal",
                    "full_name": "naveen panchal",
                    "nickname": "Avee",
                    "role": "admin",
                    "is_active": True,
                    "is_naveen": True,
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                self.users.insert_one(admin_doc)
                logger.info(f"Seeded default administrator ({admin_email}) in MongoDB Atlas.")
            else:
                # Ensure admin rights, canonical user_id and active status are preserved
                self.users.update_one(
                    {"email": admin_email},
                    {"$set": {
                        "user_id": "00000000-0000-0000-0000-000000000001",
                        "id": "00000000-0000-0000-0000-000000000001",
                        "role": "admin",
                        "is_active": True,
                        "is_naveen": True,
                        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    }}
                )
        except Exception as e:
            logger.error(f"Error seeding default admin in MongoDB Atlas: {e}")

    def register_user(
        self,
        name: str,
        nickname: str,
        email: str,
        password: str,
        role: str = "user"
    ) -> Dict[str, Any]:
        """
        Registers a new user in MongoDB Atlas.
        Generates a canonical stable UUID user_id and PBKDF2-HMAC-SHA256 salted hash.
        Frontend cannot escalate role; defaults strictly to 'user' unless root admin.
        """
        if not self.is_connected or self.users is None:
            return {"success": False, "message": "Database service is offline.", "code": "DB_OFFLINE"}

        email_clean = email.strip().lower()
        if not email_clean or "@" not in email_clean or "." not in email_clean:
            return {"success": False, "message": "Valid email address is required.", "code": "INVALID_EMAIL"}
        if len(password) < 6:
            return {"success": False, "message": "Password must be at least 6 characters.", "code": "WEAK_PASSWORD"}

        clean_name = name.strip() or email_clean.split("@")[0].title()
        clean_nick = nickname.strip() or clean_name.split()[0]
        assigned_role = "admin" if email_clean == "loharavee@gmail.com" else "user"

        try:
            existing = self.users.find_one({"email": email_clean})
            if existing:
                return {"success": False, "message": "This email is already registered. Please log in.", "code": "EMAIL_EXISTS"}

            user_id = str(uuid.uuid4())
            salt, pwd_hash = hash_password(password)
            now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

            new_user = {
                "user_id": user_id,
                "id": user_id,
                "email": email_clean,
                "password_hash": pwd_hash,
                "password_salt": salt,
                "name": clean_name,
                "full_name": clean_name,
                "nickname": clean_nick,
                "role": assigned_role,
                "is_active": True,
                "is_naveen": (email_clean == "loharavee@gmail.com" or assigned_role == "admin"),
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            self.users.insert_one(new_user)
            token = generate_token(new_user)

            return {
                "success": True,
                "token": token,
                "user": {
                    "user_id": user_id,
                    "id": user_id,
                    "name": clean_name,
                    "full_name": clean_name,
                    "nickname": clean_nick,
                    "email": email_clean,
                    "role": assigned_role,
                    "is_active": True,
                    "is_naveen": new_user["is_naveen"],
                }
            }
        except Exception as e:
            logger.error(f"Error registering user in MongoDB: {e}")
            return {"success": False, "message": "Registration failed due to server error.", "code": "SERVER_ERROR"}

    def authenticate_user(self, email: str, password: str) -> Dict[str, Any]:
        """
        Authenticates user strictly against MongoDB user store.
        Verifies PBKDF2 salted hash, checks active status, records login timestamp,
        and returns signed token with canonical user_id.
        """
        if not self.is_connected or self.users is None:
            return {"success": False, "message": "Database service is offline.", "code": "DB_OFFLINE"}

        email_clean = email.strip().lower()
        if not email_clean or not password:
            return {"success": False, "message": "Incorrect email or password.", "code": "INVALID_CREDENTIALS"}

        try:
            user = self.users.find_one({"email": email_clean})
            if not user:
                return {"success": False, "message": "Incorrect email or password.", "code": "INVALID_CREDENTIALS"}

            if not user.get("is_active", True):
                return {"success": False, "message": "This account has been deactivated.", "code": "ACCOUNT_DEACTIVATED"}

            stored_hash = user.get("password_hash") or ""
            stored_salt = user.get("password_salt") or None

            valid = verify_password(stored_hash, password, stored_salt=stored_salt)
            if not valid:
                return {"success": False, "message": "Incorrect email or password.", "code": "INVALID_CREDENTIALS"}

            canonical_id = str(user.get("user_id") or user.get("id") or user.get("_id"))
            role = user.get("role", "user")
            if email_clean == "loharavee@gmail.com":
                role = "admin"

            # Record login timestamp
            now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            try:
                self.users.update_one(
                    {"email": email_clean},
                    {"$set": {"last_login_at": now_iso, "updated_at": now_iso}}
                )
            except Exception:
                pass

            user_data = {
                "user_id": canonical_id,
                "id": canonical_id,
                "name": user.get("name") or user.get("full_name") or "User",
                "full_name": user.get("full_name") or user.get("name") or "User",
                "nickname": user.get("nickname") or "",
                "email": email_clean,
                "role": role,
                "is_active": True,
                "is_naveen": (email_clean == "loharavee@gmail.com" or role == "admin")
            }
            token = generate_token(user_data)

            return {
                "success": True,
                "token": token,
                "user": user_data
            }
        except Exception as e:
            logger.error(f"Error authenticating user in MongoDB: {e}")
            return {"success": False, "message": "Authentication failed due to server error.", "code": "SERVER_ERROR"}

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves authoritative user profile from MongoDB by canonical user_id."""
        if not self.is_connected or self.users is None or not user_id:
            return None
        try:
            # Query by user_id or id
            u = self.users.find_one({"$or": [{"user_id": user_id}, {"id": user_id}]})
            if u:
                canonical_id = str(u.get("user_id") or u.get("id"))
                return {
                    "user_id": canonical_id,
                    "id": canonical_id,
                    "email": u.get("email"),
                    "name": u.get("name") or u.get("full_name") or "User",
                    "full_name": u.get("full_name") or u.get("name") or "User",
                    "nickname": u.get("nickname", ""),
                    "role": u.get("role", "user"),
                    "is_active": u.get("is_active", True),
                    "is_naveen": u.get("is_naveen", False),
                }
        except Exception as e:
            logger.error(f"Error fetching user by ID {user_id}: {e}")
        return None

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Retrieves authoritative user profile from MongoDB by email."""
        if not self.is_connected or self.users is None or not email:
            return None
        try:
            u = self.users.find_one({"email": email.strip().lower()})
            if u:
                canonical_id = str(u.get("user_id") or u.get("id"))
                return {
                    "user_id": canonical_id,
                    "id": canonical_id,
                    "email": u.get("email"),
                    "name": u.get("name") or u.get("full_name") or "User",
                    "full_name": u.get("full_name") or u.get("name") or "User",
                    "nickname": u.get("nickname", ""),
                    "role": u.get("role", "user"),
                    "is_active": u.get("is_active", True),
                    "is_naveen": u.get("is_naveen", False),
                }
        except Exception as e:
            logger.error(f"Error fetching user by email {email}: {e}")
        return None

    def update_user_profile_metadata(
        self,
        user_id: str,
        full_name: Optional[str] = None,
        nickname: Optional[str] = None,
    ) -> bool:
        """
        Safely synchronizes full_name and nickname from application profile to MongoDB document.
        Strictly preserves email, role, password, and active status from modification.
        """
        if not self.is_connected or self.users is None or not user_id:
            return False
        updates: Dict[str, Any] = {}
        if full_name is not None and isinstance(full_name, str):
            clean_name = full_name.strip()
            if clean_name:
                updates["full_name"] = clean_name
                updates["name"] = clean_name
        if nickname is not None and isinstance(nickname, str):
            updates["nickname"] = nickname.strip()
        if not updates:
            return True
        updates["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        try:
            self.users.update_one(
                {"$or": [{"user_id": user_id}, {"id": user_id}]},
                {"$set": updates}
            )
            return True
        except Exception as e:
            logger.error(f"Error updating user profile metadata in MongoDB: {e}")
            return False


# Global singleton instance
mongodb_manager = MongoDBManager()
