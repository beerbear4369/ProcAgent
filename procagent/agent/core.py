"""
ProcAgent Core - Claude Agent SDK Integration (Minimal, No MCP)

Simplified version without custom MCP servers for testing.
"""

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    SystemMessage,
    TextBlock,
    ToolUseBlock,
    ResultMessage,
)

from ..config import get_settings
from ..logging_config import get_logger
from ..models import (
    AgentResponse,
    ChatMessage,
    ResponseType,
    ResultsInfo,
    ToolUseInfo,
    PerformanceTarget,
    SimulationResult,
    ResultsComparison,
    TargetAssessment,
)

logger = get_logger("agent.core")


# Simple system prompt for testing
SYSTEM_PROMPT = """You are ProcAgent, an AI copilot for chemical process simulation.

Be helpful and concise. When asked about ProMax or simulations, explain that
custom tools are being configured and will be available soon.
"""


class ProcAgentCore:
    """
    Core orchestrator using Claude Agent SDK with streaming.
    Minimal version without custom MCP servers.
    """

    def __init__(
        self,
        session_id: str,
        working_dir: Optional[Path] = None,
    ):
        self.session_id = session_id
        self.working_dir = working_dir or Path("./projects")
        self.settings = get_settings()
        self.targets: List[PerformanceTarget] = []

        logger.info(f"ProcAgentCore initialized for session {session_id}")

    async def process_message(
        self,
        message: ChatMessage,
    ) -> AsyncIterator[AgentResponse]:
        """
        Process a user message with streaming using Claude Agent SDK.
        """
        prompt = message.message

        if message.stream_data:
            prompt = f"Stream data:\n```json\n{json.dumps(message.stream_data, indent=2)}\n```\n\n{prompt}"

        # Simple options without MCP
        options = ClaudeAgentOptions(
            system_prompt=SYSTEM_PROMPT,
            max_turns=3,
        )

        try:
            async for msg in query(prompt=prompt, options=options):
                if isinstance(msg, SystemMessage):
                    logger.info(f"Session started: {msg.data.get('session_id', 'unknown')}")
                    yield AgentResponse(
                        type=ResponseType.STATUS,
                        status=f"Connected to Claude ({msg.data.get('model', 'unknown')})"
                    )
                elif isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            yield AgentResponse(
                                type=ResponseType.TEXT,
                                content=block.text
                            )
                        elif isinstance(block, ToolUseBlock):
                            yield AgentResponse(
                                type=ResponseType.TOOL_USE,
                                tool_info=ToolUseInfo(
                                    tool_name=block.name,
                                    tool_input=block.input,
                                    tool_id=block.id
                                )
                            )
                elif isinstance(msg, ResultMessage):
                    yield AgentResponse(
                        type=ResponseType.RESULTS,
                        results=ResultsInfo(
                            parameters=[
                                {"name": "duration_ms", "target": 0, "actual": getattr(msg, 'duration_ms', 0), "unit": "ms", "passed": True},
                                {"name": "cost_usd", "target": 0, "actual": getattr(msg, 'cost_usd', 0), "unit": "USD", "passed": True},
                            ],
                            overall_pass=True
                        )
                    )

        except Exception as e:
            logger.error(f"Agent error: {e}", exc_info=True)
            yield AgentResponse(
                type=ResponseType.ERROR,
                content=f"Error: {str(e)}"
            )

    def set_performance_targets(self, targets: List[PerformanceTarget]) -> None:
        self.targets = targets

    def compare_results(self, results: SimulationResult) -> ResultsComparison:
        if not self.targets:
            return ResultsComparison(assessments=[], overall_pass=True, summary="No targets")

        assessments = []
        for target in self.targets:
            actual = results.result_values.get(target.parameter, 0)
            deviation = actual - target.target_value
            passed = abs(deviation) <= target.tolerance
            assessments.append(TargetAssessment(
                target=target, actual_value=actual, passed=passed, deviation=deviation
            ))

        passed_count = sum(1 for a in assessments if a.passed)
        return ResultsComparison(
            assessments=assessments,
            overall_pass=all(a.passed for a in assessments),
            summary=f"{passed_count}/{len(assessments)} targets met"
        )

    async def cleanup(self) -> None:
        logger.info(f"Cleaning up session {self.session_id}")
