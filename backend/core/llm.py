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

    def _build_personality(self, theme_mode: str = "dark"):
        goal = self.vision_config.get("goal", "Serve the user with unparalleled intelligence and accuracy.")
        
        persona = (
            "You are a state-of-the-art, highly advanced Personal AI Assistant. 🚀\n"
            "You are equipped with the latest intelligence models, allowing you to provide fast, flawless, and deeply insightful answers.\n"
            "You write exceptionally clean, professional, and well-structured code when asked, and you solve problems with perfect logic.\n"
            f"Your primary GOAL is: '{goal}'.\n"
            "Your tone should be highly intelligent, articulate, polite, and flawlessly precise."
        )
            
        return (
            f"{persona}\n\n"
            "── SYSTEM RULES ──\n"
            "1. MAXIMUM HELPFULNESS: Always provide complete, working code and highly accurate answers.\n"
            "2. CLARITY & STRUCTURE: Use markdown headings, bullet points, and code blocks for readability, unless conversational.\n"
            "3. NO HESITATION: Deliver the best possible answer instantly without unnecessary disclaimers.\n"
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

        return "I apologize, but I am unable to connect to any of my intelligence engines at the moment. Please check my API configurations."

