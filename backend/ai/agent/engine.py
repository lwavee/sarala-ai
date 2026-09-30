"""
Agent Planning & Execution Engine Facade.
Provides the single unified entry point for FastAPI routes and Chat orchestration.
"""

from typing import Dict, Any, List, Optional
from ai.agent.models import (
    AgentRunRecord,
    AgentStepRecord,
    AgentRunDetailResponse,
    AgentRunStatus,
    ExecutionMode,
)
from ai.agent.errors import AgentNotFoundError, AgentNotOwnedError, AgentDisabledError
from ai.agent.config import agent_config
from ai.agent.repository import agent_repository, AgentRepository
from ai.agent.planner import agent_planner, AgentPlanner
from ai.agent.manager import agent_execution_manager, AgentExecutionManager


class AgentEngine:
    """
    Unified high-level facade for the AI Agent Planning & Execution Layer.
    """

    def __init__(
        self,
        repository: Optional[AgentRepository] = None,
        planner: Optional[AgentPlanner] = None,
        manager: Optional[AgentExecutionManager] = None,
    ):
        self.repo = repository or agent_repository
        self.planner = planner or agent_planner
        self.manager = manager or agent_execution_manager

    def check_enabled(self) -> None:
        """Verifies that the agent engine is enabled in configuration."""
        if not agent_config.enabled:
            raise AgentDisabledError("Agent engine is currently disabled.")

    def needs_agent_execution(self, prompt: str) -> bool:
        """Determines whether a user prompt requires multi-step agent planning."""
        if not agent_config.enabled:
            return False
        return self.planner.needs_agent_execution(prompt)

    def create_run(
        self,
        user_id: str,
        role: str,
        goal: str,
        conversation_id: Optional[str] = None,
        initial_message_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        max_steps: Optional[int] = None,
        execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL,
        auto_execute: bool = True,
    ) -> AgentRunRecord:
        """Creates a new agent run with plan and step records."""
        self.check_enabled()
        return self.manager.create_run(
            user_id=user_id,
            role=role,
            goal=goal,
            conversation_id=conversation_id,
            initial_message_id=initial_message_id,
            idempotency_key=idempotency_key,
            max_steps=max_steps,
            execution_mode=execution_mode,
            auto_execute=auto_execute,
        )

    def get_run_detail(self, user_id: str, run_id: str) -> AgentRunDetailResponse:
        """Retrieves complete agent run details including steps and events with strict user scoping."""
        run = self.repo.get_run(user_id, run_id)
        if not run:
            unscoped = self.repo.get_run_unscoped(run_id)
            if unscoped:
                raise AgentNotOwnedError(f"Access denied: Agent run '{run_id}' belongs to another user.")
            raise AgentNotFoundError(f"Agent run '{run_id}' not found.")

        steps = self.repo.get_steps(run_id, user_id)
        events = self.repo.get_events(run_id, user_id)
        return AgentRunDetailResponse(run=run, steps=steps, events=events)

    def list_runs(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> List[AgentRunRecord]:
        """Lists agent runs scoped to user_id."""
        return self.repo.list_runs(
            user_id=user_id,
            limit=limit,
            offset=offset,
            status=status,
            conversation_id=conversation_id,
        )

    def pause_run(self, run_id: str, user_id: str) -> AgentRunRecord:
        """Pauses execution of an agent run."""
        self.check_enabled()
        return self.manager.pause_run(run_id, user_id)

    def resume_run(self, run_id: str, user_id: str, role: str) -> AgentRunRecord:
        """Resumes a paused agent run."""
        self.check_enabled()
        return self.manager.resume_run(run_id, user_id, role)

    def cancel_run(self, run_id: str, user_id: str) -> AgentRunRecord:
        """Cancels an active or paused agent run."""
        return self.manager.cancel_run(run_id, user_id)

    def approve_step(
        self,
        run_id: str,
        user_id: str,
        role: str,
        step_id: Optional[str] = None,
    ) -> AgentRunRecord:
        """Approves a pending approval gate and resumes execution."""
        self.check_enabled()
        return self.manager.approve_step(run_id, user_id, role, step_id=step_id)

    def reject_step(
        self,
        run_id: str,
        user_id: str,
        step_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> AgentRunRecord:
        """Rejects a pending step, cancelling the agent run."""
        return self.manager.reject_step(run_id, user_id, step_id=step_id, reason=reason)


# Global singleton agent engine
agent_engine = AgentEngine()
