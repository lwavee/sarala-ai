import json
import os


class MemoryStorage:
    """
    Handles both:
    - Long-term memory: key-value pairs saved to memory.json (e.g. user_name, preferences)
    - Short-term memory: last N chat messages kept in RAM for LLM context
    """
    def __init__(self, filepath="memory.json", max_history=10):
        self.filepath = filepath
        self.max_history = max_history
        self.data = {}          # Long-term JSON based memory
        self.chat_history = []  # Short-term in-memory conversation log
        self.load()

    # ---- Long-Term Memory ----
    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {}

    def save(self):
        with open(self.filepath, "w") as f:
            json.dump(self.data, f, indent=4)

    def remember(self, key, value):
        """Save a long-term fact (e.g. user_name = 'Naveen')"""
        self.data[key] = value
        self.save()

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
