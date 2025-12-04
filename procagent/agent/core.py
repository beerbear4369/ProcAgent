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
    tool,
    create_sdk_mcp_server,
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


# =============================================================================
# System Prompt
# =============================================================================

SYSTEM_PROMPT = """You are ProcAgent, an AI copilot for chemical process simulation using ProMax.

## Your Role
Help engineers create and run process simulations in ProMax.

## Available Tools (via MCP)
- connect_promax: Initialize ProMax connection (call this FIRST)
- create_project: Create a new ProMax project
- add_components: Add chemical components
- create_stream: Create process streams
- set_stream_properties: Set T, P, flow rate
- set_stream_composition: Set mole fractions (MUST sum to 1.0)
- flash_stream: Flash stream to equilibrium
- get_stream_results: Get stream calculation results

## Important Rules
1. ALWAYS call connect_promax FIRST before any ProMax operation
2. Composition mole fractions MUST sum to 1.0
3. ALWAYS flash streams after setting composition
4. You maintain conversation history - refer back to previous messages
"""


# =============================================================================
# ProMax COM State (Global)
# =============================================================================

_promax_app = None
_promax_project = None
_promax_flowsheet = None


# =============================================================================
# MCP Tools using @tool decorator
# =============================================================================

@tool(
    "connect_promax",
    "Initialize connection to ProMax. MUST be called first before any other operation.",
    {"with_gui": bool}
)
async def connect_promax_tool(args: dict) -> dict:
    """Connect to ProMax COM server."""
    global _promax_app
    try:
        import win32com.client
        _promax_app = win32com.client.Dispatch("ProMax.ProMax")
        version = f"{_promax_app.Version.Major}.{_promax_app.Version.Minor}"
        return {"content": [{"type": "text", "text": f"Connected to ProMax version {version}"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}]}


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
            return {"content": [{"type": "text", "text": "Error: Call connect_promax first"}]}
        flowsheet_name = args.get("flowsheet_name", "Main")
        _promax_project = _promax_app.New()  # Correct method: New() not NewProject()
        _promax_flowsheet = _promax_project.Flowsheets.Add(flowsheet_name)  # Correct: Flowsheets.Add()
        return {"content": [{"type": "text", "text": f"Created project with flowsheet '{flowsheet_name}'"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}]}


@tool(
    "add_components",
    "Add chemical components to the flowsheet",
    {"components": list}
)
async def add_components_tool(args: dict) -> dict:
    """Add components to environment."""
    global _promax_flowsheet
    try:
        if not _promax_flowsheet:
            return {"content": [{"type": "text", "text": "Error: Create project first"}]}
        components = args.get("components", [])
        env = _promax_flowsheet.Environment
        for comp in components:
            env.Components.Add(comp)  # Correct: Components.Add() not AddComponent()
        return {"content": [{"type": "text", "text": f"Added: {', '.join(components)}"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}]}


@tool(
    "create_stream",
    "Create a process stream",
    {"name": str}
)
async def create_stream_tool(args: dict) -> dict:
    """Create a stream."""
    global _promax_flowsheet
    try:
        if not _promax_flowsheet:
            return {"content": [{"type": "text", "text": "Error: Create project first"}]}
        name = args.get("name")
        _promax_flowsheet.CreatePStream(name)  # Correct: CreatePStream() not AddStream()
        return {"content": [{"type": "text", "text": f"Created stream '{name}'"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}]}


@tool(
    "set_stream_properties",
    "Set stream temperature, pressure, and flow",
    {"stream_name": str, "temperature_c": float, "pressure_kpa": float, "molar_flow_kmol_hr": float}
)
async def set_stream_properties_tool(args: dict) -> dict:
    """Set stream properties using Phases/Properties collections."""
    global _promax_flowsheet
    try:
        if not _promax_flowsheet:
            return {"content": [{"type": "text", "text": "Error: Create project first"}]}
        name = args.get("stream_name")
        stream = _promax_flowsheet.PStreams(name)  # Correct: PStreams not Streams.Item
        phase = stream.Phases(5)  # pmxTotalPhase = 5
        props = []
        if "temperature_c" in args and args["temperature_c"] is not None:
            phase.Properties(0).Value = args["temperature_c"] + 273.15  # pmxPhaseTemperature (K)
            props.append(f"T={args['temperature_c']}C")
        if "pressure_kpa" in args and args["pressure_kpa"] is not None:
            phase.Properties(1).Value = args["pressure_kpa"] * 1000  # pmxPhasePressure (Pa)
            props.append(f"P={args['pressure_kpa']}kPa")
        if "molar_flow_kmol_hr" in args and args["molar_flow_kmol_hr"] is not None:
            # Convert kmol/hr to mol/s: kmol/hr * 1000 / 3600
            mol_per_s = args["molar_flow_kmol_hr"] * 1000 / 3600
            phase.Properties(16).Value = mol_per_s  # pmxPhaseMolarFlow (mol/s)
            props.append(f"Flow={args['molar_flow_kmol_hr']}kmol/hr")
        return {"content": [{"type": "text", "text": f"Set {name}: {', '.join(props)}"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}]}


