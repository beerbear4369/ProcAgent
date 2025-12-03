# ProMax COM API Reference

This document provides a comprehensive reference for the ProMax COM API, discovered through Python introspection using `pywin32`.

## Overview

ProMax exposes a COM interface that can be accessed from any COM-compatible language:
- **Python**: `win32com.client.Dispatch("ProMax.ProMax")`
- **VBA**: `CreateObject("ProMax.ProMax")`
- **C#**: COM Interop reference

### Connection Modes

| ProgID | Description | Use Case |
|--------|-------------|----------|
| `ProMax.ProMax` | Background mode (no Visio GUI) | Fast data operations, no visual diagram |
| `ProMax.ProMaxOutOfProc` | With Visio GUI visible | Creating visual diagrams with shapes |

**Critical Insight:**
- `ProMax.ProMax` creates data objects (blocks, streams) but **NO Visio shapes**
- `ProMax.ProMaxOutOfProc` + dropping shapes from stencils creates **BOTH** Visio shapes AND ProMax data objects
- If you need visual diagrams, you MUST use `ProMaxOutOfProc` and drop shapes from Visio stencils

### Tested Version

- ProMax 6.0 (Build 23032)
- Python 3.13 with pywin32

---

## Object Hierarchy

```
ProMax.ProMax (Application)
├── Version
├── Name
├── ProcessId
├── Project (current project)
│   ├── Name, Path
│   ├── Flowsheets (collection)
│   │   └── Flowsheet
│   │       ├── Name
│   │       ├── Environment (thermodynamic package)
│   │       │   ├── Components
│   │       │   ├── FlashOptions
│   │       │   └── ModelParameters
│   │       ├── PStreams (process streams collection)
│   │       │   └── PStream
│   │       │       ├── Name, Status
│   │       │       ├── Phases (collection, indexed by pmxPhaseEnum)
│   │       │       │   └── Phase
│   │       │       │       ├── Properties (indexed by pmxPhasePropEnum)
│   │       │       │       │   └── Property (Value, Units, SetValue)
│   │       │       │       └── Composition
│   │       │       ├── Flash()
│   │       │       ├── FromConnection, ToConnection
│   │       │       └── Analyses
│   │       ├── QStreams (heat streams collection)
│   │       ├── Blocks (collection)
│   │       │   └── Block
│   │       │       ├── Name, Type, Status
│   │       │       ├── Inlets, Outlets
│   │       │       ├── Properties, PropertiesExt
│   │       │       └── Solve()
│   │       └── Solver
│   │           ├── Solve()
│   │           ├── Pause(), Abort()
│   │           ├── IsSolving, Paused
│   │           └── LastSolverExecStatus
│   ├── Environments
│   ├── Reactions, ReactionSets
│   ├── Calculators
│   ├── Save(), SaveAs(), Close()
│   └── Solver
├── New() → Project
├── Open(path) → Project
├── VisioApp
└── ExcelApp
```

---

## Quick Start Example

```python
import win32com.client
from win32com.client import gencache

# Connect to ProMax (early binding for constants)
pmx = gencache.EnsureDispatch('ProMax.ProMax')

# Create new project
prj = pmx.New()
print(f"Created project: {prj.Name}")

# Add flowsheet
fs = prj.Flowsheets.Add("MainFlowsheet")

# Create a stream
stream = fs.CreatePStream("Feed")

# Set stream properties (Total phase = 5)
phase = stream.Phases(5)  # pmxTotalPhase
phase.Properties(0).Value = 313.15  # Temperature in K (40°C)
phase.Properties(1).Value = 3500000  # Pressure in Pa (3500 kPa)
phase.Properties(16).Value = 1000    # Molar flow in mol/s

# Add a separator block
sep = fs.Blocks.Add(12, "V-100")  # pmxSeparatorBlock = 12

# Save project
prj.SaveAs(r"C:\path\to\project.pmx")

# Close
prj.Close()
```

---

## Constants Reference

