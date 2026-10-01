import sys
import os
import re
import json
import time
import io
import urllib.parse
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException, Header, Body, UploadFile, File, Form, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.brain import Brain
from core.logger import logger
from core.admin_service import admin_service
from core.supabase_client import supabase_manager
from core.mongodb_client import mongodb_manager
from core.auth import CurrentUser, get_current_user, get_current_user_optional, get_current_admin
from core.services import (
    profile_service,
    preferences_service,
    conversation_service,
    message_service,
    memory_service,
    memory_extraction_service,
    user_file_service,
)
from voice.natural_voice import natural_voice_manager, clean_text_for_synthesis
from voice.voice_service import get_voice_health, synthesize_sarala_voice, VoiceSynthesisError
from ai.agent import (
    agent_engine,
    AgentRunStatus,
    AgentRunCreateRequest,
    AgentApprovalRequest,
    AgentRejectionRequest,
    AgentEngineError,
    AgentNotFoundError,
    AgentNotOwnedError,
    AgentInvalidStateError,
    AgentPlanInvalidError,
    AgentStepInvalidError,
    AgentDependencyError,
    AgentApprovalRequiredError,
    AgentApprovalInvalidError,
    AgentLimitReachedError,
    AgentTimeoutError,
    AgentCancelledError,
    AgentToolFailedError,
    AgentDisabledError,
)

# ── Lifespan Context Manager ──────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Sarla Web Server is starting up with Supabase & In-Memory Voice Streaming...")
    yield

# ── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(title="Sarla AI API", version="2.0.0", lifespan=lifespan)

allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3002",
    "http://localhost:3005",
    "http://127.0.0.1:3005",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8008",
    "http://127.0.0.1:8008",
    "https://sarala-ai-pi.vercel.app",
]

frontend_url = os.getenv("FRONTEND_URL", "")
if frontend_url:
    for origin in frontend_url.split(","):
        origin = origin.strip()
        if origin and origin not in allowed_origins:
            allowed_origins.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (HTML, CSS, JS)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# ── Shared Brain instance ───────────────────────────────────────────────────
brain = Brain()

# ── Schemas & Models ─────────────────────────────────────────────────────────
from core.schemas import (
    LoginRequest,
    SignupRequest,
    ProfileUpdateRequest,
    PreferencesUpdateRequest,
    CreateConversationRequest,
    UpdateConversationRequest,
    CreateMessageRequest,
    CreateMemoryRequest,
    UpdateMemoryRequest,
    RecordFileRequest,
    UpdateFileRequest,
    ChatRequest,
    ToolExecuteRequest,
    ToolConfirmRequest,
)

class TrainingItemRequest(BaseModel):
    id: Optional[str] = None
    topic: str
    category: str = "tech"
    prompt_pattern: str
    target_response: str
    confidence: float = 1.0
    source: str = "admin_training"
    is_active: bool = True

class BulkTrainingRequest(BaseModel):
    items: List[TrainingItemRequest]

class IngestKnowledgeRequest(BaseModel):
    title: str
    content: str
    category: str = "general"

class ApproveEngineRequest(BaseModel):
    engine_key: str
    engine_name: str
    notes: str = ""

# ── Helper: Emotion Classifier for 3D Avatar ─────────────────────────────────
def classify_emotion(text: str) -> tuple:
    lower = text.lower()
    if any(w in lower for w in ["sad", "dukhi", "sorry", "afsos", "kharab", "galti", "warning", "danger"]):
        return "concerned", "calmGesture"
    if any(w in lower for w in ["congrat", "mubarak", "great", "awesome", "badhiya", "shandar", "superb", "wah"]):
        return "excited", "excitedGesture"
    if any(w in lower for w in ["happy", "khush", "welcome", "swagat", "namaste", "hello", "hi ", "hey", "shukriya", "thanks"]):
        return "happy", "greetingWave"
    if any(w in lower for w in ["let me check", "sochne do", "dekhte hain", "analyz", "calculat", "samajh"]):
        return "thinking", "thinkingPose"
    if any(w in lower for w in ["step", "first", "second", "code", "python", "html", "react", "tarika", "kaise"]):
        return "friendly", "explainOneHand"
    return "neutral", "explainOneHand"

# ── In-Memory Login Rate Limiter (Brute-Force Protection) ─────────────────────
login_attempt_history: Dict[str, List[float]] = {}
RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_WINDOW_SECONDS = 300  # 5 minutes
RATE_LIMIT_LOCKOUT_SECONDS = 60  # 60 seconds lockout

def check_login_rate_limit(key: str):
    now = time.time()
    history = login_attempt_history.get(key, [])
    # Filter attempts within moving window
    history = [t for t in history if now - t < RATE_LIMIT_WINDOW_SECONDS]
    login_attempt_history[key] = history
    if len(history) >= RATE_LIMIT_MAX_ATTEMPTS:
        time_since_last = now - history[-1]
        if time_since_last < RATE_LIMIT_LOCKOUT_SECONDS:
            remaining = int(RATE_LIMIT_LOCKOUT_SECONDS - time_since_last)
            raise HTTPException(
                status_code=429,
                detail=f"Too many failed login attempts. Please wait {remaining} seconds before trying again."
            )

def record_failed_login(key: str):
    now = time.time()
    history = login_attempt_history.get(key, [])
    history.append(now)
    login_attempt_history[key] = history

def reset_login_rate_limit(key: str):
    if key in login_attempt_history:
        del login_attempt_history[key]

# ── General Routes ───────────────────────────────────────────────────────────
@app.get("/")
async def index():
    """Redirect visitors from backend Render URL directly to the official modern Vercel UI."""
    return RedirectResponse(url="https://sarala-ai-pi.vercel.app/")


@app.get("/health")
async def health():
    """
    Granular system health check. Distinguishes:
    - MongoDB Atlas status (authentication authority)
    - Supabase PostgreSQL status (application data)
    - Global application status
    """
    mongo_ok = mongodb_manager.is_connected
    supa_ok = supabase_manager.is_connected
    is_healthy = mongo_ok and supa_ok
    status_str = "healthy" if is_healthy else ("degraded" if (mongo_ok or supa_ok) else "unhealthy")

    return {
        "status": status_str,
        "agent": "Sarla AI",
        "mongodb_connected": mongo_ok,
        "supabase_connected": supa_ok,
        "database": {
            "mongodb": "connected" if mongo_ok else "disconnected",
            "supabase": "connected" if supa_ok else "disconnected"
        },
        "authentication": {
            "provider": "mongodb",
            "authority": "MongoDB Atlas",
            "status": "operational" if mongo_ok else "unavailable"
        }
    }

