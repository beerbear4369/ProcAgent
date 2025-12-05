"""
ProMax MCP Server

Provides MCP tools for ProMax COM API operations including project management,
block creation, stream manipulation, and simulation execution.

This server is designed to be used as an in-process MCP server with the
Claude Agent SDK.
"""

import json
import platform
from typing import Any, Dict, List, Optional

from claude_agent_sdk import tool, create_sdk_mcp_server

from ..logging_config import get_logger

logger = get_logger("mcp.promax")

# Platform check
if platform.system() != "Windows":
    logger.warning(
        f"ProMax MCP Server requires Windows. Current: {platform.system()}"
    )


# ============================================================================
# Unit conversion constants
# ============================================================================

UNIT_CONVERSIONS = {
    "temperature": {
        "K": lambda x: x,
        "C": lambda x: x + 273.15,
        "F": lambda x: (x - 32) * 5 / 9 + 273.15,
        "R": lambda x: x * 5 / 9,
    },
    "pressure": {
        "Pa": lambda x: x,
        "kPa": lambda x: x * 1000,
        "bar": lambda x: x * 100000,
        "atm": lambda x: x * 101325,
        "psi": lambda x: x * 6894.76,
    },
    "flow": {
        "mol/s": lambda x: x,
        "kmol/hr": lambda x: x * 1000 / 3600,
        "kg/s": lambda x: x,
        "kg/hr": lambda x: x / 3600,
    },
}

# ProMax phase constants
PMX_TOTAL_PHASE = 5
PMX_MOLAR_FRAC_BASIS = 6

# Phase property indices (pmxPhasePropEnum)
PHASE_PROPS = {
    "temperature": 0,  # K
    "pressure": 1,     # Pa
    "molar_flow": 16,  # mol/s
    "mass_flow": 17,   # kg/s
}


def convert_units(value: float, unit: str, unit_type: str) -> float:
    """Convert value to SI units."""
    if unit_type not in UNIT_CONVERSIONS:
        raise ValueError(f"Unknown unit type: {unit_type}")
    if unit not in UNIT_CONVERSIONS[unit_type]:
        raise ValueError(f"Unknown {unit_type} unit: {unit}")
    return UNIT_CONVERSIONS[unit_type][unit](value)


# ============================================================================
# ProMax State Management
# ============================================================================

class ProMaxState:
    """Singleton state for ProMax COM session management."""

    _instance: Optional["ProMaxState"] = None

    def __new__(cls) -> "ProMaxState":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.pmx = None           # ProMax COM object
            self.project = None       # Current project
            self.flowsheet = None     # Current flowsheet
            self.visio = None         # Visio application
            self.vpage = None         # Visio page
            self.stencils: Dict[str, Any] = {}
            self.stream_shapes: Dict[str, Any] = {}
            self.block_shapes: Dict[str, Any] = {}
            self.with_gui = False
            self._initialized = True

    def reset(self) -> None:
        """Reset state for new session."""
        self.pmx = None
        self.project = None
        self.flowsheet = None
        self.visio = None
        self.vpage = None
        self.stencils.clear()
        self.stream_shapes.clear()
        self.block_shapes.clear()
        self.with_gui = False

    @property
    def is_connected(self) -> bool:
        """Check if connected to ProMax."""
        return self.pmx is not None

    @property
    def has_flowsheet(self) -> bool:
        """Check if a flowsheet is active."""
        return self.flowsheet is not None


# Global state instance
_state = ProMaxState()


def get_promax_state() -> ProMaxState:
    """Get the ProMax state instance."""
    return _state


def _result(text: str) -> dict:
    """Helper to create MCP tool result format."""
    return {"content": [{"type": "text", "text": text}]}


# ============================================================================
# MCP Tool Definitions using @tool decorator
# ============================================================================

