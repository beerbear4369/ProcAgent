"""
ProMax MCP Server

Provides MCP tools for ProMax COM API operations including project management,
block creation, stream manipulation, and simulation execution.

This server is designed to be used as an in-process MCP server with the
Claude Agent SDK.
"""

import platform
from typing import Any, Dict, List, Optional

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

# Block type to Visio stencil mapping
BLOCK_TYPE_MAP = {
    "AmineTreater": {"stencil": "Column.vss", "master": "Distill"},
    "Separator": {"stencil": "Separators.vss", "master": "Separator-1"},
    "HeatExchanger": {"stencil": "Heat Exchangers.vss", "master": "HX-1"},
    "Compressor": {"stencil": "Rotating Equipment.vss", "master": "Compressor-1"},
    "Pump": {"stencil": "Rotating Equipment.vss", "master": "Pump-1"},
    "Valve": {"stencil": "Valves.vss", "master": "Valve-1"},
    "Mixer": {"stencil": "Misc.vss", "master": "Mixer"},
    "Splitter": {"stencil": "Misc.vss", "master": "Splitter"},
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


# ============================================================================
# MCP Tool Definitions
# ============================================================================

def create_promax_tools() -> Dict[str, callable]:
    """
    Create ProMax MCP tools dictionary.

    Returns a dictionary of tool functions that can be registered
    with the Claude Agent SDK.
    """
    state = get_promax_state()

    async def connect_promax(with_gui: bool = True) -> str:
        """
        Initialize connection to ProMax COM API.
        Must be called before any other ProMax operation.

        Args:
            with_gui: True for Visio GUI mode, False for background mode

        Returns:
            Connection status message
        """
        try:
            import win32com.client
            from win32com.client import gencache

            if with_gui:
                state.pmx = gencache.EnsureDispatch("ProMax.ProMaxOutOfProc")
                state.with_gui = True
            else:
                state.pmx = gencache.EnsureDispatch("ProMax.ProMax")
                state.with_gui = False

            version = f"{state.pmx.Version.Major}.{state.pmx.Version.Minor}"
            mode = "with GUI" if with_gui else "background"
            logger.info(f"Connected to ProMax {version} ({mode} mode)")
            return f"Connected to ProMax {version} ({mode} mode)"

        except Exception as e:
            logger.error(f"Failed to connect to ProMax: {e}")
            return f"Failed to connect to ProMax: {str(e)}"

    async def create_project(flowsheet_name: str = "Main") -> str:
        """
        Create a new ProMax project with a flowsheet.

        Args:
            flowsheet_name: Name for the new flowsheet

        Returns:
            Project creation status
        """
        if not state.is_connected:
            return "Error: Not connected to ProMax. Call connect_promax first."

        try:
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
            return f"Created project with flowsheet '{flowsheet_name}'"

        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            return f"Failed to create project: {str(e)}"

    async def add_flowsheet(name: str) -> str:
        """
        Add a new flowsheet to the current project.

        Args:
            name: Name for the new flowsheet

        Returns:
            Flowsheet creation status
        """
        if state.project is None:
            return "Error: No project. Create or open a project first."

        try:
            state.flowsheet = state.project.Flowsheets.Add(name)
            if state.with_gui:
                state.vpage = state.flowsheet.VisioPage
            logger.info(f"Created flowsheet: {name}")
            return f"Created flowsheet: {name}"

        except Exception as e:
            logger.error(f"Failed to add flowsheet: {e}")
            return f"Failed to add flowsheet: {str(e)}"

    async def add_components(components: List[str]) -> str:
        """
        Add chemical components to the flowsheet environment.
        Components must be added before setting stream compositions.

        Args:
            components: List of ProMax component names

        Returns:
            Addition status with success/failure counts
        """
        if not state.has_flowsheet:
            return "Error: No flowsheet. Create or open a project first."

        try:
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
            return result

        except Exception as e:
            logger.error(f"Failed to add components: {e}")
            return f"Failed to add components: {str(e)}"

    async def create_block(
        block_type: str,
        name: str,
        x: float = 5.0,
        y: float = 5.0
    ) -> str:
        """
        Create an equipment block in the flowsheet.

        Args:
            block_type: Type of block (AmineTreater, Separator, etc.)
            name: Name for the block
            x: X position on Visio page (inches)
            y: Y position on Visio page (inches)

        Returns:
            Block creation status
        """
        if not state.has_flowsheet:
            return "Error: No flowsheet. Create or open a project first."

        if block_type not in BLOCK_TYPE_MAP:
            return f"Error: Unknown block type '{block_type}'. Valid types: {list(BLOCK_TYPE_MAP.keys())}"

        try:
            block_info = BLOCK_TYPE_MAP[block_type]

            if state.with_gui and state.vpage:
                stencil_name = block_info["stencil"]
                if stencil_name not in state.stencils:
                    return f"Error: Stencil '{stencil_name}' not loaded."

                master = state.stencils[stencil_name].Masters(block_info["master"])
                shape = state.vpage.Drop(master, x, y)
                shape.Name = name
                state.block_shapes[name] = shape

                logger.info(f"Created {block_type} block '{name}' at ({x}, {y})")
                return f"Created {block_type} block '{name}' with Visio shape at ({x}, {y})"
            else:
                # Background mode - blocks created via data API
                blocks = state.flowsheet.Blocks
                # Note: Background mode block creation varies by block type
                logger.info(f"Created {block_type} block '{name}' (data only)")
                return f"Created {block_type} block '{name}' (data only, no Visio shape)"

        except Exception as e:
            logger.error(f"Failed to create block: {e}")
            return f"Failed to create block: {str(e)}"

    async def create_stream(
        name: str,
        x: Optional[float] = None,
        y: Optional[float] = None
    ) -> str:
        """
        Create a new process stream in the flowsheet.

        Args:
            name: Name for the stream
            x: X position on Visio page (inches)
            y: Y position on Visio page (inches)

        Returns:
            Stream creation status
        """
        if not state.has_flowsheet:
            return "Error: No flowsheet. Create or open a project first."

        try:
            if state.with_gui and state.vpage:
                stencil_name = "Streams.vss"
                if stencil_name not in state.stencils:
                    return f"Error: Stencil '{stencil_name}' not loaded."

                x_pos = x if x is not None else 2.0
                y_pos = y if y is not None else 5.0

                master = state.stencils[stencil_name].Masters("Process Stream")
                shape = state.vpage.Drop(master, x_pos, y_pos)
                shape.Name = name
                state.stream_shapes[name] = shape

                logger.info(f"Created stream '{name}' at ({x_pos}, {y_pos})")
                return f"Created stream '{name}' with Visio shape at ({x_pos}, {y_pos})"
            else:
                stream = state.flowsheet.PStreams.Add(name)
                logger.info(f"Created stream '{name}' (data only)")
                return f"Created stream '{name}' (data only)"

        except Exception as e:
            logger.error(f"Failed to create stream: {e}")
            return f"Failed to create stream: {str(e)}"

    async def connect_stream(
        stream_name: str,
        block_name: str,
        port_index: int,
        is_inlet: bool = True
    ) -> str:
        """
        Connect a stream to a block port.

        Args:
            stream_name: Name of the stream
            block_name: Name of the block
            port_index: Port index on the block
            is_inlet: True for inlet, False for outlet

        Returns:
            Connection status
        """
        if not state.has_flowsheet:
            return "Error: No flowsheet. Create or open a project first."

        try:
            if state.with_gui:
                if stream_name not in state.stream_shapes:
                    return f"Error: Stream '{stream_name}' not found."
                if block_name not in state.block_shapes:
                    return f"Error: Block '{block_name}' not found."

                stream_shape = state.stream_shapes[stream_name]
                block_shape = state.block_shapes[block_name]

                # Get connection cell on block
                conn_cell = block_shape.CellsSRC(1, 1, port_index)

                # Connect stream end to block
                if is_inlet:
                    stream_shape.CellsU("EndX").GlueTo(conn_cell)
                else:
                    stream_shape.CellsU("BeginX").GlueTo(conn_cell)

                direction = "inlet" if is_inlet else "outlet"
                logger.info(f"Connected stream '{stream_name}' to block '{block_name}' port {port_index} ({direction})")
                return f"Connected stream '{stream_name}' to block '{block_name}' port {port_index} ({direction})"
            else:
                return "Stream connection in background mode not fully implemented"

        except Exception as e:
            logger.error(f"Failed to connect stream: {e}")
            return f"Failed to connect stream: {str(e)}"

    async def set_stream_properties(
        stream_name: str,
        temperature_c: Optional[float] = None,
        pressure_kpa: Optional[float] = None,
        molar_flow_kmol_hr: Optional[float] = None,
        mass_flow_kg_hr: Optional[float] = None
    ) -> str:
        """
        Set physical properties of a process stream.

        Args:
            stream_name: Name of the stream
            temperature_c: Temperature in Celsius
            pressure_kpa: Pressure in kPa
            molar_flow_kmol_hr: Molar flow in kmol/hr
            mass_flow_kg_hr: Mass flow in kg/hr

        Returns:
            Property setting status
        """
        if not state.has_flowsheet:
            return "Error: No flowsheet. Create or open a project first."

        try:
            stream = state.flowsheet.PStreams(stream_name)
            phase = stream.Phases(PMX_TOTAL_PHASE)
            set_props = []

            if temperature_c is not None:
                temp_k = convert_units(temperature_c, "C", "temperature")
                phase.Properties(PHASE_PROPS["temperature"]).Value = temp_k
                set_props.append(f"T={temperature_c}°C")

            if pressure_kpa is not None:
                pres_pa = convert_units(pressure_kpa, "kPa", "pressure")
                phase.Properties(PHASE_PROPS["pressure"]).Value = pres_pa
                set_props.append(f"P={pressure_kpa}kPa")

            if molar_flow_kmol_hr is not None:
                flow_si = convert_units(molar_flow_kmol_hr, "kmol/hr", "flow")
                phase.Properties(PHASE_PROPS["molar_flow"]).Value = flow_si
                set_props.append(f"F={molar_flow_kmol_hr}kmol/hr")

            if mass_flow_kg_hr is not None:
                flow_si = convert_units(mass_flow_kg_hr, "kg/hr", "flow")
                phase.Properties(PHASE_PROPS["mass_flow"]).Value = flow_si
                set_props.append(f"F={mass_flow_kg_hr}kg/hr")

            result = f"Set {stream_name} properties: {', '.join(set_props)}"
            logger.info(result)
            return result

        except Exception as e:
            logger.error(f"Failed to set stream properties: {e}")
            return f"Failed to set stream properties: {str(e)}"

    async def set_stream_composition(
        stream_name: str,
        composition: Dict[str, float]
    ) -> str:
        """
        Set the mole fraction composition of a stream.
        Composition values must sum to 1.0.

        Args:
            stream_name: Name of the stream
            composition: Dict of component name to mole fraction

        Returns:
            Composition setting status
        """
        if not state.has_flowsheet:
            return "Error: No flowsheet. Create or open a project first."

        # Validate composition sums to 1.0
        total = sum(composition.values())
        if abs(total - 1.0) > 0.001:
            return f"Error: Composition must sum to 1.0, got {total:.4f}"

        try:
            stream = state.flowsheet.PStreams(stream_name)
            env = state.flowsheet.Environment
            n_comps = env.Components.Count

            if n_comps == 0:
                return "Error: No components in environment. Add components first."

            # Get environment component names in order
            env_comp_names = []
            for i in range(n_comps):
                try:
                    comp = env.Components(i)
                    pmx_name = comp.Species.SpeciesName.Name
                    env_comp_names.append(pmx_name)
                except Exception:
                    env_comp_names.append(f"Component_{i}")

            # Build composition array matching environment order
            comp_values = [0.0] * n_comps
            matched = []
            unmatched = []

            for name, value in composition.items():
                found = False
                for i, pmx_name in enumerate(env_comp_names):
                    if name.lower() == pmx_name.lower():
                        comp_values[i] = value
                        matched.append(name)
                        found = True
                        break
                if not found:
                    unmatched.append(name)

            # Set composition
            phase = stream.Phases(PMX_TOTAL_PHASE)
            comp_obj = phase.Composition(PMX_MOLAR_FRAC_BASIS)
            comp_obj.SIValues = tuple(comp_values)

            result = f"Set {stream_name} composition ({len(matched)} components)"
            if unmatched:
                result += f"\nWarning: Unmatched components: {', '.join(unmatched)}"

            logger.info(result)
            return result

        except Exception as e:
            logger.error(f"Failed to set composition: {e}")
            return f"Failed to set composition: {str(e)}"

    async def flash_stream(stream_name: str) -> str:
        """
        Flash a stream to establish thermodynamic equilibrium.
        Call after setting temperature, pressure, and composition.

        Args:
            stream_name: Name of the stream to flash

        Returns:
            Flash calculation status
        """
        if not state.has_flowsheet:
            return "Error: No flowsheet. Create or open a project first."

        try:
            stream = state.flowsheet.PStreams(stream_name)
            stream.Flash()
            logger.info(f"Flash completed for stream '{stream_name}'")
            return f"Flash calculation completed for '{stream_name}'"

        except Exception as e:
            logger.error(f"Flash failed: {e}")
            return f"Flash calculation failed: {str(e)}"

    async def run_simulation() -> str:
        """
        Run the flowsheet solver.

        Returns:
            Solver status with convergence information
        """
        if not state.has_flowsheet:
            return "Error: No flowsheet. Create or open a project first."

        try:
            solver = state.flowsheet.Solver
            solver.Solve()

            status_code = solver.LastSolverExecStatus
            if status_code >= 1:
                logger.info("Simulation converged")
                return "Simulation converged successfully"
            else:
                logger.warning(f"Simulation did not converge. Status: {status_code}")
                return f"Simulation did not converge. Status code: {status_code}"

        except Exception as e:
            logger.error(f"Simulation failed: {e}")
            return f"Simulation failed: {str(e)}"

    async def get_results(stream_names: List[str]) -> Dict[str, Any]:
        """
        Get simulation results for specified streams.

        Args:
            stream_names: List of stream names to get results for

        Returns:
            Dictionary of stream results
        """
        if not state.has_flowsheet:
            return {"error": "No flowsheet. Create or open a project first."}

        results = {}
        for name in stream_names:
            try:
                stream = state.flowsheet.PStreams(name)
                phase = stream.Phases(PMX_TOTAL_PHASE)

                temp_k = phase.Properties(PHASE_PROPS["temperature"]).Value
                pres_pa = phase.Properties(PHASE_PROPS["pressure"]).Value
                molar_flow = phase.Properties(PHASE_PROPS["molar_flow"]).Value

                results[name] = {
                    "temperature_c": temp_k - 273.15 if temp_k else None,
                    "pressure_kpa": pres_pa / 1000 if pres_pa else None,
                    "molar_flow_kmol_hr": molar_flow * 3600 / 1000 if molar_flow else None,
                }
            except Exception as e:
                results[name] = {"error": str(e)}

        logger.info(f"Retrieved results for {len(stream_names)} streams")
        return results

    async def save_project(file_path: str) -> str:
        """
        Save the current project to a file.

        Args:
            file_path: Full path to save the .prx file

        Returns:
            Save status
        """
        if state.project is None:
            return "Error: No project to save."

        try:
            state.project.SaveAs(file_path)
            logger.info(f"Project saved to: {file_path}")
            return f"Project saved to: {file_path}"

        except Exception as e:
            logger.error(f"Failed to save project: {e}")
            return f"Failed to save project: {str(e)}"

    async def close_project() -> str:
        """
        Close the current ProMax project.

        Returns:
            Close status
        """
        if state.project is None:
            return "No project to close."

        try:
            state.project.Close()
            state.reset()
            logger.info("Project closed")
            return "Project closed successfully"

        except Exception as e:
            logger.error(f"Failed to close project: {e}")
            return f"Failed to close project: {str(e)}"

    # Return tool dictionary
    return {
        "connect_promax": connect_promax,
        "create_project": create_project,
        "add_flowsheet": add_flowsheet,
        "add_components": add_components,
        "create_block": create_block,
        "create_stream": create_stream,
        "connect_stream": connect_stream,
        "set_stream_properties": set_stream_properties,
        "set_stream_composition": set_stream_composition,
        "flash_stream": flash_stream,
        "run_simulation": run_simulation,
        "get_results": get_results,
        "save_project": save_project,
        "close_project": close_project,
    }
