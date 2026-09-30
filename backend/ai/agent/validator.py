"""
Agent Plan Validator.
Enforces strict security, structural integrity, role-based tool authorization,
and dependency graph cycle prevention before any step is permitted to execute.
"""

from typing import Dict, Any, List, Set, Optional
from core.logger import logger
from ai.agent.models import AgentPlan, StepPlan, StepType
from ai.agent.errors import AgentPlanInvalidError
from ai.agent.config import agent_config
from ai.tools.registry import tool_registry, ToolRegistry


class AgentPlanValidator:
    """
    Validates Agent Plans before persistence and execution.
    Guarantees:
    - Step count limits
    - Valid step types
    - Tool authorization & existence in ToolRegistry
    - Role restrictions (Admin cannot be bypassed)
    - Valid dependencies & strict DAG cycle detection
    - Input structure validity
    """

    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.tool_registry = registry or tool_registry

    def validate_plan(
        self,
        plan: AgentPlan,
        user_id: str = "",
        user_role: str = "user",
        max_steps: Optional[int] = None,
    ) -> None:
        """
        Validates the entire plan. Raises AgentPlanInvalidError on any violation.
        """
        effective_max_steps = max_steps or agent_config.max_steps

        # 1. Step Count Limit
        if not plan.steps or len(plan.steps) == 0:
            raise AgentPlanInvalidError("Plan must contain at least one step.")

        if len(plan.steps) > effective_max_steps:
            raise AgentPlanInvalidError(
                f"Plan step count ({len(plan.steps)}) exceeds maximum permitted limit ({effective_max_steps})."
            )

        # 2. Duplicate Step IDs
        seen_step_ids: Set[str] = set()
        for idx, step in enumerate(plan.steps):
            if not step.step_id or not str(step.step_id).strip():
                raise AgentPlanInvalidError(f"Step at index {idx} has an empty or invalid step_id.")
            
            clean_id = str(step.step_id).strip()
            if clean_id in seen_step_ids:
                raise AgentPlanInvalidError(f"Duplicate step_id '{clean_id}' detected in plan.")
            seen_step_ids.add(clean_id)

        # 3. Tool Authorization, Step Types, and Inputs
        is_authenticated = bool(user_id and str(user_id).strip())
        role = user_role or "user"

        for idx, step in enumerate(plan.steps):
            # Input validation
            if not isinstance(step.input, dict):
                raise AgentPlanInvalidError(f"Step '{step.step_id}' input must be a dictionary.")

            # Step Type verification
            if not isinstance(step.step_type, StepType):
                try:
                    step.step_type = StepType(str(step.step_type))
                except ValueError:
                    raise AgentPlanInvalidError(f"Step '{step.step_id}' has an invalid step_type '{step.step_type}'.")

            # Tool Call validation
            if step.step_type == StepType.TOOL_CALL:
                if not step.tool_name or not str(step.tool_name).strip():
                    raise AgentPlanInvalidError(f"Tool step '{step.step_id}' is missing required 'tool_name'.")

                tool_name = str(step.tool_name).strip()
                tool = self.tool_registry.get(tool_name)

                # Tool existence
                if not tool:
                    raise AgentPlanInvalidError(f"Tool '{tool_name}' requested in step '{step.step_id}' is not registered.")

                # Tool enabled
                if not tool.enabled:
                    raise AgentPlanInvalidError(f"Tool '{tool_name}' requested in step '{step.step_id}' is currently disabled.")

                # Tool authentication
                if tool.requires_authentication and not is_authenticated:
                    raise AgentPlanInvalidError(
                        f"Tool '{tool_name}' in step '{step.step_id}' requires authentication, but user is not authenticated."
                    )

                # Role-based authorization (Strict: normal user cannot execute admin tools)
                if role not in tool.allowed_roles:
                    raise AgentPlanInvalidError(
                        f"Role '{role}' is not authorized to plan or execute tool '{tool_name}'. Allowed roles: {tool.allowed_roles}"
                    )

        # 4. Dependency Validation & Cycle Detection
        self._validate_dependencies(plan.steps, seen_step_ids)

    def _validate_dependencies(self, steps: List[StepPlan], valid_step_ids: Set[str]):
        """
        Validates step dependencies and ensures graph is a Directed Acyclic Graph (DAG).
        """
        adj_list: Dict[str, List[str]] = {s.step_id: [] for s in steps}
        step_position: Dict[str, int] = {s.step_id: idx for idx, s in enumerate(steps)}

        for step in steps:
            for dep in step.depends_on:
                dep_id = str(dep).strip()
                
                # Check dependency exists
                if dep_id not in valid_step_ids:
                    raise AgentPlanInvalidError(
                        f"Step '{step.step_id}' depends on non-existent step '{dep_id}'."
                    )

                # Self-dependency check
                if dep_id == step.step_id:
                    raise AgentPlanInvalidError(
                        f"Step '{step.step_id}' cannot depend on itself."
                    )

                # Forward dependency check (cannot depend on downstream step in sequential mode)
                if step_position[dep_id] > step_position[step.step_id]:
                    raise AgentPlanInvalidError(
                        f"Step '{step.step_id}' cannot depend on future step '{dep_id}'."
                    )

                adj_list[step.step_id].append(dep_id)

        # 5. Cycle Detection using Depth-First Search (DFS)
        # States: 0 = unvisited, 1 = visiting (in current recursion stack), 2 = visited
        visited: Dict[str, int] = {s.step_id: 0 for s in steps}

        def dfs(node: str, path: List[str]) -> None:
            visited[node] = 1
            for neighbor in adj_list.get(node, []):
                if visited[neighbor] == 1:
                    cycle = " -> ".join(path + [neighbor])
                    raise AgentPlanInvalidError(f"Circular dependency detected: {cycle}")
                elif visited[neighbor] == 0:
                    dfs(neighbor, path + [neighbor])
            visited[node] = 2

        for step in steps:
            if visited[step.step_id] == 0:
                dfs(step.step_id, [step.step_id])


# Global singleton validator
agent_plan_validator = AgentPlanValidator()
