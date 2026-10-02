import os
import re
import io
import shutil
import logging
import unicodedata
from typing import Optional, Tuple, Dict, Set
from dotenv import load_dotenv

from core.supabase_client import supabase_manager

logger = logging.getLogger("sarala.services.file_storage")

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
load_dotenv()

# Configuration
DEFAULT_MAX_FILE_SIZE_MB = 25
try:
    MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", str(DEFAULT_MAX_FILE_SIZE_MB)))
except (ValueError, TypeError):
    MAX_FILE_SIZE_MB = DEFAULT_MAX_FILE_SIZE_MB

MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "user_files").strip() or "user_files"

# Base local storage directory (strictly partitioned by users/{user_id}/files/{file_id}/...)
DEFAULT_LOCAL_STORAGE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "storage")
)
LOCAL_STORAGE_DIR = os.getenv("LOCAL_STORAGE_DIR", DEFAULT_LOCAL_STORAGE_DIR)

ALLOWED_EXTENSIONS: Set[str] = {
    "pdf",
    "txt",
    "md",
    "docx",
    "csv",
    "xlsx",
    "png",
    "jpg",
    "jpeg",
    "webp",
}

ALLOWED_MIME_TYPES: Dict[str, Set[str]] = {
    "pdf": {"application/pdf"},
    "txt": {"text/plain"},
    "md": {"text/markdown", "text/plain", "application/octet-stream"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        "application/octet-stream",
    },
    "csv": {"text/csv", "application/csv", "text/plain"},
    "xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
        "application/octet-stream",
    },
    "png": {"image/png"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "webp": {"image/webp"},
}

