"""
Pydantic Request and Response Schemas for Sarala AI Persistent User Data API Layer.
All schemas enforce strict ownership derivation: user_id is never accepted from frontend
as an authoritative owner identifier.
"""

from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, field_validator


# ── Generic API Response Container ────────────────────────────────────────────
class APIResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    message: Optional[str] = None
    pagination: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ── Profile Schemas ───────────────────────────────────────────────────────────
class ProfileUpdateRequest(BaseModel):
    model_config = {"extra": "ignore"}
    full_name: Optional[str] = Field(None, max_length=100)
    nickname: Optional[str] = Field(None, max_length=50)
    avatar_url: Optional[str] = Field(None, max_length=500)
    bio: Optional[str] = Field(None, max_length=1000)

    @field_validator("full_name", "nickname", "avatar_url", "bio", mode="before")
    @classmethod
    def clean_strings(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v


class ProfileResponseData(BaseModel):
    user_id: str
    id: str
    email: str
    full_name: str
    nickname: str = ""
    avatar_url: str = ""
    bio: str = ""
    role: str
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_login_at: Optional[str] = None


# ── Preferences Schemas ───────────────────────────────────────────────────────
ALLOWED_CANONICAL_MODES = {"normal", "love", "expert"}

class PreferencesUpdateRequest(BaseModel):
    ai_mode: Optional[str] = Field(None, max_length=30)
    theme_mode: Optional[str] = Field(None, max_length=30)
    language: Optional[str] = Field(None, max_length=10)
    timezone: Optional[str] = Field(None, max_length=50)
    voice_enabled: Optional[bool] = None
    notifications_enabled: Optional[bool] = None
    assistant_personality: Optional[str] = Field(None, max_length=50)
    preferred_voice: Optional[str] = Field(None, max_length=50)
    preferred_model: Optional[str] = Field(None, max_length=50)
    ui_preferences: Optional[Dict[str, Any]] = None
    persona_settings: Optional[Dict[str, Any]] = None

    @field_validator("ai_mode", mode="before")
    @classmethod
    def validate_ai_mode(cls, v):
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("ai_mode must be a string")
        clean = v.strip().lower()
        if clean not in ALLOWED_CANONICAL_MODES:
            raise ValueError(f"Invalid ai_mode '{v}'. Allowed canonical modes: 'normal', 'love', 'expert'.")
        return clean

    @field_validator("theme_mode", mode="before")
    @classmethod
    def validate_theme_mode(cls, v):
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("theme_mode must be a string")
        clean = v.strip().lower()
        if clean not in ALLOWED_CANONICAL_MODES:
            raise ValueError(f"Invalid theme_mode '{v}'. Allowed canonical modes: 'normal', 'love', 'expert'.")
        return clean

    @field_validator("voice_enabled", "notifications_enabled", mode="before")
    @classmethod
    def validate_booleans(cls, v):
        if v is not None and not isinstance(v, bool):
            raise ValueError("Value must be a boolean (true or false)")
        return v

    @field_validator("persona_settings", "ui_preferences", mode="before")
    @classmethod
    def validate_dicts(cls, v):
        if v is None:
            return None
        if not isinstance(v, dict):
            raise ValueError("Must be a JSON object dictionary")
        # Sanitize any accidental credentials from persona settings
        sanitized = {}
        for k, val in v.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in ("password", "secret", "api_key", "token")):
                continue
            sanitized[str(k)[:50]] = val
        return sanitized


