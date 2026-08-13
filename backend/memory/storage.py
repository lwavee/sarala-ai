import json
import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Try to import supabase, but don't fail if not installed yet
try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv()

class MemoryStorage:
    """
    Handles both:
    - Long-term memory: key-value pairs saved to Supabase (fallback to memory.json)
    - Short-term memory: last N chat messages kept in RAM for LLM context
    """
    def __init__(self, filepath="memory.json", max_history=10):
        self.filepath = filepath
        self.max_history = max_history
        self.data = {}          # Long-term memory cache
        self.chat_history = []  # Short-term in-memory conversation log
        self.supabase = None
        
        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_KEY", "")
        
        self.use_supabase = (
            HAS_SUPABASE and 
            supabase_url and 
            supabase_key and 
            supabase_url != "your_supabase_url_here" and 
            supabase_key != "your_supabase_anon_key_here"
        )
        
        if self.use_supabase:
            try:
                self.supabase = create_client(supabase_url, supabase_key)
                logger.info("Supabase client initialized for MemoryStorage.")
            except Exception as e:
                logger.error(f"Failed to initialize Supabase: {e}")
                self.use_supabase = False
                
        self.load()

    # ---- Long-Term Memory ----
    def load(self):
        if self.use_supabase:
            try:
                response = self.supabase.table("memories").select("*").execute()
                for row in response.data:
                    self.data[row["key"]] = row["value"]
                logger.info(f"Loaded {len(self.data)} memories from Supabase.")
                return
            except Exception as e:
                logger.error(f"Failed to load from Supabase, falling back to local: {e}")
                self.use_supabase = False
                
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {}

    def save(self):
        # Local save only needed if not using Supabase, or as backup
        with open(self.filepath, "w") as f:
            json.dump(self.data, f, indent=4)

    def remember(self, key, value):
        """Save a long-term fact (e.g. user_name = 'Naveen')"""
        self.data[key] = value
        
        if self.use_supabase:
            try:
                # Upsert into memories table
                self.supabase.table("memories").upsert({"key": key, "value": value}).execute()
            except Exception as e:
                logger.error(f"Failed to save memory to Supabase: {e}")
                
        self.save() # Always save locally as backup

    def recall(self, key):
        """Retrieve a long-term fact by key"""
        return self.data.get(key, None)

    def get_all_facts(self) -> str:
        """Summary string of all known facts, to inject into LLM context"""
        if not self.data:
            return ""
        lines = [f"{k}: {v}" for k, v in self.data.items()]
        return "Known facts: " + ", ".join(lines)

    # ---- Short-Term Chat History ----
    def add_to_history(self, role: str, text: str):
        """Add a message to short-term conversation memory"""
        self.chat_history.append({"role": role, "text": text})
        # Keep only last max_history messages
        if len(self.chat_history) > self.max_history:
            self.chat_history = self.chat_history[-self.max_history:]

    def get_history_context(self) -> str:
        """Format short-term chat history as a context block for LLM"""
        if not self.chat_history:
            return ""
        lines = [f"{m['role'].capitalize()}: {m['text']}" for m in self.chat_history]
        return "\n".join(lines)
