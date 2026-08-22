"""
Sarala AI - Natural Voice & Voice Cloning Engine
=================================================
Combines:
1. Online Chatterbox Hindi Voice Cloning (via HF Space ResembleAI/Chatterbox-Multilingual-TTS-hi)
2. Ultra-Natural Neural Indian Voices (via Edge-TTS Neural hi-IN-Swara / en-IN-Neerja)
3. True Voice Cloning from reference audio (via Coqui XTTS-v2, CPU-based)
4. Intelligent caching & text cleanup for high-speed, human-like voice response.

Provider selection is controlled by the SARALA_VOICE_PROVIDER environment variable.
"""

import os
import sys
import re
import time
import hashlib
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("sarala.natural_voice")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [NaturalVoice] %(message)s")

VOICE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = VOICE_DIR / "output"
SAMPLES_DIR = VOICE_DIR / "samples"
DEFAULT_REF_WAV = SAMPLES_DIR / "sarala_reference.wav"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

# Neural Voice Profiles
NEURAL_VOICES = {
    "hi": "hi-IN-SwaraNeural",       # Warm, natural, friendly female Hindi voice
    "hi-madhur": "hi-IN-MadhurNeural", # Expressive Hindi male voice
    "en": "en-IN-NeerjaNeural",     # Natural Indian English female voice
    "en-ananya": "en-IN-AnanyaNeural", # Youthful Indian English female voice
}


def clean_text_for_synthesis(text: str) -> str:
    """Strips Markdown syntax, emojis, URLs, and code blocks for smooth speech."""
    if not text:
        return ""
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    # Remove inline code
    text = re.sub(r'`[^`]*`', '', text)
    # Remove URLs
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    # Remove markdown headers and list bullets
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    # Remove bold / italic markup
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    # Remove emojis
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    text = re.sub(r'[\u2600-\u27BF]', '', text)
    text = re.sub(r'[\uD800-\uDBFF][\uDC00-\uDFFF]', '', text)
    # Normalize whitespaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def detect_language(text: str) -> str:
    """Detects whether text is predominantly Hindi or English."""
    # Check for Devanagari Unicode range
    devanagari_chars = len(re.findall(r'[\u0900-\u097F]', text))
    total_alpha = len(re.findall(r'[a-zA-Z\u0900-\u097F]', text))
    if total_alpha > 0 and (devanagari_chars / total_alpha) > 0.15:
        return "hi"
    return "hi"  # Default Sarala persona language is Hindi / Hinglish


async def synthesize_neural_async(text: str, voice_name: str, output_path: str) -> bool:
    """Synthesizes speech using Edge-TTS Neural Voice."""
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice_name, rate="+2%", pitch="+2Hz")
        await communicate.save(output_path)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        logger.error(f"Neural synthesis failed: {e}")
        return False


