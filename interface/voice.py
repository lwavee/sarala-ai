import asyncio
import tempfile
import os
import re
import threading

# Edge TTS (Microsoft Neural voices — free, high quality)
try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

# Pygame for audio playback
try:
    import pygame
    HAS_PYGAME = True
except ImportError:
    HAS_PYGAME = False

# SpeechRecognition for mic input (STT)
try:
    import speech_recognition as sr
    HAS_STT = True
except ImportError:
    HAS_STT = False

from core.logger import logger

# Best Indian female neural voice from Microsoft Edge TTS
VOICE = "en-IN-NeerjaNeural"

def _clean_text(text: str) -> str:
    """Remove emojis and markdown before sending to TTS."""
    emoji_pattern = re.compile(
        "[\U00010000-\U0010ffff"
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F9FF"
        "\u2600-\u26FF\u2700-\u27BF]+",
        flags=re.UNICODE
    )
    text = emoji_pattern.sub("", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    return text.strip()

async def _async_speak(text: str) -> bool:
    """Generate and play speech. Returns True if successful."""
    cleaned = _clean_text(text)
    if not cleaned: return False

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        tmp_path = f.name

    try:
        communicate = edge_tts.Communicate(text=cleaned, voice=VOICE, rate="-5%")
        await communicate.save(tmp_path)

        if HAS_PYGAME and os.path.exists(tmp_path):
            try:
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                pygame.mixer.music.load(tmp_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    pygame.time.wait(50)
                pygame.mixer.music.unload()
                return True
            except Exception as e:
                logger.warning(f"Audio playback failed: {e}")
                return False
    finally:
        try: os.unlink(tmp_path)
        except: pass
    return False

class VoiceSystem:
    """Realistic Neural TTS and Google STT system."""
    def __init__(self):
        self.recognizer = sr.Recognizer() if HAS_STT else None
        if not HAS_EDGE_TTS: logger.warning("edge-tts missing.")
        if not HAS_PYGAME: logger.warning("pygame missing.")

    def speak(self, text: str):
        """Speak text (non-blocking wrapper)."""
        if not HAS_EDGE_TTS or not HAS_PYGAME:
            logger.info(f"Sarla (Text Only): {text}")
            return

        logger.info(f"Sarla: {text}")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            success = loop.run_until_complete(_async_speak(text))
            loop.close()
            if not success: logger.warning("TTS failed.")
        except Exception as e:
            logger.error(f"TTS Error: {e}")

    def listen(self) -> str:
        """Listen from mic and return text."""
        if not HAS_STT or not self.recognizer:
            logger.warning("STT unavailable.")
            return ""

        try:
            mic = sr.Microphone()
            with mic as source:
                logger.info("Listening...")
                self.recognizer.adjust_for_ambient_noise(source, duration=0.8)
                audio = self.recognizer.listen(source, timeout=7, phrase_time_limit=10)
                text = self.recognizer.recognize_google(audio, language="hi-IN")
                logger.info(f"You (voice): {text}")
                return text
        except Exception as e:
            logger.debug(f"STT Error: {e}")
            return ""
