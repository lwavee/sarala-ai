import sys
import os
import json
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from core.brain import Brain
from core.logger import logger

# ── Lifespan Context Manager ──────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Sarla Web Server is starting up...")
    yield

# ── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(title="Sarla AI API", version="1.0.0", lifespan=lifespan)

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

# ── Models ───────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: str
    password: str

class SignupRequest(BaseModel):
    name: str
    nickname: str = ""
    email: str
    password: str

class ChatRequest(BaseModel):
    message: str
    theme_mode: str = "dark"
    user_name: str = ""
    user_nickname: str = ""
    is_live: bool = False

# ── Routes ───────────────────────────────────────────────────────────────────
@app.get("/")
async def index():
    """Serve the main chat UI."""
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.post("/api/login")
async def login(req: LoginRequest):
    result = brain.memory.authenticate_user(req.email, req.password)
    return JSONResponse(result)

@app.post("/api/signup")
async def signup(req: SignupRequest):
    result = brain.memory.register_user(req.name, req.nickname, req.email, req.password)
    return JSONResponse(result)

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

# ── Voice Cloning & Natural Voice Integration ─────────────────────────────────────
import re
import asyncio
from voice.natural_voice import natural_voice_manager, clean_text_for_synthesis
from voice.voice_service import get_voice_health, synthesize_sarala_voice, generate_sarala_voice, VoiceSynthesisError

@app.post("/chat")
async def chat(req: ChatRequest):
    """Process a user message and return Sarla's response with cloned voice audio from backend/voice/output & animation metadata."""
    msg = req.message.strip()
    if not msg:
        return JSONResponse({
            "response": "Kuch to boliye 😊",
            "emotion": "friendly",
            "gesture": "greetingWave",
            "audio_url": None
        })
    
    logger.info(f"User Request: {msg[:50]}... (User: {req.user_name}, Theme Mode: {req.theme_mode}, Live: {req.is_live})")
    try:
        response = brain.process_input(
            msg, 
            theme_mode=req.theme_mode, 
            user_name=req.user_name, 
            user_nickname=req.user_nickname,
            is_live=req.is_live
        )

        logger.info("Sarla responded successfully.")
        emotion, gesture = classify_emotion(response)

        # Generate Sarala Cloned Voice from backend/voice/output (Chatterbox)
        cleaned_speech_text = clean_text_for_synthesis(response)
        audio_url = None
        voice_engine_used = "chatterbox_cloned"

        try:
            synthesis_result = await asyncio.to_thread(
                synthesize_sarala_voice,
                text=cleaned_speech_text,
                language="hi"
            )
            if synthesis_result.get("success") and synthesis_result.get("audio_url"):
                audio_url = synthesis_result.get("audio_url")
                voice_engine_used = "chatterbox_cloned"
        except Exception as voice_err:
            logger.warning(f"Cloned voice synthesis fallback: {voice_err}")
            import urllib.parse
            audio_url = f"/voice/stream?text={urllib.parse.quote(response)}&language=hi"
            voice_engine_used = "streaming_ram_fallback"

        return JSONResponse({
            "response": response,
            "emotion": emotion,
            "gesture": gesture,
            "audio_url": audio_url,
            "voice_engine": voice_engine_used
        })
    except Exception as e:
        logger.error(f"Chat Endpoint Error: {str(e)}")
        return JSONResponse({
            "response": "Maaf kijiye, server busy hai ya kuch technical issue hai. Dobara try karein 😊",
            "emotion": "concerned",
            "gesture": "calmGesture",
            "audio_url": None
        }, status_code=200)


@app.get("/health")
async def health():
    return {"status": "ok", "agent": "Sarla AI"}


# ── In-Memory Streaming Voice Endpoints (Zero Disk Writes) ──────────────────
@app.get("/voice/stream")
async def voice_stream_get(text: str = Query(...), language: str = "hi"):
    """Streams audio chunks in RAM directly to browser without writing any file to disk."""
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
    """Streams audio chunks in RAM directly to browser without writing any file to disk."""
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