DEFAULT_MIME_MAP: Dict[str, str] = {
    "pdf": "application/pdf",
    "txt": "text/plain",
    "md": "text/markdown",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


def sanitize_filename(original_name: str) -> str:
    """
    Sanitizes user-provided filename:
    - Strips path traversal sequences (../, ..\\, etc.)
    - Removes null bytes and control characters
    - Normalizes unicode characters
    - Restricts to safe alphanumeric, dots, dashes, and underscores
    - Preserves safe extension
    """
    if not original_name:
        return "unnamed_file"

    # 1. Remove null bytes and path components
    cleaned = original_name.replace("\x00", "").strip()
    cleaned = os.path.basename(cleaned.replace("\\", "/"))

    # 2. Strip directory traversal remnants
    while ".." in cleaned:
        cleaned = cleaned.replace("..", "")

    # 3. Unicode normalization
    cleaned = unicodedata.normalize("NFKD", cleaned)

    # 4. Remove control characters
    cleaned = "".join(ch for ch in cleaned if ord(ch) >= 32 and ord(ch) != 127)

    # 5. Sanitize characters except alphanumeric, dot, underscore, dash, space
    cleaned = re.sub(r'[^a-zA-Z0-9.\-_ ]', '_', cleaned).strip()

    # 6. Fallback if empty or purely dots
    if not cleaned or set(cleaned) == {"."}:
        return "unnamed_file"

    # Truncate if excessively long while preserving extension
    if len(cleaned) > 200:
        if "." in cleaned:
            base, ext = cleaned.rsplit(".", 1)
            cleaned = base[:190] + "." + ext
        else:
            cleaned = cleaned[:200]

    return cleaned


def validate_file_content(
    original_name: str,
    content: bytes,
    declared_mime: Optional[str] = None,
) -> Tuple[bool, str, str, str, str]:
    """
    Validates uploaded file:
    - File size <= MAX_FILE_SIZE_MB
    - Content non-empty
    - Extension in ALLOWED_EXTENSIONS
    - Magic bytes signature matches expected type
    Returns (is_valid, error_msg, safe_filename, extension, normalized_mime_type).
    """
    safe_filename = sanitize_filename(original_name)
    if not content:
        return False, "File is empty (0 bytes).", safe_filename, "", ""

    size_bytes = len(content)
    if size_bytes > MAX_FILE_SIZE_BYTES:
        return (
            False,
            f"File exceeds maximum allowed size of {MAX_FILE_SIZE_MB}MB ({size_bytes} bytes).",
            safe_filename,
            "",
            "",
        )

    # Extract extension
    ext = safe_filename.rsplit(".", 1)[-1].lower() if "." in safe_filename else ""
    if not ext or ext not in ALLOWED_EXTENSIONS:
        allowed_list = ", ".join(sorted(ALLOWED_EXTENSIONS))
        return (
            False,
            f"Unsupported file type '.{ext}'. Supported types are: {allowed_list}.",
            safe_filename,
            ext,
            "",
        )

    # Magic byte & signature verification
    magic_error = _verify_magic_bytes(ext, content)
    if magic_error:
        return False, magic_error, safe_filename, ext, ""

    # Normalize MIME type
    norm_mime = DEFAULT_MIME_MAP.get(ext, "application/octet-stream")
    if declared_mime:
        cleaned_declared = declared_mime.split(";")[0].strip().lower()
        if ext in ALLOWED_MIME_TYPES and cleaned_declared in ALLOWED_MIME_TYPES[ext]:
            norm_mime = cleaned_declared

    return True, "", safe_filename, ext, norm_mime


def _verify_magic_bytes(ext: str, content: bytes) -> Optional[str]:
    """Validates file magic signatures to detect extension spoofing."""
    if ext == "pdf":
        if not content.startswith(b"%PDF-"):
            return "Invalid PDF file: Missing %PDF- magic signature."
    elif ext == "png":
        if not content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "Invalid PNG image: Missing PNG magic signature."
    elif ext in ("jpg", "jpeg"):
        if not content.startswith(b"\xff\xd8\xff"):
            return "Invalid JPEG image: Missing JPEG magic signature."
    elif ext == "webp":
        if len(content) < 12 or not (content.startswith(b"RIFF") and content[8:12] == b"WEBP"):
            return "Invalid WEBP image: Missing RIFF/WEBP magic signature."
    elif ext in ("docx", "xlsx"):
        # OOXML documents are ZIP archives starting with PK\x03\x04
        if not content.startswith(b"PK\x03\x04"):
            return f"Invalid Office document (.{ext}): Missing ZIP container signature."
    elif ext in ("txt", "csv", "md"):
        # Text files shouldn't contain null bytes in initial sample
        sample = content[:1024]
        if b"\x00" in sample:
            return f"Invalid text file (.{ext}): Binary content or null bytes detected."

    return None


class FileStorageService:
    """
    Production-ready storage service managing binary file storage.
    Supports Supabase Storage bucket with transparent fallback to user-partitioned
    local disk storage. Enforces strict user isolation:
    Storage paths: users/{user_id}/files/{file_id}/{safe_filename}
    """

    def __init__(self):
        self._supabase_storage_available: Optional[bool] = None

    def _check_supabase_storage(self) -> bool:
        """Determines if Supabase Storage is available and functional."""
        if not supabase_manager.is_connected or not supabase_manager.client:
            return False
        if not hasattr(supabase_manager.client, "storage"):
            return False

        if self._supabase_storage_available is not None:
            return self._supabase_storage_available

        try:
            # Probe bucket existence or accessibility
            buckets = supabase_manager.client.storage.list_buckets()
            bucket_names = [b.name for b in buckets] if buckets else []
            if SUPABASE_STORAGE_BUCKET in bucket_names:
                self._supabase_storage_available = True
                return True

            # If not in list, try to create or check access
            try:
                supabase_manager.client.storage.create_bucket(
                    SUPABASE_STORAGE_BUCKET,
                    options={"public": False},
                )
                self._supabase_storage_available = True
                return True
            except Exception as be:
                logger.debug(f"Supabase bucket creation skipped: {be}")
                # May already exist but private/unlisted
                self._supabase_storage_available = False
                return False
        except Exception as e:
            logger.debug(f"Supabase Storage unavailable: {e}")
            self._supabase_storage_available = False
            return False

    def generate_storage_key(self, user_id: str, file_id: str, safe_filename: str) -> str:
        """
        Generates server-controlled, user-partitioned storage key.
        Never allows user to supply arbitrary paths.
        users/{user_id}/files/{file_id}/{safe_filename}
        """
        clean_user_id = re.sub(r'[^a-zA-Z0-9_\-]', '', user_id)
        clean_file_id = re.sub(r'[^a-zA-Z0-9_\-]', '', file_id)
        return f"users/{clean_user_id}/files/{clean_file_id}/{safe_filename}"

    def save_file(
        self,
        user_id: str,
        file_id: str,
        safe_filename: str,
        content: bytes,
        mime_type: str,
    ) -> Tuple[str, str]:
        """
        Stores file bytes into storage provider.
        Returns (storage_provider, storage_key).
        """
        storage_key = self.generate_storage_key(user_id, file_id, safe_filename)

        # 1. Attempt Supabase Storage if configured and available
        if self._check_supabase_storage():
            try:
                storage_client = supabase_manager.client.storage.from_(SUPABASE_STORAGE_BUCKET)
                res = storage_client.upload(
                    path=storage_key,
                    file=content,
                    file_options={"content-type": mime_type, "upsert": "true"},
                )
                logger.info(f"Stored file {file_id} to Supabase Storage: {storage_key}")
                return "supabase_storage", storage_key
            except Exception as e:
                logger.warning(f"Supabase Storage upload failed, falling back to local: {e}")

        # 2. Local user-partitioned storage fallback
        abs_target_path = self._resolve_local_path(user_id, storage_key)
        os.makedirs(os.path.dirname(abs_target_path), exist_ok=True)

        try:
            with open(abs_target_path, "wb") as f:
                f.write(content)
            logger.info(f"Stored file {file_id} to local partitioned storage: {abs_target_path}")
            return "local", storage_key
        except Exception as e:
            logger.error(f"Failed to write file to local storage {abs_target_path}: {e}")
            raise IOError(f"Storage write failure: {e}")

    def read_file(self, user_id: str, storage_provider: str, storage_key: str) -> bytes:
        """
        Reads file bytes from storage provider.
        Enforces user partition verification: storage_key must belong to user_id.
        """
        expected_prefix = f"users/{user_id}/files/"
        if not storage_key.startswith(expected_prefix):
            logger.warning(f"User {user_id} attempted access to non-owned storage key: {storage_key}")
            raise PermissionError("Access to storage key denied.")

        if storage_provider == "supabase_storage" and supabase_manager.is_connected:
            try:
                storage_client = supabase_manager.client.storage.from_(SUPABASE_STORAGE_BUCKET)
                res = storage_client.download(storage_key)
                if isinstance(res, bytes):
                    return res
                elif hasattr(res, "read"):
                    return res.read()
            except Exception as e:
                logger.warning(f"Supabase Storage download failed for {storage_key}: {e}")

        # Local storage fallback
        abs_target_path = self._resolve_local_path(user_id, storage_key)
        if not os.path.exists(abs_target_path):
            raise FileNotFoundError(f"Stored file object does not exist: {storage_key}")

        with open(abs_target_path, "rb") as f:
            return f.read()

    def delete_file(self, user_id: str, storage_provider: str, storage_key: str) -> bool:
        """
        Deletes stored file bytes from storage provider.
        Enforces user partition verification.
        """
        expected_prefix = f"users/{user_id}/files/"
        if not storage_key.startswith(expected_prefix):
            logger.warning(f"User {user_id} attempted to delete non-owned storage key: {storage_key}")
            return False

        deleted = False

        if storage_provider == "supabase_storage" and supabase_manager.is_connected:
            try:
                storage_client = supabase_manager.client.storage.from_(SUPABASE_STORAGE_BUCKET)
                storage_client.remove([storage_key])
                deleted = True
            except Exception as e:
                logger.debug(f"Supabase Storage deletion failed for {storage_key}: {e}")

        # Local storage cleanup
        try:
            abs_target_path = self._resolve_local_path(user_id, storage_key)
            if os.path.exists(abs_target_path):
                os.remove(abs_target_path)
                deleted = True

            # Clean up parent directory if empty
            parent_dir = os.path.dirname(abs_target_path)
            if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                shutil.rmtree(parent_dir, ignore_errors=True)
        except Exception as e:
            logger.debug(f"Local storage deletion error for {storage_key}: {e}")

        return deleted

    def get_signed_url(
        self,
        user_id: str,
        storage_provider: str,
        storage_key: str,
        expires_in: int = 3600,
    ) -> Optional[str]:
        """Generates a short-lived signed URL if Supabase Storage is active."""
        expected_prefix = f"users/{user_id}/files/"
        if not storage_key.startswith(expected_prefix):
            return None

        if storage_provider == "supabase_storage" and supabase_manager.is_connected:
            try:
                storage_client = supabase_manager.client.storage.from_(SUPABASE_STORAGE_BUCKET)
                res = storage_client.create_signed_url(storage_key, expires_in)
                if isinstance(res, dict) and "signedURL" in res:
                    return res["signedURL"]
                elif hasattr(res, "signed_url"):
                    return res.signed_url
            except Exception as e:
                logger.debug(f"Failed to generate signed URL for {storage_key}: {e}")

        return None

    def _resolve_local_path(self, user_id: str, storage_key: str) -> str:
        """
        Resolves local absolute storage path and verifies canonical containment.
        Prevents directory traversal outside LOCAL_STORAGE_DIR.
        """
        base_dir = os.path.abspath(LOCAL_STORAGE_DIR)
        # Normalize slashes
        norm_key = storage_key.replace("\\", "/").strip("/")
        target_path = os.path.abspath(os.path.join(base_dir, norm_key))

        # Security check: canonical path containment
        if os.path.commonpath([base_dir, target_path]) != base_dir:
            raise PermissionError("Path traversal attempt detected outside storage boundary.")

        # Ensure user partition is in path
        clean_user_id = re.sub(r'[^a-zA-Z0-9_\-]', '', user_id)
        expected_segment = os.path.join("users", clean_user_id)
        if expected_segment not in target_path:
            raise PermissionError("Path traversal attempt outside user storage partition.")

        return target_path


file_storage_service = FileStorageService()