### Phase Types (pmxPhaseEnum)

| Constant | Value | Description |
|----------|-------|-------------|
| `pmxVaporPhase` | 0 | Vapor phase |
| `pmxLLiquidPhase` | 1 | Light liquid phase |
| `pmxHLiquidPhase` | 2 | Heavy liquid phase |
| `pmxSolidPhase` | 3 | Solid phase |
| `pmxMixedLiquidPhase` | 4 | Mixed liquid phase |
| `pmxTotalPhase` | 5 | Total stream (all phases combined) |
| `pmxNonspecificLiquidPhase` | 6 | Non-specific liquid |
| `pmxAqueousPhase` | 7 | Aqueous phase |
| `pmxSulfurPhase` | 8 | Sulfur phase |
| `pmxMercuryPhase` | 9 | Mercury phase |

### Phase Properties (pmxPhasePropEnum)

| Constant | Value | Description | Default Units |
|----------|-------|-------------|---------------|
| `pmxPhaseTemperature` | 0 | Temperature | K |
| `pmxPhasePressure` | 1 | Pressure | Pa |
| `pmxPhaseMoleFracVapor` | 2 | Vapor mole fraction | - |
| `pmxPhaseMoleFracLLiquid` | 3 | Light liquid mole fraction | - |
| `pmxPhaseMoleFracHLiquid` | 4 | Heavy liquid mole fraction | - |
| `pmxPhaseMassFracVapor` | 5 | Vapor mass fraction | - |
| `pmxPhaseMoleWeight` | 11 | Molecular weight | kg/kmol |
| `pmxPhaseMolarDensity` | 12 | Molar density | mol/m³ |
| `pmxPhaseMassDensity` | 13 | Mass density | kg/m³ |
| `pmxPhaseMolarVolume` | 14 | Molar volume | m³/mol |
| `pmxPhaseMolarFlow` | 16 | Molar flow rate | mol/s |
| `pmxPhaseMassFlow` | 17 | Mass flow rate | kg/s |
| `pmxPhaseVapVolumeFlow` | 18 | Vapor volume flow | m³/s |
| `pmxPhaseLiqVolumeFlow` | 19 | Liquid volume flow | m³/s |
| `pmxPhaseCompressibility` | 23 | Compressibility factor | - |
| `pmxPhaseSpecificGravity` | 24 | Specific gravity | - |
| `pmxPhaseAPIGravity` | 25 | API gravity | - |
| `pmxPhaseEnthalpy` | 26 | Enthalpy | J |
| `pmxPhaseMolarEnthalpy` | 27 | Molar enthalpy | J/mol |
| `pmxPhaseMassEnthalpy` | 28 | Mass enthalpy | J/kg |
| `pmxPhaseEntropy` | 29 | Entropy | J/K |
| `pmxPhaseMolarEntropy` | 30 | Molar entropy | J/(mol·K) |
| `pmxPhaseGibbs` | 32 | Gibbs free energy | J |
| `pmxPhaseInternalEnergy` | 35 | Internal energy | J |
| `pmxPhaseMolarCp` | 38 | Molar heat capacity (Cp) | J/(mol·K) |
| `pmxPhaseMolarCv` | 40 | Molar heat capacity (Cv) | J/(mol·K) |
| `pmxPhaseCpCvRatio` | 43 | Cp/Cv ratio | - |
| `pmxPhaseDynViscosity` | 44 | Dynamic viscosity | Pa·s |
| `pmxPhaseKinViscosity` | 45 | Kinematic viscosity | m²/s |
| `pmxPhaseThermalCond` | 46 | Thermal conductivity | W/(m·K) |
| `pmxPhaseSurfaceTension` | 47 | Surface tension | N/m |
| `pmxPhaseNetIGHeatValue` | 50 | Net ideal gas heat value | J/mol |
| `pmxPhaseGrossIGHeatValue` | 52 | Gross ideal gas heat value | J/mol |

### Composition Basis (pmxCompositionEnum)

