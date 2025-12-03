#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
ProMax MCP Server
Provides MCP server for ProMax COM API operations including stream manipulation
(temperature, pressure, composition) and flowsheet management.
"""

import platform
import sys

# Platform check - this module requires Windows
if platform.system() != "Windows":
    import logging

    logging.warning(
        f"promax_com_mcp_server.py requires Windows platform. Current: {platform.system()}. Skipping module initialization."
    )
    sys.exit(0)

from typing import Annotated, Any, Dict, List, Optional

from fastmcp import FastMCP
from fastmcp.client import Client
from pydantic import Field

from ufo.client.mcp.mcp_registry import MCPRegistry


# Unit conversion constants
UNIT_CONVERSIONS = {
    "temperature": {
        "K": lambda x: x,  # Base unit
        "C": lambda x: x + 273.15,
        "F": lambda x: (x - 32) * 5 / 9 + 273.15,
        "R": lambda x: x * 5 / 9,
    },
    "pressure": {
        "Pa": lambda x: x,  # Base unit
        "kPa": lambda x: x * 1000,
        "bar": lambda x: x * 100000,
        "atm": lambda x: x * 101325,
        "psi": lambda x: x * 6894.76,
        "kg/cm2": lambda x: x * 98066.5,
        "kg/cm2(g)": lambda x: x * 98066.5 + 101325,  # Gauge to absolute
    },
    "flow": {
        "mol/s": lambda x: x,  # Base unit
        "kmol/hr": lambda x: x * 1000 / 3600,
        "kg/s": lambda x: x,
        "kg/hr": lambda x: x / 3600,
    },
}


# Phase property indices (pmxPhasePropEnum)
PHASE_PROPS = {
    "temperature": 0,  # K
    "pressure": 1,  # Pa
    "molar_flow": 16,  # mol/s
    "mass_flow": 17,  # kg/s
}

# Phase constants
PMX_TOTAL_PHASE = 5
PMX_MOLAR_FRAC_BASIS = 6
PMX_MASS_FLOW_BASIS = 1


class ProMaxServerState:
    """Singleton state for ProMax COM session management."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProMaxServerState, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.pmx = None  # ProMax COM object
            self.project = None  # Current project
            self.flowsheet = None  # Current flowsheet
            self.visio = None  # Visio application (if with_gui)
            self.vpage = None  # Visio page (if with_gui)
            self.stencils = {}  # Loaded stencils
            self.stream_shapes = {}  # Track stream Visio shapes {name: shape}
            self.stream_positions = {}  # Track stream positions {name: (x, y)}
            self.next_stream_x = 2.0  # Next x position for auto-placement
            self.next_stream_y = 5.0  # Next y position for auto-placement
            self.with_gui = False
            ProMaxServerState._initialized = True

    def reset(self):
        """Reset the state for a new session."""
        self.pmx = None
        self.project = None
        self.flowsheet = None
        self.visio = None
        self.vpage = None
        self.stencils = {}
        self.stream_shapes = {}
        self.stream_positions = {}
        self.next_stream_x = 2.0
        self.next_stream_y = 5.0
        self.with_gui = False


def convert_units(value: float, unit: str, unit_type: str) -> float:
    """Convert value to SI units."""
    if unit_type not in UNIT_CONVERSIONS:
        raise ValueError(f"Unknown unit type: {unit_type}")
    if unit not in UNIT_CONVERSIONS[unit_type]:
        raise ValueError(f"Unknown {unit_type} unit: {unit}")
    return UNIT_CONVERSIONS[unit_type][unit](value)


