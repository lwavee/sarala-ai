"""
AI Agent Planner.
Analyzes user intent, decides whether multi-step agent execution is required,
and creates structured, validated execution plans using AIOrchestrator and ToolRegistry.
"""

import json
import re
from typing import Dict, Any, List, Optional
from core.logger import logger
from ai.agent.models import AgentPlan, StepPlan, StepType
from ai.agent.errors import AgentPlanInvalidError
from ai.agent.validator import agent_plan_validator, AgentPlanValidator
from ai.agent.config import agent_config
from ai.models import AIRequest
from ai.orchestrator import ai_orchestrator, AIOrchestrator
from ai.tools.registry import tool_registry, ToolRegistry
from ai.tools.models import ToolActionType, RiskLevel


# Patterns indicating multi-step complex workflows
_MULTI_STEP_PATTERNS = [
    r"\b(analyze|check|search|fetch|find)\b.*\b(and|then)\b.*\b(calculate|compute|solve)\b",
    r"\b(calculate|compute)\b.*\b(and|then)\b.*\b(save|store|remember|record)\b",
    r"\b(retrieve|get|read)\b.*\b(and|then)\b.*\b(update|modify|delete|change)\b",
    r"\b(first|step 1|step one)\b.*\b(then|next|step 2|step two)\b",
    r"\b(multi-?step|workflow|pipeline|plan and execute)\b",
    r"\b(summarize and save|calculate and remember|find my .+ and calculate)\b",
]

# Patterns representing simple direct questions that should bypass agent engine
_SIMPLE_CHAT_PATTERNS = [
    r"^(what is|who is|explain|define|tell me about|how to|write a|kya hai|batao)\b",
    r"^(hi|hello|namaste|hey|kem cho|kaisa hai|good morning|good evening)\b",
]


