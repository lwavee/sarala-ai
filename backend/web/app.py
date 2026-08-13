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

frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
allowed_origins = [origin.strip() for origin in frontend_url.split(",") if origin.strip()]
if "http://localhost:3000" not in allowed_origins:
    allowed_origins.append("http://localhost:3000")
if "http://127.0.0.1:3000" not in allowed_origins:
    allowed_origins.append("http://127.0.0.1:3000")

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

@app.post("/chat")
async def chat(req: ChatRequest):
    """Process a user message and return Sarla's response."""
    msg = req.message.strip()
    if not msg:
        return JSONResponse({"response": "Kuch to boliye 😊"})
    
    logger.info(f"User Request: {msg[:50]}... (User: {req.user_name}, Theme Mode: {req.theme_mode})")
    try:
        response = brain.process_input(
            msg, 
            theme_mode=req.theme_mode, 
            user_name=req.user_name, 
            user_nickname=req.user_nickname
        )
        logger.info("Sarla responded successfully.")
        return JSONResponse({"response": response})
    except Exception as e:
        logger.error(f"Chat Endpoint Error: {str(e)}")
        return JSONResponse({
            "response": "Maaf kijiye, server busy hai ya kuch technical issue hai. Dobara try karein 😊"
        }, status_code=200)


@app.get("/health")
async def health():
    return {"status": "ok", "agent": "Sarla AI"}