@MCPRegistry.register_factory_decorator("ProMaxCOMExecutor")
def create_promax_mcp_server(process_name: str) -> FastMCP:
    """
    Create and return the ProMax MCP server instance.
    :param process_name: Name of the ProMax process.
    :return: FastMCP instance for ProMax operations.
    """
    state = ProMaxServerState()

    mcp = FastMCP(
        "UFO ProMax MCP Server",
        instructions="""ProMax Process Simulation Tools (runs inside VISIO.EXE)

IMPORTANT: ProMax is a process simulation application that uses Microsoft Visio as its GUI frontend.
When you see a VISIO.EXE window that is actually ProMax, use these COM API tools instead of UI clicks
for reliable automation of process engineering tasks.

These tools provide direct programmatic access to ProMax functionality:
- Creating/opening simulation projects
- Managing chemical components and thermodynamic packages
- Creating and configuring process streams (temperature, pressure, flow, composition)
- Running flowsheet calculations (flash, solve)
- Querying stream properties and results

Workflow: Always call connect_promax FIRST before any other ProMax operation.""",
    )

    @mcp.tool(tags={"AppAgent"})
    def connect_promax(
        with_gui: Annotated[
            bool,
            Field(
                description="Whether to connect with Visio GUI (True) or background mode (False). Use True for visual diagrams."
            ),
        ] = True,
    ) -> Annotated[str, Field(description="Connection status message")]:
        """
        Initialize connection to ProMax COM API. MUST be called before any other ProMax operation.

        ProMax is a process simulation application that runs inside VISIO.EXE. This tool establishes
        programmatic COM access to ProMax for reliable automation (preferred over UI clicks).

        Use with_gui=True to see visual Visio diagrams, with_gui=False for faster background processing.
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
            return f"Connected to ProMax {version} ({mode} mode)"

        except Exception as e:
            return f"Failed to connect to ProMax: {str(e)}"

    @mcp.tool(tags={"AppAgent"})
    def create_project(
        flowsheet_name: Annotated[
            str,
            Field(description="Name for the new flowsheet (e.g., '301E_AmineTreater')"),
        ] = "Main",
    ) -> Annotated[str, Field(description="Project creation status")]:
        """
        Create a new ProMax simulation project with a flowsheet.
        Use this COM tool for programmatic project creation (more reliable than UI navigation).
        Requires prior connect_promax call.
        """
        if not state.pmx:
            return "Error: Not connected to ProMax. Call connect_promax first."

        try:
            state.project = state.pmx.New()
            state.flowsheet = state.project.Flowsheets.Add(flowsheet_name)

            # Load stencils and get Visio page if using GUI mode
            if state.with_gui:
                state.visio = state.pmx.VisioApp
                state.vpage = state.flowsheet.VisioPage
                for i in range(1, state.visio.Documents.Count + 1):
                    doc = state.visio.Documents(i)
                    if doc.Type == 2:  # Stencil
                        state.stencils[doc.Name] = doc

            return f"Created project with flowsheet '{flowsheet_name}'"

        except Exception as e:
            return f"Failed to create project: {str(e)}"

    @mcp.tool(tags={"AppAgent"})
    def open_project(
        file_path: Annotated[str, Field(description="Full path to the .pmx file")],
    ) -> Annotated[str, Field(description="Project open status")]:
        """
        Open an existing ProMax project file.
        """
        if not state.pmx:
            return "Error: Not connected to ProMax. Call connect_promax first."

        try:
            state.project = state.pmx.Open(file_path)
            if state.project.Flowsheets.Count > 0:
                state.flowsheet = state.project.Flowsheets(0)
            return f"Opened project: {file_path}"

        except Exception as e:
            return f"Failed to open project: {str(e)}"

    @mcp.tool(tags={"AppAgent"})
    def add_component(
        component_name: Annotated[
            str,
            Field(
                description="ProMax component name (e.g., 'Methane', 'Water', 'MDEA', 'Carbon Dioxide')"
            ),
        ],
    ) -> Annotated[str, Field(description="Component addition status")]:
        """
        Add a component to the flowsheet environment. Components must be added before setting compositions.
        """
        if not state.flowsheet:
            return "Error: No flowsheet. Create or open a project first."

        try:
            env = state.flowsheet.Environment
            env.Components.Add(component_name)
            return f"Added component: {component_name}"

        except Exception as e:
            return f"Failed to add component '{component_name}': {str(e)}"

    @mcp.tool(tags={"AppAgent"})
    def add_components_batch(
        component_names: Annotated[
            List[str],
            Field(
                description="List of ProMax component names to add (e.g., ['Methane', 'Ethane', 'Water', 'MDEA'])"
            ),
        ],
    ) -> Annotated[str, Field(description="Batch addition status with results")]:
        """
        Add multiple components to the flowsheet environment at once.
        """
        if not state.flowsheet:
            return "Error: No flowsheet. Create or open a project first."

        env = state.flowsheet.Environment
        added = []
        failed = []

        for comp_name in component_names:
            try:
                env.Components.Add(comp_name)
                added.append(comp_name)
            except Exception as e:
                failed.append(f"{comp_name}: {str(e)}")

        result = f"Added {len(added)} components: {', '.join(added)}"
        if failed:
            result += f"\nFailed: {'; '.join(failed)}"
        return result

    @mcp.tool(tags={"AppAgent"})
    def create_stream(
        stream_name: Annotated[
            str, Field(description="Name for the new process stream (e.g., '210_Sour_Offgas')")
        ],
        x_position: Annotated[
            Optional[float],
            Field(description="X position on Visio page (inches). Auto-positioned if not specified."),
        ] = None,
        y_position: Annotated[
            Optional[float],
            Field(description="Y position on Visio page (inches). Auto-positioned if not specified."),
        ] = None,
    ) -> Annotated[str, Field(description="Stream creation status")]:
        """
        Create a new process stream in the flowsheet.
        In GUI mode, this also creates a visual Visio shape on the flowsheet diagram.
        """
        if not state.flowsheet:
            return "Error: No flowsheet. Create or open a project first."

        try:
            # Determine position
            x = x_position if x_position is not None else state.next_stream_x
            y = y_position if y_position is not None else state.next_stream_y

            if state.with_gui and state.vpage:
                # GUI mode: Create stream with Visio shape
                stencil_name = "Streams.vss"
                if stencil_name not in state.stencils:
                    return f"Error: Stencil '{stencil_name}' not loaded. Ensure GUI mode is properly initialized."

                # Get stream master and drop shape
                stream_master = state.stencils[stencil_name].Masters("Process Stream")
                shape = state.vpage.Drop(stream_master, x, y)
                shape.Name = stream_name

                # Track the shape and position
                state.stream_shapes[stream_name] = shape
                state.stream_positions[stream_name] = (x, y)

                # Update auto-position for next stream (move right)
                if x_position is None:
                    state.next_stream_x += 2.0
                    # Wrap to new row if too far right
                    if state.next_stream_x > 10.0:
                        state.next_stream_x = 2.0
                        state.next_stream_y -= 2.0

                return f"Created stream with Visio shape: {stream_name} at ({x:.1f}, {y:.1f})"
            else:
                # Background mode: Create data-only stream
                stream = state.flowsheet.PStreams.Add(stream_name)
                return f"Created stream: {stream_name} (data only, no Visio shape)"

        except Exception as e:
            return f"Failed to create stream: {str(e)}"

    @mcp.tool(tags={"AppAgent"})
    def set_stream_temperature(
        stream_name: Annotated[str, Field(description="Name of the stream to modify")],
        value: Annotated[float, Field(description="Temperature value")],
        units: Annotated[
            str,
            Field(description="Temperature units: 'K' (Kelvin), 'C' (Celsius), 'F' (Fahrenheit), 'R' (Rankine)"),
        ] = "C",
    ) -> Annotated[str, Field(description="Temperature setting status")]:
        """
        Set the temperature of a process stream.
        """
        if not state.flowsheet:
            return "Error: No flowsheet. Create or open a project first."

        try:
            stream = state.flowsheet.PStreams(stream_name)
            phase = stream.Phases(PMX_TOTAL_PHASE)

            # Convert to Kelvin
            temp_K = convert_units(value, units, "temperature")
            phase.Properties(PHASE_PROPS["temperature"]).Value = temp_K

            return f"Set {stream_name} temperature to {value} {units} ({temp_K:.2f} K)"

        except Exception as e:
            return f"Failed to set temperature: {str(e)}"

    @mcp.tool(tags={"AppAgent"})
    def set_stream_pressure(
        stream_name: Annotated[str, Field(description="Name of the stream to modify")],
        value: Annotated[float, Field(description="Pressure value")],
        units: Annotated[
            str,
            Field(
                description="Pressure units: 'Pa', 'kPa', 'bar', 'atm', 'psi', 'kg/cm2', 'kg/cm2(g)' (gauge)"
            ),
        ] = "kPa",
    ) -> Annotated[str, Field(description="Pressure setting status")]:
        """
        Set the pressure of a process stream. Use 'kg/cm2(g)' for gauge pressure.
        """
        if not state.flowsheet:
            return "Error: No flowsheet. Create or open a project first."

        try:
            stream = state.flowsheet.PStreams(stream_name)
            phase = stream.Phases(PMX_TOTAL_PHASE)

            # Convert to Pascals
            pres_Pa = convert_units(value, units, "pressure")
            phase.Properties(PHASE_PROPS["pressure"]).Value = pres_Pa

            return f"Set {stream_name} pressure to {value} {units} ({pres_Pa/1000:.2f} kPa)"

        except Exception as e:
            return f"Failed to set pressure: {str(e)}"

    @mcp.tool(tags={"AppAgent"})
    def set_stream_flow(
        stream_name: Annotated[str, Field(description="Name of the stream to modify")],
        value: Annotated[float, Field(description="Flow rate value")],
        flow_type: Annotated[
            str, Field(description="Flow type: 'molar' or 'mass'")
        ] = "molar",
        units: Annotated[
            str,
            Field(description="Flow units: 'mol/s', 'kmol/hr' for molar; 'kg/s', 'kg/hr' for mass"),
        ] = "kmol/hr",
    ) -> Annotated[str, Field(description="Flow setting status")]:
        """
        Set the molar or mass flow rate of a process stream.
        """
        if not state.flowsheet:
            return "Error: No flowsheet. Create or open a project first."

        try:
            stream = state.flowsheet.PStreams(stream_name)
            phase = stream.Phases(PMX_TOTAL_PHASE)

            # Convert to SI units
            flow_si = convert_units(value, units, "flow")

            if flow_type.lower() == "molar":
                phase.Properties(PHASE_PROPS["molar_flow"]).Value = flow_si
                return f"Set {stream_name} molar flow to {value} {units} ({flow_si:.4f} mol/s)"
            else:
                phase.Properties(PHASE_PROPS["mass_flow"]).Value = flow_si
                return f"Set {stream_name} mass flow to {value} {units} ({flow_si:.4f} kg/s)"

        except Exception as e:
            return f"Failed to set flow: {str(e)}"

    @mcp.tool(tags={"AppAgent"})
    def set_stream_composition(
        stream_name: Annotated[str, Field(description="Name of the stream to modify")],
        composition: Annotated[
            Dict[str, float],
            Field(
                description="Dictionary of component names to mass flows in kg/hr (e.g., {'Methane': 302, 'Ethane': 343, 'Water': 8})"
            ),
        ],
    ) -> Annotated[str, Field(description="Composition setting status with details")]:
        """
        Set the composition of a process stream using mass flow basis (kg/hr).
        Components must be added to the environment first using add_component or add_components_batch.
        """
        if not state.flowsheet:
            return "Error: No flowsheet. Create or open a project first."

        try:
            stream = state.flowsheet.PStreams(stream_name)
            env = state.flowsheet.Environment
            n_comps = env.Components.Count

            if n_comps == 0:
                return f"Error: No components in environment. Add components first."

            # Get total mass flow
            total_mass = sum(composition.values())

            # Calculate mass fractions
            mass_fractions = {k: v / total_mass for k, v in composition.items()}

            # Get environment component names in order
            env_comp_names = []
            for i in range(n_comps):
                try:
                    comp = env.Components(i)
                    pmx_name = comp.Species.SpeciesName.Name
                    env_comp_names.append(pmx_name)
                except:
                    env_comp_names.append(f"Component_{i}")

            # Build composition array matching environment order
            comp_values = [0.0] * n_comps
            matched = []
            unmatched = []

            for our_name, mass_frac in mass_fractions.items():
                found = False
                for i, pmx_name in enumerate(env_comp_names):
                    if our_name.lower() == pmx_name.lower():
                        comp_values[i] = mass_frac
                        matched.append(f"{our_name}: {mass_frac*100:.2f}%")
                        found = True
                        break
                if not found:
                    unmatched.append(our_name)

            # Set composition using molar fraction basis
            phase = stream.Phases(PMX_TOTAL_PHASE)
            comp_obj = phase.Composition(PMX_MOLAR_FRAC_BASIS)
            comp_obj.SIValues = tuple(comp_values)

            result = f"Set {stream_name} composition ({len(matched)} components)"
            if unmatched:
                result += f"\nWarning: Unmatched components: {', '.join(unmatched)}"

            return result

        except Exception as e:
            return f"Failed to set composition: {str(e)}"

    @mcp.tool(tags={"AppAgent"})
    def flash_stream(
        stream_name: Annotated[str, Field(description="Name of the stream to flash")],
    ) -> Annotated[str, Field(description="Flash calculation status")]:
        """
        Run flash calculation on a stream to calculate derived properties from specified conditions.
        Call this after setting temperature, pressure, and composition.
        """
        if not state.flowsheet:
            return "Error: No flowsheet. Create or open a project first."

        try:
            stream = state.flowsheet.PStreams(stream_name)
            stream.Flash()
            return f"Flash calculation completed for {stream_name}"

        except Exception as e:
            return f"Flash calculation failed: {str(e)}"

    @mcp.tool(tags={"AppAgent"})
    def get_stream_properties(
        stream_name: Annotated[str, Field(description="Name of the stream to query")],
    ) -> Annotated[Dict[str, Any], Field(description="Stream properties dictionary")]:
        """
        Get current properties of a process stream including temperature, pressure, and flow rates.
        """
        if not state.flowsheet:
            return {"error": "No flowsheet. Create or open a project first."}

        try:
            stream = state.flowsheet.PStreams(stream_name)
            phase = stream.Phases(PMX_TOTAL_PHASE)

            temp_K = phase.Properties(PHASE_PROPS["temperature"]).Value
            pres_Pa = phase.Properties(PHASE_PROPS["pressure"]).Value
            molar_flow = phase.Properties(PHASE_PROPS["molar_flow"]).Value
            mass_flow = phase.Properties(PHASE_PROPS["mass_flow"]).Value

            return {
                "stream_name": stream_name,
                "temperature_K": temp_K,
                "temperature_C": temp_K - 273.15 if temp_K else None,
                "pressure_Pa": pres_Pa,
                "pressure_kPa": pres_Pa / 1000 if pres_Pa else None,
                "molar_flow_mol_s": molar_flow,
                "molar_flow_kmol_hr": molar_flow * 3600 / 1000 if molar_flow else None,
                "mass_flow_kg_s": mass_flow,
                "mass_flow_kg_hr": mass_flow * 3600 if mass_flow else None,
            }

        except Exception as e:
            return {"error": f"Failed to get properties: {str(e)}"}

    @mcp.tool(tags={"AppAgent"})
    def list_streams(
    ) -> Annotated[List[str], Field(description="List of stream names in the flowsheet")]:
        """
        List all process streams in the current flowsheet.
        """
        if not state.flowsheet:
            return ["Error: No flowsheet. Create or open a project first."]

        try:
            streams = []
            for i in range(state.flowsheet.PStreams.Count):
                stream = state.flowsheet.PStreams(i)
                streams.append(stream.Name)
            return streams

        except Exception as e:
            return [f"Error listing streams: {str(e)}"]

    @mcp.tool(tags={"AppAgent"})
    def list_components(
    ) -> Annotated[List[str], Field(description="List of components in the environment")]:
        """
        List all components currently in the flowsheet environment.
        """
        if not state.flowsheet:
            return ["Error: No flowsheet. Create or open a project first."]

        try:
            env = state.flowsheet.Environment
            components = []
            for i in range(env.Components.Count):
                comp = env.Components(i)
                try:
                    name = comp.Species.SpeciesName.Name
                except:
                    name = f"Component_{i}"
                components.append(name)
            return components

        except Exception as e:
            return [f"Error listing components: {str(e)}"]

    @mcp.tool(tags={"AppAgent"})
    def solve_flowsheet(
    ) -> Annotated[str, Field(description="Solver execution status")]:
        """
        Run the flowsheet solver to calculate all outlet streams and equipment.
        """
        if not state.flowsheet:
            return "Error: No flowsheet. Create or open a project first."

        try:
            solver = state.flowsheet.Solver
            solver.Solve()

            status = solver.LastSolverExecStatus
            if status >= 1:  # pmxConverged
                return "Flowsheet solved successfully (converged)"
            else:
                detail = solver.DetailStatus if hasattr(solver, "DetailStatus") else "Unknown"
                return f"Solver did not converge. Status: {status}, Detail: {detail}"

        except Exception as e:
            return f"Solver failed: {str(e)}"

    @mcp.tool(tags={"AppAgent"})
    def save_project(
        file_path: Annotated[str, Field(description="Full path to save the .pmx file")],
    ) -> Annotated[str, Field(description="Save status")]:
        """
        Save the current project to a .pmx file.
        """
        if not state.project:
            return "Error: No project to save."

        try:
            state.project.SaveAs(file_path)
            return f"Project saved to: {file_path}"

        except Exception as e:
            return f"Failed to save project: {str(e)}"

    @mcp.tool(tags={"AppAgent"})
    def close_project(
    ) -> Annotated[str, Field(description="Close status")]:
        """
        Close the current ProMax project.
        """
        if not state.project:
            return "No project to close."

        try:
            state.project.Close()
            state.reset()
            return "Project closed successfully"

        except Exception as e:
            return f"Failed to close project: {str(e)}"

    return mcp


async def main():
    """
    Main function to test the MCP server.
    """
    process_name = "promax"

    mcp_server = create_promax_mcp_server(process_name)

    async with Client(mcp_server) as client:
        print(f"Starting MCP server for {process_name}...")
        tool_list = await client.list_tools()
        for tool in tool_list:
            print(f"Available tool: {tool.name} - {tool.description}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
