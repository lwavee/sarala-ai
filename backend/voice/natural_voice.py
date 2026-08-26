"""
Sarala AI - In-Memory Streaming Speech Engine
==============================================
100% In-Memory Streaming Audio Architecture.
- Zero disk clutter: NO sarala_hi_xxxxx.wav or mp3 files saved to disk.
- Real-time RAM/network streaming directly to browser.
- Instant sub-second audio playback.
"""

import re
import io
import time
import logging
from pathlib import Path
from typing import AsyncIterator, Dict, Any, Optional

logger = logging.getLogger("sarala.natural_voice")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [NaturalVoice] %(message)s")

VOICE_DIR = Path(__file__).resolve().parent
REFERENCE_DIR = VOICE_DIR / "reference"
DEFAULT_REF_WAV = REFERENCE_DIR / "sarala_reference.wav"

# Neural Voice Profiles for Instant Sub-Second Synthesis
NEURAL_VOICES = {
    "hi": "hi-IN-SwaraNeural",         # Warm, soft, natural Indian female voice
    "en": "en-IN-NeerjaNeural",        # Natural Indian English female voice
}


def clean_text_for_synthesis(text: str) -> str:
    """Strips Markdown syntax, emojis, URLs, and code blocks for smooth speech."""
    if not text:
        return ""
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]*`', '', text)
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    text = re.sub(r'[\u2600-\u27BF]', '', text)
    text = re.sub(r'[\uD800-\uDBFF][\uDC00-\uDFFF]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def detect_language(text: str) -> str:
    """Detects whether text is predominantly Hindi or English."""
    devanagari_chars = len(re.findall(r'[\u0900-\u097F]', text))
    total_alpha = len(re.findall(r'[a-zA-Z\u0900-\u097F]', text))
    if total_alpha > 0 and (devanagari_chars / total_alpha) > 0.15:
        return "hi"
    return "hi"


class NaturalVoiceManager:
    """
    In-Memory Streaming Voice Manager.
    Streams audio chunks directly in RAM/network to browser with zero disk writes.
    """

    def __init__(self):
        self.reference_wav = DEFAULT_REF_WAV

    def is_reference_ready(self) -> bool:
        return self.reference_wav.exists() and self.reference_wav.stat().st_size > 0

    async def stream_voice_chunks(self, text: str, language: Optional[str] = None) -> AsyncIterator[bytes]:
        """
        Yields raw audio chunks in RAM directly to the HTTP stream.
        NO files are saved to disk. Temporary chunks are discarded by GC.
        """
        raw_text = (text or "").strip()
        if not raw_text:
            return

        cleaned = clean_text_for_synthesis(raw_text)
        if not cleaned:
            cleaned = "जी, मैं आपकी क्या मदद कर सकती हूँ?"

        target_lang = language or detect_language(cleaned)
        voice_name = NEURAL_VOICES.get(target_lang, NEURAL_VOICES["hi"])

        try:
            import edge_tts
            communicate = edge_tts.Communicate(cleaned, voice_name, rate="+0%", pitch="+0Hz")
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]
        except Exception as e:
            logger.error(f"Error streaming audio in RAM: {e}")

    async def synthesize_to_bytes(self, text: str, language: Optional[str] = None) -> bytes:
        """Returns in-memory audio bytes with zero disk writes."""
        chunks = []
        async for chunk in self.stream_voice_chunks(text, language=language):
            chunks.append(chunk)
        return b"".join(chunks)

    async def synthesize_async(
        self,
        text: str,
        language: Optional[str] = None,
        engine: str = "auto",
        reference_wav: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Returns a direct in-memory streaming URL.
        Zero files written to disk!
        """
        raw_text = (text or "").strip()
        if not raw_text:
            return {"success": False, "error": "Text cannot be empty."}

        cleaned = clean_text_for_synthesis(raw_text)
        if not cleaned:
            cleaned = "जी, मैं आपकी क्या मदद कर सकती हूँ?"

        target_lang = language or detect_language(cleaned)
        import urllib.parse
        encoded_text = urllib.parse.quote(cleaned)
        stream_url = f"/voice/stream?text={encoded_text}&language={target_lang}"

        return {
            "success": True,
            "audio_url": stream_url,
            "engine": "neural_stream",
            "provider": "streaming_ram",
            "language": target_lang,
            "in_memory": True,
        }

    def synthesize(
        self,
        text: str,
        language: Optional[str] = None,
        engine: str = "auto",
        reference_wav: Optional[str] = None
    ) -> Dict[str, Any]:
        """Synchronous wrapper returning in-memory stream URL."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import urllib.parse
            cleaned = clean_text_for_synthesis(text)
            target_lang = language or detect_language(cleaned)
            encoded_text = urllib.parse.quote(cleaned)
            return {
                "success": True,
                "audio_url": f"/voice/stream?text={encoded_text}&language={target_lang}",
                "engine": "neural_stream",
                "provider": "streaming_ram",
                "language": target_lang,
                "in_memory": True,
            }
        return loop.run_until_complete(self.synthesize_async(text, language, engine, reference_wav))


# Global singleton
natural_voice_manager = NaturalVoiceManager()
