"""
ProMax 301-E Amine Treater Demo Script

Creates the 301-E Offgas Amine Treater with:
- Inlet Stream 210 (Sour Offgas) with full composition
- Inlet Stream 220 (Lean Amine) with full composition
- Outlet streams (Sweet Gas, Rich Amine)

Based on data from:
- RD EOR (工况1).pdf - Stream data tables
- 流程图PFD.pdf - Process Flow Diagram

301-E OFFGAS AMINE TREATER:
- ID: 1.5 m
- T-T: 15.0 m
- Type: Staged Column (Amine Contactor)

Usage:
    python promax_301e_amine_treater.py
"""

import os
import sys
from datetime import datetime

try:
    import win32com.client
    from win32com.client import gencache
except ImportError:
    print("ERROR: pywin32 not installed. Run: pip install pywin32")
    sys.exit(1)


# === Constants ===

# Phase Types (pmxPhaseEnum)
pmxTotalPhase = 5

# Phase Properties (pmxPhasePropEnum)
pmxPhaseTemperature = 0
pmxPhasePressure = 1
pmxPhaseMolarFlow = 16
pmxPhaseMassFlow = 17

# Composition basis
pmxMassFlowBasis = 1
pmxMolarFracBasis = 6


# === Stream Data from PDF ===

# Stream 210 - SOUR OFFGAS (inlet to 301-E)
STREAM_210 = {
    "name": "210_Sour_Offgas",
    "description": "SOUR OFFGAS",
    "temperature_C": 43,
    "pressure_kPa": 4.6 * 98.0665 + 101.325,  # kg/cm²(g) to kPa(abs)
    "mass_flow_kg_hr": 4536,
    "molar_flow_kmol_hr": 196.9,
    "vapor_fraction": 1.0,
    # Composition in kg/hr (mass flow)
    "composition_kg_hr": {
        "Hydrogen": 176,
        "Water": 8,
        "Carbon Monoxide": 7,
        "Carbon Dioxide": 450,
        "Hydrogen Sulfide": 8,
        "Methane": 302,
        "Ethane": 343,
        "Propane": 2426,
        "n-Butane": 178,
        "Isobutane": 239,
        "n-Pentane": 381,  # Naphtha approximated as n-Pentane
        "n-Hexane": 3,      # Wax approximated as n-Hexane
        "n-Heptane": 15,    # RD approximated as n-Heptane
    }
}

# Stream 220 - LEAN AMINE (inlet to 301-E)
STREAM_220 = {
    "name": "220_Lean_Amine",
    "description": "LEAN AMINE",
    "temperature_C": 50,
    "pressure_kPa": 5.7 * 98.0665 + 101.325,  # kg/cm²(g) to kPa(abs)
    "mass_flow_kg_hr": 46000,
    "molar_flow_kmol_hr": 1902.1,
    "vapor_fraction": 0.0,
    # Composition in kg/hr (mass flow)
    "composition_kg_hr": {
        "Water": 32161,
        "Hydrogen Sulfide": 39,
        "MDEA": 13800,
    }
}

# Stream 211 - TREATED OFFGAS (outlet from 301-E, vapor)
STREAM_211 = {
    "name": "211_Treated_Offgas",
    "description": "TREATED OFFGAS",
}

# Stream 222 - RICH AMINE (outlet from 301-E, liquid)
STREAM_222 = {
    "name": "222_Rich_Amine",
    "description": "RICH AMINE",
}


def convert_pressure_kgcm2g_to_pa(p_kgcm2g: float) -> float:
    """Convert pressure from kg/cm²(g) to Pa (absolute)."""
    # 1 kg/cm² = 98066.5 Pa
    # Add atmospheric pressure (101325 Pa) to convert gauge to absolute
    return (p_kgcm2g * 98066.5) + 101325


