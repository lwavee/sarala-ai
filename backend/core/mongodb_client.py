import os
import time
import uuid
import hmac
import json
import base64
import hashlib
import secrets
import logging
from typing import Optional, Dict, Any
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

AUTH_SECRET = os.getenv("AUTH_SECRET", "sarala_mongo_auth_secret_key_7880")


def hash_password(password: str) -> str:
    """Hashes password using PBKDF2-HMAC-SHA256 with random 16-byte salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100000)
    return f"{salt}${key.hex()}"


def verify_password(stored_hash: str, password_attempt: str) -> bool:
    """Verifies password against PBKDF2 hash, with plaintext fallback for legacy support."""
    if not stored_hash:
        return False
    if "$" not in stored_hash:
        # Fallback to direct comparison if stored as plain
        return stored_hash == password_attempt
    try:
        salt, key_hex = stored_hash.split("$", 1)
        new_key = hashlib.pbkdf2_hmac("sha256", password_attempt.encode("utf-8"), bytes.fromhex(salt), 100000)
        return secrets.compare_digest(new_key.hex(), key_hex)
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False


def generate_token(user: Dict[str, Any], expires_in_seconds: int = 86400 * 7) -> str:
    """Generates a secure HMAC-signed auth token containing user identity and expiration."""
    payload = {
        "id": user.get("id"),
        "email": user.get("email"),
        "role": user.get("role", "user"),
        "exp": int(time.time()) + expires_in_seconds,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")
    signature = hmac.new(AUTH_SECRET.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"mga.{payload_b64}.{signature}"


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verifies HMAC signature and expiration on an auth token."""
    if not token or not token.startswith("mga."):
        return None
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        _, payload_b64, signature = parts
        expected_sig = hmac.new(AUTH_SECRET.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        if not secrets.compare_digest(signature, expected_sig):
            return None
        # Add padding back
        rem = len(payload_b64) % 4
        padded_b64 = payload_b64 + ("=" * (4 - rem) if rem else "")
        payload_bytes = base64.urlsafe_b64decode(padded_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
        if payload.get("exp", 0) < int(time.time()):
            logger.warning(f"Auth token expired for user {payload.get('email')}")
            return None
        return payload
    except Exception as e:
        logger.debug(f"Token verification error: {e}")
        return None


class MongoDBManager:
    """
    Centralized MongoDB Connection and Authentication Layer.
    Manages user collections, authentication, registration, and profile lookups.
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
        return bool(self.client is not None and self._is_connected and self.users is not None)

    def _init_connection(self):
        if not HAS_PYMONGO or MongoClient is None:
            logger.warning("pymongo is not installed.")
            self._is_connected = False
            return

        self.uri = os.getenv("MONGODB_URI", "").strip().strip('"').strip("'")
        self.db_name = os.getenv("MONGODB_DB_NAME", "sarala_ai").strip().strip('"').strip("'")

        if not self.uri:
            logger.warning("MONGODB_URI not found in environment.")
            self._is_connected = False
            return

        try:
            client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
            # Verify connectivity with ping
            client.admin.command("ping")
            db = client[self.db_name]
            users = db["users"]
            # Ensure unique index on email and id
            users.create_index([("email", ASCENDING)], unique=True)
            users.create_index([("id", ASCENDING)], unique=True)
            self.client = client
            self.db = db
            self.users = users
            self._is_connected = True
            logger.info(f"Connected to MongoDB Atlas ({self.db_name}) successfully.")
            self._seed_default_admin()
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB Atlas: {e}")
            self._is_connected = False
            self.client = None
            self.db = None
            self.users = None

    def _seed_default_admin(self):
        """Ensures the primary admin account (Naveen / Avee) is initialized in MongoDB."""
        if not self.is_connected or self.users is None:
            return
        admin_email = "loharavee@gmail.com"
        try:
            existing = self.users.find_one({"email": admin_email})
            if not existing:
                admin_doc = {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "email": admin_email,
                    "password_hash": hash_password("Sarala@7880"),
                    "name": "naveen panchal",
                    "nickname": "Avee",
                    "role": "admin",
                    "is_active": True,
                    "is_naveen": True,
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                self.users.insert_one(admin_doc)
                logger.info(f"Seeded default administrator ({admin_email}) in MongoDB.")
            else:
                # Update role and admin flags to ensure admin rights are always active
                self.users.update_one(
                    {"email": admin_email},
                    {"$set": {
                        "role": "admin",
                        "is_active": True,
                        "is_naveen": True,
                        "name": "naveen panchal",
                        "nickname": "Avee",
                        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    }}
                )
        except Exception as e:
            logger.error(f"Error seeding default admin in MongoDB: {e}")

    def register_user(
        self,
        name: str,
        nickname: str,
        email: str,
        password: str,
        role: str = "user"
    ) -> Dict[str, Any]:
        """Registers a new user in MongoDB Atlas."""
        if not self.is_connected or self.users is None:
            return {"success": False, "message": "Database service is offline."}

        email_clean = email.strip().lower()
        if not email_clean or "@" not in email_clean:
            return {"success": False, "message": "Valid email is required."}
        if len(password) < 6:
            return {"success": False, "message": "Password must be at least 6 characters."}

        clean_name = name.strip() or email_clean.split("@")[0].title()
        clean_nick = nickname.strip() or clean_name.split()[0]
        assigned_role = "admin" if email_clean == "loharavee@gmail.com" else ("admin" if role == "admin" else "user")

        try:
            existing = self.users.find_one({"email": email_clean})
            if existing:
                return {"success": False, "message": "This email is already registered. Please log in."}

            user_id = str(uuid.uuid4())
            new_user = {
                "id": user_id,
                "email": email_clean,
                "password_hash": hash_password(password),
                "name": clean_name,
                "nickname": clean_nick,
                "role": assigned_role,
                "is_active": True,
                "is_naveen": (email_clean == "loharavee@gmail.com" or assigned_role == "admin"),
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            self.users.insert_one(new_user)
            token = generate_token(new_user)

            return {
                "success": True,
                "token": token,
                "user": {
                    "id": user_id,
                    "name": clean_name,
                    "nickname": clean_nick,
                    "email": email_clean,
                    "role": assigned_role,
                    "is_active": True,
                    "is_naveen": new_user["is_naveen"],
                }
            }
        except Exception as e:
            logger.error(f"Error registering user in MongoDB: {e}")
            return {"success": False, "message": f"Registration error: {e}"}

    def authenticate_user(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticates user against MongoDB user store."""
        if not self.is_connected or self.users is None:
            return {"success": False, "message": "Database service is offline."}

        email_clean = email.strip().lower()
        try:
            user = self.users.find_one({"email": email_clean})
            if not user:
                return {"success": False, "message": "Incorrect email or password."}

            if not user.get("is_active", True):
                return {"success": False, "message": "This account has been deactivated."}

            stored_hash = user.get("password_hash") or user.get("password") or ""
            # Verify password or allow primary admin known passwords
            valid = verify_password(stored_hash, password)
            if not valid and email_clean == "loharavee@gmail.com":
                if password in ("Sarala@7880", "Sarla@123"):
                    valid = True
                    # Upgrade stored hash to new secure hash
                    self.users.update_one(
                        {"email": email_clean},
                        {"$set": {"password_hash": hash_password(password)}}
                    )

            if not valid:
                return {"success": False, "message": "Incorrect email or password."}

            role = user.get("role", "user")
            if email_clean == "loharavee@gmail.com":
                role = "admin"

            # Record last_login_at in MongoDB
            now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self.users.update_one(
                {"email": email_clean},
                {"$set": {"last_login_at": now_iso, "updated_at": now_iso}}
            )

            user_data = {
                "id": str(user.get("id") or user.get("_id")),
                "name": user.get("name") or "User",
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
            return {"success": False, "message": "Authentication failed due to server error."}

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves user profile by UUID or ID."""
        if not self.is_connected or self.users is None:
            return None
        try:
            u = self.users.find_one({"id": user_id})
            if u:
                return {
                    "id": str(u.get("id")),
                    "email": u.get("email"),
                    "name": u.get("name"),
                    "nickname": u.get("nickname", ""),
                    "role": u.get("role", "user"),
                    "is_active": u.get("is_active", True),
                    "is_naveen": u.get("is_naveen", False),
                }
        except Exception as e:
            logger.error(f"Error fetching user by ID {user_id}: {e}")
        return None

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Retrieves user profile by email."""
        if not self.is_connected or self.users is None:
            return None
        try:
            u = self.users.find_one({"email": email.strip().lower()})
            if u:
                return {
                    "id": str(u.get("id")),
                    "email": u.get("email"),
                    "name": u.get("name"),
                    "nickname": u.get("nickname", ""),
                    "role": u.get("role", "user"),
                    "is_active": u.get("is_active", True),
                    "is_naveen": u.get("is_naveen", False),
                }
        except Exception as e:
            logger.error(f"Error fetching user by email {email}: {e}")
        return None


# Global singleton instance
mongodb_manager = MongoDBManager()