| Constant | Value | Description |
|----------|-------|-------------|
| `pmxMolarFlowBasis` | 0 | Molar flow basis |
| `pmxMassFlowBasis` | 1 | Mass flow basis |
| `pmxVolFlowBasis` | 2 | Volume flow basis |
| `pmxStdVapVolFlowBasis` | 3 | Standard vapor volume flow |
| `pmxNormalVapVolFlowBasis` | 4 | Normal vapor volume flow |
| `pmxStdLiqVolFlowBasis` | 5 | Standard liquid volume flow |
| `pmxMolarFracBasis` | 6 | Molar fraction basis |

### Block Types (pmxBlockTypesEnum)

| Constant | Value | Description |
|----------|-------|-------------|
| `pmxCompExpBlock` | 0 | Compressor/Expander |
| `pmxCRHEXBlock` | 1 | Cross-flow Heat Exchanger |
| `pmxDividerBlock` | 2 | Stream Divider |
| `pmxJTValveBlock` | 3 | JT Valve (Joule-Thomson) |
| `pmxMakeupBlock` | 4 | Makeup Stream |
| `pmxMixerSplitterBlock` | 5 | Mixer/Splitter |
| `pmxMSHEXBlock` | 6 | Multi-stream Heat Exchanger |
| `pmxPipelineBlock` | 7 | Pipeline |
| `pmxPipeSegmentBlock` | 8 | Pipe Segment |
| `pmxPumpBlock` | 9 | Pump |
| `pmxRecycleBlock` | 10 | Recycle |
| `pmxSaturatorBlock` | 11 | Saturator |
| `pmxSeparatorBlock` | 12 | Separator (2-phase, 3-phase) |
| `pmxSSHEXBlock` | 13 | Shell & Tube Heat Exchanger |
| `pmxStageBlock` | 14 | Single Stage |
| `pmxStagedColumnBlock` | 15 | Staged Column (Amine Treater, Distillation) |
| `pmxXFSConnectorBlock` | 16 | Cross-Flowsheet Connector |
| `pmxQRecycleBlock` | 17 | Heat Recycle |
| `pmxReactorBlock` | 18 | Reactor |
| `pmxCRReactorBlock` | 19 | Continuous Reactor |
| `pmxVLReactorBlock` | 20 | Vapor-Liquid Reactor |
| `pmxNEQReactorBlock` | 21 | Non-Equilibrium Reactor |
| `pmxCapeOpenBlock` | 22 | CAPE-OPEN Unit |
| `pmxTeeWyeBlock` | 23 | Tee/Wye |
| `pmxEjectorBlock` | 24 | Ejector |
| `pmxMembraneBlock` | 25 | Membrane |
| `pmxFlareTipBlock` | 26 | Flare Tip |
| `pmxSealDrumBlock` | 27 | Seal Drum |
| `pmxReliefBlock` | 28 | Relief Valve |
| `pmxTankLossesBlock` | 29 | Tank Losses |
| `pmxAdsorberBlock` | 30 | Adsorber |
| `pmxWaterElectrolysisBlock` | 31 | Water Electrolysis |

### Separator Types (pmxSeparatorTypeEnum)

| Constant | Value | Description |
|----------|-------|-------------|
| `pmxSepTypeVert2P` | 0 | Vertical 2-phase |
| `pmxSepTypeVert3P` | 1 | Vertical 3-phase |
| `pmxSepTypeHorz2P` | 2 | Horizontal 2-phase |
| `pmxSepTypeHorz3P` | 3 | Horizontal 3-phase |
| `pmxSepTypeHorz3PBoot` | 4 | Horizontal 3-phase with boot |
| `pmxSepTypeHorz3PWeir` | 5 | Horizontal 3-phase with weir |
| `pmxSepTypeHorz3PBuckWeir` | 6 | Horizontal 3-phase bucket weir |
| `pmxSepTypeHorz3PBootWeir` | 7 | Horizontal 3-phase boot weir |