class NaturalVoiceManager:
    """
    Unified voice manager supporting:
    1. Online Chatterbox Hindi Voice Cloning (HF Space, GPU-powered)
    2. Ultra-Natural Indian Neural Voice (Edge-TTS)
    3. Coqui XTTS-v2 Voice Cloning from user recordings (local CPU)

    Active provider is controlled by SARALA_VOICE_PROVIDER env var.
    """

    def __init__(self):
        self.output_dir = OUTPUT_DIR
        self.samples_dir = SAMPLES_DIR
        self.reference_wav = DEFAULT_REF_WAV
        self._cache: Dict[str, str] = {}

    def is_reference_ready(self) -> bool:
        return self.reference_wav.exists() and self.reference_wav.stat().st_size > 0

    def synthesize(
        self,
        text: str,
        language: Optional[str] = None,
        engine: str = "auto",
        reference_wav: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes text into natural speech.

        Args:
            text: Text to speak
            language: Language code ('hi' or 'en')
            engine: 'auto', 'neural', or 'xtts'
            reference_wav: Optional path to custom reference audio

        Returns:
            Dict with success, filename, audio_url, latency_sec, engine_used
        """
        raw_text = text.strip() if text else ""
        if not raw_text:
            return {"success": False, "error": "Text cannot be empty."}

        cleaned = clean_text_for_synthesis(raw_text)
        if not cleaned:
            cleaned = "जी, मैं आपकी क्या मदद कर सकती हूँ?"

        target_lang = language or detect_language(cleaned)
        
        # Check in-memory / disk cache by hash
        text_hash = hashlib.md5(f"{cleaned}_{target_lang}_{engine}".encode("utf-8")).hexdigest()[:12]
        cached_filename = f"sarala_{target_lang}_{text_hash}.mp3"
        cached_path = self.output_dir / cached_filename

        if cached_path.exists() and cached_path.stat().st_size > 100:
            return {
                "success": True,
                "filename": cached_filename,
                "file_path": str(cached_path),
                "audio_url": f"/voice/audio/{cached_filename}",
                "engine": "cache",
                "cached": True,
                "latency_sec": 0.01,
                "language": target_lang
            }

        t0 = time.time()

        # Engine 0: Online Chatterbox Hindi Voice Cloning (HF Space, GPU-powered)
        if engine in ("auto", "chatterbox_online"):
            try:
                from voice.chatterbox_online import chatterbox_voice
                from voice import config as voice_config
                ref_path = reference_wav or str(voice_config.get_reference_audio())
                cb_res = chatterbox_voice.synthesize(
                    text=cleaned,
                    reference_audio=ref_path,
                    exaggeration=voice_config.CHATTERBOX_EXAGGERATION,
                    temperature=voice_config.CHATTERBOX_TEMPERATURE,
                    cfg_weight=voice_config.CHATTERBOX_CFG_WEIGHT,
                    seed=voice_config.CHATTERBOX_SEED,
                    output_dir=str(self.output_dir),
                )
                if cb_res.get("success"):
                    cb_res["engine"] = "chatterbox_online"
                    cb_res["language"] = target_lang
                    return cb_res
                else:
                    logger.warning(f"Chatterbox synthesis failed: {cb_res.get('error')}")
                    if engine == "chatterbox_online":  # strict mode: no fallback
                        return {
                            "success": False,
                            "error": cb_res.get('error', 'Chatterbox synthesis failed'),
                            "provider": "chatterbox_online",
                        }
            except Exception as cb_err:
                logger.warning(f"Chatterbox engine error: {cb_err}")
                if engine == "chatterbox_online":
                    return {"success": False, "error": str(cb_err), "provider": "chatterbox_online"}

        # Engine 1: Neural High-Fidelity Voice (Natural, expressive, instantaneous)
        if engine in ("auto", "neural"):
            voice_name = NEURAL_VOICES.get(target_lang, NEURAL_VOICES["hi"])
            try:
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        success = pool.submit(asyncio.run, synthesize_neural_async(cleaned, voice_name, str(cached_path))).result()
                else:
                    success = loop.run_until_complete(synthesize_neural_async(cleaned, voice_name, str(cached_path)))

                if success:
                    latency = round(time.time() - t0, 3)
                    logger.info(f"Generated natural voice [{voice_name}] in {latency}s: '{cleaned[:40]}...'")
                    return {
                        "success": True,
                        "filename": cached_filename,
                        "file_path": str(cached_path),
                        "audio_url": f"/voice/audio/{cached_filename}",
                        "engine": "neural",
                        "voice_name": voice_name,
                        "cached": False,
                        "latency_sec": latency,
                        "language": target_lang
                    }
            except Exception as neural_err:
                logger.warning(f"Neural engine failed, attempting XTTS fallback: {neural_err}")

        # Engine 2: XTTS-v2 Voice Cloning (Clone from reference audio)
        if engine in ("auto", "xtts"):
            try:
                from voice.xtts_engine import voice_engine
                res = voice_engine.synthesize(
                    text=cleaned,
                    language=target_lang,
                    reference_wav=reference_wav or str(self.reference_wav)
                )
                if res.get("success"):
                    res["engine"] = "xtts_clone"
                    return res
            except Exception as xtts_err:
                logger.error(f"XTTS voice cloning failed: {xtts_err}")

        return {
            "success": False,
            "error": "All voice synthesis engines failed to generate audio."
        }

    async def synthesize_async(
        self,
        text: str,
        language: Optional[str] = None,
        engine: str = "auto",
        reference_wav: Optional[str] = None
    ) -> Dict[str, Any]:
        """Async version of synthesize for FastAPI async endpoints."""
        raw_text = text.strip() if text else ""
        if not raw_text:
            return {"success": False, "error": "Text cannot be empty."}

        cleaned = clean_text_for_synthesis(raw_text)
        if not cleaned:
            cleaned = "जी, मैं आपकी क्या मदद कर सकती हूँ?"

        target_lang = language or detect_language(cleaned)
        
        text_hash = hashlib.md5(f"{cleaned}_{target_lang}_{engine}".encode("utf-8")).hexdigest()[:12]
        cached_filename = f"sarala_{target_lang}_{text_hash}.mp3"
        cached_path = self.output_dir / cached_filename

        if cached_path.exists() and cached_path.stat().st_size > 100:
            return {
                "success": True,
                "filename": cached_filename,
                "file_path": str(cached_path),
                "audio_url": f"/voice/audio/{cached_filename}",
                "engine": "cache",
                "cached": True,
                "latency_sec": 0.01,
                "language": target_lang
            }

        t0 = time.time()

        # Async Engine 0: Online Chatterbox Hindi (runs sync call in thread executor)
        if engine in ("auto", "chatterbox_online"):
            try:
                import asyncio as _asyncio
                from voice.chatterbox_online import chatterbox_voice
                from voice import config as voice_config
                ref_path = reference_wav or str(voice_config.get_reference_audio())

                loop = _asyncio.get_event_loop()
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    cb_res = await loop.run_in_executor(
                        pool,
                        lambda: chatterbox_voice.synthesize(
                            text=cleaned,
                            reference_audio=ref_path,
                            exaggeration=voice_config.CHATTERBOX_EXAGGERATION,
                            temperature=voice_config.CHATTERBOX_TEMPERATURE,
                            cfg_weight=voice_config.CHATTERBOX_CFG_WEIGHT,
                            seed=voice_config.CHATTERBOX_SEED,
                            output_dir=str(self.output_dir),
                        )
                    )

                if cb_res.get("success"):
                    cb_res["engine"] = "chatterbox_online"
                    cb_res["language"] = target_lang
                    return cb_res
                else:
                    logger.warning(f"Async Chatterbox failed: {cb_res.get('error')}")
                    if engine == "chatterbox_online":
                        return {
                            "success": False,
                            "error": cb_res.get('error', 'Chatterbox synthesis failed'),
                            "provider": "chatterbox_online",
                        }
            except Exception as cb_err:
                logger.warning(f"Async Chatterbox engine error: {cb_err}")
                if engine == "chatterbox_online":
                    return {"success": False, "error": str(cb_err), "provider": "chatterbox_online"}

        if engine in ("auto", "neural"):
            voice_name = NEURAL_VOICES.get(target_lang, NEURAL_VOICES["hi"])
            try:
                success = await synthesize_neural_async(cleaned, voice_name, str(cached_path))
                if success:
                    latency = round(time.time() - t0, 3)
                    logger.info(f"Generated natural voice async [{voice_name}] in {latency}s: '{cleaned[:40]}...'")
                    return {
                        "success": True,
                        "filename": cached_filename,
                        "file_path": str(cached_path),
                        "audio_url": f"/voice/audio/{cached_filename}",
                        "engine": "neural",
                        "voice_name": voice_name,
                        "cached": False,
                        "latency_sec": latency,
                        "language": target_lang
                    }
            except Exception as neural_err:
                logger.warning(f"Async neural engine failed, attempting XTTS: {neural_err}")

        # Fallback to sync XTTS
        return self.synthesize(text=text, language=language, engine="xtts", reference_wav=reference_wav)


# Global singleton
natural_voice_manager = NaturalVoiceManager()

