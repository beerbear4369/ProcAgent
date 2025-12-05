"""
ProcAgent Core - Claude Agent SDK Integration with MCP Tools

Uses ClaudeSDKClient for multi-turn conversations with ProMax MCP tools.
"""

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    SystemMessage,
    TextBlock,
    ToolUseBlock,
    ResultMessage,
)

from ..config import get_settings
from ..logging_config import get_logger
from ..mcp.promax_server import create_promax_mcp_server, ALLOWED_TOOLS, get_promax_state
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


# =============================================================================
# System Prompt
# =============================================================================

SYSTEM_PROMPT = """You are ProcAgent, an AI copilot for chemical process simulation using ProMax.

## Your Role
Help engineers create and run process simulations in ProMax.

## Available Tools (via MCP)
### Connection & Project
- connect_promax: Initialize ProMax connection (MUST call FIRST)
- create_project: Create a new ProMax project with flowsheet
- open_project: Open an existing .pmx file
- save_project: Save project to .pmx file
- close_project: Close the current project

### Components & Streams
- add_components: Add chemical components to environment
- create_stream: Create process streams at (x, y) position in mm
- set_stream_properties: Set temperature (°C), pressure (kPa), molar flow (kmol/hr)
- set_stream_composition: Set mole fractions (MUST sum to 1.0)
- flash_stream: Flash stream to equilibrium (call after setting T/P/composition)
- get_stream_results: Get stream calculation results
- list_streams: List all streams in flowsheet

### Blocks (Unit Operations)
- create_block: Create unit operation (separator, staged_column, mixer, pump, compressor, heat_exchanger, valve)
- connect_stream: Connect stream to block inlet/outlet via connection points
- list_blocks: List all blocks in flowsheet

### Simulation
- run_simulation: Run the flowsheet solver

## Canvas Layout (A4 Landscape)
The ProMax flowsheet canvas is 297mm wide x 210mm tall:
- **x-axis**: 0 (left) to 297 (right) mm
- **y-axis**: 0 (bottom) to 210 (top) mm
- **Grid spacing**: 3.175mm

### Recommended Stream Positioning
- Feed streams: x=30-60mm (left region), y=80-180mm
- Product streams: x=240-280mm (right region), y=80-180mm
- Intermediate streams: x=100-200mm (center), y varies
- Space streams 20-30mm apart vertically

## Block Connection Points
When connecting streams to blocks:
- **Separator (2-phase vertical)**: 1=left/feed, 2=top/vapor, 3=bottom/liquid
- **Staged Column (Amine Treater)**: 1=top-center, 2=bottom-center, 3=top-left, 4=top-right, 5=bottom-left, 6=bottom-right
- Use is_inlet=true for feed streams, is_inlet=false for outlet streams

## Important Rules
1. ALWAYS call connect_promax FIRST before any ProMax operation
2. Composition mole fractions MUST sum to 1.0
3. ALWAYS flash streams after setting composition
4. Use with_gui=true (default) to see visual shapes in Visio
5. You maintain conversation history - refer back to previous messages
6. Position streams logically on canvas - feeds on left, products on right
7. Create blocks in the center region (x=100-200mm) between feed and product streams
"""


# =============================================================================
# Main Agent Core Class
# =============================================================================

class ProcAgentCore:
    """
    Core orchestrator using Claude Agent SDK with ClaudeSDKClient.
    Maintains session history and provides ProMax MCP tools.
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

        # Create MCP server
        self._promax_server = create_promax_mcp_server()

        # SDK client options with MCP
        self.options = ClaudeAgentOptions(
            system_prompt=SYSTEM_PROMPT,
            max_turns=20,
            mcp_servers={"promax": self._promax_server},
            allowed_tools=ALLOWED_TOOLS,
            permission_mode="bypassPermissions",  # Auto-approve MCP tools
        )

        # Client instance (created on first message)
        self._client: Optional[ClaudeSDKClient] = None
        self._client_started = False

        logger.info(f"ProcAgentCore initialized for session {session_id} with ProMax MCP")

    async def _ensure_client(self) -> ClaudeSDKClient:
        """Ensure client is created and started."""
        if self._client is None:
            self._client = ClaudeSDKClient(options=self.options)

        if not self._client_started:
            await self._client.__aenter__()
            self._client_started = True
            logger.info(f"ClaudeSDKClient started for session {self.session_id}")

        return self._client

    async def process_message(
        self,
        message: ChatMessage,
    ) -> AsyncIterator[AgentResponse]:
        """
        Process a user message with streaming.
        Uses ClaudeSDKClient to maintain conversation history.
        """
        prompt = message.message

        if message.stream_data:
            prompt = f"Stream data:\n```json\n{json.dumps(message.stream_data, indent=2)}\n```\n\n{prompt}"

        try:
            client = await self._ensure_client()

            # DEBUG: Log the prompt being sent
            logger.debug(f"[PROMPT] {prompt[:500]}{'...' if len(prompt) > 500 else ''}")

            await client.query(prompt)

            async for msg in client.receive_response():
                # DEBUG: Log raw message type
                logger.debug(f"[MSG] {type(msg).__name__}: {str(msg)[:200]}")

                if isinstance(msg, SystemMessage):
                    logger.info(f"SDK session: {msg.data.get('session_id', 'unknown')}")
                    logger.debug(f"[SYSTEM] {msg.data}")
                    yield AgentResponse(
                        type=ResponseType.STATUS,
                        status=f"Connected to Claude ({msg.data.get('model', 'unknown')})"
                    )
                elif isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            logger.debug(f"[TEXT] {block.text[:200]}{'...' if len(block.text) > 200 else ''}")
                            yield AgentResponse(
                                type=ResponseType.TEXT,
                                content=block.text
                            )
                        elif isinstance(block, ToolUseBlock):
                            logger.debug(f"[TOOL_USE] {block.name}: {json.dumps(block.input)}")
                            yield AgentResponse(
                                type=ResponseType.TOOL_USE,
                                tool_info=ToolUseInfo(
                                    tool_name=block.name,
                                    tool_input=block.input,
                                    tool_id=block.id
                                )
                            )
                elif isinstance(msg, ResultMessage):
                    logger.debug(f"[RESULT] duration_ms={getattr(msg, 'duration_ms', 0)}")
                    yield AgentResponse(
                        type=ResponseType.RESULTS,
                        results=ResultsInfo(
                            parameters=[
                                {"name": "duration_ms", "target": 0, "actual": getattr(msg, 'duration_ms', 0), "unit": "ms", "passed": True},
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
        """Clean up resources and close SDK client."""
        logger.info(f"Cleaning up session {self.session_id}")

        # Close ProMax project via state singleton
        try:
            state = get_promax_state()
            if state.project:
                state.project.Close()
            state.reset()
        except Exception as e:
            logger.warning(f"ProMax cleanup error: {e}")

        # Close SDK client
        if self._client and self._client_started:
            try:
                await self._client.__aexit__(None, None, None)
                logger.info(f"ClaudeSDKClient closed for session {self.session_id}")
            except Exception as e:
                logger.warning(f"Client cleanup error: {e}")
            finally:
                self._client = None
                self._client_started = False
