"""
Domain Models, Enums, and Schemas for AI Agent Planning & Execution Engine.
Strictly defines controlled states, safe step types, and execution structures.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import datetime


class AgentRunStatus(str, Enum):
    QUEUED = "queued"
    PLANNING = "planning"
    PLANNED = "planned"
    VALIDATING = "validating"
    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class StepType(str, Enum):
    REASONING = "reasoning"
    TOOL_CALL = "tool_call"
    VALIDATION = "validation"
    TRANSFORMATION = "transformation"
    FINAL_RESPONSE = "final_response"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class ExecutionMode(str, Enum):
    SEQUENTIAL = "sequential"
    DEPENDENCY_GRAPH = "dependency_graph"


class AgentEventType(str, Enum):
    AGENT_CREATED = "agent_created"
    PLAN_CREATED = "plan_created"
    PLAN_VALIDATED = "plan_validated"
    STEP_STARTED = "step_started"
    TOOL_CALLED = "tool_called"
    TOOL_COMPLETED = "tool_completed"
    STEP_FAILED = "step_failed"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RECEIVED = "approval_received"
    RUN_PAUSED = "run_paused"
    RUN_RESUMED = "run_resumed"
    RUN_CANCELLED = "run_cancelled"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"


# ── Planning Models ──────────────────────────────────────────────────────────

class StepPlan(BaseModel):
    """Declarative specification of a single planned step."""
    step_id: str
    title: str
    description: str = ""
    step_type: StepType = StepType.TOOL_CALL
    tool_name: Optional[str] = None
    input: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)
    requires_approval: bool = False


class AgentPlan(BaseModel):
    """Complete structured plan generated for a user goal."""
    goal: str
    steps: List[StepPlan] = Field(default_factory=list)
    estimated_steps: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── Persistent Record Models ─────────────────────────────────────────────────

class AgentStepRecord(BaseModel):
    """Persistent database representation of an individual execution step."""
    id: str
    agent_run_id: str
    user_id: str
    step_index: int
    step_id: str
    title: str
    description: str = ""
    step_type: StepType = StepType.TOOL_CALL
    status: StepStatus = StepStatus.PENDING
    tool_name: Optional[str] = None
    input: Dict[str, Any] = Field(default_factory=dict)
    output: Optional[Dict[str, Any]] = None
    depends_on: List[str] = Field(default_factory=list)
    requires_approval: bool = False
    retry_count: int = 0
    max_retries: int = 2
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "agent_run_id": self.agent_run_id,
            "user_id": self.user_id,
            "step_index": self.step_index,
            "step_id": self.step_id,
            "title": self.title,
            "description": self.description,
            "step_type": self.step_type.value if isinstance(self.step_type, StepType) else str(self.step_type),
            "status": self.status.value if isinstance(self.status, StepStatus) else str(self.status),
            "tool_name": self.tool_name,
            "input": self.input,
            "output": self.output,
            "depends_on": self.depends_on,
            "requires_approval": self.requires_approval,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "error": self.error,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class AgentRunRecord(BaseModel):
    """Persistent database representation of an agent run."""
    id: str
    user_id: str
    conversation_id: Optional[str] = None
    initial_message_id: Optional[str] = None
    goal: str
    status: AgentRunStatus = AgentRunStatus.QUEUED
    execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    current_step: int = 0
    total_steps: int = 0
    max_steps: int = 10
    requires_approval: bool = False
    waiting_for_approval: bool = False
    failure_reason: Optional[str] = None
    final_result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "initial_message_id": self.initial_message_id,
            "goal": self.goal,
            "status": self.status.value if isinstance(self.status, AgentRunStatus) else str(self.status),
            "execution_mode": self.execution_mode.value if isinstance(self.execution_mode, ExecutionMode) else str(self.execution_mode),
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "max_steps": self.max_steps,
            "requires_approval": self.requires_approval,
            "waiting_for_approval": self.waiting_for_approval,
            "failure_reason": self.failure_reason,
            "final_result": self.final_result,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


# ── API Request & Response Schemas ───────────────────────────────────────────

class AgentRunCreateRequest(BaseModel):
    goal: str
    conversation_id: Optional[str] = None
    initial_message_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    max_steps: Optional[int] = None
    auto_execute: bool = True
    execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL


class AgentApprovalRequest(BaseModel):
    step_id: Optional[str] = None
    reason: Optional[str] = None


class AgentRejectionRequest(BaseModel):
    step_id: Optional[str] = None
    reason: Optional[str] = None


class AgentRunDetailResponse(BaseModel):
    run: AgentRunRecord
    steps: List[AgentStepRecord] = Field(default_factory=list)
    events: List[Dict[str, Any]] = Field(default_factory=list)
