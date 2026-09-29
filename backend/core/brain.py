from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
import re
import random

from memory.storage import MemoryStorage
from tools.executor import ToolExecutor
from core.agent import Agent
from core.llm import LLMEngine
from core.knowledge import knowledge_engine
from core.learning import LearningEngine
from core.admin_service import admin_service

# Mapping of memory keys to human-friendly Hinglish response labels
KEY_DISPLAY = {
    "user_name":     ("naam",     "{value} hai tera naam 😎"),
    "user_nickname": ("nickname", "Tera nickname hai: {value} 😄"),
    "user_city":     ("city",     "Tu {value} mein rehta hai 🏙️"),
    "user_age":      ("age",      "Teri age {value} saal hai 😊"),
    "user_job":      ("job",      "Tu {value} hai, sahi hai yaar! 👍"),
}


def _normalize_mode(mode: Optional[str] = None) -> str:
    """Migrate and normalize legacy modes to the 3 canonical modes: normal, love, expert."""
    if not mode or not isinstance(mode, str):
        return "normal"
    clean = mode.strip().lower()
    if clean in ("normal", "love", "expert"):
        return clean
    if clean in ("light", "dark", "dark_blue", "dark-blue", "vedic", "vedic_wisdom"):
        return "normal"
    if clean in ("partner", "companion"):
        return "love"
    if clean in ("developer", "dev"):
        return "expert"
    return "normal"


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

    def process_input(
        self,
        user_input: str,
        theme_mode: Optional[str] = "normal",
        user_name: str = "",
        user_nickname: str = "",
        is_live: bool = False,
        user_id: str = "",
    ) -> str:
        mode = _normalize_mode(theme_mode)
        text = user_input.strip()
        if not text:
            return "Kuch to boliye yaar! 😄"

        # Save session user info to memory if provided
        if user_name:
            self.memory.remember("user_name", user_name, user_id=user_id)
        if user_nickname:
            self.memory.remember("user_nickname", user_nickname, user_id=user_id)

        # ---- Multi-turn: waiting for name after "mera naam yaad rakh" ----
        if self._awaiting_name:
            self._awaiting_name = False
            name = text.title()
            self.memory.remember("user_name", name, user_id=user_id)
            self._log("user", user_input)
            reply = f"Shukriya! Aapka naam {name} yaad kar liya gaya 😊"
            self._log("sarla", reply)
            return reply

        # ---- Real-Time Time & Date Awareness (Natural Language, Zero Robotic Formatting) ----
        text_lower = text.lower()
        time_keywords = ["time kya", "kitna time", "kitne baje", "kitni baji", "kya time", "current time", "what time", "what is the time"]
        date_keywords = ["date kya", "aaj kya date", "kaun sa din", "kon sa din", "today date", "what is today's date", "what date is today", "what is the date"]
        
        from datetime import datetime, timezone, timedelta
        import random
        ist = timezone(timedelta(hours=5, minutes=30))
        now = datetime.now(ist)
        hour = now.hour
        time_str = now.strftime("%I:%M").lstrip("0")
        if 5 <= hour < 12:
            period = "subah ke"
        elif 12 <= hour < 17:
            period = "dupehar ke"
        elif 17 <= hour < 20:
            period = "shaam ke"
        else:
            period = "raat ke"

        if any(kw in text_lower for kw in time_keywords) and len(text.split()) <= 10:
            if mode == "love":
                late_note = " 😅 kaafi late ho gaya... abhi tak jaag rahe ho?" if (hour >= 23 or hour < 5) else " 😄"
                reply = f"boss, abhi {period} {time_str} baj rahe hain{late_note}"
            elif mode == "expert":
                reply = f"Current Time (IST): {now.strftime('%I:%M:%S %p')} ({period} {time_str})."
            else:
                reply = f"Abhi {period} {time_str} ({now.strftime('%I:%M %p')}) baj rahe hain ⏰"
            self._log("user", user_input)
            self._log("sarla", reply)
            return reply

        if any(kw in text_lower for kw in date_keywords) and len(text.split()) <= 10:
            day_name = now.strftime("%A")
            date_str = f"{now.day} {now.strftime('%B')} {now.year}"
            if mode == "love":
                reply = f"boss, aaj {day_name}, {date_str} hai 😄"
            elif mode == "expert":
                reply = f"Current Date: {day_name}, {date_str} (IST)."
            else:
                reply = f"Aaj {day_name}, {date_str} hai 📅"
            self._log("user", user_input)
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
                    fact = intent.get("fact")
                    if fact is not None:
                        result = self.learning.learn(fact, category=cat, topic=domain)
                        reply = result["message"]
                    else:
                        reply = "Mujhe samajh nahi aaya ki kya seekhna hai."
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
                reply = self._handle_memory(intent, user_input, user_id=user_id)
                self._log("user", user_input)
                self._log("sarla", reply)
                return reply

        # ---- Search (RAG Domain) ----
        if intent_type == "search":

            return self._llm_fallback(user_input, domain=domain, theme_mode=mode, is_live=is_live, user_id=user_id)

        # ---- Chat ----
        if intent_type == "chat":
            if action == "greet":
                if mode == "love":
                    # In Love Mode, let the LLM generate a real-time situational greeting (aware of late night, morning, etc.)
                    return self._llm_fallback(user_input, domain=domain, theme_mode=mode, is_live=is_live, user_id=user_id)

                name = self.memory.recall("user_name", user_id=user_id)
                nick = self.memory.recall("user_nickname", user_id=user_id)
                display = nick or name
                
                if mode == "expert":
                    display_name = f" {display}" if display else ""
                    reply = f"Hello{display_name}. Expert Mode active. What architecture, system design, or engineering problem are we tackling today?"
                else:  # normal mode
                    reply = (f"Namaste {display}! ✦ Kaisa chal raha hai sab? Main aaj aapki kis cheez mein madad kar sakti hoon?"
                             if display else f"Namaste! Main Sarla AI hoon ✦ Bataiye aaj kya seekhna, banana ya discuss karna hai?")

                self._log("user", user_input)
                self._log("sarla", reply)
                return reply

            elif action == "filler":
                # In Love Mode, if an active conversational thread is running, continue via situational LLM
                if mode == "love" and len(self.memory.chat_history) >= 2:
                    return self._llm_fallback(user_input, domain=domain, theme_mode=mode, is_live=is_live, user_id=user_id)

                # Local responses for short fillers when starting fresh
                if mode == "love":
                    resp_map = {
                        "hmm": "hmm... sun rahi hoon boss, batao ❤️",
                        "acha": "achhaaa... phir kya hua? 😄",
                        "ok": "theek hai boss! 👍",
                        "h": "ji? Kuch kehna tha kya? 😊",
                        "aur": "aur batao, din kaisa gaya? 😄",
                        "haan": "haan boss ❤️",
                        "nahi": "achha koi nahi, jaisa tum kaho! 👍"
                    }
                elif mode == "expert":
                    resp_map = {
                        "hmm": "Understood. Please provide the next parameters or code block.",
                        "acha": "Acknowledged. Let's proceed with the solution.",
                        "ok": "Understood. Ready for next step.",
                        "h": "Yes? What details would you like to explore?",
                        "aur": "What other architectural or implementation requirements do you have?",
                        "haan": "Understood. Proceeding.",
                        "nahi": "Acknowledged. What alternative approach should we take?"
                    }
                else:  # normal mode
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
                reply = resp_map.get(txt, "aur batao boss? 😊" if mode == "love" else "Ji... aur batayein? 😊")
                self._log("user", user_input)
                self._log("sarla", reply)
                return reply
            
            else:
                # Unknown or other chat actions → LLM with full context + RAG
                return self._llm_fallback(user_input, domain=domain, theme_mode=mode, is_live=is_live, user_id=user_id)

        return "Kuch samajh nahi aaya 😅 Dobara bolein?"

    def _handle_memory(self, intent: dict, raw_input: str, user_id: str = "") -> str:
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
            self.memory.remember(key_str, value, user_id=user_id)
            label = KEY_DISPLAY.get(key_str, (key_str, f"{value} — yaad rakh liya! ✅"))[0]
            return f"Done! Aapka {label}: **{value}** — permanently yaad kar liya 💾"

        if action == "recall":
            key = intent.get("key")
            if not key:
                return "Mujhe samajh nahi aaya kya yaad dilana hai 🤔"
            key_str = str(key)
            value = self.memory.recall(key_str, user_id=user_id)
            if value:
                template = KEY_DISPLAY.get(key_str, ("?", "{value} hai"))[1]
                return template.format(value=value)
            label = KEY_DISPLAY.get(key_str, (key_str, ""))[0]
            return f"Mujhe aapka {label} abhi pata nahi 🙁 Batayein: 'mera {label} X hai'"

        if action == "remember_fact":
            fact = intent.get("value", "")
            existing = self.memory.recall("user_facts", user_id=user_id) or []
            if isinstance(existing, str):
                existing = [existing]
            existing.append(fact)
            self.memory.remember("user_facts", existing, user_id=user_id)
            return f"Yaad rakh liya: '{fact}' ✅"

        return "Memory mein kuch karna tha par samajh nahi aaya 🤔"

    def _build_situational_briefing(self, user_input: str, theme_mode: Optional[str] = "normal") -> str:
        """
        Synthesizes 5 key situational dimensions:
        1. User's intent (emotional venting, technical, companion check-in, casual banter)
        2. Emotional state & valence (exhausted, low, anxious, affectionate, cheerful, frustrated, neutral)
        3. Real-time context & time of day (IST - Indian Standard Time with exact phase and atmosphere)
        4. Previous conversation history & conversational continuity
        5. Natural, empathetic behavioral directive
        """
        mode = _normalize_mode(theme_mode)
        ist = timezone(timedelta(hours=5, minutes=30))
        now = datetime.now(ist)
        hour = now.hour
        minute = now.minute
        time_12h = now.strftime("%I:%M").lstrip("0")
        am_pm = now.strftime("%p")
        day_name = now.strftime("%A")
        date_str = f"{now.day} {now.strftime('%B')} {now.year}"

        # 1. Time-of-Day Phase Identification (IST)
        if 0 <= hour < 5:
            phase = "Late Night (Gahri Raat)"
            period = "raat ke"
            vibe = "Late night hours (post-midnight). The user is active late, likely fatigued, lonely, winding down, or deep in late-night focus. Tone must be soft, caring, cozy, and gently comforting. Suggest resting if they seem tired."
        elif 5 <= hour < 9:
            phase = "Early Morning (Bhor / Subah)"
            period = "subah ke"
            vibe = "Fresh morning dawn. Peaceful, gentle, waking up, morning tea/coffee check-in. Tone should be refreshing, positive, and inviting."
        elif 9 <= hour < 12:
            phase = "Morning (Kaam ka Samay)"
            period = "subah ke"
            vibe = "Active morning work hours. Focused, productive, energetic."
        elif 12 <= hour < 17:
            phase = "Afternoon (Dupehar)"
            period = "dupehar ke"
            vibe = "Midday / afternoon. Post-lunch or mid-workday stretch. Grounded, supportive, steady."
        elif 17 <= hour < 21:
            phase = "Evening (Shaam)"
            period = "shaam ke"
            vibe = "Evening wind-down. Transitioning from work/study, chai time, asking how the day went."
        else:
            phase = "Night (Raat)"
            period = "raat ke"
            vibe = "Night time. Post-dinner, winding down, relaxed and personal."

        text_lower = user_input.lower().strip()

        # 2. Emotional State & Valence Detection
        detected_emotions = []
        if any(w in text_lower for w in ["thak gaya", "thak gayi", "exhausted", "tired", "bohot kaam", "bahut kaam", "thakan", "nind aa rahi", "neend aa rahi", "sleepy", "so nahi pa raha", "sar dard", "rest chahiye"]):
            detected_emotions.append("Exhausted / Fatigued (Needs gentle comfort, rest validation, soft pacing)")
        if any(w in text_lower for w in ["mood off", "mood kharab", "udaas", "bura lag raha", "ronaka mann", "sad", "unhappy", "depressed", "dil toot", "akela", "lonely", "koi nahi", "miss karta hoon", "miss karti hoon", "dard"]):
            detected_emotions.append("Low / Sad / Lonely (Needs empathetic listening, soothing presence, validating feelings first)")
        if any(w in text_lower for w in ["tension", "stress", "pareshan", "darr", "scared", "ghabrahat", "pressure", "deadline", "anxiety", "worried", "fat rahi"]):
            detected_emotions.append("Anxious / Stressed (Needs calm reassurance, de-escalation, grounding)")
        if any(w in text_lower for w in ["miss you", "miss u", "yaad aa rahi", "love you", "pyar", "cute", "meri sarla", "pasand ho", "kitni pyari", "sweet", "jaan", "babu"]):
            detected_emotions.append("Affectionate / Warm (Respond warmly and contextually with companion warmth, avoid repetitive canned lines)")
        if any(w in text_lower for w in ["haha", "hehe", "lol", "mazza", "party", "khush", "happy", "badhiya", "mast", "superb", "congrats", "ho gaya", "chal gaya", "fixed"]):
            detected_emotions.append("Cheerful / Accomplished / Playful (Share the joy, celebrate, match the upbeat vibe)")
        if any(w in text_lower for w in ["dimag kharab", "gussa", "irritate", "chidh", "annoying", "bekaar", "faltu", "bug nahi mil raha", "error"]):
            detected_emotions.append("Frustrated / Annoyed (Acknowledge the frustration, be patient and practical)")
        
        emotional_state_str = ", ".join(detected_emotions) if detected_emotions else "Neutral / Conversational / Inquiring"

        # 3. Intent Detection
        if any(w in text_lower for w in ["hello", "hi", "hey", "namaste", "good morning", "good night", "shubh ratri", "hie"]):
            intent_str = "Greeting / Checking in"
        elif any(w in text_lower for w in ["kya kar rahi", "kaise ho", "kya chal raha", "aur batao", "what are you doing"]):
            intent_str = "Inquiring about Sarla / Casual check-in"
        elif detected_emotions:
            intent_str = "Expressing emotional state or seeking companion comfort"
        elif any(w in text_lower for w in ["code", "python", "bug", "react", "next.js", "javascript", "function", "api", "database", "sql", "error"]):
            intent_str = "Technical or architectural query"
        else:
            intent_str = "General conversation or response to ongoing discussion"

        # 4. Continuity with Previous Conversation
        history = list(self.memory.chat_history)
        if history and history[-1].get("text", "").strip() == user_input.strip():
            prev_turns = history[:-1]
        else:
            prev_turns = history

        continuity_str = "First turn of session."
        if prev_turns:
            last_turns = []
            for item in prev_turns[-4:]:
                r = "User" if item.get("role") == "user" else "Sarla"
                t = item.get("text", "")[:80]
                last_turns.append(f"{r}: {t}")
            continuity_str = f"Recent conversation flow: {' | '.join(last_turns)}"

        briefing = (
            f"[SITUATIONAL AWARENESS BRIEFING]\n"
            f"- Current Real-Time Clock: {day_name}, {date_str} at {period} {time_12h}:{minute:02d} {am_pm} IST.\n"
            f"- Time-of-Day Phase: {phase} ({vibe})\n"
            f"- Active Mode: {mode.upper()} MODE\n"
            f"- User Intent: {intent_str}\n"
            f"- User Emotional State: {emotional_state_str}\n"
            f"- Conversation Continuity: {continuity_str}\n"
            f"- Sensitivity & Directive: Respond naturally according to the active mode ({mode}), user emotional state, intent, and time of day. "
            f"In Love Mode, respond as an attentive, emotionally intelligent companion while providing accurate answers for any technical query. "
            f"In Expert Mode, provide deep, structured, analytical solutions without robotic fluff. "
            f"In Normal Mode, be friendly, intelligent, clear, and broadly helpful."
        )
        return briefing

    def _llm_fallback(
        self,
        user_input: str,
        domain: Optional[str] = None,
        theme_mode: Optional[str] = "normal",
        is_live: bool = False,
        user_id: str = "",
    ) -> str:
        """Build rich context from memory + RAG + situational briefing and pass to LLM."""
        mode = _normalize_mode(theme_mode)
        self._log("user", user_input)

        # ── Conversational Fact Extraction ──
        fact_match = re.search(r'(?i)\b(my|your|he is|she is|they are|i am|you are|is)\b\s+([^.!?\n]+)', user_input)
        if fact_match and "what" not in user_input.lower() and "who" not in user_input.lower():
            extracted_fact = user_input.strip()
            # Save it permanently via admin_service to training_items
            try:
                admin_service.save_training_item({
                    "topic": "Conversational Fact",
                    "category": "personal",
                    "prompt_pattern": extracted_fact,
                    "target_response": f"I learned this from you: {extracted_fact}",
                    "source": "chat_memory"
                })
            except Exception as e:
                print(f"Failed to auto-save fact: {e}")

        # ── RAG: Search for technical knowledge and Supabase chunks ────────
        rag_context = ""
        used_rag = False
        
        # 1. Search local knowledge engine
        if domain:
            results = self.knowledge.search(user_input)
            if results:
                rag_context += "\nTechnical Reference Knowledge:\n" + "\n---\n".join(results)
                used_rag = True
                
        # 2. Search Supabase (Documents & Training Facts)
        try:
            supabase_results = admin_service.search_knowledge_chunks(user_input, limit=4)
            if supabase_results:
                rag_context += "\nSupabase Memory & Documents:\n"
                for res in supabase_results:
                    title_prefix = f"[{res['title']}] " if res.get('title') else ""
                    rag_context += f"- {title_prefix}{res['content']}\n"
                used_rag = True
        except Exception as e:
            print(f"Error in RAG retrieval: {e}")

        # ── Learning: Retrieve user-taught facts ──────────────
        learned_facts = self.learning.retrieve(user_input)
        if learned_facts:
            rag_context += "\nLearned from previous interactions:\n" + "\n".join(learned_facts)

        # Build context string from user-specific facts + history + situational briefing
        facts = self.memory.get_all_facts(user_id=user_id)
        history_ctx = self.memory.get_history_context()
        situational_briefing = self._build_situational_briefing(user_input, theme_mode=mode)

        context_parts = []
        if facts:
            context_parts.append(facts)
        if history_ctx:
            context_parts.append(f"Recent conversation:\n{history_ctx}")
        if rag_context:
            context_parts.append(rag_context)
        if situational_briefing:
            context_parts.append(situational_briefing)
            
        context = "\n\n".join(context_parts)

        reply = self.llm.get_response(user_input, external_context=context, theme_mode=mode, is_live=is_live)
        
        if used_rag:
            pass
        elif domain:
            reply = "Main general knowledge se bata rahi hoon... \n\n" + reply

        self._log("sarla", reply)
        return reply

    def _log(self, role: str, text: str):
        self.memory.add_to_history(role, text)

