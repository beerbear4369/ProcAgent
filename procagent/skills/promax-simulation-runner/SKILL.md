---
name: promax-simulation-runner
description: Run ProMax simulations and interpret results
---

# Simulation Runner Skill

Use this skill when running simulations and checking convergence in ProMax.

## Pre-Simulation Checklist

Before calling `run_simulation`, verify:

- [ ] All inlet streams have temperature defined
- [ ] All inlet streams have pressure defined
- [ ] All inlet streams have flow rate defined (molar or mass)
- [ ] All inlet stream compositions are set and sum to 1.0
- [ ] All inlet streams have been flashed
- [ ] Block connections are complete (streams connected to correct ports)

## Running the Simulation

```
result = mcp__promax__run_simulation()
```

## Interpreting Solver Status

| Status Code | Meaning | Action |
|-------------|---------|--------|
| ≥ 1 | Converged | Proceed to read results |
| 0 | Not converged | Check specifications |
| < 0 | Error | Check error messages |

## Convergence Troubleshooting

### "Not converged" - Common Causes

1. **Missing Specifications**
   - Check all inlet streams are fully specified
   - Verify each stream has T, P, flow, and composition

2. **Infeasible Conditions**
   - Check thermodynamic validity (e.g., liquid at too high temperature)
   - Verify pressure is sufficient for desired phase

3. **Missing Components**
   - Ensure all species in stream compositions are in the environment
   - Check component names match exactly

4. **Block Configuration**
   - Verify block type is appropriate for the operation
   - Check stage count is reasonable

### Quick Fixes

```
# Re-flash all inlet streams
for stream in inlet_streams:
    mcp__promax__flash_stream(stream_name=stream)

# Then retry simulation
mcp__promax__run_simulation()
```

## Reading Results

After successful convergence:

```
results = mcp__promax__get_results(
    stream_names=["Treated_Gas", "Rich_Amine"]
)
```

Returns for each stream:
- temperature_c
- pressure_kpa
- molar_flow_kmol_hr

## Result Comparison Workflow

1. **Get outlet stream results**
   ```
   results = mcp__promax__get_results(stream_names=["Treated_Gas"])
   ```

2. **Compare to targets**
   ```python
   targets = {
       "Offgas H2S": {"value": 100, "unit": "ppm", "comparison": "le"},
       "Rich Amine Loading": {"value": 0.45, "unit": "mol/mol", "comparison": "le"}
   }
   ```

3. **Calculate deviation**
   ```python
   deviation = actual - target
   deviation_percent = (deviation / target) * 100
   ```

4. **Generate assessment**
   - PASS: actual meets target criteria
   - FAIL: actual exceeds target criteria

## Suggesting Adjustments

When targets are not met, suggest:

| Failed Target | Suggested Adjustment | Rationale |
|---------------|---------------------|-----------|
| High outlet H2S | Increase amine flow rate | More amine absorbs more H2S |
| High outlet H2S | Lower lean amine loading | More absorption capacity |
| High rich loading | Increase amine flow rate | Distribute loading across more amine |
| High outlet CO2 | Add more stages | More contact time for absorption |

## Example: Complete Simulation Workflow

```
# 1. Run simulation
result = mcp__promax__run_simulation()

# 2. Check convergence
if "converged" in result.lower():
    # 3. Get results
    results = mcp__promax__get_results(
        stream_names=["Treated_Gas", "Rich_Amine"]
    )

    # 4. Compare to targets
    # ... target comparison logic ...

    # 5. Report to user
    # "Simulation converged. Outlet H2S: 85 ppm (Target: ≤100 ppm) ✓"
else:
    # Handle non-convergence
    # "Simulation did not converge. Please check inlet specifications."
```
