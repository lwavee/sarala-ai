import re
import logging
from typing import Dict, Any, List, Optional
from core.schemas import ALLOWED_MEMORY_TYPES, normalize_memory_type, normalize_importance
from core.services.memory_service import memory_service

logger = logging.getLogger("sarala.services.memory_extraction")

# Sensitive keywords that must NEVER be persisted as plain memories
SENSITIVE_PATTERNS = [
    r"(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?token|bearer|credit[_-]?card|cvv|pin)\b",
    r"(?i)\b[a-zA-Z0-9_-]{20,}\b",  # Tokens / keys
]

# Patterns for hypothetical, conditional, or speculative phrasing that should be rejected
SPECULATION_PATTERNS = [
    r"(?i)\b(maybe|might|could be|perhaps|possibly|what if|if i|hypothetically|wondering if)\b",
]

# Common query prefixes that denote questions rather than facts
QUESTION_PREFIXES = [
    r"(?i)^(what|who|where|when|why|how|is|are|can|could|would|should|will|do|does|did)\b",
    r"(?i)^(kya|kaun|kahan|kab|kyun|kaise|kitna|batao|bataiye)\b",
]


class MemoryExtractionService:
    """
    Intelligent, deterministic, and safe extraction engine for user-specific persistent memory.
    Identifies durable facts, preferences, identity attributes, and explicit remember/forget commands.
    Guarantees:
    - Never stores sensitive credentials, tokens, or passwords.
    - Never converts speculation ('Maybe I will...') or questions into facts.
    - Resolves updates on existing keys to prevent duplicate clutter.
    - Scoped strictly to authenticated user_id.
    """

    def is_sensitive(self, text: str) -> bool:
        """Checks if text contains potential secrets or passwords."""
        for pattern in SENSITIVE_PATTERNS:
            if re.search(pattern, text):
                return True
        return False

    def is_question_or_speculation(self, text: str) -> bool:
        """Determines if input is a question, hypothetical, or speculative statement."""
        t = text.strip()
        if t.endswith("?"):
            return True
        for pat in QUESTION_PREFIXES:
            if re.search(pat, t):
                return True
        for pat in SPECULATION_PATTERNS:
            if re.search(pat, t):
                return True
        return False

    def extract_candidates(self, user_input: str) -> Dict[str, Any]:
        """
        Extracts structured memory candidates and forget directives from user text.
        Returns:
            {
                "should_remember": bool,
                "memories": List[Dict[str, Any]],
                "should_forget": bool,
                "forget_targets": List[str]
            }
        """
        raw = user_input.strip()
        result: Dict[str, Any] = {
            "should_remember": False,
            "memories": [],
            "should_forget": False,
            "forget_targets": [],
        }

        if not raw or self.is_sensitive(raw):
            return result

        # ── 1. Check for Explicit Forget Directives ───────────────────────────
        # "Forget that I prefer dark mode", "Forget my name", "Forget my company", "Bhool jao mera..."
        forget_patterns = [
            r"(?i)\b(?:please\s+)?(?:forget|delete|remove)\s+(?:everything\s+about\s+my\s+|everything\s+you\s+know\s+about\s+my\s+|my\s+|that\s+i\s+prefer\s+|that\s+i\s+like\s+|that\s+i\s+)?([a-zA-Z0-9_\s]{2,40})",
            r"(?i)\b(?:bhool\s+jao|hata\s+do|delete\s+kar\s+do)\s+(?:mera|meri|meru)?\s*([a-zA-Z0-9_\s]{2,40})",
        ]
        for pat in forget_patterns:
            m = re.search(pat, raw)
            if m:
                target = m.group(1).strip().lower()
                # Normalize target words to likely memory keys
                target_key = self._map_topic_to_key(target)
                result["should_forget"] = True
                result["forget_targets"].append(target_key)
                return result

        # ── 2. Check for Explicit Remember Directives (High Priority) ────────
        # "Remember that I prefer dark mode", "Remember my company is XYZ", "Yaad rakhna..."
        explicit_patterns = [
            r"(?i)\b(?:please\s+)?remember\s+(?:that\s+)?(?:my\s+)?([a-zA-Z0-9_\s]{2,30})\s+(?:is|=|now\s+is)\s+([^.!?\n]+)",
            r"(?i)\b(?:please\s+)?remember\s+that\s+([^.!?\n]+)",
            r"(?i)\b(?:yaad\s+rakhna|yaad\s+rakho)\s+(?:ki\s+)?([^.!?\n]+)",
        ]
        for pat in explicit_patterns:
            m = re.search(pat, raw)
            if m:
                if len(m.groups()) == 2:
                    k_raw, v_raw = m.group(1).strip(), m.group(2).strip()
                    key = self._map_topic_to_key(k_raw)
                    val = v_raw
                    mem_type = self._infer_memory_type(key, val)
                    result["should_remember"] = True
                    result["memories"].append({
                        "memory_key": key,
                        "memory_value": val,
                        "memory_type": mem_type,
                        "importance": "high",
                        "source": "explicit_user_command",
                    })
                    return result
                elif len(m.groups()) == 1:
                    statement = m.group(1).strip()
                    parsed = self._parse_durable_fact(statement)
                    if parsed:
                        parsed["importance"] = "high"
                        parsed["source"] = "explicit_user_command"
                        result["should_remember"] = True
                        result["memories"].append(parsed)
                        return result
                    else:
                        # Fallback to key derived from statement
                        key = "user_note"
                        if "dark mode" in statement.lower() or "light mode" in statement.lower() or "theme" in statement.lower():
                            key = "theme_preference"
                        elif "prefer" in statement.lower():
                            key = "user_preference"
                        result["should_remember"] = True
                        result["memories"].append({
                            "memory_key": key,
                            "memory_value": statement,
                            "memory_type": "preference" if "prefer" in statement.lower() or "theme" in key else "personal",
                            "importance": "high",
                            "source": "explicit_user_command",
                        })
                        return result

        # If it's a question, speculative query, or short conversational banter, do NOT auto-extract
        if self.is_question_or_speculation(raw):
            return result

        # ── 3. Natural Durable Facts & Preferences ────────────────────────────
        fact = self._parse_durable_fact(raw)
        if fact:
            result["should_remember"] = True
            result["memories"].append(fact)

        return result

    def _map_topic_to_key(self, topic: str) -> str:
        """Maps user phrases like 'my preferred language' to a canonical key."""
        t = topic.strip().lower()
        mapping = {
            "name": "user_name",
            "my name": "user_name",
            "nickname": "user_nickname",
            "my nickname": "user_nickname",
            "company": "company",
            "my company": "company",
            "work": "company",
            "city": "city",
            "location": "city",
            "language": "preferred_language",
            "preferred language": "preferred_language",
            "favorite language": "favorite_language",
            "favorite programming language": "favorite_language",
            "programming language": "favorite_language",
            "dark mode": "theme_preference",
            "mode": "theme_preference",
            "theme": "theme_preference",
            "framework": "preferred_framework",
            "project": "main_project",
            "main project": "main_project",
            "agency": "company",
            "occupation": "occupation",
            "job": "occupation",
        }
        for k, v in mapping.items():
            if t == k or t.endswith(f" {k}"):
                return v
        return re.sub(r"[^a-zA-Z0-9_]+", "_", t).strip("_")

    def _infer_memory_type(self, key: str, value: str) -> str:
        """Maps key and value semantics to controlled memory types."""
        k = key.lower()
        if k in ["user_name", "user_nickname", "name", "nickname", "full_name"]:
            return "identity"
        if "preference" in k or "favorite" in k or "theme" in k:
            return "preference"
        if k in ["company", "business", "agency", "agency_name"]:
            return "business"
        if k in ["occupation", "job", "profession", "role"]:
            return "work"
        if k in ["learning", "learning_goal", "education", "degree", "college"]:
            return "education"
        if k in ["tech_stack", "preferred_framework", "favorite_language", "database", "tools"]:
            return "technical"
        if k in ["main_project", "project"]:
            return "project"
        if k in ["preferred_language", "communication_style", "tone"]:
            return "communication"
        if k in ["city", "location", "hometown"]:
            return "personal"
        return "personal"

    def _parse_durable_fact(self, text: str) -> Optional[Dict[str, Any]]:
        """Parses natural language statements into structured durable facts."""
        t = text.strip()

        # 1. Name patterns: "My name is Rahul", "Mera naam Rahul hai", "Call me Avee"
        m_name = re.search(r"(?i)\b(?:my\s+name\s+is|mera\s+naam|i\s+am|myself)\s+([A-Z][a-zA-Z0-9_\s]{1,30})", t)
        if m_name and not any(neg in t.lower() for neg in ["not", "learning", "trying", "working"]):
            name = m_name.group(1).split(" and ")[0].split(" but ")[0].strip()
            # Exclude false positives like "I am fine", "I am happy"
            if name.lower() not in ["fine", "good", "happy", "learning", "writing", "thinking", "here", "ready"]:
                return {
                    "memory_key": "user_name",
                    "memory_value": name.title(),
                    "memory_type": "identity",
                    "importance": "high",
                    "source": "conversation",
                }

        # Nickname / Call me
        m_nick = re.search(r"(?i)\b(?:call\s+me|my\s+nickname\s+is)\s+([A-Za-z0-9_]{2,20})", t)
        if m_nick:
            return {
                "memory_key": "user_nickname",
                "memory_value": m_nick.group(1).strip().capitalize(),
                "memory_type": "identity",
                "importance": "high",
                "source": "conversation",
            }

        # 2. Location patterns: "I live in Udaipur", "Main Udaipur mein rehta hoon"
        m_city = re.search(r"(?i)\b(?:i\s+live\s+in|i\s+stay\s+in|main\s+([A-Za-z]+)\s+mein\s+rehta\s+hoon|i\s+am\s+from)\s+([A-Za-z\s]{2,30})", t)
        if m_city:
            city = (m_city.group(1) or m_city.group(2)).strip().title()
            return {
                "memory_key": "city",
                "memory_value": city,
                "memory_type": "personal",
                "importance": "medium",
                "source": "conversation",
            }

        # 3. Learning goals: "I am learning Python", "Main Python seekh raha hoon"
        m_learn = re.search(r"(?i)\b(?:i\s+am\s+learning|i\s+want\s+to\s+learn|main\s+([A-Za-z0-9+#]+)\s+seekh\s+raha\s+hoon)\s+([A-Za-z0-9+#\s]{2,40})", t)
        if m_learn:
            skill = (m_learn.group(1) or m_learn.group(2)).strip()
            return {
                "memory_key": "learning_goal",
                "memory_value": f"Learning {skill}",
                "memory_type": "education",
                "importance": "medium",
                "source": "conversation",
            }

        # 4. Company / Business / Agency: "I own a web development agency", "My company is XYZ", "I work at Google"
        m_company = re.search(r"(?i)\b(?:my\s+company\s+is|i\s+work\s+at|i\s+own\s+(?:a\s+)?)\s+([^.!?\n]{2,50})", t)
        if m_company:
            comp = m_company.group(1).strip()
            return {
                "memory_key": "company",
                "memory_value": comp,
                "memory_type": "business" if "agency" in comp.lower() or "company" in comp.lower() else "work",
                "importance": "medium",
                "source": "conversation",
            }

        # 5. Preferences: "My favorite language is Python", "I now prefer Rust", "I prefer concise answers"
        m_pref = re.search(r"(?i)\b(?:my\s+favorite\s+language\s+is(?:\s+now)?|i\s+(?:now\s+)?prefer\s+(?:language\s+)?)\s+([^.!?\n]{2,50})", t)
        if m_pref:
            target = m_pref.group(1).strip()
            target = re.sub(r"(?i)^now\s+", "", target).strip()
            for lang in ["Python", "Rust", "JavaScript", "TypeScript", "Go", "Java", "C++"]:
                if lang.lower() == target.lower() or target.lower().endswith(lang.lower()):
                    return {
                        "memory_key": "favorite_language",
                        "memory_value": lang,
                        "memory_type": "preference",
                        "importance": "medium",
                        "source": "conversation",
                    }
            if "concise" in target.lower() or "short" in target.lower() or "detailed" in target.lower():
                return {
                    "memory_key": "response_preference",
                    "memory_value": target,
                    "memory_type": "preference",
                    "importance": "medium",
                    "source": "conversation",
                }

        # Theme / mode preference: "I prefer dark mode", "I like dark mode"
        m_theme = re.search(r"(?i)\b(?:i\s+(?:prefer|like|use)\s+)?(dark\s+mode|light\s+mode|dark\s+theme|light\s+theme)\b", t)
        if m_theme:
            return {
                "memory_key": "theme_preference",
                "memory_value": m_theme.group(1).strip().lower(),
                "memory_type": "preference",
                "importance": "high",
                "source": "conversation",
            }

        # Language communication preference: "I want responses in Hinglish", "Speak in Hinglish"
        m_lang = re.search(r"(?i)\b(?:responses?\s+in|speak\s+(?:to\s+me\s+)?in|talk\s+in)\s+([A-Za-z]{3,20})", t)
        if m_lang:
            lang = m_lang.group(1).strip().capitalize()
            return {
                "memory_key": "preferred_language",
                "memory_value": lang,
                "memory_type": "communication",
                "importance": "medium",
                "source": "conversation",
            }

        # 6. Tech stack / Frameworks: "I use Next.js and FastAPI", "My main project is Sarala AI"
        m_stack = re.search(r"(?i)\bi\s+use\s+([^.!?\n]{3,60})", t)
        if m_stack and any(tech in t.lower() for tech in ["next", "fastapi", "react", "vue", "docker", "postgres", "supabase", "mongo"]):
            stack = m_stack.group(1).strip()
            return {
                "memory_key": "tech_stack",
                "memory_value": stack,
                "memory_type": "technical",
                "importance": "medium",
                "source": "conversation",
            }

        m_proj = re.search(r"(?i)\bmy\s+main\s+project\s+is\s+([^.!?\n]{2,60})", t)
        if m_proj:
            proj = m_proj.group(1).strip()
            return {
                "memory_key": "main_project",
                "memory_value": proj,
                "memory_type": "project",
                "importance": "high",
                "source": "conversation",
            }

        return None

    def extract_and_apply(
        self,
        user_id: str,
        user_input: str,
        ai_response: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extracts durable facts or handles explicit forget commands, applying changes directly
        to memory_service scoped strictly to user_id.
        """
        if not user_id:
            return {"applied": False, "reason": "no_user_id"}

        candidates = self.extract_candidates(user_input)

        actions_taken = {
            "applied": False,
            "forgot": [],
            "saved": [],
        }

        # 1. Handle Forget requests
        if candidates.get("should_forget") and candidates.get("forget_targets"):
            for target in candidates["forget_targets"]:
                # Try finding matching keys or delete directly
                mem = memory_service.get_memory(user_id, target)
                if mem:
                    memory_service.delete_memory(user_id, target)
                    actions_taken["forgot"].append(target)
                else:
                    # Also try search match
                    matching, _ = memory_service.list_memories(user_id, search=target)
                    for m in matching:
                        k = m.get("memory_key")
                        if k:
                            memory_service.delete_memory(user_id, k)
                            actions_taken["forgot"].append(k)
            actions_taken["applied"] = True

        # 2. Handle Remember requests
        if candidates.get("should_remember") and candidates.get("memories"):
            for mem in candidates["memories"]:
                key = mem["memory_key"]
                val = mem["memory_value"]
                m_type = normalize_memory_type(mem.get("memory_type", "personal"))
                imp = normalize_importance(mem.get("importance", 1.0))
                source = mem.get("source", "conversation")

                # Upsert memory: automatically updates existing key, resolving conflicts without duplicates
                saved_doc = memory_service.set_memory(
                    user_id=user_id,
                    memory_key=key,
                    memory_value=val,
                    memory_type=m_type,
                    importance=imp,
                    source=source,
                )
                actions_taken["saved"].append(key)
                actions_taken["applied"] = True

        return actions_taken


memory_extraction_service = MemoryExtractionService()
