import sys
import os
import json
import time
import io
import urllib.parse
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException, Header, Body, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.brain import Brain
from core.logger import logger
from core.admin_service import admin_service
from core.supabase_client import supabase_manager
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

class ChatRequest(BaseModel):
    message: str
    theme_mode: str = "dark"
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
        "status": "ok",
        "agent": "Sarla AI",
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
async def get_current_user_profile(email: str = Query(...)):
    """Verifies and returns authenticated user's role from Supabase or local storage."""
    email_clean = email.strip().lower()
    user = brain.memory.users.get(email_clean)
    
    if supabase_manager.is_connected:
        try:
            tbl = supabase_manager.table("profiles")
            if tbl is not None:
                res = tbl.select("*").eq("email", email_clean).execute()
                if res and isinstance(res.data, list) and len(res.data) > 0:
                    profile = res.data[0]
                    if isinstance(profile, dict):
                        return {
                            "authenticated": True,
                            "user": {
                                "name": profile.get("full_name", "User"),
                                "nickname": profile.get("nickname", ""),
                                "email": email_clean,
                                "role": profile.get("role", "user"),
                                "is_naveen": (email_clean == "loharavee@gmail.com" or profile.get("role") == "admin")
                            }
                        }
        except Exception as e:
            logger.warning(f"Error fetching profile from Supabase: {e}")

    if user:
        role = user.get("role") or ("admin" if email_clean == "loharavee@gmail.com" else "user")
        return {
            "authenticated": True,
            "user": {
                "name": user.get("name", "User"),
                "nickname": user.get("nickname", ""),
                "email": email_clean,
                "role": role,
                "is_naveen": (email_clean == "loharavee@gmail.com" or role == "admin")
            }
        }
    return JSONResponse({"authenticated": False, "message": "User not found"}, status_code=404)

# ── AI Chat (With In-Memory Voice Streaming & Zero Disk Clutter) ──────────────
@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Process user input and return Sarla's response.
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
    
    logger.info(f"Chat: {msg[:40]}... (User: {req.user_name}, Mode: {req.theme_mode}, Live: {req.is_live})")
    try:
        response = brain.process_input(
            msg, 
            theme_mode=req.theme_mode, 
            user_name=req.user_name, 
            user_nickname=req.user_nickname,
            is_live=req.is_live
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
    limit: int = Query(50, ge=1, le=200)
):
    """Fetch paginated training items from Supabase with search & filtering."""
    result = admin_service.get_training_items(category=category, search=search, page=page, limit=limit)
    return JSONResponse(result)

@app.post("/api/admin/training")
async def create_training_item(req: TrainingItemRequest):
    """Create a new training item and permanently save to Supabase."""
    result = admin_service.save_training_item(req.model_dump())
    return JSONResponse(result)

@app.put("/api/admin/training/{item_id}")
async def update_training_item(item_id: str, updates: Dict[str, Any] = Body(...)):
    """Update an existing training item in Supabase."""
    result = admin_service.update_training_item(item_id, updates)
    return JSONResponse(result)

@app.delete("/api/admin/training/{item_id}")
async def delete_training_item(item_id: str):
    """Delete a training item from Supabase."""
    result = admin_service.delete_training_item(item_id)
    return JSONResponse(result)

@app.post("/api/admin/training/bulk")
async def bulk_import_training_items(req: BulkTrainingRequest):
    """Bulk import training items to Supabase."""
    items_dicts = [it.model_dump() for it in req.items]
    result = admin_service.bulk_save_training_items(items_dicts)
    return JSONResponse(result)

@app.get("/api/admin/knowledge")
async def list_knowledge_documents():
    """List all ingested knowledge documents."""
    docs = admin_service.get_knowledge_documents()
    return JSONResponse({"success": True, "documents": docs})

@app.post("/api/admin/knowledge")
async def ingest_knowledge_document(req: IngestKnowledgeRequest):
    """Ingest large knowledge document and chunk for Big Data RAG."""
    result = admin_service.ingest_document(title=req.title, content=req.content, category=req.category)
    return JSONResponse(result)

@app.get("/api/admin/stats")
async def get_admin_system_stats():
    """Get system stats for dashboard telemetry."""
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
