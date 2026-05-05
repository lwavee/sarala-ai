import os
import time
from core.logger import logger

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False


class LLMEngine:
    """
    Core LLM Engine for Sarla.
    Coordinates between Google Gemini (Primary) and Groq (Fallback).
    Includes logging, robust error handling, and Vision/Personality integration.
    """

    def __init__(self):
        # API Keys (Loaded from env variables to prevent secret leakage)
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.groq_key = os.getenv("GROQ_API_KEY", "")
        self.client = None
        self.vision_config = self._load_vision()
        self.personality = self._build_personality()
        
        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            logger.info("Gemini Client initialized.")
        except ImportError:
            logger.error("google-genai install nahi hai 😊 Run: pip install google-genai")
        except Exception as e:
            logger.error(f"Gemini Init Error: {e}")

    def _load_vision(self):
        import json
        try:
            with open("vision.json", "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Vision config not found: {e}. Using defaults.")
            return {"goal": "Assist user", "tone": "respectful", "learning": True}

    def _build_personality(self):
        goal = self.vision_config.get("goal", "Help the user")
        tone = self.vision_config.get("tone", "friendly and respectful")
        
        return (
            "Aap Sarla ho — ek advanced AI assistant jo professional Markdown formatted responses deti hai. "
            f"Aapka Primary GOAL hai: '{goal}'. "
            f"Aapka TONE humesha '{tone}' hona chahiye.\n\n"
            "── SYSTEM RULES ──\n"
            "1. HINGLISH & RESPECT: Hamesha properly natural Hinglish me baat karein. 'Ji', 'Namaste', 'Shukriya' jaise respectful words use karein.\n"
            "2. MARKDOWN USE KAREIN: Hamesha triple backticks use karein code ke liye.\n"
            "3. BE HUMAN: Human-like flow rakhein, robot jaise nahi. Baatcheet bilkul natural lape me ho.\n"
            "4. DOMAIN EXPERT: Agar technical sawal ho, toh structured format (Headings, bullet points) me samjhayein.\n"
        )

    def get_response(self, user_input: str, external_context: str = "") -> str:
        """Get response from Gemini, fallback to Groq if failed."""
        prompt = f"{self.personality}\n\n"
        if external_context:
            prompt += f"Context for this conversation:\n{external_context}\n\n"
        prompt += f"User: {user_input}"

        logger.debug(f"Calling Gemini API for input: {user_input[:40]}...")
        start_time = time.time()
        
        try:
            if not self.client:
                raise Exception("Gemini client not available")

            # Primary Attempt: Gemini 2.0 Flash Lite (Fast & Smart)
            response = self.client.models.generate_content(
                model="gemini-2.0-flash-lite",
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
            return "Maaf kijiye, abhi mera connection nahi chal raha hai. Thodi der mein try karein ji 😊"
