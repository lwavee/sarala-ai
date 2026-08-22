"""
Sarala AI - Voice Service
==========================
Clean public interface for voice synthesis. Routes requests to the
active provider (chatterbox_online, neural, or xtts) based on
the SARALA_VOICE_PROVIDER environment variable.

Usage:
    from voice.voice_service import synthesize_sarala_voice

    result = synthesize_sarala_voice("नमस्ते, मैं सरला हूँ।")
    # → {"success": True, "audio_url": "/voice/audio/sarala_hi_xxx.wav", ...}
"""

import os
import re
import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("sarala.voice_service")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [VoiceService] %(message)s",
    )


def _clean_text(text: str) -> str:
    """Strip markdown, emojis, code blocks, and extra whitespace for TTS."""
    if not text:
        return ""
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`[^`]*`", "", text)
    text = re.sub(r"https?://\S+|www\.\S+", "", text)
    text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"[\U00010000-\U0010ffff]", "", text)
    text = re.sub(r"[\u2600-\u27BF]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def synthesize_sarala_voice(
    text: str,
    language: str = "hi",
    engine: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Synthesize Sarala's voice from the given text.

    Args:
        text:     Text to synthesize (will be cleaned of markdown/emojis).
        language: Language code (default "hi" for Hindi).
        engine:   Override active engine ("chatterbox_online" | "neural" | "xtts").
                  If None, uses SARALA_VOICE_PROVIDER env var.

    Returns:
        {
            "success": True/False,
            "audio_url": "/voice/audio/sarala_hi_xxx.wav",
            "filename": "sarala_hi_xxx.wav",
            "provider": "chatterbox_online",
            "language": "hi",
            "latency_sec": 4.2,
            "duration_sec": 3.1,
            "error": None or "error message",
        }
    """
    from voice import config as voice_config  # lazy import avoids circular deps

    # ── Validate text ────────────────────────────────────────────────────────
    cleaned = _clean_text(text)
    if not cleaned:
        cleaned = "जी, मैं आपकी क्या मदद कर सकती हूँ?"

    # ── Determine active provider ────────────────────────────────────────────
    active_engine = (engine or voice_config.VOICE_PROVIDER).lower().strip()
    if not voice_config.VOICE_ENABLED:
        return {
            "success": False,
            "error": "Voice synthesis is disabled (SARALA_VOICE_ENABLED=false).",
            "provider": active_engine,
        }

    # ── Get reference audio path ─────────────────────────────────────────────
    ref_audio = voice_config.get_reference_audio()

    # ── Route to active provider ─────────────────────────────────────────────
    t0 = time.time()

    if active_engine in ("chatterbox_online", "auto"):
        result = _synthesize_chatterbox(cleaned, ref_audio, voice_config)
        if result.get("success"):
            return result
        # auto fallback to neural
        if active_engine == "auto":
            logger.warning(
                f"Chatterbox failed ({result.get('error', 'unknown')}), "
                f"falling back to neural voice."
            )
            return _synthesize_neural(cleaned, language, voice_config)
        return result

    if active_engine == "neural":
        return _synthesize_neural(cleaned, language, voice_config)

    if active_engine == "xtts":
        return _synthesize_xtts(cleaned, language, str(ref_audio), voice_config)

    return {
        "success": False,
        "error": f"Unknown voice provider: '{active_engine}'. "
                 f"Valid options: chatterbox_online, neural, xtts, auto.",
        "provider": active_engine,
    }


# ── Provider implementations ─────────────────────────────────────────────────

def _synthesize_chatterbox(cleaned_text: str, ref_audio, voice_config) -> Dict[str, Any]:
    """Synthesize using online Chatterbox HF Space."""
    try:
        from voice.chatterbox_online import chatterbox_voice

        result = chatterbox_voice.synthesize(
            text=cleaned_text,
            reference_audio=str(ref_audio),
            exaggeration=voice_config.CHATTERBOX_EXAGGERATION,
            temperature=voice_config.CHATTERBOX_TEMPERATURE,
            cfg_weight=voice_config.CHATTERBOX_CFG_WEIGHT,
            seed=voice_config.CHATTERBOX_SEED,
            output_dir=str(voice_config.OUTPUT_DIR),
        )
        if result.get("success"):
            result["language"] = voice_config.VOICE_LANGUAGE
        return result

    except Exception as e:
        logger.error(f"Chatterbox synthesis error: {e}")
        return {
            "success": False,
            "error": f"Chatterbox synthesis failed: {e}",
            "provider": "chatterbox_online",
        }


def _synthesize_neural(cleaned_text: str, language: str, voice_config) -> Dict[str, Any]:
    """Synthesize using Edge-TTS neural voice (fast, online, no cloning)."""
    try:
        import asyncio
        import hashlib
        from pathlib import Path

        NEURAL_VOICES = {
            "hi": "hi-IN-SwaraNeural",
            "en": "en-IN-NeerjaNeural",
        }
        voice_name = NEURAL_VOICES.get(language, NEURAL_VOICES["hi"])
        text_hash = hashlib.md5(
            f"{cleaned_text}_{language}_neural".encode("utf-8")
        ).hexdigest()[:12]
        filename = f"sarala_{language}_{text_hash}.mp3"
        out_path = voice_config.OUTPUT_DIR / filename

        if out_path.exists() and out_path.stat().st_size > 100:
            return {
                "success": True,
                "filename": filename,
                "file_path": str(out_path),
                "audio_url": f"/voice/audio/{filename}",
                "provider": "neural",
                "language": language,
                "latency_sec": 0.01,
                "duration_sec": 0.0,
                "cached": True,
                "error": None,
            }

        import edge_tts
        import time

        t0 = time.time()
        communicate = edge_tts.Communicate(cleaned_text, voice_name, rate="+2%", pitch="+2Hz")
        asyncio.run(communicate.save(str(out_path)))

        if not out_path.exists():
            return {"success": False, "error": "Edge-TTS failed to produce output.", "provider": "neural"}

        return {
            "success": True,
            "filename": filename,
            "file_path": str(out_path),
            "audio_url": f"/voice/audio/{filename}",
            "provider": "neural",
            "language": language,
            "latency_sec": round(time.time() - t0, 2),
            "duration_sec": 0.0,
            "cached": False,
            "error": None,
        }
    except Exception as e:
        logger.error(f"Neural synthesis error: {e}")
        return {"success": False, "error": f"Neural TTS failed: {e}", "provider": "neural"}


def _synthesize_xtts(
    cleaned_text: str, language: str, ref_audio: str, voice_config
) -> Dict[str, Any]:
    """Synthesize using local XTTS-v2 (kept available for SARALA_VOICE_PROVIDER=xtts)."""
    try:
        from voice.xtts_engine import voice_engine

        result = voice_engine.synthesize(
            text=cleaned_text,
            language=language,
            reference_wav=ref_audio,
        )
        if result.get("success"):
            result["provider"] = "xtts"
        return result
    except Exception as e:
        logger.error(f"XTTS synthesis error: {e}")
        return {"success": False, "error": f"XTTS synthesis failed: {e}", "provider": "xtts"}


def get_voice_health() -> Dict[str, Any]:
    """
    Returns comprehensive voice system health status.
    Called by the /voice/health backend endpoint.
    """
    from voice import config as voice_config

    health: Dict[str, Any] = {
        "active_provider": voice_config.VOICE_PROVIDER,
        "voice_enabled": voice_config.VOICE_ENABLED,
        "language": voice_config.VOICE_LANGUAGE,
        "reference_audio": str(voice_config.VOICE_REFERENCE_PATH),
        "reference_exists": voice_config.VOICE_REFERENCE_PATH.exists(),
        "reference_size_bytes": (
            voice_config.VOICE_REFERENCE_PATH.stat().st_size
            if voice_config.VOICE_REFERENCE_PATH.exists()
            else 0
        ),
        "chatterbox_space": voice_config.CHATTERBOX_SPACE,
    }

    # Check Chatterbox reachability
    try:
        from voice.chatterbox_online import chatterbox_voice
        cb_health = chatterbox_voice.health_check()
        health["chatterbox_online"] = cb_health.get("chatterbox_online", False)
        health["chatterbox_status"] = cb_health.get("status", cb_health.get("error", "unknown"))
    except Exception as e:
        health["chatterbox_online"] = False
        health["chatterbox_status"] = str(e)

    return health