### Staged Column Add-ons (pmxStagedColumnAddOnEnum)

| Constant | Value | Description |
|----------|-------|-------------|
| `pmxStagedColumnNoAddOn` | 0 | No add-on |
| `pmxStagedColumnWithReboiler` | 1 | With reboiler |
| `pmxStagedColumnWithTotalCondenser` | 2 | With total condenser |
| `pmxStagedColumnWithReboilerAndTotalCondenser` | 3 | With reboiler and total condenser |
| `pmxStagedColumnWithPartialCondenser` | 4 | With partial condenser |
| `pmxStagedColumnWithReboilerAndPartialCondenser` | 5 | With reboiler and partial condenser |

### Amine Analysis Properties (pmxAmineAnalysisEnum)

| Constant | Value | Description |
|----------|-------|-------------|
| `pmxAACO2LoadingMassPerVol` | 0 | CO2 loading (mass/volume) |
| `pmxAACO2LoadingVolPerVol` | 1 | CO2 loading (vol/vol) |
| `pmxAACO2LoadingMolePerMoleAmine` | 2 | CO2 loading (mol/mol amine) |
| `pmxAAH2SLoadingMassPerVol` | 3 | H2S loading (mass/volume) |
| `pmxAAH2SLoadingVolPerVol` | 4 | H2S loading (vol/vol) |
| `pmxAAH2SLoadingMolePerMoleAmine` | 5 | H2S loading (mol/mol amine) |
| `pmxAATotalAcidGasLoading` | 6 | Total acid gas loading |
| `pmxAApH` | 7 | pH |
| `pmxAAMolarity` | 8 | Amine molarity |
| `pmxAAIncludeAmmonia` | 9 | Include ammonia in analysis |

---

## API Reference

### ProMax Application Object

```python
pmx = win32com.client.Dispatch("ProMax.ProMax")
```

| Property/Method | Type | Description |
|----------------|------|-------------|
| `Version` | Property | Returns version info (Major, Minor, Build) |
| `Name` | Property | Application instance name |
| `ProcessId` | Property | Windows process ID |
| `Project` | Property | Current project (or None) |
| `New()` | Method | Create new project, returns Project |
| `Open(path)` | Method | Open project file, returns Project |
| `VisioApp` | Property | Access to Visio application |
| `VisioAsGUI()` | Method | Enable Visio GUI mode |
| `ExcelApp` | Property | Access to Excel application |

### Project Object

| Property/Method | Type | Description |
|----------------|------|-------------|
| `Name` | Property | Project name |
| `Path` | Property | File path |
| `IsSaved` | Property | Whether project has unsaved changes |
| `Flowsheets` | Collection | Flowsheets in project |
| `Environments` | Collection | Thermodynamic environments |
| `Reactions` | Collection | Reaction definitions |
| `Calculators` | Collection | Calculator blocks |
| `Solver` | Object | Project-level solver |
| `Save()` | Method | Save project |
| `SaveAs(path)` | Method | Save project to new path |
| `SaveTo(path)` | Method | Save copy to path |
| `Close()` | Method | Close project |
| `Export()` | Method | Export project |

### Flowsheets Collection

| Property/Method | Type | Description |
|----------------|------|-------------|
| `Count` | Property | Number of flowsheets |
| `Add(name)` | Method | Add new flowsheet |
| `Item(index_or_name)` | Method | Get flowsheet by index or name |

### Flowsheet Object

| Property/Method | Type | Description |
|----------------|------|-------------|
| `Name` | Property | Flowsheet name |
| `Environment` | Object | Thermodynamic environment |
| `PStreams` | Collection | Process streams |
| `QStreams` | Collection | Heat streams |
| `Blocks` | Collection | Equipment blocks |
| `Solver` | Object | Flowsheet solver |
| `CreatePStream(name)` | Method | Create process stream |
| `CreateQStream(name)` | Method | Create heat stream |
| `Delete()` | Method | Delete flowsheet |

### PStream (Process Stream) Object

