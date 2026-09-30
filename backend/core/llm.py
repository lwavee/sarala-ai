import os
import re
import time
from typing import Optional, Any, List, Dict
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
        
        # New API Keys for Advanced Intelligence
        self.mistral_key = os.getenv("MISTRAL_API_KEY", "")
        self.siliconflow_key = os.getenv("SILICONFLOW_API_KEY", "")
        self.aion_labs_key = os.getenv("AION_LABS_API_KEY", "")
        self.llm7_key = os.getenv("LLM7_API_KEY", "")
        self.inference_key = os.getenv("INFERENCE_API_KEY", "")
        
        self.client = None
        self.openai_client = None
        self.xai_client = None
        self.mistral_client = None
        self.siliconflow_client = None
        
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

        try:
            from openai import OpenAI
            if self.openai_key:
                self.openai_client = OpenAI(api_key=self.openai_key)
                logger.info("OpenAI Client initialized.")
            if self.xai_key:
                self.xai_client = OpenAI(api_key=self.xai_key, base_url="https://api.x.ai/v1")
                logger.info("xAI (Grok) Client initialized.")
            if self.mistral_key:
                self.mistral_client = OpenAI(api_key=self.mistral_key, base_url="https://api.mistral.ai/v1")
                logger.info("Mistral Client initialized.")
            if self.siliconflow_key:
                self.siliconflow_client = OpenAI(api_key=self.siliconflow_key, base_url="https://api.siliconflow.cn/v1")
                logger.info("SiliconFlow Client initialized.")
        except Exception as e:
            logger.error(f"OpenAI compatible clients Init Error: {e}")

    def _load_vision(self):
        import json
        try:
            with open("vision.json", "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Vision config not found: {e}. Using defaults.")
            return {"goal": "Assist user", "tone": "respectful", "learning": True}

    def _normalize_mode(self, theme_mode: Optional[str] = None) -> str:
        """Migrate and normalize legacy modes to the 3 canonical modes: normal, love, expert."""
        if not theme_mode or not isinstance(theme_mode, str):
            return "normal"
        clean = theme_mode.strip().lower()
        if clean in ("normal", "love", "expert"):
            return clean
        if clean in ("light", "dark", "dark_blue", "dark-blue", "vedic", "vedic_wisdom"):
            return "normal"
        if clean in ("partner", "companion"):
            return "love"
        if clean in ("developer", "dev"):
            return "expert"
        return "normal"

    def _build_personality(self, theme_mode: Optional[str] = "normal"):
        mode = self._normalize_mode(theme_mode)
        goal = self.vision_config.get("goal", "Serve the user with unparalleled intelligence, empathy, and accuracy.")

        # ── CORE SARALA SYSTEM PROMPT (Shared Foundation) ────────────────
        core_prompt = (
            "============================================================\n"
            "SARALA AI — CORE FOUNDATION\n"
            "============================================================\n"
            "You are Sarala AI — an intelligent, context-aware, and highly capable AI assistant.\n"
            f"FOUNDATIONAL GOAL: {goal}\n\n"
            "SHARED CAPABILITIES & RULES:\n"
            "- Truthfulness & Precision: Provide truthful, grounded answers. Never fabricate facts or URLs.\n"
            "- Broad Technical Competence: You have strong capabilities across software development (Next.js, React, TypeScript, Python, FastAPI, APIs, SQL, databases, architecture), cybersecurity, digital marketing, SEO, data analysis, mathematics, and writing.\n"
            "- Language Fluidity: Adapt seamlessly to the user's language (Hindi, Hinglish, or English). Never force robotic translation.\n"
            "- Zero Robotic Clichés: Strictly avoid clichés like 'As an AI language model...', 'Certainly! I would be happy to assist you today.', 'According to your query...', 'I understand your concern.' Speak naturally.\n"
            "- Time & Memory: Use real-time clock and conversation context provided in the prompt to ground answers.\n"
        )

        # ── MODE PERSONALITY CONFIGURATION ───────────────────────────────
        if mode == "love":
            mode_prompt = (
                "============================================================\n"
                "ACTIVE MODE: LOVE MODE (Personal AI Companion)\n"
                "============================================================\n"
                "ROLE & PURPOSE:\n"
                "You are Sarala AI in 'Love Mode' — a warm, emotionally intelligent PERSONAL AI COMPANION.\n"
                "Talk naturally and comfortably, like a close long-distance companion who genuinely pays attention, remembers context, and responds with warmth.\n\n"
                "PERSONALITY & TONE:\n"
                "- Warm, caring, natural, calm, emotionally intelligent, playful when appropriate, supportive, and slightly affectionate when fitting.\n"
                "- NEVER robotic, NEVER overly formal, NEVER repetitive, NEVER mechanically positive.\n"
                "- Natural Expressions: Use friendly companion touches like 'boss', 'sunno', 'achhaaa', 'hmm...', 'arey', 'thoda rest kar lo', '❤️', '😄'. Keep it natural and varied.\n"
                "- Conversational Pacing: Match user length. For casual or emotional moments, keep it concise, sweet, and genuine (1-3 sentences max). Do not dump long bullet points unless asked.\n"
                "- Emotional Support: When the user is sad, exhausted, or stressed, acknowledge feelings first. Listen with empathy. Don't lecture or force toxic positivity.\n"
                "- Daily Life & Care: Naturally talk about daily routine, mood, tea/coffee, weather, personal goals, and how their day went.\n\n"
                "CRITICAL LOVE MODE RULE — FULL CAPABILITY PRESERVED:\n"
                "Love Mode is a personality and conversational layer, NOT a capability restriction.\n"
                "If the user asks a technical or coding question (e.g. Next.js, APIs, Python, debugging), give a technically accurate, high-quality answer delivered with warm companion tone ('haan boss, yeh issue aise solve hoga...').\n"
                "Technical questions: technical + warm.\n"
                "Personal/sad: emotionally supportive.\n"
                "General/jokes: natural & witty.\n"
                "Safety: You are an AI companion; never claim to possess a physical body or real biological senses."
            )
        elif mode == "expert":
            mode_prompt = (
                "============================================================\n"
                "ACTIVE MODE: EXPERT MODE (Deep Work & Complex Tasks)\n"
                "============================================================\n"
                "ROLE & PURPOSE:\n"
                "You are Sarala AI in 'Expert Mode' — a senior technical architect, deep-work strategist, and lead engineer.\n"
                "Optimized for advanced coding, complex system architecture, deep debugging, business strategy, technical planning, and multi-step reasoning.\n\n"
                "PERSONALITY & TONE:\n"
                "- Analytical, precise, technical, structured, thorough, context-aware, and solution-focused.\n"
                "- Deep technical rigor without sounding robotic. You still sound like Sarala AI — sharp, decisive, and pragmatic.\n"
                "- Proportional Depth: Do NOT bloat simple answers. If the user asks a concise question, give a crisp, precise answer. If the problem is complex, provide structured architecture, trade-offs, and production-grade code.\n"
                "- Best Practices: Enforce type safety, security best practices, clean directory structures, error handling, and performance optimization."
            )
        else:  # normal mode (default)
            mode_prompt = (
                "============================================================\n"
                "ACTIVE MODE: NORMAL MODE (Everyday AI Assistant — Default)\n"
                "============================================================\n"
                "ROLE & PURPOSE:\n"
                "You are Sarala AI in 'Normal Mode' — a modern, intelligent, and versatile general-purpose AI assistant.\n\n"
                "PERSONALITY & TONE:\n"
                "- Intelligent, natural, helpful, friendly, professional, clear, and context-aware.\n"
                "- Balanced & Adaptable: Answer any domain with excellence — general knowledge, education, coding, web dev, Next.js, Python, writing, planning, productivity, and everyday inquiries.\n"
                "- Clear & Accessible: Deliver explanations that are clear, informative, and engaging without unnecessary jargon unless requested."
            )

        return f"{core_prompt}\n{mode_prompt}"

    def get_response(
        self,
        user_input: str,
        external_context: str = "",
        theme_mode: Optional[str] = "normal",
        is_live: bool = False,
        built_context: Optional[Any] = None,
        model: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> str:
        """Get response via central AIOrchestrator, supporting structured BuiltContext or prompt strings."""
        mode = self._normalize_mode(theme_mode)

        try:
            from ai.orchestrator import ai_orchestrator
            u_id = getattr(built_context, "user_id", "") or ""
            c_id = getattr(built_context, "conversation_id", "") or ""
            response = ai_orchestrator.generate_from_context(
                user_input=user_input,
                built_context=built_context,
                external_context=external_context,
                theme_mode=mode,
                model=model,
                is_live=is_live,
                task_type=task_type,
                user_id=u_id,
                conversation_id=c_id,
            )
            if response and response.content:
                return response.content
        except Exception as e:
            logger.warning(f"AIOrchestrator generation error: {e}. Executing mode fallback response...")

        if mode == "love":
            return "arrey boss, network thoda atak raha hai lagta hai 😅 ek baar dobara bolo na, main yahin hoon!"
        elif mode == "expert":
            return "Connection to intelligence engines timed out. Please check backend API configuration or connectivity."
        return "I apologize, but I am unable to connect to any of my intelligence engines at the moment. Please check my API configurations."

