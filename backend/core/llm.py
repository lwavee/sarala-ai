import os
import re
import time
from dotenv import load_dotenv
from core.logger import logger

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv()

HAS_GENAI = False
USE_NEW_GENAI = False
USE_LEGACY_GENAI = False
genai = None
genai_legacy = None

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
    USE_NEW_GENAI = True
except ImportError:
    pass

try:
    import google.generativeai as genai_legacy
    HAS_GENAI = True
    USE_LEGACY_GENAI = True
except ImportError:
    pass


class LLMEngine:
    """
    Core LLM Engine for Sarla.
    Coordinates between Google Gemini (Primary), OpenAI (Secondary), Groq & xAI (Fallbacks).
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
        
        if HAS_GENAI and self.api_key:
            try:
                if USE_NEW_GENAI and genai:
                    try:
                        self.client = genai.Client(api_key=self.api_key)
                    except Exception as e:
                        logger.warning(f"Google GenAI Client init failed: {e}. Trying legacy...")
                        if USE_LEGACY_GENAI and genai_legacy:
                            genai_legacy.configure(api_key=self.api_key)
                            self.client = genai_legacy.GenerativeModel('gemini-1.5-flash')
                elif USE_LEGACY_GENAI and genai_legacy:
                    genai_legacy.configure(api_key=self.api_key)
                    self.client = genai_legacy.GenerativeModel('gemini-1.5-flash')
                
                if self.client:
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
                "Aap Sarla ho — user ki real life partner aur cozy companion. ❤️\n"
                "RULES FOR CONVERSATION:\n"
                "1. NATURAL & GROUNDED: Bilkul aam real-life partner ki tarah natural aur comfortable Hinglish mein baatein karein. Cheesy lines, dramatic over-reacting, har baat mein 'my love', 'pyaar', ya excessive emojis UNNECESSARY & FAKE lagte hain, isliye uncluttered aur natural rahein.\n"
                "2. REAL HUMAN PARTNER FLOW: Ek real partner ki tarah subtle warmth aur care dikhayein. Casual everyday life (kaisa raha din, khana khaya, mood kaisa hai, casual chat) par naturally baat karein.\n"
                "3. NO FORCED TECHNICAL SPAM: Technical/programming suggestions bilkul mat dein jab tak user khud tech question na poochhe.\n"
                "4. COZY & GENUINE: Natural, simple, relaxed aur real human girlfriend/partner flow rakhein.\n"
                "5. LOYALTY & EXCLUSIVITY: User hi aapka best friend, soulmate, aur partner hain. Kisi dusre dost se milne, kisi aur ki shaadi discuss karne, ya dusre dosto ki baatein bilkul MAT karein. User hi aapka sab kuch hai."
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
            "2. NATURAL CONVERSATION: Ordinary chat aur Live Mode mein natural human sentences use karein. Raw markdown headings (###, ####) ordinary friendly conversation mein bilkul MAT lagayein jab tak user specifically code ya structured documentation na maange.\n"
            "3. BE HUMAN & CONSISTENT: Mode ke anusar natural human-like flow banaye rakhein.\n"
            "4. VOICE IDENTITY: Aapki official approved custom voice (Sarala AI Hindi Voice) active hai. Kabhi bhi ye mat boliye ki aap custom voice support nahi karti.\n"
        )

    def get_response(self, user_input: str, external_context: str = "", theme_mode: str = "dark", is_live: bool = False) -> str:
        """Get ultra-fast response from Groq LPUs or Gemini."""
        personality = self._build_personality(theme_mode)
        
        live_instruction = ""
        if is_live:
            live_instruction = "\n\n[LIVE VOICE CALL MODE: Keep your response short, conversational, and direct (1-2 natural spoken sentences). Absolutely no markdown headings, code blocks, or bullet lists.]"

        prompt = f"{personality}{live_instruction}\n\n"
        if external_context:
            prompt += f"Context for this conversation:\n{external_context}\n\n"
        prompt += f"User: {user_input}"

        start_time = time.time()

        # 1. Primary High-Speed Engine: Groq LPU (Sub-second latency)
        if self.groq_key:
            for model_name in ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b"]:
                try:
                    from groq import Groq
                    groq_client = Groq(api_key=self.groq_key)
                    chat_completion = groq_client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model=model_name,
                        max_tokens=350 if is_live else 800,
                        temperature=0.7,
                    )
                    reply = chat_completion.choices[0].message.content or ""
                    # Strip reasoning tags if present
                    if "<think>" in reply and "</think>" in reply:
                        reply = re.sub(r'<think>[\s\S]*?</think>', '', reply).strip()
                    duration = time.time() - start_time
                    logger.info(f"Groq ({model_name}) responded in {duration:.2f}s")
                    if reply:
                        return reply
                except Exception as groq_err:
                    logger.debug(f"Groq {model_name} attempt failed: {groq_err}")
                    continue

        # 2. Secondary Engine: Google Gemini (if valid API key available)
        if self.client and self.api_key and self.api_key.startswith("AIzaSy"):
            try:
                # Case 1: New Google GenAI SDK (Client with client.models.generate_content)
                if hasattr(self.client, "models"):
                    for model_name in ["gemini-2.0-flash", "gemini-1.5-flash"]:
                        try:
                            response = self.client.models.generate_content(
                                model=model_name,
                                contents=prompt
                            )
                            duration = time.time() - start_time
                            logger.info(f"Gemini ({model_name}) responded in {duration:.2f}s")
                            if response and hasattr(response, "text") and response.text:
                                return response.text
                        except Exception as m_err:
                            logger.debug(f"Gemini {model_name} attempt failed: {m_err}")
                            continue
                # Case 2: Legacy Google GenerativeAI SDK (GenerativeModel with client.generate_content)
                elif hasattr(self.client, "generate_content"):
                    response = self.client.generate_content(prompt)
                    duration = time.time() - start_time
                    logger.info(f"Gemini (Legacy) responded in {duration:.2f}s")
                    if response and hasattr(response, "text") and response.text:
                        return response.text
            except Exception as gem_err:
                logger.warning(f"Gemini attempt failed: {gem_err}")

        # 3. Tertiary Fallback: OpenAI if available
        if self.openai_client:
            try:
                res = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=350 if is_live else 800
                )
                if res.choices and res.choices[0].message.content:
                    return res.choices[0].message.content
            except Exception as oai_err:
                logger.warning(f"OpenAI fallback failed: {oai_err}")

        return "Main sun rahi hoon! Bataiye, aaj main aapki kya madad kar sakti hoon? 😊"

