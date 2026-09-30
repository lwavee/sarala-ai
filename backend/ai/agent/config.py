"""
Agent Planning & Execution Engine Configuration.
Centralized environment-backed operational limits and thresholds.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentConfig:
    enabled: bool = os.getenv("AGENT_ENABLED", "true").lower() in ("true", "1", "yes")
    max_steps: int = int(os.getenv("AGENT_MAX_STEPS", "10"))
    max_tool_calls: int = int(os.getenv("AGENT_MAX_TOOL_CALLS", "15"))
    max_runtime_seconds: float = float(os.getenv("AGENT_MAX_RUNTIME_SECONDS", "120.0"))
    max_retries: int = int(os.getenv("AGENT_MAX_RETRIES", "2"))
    max_result_size: int = int(os.getenv("AGENT_MAX_RESULT_SIZE", "16384"))
    default_execution_mode: str = os.getenv("AGENT_DEFAULT_MODE", "sequential")
    retry_delay_seconds: float = float(os.getenv("AGENT_RETRY_DELAY_SECONDS", "1.0"))


# Singleton configuration
agent_config = AgentConfig()
