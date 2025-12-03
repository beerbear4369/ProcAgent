"""
ProcAgent Core - Claude Agent SDK Orchestrator

Main orchestrator that coordinates Claude Agent SDK, ProMax MCP tools,
and Computer Use fallback for process simulation tasks.
"""

import asyncio
import base64
import json
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

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
    SimulationStatus,
    ResultsComparison,
    TargetAssessment,
    AdjustmentSuggestion,
)

logger = get_logger("agent.core")


# System prompt for ProMax operations
SYSTEM_PROMPT = """You are ProcAgent, an AI copilot for chemical process simulation using ProMax.

## Your Role
Help junior chemical engineers create and run process simulations in ProMax.
You have access to two types of tools:

### Primary Tools (ProMax COM API)
Use these MCP tools for standard operations:
- mcp__promax__connect_promax: Initialize ProMax connection
- mcp__promax__create_project: Create a new ProMax project with flowsheet
- mcp__promax__add_components: Add chemical components to the environment
- mcp__promax__create_block: Create equipment blocks (AmineTreater, Separator, etc.)
- mcp__promax__create_stream: Create process streams
- mcp__promax__connect_stream: Connect streams to block inlet/outlet ports
- mcp__promax__set_stream_properties: Set T, P, flow rate
- mcp__promax__set_stream_composition: Set component mole fractions (must sum to 1.0)
- mcp__promax__flash_stream: Flash a stream to establish equilibrium
- mcp__promax__run_simulation: Execute the simulation solver
- mcp__promax__get_results: Retrieve simulation results
- mcp__promax__save_project: Save the project file

### Fallback Tools (Computer Use)
Only use these when COM API tools cannot accomplish a task:
- mcp__computer__screenshot: Capture current ProMax screen
- mcp__computer__click: Click at screen coordinates
- mcp__computer__type: Type text at current cursor
- mcp__computer__key: Press keyboard keys

## Workflow for Amine Treater Demo

1. **Analyze Input**: If user uploads a PFD, analyze it to identify the highlighted block
2. **Connect to ProMax**: Use connect_promax (with_gui=True)
3. **Create Project**: Use create_project with flowsheet name
4. **Add Components**: Add all required chemical species (MDEA, H2S, CO2, Water, Methane, etc.)
5. **Create Block**: Create the Amine Treater (Staged Column) block
6. **Create Streams**: Create inlet (Sour Offgas, Lean Amine) and outlet streams
7. **Connect Streams**: Connect streams to appropriate block ports
8. **Set Properties**: Set stream T, P, flow rate
9. **Set Compositions**: Set mole fractions (must sum to 1.0)
10. **Flash Streams**: Flash inlet streams to establish equilibrium
11. **Run Simulation**: Execute solver and check convergence
12. **Get Results**: Retrieve outlet stream properties
13. **Compare to Targets**: Check if H2S <= 100 ppm, loading <= 0.45

## Important Rules

1. ALWAYS use COM API tools first - they are faster and more reliable
2. Only use Computer Use tools when COM API fails or for operations not supported by COM
3. When setting stream compositions, values MUST sum to 1.0
4. ALWAYS flash streams after setting composition
5. ALWAYS check simulation convergence before reading results
6. Explain what you are doing to help the user learn

## Performance Targets (Amine Treater Demo)
- Offgas H2S: <= 100 ppm(mol)
- Rich Amine Loading: <= 0.45 mol H2S/mol amine
"""


