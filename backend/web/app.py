import sys
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from core.brain import Brain
from core.logger import logger

# ── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(title="Sarla AI API", version="1.0.0")

@app.on_event("startup")
async def startup_event():
    logger.info("Sarla Web Server is starting up...")

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

@app.post("/chat")
async def chat(req: ChatRequest):
    """Process a user message and return Sarla's response with animation metadata."""
    msg = req.message.strip()
    if not msg:
        return JSONResponse({
            "response": "Kuch to boliye 😊",
            "emotion": "friendly",
            "gesture": "greetingWave"
        })
    
    logger.info(f"User Request: {msg[:50]}... (User: {req.user_name}, Theme Mode: {req.theme_mode})")
    try:
        response = brain.process_input(
            msg, 
            theme_mode=req.theme_mode, 
            user_name=req.user_name, 
            user_nickname=req.user_nickname
        )
        logger.info("Sarla responded successfully.")
        emotion, gesture = classify_emotion(response)
        return JSONResponse({
            "response": response,
            "emotion": emotion,
            "gesture": gesture
        })
    except Exception as e:
        logger.error(f"Chat Endpoint Error: {str(e)}")
        return JSONResponse({
            "response": "Maaf kijiye, server busy hai ya kuch technical issue hai. Dobara try karein 😊",
            "emotion": "concerned",
            "gesture": "calmGesture"
        }, status_code=200)


@app.get("/health")
async def health():
    return {"status": "ok", "agent": "Sarla AI"}
