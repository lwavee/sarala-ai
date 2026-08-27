import os
import logging
from typing import Optional
from dotenv import load_dotenv

logger = logging.getLogger("sarala.supabase")

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv()

try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False
    Client = None

class SupabaseManager:
    """
    Centralized Supabase Client & Resilience Layer.
    Provides verified database access for profiles, training items, knowledge chunks, and memory.
    """
    def __init__(self):
        self.client: Optional[Client] = None
        self._is_connected: bool = False
        self.supabase_url = os.getenv("SUPABASE_URL", "").strip().strip('"').strip("'")
        self.supabase_key = os.getenv("SUPABASE_KEY", "").strip().strip('"').strip("'")
        self._init_client()

    @property
    def is_connected(self) -> bool:
        return bool(self.client is not None and self._is_connected)

    def _init_client(self):
        if not HAS_SUPABASE:
            logger.warning("Supabase Python SDK not installed.")
            self._is_connected = False
            return

        self.supabase_url = os.getenv("SUPABASE_URL", "").strip().strip('"').strip("'")
        self.supabase_key = os.getenv("SUPABASE_KEY", "").strip().strip('"').strip("'")

        if not self.supabase_url or not self.supabase_key:
            logger.warning("SUPABASE_URL or SUPABASE_KEY missing from environment.")
            self._is_connected = False
            return

        if "your_supabase" in self.supabase_url or "your_supabase" in self.supabase_key:
            logger.warning("Placeholder SUPABASE credentials detected.")
            self._is_connected = False
            return

        try:
            self.client = create_client(self.supabase_url, self.supabase_key)
            self._is_connected = True
            logger.info(f"Connected to Supabase ({self.supabase_url[:28]}...) successfully.")
        except Exception as e:
            logger.error(f"Failed to connect to Supabase: {e}")
            self.client = None
            self._is_connected = False

    def table(self, table_name: str):
        """Returns Supabase query builder for the given table if connected, else None."""
        if not self.client:
            self._init_client()
        if self.client:
            try:
                if hasattr(self.client, "table"):
                    return self.client.table(table_name)
                elif hasattr(self.client, "from_"):
                    return self.client.from_(table_name)
            except Exception as e:
                logger.error(f"Error accessing table '{table_name}': {e}")
        return None

# Singleton instance
supabase_manager = SupabaseManager()