class AgentPlanner:
    """
    Central Agent Planner.
    Coordinates intent discrimination and structured plan generation.
    """

    def __init__(
        self,
        orchestrator: Optional[AIOrchestrator] = None,
        registry: Optional[ToolRegistry] = None,
        validator: Optional[AgentPlanValidator] = None,
    ):
        self.orchestrator = orchestrator or ai_orchestrator
        self.tool_registry = registry or tool_registry
        self.validator = validator or agent_plan_validator

    def needs_agent_execution(self, prompt: str) -> bool:
        """
        Determines whether the given prompt requires multi-step agent planning and execution.
        Guarantees that simple informational questions continue using standard chat flow.
        """
        if not prompt or not isinstance(prompt, str):
            return False

        clean = prompt.strip().lower()

        # Check explicit prefix override
        if clean.startswith("agent:") or clean.startswith("/agent") or clean.startswith("plan:"):
            return True

        # Simple direct questions bypass agent execution
        for pattern in _SIMPLE_CHAT_PATTERNS:
            if re.search(pattern, clean):
                # Unless explicitly asked for multi-step execution in the same sentence
                if not any(re.search(mp, clean) for mp in _MULTI_STEP_PATTERNS):
                    return False

        # Multi-step action indicators
        for pattern in _MULTI_STEP_PATTERNS:
            if re.search(pattern, clean):
                return True

        # Check clause complexity (e.g. multiple distinct action commands)
        action_verbs = ["search", "calculate", "summarize", "save", "delete", "update", "retrieve"]
        matched_actions = [v for v in action_verbs if f" {v} " in f" {clean} "]
        if len(matched_actions) >= 2:
            return True

        return False

    def create_plan(
        self,
        goal: str,
        user_id: str = "",
        user_role: str = "user",
        conversation_context: Optional[str] = None,
        max_steps: Optional[int] = None,
    ) -> AgentPlan:
        """
        Generates a validated AgentPlan for the given user goal.
        """
        clean_goal = goal.strip()
        # Strip optional command prefixes
        if clean_goal.lower().startswith("agent:"):
            clean_goal = clean_goal[6:].strip()
        elif clean_goal.lower().startswith("/agent"):
            clean_goal = clean_goal[6:].strip()

        # Retrieve available tools for this user identity
        is_authenticated = bool(user_id and str(user_id).strip())
        available_tools = self.tool_registry.list_tools(
            user_role=user_role,
            authenticated=is_authenticated,
            enabled_only=True,
        )

        tool_catalog = [
            {
                "name": t.name,
                "description": t.description,
                "requires_confirmation": t.requires_confirmation,
                "risk_level": t.risk_level.value,
                "input_schema": t.input_schema,
            }
            for t in available_tools
        ]

        # 1. Attempt AI-assisted plan generation
        try:
            plan = self._generate_ai_plan(clean_goal, tool_catalog, conversation_context)
            # Post-process approval flags based on actual tool definitions
            self._enrich_approval_requirements(plan)
            # Validate plan
            self.validator.validate_plan(
                plan,
                user_id=user_id,
                user_role=user_role,
                max_steps=max_steps or agent_config.max_steps,
            )
            return plan
        except Exception as e:
            logger.warning(f"AI plan generation failed or rejected ({e}). Falling back to deterministic plan.")

        # 2. Deterministic Fallback Plan
        fallback_plan = self._generate_fallback_plan(clean_goal, available_tools)
        self._enrich_approval_requirements(fallback_plan)
        self.validator.validate_plan(
            fallback_plan,
            user_id=user_id,
            user_role=user_role,
            max_steps=max_steps or agent_config.max_steps,
        )
        return fallback_plan

    def _generate_ai_plan(
        self,
        goal: str,
        tool_catalog: List[Dict[str, Any]],
        conversation_context: Optional[str] = None,
    ) -> AgentPlan:
        """Invokes AIOrchestrator to produce structured JSON plan."""
        system_prompt = (
            "You are the Sarala AI Agent Planning Engine. "
            "Your job is to break down the user's high-level goal into a controlled sequence of atomic execution steps. "
            "STRICT RULES:\n"
            "1. Output ONLY valid, parseable JSON conforming exactly to the requested schema.\n"
            "2. Never use tools that are not listed in the available tools catalog.\n"
            "3. Dependencies must reference earlier step_ids (e.g. 'depends_on': ['step_1']).\n"
            "4. Never create circular or forward dependencies.\n"
            "5. Mark destructive or state-changing operations as 'requires_approval': true.\n"
            "6. Keep step descriptions concise and operational. Never include chain-of-thought reasoning.\n"
        )

        tools_desc = json.dumps(tool_catalog, indent=2)
        user_prompt = (
            f"Goal: {goal}\n\n"
            f"Available Tools:\n{tools_desc}\n\n"
            "Respond with JSON format:\n"
            "{\n"
            '  "goal": "' + goal + '",\n'
            '  "steps": [\n'
            '    {\n'
            '      "step_id": "step_1",\n'
            '      "title": "Short title",\n'
            '      "description": "Safe operational description",\n'
            '      "step_type": "tool_call",\n'
            '      "tool_name": "tool_name_here",\n'
            '      "input": {"param": "value"},\n'
            '      "depends_on": [],\n'
            '      "requires_approval": false\n'
            '    }\n'
            '  ]\n'
            "}"
        )

        target_model = self.orchestrator.select_model(None, task_type="planning")
        ai_req = AIRequest(
            model=target_model.model_name,
            provider=target_model.provider,
            messages=[{"role": "user", "content": user_prompt}],
            system_context=system_prompt,
            temperature=0.1,  # Low temperature for deterministic structural adherence
            max_output_tokens=1000,
            metadata={"task_type": "planning"},
        )

        resp = self.orchestrator.generate(ai_req)
        raw_text = resp.content.strip()

        # Extract JSON from code blocks if present
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].split("```")[0].strip()

        parsed = json.loads(raw_text)
        steps_data = parsed.get("steps", [])
        if not steps_data:
            raise AgentPlanInvalidError("AI returned an empty steps array.")

        step_plans: List[StepPlan] = []
        for s in steps_data:
            step_plans.append(StepPlan(
                step_id=str(s.get("step_id", f"step_{len(step_plans)+1}")),
                title=str(s.get("title", "Execute Step")),
                description=str(s.get("description", "")),
                step_type=StepType(s.get("step_type", "tool_call")),
                tool_name=s.get("tool_name"),
                input=s.get("input", {}),
                depends_on=s.get("depends_on", []),
                requires_approval=bool(s.get("requires_approval", False)),
            ))

        return AgentPlan(
            goal=goal,
            steps=step_plans,
            estimated_steps=len(step_plans),
            metadata={"generated_by": "ai_orchestrator", "model": resp.model},
        )

    def _generate_fallback_plan(self, goal: str, available_tools: list) -> AgentPlan:
        """
        Creates a safe, deterministic plan when the AI model is offline or produces malformed output.
        Inspects keywords to construct a sequential workflow.
        """
        tool_names = {t.name: t for t in available_tools}
        clean = goal.lower()
        steps: List[StepPlan] = []

        # 1. Search / Recall step
        if any(w in clean for w in ["saved", "information", "memory", "recall", "find", "search"]):
            if "search_user_memories" in tool_names:
                steps.append(StepPlan(
                    step_id="step_1",
                    title="Retrieve relevant saved information",
                    description="Search user memory for requested data.",
                    step_type=StepType.TOOL_CALL,
                    tool_name="search_user_memories",
                    input={"query": goal},
                    depends_on=[],
                    requires_approval=False,
                ))

        # 2. Calculation step
        if any(w in clean for w in ["calculate", "math", "values", "sum", "average", "compute"]):
            dep = [steps[-1].step_id] if steps else []
            step_num = len(steps) + 1
            # Extract expression if available
            expr_match = re.search(r"calculate\s+([0-9\+\-\*\/\^\(\)\.\s]+)", clean)
            expr = expr_match.group(1).strip() if expr_match else "0"
            if "calculator" in tool_names:
                steps.append(StepPlan(
                    step_id=f"step_{step_num}",
                    title="Perform mathematical calculation",
                    description="Evaluate mathematical expression safely via AST calculator.",
                    step_type=StepType.TOOL_CALL,
                    tool_name="calculator",
                    input={"expression": expr},
                    depends_on=dep,
                    requires_approval=False,
                ))

        # 3. Save / Update / Delete step
        if any(w in clean for w in ["save", "remember", "store", "record"]):
            dep = [steps[-1].step_id] if steps else []
            step_num = len(steps) + 1
            if "create_user_memory" in tool_names:
                steps.append(StepPlan(
                    step_id=f"step_{step_num}",
                    title="Save final result to user memory",
                    description="Store calculated result or summary in durable memory.",
                    step_type=StepType.TOOL_CALL,
                    tool_name="create_user_memory",
                    input={"key": "agent_result", "value": "Execution completed successfully."},
                    depends_on=dep,
                    requires_approval=False,
                ))
        elif any(w in clean for w in ["delete", "remove", "erase", "forget"]):
            dep = [steps[-1].step_id] if steps else []
            step_num = len(steps) + 1
            if "delete_user_memory" in tool_names:
                steps.append(StepPlan(
                    step_id=f"step_{step_num}",
                    title="Delete stored user memory",
                    description="Remove target memory key upon confirmation.",
                    step_type=StepType.TOOL_CALL,
                    tool_name="delete_user_memory",
                    input={"key": "target_memory"},
                    depends_on=dep,
                    requires_approval=True,  # Approval gate required
                ))

        # Default fallback if no specific keywords matched
        if not steps:
            # Simple single or two-step fallback
            if "calculator" in tool_names and any(c in clean for c in "0123456789+-*/"):
                steps.append(StepPlan(
                    step_id="step_1",
                    title="Calculate expression",
                    description="Evaluate mathematical calculation.",
                    step_type=StepType.TOOL_CALL,
                    tool_name="calculator",
                    input={"expression": "1 + 1"},
                    depends_on=[],
                    requires_approval=False,
                ))
            elif "search_user_memories" in tool_names:
                steps.append(StepPlan(
                    step_id="step_1",
                    title="Search memory",
                    description="Search user memories.",
                    step_type=StepType.TOOL_CALL,
                    tool_name="search_user_memories",
                    input={"query": goal},
                    depends_on=[],
                    requires_approval=False,
                ))
            else:
                steps.append(StepPlan(
                    step_id="step_1",
                    title="Analyze task",
                    description="Analyze task requirements.",
                    step_type=StepType.REASONING,
                    depends_on=[],
                    requires_approval=False,
                ))

        return AgentPlan(
            goal=goal,
            steps=steps,
            estimated_steps=len(steps),
            metadata={"generated_by": "deterministic_fallback"},
        )

    def _enrich_approval_requirements(self, plan: AgentPlan) -> None:
        """Enforces requires_approval on steps whose tools demand explicit human confirmation."""
        for step in plan.steps:
            if step.step_type == StepType.TOOL_CALL and step.tool_name:
                tool = self.tool_registry.get(step.tool_name)
                if tool:
                    if tool.requires_confirmation or tool.risk_level == RiskLevel.HIGH or tool.action_type == ToolActionType.WRITE:
                        step.requires_approval = True


# Global singleton planner
agent_planner = AgentPlanner()