class ProcAgentCore:
    """
    Core orchestrator for ProcAgent using Claude Agent SDK.

    Manages the interaction between the chat interface, Claude LLM,
    and the ProMax/Computer Use MCP tools.
    """

    def __init__(
        self,
        session_id: str,
        working_dir: Optional[Path] = None,
    ):
        """
        Initialize ProcAgentCore.

        Args:
            session_id: Unique session identifier
            working_dir: Working directory for project files
        """
        self.session_id = session_id
        self.working_dir = working_dir or Path("./projects")
        self.settings = get_settings()

        # Conversation history
        self.messages: List[Dict[str, Any]] = []

        # Performance targets for comparison
        self.targets: List[PerformanceTarget] = []

        # Import tools
        from ..mcp.promax_server import create_promax_tools
        from ..cua.computer_use import create_computer_use_tools

        self.promax_tools = create_promax_tools()
        self.computer_tools = create_computer_use_tools()

        logger.info(f"ProcAgentCore initialized for session {session_id}")

    def set_performance_targets(self, targets: List[PerformanceTarget]) -> None:
        """Set performance targets for result comparison."""
        self.targets = targets
        logger.info(f"Set {len(targets)} performance targets")

    async def process_message(
        self,
        message: ChatMessage,
    ) -> AsyncIterator[AgentResponse]:
        """
        Process a user message and yield responses.

        Args:
            message: User chat message with optional PFD image

        Yields:
            AgentResponse objects for streaming to client
        """
        # Build user message content
        content_parts = []

        # Add image if present
        if message.pfd_image:
            content_parts.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": message.pfd_image,
                }
            })

        # Add stream data if present
        if message.stream_data:
            content_parts.append({
                "type": "text",
                "text": f"Stream data provided:\n```json\n{json.dumps(message.stream_data, indent=2)}\n```"
            })

        # Add user message
        content_parts.append({
            "type": "text",
            "text": message.message
        })

        # Add to conversation history
        self.messages.append({
            "role": "user",
            "content": content_parts if len(content_parts) > 1 else message.message
        })

        # Yield status update
        yield AgentResponse(
            type=ResponseType.STATUS,
            status="Processing your request..."
        )

        try:
            # Call Claude API (simplified - real implementation uses Claude Agent SDK)
            response = await self._call_claude()

            # Process response
            for item in response:
                if item["type"] == "text":
                    yield AgentResponse(
                        type=ResponseType.TEXT,
                        content=item["content"]
                    )
                elif item["type"] == "tool_use":
                    yield AgentResponse(
                        type=ResponseType.TOOL_USE,
                        tool_info=ToolUseInfo(
                            tool_name=item["tool_name"],
                            tool_input=item["tool_input"]
                        )
                    )

                    # Execute tool
                    result = await self._execute_tool(
                        item["tool_name"],
                        item["tool_input"]
                    )

                    yield AgentResponse(
                        type=ResponseType.STATUS,
                        status=f"Tool result: {str(result)[:100]}..."
                    )

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            yield AgentResponse(
                type=ResponseType.ERROR,
                content=f"Error: {str(e)}"
            )

    async def _call_claude(self) -> List[Dict[str, Any]]:
        """
        Call Claude API with current conversation.

        This is a simplified implementation. The full implementation
        would use the Claude Agent SDK's ClaudeSDKClient.

        Returns:
            List of response items (text, tool_use)
        """
        # Placeholder - actual implementation uses Claude Agent SDK
        # For now, return a simple acknowledgment
        return [{
            "type": "text",
            "content": "I understand your request. Let me help you with the ProMax simulation."
        }]

    async def _execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any]
    ) -> Any:
        """
        Execute a tool by name.

        Args:
            tool_name: Full tool name (e.g., "mcp__promax__create_project")
            tool_input: Tool input parameters

        Returns:
            Tool execution result
        """
        # Parse tool name
        parts = tool_name.split("__")
        if len(parts) < 3:
            return f"Invalid tool name: {tool_name}"

        namespace = parts[1]  # promax or computer
        action = parts[2]     # specific action

        # Get tool function
        if namespace == "promax":
            if action in self.promax_tools:
                return await self.promax_tools[action](**tool_input)
            return f"Unknown ProMax tool: {action}"
        elif namespace == "computer":
            if action in self.computer_tools:
                return await self.computer_tools[action](**tool_input)
            return f"Unknown Computer Use tool: {action}"
        else:
            return f"Unknown tool namespace: {namespace}"

    def compare_results(
        self,
        results: SimulationResult
    ) -> ResultsComparison:
        """
        Compare simulation results against performance targets.

        Args:
            results: Simulation results

        Returns:
            ResultsComparison with assessments
        """
        if not self.targets:
            return ResultsComparison(
                assessments=[],
                overall_pass=True,
                summary="No targets defined for comparison"
            )

        assessments = []
        all_passed = True

        for target in self.targets:
            actual = results.result_values.get(target.parameter)
            if actual is None:
                assessments.append(TargetAssessment(
                    target=target,
                    actual_value=0.0,
                    passed=False,
                    deviation=0.0,
                ))
                all_passed = False
                continue

            # Evaluate based on comparison type
            deviation = actual - target.target_value
            if target.comparison == "le":
                passed = actual <= target.target_value
            elif target.comparison == "ge":
                passed = actual >= target.target_value
            else:  # eq
                passed = abs(deviation) <= target.tolerance

            deviation_percent = None
            if target.target_value != 0:
                deviation_percent = (deviation / target.target_value) * 100

            assessments.append(TargetAssessment(
                target=target,
                actual_value=actual,
                passed=passed,
                deviation=deviation,
                deviation_percent=deviation_percent,
            ))

            if not passed:
                all_passed = False

        # Generate summary
        passed_count = sum(1 for a in assessments if a.passed)
        total_count = len(assessments)
        if all_passed:
            summary = f"All {total_count} targets met!"
        else:
            summary = f"{passed_count}/{total_count} targets met"

        return ResultsComparison(
            assessments=assessments,
            overall_pass=all_passed,
            summary=summary
        )

    def suggest_adjustments(
        self,
        comparison: ResultsComparison
    ) -> List[AdjustmentSuggestion]:
        """
        Generate adjustment suggestions for failed targets.

        Args:
            comparison: Results comparison

        Returns:
            List of adjustment suggestions
        """
        suggestions = []

        for assessment in comparison.assessments:
            if assessment.passed:
                continue

            target = assessment.target
            actual = assessment.actual_value

            # Generate suggestion based on target type
            if "H2S" in target.parameter:
                if actual > target.target_value:
                    suggestions.append(AdjustmentSuggestion(
                        parameter="Lean Amine Flow Rate",
                        current_value=0.0,  # Would be populated from results
                        suggested_value=0.0,  # Calculated
                        unit="kmol/hr",
                        rationale="Increase amine circulation to absorb more H2S",
                        expected_impact="Lower outlet H2S concentration"
                    ))
            elif "Loading" in target.parameter:
                if actual > target.target_value:
                    suggestions.append(AdjustmentSuggestion(
                        parameter="Lean Amine Loading",
                        current_value=actual,
                        suggested_value=target.target_value * 0.8,
                        unit="mol/mol",
                        rationale="Use leaner amine to increase absorption capacity",
                        expected_impact="Lower rich amine loading"
                    ))

        return suggestions

    async def cleanup(self) -> None:
        """Clean up resources."""
        logger.info(f"Cleaning up session {self.session_id}")
        # Close ProMax project if open
        try:
            await self.promax_tools["close_project"]()
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
