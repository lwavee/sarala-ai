"""
Agent Execution Repository & State Persistence Layer.
Persists Agent Runs, Steps, and Execution Events to Supabase PostgreSQL with in-memory resilience.
Strictly enforces ownership using canonical MongoDB user_id.
"""

import threading
import datetime
from typing import Optional, Dict, Any, List
from core.logger import logger
from core.supabase_client import supabase_manager
from ai.agent.models import (
    AgentRunRecord,
    AgentStepRecord,
    AgentRunStatus,
    StepStatus,
    StepType,
    ExecutionMode,
)


class AgentRepository:
    """
    Central repository for Agent Execution state.
    Provides verified multi-tier persistence with Supabase PostgreSQL and fallback in-memory cache.
    """

    def __init__(self):
        self._lock = threading.RLock()
        # In-memory stores for testing, development, and offline resilience
        self._runs: Dict[str, Dict[str, Any]] = {}  # run_id -> run_dict
        self._steps: Dict[str, List[Dict[str, Any]]] = {}  # run_id -> list of step_dict
        self._events: Dict[str, List[Dict[str, Any]]] = {}  # run_id -> list of event_dict
        self._idempotency_map: Dict[str, str] = {}  # idempotency_key -> run_id

    # ── AGENT RUN METHODS ────────────────────────────────────────────────────

    def get_run_by_idempotency_key(self, user_id: str, idempotency_key: str) -> Optional[AgentRunRecord]:
        """Retrieves an existing run by idempotency_key scoped to user_id."""
        with self._lock:
            if idempotency_key in self._idempotency_map:
                run_id = self._idempotency_map[idempotency_key]
                return self.get_run(user_id, run_id)
        return None

    def create_run(self, run: AgentRunRecord, idempotency_key: Optional[str] = None) -> AgentRunRecord:
        """Persists a new AgentRunRecord."""
        with self._lock:
            if idempotency_key and idempotency_key in self._idempotency_map:
                existing_id = self._idempotency_map[idempotency_key]
                existing_run = self.get_run_unscoped(existing_id)
                if existing_run and existing_run.user_id == run.user_id:
                    return existing_run

            data = run.to_dict()
            self._runs[run.id] = dict(data)
            self._steps[run.id] = []
            self._events[run.id] = []
            if idempotency_key:
                self._idempotency_map[idempotency_key] = run.id

        # Attempt Supabase insert
        if supabase_manager.is_connected:
            try:
                table = supabase_manager.table("agent_runs")
                if table:
                    table.insert(data).execute()
            except Exception as e:
                logger.debug(f"Optional Supabase agent_runs insert skipped: {e}")

        return run

    def get_run(self, user_id: str, run_id: str) -> Optional[AgentRunRecord]:
        """Retrieves an AgentRunRecord strictly scoped to the authenticated user_id."""
        with self._lock:
            # First check in-memory cache
            if run_id in self._runs:
                raw = self._runs[run_id]
                if raw.get("user_id") == user_id:
                    return AgentRunRecord(**raw)
                return None

        # Check Supabase
        if supabase_manager.is_connected:
            try:
                table = supabase_manager.table("agent_runs")
                if table:
                    res = table.select("*").eq("id", run_id).eq("user_id", user_id).execute()
                    if res.data and len(res.data) > 0:
                        with self._lock:
                            self._runs[run_id] = res.data[0]
                        return AgentRunRecord(**res.data[0])
            except Exception as e:
                logger.debug(f"Error querying Supabase agent_runs: {e}")

        return None

    def get_run_unscoped(self, run_id: str) -> Optional[AgentRunRecord]:
        """Retrieves an AgentRunRecord without user filtering to distinguish 404 from 403."""
        with self._lock:
            if run_id in self._runs:
                return AgentRunRecord(**self._runs[run_id])

        if supabase_manager.is_connected:
            try:
                table = supabase_manager.table("agent_runs")
                if table:
                    res = table.select("*").eq("id", run_id).execute()
                    if res.data and len(res.data) > 0:
                        with self._lock:
                            self._runs[run_id] = res.data[0]
                        return AgentRunRecord(**res.data[0])
            except Exception as e:
                logger.debug(f"Error querying Supabase agent_runs unscoped: {e}")

        return None

    def list_runs(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> List[AgentRunRecord]:
        """Lists runs belonging strictly to user_id, ordered by creation descending."""
        runs: List[AgentRunRecord] = []

        with self._lock:
            for r in self._runs.values():
                if r.get("user_id") == user_id:
                    if status and r.get("status") != status:
                        continue
                    if conversation_id and r.get("conversation_id") != conversation_id:
                        continue
                    runs.append(AgentRunRecord(**r))

            # Sort descending by created_at
            runs.sort(key=lambda x: x.created_at, reverse=True)
            mem_slice = runs[offset : offset + limit]

        # If Supabase is connected, attempt fetch for persistent sync
        if supabase_manager.is_connected:
            try:
                table = supabase_manager.table("agent_runs")
                if table:
                    q = table.select("*").eq("user_id", user_id).order("created_at", desc=True)
                    if status:
                        q = q.eq("status", status)
                    if conversation_id:
                        q = q.eq("conversation_id", conversation_id)
                    res = q.range(offset, offset + limit - 1).execute()
                    if res.data:
                        supa_runs = [AgentRunRecord(**row) for row in res.data]
                        with self._lock:
                            for row in res.data:
                                self._runs[row["id"]] = row
                        return supa_runs
            except Exception as e:
                logger.debug(f"Error querying Supabase agent_runs list: {e}")

        return mem_slice

    def update_run(self, user_id: str, run_id: str, updates: Dict[str, Any]) -> Optional[AgentRunRecord]:
        """Updates an AgentRunRecord verified by user_id."""
        with self._lock:
            if run_id not in self._runs:
                # Try loading from Supabase first
                rec = self.get_run(user_id, run_id)
                if not rec:
                    return None

            raw = self._runs[run_id]
            if raw.get("user_id") != user_id:
                return None

            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            updates["updated_at"] = now_iso

            # Merge updates
            for k, v in updates.items():
                if hasattr(v, "value"):
                    raw[k] = v.value
                else:
                    raw[k] = v

            updated_record = AgentRunRecord(**raw)

        # Update Supabase
        if supabase_manager.is_connected:
            try:
                table = supabase_manager.table("agent_runs")
                if table:
                    db_payload = {}
                    for k, v in updates.items():
                        if hasattr(v, "value"):
                            db_payload[k] = v.value
                        else:
                            db_payload[k] = v
                    table.update(db_payload).eq("id", run_id).eq("user_id", user_id).execute()
            except Exception as e:
                logger.debug(f"Error updating Supabase agent_runs: {e}")

        return updated_record

    # ── AGENT STEP METHODS ───────────────────────────────────────────────────

    def create_steps(self, steps: List[AgentStepRecord]) -> List[AgentStepRecord]:
        """Batch inserts execution steps for an agent run."""
        if not steps:
            return []

        run_id = steps[0].agent_run_id
        user_id = steps[0].user_id

        with self._lock:
            if run_id not in self._steps:
                self._steps[run_id] = []
            for s in steps:
                self._steps[run_id].append(s.to_dict())

        # Insert to Supabase
        if supabase_manager.is_connected:
            try:
                table = supabase_manager.table("agent_steps")
                if table:
                    payload = [s.to_dict() for s in steps]
                    table.insert(payload).execute()
            except Exception as e:
                logger.debug(f"Error batch inserting agent_steps to Supabase: {e}")

        return steps

    def get_steps(self, run_id: str, user_id: str) -> List[AgentStepRecord]:
        """Retrieves all steps for a run, ordered by step_index."""
        with self._lock:
            if run_id in self._steps:
                raw_list = self._steps[run_id]
                steps = [AgentStepRecord(**s) for s in raw_list if s.get("user_id") == user_id]
                steps.sort(key=lambda s: s.step_index)
                if steps:
                    return steps

        # Check Supabase
        if supabase_manager.is_connected:
            try:
                table = supabase_manager.table("agent_steps")
                if table:
                    res = table.select("*").eq("agent_run_id", run_id).eq("user_id", user_id).order("step_index").execute()
                    if res.data:
                        supa_steps = [AgentStepRecord(**row) for row in res.data]
                        with self._lock:
                            self._steps[run_id] = res.data
                        return supa_steps
            except Exception as e:
                logger.debug(f"Error querying Supabase agent_steps: {e}")

        return []

    def get_step(self, run_id: str, step_id: str, user_id: str) -> Optional[AgentStepRecord]:
        """Retrieves an individual step by step_id and verified user_id."""
        with self._lock:
            if run_id in self._steps:
                for s in self._steps[run_id]:
                    if s.get("step_id") == step_id and s.get("user_id") == user_id:
                        return AgentStepRecord(**s)

        if supabase_manager.is_connected:
            try:
                table = supabase_manager.table("agent_steps")
                if table:
                    res = table.select("*").eq("agent_run_id", run_id).eq("step_id", step_id).eq("user_id", user_id).execute()
                    if res.data and len(res.data) > 0:
                        return AgentStepRecord(**res.data[0])
            except Exception as e:
                logger.debug(f"Error querying Supabase single agent_step: {e}")

        return None

    def update_step(self, run_id: str, step_id: str, user_id: str, updates: Dict[str, Any]) -> Optional[AgentStepRecord]:
        """Updates an individual step record."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        updates["updated_at"] = now_iso

        with self._lock:
            target = None
            if run_id in self._steps:
                for s in self._steps[run_id]:
                    if s.get("step_id") == step_id and s.get("user_id") == user_id:
                        for k, v in updates.items():
                            if hasattr(v, "value"):
                                s[k] = v.value
                            else:
                                s[k] = v
                        target = AgentStepRecord(**s)
                        break

        # Update Supabase
        if supabase_manager.is_connected:
            try:
                table = supabase_manager.table("agent_steps")
                if table:
                    db_payload = {}
                    for k, v in updates.items():
                        if hasattr(v, "value"):
                            db_payload[k] = v.value
                        else:
                            db_payload[k] = v
                    table.update(db_payload).eq("agent_run_id", run_id).eq("step_id", step_id).eq("user_id", user_id).execute()
            except Exception as e:
                logger.debug(f"Error updating Supabase agent_steps: {e}")

        return target

    # ── AGENT EVENT METHODS ──────────────────────────────────────────────────

    def record_event(
        self,
        run_id: str,
        user_id: str,
        event_type: str,
        step_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Records an execution event for auditability and observability. Zero secrets stored."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        event_dict = {
            "agent_run_id": run_id,
            "user_id": user_id,
            "step_id": step_id,
            "event_type": str(event_type),
            "metadata": metadata or {},
            "created_at": now_iso,
        }

        with self._lock:
            if run_id not in self._events:
                self._events[run_id] = []
            self._events[run_id].append(event_dict)

        if supabase_manager.is_connected:
            try:
                table = supabase_manager.table("agent_events")
                if table:
                    table.insert(event_dict).execute()
            except Exception as e:
                logger.debug(f"Error writing agent_event to Supabase: {e}")

        return event_dict

    def get_events(self, run_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Retrieves events for an agent run strictly scoped to user_id."""
        with self._lock:
            if run_id in self._events:
                return [e for e in self._events[run_id] if e.get("user_id") == user_id]

        if supabase_manager.is_connected:
            try:
                table = supabase_manager.table("agent_events")
                if table:
                    res = table.select("*").eq("agent_run_id", run_id).eq("user_id", user_id).order("created_at").execute()
                    if res.data:
                        with self._lock:
                            self._events[run_id] = res.data
                        return res.data
            except Exception as e:
                logger.debug(f"Error querying Supabase agent_events: {e}")

        return []


# Global singleton repository
agent_repository = AgentRepository()
