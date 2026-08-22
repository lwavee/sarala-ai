"""
Sarala AI - Voice Configuration
================================
Centralised voice settings loaded from environment variables.
All voice providers (chatterbox_online, neural, xtts) use this config.
"""

import os
from pathlib import Path

# Load .env from backend directory (same pattern as core/llm.py)
try:
    from dotenv import load_dotenv as _load_dotenv
    _this_dir = Path(__file__).resolve().parent
    _load_dotenv(_this_dir.parent / ".env")  # backend/.env
    _load_dotenv()  # fallback: CWD .env
except ImportError:
    pass  # python-dotenv not available; rely on OS env vars

# ── Base Paths ──────────────────────────────────────────────────────────────
VOICE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = VOICE_DIR.parent

# ── Provider Selection ───────────────────────────────────────────────────────
# Options: "chatterbox_online" | "neural" | "xtts" | "auto"
# "auto" = tries chatterbox_online first, falls back to neural
VOICE_PROVIDER = os.getenv("SARALA_VOICE_PROVIDER", "auto").lower().strip()

VOICE_ENABLED = os.getenv("SARALA_VOICE_ENABLED", "true").lower() == "true"

VOICE_LANGUAGE = os.getenv("SARALA_VOICE_LANGUAGE", "hi").lower().strip()

# ── Reference Audio ──────────────────────────────────────────────────────────
# Default: backend/voice/samples/sarala_reference.wav
_ref_env = os.getenv("SARALA_VOICE_REFERENCE", "")
if _ref_env:
    _ref_p = Path(_ref_env)
    if _ref_p.is_absolute():
        VOICE_REFERENCE_PATH = _ref_p
    else:
        # Resolve relative to project root (parent of backend/)
        PROJECT_ROOT = BACKEND_DIR.parent
        VOICE_REFERENCE_PATH = PROJECT_ROOT / _ref_env
        # If that doesn't exist, try relative to backend dir
        if not VOICE_REFERENCE_PATH.exists():
            VOICE_REFERENCE_PATH = BACKEND_DIR / _ref_env
else:
    VOICE_REFERENCE_PATH = VOICE_DIR / "samples" / "sarala_reference.wav"

# ── Chatterbox Online Settings ───────────────────────────────────────────────
CHATTERBOX_SPACE = os.getenv(
    "CHATTERBOX_SPACE", "ResembleAI/Chatterbox-Multilingual-TTS-hi"
)

# Chatterbox synthesis parameters (neutral, natural quality settings)
CHATTERBOX_EXAGGERATION = float(os.getenv("CHATTERBOX_EXAGGERATION", "0.5"))
CHATTERBOX_TEMPERATURE  = float(os.getenv("CHATTERBOX_TEMPERATURE", "0.8"))
CHATTERBOX_CFG_WEIGHT   = float(os.getenv("CHATTERBOX_CFG_WEIGHT", "0.5"))
CHATTERBOX_SEED         = int(os.getenv("CHATTERBOX_SEED", "0"))

# Chatterbox hard text limit (enforced by the HF Space)
CHATTERBOX_MAX_CHARS = 300

# ── Output Directory ─────────────────────────────────────────────────────────
OUTPUT_DIR = VOICE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_reference_audio() -> Path:
    """Return the active Sarala reference audio path, with validation."""
    if VOICE_REFERENCE_PATH.exists() and VOICE_REFERENCE_PATH.stat().st_size > 0:
        return VOICE_REFERENCE_PATH
    # Fallback: search samples directory for any usable WAV
    samples_dir = VOICE_DIR / "samples"
    for wav in sorted(samples_dir.glob("*.wav"), key=lambda p: p.stat().st_size, reverse=True):
        if wav.stat().st_size > 50_000:
            return wav
    return VOICE_REFERENCE_PATH  # Return even if missing; caller will handle error


def describe() -> dict:
    """Returns a diagnostic snapshot of the current voice configuration."""
    ref = VOICE_REFERENCE_PATH
    return {
        "provider": VOICE_PROVIDER,
        "enabled": VOICE_ENABLED,
        "language": VOICE_LANGUAGE,
        "reference_audio": str(ref),
        "reference_exists": ref.exists(),
        "reference_size_bytes": ref.stat().st_size if ref.exists() else 0,
        "chatterbox_space": CHATTERBOX_SPACE,
        "output_dir": str(OUTPUT_DIR),
    }