class PreferencesResponseData(BaseModel):
    user_id: str
    ai_mode: str = "normal"
    theme_mode: str = "normal"
    language: str = "hi"
    timezone: str = "Asia/Kolkata"
    voice_enabled: bool = True
    notifications_enabled: bool = True
    assistant_personality: str = "normal"
    preferred_voice: str = "sarala"
    preferred_model: str = "default"
    ui_preferences: Dict[str, Any] = {}
    persona_settings: Dict[str, Any] = {}
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ── Conversation Schemas ──────────────────────────────────────────────────────
class CreateConversationRequest(BaseModel):
    title: str = Field("New Conversation", max_length=200)
    mode: str = Field("normal", max_length=50)

    @field_validator("title", mode="before")
    @classmethod
    def clean_title(cls, v) -> str:
        if v is not None:
            if isinstance(v, str) and v.strip():
                return v.strip()
        return "New Conversation"

    @field_validator("mode", mode="before")
    @classmethod
    def validate_mode(cls, v) -> str:
        if v is not None:
            if isinstance(v, str):
                v_clean = v.strip().lower()
                if v_clean in {"normal", "love", "expert"}:
                    return v_clean
        return "normal"


class UpdateConversationRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    mode: Optional[str] = Field(None, max_length=50)
    status: Optional[str] = Field(None, max_length=50)
    summary: Optional[str] = Field(None, max_length=5000)
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("title", mode="before")
    @classmethod
    def clean_title(cls, v):
        if v is not None:
            if not isinstance(v, str):
                raise ValueError("title must be a string")
            v_clean = v.strip()
            if not v_clean:
                raise ValueError("title cannot be empty")
            return v_clean
        return v

    @field_validator("mode", mode="before")
    @classmethod
    def validate_mode(cls, v):
        if v is not None:
            if not isinstance(v, str):
                raise ValueError("mode must be a string")
            v_clean = v.strip().lower()
            if v_clean not in {"normal", "love", "expert"}:
                raise ValueError("Invalid mode. Allowed modes: normal, love, expert.")
            return v_clean
        return v


class ConversationResponseData(BaseModel):
    id: str
    user_id: str
    title: str
    mode: str
    status: str
    message_count: int = 0
    created_at: str
    updated_at: str
    last_message_at: str
    summary: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# ── Message Schemas ───────────────────────────────────────────────────────────
ALLOWED_ROLES = {"user", "assistant", "system", "tool"}

class CreateMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=50000)
    role: str = Field("user")
    message_type: str = Field("text", max_length=50)
    client_message_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in ALLOWED_ROLES:
            raise ValueError(f"Invalid role '{clean}'. Must be one of: {', '.join(sorted(ALLOWED_ROLES))}")
        return clean

    @field_validator("content", mode="before")
    @classmethod
    def validate_content(cls, v):
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Message content cannot be empty.")
        return v


class MessageResponseData(BaseModel):
    id: str
    conversation_id: str
    user_id: str
    role: str
    content: str
    message_type: str = "text"
    metadata: Dict[str, Any] = {}
    created_at: str


# ── Memory Schemas ────────────────────────────────────────────────────────────
ALLOWED_MEMORY_TYPES = {
    "identity",
    "preference",
    "personal",
    "work",
    "education",
    "technical",
    "business",
    "relationship",
    "routine",
    "goal",
    "project",
    "communication",
    "other",
}

def normalize_memory_type(val: Optional[str]) -> str:
    """Normalizes memory type to controlled vocabulary with safe 'other' fallback."""
    if not val:
        return "other"
    cleaned = str(val).strip().lower()
    return cleaned if cleaned in ALLOWED_MEMORY_TYPES else "other"

def normalize_importance(val: Any) -> float:
    """Normalizes importance from strings ('low', 'medium', 'high') or numbers to float."""
    if val is None:
        return 1.0
    if isinstance(val, (int, float)):
        return max(0.1, min(5.0, float(val)))
    val_str = str(val).strip().lower()
    if val_str == "high":
        return 3.0
    if val_str == "medium":
        return 2.0
    if val_str == "low":
        return 1.0
    try:
        f = float(val_str)
        return max(0.1, min(5.0, f))
    except ValueError:
        return 1.0


