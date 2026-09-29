import os
import re
import time
from typing import Optional
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

    def get_response(self, user_input: str, external_context: str = "", theme_mode: Optional[str] = "normal", is_live: bool = False) -> str:
        """Get ultra-fast response from Groq LPUs or Gemini."""
        mode = self._normalize_mode(theme_mode)
        personality = self._build_personality(mode)
        
        # Real-time clock calculation in India Standard Time (IST)
        from datetime import datetime, timezone, timedelta
        ist = timezone(timedelta(hours=5, minutes=30))
        now_ist = datetime.now(ist)
        hour = now_ist.hour
        time_12h = now_ist.strftime("%I:%M").lstrip("0")
        am_pm = now_ist.strftime("%p")
        if 5 <= hour < 12:
            period = "subah ke"
        elif 12 <= hour < 17:
            period = "dupehar ke"
        elif 17 <= hour < 20:
            period = "shaam ke"
        else:
            period = "raat ke"
        date_str = f"{now_ist.strftime('%A')}, {now_ist.day} {now_ist.strftime('%B')} {now_ist.year}"
        
        clock_context = (
            f"[REAL-TIME SYSTEM CLOCK (IST / India): Current time is {period} {time_12h} {am_pm}. Today is {date_str}. "
            f"When user asks about time or date, answer naturally based on this exact clock.]"
        )
        
        live_instruction = ""
        if is_live:
            live_instruction = "\n\n[LIVE VOICE CALL MODE: Keep your response short, conversational, and direct (1-2 natural spoken sentences). Absolutely no markdown headings, code blocks, or bullet lists.]"

        prompt = f"{personality}\n\n{clock_context}{live_instruction}\n\n"
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

        # 2. Advanced Engine: SiliconFlow
        if self.siliconflow_client:
            for model_name in ["deepseek-ai/DeepSeek-V2.5", "Qwen/Qwen2.5-72B-Instruct"]:
                try:
                    res = self.siliconflow_client.chat.completions.create(
                        model=model_name,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=350 if is_live else 800,
                        temperature=0.7,
                        stream=False
                    )
                    
                    if hasattr(res, 'choices'):
                        if res.choices and res.choices[0].message.content:
                            duration = time.time() - start_time
                            logger.info(f"SiliconFlow ({model_name}) responded in {duration:.2f}s")
                            return res.choices[0].message.content
                    else:
                        full_content = ""
                        for chunk in res:
                            if hasattr(chunk, 'choices') and chunk.choices and chunk.choices[0].delta.content:
                                full_content += chunk.choices[0].delta.content
                        if full_content:
                            duration = time.time() - start_time
                            logger.info(f"SiliconFlow ({model_name}) stream responded in {duration:.2f}s")
                            return full_content
                except Exception as e:
                    logger.debug(f"SiliconFlow {model_name} attempt failed: {e}")

        # 3. Advanced Engine: Mistral
        if self.mistral_client:
            try:
                res = self.mistral_client.chat.completions.create(
                    model="mistral-large-latest",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=350 if is_live else 800,
                    temperature=0.7,
                    stream=False
                )
                
                if hasattr(res, 'choices'):
                    if res.choices and res.choices[0].message.content:
                        duration = time.time() - start_time
                        logger.info(f"Mistral responded in {duration:.2f}s")
                        return res.choices[0].message.content
                else:
                    full_content = ""
                    for chunk in res:
                        if hasattr(chunk, 'choices') and chunk.choices and chunk.choices[0].delta.content:
                            full_content += chunk.choices[0].delta.content
                    if full_content:
                        duration = time.time() - start_time
                        logger.info(f"Mistral stream responded in {duration:.2f}s")
                        return full_content
            except Exception as e:
                logger.debug(f"Mistral attempt failed: {e}")

        # 4. Secondary Engine: Google Gemini (if valid API key available)
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

        # 5. Tertiary Fallback: OpenAI if available
        if self.openai_client:
            try:
                res = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=350 if is_live else 800,
                    stream=False
                )
                
                if hasattr(res, 'choices'):
                    if res.choices and res.choices[0].message.content:
                        return res.choices[0].message.content
                else:
                    full_content = ""
                    for chunk in res:
                        if hasattr(chunk, 'choices') and chunk.choices and chunk.choices[0].delta.content:
                            full_content += chunk.choices[0].delta.content
                    if full_content:
                        return full_content
            except Exception as oai_err:
                logger.warning(f"OpenAI fallback failed: {oai_err}")

        if mode == "love":
            return "arrey boss, network thoda atak raha hai lagta hai 😅 ek baar dobara bolo na, main yahin hoon!"
        elif mode == "expert":
            return "Connection to intelligence engines timed out. Please check backend API configuration or connectivity."
        return "I apologize, but I am unable to connect to any of my intelligence engines at the moment. Please check my API configurations."