@tool(
    "connect_promax",
    "Initialize connection to ProMax COM API. MUST be called first before any other ProMax operation.",
    {"with_gui": bool}
)
async def connect_promax_tool(args: dict) -> dict:
    """Connect to ProMax COM server."""
    state = get_promax_state()
    try:
        from win32com.client import gencache

        with_gui = args.get("with_gui", True)

        if with_gui:
            state.pmx = gencache.EnsureDispatch("ProMax.ProMaxOutOfProc")
            state.with_gui = True
        else:
            state.pmx = gencache.EnsureDispatch("ProMax.ProMax")
            state.with_gui = False

        version = f"{state.pmx.Version.Major}.{state.pmx.Version.Minor}"
        mode = "GUI" if with_gui else "background"
        logger.info(f"Connected to ProMax {version} ({mode} mode)")
        return _result(f"Connected to ProMax {version} ({mode} mode)")

    except Exception as e:
        logger.error(f"Failed to connect to ProMax: {e}")
        return _result(f"Error: Failed to connect to ProMax: {str(e)}")


@tool(
    "create_project",
    "Create a new ProMax project with a flowsheet",
    {"flowsheet_name": str}
)
async def create_project_tool(args: dict) -> dict:
    """Create a new ProMax project."""
    state = get_promax_state()

    if not state.is_connected:
        return _result("Error: Not connected to ProMax. Call connect_promax first.")

    try:
        flowsheet_name = args.get("flowsheet_name", "Main")
        state.project = state.pmx.New()
        state.flowsheet = state.project.Flowsheets.Add(flowsheet_name)

        if state.with_gui:
            state.visio = state.pmx.VisioApp
            state.vpage = state.flowsheet.VisioPage
            # Load stencils
            for i in range(1, state.visio.Documents.Count + 1):
                doc = state.visio.Documents(i)
                if doc.Type == 2:  # Stencil
                    state.stencils[doc.Name] = doc

        logger.info(f"Created project with flowsheet '{flowsheet_name}'")
        return _result(f"Created project with flowsheet '{flowsheet_name}'")

    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        return _result(f"Error: Failed to create project: {str(e)}")


@tool(
    "add_components",
    "Add chemical components to the flowsheet environment. Components must be added before setting stream compositions.",
    {"components": list}
)
async def add_components_tool(args: dict) -> dict:
    """Add components to environment."""
    state = get_promax_state()

    if not state.has_flowsheet:
        return _result("Error: No flowsheet. Create a project first.")

    try:
        components = args.get("components", [])

        # Normalize: if string, convert to list
        # Handle comma-separated string: "Hydrogen, Water, Methane"
        if isinstance(components, str):
            if ',' in components:
                components = [c.strip() for c in components.split(',')]
            else:
                components = [components]

        env = state.flowsheet.Environment
        added = []
        failed = []

        for comp in components:
            try:
                env.Components.Add(comp)
                added.append(comp)
            except Exception as e:
                failed.append(f"{comp}: {str(e)}")

        result = f"Added {len(added)} components: {', '.join(added)}"
        if failed:
            result += f"\nFailed: {'; '.join(failed)}"

        logger.info(result)
        return _result(result)

    except Exception as e:
        logger.error(f"Failed to add components: {e}")
        return _result(f"Error: Failed to add components: {str(e)}")


@tool(
    "create_stream",
    "Create a new process stream in the flowsheet",
    {"name": str, "x": float, "y": float}
)
async def create_stream_tool(args: dict) -> dict:
    """Create a process stream."""
    state = get_promax_state()

    if not state.has_flowsheet:
        return _result("Error: No flowsheet. Create a project first.")

    try:
        name = args.get("name")
        x = args.get("x", 2.0)
        y = args.get("y", 5.0)

        if state.with_gui and state.vpage:
            stencil_name = "Streams.vss"
            if stencil_name not in state.stencils:
                return _result(f"Error: Stencil '{stencil_name}' not loaded.")

            master = state.stencils[stencil_name].Masters("Process Stream")
            shape = state.vpage.Drop(master, x, y)
            shape.Name = name
            state.stream_shapes[name] = shape

            logger.info(f"Created stream '{name}' at ({x}, {y})")
            return _result(f"Created stream '{name}' with Visio shape at ({x}, {y})")
        else:
            state.flowsheet.CreatePStream(name)
            logger.info(f"Created stream '{name}' (data only)")
            return _result(f"Created stream '{name}' (data only)")

    except Exception as e:
        logger.error(f"Failed to create stream: {e}")
        return _result(f"Error: Failed to create stream: {str(e)}")