| Property/Method | Type | Description |
|----------------|------|-------------|
| `Name` | Property | Stream name |
| `Status` | Property | Stream status code |
| `Phases` | Collection | Phase collection (indexed by pmxPhaseEnum) |
| `FromConnection` | Property | Upstream block connection |
| `ToConnection` | Property | Downstream block connection |
| `Analyses` | Collection | Stream analyses |
| `Flash()` | Method | Perform flash calculation |
| `Clear()` | Method | Clear stream data |
| `CopyFrom(stream)` | Method | Copy from another stream |
| `LinkTo(stream)` | Method | Link to another stream |
| `Delete()` | Method | Delete stream |

### Phase Object

| Property/Method | Type | Description |
|----------------|------|-------------|
| `Type` | Property | Phase type (pmxPhaseEnum) |
| `Status` | Property | Phase status |
| `Properties` | Collection | Phase properties (indexed by pmxPhasePropEnum) |
| `Composition` | Object | Phase composition |

### Property Object

| Property/Method | Type | Description |
|----------------|------|-------------|
| `Name` | Property | Property name |
| `Value` | Property | Get/set value in default units |
| `SIValue` | Property | Get/set value in SI units |
| `Units` | Property | Current units string |
| `UnitsEnum` | Property | Units enumeration value |
| `SetValue(value, units)` | Method | Set value with specific units |
| `GetValue(units)` | Method | Get value in specific units |
| `Clear()` | Method | Clear property value |

### Blocks Collection

| Property/Method | Type | Description |
|----------------|------|-------------|
| `Count` | Property | Number of blocks |
| `Add(type, name)` | Method | Add block (type from pmxBlockTypesEnum) |
| `Item(index_or_name)` | Method | Get block by index or name |

### Block Object

| Property/Method | Type | Description |
|----------------|------|-------------|
| `Name` | Property | Block name |
| `Type` | Property | Block type |
| `Status` | Property | Block status |
| `Inlets` | Collection | Inlet stream connections |
| `Outlets` | Collection | Outlet stream connections |
| `Properties` | Object | Block-specific properties |
| `PropertiesExt` | Object | Extended properties |
| `EnergyConnections` | Collection | Energy stream connections |
| `Solve()` | Method | Solve this block only |
| `Clear()` | Method | Clear block results |
| `Delete()` | Method | Delete block |

### Solver Object

| Property/Method | Type | Description |
|----------------|------|-------------|
| `IsSolving` | Property | Whether solver is running |
| `Paused` | Property | Whether solver is paused |
| `PauseRequested` | Property | Whether pause was requested |
| `AbortRequested` | Property | Whether abort was requested |
| `LastSolverExecStatus` | Property | Last execution status |
| `DetailStatus` | Property | Detailed status information |
| `Solve()` | Method | Run solver |
| `Pause()` | Method | Pause solver |
| `ContinueExecute()` | Method | Continue after pause |
| `Abort()` | Method | Abort solver |

---

## Visio Integration

ProMax uses Microsoft Visio for flowsheet diagrams. When using `ProMaxOutOfProc`, you can create visual diagrams by dropping shapes from stencils.

### Available Stencils

| Stencil | Contents |
|---------|----------|
| `Separators.vss` | 2-Phase Separators, 3-Phase Separators |
| `Column.vss` | Distillation columns, Staged columns (Amine Treaters) |
| `Exchangers.vss` | Heat exchangers, Shell & Tube, Fin Fan |
| `Fluid Drivers.vss` | Compressors, Expanders, Pumps |
| `Mixer.vss` | Mixers, Splitters, Tees, Wyes |
| `Reactor.vss` | Various reactor types |
| `Streams.vss` | Process streams, Energy streams |
| `Valves.vss` | JT Valves, Relief valves |
| `Auxiliary.vss` | Dividers, Pipelines, Membranes, Adsorbers |
| `Recycle.vss` | Recycle blocks |

### Creating Shapes (With Visio Diagrams)

