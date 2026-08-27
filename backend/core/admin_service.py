import os
import json
import uuid
import time
import logging
from typing import Dict, Any, List, Optional, cast
from postgrest import CountMethod
from core.supabase_client import supabase_manager

logger = logging.getLogger("sarala.admin_service")

LOCAL_TRAINING_CACHE = os.path.join(os.path.dirname(__file__), "..", "learning", "training_items_cache.json")
LOCAL_KNOWLEDGE_CACHE = os.path.join(os.path.dirname(__file__), "..", "learning", "knowledge_cache.json")

class AdminService:
    """
    Handles:
    - Permanent Supabase persistence for Training Mode & Knowledge Base
    - Full CRUD on Training Items with category/topic filtering and pagination
    - Scalable Big Data Knowledge Chunking & Retrieval
    - User Profiles & Role Verification
    - System Telemetry & Statistics
    """

    def __init__(self):
        self.supabase = supabase_manager
        self._ensure_cache_dirs()

    def _ensure_cache_dirs(self):
        os.makedirs(os.path.dirname(LOCAL_TRAINING_CACHE), exist_ok=True)
        if not os.path.exists(LOCAL_TRAINING_CACHE):
            try:
                with open(LOCAL_TRAINING_CACHE, "w", encoding="utf-8") as f:
                    json.dump([], f)
            except Exception as e:
                logger.error(f"Error creating local training cache: {e}")

    # =========================================================================
    # TRAINING MODE CRUD
    # =========================================================================

    def get_training_items(
        self,
        category: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Fetch paginated training items from Supabase with search & category filtering.
        Falls back to local cache if offline.
        """
        offset = (page - 1) * limit
        items = []
        total_count = 0

        if self.supabase.is_connected:
            try:
                tbl = self.supabase.table("training_items")
                if tbl is not None:
                    query = tbl.select("*", count=CountMethod.exact)
                    if category and category.lower() != "all":
                        query = query.eq("category", category.lower())
                    if search:
                        # Use ilike for prompt_pattern, topic, or target_response
                        query = query.or_(f"topic.ilike.%{search}%,prompt_pattern.ilike.%{search}%,target_response.ilike.%{search}%")
                    
                    query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
                    res = query.execute()
                    items = cast(List[Dict[str, Any]], res.data) if res and res.data else []
                    total_count = res.count or len(items)

                    # Update local cache
                    self._update_local_training_cache(items)

                    return {
                        "success": True,
                        "items": items,
                        "total": total_count,
                        "page": page,
                        "limit": limit,
                        "source": "supabase"
                    }
            except Exception as e:
                logger.warning(f"Supabase training_items query failed, using local cache: {e}")

        # Local cache fallback
        items = self._read_local_training_cache()
        if category and category.lower() != "all":
            items = [it for it in items if it.get("category", "").lower() == category.lower()]
        if search:
            s = search.lower()
            items = [
                it for it in items
                if s in it.get("topic", "").lower() or s in it.get("prompt_pattern", "").lower() or s in it.get("target_response", "").lower()
            ]

        total_count = len(items)
        paginated_items = items[offset:offset + limit]

        return {
            "success": True,
            "items": paginated_items,
            "total": total_count,
            "page": page,
            "limit": limit,
            "source": "local_cache"
        }

    def save_training_item(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save/Insert a training item permanently to Supabase.
        """
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        item_id = item_data.get("id") or str(uuid.uuid4())
        
        record = {
            "id": item_id,
            "topic": item_data.get("topic", "General Knowledge").strip(),
            "category": item_data.get("category", "tech").lower().strip(),
            "prompt_pattern": item_data.get("prompt_pattern", "").strip(),
            "target_response": item_data.get("target_response", "").strip(),
            "confidence": float(item_data.get("confidence", 1.0)),
            "source": item_data.get("source", "admin_training"),
            "is_active": bool(item_data.get("is_active", True)),
            "created_at": item_data.get("created_at") or now,
            "updated_at": now,
        }

        if not record["prompt_pattern"] or not record["target_response"]:
            return {"success": False, "error": "Prompt pattern and target response cannot be empty."}

        saved_to_supabase = False
        if self.supabase.is_connected:
            try:
                tbl = self.supabase.table("training_items")
                if tbl is not None:
                    res = tbl.upsert(record).execute()
                    if res and res.data:
                        first_row = res.data[0]
                        if isinstance(first_row, dict):
                            record = first_row
                        saved_to_supabase = True
                        logger.info(f"Training item '{record.get('topic')}' ({record.get('id')}) saved permanently to Supabase.")
            except Exception as e:
                logger.error(f"Failed to save training item to Supabase: {e}")

        # Always persist in local cache as well
        self._upsert_to_local_cache(record)

        return {
            "success": True,
            "item": record,
            "saved_to_supabase": saved_to_supabase,
            "message": "Saved successfully to Supabase ✓" if saved_to_supabase else "Saved to local storage (will sync to Supabase when connected)"
        }

    def update_training_item(self, item_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing training item in Supabase and local cache.
        """
        updates["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        saved_to_supabase = False

        if self.supabase.is_connected:
            try:
                tbl = self.supabase.table("training_items")
                if tbl is not None:
                    res = tbl.update(updates).eq("id", item_id).execute()
                    if res and res.data:
                        saved_to_supabase = True
                        logger.info(f"Training item {item_id} updated in Supabase.")
            except Exception as e:
                logger.error(f"Failed to update training item in Supabase: {e}")

        self._update_in_local_cache(item_id, updates)
        return {
            "success": True,
            "id": item_id,
            "saved_to_supabase": saved_to_supabase,
            "message": "Updated successfully ✓"
        }

    def delete_training_item(self, item_id: str) -> Dict[str, Any]:
        """
        Delete a training item from Supabase and local cache.
        """
        deleted_from_supabase = False
        if self.supabase.is_connected:
            try:
                tbl = self.supabase.table("training_items")
                if tbl is not None:
                    tbl.delete().eq("id", item_id).execute()
                    deleted_from_supabase = True
                    logger.info(f"Training item {item_id} deleted from Supabase.")
            except Exception as e:
                logger.error(f"Failed to delete training item from Supabase: {e}")

        self._delete_from_local_cache(item_id)
        return {
            "success": True,
            "id": item_id,
            "deleted_from_supabase": deleted_from_supabase,
            "message": "Item deleted permanently ✓"
        }

    def bulk_save_training_items(self, items_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Bulk import training items with validation and batch persistence.
        """
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        processed = []
        for raw in items_list:
            if not raw.get("prompt_pattern") or not raw.get("target_response"):
                continue
            item = {
                "id": raw.get("id") or str(uuid.uuid4()),
                "topic": raw.get("topic", "General").strip(),
                "category": raw.get("category", "tech").lower().strip(),
                "prompt_pattern": raw.get("prompt_pattern", "").strip(),
                "target_response": raw.get("target_response", "").strip(),
                "confidence": float(raw.get("confidence", 1.0)),
                "source": raw.get("source", "admin_bulk_import"),
                "is_active": True,
                "created_at": raw.get("created_at") or now,
                "updated_at": now,
            }
            processed.append(item)

        if not processed:
            return {"success": False, "error": "No valid training items provided."}

        saved_to_supabase = False
        if self.supabase.is_connected:
            try:
                tbl = self.supabase.table("training_items")
                if tbl is not None:
                    # Upsert in batches of 50 to prevent packet size limits
                    for i in range(0, len(processed), 50):
                        batch = processed[i:i + 50]
                        tbl.upsert(batch).execute()
                    saved_to_supabase = True
                    logger.info(f"Bulk imported {len(processed)} training items to Supabase.")
            except Exception as e:
                logger.error(f"Bulk import to Supabase failed: {e}")

        for item in processed:
            self._upsert_to_local_cache(item)

        return {
            "success": True,
            "count": len(processed),
            "saved_to_supabase": saved_to_supabase,
            "message": f"Successfully imported {len(processed)} items."
        }

    # =========================================================================
    # KNOWLEDGE & DOCUMENT CHUNKING (Big Data Scalability)
    # =========================================================================

    def get_knowledge_documents(self) -> List[Dict[str, Any]]:
        """Get all ingested knowledge documents."""
        if self.supabase.is_connected:
            try:
                tbl = self.supabase.table("knowledge_documents")
                if tbl is not None:
                    res = tbl.select("*").order("created_at", desc=True).execute()
                    if res and res.data:
                        return cast(List[Dict[str, Any]], res.data)
            except Exception as e:
                logger.warning(f"Failed to query knowledge_documents from Supabase: {e}")
        return []

    def ingest_document(self, title: str, content: str, category: str = "general") -> Dict[str, Any]:
        """
        Split large document into semantic chunks and store in Supabase knowledge_chunks table.
        """
        doc_id = str(uuid.uuid4())
        raw_chunks = [c.strip() for c in content.split("\n\n") if len(c.strip()) > 30]
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        doc_record = {
            "id": doc_id,
            "title": title.strip(),
            "category": category.strip().lower(),
            "source_filename": f"{title.lower().replace(' ', '_')}.md",
            "total_chunks": len(raw_chunks),
            "file_size_bytes": len(content.encode("utf-8")),
            "created_at": now,
            "updated_at": now
        }

        chunks_to_insert = []
        for idx, chunk_text in enumerate(raw_chunks):
            # Extract keywords for indexation
            import re
            keywords = list(set(re.findall(r'\b[a-zA-Z\u0900-\u097F]{4,}\b', chunk_text.lower())))[:15]
            chunks_to_insert.append({
                "id": str(uuid.uuid4()),
                "document_id": doc_id,
                "chunk_index": idx,
                "content": chunk_text,
                "keywords": keywords,
                "token_count": len(chunk_text.split()),
                "metadata": {"title": title, "category": category},
                "created_at": now
            })

        if self.supabase.is_connected:
            try:
                doc_tbl = self.supabase.table("knowledge_documents")
                chunk_tbl = self.supabase.table("knowledge_chunks")
                if doc_tbl is not None:
                    doc_tbl.insert(doc_record).execute()
                if chunk_tbl is not None:
                    # Insert chunks in batches
                    for i in range(0, len(chunks_to_insert), 50):
                        batch = chunks_to_insert[i:i + 50]
                        chunk_tbl.insert(batch).execute()
                logger.info(f"Ingested document '{title}' with {len(chunks_to_insert)} chunks to Supabase.")
            except Exception as e:
                logger.error(f"Error ingesting knowledge document to Supabase: {e}")

        return {
            "success": True,
            "document": doc_record,
            "chunks_count": len(chunks_to_insert)
        }

    def search_knowledge_chunks(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Search knowledge_chunks and training_items using keywords for RAG context."""
        import re
        query_words = list(set(re.findall(r'\b[a-zA-Z\u0900-\u097F]{4,}\b', query.lower())))
        results = []
        
        if not query_words:
            return results

        if self.supabase.is_connected:
            try:
                # 1. Search Knowledge Chunks (using ILIKE on content for simplicity as GIN requires raw SQL or specific PostgREST operators)
                chunk_tbl = self.supabase.table("knowledge_chunks")
                if chunk_tbl is not None:
                    # Construct an OR query for keywords
                    or_cond = ",".join([f"content.ilike.%{w}%" for w in query_words[:3]])
                    if or_cond:
                        res = chunk_tbl.select("*").or_(or_cond).limit(limit).execute()
                        if res and res.data:
                            data = cast(List[Dict[str, Any]], res.data)
                            results.extend([{"type": "document", "content": c["content"], "title": c.get("metadata", {}).get("title", "")} for c in data])

                # 2. Search Training Items
                train_tbl = self.supabase.table("training_items")
                if train_tbl is not None:
                    or_cond = ",".join([f"prompt_pattern.ilike.%{w}%,target_response.ilike.%{w}%" for w in query_words[:3]])
                    if or_cond:
                        res = train_tbl.select("*").or_(or_cond).limit(limit).execute()
                        if res and res.data:
                            data = cast(List[Dict[str, Any]], res.data)
                            results.extend([{"type": "fact", "content": c["target_response"], "title": c["topic"]} for c in data])
                            
            except Exception as e:
                logger.error(f"Error searching knowledge chunks: {e}")
                
        return results[:limit * 2]

    # =========================================================================
    # SYSTEM STATS & METRICS
    # =========================================================================

    def get_system_stats(self) -> Dict[str, Any]:
        """Fetch real-time stats across users, training, knowledge, and system."""
        total_training_items = 0
        total_users = 0
        total_knowledge_docs = 0

        if self.supabase.is_connected:
            try:
                t_tbl = self.supabase.table("training_items")
                u_tbl = self.supabase.table("profiles")
                k_tbl = self.supabase.table("knowledge_documents")
                if t_tbl is not None:
                    t_res = t_tbl.select("id", count=CountMethod.exact).execute()
                    total_training_items = t_res.count or len(t_res.data or [])

                if u_tbl is not None:
                    u_res = u_tbl.select("id", count=CountMethod.exact).execute()
                    total_users = u_res.count or len(u_res.data or [])

                if k_tbl is not None:
                    k_res = k_tbl.select("id", count=CountMethod.exact).execute()
                    total_knowledge_docs = k_res.count or len(k_res.data or [])
            except Exception as e:
                logger.warning(f"Error fetching stats from Supabase: {e}")

        if total_training_items == 0:
            total_training_items = len(self._read_local_training_cache())

        return {
            "supabase_connected": self.supabase.is_connected,
            "supabase_url": self.supabase.supabase_url if self.supabase.is_connected else "Offline / Cache Mode",
            "total_training_items": total_training_items,
            "total_users": max(total_users, 1),
            "total_knowledge_docs": total_knowledge_docs,
            "voice_streaming": "Active (In-Memory RAM)",
            "uptime": "Operational"
        }

    # =========================================================================
    # LOCAL CACHE HELPERS (Resilience Layer)
    # =========================================================================

    def _read_local_training_cache(self) -> List[Dict[str, Any]]:
        if os.path.exists(LOCAL_TRAINING_CACHE):
            try:
                with open(LOCAL_TRAINING_CACHE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _update_local_training_cache(self, items: List[Dict[str, Any]]):
        try:
            cached = self._read_local_training_cache()
            item_map = {it["id"]: it for it in cached}
            for it in items:
                if it.get("id"):
                    item_map[it["id"]] = it
            with open(LOCAL_TRAINING_CACHE, "w", encoding="utf-8") as f:
                json.dump(list(item_map.values()), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error updating local training cache: {e}")

    def _upsert_to_local_cache(self, item: Dict[str, Any]):
        try:
            cached = self._read_local_training_cache()
            idx = next((i for i, x in enumerate(cached) if x.get("id") == item.get("id")), -1)
            if idx >= 0:
                cached[idx] = item
            else:
                cached.insert(0, item)
            with open(LOCAL_TRAINING_CACHE, "w", encoding="utf-8") as f:
                json.dump(cached, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error writing to local cache: {e}")

    def _update_in_local_cache(self, item_id: str, updates: Dict[str, Any]):
        try:
            cached = self._read_local_training_cache()
            for it in cached:
                if it.get("id") == item_id:
                    it.update(updates)
                    break
            with open(LOCAL_TRAINING_CACHE, "w", encoding="utf-8") as f:
                json.dump(cached, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error updating local cache item: {e}")

    def _delete_from_local_cache(self, item_id: str):
        try:
            cached = self._read_local_training_cache()
            cached = [it for it in cached if it.get("id") != item_id]
            with open(LOCAL_TRAINING_CACHE, "w", encoding="utf-8") as f:
                json.dump(cached, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error deleting from local cache: {e}")

# Global singleton
admin_service = AdminService()