@tool(
    "set_stream_properties",
    "Set physical properties of a process stream (temperature, pressure, flow rate)",
    {"stream_name": str, "temperature_c": float, "pressure_kpa": float, "molar_flow_kmol_hr": float}
)
async def set_stream_properties_tool(args: dict) -> dict:
    """Set stream properties."""
    state = get_promax_state()

    if not state.has_flowsheet:
        return _result("Error: No flowsheet. Create a project first.")

    try:
        name = args.get("stream_name")
        stream = state.flowsheet.PStreams(name)
        phase = stream.Phases(PMX_TOTAL_PHASE)
        set_props = []

        if "temperature_c" in args and args["temperature_c"] is not None:
            temp_k = convert_units(args["temperature_c"], "C", "temperature")
            phase.Properties(PHASE_PROPS["temperature"]).Value = temp_k
            set_props.append(f"T={args['temperature_c']}°C")

        if "pressure_kpa" in args and args["pressure_kpa"] is not None:
            pres_pa = convert_units(args["pressure_kpa"], "kPa", "pressure")
            phase.Properties(PHASE_PROPS["pressure"]).Value = pres_pa
            set_props.append(f"P={args['pressure_kpa']}kPa")

        if "molar_flow_kmol_hr" in args and args["molar_flow_kmol_hr"] is not None:
            flow_si = convert_units(args["molar_flow_kmol_hr"], "kmol/hr", "flow")
            phase.Properties(PHASE_PROPS["molar_flow"]).Value = flow_si
            set_props.append(f"F={args['molar_flow_kmol_hr']}kmol/hr")

        result = f"Set {name} properties: {', '.join(set_props)}"
        logger.info(result)
        return _result(result)

    except Exception as e:
        logger.error(f"Failed to set stream properties: {e}")
        return _result(f"Error: Failed to set stream properties: {str(e)}")


@tool(
    "set_stream_composition",
    "Set the mole fraction composition of a stream. Composition values must sum to 1.0.",
    {"stream_name": str, "composition": dict}
)
async def set_stream_composition_tool(args: dict) -> dict:
    """Set stream composition."""
    state = get_promax_state()

    if not state.has_flowsheet:
        return _result("Error: No flowsheet. Create a project first.")

    try:
        name = args.get("stream_name")
        composition = args.get("composition", {})

        # Handle JSON string: Claude sometimes sends "{\"Hydrogen\": 0.446}"
        if isinstance(composition, str):
            composition = json.loads(composition)

        # Validate composition sums to 1.0
        total = sum(composition.values())
        if abs(total - 1.0) > 0.001:
            return _result(f"Error: Composition must sum to 1.0, got {total:.4f}")

        stream = state.flowsheet.PStreams(name)
        env = state.flowsheet.Environment
        n_comps = env.Components.Count

        if n_comps == 0:
            return _result("Error: No components in environment. Add components first.")

        # Get environment component names in order
        env_comp_names = []
        for i in range(n_comps):
            try:
                comp = env.Components(i)
                pmx_name = comp.Species.SpeciesName.Name
                env_comp_names.append(pmx_name)
            except Exception:
                env_comp_names.append(f"Component_{i}")

        # Build composition array matching environment order (case-insensitive)
        comp_values = [0.0] * n_comps
        matched = []
        unmatched = []

        for user_name, value in composition.items():
            found = False
            for i, pmx_name in enumerate(env_comp_names):
                if user_name.lower() == pmx_name.lower():
                    comp_values[i] = value
                    matched.append(user_name)
                    found = True
                    break
            if not found:
                unmatched.append(user_name)

        # Set composition
        phase = stream.Phases(PMX_TOTAL_PHASE)
        comp_obj = phase.Composition(PMX_MOLAR_FRAC_BASIS)
        comp_obj.SIValues = tuple(comp_values)

        result = f"Set {name} composition ({len(matched)} components)"
        if unmatched:
            result += f"\nWarning: Unmatched components: {', '.join(unmatched)}"

        logger.info(result)
        return _result(result)

    except Exception as e:
        logger.error(f"Failed to set composition: {e}")
        return _result(f"Error: Failed to set composition: {str(e)}")