```python
import win32com.client
from win32com.client import gencache

# Must use OutOfProc for Visio
pmx = gencache.EnsureDispatch('ProMax.ProMaxOutOfProc')
prj = pmx.New()
fs = prj.Flowsheets.Add("Main")

# Access Visio
visio = pmx.VisioApp
vpage = fs.VisioPage  # Visio page for this flowsheet

# Find stencils
stencils = {}
for i in range(1, visio.Documents.Count + 1):
    doc = visio.Documents(i)
    if doc.Type == 2:  # Stencil
        stencils[doc.Name] = doc

# Get master shapes from stencils
stream_master = stencils['Streams.vss'].Masters('Process Stream')
sep_master = stencils['Separators.vss'].Masters('2 Phase Separator - Vertical')
column_master = stencils['Column.vss'].Masters('Distill')

# Drop shapes at (x, y) coordinates
# This creates BOTH the Visio shape AND the ProMax object!
inlet = vpage.Drop(stream_master, 1, 5)
inlet.Name = "Feed"  # Rename the stream

separator = vpage.Drop(sep_master, 3, 5)
# separator.Name is auto-generated like "VSSL-100"

column = vpage.Drop(column_master, 6, 5)
# column.Name is auto-generated like "DTWR-100"

# Now ProMax objects exist with VShape references
print(fs.Blocks.Count)  # 2 (separator + column)
print(fs.PStreams.Count)  # 1 (Feed)

# Access the ProMax objects
sep_block = fs.Blocks("VSSL-100")
print(sep_block.VShape)  # Reference to Visio shape
```

### Key Master Shape Names

| Stencil | Master Name | ProMax Block Type |
|---------|-------------|-------------------|
| Separators.vss | "2 Phase Separator - Vertical" | Separator |
| Separators.vss | "3 Phase Separator" | Separator |
| Column.vss | "Distill" | Staged Column (Amine Treater) |
| Exchangers.vss | "Shell and Tube Exchanger" | SSHEX |
| Fluid Drivers.vss | "Compressor" | CompExp |
| Fluid Drivers.vss | "Centrifugal Pump" | Pump |
| Streams.vss | "Process Stream" | PStream |
| Streams.vss | "Energy Stream" | QStream |
| Valves.vss | "JT Valve" | JTValve |

---

## Connecting Streams to Blocks (Visio GlueTo Method)

**Critical Discovery**: Streams are connected to blocks by "gluing" Visio shape cells together. This is the only reliable way to create connections programmatically when using `ProMaxOutOfProc`.

### Connection Method

```python
# For INLET streams: Glue stream's END to block's connection point
stream_shape.Cells("EndX").GlueTo(block_shape.Cells("Connections.X{n}"))

# For OUTLET streams: Glue stream's BEGIN to block's connection point
stream_shape.Cells("BeginX").GlueTo(block_shape.Cells("Connections.X{n}"))
```

Where `{n}` is the 1-based connection point index.

### Finding Connection Points

```python
# Get connection points on a shape
section_idx = 7  # visSectionConnectionPts
num_pts = shape.RowCount(section_idx)

for i in range(num_pts):
    x = shape.CellsSRC(section_idx, i, 0).ResultIU  # X coordinate
    y = shape.CellsSRC(section_idx, i, 1).ResultIU  # Y coordinate
    print(f"Point {i}: ({x:.3f}, {y:.3f})")
```

### Separator Connection Points (2-Phase Vertical)

| Point Index | Visio Cell | Location | Purpose |
|-------------|------------|----------|---------|
| 0 | Connections.X1 | Left side | Feed inlet |
| 1 | Connections.X2 | Top | Vapor outlet |
| 2 | Connections.X3 | Bottom | Liquid outlet |
| 3-5 | Connections.X4-6 | Various | Additional connections |