def create_301e_amine_treater(output_dir: str) -> str:
    """
    Create ProMax project with 301-E Amine Treater and inlet streams.

    Args:
        output_dir: Directory to save the project file

    Returns:
        Path to the saved project file
    """
    print("=" * 70)
    print("ProMax 301-E Amine Treater Demo")
    print("=" * 70)

    # Connect to ProMax with Visio GUI
    print("\n[1] Connecting to ProMax (with Visio)...")
    try:
        pmx = gencache.EnsureDispatch('ProMax.ProMaxOutOfProc')
        print(f"    Connected to ProMax {pmx.Version.Major}.{pmx.Version.Minor}")
    except Exception as e:
        print(f"    ERROR: Could not connect to ProMax: {e}")
        sys.exit(1)

    # Create new project
    print("\n[2] Creating new project...")
    prj = pmx.New()
    print(f"    Project: {prj.Name}")

    # Add flowsheet
    fs = prj.Flowsheets.Add("Amine_Treater_301E")
    print(f"    Flowsheet: {fs.Name}")

    # Get Visio objects
    visio = pmx.VisioApp
    vpage = fs.VisioPage

    # Find stencils
    print("\n[3] Loading Visio stencils...")
    stencils = {}
    for i in range(1, visio.Documents.Count + 1):
        doc = visio.Documents(i)
        if doc.Type == 2:  # Stencil
            stencils[doc.Name] = doc

    streams_stencil = stencils.get('Streams.vss')
    column_stencil = stencils.get('Column.vss')

    if not streams_stencil or not column_stencil:
        print("    ERROR: Required stencils not found!")
        prj.Close()
        return None

    # Get master shapes
    stream_master = streams_stencil.Masters('Process Stream')
    # Use "Distill" for staged column (Amine Treater)
    column_master = column_stencil.Masters('Distill')

    # Drop shapes
    print("\n[4] Creating equipment and streams...")

    # Drop inlet stream 210 (Sour Offgas) - left side, top
    shape_210 = vpage.Drop(stream_master, 2, 9)
    shape_210.Name = "210"
    print(f"    Created stream: 210 (Sour Offgas)")

    # Drop inlet stream 220 (Lean Amine) - left side, bottom
    shape_220 = vpage.Drop(stream_master, 2, 5)
    shape_220.Name = "220"
    print(f"    Created stream: 220 (Lean Amine)")

    # Drop 301-E Amine Treater column - center
    shape_301e = vpage.Drop(column_master, 5, 7)
    # Rename the block after it's created
    print(f"    Created column: {shape_301e.Name} (will be renamed to 301-E)")

    # Drop outlet stream 211 (Treated Offgas) - right side, top
    shape_211 = vpage.Drop(stream_master, 8, 9)
    shape_211.Name = "211"
    print(f"    Created stream: 211 (Treated Offgas)")

    # Drop outlet stream 222 (Rich Amine) - right side, bottom
    shape_222 = vpage.Drop(stream_master, 8, 5)
    shape_222.Name = "222"
    print(f"    Created stream: 222 (Rich Amine)")

    # Get ProMax objects
    print("\n[5] Accessing ProMax objects...")
    print(f"    Blocks: {fs.Blocks.Count}")
    for i in range(fs.Blocks.Count):
        blk = fs.Blocks(i)
        print(f"      - {blk.Name}")

    print(f"    Streams: {fs.PStreams.Count}")
    for i in range(fs.PStreams.Count):
        ps = fs.PStreams(i)
        print(f"      - {ps.Name}")

    # Get the column block (should be DTWR-100 or similar)
    column_block = fs.Blocks(0)
    print(f"\n    Column block: {column_block.Name}")

    # Set stream properties
    print("\n[6] Setting stream 210 (Sour Offgas) properties...")
    stream_210 = fs.PStreams("210")
    phase_210 = stream_210.Phases(pmxTotalPhase)

    # Temperature: 43°C = 316.15 K
    temp_K = STREAM_210["temperature_C"] + 273.15
    phase_210.Properties(pmxPhaseTemperature).Value = temp_K
    print(f"    Temperature: {temp_K:.2f} K ({STREAM_210['temperature_C']}°C)")

    # Pressure: 4.6 kg/cm²(g) = ~552 kPa(abs) = 552000 Pa
    pres_Pa = convert_pressure_kgcm2g_to_pa(4.6)
    phase_210.Properties(pmxPhasePressure).Value = pres_Pa
    print(f"    Pressure: {pres_Pa/1000:.1f} kPa ({4.6} kg/cm²(g))")

    # Mass flow: 4536 kg/hr = 1.26 kg/s
    mass_flow_kgs = STREAM_210["mass_flow_kg_hr"] / 3600
    phase_210.Properties(pmxPhaseMassFlow).Value = mass_flow_kgs
    print(f"    Mass Flow: {mass_flow_kgs:.4f} kg/s ({STREAM_210['mass_flow_kg_hr']} kg/hr)")

    print("\n[7] Setting stream 220 (Lean Amine) properties...")
    stream_220 = fs.PStreams("220")
    phase_220 = stream_220.Phases(pmxTotalPhase)

    # Temperature: 50°C = 323.15 K
    temp_K = STREAM_220["temperature_C"] + 273.15
    phase_220.Properties(pmxPhaseTemperature).Value = temp_K
    print(f"    Temperature: {temp_K:.2f} K ({STREAM_220['temperature_C']}°C)")

    # Pressure: 5.7 kg/cm²(g)
    pres_Pa = convert_pressure_kgcm2g_to_pa(5.7)
    phase_220.Properties(pmxPhasePressure).Value = pres_Pa
    print(f"    Pressure: {pres_Pa/1000:.1f} kPa ({5.7} kg/cm²(g))")

    # Mass flow: 46000 kg/hr
    mass_flow_kgs = STREAM_220["mass_flow_kg_hr"] / 3600
    phase_220.Properties(pmxPhaseMassFlow).Value = mass_flow_kgs
    print(f"    Mass Flow: {mass_flow_kgs:.4f} kg/s ({STREAM_220['mass_flow_kg_hr']} kg/hr)")

    # Display composition info (setting composition requires Environment setup)
    print("\n[8] Stream Compositions (reference data):")
    print("\n    Stream 210 - Sour Offgas Composition (kg/hr):")
    for comp, mass in STREAM_210["composition_kg_hr"].items():
        pct = mass / STREAM_210["mass_flow_kg_hr"] * 100
        print(f"      {comp}: {mass} kg/hr ({pct:.2f} wt%)")

    print("\n    Stream 220 - Lean Amine Composition (kg/hr):")
    for comp, mass in STREAM_220["composition_kg_hr"].items():
        pct = mass / STREAM_220["mass_flow_kg_hr"] * 100
        print(f"      {comp}: {mass} kg/hr ({pct:.2f} wt%)")

    # Check environment for available components
    print("\n[9] Checking thermodynamic environment...")
    env = fs.Environment
    print(f"    Environment: {env.Name}")
    print(f"    Components count: {env.Components.Count}")

    if env.Components.Count > 0:
        print("    Available components:")
        for i in range(min(env.Components.Count, 20)):
            comp = env.Components(i)
            try:
                name = comp.Species.SpeciesName.Name
                print(f"      [{i}] {name}")
            except:
                print(f"      [{i}] (unable to get name)")
    else:
        print("    NOTE: No components in environment yet.")
        print("    To set composition, you need to configure the thermodynamic")
        print("    environment with the required components in ProMax first.")

    # Save project
    print("\n[10] Saving project...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"301E_AmineTreater_{timestamp}.pmx"
    filepath = os.path.join(output_dir, filename)

    try:
        prj.SaveAs(filepath)
        print(f"    Saved to: {filepath}")
    except Exception as e:
        print(f"    ERROR saving: {e}")
        filepath = None

    # Summary
    print("\n" + "=" * 70)
    print("PROJECT SUMMARY")
    print("=" * 70)
    print(f"""
Equipment:
  - 301-E Offgas Amine Treater (Staged Column)
    ID: 1.5 m, T-T: 15.0 m

Inlet Streams:
  - 210 Sour Offgas: T=43°C, P=4.6 kg/cm²(g), Flow=4536 kg/hr
    Composition: H2, CO, CO2, H2S, CH4, C2H6, C3H8, C4H10, etc.

  - 220 Lean Amine: T=50°C, P=5.7 kg/cm²(g), Flow=46000 kg/hr
    Composition: Water (70%), MDEA (30%), trace H2S

Outlet Streams:
  - 211 Treated Offgas (sweet gas)
  - 222 Rich Amine

Performance Targets:
  - Offgas H2S: <= 100 ppm(mol)
  - Rich Amine Loading: <= 0.45 mol H2S/mol amine
""")
    print("=" * 70)

    # Close project
    print("\n[11] Closing project...")
    prj.Close()
    print("    Done!")

    return filepath


def main():
    """Main entry point."""
    # Output directory
    output_dir = r"D:\HuaweiMoveData\Users\ianle\Desktop\Promax COM"

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Create the 301-E Amine Treater project
    saved_path = create_301e_amine_treater(output_dir)

    if saved_path:
        print(f"\nProject saved to: {saved_path}")
        print("\nNext steps in ProMax:")
        print("1. Open the project")
        print("2. Configure thermodynamic environment with required components")
        print("3. Set stream compositions")
        print("4. Connect streams to column")
        print("5. Configure column parameters (stages, etc.)")
        print("6. Run simulation")


if __name__ == "__main__":
    main()
