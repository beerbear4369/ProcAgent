"""
ProcAgent Core - Claude Agent SDK Integration

Main orchestrator using the official Claude Agent SDK with streaming,
MCP server integration, and proper tool execution.
"""

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    tool,
    create_sdk_mcp_server,
    AssistantMessage,
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

## Available Tools

### ProMax COM API Tools (Primary - use these first)
- connect_promax: Initialize ProMax connection (call this FIRST)
- create_project: Create a new ProMax project with flowsheet
- add_components: Add chemical components to the environment
- create_block: Create equipment blocks (AmineTreater, Separator, etc.)
- create_stream: Create process streams
- connect_stream: Connect streams to block ports
- set_stream_properties: Set T, P, flow rate
- set_stream_composition: Set mole fractions (MUST sum to 1.0)
- flash_stream: Flash stream to establish equilibrium
- run_simulation: Execute the solver
- get_results: Retrieve simulation results
- save_project: Save the project file

### Computer Use Tools (Fallback - only when COM fails)
- screenshot: Capture ProMax screen
- click: Click at coordinates
- type_text: Type text
- key: Press keyboard keys

## Workflow for Amine Treater Demo

1. connect_promax(with_gui=true) - Initialize ProMax
2. create_project(flowsheet_name="AmineTreater") - Create project
3. add_components(["MDEA", "Water", "Hydrogen Sulfide", "Carbon Dioxide", "Methane", "Ethane"])
4. create_block(block_type="AmineTreater", name="301-E")
5. create_stream for each inlet/outlet
6. connect_stream to block ports
7. set_stream_properties (T, P, flow)
8. set_stream_composition (mole fractions sum to 1.0)
9. flash_stream for each inlet
10. run_simulation
11. get_results
12. Compare to targets: H2S <= 100 ppm, Loading <= 0.45