# ── Voice Studio & Status Endpoints ─────────────────────────────────────────
class VoiceSynthesizeRequest(BaseModel):
    text: str
    language: str = "hi"
    engine: str = "auto"
    provider: str | None = None

@app.get("/voice/health")
async def voice_health():
    """Health check for Sarala voice system."""
    try:
        status = get_voice_health()
    except Exception as e:
        logger.warning(f"Voice health check error: {e}")
        status = {
            "provider": "streaming_ram",
            "error": str(e),
            "model_loaded": True,
            "device": "in_memory",
        }
    return JSONResponse(status)

@app.post("/voice/synthesize")
async def voice_synthesize(req: VoiceSynthesizeRequest):
    """Synthesize speech using cloned Sarala voice saved to backend/voice/output, with streaming fallback."""
    txt = req.text.strip()
    if not txt:
        return JSONResponse({"success": False, "error": "Text cannot be empty"}, status_code=400)

    # 1. Try Chatterbox voice cloning (saves to backend/voice/output)
    try:
        res = await asyncio.to_thread(
            synthesize_sarala_voice,
            text=txt,
            language=req.language,
            provider=req.provider
        )
        if res.get("success"):
            return JSONResponse(res)
    except Exception as e:
        logger.warning(f"Voice synthesis fallback to natural stream: {e}")

    # 2. Fallback to in-memory streaming
    res = await natural_voice_manager.synthesize_async(txt, language=req.language, engine=req.engine)
    return JSONResponse(res)


@app.get("/voice/audio/{filename}")
async def get_voice_audio(filename: str):
    """Serve reference WAV or existing audio files safely."""
    if not re.match(r"^[a-zA-Z0-9_\-]+\.(wav|mp3)$", filename):
        return JSONResponse({"error": "Invalid filename format"}, status_code=400)
    
    # Check in output or reference dir
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(os.path.dirname(base_dir), "voice", "output", filename)
    if not os.path.exists(file_path):
        ref_path = os.path.join(os.path.dirname(base_dir), "voice", "reference", filename)
        if os.path.exists(ref_path):
            file_path = ref_path
        else:
            return JSONResponse({"error": "Audio file not found"}, status_code=404)
    
    media_type = "audio/mpeg" if filename.endswith(".mp3") else "audio/wav"
    return FileResponse(file_path, media_type=media_type)



# ── Isolated Voice Benchmark Endpoints ──────────────────────────────────────
BENCHMARK_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "voice", "benchmark")

class ApproveEngineRequest(BaseModel):
    engine_key: str
    engine_name: str
    notes: str = ""

@app.get("/api/benchmark/report")
async def get_benchmark_report():
    """Returns the latest isolated voice engine benchmark report."""
    report_file = os.path.join(BENCHMARK_DIR, "voice_benchmark_report.json")
    if not os.path.exists(report_file):
        return JSONResponse({"error": "Benchmark report not generated yet. Run benchmark first."}, status_code=404)
    
    try:
        with open(report_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"error": f"Failed to read report: {str(e)}"}, status_code=500)

@app.get("/api/benchmark/audio/{filename}")
async def get_benchmark_audio(filename: str):
    """Streams isolated voice benchmark WAV files."""
    if not re.match(r"^[a-zA-Z0-9_\-]+\.wav$", filename):
        return JSONResponse({"error": "Invalid filename"}, status_code=400)
    
    file_path = os.path.join(BENCHMARK_DIR, filename)
    if not os.path.exists(file_path):
        # Fallback to voice/samples if reference audio
        sample_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "voice", "samples", filename)
        if os.path.exists(sample_path):
            return FileResponse(sample_path, media_type="audio/wav")
        return JSONResponse({"error": f"Benchmark audio file {filename} not found."}, status_code=404)
    
    return FileResponse(file_path, media_type="audio/wav")

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
            "message": f"Successfully approved {req.engine_name}. Stored in selected_engine.json. LiveAvatar remains isolated until explicitly integrated.",
            "approval": approval_data
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

