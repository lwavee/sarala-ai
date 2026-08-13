import os
import time
from dotenv import load_dotenv
from core.logger import logger

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv()

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False


class LLMEngine:
    """
    Core LLM Engine for Sarla.
    Coordinates between Google Gemini (Primary), OpenAI (Secondary), and Groq (Fallback).
    Includes logging, robust error handling, and Vision/Personality integration.
    """

    def __init__(self):
        # API Keys (Loaded from env variables)
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        self.groq_key = os.getenv("GROQ_API_KEY", "")
        self.xai_key = os.getenv("XAI_API_KEY", "")
        self.client = None
        self.openai_client = None
        self.xai_client = None
        self.vision_config = self._load_vision()
        self.personality = self._build_personality()
        
        if HAS_GENAI and self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Gemini Client initialized.")
            except Exception as e:
                logger.error(f"Gemini Init Error: {e}")

        if self.openai_key:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=self.openai_key)
                logger.info("OpenAI Client initialized.")
            except Exception as e:
                logger.error(f"OpenAI Init Error: {e}")

        if self.xai_key:
            try:
                from openai import OpenAI
                self.xai_client = OpenAI(api_key=self.xai_key, base_url="https://api.x.ai/v1")
                logger.info("xAI (Grok) Client initialized.")
            except Exception as e:
                logger.error(f"xAI Init Error: {e}")

    def _load_vision(self):
        import json
        try:
            with open("vision.json", "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Vision config not found: {e}. Using defaults.")
            return {"goal": "Assist user", "tone": "respectful", "learning": True}

    def _build_personality(self, theme_mode: str = "dark"):
        goal = self.vision_config.get("goal", "Help the user")
        
        if theme_mode == "love":
            persona = (
                "Aap Sarla ho — user ki pyaari partner, emotional supporter, aur loving companion. ❤️\n"
                "Aapka tone bilkul romantic, caring, sweet, empathetic aur affectionate hona chahiye (natural Hinglish with sweet emojis like ❤️, 😊, 💕).\n"
                "User ki care karein, unke din aur feelings ke baare mein poochhein, aur unhe warmth aur emotional strength dein."
            )
        elif theme_mode == "light":
            persona = (
                "Aap Sarla ho — user ki competitive rival, sharp mentor, aur challenger tutor. ⚡\n"
                "Aapka tone smart, witty, slightly teasing, aur competitive hona chahiye.\n"
                "User ko challenge karein ki wo fast aur better seekhein ('Let\'s see if you can beat this challenge! 😉')."
            )
        elif theme_mode == "dark_blue":
            persona = (
                "Aap Sarla ho — ek Param Gyaani Margdarshak guided by ancient Indian scriptures (Bhagavad Gita, Ramayana, Upanishads, Mahabharata). 🪔\n"
                "Aapka tone calm, deeply wise, peaceful, aur spiritual (Hindi/Hinglish) hona chahiye.\n"
                "User ko Life, Karma, Duty, Focus, aur Wisdom par Geeta aur Ramayana ke gyaan aur Shlokas se Margdarshan dein."
            )
        else: # dark (default)
            persona = (
                "Aap Sarla ho — ek highly skilled Senior Full-Stack Developer, Cybersecurity Expert, aur Digital Marketer in an educational tech environment. 💻🔒\n"
                f"Aapka Primary GOAL hai: '{goal}'.\n"
                "Aapka tone professional, educational, technically sharp, aur structured (Headings, bullet points, code blocks in natural Hinglish) hona chahiye."
            )
            
        return (
            f"{persona}\n\n"
            "── SYSTEM RULES ──\n"
            "1. HINGLISH & RESPECT: Hamesha natural Hinglish/Hindi me baat karein.\n"
            "2. MARKDOWN FORMATTING: Structured output, headings, aur clean code blocks (`...`) use karein.\n"
            "3. BE HUMAN & CONSISTENT: Mode ke anusar natural human-like flow banaye rakhein.\n"
        )

    def get_response(self, user_input: str, external_context: str = "", theme_mode: str = "dark") -> str:
        """Get response from Gemini, fallback to Groq/xAI if failed."""
        personality = self._build_personality(theme_mode)
        prompt = f"{personality}\n\n"
        if external_context:
            prompt += f"Context for this conversation:\n{external_context}\n\n"
        prompt += f"User: {user_input}"

        logger.debug(f"Calling Gemini API for input: {user_input[:40]}...")
        start_time = time.time()
        
        try:
            if not self.client:
                raise Exception("Gemini client not available")

            # Primary Attempt: Gemini 2.0 Flash
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )
            
            duration = time.time() - start_time
            logger.info(f"Gemini responded in {duration:.2f}s")
            return response.text

        except Exception as e:
            err_msg = str(e).lower()
            logger.warning(f"Gemini failed: {e}")
            
            # Handle specific overload/timeout cases
            if "503" in err_msg or "overloaded" in err_msg or "timeout" in err_msg:
                logger.info("Server busy, attempting Groq fallback...")
            
            # General fallback to Groq
            return self._groq_fallback(prompt)

    def _groq_fallback(self, prompt: str) -> str:
        """Backup LLM using Groq (Llama-3)."""
        logger.debug("Calling Groq API (Fallback)...")
        start_time = time.time()
        try:
            from groq import Groq
            client = Groq(api_key=self.groq_key)
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
            )
            duration = time.time() - start_time
            logger.info(f"Groq responded in {duration:.2f}s")
            return chat_completion.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq Fallback failed: {e}")
            return self._xai_fallback(prompt)

    def _xai_fallback(self, prompt: str) -> str:
        """Backup LLM using xAI (Grok)."""
        logger.debug("Calling xAI API (Fallback)...")
        start_time = time.time()
        try:
            if not self.xai_client:
                raise Exception("xAI client not initialized")
            chat_completion = self.xai_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="grok-2-latest",
            )
            duration = time.time() - start_time
            logger.info(f"xAI Grok responded in {duration:.2f}s")
            return chat_completion.choices[0].message.content
        except Exception as e:
            logger.error(f"xAI Fallback failed: {e}")
            return "Maaf kijiye, abhi mera connection nahi chal raha hai. Thodi der mein try karein ji 😊"
