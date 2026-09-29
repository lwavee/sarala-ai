import sys
import os
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
    user_file_service,
)
from voice.natural_voice import natural_voice_manager, clean_text_for_synthesis
from voice.voice_service import get_voice_health, synthesize_sarala_voice, VoiceSynthesisError

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

# ── Request / Response Models ────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: str
    password: str

class SignupRequest(BaseModel):
    name: str
    nickname: str = ""
    email: str
    password: str
    role: str = "user"

class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None

class PreferencesUpdateRequest(BaseModel):
    theme_mode: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None
    voice_enabled: Optional[bool] = None
    notifications_enabled: Optional[bool] = None
    assistant_personality: Optional[str] = None
    preferred_voice: Optional[str] = None
    preferred_model: Optional[str] = None
    ui_preferences: Optional[Dict[str, Any]] = None
    persona_settings: Optional[Dict[str, Any]] = None

class CreateConversationRequest(BaseModel):
    title: str = "New Conversation"
    mode: str = "normal"

class UpdateConversationRequest(BaseModel):
    title: Optional[str] = None
    mode: Optional[str] = None
    status: Optional[str] = None

class CreateMessageRequest(BaseModel):
    content: str
    role: str = "user"
    message_type: str = "text"
    metadata: Optional[Dict[str, Any]] = None

class CreateMemoryRequest(BaseModel):
    memory_key: str
    memory_value: Any
    memory_type: str = "personal"
    importance: float = 1.0
    source: str = "user_input"
    metadata: Optional[Dict[str, Any]] = None

class RecordFileRequest(BaseModel):
    original_name: str
    storage_key: str
    size_bytes: int
    mime_type: str = "application/octet-stream"
    storage_provider: str = "local"
    status: str = "uploaded"
    metadata: Optional[Dict[str, Any]] = None

class ChatRequest(BaseModel):
    message: str
    theme_mode: str = "normal"
    user_name: str = ""
    user_nickname: str = ""
    is_live: bool = False

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

# ── General Routes ───────────────────────────────────────────────────────────
@app.get("/")
async def index():
    """Redirect visitors from backend Render URL directly to the official modern Vercel UI."""
    return RedirectResponse(url="https://sarala-ai-pi.vercel.app/")


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "agent": "Sarla AI",
        "mongodb_connected": mongodb_manager.is_connected,
        "supabase_connected": supabase_manager.is_connected
    }

# ── Authentication & Profiles ────────────────────────────────────────────────
@app.post("/api/login")
async def login(req: LoginRequest):
    result = brain.memory.authenticate_user(req.email, req.password)
    return JSONResponse(result)

@app.post("/api/signup")
async def signup(req: SignupRequest):
    result = brain.memory.register_user(req.name, req.nickname, req.email, req.password, req.role)
    return JSONResponse(result)

@app.get("/api/auth/me")
async def get_current_user_profile(current_user: CurrentUser = Depends(get_current_user)):
    """Verifies and returns authenticated user's role and profile from MongoDB + Supabase."""
    prof = profile_service.get_profile(current_user.user_id) or {}
    return {
        "authenticated": True,
        "user": {
            "id": current_user.id,
            "user_id": current_user.user_id,
            "name": prof.get("full_name") or current_user.full_name,
            "nickname": prof.get("nickname") or current_user.nickname,
            "email": current_user.email,
            "role": current_user.role,
            "is_active": current_user.is_active,
            "avatar_url": prof.get("avatar_url", ""),
            "bio": prof.get("bio", ""),
        }
    }