@tool(
    "flash_stream",
    "Flash a stream to establish thermodynamic equilibrium. Call after setting T, P, and composition.",
    {"stream_name": str}
)
async def flash_stream_tool(args: dict) -> dict:
    """Flash a stream."""
    state = get_promax_state()

    if not state.has_flowsheet:
        return _result("Error: No flowsheet. Create a project first.")

    try:
        name = args.get("stream_name")
        stream = state.flowsheet.PStreams(name)
        stream.Flash()
        logger.info(f"Flash completed for stream '{name}'")
        return _result(f"Flash calculation completed for '{name}'")

    except Exception as e:
        logger.error(f"Flash failed: {e}")
        return _result(f"Error: Flash calculation failed: {str(e)}")


@tool(
    "get_stream_results",
    "Get simulation results for a stream (temperature, pressure, flow, vapor fraction)",
    {"stream_name": str}
)
async def get_stream_results_tool(args: dict) -> dict:
    """Get stream results."""
    state = get_promax_state()

    if not state.has_flowsheet:
        return _result("Error: No flowsheet. Create a project first.")

    try:
        name = args.get("stream_name")
        stream = state.flowsheet.PStreams(name)
        phase = stream.Phases(PMX_TOTAL_PHASE)

        temp_k = phase.Properties(PHASE_PROPS["temperature"]).Value
        pres_pa = phase.Properties(PHASE_PROPS["pressure"]).Value
        molar_flow = phase.Properties(PHASE_PROPS["molar_flow"]).Value

        results = {
            "stream_name": name,
            "temperature_c": temp_k - 273.15 if temp_k else None,
            "pressure_kpa": pres_pa / 1000 if pres_pa else None,
            "molar_flow_kmol_hr": molar_flow * 3600 / 1000 if molar_flow else None,
        }

        logger.info(f"Retrieved results for stream '{name}'")
        return _result(json.dumps(results, indent=2))

    except Exception as e:
        logger.error(f"Failed to get stream results: {e}")
        return _result(f"Error: Failed to get stream results: {str(e)}")


@tool(
    "run_simulation",
    "Run the flowsheet solver to calculate all blocks and streams",
    {}
)
async def run_simulation_tool(args: dict) -> dict:
    """Run flowsheet solver."""
    state = get_promax_state()

    if not state.has_flowsheet:
        return _result("Error: No flowsheet. Create a project first.")

    try:
        solver = state.flowsheet.Solver
        solver.Solve()

        status_code = solver.LastSolverExecStatus
        if status_code >= 1:
            logger.info("Simulation converged")
            return _result("Simulation converged successfully")
        else:
            logger.warning(f"Simulation did not converge. Status: {status_code}")
            return _result(f"Simulation did not converge. Status code: {status_code}")

    except Exception as e:
        logger.error(f"Simulation failed: {e}")
        return _result(f"Error: Simulation failed: {str(e)}")


@tool(
    "save_project",
    "Save the current project to a .pmx file",
    {"filepath": str}
)
async def save_project_tool(args: dict) -> dict:
    """Save project to file."""
    state = get_promax_state()

    if state.project is None:
        return _result("Error: No project to save.")

    try:
        filepath = args.get("filepath")
        state.project.SaveAs(filepath)
        logger.info(f"Project saved to: {filepath}")
        return _result(f"Project saved to: {filepath}")

    except Exception as e:
        logger.error(f"Failed to save project: {e}")
        return _result(f"Error: Failed to save project: {str(e)}")


@tool(
    "close_project",
    "Close the current ProMax project",
    {}
)
async def close_project_tool(args: dict) -> dict:
    """Close project."""
    state = get_promax_state()

    if state.project is None:
        return _result("No project to close.")

    try:
        state.project.Close()
        state.reset()
        logger.info("Project closed")
        return _result("Project closed successfully")

    except Exception as e:
        logger.error(f"Failed to close project: {e}")
        return _result(f"Error: Failed to close project: {str(e)}")


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
            create_stream_tool,
            set_stream_properties_tool,
            set_stream_composition_tool,
            flash_stream_tool,
            get_stream_results_tool,
            run_simulation_tool,
            save_project_tool,
            close_project_tool,
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
    "mcp__promax__run_simulation",
    "mcp__promax__save_project",
    "mcp__promax__close_project",
]