class CreateMemoryRequest(BaseModel):
    memory_key: str = Field(..., min_length=1, max_length=100)
    memory_value: Any
    memory_type: str = Field("personal", max_length=50)
    importance: Union[float, str] = Field(1.0)
    source: str = Field("user_input", max_length=50)
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("memory_key", mode="before")
    @classmethod
    def clean_key(cls, v):
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Memory key cannot be empty.")
        cleaned = v.strip().lower().replace(" ", "_")
        if len(cleaned) > 100:
            cleaned = cleaned[:100]
        return cleaned

    @field_validator("memory_value", mode="before")
    @classmethod
    def clean_value(cls, v):
        if v is None:
            raise ValueError("Memory value cannot be null.")
        val_str = str(v).strip()
        if not val_str:
            raise ValueError("Memory value cannot be empty.")
        if len(val_str) > 5000:
            val_str = val_str[:5000]
        return val_str

    @field_validator("memory_type", mode="before")
    @classmethod
    def clean_type(cls, v):
        return normalize_memory_type(v)

    @field_validator("importance", mode="before")
    @classmethod
    def clean_importance(cls, v):
        return normalize_importance(v)


class UpdateMemoryRequest(BaseModel):
    memory_value: Optional[Any] = None
    memory_type: Optional[str] = Field(None, max_length=50)
    importance: Optional[Union[float, str]] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("memory_value", mode="before")
    @classmethod
    def clean_value(cls, v):
        if v is not None:
            val_str = str(v).strip()
            if len(val_str) > 5000:
                val_str = val_str[:5000]
            return val_str
        return v

    @field_validator("memory_type", mode="before")
    @classmethod
    def clean_type(cls, v):
        if v is not None:
            return normalize_memory_type(v)
        return v

    @field_validator("importance", mode="before")
    @classmethod
    def clean_importance(cls, v):
        if v is not None:
            return normalize_importance(v)
        return v


class MemoryResponseData(BaseModel):
    id: str
    user_id: str
    memory_key: str
    memory_value: str
    memory_type: str = "other"
    importance: float = 1.0
    source: str = "user_input"
    metadata: Dict[str, Any] = {}
    created_at: str
    updated_at: str
    last_accessed_at: Optional[str] = None
    deleted_at: Optional[str] = None


# ── User File Metadata Schemas ────────────────────────────────────────────────
class RecordFileRequest(BaseModel):
    original_name: str = Field(..., min_length=1, max_length=255)
    storage_key: str = Field(..., min_length=1, max_length=500)
    size_bytes: int = Field(0, ge=0)
    mime_type: str = Field("application/octet-stream", max_length=100)
    storage_provider: str = Field("local", max_length=50)
    status: str = Field("uploaded", max_length=50)
    metadata: Optional[Dict[str, Any]] = None


class UpdateFileRequest(BaseModel):
    original_name: Optional[str] = Field(None, max_length=255)
    status: Optional[str] = Field(None, max_length=50)
    metadata: Optional[Dict[str, Any]] = None


class UserFileResponseData(BaseModel):
    id: str
    user_id: str
    original_name: str
    storage_provider: str
    storage_key: str
    mime_type: str
    size_bytes: int
    status: str
    metadata: Dict[str, Any] = {}
    created_at: str
    updated_at: str
    deleted_at: Optional[str] = None


# ── Chat & Auth Request Schemas ───────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    client_message_id: Optional[str] = None
    theme_mode: str = "normal"
    user_name: str = ""
    user_nickname: str = ""
    is_live: bool = False
    model: Optional[str] = None
    task_type: Optional[str] = None
    agent_mode: Optional[bool] = False


class LoginRequest(BaseModel):
    email: str
    password: str


class SignupRequest(BaseModel):
    name: str
    nickname: str = ""
    email: str
    password: str
    role: str = "user"


class ToolExecuteRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    conversation_id: Optional[str] = None
    confirmation_token: Optional[str] = None


class ToolConfirmRequest(BaseModel):
    confirmation_token: str
    conversation_id: Optional[str] = None