**Example - Connecting streams to a separator:**
```python
# Create shapes
sep_shape = vpage.Drop(sep_master, 5, 5)
inlet_shape = vpage.Drop(stream_master, 2, 5)
vapor_shape = vpage.Drop(stream_master, 5, 7)
liquid_shape = vpage.Drop(stream_master, 5, 3)

# Connect inlet (stream END to block connection point 1)
inlet_shape.Cells("EndX").GlueTo(sep_shape.Cells("Connections.X1"))

# Connect vapor outlet (stream BEGIN from block connection point 2)
vapor_shape.Cells("BeginX").GlueTo(sep_shape.Cells("Connections.X2"))

# Connect liquid outlet (stream BEGIN from block connection point 3)
liquid_shape.Cells("BeginX").GlueTo(sep_shape.Cells("Connections.X3"))
```

### Column Connection Points (Distill/Amine Treater)

Columns (Staged Columns, Amine Treaters) have **6 connection points** by default:

| Point Index | Visio Cell | Coordinates | Location | Purpose |
|-------------|------------|-------------|----------|---------|
| 0 | Connections.X1 | (0.150, 1.125) | Top center | Overhead vapor |
| 1 | Connections.X2 | (0.150, 0.000) | Bottom center | Bottoms liquid |
| 2 | Connections.X3 | (0.000, 1.050) | Top left | Feed to top stage |
| 3 | Connections.X4 | (0.300, 1.050) | Top right | Draw from top stage |
| 4 | Connections.X5 | (0.000, 0.075) | Bottom left | Feed to bottom stage |
| 5 | Connections.X6 | (0.300, 0.075) | Bottom right | Draw from bottom stage |

**Example - Amine Treater (301-E) stream connections:**
```python
# For an amine treater:
# - Sour gas feed enters at BOTTOM LEFT (point 5)
# - Lean amine enters at TOP LEFT (point 3)
# - Treated gas exits from TOP RIGHT (point 4)
# - Rich amine exits from BOTTOM RIGHT (point 6)

# Create column
col_shape = vpage.Drop(column_master, 5, 5)

# Create streams
sour_gas = vpage.Drop(stream_master, 2, 3.5)
sour_gas.Name = "210_Sour_Offgas"

lean_amine = vpage.Drop(stream_master, 2, 6.5)
lean_amine.Name = "220_Lean_Amine"

treated_gas = vpage.Drop(stream_master, 8, 6.5)
treated_gas.Name = "211_Treated_Offgas"

rich_amine = vpage.Drop(stream_master, 8, 3.5)
rich_amine.Name = "222_Rich_Amine"

# Connect streams
sour_gas.Cells("EndX").GlueTo(col_shape.Cells("Connections.X5"))      # Bottom left inlet
lean_amine.Cells("EndX").GlueTo(col_shape.Cells("Connections.X3"))    # Top left inlet
treated_gas.Cells("BeginX").GlueTo(col_shape.Cells("Connections.X4")) # Top right outlet
rich_amine.Cells("BeginX").GlueTo(col_shape.Cells("Connections.X6"))  # Bottom right outlet
```

### Verifying Connections

After gluing, verify connections through the ProMax block object:

```python
block = fs.Blocks(0)

# Check inlets
print(f"Inlets: {block.Inlets.Count}")
for i in range(block.Inlets.Count):
    conn = block.Inlets(i)
    print(f"  Inlet {i}: connected")

# Check outlets
print(f"Outlets: {block.Outlets.Count}")
for i in range(block.Outlets.Count):
    conn = block.Outlets(i)
    print(f"  Outlet {i}: connected")
```

### Important Notes

1. **Connection point indices are 0-based** when reading via `CellsSRC`, but **1-based** when using `Cells("Connections.X{n}")`.

2. **Inlet vs Outlet streams**:
   - Inlet streams: Use `EndX` cell (stream flows INTO block)
   - Outlet streams: Use `BeginX` cell (stream flows FROM block)

3. **Column stages**: For columns, streams connect to specific stages. The default 2-stage column has top and bottom stages with left/right connection points on each.

4. **Illegal connections**: Attempting to connect to an incompatible connection point will raise a COM error: "An attempt has been made to create an illegal connection on block..."

