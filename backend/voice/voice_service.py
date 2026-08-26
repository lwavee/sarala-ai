"""
Sarala AI — Voice Service
==========================
High-level facade for synthesizing Sarala's voice using Chatterbox Multilingual.

Features:
- Exposes generate_sarala_voice(text, language="hi").
- Conditioned on backend/voice/reference/sarala_reference.wav or backend/voice/output.
- 100% Free Open-Source voice cloning with remote GPU inference.
"""

import os
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from voice.config import voice_config
from voice.providers.chatterbox_provider import (
    ChatterboxProvider,
    VoiceSynthesisError,
    get_chatterbox_provider,
)

logger = logging.getLogger("sarala.voice_service")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [VoiceService] %(message)s"
    )


def generate_sarala_voice(
    text: str,
    language: str = "hi",
) -> Dict[str, Any]:
    """
    Approved standard voice generation function for Sarala AI.
    
    Uses Chatterbox Multilingual conditioned on Sarala reference audio.
    
    Args:
        text: Arbitrary Hindi text (or Hinglish/English) to speak.
        language: Language code, default "hi".
        
    Returns:
        Dict with audio_path, audio_url, filename, duration_sec, latency_sec, provider, success.
    """
    return synthesize_sarala_voice(text=text, language=language)


def synthesize_sarala_voice(
    text: str,
    language: str = "hi",
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Primary voice synthesis interface for Sarala AI.

    Args:
        text: Text to synthesize. May contain Hindi/Hinglish/English.
        language: Language code, default "hi" for Hindi.
        provider: Optional provider override ("chatterbox").

    Returns:
        Dict with audio_url, filename, audio_path, duration_sec, latency_sec, etc.
    """
    text = (text or "").strip()
    if not text:
        raise VoiceSynthesisError("Text cannot be empty.")

    active_provider = (provider or voice_config.provider).lower().strip()
    logger.info(f"Voice synthesis requested [{active_provider}]: '{text[:60]}...'")

    chatterbox = get_chatterbox_provider()
    result = chatterbox.synthesize(
        text=text,
        language=language,
        reference_audio=str(voice_config.reference_audio_path),
        exaggeration=voice_config.exaggeration,
        temperature=voice_config.temperature,
        seed=voice_config.seed,
        cfg_weight=voice_config.cfg_weight,
    )
    return result


def get_voice_health() -> Dict[str, Any]:
    """
    Returns comprehensive health status for the active voice provider.
    Used by GET /voice/health endpoint.
    """
    provider = voice_config.provider
    ref_path = voice_config.reference_audio_path
    ref_exists = ref_path.exists() and ref_path.stat().st_size > 0

    return {
        "enabled": voice_config.enabled,
        "provider": "chatterbox",
        "language": voice_config.language,
        "reference_audio": str(ref_path),
        "reference_audio_exists": ref_exists,
        "inference_mode": voice_config.inference_mode,
        "status": "ready" if ref_exists else "missing_reference",
        "output_dir": str(voice_config.output_dir),
        "model_loaded": True,
        "device": f"online ({voice_config.inference_mode})",
    }
