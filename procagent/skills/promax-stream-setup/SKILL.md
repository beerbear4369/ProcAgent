---
name: promax-stream-setup
description: Set up process streams with properties and compositions in ProMax
---

# Stream Setup Skill

Use this skill when configuring stream properties and compositions in ProMax.

## Critical: Property Setting Order

ALWAYS follow this exact sequence:

```
1. Set temperature (°C → converted to K internally)
2. Set pressure (kPa → converted to Pa internally)
3. Set flow rate (kmol/h or kg/h)
4. Set composition (mole fractions)
5. Flash the stream
```

**Why this order matters:**
- ProMax calculates derived properties based on what's specified
- Setting composition before T/P can cause calculation errors
- Flash establishes thermodynamic equilibrium

## Composition Rules

### Mole Fractions MUST Sum to 1.0

```python
# CORRECT
composition = {
    "Methane": 0.70,
    "Ethane": 0.15,
    "Propane": 0.10,
    "Carbon Dioxide": 0.05
}  # Sum = 1.0 ✓

# INCORRECT - will be rejected
composition = {
    "Methane": 0.70,
    "Ethane": 0.15
}  # Sum = 0.85 ✗
```

### Normalization

If user provides values that don't sum to 1.0 but are close, normalize:

```python
# User provides mass flows or percentages
raw_values = {"Methane": 70, "Ethane": 15, "Propane": 15}
total = sum(raw_values.values())
normalized = {k: v/total for k, v in raw_values.items()}
```

### Component Name Matching

Use exact ProMax component names:
- "Hydrogen Sulfide" not "H2S"
- "Carbon Dioxide" not "CO2"
- "MDEA" not "Methyldiethanolamine"

## Flash Requirements

ALWAYS flash inlet streams after setting composition:

```
mcp__promax__flash_stream(stream_name="210_Sour_Offgas")
```

**What flash does:**
- Establishes vapor-liquid equilibrium
- Calculates phase fractions
- Determines derived properties (density, enthalpy, etc.)

## Common Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| "Composition does not sum to 1.0" | Math error in fractions | Normalize values |
| "Component not found" | Wrong component name | Check exact ProMax names |
| "Stream not defined" | Missing flash | Call flash_stream |
| "Negative mole fraction" | Invalid input | Check all values ≥ 0 |

## Example: Complete Stream Setup

```
# 1. Create stream
mcp__promax__create_stream(name="210_Sour_Offgas")

# 2. Set properties
mcp__promax__set_stream_properties(
    stream_name="210_Sour_Offgas",
    temperature_c=45.0,
    pressure_kpa=700.0,
    molar_flow_kmol_hr=100.0
)

# 3. Set composition (must sum to 1.0)
mcp__promax__set_stream_composition(
    stream_name="210_Sour_Offgas",
    composition={
        "Methane": 0.60,
        "Ethane": 0.15,
        "Propane": 0.10,
        "Hydrogen Sulfide": 0.10,
        "Carbon Dioxide": 0.05
    }
)

# 4. Flash to establish equilibrium
mcp__promax__flash_stream(stream_name="210_Sour_Offgas")
```
