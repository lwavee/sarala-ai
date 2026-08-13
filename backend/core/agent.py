class Agent:
    """
    Intent detection engine.
    Classifies user input into structured intents so the Brain can route them.
    Supports English + Hinglish patterns with dynamic key-value memory save/recall.
    """

    # Map of English keys to friendly Hinglish names for display
    KEY_LABELS = {
        "user_name": "naam",
        "user_nickname": "nickname",
        "user_city": "city",
        "user_age": "age",
        "user_job": "kaam"
    }

    def __init__(self):
        pass

    def understand(self, user_input: str) -> dict:
        text = user_input.strip().lower()

        # ---- Domain Detection (Technical Expertise) ----
        domain = None
        if any(w in text for w in ["html", "css", "js", "web", "javascript", "website", "frontend", "backend"]):
            domain = "web"
        elif any(w in text for w in ["python", "c++", "java", "code", "programming", "script", "function", "coding"]):
            domain = "programming"
        elif any(w in text for w in ["hacking", "sqlmap", "injection", "exploit", "security", "vulnerability", "kali", "sql injection"]):
            domain = "security"
        elif any(w in text for w in ["cpu", "ram", "motherboard", "hardware", "gpu", "processor"]):
            domain = "hardware"
        elif any(w in text for w in ["robot", "sensor", "arduino", "robotics", "motor", "servo"]):
            domain = "robotics"

        # ---- Command Intents (System + Tools) ----
        if text in ["exit", "quit", "bye", "stop", "band karo", "bye bye", "alvida"]:
            return {"type": "command", "action": "exit"}

        if text == "":
            return {"type": "command", "action": "empty"}

        # ---- Memory: Recall — MUST come before save patterns ----
        if text in ["what is my name?", "mera naam kya hai", "mera naam batao", "apna naam batao"]:
            return {"type": "memory", "action": "recall", "key": "user_name"}
        if text in ["mera nickname kya hai", "what is my nickname"]:
            return {"type": "memory", "action": "recall", "key": "user_nickname"}
        
        # ---- Memory: Learning & Feedback ----
        if text.startswith("remember that ") or text.startswith("yaad rakh ki "):
            fact = (text[14:] if text.startswith("remember that ") else text[13:]).strip()
            return {"type": "memory", "action": "teach", "fact": fact}

        if text in ["sahi hai", "bilkul sahi", "correct", "perfect"]:
            return {"type": "memory", "action": "feedback_pos"}
        
        if text in ["ye galat hai", "galat hai", "wrong", "thik nahi hai"]:
            return {"type": "memory", "action": "feedback_neg"}

        if text in ["mera city kya hai", "where do i live"]:
            return {"type": "memory", "action": "recall", "key": "user_city"}
        if text in ["meri age kya hai", "how old am i"]:
            return {"type": "memory", "action": "recall", "key": "user_age"}
        if text in ["mera kaam kya hai", "what is my job"]:
            return {"type": "memory", "action": "recall", "key": "user_job"}

        # ---- Memory: Multi-turn ----
        if "mera naam yaad rakh" in text:
            return {"type": "memory", "action": "ask_for_name"}

        # ---- Memory: Save ----
        if text.startswith("my name is "):
            val = user_input.strip()[11:].strip().title()
            return {"type": "memory", "action": "remember", "key": "user_name", "value": val}
        if text.startswith("mera naam ") and text.endswith(" hai"):
            val = text[10:-4].strip().title()
            return {"type": "memory", "action": "remember", "key": "user_name", "value": val}

        # Generic remember-this
        if text.startswith("remember that ") or text.startswith("yaad rakh ki "):
            fact = (text[14:] if text.startswith("remember that ") else text[13:]).strip()
            return {"type": "memory", "action": "remember_fact", "value": fact}

        # ---- Command Intents (Tools) ----
        if text.startswith("play ") and " on youtube" in text:
            q = text[5:text.find(" on youtube")].strip()
            return {"type": "command", "action": "play_youtube", "target": q}
        if " on google" in text and (text.startswith("search ") or text.startswith("dhundo ")):
            pre = 11 if text.startswith("search for ") else 7
            q = text[pre:text.find(" on google")].strip()
            return {"type": "command", "action": "search_google", "target": q}

        # ---- Chat Intents ----
        if text in ["hello", "hi", "hy", "hie", "hey", "namaste", "helloo", "heyya", "kaise ho", "kya kar rahi ho", "kaise ho aap"]:
            return {"type": "chat", "action": "greet"}
        
        if text in ["hmm", "acha", "okay", "ok", "haan", "nahi"]:
            return {"type": "chat", "action": "filler", "text": text}

        # ---- Search Intents (RAG) ----
        if domain:
            return {"type": "search", "action": "expert_help", "domain": domain, "text": text}
            
        # ---- Fallback Chat ----
        return {"type": "chat", "action": "unknown", "text": text}