---

## Common Operations

### Adding Components to Environment

Before setting stream compositions, you must add the required components to the flowsheet environment:

```python
# Get environment and components collection
env = fs.Environment
components = env.Components

# Add components by name (must match ProMax species database)
components.Add("Methane")
components.Add("Ethane")
components.Add("Propane")
components.Add("n-Butane")
components.Add("Carbon Dioxide")
components.Add("Hydrogen Sulfide")
components.Add("Water")
components.Add("MDEA")  # Methyldiethanolamine for amine treating

print(f"Total components: {components.Count}")
```

### Setting Stream Composition

**IMPORTANT**: The composition is set using the `SIValues` property on the Composition object, NOT by setting individual component values.

```python
# Get environment for component list
env = fs.Environment
n_comps = env.Components.Count

# Build composition array matching environment component order
composition = [0.0] * n_comps
for i in range(n_comps):
    comp_name = env.Components(i).Species.SpeciesName.Name
    if comp_name == "Methane":
        composition[i] = 0.80
    elif comp_name == "Ethane":
        composition[i] = 0.15
    elif comp_name == "Propane":
        composition[i] = 0.05

# Set composition on total phase using SIValues
phase = stream.Phases(5)  # pmxTotalPhase
comp_obj = phase.Composition(6)  # pmxMolarFracBasis = 6

# Use SIValues to set all component values at once (must be a tuple)
comp_obj.SIValues = tuple(composition)

# Flash the stream to calculate properties
stream.Flash()
```

**Key Points:**
- `Composition(6)` returns a `_PDoubleTable` object for molar fraction basis
- Use `SIValues = tuple(values)` to set all component values at once
- Individual component access `comp_obj(i).Value = val` does NOT work
- `SetValues()` requires specific array format and may fail with type mismatch
- Values should sum to 1.0 for molar/mass fraction basis

### Running Simulation

```python
# Run flowsheet solver
solver = fs.Solver
status = solver.Solve()

# Check if converged
if solver.LastSolverExecStatus >= 1:  # pmxConverged
    print("Simulation converged!")
else:
    print("Simulation did not converge")
    print(f"Status: {solver.DetailStatus}")
```

### Reading Results

```python
# After solving, read outlet stream properties
outlet = fs.PStreams("Outlet")
total = outlet.Phases(5)  # pmxTotalPhase

temp_K = total.Properties(0).Value  # Temperature
pres_Pa = total.Properties(1).Value  # Pressure
flow_mols = total.Properties(16).Value  # Molar flow

print(f"T = {temp_K - 273.15:.1f} °C")
print(f"P = {pres_Pa/1000:.1f} kPa")
print(f"Flow = {flow_mols:.1f} mol/s")
```

---

## Error Handling

```python
import pywintypes

try:
    prj = pmx.Open(r"C:\path\to\project.pmx")
except pywintypes.com_error as e:
    hr, msg, exc, arg = e.args
    if exc:
        source, description, help_file, help_context, scode = exc[:5]
        print(f"COM Error: {description}")
    else:
        print(f"Error: {msg}")
```

---

## Notes and Limitations

1. **Units**: Default units are SI (K, Pa, mol/s). Use `SetValue(val, units)` for other units, but unit strings must match ProMax's expected format.

2. **Early vs Late Binding**: Use `gencache.EnsureDispatch()` for early binding to access constants and better IntelliSense.

3. **Background Mode**: `ProMax.ProMax` runs without Visio GUI. Use `ProMax.ProMaxOutOfProc` if you need the visual interface.

4. **Thermodynamic Package**: Must configure Environment with components before streams can have valid compositions.

5. **Block Connections**: Blocks must be connected to streams for simulation to run properly.

---

## See Also

- ProMax VBA Manual (BR&E documentation)
- pywin32 documentation: https://github.com/mhammond/pywin32
- COM automation in Python: https://docs.python.org/3/library/win32com.html
