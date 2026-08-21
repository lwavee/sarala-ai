from typing import Optional, Dict, Any, List
from memory.storage import MemoryStorage
from tools.executor import ToolExecutor
from core.agent import Agent
from core.llm import LLMEngine
from core.knowledge import knowledge_engine
from core.learning import LearningEngine

# Mapping of memory keys to human-friendly Hinglish response labels
KEY_DISPLAY = {
    "user_name":     ("naam",     "{value} hai tera naam 😎"),
    "user_nickname": ("nickname", "Tera nickname hai: {value} 😄"),
    "user_city":     ("city",     "Tu {value} mein rehta hai 🏙️"),
    "user_age":      ("age",      "Teri age {value} saal hai 😊"),
    "user_job":      ("job",      "Tu {value} hai, sahi hai yaar! 👍"),
}


class Brain:
    """
    Sarla's central coordinator.
    Routes user input via Agent intent → calls Memory / Tools / LLM.
    Manages short-term chat history + injects persistent memory context into LLM.
    """

    def __init__(self):
        self.name = "Sarla"
        self.memory = MemoryStorage("memory.json")
        self.tools = ToolExecutor()
        self.agent = Agent()
        self.llm = LLMEngine()
        self.knowledge = knowledge_engine
        self.learning = LearningEngine()
        self.knowledge.load_all_documents()
        self.knowledge.index_documents()
        self._awaiting_name = False  # Multi-turn state flag

    def process_input(self, user_input: str, theme_mode: str = "dark", user_name: str = "", user_nickname: str = "", is_live: bool = False) -> str:
        text = user_input.strip()
        if not text:
            return "Kuch to boliye yaar! 😄"

        # Save session user info to memory if provided
        if user_name:
            self.memory.remember("user_name", user_name)
        if user_nickname:
            self.memory.remember("user_nickname", user_nickname)

        # ---- Multi-turn: waiting for name after "mera naam yaad rakh" ----
        if self._awaiting_name:
            self._awaiting_name = False
            name = text.title()
            self.memory.remember("user_name", name)
            self._log("user", user_input)
            reply = f"Shukriya! Aapka naam {name} yaad kar liya gaya 😊"
            self._log("sarla", reply)
            return reply

        intent = self.agent.understand(user_input)
        intent_type = intent.get("type")
        action = intent.get("action")
        domain = intent.get("domain")

        # Record domain interest for learning mode memory
        if domain:
            interests = self.memory.recall("user_interests") or []
            if domain not in interests:
                interests.append(domain)
                self.memory.remember("user_interests", interests)

        # ---- Command Intents (System + Tools) ----
        if intent_type == "command":
            if action == "exit":
                return "Theek hai, phir milenge! Take care 👋😊"
            if action == "empty":
                return "Kuch boliye na 🤗"

            target = intent.get("target")
            # Execute Tools
            if not target or not isinstance(target, str):
                if action == "open":
                    result = "Kaunsi application open karni hai, batayein? 🤔"
                elif action == "play_youtube":
                    result = "YouTube par kya chalana hai? 🎵"
                elif action == "search_google":
                    result = "Google par kya search karna hai? 🔍"
                else:
                    result = "Kuch samajh nahi aaya 😅"
            elif action == "open":
                result = self.tools.open_application(target)
            elif action == "play_youtube":
                result = self.tools.play_youtube(target)
            elif action == "search_google":
                result = self.tools.search_google(target)
            else:
                result = "Kuch samajh nahi aaya 😅"
                
            self._log("user", user_input)
            self._log("sarla", result)
            return result

        # ---- Memory & Learning ----
        if intent_type == "memory":
            if action in ["teach", "feedback_pos", "feedback_neg"]:
                if action == "teach":
                    cat = "tech" if domain or any(w in text for w in ["python", "js", "web", "tech"]) else "personal"
                    result = self.learning.learn(intent.get("fact"), category=cat, topic=domain)
                    reply = result["message"]
                elif action == "feedback_pos":
                    self.learning.update_feedback(text, is_positive=True)
                    reply = "Shukriya! Maine seekh liya ki main sahi thi 😊"
                elif action == "feedback_neg":
                    self.learning.update_feedback(text, is_positive=False)
                    reply = "Sorry, meri galti 😔 Maine apni knowledge update kar li hai."
                self._log("user", user_input)
                self._log("sarla", reply)
                return reply
            else:
                reply = self._handle_memory(intent, user_input)
                self._log("user", user_input)
                self._log("sarla", reply)
                return reply

        # ---- Search (RAG Domain) ----
        if intent_type == "search":

            return self._llm_fallback(user_input, domain=domain, theme_mode=theme_mode, is_live=is_live)

        # ---- Chat ----
        if intent_type == "chat":
            if action == "greet":
                name = self.memory.recall("user_name")
                nick = self.memory.recall("user_nickname")
                display = nick or name
                
                if theme_mode == "love":
                    display_name = display or "Naveen"
                    reply = f"Hey {display_name}! 😊 Kaisa raha aaj ka din? Sab theek chal raha hai na?"
                elif theme_mode == "light":
                    display_name = display or "champion"
                    reply = f"Hey {display_name}! ⚡ Aaj kya naya seekhna hai ya coding challenge ke liye ready ho? Let's see who wins today! 😉"
                elif theme_mode == "dark_blue":
                    display_name = display or "priye"
                    reply = f"Hari Om {display_name}! 🪔 Shanti aur gyaan ke dwaar par aapka swagat hai. Aaj Geeta ya Ramayana ke kis gyaan par vichar karein?"
                else:
                    reply = (f"Namaste {display}! 💻 Kaisa chal raha hai project? Main aaj aapki coding, security, ya marketing mein kaise madad kar sakti hoon?"
                             if display else f"Namaste! Main Sarla AI hoon 💻 Bataiye aaj kis technical domain ya project par kaam karna hai?")

                self._log("user", user_input)
                self._log("sarla", reply)
                return reply

            elif action == "filler":
                # Local responses for short fillers to save API quota
                resp_map = {
                    "hmm": "Hmm... aur batayein? 😊",
                    "acha": "Achcha... sahi hai 👍",
                    "ok": "Theek hai! ✅",
                    "h": "Ji? Kuch kehna chahte hain? 🤔",
                    "aur": "Aur sab badhiya? 😄",
                    "haan": "Ji! 😊",
                    "nahi": "Theek hai, jaisi aapki marzi! 👍"
                }
                txt = intent.get("text", "hmm")
                reply = resp_map.get(txt, "Ji... aur sunaiye? 😊")
                self._log("user", user_input)
                self._log("sarla", reply)
                return reply
            
            else:
                # Unknown or other chat actions → LLM with full context + RAG
                return self._llm_fallback(user_input, domain=domain, theme_mode=theme_mode, is_live=is_live)

        return "Kuch samajh nahi aaya 😅 Dobara bolein?"

    def _handle_memory(self, intent: dict, raw_input: str) -> str:
        action = intent.get("action")

        if action == "ask_for_name":
            self._awaiting_name = True
            return "Zaroor 😊 Aapka naam kya hai?"

        if action == "remember":
            key = intent.get("key")
            value = str(intent.get("value", "")).strip()
            if not key or not value:
                return "Hmm, value samajh nahi aayi 🤔"
            key_str = str(key)
            self.memory.remember(key_str, value)
            label = KEY_DISPLAY.get(key_str, (key_str, f"{value} — yaad rakh liya! ✅"))[0]
            return f"Done! Aapka {label}: **{value}** — permanently yaad kar liya 💾"

        if action == "recall":
            key = intent.get("key")
            if not key:
                return "Mujhe samajh nahi aaya kya yaad dilana hai 🤔"
            key_str = str(key)
            value = self.memory.recall(key_str)
            if value:
                template = KEY_DISPLAY.get(key_str, ("?", "{value} hai"))[1]
                return template.format(value=value)
            label = KEY_DISPLAY.get(key_str, (key_str, ""))[0]
            return f"Mujhe aapka {label} abhi pata nahi 🙁 Batayein: 'mera {label} X hai'"

        if action == "remember_fact":
            fact = intent.get("value", "")
            existing = self.memory.recall("user_facts") or []
            if isinstance(existing, str):
                existing = [existing]
            existing.append(fact)
            self.memory.remember("user_facts", existing)
            return f"Yaad rakh liya: '{fact}' ✅"

        return "Memory mein kuch karna tha par samajh nahi aaya 🤔"

    def _llm_fallback(self, user_input: str, domain: Optional[str] = None, theme_mode: str = "dark", is_live: bool = False) -> str:
        """Build rich context from memory + RAG and pass to LLM."""
        self._log("user", user_input)

        # ── RAG: Search for technical knowledge if domain is detected ────────
        rag_context = ""
        used_rag = False
        if domain:
            results = self.knowledge.search(user_input)
            if results:
                rag_context = "\nTechnical Reference Knowledge:\n" + "\n---\n".join(results)
                used_rag = True

        # ── Learning: Retrieve user-taught facts ──────────────
        learned_facts = self.learning.retrieve(user_input)
        if learned_facts:
            rag_context += "\nLearned from previous interactions:\n" + "\n".join(learned_facts)

        # Build context string from all known facts
        facts = self.memory.get_all_facts()
        history_ctx = self.memory.get_history_context()
        context_parts = []
        if facts:
            context_parts.append(facts)
        if history_ctx:
            context_parts.append(f"Recent conversation:\n{history_ctx}")
        if rag_context:
            context_parts.append(rag_context)
            
        context = "\n".join(context_parts)

        reply = self.llm.get_response(user_input, external_context=context, theme_mode=theme_mode, is_live=is_live)
        
        if used_rag:
            pass
        elif domain:
            reply = "Main general knowledge se bata rahi hoon... \n\n" + reply

        self._log("sarla", reply)
        return reply

    def _log(self, role: str, text: str):
        self.memory.add_to_history(role, text)