@tool(
    "set_stream_composition",
    "Set mole fractions (must sum to 1.0)",
    {"stream_name": str, "composition": dict}
)
async def set_stream_composition_tool(args: dict) -> dict:
    """Set stream composition using Composition.SIValues."""
    global _promax_flowsheet
    try:
        if not _promax_flowsheet:
            return {"content": [{"type": "text", "text": "Error: Create project first"}]}
        name = args.get("stream_name")
        composition = args.get("composition", {})
        total = sum(composition.values())
        if abs(total - 1.0) > 0.001:
            return {"content": [{"type": "text", "text": f"Error: Sum={total}, must be 1.0"}]}

        # Get environment to know component order
        env = _promax_flowsheet.Environment
        n_comps = env.Components.Count

        # Build composition array matching environment component order
        comp_values = [0.0] * n_comps
        for i in range(n_comps):
            comp_name = env.Components(i).Species.SpeciesName.Name
            if comp_name in composition:
                comp_values[i] = composition[comp_name]

        # Set composition on total phase using SIValues
        stream = _promax_flowsheet.PStreams(name)
        phase = stream.Phases(5)  # pmxTotalPhase = 5
        comp_obj = phase.Composition(6)  # pmxMolarFracBasis = 6
        comp_obj.SIValues = tuple(comp_values)

        return {"content": [{"type": "text", "text": f"Set composition for '{name}': {composition}"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}]}


@tool(
    "flash_stream",
    "Flash stream to equilibrium",
    {"stream_name": str}
)
async def flash_stream_tool(args: dict) -> dict:
    """Flash a stream."""
    global _promax_flowsheet
    try:
        if not _promax_flowsheet:
            return {"content": [{"type": "text", "text": "Error: Create project first"}]}
        name = args.get("stream_name")
        stream = _promax_flowsheet.PStreams(name)  # Correct: PStreams not Streams.Item
        stream.Flash()
        return {"content": [{"type": "text", "text": f"Flashed '{name}'"}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}]}


@tool(
    "get_stream_results",
    "Get stream calculation results",
    {"stream_name": str}
)
async def get_stream_results_tool(args: dict) -> dict:
    """Get stream results using Phases/Properties collections."""
    global _promax_flowsheet
    try:
        if not _promax_flowsheet:
            return {"content": [{"type": "text", "text": "Error: Create project first"}]}
        name = args.get("stream_name")
        stream = _promax_flowsheet.PStreams(name)  # Correct: PStreams not Streams.Item
        phase = stream.Phases(5)  # pmxTotalPhase = 5

        # Read properties (converting from SI units)
        temp_k = phase.Properties(0).Value  # pmxPhaseTemperature (K)
        pressure_pa = phase.Properties(1).Value  # pmxPhasePressure (Pa)
        molar_flow_mol_s = phase.Properties(16).Value  # pmxPhaseMolarFlow (mol/s)
        vapor_frac = phase.Properties(2).Value  # pmxPhaseMoleFracVapor

        results = {
            "temperature_c": temp_k - 273.15 if temp_k else None,
            "pressure_kpa": pressure_pa / 1000 if pressure_pa else None,
            "molar_flow_kmol_hr": molar_flow_mol_s * 3600 / 1000 if molar_flow_mol_s else None,
            "vapor_fraction": vapor_frac,
        }
        return {"content": [{"type": "text", "text": json.dumps(results, indent=2)}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}]}


# =============================================================================
# Create MCP Server
# =============================================================================

def create_promax_mcp_server():
    """Create the ProMax MCP server with all tools."""
    return create_sdk_mcp_server(
        name="promax",
        tools=[
            connect_promax_tool,
            create_project_tool,
            add_components_tool,
            create_stream_tool,
            set_stream_properties_tool,
            set_stream_composition_tool,
            flash_stream_tool,
            get_stream_results_tool,
        ]
    )


# List of allowed MCP tools
ALLOWED_TOOLS = [
    "mcp__promax__connect_promax",
    "mcp__promax__create_project",
    "mcp__promax__add_components",
    "mcp__promax__create_stream",
    "mcp__promax__set_stream_properties",
    "mcp__promax__set_stream_composition",
    "mcp__promax__flash_stream",
    "mcp__promax__get_stream_results",
]


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
        global _promax_project, _promax_flowsheet
        logger.info(f"Cleaning up session {self.session_id}")

        # Close ProMax project
        try:
            if _promax_project:
                _promax_project.Close()
            _promax_project = None
            _promax_flowsheet = None
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