# ── Application Profile Endpoints (Supabase) ──────────────────────────────────
@app.get("/api/profile")
async def get_user_profile(current_user: CurrentUser = Depends(get_current_user)):
    """Fetches application profile for the authenticated user from Supabase."""
    prof = profile_service.get_profile(current_user.user_id) or {}
    return {
        "success": True,
        "profile": {
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
    }

@app.put("/api/profile")
async def update_user_profile(
    updates: ProfileUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Updates profile. Strips role, is_active, and user_id to prevent escalation."""
    fields = updates.model_dump(exclude_unset=True)
    updated = profile_service.update_user_profile(current_user.user_id, fields)
    return {"success": True, "profile": updated}

# ── User Preferences Endpoints (Supabase) ────────────────────────────────────
@app.get("/api/preferences")
async def get_preferences(current_user: CurrentUser = Depends(get_current_user)):
    """Fetches user preferences partitioned by user_id."""
    prefs = preferences_service.get_preferences(current_user.user_id)
    return {"success": True, "preferences": prefs}

@app.put("/api/preferences")
async def update_preferences(
    updates: PreferencesUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Updates user preferences for the authenticated user_id."""
    fields = updates.model_dump(exclude_unset=True)
    updated = preferences_service.update_preferences(current_user.user_id, fields)
    return {"success": True, "preferences": updated}

# ── Conversation Endpoints (Supabase) ────────────────────────────────────────
@app.get("/api/conversations")
async def list_conversations(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Lists conversations strictly owned by current_user.user_id."""
    convs = conversation_service.list_conversations(current_user.user_id, limit=limit, offset=offset)
    return {"success": True, "conversations": convs}

@app.post("/api/conversations")
async def create_conversation(
    req: CreateConversationRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Creates a new conversation owned by current_user.user_id."""
    conv = conversation_service.create_conversation(current_user.user_id, title=req.title, mode=req.mode)
    return {"success": True, "conversation": conv}

@app.get("/api/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Retrieves conversation if owned by current_user.user_id."""
    conv = conversation_service.get_conversation(current_user.user_id, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"success": True, "conversation": conv}

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
    return {"success": True, "conversation": conv}

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
    msgs = message_service.list_messages(current_user.user_id, conversation_id, limit=limit, offset=offset)
    return {"success": True, "messages": msgs}

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
    return {"success": True, "message": msg}

# ── Memory Endpoints (Supabase) ──────────────────────────────────────────────
@app.get("/api/memories")
async def list_memories(current_user: CurrentUser = Depends(get_current_user)):
    """Lists all memories partitioned by current_user.user_id."""
    mems = memory_service.list_memories(current_user.user_id)
    return {"success": True, "memories": mems}

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
    return {"success": True, "memory": mem}

@app.delete("/api/memories/{memory_key}")
async def delete_memory(
    memory_key: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Deletes memory owned by current_user.user_id."""
    success = memory_service.delete_memory(current_user.user_id, memory_key)
    return {"success": success}

# ── User File Metadata Endpoints (Supabase) ──────────────────────────────────
@app.get("/api/files")
async def list_files(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Lists file metadata owned by current_user.user_id."""
    files = user_file_service.list_files(current_user.user_id, limit=limit, offset=offset)
    return {"success": True, "files": files}

@app.post("/api/files")
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
    return {"success": True, "file": f}

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

# ── AI Chat (With In-Memory Voice Streaming & Zero Disk Clutter) ──────────────
@app.post("/chat")
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
    
    # Priority: Derived authenticated identity -> fallback to request body if guest
    user_id = current_user.user_id if current_user else ""
    user_name = current_user.full_name if current_user else (req.user_name or "")
    user_nickname = current_user.nickname if current_user else (req.user_nickname or "")
    user_identifier = f"{user_name} ({current_user.id})" if current_user else f"Guest ({req.user_name or 'Anonymous'})"

    logger.info(f"Chat: {msg[:40]}... (User: {user_identifier}, Mode: {req.theme_mode}, Live: {req.is_live})")
    try:
        response = brain.process_input(
            msg, 
            theme_mode=req.theme_mode, 
            user_name=user_name, 
            user_nickname=user_nickname,
            is_live=req.is_live,
            user_id=user_id,
        )

        emotion, gesture = classify_emotion(response)
        cleaned_speech = clean_text_for_synthesis(response)
        
        # In-memory RAM streaming audio URL (Zero disk files created)
        encoded_speech = urllib.parse.quote(cleaned_speech)
        audio_url = f"/voice/stream?text={encoded_speech}&language=hi"

        return JSONResponse({
            "response": response,
            "emotion": emotion,
            "gesture": gesture,
            "audio_url": audio_url,
            "voice_engine": "in_memory_stream"
        })
    except Exception as e:
        logger.error(f"Chat Endpoint Error: {str(e)}")
        return JSONResponse({
            "response": "Maaf kijiye, server busy hai ya kuch technical issue hai. Dobara try karein 😊",
            "emotion": "concerned",
            "gesture": "calmGesture",
            "audio_url": None
        }, status_code=200)

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