# ── Authentication & Profiles (MongoDB Atlas Authority) ──────────────────────
@app.post("/api/login")
async def login(req: LoginRequest):
    """
    Authoritative login endpoint. Authenticates strictly against MongoDB Atlas.
    Zero fallback to local storage or Supabase Auth.
    Enforces rate limiting, constant-time PBKDF2 hash verification, and account active checks.
    """
    email_clean = (req.email or "").strip().lower()
    if not email_clean or not req.password:
        raise HTTPException(status_code=400, detail="Email and password are required.")

    # Brute-force throttling per email
    check_login_rate_limit(email_clean)

    if not mongodb_manager.is_connected:
        raise HTTPException(
            status_code=503,
            detail="Authentication service is currently unavailable. Please try again shortly."
        )

    result = mongodb_manager.authenticate_user(email_clean, req.password)
    if not result.get("success"):
        record_failed_login(email_clean)
        code = result.get("code")
        if code == "ACCOUNT_DEACTIVATED":
            raise HTTPException(status_code=403, detail="This account has been deactivated.")
        if code == "DB_OFFLINE":
            raise HTTPException(status_code=503, detail="Authentication service is currently unavailable.")
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    # Reset failed attempts upon successful login
    reset_login_rate_limit(email_clean)

    user_info = result["user"]
    user_id = str(user_info.get("user_id") or user_info.get("id"))

    # Synchronize Supabase profile & default preferences
    try:
        profile_service.sync_login(
            user_id=user_id,
            email=user_info["email"],
            role=user_info.get("role", "user"),
            full_name=user_info.get("full_name") or user_info.get("name") or "User",
            nickname=user_info.get("nickname", ""),
            is_active=True,
        )
        preferences_service.init_default_preferences(user_id)
    except Exception as e:
        logger.debug(f"Profile synchronization note: {e}")

    safe_user = {
        "id": user_id,
        "user_id": user_id,
        "email": user_info["email"],
        "name": user_info.get("name") or user_info.get("full_name") or "User",
        "full_name": user_info.get("full_name") or user_info.get("name") or "User",
        "nickname": user_info.get("nickname", ""),
        "role": user_info.get("role", "user"),
        "is_active": True,
    }

    return JSONResponse({
        "success": True,
        "token": result["token"],
        "user": safe_user,
        "data": {
            "token": result["token"],
            "user": safe_user
        }
    })

@app.post("/api/signup", status_code=201)
async def signup(req: SignupRequest):
    """
    Registers a new user in MongoDB Atlas (sole auth authority) with canonical UUID user_id.
    Prevents frontend role escalation (forces role='user' unless root administrator).
    Provisions corresponding Supabase application profile and default preferences.
    """
    email_clean = (req.email or "").strip().lower()
    if not email_clean or "@" not in email_clean or "." not in email_clean:
        raise HTTPException(status_code=400, detail="A valid email address is required.")
    if not req.password or len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    if not mongodb_manager.is_connected:
        raise HTTPException(
            status_code=503,
            detail="Registration service is currently unavailable. Please try again shortly."
        )

    assigned_role = "admin" if email_clean == "loharavee@gmail.com" else "user"

    result = mongodb_manager.register_user(
        name=req.name,
        nickname=req.nickname,
        email=email_clean,
        password=req.password,
        role=assigned_role,
    )
    if not result.get("success"):
        code = result.get("code")
        if code == "EMAIL_EXISTS":
            raise HTTPException(status_code=409, detail=result.get("message", "This email is already registered."))
        if code == "DB_OFFLINE":
            raise HTTPException(status_code=503, detail="Registration service is currently unavailable.")
        raise HTTPException(status_code=400, detail=result.get("message", "Registration failed."))

    user_info = result["user"]
    user_id = str(user_info.get("user_id") or user_info.get("id"))

    # Provision Supabase application profile and preferences
    try:
        profile_service.create_or_update_profile(
            user_id=user_id,
            email=email_clean,
            full_name=user_info.get("full_name") or user_info.get("name") or req.name,
            nickname=user_info.get("nickname") or req.nickname,
            role=assigned_role,
            is_active=True,
        )
        preferences_service.init_default_preferences(user_id)
    except Exception as e:
        logger.error(f"Error provisioning Supabase profile for {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Account created in authentication database, but profile provisioning encountered an error."
        )

    safe_user = {
        "id": user_id,
        "user_id": user_id,
        "email": user_info["email"],
        "name": user_info.get("name") or user_info.get("full_name") or req.name,
        "full_name": user_info.get("full_name") or user_info.get("name") or req.name,
        "nickname": user_info.get("nickname", ""),
        "role": assigned_role,
        "is_active": True,
    }

    return JSONResponse({
        "success": True,
        "token": result["token"],
        "user": safe_user,
        "data": {
            "token": result["token"],
            "user": safe_user
        }
    }, status_code=201)

@app.post("/api/logout")
async def logout(current_user: Optional[CurrentUser] = Depends(get_current_user_optional)):
    """Stateless session logout acknowledgment. Client removes Bearer token."""
    return {"success": True, "message": "Successfully logged out."}

@app.get("/api/auth/me")
async def get_current_user_profile(current_user: CurrentUser = Depends(get_current_user)):
    """Verifies and returns authoritative user identity from MongoDB Atlas + Supabase profile."""
    prof = profile_service.get_profile(current_user.user_id) or {}
    user_payload = {
        "id": current_user.id,
        "user_id": current_user.user_id,
        "name": current_user.full_name,
        "full_name": current_user.full_name,
        "nickname": current_user.nickname,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "avatar_url": prof.get("avatar_url", ""),
        "bio": prof.get("bio", ""),
    }
    return {
        "authenticated": True,
        "success": True,
        "data": user_payload,
        "user": user_payload
    }

# ── Application Profile Endpoints (Supabase) ──────────────────────────────────
@app.get("/api/profile")
async def get_user_profile(current_user: CurrentUser = Depends(get_current_user)):
    """Fetches application profile for the authenticated user from Supabase. Auto-provisions defaults if missing."""
    prof = profile_service.get_profile(current_user.user_id)
    if not prof:
        prof = profile_service.create_or_update_profile(
            user_id=current_user.user_id,
            email=current_user.email,
            full_name=current_user.full_name,
            nickname=current_user.nickname,
            role=current_user.role,
            is_active=current_user.is_active,
        )
    profile_data = {
        "user_id": current_user.user_id,
        "id": current_user.id,
        "email": current_user.email,
        "full_name": prof.get("full_name") or current_user.full_name,
        "nickname": prof.get("nickname") or current_user.nickname,
        "avatar_url": prof.get("avatar_url", ""),
        "bio": prof.get("bio", ""),
        "role": current_user.role,
        "is_active": current_user.is_active,
        "created_at": prof.get("created_at"),
        "updated_at": prof.get("updated_at"),
        "last_login_at": prof.get("last_login_at"),
    }
    return {
        "success": True,
        "data": profile_data,
        "profile": profile_data
    }

