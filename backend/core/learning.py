import json
import os
import datetime

class LearningEngine:
    """
    Auto-Learning System for Sarala AI.
    Handles storage, validation (safety/logic), and retrieval of learned facts.
    """
    
    def __init__(self, learning_dir="learning"):
        self.learning_dir = learning_dir
        self.files = {
            "personal": "user_facts.json",
            "tech": "tech_knowledge.json",
            "preferences": "preferences.json"
        }
        self.data = {k: [] for k in self.files}
        self.load()

    def load(self):
        """Load learned data from JSON files."""
        for key, filename in self.files.items():
            path = os.path.join(self.learning_dir, filename)
            if not os.path.exists(path):
                # Ensure directory exists
                os.makedirs(self.learning_dir, exist_ok=True)
                with open(path, "w") as f:
                    json.dump([], f)
                continue
                
            try:
                with open(path, "r") as f:
                    content = f.read().strip()
                    if content:
                        self.data[key] = json.loads(content)
            except Exception as e:
                print(f"Error loading {filename}: {e}")

    def save(self, category):
        """Save specific category back to JSON."""
        path = os.path.join(self.learning_dir, self.files[category])
        with open(path, "w") as f:
            json.dump(self.data[category], f, indent=4)

    def learn(self, fact, category="tech", source="user", topic=None):
        """
        Trigger a learning event. 
        Includes validation layer before storage.
        """
        # 1. Validation Logic
        if not self._is_logical(fact):
            return {"status": "error", "message": "Info logical nahi lag rahi 🧐"}
        
        if self._is_duplicate(fact, category):
            return {"status": "info", "message": "Ye toh mujhe pehle se pata hai! 😊"}

        if self._is_harmful(fact):
            return {"status": "error", "message": "Main aisi cheezein nahi seekhti 🙅‍♀️"}

        # 2. Smart Save Format
        entry = {
            "topic": topic or category,
            "fact": fact,
            "source": source,
            "confidence": 0.8,
            "timestamp": datetime.datetime.now().isoformat()
        }

        # 3. Store
        self.data[category].append(entry)
        self.save(category)
        return {"status": "success", "message": "Theek hai, maine yaad kar liya! ✅"}

    def _is_logical(self, fact):
        """Basic logical check."""
        if len(fact) < 5: return False
        if fact.isdigit() or len(set(fact)) < 3: return False
        return True

    def _is_duplicate(self, fact, category):
        """Check if fact already exists."""
        fact_lower = fact.lower()
        for item in self.data[category]:
            if fact_lower in item["fact"].lower():
                return True
        return False

    def _is_harmful(self, fact):
        """Safety check."""
        harmful_keywords = ["bomb", "kill", "hack", "password", "abuse", "vulgar"]
        return any(k in fact.lower() for k in harmful_keywords)

    def retrieve(self, query, category=None):
        """Search learned data for matches."""
        results = []
        categories = [category] if category else self.data.keys()
        
        query_words = set(query.lower().split())
        for cat in categories:
            for item in self.data[cat]:
                fact_words = set(item["fact"].lower().split())
                if query_words & fact_words and item["confidence"] > 0.4:
                    results.append(item["fact"])
        
        return results

    def update_feedback(self, query, is_positive=True):
        """Update confidence based on user feedback."""
        found = False
        for cat in self.data:
            for item in reversed(self.data[cat]):
                if any(word in item["fact"].lower() for word in query.lower().split() if len(word) > 3):
                    if is_positive:
                        item["confidence"] = min(1.0, item["confidence"] + 0.1)
                    else:
                        item["confidence"] = max(0.0, item["confidence"] - 0.2)
                    self.save(cat)
                    found = True
                    break
            if found: break
        return found