## Important Rules
1. ALWAYS call connect_promax FIRST before any other ProMax operation
2. Composition mole fractions MUST sum to 1.0
3. ALWAYS flash streams after setting composition
4. Check simulation convergence before reading results
5. Explain what you're doing to help users learn
"""


# ============================================================================
# ProMax State Management
# ============================================================================

# Global ProMax COM object reference
_promax_app = None
_promax_project = None
_promax_flowsheet = None


# ============================================================================
# Raw Tool Functions (for direct testing)
# ============================================================================

async def _connect_promax(with_gui: bool = True) -> dict:
    """Connect to ProMax COM server (raw function)."""
    global _promax_app
    try:
        import win32com.client

        if with_gui:
            _promax_app = win32com.client.Dispatch("ProMax.ProMax")
        else:
            _promax_app = win32com.client.Dispatch("ProMax.ProMax")

        version = f"{_promax_app.Version.Major}.{_promax_app.Version.Minor}"
        return {"content": [{"type": "text", "text": f"Connected to ProMax version {version}"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error connecting to ProMax: {str(e)}"}]}


# ============================================================================
# ProMax Tools using @tool decorator
# ============================================================================

@tool(
    "connect_promax",
    "Initialize connection to ProMax. MUST be called first before any other ProMax operation.",
    {"with_gui": bool}
)
async def connect_promax_tool(args: dict) -> dict:
    """Connect to ProMax COM server."""
    return await _connect_promax(args.get("with_gui", True))


@tool(
    "create_project",
    "Create a new ProMax project with a flowsheet",
    {"flowsheet_name": str}
)
async def create_project_tool(args: dict) -> dict:
    """Create a new ProMax project."""
    global _promax_app, _promax_project, _promax_flowsheet
    try:
        if not _promax_app:
            return {"content": [{"type": "text", "text": "Error: ProMax not connected. Call connect_promax first."}]}

        flowsheet_name = args.get("flowsheet_name", "Main")
        _promax_project = _promax_app.NewProject()
        _promax_flowsheet = _promax_project.AddFlowsheet(flowsheet_name)

        return {"content": [{"type": "text", "text": f"Created project with flowsheet '{flowsheet_name}'"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error creating project: {str(e)}"}]}


@tool(
    "add_components",
    "Add chemical components to the flowsheet environment",
    {"components": list}
)
async def add_components_tool(args: dict) -> dict:
    """Add components to the environment."""
    global _promax_flowsheet
    try:
        if not _promax_flowsheet:
            return {"content": [{"type": "text", "text": "Error: No flowsheet. Call create_project first."}]}

        components = args.get("components", [])
        env = _promax_flowsheet.Environment
        added = []

        for comp_name in components:
            env.AddComponent(comp_name)
            added.append(comp_name)

        return {"content": [{"type": "text", "text": f"Added components: {', '.join(added)}"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error adding components: {str(e)}"}]}


@tool(
    "create_block",
    "Create an equipment block in the flowsheet",
    {"block_type": str, "name": str, "x": float, "y": float}
)
async def create_block_tool(args: dict) -> dict:
    """Create an equipment block."""
    global _promax_flowsheet
    try:
        if not _promax_flowsheet:
            return {"content": [{"type": "text", "text": "Error: No flowsheet. Call create_project first."}]}

        block_type = args.get("block_type")
        name = args.get("name")
        x = args.get("x", 5.0)
        y = args.get("y", 5.0)

        # Map block types to ProMax block creation
        block_type_map = {
            "AmineTreater": "Distill",
            "Separator": "Separator",
            "HeatExchanger": "HeatExchanger",
            "Compressor": "Compressor",
            "Pump": "Pump",
            "Valve": "Valve",
            "Mixer": "Mixer",
            "Splitter": "Splitter",
        }

        promax_type = block_type_map.get(block_type, block_type)
        block = _promax_flowsheet.AddBlock(promax_type, name, x, y)

        return {"content": [{"type": "text", "text": f"Created {block_type} block '{name}'"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error creating block: {str(e)}"}]}


@tool(
    "create_stream",
    "Create a process stream in the flowsheet",
    {"name": str, "x": float, "y": float}
)
async def create_stream_tool(args: dict) -> dict:
    """Create a process stream."""
    global _promax_flowsheet
    try:
        if not _promax_flowsheet:
            return {"content": [{"type": "text", "text": "Error: No flowsheet. Call create_project first."}]}

        name = args.get("name")
        x = args.get("x", 0.0)
        y = args.get("y", 0.0)

        stream = _promax_flowsheet.AddStream(name, x, y)

        return {"content": [{"type": "text", "text": f"Created stream '{name}'"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error creating stream: {str(e)}"}]}


@tool(
    "connect_stream",
    "Connect a stream to a block port",
    {"stream_name": str, "block_name": str, "port_index": int, "is_inlet": bool}
)
async def connect_stream_tool(args: dict) -> dict:
    """Connect a stream to a block port."""
    global _promax_flowsheet
    try:
        if not _promax_flowsheet:
            return {"content": [{"type": "text", "text": "Error: No flowsheet. Call create_project first."}]}

        stream_name = args.get("stream_name")
        block_name = args.get("block_name")
        port_index = args.get("port_index")
        is_inlet = args.get("is_inlet", True)

        stream = _promax_flowsheet.Streams.Item(stream_name)
        block = _promax_flowsheet.Blocks.Item(block_name)

        if is_inlet:
            block.Inlets(port_index).Connect(stream)
        else:
            block.Outlets(port_index).Connect(stream)

        direction = "inlet" if is_inlet else "outlet"
        return {"content": [{"type": "text", "text": f"Connected stream '{stream_name}' to {direction} port {port_index} of '{block_name}'"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error connecting stream: {str(e)}"}]}


@tool(
    "set_stream_properties",
    "Set physical properties of a stream",
    {"stream_name": str, "temperature_c": float, "pressure_kpa": float, "molar_flow_kmol_hr": float, "mass_flow_kg_hr": float}
)
async def set_stream_properties_tool(args: dict) -> dict:
    """Set stream temperature, pressure, and flow."""
    global _promax_flowsheet
    try:
        if not _promax_flowsheet:
            return {"content": [{"type": "text", "text": "Error: No flowsheet. Call create_project first."}]}

        stream_name = args.get("stream_name")
        stream = _promax_flowsheet.Streams.Item(stream_name)

        props_set = []

        if "temperature_c" in args:
            temp_k = args["temperature_c"] + 273.15
            stream.Temperature = temp_k
            props_set.append(f"T={args['temperature_c']}°C")

        if "pressure_kpa" in args:
            pressure_pa = args["pressure_kpa"] * 1000
            stream.Pressure = pressure_pa
            props_set.append(f"P={args['pressure_kpa']} kPa")

        if "molar_flow_kmol_hr" in args:
            stream.MolarFlow = args["molar_flow_kmol_hr"]
            props_set.append(f"Flow={args['molar_flow_kmol_hr']} kmol/hr")

        if "mass_flow_kg_hr" in args:
            stream.MassFlow = args["mass_flow_kg_hr"]
            props_set.append(f"Flow={args['mass_flow_kg_hr']} kg/hr")

        return {"content": [{"type": "text", "text": f"Set properties for '{stream_name}': {', '.join(props_set)}"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error setting stream properties: {str(e)}"}]}


@tool(
    "set_stream_composition",
    "Set mole fraction composition of a stream. Values MUST sum to 1.0",
    {"stream_name": str, "composition": dict}
)
async def set_stream_composition_tool(args: dict) -> dict:
    """Set stream composition."""
    global _promax_flowsheet
    try:
        if not _promax_flowsheet:
            return {"content": [{"type": "text", "text": "Error: No flowsheet. Call create_project first."}]}

        stream_name = args.get("stream_name")
        composition = args.get("composition", {})

        # Validate sum
        total = sum(composition.values())
        if abs(total - 1.0) > 0.001:
            return {"content": [{"type": "text", "text": f"Error: Composition must sum to 1.0, got {total}"}]}

        stream = _promax_flowsheet.Streams.Item(stream_name)

        for comp_name, mole_frac in composition.items():
            stream.SetMoleFraction(comp_name, mole_frac)

        return {"content": [{"type": "text", "text": f"Set composition for '{stream_name}': {len(composition)} components"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error setting composition: {str(e)}"}]}


@tool(
    "flash_stream",
    "Flash a stream to establish thermodynamic equilibrium",
    {"stream_name": str}
)
async def flash_stream_tool(args: dict) -> dict:
    """Flash a stream."""
    global _promax_flowsheet
    try:
        if not _promax_flowsheet:
            return {"content": [{"type": "text", "text": "Error: No flowsheet. Call create_project first."}]}

        stream_name = args.get("stream_name")
        stream = _promax_flowsheet.Streams.Item(stream_name)
        stream.Flash()

        return {"content": [{"type": "text", "text": f"Flashed stream '{stream_name}'"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error flashing stream: {str(e)}"}]}


@tool(
    "run_simulation",
    "Run the flowsheet solver",
    {}
)
async def run_simulation_tool(args: dict) -> dict:
    """Run the simulation."""
    global _promax_flowsheet
    try:
        if not _promax_flowsheet:
            return {"content": [{"type": "text", "text": "Error: No flowsheet. Call create_project first."}]}

        result = _promax_flowsheet.Solve()

        if result >= 1:
            return {"content": [{"type": "text", "text": f"Simulation converged (status={result})"}]}
        elif result == 0:
            return {"content": [{"type": "text", "text": "Simulation did not converge. Check specifications."}]}
        else:
            return {"content": [{"type": "text", "text": f"Simulation error (status={result})"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error running simulation: {str(e)}"}]}


@tool(
    "get_results",
    "Get simulation results for specified streams",
    {"stream_names": list}
)
async def get_results_tool(args: dict) -> dict:
    """Get simulation results."""
    global _promax_flowsheet
    try:
        if not _promax_flowsheet:
            return {"content": [{"type": "text", "text": "Error: No flowsheet. Call create_project first."}]}

        stream_names = args.get("stream_names", [])
        results = {}

        for name in stream_names:
            stream = _promax_flowsheet.Streams.Item(name)
            results[name] = {
                "temperature_c": stream.Temperature - 273.15,
                "pressure_kpa": stream.Pressure / 1000,
                "molar_flow_kmol_hr": stream.MolarFlow,
            }

        return {"content": [{"type": "text", "text": json.dumps(results, indent=2)}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error getting results: {str(e)}"}]}


@tool(
    "save_project",
    "Save the ProMax project to a file",
    {"file_path": str}
)
async def save_project_tool(args: dict) -> dict:
    """Save the project."""
    global _promax_project
    try:
        if not _promax_project:
            return {"content": [{"type": "text", "text": "Error: No project. Call create_project first."}]}

        file_path = args.get("file_path")
        _promax_project.SaveAs(file_path)

        return {"content": [{"type": "text", "text": f"Project saved to '{file_path}'"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error saving project: {str(e)}"}]}


@tool(
    "close_project",
    "Close the current ProMax project",
    {}
)
async def close_project_tool(args: dict) -> dict:
    """Close the project."""
    global _promax_app, _promax_project, _promax_flowsheet
    try:
        if _promax_project:
            _promax_project.Close()

        _promax_project = None
        _promax_flowsheet = None

        return {"content": [{"type": "text", "text": "Project closed"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error closing project: {str(e)}"}]}


# ============================================================================
# Computer Use Tools
# ============================================================================

@tool(
    "screenshot",
    "Capture a screenshot of the screen",
    {}
)
async def screenshot_tool(args: dict) -> dict:
    """Capture screenshot."""
    try:
        import mss
        import base64
        from io import BytesIO

        with mss.mss() as sct:
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)

            # Convert to PNG bytes
            from PIL import Image
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            img_base64 = base64.b64encode(buffer.getvalue()).decode()

        return {"content": [
            {"type": "text", "text": "Screenshot captured"},
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_base64}}
        ]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error capturing screenshot: {str(e)}"}]}


@tool(
    "click",
    "Click at screen coordinates",
    {"x": int, "y": int, "button": str}
)
async def click_tool(args: dict) -> dict:
    """Click at coordinates."""
    try:
        import pyautogui

        x = args.get("x")
        y = args.get("y")
        button = args.get("button", "left")

        pyautogui.click(x, y, button=button)

        return {"content": [{"type": "text", "text": f"Clicked at ({x}, {y}) with {button} button"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error clicking: {str(e)}"}]}


@tool(
    "type_text",
    "Type text at current cursor position",
    {"text": str}
)
async def type_text_tool(args: dict) -> dict:
    """Type text."""
    try:
        import pyautogui

        text = args.get("text")
        pyautogui.write(text, interval=0.02)

        return {"content": [{"type": "text", "text": f"Typed: {text[:50]}..."}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error typing: {str(e)}"}]}


@tool(
    "key",
    "Press a keyboard key or combination",
    {"key": str}
)
async def key_tool(args: dict) -> dict:
    """Press keyboard key."""
    try:
        import pyautogui

        key = args.get("key")
        pyautogui.hotkey(*key.split("+"))

        return {"content": [{"type": "text", "text": f"Pressed: {key}"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error pressing key: {str(e)}"}]}


# ============================================================================
# MCP Server Creation
# ============================================================================

def create_promax_mcp_server():
    """Create the ProMax MCP server with all tools."""
    return create_sdk_mcp_server(
        name="promax",
        tools=[
            connect_promax_tool,
            create_project_tool,
            add_components_tool,
            create_block_tool,
            create_stream_tool,
            connect_stream_tool,
            set_stream_properties_tool,
            set_stream_composition_tool,
            flash_stream_tool,
            run_simulation_tool,
            get_results_tool,
            save_project_tool,
            close_project_tool,
        ]
    )


def create_computer_use_mcp_server():
    """Create the Computer Use MCP server."""
    return create_sdk_mcp_server(
        name="computer_use",
        tools=[
            screenshot_tool,
            click_tool,
            type_text_tool,
            key_tool,
        ]
    )


# ============================================================================
# Main Agent Core Class
# ============================================================================

class ProcAgentCore:
    """
    Core orchestrator using Claude Agent SDK with streaming.
    """

    def __init__(
        self,
        session_id: str,
        working_dir: Optional[Path] = None,
    ):
        self.session_id = session_id
        self.working_dir = working_dir or Path("./projects")
        self.settings = get_settings()

        # MCP servers
        self.promax_server = create_promax_mcp_server()
        self.computer_server = create_computer_use_mcp_server()

        # Performance targets
        self.targets: List[PerformanceTarget] = []

        # SDK client (created per conversation)
        self._client: Optional[ClaudeSDKClient] = None

        logger.info(f"ProcAgentCore initialized for session {session_id}")

    async def process_message(
        self,
        message: ChatMessage,
    ) -> AsyncIterator[AgentResponse]:
        """
        Process a user message with streaming using Claude Agent SDK.

        Args:
            message: User chat message with optional PFD image

        Yields:
            AgentResponse objects for streaming to client
        """
        # Build prompt
        prompt = message.message

        # Add context if present
        if message.stream_data:
            prompt = f"Stream data:\n```json\n{json.dumps(message.stream_data, indent=2)}\n```\n\n{prompt}"

        # Configure agent options
        options = ClaudeAgentOptions(
            system_prompt=SYSTEM_PROMPT,
            mcp_servers=[self.promax_server, self.computer_server],
            permission_mode="acceptEdits",
        )

        try:
            async with ClaudeSDKClient(options=options) as client:
                self._client = client

                # Send query
                await client.query(prompt)

                # Stream responses
                async for msg in client.receive_response():
                    if isinstance(msg, AssistantMessage):
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
                        # Final metrics
                        yield AgentResponse(
                            type=ResponseType.RESULTS,
                            results=ResultsInfo(
                                converged=True,
                                result_values={
                                    "duration_ms": msg.duration_ms if hasattr(msg, 'duration_ms') else 0,
                                    "cost_usd": msg.cost_usd if hasattr(msg, 'cost_usd') else 0,
                                }
                            )
                        )

        except Exception as e:
            logger.error(f"Agent error: {e}")
            yield AgentResponse(
                type=ResponseType.ERROR,
                content=f"Error: {str(e)}"
            )
        finally:
            self._client = None

    def set_performance_targets(self, targets: List[PerformanceTarget]) -> None:
        """Set performance targets for result comparison."""
        self.targets = targets

    def compare_results(self, results: SimulationResult) -> ResultsComparison:
        """Compare simulation results against targets."""
        if not self.targets:
            return ResultsComparison(
                assessments=[],
                overall_pass=True,
                summary="No targets defined"
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

            deviation = actual - target.target_value
            if target.comparison == "le":
                passed = actual <= target.target_value
            elif target.comparison == "ge":
                passed = actual >= target.target_value
            else:
                passed = abs(deviation) <= target.tolerance

            assessments.append(TargetAssessment(
                target=target,
                actual_value=actual,
                passed=passed,
                deviation=deviation,
            ))

            if not passed:
                all_passed = False

        passed_count = sum(1 for a in assessments if a.passed)
        summary = f"{passed_count}/{len(assessments)} targets met"

        return ResultsComparison(
            assessments=assessments,
            overall_pass=all_passed,
            summary=summary
        )

    async def cleanup(self) -> None:
        """Clean up resources."""
        logger.info(f"Cleaning up session {self.session_id}")
        try:
            await close_project_tool({})
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
