import os
import glob
import re

class KnowledgeEngine:
    """
    Lightweight Zero-Dependency Knowledge Engine for Sarala.
    Uses keyword-based scoring to remain fast and disk-space friendly 
    (No heavy AI models required).
    """

    def __init__(self, knowledge_dir="knowledge"):
        self.knowledge_dir = knowledge_dir
        self.documents = []  # List of dicts {content: str, keywords: set}
        self.load_all_documents()

    def load_all_documents(self):
        """Load all .md and .txt files from the knowledge directory."""
        self.documents = []
        files = glob.glob(os.path.join(self.knowledge_dir, "**", "*.md"), recursive=True)
        files += glob.glob(os.path.join(self.knowledge_dir, "**", "*.txt"), recursive=True)
        
        for file_path in files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    chunks = self._chunk_text(content, file_path)
                    for chunk_text in chunks:
                        # Pre-process keywords for faster matching
                        keywords = set(re.findall(r'\w+', chunk_text.lower()))
                        self.documents.append({
                            "content": chunk_text,
                            "keywords": keywords,
                            "source": os.path.basename(file_path)
                        })
            except Exception as e:
                print(f"Error loading {file_path}: {e}")
        
        print(f"Loaded {len(self.documents)} document chunks (Lightweight Mode).")

    def _chunk_text(self, text, source):
        """Split text by paragraphs/sections."""
        raw_chunks = text.split("\n\n")
        processed_chunks = []
        for c in raw_chunks:
            c = c.strip()
            if len(c) > 40: 
                processed_chunks.append(f"Source: {os.path.basename(source)}\n{c}")
        return processed_chunks

    def index_documents(self):
        """Not needed for keyword mode, kept for compatibility."""
        pass

    def search(self, query, top_k=2):
        """Search using keyword overlap scoring."""
        if not self.documents:
            return []
        
        query_words = set(re.findall(r'\w+', query.lower()))
        scored_docs = []

        for doc in self.documents:
            # Score based on keyword overlap
            score = len(query_words & doc["keywords"])
            if score > 0:
                scored_docs.append((score, doc["content"]))
        
        # Sort by score descending
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        return [doc[1] for doc in scored_docs[:top_k]]

# Singleton instance
knowledge_engine = KnowledgeEngine()

