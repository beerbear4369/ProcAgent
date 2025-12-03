---
name: promax-amine-treater
description: Create and configure an Amine Treater (absorber column) for H2S/CO2 removal in ProMax
---

# Amine Treater Creation Skill

Use this skill when the user wants to create an amine treater, absorber, or acid gas removal column.

## Required Components

Add these components to the flowsheet environment FIRST:

**Amine Components:**
- MDEA (Methyldiethanolamine) - or DEA, MEA depending on user spec
- Water

**Acid Gases:**
- Hydrogen Sulfide
- Carbon Dioxide

**Hydrocarbon Feed (typical):**
- Methane
- Ethane
- Propane
- n-Butane
- Isobutane
- n-Pentane (heavier hydrocarbons if present)

## Block Creation Steps

1. Use `mcp__promax__create_block` with:
   - block_type: "AmineTreater"
   - This drops a "Distill" shape from Column.vss stencil
   - Default name will be DTWR-100 or similar

2. Create and connect streams:

| Stream | Type | Port | Description |
|--------|------|------|-------------|
| Sour Gas | Inlet | 5 (Bottom Left) | Feed gas containing H2S/CO2 |
| Lean Amine | Inlet | 3 (Top Left) | Regenerated amine solution |
| Treated Gas | Outlet | 4 (Top Right) | Sweet gas product |
| Rich Amine | Outlet | 6 (Bottom Right) | Amine loaded with acid gas |

## Stream Property Setting Order

ALWAYS follow this sequence for each inlet stream:

1. Set temperature (C)
2. Set pressure (kPa)
3. Set molar or mass flow rate
4. Set composition (mole fractions MUST sum to 1.0)
5. Flash the stream

## Typical Operating Conditions

| Parameter | Typical Range | Unit |
|-----------|---------------|------|
| Column stages | 10-20 | theoretical stages |
| Sour gas inlet T | 30-60 | °C |
| Sour gas inlet P | 500-1000 | kPa |
| Lean amine inlet T | 40-55 | °C |
| Lean amine inlet P | slightly above column | kPa |
| Amine concentration | 30-50 | wt% MDEA in water |

## Performance Targets

| Parameter | Target | Unit |
|-----------|--------|------|
| Treated gas H2S | ≤ 100 | ppm(mol) |
| Treated gas CO2 | ≤ 2 | mol% |
| Rich amine loading | ≤ 0.45 | mol acid gas/mol amine |

## Common Issues and Solutions

| Issue | Likely Cause | Solution |
|-------|--------------|----------|
| High outlet H2S | Insufficient amine flow | Increase lean amine rate |
| High rich loading | Amine saturation | Increase stages or amine rate |
| No convergence | Missing specifications | Check all inlet streams are fully specified and flashed |