@app.patch("/api/profile")
@app.put("/api/profile")
async def update_user_profile(
    updates: ProfileUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Updates profile. Strips role, is_active, and user_id to prevent escalation."""
    fields = updates.model_dump(exclude_unset=True)
    updated = profile_service.update_user_profile(current_user.user_id, fields)
    profile_data = {
        "user_id": current_user.user_id,
        "id": current_user.id,
        "email": current_user.email,
        "full_name": updated.get("full_name") or current_user.full_name,
        "nickname": updated.get("nickname") or current_user.nickname,
        "avatar_url": updated.get("avatar_url", ""),
        "bio": updated.get("bio", ""),
        "role": current_user.role,
        "is_active": current_user.is_active,
        "created_at": updated.get("created_at"),
        "updated_at": updated.get("updated_at"),
        "last_login_at": updated.get("last_login_at"),
    }
    return {"success": True, "data": profile_data, "profile": profile_data}

# ── User Preferences Endpoints (Supabase) ────────────────────────────────────
@app.get("/api/preferences")
async def get_preferences(current_user: CurrentUser = Depends(get_current_user)):
    """Fetches user preferences partitioned by user_id."""
    prefs = preferences_service.get_preferences(current_user.user_id)
    return {"success": True, "data": prefs, "preferences": prefs}

@app.patch("/api/preferences")
@app.put("/api/preferences")
async def update_preferences(
    updates: PreferencesUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Updates user preferences for the authenticated user_id."""
    fields = updates.model_dump(exclude_unset=True)
    updated = preferences_service.update_preferences(current_user.user_id, fields)
    return {"success": True, "data": updated, "preferences": updated}

# ── Conversation Endpoints (Supabase) ────────────────────────────────────────
@app.get("/api/conversations")
async def list_conversations(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Lists conversations strictly owned by current_user.user_id."""
    convs, total = conversation_service.list_conversations(
        current_user.user_id,
        limit=limit,
        offset=offset,
        search=search,
        status=status,
    )
    return {
        "success": True,
        "data": convs,
        "conversations": convs,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total,
        }
    }

@app.post("/api/conversations")
async def create_conversation(
    req: CreateConversationRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Creates a new conversation owned by current_user.user_id."""
    conv = conversation_service.create_conversation(
        current_user.user_id,
        title=str(req.title or "New Conversation"),
        mode=str(req.mode or "normal"),
    )
    return {"success": True, "data": conv, "conversation": conv}

@app.get("/api/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Retrieves conversation if owned by current_user.user_id."""
    conv = conversation_service.get_conversation(current_user.user_id, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"success": True, "data": conv, "conversation": conv}

@app.patch("/api/conversations/{conversation_id}")
@app.put("/api/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    req: UpdateConversationRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Updates conversation if owned by current_user.user_id."""
    fields = req.model_dump(exclude_unset=True)
    conv = conversation_service.update_conversation(current_user.user_id, conversation_id, fields)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"success": True, "data": conv, "conversation": conv}

@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Deletes conversation if owned by current_user.user_id."""
    success = conversation_service.delete_conversation(current_user.user_id, conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"success": True, "message": "Conversation deleted."}

# ── Message Endpoints (Supabase) ─────────────────────────────────────────────
@app.get("/api/conversations/{conversation_id}/messages")
async def list_messages(
    conversation_id: str,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Lists messages for conversation, verifying current_user.user_id ownership."""
    msgs, total = message_service.list_messages(
        current_user.user_id,
        conversation_id,
        limit=limit,
        offset=offset,
    )
    return {
        "success": True,
        "data": msgs,
        "messages": msgs,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total,
        }
    }

@app.post("/api/conversations/{conversation_id}/messages")
async def create_message(
    conversation_id: str,
    req: CreateMessageRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Creates message in conversation, verifying current_user.user_id ownership."""
    msg = message_service.create_message(
        user_id=current_user.user_id,
        conversation_id=conversation_id,
        role=req.role,
        content=req.content,
        message_type=req.message_type,
        metadata=req.metadata
    )
    if not msg:
        raise HTTPException(status_code=404, detail="Conversation not found or not owned by you.")
    return {"success": True, "data": msg, "message": msg}

# ── Memory Endpoints (Supabase) ──────────────────────────────────────────────
@app.get("/api/memories")
async def list_memories(
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
    memory_type: Optional[str] = Query(None),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Lists all memories partitioned by current_user.user_id."""
    mems, total = memory_service.list_memories(
        current_user.user_id,
        limit=limit,
        offset=offset,
        search=search,
        memory_type=memory_type,
    )
    return {
        "success": True,
        "data": mems,
        "memories": mems,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total,
        }
    }

@app.post("/api/memories")
async def create_memory(
    req: CreateMemoryRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Upserts a memory for current_user.user_id on (user_id, memory_key)."""
    mem = memory_service.set_memory(
        user_id=current_user.user_id,
        memory_key=req.memory_key,
        memory_value=req.memory_value,
        memory_type=req.memory_type,
        importance=req.importance,
        source=req.source,
        metadata=req.metadata,
    )
    return {"success": True, "data": mem, "memory": mem}

@app.get("/api/memories/{identifier}")
async def get_memory(
    identifier: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Retrieves a single memory by key or ID owned by current_user.user_id."""
    mem = memory_service.get_memory(current_user.user_id, identifier)
    if not mem:
        raise HTTPException(status_code=404, detail="Memory not found.")
    return {"success": True, "data": mem, "memory": mem}

@app.patch("/api/memories/{identifier}")
@app.put("/api/memories/{identifier}")
async def update_memory(
    identifier: str,
    req: UpdateMemoryRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Updates an existing memory owned by current_user.user_id."""
    fields = req.model_dump(exclude_unset=True)
    mem = memory_service.update_memory(current_user.user_id, identifier, fields)
    if not mem:
        raise HTTPException(status_code=404, detail="Memory not found.")
    return {"success": True, "data": mem, "memory": mem}

@app.delete("/api/memories/{identifier}")
async def delete_memory(
    identifier: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Deletes memory owned by current_user.user_id."""
    success = memory_service.delete_memory(current_user.user_id, identifier)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found.")
    return {"success": True, "message": "Memory deleted."}

@app.delete("/api/memories")
async def clear_all_memories(
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Safely clears all memories belonging exclusively to current_user.user_id.
    Strictly isolated: WHERE user_id = authenticated_user.user_id.
    """
    count = memory_service.clear_all_memories(current_user.user_id)
    return {
        "success": True,
        "message": f"Successfully cleared {count} personal memories.",
        "cleared_count": count
    }

@app.get("/api/memories/search/relevant")
async def search_relevant_memories(
    q: str = Query(..., min_length=1),
    limit: int = Query(5, ge=1, le=20),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Retrieves ranked relevant memories for a prompt query for current_user.user_id."""
    relevant = memory_service.retrieve_relevant_memories(current_user.user_id, q, limit=limit)
    return {"success": True, "data": relevant, "memories": relevant}

# ── User File Metadata Endpoints (Supabase) ──────────────────────────────────
@app.get("/api/files")
async def list_files(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Lists file metadata owned by current_user.user_id."""
    files, total = user_file_service.list_files(
        current_user.user_id,
        limit=limit,
        offset=offset,
        status=status,
    )
    return {
        "success": True,
        "data": files,
        "files": files,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total,
        }
    }

@app.post("/api/files")
@app.post("/api/files/metadata")
async def record_file(
    req: RecordFileRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Records file metadata tied to current_user.user_id."""
    f = user_file_service.record_file(
        user_id=current_user.user_id,
        original_name=req.original_name,
        storage_key=req.storage_key,
        size_bytes=req.size_bytes,
        mime_type=req.mime_type,
        storage_provider=req.storage_provider,
        status=req.status,
        metadata=req.metadata,
    )
    return {"success": True, "data": f, "file": f}

@app.get("/api/files/{file_id}")
async def get_file(
    file_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Retrieves file metadata owned by current_user.user_id."""
    f = user_file_service.get_file(current_user.user_id, file_id)
    if not f:
        raise HTTPException(status_code=404, detail="File metadata not found.")
    return {"success": True, "data": f, "file": f}

@app.patch("/api/files/{file_id}")
@app.put("/api/files/{file_id}")
async def update_file(
    file_id: str,
    req: UpdateFileRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Updates file metadata owned by current_user.user_id."""
    fields = req.model_dump(exclude_unset=True)
    f = user_file_service.update_file(current_user.user_id, file_id, fields)
    if not f:
        raise HTTPException(status_code=404, detail="File metadata not found.")
    return {"success": True, "data": f, "file": f}

@app.delete("/api/files/{file_id}")
async def delete_file(
    file_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Soft-deletes file metadata owned by current_user.user_id."""
    success = user_file_service.delete_file(current_user.user_id, file_id)
    if not success:
        raise HTTPException(status_code=404, detail="File metadata not found.")
    return {"success": True, "message": "File metadata deleted."}

def _generate_conversation_title(msg: str) -> str:
    clean = re.sub(r'[\r\n\t]+', ' ', msg).strip()
    words = clean.split()
    if len(words) > 6:
        return " ".join(words[:6]) + "..."
    return clean[:35] or "New Conversation"

# ── AI Chat (With In-Memory Voice Streaming & Zero Disk Clutter) ──────────────
@app.post("/chat")
@app.post("/api/chat")
async def chat(
    req: ChatRequest,
    current_user: Optional[CurrentUser] = Depends(get_current_user_optional)
):
    """
    Process user input and return Sarla's response.
    Uses authenticated Supabase user identity when token is provided, preventing user spoofing.
    Uses RAM streaming (/voice/stream) for voice synthesis to avoid writing permanent files.
    """
    msg = req.message.strip()
    if not msg:
        return JSONResponse({
            "response": "Kuch to boliye 😊",
            "emotion": "friendly",
            "gesture": "greetingWave",
            "audio_url": None
        })
    
    # Validate requested model if provided (Allowlist check)
    if req.model:
        from ai.models import model_registry
        from ai.errors import ModelUnavailableError
        try:
            model_registry.validate_model(req.model)
        except ModelUnavailableError as e:
            return JSONResponse(
                {
                    "error": True,
                    "code": "MODEL_UNAVAILABLE",
                    "message": str(e),
                },
                status_code=400,
            )

    # Priority: Derived authenticated identity -> fallback to request body if guest
    user_id = current_user.user_id if current_user else ""
    user_name = current_user.full_name if current_user else (req.user_name or "")
    user_nickname = current_user.nickname if current_user else (req.user_nickname or "")
    user_identifier = f"{user_name} ({current_user.id})" if current_user else f"Guest ({req.user_name or 'Anonymous'})"

    # Persistent conversation integration
    active_conv_id = req.conversation_id
    if current_user:
        try:
            conv = None
            if active_conv_id:
                conv = conversation_service.get_conversation(user_id, active_conv_id)
            if not conv:
                initial_title = _generate_conversation_title(msg)
                conv = conversation_service.create_conversation(
                    user_id=user_id,
                    title=initial_title,
                    mode=req.theme_mode,
                )
                active_conv_id = str(conv["id"])
            else:
                active_conv_id = str(conv["id"])
                # If title is still default, update it with first meaningful user prompt
                current_title = (conv.get("title") or "").strip()
                if current_title in ("New Conversation", "Untitled Conversation", "", None):
                    new_title = _generate_conversation_title(msg)
                    conversation_service.update_conversation(user_id, active_conv_id, {"title": new_title})
                    conv["title"] = new_title

            # Persist user message first (with idempotency support)
            message_service.create_message(
                user_id=user_id,
                conversation_id=active_conv_id,
                role="user",
                content=msg,
                message_type="text",
                client_message_id=req.client_message_id,
            )

            # Check for explicit forget directives before response generation
            try:
                cand = memory_extraction_service.extract_candidates(msg)
                if cand.get("should_forget") and cand.get("forget_targets"):
                    for target in cand["forget_targets"]:
                        memory_service.delete_memory(user_id, target)
            except Exception as f_err:
                logger.warning(f"Error processing forget directive: {f_err}")

        except Exception as err:
            logger.warning(f"Error persisting user message to conversation {active_conv_id}: {err}")

    try:
        # Check if agent execution is explicitly requested or inferred
        if current_user and (req.agent_mode or agent_engine.needs_agent_execution(msg)):
            logger.info(f"Routing request to Agent Planning & Execution Engine for user '{user_id}'.")
            try:
                run = agent_engine.create_run(
                    user_id=user_id,
                    role=current_user.role,
                    goal=msg,
                    conversation_id=active_conv_id,
                    initial_message_id=req.client_message_id,
                    auto_execute=True,
                )
                if run.status == AgentRunStatus.COMPLETED and run.final_result:
                    summary_text = run.final_result.get("summary", "Agent workflow completed successfully.")
                    return JSONResponse({
                        "response": summary_text,
                        "conversation_id": active_conv_id,
                        "agent_run_id": run.id,
                        "agent_status": run.status.value,
                        "emotion": "friendly",
                        "gesture": "nodding",
                        "audio_url": None,
                    })
                elif run.status == AgentRunStatus.WAITING_FOR_APPROVAL:
                    return JSONResponse({
                        "response": f"Agent created a plan but is paused waiting for your approval to proceed with one of the steps. (Run ID: {run.id})",
                        "conversation_id": active_conv_id,
                        "agent_run_id": run.id,
                        "agent_status": run.status.value,
                        "waiting_for_approval": True,
                        "emotion": "thoughtful",
                        "gesture": "stopGesture",
                        "audio_url": None,
                    })
                elif run.status == AgentRunStatus.FAILED:
                    return JSONResponse({
                        "response": f"Agent workflow could not complete: {run.failure_reason}",
                        "conversation_id": active_conv_id,
                        "agent_run_id": run.id,
                        "agent_status": run.status.value,
                        "error": run.failure_reason,
                        "emotion": "concerned",
                        "gesture": "calmGesture",
                        "audio_url": None,
                    })
            except Exception as agent_err:
                logger.warning(f"Agent execution encountered error: {agent_err}. Falling back to standard chat.")

        response = brain.process_input(
            msg, 
            theme_mode=req.theme_mode, 
            user_name=user_name, 
            user_nickname=user_nickname,
            is_live=req.is_live,
            user_id=user_id,
            conversation_id=active_conv_id or "",
            model=req.model,
            task_type=req.task_type,
        )

        # Persist assistant response to conversation
        if current_user and active_conv_id:
            try:
                message_service.create_message(
                    user_id=user_id,
                    conversation_id=active_conv_id,
                    role="assistant",
                    content=response,
                    message_type="text",
                )
            except Exception as err:
                logger.warning(f"Error persisting assistant message to conversation {active_conv_id}: {err}")

            # Check if conversation needs summarization and invalidate context cache for fresh turns
            try:
                from core.services.ai_context_builder import ai_context_builder
                ai_context_builder.summarize_conversation_if_needed(user_id, active_conv_id)
                ai_context_builder.invalidate_cache(user_id, active_conv_id)
            except Exception as sum_err:
                logger.debug(f"Post-message context summary update skipped: {sum_err}")

        # Post-turn durable memory extraction (safe, non-blocking, strictly user_id scoped)
        if current_user:
            try:
                memory_extraction_service.extract_and_apply(
                    user_id=user_id,
                    user_input=msg,
                    ai_response=response
                )
            except Exception as mem_err:
                logger.warning(f"Error extracting memory post-chat: {mem_err}")

        emotion, gesture = classify_emotion(response)
        cleaned_speech = clean_text_for_synthesis(response)
        
        # In-memory RAM streaming audio URL (Zero disk files created)
        encoded_speech = urllib.parse.quote(cleaned_speech)
        audio_url = f"/voice/stream?text={encoded_speech}&language=hi"

        return JSONResponse({
            "response": response,
            "conversation_id": active_conv_id,
            "emotion": emotion,
            "gesture": gesture,
            "audio_url": audio_url,
            "voice_engine": "in_memory_stream"
        })
    except Exception as e:
        logger.error(f"Chat Endpoint Error: {str(e)}")
        # Safe fallback: still attempt durable memory extraction from user message
        if current_user:
            try:
                memory_extraction_service.extract_and_apply(
                    user_id=user_id,
                    user_input=msg,
                    ai_response=""
                )
            except Exception as mem_err:
                logger.warning(f"Error extracting memory during fallback: {mem_err}")

        # Notice: User message was safely retained; return recoverable response with active_conv_id
        return JSONResponse({
            "response": "Maaf kijiye, server busy hai ya response generate karne mein samasya aayi. Aapka message save ho chuka hai, kripya dobara try karein 😊",
            "conversation_id": active_conv_id,
            "emotion": "concerned",
            "gesture": "calmGesture",
            "audio_url": None,
            "error": "AI generation error",
            "retryable": True
        }, status_code=200)

# ── AI Model Registry & Health Endpoints ─────────────────────────────────────
@app.get("/api/ai/models")
async def get_ai_models():
    """
    Returns public catalog of available AI models for frontend selection.
    Sanitized: contains zero secret keys, tokens, or internal URLs.
    """
    from ai.models import model_registry
    return JSONResponse({
        "models": model_registry.list_public_models(),
        "default_model": model_registry.get_default_model().model_name,
    })


@app.get("/api/ai/health")
async def get_ai_health():
    """Returns AI provider and model health telemetry."""
    from ai.orchestrator import ai_orchestrator
    return JSONResponse(ai_orchestrator.get_health_status())


# ── AI Tool Registry & Execution Endpoints (Task 1.8) ─────────────────────────
@app.get("/api/ai/tools")
async def get_ai_tools(
    current_user: Optional[CurrentUser] = Depends(get_current_user_optional)
):
    """
    Returns public catalog of authorized AI tools for frontend/user discovery.
    Strictly sanitized: zero secrets, passwords, or internal handlers exposed.
    """
    from ai.tools.registry import tool_registry
    user_role = current_user.role if current_user else "user"
    is_authenticated = bool(current_user)
    tools = tool_registry.list_tools(user_role=user_role, authenticated=is_authenticated, enabled_only=True)
    return JSONResponse({
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category.value,
                "action_type": t.action_type.value,
                "risk_level": t.risk_level.value,
                "requires_authentication": t.requires_authentication,
                "requires_confirmation": t.requires_confirmation,
                "input_schema": t.input_schema,
            }
            for t in tools
        ],
        "authenticated": is_authenticated,
        "role": user_role,
    })


@app.post("/api/ai/tools/execute")
async def execute_tool_endpoint(
    req: ToolExecuteRequest,
    current_user: Optional[CurrentUser] = Depends(get_current_user_optional)
):
    """
    Executes a registered tool through the centralized execution layer.
    Canonical identity (MongoDB user_id) is enforced. AI/body user_id cannot spoof identity.
    """
    from ai.tools.executor import tool_executor
    user_id = current_user.user_id if current_user else ""
    user_role = current_user.role if current_user else "user"

    result = tool_executor.execute(
        tool_name=req.tool_name,
        arguments=req.arguments,
        user_id=user_id,
        role=user_role,
        conversation_id=req.conversation_id or "",
        confirmation_token=req.confirmation_token,
    )
    status_code = 200 if result.success or result.requires_confirmation else 400
    return JSONResponse(result.to_dict(), status_code=status_code)


@app.post("/api/ai/tools/confirm")
async def confirm_tool_execution(
    req: ToolConfirmRequest,
    current_user: Optional[CurrentUser] = Depends(get_current_user_optional)
):
    """
    Confirms and executes a pending state-changing tool action using a secure confirmation token.
    Token is validated, single-use, and tied strictly to current_user.user_id.
    """
    from ai.tools.confirmation import confirmation_manager
    from ai.tools.executor import tool_executor

    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required to confirm tool execution.")

    pending = confirmation_manager.get_pending(req.confirmation_token)
    if not pending:
        raise HTTPException(status_code=400, detail="Confirmation token is invalid, expired, or already used.")

    if pending.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Confirmation token does not belong to this user.")

    result = tool_executor.execute(
        tool_name=pending.tool_name,
        arguments=pending.arguments,
        user_id=current_user.user_id,
        role=current_user.role,
        conversation_id=req.conversation_id or pending.conversation_id,
        tool_call_id=pending.tool_call_id,
        confirmation_token=req.confirmation_token,
    )
    status_code = 200 if result.success else 400
    return JSONResponse(result.to_dict(), status_code=status_code)


@app.get("/api/tool-executions")
@app.get("/api/ai/tools/executions")
async def list_tool_executions_endpoint(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    conversation_id: Optional[str] = Query(None),
    tool_name: Optional[str] = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Lists tool execution audit records strictly scoped to authenticated current_user.user_id.
    Query parameters cannot be used to retrieve another user's executions.
    """
    if supabase_manager.is_connected and supabase_manager.client:
        try:
            tbl = supabase_manager.table("tool_executions")
            if tbl is not None:
                query = tbl.select("*", count="exact").eq("user_id", current_user.user_id)
                if conversation_id:
                    query = query.eq("conversation_id", conversation_id)
                if tool_name:
                    query = query.eq("tool_name", tool_name)
                res = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
                if res and isinstance(res.data, list):
                    total = res.count if hasattr(res, "count") and res.count is not None else len(res.data)
                    return JSONResponse({
                        "success": True,
                        "data": res.data,
                        "tool_executions": res.data,
                        "pagination": {"limit": limit, "offset": offset, "total": total}
                    })
        except Exception as e:
            logger.debug(f"Error listing tool executions: {e}")
    return JSONResponse({
        "success": True,
        "data": [],
        "tool_executions": [],
        "pagination": {"limit": limit, "offset": offset, "total": 0}
    })


# ── AI Agent Planning & Execution Engine Endpoints (Task 1.9) ────────────────
@app.post("/api/agent/runs", status_code=201)
async def create_agent_run_endpoint(
    req: AgentRunCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Creates a new multi-step agent run with a validated execution plan.
    Strictly derives identity from MongoDB session.
    """
    try:
        run = agent_engine.create_run(
            user_id=current_user.user_id,
            role=current_user.role,
            goal=req.goal,
            conversation_id=req.conversation_id,
            initial_message_id=req.initial_message_id,
            idempotency_key=req.idempotency_key,
            max_steps=req.max_steps,
            execution_mode=req.execution_mode,
            auto_execute=req.auto_execute,
        )
        return JSONResponse(run.to_dict(), status_code=201)
    except AgentEngineError as e:
        return JSONResponse(e.to_dict(), status_code=e.status_code)
    except Exception as e:
        logger.error(f"Unexpected error creating agent run: {e}")
        return JSONResponse({"error": True, "code": "AGENT_ERROR", "message": "Failed to create agent run."}, status_code=500)


@app.get("/api/agent/runs")
async def list_agent_runs_endpoint(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    conversation_id: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Lists agent execution runs strictly scoped to the authenticated user.
    """
    try:
        runs = agent_engine.list_runs(
            user_id=current_user.user_id,
            limit=limit,
            offset=offset,
            status=status,
            conversation_id=conversation_id,
        )
        return JSONResponse({
            "runs": [r.to_dict() for r in runs],
            "total": len(runs),
            "limit": limit,
            "offset": offset,
        })
    except AgentEngineError as e:
        return JSONResponse(e.to_dict(), status_code=e.status_code)


@app.get("/api/agent/runs/{agent_run_id}")
async def get_agent_run_endpoint(
    agent_run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Retrieves full details, step records, and observability events for an agent run.
    Guarantees user isolation; cross-user queries return 403 Forbidden.
    """
    try:
        detail = agent_engine.get_run_detail(current_user.user_id, agent_run_id)
        return JSONResponse({
            "run": detail.run.to_dict(),
            "steps": [s.to_dict() for s in detail.steps],
            "events": detail.events,
        })
    except AgentEngineError as e:
        return JSONResponse(e.to_dict(), status_code=e.status_code)


@app.post("/api/agent/runs/{agent_run_id}/pause")
async def pause_agent_run_endpoint(
    agent_run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Pauses an active or queued agent run while preserving full execution state.
    """
    try:
        updated = agent_engine.pause_run(agent_run_id, current_user.user_id)
        return JSONResponse({
            "success": True,
            "message": "Agent run paused successfully.",
            "run": updated.to_dict(),
        })
    except AgentEngineError as e:
        return JSONResponse(e.to_dict(), status_code=e.status_code)


@app.post("/api/agent/runs/{agent_run_id}/resume")
async def resume_agent_run_endpoint(
    agent_run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Resumes execution of a paused agent run from its current pending step.
    """
    try:
        updated = agent_engine.resume_run(agent_run_id, current_user.user_id, current_user.role)
        return JSONResponse({
            "success": True,
            "message": "Agent run resumed successfully.",
            "run": updated.to_dict(),
        })
    except AgentEngineError as e:
        return JSONResponse(e.to_dict(), status_code=e.status_code)


@app.post("/api/agent/runs/{agent_run_id}/cancel")
async def cancel_agent_run_endpoint(
    agent_run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Cancels an active or paused agent run. Finalized runs cannot be cancelled.
    """
    try:
        updated = agent_engine.cancel_run(agent_run_id, current_user.user_id)
        return JSONResponse({
            "success": True,
            "message": "Agent run cancelled successfully.",
            "run": updated.to_dict(),
        })
    except AgentEngineError as e:
        return JSONResponse(e.to_dict(), status_code=e.status_code)


@app.post("/api/agent/runs/{agent_run_id}/approve")
async def approve_agent_step_endpoint(
    agent_run_id: str,
    req: Optional[AgentApprovalRequest] = None,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Explicit human approval gate: Approves a pending step and resumes execution.
    """
    try:
        step_id = req.step_id if req else None
        updated = agent_engine.approve_step(
            agent_run_id,
            current_user.user_id,
            current_user.role,
            step_id=step_id,
        )
        return JSONResponse({
            "success": True,
            "message": "Agent step approved. Execution resumed.",
            "run": updated.to_dict(),
        })
    except AgentEngineError as e:
        return JSONResponse(e.to_dict(), status_code=e.status_code)


@app.post("/api/agent/runs/{agent_run_id}/reject")
async def reject_agent_step_endpoint(
    agent_run_id: str,
    req: Optional[AgentRejectionRequest] = None,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Explicit human approval gate: Rejects a pending step, cancelling the agent run.
    """
    try:
        step_id = req.step_id if req else None
        reason = req.reason if req else None
        updated = agent_engine.reject_step(
            agent_run_id,
            current_user.user_id,
            step_id=step_id,
            reason=reason,
        )
        return JSONResponse({
            "success": True,
            "message": "Agent step rejected. Execution cancelled.",
            "run": updated.to_dict(),
        })
    except AgentEngineError as e:
        return JSONResponse(e.to_dict(), status_code=e.status_code)



# ── AI Streaming Chat Endpoint (SSE text/event-stream) ────────────────────────
@app.post("/api/chat/stream")
async def chat_stream(
    req: ChatRequest,
    current_user: Optional[CurrentUser] = Depends(get_current_user_optional)
):
    """
    Streaming AI chat endpoint with Server-Sent Events (SSE).
    - Validates model allowlist.
    - Persists user message first with idempotency.
    - Streams normalized chunks as they are generated.
    - Accumulates the full assistant response and persists ONE message upon completion.
    - Safely handles errors without saving corrupted assistant responses.
    """
    msg = req.message.strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # Validate model allowlist
    if req.model:
        from ai.models import model_registry
        from ai.errors import ModelUnavailableError
        try:
            model_registry.validate_model(req.model)
        except ModelUnavailableError as e:
            raise HTTPException(status_code=400, detail=str(e))

    user_id = current_user.user_id if current_user else ""
    user_name = current_user.full_name if current_user else (req.user_name or "")
    user_nickname = current_user.nickname if current_user else (req.user_nickname or "")

    # Persistent conversation integration
    active_conv_id = req.conversation_id
    if current_user:
        try:
            conv = None
            if active_conv_id:
                conv = conversation_service.get_conversation(user_id, active_conv_id)
            if not conv:
                conv = conversation_service.create_conversation(
                    user_id=user_id,
                    title=_generate_conversation_title(msg),
                    mode=req.theme_mode,
                )
                active_conv_id = str(conv["id"])
            else:
                active_conv_id = str(conv["id"])

            message_service.create_message(
                user_id=user_id,
                conversation_id=active_conv_id,
                role="user",
                content=msg,
                message_type="text",
                client_message_id=req.client_message_id,
            )
        except Exception as err:
            logger.warning(f"Error persisting user message in stream: {err}")

    async def event_generator():
        from ai.orchestrator import ai_orchestrator
        from core.services.ai_context_builder import ai_context_builder
        import json

        built_ctx = ai_context_builder.build_context(
            user_input=msg,
            user_id=user_id,
            conversation_id=active_conv_id or "",
            theme_mode=req.theme_mode,
            user_name=user_name,
            user_nickname=user_nickname,
            is_live=req.is_live,
        )

        full_content = []
        try:
            async for chunk in ai_orchestrator.stream_from_context(
                user_input=msg,
                built_context=built_ctx,
                theme_mode=req.theme_mode,
                model=req.model,
                is_live=req.is_live,
                task_type=req.task_type,
                user_id=user_id,
                conversation_id=active_conv_id or "",
            ):
                if chunk.content:
                    full_content.append(chunk.content)
                    data = json.dumps({"type": "chunk", "content": chunk.content})
                    yield f"data: {data}\n\n"

            final_text = "".join(full_content)

            # Persist ONE assistant message to Supabase
            if current_user and active_conv_id and final_text:
                try:
                    message_service.create_message(
                        user_id=user_id,
                        conversation_id=active_conv_id,
                        role="assistant",
                        content=final_text,
                        message_type="text",
                    )
                    ai_context_builder.summarize_conversation_if_needed(user_id, active_conv_id)
                    ai_context_builder.invalidate_cache(user_id, active_conv_id)
                except Exception as p_err:
                    logger.warning(f"Error persisting streamed assistant message: {p_err}")

            done_payload = json.dumps({
                "type": "done",
                "conversation_id": active_conv_id,
                "response": final_text,
            })
            yield f"data: {done_payload}\n\n"

        except Exception as err:
            logger.error(f"Stream generation error: {err}")
            err_data = json.dumps({
                "type": "error",
                "error": "STREAM_GENERATION_FAILED",
                "message": "AI stream encountered an error."
            })
            yield f"data: {err_data}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/chat/upload")
async def chat_upload_file(file: UploadFile = File(...), category: str = Form("general")):
    """Handles PDF/TXT/Image file uploads from chat, extracts text, and stores in knowledge chunks."""
    try:
        content = ""
        ext = file.filename.split(".")[-1].lower() if file.filename else ""
        
        # Read file bytes
        file_bytes = await file.read()
        
        if ext == "pdf":
            try:
                import PyPDF2
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text:
                        content += text + "\n\n"
            except ImportError:
                return JSONResponse({"success": False, "error": "PyPDF2 is not installed."})
        elif ext in ["txt", "md", "csv"]:
            content = file_bytes.decode("utf-8", errors="ignore")
        elif ext in ["png", "jpg", "jpeg"]:
            try:
                from PIL import Image
                import pytesseract
                img = Image.open(io.BytesIO(file_bytes))
                content = str(pytesseract.image_to_string(img))
            except Exception as e:
                logger.warning(f"Image OCR failed: {e}")
                content = "Image content could not be extracted automatically."
        else:
            return JSONResponse({"success": False, "error": f"Unsupported file format: {ext}"})
            
        if not content.strip():
            return JSONResponse({"success": False, "error": "No extractable text found in file."})
            
        # Send to admin_service to chunk and store permanently
        title = file.filename or "Uploaded Document"
        result = admin_service.ingest_document(title=title, content=content, category=category)
        
        return JSONResponse({
            "success": True, 
            "message": f"Successfully memorized {file.filename}.",
            "details": f"Extracted {len(content)} characters and saved permanently."
        })
    except Exception as e:
        logger.error(f"File upload error: {str(e)}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

# ── In-Memory Streaming Voice Endpoints (Zero Disk Writes) ──────────────────
@app.get("/voice/stream")
async def voice_stream_get(text: str = Query(...), language: str = "hi"):
    """Streams audio chunks directly from RAM to browser without writing any file to disk."""
    if not text.strip():
        return JSONResponse({"error": "Empty text"}, status_code=400)
    return StreamingResponse(
        natural_voice_manager.stream_voice_chunks(text, language=language),
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-cache",
            "Accept-Ranges": "bytes",
        }
    )

class StreamAudioRequest(BaseModel):
    text: str
    language: str = "hi"

@app.post("/voice/stream")
async def voice_stream_post(req: StreamAudioRequest):
    """Streams audio chunks directly from RAM to browser without writing any file to disk."""
    if not req.text.strip():
        return JSONResponse({"error": "Empty text"}, status_code=400)
    return StreamingResponse(
        natural_voice_manager.stream_voice_chunks(req.text, language=req.language),
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-cache",
            "Accept-Ranges": "bytes",
        }
    )

@app.get("/voice/health")
async def voice_health():
    """Health check for Sarala voice system."""
    try:
        status = get_voice_health()
    except Exception as e:
        status = {
            "provider": "streaming_ram",
            "error": str(e),
            "model_loaded": True,
            "device": "in_memory",
        }
    return JSONResponse(status)

class VoiceSynthesizeRequest(BaseModel):
    text: str
    language: str = "hi"
    engine: str = "auto"
    provider: Optional[str] = None

@app.post("/voice/synthesize")
async def voice_synthesize(req: VoiceSynthesizeRequest):
    """Direct voice synthesis with fallback to in-memory streaming."""
    txt = req.text.strip()
    if not txt:
        return JSONResponse({"success": False, "error": "Text cannot be empty"}, status_code=400)

    try:
        res = natural_voice_manager.synthesize(txt, language=req.language, engine=req.engine)
        return JSONResponse(res)
    except Exception as e:
        logger.warning(f"Voice synthesis fallback: {e}")
        encoded = urllib.parse.quote(txt)
        return JSONResponse({
            "success": True,
            "audio_url": f"/voice/stream?text={encoded}&language={req.language}",
            "engine": "neural_stream",
            "in_memory": True
        })

@app.get("/voice/audio/{filename}")
async def get_voice_audio(filename: str):
    """Serve reference WAV or sample audio files safely."""
    import re
    if not re.match(r"^[a-zA-Z0-9_\-]+\.(wav|mp3)$", filename):
        return JSONResponse({"error": "Invalid filename format"}, status_code=400)
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ref_path = os.path.join(os.path.dirname(base_dir), "voice", "reference", filename)
    if os.path.exists(ref_path):
        return FileResponse(ref_path, media_type="audio/wav")

    out_path = os.path.join(os.path.dirname(base_dir), "voice", "output", filename)
    if os.path.exists(out_path):
        return FileResponse(out_path, media_type="audio/wav")

    return JSONResponse({"error": "Audio file not found"}, status_code=404)

# =============================================================================
# ADMIN DASHBOARD & TRAINING MODE API ENDPOINTS
# =============================================================================

@app.get("/api/admin/training")
async def list_training_items(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    admin: CurrentUser = Depends(get_current_admin)
):
    """Fetch paginated training items from Supabase with search & filtering (Admin only)."""
    result = admin_service.get_training_items(category=category, search=search, page=page, limit=limit)
    return JSONResponse(result)

@app.post("/api/admin/training")
async def create_training_item(
    req: TrainingItemRequest,
    admin: CurrentUser = Depends(get_current_admin)
):
    """Create a new training item and permanently save to Supabase (Admin only)."""
    result = admin_service.save_training_item(req.model_dump())
    return JSONResponse(result)

@app.put("/api/admin/training/{item_id}")
async def update_training_item(
    item_id: str, 
    updates: Dict[str, Any] = Body(...),
    admin: CurrentUser = Depends(get_current_admin)
):
    """Update an existing training item in Supabase (Admin only)."""
    result = admin_service.update_training_item(item_id, updates)
    return JSONResponse(result)

@app.delete("/api/admin/training/{item_id}")
async def delete_training_item(
    item_id: str,
    admin: CurrentUser = Depends(get_current_admin)
):
    """Delete a training item from Supabase (Admin only)."""
    result = admin_service.delete_training_item(item_id)
    return JSONResponse(result)

@app.post("/api/admin/training/bulk")
async def bulk_import_training_items(
    req: BulkTrainingRequest,
    admin: CurrentUser = Depends(get_current_admin)
):
    """Bulk import training items to Supabase (Admin only)."""
    items_dicts = [it.model_dump() for it in req.items]
    result = admin_service.bulk_save_training_items(items_dicts)
    return JSONResponse(result)

@app.get("/api/admin/knowledge")
async def list_knowledge_documents(admin: CurrentUser = Depends(get_current_admin)):
    """List all ingested knowledge documents (Admin only)."""
    docs = admin_service.get_knowledge_documents()
    return JSONResponse({"success": True, "documents": docs})

@app.post("/api/admin/knowledge")
async def ingest_knowledge_document(
    req: IngestKnowledgeRequest,
    admin: CurrentUser = Depends(get_current_admin)
):
    """Ingest large knowledge document and chunk for Big Data RAG (Admin only)."""
    result = admin_service.ingest_document(title=req.title, content=req.content, category=req.category)
    return JSONResponse(result)

@app.get("/api/admin/stats")
async def get_admin_system_stats(admin: CurrentUser = Depends(get_current_admin)):
    """Get system stats for dashboard telemetry (Admin only)."""
    stats = admin_service.get_system_stats()
    return JSONResponse({"success": True, "stats": stats})

# =============================================================================
# ISOLATED VOICE BENCHMARK ENDPOINTS
# =============================================================================
BENCHMARK_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "voice", "benchmark")

@app.get("/api/benchmark/report")
async def get_benchmark_report():
    """Returns the latest isolated voice engine benchmark report."""
    report_file = os.path.join(BENCHMARK_DIR, "voice_benchmark_report.json")
    if not os.path.exists(report_file):
        return JSONResponse({"error": "Benchmark report not generated yet."}, status_code=404)
    
    try:
        with open(report_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"error": f"Failed to read report: {str(e)}"}, status_code=500)

@app.get("/api/benchmark/audio/{filename}")
async def get_benchmark_audio(filename: str):
    """Streams isolated voice benchmark WAV files."""
    import re
    if not re.match(r"^[a-zA-Z0-9_\-]+\.wav$", filename):
        return JSONResponse({"error": "Invalid filename"}, status_code=400)
    
    file_path = os.path.join(BENCHMARK_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="audio/wav")
    
    sample_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "voice", "samples", filename)
    if os.path.exists(sample_path):
        return FileResponse(sample_path, media_type="audio/wav")

    return JSONResponse({"error": f"Benchmark audio file {filename} not found."}, status_code=404)

@app.post("/api/benchmark/approve")
async def approve_engine(req: ApproveEngineRequest):
    """Records manual approval of preferred voice engine without mutating LiveAvatar."""
    report_file = os.path.join(BENCHMARK_DIR, "voice_benchmark_report.json")
    approval_file = os.path.join(os.path.dirname(BENCHMARK_DIR), "selected_engine.json")
    
    approval_data = {
        "approved_engine_key": req.engine_key,
        "approved_engine_name": req.engine_name,
        "notes": req.notes,
        "approved_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "live_avatar_integrated": False,
        "status": "Awaiting Phase 2 integration pipeline"
    }
    
    try:
        with open(approval_file, "w", encoding="utf-8") as f:
            json.dump(approval_data, f, indent=2)
            
        if os.path.exists(report_file):
            with open(report_file, "r", encoding="utf-8") as f:
                rep = json.load(f)
            rep["approval_status"] = approval_data
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(rep, f, indent=2, ensure_ascii=False)
                
        return JSONResponse({
            "success": True,
            "message": f"Successfully approved {req.engine_name}.",
            "approval": approval_data
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)
